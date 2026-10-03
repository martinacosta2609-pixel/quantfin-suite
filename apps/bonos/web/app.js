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

// Charts
let curveChart = null;
let parityChart = null;
let horizonChart = null;

// VAN Module State
let vanSelectedBond = null;
let vanInvestment = 1000.0;
let vanKRate = 12.0;
let vanIncludeTerminalVT = true;

// Horizon Module State (Default 5.0 years -> 2031)
let horizonYears = 5.0;

// Sovereign Benchmark Tickers
const SOVEREIGN_BENCHMARKS = ['AL29', 'GD29', 'AL30', 'GD30', 'AL35', 'GD35', 'AE38', 'GD38', 'AL41', 'GD41'];

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
      renderView();
    }
  });

  // Main Desktop View Switcher
  document.getElementById('btnViewTable').addEventListener('click', () => switchDesktopView('table'));
  document.getElementById('btnViewVan').addEventListener('click', () => switchDesktopView('van'));
  document.getElementById('btnViewHorizon').addEventListener('click', () => switchDesktopView('horizon'));
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
}

// Switch View Panels
function switchDesktopView(view) {
  const views = ['table', 'van', 'horizon', 'charts'];
  views.forEach(v => {
    const el = document.getElementById(v + 'View');
    if (el) el.style.display = (v === view) ? 'flex' : 'none';
  });

  // Update Buttons
  document.getElementById('btnViewTable').classList.toggle('active', view === 'table');
  document.getElementById('btnViewVan').classList.toggle('active', view === 'van');
  document.getElementById('btnViewHorizon').classList.toggle('active', view === 'horizon');
  document.getElementById('btnViewCharts').classList.toggle('active', view === 'charts');

  if (view === 'van') {
    populateVanBondSelector();
    runVanCalculation();
  } else if (view === 'horizon') {
    runHorizonCalculation();
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
    if (window.pywebview && window.pywebview.api && window.pywebview.api.get_market_data) {
      result = await window.pywebview.api.get_market_data();
    } else {
      const resp = await fetch('/api/data');
      result = await resp.json();
    }

    if (result && result.bonds) {
      allBonds = result.bonds;
      macroData = result.macro || {};
      updateHUD();
      renderView();

      // Update active view if it was VAN or Horizon
      if (document.getElementById('vanView').style.display === 'flex') {
        populateVanBondSelector();
        runVanCalculation();
      } else if (document.getElementById('horizonView').style.display === 'flex') {
        runHorizonCalculation();
      } else if (document.getElementById('chartsView').style.display === 'flex') {
        renderCharts();
      }
    }
  } catch (err) {
    console.error('Error fetching market data:', err);
  } finally {
    if (spinIcon) spinIcon.classList.remove('spinning');
  }
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
    const brecha = macroData.brecha_mep_oficial;
    elBrecha.innerText = brecha !== undefined && brecha !== null ? `${brecha.toFixed(1)}%` : '-%';
    elBrecha.style.color = (brecha > 30) ? '#f43f5e' : (brecha > 15 ? '#f59e0b' : '#10b981');
  }

  const elBadlar = document.getElementById('hudBadlar');
  if (elBadlar) elBadlar.innerText = macroData.tasa_badlar ? `${macroData.tasa_badlar.toFixed(2)}%` : '-%';

  const elCer = document.getElementById('hudCer');
  if (elCer) elCer.innerText = macroData.cer_actual ? macroData.cer_actual.toFixed(2) : '-';

  const elInf = document.getElementById('hudInf');
  if (elInf) elInf.innerText = macroData.inflacion_mensual ? `${macroData.inflacion_mensual.toFixed(1)}%` : '-%';

  const statTime = document.getElementById('statTime');
  if (statTime) {
    const now = new Date();
    statTime.innerText = now.toTimeString().split(' ')[0];
  }

  const countEl = document.getElementById('totalBondsCount');
  if (countEl) countEl.innerText = allBonds.length;

  const statCount = document.getElementById('statCount');
  if (statCount) statCount.innerText = allBonds.length;
}

// ========================================================
// FILTER & TABLE RENDERING
// ========================================================
function getFilteredData() {
  return allBonds.filter(b => {
    // Category filter
    let matchCat = true;
    if (currentFilter === 'sovereign') {
      matchCat = (b.type === 'Soberano USD' || b.type === 'Soberano');
    } else if (currentFilter === 'usd') {
      matchCat = (b.symbol.endsWith('D') || b.symbol.endsWith('C') || b.currency === 'USD');
    } else if (currentFilter === 'bopreal') {
      matchCat = (b.type === 'Bopreal' || b.symbol.startsWith('BP'));
    } else if (currentFilter === 'cer') {
      matchCat = (b.type === 'Boncer CER' || b.symbol.startsWith('TX') || b.symbol.startsWith('TC') || b.symbol.startsWith('CU'));
    } else if (currentFilter === 'lecap') {
      matchCat = (b.type === 'Lecap' || b.symbol.startsWith('S') || b.symbol.startsWith('Y'));
    }

    // Search query
    let matchSearch = true;
    if (searchQuery) {
      matchSearch = b.symbol.toLowerCase().includes(searchQuery) ||
                    (b.name && b.name.toLowerCase().includes(searchQuery)) ||
                    (b.type && b.type.toLowerCase().includes(searchQuery));
    }

    return matchCat && matchSearch;
  });
}

function renderView() {
  const data = getFilteredData();

  // Sorting
  data.sort((a, b) => {
    let valA = a[sortCol];
    let valB = b[sortCol];

    if (valA === undefined || valA === null) valA = sortAsc ? Infinity : -Infinity;
    if (valB === undefined || valB === null) valB = sortAsc ? Infinity : -Infinity;

    if (typeof valA === 'string') {
      return sortAsc ? valA.localeCompare(valB) : valB.localeCompare(valA);
    }
    return sortAsc ? valA - valB : valB - valA;
  });

  const tbody = document.getElementById('bondsTableBody');
  const emptyState = document.getElementById('emptyState');
  tbody.innerHTML = '';

  if (data.length === 0) {
    emptyState.style.display = 'flex';
    return;
  }
  emptyState.style.display = 'none';

  data.forEach(bond => {
    const tr = document.createElement('tr');
    tr.id = `row-${bond.symbol}`;

    // Tag badge
    let badgeClass = 'badge-sovereign';
    if (bond.type === 'Bopreal') badgeClass = 'badge-bopreal';
    else if (bond.type === 'Boncer CER') badgeClass = 'badge-cer';
    else if (bond.type === 'Lecap') badgeClass = 'badge-lecap';

    // Change Class
    const changeClass = bond.change_pct > 0 ? 'cell-pos' : (bond.change_pct < 0 ? 'cell-neg' : '');
    const changeSign = bond.change_pct > 0 ? '+' : '';

    // Parity Badge
    let parityBadge = '-';
    if (bond.parity > 0) {
      let pClass = 'parity-mid';
      if (bond.parity > 95) pClass = 'parity-high';
      else if (bond.parity < 55) pClass = 'parity-low';
      parityBadge = `<span class="parity-badge ${pClass}">${bond.parity.toFixed(1)}%</span>`;
    }

    // Currency symbol
    const curSym = bond.currency === 'USD' ? 'u$s' : '$';

    tr.innerHTML = `
      <td>
        <div class="ticker-cell">
          <span class="ticker-name">${bond.symbol}</span>
          <span class="badge-tag ${badgeClass}">${bond.currency}</span>
        </div>
      </td>
      <td>
        <span style="font-size:11px; color:var(--text-muted);">${bond.type || 'Soberano'}</span>
        ${bond.law ? `<span style="font-size:10px; color:var(--text-dim);"> &bull; ${bond.law}</span>` : ''}
      </td>
      <td class="right" style="font-weight:700; color:#fff;">
        ${curSym} ${bond.price ? bond.price.toFixed(2) : '-'}
      </td>
      <td class="right ${changeClass}" style="font-weight:700;">
        ${bond.change_pct !== undefined ? `${changeSign}${bond.change_pct.toFixed(2)}%` : '-'}
      </td>
      <td class="right">${bond.vt ? `${curSym} ${bond.vt.toFixed(2)}` : '-'}</td>
      <td class="center">${parityBadge}</td>
      <td class="right" style="color:var(--primary-cyan); font-weight:700;">
        ${bond.tir ? `${bond.tir.toFixed(2)}%` : '-'}
      </td>
      <td class="right">${bond.duration ? `${bond.duration.toFixed(2)} a` : '-'}</td>
      <td class="right">${bond.mod_duration ? `${bond.mod_duration.toFixed(2)} a` : '-'}</td>
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

    tbody.appendChild(tr);
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
    kSlider.addEventListener('input', (e) => {
      vanKRate = parseFloat(e.target.value);
      kInput.value = vanKRate.toFixed(1);
      document.getElementById('vanKDisplay').innerText = `${vanKRate.toFixed(2)}%`;
      document.getElementById('vanKRankingLabel').innerText = `${vanKRate.toFixed(1)}%`;
      runVanCalculation();
    });

    kInput.addEventListener('input', (e) => {
      vanKRate = parseFloat(e.target.value) || 12.0;
      kSlider.value = Math.min(35, Math.max(1, vanKRate));
      document.getElementById('vanKDisplay').innerText = `${vanKRate.toFixed(2)}%`;
      document.getElementById('vanKRankingLabel').innerText = `${vanKRate.toFixed(1)}%`;
      runVanCalculation();
    });
  }

  // Presets
  document.querySelectorAll('.preset-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const k = parseFloat(btn.dataset.k);
      vanKRate = k;
      if (kSlider) kSlider.value = k;
      if (kInput) kInput.value = k.toFixed(1);
      document.getElementById('vanKDisplay').innerText = `${k.toFixed(2)}%`;
      document.getElementById('vanKRankingLabel').innerText = `${k.toFixed(1)}%`;
      runVanCalculation();
    });
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
}

// Plausible ranges for an instrument with a real prospectus schedule
const VAN_TIR_MIN = -5.0;
const VAN_TIR_MAX = 50.0;
const VAN_PARITY_MIN = 15.0;
const VAN_PARITY_MAX = 150.0;

// Only instruments with a real cashflow schedule and sane metrics can be valued by VAN.
// Generic instruments (Lecaps, Boncer CER, letras, ONs) only carry an invented bullet flow
// and produce meaningless TIRs (e.g. > 10.000%), so they are excluded from this module.
function isVanEligible(bond) {
  if (!bond) return false;
  if (typeof bond.van_eligible === 'boolean' && !bond.van_eligible) return false;
  if (!bond.is_sovereign) return false;
  if (!bond.cashflows || bond.cashflows.length === 0) return false;
  const evalPrice = bond.eval_price || bond.eval_price_usd || 0.0;
  if (!(evalPrice > 0)) return false;
  const tir = Number(bond.tir);
  if (!isFinite(tir) || tir === 0 || tir < VAN_TIR_MIN || tir > VAN_TIR_MAX) return false;
  const parity = Number(bond.parity);
  if (!isFinite(parity) || parity < VAN_PARITY_MIN || parity > VAN_PARITY_MAX) return false;
  return true;
}

function populateVanBondSelector() {
  const sel = document.getElementById('vanBondSelect');
  if (!sel) return;

  const validBonds = allBonds.filter(isVanEligible);
  // Sort with main benchmarks on top
  validBonds.sort((a, b) => {
    const isMainA = SOVEREIGN_BENCHMARKS.some(s => a.symbol.startsWith(s));
    const isMainB = SOVEREIGN_BENCHMARKS.some(s => b.symbol.startsWith(s));
    if (isMainA && !isMainB) return -1;
    if (!isMainA && isMainB) return 1;
    return a.symbol.localeCompare(b.symbol);
  });

  const prevVal = sel.value;
  sel.innerHTML = '';

  const excludedCount = allBonds.length - validBonds.length;
  const noteEl = document.getElementById('vanExcludedNote');
  if (noteEl) {
    noteEl.innerText = excludedCount > 0
      ? `${validBonds.length} instrumentos con cronograma de flujos real. ${excludedCount} excluidos (Lecaps, Boncer, letras y ONs sin flujos confiables).`
      : '';
  }

  if (validBonds.length === 0) {
    const opt = document.createElement('option');
    opt.value = '';
    opt.innerText = 'Sin instrumentos valuables (mercado cerrado o sin precios)';
    sel.appendChild(opt);
    vanSelectedBond = null;
    return;
  }

  validBonds.forEach(b => {
    const opt = document.createElement('option');
    opt.value = b.symbol;
    const px = b.eval_price || b.eval_price_usd || b.price;
    opt.innerText = `${b.symbol} - ${b.name || b.type} (TIR ${b.tir.toFixed(2)}% | Precio u$s ${Number(px).toFixed(2)})`;
    sel.appendChild(opt);
  });

  if (prevVal && validBonds.some(b => b.symbol === prevVal)) {
    sel.value = prevVal;
    vanSelectedBond = prevVal;
  } else {
    // Default to GD30D, AL30D or first
    const defaultBond = validBonds.find(b => b.symbol === 'GD30D' || b.symbol === 'AL30D') || validBonds[0];
    sel.value = defaultBond.symbol;
    vanSelectedBond = defaultBond.symbol;
  }
}

function calculateVANMath(bond, investment, kRatePct, includeTerminalVT = vanIncludeTerminalVT) {
  if (!isVanEligible(bond)) return null;
  const evalPrice = bond.eval_price || bond.eval_price_usd || 0.0;
  if (evalPrice <= 0) return null;

  const k = kRatePct / 100.0;
  const freq = 2.0; // Semiannual standard
  const vt = bond.vt || bond.vr || 100.0;

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
    // Semiannual discount factor: 1 / (1 + k/2)^(2*t)
    const df = 1.0 / Math.pow(1.0 + k / freq, freq * t);
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

  let verdict = "En Precio Teórico (Rinde ~ k)";
  let verdictBadge = "neutral";
  let verdictIcon = "⚪";
  let verdictDesc = `El bono cotiza alineado con la tasa de descuento exigida (${kRatePct.toFixed(1)}%). Su valor presente coincide con el precio de compra.`;

  if (totalVAN > 1.0) {
    verdict = "OPORTUNIDAD / SUBVALUADO (VAN Positivo)";
    verdictBadge = "success";
    verdictIcon = "🟢";
    verdictDesc = `A una tasa exigida del ${kRatePct.toFixed(1)}%, el valor presente de los flujos ($ ${totalPV.toFixed(2)}) supera ampliamente tu inversión inicial ($ ${investment.toFixed(2)}). Comprarías $ ${totalPV.toFixed(2)} de valor futuro pagando solo $ ${investment.toFixed(2)}, con un margen de seguridad del +${marginPct.toFixed(1)}%.`;
  } else if (totalVAN < -1.0) {
    verdict = "SOBREVALUADO / RENDIMIENTO INFERIOR (VAN Negativo)";
    verdictBadge = "danger";
    verdictIcon = "🔴";
    verdictDesc = `A una tasa exigida del ${kRatePct.toFixed(1)}%, el mercado está pidiendo un precio demasiado alto respecto a los flujos descontados. El bono rinde menos que tu costo de oportunidad de capital k.`;
  }

  return {
    bond: bond,
    investment: investment,
    kRatePct: kRatePct,
    evalPrice: evalPrice,
    vt: vt,
    includeTerminalVT: includeTerminalVT,
    nominals: nominals,
    theoreticalPrice: theoreticalPrice,
    totalPV: totalPV,
    totalVAN: totalVAN,
    vanPct: vanPct,
    marginPct: marginPct,
    tirMarket: bond.tir || 0.0,
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
  const res = bond ? calculateVANMath(bond, vanInvestment, vanKRate, vanIncludeTerminalVT) : null;
  if (!res) {
    const cfTbodyEmpty = document.getElementById('vanCashflowsBody');
    if (cfTbodyEmpty) {
      cfTbodyEmpty.innerHTML = `<tr><td colspan="9" class="center" style="padding:16px; color:var(--text-dim);">No hay instrumentos con flujos de fondos confiables para valuar en este momento.</td></tr>`;
    }
    renderMarketVanRanking();
    return;
  }

  // Update KPIs (eligible instruments are valued in USD)
  const curSym = 'u$s';
  document.getElementById('kpiInvestment').innerText = `${curSym} ${res.investment.toLocaleString('es-AR', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
  document.getElementById('kpiNominals').innerText = `Nominales: ${Math.round(res.nominals).toLocaleString('es-AR')}`;

  document.getElementById('kpiPV').innerText = `${curSym} ${res.totalPV.toLocaleString('es-AR', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;

  const vanEl = document.getElementById('kpiVAN');
  const sign = res.totalVAN >= 0 ? '+' : '';
  vanEl.innerText = `${sign}${curSym} ${res.totalVAN.toFixed(2)}`;
  vanEl.className = 'kpi-value ' + (res.totalVAN > 0 ? 'kpi-pos' : (res.totalVAN < 0 ? 'kpi-neg' : ''));

  const vanPctEl = document.getElementById('kpiVanPct');
  vanPctEl.innerText = `Rentabilidad neta: ${sign}${res.vanPct.toFixed(2)}%`;
  vanPctEl.style.color = res.totalVAN > 0 ? '#10b981' : (res.totalVAN < 0 ? '#f43f5e' : '#94a3b8');

  document.getElementById('kpiPrices').innerText = `${curSym} ${res.theoreticalPrice.toFixed(2)} vs ${res.evalPrice.toFixed(2)}`;
  document.getElementById('kpiMargin').innerText = `Margen: ${res.marginPct >= 0 ? '+' : ''}${res.marginPct.toFixed(1)}%`;

  document.getElementById('kpiYields').innerText = `${res.tirMarket.toFixed(2)}% vs ${res.kRatePct.toFixed(2)}%`;
  const spread = Math.round((res.tirMarket - res.kRatePct) * 100);
  document.getElementById('kpiSpread').innerText = `Spread: ${spread >= 0 ? '+' : ''}${spread} bps`;

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
      ? `<span style="color:#10b981; font-weight:700;">${curSym} ${cf.cumCapital.toFixed(2)} (${capPct.toFixed(0)}%)</span>`
      : `<span style="color:var(--text-muted);">${curSym} ${cf.cumCapital.toFixed(2)}</span>`;
    const amortCell = cf.terminalCapital > 0
      ? `${curSym} ${cf.amort.toFixed(2)} <span style="color:#10b981;">+ ${cf.terminalCapital.toFixed(2)}</span>`
      : `${curSym} ${cf.amort.toFixed(2)}`;

    tr.innerHTML = `
      <td><strong>${cf.date}</strong> ${cf.isLast ? '<span class="badge-tag badge-lecap" style="font-size:9px; padding:1px 4px; margin-left:4px;">VTO</span>' : ''}</td>
      <td class="right">${curSym} ${cf.coupon.toFixed(3)}</td>
      <td class="right">${amortCell}</td>
      <td class="right">${capitalCell}</td>
      <td class="right" style="font-weight:700; color:#fff;">${curSym} ${cf.total.toFixed(2)}</td>
      <td class="right">${cf.years.toFixed(2)}</td>
      <td class="right" style="font-family:var(--font-mono); color:var(--text-dim);">${cf.df.toFixed(4)}</td>
      <td class="right" style="color:var(--primary-cyan); font-weight:700;">${curSym} ${cf.pv.toFixed(2)}</td>
      <td class="right" style="font-weight:700;">${curSym} ${cf.cumPv.toFixed(2)}</td>
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

  const candidates = [];
  const seen = new Set();

  allBonds.forEach(b => {
    if (!isVanEligible(b)) return;
    // Prefer USD benchmarks and single tickers
    const sym = b.symbol;
    if (!sym.endsWith('D') && !SOVEREIGN_BENCHMARKS.includes(sym)) return;
    const base = sym.substring(0, 4);
    if (seen.has(base) && !sym.endsWith('D')) return;
    seen.add(base);

    const vanRes = calculateVANMath(b, 1000.0, vanKRate, vanIncludeTerminalVT);
    if (vanRes) candidates.push(vanRes);
  });

  // Sort by VAN descending (most attractive first)
  candidates.sort((a, b) => b.totalVAN - a.totalVAN);

  if (candidates.length === 0) {
    rankingTbody.innerHTML = `<tr><td colspan="6" class="center" style="padding:16px; color:var(--text-dim);">Sin instrumentos con flujos confiables y precio vigente.</td></tr>`;
    return;
  }

  candidates.forEach(c => {
    const tr = document.createElement('tr');
    const isCurrent = (c.bond.symbol === vanSelectedBond);
    if (isCurrent) tr.style.backgroundColor = 'rgba(56, 189, 248, 0.15)';

    const vanClass = c.totalVAN > 0 ? 'cell-pos' : (c.totalVAN < 0 ? 'cell-neg' : '');
    const vanSign = c.totalVAN >= 0 ? '+' : '';

    tr.innerHTML = `
      <td>
        <strong style="color:#fff; cursor:pointer;" onclick="selectVanBond('${c.bond.symbol}')">${c.bond.symbol}</strong>
      </td>
      <td class="right">$ ${c.evalPrice.toFixed(2)}</td>
      <td class="right">$ ${c.theoreticalPrice.toFixed(2)}</td>
      <td class="right" style="color:var(--primary-cyan); font-weight:700;">${c.tirMarket.toFixed(2)}%</td>
      <td class="right ${vanClass}" style="font-weight:800; font-family:var(--font-mono);">
        ${vanSign}$ ${c.totalVAN.toFixed(1)}
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
  const slider = document.getElementById('horizonSlider');
  if (slider) {
    slider.addEventListener('input', (e) => {
      horizonYears = parseFloat(e.target.value);
      updateHorizonDisplays();
      runHorizonCalculation();
    });
  }

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

// Horizon IRR Math Calculation
function calculateBondHorizon(bond, horizonYrs) {
  if (!bond || !bond.cashflows || bond.cashflows.length === 0) return null;
  const evalPrice = bond.eval_price || bond.eval_price_usd || bond.price || 0.0;
  if (evalPrice <= 0) return null;

  const maxYear = Math.max(...bond.cashflows.map(c => c.years));
  // STRICT FILTER: "elimine los bonos tienen menos duracion / vencimiento"
  if (maxYear < (horizonYrs - 0.05)) {
    return {
      eligible: false,
      reason: `Vence en ${maxYear.toFixed(1)} años (antes de los ${horizonYrs.toFixed(1)} años)`
    };
  }

  const cfsDuring = bond.cashflows.filter(c => c.years <= (horizonYrs + 0.01));
  const cfsAfter = bond.cashflows.filter(c => c.years > (horizonYrs + 0.01));

  const cashCollected = cfsDuring.reduce((acc, c) => acc + c.total, 0.0);
  const freq = 2.0;
  const yExit = Math.max(0.001, (bond.tir || 10.0) / 100.0);

  let terminalPrice = 0.0;
  if (cfsAfter.length > 0) {
    cfsAfter.forEach(c => {
      const tRem = c.years - horizonYrs;
      const df = 1.0 / Math.pow(1.0 + yExit / freq, freq * tRem);
      terminalPrice += c.total * df;
    });
  }

  const totalInflow = cashCollected + terminalPrice;
  const hprPct = ((totalInflow - evalPrice) / evalPrice) * 100.0;

  // Solve Horizon IRR r via bisection search
  function diff(r) {
    let pv = 0.0;
    cfsDuring.forEach(c => {
      pv += c.total / Math.pow(1.0 + r / freq, freq * c.years);
    });
    pv += terminalPrice / Math.pow(1.0 + r / freq, freq * horizonYrs);
    return pv - evalPrice;
  }

  let low = -0.49;
  let high = 3.0;
  let horizonTir = 0.0;

  for (let iter = 0; iter < 60; iter++) {
    const mid = (low + high) / 2.0;
    const d = diff(mid);
    if (Math.abs(d) < 1e-5) {
      horizonTir = mid * 100.0;
      break;
    }
    if (d > 0) {
      low = mid;
    } else {
      high = mid;
    }
    horizonTir = mid * 100.0;
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
    cashCollected: cashCollected,
    terminalPrice: terminalPrice,
    totalInflow: totalInflow,
    hprPct: hprPct,
    horizonTir: horizonTir
  };
}

function runHorizonCalculation() {
  updateHorizonDisplays();

  const results = [];
  const seen = new Set();

  allBonds.forEach(b => {
    if (!b.cashflows || b.cashflows.length === 0) return;
    const sym = b.symbol;
    if (!sym.endsWith('D') && !SOVEREIGN_BENCHMARKS.includes(sym)) return;
    const base = sym.substring(0, 4);
    if (seen.has(base) && !sym.endsWith('D')) return;
    seen.add(base);

    const hRes = calculateBondHorizon(b, horizonYears);
    if (hRes && hRes.eligible) {
      results.push(hRes);
    }
  });

  // Sort by Horizon TIR descending (best investment on top)
  results.sort((a, b) => b.horizonTir - a.horizonTir);

  const eligibleCountEl = document.getElementById('horizonEligibleCount');
  if (eligibleCountEl) eligibleCountEl.innerText = `${results.length} bonos elegibles`;

  const rankingTbody = document.getElementById('horizonRankingBody');
  rankingTbody.innerHTML = '';

  if (results.length === 0) {
    rankingTbody.innerHTML = `<tr><td colspan="11" class="center" style="padding: 24px; color: var(--text-dim);">No hay bonos con vencimiento mayor o igual a ${horizonYears.toFixed(1)} años. Prueba reduciendo el horizonte.</td></tr>`;
    document.getElementById('horizonWinnerCard').style.display = 'none';
    return;
  }

  document.getElementById('horizonWinnerCard').style.display = 'flex';

  // Winner Showcase (Top #1)
  const winner = results[0];
  document.getElementById('winnerTicker').innerText = winner.symbol;
  document.getElementById('winnerName').innerText = `${winner.name} (${winner.law || 'Ley Arg/NY'})`;
  document.getElementById('winnerTir').innerText = `${winner.horizonTir.toFixed(2)}%`;
  document.getElementById('winnerCash').innerText = `u$s ${winner.cashCollected.toFixed(2)}`;
  document.getElementById('winnerTerminal').innerText = `u$s ${winner.terminalPrice.toFixed(2)}`;
  document.getElementById('winnerHpr').innerText = `+${winner.hprPct.toFixed(1)}%`;

  // Render Table
  results.forEach((r, idx) => {
    const tr = document.createElement('tr');
    const isWinner = (idx === 0);
    if (isWinner) tr.style.backgroundColor = 'rgba(245, 158, 11, 0.12)';

    tr.innerHTML = `
      <td class="center" style="font-weight:700; color:${isWinner ? 'var(--accent-amber)' : 'var(--text-dim)'};">
        ${isWinner ? '🏆 #1' : `#${idx + 1}`}
      </td>
      <td>
        <strong style="color:#fff; font-family:var(--font-mono);">${r.symbol}</strong>
      </td>
      <td style="font-size:11px; color:var(--text-muted);">${r.type} &bull; ${r.law || 'Arg'}</td>
      <td class="right" style="font-weight:700;">$ ${r.price.toFixed(2)}</td>
      <td class="center" style="font-size:11px; color:var(--text-muted);">${r.maturityDate ? r.maturityDate.substring(0, 10) : '-'}</td>
      <td class="right">${r.maturityYears.toFixed(1)} a</td>
      <td class="right" style="color:var(--text-main); font-weight:700;">$ ${r.cashCollected.toFixed(2)}</td>
      <td class="right" style="color:var(--text-muted);">$ ${r.terminalPrice.toFixed(2)}</td>
      <td class="right" style="color:var(--accent-green); font-weight:700;">+${r.hprPct.toFixed(1)}%</td>
      <td class="right highlight-col" style="font-size:13px; font-weight:800; font-family:var(--font-mono);">
        ${r.horizonTir.toFixed(2)}%
      </td>
      <td class="center">
        <button class="btn-inspect" onclick="openBondModal('${r.symbol}')">Ficha</button>
      </td>
    `;
    rankingTbody.appendChild(tr);
  });

  // Render Horizon Bar Chart
  renderHorizonChart(results);
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
    if (b.tir > 0 && b.mod_duration > 0 && b.tir < 100 && (b.type === 'Soberano USD' || b.type === 'Soberano')) {
      const point = { x: b.mod_duration, y: b.tir, symbol: b.symbol };
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
          title: { display: true, text: 'TIR / YTM (%)', color: '#94a3b8' },
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
    if (b.parity > 0 && b.mod_duration > 0 && (b.type === 'Soberano USD' || b.type === 'Soberano')) {
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
  const curSym = bond.currency === 'USD' ? 'u$s' : '$';

  document.getElementById('modalTicker').innerText = bond.symbol;
  document.getElementById('modalName').innerText = bond.name || bond.symbol;
  document.getElementById('modalType').innerText = `${bond.type || 'Soberano'} ${bond.currency || 'USD'}`;
  document.getElementById('modalLaw').innerText = bond.law || 'Ley Argentina';

  document.getElementById('modalPrice').innerText = `${curSym} ${bond.price ? bond.price.toFixed(2) : '-'}`;
  document.getElementById('modalVT').innerText = `${curSym} ${bond.vt ? bond.vt.toFixed(2) : '-'}`;
  document.getElementById('modalVR').innerText = `VR: ${bond.vr ? bond.vr.toFixed(2) : '-'} | IC: ${bond.accrued ? bond.accrued.toFixed(2) : '-'}`;

  document.getElementById('modalParity').innerText = bond.parity ? `${bond.parity.toFixed(1)}%` : '-%';
  document.getElementById('modalTIR').innerText = bond.tir ? `${bond.tir.toFixed(2)}%` : '-%';
  document.getElementById('modalDuration').innerText = bond.duration ? `${bond.duration.toFixed(2)} a` : '-';
  document.getElementById('modalMD').innerText = bond.mod_duration ? `${bond.mod_duration.toFixed(2)} a` : '-';

  // Reset Sensitivity Slider
  document.getElementById('simBpsSlider').value = 0;
  document.getElementById('simBpsVal').innerText = '0 bps';
  updateSimulator(0);

  // Update Quick Modal VAN
  updateModalVAN();

  // Render Cashflows Table
  const cfTbody = document.getElementById('cashflowsTableBody');
  cfTbody.innerHTML = '';

  if (bond.cashflows && bond.cashflows.length > 0) {
    bond.cashflows.forEach(cf => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${cf.date}</td>
        <td class="right">${curSym} ${cf.coupon.toFixed(3)}</td>
        <td class="right">${curSym} ${cf.amort.toFixed(2)}</td>
        <td class="right" style="font-weight:700;">${curSym} ${cf.total.toFixed(3)}</td>
        <td class="right">${cf.remaining_vr.toFixed(1)}</td>
        <td class="right">${cf.years.toFixed(2)}</td>
      `;
      cfTbody.appendChild(tr);
    });
  } else {
    cfTbody.innerHTML = `<tr><td colspan="6" class="center" style="color:var(--text-dim); padding:16px;">Cronograma no disponible para este instrumento genérico.</td></tr>`;
  }

  document.getElementById('bondModal').style.display = 'flex';
}

function closeModal() {
  document.getElementById('bondModal').style.display = 'none';
  currentSelectedBond = null;
}

function updateSimulator(bps) {
  if (!currentSelectedBond) return;
  const bond = currentSelectedBond;
  const curSym = bond.currency === 'USD' ? 'u$s' : '$';

  const p0 = bond.eval_price || bond.price || 0;
  const md = bond.mod_duration || 0;
  const vt = bond.vt || 100;

  // Price impact approx: dP / P = - MD * dy
  const dy = bps / 10000.0;
  const dPricePct = - md * dy;
  const newPrice = Math.max(0.01, p0 * (1.0 + dPricePct));
  const newParity = (vt > 0) ? (newPrice / vt * 100.0) : 0;

  document.getElementById('simEstPrice').innerText = `${curSym} ${newPrice.toFixed(2)}`;
  document.getElementById('simEstParity').innerText = `${newParity.toFixed(1)}%`;

  const impactEl = document.getElementById('simImpactPct');
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

  const res = calculateVANMath(currentSelectedBond, inv, k, vanIncludeTerminalVT);
  if (!res) {
    amtEl.innerText = 'No disponible: sin flujos de fondos confiables';
    amtEl.style.color = 'var(--text-dim)';
    badgeEl.style.backgroundColor = 'transparent';
    badgeEl.style.borderColor = 'var(--border-subtle)';
    return;
  }

  const curSym = currentSelectedBond.currency === 'USD' ? 'u$s' : '$';
  const sign = res.totalVAN >= 0 ? '+' : '';
  amtEl.innerText = `${sign}${curSym} ${res.totalVAN.toFixed(2)} (${sign}${res.vanPct.toFixed(1)}%)`;

  if (res.totalVAN > 1.0) {
    badgeEl.style.backgroundColor = 'rgba(16, 185, 129, 0.15)';
    badgeEl.style.borderColor = '#10b981';
    amtEl.style.color = '#10b981';
  } else if (res.totalVAN < -1.0) {
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

  const headers = ['Symbol', 'Tipo', 'Moneda', 'Precio', 'Var%', 'ValorTecnico', 'Paridad%', 'TIR%', 'DurationMac', 'DurationMod', 'Volumen', 'Vencimiento'];
  const rows = data.map(b => [
    b.symbol,
    `"${b.type || ''}"`,
    b.currency,
    b.price || '',
    b.change_pct || '',
    b.vt || '',
    b.parity || '',
    b.tir || '',
    b.duration || '',
    b.mod_duration || '',
    b.volume_amount || '',
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
