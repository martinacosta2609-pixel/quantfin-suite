"""
TEST SUITE - Verificacion rigurosa de cuantificacion y diagnosticos econometricos
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from backend.quant_engine import QuantEngine
from backend.econometrics import EconometricValidator
from backend.bridge import ApiBridge


def test_quant_engine():
    print("--- 1. Testing QuantEngine BSM & Black-76 ---")
    # Benchmark conocido de John Hull: S=42, K=40, r=0.10, sigma=0.20, T=0.5
    # Call teorico exacto BSM ~ 4.76
    c_hull = QuantEngine.bsm_price(S=42, K=40, T=0.5, r=0.10, sigma=0.20, q=0.0, option_type="call")
    p_hull = QuantEngine.bsm_price(S=42, K=40, T=0.5, r=0.10, sigma=0.20, q=0.0, option_type="put")
    print(f"Hull Benchmark Call: {c_hull:.4f} (Esperado ~ 4.76)")
    print(f"Hull Benchmark Put:  {p_hull:.4f} (Esperado ~ 0.81)")
    assert 4.70 < c_hull < 4.82, "Fallo en BSM Call benchmark"
    assert 0.75 < p_hull < 0.85, "Fallo en BSM Put benchmark"

    # Paridad Put-Call BSM: C - P = S - K * exp(-r*T)
    parity_diff = (c_hull - p_hull) - (42 - 40 * np.exp(-0.10 * 0.5))
    print(f"Discrepancia Paridad Put-Call BSM: {parity_diff:.8f}")
    assert abs(parity_diff) < 1e-5, "Fallo en Put-Call Parity BSM"

    # Black-76 Futures benchmark
    # F=100, K=100, T=1.0, r=0.05, sigma=0.20
    # d1 = (0.5 * 0.04 * 1) / 0.2 = 0.1, d2 = -0.1
    c_b76 = QuantEngine.black76_price(F=100, K=100, T=1.0, r=0.05, sigma=0.20, option_type="call")
    p_b76 = QuantEngine.black76_price(F=100, K=100, T=1.0, r=0.05, sigma=0.20, option_type="put")
    print(f"Black-76 Call ATM: {c_b76:.4f}")
    print(f"Black-76 Put ATM:  {p_b76:.4f}")
    # En Black-76 ATM, Call = Put
    assert abs(c_b76 - p_b76) < 1e-5, "Fallo en Black-76 ATM symmetry"

    # Griegas
    g = QuantEngine.calculate_greeks(S_or_F=100, K=100, T=1.0, r=0.05, sigma=0.20, model="black76", option_type="call")
    print("Griegas Black-76:", g)
    assert 0.4 < g["delta"] < 0.6, "Fallo en Delta Black-76"
    assert g["gamma"] > 0, "Fallo en Gamma"
    assert g["vega"] > 0, "Fallo en Vega"

    # Solver de Volatilidad Implicita
    target_price = 8.50
    iv = QuantEngine.calculate_implied_volatility(
        market_price=target_price, S_or_F=100, K=100, T=1.0, r=0.05, model="black76", option_type="call"
    )
    print(f"IV Invertida para precio={target_price}: {iv:.4f}")
    check_price = QuantEngine.black76_price(F=100, K=100, T=1.0, r=0.05, sigma=iv, option_type="call")
    assert abs(check_price - target_price) < 1e-4, "Fallo en inversion de IV"

    print("QuantEngine: TODOS LOS TESTS SUPERADOS.\n")


def test_greeks_vs_finite_differences():
    print("--- 1b. Griegas analiticas vs diferencias finitas (BSM, BSM con q, Black-76) ---")
    S, T, r, sigma, h = 100.0, 0.4, 0.045, 0.27, 1e-4

    for model, q in (("black76", 0.0), ("bsm", 0.0), ("bsm", 0.02)):
        for opt in ("call", "put"):
            for K in (90.0, 100.0, 110.0):
                def px(S_=S, T_=T, r_=r, s_=sigma):
                    if model == "black76":
                        return QuantEngine.black76_price(S_, K, T_, r_, s_, opt)
                    return QuantEngine.bsm_price(S_, K, T_, r_, s_, q, opt)

                g = QuantEngine.calculate_greeks(S, K, T, r, sigma, q, model, opt)
                fd = {
                    "delta": (px(S_=S + h) - px(S_=S - h)) / (2 * h),
                    "gamma": (px(S_=S + h) - 2 * px() + px(S_=S - h)) / h ** 2,
                    "vega": (px(s_=sigma + h) - px(s_=sigma - h)) / (2 * h) / 100.0,
                    # Theta = -dP/dT, por dia calendario (regresion: Black-76 tenia el signo de r*P invertido)
                    "theta": (px(T_=T - h) - px(T_=T + h)) / (2 * h) / 365.0,
                    "rho": (px(r_=r + h) - px(r_=r - h)) / (2 * h) / 100.0,
                }
                for name, expected in fd.items():
                    assert abs(g[name] - expected) <= 5e-4 * max(1.0, abs(expected)), \
                        f"{model} q={q} {opt} K={K}: {name} analitica={g[name]:.6f} vs numerica={expected:.6f}"
    print("Delta, Gamma, Vega, Theta y Rho coinciden con la derivada numerica en todos los casos.")

    # La curva vectorizada debe ser identica a evaluar punto por punto
    spots = np.linspace(70, 130, 45)
    vec = QuantEngine.price_curve(spots, 100.0, 0.25, 0.04, 0.3, 0.0, "bsm", "put")
    scalar = np.array([QuantEngine.bsm_price(s, 100.0, 0.25, 0.04, 0.3, 0.0, "put") for s in spots])
    assert np.allclose(vec, scalar, atol=1e-12), "Curva vectorizada distinta de la escalar"

    # Black-76 == BSM con S=F y q=r
    assert abs(QuantEngine.black76_price(100, 95, 0.5, 0.05, 0.3, "call")
               - QuantEngine.bsm_price(100, 95, 0.5, 0.05, 0.3, 0.05, "call")) < 1e-12

    # IV: ida y vuelta en ambos modelos
    for model in ("black76", "bsm"):
        p = (QuantEngine.black76_price(100, 105, 0.3, 0.04, 0.41, "call") if model == "black76"
             else QuantEngine.bsm_price(100, 105, 0.3, 0.04, 0.41, 0.0, "call"))
        iv = QuantEngine.calculate_implied_volatility(p, 100, 105, 0.3, 0.04, 0.0, model, "call")
        assert iv is not None and abs(iv - 0.41) < 1e-4, f"IV no se recupera en {model}"
    print("Curva vectorizada, equivalencia Black-76/BSM e inversion de IV: OK.\n")


def test_econometric_validator():
    print("--- 2. Testing EconometricValidator ---")
    # Generar serie simulada con movimiento browniano geometrico
    np.random.seed(42)
    n = 300
    dates = pd.date_range("2025-01-01", periods=n, freq="B")
    ret = np.random.normal(0.0002, 0.015, n)
    prices = 100 * np.exp(np.cumsum(ret))
    highs = prices * (1 + np.abs(np.random.normal(0, 0.008, n)))
    lows = prices * (1 - np.abs(np.random.normal(0, 0.008, n)))
    opens = prices * (1 + np.random.normal(0, 0.004, n))

    df = pd.DataFrame({
        "Open": opens, "High": highs, "Low": lows, "Close": prices
    }, index=dates)

    target_date = dates[200].strftime("%Y-%m-%d")
    result = EconometricValidator.run_historical_test(
        history_df=df,
        target_date=target_date,
        option_type="call",
        moneyness=1.0,
        horizon_days=30,
        window_days=60,
        vol_estimator="garman_klass",
        model="black76",
        risk_free_rate=0.04
    )

    print("Resultado Auditoria Econometrica:")
    print("Fecha t0:", result["target_date"])
    print("Spot t0:", result["underlying_at_t0"])
    print("Strike K:", result["strike_K"])
    print("Sigma Hat:", result["sigma_hat_pct"], "%")
    print("Precio Teorico t0:", result["theoretical_price_t0"])
    print("Precio Terminal Real ST:", result["terminal_price_ST"])
    print("Payoff Terminal:", result["payoff_terminal"])
    print("Error Puntual:", result["punctual_error"])

    diag = result["rolling_diagnostics"]
    print(f"Diagnosticos Rolling: RMSE={diag['rmse']}, MAE={diag['mae']}, Bias={diag['mean_bias']}")
    print(f"Jarque-Bera Stat={diag['jarque_bera_stat']}, p-val={diag['jarque_bera_pvalue']}")
    print(f"Durbin-Watson Stat={diag['durbin_watson']}")

    assert "rmse" in diag and diag["rmse"] >= 0, "Fallo en diagnosticos RMSE"
    assert "durbin_watson" in diag, "Fallo en Durbin Watson"

    # El horizonte se mide en dias CALENDARIO: la fecha de la ultima rueda del camino debe caer
    # dentro de t0 + 30 dias (antes se tomaban 30 ruedas, ~42 dias calendario).
    t0 = pd.Timestamp(result["target_date"])
    last_path_date = pd.Timestamp(result["path_dates"][-1])
    assert (last_path_date - t0).days <= 30, "El horizonte no esta en dias calendario"
    assert (last_path_date - t0).days >= 26, "El camino real es mas corto que el horizonte"
    assert result["horizon_days"] == 30
    print("EconometricValidator: TODOS LOS TESTS SUPERADOS.\n")


def test_api_bridge():
    print("--- 3. Testing ApiBridge End-to-End ---")
    bridge = ApiBridge()
    comms = bridge.get_commodities()
    assert comms["status"] == "success" and len(comms["data"]) >= 8

    # Quote Oro
    q = bridge.get_quote("gold")
    print(f"Quote Gold: {q['data']['name']}, Precio={q['data']['price']}, Vol={q['data'].get('vol_garman_klass_pct')}%")
    assert q["status"] == "success" and q["data"]["price"] > 0

    # Single Option Calculation (Dual Fair Premium Evaluation)
    calc = bridge.calculate_single_option({
        "underlying_price": 2650.0,
        "strike": 2650.0,
        "days_to_expiry": 30,
        "risk_free_rate": 4.0,
        "volatility": 18.0,
        "model": "black76",
        "option_type": "call",
        "market_price": 42.0
    })
    print("Prima Justa Call:", calc["data"]["call"]["fair_premium"])
    print("Prima Justa Put:", calc["data"]["put"]["fair_premium"])
    print("Paridad Put-Call Discrepancia:", calc["data"]["put_call_parity"]["discrepancy"])
    assert calc["status"] == "success"
    assert "call" in calc["data"] and calc["data"]["call"]["fair_premium"] > 0
    assert "put" in calc["data"] and calc["data"]["put"]["fair_premium"] > 0
    assert "put_call_parity" in calc["data"]
    assert calc["data"]["put_call_parity"]["is_satisfied"]
    assert "greeks" in calc["data"]
    assert "payoff_curve" in calc["data"]

    print("ApiBridge: TODOS LOS TESTS SUPERADOS.\n")


if __name__ == "__main__":
    test_quant_engine()
    test_greeks_vs_finite_differences()
    test_econometric_validator()
    test_api_bridge()
    print(">>> TODAS LAS PRUEBAS CUANTITATIVAS Y ECONOMETRICAS PASARON CON EXITO (100%). <<<")
