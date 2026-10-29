// Web Browser Adapter for BSM Terminal Cloud Environment
// Bridges window.pywebview.api calls directly to FastAPI HTTP endpoints
// Includes Zero-Latency Client-Side Black-Scholes-Merton & Black-76 Pricing Engine
(function() {
    const INV_SQRT_2PI = 1.0 / Math.sqrt(2.0 * Math.PI);
    const INV_SQRT_2 = 1.0 / Math.sqrt(2.0);
    const EPS = 1e-7;

    function erf(x) {
        const sign = x >= 0 ? 1 : -1;
        const ax = Math.abs(x);
        const t = 1.0 / (1.0 + 0.3275911 * ax);
        const y = 1.0 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-ax * ax);
        return sign * y;
    }

    function ndtr(x) {
        return 0.5 * (1.0 + erf(x * INV_SQRT_2));
    }

    function pdf(x) {
        return Math.exp(-0.5 * x * x) * INV_SQRT_2PI;
    }

    function roundN(val, dec) {
        const f = Math.pow(10, dec);
        return Math.round(val * f) / f;
    }

    function priceSingle(S, K, T, r, sigma, q, isCall) {
        if (T <= EPS) {
            return Math.max(0.0, isCall ? (S - K) : (K - S));
        }
        const discQ = Math.exp(-q * T);
        const discR = Math.exp(-r * T);
        if (sigma <= EPS) {
            const fwd = S * discQ - K * discR;
            return Math.max(0.0, isCall ? fwd : -fwd);
        }
        const sqrtT = Math.sqrt(T);
        const d1 = (Math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / (sigma * sqrtT);
        const d2 = d1 - sigma * sqrtT;
        const p = isCall
            ? (S * discQ * ndtr(d1) - K * discR * ndtr(d2))
            : (K * discR * ndtr(-d2) - S * discQ * ndtr(-d1));
        return Math.max(0.0, p);
    }

    function calcGreeks(S, K, T, r, sigma, q, model, isCall) {
        const useBlack76 = model === 'black76';
        if (T <= EPS || sigma <= EPS) {
            const intrinsic = isCall ? (S - K) : (K - S);
            const itm = intrinsic > 0;
            return {
                delta: (isCall && itm) ? 1.0 : ((!isCall && itm) ? -1.0 : 0.0),
                gamma: 0.0, vega: 0.0, theta: 0.0, rho: 0.0, d1: 0.0, d2: 0.0
            };
        }
        const qEff = useBlack76 ? r : q;
        const sqrtT = Math.sqrt(T);
        const d1 = (Math.log(S / K) + (r - qEff + 0.5 * sigma * sigma) * T) / (sigma * sqrtT);
        const d2 = d1 - sigma * sqrtT;
        const discR = Math.exp(-r * T);
        const discQ = Math.exp(-qEff * T);
        const pdfD1 = pdf(d1);
        const nD1 = ndtr(d1), nD2 = ndtr(d2);
        const nMD1 = 1.0 - nD1, nMD2 = 1.0 - nD2;

        const delta = isCall ? (discQ * nD1) : (-discQ * nMD1);
        const gamma = (discQ * pdfD1) / (S * sigma * sqrtT);
        const vegaTotal = S * discQ * pdfD1 * sqrtT;

        const term1 = -(S * discQ * pdfD1 * sigma) / (2.0 * sqrtT);
        const thetaAnnual = isCall
            ? (term1 - r * K * discR * nD2 + qEff * S * discQ * nD1)
            : (term1 + r * K * discR * nMD2 - qEff * S * discQ * nMD1);

        let rhoAnnual;
        if (useBlack76) {
            const price = isCall
                ? (S * discQ * nD1 - K * discR * nD2)
                : (K * discR * nMD2 - S * discQ * nMD1);
            rhoAnnual = -T * price;
        } else {
            rhoAnnual = isCall ? (K * T * discR * nD2) : (-K * T * discR * nMD2);
        }

        return {
            delta: delta,
            gamma: gamma,
            vega: vegaTotal / 100.0,
            theta: thetaAnnual / 365.0,
            rho: rhoAnnual / 100.0,
            d1: d1,
            d2: d2
        };
    }

    function calcImpliedVol(marketPrice, S, K, T, r, q, model, isCall) {
        if (marketPrice <= 0.0 || T <= EPS) return null;
        const qEff = model === 'black76' ? r : q;
        const discR = Math.exp(-r * T);
        const discQ = Math.exp(-qEff * T);
        const fwd = S * discQ - K * discR;
        const intrinsic = Math.max(0.0, isCall ? fwd : -fwd);
        if (marketPrice < intrinsic - 1e-4) return null;

        const obj = (sig) => priceSingle(S, K, T, r, sig, qEff, isCall) - marketPrice;
        let sigma = 0.25;
        const sqrtT = Math.sqrt(T);
        for (let i = 0; i < 60; i++) {
            const diff = obj(sigma);
            if (Math.abs(diff) < 1e-5) return sigma;
            const d1 = (Math.log(S / K) + (r - qEff + 0.5 * sigma * sigma) * T) / (sigma * sqrtT);
            const vega = S * discQ * pdf(d1) * sqrtT;
            if (Math.abs(vega) < 1e-6) break;
            sigma -= diff / vega;
            if (sigma <= 0.001 || sigma > 8.0) break;
        }
        let low = 0.001, high = 5.0;
        let fLow = obj(low), fHigh = obj(high);
        if (fLow * fHigh < 0) {
            for (let i = 0; i < 45; i++) {
                const mid = 0.5 * (low + high);
                const fMid = obj(mid);
                if (Math.abs(fMid) < 1e-5 || (high - low) < 1e-5) return mid;
                if (fLow * fMid < 0) {
                    high = mid; fHigh = fMid;
                } else {
                    low = mid; fLow = fMid;
                }
            }
            return 0.5 * (low + high);
        }
        return null;
    }

    function evalFairPremium(marketPrice, theoPrice, iv, hv, isCall, d2, S, K) {
        const intrinsicVal = Math.max(0.0, isCall ? (S - K) : (K - S));
        const timeVal = Math.max(0.0, theoPrice - intrinsicVal);
        const probItm = (isCall ? ndtr(d2) : ndtr(-d2)) * 100.0;
        const hasMarket = marketPrice !== null && marketPrice !== undefined && marketPrice > 0.001;
        const mktP = hasMarket ? Number(marketPrice) : theoPrice;
        const diff = mktP - theoPrice;
        const diffPct = theoPrice > 0.001 ? (diff / theoPrice * 100.0) : 0.0;

        let valuationStatus, statusColor;
        if (!hasMarket) {
            valuationStatus = 'Prima Justa Teórica';
            statusColor = '#38BDF8';
        } else if (Math.abs(diffPct) <= 2.5) {
            valuationStatus = 'En Paridad con el Mercado (±2.5%)';
            statusColor = '#38BDF8';
        } else if (diff > 0) {
            valuationStatus = `Prima de Mercado Sobre la Par (+${Math.abs(diffPct).toFixed(1)}%)`;
            statusColor = '#F59E0B';
        } else {
            valuationStatus = `Prima de Mercado Bajo la Par (-${Math.abs(diffPct).toFixed(1)}%)`;
            statusColor = '#10B981';
        }

        const volSpread = iv !== null ? (iv - hv) : 0.0;
        const details = [
            `Prima Justa Calculada: $${theoPrice.toFixed(4)} (Intrínseco: $${intrinsicVal.toFixed(2)} | Valor Tiempo: $${timeVal.toFixed(2)}).`,
            `Probabilidad de Ejercicio a Vencimiento (ITM): ${probItm.toFixed(1)}%.`
        ];
        if (hasMarket) {
            const signDiff = diff >= 0 ? '+' : '';
            const signPct = diffPct >= 0 ? '+' : '';
            details.push(`Cotización Observada en Mercado: $${mktP.toFixed(2)} (Diferencia: ${signDiff}${diff.toFixed(2)} / ${signPct}${diffPct.toFixed(1)}%).`);
            if (iv !== null) {
                const signSpread = volSpread >= 0 ? '+' : '';
                details.push(`Volatilidad Implícita (IV): ${(iv * 100).toFixed(1)}% vs Histórica (HV): ${(hv * 100).toFixed(1)}% (Spread: ${signSpread}${(volSpread * 100).toFixed(1)}%).`);
            }
        }

        return {
            theoretical_price: roundN(theoPrice, 4),
            market_price: roundN(mktP, 4),
            has_market_price: Boolean(hasMarket),
            intrinsic_value: roundN(intrinsicVal, 4),
            time_value: roundN(timeVal, 4),
            diff_amount: roundN(diff, 4),
            diff_pct: roundN(diffPct, 2),
            valuation_status: valuationStatus,
            status_color: statusColor,
            prob_itm_pct: roundN(probItm, 1),
            vol_spread_pct: roundN(volSpread * 100, 2),
            details: details
        };
    }

    function calculateSingleOptionClient(params) {
        const S = Number(params.underlying_price ?? 100.0);
        const K = Number(params.strike ?? 100.0);
        const days = Number(params.days_to_expiry ?? 30.0);
        const T = Math.max(1e-5, days / 365.0);
        const r = Number(params.risk_free_rate ?? 4.0) / 100.0;
        const sigma = Number(params.volatility ?? 20.0) / 100.0;
        const q = Number(params.dividend_yield ?? 0.0) / 100.0;
        const model = String(params.model ?? 'black76').toLowerCase();
        const optionType = String(params.option_type ?? 'call').toLowerCase();
        const qEff = model === 'black76' ? r : q;

        let callMkt = params.call_market_price;
        if ((callMkt === null || callMkt === undefined) && optionType === 'call') {
            callMkt = params.market_price ?? 0.0;
        }
        callMkt = callMkt !== null && callMkt !== undefined ? Number(callMkt) : 0.0;

        let putMkt = params.put_market_price;
        if ((putMkt === null || putMkt === undefined) && optionType === 'put') {
            putMkt = params.market_price ?? 0.0;
        }
        putMkt = putMkt !== null && putMkt !== undefined ? Number(putMkt) : 0.0;

        const callTheo = priceSingle(S, K, T, r, sigma, qEff, true);
        const putTheo = priceSingle(S, K, T, r, sigma, qEff, false);
        const callGreeks = calcGreeks(S, K, T, r, sigma, q, model, true);
        const putGreeks = calcGreeks(S, K, T, r, sigma, q, model, false);

        const callIv = callMkt > 0.001 ? calcImpliedVol(callMkt, S, K, T, r, q, model, true) : null;
        const putIv = putMkt > 0.001 ? calcImpliedVol(putMkt, S, K, T, r, q, model, false) : null;

        const callEval = evalFairPremium(callMkt, callTheo, callIv, sigma, true, callGreeks.d2, S, K);
        const putEval = evalFairPremium(putMkt, putTheo, putIv, sigma, false, putGreeks.d2, S, K);

        const parityTarget = model === 'black76'
            ? (Math.exp(-r * T) * (S - K))
            : (S * Math.exp(-q * T) - K * Math.exp(-r * T));
        const parityObserved = callTheo - putTheo;
        const parityDiff = Math.abs(parityObserved - parityTarget);

        const callEffMkt = callMkt > 0.001 ? callMkt : callTheo;
        const putEffMkt = putMkt > 0.001 ? putMkt : putTheo;
        const callBe = K + callEffMkt;
        const putBe = Math.max(0.0, K - putEffMkt);

        const sMin = S * 0.70, sMax = S * 1.30;
        const spots = [], callExpiryPnl = [], putExpiryPnl = [], callTodayVal = [], putTodayVal = [];
        for (let i = 0; i < 45; i++) {
            const spot = sMin + (sMax - sMin) * (i / 44.0);
            spots.push(roundN(spot, 2));
            callExpiryPnl.push(roundN(Math.max(0.0, spot - K) - callEffMkt, 2));
            putExpiryPnl.push(roundN(Math.max(0.0, K - spot) - putEffMkt, 2));
            callTodayVal.push(roundN(priceSingle(spot, K, T, r, sigma, qEff, true) - callEffMkt, 2));
            putTodayVal.push(roundN(priceSingle(spot, K, T, r, sigma, qEff, false) - putEffMkt, 2));
        }

        const activeIsCall = optionType === 'call';
        const activeTheo = activeIsCall ? callTheo : putTheo;
        const activeMkt = activeIsCall ? callEffMkt : putEffMkt;
        const activeEval = activeIsCall ? callEval : putEval;
        const activeGreeks = activeIsCall ? callGreeks : putGreeks;
        const activeBe = activeIsCall ? callBe : putBe;

        return {
            status: 'success',
            data: {
                inputs: {
                    underlying_price: S,
                    strike: K,
                    days_to_expiry: days,
                    T: roundN(T, 6),
                    risk_free_rate_pct: r * 100.0,
                    volatility_pct: sigma * 100.0,
                    dividend_yield_pct: q * 100.0,
                    model: model
                },
                call: {
                    fair_premium: roundN(callTheo, 4),
                    market_price: roundN(callEffMkt, 4),
                    has_market_price: callEval.has_market_price,
                    intrinsic_value: callEval.intrinsic_value,
                    time_value: callEval.time_value,
                    diff_amount: callEval.diff_amount,
                    diff_pct: callEval.diff_pct,
                    valuation_status: callEval.valuation_status,
                    status_color: callEval.status_color,
                    implied_volatility_pct: callIv !== null ? roundN(callIv * 100.0, 2) : null,
                    break_even: roundN(callBe, 2),
                    prob_itm_pct: callEval.prob_itm_pct,
                    greeks: callGreeks,
                    details: callEval.details
                },
                put: {
                    fair_premium: roundN(putTheo, 4),
                    market_price: roundN(putEffMkt, 4),
                    has_market_price: putEval.has_market_price,
                    intrinsic_value: putEval.intrinsic_value,
                    time_value: putEval.time_value,
                    diff_amount: putEval.diff_amount,
                    diff_pct: putEval.diff_pct,
                    valuation_status: putEval.valuation_status,
                    status_color: putEval.status_color,
                    implied_volatility_pct: putIv !== null ? roundN(putIv * 100.0, 2) : null,
                    break_even: roundN(putBe, 2),
                    prob_itm_pct: putEval.prob_itm_pct,
                    greeks: putGreeks,
                    details: putEval.details
                },
                put_call_parity: {
                    observed_diff: roundN(parityObserved, 4),
                    target_diff: roundN(parityTarget, 4),
                    discrepancy: roundN(parityDiff, 6),
                    is_satisfied: Boolean(parityDiff < 1e-4)
                },
                theoretical_price: roundN(activeTheo, 4),
                market_price: roundN(activeMkt, 4),
                model_used: model === 'black76' ? 'Black-76 (Futuros Oficial)' : 'Black-Scholes-Merton (Carry)',
                break_even: roundN(activeBe, 2),
                greeks: activeGreeks,
                fair_evaluation: activeEval,
                recommendation: {
                    action: activeEval.valuation_status,
                    signal_strength: 'PARIDAD TEÓRICA',
                    color: activeEval.status_color,
                    edge_pct: activeEval.diff_pct,
                    theoretical_price: roundN(activeTheo, 4),
                    market_price: roundN(activeMkt, 4),
                    prob_itm_pct: activeEval.prob_itm_pct,
                    vol_spread_pct: activeEval.vol_spread_pct,
                    rationale: activeEval.details
                },
                payoff_curve: {
                    spots: spots,
                    call_expiry_pnl: callExpiryPnl,
                    call_today_val: callTodayVal,
                    put_expiry_pnl: putExpiryPnl,
                    put_today_val: putTodayVal,
                    expiry_pnl: activeIsCall ? callExpiryPnl : putExpiryPnl,
                    today_pnl: activeIsCall ? callTodayVal : putTodayVal
                }
            }
        };
    }

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
                    try {
                        return calculateSingleOptionClient(params || {});
                    } catch (_e) {
                        const res = await fetch('/api/bsm/calculate_single_option', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ params: params })
                        });
                        return await res.json();
                    }
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

