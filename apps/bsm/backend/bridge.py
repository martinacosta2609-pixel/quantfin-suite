"""
BRIDGE MODULE - Python to PyWebView JavaScript API Interface
Expone funciones cuanticas y econometricas al frontend con serializacion JSON transparente.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional
from backend.quant_engine import QuantEngine
from backend.market_data import MarketDataProvider
from backend.econometrics import EconometricValidator


class ApiBridge:
    def __init__(self):
        self.market_provider = MarketDataProvider()

    def get_commodities(self) -> Dict[str, Any]:
        """Devuelve el catalogo oficial de commodities categorizados."""
        return {
            "status": "success",
            "data": self.market_provider.get_catalog()
        }

    def get_quote(self, comm_id: str) -> Dict[str, Any]:
        """Obtiene la cotizacion oficial del commodity y metricas de volatilidad."""
        quote = self.market_provider.get_live_quote(comm_id)
        return {
            "status": "success",
            "data": quote
        }

    def get_options_chain(self, comm_id: str, expiry: Optional[str] = None) -> Dict[str, Any]:
        """Obtiene la cadena completa de opciones en vivo para el vencimiento solicitado."""
        chain = self.market_provider.get_options_chain_data(comm_id, expiry)
        return {
            "status": "success",
            "data": chain
        }

    def calculate_single_option(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calcula las primas justas teoricas tanto de CALL como de PUT de manera simultanea,
        junto con sus Griegas analiticas, descomposicion de valor intrinseco/temporal,
        comparativa contra precios de mercado (si estan disponibles) y paridad Put-Call.
        """
        try:
            S_or_F = float(params.get("underlying_price", 100.0))
            K = float(params.get("strike", 100.0))
            days = float(params.get("days_to_expiry", 30.0))
            T = max(1e-5, days / 365.0)
            r = float(params.get("risk_free_rate", 4.0)) / 100.0
            sigma = float(params.get("volatility", 20.0)) / 100.0
            q = float(params.get("dividend_yield", 0.0)) / 100.0
            model = str(params.get("model", "black76")).lower()
            option_type = str(params.get("option_type", "call")).lower()

            call_market_price = params.get("call_market_price")
            if call_market_price is None and option_type == "call":
                call_market_price = params.get("market_price", 0.0)
            call_market_price = float(call_market_price) if call_market_price is not None else 0.0

            put_market_price = params.get("put_market_price")
            if put_market_price is None and option_type == "put":
                put_market_price = params.get("market_price", 0.0)
            put_market_price = float(put_market_price) if put_market_price is not None else 0.0

            # 1. Calculo de Prima Justa Teórica (Call y Put)
            if model == "black76":
                call_theo = QuantEngine.black76_price(S_or_F, K, T, r, sigma, "call")
                put_theo = QuantEngine.black76_price(S_or_F, K, T, r, sigma, "put")
            else:
                call_theo = QuantEngine.bsm_price(S_or_F, K, T, r, sigma, q, "call")
                put_theo = QuantEngine.bsm_price(S_or_F, K, T, r, sigma, q, "put")

            # 2. Griegas Analíticas completas para Call y Put
            call_greeks = QuantEngine.calculate_greeks(S_or_F, K, T, r, sigma, q, model, "call")
            put_greeks = QuantEngine.calculate_greeks(S_or_F, K, T, r, sigma, q, model, "put")

            # 3. Volatilidad Implicita (si hay cotizaciones de mercado)
            call_iv = None
            if call_market_price > 0.001:
                call_iv = QuantEngine.calculate_implied_volatility(
                    market_price=call_market_price, S_or_F=S_or_F, K=K, T=T, r=r, q=q, model=model, option_type="call"
                )

            put_iv = None
            if put_market_price > 0.001:
                put_iv = QuantEngine.calculate_implied_volatility(
                    market_price=put_market_price, S_or_F=S_or_F, K=K, T=T, r=r, q=q, model=model, option_type="put"
                )

            # 4. Evaluación de Prima Justa (sin recomendaciones de compra/venta)
            call_eval = QuantEngine.evaluate_fair_premium(
                market_price=call_market_price,
                theoretical_price=call_theo,
                iv=call_iv,
                hv=sigma,
                option_type="call",
                delta=call_greeks["delta"],
                d2=call_greeks["d2"],
                underlying_price=S_or_F,
                strike=K
            )

            put_eval = QuantEngine.evaluate_fair_premium(
                market_price=put_market_price,
                theoretical_price=put_theo,
                iv=put_iv,
                hv=sigma,
                option_type="put",
                delta=put_greeks["delta"],
                d2=put_greeks["d2"],
                underlying_price=S_or_F,
                strike=K
            )

            # 5. Paridad Put-Call Teórica
            if model == "black76":
                parity_target = float(np.exp(-r * T) * (S_or_F - K))
            else:
                parity_target = float(S_or_F * np.exp(-q * T) - K * np.exp(-r * T))
            parity_observed = call_theo - put_theo
            parity_diff = abs(parity_observed - parity_target)

            # 6. Puntos de Equilibrio (Break-Evens)
            call_eff_mkt = call_market_price if call_market_price > 0.001 else call_theo
            put_eff_mkt = put_market_price if put_market_price > 0.001 else put_theo
            call_break_even = K + call_eff_mkt
            put_break_even = max(0.0, K - put_eff_mkt)

            # 7. Curvas de Payoff y Valor Teórico (para Call y Put)
            s_min = S_or_F * 0.70
            s_max = S_or_F * 1.30
            spot_steps = np.linspace(s_min, s_max, 45)

            # Todo el barrido de precios se valua en una sola pasada vectorizada
            call_expiry_pnl = np.round(np.maximum(0.0, spot_steps - K) - call_eff_mkt, 2).tolist()
            put_expiry_pnl = np.round(np.maximum(0.0, K - spot_steps) - put_eff_mkt, 2).tolist()
            call_today_val = np.round(
                QuantEngine.price_curve(spot_steps, K, T, r, sigma, q, model, "call") - call_eff_mkt, 2
            ).tolist()
            put_today_val = np.round(
                QuantEngine.price_curve(spot_steps, K, T, r, sigma, q, model, "put") - put_eff_mkt, 2
            ).tolist()

            # Referencia activa segun el toggle seleccionado por el usuario
            active_is_call = (option_type == "call")
            active_theo = call_theo if active_is_call else put_theo
            active_mkt = call_eff_mkt if active_is_call else put_eff_mkt
            active_eval = call_eval if active_is_call else put_eval
            active_greeks = call_greeks if active_is_call else put_greeks
            active_be = call_break_even if active_is_call else put_break_even

            return {
                "status": "success",
                "data": {
                    # Parametros efectivamente usados (el frontend los usa para explicar los resultados)
                    "inputs": {
                        "underlying_price": S_or_F,
                        "strike": K,
                        "days_to_expiry": days,
                        "T": round(T, 6),
                        "risk_free_rate_pct": r * 100.0,
                        "volatility_pct": sigma * 100.0,
                        "dividend_yield_pct": q * 100.0,
                        "model": model
                    },
                    # Datos integrales de ambas primas justas
                    "call": {
                        "fair_premium": round(call_theo, 4),
                        "market_price": round(call_eff_mkt, 4),
                        "has_market_price": call_eval["has_market_price"],
                        "intrinsic_value": call_eval["intrinsic_value"],
                        "time_value": call_eval["time_value"],
                        "diff_amount": call_eval["diff_amount"],
                        "diff_pct": call_eval["diff_pct"],
                        "valuation_status": call_eval["valuation_status"],
                        "status_color": call_eval["status_color"],
                        "implied_volatility_pct": round(call_iv * 100.0, 2) if call_iv else None,
                        "break_even": round(call_break_even, 2),
                        "prob_itm_pct": call_eval["prob_itm_pct"],
                        "greeks": call_greeks,
                        "details": call_eval["details"]
                    },
                    "put": {
                        "fair_premium": round(put_theo, 4),
                        "market_price": round(put_eff_mkt, 4),
                        "has_market_price": put_eval["has_market_price"],
                        "intrinsic_value": put_eval["intrinsic_value"],
                        "time_value": put_eval["time_value"],
                        "diff_amount": put_eval["diff_amount"],
                        "diff_pct": put_eval["diff_pct"],
                        "valuation_status": put_eval["valuation_status"],
                        "status_color": put_eval["status_color"],
                        "implied_volatility_pct": round(put_iv * 100.0, 2) if put_iv else None,
                        "break_even": round(put_break_even, 2),
                        "prob_itm_pct": put_eval["prob_itm_pct"],
                        "greeks": put_greeks,
                        "details": put_eval["details"]
                    },
                    "put_call_parity": {
                        "observed_diff": round(float(parity_observed), 4),
                        "target_diff": round(float(parity_target), 4),
                        "discrepancy": round(float(parity_diff), 6),
                        "is_satisfied": bool(parity_diff < 1e-4)
                    },
                    # Campos principales
                    "theoretical_price": round(active_theo, 4),
                    "market_price": round(active_mkt, 4),
                    "model_used": "Black-76 (Futuros Oficial)" if model == "black76" else "Black-Scholes-Merton (Carry)",
                    "break_even": round(active_be, 2),
                    "greeks": active_greeks,
                    "fair_evaluation": active_eval,
                    "recommendation": {
                        "action": active_eval["valuation_status"],
                        "signal_strength": "PARIDAD TEÓRICA",
                        "color": active_eval["status_color"],
                        "edge_pct": active_eval["diff_pct"],
                        "theoretical_price": round(active_theo, 4),
                        "market_price": round(active_mkt, 4),
                        "prob_itm_pct": active_eval["prob_itm_pct"],
                        "vol_spread_pct": active_eval["vol_spread_pct"],
                        "rationale": active_eval["details"]
                    },
                    "payoff_curve": {
                        "spots": [round(float(s), 2) for s in spot_steps],
                        "call_expiry_pnl": call_expiry_pnl,
                        "call_today_val": call_today_val,
                        "put_expiry_pnl": put_expiry_pnl,
                        "put_today_val": put_today_val,
                        "expiry_pnl": call_expiry_pnl if active_is_call else put_expiry_pnl,
                        "today_pnl": call_today_val if active_is_call else put_today_val
                    }
                }
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def run_econometric_backtest(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ejecuta el modulo de testeo econometrico:
        Calcula el valor de la opcion en una fecha pasada con datos anteriores a esa fecha,
        y mide con exactitud el error respecto a los datos reales observados.
        """
        try:
            comm_id = str(params.get("commodity_id", "gold"))
            target_date = str(params.get("target_date", "2026-03-01"))
            option_type = str(params.get("option_type", "call"))
            moneyness = float(params.get("moneyness", 1.0))
            horizon_days = int(params.get("horizon_days", 30))
            window_days = int(params.get("window_days", 90))
            vol_estimator = str(params.get("vol_estimator", "garman_klass"))
            model = str(params.get("model", "black76"))
            r = self.market_provider.get_risk_free_rate()

            hist_df = self.market_provider.get_historical_data(comm_id, period="2y")
            if hist_df.empty:
                return {"status": "error", "message": f"No se pudieron descargar datos historicos para {comm_id}"}

            result = EconometricValidator.run_historical_test(
                history_df=hist_df,
                target_date=target_date,
                option_type=option_type,
                moneyness=moneyness,
                horizon_days=horizon_days,
                window_days=window_days,
                vol_estimator=vol_estimator,
                model=model,
                risk_free_rate=r
            )

            if "error" in result:
                return {"status": "error", "message": result["error"]}

            return {
                "status": "success",
                "data": result
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_historical_series(self, comm_id: str, period: str = "1y") -> Dict[str, Any]:
        """Obtiene la serie historica de precios para graficar en el frontend."""
        try:
            df = self.market_provider.get_historical_data(comm_id, period=period)
            if df.empty:
                return {"status": "error", "message": "Datos no disponibles"}

            dates = [d.strftime("%Y-%m-%d") for d in df.index]
            prices = [round(float(p), 2) for p in df['Close']]
            volumes = [int(v) for v in df.get('Volume', [0] * len(df))]

            return {
                "status": "success",
                "data": {
                    "dates": dates,
                    "prices": prices,
                    "volumes": volumes
                }
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
