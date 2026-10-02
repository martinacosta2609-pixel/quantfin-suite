import numpy as np
import pandas as pd
from typing import Dict, Any, List
from core.econometrics import EconometricDiagnostics

FACTOR_CONFIGS = {
    "FF3": {
        "name": "Fama-French 3 Factores (1993)",
        "factors": ["Mkt-RF", "SMB", "HML"],
        "descriptions": {
            "Mkt-RF": "Exceso de Retorno de Mercado sobre tasa libre de riesgo (Riesgo Sistemático)",
            "SMB": "Small Minus Big: Prima por tamaño (pequeña capitalización vs gran capitalización)",
            "HML": "High Minus Low: Prima por valor (alta relación valor libros/mercado vs acciones de crecimiento)"
        }
    },
    "FF5": {
        "name": "Fama-French 5 Factores (2015)",
        "factors": ["Mkt-RF", "SMB", "HML", "RMW", "CMA"],
        "descriptions": {
            "Mkt-RF": "Riesgo Sistemático de Mercado (Beta de Mercado)",
            "SMB": "Small Minus Big: Prima por tamaño",
            "HML": "High Minus Low: Prima por valor",
            "RMW": "Robust Minus Weak: Rentabilidad operativa robusta vs débil",
            "CMA": "Conservative Minus Aggressive: Política de inversión conservadora vs agresiva"
        }
    },
    "CARHART4": {
        "name": "Carhart 4 Factores (1997 con Momentum)",
        "factors": ["Mkt-RF", "SMB", "HML", "MOM"],
        "descriptions": {
            "Mkt-RF": "Riesgo Sistemático de Mercado",
            "SMB": "Small Minus Big: Prima por tamaño",
            "HML": "High Minus Low: Prima por valor",
            "MOM": "Momentum: Rendimiento de acciones ganadoras vs perdedoras a 12 meses"
        }
    }
}

class FamaFrenchEngine:
    def __init__(self, model_type: str = "FF5"):
        if model_type not in FACTOR_CONFIGS:
            model_type = "FF5"
        self.model_type = model_type
        self.config = FACTOR_CONFIGS[model_type]
        self.factors = self.config["factors"]

    def set_model_type(self, model_type: str):
        if model_type in FACTOR_CONFIGS:
            self.model_type = model_type
            self.config = FACTOR_CONFIGS[model_type]
            self.factors = self.config["factors"]

    def estimate(self, aligned_df: pd.DataFrame, cov_type: str = "HAC") -> Dict[str, Any]:
        """
        Runs the multi-factor estimation for the stock using aligned data.
        Returns econometric diagnostics, factor betas, expected returns, and cost of equity.
        """
        if aligned_df.empty or len(aligned_df) < 30:
            raise ValueError("Muestra insuficiente para estimación econométrica (mínimo 30 observaciones).")

        y = aligned_df["Stock_Excess_Return"]
        # Ensure selected factors are in dataset
        available_factors = [f for f in self.factors if f in aligned_df.columns]
        if not available_factors:
            raise ValueError("Los factores seleccionados no están disponibles en la serie de datos.")

        X = aligned_df[available_factors]

        # Run OLS with HAC Newey-West standard errors
        hac_lags = min(10, max(3, int(np.floor(4 * (len(aligned_df) / 100) ** (2 / 9)))))
        regression_output = EconometricDiagnostics.run_ols_with_diagnostics(
            y, X, cov_type=cov_type, hac_maxlags=hac_lags
        )

        # Calculate annualized factor statistics and risk premia
        annual_factor_returns = {}
        for f in available_factors:
            mean_daily = float(aligned_df[f].mean())
            std_daily = float(aligned_df[f].std())
            annual_factor_returns[f] = {
                "mean_annual": mean_daily * 252.0,
                "vol_annual": std_daily * np.sqrt(252.0)
            }

        # Daily and Annualized Risk-free rate
        rf_daily_mean = float(aligned_df["RF"].mean())
        rf_annual = rf_daily_mean * 252.0

        # Calculate Expected Return (Cost of Equity: k_e)
        # E[R_i] = Rf + sum(beta_k * E[F_k])
        params_by_name = {p["factor"]: p for p in regression_output["parameters"]}
        alpha_daily = params_by_name.get("const", {}).get("coef", 0.0)
        alpha_annual = (1.0 + alpha_daily) ** 252.0 - 1.0

        factor_contributions = []
        expected_excess_return_annual = 0.0

        for f in available_factors:
            beta = params_by_name.get(f, {}).get("coef", 0.0)
            premium = annual_factor_returns[f]["mean_annual"]
            contrib = beta * premium
            expected_excess_return_annual += contrib

            # Interpretation string
            interp = self._get_beta_interpretation(f, beta)

            factor_contributions.append({
                "factor": f,
                "beta": beta,
                "std_err": params_by_name.get(f, {}).get("std_err", 0.0),
                "t_stat": params_by_name.get(f, {}).get("t_stat", 0.0),
                "p_value": params_by_name.get(f, {}).get("p_value", 1.0),
                "factor_premium_annual": premium,
                "annual_contribution": contrib,
                "interpretation": interp
            })

        # Required Rate of Return / Cost of Equity
        cost_of_equity = rf_annual + expected_excess_return_annual

        # Stock price stats
        current_price = float(aligned_df["Close"].iloc[-1])
        vol_stock_daily = float(aligned_df["Return"].std())
        vol_stock_annual = vol_stock_daily * np.sqrt(252.0)

        return {
            "model_type": self.model_type,
            "model_name": self.config["name"],
            "observations": len(aligned_df),
            "date_start": aligned_df["Date"].min().strftime("%Y-%m-%d"),
            "date_end": aligned_df["Date"].max().strftime("%Y-%m-%d"),
            "current_price": current_price,
            "rf_annual": rf_annual,
            "alpha_daily": alpha_daily,
            "alpha_annual": alpha_annual,
            "alpha_pvalue": params_by_name.get("const", {}).get("p_value", 1.0),
            "expected_excess_return_annual": expected_excess_return_annual,
            "cost_of_equity": cost_of_equity,
            "stock_annual_volatility": vol_stock_annual,
            "factor_contributions": factor_contributions,
            "econometrics": regression_output
        }

    def _get_beta_interpretation(self, factor: str, beta: float) -> str:
        if factor == "Mkt-RF":
            if beta > 1.2:
                return "Alta sensibilidad al mercado (Cíclica / Agresiva, beta > 1.2)"
            elif beta < 0.8:
                return "Baja sensibilidad al mercado (Defensiva, beta < 0.8)"
            else:
                return "Sensibilidad neutra cercana al mercado (~1.0)"
        elif factor == "SMB":
            if beta > 0.2:
                return "Sesgo hacia pequeña/mediana capitalización (Small Cap tilt)"
            elif beta < -0.2:
                return "Sesgo hacia mega/gran capitalización (Large Cap tilt)"
            else:
                return "Sin sesgo marcado de capitalización"
        elif factor == "HML":
            if beta > 0.2:
                return "Sesgo hacia acciones de Valor (Value tilt, alto B/M)"
            elif beta < -0.2:
                return "Sesgo hacia acciones de Crecimiento (Growth tilt, bajo B/M)"
            else:
                return "Estilo neutro entre Valor y Crecimiento"
        elif factor == "RMW":
            if beta > 0.15:
                return "Alta rentabilidad operativa / Calidad de balance (Robust Profitability)"
            elif beta < -0.15:
                return "Rentabilidad operativa débil o especulativa"
            else:
                return "Rentabilidad operativa media"
        elif factor == "CMA":
            if beta > 0.15:
                return "Inversión conservadora y disciplinada en activos"
            elif beta < -0.15:
                return "Inversión agresiva o alta tasa de reinversión en expansión"
            else:
                return "Tasa de reinversión corporativa neutral"
        elif factor == "MOM":
            if beta > 0.15:
                return "Fuerte inercia alcista (Comportamiento de Momentum ganador)"
            elif beta < -0.15:
                return "Bajo o negativo momentum reciente"
            else:
                return "Momentum neutro"
        return "Factor de riesgo sistemático"
