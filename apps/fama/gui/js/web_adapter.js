// Web Browser Adapter for FAMA-FRENCH Cloud Environment
// Bridges window.pywebview.api calls directly to FastAPI HTTP endpoints
(function() {
    if (!window.pywebview) {
        window.pywebview = {
            api: {
                get_factors_info: async function() {
                    const res = await fetch('/api/fama/get_factors_info');
                    return await res.json();
                },
                refresh_factors: async function() {
                    const res = await fetch('/api/fama/refresh_factors', { method: 'POST' });
                    return await res.json();
                },
                analyze_stock: async function(ticker, model, period) {
                    const res = await fetch('/api/fama/analyze_stock', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ ticker: ticker, model_type: model, period: period })
                    });
                    return await res.json();
                },
                run_backtest: async function(cutoffDate, trainWindow, testHorizon, model) {
                    const res = await fetch('/api/fama/run_backtest', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            cutoff_date: cutoffDate,
                            train_window_days: trainWindow,
                            test_horizon_days: testHorizon,
                            model_type: model
                        })
                    });
                    return await res.json();
                },
                analyze_sector: async function(sectorId, model, period) {
                    const res = await fetch('/api/fama/analyze_sector', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ sector_id: sectorId, model_type: model, period: period })
                    });
                    return await res.json();
                }
            }
        };

        // Emit pywebviewready event so FAMA's app.js triggers its initialization
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', function() {
                setTimeout(function() {
                    window.dispatchEvent(new Event('pywebviewready'));
                }, 80);
            });
        } else {
            setTimeout(function() {
                window.dispatchEvent(new Event('pywebviewready'));
            }, 80);
        }
    }
})();
