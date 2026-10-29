/* ========================================================
   Terminal Bonos Argentinos - Desktop Financial Terminal
   BYMA Oficial & BCRA API v4.0 - Engine Controller
   ======================================================== */

let allBonds = [];
let macroData = {};
let currentFilter = 'sovereign';
let searchQuery = '';
let sortCol = 'volume_amount';
let sortAsc = false;
let refreshCountdown = 30;
let refreshInterval = null;
let currentSelectedBond = null;
let tableRowLimit = 300;
let lastLoadError = null;

// Charts & Yield Curve State (Unidad 4 · Renta Fija)
let curveChart = null;
let parityChart = null;
let horizonChart = null;
let curveFamily = 'usd';          // 'usd' = Soberanos USD | 'lecap' = Pesos Tasa Fija | 'cer' = Pesos CER
let curveAxis = 'years';          // 'years' = Plazo al Vto (Años) | 'md' = Duration Modificada (Años)
let curveTheoryOverlay = null;    // null | 'normal' | 'plana' | 'invertida' | 'joroba'

// VAN Module State (k is remembered per currency: a USD hurdle rate is meaningless in pesos)
let vanSelectedBond = null;
let vanInvestment = 1000.0;
let vanCcy = 'USD';
let vanKByCcy = { USD: 12.0, ARS: 30.0 };
let vanKRate = vanKByCcy[vanCcy];
let vanIncludeTerminalVT = true;
const VAN_K_RANGE = { USD: { min: 2, max: 40 }, ARS: { min: 5, max: 120 } };

// Horizon Module State (Default 5.0 years -> 2031)
let horizonYears = 5.0;
let horizCcy = 'USD';
let horizExitMode = 'par';        // 'par' = precio sin cambios (ceteris paribus) | 'cero' = solo flujos | 'tir'
let horizIncludeMatured = true;   // also rank instruments that mature before the horizon

// Sovereign Benchmark Tickers
const SOVEREIGN_BENCHMARKS = ['AL29', 'GD29', 'AL30', 'GD30', 'AL35', 'GD35', 'AE38', 'GD38', 'AL41', 'GD41'];

// Category tabs -> backend `family`
const FILTERS = [
  { id: 'sovereign', label: '⭐ Soberanos USD', families: ['soberano_usd'] },
  { id: 'bopreal', label: '🏦 Bopreales', families: ['bopreal'] },
  { id: 'cer', label: '📈 CER', families: ['cer'] },
  { id: 'letra', label: '📜 Letras / Lecaps', families: ['letra'] },
  { id: 'subsoberano', label: '🏛 Subsoberanos', families: ['subsoberano'] },
  { id: 'on', label: '🏢 ONs', families: ['on'] },
  { id: 'caucion', label: '💱 Cauciones', families: ['caucion'] },
  { id: 'otros', label: 'Otros públicos', families: ['bono_otro'] },
  { id: 'all', label: '🌐 Todos', families: null }
];

// ========================================================
// QA TRACE & RATE HELPERS
// ========================================================
// Every module logs its inputs, intermediate math and result under "QA Trace · <módulo>" (F12).
// Silence it from the console with:  QA.enabled = false
const QA = { enabled: true };

function qaTrace(module, title, steps, table) {
  if (!QA.enabled) return;
  console.groupCollapsed(`QA Trace · ${module} · ${title}`);
  Object.entries(steps || {}).forEach(([label, value]) => console.log(label, value));
  if (table && table.length) console.table(table);
  console.groupEnd();
}

// Unit contract with the backend: every rate arrives in PERCENT (8.53 = 8,53%), never as a decimal.
// `tir`     = TNA capitalización semestral (cauciones: TNA simple).
// `tir_tea` = efectiva anual Act/365. The UI compares and discounts ONLY with TEA.
const teaOf = (b) => (b && b.tir_tea !== null && b.tir_tea !== undefined && isFinite(b.tir_tea)) ? b.tir_tea : null;
const hasNum = (v) => v !== null && v !== undefined && isFinite(v);
const fmtPct = (v, d = 2) => hasNum(v) ? `${v.toFixed(d)}%` : 'N/D';
const fmtNum = (v, d = 2) => hasNum(v) ? v.toLocaleString('es-AR', { minimumFractionDigits: d, maximumFractionDigits: d }) : '-';
const curSymbol = (ccy) => (ccy === 'USD') ? 'u$s' : '$';
const round4 = (v) => hasNum(v) ? Math.round(v * 1e4) / 1e4 : v;

// Rate algebra, all in percent
const monthlyToTEA = (mPct) => (Math.pow(1 + mPct / 100, 12) - 1) * 100;
const compound = (aPct, bPct) => ((1 + aPct / 100) * (1 + bPct / 100) - 1) * 100;   // (1+a)(1+b)-1
const deflate = (aPct, bPct) => ((1 + aPct / 100) / (1 + bPct / 100) - 1) * 100;    // Fisher: (1+a)/(1+b)-1

// Expected inflation used wherever a nominal-peso rate meets a CER (real) instrument.
// Default: BCRA REM median for the next 12 months, else last monthly print annualized.
function defaultInflTEA() {
  if (macroData.inflacion_esperada_12m > 0) return macroData.inflacion_esperada_12m;
  if (macroData.inflacion_mensual > 0) return monthlyToTEA(macroData.inflacion_mensual);
  return 25.0;
}

// Instruments that can be discounted in `ccy`: they pay in that currency, are quoted in it
// (AL30D, not AL30 in pesos), and carry a real cashflow schedule from the backend.
function dcfUniverse(ccy) {
  return allBonds.filter(b => b.is_native_quote && b.currency === ccy &&
    b.cashflows && b.cashflows.length > 0 && b.eval_price > 0);
}
const yieldBasis = (b) => b.is_cer ? 'REAL (sobre CER)' : 'NOMINAL';

document.addEventListener('DOMContentLoaded', () => {
  initUIEvents();
  startAutoRefresh();
  loadData();
});

// ========================================================
// INITIALIZATION & UI EVENTS
// ========================================================
function initUIEvents() {
  // Search box
  const searchInput = document.getElementById('searchInput');
  const clearSearch = document.getElementById('clearSearch');
  searchInput.addEventListener('input', (e) => {
    searchQuery = e.target.value.trim().toLowerCase();
    clearSearch.style.display = searchQuery ? 'block' : 'none';
    renderView();
  });
  clearSearch.addEventListener('click', () => {
    searchInput.value = '';
    searchQuery = '';
    clearSearch.style.display = 'none';
    renderView();
  });

  // Category Filter Tabs
  const filterTabs = document.getElementById('filterTabs');
  filterTabs.addEventListener('click', (e) => {
    const tab = e.target.closest('.cat-tab');
    if (tab) {
      document.querySelectorAll('.cat-tab').forEach(b => b.classList.remove('active'));
      tab.classList.add('active');
      currentFilter = tab.dataset.filter;
      tableRowLimit = 300;
      renderView();
    }
  });

  // Main Desktop View Switcher
  document.getElementById('btnViewTable').addEventListener('click', () => switchDesktopView('table'));
  document.getElementById('btnViewVan').addEventListener('click', () => switchDesktopView('van'));
  document.getElementById('btnViewHorizon').addEventListener('click', () => switchDesktopView('horizon'));
  document.getElementById('btnViewScenarios').addEventListener('click', () => switchDesktopView('scenarios'));
  document.getElementById('btnViewCharts').addEventListener('click', () => switchDesktopView('charts'));

  // Refresh Button
  document.getElementById('btnRefresh').addEventListener('click', () => {
    refreshCountdown = 30;
    loadData();
  });

  // Export CSV Button
  const btnExport = document.getElementById('btnExport');
  if (btnExport) btnExport.addEventListener('click', exportCSV);

  // Table Headers Sorting
  document.querySelectorAll('.financial-table th.sortable').forEach(th => {
    th.addEventListener('click', () => {
      const col = th.dataset.sort;
      if (sortCol === col) {
        sortAsc = !sortAsc;
      } else {
        sortCol = col;
        sortAsc = (col === 'symbol' || col === 'maturity_date');
      }
      updateSortIcons();
      renderView();
    });
  });

  // Modal Close
  document.getElementById('btnModalClose').addEventListener('click', closeModal);
  document.getElementById('bondModal').addEventListener('click', (e) => {
    if (e.target.id === 'bondModal') closeModal();
  });

  // Modal Sensitivity What-If Slider
  const simSlider = document.getElementById('simBpsSlider');
  simSlider.addEventListener('input', (e) => {
    const bps = parseInt(e.target.value, 10);
    document.getElementById('simBpsVal').innerText = (bps >= 0 ? '+' : '') + bps + ' bps';
    updateSimulator(bps);
  });

  // Modal Quick VAN Controls
  const modalVanInvest = document.getElementById('modalVanInvest');
  const modalVanKSlider = document.getElementById('modalVanKSlider');
  if (modalVanInvest && modalVanKSlider) {
    modalVanInvest.addEventListener('input', updateModalVAN);
    modalVanKSlider.addEventListener('input', () => {
      document.getElementById('modalVanKVal').innerText = parseFloat(modalVanKSlider.value).toFixed(1) + '%';
      updateModalVAN();
    });
  }

  // VAN Module UI Events
  initVanEvents();

  // Horizon Module UI Events
  initHorizonEvents();
  
  // Comparación de Bonos Events
  initScenariosEvents();

  // Curvas de Rendimiento Events
  initChartsEvents();
}

// Switch View Panels
function switchDesktopView(view) {
  const views = ['table', 'van', 'horizon', 'scenarios', 'charts'];
  views.forEach(v => {
    const el = document.getElementById(v + 'View');
    if (el) el.style.display = (v === view) ? 'flex' : 'none';
  });

  // Update Buttons
  document.getElementById('btnViewTable').classList.toggle('active', view === 'table');
  document.getElementById('btnViewVan').classList.toggle('active', view === 'van');
  document.getElementById('btnViewHorizon').classList.toggle('active', view === 'horizon');
  document.getElementById('btnViewScenarios').classList.toggle('active', view === 'scenarios');
  document.getElementById('btnViewCharts').classList.toggle('active', view === 'charts');

  if (view === 'van') {
    populateVanBondSelector();
    runVanCalculation();
  } else if (view === 'horizon') {
    runHorizonCalculation();
  } else if (view === 'scenarios') {
    populateScenarios();
    runScenarios();
  } else if (view === 'charts') {
    renderCharts();
  }
}

function updateSortIcons() {
  document.querySelectorAll('.financial-table th.sortable').forEach(th => {
    const icon = th.querySelector('.sort-icon');
    if (!icon) return;
    if (th.dataset.sort === sortCol) {
      icon.innerText = sortAsc ? ' ▲' : ' ▼';
      icon.style.color = '#38bdf8';
    } else {
      icon.innerText = '';
    }
  });
}

function startAutoRefresh() {
  if (refreshInterval) clearInterval(refreshInterval);
  refreshInterval = setInterval(() => {
    if (document.hidden) return;
    refreshCountdown--;
    const timerEl = document.getElementById('refreshTimer');
    if (timerEl) timerEl.innerText = `${refreshCountdown}s`;
    if (refreshCountdown <= 0) {
      refreshCountdown = 45;
      loadData(false);
    }
  }, 1000);
}

// ========================================================
// DATA FETCHING & HUD
// ========================================================
async function loadData(showSpin = true) {
  const spinIcon = document.getElementById('spinIcon');
  if (showSpin && spinIcon) spinIcon.classList.add('spinning');

  try {
    let result = null;
    let transport = 'fetch /api/data';
    if (window.pywebview && window.pywebview.api && window.pywebview.api.get_market_data) {
      transport = 'pywebview.api.get_market_data';
      result = await window.pywebview.api.get_market_data();
    } else {
      const resp = await fetch('/api/data');
      if (!resp.ok) throw new Error(`HTTP ${resp.status} en /api/data`);
      result = await resp.json();
    }

    if (!result || !Array.isArray(result.bonds)) throw new Error('Payload sin lista de instrumentos');
    lastLoadError = result.bonds.length === 0 ? 'El backend devolvió 0 instrumentos' : null;

    allBonds = result.bonds;
    macroData = result.macro || {};
    tracePayload(transport);
    updateHUD();
    renderFilterTabs();
    renderView();
    refreshActiveView();
  } catch (err) {
    lastLoadError = String(err && err.message || err);
    console.error('QA Trace · Datos · error al cargar el mercado:', err);
    updateHUD();
    refreshActiveView();
  } finally {
    if (spinIcon) spinIcon.classList.remove('spinning');
  }
}

// Re-renders whichever analytical view is on screen with the fresh data
function refreshActiveView() {
  const visible = (id) => document.getElementById(id).style.display === 'flex';
  if (visible('vanView')) {
    populateVanBondSelector();
    runVanCalculation();
  } else if (visible('horizonView')) {
    runHorizonCalculation();
  } else if (visible('scenariosView')) {
    populateScenarios();
    runScenarios();
  } else if (visible('chartsView')) {
    renderCharts();
  }
}

// QA Trace of the raw payload: what arrived, in which units, and how it was classified
function tracePayload(transport) {
  if (!QA.enabled) return;
  const byFamily = {};
  allBonds.forEach(b => {
    const f = byFamily[b.family] || (byFamily[b.family] = { familia: b.family, instrumentos: 0, con_TIR: 0, con_flujos: 0, ejemplo: b.symbol });
    f.instrumentos++;
    if (teaOf(b) !== null) f.con_TIR++;
    if (b.cashflows && b.cashflows.length) f.con_flujos++;
  });
  const teas = allBonds.map(teaOf).filter(v => v !== null);
  const sample = allBonds.find(b => b.symbol === 'AL30D') || allBonds[0];
  qaTrace('Datos', `payload (${allBonds.length} instrumentos vía ${transport})`, {
    '1. Unidades': 'tasas en PORCENTAJE (8.53 = 8,53%); precios c/100 VN; el frontend NO multiplica por 100',
    '2. Rango de TEA recibido': teas.length ? { min: Math.min(...teas), max: Math.max(...teas), n: teas.length } : 'sin tasas',
    '3. Instrumento de muestra (crudo)': sample ? { ...sample, cashflows: `[${(sample.cashflows || []).length} flujos]` } : null,
    '4. Macro': { ...macroData, qa: undefined },
    '5. Auditoría del backend': macroData.qa
  }, Object.values(byFamily));
}

function updateHUD() {
  const elOficial = document.getElementById('hudOficial');
  if (elOficial) elOficial.innerText = macroData.dolar_oficial ? `$ ${macroData.dolar_oficial.toFixed(2)}` : '$ -';

  const elMep = document.getElementById('hudMep');
  if (elMep) elMep.innerText = macroData.dolar_mep ? `$ ${macroData.dolar_mep.toFixed(2)}` : '$ -';

  const elCcl = document.getElementById('hudCcl');
  if (elCcl) elCcl.innerText = macroData.dolar_ccl ? `$ ${macroData.dolar_ccl.toFixed(2)}` : '$ -';

  const elBrecha = document.getElementById('hudBrecha');
  if (elBrecha) {
    const brecha = macroData.brecha_mep !== undefined ? macroData.brecha_mep : macroData.brecha_mep_oficial;
    elBrecha.innerText = brecha !== undefined && brecha !== null ? `${brecha.toFixed(1)}%` : '-%';
    elBrecha.style.color = (brecha > 30) ? '#f43f5e' : (brecha > 15 ? '#f59e0b' : '#10b981');
  }

  const elBadlar = document.getElementById('hudBadlar');
  if (elBadlar) elBadlar.innerText = macroData.tasa_badlar ? `${macroData.tasa_badlar.toFixed(2)}%` : '-%';

  const elCer = document.getElementById('hudCer');
  if (elCer) {
    const cerVal = macroData.cer !== undefined ? macroData.cer : macroData.cer_actual;
    elCer.innerText = cerVal ? cerVal.toFixed(2) : '-';
  }

  const elInf = document.getElementById('hudInf');
  if (elInf) elInf.innerText = macroData.inflacion_mensual ? `${macroData.inflacion_mensual.toFixed(1)}%` : '-%';

  const statTime = document.getElementById('statTime');
  if (statTime) {
    // Never show a fresh-looking clock over stale or missing data
    if (lastLoadError) {
      statTime.innerText = `ERROR: ${lastLoadError}`;
      statTime.style.color = '#f43f5e';
    } else if (macroData.data_status && macroData.data_status !== 'live') {
      statTime.innerText = `${macroData.updated_at || '--:--:--'} (último snapshot: ${macroData.data_status_reason || 'BYMA sin datos'})`;
      statTime.style.color = '#f59e0b';
    } else {
      statTime.innerText = macroData.updated_at || new Date().toTimeString().split(' ')[0];
      statTime.style.color = '';
    }
  }

  const countEl = document.getElementById('totalBondsCount');
  if (countEl) countEl.innerText = allBonds.length;

  const statCount = document.getElementById('statCount');
  if (statCount) statCount.innerText = allBonds.length;
}

// ========================================================
// FILTER & TABLE RENDERING
// ========================================================
function renderFilterTabs() {
  const host = document.getElementById('filterTabs');
  if (!host) return;
  const counts = {};
  allBonds.forEach(b => { counts[b.family] = (counts[b.family] || 0) + 1; });
  host.innerHTML = FILTERS.map(f => {
    const n = f.families ? f.families.reduce((acc, fam) => acc + (counts[fam] || 0), 0) : allBonds.length;
    return `<button class="cat-tab ${f.id === currentFilter ? 'active' : ''}" data-filter="${f.id}">${f.label} (${n})</button>`;
  }).join('');
}

function getFilteredData() {
  const filter = FILTERS.find(f => f.id === currentFilter) || FILTERS[FILTERS.length - 1];
  return allBonds.filter(b => {
    const matchCat = !filter.families || filter.families.includes(b.family);

    let matchSearch = true;
    if (searchQuery) {
      matchSearch = b.symbol.toLowerCase().includes(searchQuery) ||
                    (b.name && b.name.toLowerCase().includes(searchQuery)) ||
                    (b.type && b.type.toLowerCase().includes(searchQuery));
    }

    return matchCat && matchSearch;
  });
}

// Same wording as engine.INFO_GAP: shown when the public source lacks the data to compute the metrics
const INFO_GAP_MSG = 'No hay información suficiente desde la API pública de BYMA';

const FAMILY_BADGE = { bopreal: 'badge-bopreal', cer: 'badge-cer', letra: 'badge-lecap', on: 'badge-corp', caucion: 'badge-lecap' };
const SORT_KEY = { tir: 'tir_tea' };   // the TIR column shows and sorts by TEA

function tirCellHtml(bond) {
  const tea = teaOf(bond);
  if (tea === null) {
    return `<span style="color:var(--text-dim); font-weight:normal;" title="${bond.tir_reason || 'Sin datos para calcular'}">N/D</span>`;
  }
  const tag = bond.family === 'caucion' ? `TNA ${fmtPct(bond.tir)}`
    : (bond.tir_quality === 'estimada' ? 'estimada' : (bond.is_cer ? 'real' : ''));
  return `<span title="${bond.tir_basis || ''} · ${bond.tir_reason || 'cronograma de prospecto'}">${fmtPct(tea)}</span>` +
    (tag ? `<div style="font-size:10px; color:var(--text-dim); font-weight:normal;">${tag}</div>` : '');
}

function renderView() {
  const data = getFilteredData();
  const key = SORT_KEY[sortCol] || sortCol;

  // Sorting
  data.sort((a, b) => {
    let valA = a[key];
    let valB = b[key];

    if (valA === undefined || valA === null) valA = sortAsc ? Infinity : -Infinity;
    if (valB === undefined || valB === null) valB = sortAsc ? Infinity : -Infinity;

    if (typeof valA === 'string' || typeof valB === 'string') {
      return sortAsc ? String(valA).localeCompare(String(valB)) : String(valB).localeCompare(String(valA));
    }
    return sortAsc ? valA - valB : valB - valA;
  });

  const tbody = document.getElementById('bondsTableBody');
  const emptyState = document.getElementById('emptyState');
  tbody.innerHTML = '';

  if (data.length === 0) {
    emptyState.style.display = 'flex';
    const msg = emptyState.querySelector('p');
    if (msg) msg.innerText = lastLoadError
      ? `Sin datos de mercado: ${lastLoadError}`
      : 'No se encontraron instrumentos para el filtro actual.';
    return;
  }
  emptyState.style.display = 'none';

  // Rendering thousands of rows on every 30s refresh freezes the WebView: paint a page at a time
  const page = data.slice(0, tableRowLimit);
  const frag = document.createDocumentFragment();

  page.forEach(bond => {
    const tr = document.createElement('tr');
    tr.id = `row-${bond.symbol}`;

    const badgeClass = FAMILY_BADGE[bond.family] || 'badge-sovereign';
    const isCaucion = bond.family === 'caucion';

    // Change Class
    const changeClass = bond.change_pct > 0 ? 'cell-pos' : (bond.change_pct < 0 ? 'cell-neg' : '');
    const changeSign = bond.change_pct > 0 ? '+' : '';

    let parityBadge = '-';
    if (hasNum(bond.parity) && bond.parity > 0) {
      let pClass = 'parity-mid';
      if (bond.parity > 95) pClass = 'parity-high';
      else if (bond.parity < 55) pClass = 'parity-low';
      parityBadge = `<span class="parity-badge ${pClass}">${bond.parity.toFixed(1)}%</span>`;
    }

    // Currency symbols: Quote currency for trading price, payment currency for VT
    const quoteSym = (bond.ccy === 'USD' || bond.ccy === 'EXT') ? 'u$s' : '$';
    const paySym = curSymbol(bond.currency);
    const hasUsdEquivalent = (bond.ccy === 'ARS' && bond.currency === 'USD' && bond.eval_price_usd);
    const staleNote = (bond.price_source && bond.price_source !== 'ultimo')
      ? `<div style="font-size:10px; color:var(--text-dim); font-weight:normal;">${bond.price_source === 'cierre' ? 'cierre' : 'cierre ant.'}</div>` : '';
    const priceHtml = isCaucion
      ? `TNA ${fmtPct(bond.price)}`
      : `${quoteSym} ${hasNum(bond.price) ? bond.price.toFixed(2) : '-'}`;

    tr.innerHTML = `
      <td>
        <div class="ticker-cell">
          <span class="ticker-name">${bond.symbol}</span>
          <span class="badge-tag ${badgeClass}">${bond.currency}${bond.segment === 'SENEBI' ? ' · SENEBI' : ''}</span>
        </div>
      </td>
      <td>
        <span style="font-size:11px; color:var(--text-muted);">${bond.type || '-'}</span>
        ${bond.law && !isCaucion ? `<span style="font-size:10px; color:var(--text-dim);"> &bull; ${bond.law}</span>` : ''}
      </td>
      <td class="right" style="font-weight:700; color:#fff;">
        ${priceHtml}
        ${hasUsdEquivalent ? `<div style="font-size:10px; color:var(--text-dim); font-weight:normal;">(u$s ${bond.eval_price_usd.toFixed(2)})</div>` : ''}
        ${staleNote}
      </td>
      <td class="right ${changeClass}" style="font-weight:700;">
        ${hasNum(bond.change_pct) ? `${changeSign}${bond.change_pct.toFixed(2)}%` : '-'}
      </td>
      ${bond.data_gap ? `
      <td colspan="5" class="center" style="font-size:11px; color:var(--text-dim);" title="${bond.tir_reason || ''}">
        ${INFO_GAP_MSG}
      </td>` : `
      <td class="right">${hasNum(bond.vt) && bond.vt > 0 ? `${paySym} ${bond.vt.toFixed(2)}` : '-'}</td>
      <td class="center">${parityBadge}</td>
      <td class="right" style="color:var(--primary-cyan); font-weight:700;">${tirCellHtml(bond)}</td>
      <td class="right">${isCaucion ? `${bond.days_to_maturity} d` : ((bond.duration > 0) ? `${bond.duration.toFixed(2)} a` : '-')}</td>
      <td class="right">${(bond.mod_duration > 0) ? `${bond.mod_duration.toFixed(2)} a` : '-'}</td>`}
      <td class="right" style="color:var(--text-muted); font-size:11px;">
        ${bond.volume_amount ? `$ ${(bond.volume_amount / 1e6).toFixed(1)}M` : '-'}
      </td>
      <td class="center" style="font-size:11px; color:var(--text-muted);">
        ${bond.maturity_date ? bond.maturity_date.substring(0, 10) : '-'}
      </td>
      <td class="center">
        <button class="btn-inspect" onclick="openBondModal('${bond.symbol}')">Ficha</button>
      </td>
    `;

    tr.addEventListener('click', (e) => {
      if (e.target.tagName !== 'BUTTON') {
        openBondModal(bond.symbol);
      }
    });

    frag.appendChild(tr);
  });

  if (data.length > page.length) {
    const more = document.createElement('tr');
    more.innerHTML = `<td colspan="12" class="center" style="padding:14px; color:var(--text-dim);">
      Mostrando ${page.length} de ${data.length} instrumentos.
      <button class="btn-inspect" id="btnShowMoreRows">Mostrar 300 más</button>
    </td>`;
    frag.appendChild(more);
  }
  tbody.appendChild(frag);

  const btnMore = document.getElementById('btnShowMoreRows');
  if (btnMore) btnMore.addEventListener('click', (e) => {
    e.stopPropagation();
    tableRowLimit += 300;
    renderView();
  });
}

// ========================================================
// 2. VALUACIÓN POR VAN (TASA k) MODULE
// ========================================================
function initVanEvents() {
  const bondSelect = document.getElementById('vanBondSelect');
  const investInput = document.getElementById('vanInvestmentInput');
  const kSlider = document.getElementById('vanKSlider');
  const kInput = document.getElementById('vanKInput');
  const inflInput = document.getElementById('vanInflInput');

  // Currency toggle (ARS / USD)
  document.getElementById('vanTabUSD')?.addEventListener('click', () => setVanCurrency('USD'));
  document.getElementById('vanTabARS')?.addEventListener('click', () => setVanCurrency('ARS'));

  if (bondSelect) {
    bondSelect.addEventListener('change', (e) => {
      vanSelectedBond = e.target.value;
      runVanCalculation();
    });
  }

  if (investInput) {
    investInput.addEventListener('input', (e) => {
      vanInvestment = Math.max(10, parseFloat(e.target.value) || 1000);
      runVanCalculation();
    });
  }

  if (kSlider && kInput) {
    kSlider.addEventListener('input', (e) => setVanK(parseFloat(e.target.value)));
    kInput.addEventListener('input', (e) => {
      const k = parseFloat(e.target.value);
      if (isFinite(k) && k > -99) setVanK(k, true);
    });
  }

  if (inflInput) inflInput.addEventListener('input', runVanCalculation);

  // Presets (each currency has its own chip row)
  document.querySelectorAll('.preset-btn').forEach(btn => {
    btn.addEventListener('click', () => setVanK(parseFloat(btn.dataset.k)));
  });

  // Terminal VT Recovery Checkbox
  const vtCheckbox = document.getElementById('vanIncludeVT');
  if (vtCheckbox) {
    vtCheckbox.checked = vanIncludeTerminalVT;
    vtCheckbox.addEventListener('change', (e) => {
      vanIncludeTerminalVT = e.target.checked;
      runVanCalculation();
    });
  }

  syncVanCurrencyUI();
}

// Single place where the discount rate k changes: keeps slider, input, chips and labels in sync
function setVanK(k, fromInput = false) {
  if (!isFinite(k)) return;
  vanKRate = k;
  vanKByCcy[vanCcy] = k;
  const kSlider = document.getElementById('vanKSlider');
  const kInput = document.getElementById('vanKInput');
  if (kSlider) kSlider.value = Math.min(parseFloat(kSlider.max), Math.max(parseFloat(kSlider.min), k));
  if (kInput && !fromInput) kInput.value = k.toFixed(1);
  document.getElementById('vanKDisplay').innerText = `${k.toFixed(2)}%`;
  document.getElementById('vanKRankingLabel').innerText = `${k.toFixed(1)}%`;
  const chips = document.getElementById(vanCcy === 'USD' ? 'vanPresetsUSD' : 'vanPresetsARS');
  if (chips) chips.querySelectorAll('.preset-btn').forEach(b => b.classList.toggle('active', parseFloat(b.dataset.k) === k));
  runVanCalculation();
}

// ARS <-> USD toggle: swaps the instrument universe, the money prefix and the rate k (with its range)
function setVanCurrency(ccy) {
  if (ccy === vanCcy) return;
  vanKByCcy[vanCcy] = vanKRate;
  vanCcy = ccy;
  vanSelectedBond = null;
  syncVanCurrencyUI();
  populateVanBondSelector();
  setVanK(vanKByCcy[ccy]);   // also recalculates
  qaTrace('VAN', `toggle de moneda -> ${ccy}`, {
    'Universo filtrado': dcfUniverse(ccy).map(b => b.symbol),
    'k restaurada para la moneda (TEA %)': vanKByCcy[ccy]
  });
}

function syncVanCurrencyUI() {
  const isUsd = vanCcy === 'USD';
  document.getElementById('vanTabUSD')?.classList.toggle('active', isUsd);
  document.getElementById('vanTabARS')?.classList.toggle('active', !isUsd);
  document.getElementById('vanPresetsUSD').style.display = isUsd ? 'flex' : 'none';
  document.getElementById('vanPresetsARS').style.display = isUsd ? 'none' : 'flex';
  document.getElementById('vanInvestPrefix').innerText = curSymbol(vanCcy);

  const range = VAN_K_RANGE[vanCcy];
  const kSlider = document.getElementById('vanKSlider');
  if (kSlider) { kSlider.min = range.min; kSlider.max = range.max; }

  // Expected inflation only matters in pesos (to discount CER flows with a nominal k)
  // (its default, the BCRA REM, is filled in populateVanBondSelector once market data has loaded)
  const inflField = document.getElementById('vanInflField');
  if (inflField) inflField.style.display = isUsd ? 'none' : 'flex';

  const note = document.getElementById('vanCcyNote');
  if (note) note.innerText = isUsd
    ? 'Flujos, precios y tasa k en dólares. k es una tasa efectiva anual (TEA) en USD.'
    : 'Flujos, precios y tasa k en pesos. k es una TEA NOMINAL en ARS: para bonos CER se convierte a tasa real con la inflación esperada (Fisher).';
}

function vanInflPct() {
  const el = document.getElementById('vanInflInput');
  const v = el ? parseFloat(el.value) : NaN;
  return isFinite(v) ? v : defaultInflTEA();
}

// Only instruments with a real cashflow schedule can be valued by VAN. The backend sends
// `cashflows: []` for anything without a prospectus schedule (ONs, provinciales, letras estimadas).
function isVanEligible(bond) {
  if (!bond) return false;
  if (!bond.cashflows || bond.cashflows.length === 0) return false;
  return (bond.eval_price || 0) > 0;
}

function populateVanBondSelector() {
  const sel = document.getElementById('vanBondSelect');
  if (!sel) return;
  const inflInput = document.getElementById('vanInflInput');
  if (inflInput && !inflInput.value) inflInput.value = defaultInflTEA().toFixed(1);

  const validBonds = dcfUniverse(vanCcy);
  validBonds.sort((a, b) => (a.family + a.maturity_date + a.symbol).localeCompare(b.family + b.maturity_date + b.symbol));

  const prevVal = vanSelectedBond || sel.value;
  sel.innerHTML = '';

  if (validBonds.length === 0) {
    const opt = document.createElement('option');
    opt.value = '';
    opt.innerText = `Sin instrumentos en ${vanCcy} con cronograma de flujos`;
    sel.appendChild(opt);
    vanSelectedBond = null;
    return;
  }

  const curSym = curSymbol(vanCcy);
  validBonds.forEach(b => {
    const opt = document.createElement('option');
    opt.value = b.symbol;
    opt.innerText = `${b.symbol} · ${b.name || b.type} · TIR ${fmtPct(teaOf(b))} TEA ${b.is_cer ? 'real' : ''} · ${curSym} ${fmtNum(b.eval_price)}`;
    sel.appendChild(opt);
  });

  if (prevVal && validBonds.some(b => b.symbol === prevVal)) {
    sel.value = prevVal;
    vanSelectedBond = prevVal;
  } else {
    const preferred = vanCcy === 'USD' ? ['GD30D', 'AL30D'] : ['TX28', 'TX26'];
    const defaultBond = validBonds.find(b => preferred.includes(b.symbol)) || validBonds[0];
    sel.value = defaultBond.symbol;
    vanSelectedBond = defaultBond.symbol;
  }
}

/**
 * VAN of `investment` in `bond`, discounting at k (TEA %, in the bond's payment currency).
 *   VP_i = CF_i / (1 + k)^t_i        t_i = días/365 (Actual/365)
 * CER bonds: their cashflows are expressed in today's CER pesos (real terms), so a nominal k is
 * first converted to a real rate with Fisher: k_real = (1 + k) / (1 + inflación) - 1.
 */
function calculateVANMath(bond, investment, kRatePct, opts = {}) {
  const includeTerminalVT = opts.includeTerminalVT !== undefined ? opts.includeTerminalVT : vanIncludeTerminalVT;
  const inflPct = opts.inflPct !== undefined ? opts.inflPct : vanInflPct();
  if (!isVanEligible(bond)) return null;

  const rawPrice = bond.eval_price;
  const FEE_RATE = 0.005; // 0.5% broker fee on the purchase
  const evalPrice = rawPrice * (1.0 + FEE_RATE);

  const kAppliedPct = bond.is_cer ? deflate(kRatePct, inflPct) : kRatePct;
  const k = kAppliedPct / 100.0;
  if (k <= -1) return null;
  const cur = curSymbol(bond.currency);

  let theoreticalPrice = 0.0;
  let cumPv = 0.0;
  let cumCapital = 0.0;
  const pvCashflows = [];
  const n = bond.cashflows.length;

  bond.cashflows.forEach((cf, idx) => {
    const isLast = (idx === n - 1);
    // The capital (VR) is returned once, per the prospectus: amortizations + final redemption.
    // Only principal left unamortized by the schedule is added at maturity (normally 0).
    const residual = isLast ? Math.max(0.0, cf.remaining_vr || 0.0) : 0.0;
    const terminalCapital = includeTerminalVT ? residual : 0.0;
    const totalWithTerminal = cf.total + terminalCapital;
    cumCapital += cf.amort + terminalCapital;
    const t = Math.max(0.001, cf.years);
    const df = 1.0 / Math.pow(1.0 + k, t);
    const pv = totalWithTerminal * df;
    cumPv += pv;

    pvCashflows.push({
      date: cf.date,
      coupon: cf.coupon,
      amort: cf.amort,
      terminalCapital: terminalCapital,
      cumCapital: cumCapital,
      isLast: isLast,
      total: totalWithTerminal,
      baseTotal: cf.total,
      years: t,
      df: df,
      pv: pv,
      cumPv: cumPv
    });
    theoreticalPrice += pv;
  });

  const scale = investment / evalPrice;
  const totalPV = theoreticalPrice * scale;
  const totalVAN = totalPV - investment;
  const vanPct = (totalVAN / investment) * 100.0;
  const marginPct = ((theoreticalPrice - evalPrice) / evalPrice) * 100.0;
  const nominals = (investment / (evalPrice / 100.0));
  const tirMarket = teaOf(bond);
  const tolerance = investment * 0.001;   // ±0,1% of the ticket counts as "at fair value"

  let verdict = "En Precio Teórico (Rinde ~ k)";
  let verdictBadge = "neutral";
  let verdictIcon = "⚪";
  let verdictDesc = `El instrumento cotiza alineado con la tasa de descuento exigida (${kAppliedPct.toFixed(1)}%). Su valor presente coincide con el precio de compra.`;

  if (totalVAN > tolerance) {
    verdict = "OPORTUNIDAD / SUBVALUADO (VAN Positivo)";
    verdictBadge = "success";
    verdictIcon = "🟢";
    verdictDesc = `A una tasa exigida del ${kRatePct.toFixed(1)}%, el valor presente de los flujos (${cur} ${fmtNum(totalPV)}) supera tu inversión inicial (${cur} ${fmtNum(investment)}), con un margen de seguridad del +${marginPct.toFixed(1)}%.`;
  } else if (totalVAN < -tolerance) {
    verdict = "SOBREVALUADO / RENDIMIENTO INFERIOR (VAN Negativo)";
    verdictBadge = "danger";
    verdictIcon = "🔴";
    verdictDesc = `A una tasa exigida del ${kRatePct.toFixed(1)}%, el precio de mercado es alto respecto a los flujos descontados: el instrumento rinde menos que tu costo de oportunidad k.`;
  }
  if (bond.is_cer) {
    verdictDesc += ` Bono CER: k nominal ${kRatePct.toFixed(1)}% con inflación esperada ${inflPct.toFixed(1)}% equivale a una tasa real de ${kAppliedPct.toFixed(2)}%, que es la que descuenta sus flujos.`;
  }

  if (opts.trace) {
    qaTrace('VAN', `${bond.symbol} en ${bond.currency}`, {
      '1. Dato crudo (backend)': {
        symbol: bond.symbol, familia: bond.family, moneda_cotizacion: bond.ccy, moneda_pago: bond.currency,
        precio_BYMA: bond.price, eval_price: bond.eval_price, 'tir (TNA sem. %)': bond.tir, 'tir_tea (%)': bond.tir_tea,
        base: bond.tir_basis, calidad: bond.tir_quality
      },
      '2. Inputs del usuario': { moneda: vanCcy, inversion: investment, 'k (TEA %)': kRatePct, 'inflación esperada (TEA %)': bond.is_cer ? inflPct : 'no aplica' },
      '3. Tasa de descuento aplicada': bond.is_cer
        ? `Fisher: (1 + ${kRatePct}/100) / (1 + ${inflPct}/100) - 1 = ${kAppliedPct.toFixed(4)}% real`
        : `${kAppliedPct}% nominal en ${bond.currency} (sin ajuste)`,
      '4. Precio de compra': `${rawPrice} x (1 + ${FEE_RATE} comisión) = ${round4(evalPrice)}`,
      '5. Resultado': {
        precio_teorico: round4(theoreticalPrice), nominales: round4(nominals), VP_total: round4(totalPV),
        VAN: round4(totalVAN), 'VAN %': round4(vanPct), 'TIR mercado (TEA %)': tirMarket, veredicto: verdict
      }
    }, pvCashflows.map(c => ({ fecha: c.date, flujo: round4(c.total), 't (años)': round4(c.years), DF: round4(c.df), VP: round4(c.pv), VP_acum: round4(c.cumPv) })));
  }

  return {
    bond: bond,
    investment: investment,
    kRatePct: kRatePct,
    kAppliedPct: kAppliedPct,
    inflPct: inflPct,
    evalPrice: evalPrice,
    vt: bond.vt,
    includeTerminalVT: includeTerminalVT,
    nominals: nominals,
    theoreticalPrice: theoreticalPrice,
    totalPV: totalPV,
    totalVAN: totalVAN,
    vanPct: vanPct,
    marginPct: marginPct,
    tirMarket: tirMarket,
    verdict: verdict,
    verdictBadge: verdictBadge,
    verdictIcon: verdictIcon,
    verdictDesc: verdictDesc,
    cashflows: pvCashflows
  };
}

function runVanCalculation() {
  if (!vanSelectedBond) {
    populateVanBondSelector();
  }
  const bond = allBonds.find(b => b.symbol === vanSelectedBond);
  const res = bond ? calculateVANMath(bond, vanInvestment, vanKRate, { trace: true }) : null;
  if (!res) {
    const why = lastLoadError ? `Sin datos de mercado: ${lastLoadError}`
      : `No hay instrumentos en ${vanCcy} con cronograma de flujos para valuar.`;
    ['kpiInvestment', 'kpiPV', 'kpiVAN', 'kpiPrices', 'kpiYields'].forEach(id => { document.getElementById(id).innerText = '-'; });
    document.getElementById('verdictIcon').innerText = '⚪';
    document.getElementById('verdictTitle').innerText = 'Sin instrumento para valuar';
    document.getElementById('verdictDesc').innerText = why;
    const cfTbodyEmpty = document.getElementById('vanCashflowsBody');
    if (cfTbodyEmpty) {
      cfTbodyEmpty.innerHTML = `<tr><td colspan="9" class="center" style="padding:16px; color:var(--text-dim);">${why}</td></tr>`;
    }
    renderMarketVanRanking();
    return;
  }

  // Update KPIs
  const curSym = curSymbol(vanCcy);
  document.getElementById('kpiInvestment').innerText = `${curSym} ${fmtNum(res.investment)}`;
  document.getElementById('kpiNominals').innerText = `Nominales: ${Math.round(res.nominals).toLocaleString('es-AR')} (incl. 0,5% comisión)`;

  document.getElementById('kpiPV').innerText = `${curSym} ${fmtNum(res.totalPV)}`;

  const vanEl = document.getElementById('kpiVAN');
  const sign = res.totalVAN >= 0 ? '+' : '';
  vanEl.innerText = `${sign}${curSym} ${fmtNum(res.totalVAN)}`;
  vanEl.className = 'kpi-value ' + (res.totalVAN > 0 ? 'kpi-pos' : (res.totalVAN < 0 ? 'kpi-neg' : ''));

  const vanPctEl = document.getElementById('kpiVanPct');
  vanPctEl.innerText = `Rentabilidad neta: ${sign}${res.vanPct.toFixed(2)}%`;
  vanPctEl.style.color = res.totalVAN > 0 ? '#10b981' : (res.totalVAN < 0 ? '#f43f5e' : '#94a3b8');

  document.getElementById('kpiPrices').innerText = `${curSym} ${fmtNum(res.theoreticalPrice)} vs ${fmtNum(res.evalPrice)}`;
  document.getElementById('kpiMargin').innerText = `Margen: ${res.marginPct >= 0 ? '+' : ''}${res.marginPct.toFixed(1)}%`;

  // TIR and k are compared on the same basis (both real for CER, both nominal otherwise)
  const basis = bond.is_cer ? ' real' : '';
  document.getElementById('kpiYields').innerText = `${fmtPct(res.tirMarket)} vs ${res.kAppliedPct.toFixed(2)}%${basis}`;
  if (res.tirMarket !== null) {
    const spread = Math.round((res.tirMarket - res.kAppliedPct) * 100);
    document.getElementById('kpiSpread').innerText = `Spread: ${spread >= 0 ? '+' : ''}${spread} bps (TEA)`;
  } else {
    document.getElementById('kpiSpread').innerText = 'Spread: N/D';
  }

  // Verdict Box
  const vBox = document.getElementById('vanVerdictBox');
  vBox.className = 'van-verdict-box ' + (res.verdictBadge === 'danger' ? 'verdict-danger' : (res.verdictBadge === 'neutral' ? 'verdict-neutral' : ''));
  document.getElementById('verdictIcon').innerText = res.verdictIcon;
  document.getElementById('verdictTitle').innerText = res.verdict;
  document.getElementById('verdictDesc').innerText = res.verdictDesc;

  // Render Cashflows Table
  const cfTbody = document.getElementById('vanCashflowsBody');
  cfTbody.innerHTML = '';
  const vrTotal = bond.vr || 100.0;
  res.cashflows.forEach(cf => {
    const tr = document.createElement('tr');
    if (cf.isLast) {
      tr.style.backgroundColor = 'rgba(16, 185, 129, 0.12)';
    }
    const capPct = vrTotal > 0 ? (cf.cumCapital / vrTotal) * 100.0 : 0.0;
    const capitalCell = cf.isLast
      ? `<span style="color:#10b981; font-weight:700;">${curSym} ${fmtNum(cf.cumCapital)} (${capPct.toFixed(0)}%)</span>`
      : `<span style="color:var(--text-muted);">${curSym} ${fmtNum(cf.cumCapital)}</span>`;
    const amortCell = cf.terminalCapital > 0
      ? `${curSym} ${fmtNum(cf.amort)} <span style="color:#10b981;">+ ${fmtNum(cf.terminalCapital)}</span>`
      : `${curSym} ${fmtNum(cf.amort)}`;

    tr.innerHTML = `
      <td><strong>${cf.date}</strong> ${cf.isLast ? '<span class="badge-tag badge-lecap" style="font-size:9px; padding:1px 4px; margin-left:4px;">VTO</span>' : ''}</td>
      <td class="right">${curSym} ${fmtNum(cf.coupon, 3)}</td>
      <td class="right">${amortCell}</td>
      <td class="right">${capitalCell}</td>
      <td class="right" style="font-weight:700; color:#fff;">${curSym} ${fmtNum(cf.total)}</td>
      <td class="right">${cf.years.toFixed(2)}</td>
      <td class="right" style="font-family:var(--font-mono); color:var(--text-dim);">${cf.df.toFixed(4)}</td>
      <td class="right" style="color:var(--primary-cyan); font-weight:700;">${curSym} ${fmtNum(cf.pv)}</td>
      <td class="right" style="font-weight:700;">${curSym} ${fmtNum(cf.cumPv)}</td>
    `;
    cfTbody.appendChild(tr);
  });

  // Render Market-Wide VAN Ranking
  renderMarketVanRanking();
}

function renderMarketVanRanking() {
  const rankingTbody = document.getElementById('vanMarketRankingBody');
  if (!rankingTbody) return;
  rankingTbody.innerHTML = '';

  // Same universe as the selector: one species per instrument, in the selected currency
  const candidates = dcfUniverse(vanCcy)
    .map(b => calculateVANMath(b, 1000.0, vanKRate))
    .filter(Boolean);

  // Sort by VAN descending (most attractive first)
  candidates.sort((a, b) => b.totalVAN - a.totalVAN);

  if (candidates.length === 0) {
    rankingTbody.innerHTML = `<tr><td colspan="7" class="center" style="padding:16px; color:var(--text-dim);">Sin instrumentos en ${vanCcy} con cronograma de flujos y precio vigente.</td></tr>`;
    return;
  }

  const curSym = curSymbol(vanCcy);

  candidates.forEach(c => {
    const tr = document.createElement('tr');
    const isCurrent = (c.bond.symbol === vanSelectedBond);
    if (isCurrent) tr.style.backgroundColor = 'rgba(56, 189, 248, 0.15)';

    const vanClass = c.totalVAN > 0 ? 'cell-pos' : (c.totalVAN < 0 ? 'cell-neg' : '');
    const vanSign = c.totalVAN >= 0 ? '+' : '';
    const vtoStr = c.bond.maturity_date ? c.bond.maturity_date.substring(0, 10) : '-';

    tr.innerHTML = `
      <td>
        <strong style="color:#fff; cursor:pointer;" onclick="selectVanBond('${c.bond.symbol}')">${c.bond.symbol}</strong>
      </td>
      <td class="center" style="font-size:11px; color:var(--text-muted);">${vtoStr}</td>
      <td class="right">${curSym} ${fmtNum(c.evalPrice)}</td>
      <td class="right">${curSym} ${fmtNum(c.theoreticalPrice)}</td>
      <td class="right" style="color:var(--primary-cyan); font-weight:700;">${fmtPct(c.tirMarket)}${c.bond.is_cer ? ' <span style="font-size:10px; color:var(--text-dim);">real</span>' : ''}</td>
      <td class="right ${vanClass}" style="font-weight:800; font-family:var(--font-mono);">
        ${vanSign}${curSym} ${fmtNum(c.totalVAN, 1)}
      </td>
      <td class="center">
        <span class="badge-tag ${c.verdictBadge === 'success' ? 'badge-lecap' : (c.verdictBadge === 'danger' ? 'badge-corp' : 'badge-sovereign')}">
          ${c.verdictBadge === 'success' ? 'Oportunidad' : (c.verdictBadge === 'danger' ? 'Sobrevaluado' : 'Equilibrio')}
        </span>
      </td>
    `;
    rankingTbody.appendChild(tr);
  });
}

function selectVanBond(sym) {
  const sel = document.getElementById('vanBondSelect');
  if (sel) {
    sel.value = sym;
    vanSelectedBond = sym;
    runVanCalculation();
  }
}

// ========================================================
// 3. COMPARADOR POR HORIZONTE DE INVERSIÓN (TIR A PLAZO)
// ========================================================
function initHorizonEvents() {
  document.getElementById('horizonExitMode')?.addEventListener('change', (e) => {
    horizExitMode = e.target.value;
    runHorizonCalculation();
  });
  document.getElementById('horizonIncludeMatured')?.addEventListener('change', (e) => {
    horizIncludeMatured = e.target.checked;
    runHorizonCalculation();
  });

  const slider = document.getElementById('horizonSlider');
  if (slider) {
    slider.addEventListener('input', (e) => {
      horizonYears = parseFloat(e.target.value);
      updateHorizonDisplays();
      runHorizonCalculation();
    });
  }

  // Currency Tabs
  document.getElementById('horizTabUSD')?.addEventListener('click', (e) => {
    document.getElementById('horizTabUSD').classList.add('active');
    document.getElementById('horizTabARS').classList.remove('active');
    horizCcy = 'USD';
    runHorizonCalculation();
  });
  document.getElementById('horizTabARS')?.addEventListener('click', (e) => {
    document.getElementById('horizTabARS').classList.add('active');
    document.getElementById('horizTabUSD').classList.remove('active');
    horizCcy = 'ARS';
    runHorizonCalculation();
  });

  document.querySelectorAll('.horizon-preset-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.horizon-preset-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const yrs = parseFloat(btn.dataset.years);
      horizonYears = yrs;
      if (slider) slider.value = yrs;
      updateHorizonDisplays();
      runHorizonCalculation();
    });
  });
}

function updateHorizonDisplays() {
  const targetDate = new Date();
  targetDate.setDate(targetDate.getDate() + Math.round(horizonYears * 365.25));
  const monthNames = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];
  const targetStr = `${monthNames[targetDate.getMonth()]} ${targetDate.getFullYear()}`;

  document.getElementById('horizonYearsDisplay').innerText = `${horizonYears.toFixed(1)} años`;
  document.getElementById('horizonTargetDateDisplay').innerText = targetStr;
  document.getElementById('horizonFilterYear').innerText = `${targetDate.getFullYear()}`;
  document.getElementById('horizonTableYearTitle').innerText = `${targetDate.getFullYear()} (${horizonYears.toFixed(1)} a)`;
}

// Effective annual rate r that solves  price = Σ CF_i/(1+r)^t_i  (bisection; null if no sign change)
function solveEffectiveRate(pvAt, price) {
  let low = -0.95, high = 10.0;
  if (pvAt(low) - price < 0 || pvAt(high) - price > 0) return null;
  for (let iter = 0; iter < 100; iter++) {
    const mid = (low + high) / 2.0;
    const d = pvAt(mid) - price;
    if (Math.abs(d) < 1e-9) return mid;
    if (d > 0) low = mid; else high = mid;
  }
  return (low + high) / 2.0;
}

/**
 * Holding-period return of buying today and selling at `horizonYrs`.
 * Coupons/amortizations collected are kept as cash; the remaining flows are sold at the bond's
 * current TIR (constant-yield exit). All rates are TEA, Act/365. For CER bonds the result is REAL.
 */
function calculateBondHorizon(bond, horizonYrs, opts = {}) {
  if (!bond || !bond.cashflows || bond.cashflows.length === 0) {
    return { eligible: false, code: 'sin_flujos', reason: 'Sin cronograma de flujos' };
  }
  const tea = teaOf(bond);
  if (!(bond.eval_price > 0) || tea === null) {
    return { eligible: false, code: 'sin_tir', reason: 'Sin precio o TIR para proyectar el precio de salida' };
  }
  const FEE_RATE = 0.005;
  const evalPrice = bond.eval_price * (1.0 + FEE_RATE);

  const mode = opts.exitMode || 'tir';
  const maxYear = Math.max(...bond.cashflows.map(c => c.years));
  const maturesBefore = maxYear < (horizonYrs - 0.05);
  if (maturesBefore && !opts.includeMatured) {
    return {
      eligible: false, code: 'vence_antes', maturityYears: maxYear,
      reason: `Vence en ${maxYear.toFixed(1)} años (antes de los ${horizonYrs.toFixed(1)} años)`
    };
  }
  // An instrument that matures earlier is measured over its own life (its TIR to maturity)
  const effYears = maturesBefore ? maxYear : horizonYrs;

  const cfsDuring = bond.cashflows.filter(c => c.years <= (horizonYrs + 0.01));
  const cfsAfter = bond.cashflows.filter(c => c.years > (horizonYrs + 0.01));

  const cashCollected = cfsDuring.reduce((acc, c) => acc + c.total, 0.0);
  if (cfsDuring.length === 0 && mode !== 'tir') {
    return { eligible: false, code: 'sin_pagos_en_plazo', maturityYears: maxYear, reason: 'No paga cupones ni amortizaciones dentro del plazo' };
  }

  // Value assigned to what is still unpaid at the horizon:
  //   'par'  -> ceteris paribus: the price does not move, so the residual is worth today's price
  //             in proportion to the capital not yet amortized (no capital gain or loss)
  //   'cero' -> strictly cash: nothing beyond the horizon counts
  //   'tir'  -> sold at the bond's current TIR (used by Escenarios)
  let terminalPrice = 0.0;
  let exitNote = 'todo el capital se cobró dentro del plazo';
  if (cfsAfter.length > 0) {
    if (mode === 'tir') {
      cfsAfter.forEach(c => { terminalPrice += c.total / Math.pow(1.0 + tea / 100.0, c.years - horizonYrs); });
      exitNote = `${cfsAfter.length} flujos restantes descontados a TEA ${tea}%`;
    } else if (mode === 'par') {
      const vrNow = bond.vr > 0 ? bond.vr : 100.0;
      const vrLeft = cfsDuring.length ? cfsDuring[cfsDuring.length - 1].remaining_vr : vrNow;
      terminalPrice = bond.eval_price * (vrLeft / vrNow);
      exitNote = `precio de hoy ${bond.eval_price} x capital residual ${round4(vrLeft)}/${round4(vrNow)}`;
    } else {
      exitNote = 'no se cuenta nada posterior al plazo (valor residual = 0)';
    }
  }

  const totalInflow = cashCollected + terminalPrice;
  const hprPct = ((totalInflow - evalPrice) / evalPrice) * 100.0;

  const pvAt = (r) => cfsDuring.reduce((acc, c) => acc + c.total / Math.pow(1.0 + r, c.years), 0.0) +
    terminalPrice / Math.pow(1.0 + r, effYears);
  const root = solveEffectiveRate(pvAt, evalPrice);
  if (root === null) {
    return { eligible: false, code: 'sin_raiz', reason: 'La TIR al horizonte no tiene solución en [-95%, 1000%]' };
  }
  const horizonTir = root * 100.0;

  if (opts.trace) {
    qaTrace('Horizonte', `${bond.symbol} a ${horizonYrs} años`, {
      '1. Dato crudo (backend)': { eval_price: bond.eval_price, 'tir_tea (%)': bond.tir_tea, base: yieldBasis(bond), vence_en_años: round4(maxYear) },
      '2. Precio de compra con comisión': round4(evalPrice),
      '3. Flujos cobrados en el plazo': { cantidad: cfsDuring.length, efectivo: round4(cashCollected) },
      '4. Valor residual al plazo': `modo "${mode}": ${exitNote} = ${round4(terminalPrice)}`,
      '4b. Plazo efectivo (años)': maturesBefore ? `${round4(effYears)} (vence antes del plazo pedido)` : effYears,
      '5. Resultado': { retorno_acumulado_pct: round4(hprPct), 'TIR al horizonte (TEA %)': round4(horizonTir) }
    });
  }

  return {
    eligible: true,
    bond: bond,
    symbol: bond.symbol,
    name: bond.name || bond.symbol,
    type: bond.type,
    law: bond.law,
    price: evalPrice,
    maturityDate: bond.maturity_date,
    maturityYears: maxYear,
    maturesBefore: maturesBefore,
    cashCollected: cashCollected,
    terminalPrice: terminalPrice,
    totalInflow: totalInflow,
    hprPct: hprPct,
    horizonTir: horizonTir
  };
}

function horizonFallbackRow(html) {
  document.getElementById('horizonRankingBody').innerHTML =
    `<tr><td colspan="11" class="center" style="padding: 24px; color: var(--text-dim);">${html}</td></tr>`;
  document.getElementById('horizonWinnerCard').style.display = 'none';
  const eligibleCountEl = document.getElementById('horizonEligibleCount');
  if (eligibleCountEl) eligibleCountEl.innerText = '0 instrumentos elegibles';
  if (horizonChart) { horizonChart.destroy(); horizonChart = null; }
}

function setHorizonYears(yrs) {
  horizonYears = yrs;
  const slider = document.getElementById('horizonSlider');
  if (slider) slider.value = yrs;
  document.querySelectorAll('.horizon-preset-btn').forEach(b => b.classList.toggle('active', parseFloat(b.dataset.years) === yrs));
  runHorizonCalculation();
}

function runHorizonCalculation() {
  try {
    renderHorizonRanking();
  } catch (err) {
    // A rendering error must never leave the section silently blank
    console.error('QA Trace · Horizonte · error de renderizado:', err);
    horizonFallbackRow(`No se pudo calcular el comparador: ${String(err && err.message || err)}. El detalle está en la consola (F12).`);
  }
}

function renderHorizonRanking() {
  updateHorizonDisplays();

  // Funnel: every stage is counted so an empty table can always be explained
  const universe = dcfUniverse(horizCcy);
  const hOpts = { exitMode: horizExitMode, includeMatured: horizIncludeMatured };
  const evaluated = universe.map(b => calculateBondHorizon(b, horizonYears, hOpts));
  const results = evaluated.filter(r => r.eligible);
  const rejected = {};
  evaluated.filter(r => !r.eligible).forEach(r => { rejected[r.code] = (rejected[r.code] || 0) + 1; });
  const longest = universe.reduce((best, b) => {
    const y = Math.max(...b.cashflows.map(c => c.years));
    return (!best || y > best.years) ? { symbol: b.symbol, years: y } : best;
  }, null);

  // In pesos, CER bonds yield a REAL rate and Lecaps a NOMINAL one: rank both on a nominal basis,
  // converting the real rate with the expected inflation (BCRA REM) via Fisher.
  const inflTEA = defaultInflTEA();
  results.forEach(r => {
    r.rankTir = (horizCcy === 'ARS' && r.bond.is_cer) ? compound(r.horizonTir, inflTEA) : r.horizonTir;
  });

  // Sort by Horizon TIR descending (best investment on top)
  results.sort((a, b) => b.rankTir - a.rankTir);

  qaTrace('Horizonte', `ranking ${horizCcy} a ${horizonYears} años`, {
    '0. Criterio': { valor_residual: horizExitMode, incluye_los_que_vencen_antes: horizIncludeMatured },
    '1. Instrumentos en el payload': allBonds.length,
    [`2. Pagan en ${horizCcy}, cotizan en ${horizCcy} y tienen flujos`]: universe.length,
    '3. Descartados (motivo -> cantidad)': rejected,
    '4. Elegibles': results.length,
    '5. Instrumento más largo disponible': longest
  }, results.map(r => ({
    ticker: r.symbol, precio: round4(r.price), vence_en_años: round4(r.maturityYears), efectivo: round4(r.cashCollected),
    precio_salida: round4(r.terminalPrice), 'retorno_%': round4(r.hprPct), 'TIR_horizonte_TEA_%': round4(r.horizonTir), base: yieldBasis(r.bond),
    'TIR_para_ranking_%': round4(r.rankTir)
  })));

  // Fallbacks: say WHY there is nothing to show
  if (allBonds.length === 0) {
    horizonFallbackRow(`Sin datos de mercado${lastLoadError ? `: ${lastLoadError}` : ''}. Usá el botón de actualizar para reintentar.`);
    return;
  }
  if (universe.length === 0) {
    horizonFallbackRow(`No hay instrumentos en ${horizCcy} con cronograma de flujos cargado. Probá con la otra moneda.`);
    return;
  }
  if (results.length === 0 && horizIncludeMatured) {
    horizonFallbackRow(`Ningún instrumento en ${horizCcy} paga flujos dentro de ${horizonYears.toFixed(1)} años (${universe.length} evaluados).`);
    return;
  }
  if (results.length === 0) {
    const maxHorizon = Math.max(0.5, Math.floor(longest.years * 2) / 2);
    horizonFallbackRow(`Ningún instrumento en ${horizCcy} vence después de ${horizonYears.toFixed(1)} años.
      El más largo es <strong>${longest.symbol}</strong> (${longest.years.toFixed(1)} años).
      <button class="btn-inspect" onclick="setHorizonYears(${maxHorizon})">Ajustar el horizonte a ${maxHorizon.toFixed(1)} años</button>`);
    return;
  }

  const eligibleCountEl = document.getElementById('horizonEligibleCount');
  if (eligibleCountEl) eligibleCountEl.innerText = `${results.length} instrumentos elegibles`;

  const rankingTbody = document.getElementById('horizonRankingBody');
  rankingTbody.innerHTML = '';
  document.getElementById('horizonWinnerCard').style.display = 'flex';

  // Winner Showcase (Top #1)
  const winner = results[0];
  calculateBondHorizon(winner.bond, horizonYears, { ...hOpts, trace: true });
  const winCur = curSymbol(winner.bond.currency);
  const pctSigned = (v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`;
  document.getElementById('winnerTicker').innerText = winner.symbol;
  document.getElementById('winnerName').innerText = `${winner.name} (${winner.law || 'Argentina'})`;
  document.getElementById('winnerTir').innerText = `${winner.horizonTir.toFixed(2)}%${winner.bond.is_cer ? ' real' : ''}`;
  document.getElementById('winnerCash').innerText = `${winCur} ${fmtNum(winner.cashCollected)}`;
  document.getElementById('winnerTerminal').innerText = `${winCur} ${fmtNum(winner.terminalPrice)}`;
  document.getElementById('winnerHpr').innerText = pctSigned(winner.hprPct);

  // Render Table
  results.forEach((r, idx) => {
    const tr = document.createElement('tr');
    const isWinner = (idx === 0);
    const rowCur = curSymbol(r.bond.currency);
    if (isWinner) tr.style.backgroundColor = 'rgba(245, 158, 11, 0.12)';

    tr.innerHTML = `
      <td class="center" style="font-weight:700; color:${isWinner ? 'var(--accent-amber)' : 'var(--text-dim)'};">
        ${isWinner ? '🏆 #1' : `#${idx + 1}`}
      </td>
      <td>
        <strong style="color:#fff; font-family:var(--font-mono);">${r.symbol}</strong>
      </td>
      <td style="font-size:11px; color:var(--text-muted);">${r.type} &bull; ${r.law || 'Arg'}</td>
      <td class="right" style="font-weight:700;">${rowCur} ${fmtNum(r.price)}</td>
      <td class="center" style="font-size:11px; color:var(--text-muted);">${r.maturityDate ? r.maturityDate.substring(0, 10) : '-'}</td>
      <td class="right">${r.maturityYears.toFixed(1)} a${r.maturesBefore ? '<div style="font-size:10px; color:var(--accent-amber);" title="Se mide hasta su vencimiento; compararlo con el plazo completo supone reinvertir a la misma tasa">vence antes</div>' : ''}</td>
      <td class="right" style="color:var(--text-main); font-weight:700;">${rowCur} ${fmtNum(r.cashCollected)}</td>
      <td class="right" style="color:var(--text-muted);">${rowCur} ${fmtNum(r.terminalPrice)}</td>
      <td class="right" style="color:${r.hprPct >= 0 ? 'var(--accent-green)' : '#f43f5e'}; font-weight:700;">${pctSigned(r.hprPct)}</td>
      <td class="right highlight-col" style="font-size:13px; font-weight:800; font-family:var(--font-mono);">
        ${r.horizonTir.toFixed(2)}%${r.bond.is_cer ? ` <span style="font-size:10px; font-weight:normal;">real</span>
          <div style="font-size:10px; font-weight:normal; color:var(--text-dim);">≈ ${r.rankTir.toFixed(1)}% nominal (infl. ${inflTEA.toFixed(1)}%)</div>` : ''}
      </td>
      <td class="center">
        <button class="btn-inspect" onclick="openBondModal('${r.symbol}')">Ficha</button>
      </td>
    `;
    rankingTbody.appendChild(tr);
  });

  // Render Horizon Bar Chart (Chart.js comes from a CDN: the table must survive without it)
  if (typeof Chart !== 'undefined') renderHorizonChart(results.map(r => ({ ...r, horizonTir: r.rankTir })));
}

function renderHorizonChart(results) {
  const ctx = document.getElementById('horizonChart');
  if (!ctx) return;

  if (horizonChart) {
    horizonChart.destroy();
  }

  const labels = results.map(r => r.symbol);
  const dataTir = results.map(r => r.horizonTir);
  const colors = results.map((r, idx) => idx === 0 ? '#fbbf24' : '#38bdf8');

  horizonChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: `TIR a ${horizonYears.toFixed(1)} años (%)`,
        data: dataTir,
        backgroundColor: colors,
        borderRadius: 6,
        borderWidth: 1,
        borderColor: colors
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1b1f2c',
          titleColor: '#fff',
          bodyColor: '#38bdf8',
          callbacks: {
            label: (ctx) => `TIR Anualizada al horizonte: ${ctx.parsed.y.toFixed(2)}%`
          }
        }
      },
      scales: {
        x: {
          grid: { color: '#202738' },
          ticks: { color: '#f1f5f9', font: { family: 'monospace', weight: 'bold' } }
        },
        y: {
          grid: { color: '#202738' },
          ticks: {
            color: '#94a3b8',
            callback: (v) => `${v}%`
          }
        }
      }
    }
  });
}

// ========================================================
// 4. CHARTS VIEW (ESTRUCTURA TEMPORAL Y CURVAS DE RENDIMIENTO)
// ========================================================
const CURVE_SHAPE_META = {
  normal: {
    label: 'Normal o Positiva',
    cardId: 'shapeCardNormal',
    badgeId: 'badgeShapeNormal',
    color: '#38bdf8',
    explain: 'Los plazos largos rinden más que los cortos. Refleja la prima por plazo/liquidez habitual: el inversor exige mayor rendimiento por inmovilizar capital durante más tiempo.'
  },
  plana: {
    label: 'Plana',
    cardId: 'shapeCardPlana',
    badgeId: 'badgeShapePlana',
    color: '#94a3b8',
    explain: 'Todos los plazos ofrecen rendimientos similares. Suele aparecer en etapas de transición cuando el mercado no anticipa movimientos bruscos de tasas.'
  },
  invertida: {
    label: 'Invertida',
    cardId: 'shapeCardInvertida',
    badgeId: 'badgeShapeInvertida',
    color: '#f43f5e',
    explain: 'Los plazos cortos rinden más que los largos. Indica que el mercado descuenta una baja futura de tasas (desinflación) o percibe mayor tensión de refinanciación en el corto plazo.'
  },
  joroba: {
    label: 'Con Joroba',
    cardId: 'shapeCardJoroba',
    badgeId: 'badgeShapeJoroba',
    color: '#10b981',
    explain: 'El rendimiento sube desde el tramo corto hasta alcanzar un máximo en el tramo medio y luego se aplana o cede en el tramo largo, concentrando la prima de riesgo en los vencimientos intermedios.'
  }
};

function initChartsEvents() {
  document.querySelectorAll('[data-curve-fam]').forEach(btn => {
    btn.addEventListener('click', () => {
      curveFamily = btn.dataset.curveFam;
      document.querySelectorAll('[data-curve-fam]').forEach(b => b.classList.toggle('active', b.dataset.curveFam === curveFamily));
      renderCharts();
    });
  });

  document.querySelectorAll('[data-curve-axis]').forEach(btn => {
    btn.addEventListener('click', () => {
      curveAxis = btn.dataset.curveAxis;
      document.querySelectorAll('[data-curve-axis]').forEach(b => b.classList.toggle('active', b.dataset.curveAxis === curveAxis));
      renderCharts();
    });
  });

  document.querySelectorAll('.curve-shape-card').forEach(card => {
    card.addEventListener('click', () => {
      const sh = card.dataset.shape;
      curveTheoryOverlay = (curveTheoryOverlay === sh) ? null : sh;
      renderCharts();
    });
  });

  const btnReset = document.getElementById('btnResetTheoryCurve');
  if (btnReset) {
    btnReset.addEventListener('click', () => {
      curveTheoryOverlay = null;
      renderCharts();
    });
  }
}

// Years to maturity of a bond (prefer exact days_to_maturity / 365, fallback to last cashflow year)
function bondYearsToMaturity(b) {
  if (hasNum(b.days_to_maturity) && b.days_to_maturity > 0) return b.days_to_maturity / 365.0;
  if (b.cashflows && b.cashflows.length > 0) {
    return Math.max(...b.cashflows.map(c => c.years || 0));
  }
  return 0;
}

// X coordinate according to selected axis ('years' or 'md')
function bondCurveX(b) {
  if (curveAxis === 'md') {
    if (hasNum(b.mod_duration) && b.mod_duration > 0) return b.mod_duration;
    if (hasNum(b.duration) && b.duration > 0) return b.duration;
  }
  return bondYearsToMaturity(b);
}

/**
 * Fits a smooth term-structure curve y(x) = b0 + b1*u + b2*u^2 with u = ln(max(x, 0.05))
 * via regularized Ordinary Least Squares (Nelson-Siegel quadratic approximation).
 * Because y(x) is a single-valued function of x, it never loops backward or zigzags due to
 * coupon differences between adjacent bonds (Cap. 11.4 & Cap. 41 of the Diplomado).
 */
function fitTermStructureCurve(points, numGrid = 45) {
  if (!points || points.length === 0) return { grid: [], predict: () => 0, b0: 0, b1: 0, b2: 0 };
  const sorted = [...points].sort((a, b) => a.x - b.x);
  const n = sorted.length;
  const xMin = sorted[0].x;
  const xMax = sorted[n - 1].x;

  if (n === 1 || Math.abs(xMax - xMin) < 1e-4) {
    const y0 = sorted[0].y;
    return {
      grid: [{ x: Math.max(0.1, xMin * 0.8), y: y0 }, { x: xMax * 1.2 + 0.5, y: y0 }],
      predict: () => y0,
      b0: y0, b1: 0, b2: 0
    };
  }

  const uOf = (x) => Math.log(Math.max(x, 0.05));
  const us = sorted.map(p => uOf(p.x));
  const ys = sorted.map(p => p.y);
  const uMean = us.reduce((a, b) => a + b, 0) / n;
  const uCentered = us.map(u => u - uMean);

  // Build 3x3 normal equations for y = a0 + a1*uc + a2*uc^2 with mild ridge penalty on curvature a2
  let s0 = n, s1 = 0, s2 = 0, s3 = 0, s4 = 0;
  let ty0 = 0, ty1 = 0, ty2 = 0;
  for (let i = 0; i < n; i++) {
    const uc = uCentered[i];
    const uc2 = uc * uc;
    const y = ys[i];
    s1 += uc;
    s2 += uc2;
    s3 += uc2 * uc;
    s4 += uc2 * uc2;
    ty0 += y;
    ty1 += uc * y;
    ty2 += uc2 * y;
  }

  // If fewer than 3 distinct x values, use linear fit in log-tenor (a2 = 0)
  const distinctX = new Set(sorted.map(p => p.x.toFixed(2))).size;
  const ridge2 = distinctX >= 3 ? 0.12 : 1e6;
  const A = [
    [s0, s1, s2, ty0],
    [s1, s2 + 1e-4, s3, ty1],
    [s2, s3, s4 + ridge2, ty2]
  ];

  // Gaussian elimination with partial pivoting
  for (let col = 0; col < 3; col++) {
    let pivot = col;
    for (let row = col + 1; row < 3; row++) {
      if (Math.abs(A[row][col]) > Math.abs(A[pivot][col])) pivot = row;
    }
    const tmp = A[col]; A[col] = A[pivot]; A[pivot] = tmp;
    const div = A[col][col] || 1e-9;
    for (let j = col; j <= 3; j++) A[col][j] /= div;
    for (let row = 0; row < 3; row++) {
      if (row !== col) {
        const factor = A[row][col];
        for (let j = col; j <= 3; j++) A[row][j] -= factor * A[col][j];
      }
    }
  }

  const a0 = A[0][3], a1 = A[1][3], a2 = A[2][3];
  const predict = (x) => {
    const uc = uOf(x) - uMean;
    return a0 + a1 * uc + a2 * uc * uc;
  };

  const grid = [];
  for (let i = 0; i < numGrid; i++) {
    const x = xMin + (xMax - xMin) * (i / (numGrid - 1));
    grid.push({ x, y: predict(x) });
  }
  return { grid, predict, b0: a0, b1: a1, b2: a2 };
}

/**
 * Classifies the fitted curve into one of the 4 canonical shapes from Unidad 4 (Cap. 11.2 / Lámina 27):
 *   - 'normal'    : upward sloping (long > short)
 *   - 'plana'     : flat across maturities
 *   - 'invertida' : downward sloping (short > long)
 *   - 'joroba'    : humped (rises to an intermediate peak and then declines or strongly flattens)
 */
function classifyCurveShape(grid, rawPoints = []) {
  if (!grid || grid.length < 3) return { shape: 'plana', slope: 0, peakX: 0, span: 0 };
  const n = grid.length;
  const yStart = grid[0].y;
  const yEnd = grid[n - 1].y;
  const yMid = grid[Math.floor(n / 2)].y;

  let maxIdx = 0, minIdx = 0;
  for (let i = 1; i < n; i++) {
    if (grid[i].y > grid[maxIdx].y) maxIdx = i;
    if (grid[i].y < grid[minIdx].y) minIdx = i;
  }
  const yMax = grid[maxIdx].y;
  const yMin = grid[minIdx].y;
  const span = yMax - yMin;
  const avgAbs = Math.max(4.0, Math.abs(yMid));
  const flatThreshold = Math.max(0.55, avgAbs * 0.045);

  if (span <= flatThreshold) {
    return { shape: 'plana', slope: yEnd - yStart, peakX: grid[maxIdx].x, span };
  }

  // Check for interior hump on the fitted curve OR clear intermediate peak in raw observations
  const riseToPeak = yMax - yStart;
  const dropFromPeak = yMax - yEnd;
  if (maxIdx > 2 && maxIdx < n - 3 && riseToPeak > 0.35 && dropFromPeak > 0.25) {
    return { shape: 'joroba', slope: yEnd - yStart, peakX: grid[maxIdx].x, span };
  }

  // Also check if raw points sorted by x show an interior peak higher than the longest bond
  if (rawPoints && rawPoints.length >= 4) {
    const sp = [...rawPoints].sort((a, b) => a.x - b.x);
    const firstY = sp[0].y;
    const lastY = sp[sp.length - 1].y;
    const midPoints = sp.slice(1, sp.length - 1);
    const maxMid = midPoints.reduce((m, p) => p.y > m.y ? p : m, midPoints[0]);
    if ((maxMid.y - firstY) > 0.8 && (maxMid.y - lastY) > 0.35) {
      return { shape: 'joroba', slope: yEnd - yStart, peakX: maxMid.x, span };
    }
  }

  if (yEnd > yStart) {
    return { shape: 'normal', slope: yEnd - yStart, peakX: grid[maxIdx].x, span };
  }
  return { shape: 'invertida', slope: yEnd - yStart, peakX: grid[minIdx].x, span };
}

// Generates a theoretical reference curve over [xMin, xMax] centered around yCenter
function buildTheoreticalCurve(shape, xMin, xMax, yCenter) {
  const n = 45;
  const spanY = Math.max(3.0, Math.abs(yCenter) * 0.28);
  const pts = [];
  for (let i = 0; i < n; i++) {
    const t = i / (n - 1); // 0 .. 1
    const x = xMin + (xMax - xMin) * t;
    let y = yCenter;
    if (shape === 'normal') {
      // Concave upward-sloping curve
      y = (yCenter - spanY * 0.55) + spanY * Math.pow(t, 0.58);
    } else if (shape === 'plana') {
      y = yCenter + 0.08 * Math.sin(t * Math.PI);
    } else if (shape === 'invertida') {
      // Downward-sloping curve
      y = (yCenter + spanY * 0.55) - spanY * Math.pow(t, 0.62);
    } else if (shape === 'joroba') {
      // Humped curve peaking at t ~ 0.42 and declining afterwards
      y = (yCenter - spanY * 0.45) + spanY * 1.35 * Math.sin(Math.pow(t, 0.72) * Math.PI * 0.88);
    }
    pts.push({ x, y });
  }
  return pts;
}

// Inline Chart.js plugin to draw ticker labels next to scatter points without overlapping
const pointTickerLabelsPlugin = {
  id: 'pointTickerLabels',
  afterDatasetsDraw(chart) {
    const { ctx, chartArea } = chart;
    if (!chartArea) return;
    ctx.save();
    ctx.font = 'bold 10.5px "JetBrains Mono", Consolas, monospace';
    const placed = [];

    chart.data.datasets.forEach((ds, dsIdx) => {
      if (!ds.drawPointLabels) return;
      const meta = chart.getDatasetMeta(dsIdx);
      if (!meta || meta.hidden) return;

      meta.data.forEach((elem, index) => {
        const raw = ds.data[index];
        if (!raw || !raw.symbol) return;
        const { x, y } = elem.tooltipPosition();
        if (x < chartArea.left || x > chartArea.right || y < chartArea.top || y > chartArea.bottom) return;

        const text = raw.symbol;
        const tw = ctx.measureText(text).width;
        // Try candidate offsets around the point to prevent label collisions
        const candidates = [
          { dx: 8, dy: -8 },
          { dx: 8, dy: 12 },
          { dx: -tw - 8, dy: -8 },
          { dx: -tw - 8, dy: 12 },
          { dx: -tw / 2, dy: -13 },
          { dx: -tw / 2, dy: 16 }
        ];
        let chosen = candidates[0];
        for (const c of candidates) {
          let lx = Math.min(Math.max(chartArea.left + 2, x + c.dx), chartArea.right - tw - 2);
          let ly = Math.min(Math.max(chartArea.top + 10, y + c.dy), chartArea.bottom - 4);
          const collides = placed.some(p => Math.abs(p.x - lx) < (tw + 6) && Math.abs(p.y - ly) < 12);
          if (!collides) {
            chosen = { x: lx, y: ly };
            break;
          }
          chosen = { x: lx, y: ly };
        }
        placed.push(chosen);

        ctx.fillStyle = 'rgba(12, 16, 23, 0.82)';
        ctx.fillRect(chosen.x - 2, chosen.y - 9, tw + 4, 12);
        ctx.fillStyle = ds.borderColor || '#f8fafc';
        ctx.fillText(text, chosen.x, chosen.y);
      });
    });
    ctx.restore();
  }
};

function updateCurveShapeCardsUI(detectedShapes, primaryShape) {
  ['normal', 'plana', 'invertida', 'joroba'].forEach(sh => {
    const meta = CURVE_SHAPE_META[sh];
    const card = document.getElementById(meta.cardId);
    const badge = document.getElementById(meta.badgeId);
    if (!card || !badge) return;

    const isMarketMatch = detectedShapes.includes(sh);
    const isTheoryMatch = (curveTheoryOverlay === sh);

    card.classList.toggle('active-market', isMarketMatch);
    card.classList.toggle('active-theory', isTheoryMatch);

    badge.className = 'curve-shape-badge';
    if (isTheoryMatch) {
      badge.classList.add('show-theory');
      badge.innerText = 'MODELO TEÓRICO ACTIVO';
    } else if (isMarketMatch) {
      badge.classList.add('show-market');
      badge.innerText = sh === primaryShape ? 'FORMA ACTUAL EN MERCADO' : 'TAMBIÉN OBSERVADA';
    } else {
      badge.innerText = '';
    }
  });

  const btnReset = document.getElementById('btnResetTheoryCurve');
  if (btnReset) btnReset.style.display = curveTheoryOverlay ? 'inline-block' : 'none';
}

function renderCharts() {
  renderCurveChart();
  renderParityChart();
}

function renderCurveChart() {
  const ctx = document.getElementById('curveChart');
  if (!ctx || typeof Chart === 'undefined') return;
  if (curveChart) curveChart.destroy();

  const xLabel = curveAxis === 'md' ? 'Duration Modificada (Años)' : 'Plazo al Vencimiento (Años)';
  const seriesList = [];

  if (curveFamily === 'usd') {
    const bonares = [];
    const globales = [];
    allBonds.forEach(b => {
      const tea = teaOf(b);
      const xVal = bondCurveX(b);
      if (b.family === 'soberano_usd' && b.is_native_quote && tea !== null && tea > -20 && tea < 60 && xVal > 0) {
        const pt = {
          x: xVal, y: tea, symbol: b.symbol,
          years: bondYearsToMaturity(b), md: b.mod_duration || 0, parity: b.parity || 0
        };
        if (b.symbol.startsWith('AL') || b.symbol.startsWith('AE') || b.symbol.startsWith('AO') || b.symbol.startsWith('AN')) {
          bonares.push(pt);
        } else if (b.symbol.startsWith('GD')) {
          globales.push(pt);
        }
      }
    });
    if (bonares.length) seriesList.push({ name: 'Bonares (Ley Arg)', color: '#38bdf8', points: bonares });
    if (globales.length) seriesList.push({ name: 'Globales (Ley NY)', color: '#10b981', points: globales });
  } else if (curveFamily === 'lecap') {
    const letras = [];
    allBonds.forEach(b => {
      const tea = teaOf(b);
      const xVal = bondCurveX(b);
      if (b.family === 'letra' && b.is_native_quote && b.currency === 'ARS' && !b.is_cer && tea !== null && tea > 0 && tea < 150 && xVal > 0) {
        letras.push({
          x: xVal, y: tea, symbol: b.symbol,
          years: bondYearsToMaturity(b), md: b.mod_duration || 0, parity: b.parity || 0
        });
      }
    });
    if (letras.length) seriesList.push({ name: 'Tasa Fija ARS (LECAP / BONCAP)', color: '#f59e0b', points: letras });
  } else if (curveFamily === 'cer') {
    const cerPts = [];
    allBonds.forEach(b => {
      const tea = teaOf(b);
      const xVal = bondCurveX(b);
      if ((b.family === 'cer' || b.is_cer) && b.is_native_quote && b.currency === 'ARS' && tea !== null && tea > -25 && tea < 60 && xVal > 0) {
        cerPts.push({
          x: xVal, y: tea, symbol: b.symbol,
          years: bondYearsToMaturity(b), md: b.mod_duration || 0, parity: b.parity || 0
        });
      }
    });
    if (cerPts.length) seriesList.push({ name: 'Bonos CER (TIR Real % sobre CER)', color: '#c084fc', points: cerPts });
  }

  const datasets = [];
  const detectedShapes = [];
  const diagnosisParts = [];
  let allX = [];
  let allY = [];

  seriesList.forEach(s => {
    s.points.sort((a, b) => a.x - b.x);
    s.points.forEach(p => { allX.push(p.x); allY.push(p.y); });

    const fit = fitTermStructureCurve(s.points);
    const diag = classifyCurveShape(fit.grid, s.points);
    if (!detectedShapes.includes(diag.shape)) detectedShapes.push(diag.shape);

    const shapeMeta = CURVE_SHAPE_META[diag.shape];
    // Identify cheapest bond (highest residual above curve) and richest bond (lowest residual below curve)
    let cheap = null, rich = null;
    s.points.forEach(p => {
      const diff = p.y - fit.predict(p.x);
      if (!cheap || diff > cheap.diff) cheap = { symbol: p.symbol, diff };
      if (!rich || diff < rich.diff) rich = { symbol: p.symbol, diff };
    });
    const relNote = (s.points.length >= 3 && cheap && rich)
      ? ` Sobre la curva (mayor TIR para su plazo): <strong>${cheap.symbol}</strong> (${cheap.diff >= 0 ? '+' : ''}${cheap.diff.toFixed(2)} pp); debajo de la curva: <strong>${rich.symbol}</strong> (${rich.diff.toFixed(2)} pp).`
      : '';

    diagnosisParts.push(
      `<div><span style="color:${s.color}; font-weight:800;">● ${s.name}:</span> Forma <strong>${shapeMeta.label.toUpperCase()}</strong> ` +
      `(tramo corto ${fit.grid[0].y.toFixed(2)}% → tramo largo ${fit.grid[fit.grid.length - 1].y.toFixed(2)}%, amplitud ${diag.span.toFixed(2)} pp). ` +
      `${shapeMeta.explain}${relNote}</div>`
    );

    // 1. Smooth fitted curve dataset (continuous line, no dots)
    datasets.push({
      label: `Curva ${s.name} (${shapeMeta.label})`,
      data: fit.grid,
      borderColor: s.color,
      backgroundColor: 'transparent',
      borderWidth: 2.6,
      pointRadius: 0,
      pointHoverRadius: 0,
      showLine: true,
      tension: 0.25,
      drawPointLabels: false
    });

    // 2. Observed bonds scatter dataset (dots + ticker labels)
    datasets.push({
      label: `Bonos ${s.name}`,
      data: s.points,
      backgroundColor: s.color,
      borderColor: s.color,
      pointRadius: 6,
      pointHoverRadius: 8,
      showLine: false,
      drawPointLabels: true
    });
  });

  const primaryShape = detectedShapes[0] || 'normal';
  updateCurveShapeCardsUI(detectedShapes, primaryShape);

  // Optional Theoretical Reference Curve overlay when user clicks one of the 4 cards
  if (curveTheoryOverlay) {
    const xMin = allX.length ? Math.min(...allX) : 1.0;
    const xMax = allX.length ? Math.max(...allX) : 12.0;
    const yAvg = allY.length ? (allY.reduce((a, b) => a + b, 0) / allY.length) : 10.0;
    const thMeta = CURVE_SHAPE_META[curveTheoryOverlay];
    const thGrid = buildTheoreticalCurve(curveTheoryOverlay, xMin, Math.max(xMin + 2.0, xMax), yAvg);

    datasets.push({
      label: `Modelo Teórico: Curva ${thMeta.label}`,
      data: thGrid,
      borderColor: '#fbbf24',
      backgroundColor: 'transparent',
      borderWidth: 2.5,
      borderDash: [7, 5],
      pointRadius: 0,
      pointHoverRadius: 0,
      showLine: true,
      tension: 0.3,
      drawPointLabels: false
    });

    diagnosisParts.unshift(
      `<div style="color:#fbbf24; margin-bottom:4px;"><strong>📐 Previsualización Teórica Activa (${thMeta.label}):</strong> ${thMeta.explain} <em>(Línea punteada amarilla en el gráfico; haz click nuevamente en la tarjeta para ocultarla).</em></div>`
    );
  }

  const banner = document.getElementById('curveDiagnosisBanner');
  if (banner) {
    banner.innerHTML = diagnosisParts.length
      ? diagnosisParts.join('')
      : 'No hay suficientes instrumentos con TIR calculable para trazar esta familia en este momento.';
  }

  const titleEl = document.getElementById('curveChartTitle');
  if (titleEl) {
    const famLabel = curveFamily === 'usd' ? 'Soberana USD (Bonares vs Globales)'
      : (curveFamily === 'lecap' ? 'Pesos Tasa Fija (LECAP / BONCAP)' : 'Pesos CER (Boncer)');
    titleEl.innerText = `Curva ${famLabel}: TIR (TEA %) vs ${xLabel}`;
  }

  qaTrace('Curvas', `Familia=${curveFamily} · EjeX=${curveAxis}`, {
    'Series graficadas': seriesList.map(s => ({ nombre: s.name, bonos: s.points.length })),
    'Formas detectadas': detectedShapes,
    'Overlay teórico': curveTheoryOverlay || 'ninguno'
  }, seriesList.flatMap(s => s.points.map(p => ({ ticker: p.symbol, x: round4(p.x), 'TIR_TEA_%': round4(p.y), plazo_años: round4(p.years), MD: round4(p.md) }))));

  curveChart = new Chart(ctx, {
    type: 'scatter',
    plugins: [pointTickerLabelsPlugin],
    data: { datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      layout: { padding: { top: 18, right: 28, bottom: 6, left: 6 } },
      plugins: {
        legend: {
          labels: {
            color: '#cbd5e1',
            filter: (item) => !item.text.startsWith('Bonos ')
          }
        },
        tooltip: {
          backgroundColor: '#1a1f2c',
          callbacks: {
            label: (c) => {
              const r = c.raw;
              if (r && r.symbol) {
                return `${r.symbol} · TIR ${r.y.toFixed(2)}% TEA · Plazo ${r.years.toFixed(2)} a · MD ${r.md.toFixed(2)} a`;
              }
              return `${c.dataset.label}: ${r.y.toFixed(2)}% (${xLabel}: ${r.x.toFixed(2)} a)`;
            }
          }
        }
      },
      scales: {
        x: {
          title: { display: true, text: xLabel, color: '#94a3b8' },
          grid: { color: '#202738' },
          ticks: { color: '#94a3b8' }
        },
        y: {
          title: { display: true, text: curveFamily === 'cer' ? 'TIR Real sobre CER (TEA %)' : 'TIR (TEA %)', color: '#94a3b8' },
          grid: { color: '#202738' },
          ticks: { color: '#94a3b8', callback: (v) => `${Number(v).toFixed(1)}%` }
        }
      }
    }
  });
}

function renderParityChart() {
  const ctx = document.getElementById('parityChart');
  if (!ctx || typeof Chart === 'undefined') return;
  if (parityChart) parityChart.destroy();

  const xLabel = curveAxis === 'md' ? 'Duration Modificada (Años)' : 'Plazo al Vencimiento (Años)';
  const seriesList = [];

  if (curveFamily === 'usd') {
    const bonares = [];
    const globales = [];
    allBonds.forEach(b => {
      const xVal = bondCurveX(b);
      if (b.family === 'soberano_usd' && b.is_native_quote && b.parity > 0 && b.parity < 150 && xVal > 0) {
        const pt = { x: xVal, y: b.parity, symbol: b.symbol, tir: teaOf(b) };
        if (b.symbol.startsWith('AL') || b.symbol.startsWith('AE') || b.symbol.startsWith('AO') || b.symbol.startsWith('AN')) {
          bonares.push(pt);
        } else if (b.symbol.startsWith('GD')) {
          globales.push(pt);
        }
      }
    });
    if (bonares.length) seriesList.push({ name: 'Paridad Bonares (Ley Arg)', color: '#38bdf8', points: bonares });
    if (globales.length) seriesList.push({ name: 'Paridad Globales (Ley NY)', color: '#a855f7', points: globales });
  } else {
    const pts = [];
    allBonds.forEach(b => {
      const xVal = bondCurveX(b);
      const matchFam = curveFamily === 'lecap' ? (b.family === 'letra' && !b.is_cer) : (b.family === 'cer' || b.is_cer);
      if (matchFam && b.is_native_quote && b.currency === 'ARS' && b.parity > 0 && b.parity < 200 && xVal > 0) {
        pts.push({ x: xVal, y: b.parity, symbol: b.symbol, tir: teaOf(b) });
      }
    });
    if (pts.length) seriesList.push({ name: 'Paridad (%)', color: '#a855f7', points: pts });
  }

  const datasets = [];
  seriesList.forEach(s => {
    s.points.sort((a, b) => a.x - b.x);
    const fit = fitTermStructureCurve(s.points);
    datasets.push({
      label: `Tendencia ${s.name}`,
      data: fit.grid,
      borderColor: s.color,
      backgroundColor: 'transparent',
      borderWidth: 2,
      borderDash: [4, 4],
      pointRadius: 0,
      pointHoverRadius: 0,
      showLine: true,
      tension: 0.25,
      drawPointLabels: false
    });
    datasets.push({
      label: s.name,
      data: s.points,
      backgroundColor: s.color,
      borderColor: s.color,
      pointRadius: 6,
      pointHoverRadius: 8,
      showLine: false,
      drawPointLabels: true
    });
  });

  const pTitle = document.getElementById('parityChartTitle');
  if (pTitle) pTitle.innerText = `Dispersión de Paridad (%) vs ${xLabel}`;

  parityChart = new Chart(ctx, {
    type: 'scatter',
    plugins: [pointTickerLabelsPlugin],
    data: { datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      layout: { padding: { top: 18, right: 28, bottom: 6, left: 6 } },
      plugins: {
        legend: {
          labels: {
            color: '#cbd5e1',
            filter: (item) => !item.text.startsWith('Tendencia ')
          }
        },
        tooltip: {
          backgroundColor: '#1a1f2c',
          callbacks: {
            label: (c) => {
              const r = c.raw;
              if (r && r.symbol) {
                return `${r.symbol} · Paridad ${r.y.toFixed(1)}% · ${xLabel}: ${r.x.toFixed(2)} a${hasNum(r.tir) ? ` · TIR ${r.tir.toFixed(2)}%` : ''}`;
              }
              return `Paridad tendencial: ${r.y.toFixed(1)}% (${r.x.toFixed(2)} a)`;
            }
          }
        }
      },
      scales: {
        x: {
          title: { display: true, text: xLabel, color: '#94a3b8' },
          grid: { color: '#202738' },
          ticks: { color: '#94a3b8' }
        },
        y: {
          title: { display: true, text: 'Paridad (Precio / Valor Técnico %)', color: '#94a3b8' },
          grid: { color: '#202738' },
          ticks: { color: '#94a3b8', callback: (v) => `${Number(v).toFixed(0)}%` }
        }
      }
    }
  });
}

// ========================================================
// 5. MODAL BOND INSPECTOR & WHAT-IF SIMULATOR
// ========================================================
function openBondModal(symbol) {
  const bond = allBonds.find(b => b.symbol === symbol);
  if (!bond) return;

  currentSelectedBond = bond;
  const quoteSym = (bond.ccy === 'USD' || bond.ccy === 'EXT') ? 'u$s' : '$';
  const paySym = curSymbol(bond.currency);
  const isCaucion = bond.family === 'caucion';

  document.getElementById('modalTicker').innerText = bond.symbol;
  document.getElementById('modalName').innerText = bond.name || bond.symbol;
  document.getElementById('modalType').innerText = `${bond.type || '-'} · paga ${bond.currency}`;
  document.getElementById('modalLaw').innerText = isCaucion ? 'BYMA' : `Ley ${bond.law || 'Argentina'}`;

  const usdEq = (bond.ccy === 'ARS' && bond.currency === 'USD' && bond.eval_price_usd) ? ` (u$s ${bond.eval_price_usd.toFixed(2)})` : '';
  document.getElementById('modalPrice').innerText = isCaucion
    ? `TNA ${fmtPct(bond.price)}`
    : `${quoteSym} ${hasNum(bond.price) ? bond.price.toFixed(2) : '-'}${usdEq}`;
  document.getElementById('modalVT').innerText = hasNum(bond.vt) && bond.vt > 0 ? `${paySym} ${bond.vt.toFixed(2)}` : '-';
  document.getElementById('modalVR').innerText = bond.redemption
    ? `Rescate al vto: ${paySym} ${bond.redemption.toFixed(3)}`
    : `VR: ${hasNum(bond.vr) ? bond.vr.toFixed(2) : '-'} | IC: ${hasNum(bond.accrued) ? bond.accrued.toFixed(2) : '-'}`;

  document.getElementById('modalParity').innerText = (hasNum(bond.parity) && bond.parity > 0) ? `${bond.parity.toFixed(1)}%` : '-%';

  const tea = teaOf(bond);
  const tirEl = document.getElementById('modalTIR');
  tirEl.innerText = tea !== null ? `${tea.toFixed(2)}%` : 'N/D';
  tirEl.title = [bond.tir_basis, bond.tir_reason].filter(Boolean).join(' · ');
  const tirNote = document.getElementById('modalTirNote');
  if (tirNote) {
    tirNote.innerText = tea !== null
      ? `TEA ${bond.is_cer ? 'real (sobre CER)' : 'nominal'}${bond.family === 'caucion' ? '' : ` · TNA sem. ${fmtPct(bond.tir)}`}${bond.tir_quality === 'estimada' ? ' · ESTIMADA' : ''}`
      : (bond.tir_reason || 'Sin datos para calcular la TIR');
  }
  document.getElementById('modalDuration').innerText = (bond.duration > 0) ? `${bond.duration.toFixed(2)} a` : '-';
  document.getElementById('modalMD').innerText = (bond.mod_duration > 0) ? `${bond.mod_duration.toFixed(2)} a` : '-';

  // Reset Sensitivity Slider
  document.getElementById('simBpsSlider').value = 0;
  document.getElementById('simBpsVal').innerText = '0 bps';
  updateSimulator(0);

  // Quick Modal VAN: the k slider lives in the bond's own currency
  const kSlider = document.getElementById('modalVanKSlider');
  const range = VAN_K_RANGE[bond.currency] || VAN_K_RANGE.USD;
  kSlider.min = range.min;
  kSlider.max = range.max;
  kSlider.value = vanKByCcy[bond.currency] || 12.0;
  document.getElementById('modalVanKVal').innerText = parseFloat(kSlider.value).toFixed(1) + '%';
  const investLabel = document.getElementById('modalVanCur');
  if (investLabel) investLabel.innerText = paySym;
  updateModalVAN();

  // Render Cashflows Table
  const cfTbody = document.getElementById('cashflowsTableBody');
  cfTbody.innerHTML = '';

  if (bond.cashflows && bond.cashflows.length > 0) {
    bond.cashflows.forEach(cf => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${cf.date}</td>
        <td class="right">${paySym} ${fmtNum(cf.coupon, 3)}</td>
        <td class="right">${paySym} ${fmtNum(cf.amort)}</td>
        <td class="right" style="font-weight:700;">${paySym} ${fmtNum(cf.total, 3)}</td>
        <td class="right">${fmtNum(cf.remaining_vr, 1)}</td>
        <td class="right">${cf.years.toFixed(2)}</td>
      `;
      cfTbody.appendChild(tr);
    });
  } else {
    cfTbody.innerHTML = `<tr><td colspan="6" class="center" style="color:var(--text-dim); padding:16px;">${bond.tir_reason || 'Cronograma no disponible para este instrumento.'}</td></tr>`;
  }

  qaTrace('Ficha', bond.symbol, { 'Dato crudo (backend)': { ...bond, cashflows: `[${(bond.cashflows || []).length} flujos]` } });
  document.getElementById('bondModal').style.display = 'flex';
}

function closeModal() {
  document.getElementById('bondModal').style.display = 'none';
  currentSelectedBond = null;
}

function updateSimulator(bps) {
  if (!currentSelectedBond) return;
  const bond = currentSelectedBond;
  const curSym = curSymbol(bond.currency);

  const p0 = bond.eval_price || 0;
  const md = bond.mod_duration || 0;
  const impactEl = document.getElementById('simImpactPct');

  if (!(md > 0) || !(p0 > 0) || bond.family === 'caucion') {
    document.getElementById('simEstPrice').innerText = '-';
    document.getElementById('simEstParity').innerText = '-';
    impactEl.innerText = 'N/D (sin duration)';
    impactEl.style.color = 'var(--text-dim)';
    return;
  }

  // Price impact approx: dP / P = - MD * dy
  const dy = bps / 10000.0;
  const dPricePct = - md * dy;
  const newPrice = Math.max(0.01, p0 * (1.0 + dPricePct));

  document.getElementById('simEstPrice').innerText = `${curSym} ${newPrice.toFixed(2)}`;
  document.getElementById('simEstParity').innerText = (bond.vt > 0) ? `${(newPrice / bond.vt * 100.0).toFixed(1)}%` : '-';

  const impactVal = dPricePct * 100.0;
  impactEl.innerText = (impactVal >= 0 ? '+' : '') + impactVal.toFixed(2) + '%';
  impactEl.style.color = (impactVal > 0) ? '#10b981' : (impactVal < 0 ? '#f43f5e' : '#f1f5f9');
}

function updateModalVAN() {
  if (!currentSelectedBond) return;
  const investInput = document.getElementById('modalVanInvest');
  const kSlider = document.getElementById('modalVanKSlider');
  const amtEl = document.getElementById('modalVanAmt');
  const badgeEl = document.getElementById('modalVanResultBadge');

  if (!investInput || !kSlider || !amtEl || !badgeEl) return;

  const inv = Math.max(10, parseFloat(investInput.value) || 1000);
  const k = parseFloat(kSlider.value) || 12.0;

  const res = calculateVANMath(currentSelectedBond, inv, k);
  if (!res) {
    amtEl.innerText = currentSelectedBond.data_gap ? INFO_GAP_MSG : 'No disponible: sin cronograma de flujos';
    amtEl.style.color = 'var(--text-dim)';
    badgeEl.style.backgroundColor = 'transparent';
    badgeEl.style.borderColor = 'var(--border-subtle)';
    return;
  }

  const curSym = curSymbol(currentSelectedBond.currency);
  const sign = res.totalVAN >= 0 ? '+' : '';
  amtEl.innerText = `${sign}${curSym} ${fmtNum(res.totalVAN)} (${sign}${res.vanPct.toFixed(1)}%)`;

  if (res.verdictBadge === 'success') {
    badgeEl.style.backgroundColor = 'rgba(16, 185, 129, 0.15)';
    badgeEl.style.borderColor = '#10b981';
    amtEl.style.color = '#10b981';
  } else if (res.verdictBadge === 'danger') {
    badgeEl.style.backgroundColor = 'rgba(244, 63, 94, 0.15)';
    badgeEl.style.borderColor = '#f43f5e';
    amtEl.style.color = '#f43f5e';
  } else {
    badgeEl.style.backgroundColor = 'rgba(56, 189, 248, 0.15)';
    badgeEl.style.borderColor = '#38bdf8';
    amtEl.style.color = '#38bdf8';
  }
}

// ========================================================
// 6. CSV EXPORT
// ========================================================
function exportCSV() {
  const data = getFilteredData();
  if (data.length === 0) return;

  const headers = ['Symbol', 'Familia', 'Tipo', 'MonedaCotizacion', 'MonedaPago', 'Precio', 'Var%', 'ValorTecnico', 'Paridad%', 'TIR_TEA%', 'TIR_TNA_sem%', 'BaseTIR', 'CalidadTIR', 'DurationMac', 'DurationMod', 'Volumen', 'Vencimiento'];
  const cell = (v) => (v === null || v === undefined) ? '' : v;
  const rows = data.map(b => [
    b.symbol,
    b.family,
    `"${b.type || ''}"`,
    b.ccy,
    b.currency,
    cell(b.price),
    cell(b.change_pct),
    cell(b.vt),
    cell(b.parity),
    cell(b.tir_tea),
    cell(b.tir),
    `"${b.tir_basis || ''}"`,
    b.tir_quality || '',
    cell(b.duration),
    cell(b.mod_duration),
    cell(b.volume_amount),
    b.maturity_date || ''
  ]);

  let csvContent = 'data:text/csv;charset=utf-8,' + headers.join(',') + '\n';
  rows.forEach(r => {
    csvContent += r.join(',') + '\n';
  });

  const encodedUri = encodeURI(csvContent);
  const link = document.createElement('a');
  link.setAttribute('href', encodedUri);
  link.setAttribute('download', `Bonos_Argentinos_${new Date().toISOString().substring(0, 10)}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

// ========================================================
// 7. COMPARACIÓN DE BONOS (PESOS ARS vs DÓLARES USD)
// ========================================================
// Criterio cuantitativo (Diplomado Instrumentos Financieros · Unidad 4, Cap. 8.2 y Cap. 10):
//   - Pata ARS: rinde una tasa efectiva anual (arsNominal).
//     1) Frente a la inflación en pesos (π):  arsReal  = (1 + arsNominal) / (1 + π) - 1  (Ecuación de Fisher).
//     2) Frente a la devaluación del peso (d): arsInUsd = (1 + arsNominal) / (1 + d) - 1.
//     3) Erosión macroeconómica efectiva sobre el peso: max(π, d) -> arsEffective = min(arsReal, arsInUsd).
//   - Pata USD (Hard Dollar): paga dólares billete (usdInUsd).
//     El bono en pesos SOLO gana si supera al bono en dólares tanto frente a la inflación (poder adquisitivo)
//     como frente a la devaluación cambiaria: arsReal > usdInUsd  Y  arsInUsd > usdInUsd.
function initScenariosEvents() {
  ['scenarioArsSelect', 'scenarioUsdSelect', 'scenarioInfInput', 'scenarioDevInput', 'scenarioInfUnit', 'scenarioDevUnit'].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener('input', runScenarios);
      el.addEventListener('change', runScenarios);
    }
  });

  const ySlider = document.getElementById('scenarioYearsSlider');
  if (ySlider) {
    ySlider.addEventListener('input', (e) => {
      document.getElementById('scenarioYearsVal').innerText = `${parseFloat(e.target.value).toFixed(1)} años`;
      runScenarios();
    });
  }
}

function populateScenarios() {
  const fill = (selId, ccy, preferred) => {
    const sel = document.getElementById(selId);
    if (!sel) return;
    // Order fixed-rate instruments first in ARS, then by liquidity
    const bonds = dcfUniverse(ccy).sort((a, b) => {
      if (ccy === 'ARS' && Boolean(a.is_cer) !== Boolean(b.is_cer)) {
        return a.is_cer ? 1 : -1;
      }
      return (b.volume_amount || 0) - (a.volume_amount || 0);
    });
    const prev = sel.value;
    sel.innerHTML = '';
    if (bonds.length === 0) {
      const opt = document.createElement('option');
      opt.value = '';
      opt.innerText = `Sin instrumentos en ${ccy} con flujos`;
      sel.appendChild(opt);
      return;
    }
    bonds.forEach(b => {
      const opt = document.createElement('option');
      opt.value = b.symbol;
      opt.innerText = `${b.symbol} · ${b.type} · TIR ${fmtPct(teaOf(b))} TEA`;
      sel.appendChild(opt);
    });
    if (prev && bonds.some(b => b.symbol === prev)) sel.value = prev;
    else sel.value = (preferred(bonds) || bonds[0]).symbol;
  };
  // Default peso leg: longest fixed-rate instrument (LECAP/BONCAP)
  fill('scenarioArsSelect', 'ARS', (bonds) => bonds.filter(b => !b.is_cer)
    .sort((a, b) => (b.days_to_maturity || 0) - (a.days_to_maturity || 0))[0]);
  fill('scenarioUsdSelect', 'USD', (bonds) => bonds.find(b => ['AL30D', 'GD30D', 'AO29D'].includes(b.symbol)));

  // Default expectation: BCRA REM (already annual)
  const infInp = document.getElementById('scenarioInfInput');
  if (infInp && !infInp.value) {
    infInp.value = defaultInflTEA().toFixed(1);
    document.getElementById('scenarioInfUnit').value = 'anual';
  }
}

// User expectation -> effective annual rate. A monthly figure is compounded 12 times: (1 + TEM)^12 - 1.
function scenarioRateTEA(inputId, unitId) {
  const raw = parseFloat(document.getElementById(inputId).value);
  const unit = document.getElementById(unitId).value;
  const value = isFinite(raw) ? Math.max(-99, raw) : 0;
  return { raw: value, unit, tea: unit === 'mensual' ? monthlyToTEA(value) : value };
}

// Yield of `bond` over the horizon: holding-period TIR if it outlives the horizon, else its TIR to maturity
function scenarioBaseYield(bond, yrs) {
  const h = calculateBondHorizon(bond, yrs);
  if (h.eligible) return { tea: h.horizonTir, source: `TIR al horizonte de ${yrs.toFixed(1)} años` };
  return { tea: teaOf(bond), source: `TIR a vencimiento (${h.reason}; supone reinvertir a la misma tasa)` };
}

function runScenarios() {
  const setText = (id, txt) => { const el = document.getElementById(id); if (el) el.innerText = txt; };
  const bArs = allBonds.find(b => b.symbol === document.getElementById('scenarioArsSelect').value);
  const bUsd = allBonds.find(b => b.symbol === document.getElementById('scenarioUsdSelect').value);
  const title = document.getElementById('scenVerdictTitle');
  const desc = document.getElementById('scenVerdictDesc');

  if (!bArs || !bUsd) {
    title.innerText = 'Faltan instrumentos para comparar';
    title.style.color = 'var(--text-muted)';
    desc.innerText = lastLoadError ? `Sin datos de mercado: ${lastLoadError}`
      : `Se necesita un instrumento con flujos en cada moneda (ARS: ${dcfUniverse('ARS').length}, USD: ${dcfUniverse('USD').length}).`;
    return;
  }

  const yrs = parseFloat(document.getElementById('scenarioYearsSlider').value) || 1.0;
  const inf = scenarioRateTEA('scenarioInfInput', 'scenarioInfUnit');
  const dev = scenarioRateTEA('scenarioDevInput', 'scenarioDevUnit');

  const baseArs = scenarioBaseYield(bArs, yrs);
  const baseUsd = scenarioBaseYield(bUsd, yrs);
  if (baseArs.tea === null || baseUsd.tea === null) {
    title.innerText = 'Instrumento sin TIR calculable';
    desc.innerText = 'Elegí otro instrumento.';
    return;
  }

  // --- Pata en Pesos (ARS): se evalúa con su tasa efectiva anual directa frente a la inflación y la devaluación.
  // Ecuación de Fisher:
  //   arsReal  = (1 + arsNominal) / (1 + inflación) - 1
  //   arsInUsd = (1 + arsNominal) / (1 + devaluación) - 1
  const arsNominal = baseArs.tea;
  const arsReal = deflate(arsNominal, inf.tea);
  const arsInUsd = deflate(arsNominal, dev.tea);
  // El peso sufre la mayor de las dos erosiones macroeconómicas (inflación interna o devaluación cambiaria):
  const macroErosionArs = Math.max(inf.tea, dev.tea);
  const arsEffective = Math.min(arsReal, arsInUsd); // = deflate(arsNominal, macroErosionArs)

  // --- Pata en Dólares (USD - Hard Dollar): paga dólares billete (usdInUsd).
  const usdInUsd = baseUsd.tea;
  const usdNominalArs = compound(usdInUsd, dev.tea);
  // Un bono Hard Dollar preserva moneda dura frente a la inflación doméstica en pesos, y gana poder de compra adicional si d > π:
  const usdReal = deflate(compound(usdInUsd, macroErosionArs), inf.tea);

  const unitTxt = (r, what) => r.unit === 'mensual'
    ? `${what} ${r.raw.toFixed(2)}% mensual → (1 + ${r.raw.toFixed(2)}%)^12 − 1 = ${r.tea.toFixed(2)}% TEA`
    : `${what} ${r.tea.toFixed(2)}% TEA`;
  setText('scenAssumptions', `Supuestos anualizados: ${unitTxt(inf, 'inflación en pesos')} · ${unitTxt(dev, 'devaluación cambiaria')}`);

  setText('scenArsNominal', fmtPct(arsNominal));
  setText('scenArsReal', fmtPct(arsReal));
  setText('scenArsUsd', fmtPct(arsInUsd));

  // Color feedback for negative vs positive returns on the ARS card
  const elArsReal = document.getElementById('scenArsReal');
  if (elArsReal) elArsReal.style.color = arsReal < 0 ? '#f43f5e' : (arsReal > usdInUsd ? '#10b981' : '#f8fafc');
  const elArsUsd = document.getElementById('scenArsUsd');
  if (elArsUsd) elArsUsd.style.color = arsInUsd < 0 ? '#f43f5e' : 'var(--primary-cyan)';

  setText('scenArsFormula',
    `Fisher: TIR ${arsNominal.toFixed(2)}% → real = (1+${arsNominal.toFixed(2)}%) / (1+${inf.tea.toFixed(1)}%) − 1 = ${arsReal.toFixed(2)}% · en USD = (1+${arsNominal.toFixed(2)}%) / (1+${dev.tea.toFixed(1)}%) − 1 = ${arsInUsd.toFixed(2)}%`);
  setText('scenArsBaseTir', `Base: ${baseArs.source}`);

  setText('scenUsdUsd', fmtPct(usdInUsd));
  setText('scenUsdNominal', fmtPct(usdNominalArs));
  setText('scenUsdReal', fmtPct(usdReal));
  setText('scenUsdFormula',
    `Hard Dollar: TIR ${usdInUsd.toFixed(2)}% en USD → en ARS (con deval. ${dev.tea.toFixed(1)}%) = (1+${usdInUsd.toFixed(2)}%)·(1+${dev.tea.toFixed(1)}%) − 1 = ${usdNominalArs.toFixed(2)}%`);
  setText('scenUsdBaseTir', `Base: ${baseUsd.source}`);

  // Regla de decisión (Unidad 4, Cap. 8.2):
  // El bono en pesos gana SÓLO si supera al bono en dólares tanto frente a la inflación (arsReal > usdInUsd)
  // como frente a la devaluación (arsInUsd > usdInUsd), es decir: arsEffective > usdInUsd.
  const arsWins = arsEffective > usdInUsd;
  const gap = Math.abs(arsEffective - usdInUsd);
  // Tasa máxima de inflación y devaluación que soporta el bono en pesos antes de perder contra el bono en USD:
  const breakevenRate = deflate(arsNominal, usdInUsd);

  const arsCard = document.getElementById('scenArsCard');
  const usdCard = document.getElementById('scenUsdCard');
  if (arsCard) arsCard.style.borderColor = arsWins ? 'var(--primary-cyan)' : 'var(--border-subtle)';
  if (usdCard) usdCard.style.borderColor = !arsWins ? 'var(--accent-green)' : 'var(--border-subtle)';

  if (arsWins) {
    title.innerText = `🏆 Ganador: ${bArs.symbol} (Alternativa en Pesos)`;
    title.style.color = 'var(--primary-cyan)';
    desc.innerText =
      `El bono en pesos (${bArs.symbol}, TIR ${arsNominal.toFixed(2)}% TEA) supera al bono en dólares (${bUsd.symbol}, TIR ${usdInUsd.toFixed(2)}% TEA en USD) ` +
      `tanto en poder adquisitivo real (+${arsReal.toFixed(2)}% vs inflación de ${inf.tea.toFixed(1)}%) como medido en dólares (+${arsInUsd.toFixed(2)}% vs devaluación de ${dev.tea.toFixed(1)}%), ` +
      `con una ventaja neta de +${gap.toFixed(2)} pp. La alternativa en pesos gana mientras la inflación y la devaluación se mantengan por debajo de ${breakevenRate.toFixed(1)}% anual.`;
  } else {
    title.innerText = `🏆 Ganador: ${bUsd.symbol} (Alternativa en Dólares)`;
    title.style.color = 'var(--accent-green)';
    const lostByInflation = inf.tea >= dev.tea && arsReal <= usdInUsd;
    const reasonText = lostByInflation
      ? `Con una inflación esperada en pesos de ${inf.tea.toFixed(1)}% anual frente a una TIR nominal de ${arsNominal.toFixed(2)}% en ${bArs.symbol}, ` +
        `el rendimiento real en pesos cae a ${arsReal.toFixed(2)}% (${arsReal < 0 ? 'pérdida de poder adquisitivo' : 'inferior al bono en USD'}), mientras que ${bUsd.symbol} preserva capital en moneda dura rindiendo +${usdInUsd.toFixed(2)}% TEA en USD (+${usdNominalArs.toFixed(2)}% en ARS con ${dev.tea.toFixed(1)}% de devaluación).`
      : `Con una devaluación esperada de ${dev.tea.toFixed(1)}% anual, ${bArs.symbol} rinde ${arsInUsd.toFixed(2)}% medido en USD frente al +${usdInUsd.toFixed(2)}% TEA en dólares que asegura ${bUsd.symbol} (+${gap.toFixed(2)} pp a favor del bono en dólares).`;
    desc.innerText =
      `${reasonText} Para que ${bArs.symbol} pudiera empatar a ${bUsd.symbol}, tanto la inflación como la devaluación anual deberían ubicarse por debajo de ${breakevenRate.toFixed(1)}% anual.`;
  }

  qaTrace('Comparación de Bonos', `${bArs.symbol} (ARS) vs ${bUsd.symbol} (USD) a ${yrs} años`, {
    '1. Dato crudo (backend)': {
      ARS: { symbol: bArs.symbol, 'tir_tea (%)': bArs.tir_tea, tipo: bArs.type },
      USD: { symbol: bUsd.symbol, 'tir_tea (%)': bUsd.tir_tea, tipo: bUsd.type }
    },
    '2. Expectativas del usuario -> TEA': {
      inflacion_pesos: `${inf.raw}% ${inf.unit} -> ${round4(inf.tea)}% TEA`,
      devaluacion_dolar: `${dev.raw}% ${dev.unit} -> ${round4(dev.tea)}% TEA`,
      erosion_efectiva_max: `${round4(macroErosionArs)}% TEA`
    },
    '3. Tasa base en el horizonte': { ARS: `${round4(baseArs.tea)}% · ${baseArs.source}`, USD: `${round4(baseUsd.tea)}% · ${baseUsd.source}` },
    '4. Pata ARS (TEA %)': {
      nominal: round4(arsNominal),
      'real_vs_inflacion = (1+nom)/(1+inf)-1': round4(arsReal),
      'en_USD_vs_deval = (1+nom)/(1+dev)-1': round4(arsInUsd),
      'efectivo_neto = min(real, en_USD)': round4(arsEffective)
    },
    '5. Pata USD (TEA %)': {
      'en_USD_hard_dollar': round4(usdInUsd),
      'nominal_ARS = (1+usd)(1+dev)-1': round4(usdNominalArs),
      'poder_adquisitivo_real': round4(usdReal)
    },
    '6. Veredicto': {
      ganador: arsWins ? bArs.symbol : bUsd.symbol,
      ventaja_neta_pp: round4(gap),
      tasa_limite_empate_pct: round4(breakevenRate)
    }
  });
}
