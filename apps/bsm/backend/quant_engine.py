"""
QUANT ENGINE - Black-Scholes-Merton & Black-76 Model
Calculo de precios teoricos, Griegas analiticas, Volatilidad Implicita y Estimadores Econometricos.
"""

import numpy as np
from scipy.stats import norm
from scipy.optimize import brentq
from typing import Dict, Any, Optional, Tuple


class QuantEngine:
    @staticmethod
    def bsm_price(
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        q: float = 0.0,
        option_type: str = "call"
    ) -> float:
        """
        Calcula el precio teorico segun el modelo Black-Scholes-Merton (1973) con dividendo/acarreo continuo q.
        """
        if T <= 1e-7:
            # Vencimiento inmediato
            if option_type.lower() == "call":
                return max(0.0, S - K)
            else:
                return max(0.0, K - S)
        
        if sigma <= 1e-7:
            # Volatilidad cero
            discount_S = S * np.exp(-q * T)
            discount_K = K * np.exp(-r * T)
            if option_type.lower() == "call":
                return max(0.0, discount_S - discount_K)
            else:
                return max(0.0, discount_K - discount_S)

        d1 = (np.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)

        if option_type.lower() == "call":
            price = S * np.exp(-q * T) * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        else:
            price = K * np.exp(-r * T) * norm.cdf(-d2) - S * np.exp(-q * T) * norm.cdf(-d1)

        return max(0.0, float(price))

    @staticmethod
    def black76_price(
        F: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        option_type: str = "call"
    ) -> float:
        """
        Calcula el precio teorico segun el modelo Black-76 (Fischer Black 1976),
        el estandar oficial en CME, NYMEX, CBOT e ICE para opciones sobre contratos de futuros de commodities.
        """
        if T <= 1e-7:
            if option_type.lower() == "call":
                return max(0.0, F - K)
            else:
                return max(0.0, K - F)

        if sigma <= 1e-7:
            discount = np.exp(-r * T)
            if option_type.lower() == "call":
                return max(0.0, discount * (F - K))
            else:
                return max(0.0, discount * (K - F))

        d1 = (np.log(F / K) + 0.5 * (sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        discount = np.exp(-r * T)

        if option_type.lower() == "call":
            price = discount * (F * norm.cdf(d1) - K * norm.cdf(d2))
        else:
            price = discount * (K * norm.cdf(-d2) - F * norm.cdf(-d1))

        return max(0.0, float(price))

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
        Calcula las Griegas analiticas completas:
        - Delta (dPrice / dUnderlying)
        - Gamma (d2Price / dUnderlying^2)
        - Vega  (dPrice / dSigma, expresado por punto porcentual de vol: 1%)
        - Theta (dPrice / dt, expresado por dia calendario: Theta/365)
        - Rho   (dPrice / dr, expresado por punto porcentual de tasa: 1%)
        """
        is_call = option_type.lower() == "call"
        use_black76 = model.lower() == "black76"

        if T <= 1e-7 or sigma <= 1e-7:
            # Caso limite
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

        sqrt_T = np.sqrt(T)

        if use_black76:
            F = S_or_F
            d1 = (np.log(F / K) + 0.5 * (sigma ** 2) * T) / (sigma * sqrt_T)
            d2 = d1 - sigma * sqrt_T
            discount = np.exp(-r * T)
            pdf_d1 = norm.pdf(d1)

            # Delta en Black-76
            delta = discount * norm.cdf(d1) if is_call else -discount * norm.cdf(-d1)
            # Gamma en Black-76
            gamma = (discount * pdf_d1) / (F * sigma * sqrt_T)
            # Vega en Black-76 (anual y por 1% vol)
            vega_total = discount * F * pdf_d1 * sqrt_T
            vega_1pct = vega_total / 100.0
            # Theta en Black-76 (por dia)
            term1 = -(discount * F * pdf_d1 * sigma) / (2.0 * sqrt_T)
            if is_call:
                theta_annual = term1 - r * discount * (F * norm.cdf(d1) - K * norm.cdf(d2))
            else:
                theta_annual = term1 - r * discount * (K * norm.cdf(-d2) - F * norm.cdf(-d1))
            theta_1day = theta_annual / 365.0
            # Rho en Black-76 (por 1% tasa)
            price = cls.black76_price(F, K, T, r, sigma, option_type)
            rho_annual = -T * price
            rho_1pct = rho_annual / 100.0

        else:
            S = S_or_F
            d1 = (np.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * sqrt_T)
            d2 = d1 - sigma * sqrt_T
            discount_r = np.exp(-r * T)
            discount_q = np.exp(-q * T)
            pdf_d1 = norm.pdf(d1)

            # Delta BSM
            delta = discount_q * norm.cdf(d1) if is_call else -discount_q * norm.cdf(-d1)
            # Gamma BSM
            gamma = (discount_q * pdf_d1) / (S * sigma * sqrt_T)
            # Vega BSM
            vega_total = S * discount_q * pdf_d1 * sqrt_T
            vega_1pct = vega_total / 100.0
            # Theta BSM
            term1 = -(S * discount_q * pdf_d1 * sigma) / (2.0 * sqrt_T)
            if is_call:
                theta_annual = term1 - r * K * discount_r * norm.cdf(d2) + q * S * discount_q * norm.cdf(d1)
            else:
                theta_annual = term1 + r * K * discount_r * norm.cdf(-d2) - q * S * discount_q * norm.cdf(-d1)
            theta_1day = theta_annual / 365.0
            # Rho BSM
            if is_call:
                rho_annual = K * T * discount_r * norm.cdf(d2)
            else:
                rho_annual = -K * T * discount_r * norm.cdf(-d2)
            rho_1pct = rho_annual / 100.0

        return {
            "delta": float(delta),
            "gamma": float(gamma),
            "vega": float(vega_1pct),
            "theta": float(theta_1day),
            "rho": float(rho_1pct),
            "d1": float(d1),
            "d2": float(d2)
        }

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
        Resuelve la Volatilidad Implicita (IV) por Newton-Raphson acelerado con fallback a Brentq.
        """
        if market_price <= 0.0 or T <= 1e-7:
            return None

        # Limites de arbitraje intrinseco
        is_call = option_type.lower() == "call"
        use_black76 = model.lower() == "black76"
        discount = np.exp(-r * T)

        if use_black76:
            intrinsic = discount * max(0.0, (S_or_F - K) if is_call else (K - S_or_F))
        else:
            discount_q = np.exp(-q * T)
            intrinsic = max(0.0, (S_or_F * discount_q - K * discount) if is_call else (K * discount - S_or_F * discount_q))

        if market_price < intrinsic - 1e-4:
            return None

        def objective(sigma):
            if use_black76:
                theo = cls.black76_price(S_or_F, K, T, r, sigma, option_type)
            else:
                theo = cls.bsm_price(S_or_F, K, T, r, sigma, q, option_type)
            return theo - market_price

        # Intento 1: Newton-Raphson rapido
        sigma = initial_guess
        for _ in range(max_iter):
            price_diff = objective(sigma)
            if abs(price_diff) < tol:
                return float(sigma)

            greeks = cls.calculate_greeks(S_or_F, K, T, r, sigma, q, model, option_type)
            vega = greeks["vega"] * 100.0  # Volver a vega total

            if abs(vega) < 1e-6:
                break

            step = price_diff / vega
            sigma -= step

            if sigma <= 0.001 or sigma > 8.0:
                break

        # Intento 2: Scipy Brentq robusto garantizado
        try:
            low = 0.001
            high = 5.0
            f_low = objective(low)
            f_high = objective(high)
            if f_low * f_high < 0:
                sol = brentq(objective, low, high, xtol=tol)
                return float(sol)
        except Exception:
            pass

        return None

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
        5 veces mas eficiente estadisticamente que Close-to-Close.
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
        Estimador de Garman-Klass (1980): incluye saltos de apertura y movimiento intradia.
        8 veces mas eficiente que Close-to-Close.
        """
        n = len(prices_close)
        if n < 2:
            return 0.20
        
        valid = (prices_open > 0) & (prices_high > 0) & (prices_low > 0) & (prices_close > 0)
        o = prices_open[valid]
        h = prices_high[valid]
        l = prices_low[valid]
        c = prices_close[valid]
        n_val = len(c)
        if n_val < 2:
            return 0.20

        term1 = 0.5 * (np.log(h / l) ** 2)
        term2 = (2.0 * np.log(2.0) - 1.0) * (np.log(c / o) ** 2)
        var_daily = np.mean(term1 - term2)
        if var_daily < 0:
            var_daily = 0.0
        return float(np.sqrt(var_daily * period))

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
        edge_threshold_pct: float = 4.0
    ) -> Dict[str, Any]:
        """
        Genera recomendacion cuantitativa profesional (BUY / SELL / NEUTRAL)
        basada en mispricing teorico, spread de volatilidad (IV - HV), y Probabilidad de Ganancia (PoP).
        """
        is_call = option_type.lower() == "call"
        
        if market_price <= 0.001:
            edge_pct = 0.0
        else:
            edge_pct = ((theoretical_price - market_price) / market_price) * 100.0

        # Spread de volatilidad
        vol_spread = (iv - hv) if (iv is not None) else 0.0

        # Probabilidad de terminar ITM segun medida neutral al riesgo (N(d2) para Call, N(-d2) para Put)
        prob_itm = float(norm.cdf(d2) if is_call else norm.cdf(-d2)) * 100.0

        action = "NEUTRAL"
        signal_strength = "MODERADA"
        color = "#94A3B8"  # Slate
        rationale_items = []

        # Logica cuantitativa de recomendacion:
        # Edge positivo > threshold: El valor teorico es mayor al precio de mercado (opcion barata/infravalorada)
        # Edge negativo < -threshold: El valor teorico es menor al precio de mercado (opcion cara/sobrevalorada)

        if edge_pct >= edge_threshold_pct:
            # Infravalorada en el mercado -> COMPRA
            action = f"COMPRA RECOMENDADA (LONG {'CALL' if is_call else 'PUT'})"
            color = "#10B981"  # Emerald
            if edge_pct > 12.0:
                signal_strength = "MUY FUERTE"
            elif edge_pct > 7.0:
                signal_strength = "FUERTE"
            else:
                signal_strength = "MODERADA"

            rationale_items.append(f"La opcion cotiza con un DESCUENTO teorico del {abs(edge_pct):.2f}% respecto al modelo BSM.")
            if iv is not None:
                if vol_spread < -0.02:
                    rationale_items.append(f"Volatilidad Implicita ({iv*100:.1f}%) < Volatilidad Historica ({hv*100:.1f}%): Mercado subvalorando el riesgo.")
                else:
                    rationale_items.append(f"Volatilidad Implicita cotiza en {iv*100:.1f}%.")
            rationale_items.append(f"Probabilidad estadistica neutral de finalizar ITM: {prob_itm:.1f}%.")

        elif edge_pct <= -edge_threshold_pct:
            # Sobrevalorada en el mercado -> VENTA / LANZAMIENTO (SHORT)
            action = f"VENTA / LANZAMIENTO RECOMENDADO (SHORT {'CALL' if is_call else 'PUT'})"
            color = "#F43F5E"  # Rose
            if edge_pct < -12.0:
                signal_strength = "MUY FUERTE"
            elif edge_pct < -7.0:
                signal_strength = "FUERTE"
            else:
                signal_strength = "MODERADA"

            rationale_items.append(f"La prima cotiza con un SOBREPRECIO del {abs(edge_pct):.2f}% sobre el valor teorico justo.")
            if iv is not None:
                if vol_spread > 0.02:
                    rationale_items.append(f"Volatilidad Implicita ({iv*100:.1f}%) > Volatilidad Historica ({hv*100:.1f}%): Prima inflada, oportunidad de capturar theta.")
                else:
                    rationale_items.append(f"Volatilidad Implicita cotiza en {iv*100:.1f}%.")
            rationale_items.append(f"Estrategia sugerida: Vender la prima para cobrar valor tiempo o evitar compra directa.")

        else:
            action = "PRECIO JUSTO / MANTENER"
            color = "#38BDF8"  # Sky
            signal_strength = "EQUILIBRADO"
            rationale_items.append(f"La prima de mercado esta alineada al valor teorico (desvio minimo de {edge_pct:+.2f}%).")
            rationale_items.append("El mercado refleja eficientemente la volatilidad esperada sin arbitraje evidente.")

        return {
            "action": action,
            "signal_strength": signal_strength,
            "color": color,
            "edge_pct": round(float(edge_pct), 2),
            "theoretical_price": round(float(theoretical_price), 4),
            "market_price": round(float(market_price), 4),
            "prob_itm_pct": round(float(prob_itm), 1),
            "vol_spread_pct": round(float(vol_spread * 100), 2),
            "rationale": rationale_items
        }
