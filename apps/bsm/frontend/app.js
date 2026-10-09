/**
 * QUANT BSM TERMINAL - Client Controller & Charting Engine
 * Gestion reactiva de terminal institucional y validacion econometrica.
 *
 * Notas de rendimiento:
 *  - Las peticiones independientes (cotizacion, historico, cadena) se lanzan en paralelo.
 *  - Los inputs que disparan calculos estan "debounced" y las respuestas obsoletas se descartan.
 *  - Los graficos se actualizan en sitio (sin destruir/recrear el canvas).
 *  - Cambiar CALL/PUT no hace ninguna peticion: el backend ya devuelve ambas curvas.
 */

// Estado global de la aplicacion
const AppState = {
    commodities: [],
    activeCommodityId: 'gold',
    activeOptionType: 'call',
    activeFilter: 'all',
    calcOptionType: 'call',
    activeExpiry: null,
    riskFreeRate: 0.040,
    quoteData: null,
    chainData: null,
    lastValuation: null,   // ultimo resultado de calculate_single_option (pestaña en vivo)
    lastCalc: null,        // ultimo resultado de la calculadora What-If
    lastEcon: null,        // ultimo resultado del validador econometrico
    tipsEnabled: true,
    charts: {},
    selectToken: 0,
    valSeq: 0,
    calcSeq: 0
};

// Fallback catalog en caso de conexion inicial antes de que pywebview este listo
const DEFAULT_COMMODITIES = [
    { id: "gold", name: "Oro (Gold) COMEX", ticker: "GC=F", option_ticker: "GLD", exchange: "CME / COMEX (USA)", unit: "USD/oz" },
    { id: "silver", name: "Plata (Silver) COMEX", ticker: "SI=F", option_ticker: "SLV", exchange: "CME / COMEX (USA)", unit: "USD/oz" },
    { id: "copper", name: "Cobre (Copper) COMEX", ticker: "HG=F", option_ticker: "CPER", exchange: "CME / COMEX (USA)", unit: "USD/lb" },
    { id: "wti", name: "Petróleo WTI (NYMEX)", ticker: "CL=F", option_ticker: "USO", exchange: "NYMEX / CME (USA)", unit: "USD/barril" },
    { id: "brent", name: "Petróleo Brent (ICE Europe)", ticker: "BZ=F", option_ticker: "BNO", exchange: "ICE Futures Europe", unit: "USD/barril" },
    { id: "natgas", name: "Gas Natural Henry Hub", ticker: "NG=F", option_ticker: "UNG", exchange: "NYMEX / CME (USA)", unit: "USD/MMBtu" },
    { id: "corn", name: "Maíz (Corn) CBOT", ticker: "ZC=F", option_ticker: "CORN", exchange: "CBOT / CME (USA)", unit: "US cent/bu" },
    { id: "soybeans", name: "Soja (Soybeans) CBOT", ticker: "ZS=F", option_ticker: "SOYB", exchange: "CBOT / CME (USA)", unit: "US cent/bu" },
    { id: "wheat", name: "Trigo (Wheat) CBOT", ticker: "ZW=F", option_ticker: "WEAT", exchange: "CBOT / CME (USA)", unit: "US cent/bu" },
    { id: "coffee", name: "Café Arábica (ICE US)", ticker: "KC=F", option_ticker: "JO", exchange: "ICE Futures US", unit: "US cent/lb" }
];

// ===================== UTILIDADES =====================

// Helper seguro para llamar a la API de PyWebView
async function callApi(methodName, ...args) {
    if (window.pywebview && window.pywebview.api && typeof window.pywebview.api[methodName] === 'function') {
        try {
            return await window.pywebview.api[methodName](...args);
        } catch (e) {
            console.error(`Error en API bridge [${methodName}]:`, e);
            return { status: 'error', message: e.toString() };
        }
    }
    // Si no esta cargado el bridge todavia, retornar null
    return null;
}

function hasBridge() {
    return !!(window.pywebview && window.pywebview.api);
}

function debounce(fn, ms) {
    let t;
    return (...args) => {
        clearTimeout(t);
        t = setTimeout(() => fn(...args), ms);
    };
}

const $ = (id) => document.getElementById(id);

/** Lee un input numerico respetando el 0 (el patron `|| default` convertia 0 en el valor por defecto). */
function num(id, fallback) {
    const v = parseFloat($(id).value);
    return Number.isFinite(v) ? v : fallback;
}

/** Dias calendario hasta una fecha 'YYYY-MM-DD' (misma logica que el backend: fecha - hoy). */
function daysUntil(dateStr) {
    const t = new Date();
    const today = Date.UTC(t.getFullYear(), t.getMonth(), t.getDate());
    return Math.max(1, Math.round((Date.parse(dateStr) - today) / 86400000));
}

/** Fecha local 'YYYY-MM-DD' (toISOString devolveria la fecha UTC, que puede ser el dia siguiente de noche). */
function localISODate(d) {
    const p = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

function toast(message) {
    let el = $('appToast');
    if (!el) {
        el = document.createElement('div');
        el.id = 'appToast';
        el.className = 'toast';
        el.setAttribute('role', 'alert');
        document.body.appendChild(el);
    }
    el.textContent = message;
    el.classList.add('visible');
    clearTimeout(toast._t);
    toast._t = setTimeout(() => el.classList.remove('visible'), 5000);
}

const GRID_COLOR = 'rgba(255, 255, 255, 0.05)';
const axisTicks = (size = 9, mono = false) => ({ color: '#64748B', font: mono ? { size, family: 'JetBrains Mono' } : { size } });
const legendOpts = (size = 10) => ({ labels: { color: '#94A3B8', font: { size } } });

/** Crea el grafico la primera vez y, en las siguientes, solo reemplaza sus datos (mucho mas barato). */
function upsertChart(key, canvasId, config) {
    const existing = AppState.charts[key];
    if (existing) {
        existing.data.labels = config.data.labels;
        existing.data.datasets = config.data.datasets;
        existing.update('none');
        return existing;
    }
    const canvas = $(canvasId);
    if (!canvas || typeof Chart === 'undefined') return null;
    AppState.charts[key] = new Chart(canvas.getContext('2d'), config);
    return AppState.charts[key];
}

// ===================== INICIALIZACION =====================
let appStarted = false;

function startApp() {
    if (appStarted) return;
    appStarted = true;
    initApp();
}

document.addEventListener('DOMContentLoaded', () => {
    setupTips();
    setupNavigation();
    setupEventListeners();
    setupCalculatorListeners();
    renderGlossary();
    TipEngine.init();
    // Con el adaptador web el puente existe desde el principio; con PyWebView nativo se espera su evento.
    if (hasBridge()) startApp();
});

// Evento oficial de PyWebView cuando el puente nativo esta montado (startApp ignora llamadas repetidas)
window.addEventListener('pywebviewready', startApp);

async function initApp() {
    // 1. Cargar catalogo de commodities
    const res = await callApi('get_commodities');
    AppState.commodities = (res && res.status === 'success' && res.data) ? res.data : DEFAULT_COMMODITIES;

    renderCommodityStrip();
    populateEconometricDropdown();

    // 2. Calculadora what-if (no depende de la red: se pinta enseguida)
    runCalculator();

    // 3. Cargar commodity inicial
    await selectCommodity(AppState.activeCommodityId);

    // 4. Completar en segundo plano los precios de la cinta superior
    prefetchStripQuotes();
}

// ===================== AYUDA CONTEXTUAL =====================
function setupTips() {
    let saved = null;
    try { saved = localStorage.getItem('bsmTips'); } catch (e) { /* almacenamiento no disponible */ }
    AppState.tipsEnabled = saved !== 'off';

    const btn = $('btnToggleTips');
    const apply = () => {
        document.body.classList.toggle('tips-off', !AppState.tipsEnabled);
        btn.classList.toggle('active', AppState.tipsEnabled);
        btn.setAttribute('aria-pressed', String(AppState.tipsEnabled));
        if (!AppState.tipsEnabled) TipEngine.hide();
    };
    apply();
    btn.addEventListener('click', () => {
        AppState.tipsEnabled = !AppState.tipsEnabled;
        try { localStorage.setItem('bsmTips', AppState.tipsEnabled ? 'on' : 'off'); } catch (e) { /* ignorar */ }
        apply();
    });

    const search = $('glossarySearch');
    if (search) search.addEventListener('input', debounce(() => renderGlossary(search.value), 120));
}

// ===================== GESTION DE PESTAÑAS =====================
function setupNavigation() {
    const tabs = document.querySelectorAll('.nav-tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const targetId = tab.dataset.tab;
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            document.querySelectorAll('.tab-pane').forEach(pane => pane.classList.remove('active'));
            const targetPane = $(targetId);
            if (targetPane) targetPane.classList.add('active');

            // Redibujar graficos para ajustar dimensiones tras mostrarse el panel
            requestAnimationFrame(() => {
                Object.values(AppState.charts).forEach(c => c && c.resize && c.resize());
            });
        });
    });
}

// ===================== CINTA DE COMMODITIES =====================
function renderCommodityStrip() {
    const strip = $('commodityStrip');
    if (!strip) return;

    strip.innerHTML = '';
    AppState.commodities.forEach(comm => {
        const btn = document.createElement('button');
        btn.className = `commodity-pill-btn ${comm.id === AppState.activeCommodityId ? 'active' : ''}`;
        btn.id = `pill-${comm.id}`;
        btn.innerHTML = `
            <span class="font-bold text-white">${comm.name.split(' ')[0]}</span>
            <span class="pill-price" id="pill-price-${comm.id}">--</span>
            <span class="pill-change" id="pill-change-${comm.id}">--</span>
        `;
        btn.addEventListener('click', () => selectCommodity(comm.id));
        strip.appendChild(btn);
    });
}

function updatePill(quote) {
    const pillPrice = $(`pill-price-${quote.id}`);
    const pillChange = $(`pill-change-${quote.id}`);
    const isPos = quote.change >= 0;
    if (pillPrice) pillPrice.innerText = `$${quote.price?.toFixed(1)}`;
    if (pillChange) {
        pillChange.innerText = `${isPos ? '+' : ''}${quote.change_pct?.toFixed(1)}%`;
        pillChange.className = `pill-change ${isPos ? 'positive' : 'negative'}`;
    }
}

/** Carga, de a una y sin competir con la accion del usuario, las cotizaciones del resto de la cinta. */
async function prefetchStripQuotes() {
    for (const comm of AppState.commodities) {
        if (comm.id === AppState.activeCommodityId) continue;
        const pill = $(`pill-price-${comm.id}`);
        if (!pill || pill.innerText !== '--') continue;
        const res = await callApi('get_quote', comm.id);
        if (res && res.status === 'success' && res.data && res.data.price) updatePill(res.data);
        await new Promise(r => setTimeout(r, 250));
    }
}

// ===================== SELECCION DE COMMODITY ACTIVO =====================
async function selectCommodity(commId) {
    const token = ++AppState.selectToken;
    AppState.activeCommodityId = commId;
    AppState.chainData = null;

    document.querySelectorAll('.commodity-pill-btn').forEach(btn => btn.classList.remove('active'));
    const activePill = $(`pill-${commId}`);
    if (activePill) activePill.classList.add('active');

    // Cotizacion, historico y cadena son independientes: se piden en paralelo.
    const [qRes] = await Promise.all([
        callApi('get_quote', commId),
        loadUnderlyingHistoryChart(commId, token),
        loadOptionsChain(commId, null, { resetStrike: true, token })
    ]);

    if (token !== AppState.selectToken) return; // el usuario ya eligio otro commodity

    if (qRes && qRes.status === 'success' && qRes.data) {
        AppState.quoteData = qRes.data;
        updateQuoteUI(qRes.data);
    }

    // Sin cadena disponible: usar el precio del futuro como strike inicial
    if (!AppState.chainData && AppState.quoteData && AppState.quoteData.price) {
        $('inputStrike').value = Math.round(AppState.quoteData.price);
        recalculateValuation();
    }
}

function updateQuoteUI(quote) {
    $('activeCommExchange').innerText = quote.exchange || 'MERCADO OFICIAL';
    $('activeCommName').innerText = quote.name || 'Commodity';
    $('activeCommTicker').innerText = `${quote.ticker} | Unidad: ${quote.unit}`;
    $('activeCommPrice').innerText = `$${quote.price?.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

    const changeEl = $('activeCommChange');
    const isPos = (quote.change >= 0);
    changeEl.innerText = `${isPos ? '+' : ''}${quote.change?.toFixed(2)} (${isPos ? '+' : ''}${quote.change_pct?.toFixed(2)}%)`;
    changeEl.className = `text-sm font-mono font-semibold ${isPos ? 'text-emerald-400' : 'text-rose-400'}`;

    $('activeCommHighLow').innerText = `$${quote.low_day?.toFixed(2)} - $${quote.high_day?.toFixed(2)}`;
    $('activeCommVolume').innerText = quote.volume?.toLocaleString('en-US') || '--';
    $('activeCommUnit').innerText = quote.unit || 'USD';
    const updated = $('activeCommUpdated');
    updated.innerText = quote.last_update || 'Reciente';
    updated.style.color = quote.is_offline ? '#F59E0B' : '';

    // Volatilidades
    $('volGarmanKlass').innerText = `${quote.vol_garman_klass_pct?.toFixed(1)}%`;
    $('volParkinson').innerText = `${quote.vol_parkinson_pct?.toFixed(1)}%`;
    $('volRealized').innerText = `${quote.vol_realized_pct?.toFixed(1)}%`;

    // Tasa libre de riesgo en el header
    if (quote.risk_free_rate) {
        AppState.riskFreeRate = quote.risk_free_rate / 100.0;
        $('headerRiskFreeRate').innerText = `${quote.risk_free_rate.toFixed(2)}%`;
    }

    updatePill(quote);
}

// ===================== HISTORICO DEL ACTIVO =====================
async function loadUnderlyingHistoryChart(commId, token) {
    const res = await callApi('get_historical_series', commId, '1y');
    if (token !== undefined && token !== AppState.selectToken) return;
    if (!res || res.status !== 'success' || !res.data) return;

    const { dates, prices } = res.data;
    upsertChart('underlying', 'chartUnderlyingHistory', {
        type: 'line',
        data: {
            labels: dates,
            datasets: [{
                data: prices,
                borderColor: '#06B6D4',
                borderWidth: 2,
                pointRadius: 0,
                fill: true,
                backgroundColor: 'rgba(6, 182, 212, 0.08)',
                tension: 0.1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false }, tooltip: { mode: 'index', intersect: false } },
            scales: {
                x: { display: false },
                y: { grid: { color: GRID_COLOR }, ticks: axisTicks(9, true) }
            }
        }
    });
}

// ===================== CADENA DE OPCIONES =====================
async function loadOptionsChain(commId, expiry = null, { resetStrike = false, token } = {}) {
    const res = await callApi('get_options_chain', commId, expiry);
    if (token !== undefined && token !== AppState.selectToken) return;
    if (!res || res.status !== 'success' || !res.data || res.data.error) {
        $('chainSourceBanner').innerHTML = '';
        if (res && res.data && res.data.error) toast(res.data.error);
        return;
    }

    const chain = res.data;
    AppState.chainData = chain;
    AppState.activeExpiry = chain.current_expiration;

    // Selector de vencimientos
    const expirySelect = $('selectExpiry');
    expirySelect.innerHTML = '';
    (chain.expirations || []).forEach(exp => {
        const opt = document.createElement('option');
        opt.value = exp;
        opt.innerText = `${exp} (${daysUntil(exp)} días)`;
        if (exp === chain.current_expiration) opt.selected = true;
        expirySelect.appendChild(opt);
    });

    if (resetStrike) {
        // El modelo correcto depende del subyacente de la cadena (ETF -> BSM, futuro -> Black-76)
        if (chain.model) $('selectModel').value = chain.model;
        const atm = nearestStrike(chain, chain.spot_price);
        if (atm !== null) $('inputStrike').value = atm;
    }

    renderChainBanners(chain);
    renderOptionsTable(chain);
    recalculateValuation();
}

function allStrikes(chain) {
    return [...new Set([...(chain.calls || []), ...(chain.puts || [])].map(c => c.strike))].sort((a, b) => a - b);
}

function nearestStrike(chain, target) {
    const strikes = allStrikes(chain);
    if (!strikes.length) return null;
    return strikes.reduce((best, k) => Math.abs(k - target) < Math.abs(best - target) ? k : best, strikes[0]);
}

function renderChainBanners(chain) {
    const money = (x) => `$${Number(x).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    const modelName = chain.model === 'black76' ? 'Black-76' : 'Black-Scholes-Merton';
    const volName = chain.vol_estimator === 'close_to_close' ? 'Close-to-Close' : 'Garman-Klass';
    const ub = $('underlyingBanner');
    const cb = $('chainSourceBanner');

    if (chain.is_synthetic) {
        ub.innerHTML = `<span class="src-badge src-synth">Cadena simulada</span>Valoración sobre el futuro <b>${chain.underlying_ticker}</b> (F = <b>${money(chain.spot_price)}</b>) · modelo <b>${modelName}</b> · σ ${volName} <b>${chain.historical_vol_pct.toFixed(1)}%</b> · vence <b>${chain.current_expiration}</b> (${chain.days_to_expiry} días)`;
        cb.className = 'chain-banner synthetic';
        cb.innerHTML = `<span class="src-badge src-synth">Simulada</span>No hay cadena de opciones disponible para este activo. Los precios de mercado, la IV y las griegas de la tabla se <b>generan con ${modelName}</b> sobre el futuro y una sonrisa de volatilidad sintética: no son cotizaciones reales. Volumen y Open Interest no existen en una simulación.`;
    } else {
        ub.innerHTML = `<span class="src-badge src-live">Opciones reales</span>Valoración sobre <b>${chain.underlying_ticker}</b> (ETF, spot = <b>${money(chain.spot_price)}</b>) · modelo <b>${modelName}</b> · σ ${volName} <b>${chain.historical_vol_pct.toFixed(1)}%</b> · vence <b>${chain.current_expiration}</b> (${chain.days_to_expiry} días)`;
        cb.className = 'chain-banner';
        cb.innerHTML = `<span class="src-badge src-live">Datos reales</span>Opciones del ETF <b>${chain.underlying_ticker}</b>: los strikes están en dólares del ETF, no del futuro ${AppState.quoteData ? AppState.quoteData.ticker : ''}. Valuadas con ${modelName} sobre el precio del ETF.`;
    }
}

// ===================== VALORACION =====================
/** Precio de mercado del contrato cuyo strike coincide con K (no existe precio para un strike no listado). */
function findMarketPrice(list, K, S) {
    let best = null, bestDist = Infinity;
    for (const it of list || []) {
        const d = Math.abs(it.strike - K);
        if (d < bestDist) { best = it; bestDist = d; }
    }
    if (!best || bestDist > Math.max(1e-6, 0.0005 * S)) return 0.0;
    return best.mid || best.last || 0.0;
}

async function recalculateValuation() {
    const seq = ++AppState.valSeq;
    const chain = AppState.chainData;
    const quote = AppState.quoteData;

    // El subyacente y la volatilidad deben ser los de la cadena mostrada (ETF o futuro), no mezclados
    const S = chain ? chain.spot_price : (quote ? quote.price : 100.0);
    const vol = chain ? chain.historical_vol_pct : (quote ? (quote.vol_garman_klass_pct || 20.0) : 20.0);
    const days = chain ? chain.days_to_expiry : daysUntil($('selectExpiry').value || localISODate(new Date()));
    const K = num('inputStrike', S);
    const model = $('selectModel').value;

    const params = {
        underlying_price: S,
        strike: K,
        days_to_expiry: days,
        risk_free_rate: AppState.riskFreeRate * 100.0,
        volatility: vol,
        dividend_yield: 0.0,
        model: model,
        option_type: AppState.activeOptionType,
        call_market_price: chain ? findMarketPrice(chain.calls, K, S) : 0.0,
        put_market_price: chain ? findMarketPrice(chain.puts, K, S) : 0.0
    };

    const res = await callApi('calculate_single_option', params);
    if (seq !== AppState.valSeq) return; // llego una respuesta mas nueva: esta ya no sirve
    if (!res || res.status !== 'success' || !res.data) {
        if (res && res.message) toast(`No se pudo calcular la valoración: ${res.message}`);
        return;
    }

    AppState.lastValuation = res.data;
    updateValuationUI(res.data);
}

const debouncedRecalc = debounce(recalculateValuation, 180);

function setText(id, text) { $(id).innerText = text; }

function fillOptionCard(prefix, o) {
    setText(`${prefix}FairPrice`, `$${o.fair_premium.toFixed(4)}`);
    setText(`${prefix}MarketPrice`, o.has_market_price ? `$${o.market_price.toFixed(2)}` : '--');

    const diffEl = $(`${prefix}DiffText`);
    diffEl.innerText = o.has_market_price
        ? `Dif: ${o.diff_amount >= 0 ? '+' : ''}$${o.diff_amount.toFixed(2)} (${o.diff_pct >= 0 ? '+' : ''}${o.diff_pct.toFixed(1)}%)`
        : 'Sin cotización para este strike';
    diffEl.style.color = o.status_color;

    const badge = $(`${prefix}StatusBadge`);
    badge.innerText = o.valuation_status;
    badge.style.color = o.status_color;
    badge.style.borderColor = o.status_color;

    setText(`${prefix}Intrinsic`, `$${o.intrinsic_value.toFixed(2)}`);
    setText(`${prefix}TimeValue`, `$${o.time_value.toFixed(2)}`);
    setText(`${prefix}IV`, o.implied_volatility_pct ? `${o.implied_volatility_pct.toFixed(1)}%` : '--');
    setText(`${prefix}PoP`, `${o.prob_itm_pct.toFixed(1)}%`);
    setText(`${prefix}BreakEven`, `$${o.break_even.toFixed(2)}`);

    const g = o.greeks;
    setText(`${prefix}Delta`, `${g.delta >= 0 ? '+' : ''}${g.delta.toFixed(3)}`);
    setText(`${prefix}Gamma`, `+${g.gamma.toFixed(4)}`);
    setText(`${prefix}Vega`, `$${g.vega.toFixed(3)}`);
    setText(`${prefix}Theta`, `${g.theta < 0 ? '-' : ''}$${Math.abs(g.theta).toFixed(3)}`);
    setText(`${prefix}Rho`, `${g.rho >= 0 ? '+' : '-'}$${Math.abs(g.rho).toFixed(3)}`);
    setText(`${prefix}D1`, g.d1.toFixed(3));
    setText(`${prefix}D2`, g.d2.toFixed(3));
}

function updateValuationUI(data) {
    const { call, put, put_call_parity } = data;

    if (call) fillOptionCard('call', call);
    if (put) fillOptionCard('put', put);

    if (put_call_parity) {
        setText('parityObservedDiff', `$${put_call_parity.observed_diff.toFixed(2)}`);
        setText('parityTargetDiff', `$${put_call_parity.target_diff.toFixed(2)}`);
        const parityBadge = $('parityStatusBadge');
        if (put_call_parity.is_satisfied) {
            parityBadge.innerText = `✓ Paridad Exacta (Discrepancia: ${put_call_parity.discrepancy.toFixed(6)})`;
            parityBadge.className = 'text-emerald-400 font-bold';
        } else {
            parityBadge.innerText = `Discrepancia: ${put_call_parity.discrepancy.toFixed(4)}`;
            parityBadge.className = 'text-amber-400 font-bold';
        }
    }

    renderActivePayoff();
}

/** Redibuja el payoff del lado activo con los datos ya calculados (cambiar CALL/PUT no requiere red). */
function renderActivePayoff() {
    const data = AppState.lastValuation;
    if (!data) return;
    const isCall = AppState.activeOptionType === 'call';
    const active = isCall ? data.call : data.put;
    setText('payoffChartSubtitle', `P&L = Valor Intrínseco - Prima Justa ($${active ? active.fair_premium.toFixed(2) : '0.00'})`);

    const c = data.payoff_curve;
    renderPayoffChart('payoff', 'chartPayoff', c.spots,
        isCall ? c.call_expiry_pnl : c.put_expiry_pnl,
        isCall ? c.call_today_val : c.put_today_val,
        isCall);
}

function renderPayoffChart(key, canvasId, spots, expiryPnl, todayVal, isCall) {
    const mainColor = isCall ? '#10B981' : '#F43F5E';
    const side = isCall ? 'CALL' : 'PUT';
    upsertChart(key, canvasId, {
        type: 'line',
        data: {
            labels: spots,
            datasets: [
                {
                    label: `Payoff al Vencimiento ${side} (T=0)`,
                    data: expiryPnl,
                    borderColor: mainColor,
                    borderWidth: 2.5,
                    pointRadius: 0,
                    tension: 0
                },
                {
                    label: 'Valor Teórico Justo Hoy (t=0)',
                    data: todayVal,
                    borderColor: '#38BDF8',
                    borderWidth: 1.5,
                    borderDash: [5, 5],
                    pointRadius: 0,
                    tension: 0.2
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { labels: { color: '#94A3B8', font: { family: 'Plus Jakarta Sans', size: 10 } } },
                tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: $${ctx.parsed.y.toFixed(2)}` } }
            },
            scales: {
                x: { grid: { color: GRID_COLOR }, ticks: axisTicks(9, true) },
                y: { grid: { color: GRID_COLOR }, ticks: { ...axisTicks(9, true), callback: (v) => `$${v}` } }
            }
        }
    });
}

// ===================== TABLA DE LA CADENA =====================
function renderOptionsTable(chainData) {
    const tbody = $('optionsTableBody');
    if (!tbody) return;

    const filter = AppState.activeFilter || 'all';
    const contracts = [];
    if (filter === 'all' || filter === 'calls') contracts.push(...(chainData.calls || []).map(c => ({ ...c, type: 'CALL' })));
    if (filter === 'all' || filter === 'puts') contracts.push(...(chainData.puts || []).map(p => ({ ...p, type: 'PUT' })));
    contracts.sort((a, b) => a.strike - b.strike || a.type.localeCompare(b.type));

    if (contracts.length === 0) {
        tbody.innerHTML = '<tr><td colspan="14" class="text-center py-6 text-slate-500">No hay contratos para el filtro seleccionado</td></tr>';
        return;
    }

    const fmtInt = (v) => (v === null || v === undefined) ? '--' : v.toLocaleString();
    const rows = contracts.map(item => {
        const isCall = item.type === 'CALL';
        const statusText = item.fair_status || item.recommendation || 'En Paridad';
        return `<tr data-strike="${item.strike}" data-type="${item.type}" style="cursor:pointer">
            <td><span class="${isCall ? 'badge-call' : 'badge-put'}">${item.type}</span></td>
            <td class="font-bold text-white">$${item.strike.toFixed(1)}</td>
            <td>$${item.bid.toFixed(2)}</td>
            <td>$${item.ask.toFixed(2)}</td>
            <td class="font-bold text-cyan-300">$${item.mid.toFixed(2)}</td>
            <td class="text-emerald-400 font-bold">$${item.theoretical.toFixed(2)}</td>
            <td class="font-bold" style="color: ${item.rec_color || '#FFFFFF'}">${item.edge_pct >= 0 ? '+' : ''}${item.edge_pct.toFixed(1)}%</td>
            <td class="text-amber-400">${item.iv_pct ? item.iv_pct.toFixed(1) + '%' : '--'}</td>
            <td class="${item.delta >= 0 ? 'text-emerald-400' : 'text-rose-400'}">${item.delta.toFixed(2)}</td>
            <td class="text-slate-400">${item.gamma.toFixed(3)}</td>
            <td class="text-rose-400">${item.theta.toFixed(2)}</td>
            <td class="text-slate-300">${fmtInt(item.volume)}</td>
            <td class="text-slate-400">${fmtInt(item.open_interest)}</td>
            <td><span style="color: ${item.rec_color || '#94A3B8'}; font-size: 0.72rem; font-weight: 700;">${statusText}</span></td>
        </tr>`;
    });
    tbody.innerHTML = rows.join('');
}

// ===================== EVENT LISTENERS (TERMINAL EN VIVO) =====================
function setActiveType(type) {
    AppState.activeOptionType = type;
    $('btnToggleCall').classList.toggle('active', type === 'call');
    $('btnTogglePut').classList.toggle('active', type === 'put');
}

function setupEventListeners() {
    // Toggle Call / Put: el backend ya devolvio ambas curvas, solo se redibuja
    $('btnToggleCall').addEventListener('click', () => { setActiveType('call'); renderActivePayoff(); });
    $('btnTogglePut').addEventListener('click', () => { setActiveType('put'); renderActivePayoff(); });

    // Cambios en inputs y selects
    $('selectModel').addEventListener('change', recalculateValuation);
    $('inputStrike').addEventListener('input', debouncedRecalc);
    $('selectExpiry').addEventListener('change', async () => {
        // Un vencimiento distinto implica otra cadena (strikes, precios e IV cambian)
        await loadOptionsChain(AppState.activeCommodityId, $('selectExpiry').value, { token: AppState.selectToken });
    });

    // Refresh quote
    $('btnRefreshQuote').addEventListener('click', () => selectCommodity(AppState.activeCommodityId));

    // Filtros de tabla
    $('btnFilterAll').addEventListener('click', (e) => setTableFilter('all', e.target));
    $('btnFilterCalls').addEventListener('click', (e) => setTableFilter('calls', e.target));
    $('btnFilterPuts').addEventListener('click', (e) => setTableFilter('puts', e.target));

    // Click en una fila: carga ese strike y tipo en el panel de valoracion (delegacion de eventos)
    $('optionsTableBody').addEventListener('click', (e) => {
        const tr = e.target.closest('tr[data-strike]');
        if (!tr) return;
        $('inputStrike').value = tr.dataset.strike;
        setActiveType(tr.dataset.type === 'CALL' ? 'call' : 'put');
        recalculateValuation();
        $('tab-live').querySelector('.panel-valuation').scrollIntoView({ behavior: 'smooth', block: 'start' });
    });

    // Test Econometrico
    $('btnRunEconTest').addEventListener('click', runEconometricValidation);

    // Quick date presets en el validador econometrico
    document.querySelectorAll('.date-preset').forEach(btn => {
        btn.addEventListener('click', () => {
            const d = new Date();
            d.setDate(d.getDate() - parseInt(btn.dataset.days, 10));
            $('econTargetDate').value = localISODate(d);
        });
    });
}

function setTableFilter(filter, targetBtn) {
    AppState.activeFilter = filter;
    document.querySelectorAll('#btnFilterAll, #btnFilterCalls, #btnFilterPuts').forEach(b => b.classList.remove('active'));
    targetBtn.classList.add('active');
    if (AppState.chainData) renderOptionsTable(AppState.chainData);
}

// ==================== TAB 2: VALIDADOR ECONOMETRICO ====================
function populateEconometricDropdown() {
    const sel = $('econCommSelect');
    if (!sel) return;
    sel.innerHTML = '';
    AppState.commodities.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c.id;
        opt.innerText = c.name;
        sel.appendChild(opt);
    });

    // Fecha por defecto: 90 dias atras
    const d = new Date();
    d.setDate(d.getDate() - 90);
    $('econTargetDate').value = localISODate(d);
}

const RUN_ICON = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>';

async function runEconometricValidation() {
    const btn = $('btnRunEconTest');
    btn.disabled = true;
    btn.innerHTML = `
        <svg class="animate-spin" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 2a10 10 0 0 1 10 10"/></svg>
        CALCULANDO RESIDUOS Y DIAGNÓSTICOS...
    `;

    const params = {
        commodity_id: $('econCommSelect').value,
        target_date: $('econTargetDate').value,
        option_type: $('econOptionType').value,
        moneyness: parseFloat($('econMoneyness').value),
        horizon_days: parseInt($('econHorizonDays').value, 10),
        window_days: parseInt($('econWindowDays').value, 10),
        vol_estimator: $('econVolEstimator').value,
        model: $('econModel').value
    };

    const res = await callApi('run_econometric_backtest', params);
    btn.disabled = false;
    btn.innerHTML = `${RUN_ICON} EJECUTAR VALIDACIÓN ECONOMÉTRICA HISTÓRICA`;

    if (!res || res.status !== 'success' || !res.data) {
        toast(res?.message || 'Error al ejecutar el test econométrico. Verifique las fechas seleccionadas.');
        return;
    }

    AppState.lastEcon = res.data;
    displayEconometricResults(res.data);
}

function displayEconometricResults(data) {
    const sec = $('econResultsSection');
    sec.style.display = 'block';
    sec.scrollIntoView({ behavior: 'smooth' });

    // PASO 1: ESTIMACION EN t0
    setText('econAuditDateT0', `Fecha t₀: ${data.target_date}`);
    setText('econAuditPriceT0', `$${data.underlying_at_t0.toFixed(2)}`);
    setText('econAuditStrikeK', `$${data.strike_K.toFixed(2)}`);
    setText('econAuditSigma', `${data.sigma_hat_pct.toFixed(2)}% (${data.vol_estimator})`);
    setText('econAuditRate', `${data.risk_free_rate_pct.toFixed(2)}%`);
    setText('econAuditTheoPrice', `$${data.theoretical_price_t0.toFixed(4)}`);

    // PASO 2: REALIDAD Y ERROR PUNTUAL
    setText('econAuditPriceST', `$${data.terminal_price_ST.toFixed(2)}`);
    setText('econAuditPayoffTerm', `$${data.payoff_terminal.toFixed(4)}`);
    setText('econAuditDiscountedPayoff', `$${data.realized_discounted_payoff.toFixed(4)}`);

    const pctErrEl = $('econAuditPctError');
    pctErrEl.innerText = `${data.punctual_pct_error >= 0 ? '+' : ''}${data.punctual_pct_error.toFixed(2)}%`;
    pctErrEl.style.color = (Math.abs(data.punctual_pct_error) < 10) ? '#10B981' : '#F43F5E';

    const punctErrEl = $('econAuditPunctualError');
    punctErrEl.innerText = `${data.punctual_error >= 0 ? '+' : ''}$${data.punctual_error.toFixed(4)}`;
    punctErrEl.style.color = (Math.abs(data.punctual_error) < 1.0) ? '#10B981' : '#F43F5E';

    // BATERIA DE DIAGNOSTICOS
    const diag = data.rolling_diagnostics;
    setText('econSampleSizeBadge', `Muestra rodante: ${diag.sample_points} puntos · horizonte ${data.horizon_days} días calendario`);

    setText('diagRMSE', `$${diag.rmse.toFixed(4)}`);
    setText('diagMAE', `$${diag.mae.toFixed(4)}`);
    setText('diagMAPE', `${(diag.mape ?? 0).toFixed(2)}%`);

    const biasEl = $('diagMeanBias');
    biasEl.innerText = `${diag.mean_bias >= 0 ? '+' : ''}${diag.mean_bias.toFixed(4)}`;
    biasEl.style.color = (diag.mean_bias < 0) ? '#F43F5E' : '#10B981';

    setText('diagBiasLabel', (diag.mean_bias < 0)
        ? 'El modelo sobrevalora la opción (sesgo negativo)'
        : 'El modelo subvalora la opción (sesgo positivo)');

    setText('diagJBStat', `JB: ${diag.jarque_bera_stat.toFixed(2)}`);
    const jbEl = $('diagJBPval');
    jbEl.innerText = `p-valor: ${diag.jarque_bera_pvalue.toFixed(4)} (${diag.is_normal ? 'Normalidad aceptada' : 'Normalidad rechazada - Colas pesadas'})`;
    jbEl.style.color = diag.is_normal ? '#10B981' : '#F43F5E';

    setText('diagSkewKurt', `S: ${diag.skewness.toFixed(2)} | K: ${diag.kurtosis.toFixed(2)}`);
    setText('diagDW', `DW: ${diag.durbin_watson.toFixed(2)}`);
    setText('diagDWStatus', diag.autocorrelation_status || '');

    // GRAFICOS ECONOMETRICOS
    renderEconPathChart(data.path_dates, data.path_prices, data.strike_K);
    renderEconHistChart(diag.hist_labels || [], diag.hist_counts || [], diag.hist_normal_fit || []);
    renderEconSeriesChart(diag.dates, diag.theor_series, diag.real_series);
}

const baseLineOptions = (monoY = true) => ({
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: legendOpts() },
    scales: {
        x: { grid: { color: GRID_COLOR }, ticks: axisTicks(9) },
        y: { grid: { color: GRID_COLOR }, ticks: axisTicks(9, monoY) }
    }
});

function renderEconPathChart(dates, prices, strike) {
    upsertChart('econPath', 'chartEconPath', {
        type: 'line',
        data: {
            labels: dates,
            datasets: [
                {
                    label: 'Precio Real del Commodity',
                    data: prices,
                    borderColor: '#06B6D4',
                    borderWidth: 2,
                    pointRadius: 2,
                    backgroundColor: 'rgba(6, 182, 212, 0.1)',
                    fill: true
                },
                {
                    label: `Strike K ($${strike.toFixed(2)})`,
                    data: new Array(dates.length).fill(strike),
                    borderColor: '#F59E0B',
                    borderWidth: 1.5,
                    borderDash: [6, 4],
                    pointRadius: 0
                }
            ]
        },
        options: baseLineOptions()
    });
}

function renderEconHistChart(bins, counts, normalCurve) {
    upsertChart('econHist', 'chartEconHist', {
        data: {
            labels: bins,
            datasets: [
                {
                    type: 'bar',
                    label: 'Frecuencia de Residuos eₜ',
                    data: counts,
                    backgroundColor: 'rgba(139, 92, 246, 0.5)',
                    borderColor: '#8B5CF6',
                    borderWidth: 1
                },
                {
                    type: 'line',
                    label: 'Campana Normal Gaussiana',
                    data: normalCurve,
                    borderColor: '#F43F5E',
                    borderWidth: 2,
                    pointRadius: 0,
                    tension: 0.3
                }
            ]
        },
        options: baseLineOptions(false)
    });
}

function renderEconSeriesChart(dates, theor, real) {
    upsertChart('econSeries', 'chartEconSeries', {
        type: 'line',
        data: {
            labels: dates,
            datasets: [
                { label: 'Valor Teórico BSM/Black-76', data: theor, borderColor: '#06B6D4', borderWidth: 2, pointRadius: 0 },
                { label: 'Payoff Realizado Descontado', data: real, borderColor: '#10B981', borderWidth: 2, pointRadius: 0 }
            ]
        },
        options: baseLineOptions()
    });
}

// ==================== TAB 3: CALCULADORA WHAT-IF ====================
function setupCalculatorListeners() {
    const inputs = ['calcInputS', 'calcInputK', 'calcInputDays', 'calcInputVol', 'calcInputRate', 'calcInputModel', 'calcInputMktCall', 'calcInputMktPut'];
    const run = debounce(runCalculator, 150);
    inputs.forEach(id => {
        const el = $(id);
        if (el) {
            el.addEventListener('input', run);
            el.addEventListener('change', run);
        }
    });

    $('calcToggleCall').addEventListener('click', () => { setCalcType('call'); renderCalcPayoff(); });
    $('calcTogglePut').addEventListener('click', () => { setCalcType('put'); renderCalcPayoff(); });
}

function setCalcType(type) {
    AppState.calcOptionType = type;
    $('calcToggleCall').classList.toggle('active', type === 'call');
    $('calcTogglePut').classList.toggle('active', type === 'put');
}

async function runCalculator() {
    const seq = ++AppState.calcSeq;

    // Un solo pedido: el backend devuelve call y put juntos (antes eran dos pedidos, y cada uno recalculaba ambos)
    const res = await callApi('calculate_single_option', {
        underlying_price: num('calcInputS', 100.0),
        strike: num('calcInputK', 100.0),
        days_to_expiry: num('calcInputDays', 30.0),
        volatility: num('calcInputVol', 20.0),
        risk_free_rate: num('calcInputRate', 4.0),
        dividend_yield: 0.0,
        model: $('calcInputModel').value,
        option_type: AppState.calcOptionType,
        call_market_price: Math.max(0, num('calcInputMktCall', 0.0)),
        put_market_price: Math.max(0, num('calcInputMktPut', 0.0))
    });

    if (seq !== AppState.calcSeq) return;
    if (!res || res.status !== 'success' || !res.data) return;

    const d = res.data;
    AppState.lastCalc = d;

    [['Call', d.call], ['Put', d.put]].forEach(([label, o]) => {
        setText(`calc${label}Price`, `$${o.fair_premium.toFixed(3)}`);
        setText(`calc${label}Delta`, o.greeks.delta.toFixed(3));
        setText(`calc${label}Gamma`, o.greeks.gamma.toFixed(4));
        setText(`calc${label}Vega`, `$${o.greeks.vega.toFixed(3)}`);
        setText(`calc${label}Theta`, `$${o.greeks.theta.toFixed(3)}`);
        setText(`calc${label}Rho`, `$${o.greeks.rho.toFixed(3)}`);
        setText(`calc${label}IV`, o.implied_volatility_pct ? `${o.implied_volatility_pct.toFixed(1)}%` : '--');
        setText(`calc${label}D1`, o.greeks.d1.toFixed(3));
        setText(`calc${label}D2`, o.greeks.d2.toFixed(3));
    });

    renderCalcPayoff();
}

function renderCalcPayoff() {
    const d = AppState.lastCalc;
    if (!d) return;
    const isCall = AppState.calcOptionType === 'call';
    const c = d.payoff_curve;
    renderPayoffChart('calcPayoff', 'chartCalcPayoff', c.spots,
        isCall ? c.call_expiry_pnl : c.put_expiry_pnl,
        isCall ? c.call_today_val : c.put_today_val,
        isCall);
}
