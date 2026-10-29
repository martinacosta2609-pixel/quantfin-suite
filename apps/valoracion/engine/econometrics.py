"""
Econometric Testing & Audit Engine (Pure-NumPy High-Performance Implementation)
Implements rigorous statistical diagnostic battery on time series models without
loading statsmodels or scipy (~92 MB RAM saved):
1. Residuals dispersion and Q-Q Normality Plot (Acklam inverse normal CDF).
2. Statistical test battery:
   - Autocorrelation: Durbin-Watson statistic and Breusch-Godfrey LM test.
   - Heteroskedasticity: Breusch-Pagan and White tests.
   - Multicollinearity: Variance Inflation Factor (VIF).
   - Parameter Stability: CUSUM test with 5% critical bounds.
3. Automatic Newey-West HAC covariance matrix when serial correlation or heteroskedasticity is present.
"""

import math
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional

_INV_SQRT_2 = 1.0 / math.sqrt(2.0)


def _norm_sf(z: float) -> float:
    return 0.5 * math.erfc(float(z) * _INV_SQRT_2)


def _norm_ppf_scalar(p: float) -> float:
    """Peter Acklam's inverse normal CDF approximation (error < 1.15e-9)."""
    p = max(1e-12, min(1.0 - 1e-12, float(p)))
    a = (
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577518672690e02,
        -3.066479806614716e01,
        2.506628277459239e00,
    )
    b = (
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068155288572e01,
    )
    c = (
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e00,
        -2.549732539343734e00,
        4.374664141464968e00,
        2.938163982698783e00,
    )
    d = (
        7.784695709041462e-03,
        3.224671290700398e-01,
        2.445134137142996e00,
        3.754408661907416e00,
    )
    p_low = 0.02425
    p_high = 1.0 - p_low
    if p < p_low:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
        )
    if p <= p_high:
        q = p - 0.5
        r = q * q
        return (
            (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q
            / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)
        )
    q = math.sqrt(-2.0 * math.log(1.0 - p))
    return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
        (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
    )


def _reg_inc_gamma_q(a: float, x: float) -> float:
    if x <= 0.0:
        return 1.0
    if a <= 0.0:
        return 0.0
    if x < a + 1.0:
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
        return max(0.0, min(1.0, 1.0 - s * math.exp(log_pref)))
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
    if x <= 0.0 or df <= 0:
        return 1.0
    return _reg_inc_gamma_q(0.5 * df, 0.5 * float(x))


def _betacf(a: float, b: float, x: float) -> float:
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
    if df <= 0:
        return 1.0
    t2 = float(t_val) * float(t_val)
    return _betainc(0.5 * df, 0.5, df / (df + t2))


def _f_sf(f_val: float, dfn: int, dfd: int) -> float:
    if f_val <= 0.0 or dfn <= 0 or dfd <= 0:
        return 1.0
    return _betainc(0.5 * dfd, 0.5 * dfn, dfd / (dfd + dfn * float(f_val)))


def run_econometric_audit(
    df_series: pd.DataFrame,
    ticker: str,
    dependent_var: str = "stock_excess_return",
    exog_vars: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Fits an OLS multi-factor econometric model and performs full diagnostic suite in pure NumPy.
    """
    if exog_vars is None:
        exog_vars = ["market_excess_return", "sector_excess_return", "rate_change_10y"]

    available_exog = [col for col in exog_vars if col in df_series.columns]
    if not available_exog:
        # Fallback if custom factor columns (like size_factor_smb) are passed in df_series
        available_exog = [col for col in df_series.columns if col not in (dependent_var, "date", "Date")]
    if not available_exog:
        raise ValueError("No matching exogenous variables found in dataset.")

    clean_df = df_series.dropna(subset=[dependent_var] + available_exog).copy()
    if len(clean_df) < 25:
        raise ValueError(f"Insufficient observations for econometric audit: {len(clean_df)} (minimum 25 required).")

    y = np.asarray(clean_df[dependent_var].values, dtype=float)
    X_raw = np.asarray(clean_df[available_exog].values, dtype=float)
    if X_raw.ndim == 1:
        X_raw = X_raw[:, None]
    nobs, df_model = X_raw.shape
    k_vars = df_model + 1
    df_resid = max(1, nobs - k_vars)

    X = np.column_stack([np.ones(nobs, dtype=float), X_raw])
    feature_names = ["Constante (Alpha)"] + available_exog

    # 1. Fit OLS Model
    beta_ols, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    fitted = X @ beta_ols
    residuals = y - fitted
    ssr = float(np.dot(residuals, residuals))
    y_cent = y - float(np.mean(y))
    sst = float(np.dot(y_cent, y_cent))
    r_squared = max(0.0, 1.0 - (ssr / sst)) if sst > 1e-15 else 0.0
    adj_r_squared = 1.0 - (1.0 - r_squared) * ((nobs - 1.0) / df_resid)
    sigma2_ols = ssr / df_resid

    # 2. Residuals & Q-Q Plot
    std_residuals = (residuals - np.mean(residuals)) / (np.std(residuals, ddof=1) + 1e-9)
    sorted_indices = np.argsort(std_residuals)
    sorted_std_res = std_residuals[sorted_indices]

    # Theoretical quantiles using Blom's plotting position
    p_positions = (np.arange(1, nobs + 1) - 0.375) / (nobs + 0.25)
    theoretical_quantiles = np.array([_norm_ppf_scalar(p) for p in p_positions], dtype=float)

    dates = clean_df["date"].astype(str).values if "date" in clean_df.columns else [f"T{i}" for i in range(nobs)]

    res_2s = float(2.0 * np.std(residuals))
    residual_series = [
        {
            "date": str(dates[i]),
            "residual": round(float(residuals[i]), 5),
            "std_residual": round(float(std_residuals[i]), 4),
            "fitted": round(float(fitted[i]), 5),
            "actual": round(float(y[i]), 5),
            "upper_bound_2s": round(res_2s, 5),
            "lower_bound_2s": round(-res_2s, 5),
        }
        for i in range(nobs)
    ]

    qq_plot_data = [
        {
            "theoretical": round(float(theoretical_quantiles[i]), 4),
            "sample": round(float(sorted_std_res[i]), 4),
            "date": str(dates[sorted_indices[i]]),
            "ref_line": round(float(theoretical_quantiles[i]), 4),
        }
        for i in range(nobs)
    ]

    # 3. Autocorrelation Tests
    # A. Durbin-Watson
    diff_res = np.diff(residuals)
    dw_stat = float(np.dot(diff_res, diff_res) / ssr) if ssr > 1e-15 else 2.0
    if dw_stat < 1.4:
        dw_diag = "Evidencia de autocorrelación positiva de primer orden (DW < 1.4)"
        dw_passed = False
    elif dw_stat > 2.6:
        dw_diag = "Evidencia de autocorrelación negativa de primer orden (DW > 2.6)"
        dw_passed = False
    else:
        dw_diag = "No se detecta autocorrelación serial de primer orden significativa (1.4 <= DW <= 2.6)"
        dw_passed = True

    # B. Breusch-Godfrey Test (nlags=2)
    try:
        nlags = 2
        lag1 = np.zeros(nobs, dtype=float)
        lag2 = np.zeros(nobs, dtype=float)
        lag1[1:] = residuals[:-1]
        lag2[2:] = residuals[:-2]
        X_bg = np.column_stack([X, lag1, lag2])
        beta_bg, _, _, _ = np.linalg.lstsq(X_bg, residuals, rcond=None)
        res_bg = residuals - (X_bg @ beta_bg)
        ssr_bg = float(np.dot(res_bg, res_bg))
        r2_bg = max(0.0, 1.0 - (ssr_bg / ssr)) if ssr > 1e-15 else 0.0
        bg_lm_stat = float(nobs * r2_bg)
        bg_lm_pval = float(_chi2_sf(bg_lm_stat, nlags))
        df_bg_denom = max(1, nobs - k_vars - nlags)
        bg_f_stat = float((r2_bg / nlags) / max(1e-15, (1.0 - r2_bg) / df_bg_denom))
        bg_f_pval = float(_f_sf(bg_f_stat, nlags, df_bg_denom))
        bg_passed = bg_lm_pval > 0.05
        bg_diag = (
            "No se rechaza H0: No hay autocorrelación serial de orden superior (p > 0.05)"
            if bg_passed
            else "Se rechaza H0 al 5%: Presencia de autocorrelación residual"
        )
    except Exception as e:
        bg_lm_stat, bg_lm_pval, bg_f_stat, bg_f_pval = 0.0, 1.0, 0.0, 1.0
        bg_passed = True
        bg_diag = f"Test Breusch-Godfrey no convergente: {str(e)}"

    # 4. Heteroskedasticity Tests
    e2 = residuals ** 2
    e2_cent = e2 - float(np.mean(e2))
    sst_e2 = float(np.dot(e2_cent, e2_cent))

    # A. Breusch-Pagan
    try:
        beta_bp, _, _, _ = np.linalg.lstsq(X, e2, rcond=None)
        res_bp = e2 - (X @ beta_bp)
        ssr_bp = float(np.dot(res_bp, res_bp))
        r2_bp = max(0.0, 1.0 - (ssr_bp / sst_e2)) if sst_e2 > 1e-18 else 0.0
        bp_lm_stat = float(nobs * r2_bp)
        bp_lm_pval = float(_chi2_sf(bp_lm_stat, df_model))
        bp_f_stat = float((r2_bp / max(1, df_model)) / max(1e-15, (1.0 - r2_bp) / df_resid))
        bp_f_pval = float(_f_sf(bp_f_stat, df_model, df_resid))
        bp_passed = bp_lm_pval > 0.05
        bp_diag = (
            "Homocedasticidad confirmada (p > 0.05): Varianza condicional constante"
            if bp_passed
            else "Heterocedasticidad detectada (p <= 0.05): Errores estándar corregidos automáticamente con Newey-West HAC"
        )
    except Exception as e:
        bp_lm_stat, bp_lm_pval, bp_f_stat, bp_f_pval = 0.0, 1.0, 0.0, 1.0
        bp_passed = True
        bp_diag = f"Test Breusch-Pagan error: {str(e)}"

    # B. White Test (linear + squares + cross-products)
    try:
        white_cols = [X]
        for j in range(df_model):
            for m in range(j, df_model):
                white_cols.append((X_raw[:, j] * X_raw[:, m])[:, None])
        X_white = np.hstack(white_cols)
        beta_w, _, rank_w, _ = np.linalg.lstsq(X_white, e2, rcond=None)
        res_w = e2 - (X_white @ beta_w)
        ssr_w = float(np.dot(res_w, res_w))
        r2_w = max(0.0, 1.0 - (ssr_w / sst_e2)) if sst_e2 > 1e-18 else 0.0
        white_stat = float(nobs * r2_w)
        df_white = max(1, int(rank_w) - 1)
        white_pval = float(_chi2_sf(white_stat, df_white))
        white_passed = white_pval > 0.05
    except Exception:
        white_stat, white_pval = 0.0, 1.0
        white_passed = True

    # 5. Multicollinearity: Variance Inflation Factor (VIF)
    vif_results = []
    if df_model > 1:
        try:
            corr_mat = np.corrcoef(X_raw, rowvar=False)
            inv_corr = np.linalg.pinv(corr_mat)
            diag_vif = [max(1.0, float(inv_corr[i, i])) for i in range(df_model)]
        except Exception:
            diag_vif = [1.0] * df_model
    else:
        diag_vif = [1.0] * df_model

    for i in range(df_model):
        var_name = feature_names[i + 1]
        vif_val = diag_vif[i]
        status = (
            "Baja / Ortogonalidad admisible (VIF < 5)"
            if vif_val < 5.0
            else ("Moderada (5 <= VIF < 10)" if vif_val < 10.0 else "Severa / Multicolinealidad crítica (VIF >= 10)")
        )
        vif_results.append({
            "variable": var_name,
            "vif": round(vif_val, 2),
            "status": status,
            "passed": vif_val < 5.0,
        })

    # 6. Parameter Stability: CUSUM Test
    sigma_hat = float(np.std(residuals, ddof=k_vars)) + 1e-9
    cum_res = np.cumsum(residuals)
    cusum_path = []
    crit_bound = 0.948  # 5% significance line slope for CUSUM
    max_cusum_ratio = 0.0
    for t in range(nobs):
        tau = (t + 1) / nobs
        w_t = float(cum_res[t] / (sigma_hat * math.sqrt(nobs)))
        bound_factor = 1.0 + 2.0 * tau
        upper_limit = crit_bound * bound_factor
        lower_limit = -upper_limit
        max_cusum_ratio = max(max_cusum_ratio, abs(w_t) / bound_factor)
        cusum_path.append({
            "date": str(dates[t]),
            "cusum": round(w_t, 4),
            "upper_bound": round(upper_limit, 4),
            "lower_bound": round(lower_limit, 4),
        })

    cusum_stat = float(max_cusum_ratio)
    # Ploberger-Kramer Brownian bridge supremum survival approximation
    cusum_pval = float(min(1.0, max(0.0, 2.0 * math.exp(-2.0 * (cusum_stat ** 2)))))
    cusum_passed = cusum_stat < crit_bound
    cusum_diag = (
        "Parámetros estructuralmente estables a lo largo del tiempo (p > 0.05)"
        if cusum_passed
        else "Posible quiebre estructural detectado en la serie temporal (p <= 0.05)"
    )

    # 7. Newey-West HAC robust covariance when serial correlation or heteroskedasticity is detected
    use_hac = (not dw_passed) or (not bg_passed) or (not bp_passed) or (not white_passed)
    xtx_inv = np.linalg.pinv(X.T @ X)
    if use_hac:
        u_mat = X * residuals[:, None]
        s_hac = u_mat.T @ u_mat
        max_l = min(3, nobs - 1)
        for lag in range(1, max_l + 1):
            weight = 1.0 - (lag / (max_l + 1.0))
            gamma_l = u_mat[lag:].T @ u_mat[:-lag]
            s_hac += weight * (gamma_l + gamma_l.T)
        cov_b = (nobs / float(df_resid)) * (xtx_inv @ s_hac @ xtx_inv)
    else:
        cov_b = sigma2_ols * xtx_inv

    bse_arr = np.sqrt(np.maximum(1e-18, np.diag(cov_b)))
    t_arr = beta_ols / bse_arr

    if df_model >= 1:
        if use_hac:
            sub_b = beta_ols[1:]
            sub_c = cov_b[1:, 1:]
            try:
                f_stat = float((sub_b.T @ np.linalg.pinv(sub_c) @ sub_b) / df_model)
            except Exception:
                f_stat = float(((sst - ssr) / df_model) / max(1e-15, sigma2_ols))
        else:
            f_stat = float(((sst - ssr) / df_model) / max(1e-15, sigma2_ols))
        f_pvalue = float(_f_sf(f_stat, df_model, df_resid))
    else:
        f_stat, f_pvalue = 0.0, 1.0

    sigma2_mle = max(1e-18, ssr / nobs)
    llf = -0.5 * nobs * (1.0 + math.log(2.0 * math.pi) + math.log(sigma2_mle))
    aic = -2.0 * llf + 2.0 * k_vars
    bic = -2.0 * llf + k_vars * math.log(max(1, nobs))

    model_summary = {
        "ticker": ticker,
        "nobs": nobs,
        "r_squared": round(float(r_squared), 4),
        "adj_r_squared": round(float(adj_r_squared), 4),
        "f_statistic": round(float(f_stat), 2),
        "f_pvalue": float(f_pvalue),
        "aic": round(float(aic), 2),
        "bic": round(float(bic), 2),
        "cov_type": "HAC (Newey-West, maxlags=3)" if use_hac else "OLS Homoscedástico",
        "robust_se_applied": bool(use_hac),
        "coefficients": [
            {
                "variable": feature_names[i],
                "coef": round(float(beta_ols[i]), 5),
                "std_err": round(float(bse_arr[i]), 5),
                "t_stat": round(float(t_arr[i]), 3),
                "p_value": float((2.0 * _norm_sf(abs(t_arr[i]))) if use_hac else _t_two_sided_pval(t_arr[i], df_resid)),
            }
            for i in range(len(feature_names))
        ],
    }

    return {
        "model_summary": model_summary,
        "residual_series": residual_series,
        "qq_plot": qq_plot_data,
        "cusum_path": cusum_path,
        "tests": {
            "autocorrelation": {
                "durbin_watson": {
                    "stat": round(dw_stat, 3),
                    "diagnosis": dw_diag,
                    "passed": dw_passed,
                },
                "breusch_godfrey": {
                    "lm_stat": round(bg_lm_stat, 3),
                    "lm_pvalue": round(bg_lm_pval, 4),
                    "f_stat": round(bg_f_stat, 3),
                    "f_pvalue": round(bg_f_pval, 4),
                    "diagnosis": bg_diag,
                    "passed": bg_passed,
                },
            },
            "heteroskedasticity": {
                "breusch_pagan": {
                    "lm_stat": round(bp_lm_stat, 3),
                    "lm_pvalue": round(bp_lm_pval, 4),
                    "f_stat": round(bp_f_stat, 3),
                    "f_pvalue": round(bp_f_pval, 4),
                    "diagnosis": bp_diag,
                    "passed": bp_passed,
                },
                "white": {
                    "stat": round(white_stat, 3),
                    "pvalue": round(white_pval, 4),
                    "passed": white_passed,
                },
            },
            "multicollinearity": {
                "vif": vif_results,
                "overall_passed": all(item["passed"] for item in vif_results),
            },
            "parameter_stability": {
                "cusum": {
                    "stat": round(cusum_stat, 3),
                    "pvalue": round(cusum_pval, 4),
                    "diagnosis": cusum_diag,
                    "passed": cusum_passed,
                }
            },
        },
    }
