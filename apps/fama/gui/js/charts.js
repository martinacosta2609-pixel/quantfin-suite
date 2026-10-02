// Institutional Chart Configurations using Chart.js

let priceChartInstance = null;
let residTimeChartInstance = null;
let residHistChartInstance = null;
let backtestChartInstance = null;

// Global Chart Defaults for dark terminal theme
Chart.defaults.color = '#94a3b8';
Chart.defaults.font.family = '"JetBrains Mono", Consolas, monospace';
Chart.defaults.font.size = 11;

function renderPriceTrajectoryChart(dates, actualPrices, projections, currentPrice) {
  const ctx = document.getElementById('priceTrajectoryChart').getContext('2d');
  if (priceChartInstance) {
    priceChartInstance.destroy();
  }

  // Build forward projection points (dates + prices)
  const lastDate = new Date(dates[dates.length - 1]);
  const projDates = [];
  const projExpected = [];
  const projUpper = [];
  const projLower = [];

  // Anchor point at last historical date
  projDates.push(dates[dates.length - 1]);
  projExpected.push(currentPrice);
  projUpper.push(currentPrice);
  projLower.push(currentPrice);

  projections.forEach(p => {
    const d = new Date(lastDate);
    d.setMonth(d.getMonth() + p.months);
    const dateStr = d.toISOString().split('T')[0];
    projDates.push(dateStr);
    projExpected.push(p.expected_price);
    projUpper.push(p.ci_upper);
    projLower.push(p.ci_lower);
  });

  const allLabels = [...dates, ...projDates.slice(1)];
  const histPadded = [...actualPrices, ...new Array(projDates.length - 1).fill(null)];
  
  const projPadded = [...new Array(dates.length - 1).fill(null), ...projExpected];
  const upperPadded = [...new Array(dates.length - 1).fill(null), ...projUpper];
  const lowerPadded = [...new Array(dates.length - 1).fill(null), ...projLower];

  priceChartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: allLabels,
      datasets: [
        {
          label: 'Precio Real de Mercado ($)',
          data: histPadded,
          borderColor: '#3b82f6',
          borderWidth: 2,
          pointRadius: 0,
          fill: false,
          tension: 0.1
        },
        {
          label: 'Proyección Fama-French E[P] ($)',
          data: projPadded,
          borderColor: '#10b981',
          borderWidth: 2,
          borderDash: [5, 4],
          pointRadius: 3,
          pointBackgroundColor: '#10b981',
          fill: false,
          tension: 0.1
        },
        {
          label: 'IC 95% Superior',
          data: upperPadded,
          borderColor: 'rgba(16, 185, 129, 0.25)',
          borderWidth: 1,
          pointRadius: 0,
          fill: false
        },
        {
          label: 'IC 95% Inferior (Cono)',
          data: lowerPadded,
          borderColor: 'rgba(16, 185, 129, 0.25)',
          backgroundColor: 'rgba(16, 185, 129, 0.08)',
          borderWidth: 1,
          pointRadius: 0,
          fill: '-1' // Fill to upper
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index',
        intersect: false
      },
      plugins: {
        legend: {
          position: 'top',
          labels: { boxWidth: 12, padding: 12 }
        },
        tooltip: {
          backgroundColor: '#111622',
          borderColor: 'rgba(255,255,255,0.1)',
          borderWidth: 1,
          callbacks: {
            label: function(context) {
              const val = context.raw;
              if (val === null || val === undefined) return '';
              return `${context.dataset.label}: $${val.toFixed(2)}`;
            }
          }
        }
      },
      scales: {
        x: {
          grid: { color: 'rgba(255, 255, 255, 0.04)' },
          ticks: { maxTicksLimit: 10 }
        },
        y: {
          grid: { color: 'rgba(255, 255, 255, 0.04)' },
          ticks: {
            callback: value => '$' + value.toFixed(0)
          }
        }
      }
    }
  });
}

function renderResidualsCharts(residualsList, histDist) {
  // 1. Time Series Chart
  const ctxTime = document.getElementById('residualsTimeSeriesChart').getContext('2d');
  if (residTimeChartInstance) residTimeChartInstance.destroy();

  const labels = residualsList.map((_, i) => i + 1);
  const stdResid = Math.sqrt(residualsList.reduce((acc, v) => acc + v * v, 0) / residualsList.length);

  residTimeChartInstance = new Chart(ctxTime, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Residuo (εₜ)',
          data: residualsList,
          borderColor: '#06b6d4',
          borderWidth: 1.2,
          pointRadius: 0,
          fill: false
        },
        {
          label: '+2σ Banda',
          data: new Array(labels.length).fill(2 * stdResid),
          borderColor: 'rgba(244, 63, 94, 0.5)',
          borderWidth: 1,
          borderDash: [4, 4],
          pointRadius: 0,
          fill: false
        },
        {
          label: '-2σ Banda',
          data: new Array(labels.length).fill(-2 * stdResid),
          borderColor: 'rgba(244, 63, 94, 0.5)',
          borderWidth: 1,
          borderDash: [4, 4],
          pointRadius: 0,
          fill: false
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'top', labels: { boxWidth: 10 } }
      },
      scales: {
        x: { grid: { display: false }, ticks: { display: false } },
        y: { grid: { color: 'rgba(255, 255, 255, 0.04)' } }
      }
    }
  });

  // 2. Histogram Chart
  const ctxHist = document.getElementById('residualsHistogramChart').getContext('2d');
  if (residHistChartInstance) residHistChartInstance.destroy();

  const binLabels = histDist.bin_centers.map(v => (v * 100).toFixed(2) + '%');

  residHistChartInstance = new Chart(ctxHist, {
    type: 'bar',
    data: {
      labels: binLabels,
      datasets: [
        {
          type: 'bar',
          label: 'Frecuencia Real de Residuos',
          data: histDist.actual_counts,
          backgroundColor: 'rgba(59, 130, 246, 0.4)',
          borderColor: '#3b82f6',
          borderWidth: 1,
          borderRadius: 2
        },
        {
          type: 'line',
          label: 'Distribución Normal Teórica',
          data: histDist.normal_counts,
          borderColor: '#f59e0b',
          borderWidth: 2,
          pointRadius: 0,
          fill: false,
          tension: 0.3
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'top', labels: { boxWidth: 10 } }
      },
      scales: {
        x: { grid: { display: false }, ticks: { maxTicksLimit: 7 } },
        y: { grid: { color: 'rgba(255, 255, 255, 0.04)' } }
      }
    }
  });
}

function renderBacktestChart(chartData) {
  const ctx = document.getElementById('backtestComparisonChart').getContext('2d');
  if (backtestChartInstance) {
    backtestChartInstance.destroy();
  }

  const cutoffIdx = chartData.cutoff_index;

  backtestChartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: chartData.dates,
      datasets: [
        {
          label: 'Precio Real de Mercado ($)',
          data: chartData.actual_prices,
          borderColor: '#3b82f6',
          borderWidth: 2.2,
          pointRadius: 0,
          fill: false,
          tension: 0.05
        },
        {
          label: 'Proyección Fama-French Fuera de Muestra ($)',
          data: chartData.pred_prices,
          borderColor: '#10b981',
          borderWidth: 2,
          borderDash: [5, 3],
          pointRadius: 1,
          pointBackgroundColor: '#10b981',
          fill: false,
          tension: 0.05
        },
        {
          label: 'IC 95% Superior',
          data: chartData.ci_upper,
          borderColor: 'rgba(16, 185, 129, 0.3)',
          borderWidth: 1,
          pointRadius: 0,
          fill: false
        },
        {
          label: 'Cono de Confianza 95%',
          data: chartData.ci_lower,
          borderColor: 'rgba(16, 185, 129, 0.3)',
          backgroundColor: 'rgba(16, 185, 129, 0.08)',
          borderWidth: 1,
          pointRadius: 0,
          fill: '-1'
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index',
        intersect: false
      },
      plugins: {
        legend: {
          position: 'top',
          labels: { boxWidth: 12, padding: 14 }
        },
        tooltip: {
          backgroundColor: '#111622',
          borderColor: 'rgba(255,255,255,0.1)',
          borderWidth: 1,
          callbacks: {
            title: function(items) {
              const idx = items[0].dataIndex;
              const date = items[0].label;
              if (idx === cutoffIdx) {
                return `${date} [FECHA DE CORTE T₀]`;
              } else if (idx < cutoffIdx) {
                return `${date} (Muestra de Entrenamiento Previa)`;
              } else {
                return `${date} (Periodo Fuera de Muestra)`;
              }
            },
            label: function(context) {
              const val = context.raw;
              if (val === null || val === undefined) return '';
              return `${context.dataset.label}: $${val.toFixed(2)}`;
            }
          }
        }
      },
      scales: {
        x: {
          grid: { color: 'rgba(255, 255, 255, 0.04)' },
          ticks: { maxTicksLimit: 12 }
        },
        y: {
          grid: { color: 'rgba(255, 255, 255, 0.04)' },
          ticks: {
            callback: value => '$' + value.toFixed(0)
          }
        }
      }
    }
  });
}
