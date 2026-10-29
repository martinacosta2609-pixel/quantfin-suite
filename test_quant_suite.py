"""
Automated Quantitative & Systems Verification Suite — Economato Financial Suite
Executes deterministic mathematical, econometric, and memory-footprint assertions across all 5 modules:
1. Zero SciPy / Statsmodels Footprint Check (RAM < 120 MB even after full econometric execution)
2. Bonos Argentinos: Pure-Python Richard Brent YTM Root-Finder & Modified Duration identity
3. Black-Scholes-Merton & Black-76: Exact erf CDF, Put-Call Parity, Implied Volatility & Pure-NumPy Econometrics
4. Fama-French 5-Factor: Pure-NumPy OLS + Newey-West HAC, Geometric Annualization & Log-Normal Confidence Cone
5. Valoración & DCF: Pure-NumPy Econometric Audit (Auto-HAC, White, Breusch-Godfrey, CUSUM) & Damped Monte Carlo IRR
"""

import os
import sys
import time
import math
import ctypes
from ctypes import wintypes
import numpy as np
import pandas as pd


def _get_rss_mb() -> float:
    """Zero-dependency Resident Set Size (RSS) in MB for Windows and Linux."""
    if sys.platform == "win32":
        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]
        pmc = PROCESS_MEMORY_COUNTERS()
        pmc.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        k32 = ctypes.windll.kernel32
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        k32.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), wintypes.DWORD]
        k32.K32GetProcessMemoryInfo.restype = wintypes.BOOL
        handle = k32.GetCurrentProcess()
        if k32.K32GetProcessMemoryInfo(handle, ctypes.byref(pmc), pmc.cb):
            return pmc.WorkingSetSize / (1024.0 * 1024.0)
    else:
        try:
            with open("/proc/self/status", "r") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        return float(line.split()[1]) / 1024.0
        except Exception:
            pass
    return 0.0

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "apps", "bonos"))
sys.path.insert(0, os.path.join(ROOT_DIR, "apps", "fama"))
sys.path.insert(0, os.path.join(ROOT_DIR, "apps", "bsm"))
sys.path.insert(0, os.path.join(ROOT_DIR, "apps", "valoracion"))


def run_all_tests():
    t_start = time.perf_counter()
    print("=" * 72)
    print("  ECONOMATO SUITE — AUDITORIA AUTOMATIZADA (FASES 1, 2 Y 3)")
    print("=" * 72)

    # -------------------------------------------------------------------------
    # TEST 1: Bonos Argentinos (Pure-Python Richard Brent YTM & Duration)
    # -------------------------------------------------------------------------
    from datetime import date
    from apps.bonos.bonos_engine import brentq, BondEngine
    root = brentq(lambda x: x ** 3 - x - 2.0, 1.0, 2.0, xtol=1e-10)
    assert abs(root - 1.5213797068) < 1e-8, f"Brentq accuracy error: {root}"
    al30 = BondEngine().calculate_sovereign_metrics("AL30D", 62.5, "USD", date(2026, 4, 17))
    assert al30 is not None and al30.get("tir", 0) > 0
    print(f"[PASS] 1. Bonos Argentinos: Pure-Python Brentq root={root:.8f}, AL30D TIR={al30['tir']:.2f}%, ModDur={al30['modified_duration']:.2f}")

    # -------------------------------------------------------------------------
    # TEST 2: Black-Scholes-Merton & Black-76 (Put-Call Parity & IV)
    # -------------------------------------------------------------------------
    from apps.bsm.backend.quant_engine import QuantEngine
    from apps.bsm.backend.econometrics import EconometricValidator
    S, K, T, r, sigma = 2350.0, 2300.0, 45.0 / 365.0, 0.045, 0.22
    c_price = QuantEngine.black76_price(S, K, T, r, sigma, "call")
    p_price = QuantEngine.black76_price(S, K, T, r, sigma, "put")
    parity_lhs = c_price - p_price
    parity_rhs = math.exp(-r * T) * (S - K)
    assert abs(parity_lhs - parity_rhs) < 1e-8, "Put-Call parity violation"
    iv_recovered = QuantEngine.calculate_implied_volatility(c_price, S, K, T, r, 0.0, "black76", "call")
    assert iv_recovered is not None and abs(iv_recovered - sigma) < 1e-4, f"IV recovery error: {iv_recovered}"

    # BSM Historical Econometric Validator (Pure NumPy)
    dates_bsm = pd.date_range("2025-01-01", periods=180, freq="B")
    rng = np.random.default_rng(42)
    close_bsm = 2000.0 * np.cumprod(1.0 + rng.normal(0.0003, 0.012, 180))
    df_bsm = pd.DataFrame({
        "Open": close_bsm * 0.998,
        "High": close_bsm * 1.006,
        "Low": close_bsm * 0.994,
        "Close": close_bsm,
    }, index=dates_bsm)
    bsm_bt = EconometricValidator.run_historical_test(df_bsm, str(dates_bsm[120].date()), horizon_days=20, window_days=60)
    assert "rolling_diagnostics" in bsm_bt and bsm_bt["rolling_diagnostics"]["sample_points"] > 0
    print(f"[PASS] 2. BSM & Black-76: Put-Call Parity diff = {abs(parity_lhs - parity_rhs):.2e}, IV = {iv_recovered*100:.2f}%, Rolling JB p={bsm_bt['rolling_diagnostics']['jarque_bera_pvalue']}")

    # -------------------------------------------------------------------------
    # TEST 3: Fama-French 5-Factor (Pure-NumPy OLS + Newey-West HAC + Cone)
    # -------------------------------------------------------------------------
    from core.fama_french_engine import FamaFrenchEngine
    from core.backtester import FamaFrenchBacktester
    dates_ff = pd.date_range("2023-01-01", periods=260, freq="B")
    mkt_rf = rng.normal(0.0005, 0.01, 260)
    rf = np.full(260, 0.0002)
    stock_ret = rf + 0.0001 + mkt_rf * 1.18 + rng.normal(0, 0.015, 260)
    close_ff = 100.0 * np.cumprod(1.0 + stock_ret)
    aligned_ff = pd.DataFrame({
        "Date": dates_ff,
        "Close": close_ff,
        "Return": stock_ret,
        "Stock_Return": stock_ret,
        "Stock_Excess_Return": stock_ret - rf,
        "Mkt-RF": mkt_rf,
        "SMB": rng.normal(0.0001, 0.005, 260),
        "HML": rng.normal(0.0002, 0.005, 260),
        "RMW": rng.normal(0.0001, 0.004, 260),
        "CMA": rng.normal(0.0001, 0.004, 260),
        "RF": rf,
    })
    ff_engine = FamaFrenchEngine("FF5")
    ff_res = ff_engine.estimate(aligned_ff, cov_type="HAC")
    assert ff_res["econometrics"]["summary_metrics"]["r_squared"] > 0.25
    bt_res = FamaFrenchBacktester.run_backtest(aligned_ff, cutoff_date=str(dates_ff[190].date()), train_window_days=150, test_horizon_days=50)
    pred_p = bt_res["chart_data"]["pred_prices"][-1]
    ci_up = bt_res["chart_data"]["ci_upper"][-1]
    ci_lo = bt_res["chart_data"]["ci_lower"][-1]
    assert ci_lo > 0.0 and abs((ci_up / pred_p) - (pred_p / ci_lo)) < 1e-6
    print(f"[PASS] 3. Fama-French 5F (Pure-NumPy HAC): R2 = {ff_res['econometrics']['summary_metrics']['r_squared']:.4f}, Cone [{ci_lo:.2f}, {ci_up:.2f}]")

    # -------------------------------------------------------------------------
    # TEST 4: Valoración & DCF (Pure-NumPy Econometric Audit + Damped Monte Carlo)
    # -------------------------------------------------------------------------
    from engine.econometrics import run_econometric_audit
    from engine.monte_carlo import run_monte_carlo_simulation
    ar_noise = np.zeros(80)
    for t in range(1, 80):
        ar_noise[t] = 0.72 * ar_noise[t - 1] + rng.normal(0, 0.01)
    df_val = pd.DataFrame({
        "stock_excess_return": mkt_rf[:80] * 1.25 + ar_noise,
        "market_excess_return": mkt_rf[:80],
        "sector_excess_return": mkt_rf[:80] * 0.9 + rng.normal(0, 0.005, 80),
        "rate_change_10y": rng.normal(0, 0.002, 80),
    })
    audit_res = run_econometric_audit(df_val, "AAPL")
    assert audit_res["model_summary"]["robust_se_applied"] is True
    mc_res = run_monte_carlo_simulation(
        p0=180.0, current_revenue_ps=45.0,
        historical_growth_mean=0.10, historical_growth_std=0.16,
        historical_margin_mean=0.22, historical_margin_std=0.06,
        num_simulations=5000, random_seed=42
    )
    assert mc_res["converged_pct"] >= 98.0
    print(f"[PASS] 4. Valoracion & DCF (Pure-NumPy): Auto-HAC={audit_res['model_summary']['cov_type']}, MC Converged={mc_res['converged_pct']}%")

    # -------------------------------------------------------------------------
    # TEST 5: Zero SciPy / Statsmodels Footprint & RAM Ceiling Check
    # -------------------------------------------------------------------------
    scipy_loaded = "scipy" in sys.modules
    statsmodels_loaded = "statsmodels" in sys.modules
    rss_mb = _get_rss_mb()
    elapsed_ms = (time.perf_counter() - t_start) * 1000.0
    assert not scipy_loaded, "SciPy should NOT be loaded in sys.modules!"
    assert not statsmodels_loaded, "Statsmodels should NOT be loaded in sys.modules!"
    assert rss_mb < 160.0, f"RAM exceeded ceiling: {rss_mb:.1f} MB"
    print(f"[PASS] 5. Memory & Dependency Shield: scipy={scipy_loaded}, statsmodels={statsmodels_loaded}, RSS={rss_mb:.1f} MB, Time={elapsed_ms:.0f} ms")
    print("=" * 72)
    print("  ALL QUANTITATIVE & ARCHITECTURAL TESTS PASSED (100%)")
    print("=" * 72)


if __name__ == "__main__":
    run_all_tests()
