// Web Browser Adapter for BSM Terminal Cloud Environment
// Bridges window.pywebview.api calls directly to FastAPI HTTP endpoints
(function() {
    if (!window.pywebview) {
        window.pywebview = {
            api: {
                get_commodities: async function() {
                    const res = await fetch('/api/bsm/get_commodities');
                    return await res.json();
                },
                get_quote: async function(comm_id) {
                    const res = await fetch('/api/bsm/get_quote', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ comm_id: comm_id })
                    });
                    return await res.json();
                },
                get_options_chain: async function(comm_id, expiry) {
                    const res = await fetch('/api/bsm/get_options_chain', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ comm_id: comm_id, expiry: expiry })
                    });
                    return await res.json();
                },
                calculate_single_option: async function(params) {
                    const res = await fetch('/api/bsm/calculate_single_option', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ params: params })
                    });
                    return await res.json();
                },
                run_econometric_backtest: async function(params) {
                    const res = await fetch('/api/bsm/run_econometric_backtest', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ params: params })
                    });
                    return await res.json();
                },
                get_historical_series: async function(comm_id, period) {
                    const res = await fetch('/api/bsm/get_historical_series', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ comm_id: comm_id, period: period })
                    });
                    return await res.json();
                }
            }
        };

        // Dispatch pywebviewready event so BSM initializes
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

