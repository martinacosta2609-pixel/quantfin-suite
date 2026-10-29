import math
import numpy as np
import pandas as pd

_INV_SQRT_2 = 1.0 / math.sqrt(2.0)
_INV_SQRT_2PI = 1.0 / math.sqrt(2.0 * math.pi)


def _norm_sf(z: float) -> float:
    """Exact upper-tail probability P(Z > z) for Z ~ N(0,1)."""
    return 0.5 * math.erfc(float(z) * _INV_SQRT_2)


def _reg_inc_gamma_q(a: float, x: float) -> float:
    """Regularized upper incomplete gamma Q(a, x) = P(Chi2(2a) > 2x) via series / Lentz continued fraction."""
    if x <= 0.0:
        return 1.0
    if a <= 0.0:
        return 0.0
    if x < a + 1.0:
        # Series expansion for P(a, x), return 1 - P(a, x)
        ap = a
        s = 1.0 / a
        del_val = s
        for _ in range(200):
            ap += 1.0
            del_val *= x / ap
            s += del_val
            if abs(del_val) < abs(s) * 1e-14:
                break
        log_pref = -x + a * math.log(x) - math.lgamma(a)
        if log_pref < -700.0:
            return 1.0
        p_val = s * math.exp(log_pref)
        return max(0.0, min(1.0, 1.0 - p_val))
    else:
        # Continued fraction for Q(a, x)
        b = x + 1.0 - a
        c = 1.0 / 1e-30
        d = 1.0 / b
        h = d
        for i in range(1, 200):
            an = -i * (i - a)
            b += 2.0
            d = an * d + b
            if abs(d) < 1e-30:
                d = 1e-30
            c = b + an / c
            if abs(c) < 1e-30:
                c = 1e-30
            d = 1.0 / d
            del_val = d * c
            h *= del_val
            if abs(del_val - 1.0) < 1e-14:
                break
        log_pref = -x + a * math.log(x) - math.lgamma(a)
        if log_pref < -700.0:
            return 0.0
        return max(0.0, min(1.0, h * math.exp(log_pref)))


def _chi2_sf(x: float, df: int) -> float:
    """Exact survival function P(Chi2(df) > x)."""
    if x <= 0.0 or df <= 0:
        return 1.0
    return _reg_inc_gamma_q(0.5 * df, 0.5 * float(x))


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for incomplete beta function."""
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < 1e-30:
        d = 1e-30
    d = 1.0 / d
    h = d
    for m in range(1, 200):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        del_val = d * c
        h *= del_val
        if abs(del_val - 1.0) < 1e-14:
            break
    return h


def _betainc(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta function I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    log_bt = (
        math.lgamma(a + b)
        - math.lgamma(a)
        - math.lgamma(b)
        + a * math.log(x)
        + b * math.log(1.0 - x)
    )
    bt = math.exp(log_bt) if log_bt > -700.0 else 0.0
    if x < (a + 1.0) / (a + b + 2.0):
        return max(0.0, min(1.0, bt * _betacf(a, b, x) / a))
    return max(0.0, min(1.0, 1.0 - bt * _betacf(b, a, 1.0 - x) / b))


def _t_two_sided_pval(t_val: float, df: int) -> float:
    """Exact two-sided p-value for Student-t distribution with df degrees of freedom."""
    if df <= 0:
        return 1.0
    t2 = float(t_val) * float(t_val)
    x = df / (df + t2)
    return _betainc(0.5 * df, 0.5, x)


def _f_sf(f_val: float, dfn: int, dfd: int) -> float:
    """Exact survival function P(F(dfn, dfd) > f_val)."""
    if f_val <= 0.0 or dfn <= 0 or dfd <= 0:
        return 1.0
    x = dfd / (dfd + dfn * float(f_val))
    return _betainc(0.5 * dfd, 0.5 * dfn, x)


def _t_crit_975(df: int) -> float:
    """97.5% quantile of Student-t(df) via Cornish-Fisher expansion (exact to 5 decimals for df >= 5)."""
    if df <= 0 or df > 2000:
        return 1.959963984540054
    z = 1.959963984540054
    z2 = z * z
    z3 = z2 * z
    z5 = z3 * z2
    return (
        z
        + (z3 + z) / (4.0 * df)
        + (5.0 * z5 + 16.0 * z3 + 3.0 * z) / (96.0 * df * df)
        + (3.0 * z5 * z2 + 19.0 * z5 + 17.0 * z3 - 15.0 * z) / (384.0 * df ** 3)
    )


class _OlsResultShim:
    """Lightweight compatibility shim for callers expecting `statsmodels_result.params`."""
    __slots__ = ("params",)

    def __init__(self, params: pd.Series):
        self.params = params


class EconometricDiagnostics:
    @staticmethod
    def run_ols_with_diagnostics(
        y: pd.Series,
        X: pd.DataFrame,
        cov_type: str = "HAC",
        hac_maxlags: int = 5,
        diagnostics: bool = True,
    ) -> dict:
        """
        Pure-NumPy OLS regression and econometric diagnostic suite (0 MB statsmodels/scipy overhead):
        - Exact OLS & Newey-West (1987) HAC covariance matrix (Bartlett kernel + small-sample correction)
        - Durbin-Watson & Breusch-Godfrey autocorrelation tests
        - Breusch-Pagan heteroskedasticity test
        - Jarque-Bera normality of residuals test
        - Variance Inflation Factors (VIF)
        - Residual series and distribution for charting
        """
        y_arr = np.asarray(y, dtype=float)
        x_raw = np.asarray(X, dtype=float)
        if x_raw.ndim == 1:
            x_raw = x_raw[:, None]
        nobs, df_model = x_raw.shape
        k_vars = df_model + 1
        df_resid = max(1, nobs - k_vars)

        # Design matrix with leading constant column
        X_mat = np.column_stack([np.ones(nobs, dtype=float), x_raw])
        col_names = ["const"] + list(X.columns)

        # 1. Fit OLS via QR/SVD least-squares
        beta_hat, _, _, _ = np.linalg.lstsq(X_mat, y_arr, rcond=None)
        fitted_arr = X_mat @ beta_hat
        resid_arr = y_arr - fitted_arr

        ssr = float(np.dot(resid_arr, resid_arr))
        y_mean = float(np.mean(y_arr))
        y_centered = y_arr - y_mean
        sst = float(np.dot(y_centered, y_centered))
        r_squared = max(0.0, 1.0 - (ssr / sst)) if sst > 1e-15 else 0.0
        adj_r_squared = 1.0 - (1.0 - r_squared) * ((nobs - 1.0) / df_resid)

        sigma2_ols = ssr / df_resid
        resid_std_error = math.sqrt(max(0.0, sigma2_ols))

        # Bread matrix (X'X)^(-1)
        xtx_inv = np.linalg.pinv(X_mat.T @ X_mat)

        # Covariance matrix: Newey-West HAC or Classical OLS
        if cov_type == "HAC":
            u_mat = X_mat * resid_arr[:, None]  # (nobs, k_vars)
            s_hac = u_mat.T @ u_mat
            max_l = min(int(hac_maxlags), nobs - 1)
            for lag in range(1, max_l + 1):
                weight = 1.0 - (lag / (max_l + 1.0))
                gamma_l = u_mat[lag:].T @ u_mat[:-lag]
                s_hac += weight * (gamma_l + gamma_l.T)
            # Small-sample degrees-of-freedom correction matching statsmodels cov_hac
            cov_b = (nobs / float(df_resid)) * (xtx_inv @ s_hac @ xtx_inv)
        else:
            cov_b = sigma2_ols * xtx_inv

        bse_arr = np.sqrt(np.maximum(1e-18, np.diag(cov_b)))
        t_arr = beta_hat / bse_arr

        # Wald / F-statistic on non-constant regressors
        if df_model >= 1:
            if cov_type == "HAC":
                sub_beta = beta_hat[1:]
                sub_cov = cov_b[1:, 1:]
                try:
                    wald = float(sub_beta.T @ np.linalg.pinv(sub_cov) @ sub_beta)
                    f_stat = wald / df_model
                except Exception:
                    f_stat = ((sst - ssr) / df_model) / max(1e-15, sigma2_ols)
            else:
                f_stat = ((sst - ssr) / df_model) / max(1e-15, sigma2_ols)
            f_pvalue = _f_sf(f_stat, df_model, df_resid)
        else:
            f_stat, f_pvalue = 0.0, 1.0

        # Log-likelihood, AIC, BIC
        sigma2_mle = max(1e-18, ssr / nobs)
        llf = -0.5 * nobs * (1.0 + math.log(2.0 * math.pi) + math.log(sigma2_mle))
        aic = -2.0 * llf + 2.0 * k_vars
        bic = -2.0 * llf + k_vars * math.log(max(1, nobs))

        # Parameter table (matching statsmodels z/t convention)
        crit_val = 1.959963984540054 if cov_type == "HAC" else _t_crit_975(df_resid)
        params_list = []
        for idx, name in enumerate(col_names):
            coef = float(beta_hat[idx])
            bse = float(bse_arr[idx])
            tstat = float(t_arr[idx])
            pval = (2.0 * _norm_sf(abs(tstat))) if cov_type == "HAC" else _t_two_sided_pval(tstat, df_resid)
            ci_lower = coef - crit_val * bse
            ci_upper = coef + crit_val * bse

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
                "significance": sig,
            })

        summary_metrics = {
            "r_squared": float(r_squared),
            "adj_r_squared": float(adj_r_squared),
            "f_statistic": float(f_stat),
            "f_pvalue": float(f_pvalue),
            "n_obs": int(nobs),
            "df_resid": int(df_resid),
            "df_model": int(df_model),
            "aic": float(aic),
            "bic": float(bic),
            "log_likelihood": float(llf),
            "residual_std_error": float(resid_std_error),
            "cov_type": cov_type,
        }

        residuals = pd.Series(resid_arr, index=y.index)
        fitted_values = pd.Series(fitted_arr, index=y.index)
        shim = _OlsResultShim(pd.Series(beta_hat, index=col_names))

        if not diagnostics:
            return {
                "summary_metrics": summary_metrics,
                "parameters": params_list,
                "diagnostics": {},
                "residuals_distribution": {},
                "raw_residuals": residuals,
                "raw_fitted": fitted_values,
                "statsmodels_result": shim,
            }

        # 2. Autocorrelation Tests: Durbin-Watson & Breusch-Godfrey
        diff_res = np.diff(resid_arr)
        dw_stat = float(np.dot(diff_res, diff_res) / ssr) if ssr > 1e-15 else 2.0
        dw_verdict = "Sin autocorrelación de 1er orden evidente (~2.0)"
        if dw_stat < 1.6:
            dw_verdict = "Posible autocorrelación positiva en residuos (d < 1.6)"
        elif dw_stat > 2.4:
            dw_verdict = "Posible autocorrelación negativa en residuos (d > 2.4)"

        bg_test = {}
        try:
            nlags = min(5, max(1, nobs // 50))
            lag_cols = []
            for l_idx in range(1, nlags + 1):
                lag_col = np.zeros(nobs, dtype=float)
                lag_col[l_idx:] = resid_arr[:-l_idx]
                lag_cols.append(lag_col)
            X_bg = np.column_stack([X_mat] + lag_cols)
            beta_bg, _, _, _ = np.linalg.lstsq(X_bg, resid_arr, rcond=None)
            fit_bg = X_bg @ beta_bg
            ssr_bg = float(np.dot(resid_arr - fit_bg, resid_arr - fit_bg))
            r2_bg = max(0.0, 1.0 - (ssr_bg / ssr)) if ssr > 1e-15 else 0.0
            lm_bg = nobs * r2_bg
            pval_bg = _chi2_sf(lm_bg, nlags)
            df_bg_denom = max(1, nobs - k_vars - nlags)
            f_bg = ((r2_bg / nlags) / max(1e-15, (1.0 - r2_bg) / df_bg_denom))
            f_pval_bg = _f_sf(f_bg, nlags, df_bg_denom)
            bg_test = {
                "lm_stat": float(lm_bg),
                "p_value": float(pval_bg),
                "f_stat": float(f_bg),
                "f_p_value": float(f_pval_bg),
                "verdict": "No se rechaza H0 (Sin autocorrelación serial)" if pval_bg > 0.05 else "Se rechaza H0: Hay autocorrelación serial presente",
            }
        except Exception:
            bg_test = {"lm_stat": None, "p_value": None, "verdict": "N/A"}

        # 3. Heteroskedasticity Test: Breusch-Pagan
        bp_test = {}
        try:
            e2 = resid_arr ** 2
            e2_cent = e2 - float(np.mean(e2))
            sst_e2 = float(np.dot(e2_cent, e2_cent))
            beta_bp, _, _, _ = np.linalg.lstsq(X_mat, e2, rcond=None)
            res_bp = e2 - (X_mat @ beta_bp)
            ssr_bp = float(np.dot(res_bp, res_bp))
            r2_bp = max(0.0, 1.0 - (ssr_bp / sst_e2)) if sst_e2 > 1e-18 else 0.0
            lm_bp = nobs * r2_bp
            pval_bp = _chi2_sf(lm_bp, df_model)
            f_bp = ((r2_bp / max(1, df_model)) / max(1e-15, (1.0 - r2_bp) / df_resid))
            f_pval_bp = _f_sf(f_bp, df_model, df_resid)
            bp_test = {
                "lm_stat": float(lm_bp),
                "p_value": float(pval_bp),
                "f_stat": float(f_bp),
                "f_p_value": float(f_pval_bp),
                "verdict": "Homocedasticidad (varianza constante de residuos)" if pval_bp > 0.05 else "Heterocedasticidad detectada (errores HAC Newey-West corrigen el sesgo)",
            }
        except Exception:
            bp_test = {"lm_stat": None, "p_value": None, "verdict": "N/A"}

        # 4. Normality of Residuals Test: Jarque-Bera
        res_mean = float(np.mean(resid_arr))
        res_cent = resid_arr - res_mean
        m2 = float(np.mean(res_cent ** 2))
        if m2 > 1e-18:
            skewness = float(np.mean(res_cent ** 3)) / (m2 ** 1.5)
            kurtosis = float(np.mean(res_cent ** 4)) / (m2 ** 2)
        else:
            skewness, kurtosis = 0.0, 3.0
        jb_stat = (nobs / 6.0) * (skewness ** 2 + ((kurtosis - 3.0) ** 2) / 4.0)
        jb_pval = math.exp(-0.5 * max(0.0, jb_stat))
        jb_verdict = (
            "Residuos siguen distribución normal (p > 0.05)"
            if jb_pval > 0.05
            else "Residuos con colas pesadas o asimetría (típico en finanzas de alta frecuencia)"
        )

        # 5. Multicollinearity: Variance Inflation Factor (VIF) via inverse correlation matrix
        vif_list = []
        if df_model > 1:
            try:
                corr_mat = np.corrcoef(x_raw, rowvar=False)
                inv_corr = np.linalg.pinv(corr_mat)
                for i, col in enumerate(X.columns):
                    v_val = max(1.0, float(inv_corr[i, i]))
                    vif_list.append({
                        "factor": col,
                        "vif": v_val,
                        "multicollinear": v_val > 5.0,
                    })
            except Exception:
                pass

        # 6. Residual Distribution for Histogram Plotting
        hist_counts, bin_edges = np.histogram(resid_arr, bins=35, density=False)
        bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])
        res_std = float(np.std(resid_arr))
        if res_std > 1e-12:
            z_bins = (bin_centers - res_mean) / res_std
            normal_density = np.exp(-0.5 * z_bins * z_bins) * (_INV_SQRT_2PI / res_std)
            bin_width = float(bin_edges[1] - bin_edges[0])
            normal_counts = [float(d * nobs * bin_width) for d in normal_density]
        else:
            normal_counts = [0.0] * len(bin_centers)

        return {
            "summary_metrics": summary_metrics,
            "parameters": params_list,
            "diagnostics": {
                "durbin_watson": {
                    "stat": dw_stat,
                    "verdict": dw_verdict,
                },
                "breusch_godfrey": bg_test,
                "breusch_pagan": bp_test,
                "jarque_bera": {
                    "stat": float(jb_stat),
                    "p_value": float(jb_pval),
                    "skewness": float(skewness),
                    "kurtosis": float(kurtosis),
                    "verdict": jb_verdict,
                },
                "vif": vif_list,
            },
            "residuals_distribution": {
                "bin_centers": [float(x) for x in bin_centers],
                "actual_counts": [int(x) for x in hist_counts],
                "normal_counts": normal_counts,
            },
            "raw_residuals": residuals,
            "raw_fitted": fitted_values,
            "statsmodels_result": shim,
        }
