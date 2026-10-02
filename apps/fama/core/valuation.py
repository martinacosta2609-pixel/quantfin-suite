import numpy as np
from typing import Dict, Any

class ValuationEngine:
    @staticmethod
    def compute_valuation(current_price: float, cost_of_equity: float, alpha_annual: float, 
                          alpha_pvalue: float, residual_std_error: float, 
                          stock_info: dict = None) -> Dict[str, Any]:
        """
        Calculates theoretical stock valuation, implied price targets, confidence intervals,
        and dividend/earnings capitalization using Fama-French cost of equity.
        """
        if current_price <= 0:
            current_price = 100.0

        # Annualized residual volatility
        annual_resid_vol = residual_std_error * np.sqrt(252.0)

        # 1. Forward Projected Prices (1M, 3M, 6M, 1Y, 2Y)
        horizons = [
            {"label": "1 Mes (21 días)", "months": 1, "t_years": 1/12},
            {"label": "3 Meses (63 días)", "months": 3, "t_years": 3/12},
            {"label": "6 Meses (126 días)", "months": 6, "t_years": 6/12},
            {"label": "1 Año (252 días)", "months": 12, "t_years": 1.0},
            {"label": "2 Años (504 días)", "months": 24, "t_years": 2.0},
        ]

        projections = []
        for h in horizons:
            t = h["t_years"]
            # Expected price using compound expected return
            expected_price = current_price * ((1.0 + cost_of_equity) ** t)
            
            # 95% Confidence Interval (1.96 standard deviations)
            margin = 1.96 * annual_resid_vol * np.sqrt(t) * current_price
            ci_lower = max(0.01, expected_price - margin)
            ci_upper = expected_price + margin
            expected_return_pct = ((expected_price - current_price) / current_price) * 100.0

            projections.append({
                "label": h["label"],
                "months": h["months"],
                "expected_price": float(expected_price),
                "ci_lower": float(ci_lower),
                "ci_upper": float(ci_upper),
                "expected_return_pct": float(expected_return_pct)
            })

        # 1-Year Target Details
        target_1y = projections[3]  # 12 months

        # 2. Alpha & Mispricing Assessment
        # If alpha > 0 significantly, the stock yields excess return beyond factor risk premia
        is_alpha_significant = alpha_pvalue < 0.05
        
        valuation_status = "En Precio Justo (Equilibrio de Factores)"
        status_color = "neutral"
        if is_alpha_significant:
            if alpha_annual > 0.03:
                valuation_status = "Subvaluada (Genera Alpha Anual Positivo Significativo)"
                status_color = "bullish"
            elif alpha_annual < -0.03:
                valuation_status = "Sobrevaluada (Retorno Inferior al Riesgo Sistemático de Factores)"
                status_color = "bearish"

        # 3. Dividend Capitalization (Gordon Growth Model) if dividends exist
        dividend_yield = 0.0
        gordon_value = None
        if stock_info:
            dividend_yield = stock_info.get("dividendYield") or 0.0
            if dividend_yield > 0.005:
                # Sustainable long-term growth rate assumed at 2.5% (approx inflation / GDP)
                g = 0.025
                d0 = current_price * dividend_yield
                d1 = d0 * (1.0 + g)
                if cost_of_equity > g:
                    gordon_value = d1 / (cost_of_equity - g)

        return {
            "current_price": float(current_price),
            "cost_of_equity_annual": float(cost_of_equity),
            "cost_of_equity_pct": float(cost_of_equity * 100.0),
            "alpha_annual_pct": float(alpha_annual * 100.0),
            "alpha_pvalue": float(alpha_pvalue),
            "is_alpha_significant": is_alpha_significant,
            "valuation_status": valuation_status,
            "status_color": status_color,
            "target_1y_price": float(target_1y["expected_price"]),
            "target_1y_lower": float(target_1y["ci_lower"]),
            "target_1y_upper": float(target_1y["ci_upper"]),
            "target_1y_return_pct": float(target_1y["expected_return_pct"]),
            "gordon_intrinsic_value": float(gordon_value) if gordon_value else None,
            "projections": projections
        }
