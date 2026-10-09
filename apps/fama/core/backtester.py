import numpy as np
import pandas as pd
import statsmodels.api as sm
from typing import Dict, Any, List
from core.econometrics import EconometricDiagnostics

class FamaFrenchBacktester:
    @staticmethod
    def run_backtest(aligned_df: pd.DataFrame, 
                     cutoff_date: str, 
                     train_window_days: int = 504, 
                     test_horizon_days: int = 126, 
                     factors: List[str] = None, 
                     cov_type: str = "HAC") -> Dict[str, Any]:
        """
        Executes a historical out-of-sample backtest:
        1. Truncates data strictly prior to cutoff_date (Zero look-ahead bias).
        2. Fits Fama-French model on the training window.
        3. Projects the stock price path forward over the test horizon.
        4. Compares estimated price against the actual verified historical market price.
        5. Computes statistical and econometric estimation errors (MAE, MAPE, RMSE, Tracking Error, % Error).
        """
        if factors is None:
            factors = ["Mkt-RF", "SMB", "HML", "RMW", "CMA"]

        # Filter available factors
        factors = [f for f in factors if f in aligned_df.columns]
        if not factors:
            raise ValueError("Factores no encontrados en la base de datos.")

        df = aligned_df.sort_values("Date").reset_index(drop=True)
        cutoff_dt = pd.to_datetime(cutoff_date)

        # Locate the cutoff index (last trading day <= cutoff_date)
        pre_cutoff_mask = df["Date"] <= cutoff_dt
        if not pre_cutoff_mask.any():
            raise ValueError(f"No hay datos de cotización anteriores a la fecha de corte {cutoff_date}.")

        t0_idx = df[pre_cutoff_mask].index[-1]
        
        # Check sufficient training data
        start_train_idx = max(0, t0_idx - train_window_days)
        train_df = df.iloc[start_train_idx : t0_idx + 1].copy()
        
        if len(train_df) < 30:
            raise ValueError(f"Muestra de entrenamiento insuficiente previa a {cutoff_date} (mínimo 30 días, disponibles: {len(train_df)}).")

        # Check out-of-sample test data
        if t0_idx >= len(df) - 1:
            raise ValueError(f"La fecha de corte {cutoff_date} es la fecha más reciente de los datos. Selecciona una fecha pasada para evaluar contra datos históricos posteriores.")

        end_test_idx = min(len(df), t0_idx + 1 + test_horizon_days)
        test_df = df.iloc[t0_idx + 1 : end_test_idx].copy()
        
        if test_df.empty:
            raise ValueError("No hay días de cotización posteriores al corte para contrastar la estimación.")

        # 1. Fit Model Strictly on Training Window
        y_train = train_df["Stock_Excess_Return"]
        X_train = train_df[factors]
        
        hac_lags = min(10, max(3, int(np.floor(4 * (len(train_df) / 100) ** (2 / 9)))))
        train_reg = EconometricDiagnostics.run_ols_with_diagnostics(
            y_train, X_train, cov_type=cov_type, hac_maxlags=hac_lags
        )

        model_res = train_reg["statsmodels_result"]
        alpha_daily = float(model_res.params.get("const", 0.0))
        betas = {f: float(model_res.params.get(f, 0.0)) for f in factors}
        resid_std = float(train_reg["summary_metrics"]["residual_std_error"])

        # 2. Out-of-Sample Prediction
        p0 = float(train_df["Close"].iloc[-1])
        t0_date_str = train_df["Date"].iloc[-1].strftime("%Y-%m-%d")

        # Project out-of-sample returns using factor realizations + alpha
        beta_vec = np.array([betas[f] for f in factors], dtype=float)
        pred_excess = alpha_daily + test_df[factors].to_numpy(dtype=float) @ beta_vec
        test_df["Pred_Return"] = pred_excess + test_df["RF"].to_numpy(dtype=float)
        test_df["Pred_Price"] = p0 * (1.0 + test_df["Pred_Return"]).cumprod()
        test_df["Actual_Price"] = test_df["Close"]

        # Confidence Cone along horizon (95% CI: 1.96 * SE * sqrt(t))
        t_steps = np.arange(1, len(test_df) + 1)
        ci_margins = 1.96 * resid_std * np.sqrt(t_steps) * p0
        test_df["CI_Upper"] = test_df["Pred_Price"] + ci_margins
        test_df["CI_Lower"] = np.maximum(0.01, test_df["Pred_Price"] - ci_margins)

        # 3. Econometric Estimation Error Metrics
        test_df["Error_Dollar"] = test_df["Pred_Price"] - test_df["Actual_Price"]
        test_df["Error_Pct"] = (test_df["Error_Dollar"] / test_df["Actual_Price"]) * 100.0
        test_df["Abs_Error_Pct"] = np.abs(test_df["Error_Pct"])

        final_actual_price = float(test_df["Actual_Price"].iloc[-1])
        final_pred_price = float(test_df["Pred_Price"].iloc[-1])
        final_error_dollar = float(final_pred_price - final_actual_price)
        final_error_pct = float((final_error_dollar / final_actual_price) * 100.0)

        actual_total_return = float((final_actual_price - p0) / p0 * 100.0)
        pred_total_return = float((final_pred_price - p0) / p0 * 100.0)

        mae = float(test_df["Error_Dollar"].abs().mean())
        mape = float(test_df["Abs_Error_Pct"].mean())
        rmse = float(np.sqrt((test_df["Error_Dollar"] ** 2).mean()))

        # Tracking error (volatility of daily return prediction error)
        return_errors = test_df["Pred_Return"] - test_df["Return"]
        tracking_error_annual = float(return_errors.std() * np.sqrt(252.0) * 100.0)

        # Confidence interval coverage
        inside_ci = (test_df["Actual_Price"] >= test_df["CI_Lower"]) & (test_df["Actual_Price"] <= test_df["CI_Upper"])
        ci_coverage_pct = float(inside_ci.mean() * 100.0)

        # Directional accuracy
        direction_actual = final_actual_price > p0
        direction_pred = final_pred_price > p0
        direction_correct = (direction_actual == direction_pred)

        # 4. Prepare Chart Data Payload
        # Include context: last 30 days of training window
        context_train = train_df.iloc[-min(30, len(train_df)):].copy()
        
        timeline_dates = [d.strftime("%Y-%m-%d") for d in context_train["Date"]] + [d.strftime("%Y-%m-%d") for d in test_df["Date"]]
        
        actual_price_series = [float(x) for x in context_train["Close"]] + [float(x) for x in test_df["Actual_Price"]]
        pred_price_series = [None] * len(context_train) + [float(x) for x in test_df["Pred_Price"]]
        ci_upper_series = [None] * len(context_train) + [float(x) for x in test_df["CI_Upper"]]
        ci_lower_series = [None] * len(context_train) + [float(x) for x in test_df["CI_Lower"]]
        error_pct_series = [None] * len(context_train) + [float(x) for x in test_df["Error_Pct"]]

        return {
            "cutoff_date": t0_date_str,
            "cutoff_price": p0,
            "train_observations": len(train_df),
            "test_observations": len(test_df),
            "test_end_date": test_df["Date"].iloc[-1].strftime("%Y-%m-%d"),
            "model_r_squared": float(train_reg["summary_metrics"]["r_squared"]),
            "model_adj_r_squared": float(train_reg["summary_metrics"]["adj_r_squared"]),
            "trained_betas": betas,
            "trained_alpha_daily": alpha_daily,
            "trained_alpha_annual_pct": float(((1.0 + alpha_daily) ** 252.0 - 1.0) * 100.0),
            "diagnostics_summary": {
                "durbin_watson": train_reg["diagnostics"]["durbin_watson"],
                "jarque_bera": train_reg["diagnostics"]["jarque_bera"],
                "breusch_pagan": train_reg["diagnostics"]["breusch_pagan"]
            },
            "metrics": {
                "final_actual_price": final_actual_price,
                "final_pred_price": final_pred_price,
                "final_error_dollar": final_error_dollar,
                "final_error_pct": final_error_pct,
                "actual_total_return_pct": actual_total_return,
                "pred_total_return_pct": pred_total_return,
                "mae": mae,
                "mape": mape,
                "rmse": rmse,
                "tracking_error_annual_pct": tracking_error_annual,
                "ci_coverage_pct": ci_coverage_pct,
                "directional_hit": direction_correct
            },
            "chart_data": {
                "dates": timeline_dates,
                "actual_prices": actual_price_series,
                "pred_prices": pred_price_series,
                "ci_upper": ci_upper_series,
                "ci_lower": ci_lower_series,
                "error_pct": error_pct_series,
                "cutoff_index": len(context_train) - 1,
                "cutoff_date": t0_date_str
            }
        }
