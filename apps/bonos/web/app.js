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

// Charts
let curveChart = null;
let parityChart = null;
let horizonChart = null;

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
  
  // Scenarios Events
  initScenariosEvents();
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
    refreshCountdown--;
    const timerEl = document.getElementById('refreshTimer');
    if (timerEl) timerEl.innerText = `${refreshCountdown}s`;
    if (refreshCountdown <= 0) {
      refreshCountdown = 30;
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
      <td class="right">${hasNum(bond.vt) && bond.vt > 0 ? `${paySym} ${bond.vt.toFixed(2)}` : '-'}</td>
      <td class="center">${parityBadge}</td>
      <td class="right" style="color:var(--primary-cyan); font-weight:700;">${tirCellHtml(bond)}</td>
      <td class="right">${isCaucion ? `${bond.days_to_maturity} d` : ((bond.duration > 0) ? `${bond.duration.toFixed(2)} a` : '-')}</td>
      <td class="right">${(bond.mod_duration > 0) ? `${bond.mod_duration.toFixed(2)} a` : '-'}</td>
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
// 4. CHARTS VIEW (CURVAS & DISPERSIÓN)
// ========================================================
function renderCharts() {
  renderCurveChart();
  renderParityChart();
}

function renderCurveChart() {
  const ctx = document.getElementById('curveChart');
  if (!ctx) return;
  if (curveChart) curveChart.destroy();

  const bonarData = [];
  const globalData = [];

  allBonds.forEach(b => {
    // One point per bond: the species quoted in its own payment currency (AL30D, GD30D...)
    if (b.family === 'soberano_usd' && b.is_native_quote && teaOf(b) !== null && b.mod_duration > 0) {
      const point = { x: b.mod_duration, y: teaOf(b), symbol: b.symbol };
      if (b.symbol.startsWith('AL') || b.symbol.startsWith('AE')) {
        bonarData.push(point);
      } else if (b.symbol.startsWith('GD')) {
        globalData.push(point);
      }
    }
  });

  bonarData.sort((a, b) => a.x - b.x);
  globalData.sort((a, b) => a.x - b.x);

  curveChart = new Chart(ctx, {
    type: 'scatter',
    data: {
      datasets: [
        {
          label: 'Bonares (Ley Arg)',
          data: bonarData,
          backgroundColor: '#38bdf8',
          borderColor: '#38bdf8',
          pointRadius: 6,
          pointHoverRadius: 8,
          showLine: true,
          tension: 0.3
        },
        {
          label: 'Globales (Ley NY)',
          data: globalData,
          backgroundColor: '#10b981',
          borderColor: '#10b981',
          pointRadius: 6,
          pointHoverRadius: 8,
          showLine: true,
          tension: 0.3
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: '#94a3b8' } },
        tooltip: {
          backgroundColor: '#1a1f2c',
          callbacks: {
            label: (ctx) => `${ctx.raw.symbol}: MD ${ctx.raw.x.toFixed(2)} a | TIR ${ctx.raw.y.toFixed(2)}%`
          }
        }
      },
      scales: {
        x: {
          title: { display: true, text: 'Duration Modificada (Años)', color: '#94a3b8' },
          grid: { color: '#202738' },
          ticks: { color: '#94a3b8' }
        },
        y: {
          title: { display: true, text: 'TIR (TEA %)', color: '#94a3b8' },
          grid: { color: '#202738' },
          ticks: { color: '#94a3b8' }
        }
      }
    }
  });
}

function renderParityChart() {
  const ctx = document.getElementById('parityChart');
  if (!ctx) return;
  if (parityChart) parityChart.destroy();

  const points = [];
  allBonds.forEach(b => {
    if (b.family === 'soberano_usd' && b.is_native_quote && b.parity > 0 && b.mod_duration > 0) {
      points.push({ x: b.mod_duration, y: b.parity, symbol: b.symbol });
    }
  });

  parityChart = new Chart(ctx, {
    type: 'scatter',
    data: {
      datasets: [{
        label: 'Paridad vs Duration',
        data: points,
        backgroundColor: '#a855f7',
        borderColor: '#a855f7',
        pointRadius: 6,
        pointHoverRadius: 8
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1a1f2c',
          callbacks: {
            label: (ctx) => `${ctx.raw.symbol}: MD ${ctx.raw.x.toFixed(2)} a | Paridad ${ctx.raw.y.toFixed(1)}%`
          }
        }
      },
      scales: {
        x: {
          title: { display: true, text: 'Duration Modificada (Años)', color: '#94a3b8' },
          grid: { color: '#202738' },
          ticks: { color: '#94a3b8' }
        },
        y: {
          title: { display: true, text: 'Paridad (%)', color: '#94a3b8' },
          grid: { color: '#202738' },
          ticks: { color: '#94a3b8' }
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
    amtEl.innerText = 'No disponible: sin cronograma de flujos';
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
// 7. SIMULADOR DE ESCENARIOS MACRO (ARS vs USD)
// ========================================================
// All three views of a return are shown side by side so the sign of each number can be traced:
//   NOMINAL en pesos  |  REAL (deflactado por inflación)  |  EN DÓLARES (deflactado por devaluación)
// Fisher is always applied on effective annual rates:  real = (1 + nominal) / (1 + inflación) - 1.
// Subtracting percentages (40 - 50 = -10) is never used.
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
    const bonds = dcfUniverse(ccy).sort((a, b) => (b.volume_amount || 0) - (a.volume_amount || 0));
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
      opt.innerText = `${b.symbol} · ${b.type} · TIR ${fmtPct(teaOf(b))} TEA ${b.is_cer ? 'real' : (ccy === 'ARS' ? 'nominal' : '')}`;
      sel.appendChild(opt);
    });
    if (prev && bonds.some(b => b.symbol === prev)) sel.value = prev;
    else sel.value = (preferred(bonds) || bonds[0]).symbol;
  };
  // Default peso leg: the longest fixed-rate instrument (closest in term to a dollar bond)
  fill('scenarioArsSelect', 'ARS', (bonds) => bonds.filter(b => !b.is_cer)
    .sort((a, b) => (b.days_to_maturity || 0) - (a.days_to_maturity || 0))[0]);
  fill('scenarioUsdSelect', 'USD', (bonds) => bonds.find(b => ['AL30D', 'GD30D'].includes(b.symbol)));

  // Default expectation: BCRA REM (already annual)
  const infInp = document.getElementById('scenarioInfInput');
  if (infInp && !infInp.value) {
    infInp.value = defaultInflTEA().toFixed(1);
    document.getElementById('scenarioInfUnit').value = 'anual';
  }
}

// User expectation -> effective annual rate. A monthly figure is compounded 12 times, never multiplied by 12.
function scenarioRateTEA(inputId, unitId) {
  const raw = parseFloat(document.getElementById(inputId).value);
  const unit = document.getElementById(unitId).value;
  const value = isFinite(raw) ? raw : 0;
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

  const yrs = parseFloat(document.getElementById('scenarioYearsSlider').value) || 5.0;
  const inf = scenarioRateTEA('scenarioInfInput', 'scenarioInfUnit');
  const dev = scenarioRateTEA('scenarioDevInput', 'scenarioDevUnit');

  const baseArs = scenarioBaseYield(bArs, yrs);
  const baseUsd = scenarioBaseYield(bUsd, yrs);
  if (baseArs.tea === null || baseUsd.tea === null) {
    title.innerText = 'Instrumento sin TIR calculable';
    desc.innerText = 'Elegí otro instrumento.';
    return;
  }

  // --- ARS leg. A CER bond yields a REAL rate; a fixed-rate one yields a NOMINAL rate.
  const arsNominal = bArs.is_cer ? compound(baseArs.tea, inf.tea) : baseArs.tea;
  const arsReal = bArs.is_cer ? baseArs.tea : deflate(baseArs.tea, inf.tea);
  const arsInUsd = deflate(arsNominal, dev.tea);

  // --- USD leg. Its peso return is the dollar yield compounded with the devaluation.
  const usdInUsd = baseUsd.tea;
  const usdNominalArs = compound(usdInUsd, dev.tea);
  const usdRealArs = deflate(usdNominalArs, inf.tea);

  const unitTxt = (r, what) => r.unit === 'mensual'
    ? `${what} ${r.raw.toFixed(2)}% mensual → (1 + ${r.raw.toFixed(2)}%)^12 − 1 = ${r.tea.toFixed(2)}% TEA`
    : `${what} ${r.tea.toFixed(2)}% TEA`;
  setText('scenAssumptions', `Supuestos anualizados: ${unitTxt(inf, 'inflación')} · ${unitTxt(dev, 'devaluación')}`);

  setText('scenArsNominal', fmtPct(arsNominal));
  setText('scenArsReal', fmtPct(arsReal));
  setText('scenArsUsd', fmtPct(arsInUsd));
  setText('scenArsFormula', bArs.is_cer
    ? `CER: TIR real ${baseArs.tea.toFixed(2)}% → nominal = (1+${baseArs.tea.toFixed(2)}%)·(1+${inf.tea.toFixed(2)}%)−1 → en USD = (1+nominal)/(1+${dev.tea.toFixed(2)}%)−1`
    : `Tasa fija: TIR nominal ${baseArs.tea.toFixed(2)}% → real = (1+nominal)/(1+${inf.tea.toFixed(2)}%)−1 → en USD = (1+nominal)/(1+${dev.tea.toFixed(2)}%)−1`);
  setText('scenArsBaseTir', `Base: ${baseArs.source}`);

  setText('scenUsdUsd', fmtPct(usdInUsd));
  setText('scenUsdNominal', fmtPct(usdNominalArs));
  setText('scenUsdReal', fmtPct(usdRealArs));
  setText('scenUsdFormula', `TIR en USD ${usdInUsd.toFixed(2)}% → nominal en pesos = (1+${usdInUsd.toFixed(2)}%)·(1+${dev.tea.toFixed(2)}%)−1 → real = (1+nominal)/(1+${inf.tea.toFixed(2)}%)−1`);
  setText('scenUsdBaseTir', `Base: ${baseUsd.source}`);

  // Winner: both legs measured in the same unit (USD, TEA). The ranking is identical in real pesos.
  const arsWins = arsInUsd > usdInUsd;
  const gap = Math.abs(arsInUsd - usdInUsd);
  // Devaluation at which both alternatives tie: (1 + nominal ARS) / (1 + TIR USD) - 1
  const breakevenDev = deflate(arsNominal, usdInUsd);
  if (arsWins) {
    title.innerText = `🏆 Ganador: ${bArs.symbol} (alternativa en pesos)`;
    title.style.color = 'var(--primary-cyan)';
    desc.innerText = `Medido en dólares, ${bArs.symbol} rinde ${arsInUsd.toFixed(2)}% TEA contra ${usdInUsd.toFixed(2)}% de ${bUsd.symbol} (+${gap.toFixed(2)} pp). Los pesos ganan mientras la devaluación sea menor a ${breakevenDev.toFixed(1)}% anual.`;
  } else {
    title.innerText = `🏆 Ganador: ${bUsd.symbol} (alternativa en dólares)`;
    title.style.color = 'var(--accent-green)';
    desc.innerText = `Medido en dólares, ${bUsd.symbol} rinde ${usdInUsd.toFixed(2)}% TEA contra ${arsInUsd.toFixed(2)}% de ${bArs.symbol} (+${gap.toFixed(2)} pp). Los pesos recién empatan si la devaluación baja a ${breakevenDev.toFixed(1)}% anual.`;
  }
  if (arsReal < 0) {
    desc.innerText += ` El rendimiento real de ${bArs.symbol} es negativo porque su tasa nominal (${arsNominal.toFixed(1)}%) queda por debajo de la inflación esperada (${inf.tea.toFixed(1)}%).`;
  }

  qaTrace('Escenarios', `${bArs.symbol} (ARS) vs ${bUsd.symbol} (USD) a ${yrs} años`, {
    '1. Dato crudo (backend)': {
      ARS: { symbol: bArs.symbol, 'tir_tea (%)': bArs.tir_tea, base: yieldBasis(bArs), es_CER: bArs.is_cer },
      USD: { symbol: bUsd.symbol, 'tir_tea (%)': bUsd.tir_tea }
    },
    '2. Expectativas del usuario -> TEA': {
      inflacion: `${inf.raw}% ${inf.unit} -> ${round4(inf.tea)}% TEA`,
      devaluacion: `${dev.raw}% ${dev.unit} -> ${round4(dev.tea)}% TEA`
    },
    '3. Tasa base usada en el horizonte': { ARS: `${round4(baseArs.tea)}% · ${baseArs.source}`, USD: `${round4(baseUsd.tea)}% · ${baseUsd.source}` },
    '4. Pata ARS (TEA %)': { nominal: round4(arsNominal), 'real = (1+nominal)/(1+inflación)-1': round4(arsReal), 'en USD = (1+nominal)/(1+devaluación)-1': round4(arsInUsd) },
    '5. Pata USD (TEA %)': { 'en USD': round4(usdInUsd), 'nominal ARS = (1+usd)(1+devaluación)-1': round4(usdNominalArs), 'real ARS': round4(usdRealArs) },
    '6. Veredicto': { ganador: arsWins ? bArs.symbol : bUsd.symbol, diferencia_pp_en_USD: round4(gap), devaluacion_de_empate_pct: round4(breakevenDev) }
  });
}
