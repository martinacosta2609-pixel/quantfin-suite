import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.stattools import durbin_watson, jarque_bera
from statsmodels.stats.diagnostic import het_breuschpagan, acorr_breusch_godfrey
from statsmodels.stats.outliers_influence import variance_inflation_factor
from scipy import stats

class EconometricDiagnostics:
    @staticmethod
    def run_ols_with_diagnostics(y: pd.Series, X: pd.DataFrame, cov_type: str = "HAC", hac_maxlags: int = 5,
                                 diagnostics: bool = True) -> dict:
        """
        Runs an econometric OLS regression and performs a comprehensive battery of diagnostic tests:
        - Robust standard errors (HAC / Newey-West)
        - Durbin-Watson & Breusch-Godfrey autocorrelation tests
        - Breusch-Pagan heteroskedasticity test
        - Jarque-Bera normality of residuals test
        - Variance Inflation Factors (VIF)
        - Residual series and distribution for charting

        With diagnostics=False only the estimates and fit metrics are computed (used for batch
        sector scans where the test battery and chart payloads are never displayed).
        """
        X_with_const = sm.add_constant(X)
        
        # Fit model with OLS
        ols_model = sm.OLS(y, X_with_const)
        
        if cov_type == "HAC":
            results = ols_model.fit(cov_type="HAC", cov_kwds={"maxlags": hac_maxlags})
        else:
            results = ols_model.fit()

        residuals = results.resid
        fitted_values = results.fittedvalues
        nobs = int(results.nobs)
        df_model = int(results.df_model)
        df_resid = int(results.df_resid)

        # 1. Parameter Estimates Table
        params_list = []
        conf_int = results.conf_int(alpha=0.05)
        
        for name in results.params.index:
            coef = float(results.params[name])
            bse = float(results.bse[name])
            tstat = float(results.tvalues[name])
            pval = float(results.pvalues[name])
            ci_lower = float(conf_int.loc[name, 0])
            ci_upper = float(conf_int.loc[name, 1])
            
            # Significance indicator
            sig = ""
            if pval < 0.001:
                sig = "***"
            elif pval < 0.01:
                sig = "**"
            elif pval < 0.05:
                sig = "*"
            elif pval < 0.1:
                sig = "†"

            params_list.append({
                "factor": name,
                "label": "Alpha (Const)" if name == "const" else name,
                "coef": coef,
                "std_err": bse,
                "t_stat": tstat,
                "p_value": pval,
                "ci_lower": ci_lower,
                "ci_upper": ci_upper,
                "significance": sig
            })

        # Model fit metrics (cheap; always computed)
        f_stat = float(results.fvalue) if hasattr(results, "fvalue") and results.fvalue is not None else 0.0
        f_pvalue = float(results.f_pvalue) if hasattr(results, "f_pvalue") and results.f_pvalue is not None else 0.0
        summary_metrics = {
            "r_squared": float(results.rsquared),
            "adj_r_squared": float(results.rsquared_adj),
            "f_statistic": f_stat,
            "f_pvalue": f_pvalue,
            "n_obs": nobs,
            "df_resid": df_resid,
            "df_model": df_model,
            "aic": float(results.aic),
            "bic": float(results.bic),
            "log_likelihood": float(results.llf),
            "residual_std_error": float(np.std(residuals, ddof=df_model + 1)),
            "cov_type": cov_type
        }

        if not diagnostics:
            return {
                "summary_metrics": summary_metrics,
                "parameters": params_list,
                "diagnostics": {},
                "residuals_distribution": {},
                "raw_residuals": residuals,
                "raw_fitted": fitted_values,
                "statsmodels_result": results
            }

        # 2. Autocorrelation Tests
        dw_stat = float(durbin_watson(residuals))
        dw_verdict = "Sin autocorrelación de 1er orden evidente (~2.0)"
        if dw_stat < 1.6:
            dw_verdict = "Posible autocorrelación positiva en residuos (d < 1.6)"
        elif dw_stat > 2.4:
            dw_verdict = "Posible autocorrelación negativa en residuos (d > 2.4)"

        bg_test = {}
        try:
            # Breusch-Godfrey test
            bg_result = acorr_breusch_godfrey(results, nlags=min(5, max(1, nobs // 50)))
            bg_test = {
                "lm_stat": float(bg_result[0]),
                "p_value": float(bg_result[1]),
                "f_stat": float(bg_result[2]),
                "f_p_value": float(bg_result[3]),
                "verdict": "No se rechaza H0 (Sin autocorrelación serial)" if bg_result[1] > 0.05 else "Se rechaza H0: Hay autocorrelación serial presente"
            }
        except Exception:
            bg_test = {"lm_stat": None, "p_value": None, "verdict": "N/A"}

        # 3. Heteroskedasticity Tests (Breusch-Pagan)
        bp_test = {}
        try:
            bp_res = het_breuschpagan(residuals, X_with_const)
            bp_test = {
                "lm_stat": float(bp_res[0]),
                "p_value": float(bp_res[1]),
                "f_stat": float(bp_res[2]),
                "f_p_value": float(bp_res[3]),
                "verdict": "Homocedasticidad (varianza constante de residuos)" if bp_res[1] > 0.05 else "Heterocedasticidad detectada (errores HAC Newey-West corrigen el sesgo)"
            }
        except Exception:
            bp_test = {"lm_stat": None, "p_value": None, "verdict": "N/A"}

        # 4. Normality of Residuals Tests (Jarque-Bera)
        jb_res = jarque_bera(residuals)
        jb_stat = float(jb_res[0])
        jb_pval = float(jb_res[1])
        skewness = float(jb_res[2])
        kurtosis = float(jb_res[3])
        jb_verdict = "Residuos siguen distribución normal (p > 0.05)" if jb_pval > 0.05 else "Residuos con colas pesadas o asimetría (típico en finanzas de alta frecuencia)"

        # 5. Multicollinearity: Variance Inflation Factor (VIF)
        vif_list = []
        if X.shape[1] > 1:
            for i, col in enumerate(X.columns):
                try:
                    # Note: VIF on original factors
                    v_val = float(variance_inflation_factor(X_with_const.values, i + 1))
                    vif_list.append({
                        "factor": col,
                        "vif": v_val,
                        "multicollinear": v_val > 5.0
                    })
                except Exception:
                    pass

        # 6. Residual Distribution for Histogram Plotting
        hist_counts, bin_edges = np.histogram(residuals, bins=35, density=False)
        bin_centers = [(bin_edges[i] + bin_edges[i+1]) / 2.0 for i in range(len(hist_counts))]
        
        # Theoretical normal curve for comparison
        res_std = float(residuals.std())
        res_mean = float(residuals.mean())
        normal_density = stats.norm.pdf(bin_centers, res_mean, res_std) if res_std > 0 else []
        normal_counts = [float(d * len(residuals) * (bin_edges[1] - bin_edges[0])) for d in normal_density]

        return {
            "summary_metrics": summary_metrics,
            "parameters": params_list,
            "diagnostics": {
                "durbin_watson": {
                    "stat": dw_stat,
                    "verdict": dw_verdict
                },
                "breusch_godfrey": bg_test,
                "breusch_pagan": bp_test,
                "jarque_bera": {
                    "stat": jb_stat,
                    "p_value": jb_pval,
                    "skewness": skewness,
                    "kurtosis": kurtosis,
                    "verdict": jb_verdict
                },
                "vif": vif_list
            },
            "residuals_distribution": {
                "bin_centers": [float(x) for x in bin_centers],
                "actual_counts": [int(x) for x in hist_counts],
                "normal_counts": normal_counts
            },
            "raw_residuals": residuals,
            "raw_fitted": fitted_values,
            "statsmodels_result": results
        }
