/**
 * QUANT BSM TERMINAL - Client Controller & Charting Engine
 * Gestion reactiva de terminal institucional y validacion econometrica.
 */

// Estado global de la aplicacion
const AppState = {
    commodities: [],
    activeCommodityId: 'gold',
    activeOptionType: 'call',
    activeExpiry: null,
    riskFreeRate: 0.040,
    quoteData: null,
    chainData: null,
    charts: {}
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

// INICIALIZACION AL CARGAR LA PAGINA
document.addEventListener('DOMContentLoaded', () => {
    setupNavigation();
    setupEventListeners();
    setupCalculatorListeners();
    initApp();
});

// Listener oficial del evento de PyWebView cuando el puente nativo esta montado
window.addEventListener('pywebviewready', () => {
    console.log("PyWebView Native Bridge conectado exitosamente.");
    initApp();
});

async function initApp() {
    // 1. Cargar catalogo de commodities
    const res = await callApi('get_commodities');
    if (res && res.status === 'success' && res.data) {
        AppState.commodities = res.data;
    } else {
        AppState.commodities = DEFAULT_COMMODITIES;
    }

    renderCommodityStrip();
    populateEconometricDropdown();
    
    // 2. Cargar commodity inicial
    await selectCommodity(AppState.activeCommodityId);

    // 3. Inicializar calculadora what-if
    runCalculator();
}

// GESTION DE PESTAÑAS
function setupNavigation() {
    const tabs = document.querySelectorAll('.nav-tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const targetId = tab.dataset.tab;
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            document.querySelectorAll('.tab-pane').forEach(pane => {
                pane.classList.remove('active');
            });
            const targetPane = document.getElementById(targetId);
            if (targetPane) {
                targetPane.classList.add('active');
            }

            // Redibujar graficos si es necesario para ajustar dimensiones
            setTimeout(() => {
                Object.values(AppState.charts).forEach(c => c && c.resize && c.resize());
            }, 100);
        });
    });
}

// RENDERIZADO DE LA CINTA RAPIDA DE COMMODITIES
function renderCommodityStrip() {
    const strip = document.getElementById('commodityStrip');
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

// SELECCION DE COMMODITY ACTIVO
async function selectCommodity(commId) {
    AppState.activeCommodityId = commId;

    // Actualizar estados visuales de la cinta
    document.querySelectorAll('.commodity-pill-btn').forEach(btn => btn.classList.remove('active'));
    const activePill = document.getElementById(`pill-${commId}`);
    if (activePill) activePill.classList.add('active');

    // 1. Obtener cotizacion en vivo
    const qRes = await callApi('get_quote', commId);
    if (qRes && qRes.status === 'success' && qRes.data) {
        AppState.quoteData = qRes.data;
        updateQuoteUI(qRes.data);
    }

    // 2. Obtener grafico historico del activo
    loadUnderlyingHistoryChart(commId);

    // 3. Cargar cadena de opciones
    await loadOptionsChain(commId);
}

// ACTUALIZAR UI DE COTIZACION EN VIVO
function updateQuoteUI(quote) {
    document.getElementById('activeCommExchange').innerText = quote.exchange || 'MERCADO OFICIAL';
    document.getElementById('activeCommName').innerText = quote.name || 'Commodity';
    document.getElementById('activeCommTicker').innerText = `${quote.ticker} | Unidad: ${quote.unit}`;
    document.getElementById('activeCommPrice').innerText = `$${quote.price?.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

    const changeEl = document.getElementById('activeCommChange');
    const isPos = (quote.change >= 0);
    changeEl.innerText = `${isPos ? '+' : ''}${quote.change?.toFixed(2)} (${isPos ? '+' : ''}${quote.change_pct?.toFixed(2)}%)`;
    changeEl.className = `text-sm font-mono font-semibold ${isPos ? 'text-emerald-400' : 'text-rose-400'}`;

    document.getElementById('activeCommHighLow').innerText = `$${quote.low_day?.toFixed(2)} - $${quote.high_day?.toFixed(2)}`;
    document.getElementById('activeCommVolume').innerText = quote.volume?.toLocaleString('en-US') || '--';
    document.getElementById('activeCommUnit').innerText = quote.unit || 'USD';
    document.getElementById('activeCommUpdated').innerText = quote.last_update || 'Reciente';

    // Volatilidades
    document.getElementById('volGarmanKlass').innerText = `${quote.vol_garman_klass_pct?.toFixed(1)}%`;
    document.getElementById('volParkinson').innerText = `${quote.vol_parkinson_pct?.toFixed(1)}%`;
    document.getElementById('volRealized').innerText = `${quote.vol_realized_pct?.toFixed(1)}%`;

    // Tasa libre de riesgo en el header
    if (quote.risk_free_rate) {
        AppState.riskFreeRate = quote.risk_free_rate / 100.0;
        document.getElementById('headerRiskFreeRate').innerText = `${quote.risk_free_rate.toFixed(2)}%`;
    }

    // Actualizar pill en la cinta
    const pillPrice = document.getElementById(`pill-price-${quote.id}`);
    const pillChange = document.getElementById(`pill-change-${quote.id}`);
    if (pillPrice) pillPrice.innerText = `$${quote.price?.toFixed(1)}`;
    if (pillChange) {
        pillChange.innerText = `${isPos ? '+' : ''}${quote.change_pct?.toFixed(1)}%`;
        pillChange.className = `pill-change ${isPos ? 'positive' : 'negative'}`;
    }

    // Actualizar input de Strike con el valor actual ATM
    const strikeInput = document.getElementById('inputStrike');
    if (strikeInput && quote.price) {
        strikeInput.value = Math.round(quote.price);
    }
}

// CARGAR HISTORICO DEL ACTIVO
async function loadUnderlyingHistoryChart(commId) {
    const res = await callApi('get_historical_series', commId, '1y');
    if (!res || res.status !== 'success' || !res.data) return;

    const ctx = document.getElementById('chartUnderlyingHistory').getContext('2d');
    const { dates, prices } = res.data;

    if (AppState.charts.underlying) {
        AppState.charts.underlying.destroy();
    }

    AppState.charts.underlying = new Chart(ctx, {
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
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#64748B', font: { size: 9, family: 'JetBrains Mono' } }
                }
            }
        }
    });
}

// CARGAR CADENA DE OPCIONES Y VENCIMIENTOS
async function loadOptionsChain(commId, expiry = null) {
    const res = await callApi('get_options_chain', commId, expiry);
    if (!res || res.status !== 'success' || !res.data) return;

    const chain = res.data;
    AppState.chainData = chain;

    // Actualizar selector de vencimientos
    const expirySelect = document.getElementById('selectExpiry');
    expirySelect.innerHTML = '';
    (chain.expirations || []).forEach(exp => {
        const opt = document.createElement('option');
        opt.value = exp;
        opt.innerText = `${exp} (${getDaysDiff(exp)} días)`;
        if (exp === chain.current_expiration) opt.selected = true;
        expirySelect.appendChild(opt);
    });

    AppState.activeExpiry = chain.current_expiration;

    // Renderizar tabla de la cadena
    renderOptionsTable(chain);

    // Ejecutar valoracion y recomendacion central
    recalculateValuation();
}

function getDaysDiff(dateStr) {
    const exp = new Date(dateStr);
    const today = new Date();
    const diffTime = exp - today;
    return Math.max(1, Math.ceil(diffTime / (1000 * 60 * 60 * 24)));
}

// RECALCULO DE VALORACION Y RECOMENDACION CENTRAL
async function recalculateValuation() {
    const S = AppState.quoteData ? AppState.quoteData.price : 100.0;
    const K = parseFloat(document.getElementById('inputStrike').value) || S;
    const model = document.getElementById('selectModel').value;
    const optionType = AppState.activeOptionType;
    const expiry = document.getElementById('selectExpiry').value;
    const daysToExpiry = getDaysDiff(expiry);
    const vol = AppState.quoteData ? (AppState.quoteData.vol_garman_klass_pct || 20.0) : 20.0;
    const r = AppState.riskFreeRate * 100.0;

    // Buscar precio de mercado en la cadena si existe ese strike
    let marketPrice = 0.0;
    if (AppState.chainData) {
        const sideList = (optionType === 'call') ? AppState.chainData.calls : AppState.chainData.puts;
        const match = sideList.find(item => Math.abs(item.strike - K) < 0.05 * S);
        if (match) {
            marketPrice = match.mid || match.last || 0.0;
        }
    }

    const params = {
        underlying_price: S,
        strike: K,
        days_to_expiry: daysToExpiry,
        risk_free_rate: r,
        volatility: vol,
        dividend_yield: 0.0,
        model: model,
        option_type: optionType,
        market_price: marketPrice
    };

    const res = await callApi('calculate_single_option', params);
    if (!res || res.status !== 'success' || !res.data) return;

    updateValuationUI(res.data);
}

// ACTUALIZAR UI DE VALORACION, RECOMENDACION Y GRAFICO DE PAYOFF
function updateValuationUI(data) {
    const { theoretical_price, market_price, implied_volatility_pct, break_even, greeks, recommendation, payoff_curve } = data;

    // HERO RECOMMENDATION BOX
    const actionTitleEl = document.getElementById('recActionTitle');
    const badgeIconEl = document.getElementById('recBadgeIcon');
    const cardEl = document.getElementById('recommendationCard');

    actionTitleEl.innerText = recommendation.action;
    actionTitleEl.style.color = recommendation.color;
    badgeIconEl.style.color = recommendation.color;
    badgeIconEl.innerText = recommendation.action.includes('COMPRA') ? '▲' : (recommendation.action.includes('VENTA') ? '▼' : '◆');

    cardEl.style.borderColor = recommendation.color;

    document.getElementById('recSignalStrength').innerText = recommendation.signal_strength;
    document.getElementById('recSignalStrength').style.color = recommendation.color;

    document.getElementById('recTheoreticalPrice').innerText = `$${theoretical_price.toFixed(2)}`;
    document.getElementById('recMarketPrice').innerText = `$${market_price.toFixed(2)}`;
    
    const edgeEl = document.getElementById('recEdgePct');
    edgeEl.innerText = `${recommendation.edge_pct >= 0 ? '+' : ''}${recommendation.edge_pct.toFixed(2)}%`;
    edgeEl.style.color = recommendation.color;

    document.getElementById('recIV').innerText = implied_volatility_pct ? `${implied_volatility_pct.toFixed(1)}%` : 'Calibrando';
    document.getElementById('recPoP').innerText = `${recommendation.prob_itm_pct.toFixed(1)}%`;
    document.getElementById('recBreakEven').innerText = `$${break_even.toFixed(2)}`;

    // Rationale list
    const ratListEl = document.getElementById('recRationaleList');
    ratListEl.innerHTML = '';
    (recommendation.rationale || []).forEach(item => {
        const li = document.createElement('li');
        li.innerText = item;
        ratListEl.appendChild(li);
    });

    // GRIEGAS
    document.getElementById('greekDelta').innerText = `${greeks.delta >= 0 ? '+' : ''}${greeks.delta.toFixed(3)}`;
    document.getElementById('greekGamma').innerText = `+${greeks.gamma.toFixed(4)}`;
    document.getElementById('greekVega').innerText = `$${greeks.vega.toFixed(3)}`;
    document.getElementById('greekTheta').innerText = `$${greeks.theta.toFixed(3)}`;
    document.getElementById('greekRho').innerText = `${greeks.rho >= 0 ? '+' : ''}$${greeks.rho.toFixed(3)}`;

    // GRAFICO DE PAYOFF
    renderPayoffChart(payoff_curve, break_even, AppState.quoteData?.price || 100);
}

// RENDERIZAR GRAFICO DE PAYOFF INTERACTIVO
function renderPayoffChart(payoffCurve, breakEven, currentSpot) {
    const ctx = document.getElementById('chartPayoff').getContext('2d');
    if (AppState.charts.payoff) {
        AppState.charts.payoff.destroy();
    }

    const { spots, expiry_pnl, today_pnl } = payoffCurve;

    AppState.charts.payoff = new Chart(ctx, {
        type: 'line',
        data: {
            labels: spots,
            datasets: [
                {
                    label: 'P&L al Vencimiento (T=0)',
                    data: expiry_pnl,
                    borderColor: '#10B981',
                    borderWidth: 2.5,
                    pointRadius: 0,
                    tension: 0
                },
                {
                    label: 'Valor Teórico Hoy (t=0)',
                    data: today_pnl,
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
                legend: {
                    labels: { color: '#94A3B8', font: { family: 'Plus Jakarta Sans', size: 10 } }
                },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `${ctx.dataset.label}: $${ctx.parsed.y.toFixed(2)}`
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#64748B', font: { size: 9, family: 'JetBrains Mono' } }
                },
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: {
                        color: '#64748B',
                        font: { size: 9, family: 'JetBrains Mono' },
                        callback: (v) => `$${v}`
                    }
                }
            }
        }
    });
}

// RENDERIZAR TABLA DE LA CADENA DE OPCIONES
function renderOptionsTable(chainData) {
    const tbody = document.getElementById('optionsTableBody');
    if (!tbody) return;

    tbody.innerHTML = '';
    const filter = AppState.activeFilter || 'all';

    let contracts = [];
    if (filter === 'all' || filter === 'calls') {
        contracts.push(...(chainData.calls || []).map(c => ({ ...c, type: 'CALL' })));
    }
    if (filter === 'all' || filter === 'puts') {
        contracts.push(...(chainData.puts || []).map(p => ({ ...p, type: 'PUT' })));
    }

    contracts.sort((a, b) => a.strike - b.strike);

    if (contracts.length === 0) {
        tbody.innerHTML = '<tr><td colspan="14" class="text-center py-6 text-slate-500">No hay contratos para el filtro seleccionado</td></tr>';
        return;
    }

    contracts.forEach(item => {
        const tr = document.createElement('tr');
        tr.style.cursor = 'pointer';
        const isCall = item.type === 'CALL';

        tr.innerHTML = `
            <td><span class="${isCall ? 'badge-call' : 'badge-put'}">${item.type}</span></td>
            <td class="font-bold text-white">$${item.strike.toFixed(1)}</td>
            <td>$${item.bid.toFixed(2)}</td>
            <td>$${item.ask.toFixed(2)}</td>
            <td class="font-bold text-cyan-300">$${item.mid.toFixed(2)}</td>
            <td class="text-slate-300">$${item.theoretical.toFixed(2)}</td>
            <td class="font-bold" style="color: ${item.rec_color || '#FFFFFF'}">${item.edge_pct >= 0 ? '+' : ''}${item.edge_pct.toFixed(1)}%</td>
            <td class="text-amber-400">${item.iv_pct ? item.iv_pct.toFixed(1) + '%' : '--'}</td>
            <td class="${item.delta >= 0 ? 'text-emerald-400' : 'text-rose-400'}">${item.delta.toFixed(2)}</td>
            <td class="text-slate-400">${item.gamma.toFixed(3)}</td>
            <td class="text-rose-400">${item.theta.toFixed(2)}</td>
            <td class="text-slate-300">${item.volume.toLocaleString()}</td>
            <td class="text-slate-400">${item.open_interest.toLocaleString()}</td>
            <td><span style="color: ${item.rec_color || '#94A3B8'}; font-size: 0.72rem; font-weight: 700;">${item.recommendation.split(' ')[0]}</span></td>
        `;

        // Click en fila actualiza la evaluacion central
        tr.addEventListener('click', () => {
            document.getElementById('inputStrike').value = item.strike;
            if (isCall) {
                document.getElementById('btnToggleCall').click();
            } else {
                document.getElementById('btnTogglePut').click();
            }
        });

        tbody.appendChild(tr);
    });
}

// EVENT LISTENERS DEL TERMINAL EN VIVO
function setupEventListeners() {
    // Toggle Call / Put
    const btnCall = document.getElementById('btnToggleCall');
    const btnPut = document.getElementById('btnTogglePut');

    btnCall.addEventListener('click', () => {
        btnCall.classList.add('active');
        btnPut.classList.remove('active');
        AppState.activeOptionType = 'call';
        recalculateValuation();
    });

    btnPut.addEventListener('click', () => {
        btnPut.classList.add('active');
        btnCall.classList.remove('active');
        AppState.activeOptionType = 'put';
        recalculateValuation();
    });

    // Cambios en inputs y selects
    document.getElementById('selectModel').addEventListener('change', recalculateValuation);
    document.getElementById('selectExpiry').addEventListener('change', recalculateValuation);
    document.getElementById('inputStrike').addEventListener('input', recalculateValuation);

    // Refresh quote
    document.getElementById('btnRefreshQuote').addEventListener('click', () => selectCommodity(AppState.activeCommodityId));

    // Filtros de tabla
    document.getElementById('btnFilterAll').addEventListener('click', (e) => setTableFilter('all', e.target));
    document.getElementById('btnFilterCalls').addEventListener('click', (e) => setTableFilter('calls', e.target));
    document.getElementById('btnFilterPuts').addEventListener('click', (e) => setTableFilter('puts', e.target));

    // Test Econometrico
    document.getElementById('btnRunEconTest').addEventListener('click', runEconometricValidation);

    // Quick date presets en el validador econometrico
    document.querySelectorAll('.date-preset').forEach(btn => {
        btn.addEventListener('click', () => {
            const days = parseInt(btn.dataset.days);
            const d = new Date();
            d.setDate(d.getDate() - days);
            document.getElementById('econTargetDate').value = d.toISOString().split('T')[0];
        });
    });
}

function setTableFilter(filter, targetBtn) {
    AppState.activeFilter = filter;
    document.querySelectorAll('#btnFilterAll, #btnFilterCalls, #btnFilterPuts').forEach(b => b.classList.remove('active'));
    targetBtn.classList.add('active');
    if (AppState.chainData) {
        renderOptionsTable(AppState.chainData);
    }
}

// ==================== TAB 2: VALIDADOR ECONOMETRICO ====================
function populateEconometricDropdown() {
    const sel = document.getElementById('econCommSelect');
    if (!sel) return;
    sel.innerHTML = '';
    AppState.commodities.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c.id;
        opt.innerText = c.name;
        sel.appendChild(opt);
    });

    // Default target date a 90 dias atras
    const d = new Date();
    d.setDate(d.getDate() - 90);
    document.getElementById('econTargetDate').value = d.toISOString().split('T')[0];
}

async function runEconometricValidation() {
    const btn = document.getElementById('btnRunEconTest');
    btn.disabled = true;
    btn.innerHTML = `
        <svg class="animate-spin" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 2a10 10 0 0 1 10 10"/></svg>
        CALCULANDO RESIDUOS Y DIAGNÓSTICOS...
    `;

    const params = {
        commodity_id: document.getElementById('econCommSelect').value,
        target_date: document.getElementById('econTargetDate').value,
        option_type: document.getElementById('econOptionType').value,
        moneyness: parseFloat(document.getElementById('econMoneyness').value),
        horizon_days: parseInt(document.getElementById('econHorizonDays').value),
        window_days: parseInt(document.getElementById('econWindowDays').value),
        vol_estimator: document.getElementById('econVolEstimator').value,
        model: document.getElementById('econModel').value
    };

    const res = await callApi('run_econometric_backtest', params);
    btn.disabled = false;
    btn.innerHTML = `
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
        EJECUTAR VALIDACIÓN ECONOMÉTRICA HISTÓRICA
    `;

    if (!res || res.status !== 'success' || !res.data) {
        alert(res?.message || 'Error al ejecutar el test econométrico. Verifique las fechas seleccionadas.');
        return;
    }

    displayEconometricResults(res.data);
}

function displayEconometricResults(data) {
    const sec = document.getElementById('econResultsSection');
    sec.style.display = 'block';
    sec.scrollIntoView({ behavior: 'smooth' });

    // PASO 1: ESTIMACION EN t0
    document.getElementById('econAuditDateT0').innerText = `Fecha t₀: ${data.target_date}`;
    document.getElementById('econAuditPriceT0').innerText = `$${data.underlying_at_t0.toFixed(2)}`;
    document.getElementById('econAuditStrikeK').innerText = `$${data.strike_K.toFixed(2)}`;
    document.getElementById('econAuditSigma').innerText = `${data.sigma_hat_pct.toFixed(2)}% (${data.vol_estimator})`;
    document.getElementById('econAuditRate').innerText = `${data.risk_free_rate_pct.toFixed(2)}%`;
    document.getElementById('econAuditTheoPrice').innerText = `$${data.theoretical_price_t0.toFixed(4)}`;

    // PASO 2: REALIDAD Y ERROR PUNTUAL
    document.getElementById('econAuditPriceST').innerText = `$${data.terminal_price_ST.toFixed(2)}`;
    document.getElementById('econAuditPayoffTerm').innerText = `$${data.payoff_terminal.toFixed(4)}`;
    document.getElementById('econAuditDiscountedPayoff').innerText = `$${data.realized_discounted_payoff.toFixed(4)}`;

    const pctErrEl = document.getElementById('econAuditPctError');
    pctErrEl.innerText = `${data.punctual_pct_error >= 0 ? '+' : ''}${data.punctual_pct_error.toFixed(2)}%`;
    pctErrEl.style.color = (Math.abs(data.punctual_pct_error) < 10) ? '#10B981' : '#F43F5E';

    const punctErrEl = document.getElementById('econAuditPunctualError');
    punctErrEl.innerText = `${data.punctual_error >= 0 ? '+' : ''}$${data.punctual_error.toFixed(4)}`;
    punctErrEl.style.color = (Math.abs(data.punctual_error) < 1.0) ? '#10B981' : '#F43F5E';

    // BATERIA DE DIAGNOSTICOS
    const diag = data.rolling_diagnostics;
    document.getElementById('econSampleSizeBadge').innerText = `Muestra rodante: ${diag.sample_points} puntos`;

    document.getElementById('diagRMSE').innerText = `$${diag.rmse.toFixed(4)}`;
    document.getElementById('diagMAE').innerText = `$${diag.mae.toFixed(4)}`;
    document.getElementById('diagMAPE').innerText = `${diag.mape.toFixed(2)}%`;

    const biasEl = document.getElementById('diagMeanBias');
    biasEl.innerText = `${diag.mean_bias >= 0 ? '+' : ''}${diag.mean_bias.toFixed(4)}`;
    biasEl.style.color = (diag.mean_bias < 0) ? '#F43F5E' : '#10B981';

    document.getElementById('diagBiasLabel').innerText = (diag.mean_bias < 0) 
        ? 'BSM Sobrevalora la opción (Bias Negativo)' 
        : 'BSM Subvalora la opción (Bias Positivo)';

    document.getElementById('diagJBStat').innerText = `JB: ${diag.jarque_bera_stat.toFixed(2)}`;
    document.getElementById('diagJBPval').innerText = `p-valor: ${diag.jarque_bera_pvalue.toFixed(4)} (${diag.is_normal ? 'Normalidad aceptada' : 'Normalidad rechazada - Colas pesadas'})`;
    document.getElementById('diagJBPval').style.color = diag.is_normal ? '#10B981' : '#F43F5E';

    document.getElementById('diagSkewKurt').innerText = `S: ${diag.skewness.toFixed(2)} | K: ${diag.kurtosis.toFixed(2)}`;

    document.getElementById('diagDW').innerText = `DW: ${diag.durbin_watson.toFixed(2)}`;
    document.getElementById('diagDWStatus').innerText = diag.autocorrelation_status;

    // GRAFICOS ECONOMETRICOS
    renderEconPathChart(data.path_dates, data.path_prices, data.strike_K);
    renderEconHistChart(diag.hist_labels, diag.hist_counts, diag.hist_normal_fit);
    renderEconSeriesChart(diag.dates, diag.theor_series, diag.real_series);
}

function renderEconPathChart(dates, prices, strike) {
    const ctx = document.getElementById('chartEconPath').getContext('2d');
    if (AppState.charts.econPath) AppState.charts.econPath.destroy();

    const strikeLine = new Array(dates.length).fill(strike);

    AppState.charts.econPath = new Chart(ctx, {
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
                    data: strikeLine,
                    borderColor: '#F59E0B',
                    borderWidth: 1.5,
                    borderDash: [6, 4],
                    pointRadius: 0
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { labels: { color: '#94A3B8', font: { size: 10 } } } },
            scales: {
                x: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#64748B', font: { size: 9 } } },
                y: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#64748B', font: { size: 9, family: 'JetBrains Mono' } } }
            }
        }
    });
}

function renderEconHistChart(bins, counts, normalCurve) {
    const ctx = document.getElementById('chartEconHist').getContext('2d');
    if (AppState.charts.econHist) AppState.charts.econHist.destroy();

    AppState.charts.econHist = new Chart(ctx, {
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
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { labels: { color: '#94A3B8', font: { size: 10 } } } },
            scales: {
                x: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#64748B', font: { size: 9 } } },
                y: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#64748B', font: { size: 9 } } }
            }
        }
    });
}

function renderEconSeriesChart(dates, theor, real) {
    const ctx = document.getElementById('chartEconSeries').getContext('2d');
    if (AppState.charts.econSeries) AppState.charts.econSeries.destroy();

    AppState.charts.econSeries = new Chart(ctx, {
        type: 'line',
        data: {
            labels: dates,
            datasets: [
                {
                    label: 'Valor Teórico BSM/Black-76',
                    data: theor,
                    borderColor: '#06B6D4',
                    borderWidth: 2,
                    pointRadius: 0
                },
                {
                    label: 'Payoff Realizado Descontado',
                    data: real,
                    borderColor: '#10B981',
                    borderWidth: 2,
                    pointRadius: 0
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { labels: { color: '#94A3B8', font: { size: 10 } } } },
            scales: {
                x: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#64748B', font: { size: 9 } } },
                y: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#64748B', font: { size: 9, family: 'JetBrains Mono' } } }
            }
        }
    });
}

// ==================== TAB 3: CALCULADORA WHAT-IF ====================
function setupCalculatorListeners() {
    const inputs = ['calcInputS', 'calcInputK', 'calcInputDays', 'calcInputVol', 'calcInputRate', 'calcInputModel', 'calcInputMkt'];
    inputs.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('input', runCalculator);
    });
}

async function runCalculator() {
    const S = parseFloat(document.getElementById('calcInputS').value) || 100.0;
    const K = parseFloat(document.getElementById('calcInputK').value) || 100.0;
    const days = parseFloat(document.getElementById('calcInputDays').value) || 30.0;
    const vol = parseFloat(document.getElementById('calcInputVol').value) || 20.0;
    const r = parseFloat(document.getElementById('calcInputRate').value) || 4.0;
    const model = document.getElementById('calcInputModel').value;
    const mkt = parseFloat(document.getElementById('calcInputMkt').value) || 0.0;

    // Calcular Call
    const resCall = await callApi('calculate_single_option', {
        underlying_price: S, strike: K, days_to_expiry: days,
        risk_free_rate: r, volatility: vol, dividend_yield: 0.0,
        model: model, option_type: 'call', market_price: mkt
    });

    // Calcular Put
    const resPut = await callApi('calculate_single_option', {
        underlying_price: S, strike: K, days_to_expiry: days,
        risk_free_rate: r, volatility: vol, dividend_yield: 0.0,
        model: model, option_type: 'put', market_price: mkt
    });

    if (resCall && resCall.data) {
        const d = resCall.data;
        document.getElementById('calcCallPrice').innerText = `$${d.theoretical_price.toFixed(3)}`;
        document.getElementById('calcCallDelta').innerText = d.greeks.delta.toFixed(3);
        document.getElementById('calcCallGamma').innerText = d.greeks.gamma.toFixed(4);
        document.getElementById('calcCallVega').innerText = `$${d.greeks.vega.toFixed(3)}`;
        document.getElementById('calcCallTheta').innerText = `$${d.greeks.theta.toFixed(3)}`;
        document.getElementById('calcCallRho').innerText = `$${d.greeks.rho.toFixed(3)}`;
        document.getElementById('calcCallIV').innerText = d.implied_volatility_pct ? `${d.implied_volatility_pct.toFixed(1)}%` : '--';

        // Grafico Payoff calculadora
        renderCalcPayoffChart(d.payoff_curve);
    }

    if (resPut && resPut.data) {
        const d = resPut.data;
        document.getElementById('calcPutPrice').innerText = `$${d.theoretical_price.toFixed(3)}`;
        document.getElementById('calcPutDelta').innerText = d.greeks.delta.toFixed(3);
        document.getElementById('calcPutGamma').innerText = d.greeks.gamma.toFixed(4);
        document.getElementById('calcPutVega').innerText = `$${d.greeks.vega.toFixed(3)}`;
        document.getElementById('calcPutTheta').innerText = `$${d.greeks.theta.toFixed(3)}`;
        document.getElementById('calcPutRho').innerText = `$${d.greeks.rho.toFixed(3)}`;
        document.getElementById('calcPutIV').innerText = d.implied_volatility_pct ? `${d.implied_volatility_pct.toFixed(1)}%` : '--';
    }
}

function renderCalcPayoffChart(payoffCurve) {
    const ctx = document.getElementById('chartCalcPayoff').getContext('2d');
    if (AppState.charts.calcPayoff) AppState.charts.calcPayoff.destroy();

    AppState.charts.calcPayoff = new Chart(ctx, {
        type: 'line',
        data: {
            labels: payoffCurve.spots,
            datasets: [
                {
                    label: 'Call Payoff al Vencimiento',
                    data: payoffCurve.expiry_pnl,
                    borderColor: '#10B981',
                    borderWidth: 2,
                    pointRadius: 0
                },
                {
                    label: 'Call Valor Teórico Hoy',
                    data: payoffCurve.today_pnl,
                    borderColor: '#38BDF8',
                    borderWidth: 1.5,
                    borderDash: [5, 5],
                    pointRadius: 0
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { labels: { color: '#94A3B8', font: { size: 9 } } } },
            scales: {
                x: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#64748B', font: { size: 8 } } },
                y: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#64748B', font: { size: 8 } } }
            }
        }
    });
}
