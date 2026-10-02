// Fama-French Terminal Client Logic

let currentTicker = 'AAPL';
let currentAnalysisData = null;

// DOM ready listener
document.addEventListener('DOMContentLoaded', () => {
  // Enter key trigger on ticker input
  const input = document.getElementById('tickerInput');
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      runAnalysis();
    }
  });

  // Wait for pywebview API to be injected or run init
  if (window.pywebview) {
    initApp();
  } else {
    window.addEventListener('pywebviewready', initApp);
    // Timeout fallback for direct browser debugging
    setTimeout(() => {
      if (!currentAnalysisData) {
        initApp();
      }
    }, 800);
  }
});

function initApp() {
  document.getElementById('footerConnectionStatus').textContent = 'Motor Python Conectado';
  runAnalysis();
  loadFactorsMetadata();
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

function switchTab(tabId, btn) {
  document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  
  const target = document.getElementById(tabId);
  if (target) {
    target.classList.add('active');
    btn.classList.add('active');
  }

  // Auto-resize charts when tab becomes visible
  window.dispatchEvent(new Event('resize'));
}

function setTicker(t) {
  document.querySelectorAll('.ticker-pill').forEach(p => {
    p.classList.toggle('active', p.textContent === t);
  });
  document.getElementById('tickerInput').value = t;
  runAnalysis();
}

async function runAnalysis() {
  const ticker = document.getElementById('tickerInput').value.trim().toUpperCase() || 'AAPL';
  const model = document.getElementById('modelSelect').value;
  const period = document.getElementById('periodSelect').value;
  currentTicker = ticker;

  showLoader(`Analizando ${ticker}`, `Alineando factores de Kenneth French y ajustando regresión ${model}...`);

  try {
    let result = null;
    if (window.pywebview && window.pywebview.api && window.pywebview.api.analyze_stock) {
      result = await window.pywebview.api.analyze_stock(ticker, model, period);
    } else {
      console.warn('PyWebView API no detectada en este entorno, usando fallback local.');
      hideLoader();
      return;
    }

    if (result.error) {
      alert(`Error en análisis: ${result.error}`);
      hideLoader();
      return;
    }

    currentAnalysisData = result;
    renderAnalysisResults(result);

    // Auto set backtest default cutoff to ~6 months ago
    if (result.dates && result.dates.length > 70) {
      const suggestedCutoff = result.dates[Math.floor(result.dates.length * 0.75)];
      document.getElementById('btCutoffDate').value = suggestedCutoff;
    }

  } catch (err) {
    console.error('Error running analysis:', err);
    alert(`Error de comunicación con el motor: ${err.message || err}`);
  } finally {
    hideLoader();
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
  const valBadgeContainer = document.getElementById('kpiValuationBadge');
  const badgeClass = val.status_color === 'bullish' ? 'badge-bullish' : (val.status_color === 'bearish' ? 'badge-bearish' : 'badge-neutral');
  valBadgeContainer.innerHTML = `<span class="badge ${badgeClass}">${val.valuation_status}</span>`;
  document.getElementById('kpiValuationDetail').textContent = `Rango 1Y: $${val.target_1y_lower.toFixed(2)} - $${val.target_1y_upper.toFixed(2)}`;

  // Tab badges
  document.getElementById('tabR2Badge').textContent = `R²: ${(metrics.r_squared * 100).toFixed(1)}%`;
  document.getElementById('modelNameBadge').textContent = est.model_name;
  document.getElementById('obsCountBadge').textContent = `${est.observations} Días`;

  // 2. Factor Sensitivity Breakdown
  const sensitivityContainer = document.getElementById('factorSensitivityContainer');
  sensitivityContainer.innerHTML = '';

  est.factor_contributions.forEach(fc => {
    const absBeta = Math.min(2.5, Math.abs(fc.beta));
    const barWidthPct = Math.min(100, (absBeta / 2.0) * 100);
    const barColor = fc.beta >= 0 ? '#10b981' : '#f43f5e';
    const sigStar = fc.p_value < 0.01 ? '***' : (fc.p_value < 0.05 ? '**' : (fc.p_value < 0.1 ? '*' : ''));

    const row = document.createElement('div');
    row.style.display = 'flex';
    row.style.flexDirection = 'column';
    row.style.gap = '4px';

    row.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; font-size: 11px;">
        <span style="font-weight: 700; color: #fff; font-family: var(--font-mono);">${fc.factor}</span>
        <span style="font-family: var(--font-mono); color: ${barColor}; font-weight: 600;">β = ${fc.beta.toFixed(3)} ${sigStar}</span>
      </div>
      <div class="factor-bar-track">
        <div class="factor-bar-fill" style="width: ${barWidthPct}%; background-color: ${barColor};"></div>
      </div>
      <div style="display: flex; justify-content: space-between; font-size: 10px; color: var(--text-dim);">
        <span>${fc.interpretation}</span>
        <span>Aporte a kₑ: ${(fc.annual_contribution * 100).toFixed(2)}%</span>
      </div>
    `;
    sensitivityContainer.appendChild(row);
  });

  // 3. Projections Table
  const horizTable = document.getElementById('valuationHorizonsTable');
  horizTable.innerHTML = '';
  val.projections.forEach(p => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td style="font-weight: 600; color: #fff;">${p.label}</td>
      <td class="numeric" style="color: #10b981; font-weight: 700;">$${p.expected_price.toFixed(2)}</td>
      <td class="numeric">$${p.ci_lower.toFixed(2)}</td>
      <td class="numeric">$${p.ci_upper.toFixed(2)}</td>
      <td class="numeric" style="color: ${p.expected_return_pct >= 0 ? '#10b981' : '#f43f5e'};">
        ${p.expected_return_pct >= 0 ? '+' : ''}${p.expected_return_pct.toFixed(2)}%
      </td>
    `;
    horizTable.appendChild(tr);
  });

  // 4. Cost of Equity Breakdown Table
  const ceTable = document.getElementById('costEquityBreakdownTable');
  ceTable.innerHTML = `
    <tr>
      <td style="font-weight: 600;">Tasa Libre de Riesgo (Rf)</td>
      <td class="numeric">1.000</td>
      <td class="numeric">${(est.rf_annual * 100).toFixed(2)}%</td>
      <td class="numeric" style="color: #3b82f6; font-weight: 700;">${(est.rf_annual * 100).toFixed(2)}%</td>
    </tr>
  `;
  est.factor_contributions.forEach(fc => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td style="font-weight: 600;">${fc.factor}</td>
      <td class="numeric">${fc.beta.toFixed(3)}</td>
      <td class="numeric">${(fc.factor_premium_annual * 100).toFixed(2)}%</td>
      <td class="numeric" style="color: #10b981; font-weight: 600;">${(fc.annual_contribution * 100).toFixed(2)}%</td>
    </tr>
  `;
    ceTable.appendChild(tr);
  });

  // Total row
  const totalRow = document.createElement('tr');
  totalRow.style.borderTop = '2px solid var(--border-color)';
  totalRow.innerHTML = `
    <td style="font-weight: 800; color: #fff;">TOTAL kₑ (Costo de Equity)</td>
    <td class="numeric">--</td>
    <td class="numeric">--</td>
    <td class="numeric" style="color: #10b981; font-weight: 800; font-size: 13px;">${(val.cost_of_equity_annual * 100).toFixed(2)}%</td>
  `;
  ceTable.appendChild(totalRow);

  // 5. Econometric Diagnostics Table
  document.getElementById('summaryR2').textContent = `R²: ${(metrics.r_squared * 100).toFixed(2)}%`;
  document.getElementById('summaryAdjR2').textContent = `Adj R²: ${(metrics.adj_r_squared * 100).toFixed(2)}%`;
  document.getElementById('summaryFStat').textContent = `F-Stat: ${metrics.f_statistic.toFixed(2)}`;

  const olsTable = document.getElementById('olsCoefficientsTable');
  olsTable.innerHTML = '';
  est.econometrics.parameters.forEach(p => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td style="font-weight: 700; color: #fff;">${p.label}</td>
      <td class="numeric" style="color: #06b6d4; font-weight: 600;">${p.coef.toFixed(5)}</td>
      <td class="numeric">${p.std_err.toFixed(5)}</td>
      <td class="numeric">${p.t_stat.toFixed(3)}</td>
      <td class="numeric" style="color: ${p.p_value < 0.05 ? '#10b981' : 'var(--text-muted)'}; font-weight: 600;">
        ${p.p_value < 0.0001 ? '< 0.0001' : p.p_value.toFixed(4)}
      </td>
      <td class="numeric">[${p.ci_lower.toFixed(4)}, ${p.ci_upper.toFixed(4)}]</td>
      <td><span class="badge ${p.p_value < 0.05 ? 'badge-bullish' : 'badge-neutral'}">${p.significance || 'n.s.'}</span></td>
    `;
    olsTable.appendChild(tr);
  });

  // Diagnostic Badges & Texts
  // Durbin-Watson
  document.getElementById('dwBadge').textContent = `d = ${diags.durbin_watson.stat.toFixed(3)}`;
  document.getElementById('dwDesc').textContent = diags.durbin_watson.verdict;

  // Breusch-Godfrey
  if (diags.breusch_godfrey.p_value !== null && diags.breusch_godfrey.p_value !== undefined) {
    document.getElementById('bgBadge').textContent = `p = ${diags.breusch_godfrey.p_value.toFixed(4)}`;
    document.getElementById('bgDesc').textContent = diags.breusch_godfrey.verdict;
  } else {
    document.getElementById('bgBadge').textContent = 'N/A';
    document.getElementById('bgDesc').textContent = 'Test no aplicable para la longitud de serie.';
  }

  // Breusch-Pagan
  if (diags.breusch_pagan.p_value !== null && diags.breusch_pagan.p_value !== undefined) {
    document.getElementById('bpBadge').textContent = `p = ${diags.breusch_pagan.p_value.toFixed(4)}`;
    document.getElementById('bpDesc').textContent = diags.breusch_pagan.verdict;
  } else {
    document.getElementById('bpBadge').textContent = 'N/A';
  }

  // Jarque-Bera
  document.getElementById('jbBadge').textContent = `p = ${diags.jarque_bera.p_value.toFixed(4)}`;
  document.getElementById('jbDesc').textContent = `${diags.jarque_bera.verdict} (Asimetría: ${diags.jarque_bera.skewness.toFixed(2)}, Curtosis: ${diags.jarque_bera.kurtosis.toFixed(2)})`;

  // Render Charts
  renderPriceTrajectoryChart(data.dates, data.prices, val.projections, val.current_price);
  renderResidualsCharts(data.residuals, est.econometrics.residuals_distribution);
}

async function runBacktest() {
  const cutoffDate = document.getElementById('btCutoffDate').value;
  const trainWindow = parseInt(document.getElementById('btTrainWindow').value);
  const testHorizon = parseInt(document.getElementById('btTestHorizon').value);
  const model = document.getElementById('modelSelect').value;

  if (!cutoffDate) {
    alert('Por favor selecciona una fecha de corte histórica.');
    return;
  }

  showLoader('Ejecutando Backtest Fuera de Muestra', `Calibrando Fama-French hasta ${cutoffDate} y evaluando contra datos históricos reales...`);

  try {
    let btResult = null;
    if (window.pywebview && window.pywebview.api && window.pywebview.api.run_backtest) {
      btResult = await window.pywebview.api.run_backtest(cutoffDate, trainWindow, testHorizon, model);
    } else {
      alert('PyWebView API no disponible para backtest.');
      hideLoader();
      return;
    }

    if (btResult.error) {
      alert(`Error en backtest: ${btResult.error}`);
      hideLoader();
      return;
    }

    renderBacktestResults(btResult);
  } catch (err) {
    console.error('Error running backtest:', err);
    alert(`Error al ejecutar backtest: ${err.message || err}`);
  } finally {
    hideLoader();
  }
}

function renderBacktestResults(bt) {
  const m = bt.metrics;

  document.getElementById('btP0Price').textContent = `$${bt.cutoff_price.toFixed(2)}`;
  document.getElementById('btCutoffDateText').textContent = `Corte T₀: ${bt.cutoff_date}`;

  document.getElementById('btActualFinalPrice').textContent = `$${m.final_actual_price.toFixed(2)}`;
  const signAct = m.actual_total_return_pct >= 0 ? '+' : '';
  document.getElementById('btActualReturnText').textContent = `Retorno de mercado: ${signAct}${m.actual_total_return_pct.toFixed(2)}%`;

  document.getElementById('btPredFinalPrice').textContent = `$${m.final_pred_price.toFixed(2)}`;
  const signPred = m.pred_total_return_pct >= 0 ? '+' : '';
  document.getElementById('btPredReturnText').textContent = `Retorno estimado: ${signPred}${m.pred_total_return_pct.toFixed(2)}%`;

  const signErr = m.final_error_pct >= 0 ? '+' : '';
  document.getElementById('btFinalErrorPct').textContent = `${signErr}${m.final_error_pct.toFixed(2)}%`;
  const errColor = Math.abs(m.final_error_pct) < 5 ? '#10b981' : (Math.abs(m.final_error_pct) < 15 ? '#f59e0b' : '#f43f5e');
  document.getElementById('btFinalErrorPct').style.color = errColor;
  document.getElementById('btFinalErrorDollar').textContent = `Diferencia: $${m.final_error_dollar.toFixed(2)}`;

  document.getElementById('tabErrBadge').textContent = `Error: ${Math.abs(m.final_error_pct).toFixed(1)}%`;

  document.getElementById('btMapeVal').textContent = `MAPE: ${m.mape.toFixed(2)}%`;
  document.getElementById('btRmseVal').textContent = `RMSE: $${m.rmse.toFixed(2)} | TE: ${m.tracking_error_annual_pct.toFixed(2)}%`;

  document.getElementById('btCoverageBadge').textContent = `Cobertura IC 95%: ${m.ci_coverage_pct.toFixed(1)}%`;
  document.getElementById('btDirectionBadge').textContent = `Acierto de Dirección: ${m.directional_hit ? 'CORRECTO ✓' : 'DESVIADO ✗'}`;
  document.getElementById('btDirectionBadge').className = m.directional_hit ? 'badge badge-bullish' : 'badge badge-bearish';

  // Render Backtest Chart
  renderBacktestChart(bt.chart_data);

  // Daily Trajectory Audit Table
  const tableBody = document.getElementById('backtestDailyTable');
  tableBody.innerHTML = '';
  
  const dates = bt.chart_data.dates;
  const actuals = bt.chart_data.actual_prices;
  const preds = bt.chart_data.pred_prices;
  const ciUp = bt.chart_data.ci_upper;
  const ciLow = bt.chart_data.ci_lower;
  const cutoffIdx = bt.chart_data.cutoff_index;

  for (let i = cutoffIdx + 1; i < dates.length; i++) {
    const act = actuals[i];
    const prd = preds[i];
    const diff = prd - act;
    const diffPct = (diff / act) * 100.0;
    
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="mono">${dates[i]}</td>
      <td class="numeric mono">$${act.toFixed(2)}</td>
      <td class="numeric mono" style="color: #10b981; font-weight: 600;">$${prd.toFixed(2)}</td>
      <td class="numeric mono" style="color: ${diff >= 0 ? '#10b981' : '#f43f5e'};">$${diff.toFixed(2)}</td>
      <td class="numeric mono" style="color: ${Math.abs(diffPct) < 5 ? '#10b981' : '#f59e0b'}; font-weight: 600;">
        ${diffPct >= 0 ? '+' : ''}${diffPct.toFixed(2)}%
      </td>
      <td class="numeric mono">$${ciLow[i].toFixed(2)}</td>
      <td class="numeric mono">$${ciUp[i].toFixed(2)}</td>
    `;
    tableBody.appendChild(tr);
  }
}

async function loadFactorsMetadata() {
  try {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.get_factors_info) {
      const info = await window.pywebview.api.get_factors_info();
      document.getElementById('ffLatestDate').textContent = info.latest_date || 'Sincronizado';
      document.getElementById('ffObsCount').textContent = info.observations ? `${info.observations.toLocaleString()} días` : '--';
      document.getElementById('ffCacheStatus').textContent = info.is_cached ? 'Caché Local Activa' : 'Descargando...';
    }
  } catch (e) {
    console.error('Error fetching factor metadata:', e);
  }
}

async function refreshFactorsData() {
  showLoader('Actualizando Factores Oficiales', 'Conectando con Dartmouth College (Kenneth French Library)...');
  try {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.refresh_factors) {
      await window.pywebview.api.refresh_factors();
      await loadFactorsMetadata();
      await runAnalysis();
    }
  } catch (e) {
    alert(`Error actualizando factores: ${e.message || e}`);
  } finally {
    hideLoader();
  }
}

// ================= S&P 500 SECTORS LOGIC =================
let currentSectorId = 'tech';
let currentSectorData = null;

async function onSectorDropdownChange(sectorId) {
  if (!sectorId) return;
  currentSectorId = sectorId;
  
  // Switch to Sector tab
  const btn = document.getElementById('btnSectorsTab');
  switchTab('sectorsTab', btn);
  
  await loadSector(sectorId);
}

async function reloadCurrentSector() {
  await loadSector(currentSectorId);
}

async function loadSector(sectorId) {
  const model = document.getElementById('modelSelect').value;
  const period = document.getElementById('periodSelect').value;
  
  showLoader(`Cargando Sector S&P 500`, `Descargando cotizaciones y calculando Fama-French para el sector...`);

  try {
    let result = null;
    if (window.pywebview && window.pywebview.api && window.pywebview.api.analyze_sector) {
      result = await window.pywebview.api.analyze_sector(sectorId, model, period);
    } else {
      hideLoader();
      return;
    }

    if (result.error) {
      alert(`Error analizando sector: ${result.error}`);
      hideLoader();
      return;
    }

    currentSectorData = result;
    renderSectorResults(result);
  } catch (err) {
    console.error('Error loading sector:', err);
    alert(`Error de sector: ${err.message || err}`);
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
}

function renderSectorTableRows(stocks) {
  const tbody = document.getElementById('sectorStocksTableBody');
  tbody.innerHTML = '';

  stocks.forEach(st => {
    const d = st.decision;
    const badgeClass = d.color === 'bullish' ? 'badge-bullish' : (d.color === 'bearish' ? 'badge-bearish' : 'badge-neutral');
    
    const tr = document.createElement('tr');
    tr.dataset.symbol = st.symbol.toLowerCase();
    tr.dataset.name = st.name.toLowerCase();

    tr.innerHTML = `
      <td class="mono" style="font-weight: 700; color: #fff;">
        <span style="color: var(--accent-cyan);">${st.symbol}</span>
      </td>
      <td style="font-weight: 600; color: var(--text-main);">${st.name}</td>
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
          <div><span class="badge ${badgeClass}">${d.badge}</span></div>
          <div style="font-size: 10px; color: var(--text-dim); line-height: 1.3;">${d.reason}</div>
        </div>
      </td>
      <td style="text-align: center;">
        <button class="table-inspect-btn" onclick="inspectStockFromSector('${st.symbol}')" title="Analizar a fondo en terminal">
          <span>Ver ↗</span>
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function filterSectorTable(query) {
  const q = (query || '').trim().toLowerCase();
  const rows = document.querySelectorAll('#sectorStocksTableBody tr');
  rows.forEach(r => {
    const sym = r.dataset.symbol || '';
    const name = r.dataset.name || '';
    const match = sym.includes(q) || name.includes(q);
    r.style.display = match ? '' : 'none';
  });
}

function inspectStockFromSector(symbol) {
  document.getElementById('tickerInput').value = symbol;
  // Switch to valuation tab
  const tabBtn = document.querySelector('.tabs-bar .tab-btn:first-child');
  switchTab('valuationTab', tabBtn);
  runAnalysis();
}

