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
        Calcula una opcion especifica: precio teorico, griegas completas,
        volatilidad implicita, curva de P&L al vencimiento y recomendacion.
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
            market_price = float(params.get("market_price", 0.0))

            # Precio teorico
            if model == "black76":
                theo_price = QuantEngine.black76_price(S_or_F, K, T, r, sigma, option_type)
            else:
                theo_price = QuantEngine.bsm_price(S_or_F, K, T, r, sigma, q, option_type)

            # Griegas
            greeks = QuantEngine.calculate_greeks(S_or_F, K, T, r, sigma, q, model, option_type)

            # Volatilidad Implicita si se provee precio de mercado
            iv = None
            if market_price > 0.001:
                iv = QuantEngine.calculate_implied_volatility(
                    market_price=market_price,
                    S_or_F=S_or_F,
                    K=K,
                    T=T,
                    r=r,
                    q=q,
                    model=model,
                    option_type=option_type
                )

            # Recomendacion cuantitativa
            eff_market_price = market_price if market_price > 0.001 else theo_price
            rec = QuantEngine.generate_recommendation(
                market_price=eff_market_price,
                theoretical_price=theo_price,
                iv=iv,
                hv=sigma,
                option_type=option_type,
                delta=greeks["delta"],
                d2=greeks["d2"]
            )

            # Curva de Payoff y P&L
            is_call = option_type == "call"
            s_min = S_or_F * 0.70
            s_max = S_or_F * 1.30
            spot_steps = np.linspace(s_min, s_max, 45)
            payoff_at_expiry = []
            theo_value_today = []

            for s_val in spot_steps:
                # Payoff neto de la prima comprada
                intrinsic = max(0.0, (s_val - K) if is_call else (K - s_val))
                pnl = intrinsic - eff_market_price
                payoff_at_expiry.append(round(float(pnl), 2))

                # Valor hoy con el nuevo spot
                if model == "black76":
                    v_today = QuantEngine.black76_price(s_val, K, T, r, sigma, option_type) - eff_market_price
                else:
                    v_today = QuantEngine.bsm_price(s_val, K, T, r, sigma, q, option_type) - eff_market_price
                theo_value_today.append(round(float(v_today), 2))

            # Break-even
            if is_call:
                break_even = K + eff_market_price
            else:
                break_even = max(0.0, K - eff_market_price)

            return {
                "status": "success",
                "data": {
                    "theoretical_price": round(theo_price, 4),
                    "market_price": round(eff_market_price, 4),
                    "implied_volatility_pct": round(iv * 100.0, 2) if iv else None,
                    "model_used": "Black-76 (Futuros)" if model == "black76" else "Black-Scholes-Merton (Carry)",
                    "break_even": round(break_even, 2),
                    "greeks": greeks,
                    "recommendation": rec,
                    "payoff_curve": {
                        "spots": [round(float(s), 2) for s in spot_steps],
                        "expiry_pnl": payoff_at_expiry,
                        "today_pnl": theo_value_today
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
