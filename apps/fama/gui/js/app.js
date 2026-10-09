// Fama-French Terminal Client Logic
// Depende de: glossary.js (GLOSSARY, glossaryKeyForFactor), tooltips.js (escapeHtml), charts.js (render*Chart)

let currentTicker = 'AAPL';
let currentAnalysisData = null;
let initialized = false;
let analysisSeq = 0;   // descarta respuestas de análisis que llegan fuera de orden

// ---------------------------------------------------------------------------
// Utilidades
// ---------------------------------------------------------------------------
function backend() {
  return window.pywebview && window.pywebview.api ? window.pywebview.api : null;
}

function showToast(message, type = 'error', durationMs = 7000) {
  const stack = document.getElementById('toastStack');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  toast.title = 'Clic para cerrar';
  toast.addEventListener('click', () => toast.remove());
  stack.appendChild(toast);
  setTimeout(() => toast.remove(), durationMs);
}

function showLoader(title, subtitle) {
  const overlay = document.getElementById('loadingOverlay');
  document.getElementById('loadingText').textContent = title || 'Calculando...';
  document.getElementById('loadingSubtext').textContent = subtitle || 'Procesando datos econométricos...';
  overlay.classList.add('active');
}

function hideLoader() {
  document.getElementById('loadingOverlay').classList.remove('active');
}

// Mismas marcas que la tabla de regresión del backend: *** <0.001, ** <0.01, * <0.05, † <0.1
function significanceMark(p) {
  if (p < 0.001) return '***';
  if (p < 0.01) return '**';
  if (p < 0.05) return '*';
  if (p < 0.1) return '†';
  return '';
}

function formatP(p) {
  return p < 0.0001 ? '< 0.0001' : p.toFixed(4);
}

// ---------------------------------------------------------------------------
// Arranque
// ---------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('tickerInput').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') runAnalysis();
  });

  if (backend()) {
    initApp();
  } else {
    window.addEventListener('pywebviewready', initApp);
    // Respaldo: si el puente nunca llega (p. ej. abierto en un navegador), se avisa en vez de quedar mudo.
    setTimeout(() => {
      if (!initialized) {
        initialized = true;
        document.getElementById('footerConnectionStatus').textContent = 'Motor Python no disponible';
        showToast('No se detectó el motor Python. Abre la aplicación con FAMA-FRENCH_App.vbs o "py app.py".', 'warning', 12000);
      }
    }, 1500);
  }
});

function initApp() {
  if (initialized) return;
  initialized = true;
  document.getElementById('footerConnectionStatus').textContent = 'Motor Python Conectado';
  runAnalysis();
  loadFactorsMetadata();
}

function switchTab(tabId, btn) {
  document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));

  const target = document.getElementById(tabId);
  if (target) {
    target.classList.add('active');
    btn.classList.add('active');
  }

  Tooltips.hide();
  // Los gráficos necesitan recalcular su tamaño cuando su pestaña vuelve a ser visible
  window.dispatchEvent(new Event('resize'));
}

function setTicker(t) {
  document.querySelectorAll('.ticker-pill').forEach(p => {
    p.classList.toggle('active', p.textContent === t);
  });
  document.getElementById('tickerInput').value = t;
  runAnalysis();
}

// ---------------------------------------------------------------------------
// Análisis de una acción
// ---------------------------------------------------------------------------
async function runAnalysis() {
  const api = backend();
  if (!api || !api.analyze_stock) {
    showToast('El motor Python no está disponible todavía.', 'warning');
    return;
  }

  const ticker = document.getElementById('tickerInput').value.trim().toUpperCase() || 'AAPL';
  const model = document.getElementById('modelSelect').value;
  const period = document.getElementById('periodSelect').value;
  currentTicker = ticker;
  const seq = ++analysisSeq;

  showLoader(`Analizando ${ticker}`, `Alineando factores de Kenneth French y ajustando regresión ${model}...`);

  try {
    const result = await api.analyze_stock(ticker, model, period);
    if (seq !== analysisSeq) return;   // llegó una solicitud más nueva

    if (result.error) {
      showToast(`Error en análisis: ${result.error}`);
      return;
    }

    currentAnalysisData = result;
    renderAnalysisResults(result);

    // Fecha de corte sugerida para el backtest: ~75 % de la muestra
    if (result.dates && result.dates.length > 70) {
      document.getElementById('btCutoffDate').value = result.dates[Math.floor(result.dates.length * 0.75)];
    }
  } catch (err) {
    console.error('Error running analysis:', err);
    if (seq === analysisSeq) showToast(`Error de comunicación con el motor: ${err.message || err}`);
  } finally {
    if (seq === analysisSeq) hideLoader();
  }
}

function renderAnalysisResults(data) {
  const est = data.estimation;
  const val = data.valuation;
  const info = data.stock_info;
  const metrics = est.econometrics.summary_metrics;
  const diags = est.econometrics.diagnostics;

  // 1. Header & KPIs
  document.getElementById('kpiPrice').textContent = `$${val.current_price.toFixed(2)}`;
  document.getElementById('kpiCompanyInfo').textContent = `${info.shortName || currentTicker} (${info.sector || 'US Market'})`;
  document.getElementById('footerTickerDetails').textContent = `Ticker: ${currentTicker} | ${info.shortName} | Bolsa: ${info.exchange || 'US Market'}`;

  document.getElementById('kpiCostEquity').textContent = `${(val.cost_of_equity_annual * 100).toFixed(2)}%`;
  document.getElementById('kpiRfText').textContent = `Tasa Libre de Riesgo (Rf): ${(est.rf_annual * 100).toFixed(2)}%`;

  document.getElementById('kpiTargetPrice').textContent = `$${val.target_1y_price.toFixed(2)}`;
  const sign = val.target_1y_return_pct >= 0 ? '+' : '';
  document.getElementById('kpiTargetReturn').textContent = `Retorno teórico proyectado: ${sign}${val.target_1y_return_pct.toFixed(2)}%`;

  document.getElementById('kpiAlpha').textContent = `${(est.alpha_annual * 100).toFixed(2)}%`;
  const pValStr = est.alpha_pvalue < 0.001 ? '< 0.001' : est.alpha_pvalue.toFixed(4);
  document.getElementById('kpiAlphaSig').textContent = `p-valor: ${pValStr} ${est.alpha_pvalue < 0.05 ? '(Significativo)' : '(No sig.)'}`;

  // Valuation Badge
  const badgeClass = val.status_color === 'bullish' ? 'badge-bullish' : (val.status_color === 'bearish' ? 'badge-bearish' : 'badge-neutral');
  document.getElementById('kpiValuationBadge').innerHTML = `<span class="badge ${badgeClass}">${escapeHtml(val.valuation_status)}</span>`;
  document.getElementById('kpiValuationDetail').textContent = `Rango 1Y: $${val.target_1y_lower.toFixed(2)} - $${val.target_1y_upper.toFixed(2)}`;

  // Tab badges
  document.getElementById('tabR2Badge').textContent = `R²: ${(metrics.r_squared * 100).toFixed(1)}%`;
  document.getElementById('modelNameBadge').textContent = est.model_name;
  document.getElementById('obsCountBadge').textContent = `${est.observations} Días`;

  const proxyBadge = document.getElementById('proxyBadge');
  if (data.proxy_days > 0) {
    proxyBadge.textContent = `${data.proxy_days} días estimados`;
    proxyBadge.dataset.note = `${data.proxy_days} de los ${est.observations} días de esta muestra usan factores estimados con ETFs, no los oficiales.`;
    proxyBadge.style.display = '';
  } else {
    proxyBadge.style.display = 'none';
  }

  // 2. Factor Sensitivity Breakdown
  const sensitivityContainer = document.getElementById('factorSensitivityContainer');
  sensitivityContainer.innerHTML = '';

  est.factor_contributions.forEach(fc => {
    const barWidthPct = Math.min(100, (Math.min(2.5, Math.abs(fc.beta)) / 2.0) * 100);
    const barColor = fc.beta >= 0 ? '#10b981' : '#f43f5e';
    const key = glossaryKeyForFactor(fc.factor);

    const row = document.createElement('div');
    row.style.cssText = 'display: flex; flex-direction: column; gap: 4px;';
    row.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; font-size: 11px;">
        <span class="gl" data-glossary="${escapeHtml(key)}" data-note="${escapeHtml(fc.interpretation)}"
              style="font-weight: 700; color: #fff; font-family: var(--font-mono);">${escapeHtml(fc.factor)}</span>
        <span style="font-family: var(--font-mono); color: ${barColor}; font-weight: 600;">β = ${fc.beta.toFixed(3)} ${significanceMark(fc.p_value)}</span>
      </div>
      <div class="factor-bar-track">
        <div class="factor-bar-fill" style="width: ${barWidthPct}%; background-color: ${barColor};"></div>
      </div>
      <div style="display: flex; justify-content: space-between; font-size: 10px; color: var(--text-dim);">
        <span>${escapeHtml(fc.interpretation)}</span>
        <span>Aporte a kₑ: ${(fc.annual_contribution * 100).toFixed(2)}%</span>
      </div>
    `;
    sensitivityContainer.appendChild(row);
  });

  // 3. Projections Table
  const horizTable = document.getElementById('valuationHorizonsTable');
  horizTable.innerHTML = val.projections.map(p => `
    <tr>
      <td style="font-weight: 600; color: #fff;">${escapeHtml(p.label)}</td>
      <td class="numeric" style="color: #10b981; font-weight: 700;">$${p.expected_price.toFixed(2)}</td>
      <td class="numeric">$${p.ci_lower.toFixed(2)}</td>
      <td class="numeric">$${p.ci_upper.toFixed(2)}</td>
      <td class="numeric" style="color: ${p.expected_return_pct >= 0 ? '#10b981' : '#f43f5e'};">
        ${p.expected_return_pct >= 0 ? '+' : ''}${p.expected_return_pct.toFixed(2)}%
      </td>
    </tr>`).join('');

  // 4. Cost of Equity Breakdown Table
  const rfPct = (est.rf_annual * 100).toFixed(2);
  const factorRows = est.factor_contributions.map(fc => `
    <tr>
      <td style="font-weight: 600;"><span class="gl" data-glossary="${escapeHtml(glossaryKeyForFactor(fc.factor))}" data-note="${escapeHtml(fc.interpretation)}">${escapeHtml(fc.factor)}</span></td>
      <td class="numeric">${fc.beta.toFixed(3)}</td>
      <td class="numeric">${(fc.factor_premium_annual * 100).toFixed(2)}%</td>
      <td class="numeric" style="color: #10b981; font-weight: 600;">${(fc.annual_contribution * 100).toFixed(2)}%</td>
    </tr>`).join('');

  document.getElementById('costEquityBreakdownTable').innerHTML = `
    <tr>
      <td style="font-weight: 600;"><span class="gl" data-glossary="rf">Tasa Libre de Riesgo (Rf)</span></td>
      <td class="numeric">1.000</td>
      <td class="numeric">${rfPct}%</td>
      <td class="numeric" style="color: #3b82f6; font-weight: 700;">${rfPct}%</td>
    </tr>
    ${factorRows}
    <tr style="border-top: 2px solid var(--border-color);">
      <td style="font-weight: 800; color: #fff;"><span class="gl" data-glossary="ke">TOTAL kₑ (Costo de Equity)</span></td>
      <td class="numeric">--</td>
      <td class="numeric">--</td>
      <td class="numeric" style="color: #10b981; font-weight: 800; font-size: 13px;">${(val.cost_of_equity_annual * 100).toFixed(2)}%</td>
    </tr>`;

  // 5. Econometric Diagnostics Table
  document.getElementById('summaryR2').textContent = `R²: ${(metrics.r_squared * 100).toFixed(2)}%`;
  document.getElementById('summaryAdjR2').textContent = `Adj R²: ${(metrics.adj_r_squared * 100).toFixed(2)}%`;
  document.getElementById('summaryFStat').textContent = `F-Stat: ${metrics.f_statistic.toFixed(2)}`;

  document.getElementById('olsCoefficientsTable').innerHTML = est.econometrics.parameters.map(p => {
    const note = `Coeficiente ${p.coef.toFixed(5)}, p-valor ${formatP(p.p_value)}: ` +
      (p.p_value < 0.05 ? 'estadísticamente significativo, no parece azar.' : 'no significativo, no se distingue de cero.');
    return `
    <tr>
      <td style="font-weight: 700; color: #fff;"><span class="gl" data-glossary="${escapeHtml(glossaryKeyForFactor(p.factor))}" data-note="${escapeHtml(note)}">${escapeHtml(p.label)}</span></td>
      <td class="numeric" style="color: #06b6d4; font-weight: 600;">${p.coef.toFixed(5)}</td>
      <td class="numeric">${p.std_err.toFixed(5)}</td>
      <td class="numeric">${p.t_stat.toFixed(3)}</td>
      <td class="numeric" style="color: ${p.p_value < 0.05 ? '#10b981' : 'var(--text-muted)'}; font-weight: 600;">${formatP(p.p_value)}</td>
      <td class="numeric">[${p.ci_lower.toFixed(4)}, ${p.ci_upper.toFixed(4)}]</td>
      <td><span class="badge ${p.p_value < 0.05 ? 'badge-bullish' : 'badge-neutral'}">${escapeHtml(p.significance || 'n.s.')}</span></td>
    </tr>`;
  }).join('');

  // Diagnostic Badges & Texts
  document.getElementById('dwBadge').textContent = `d = ${diags.durbin_watson.stat.toFixed(3)}`;
  document.getElementById('dwDesc').textContent = diags.durbin_watson.verdict;

  setDiagnostic('bg', diags.breusch_godfrey, 'Test no aplicable para la longitud de serie.');
  setDiagnostic('bp', diags.breusch_pagan, 'Test no aplicable.');

  document.getElementById('jbBadge').textContent = `p = ${diags.jarque_bera.p_value.toFixed(4)}`;
  document.getElementById('jbDesc').textContent = `${diags.jarque_bera.verdict} (Asimetría: ${diags.jarque_bera.skewness.toFixed(2)}, Curtosis: ${diags.jarque_bera.kurtosis.toFixed(2)})`;

  renderPriceTrajectoryChart(data.dates, data.prices, val.projections, val.current_price);
  renderResidualsCharts(data.residuals, est.econometrics.residuals_distribution);
}

function setDiagnostic(prefix, test, fallbackText) {
  const badge = document.getElementById(`${prefix}Badge`);
  const desc = document.getElementById(`${prefix}Desc`);
  if (test.p_value !== null && test.p_value !== undefined) {
    badge.textContent = `p = ${test.p_value.toFixed(4)}`;
    desc.textContent = test.verdict;
  } else {
    badge.textContent = 'N/A';
    desc.textContent = fallbackText;
  }
}

// ---------------------------------------------------------------------------
// Backtest
// ---------------------------------------------------------------------------
async function runBacktest() {
  const api = backend();
  if (!api || !api.run_backtest) {
    showToast('El motor Python no está disponible para el backtest.', 'warning');
    return;
  }

  const cutoffDate = document.getElementById('btCutoffDate').value;
  const trainWindow = parseInt(document.getElementById('btTrainWindow').value, 10);
  const testHorizon = parseInt(document.getElementById('btTestHorizon').value, 10);
  const model = document.getElementById('modelSelect').value;

  if (!cutoffDate) {
    showToast('Selecciona una fecha de corte histórica.', 'warning');
    return;
  }

  showLoader('Ejecutando Backtest Fuera de Muestra', `Calibrando Fama-French hasta ${cutoffDate} y evaluando contra datos históricos reales...`);

  try {
    const btResult = await api.run_backtest(cutoffDate, trainWindow, testHorizon, model);
    if (btResult.error) {
      showToast(`Error en backtest: ${btResult.error}`);
      return;
    }
    renderBacktestResults(btResult);
  } catch (err) {
    console.error('Error running backtest:', err);
    showToast(`Error al ejecutar backtest: ${err.message || err}`);
  } finally {
    hideLoader();
  }
}

function renderBacktestResults(bt) {
  const m = bt.metrics;

  document.getElementById('btP0Price').textContent = `$${bt.cutoff_price.toFixed(2)}`;
  document.getElementById('btCutoffDateText').textContent = `Corte T₀: ${bt.cutoff_date}`;

  document.getElementById('btActualFinalPrice').textContent = `$${m.final_actual_price.toFixed(2)}`;
  document.getElementById('btActualReturnText').textContent =
    `Retorno de mercado: ${m.actual_total_return_pct >= 0 ? '+' : ''}${m.actual_total_return_pct.toFixed(2)}%`;

  document.getElementById('btPredFinalPrice').textContent = `$${m.final_pred_price.toFixed(2)}`;
  document.getElementById('btPredReturnText').textContent =
    `Retorno estimado: ${m.pred_total_return_pct >= 0 ? '+' : ''}${m.pred_total_return_pct.toFixed(2)}%`;

  const errEl = document.getElementById('btFinalErrorPct');
  errEl.textContent = `${m.final_error_pct >= 0 ? '+' : ''}${m.final_error_pct.toFixed(2)}%`;
  errEl.style.color = Math.abs(m.final_error_pct) < 5 ? '#10b981' : (Math.abs(m.final_error_pct) < 15 ? '#f59e0b' : '#f43f5e');
  document.getElementById('btFinalErrorDollar').textContent = `Diferencia: $${m.final_error_dollar.toFixed(2)}`;

  document.getElementById('tabErrBadge').textContent = `Error: ${Math.abs(m.final_error_pct).toFixed(1)}%`;

  document.getElementById('btMapeVal').textContent = `MAPE: ${m.mape.toFixed(2)}%`;
  document.getElementById('btRmseVal').innerHTML =
    `<span class="gl" data-glossary="rmse">RMSE</span>: $${m.rmse.toFixed(2)} | <span class="gl" data-glossary="te">TE</span>: ${m.tracking_error_annual_pct.toFixed(2)}%`;

  document.getElementById('btCoverageBadge').textContent = `Cobertura IC 95%: ${m.ci_coverage_pct.toFixed(1)}%`;
  const dirBadge = document.getElementById('btDirectionBadge');
  dirBadge.textContent = `Acierto de Dirección: ${m.directional_hit ? 'CORRECTO ✓' : 'DESVIADO ✗'}`;
  dirBadge.className = m.directional_hit ? 'badge badge-bullish' : 'badge badge-bearish';

  renderBacktestChart(bt.chart_data);

  // Daily Trajectory Audit Table
  const { dates, actual_prices: actuals, pred_prices: preds, ci_upper: ciUp, ci_lower: ciLow, cutoff_index: cutoffIdx } = bt.chart_data;
  const rows = [];
  for (let i = cutoffIdx + 1; i < dates.length; i++) {
    const act = actuals[i];
    const prd = preds[i];
    const diff = prd - act;
    const diffPct = (diff / act) * 100.0;
    rows.push(`
      <tr>
        <td class="mono">${dates[i]}</td>
        <td class="numeric mono">$${act.toFixed(2)}</td>
        <td class="numeric mono" style="color: #10b981; font-weight: 600;">$${prd.toFixed(2)}</td>
        <td class="numeric mono" style="color: ${diff >= 0 ? '#10b981' : '#f43f5e'};">$${diff.toFixed(2)}</td>
        <td class="numeric mono" style="color: ${Math.abs(diffPct) < 5 ? '#10b981' : '#f59e0b'}; font-weight: 600;">
          ${diffPct >= 0 ? '+' : ''}${diffPct.toFixed(2)}%
        </td>
        <td class="numeric mono">$${ciLow[i].toFixed(2)}</td>
        <td class="numeric mono">$${ciUp[i].toFixed(2)}</td>
      </tr>`);
  }
  document.getElementById('backtestDailyTable').innerHTML = rows.join('');
}

// ---------------------------------------------------------------------------
// Factores oficiales
// ---------------------------------------------------------------------------
async function loadFactorsMetadata() {
  try {
    const api = backend();
    if (!api || !api.get_factors_info) return;
    const info = await api.get_factors_info();
    if (info.error) {
      showToast(`No se pudieron cargar los factores: ${info.error}`, 'warning');
      return;
    }
    document.getElementById('ffLatestDate').textContent = info.latest_date || 'Sincronizado';
    document.getElementById('ffObsCount').textContent = info.observations ? `${info.observations.toLocaleString()} días` : '--';
    document.getElementById('ffCacheStatus').textContent = info.is_cached ? 'Caché Local Activa' : 'Descargando...';
    document.getElementById('ffProxyDays').textContent = info.proxy_days !== undefined ? `${info.proxy_days} días` : '--';
    if (info.last_official_date) {
      document.getElementById('ffOfficialText').textContent = `Último dato oficial Dartmouth: ${info.last_official_date}`;
    }
  } catch (e) {
    console.error('Error fetching factor metadata:', e);
  }
}

async function refreshFactorsData() {
  const api = backend();
  if (!api || !api.refresh_factors) return;

  showLoader('Actualizando Factores Oficiales', 'Conectando con Dartmouth College (Kenneth French Library)...');
  try {
    const res = await api.refresh_factors();
    if (res.error) {
      showToast(`Error actualizando factores: ${res.error}`);
      return;
    }
    showToast('Factores actualizados correctamente.', 'success', 3500);
    await loadFactorsMetadata();
    await runAnalysis();
  } catch (e) {
    showToast(`Error actualizando factores: ${e.message || e}`);
  } finally {
    hideLoader();
  }
}

// ---------------------------------------------------------------------------
// Radar sectorial S&P 500
// ---------------------------------------------------------------------------
let currentSectorId = 'tech';
let currentSectorData = null;

async function onSectorDropdownChange(sectorId) {
  if (!sectorId) return;
  currentSectorId = sectorId;
  switchTab('sectorsTab', document.getElementById('btnSectorsTab'));
  await loadSector(sectorId);
}

async function reloadCurrentSector() {
  await loadSector(currentSectorId, true);
}

async function loadSector(sectorId, forceRefresh = false) {
  const api = backend();
  if (!api || !api.analyze_sector) return;

  const model = document.getElementById('modelSelect').value;
  const period = document.getElementById('periodSelect').value;

  showLoader('Cargando Sector S&P 500', 'Descargando cotizaciones y calculando Fama-French para el sector...');

  try {
    const result = await api.analyze_sector(sectorId, model, period, forceRefresh);
    if (result.error) {
      showToast(`Error analizando sector: ${result.error}`);
      return;
    }
    currentSectorData = result;
    renderSectorResults(result);
    if (result.skipped && result.skipped.length) {
      showToast(`No se pudieron analizar: ${result.skipped.join(', ')}`, 'warning');
    }
  } catch (err) {
    console.error('Error loading sector:', err);
    showToast(`Error de sector: ${err.message || err}`);
  } finally {
    hideLoader();
  }
}

function renderSectorResults(data) {
  document.getElementById('sectorHeaderTitle').textContent = data.sector_name;
  document.getElementById('sectorHeaderEtf').textContent = `ETF: ${data.etf}`;
  document.getElementById('tabSectorBadge').textContent = data.etf;
  document.getElementById('sectorHeaderDesc').textContent = data.description;
  document.getElementById('sectorStocksCountBadge').textContent = `${data.total_stocks} Acciones Analizadas`;

  const s = data.summary;
  document.getElementById('secKpiAvgKe').textContent = `${s.avg_cost_of_equity_pct.toFixed(2)}%`;
  document.getElementById('secKpiAvgBeta').textContent = `${s.avg_beta_mkt.toFixed(2)}`;
  document.getElementById('secKpiAvgAlpha').textContent = `${s.avg_alpha_pct >= 0 ? '+' : ''}${s.avg_alpha_pct.toFixed(2)}%`;

  document.getElementById('secBuyCount').textContent = `${s.buy_count} COMPRAR`;
  document.getElementById('secHoldCount').textContent = `${s.hold_count} MANTENER`;
  document.getElementById('secSellCount').textContent = `${s.sell_count} VENDER`;

  renderSectorTableRows(data.stocks);
  filterSectorTable(document.getElementById('sectorFilterInput').value);
}

const VERDICT_GLOSSARY_KEY = { COMPRAR: 'verdict_buy', MANTENER: 'verdict_hold', VENDER: 'verdict_sell' };

function renderSectorTableRows(stocks) {
  const tbody = document.getElementById('sectorStocksTableBody');
  tbody.innerHTML = '';

  stocks.forEach(st => {
    const d = st.decision;
    const badgeClass = d.color === 'bullish' ? 'badge-bullish' : (d.color === 'bearish' ? 'badge-bearish' : 'badge-neutral');
    const symbol = escapeHtml(st.symbol);

    const tr = document.createElement('tr');
    tr.dataset.symbol = st.symbol.toLowerCase();
    tr.dataset.name = st.name.toLowerCase();

    tr.innerHTML = `
      <td class="mono" style="font-weight: 700; color: #fff;">
        <span style="color: var(--accent-cyan);">${symbol}</span>
      </td>
      <td style="font-weight: 600; color: var(--text-main);">${escapeHtml(st.name)}</td>
      <td class="numeric mono">$${st.current_price.toFixed(2)}</td>
      <td class="numeric mono" style="color: #10b981; font-weight: 700;">${st.cost_of_equity_pct.toFixed(2)}%</td>
      <td class="numeric mono">${st.beta_mkt.toFixed(2)}</td>
      <td class="numeric mono">${st.beta_smb.toFixed(2)}</td>
      <td class="numeric mono">${st.beta_hml.toFixed(2)}</td>
      <td class="numeric mono" style="color: ${st.alpha_ann_pct >= 0 ? '#10b981' : '#f43f5e'}; font-weight: 600;">
        ${st.alpha_ann_pct >= 0 ? '+' : ''}${st.alpha_ann_pct.toFixed(2)}%
      </td>
      <td class="numeric mono">${st.pe_ratio ? st.pe_ratio.toFixed(1) : '--'}</td>
      <td>
        <div style="display: flex; flex-direction: column; gap: 2px;">
          <div><span class="badge ${badgeClass}" data-glossary="${VERDICT_GLOSSARY_KEY[d.verdict] || 'decision_rule'}" data-note="${escapeHtml(d.reason)}">${escapeHtml(d.badge)}</span></div>
          <div style="font-size: 10px; color: var(--text-dim); line-height: 1.3;">${escapeHtml(d.reason)}</div>
        </div>
      </td>
      <td style="text-align: center;">
        <button class="table-inspect-btn" onclick="inspectStockFromSector('${symbol}')" title="Analizar a fondo en terminal">
          <span>Ver ↗</span>
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function filterSectorTable(query) {
  const q = (query || '').trim().toLowerCase();
  document.querySelectorAll('#sectorStocksTableBody tr').forEach(r => {
    const match = (r.dataset.symbol || '').includes(q) || (r.dataset.name || '').includes(q);
    r.style.display = match ? '' : 'none';
  });
}

function inspectStockFromSector(symbol) {
  document.getElementById('tickerInput').value = symbol;
  switchTab('valuationTab', document.querySelector('.tabs-bar .tab-btn:first-child'));
  runAnalysis();
}
