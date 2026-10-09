"""
QUANT ENGINE - Black-Scholes-Merton & Black-76 Model
Calculo de precios teoricos, Griegas analiticas, Volatilidad Implicita y Estimadores Econometricos.

Nota de diseno: Black-76 es exactamente BSM con S = F (precio del futuro) y costo de acarreo
cero, es decir, con rendimiento de conveniencia q = r. Por eso ambos modelos comparten un unico
nucleo de calculo (_core) y solo difieren en el q efectivo y en la definicion de Rho.
"""

import math
import numpy as np
from scipy.special import ndtr
from scipy.optimize import brentq
from typing import Dict, Any, Optional

_INV_SQRT_2PI = 1.0 / math.sqrt(2.0 * math.pi)
_EPS = 1e-7


def _pdf(x):
    """Densidad normal estandar (mas rapida que scipy.stats.norm.pdf para escalares y arrays)."""
    return np.exp(-0.5 * x * x) * _INV_SQRT_2PI


class QuantEngine:
    # ------------------------------------------------------------------ nucleo
    @staticmethod
    def _q_eff(model: str, r: float, q: float) -> float:
        """Black-76 equivale a BSM con q = r (futuro: sin costo de acarreo)."""
        return r if model.lower() == "black76" else q

    @staticmethod
    def _d1_d2(S, K, T, r, sigma, q):
        sqrt_T = math.sqrt(T)
        d1 = (np.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / (sigma * sqrt_T)
        return d1, d1 - sigma * sqrt_T

    @classmethod
    def _price(cls, S, K, T, r, sigma, q, is_call):
        """
        Prima teorica. S puede ser un escalar o un ndarray (curvas de payoff vectorizadas);
        K, T, r, sigma y q son escalares.
        """
        if T <= _EPS:
            intrinsic = (S - K) if is_call else (K - S)
            return np.maximum(0.0, intrinsic)

        disc_q = math.exp(-q * T)
        disc_r = math.exp(-r * T)

        if sigma <= _EPS:
            fwd = S * disc_q - K * disc_r
            return np.maximum(0.0, fwd if is_call else -fwd)

        d1, d2 = cls._d1_d2(S, K, T, r, sigma, q)
        if is_call:
            price = S * disc_q * ndtr(d1) - K * disc_r * ndtr(d2)
        else:
            price = K * disc_r * ndtr(-d2) - S * disc_q * ndtr(-d1)
        return np.maximum(0.0, price)

    # --------------------------------------------------------------- precios
    @classmethod
    def bsm_price(
        cls,
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        q: float = 0.0,
        option_type: str = "call"
    ) -> float:
        """
        Precio teorico segun Black-Scholes-Merton (1973) con dividendo/acarreo continuo q.
        """
        return float(cls._price(S, K, T, r, sigma, q, option_type.lower() == "call"))

    @classmethod
    def black76_price(
        cls,
        F: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        option_type: str = "call"
    ) -> float:
        """
        Precio teorico segun Black-76 (Fischer Black, 1976), el estandar en CME, NYMEX,
        CBOT e ICE para opciones sobre futuros: BSM con S = F y q = r.
        """
        return float(cls._price(F, K, T, r, sigma, r, option_type.lower() == "call"))

    @classmethod
    def price_curve(
        cls,
        spots: np.ndarray,
        K: float,
        T: float,
        r: float,
        sigma: float,
        q: float = 0.0,
        model: str = "black76",
        option_type: str = "call"
    ) -> np.ndarray:
        """Prima teorica para un vector de precios del subyacente (una sola pasada vectorizada)."""
        spots = np.asarray(spots, dtype=float)
        return cls._price(spots, K, T, r, sigma, cls._q_eff(model, r, q), option_type.lower() == "call")

    # ---------------------------------------------------------------- griegas
    @classmethod
    def calculate_greeks(
        cls,
        S_or_F: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        q: float = 0.0,
        model: str = "black76",
        option_type: str = "call"
    ) -> Dict[str, float]:
        """
        Griegas analiticas completas:
        - Delta (dPrice / dUnderlying)
        - Gamma (d2Price / dUnderlying^2)
        - Vega  (dPrice / dSigma, por punto porcentual de vol: 1%)
        - Theta (dPrice / dt, por dia calendario: Theta/365)
        - Rho   (dPrice / dr, por punto porcentual de tasa: 1%)
        """
        is_call = option_type.lower() == "call"
        use_black76 = model.lower() == "black76"

        if T <= _EPS or sigma <= _EPS:
            intrinsic = (S_or_F - K) if is_call else (K - S_or_F)
            in_the_money = intrinsic > 0
            return {
                "delta": 1.0 if (is_call and in_the_money) else (-1.0 if (not is_call and in_the_money) else 0.0),
                "gamma": 0.0,
                "vega": 0.0,
                "theta": 0.0,
                "rho": 0.0,
                "d1": 0.0,
                "d2": 0.0
            }

        S = S_or_F
        q_eff = cls._q_eff(model, r, q)
        sqrt_T = math.sqrt(T)
        d1, d2 = cls._d1_d2(S, K, T, r, sigma, q_eff)
        disc_r = math.exp(-r * T)
        disc_q = math.exp(-q_eff * T)
        pdf_d1 = float(_pdf(d1))
        n_d1, n_d2 = float(ndtr(d1)), float(ndtr(d2))
        n_md1, n_md2 = 1.0 - n_d1, 1.0 - n_d2

        delta = disc_q * n_d1 if is_call else -disc_q * n_md1
        gamma = disc_q * pdf_d1 / (S * sigma * sqrt_T)
        vega_total = S * disc_q * pdf_d1 * sqrt_T

        term1 = -(S * disc_q * pdf_d1 * sigma) / (2.0 * sqrt_T)
        if is_call:
            theta_annual = term1 - r * K * disc_r * n_d2 + q_eff * S * disc_q * n_d1
        else:
            theta_annual = term1 + r * K * disc_r * n_md2 - q_eff * S * disc_q * n_md1

        if use_black76:
            # El futuro F queda fijo cuando cambia r: solo actua el descuento -> Rho = -T * Prima
            price = (S * disc_q * n_d1 - K * disc_r * n_d2) if is_call else (K * disc_r * n_md2 - S * disc_q * n_md1)
            rho_annual = -T * price
        else:
            rho_annual = K * T * disc_r * n_d2 if is_call else -K * T * disc_r * n_md2

        return {
            "delta": float(delta),
            "gamma": float(gamma),
            "vega": float(vega_total / 100.0),
            "theta": float(theta_annual / 365.0),
            "rho": float(rho_annual / 100.0),
            "d1": float(d1),
            "d2": float(d2)
        }

    # ------------------------------------------------------ volatilidad implicita
    @classmethod
    def calculate_implied_volatility(
        cls,
        market_price: float,
        S_or_F: float,
        K: float,
        T: float,
        r: float,
        q: float = 0.0,
        model: str = "black76",
        option_type: str = "call",
        initial_guess: float = 0.25,
        max_iter: int = 100,
        tol: float = 1e-5
    ) -> Optional[float]:
        """
        Resuelve la Volatilidad Implicita (IV) por Newton-Raphson con fallback a Brentq.
        """
        if market_price <= 0.0 or T <= _EPS:
            return None

        is_call = option_type.lower() == "call"
        q_eff = cls._q_eff(model, r, q)
        disc_r = math.exp(-r * T)
        disc_q = math.exp(-q_eff * T)

        # Limite de no-arbitraje: la prima no puede ser menor que el valor intrinseco descontado
        fwd = S_or_F * disc_q - K * disc_r
        intrinsic = max(0.0, fwd if is_call else -fwd)
        if market_price < intrinsic - 1e-4:
            return None

        def objective(sig):
            return float(cls._price(S_or_F, K, T, r, sig, q_eff, is_call)) - market_price

        # Intento 1: Newton-Raphson (la vega analitica se calcula directamente, sin recalcular griegas)
        sigma = initial_guess
        sqrt_T = math.sqrt(T)
        for _ in range(max_iter):
            price_diff = objective(sigma)
            if abs(price_diff) < tol:
                return float(sigma)

            d1, _d2 = cls._d1_d2(S_or_F, K, T, r, sigma, q_eff)
            vega = S_or_F * disc_q * float(_pdf(d1)) * sqrt_T
            if abs(vega) < 1e-6:
                break

            sigma -= price_diff / vega
            if sigma <= 0.001 or sigma > 8.0:
                break

        # Intento 2: Brentq (convergencia garantizada si hay cambio de signo en [0.1%, 500%])
        try:
            low, high = 0.001, 5.0
            if objective(low) * objective(high) < 0:
                return float(brentq(objective, low, high, xtol=tol))
        except Exception:
            pass

        return None

    # ------------------------------------------------- estimadores de volatilidad
    @staticmethod
    def estimate_historical_volatility(prices_close: np.ndarray, period: int = 252) -> float:
        """
        Estimador de Volatilidad Realizada Close-to-Close estandar (anualizada).
        """
        if len(prices_close) < 2:
            return 0.20
        log_ret = np.diff(np.log(prices_close))
        std = np.std(log_ret, ddof=1)
        return float(std * np.sqrt(period))

    @staticmethod
    def estimate_parkinson_volatility(prices_high: np.ndarray, prices_low: np.ndarray, period: int = 252) -> float:
        """
        Estimador de Volatilidad de Parkinson (1980) basado en rango High-Low.
        ~5 veces mas eficiente estadisticamente que Close-to-Close.
        """
        n = len(prices_high)
        if n < 2 or len(prices_low) != n:
            return 0.20

        valid = (prices_high > 0) & (prices_low > 0) & (prices_high >= prices_low)
        h = prices_high[valid]
        l = prices_low[valid]
        if len(h) < 2:
            return 0.20

        log_hl = np.log(h / l)
        sum_sq = np.sum(log_hl ** 2)
        variance = (1.0 / (4.0 * np.log(2.0) * len(h))) * sum_sq
        return float(np.sqrt(variance * period))

    @staticmethod
    def estimate_garman_klass_volatility(
        prices_open: np.ndarray,
        prices_high: np.ndarray,
        prices_low: np.ndarray,
        prices_close: np.ndarray,
        period: int = 252
    ) -> float:
        """
        Estimador de Garman-Klass (1980): usa Open, High, Low y Close de cada dia.
        ~7-8 veces mas eficiente que Close-to-Close (asume que no hay saltos entre cierre y apertura).
        """
        n = len(prices_close)
        if n < 2:
            return 0.20

        valid = (prices_open > 0) & (prices_high > 0) & (prices_low > 0) & (prices_close > 0)
        o = prices_open[valid]
        h = prices_high[valid]
        l = prices_low[valid]
        c = prices_close[valid]
        if len(c) < 2:
            return 0.20

        term1 = 0.5 * (np.log(h / l) ** 2)
        term2 = (2.0 * np.log(2.0) - 1.0) * (np.log(c / o) ** 2)
        var_daily = np.mean(term1 - term2)
        if var_daily < 0:
            var_daily = 0.0
        return float(np.sqrt(var_daily * period))

    # --------------------------------------------------------- evaluacion de prima
    @classmethod
    def evaluate_fair_premium(
        cls,
        market_price: Optional[float],
        theoretical_price: float,
        iv: Optional[float],
        hv: float,
        option_type: str,
        delta: float,
        d2: float,
        underlying_price: float,
        strike: float
    ) -> Dict[str, Any]:
        """
        Calcula la prima justa y su comparacion analitica contra el precio de mercado observado,
        proporcionando descomposicion de valor intrinseco/temporal sin emitir recomendaciones de compra o venta.
        """
        is_call = option_type.lower() == "call"

        # Descomposicion de la prima teorica justa
        intrinsic_val = max(0.0, (underlying_price - strike) if is_call else (strike - underlying_price))
        time_val = max(0.0, theoretical_price - intrinsic_val)

        # Probabilidad neutral al riesgo de finalizar ITM
        prob_itm = float(ndtr(d2) if is_call else ndtr(-d2)) * 100.0

        # Comparacion con precio de mercado observado
        has_market = market_price is not None and market_price > 0.001
        mkt_p = float(market_price) if has_market else theoretical_price

        diff = mkt_p - theoretical_price
        diff_pct = (diff / theoretical_price * 100.0) if theoretical_price > 0.001 else 0.0

        # Evaluacion de paridad respecto al modelo teorico
        if not has_market:
            valuation_status = "Prima Justa Teórica"
            status_color = "#38BDF8"
        elif abs(diff_pct) <= 2.5:
            valuation_status = "En Paridad con el Mercado (±2.5%)"
            status_color = "#38BDF8"
        elif diff > 0:
            valuation_status = f"Prima de Mercado Sobre la Par (+{abs(diff_pct):.1f}%)"
            status_color = "#F59E0B"
        else:
            valuation_status = f"Prima de Mercado Bajo la Par (-{abs(diff_pct):.1f}%)"
            status_color = "#10B981"

        vol_spread = (iv - hv) if (iv is not None) else 0.0

        analysis_details = [
            f"Prima Justa Calculada: ${theoretical_price:.4f} (Intrínseco: ${intrinsic_val:.2f} | Valor Tiempo: ${time_val:.2f}).",
            f"Probabilidad de Ejercicio a Vencimiento (ITM): {prob_itm:.1f}%."
        ]
        if has_market:
            analysis_details.append(
                f"Cotización Observada en Mercado: ${mkt_p:.2f} (Diferencia: {diff:+.2f} / {diff_pct:+.1f}%)."
            )
            if iv is not None:
                analysis_details.append(
                    f"Volatilidad Implícita (IV): {iv*100:.1f}% vs Histórica (HV): {hv*100:.1f}% (Spread: {vol_spread*100:+.1f}%)."
                )

        return {
            "theoretical_price": round(float(theoretical_price), 4),
            "market_price": round(float(mkt_p), 4),
            "has_market_price": bool(has_market),
            "intrinsic_value": round(float(intrinsic_val), 4),
            "time_value": round(float(time_val), 4),
            "diff_amount": round(float(diff), 4),
            "diff_pct": round(float(diff_pct), 2),
            "valuation_status": valuation_status,
            "status_color": status_color,
            "prob_itm_pct": round(float(prob_itm), 1),
            "vol_spread_pct": round(float(vol_spread * 100), 2),
            "details": analysis_details
        }

    @classmethod
    def generate_recommendation(
        cls,
        market_price: float,
        theoretical_price: float,
        iv: Optional[float],
        hv: float,
        option_type: str,
        delta: float,
        d2: float,
        edge_threshold_pct: float = 4.0,
        underlying_price: Optional[float] = None,
        strike: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Metodo mantenido para compatibilidad: retorna la evaluacion de prima justa
        sin recomendaciones de comprar o vender.
        """
        is_call = option_type.lower() == "call"
        has_market = market_price > 0.001
        mkt_p = float(market_price) if has_market else theoretical_price

        diff = mkt_p - theoretical_price
        diff_pct = (diff / theoretical_price * 100.0) if theoretical_price > 0.001 else 0.0

        vol_spread = (iv - hv) if (iv is not None) else 0.0
        prob_itm = float(ndtr(d2) if is_call else ndtr(-d2)) * 100.0

        if not has_market:
            action = f"PRIMA JUSTA {option_type.upper()}"
            color = "#38BDF8"
        elif abs(diff_pct) <= edge_threshold_pct:
            action = f"PRIMA EN PARIDAD {option_type.upper()}"
            color = "#38BDF8"
        elif diff > 0:
            action = f"PRIMA SOBRE LA PAR (+{abs(diff_pct):.1f}%)"
            color = "#F59E0B"
        else:
            action = f"PRIMA BAJO LA PAR (-{abs(diff_pct):.1f}%)"
            color = "#10B981"

        details = [
            f"Valor Teórico Calculado (Prima Justa): ${theoretical_price:.4f}.",
            f"Probabilidad de Ejercicio ITM: {prob_itm:.1f}%."
        ]
        if has_market:
            details.append(f"Precio de Mercado: ${mkt_p:.2f} (Diferencia: {diff:+.2f}).")
            if iv is not None:
                details.append(f"Volatilidad Implícita: {iv*100:.1f}% vs Histórica: {hv*100:.1f}%.")

        return {
            "action": action,
            "signal_strength": "PARIDAD TEÓRICA" if abs(diff_pct) <= edge_threshold_pct else "DESVÍO DE MERCADO",
            "color": color,
            "edge_pct": round(float(diff_pct), 2),
            "theoretical_price": round(float(theoretical_price), 4),
            "market_price": round(float(mkt_p), 4),
            "prob_itm_pct": round(float(prob_itm), 1),
            "vol_spread_pct": round(float(vol_spread * 100), 2),
            "rationale": details
        }
