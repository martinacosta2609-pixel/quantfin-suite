"""
ECONOMETRICS MODULE - Diagnostic Suite & Historical Backtesting
Calculo riguroso de errores de estimacion de Black-Scholes-Merton y Black-76:
- RMSE, MAE, MAPE, Sesgo sistematico (Mean Bias)
- Test de Normalidad de Jarque-Bera (Asimetria y Curtosis)
- Test de Autocorrelacion de Durbin-Watson
- Distribucion de residuos vs Campana Gaussiana
- Curva de Sonrisa de Volatilidad (Volatility Smile Mispricing)
"""

import numpy as np
import pandas as pd
from scipy.stats import norm, jarque_bera, skew, kurtosis
from typing import Dict, Any, List, Optional
from backend.quant_engine import QuantEngine


class EconometricValidator:
    @staticmethod
    def _terminal_position(index: pd.DatetimeIndex, pos: int, horizon_days: int):
        """
        Posicion de la ultima rueda con fecha <= fecha(pos) + horizon_days (dias calendario).
        Devuelve (posicion, horizonte_efectivo_en_dias); posicion es None si el futuro disponible
        es demasiado corto (< 5 dias) para verificar el resultado.
        """
        start = index[pos]
        target = start + pd.Timedelta(days=horizon_days)
        last = index[-1]
        if target > last:
            horizon_days = (last - start).days
            target = last
        term = int(index.searchsorted(target, side="right")) - 1
        if term <= pos or horizon_days < 5:
            return None, horizon_days
        return term, horizon_days

    @classmethod
    def run_historical_test(
        cls,
        history_df: pd.DataFrame,
        target_date: str,
        option_type: str = "call",
        moneyness: float = 1.0,           # K / S ratio (e.g. 1.0 = ATM, 1.05 = OTM Call, 0.95 = ITM Call)
        horizon_days: int = 30,           # Dias al vencimiento (T = horizon / 365)
        window_days: int = 90,            # Ventana historica previa para estimar sigma (sin lookahead bias)
        vol_estimator: str = "garman_klass", # 'realized', 'parkinson', 'garman_klass'
        model: str = "black76",           # 'black76' o 'bsm'
        risk_free_rate: float = 0.04
    ) -> Dict[str, Any]:
        """
        Ejecuta el test econometrico en la fecha pasada elegida (target_date),
        calculando el valor con datos estrictamente anteriores a esa fecha,
        y comparandolo contra la trayectoria y resultado real del mercado.
        """
        if history_df.empty or len(history_df) < (window_days + horizon_days + 10):
            return {"error": "Datos historicos insuficientes para la ventana solicitada."}

        # Asegurar formato de fechas
        df = history_df.copy()
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        
        # Eliminar timezone para comparacion limpia
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)

        target_dt = pd.to_datetime(target_date)

        # Encontrar la fecha de negociacion mas cercana o igual a target_date
        past_dates = df.index[df.index <= target_dt]
        if len(past_dates) < window_days:
            return {"error": f"No hay suficientes datos antes del {target_date} para una ventana de {window_days} dias."}

        t0_idx = past_dates[-1]
        t0_pos = df.index.get_loc(t0_idx)

        # El horizonte se mide en dias CALENDARIO (igual que T = dias / 365 en la formula).
        # Si no hay futuro suficiente, se trunca al maximo disponible.
        term_pos, horizon_days = cls._terminal_position(df.index, t0_pos, horizon_days)
        if term_pos is None:
            return {"error": "La fecha elegida es demasiado reciente para verificar el resultado a vencimiento."}

        # 1. MUESTRA ESTRICTAMENTE PREVIA A t0 (Ventana de estimacion)
        est_df = df.iloc[max(0, t0_pos - window_days): t0_pos]
        
        # 2. PRECIO SUBYACENTE / FUTURO EN t0
        S_t0 = float(df['Close'].iloc[t0_pos])
        K = round(float(S_t0 * moneyness), 2)
        T = horizon_days / 365.0

        # 3. ESTIMACION ECONOMETRICA DE SIGMA CON DATOS ANTERIORES A t0
        close_est = est_df['Close'].to_numpy()
        high_est = est_df['High'].to_numpy() if 'High' in est_df else close_est
        low_est = est_df['Low'].to_numpy() if 'Low' in est_df else close_est
        open_est = est_df['Open'].to_numpy() if 'Open' in est_df else close_est

        if vol_estimator == "parkinson":
            sigma_hat = QuantEngine.estimate_parkinson_volatility(high_est, low_est)
        elif vol_estimator == "garman_klass":
            sigma_hat = QuantEngine.estimate_garman_klass_volatility(open_est, high_est, low_est, close_est)
        else:
            sigma_hat = QuantEngine.estimate_historical_volatility(close_est)

        # Evitar ceros patologicos
        sigma_hat = max(0.01, min(sigma_hat, 2.5))

        # 4. VALOR TEORICO ESTIMADO EN t0
        if model.lower() == "black76":
            theo_val_t0 = QuantEngine.black76_price(S_t0, K, T, risk_free_rate, sigma_hat, option_type)
        else:
            theo_val_t0 = QuantEngine.bsm_price(S_t0, K, T, risk_free_rate, sigma_hat, 0.0, option_type)

        greeks_t0 = QuantEngine.calculate_greeks(S_t0, K, T, risk_free_rate, sigma_hat, 0.0, model, option_type)

        # 5. TRAYECTORIA REAL DEL SUBYACENTE POSTERIOR A t0
        post_df = df.iloc[t0_pos: term_pos + 1]
        dates_post = [d.strftime("%Y-%m-%d") for d in post_df.index]
        prices_post = post_df['Close'].tolist()
        
        S_terminal = float(prices_post[-1])
        
        # Payoff terminal real a vencimiento
        is_call = option_type.lower() == "call"
        payoff_terminal = max(0.0, (S_terminal - K) if is_call else (K - S_terminal))
        # Payoff terminal descontado a valor presente de t0
        realized_discounted_payoff = float(payoff_terminal * np.exp(-risk_free_rate * T))

        # Error puntual en t0
        punctual_error = realized_discounted_payoff - theo_val_t0
        punctual_pct_error = (punctual_error / theo_val_t0 * 100.0) if theo_val_t0 > 0.01 else 0.0

        # 6. BACKTEST RODANTE (ROLLING RESIDUALS) EN LA VENTANA HISTORICA
        # Para generar metricas econometricas solidas (RMSE, MAE, Jarque-Bera, Durbin-Watson),
        # simulamos la estimacion en cada dia de los ultimos N dias previos a t0
        rolling_results = cls._compute_rolling_residuals(
            df=df,
            end_pos=t0_pos,
            horizon_days=horizon_days,
            window_days=window_days,
            moneyness=moneyness,
            option_type=option_type,
            model=model,
            vol_estimator=vol_estimator,
            risk_free_rate=risk_free_rate
        )

        return {
            "target_date": t0_idx.strftime("%Y-%m-%d"),
            "underlying_at_t0": round(S_t0, 2),
            "strike_K": round(K, 2),
            "moneyness_ratio": round(moneyness, 3),
            "horizon_days": horizon_days,
            "window_days": window_days,
            "vol_estimator": vol_estimator,
            "sigma_hat_pct": round(sigma_hat * 100.0, 2),
            "risk_free_rate_pct": round(risk_free_rate * 100.0, 2),
            "theoretical_price_t0": round(theo_val_t0, 4),
            "terminal_price_ST": round(S_terminal, 2),
            "payoff_terminal": round(payoff_terminal, 4),
            "realized_discounted_payoff": round(realized_discounted_payoff, 4),
            "punctual_error": round(punctual_error, 4),
            "punctual_pct_error": round(punctual_pct_error, 2),
            "greeks_t0": greeks_t0,
            "path_dates": dates_post,
            "path_prices": [round(p, 2) for p in prices_post],
            "rolling_diagnostics": rolling_results
        }

    @classmethod
    def _compute_rolling_residuals(
        cls,
        df: pd.DataFrame,
        end_pos: int,
        horizon_days: int,
        window_days: int,
        moneyness: float,
        option_type: str,
        model: str,
        vol_estimator: str,
        risk_free_rate: float,
        sample_size: int = 60
    ) -> Dict[str, Any]:
        """
        Calcula la serie de residuos econometricos e_t = Realizado_t - Estimado_t
        y ejecuta los contrastes estadisticos de diagnostico (RMSE, MAE, Jarque-Bera, Durbin-Watson).
        """
        errors = []
        pct_errors = []
        theoretical_series = []
        realized_series = []
        dates_series = []

        is_call = option_type.lower() == "call"
        T = horizon_days / 365.0

        # Rango de indices para el rolling test
        start_eval = max(window_days, end_pos - sample_size)
        step = max(1, (end_pos - start_eval) // 50)

        last_date = df.index[-1]
        horizon_td = pd.Timedelta(days=horizon_days)

        for i in range(start_eval, end_pos, step):
            target_date = df.index[i] + horizon_td
            if target_date > last_date:
                break
            term_i = int(df.index.searchsorted(target_date, side="right")) - 1

            # Estimacion con datos estrictamente anteriores a i
            sub_est = df.iloc[i - window_days: i]
            c = sub_est['Close'].to_numpy()
            h = sub_est['High'].to_numpy() if 'High' in sub_est else c
            l = sub_est['Low'].to_numpy() if 'Low' in sub_est else c
            o = sub_est['Open'].to_numpy() if 'Open' in sub_est else c

            if vol_estimator == "parkinson":
                sig = QuantEngine.estimate_parkinson_volatility(h, l)
            elif vol_estimator == "garman_klass":
                sig = QuantEngine.estimate_garman_klass_volatility(o, h, l, c)
            else:
                sig = QuantEngine.estimate_historical_volatility(c)

            sig = max(0.01, min(sig, 2.5))

            S_i = float(df['Close'].iloc[i])
            K_i = S_i * moneyness

            if model.lower() == "black76":
                theo = QuantEngine.black76_price(S_i, K_i, T, risk_free_rate, sig, option_type)
            else:
                theo = QuantEngine.bsm_price(S_i, K_i, T, risk_free_rate, sig, 0.0, option_type)

            S_term = float(df['Close'].iloc[term_i])
            payoff = max(0.0, (S_term - K_i) if is_call else (K_i - S_term))
            realized = payoff * np.exp(-risk_free_rate * T)

            err = realized - theo
            errors.append(err)
            if theo > 0.01:
                pct_errors.append((err / theo) * 100.0)

            theoretical_series.append(round(theo, 2))
            realized_series.append(round(realized, 2))
            dates_series.append(df.index[i].strftime("%Y-%m-%d"))

        errors_arr = np.array(errors)
        if len(errors_arr) < 5:
            return {
                "sample_points": len(errors_arr),
                "rmse": 0.0,
                "mae": 0.0,
                "mean_bias": 0.0,
                "jarque_bera_stat": 0.0,
                "jarque_bera_pvalue": 1.0,
                "durbin_watson": 2.0,
                "skewness": 0.0,
                "kurtosis": 3.0,
                "histogram_bins": [],
                "histogram_counts": [],
                "dates": dates_series,
                "theor_series": theoretical_series,
                "real_series": realized_series,
                "residuals": [round(float(e), 2) for e in errors]
            }

        # Metricas econometricas
        rmse = float(np.sqrt(np.mean(errors_arr ** 2)))
        mae = float(np.mean(np.abs(errors_arr)))
        mape = float(np.mean(np.abs(pct_errors))) if pct_errors else 0.0
        mean_bias = float(np.mean(errors_arr))  # Sesgo: si es negativo, BSM sobreestima el precio de la opcion!

        # Asimetria y Curtosis
        sk = float(skew(errors_arr))
        kt = float(kurtosis(errors_arr, fisher=False))  # Pearson kurtosis (normal = 3)

        # Test de Jarque-Bera
        jb_stat, jb_pvalue = jarque_bera(errors_arr)

        # Estadistico de Durbin-Watson para autocorrelacion de residuos
        diff_err = np.diff(errors_arr)
        dw_stat = float(np.sum(diff_err ** 2) / np.sum(errors_arr ** 2)) if np.sum(errors_arr ** 2) > 1e-9 else 2.0

        # Histograma de distribucion de residuos para el frontend
        counts, bin_edges = np.histogram(errors_arr, bins=12)
        bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])

        # Densidad teorica normal para comparar colas pesadas
        normal_curve = norm.pdf(bin_centers, loc=mean_bias, scale=np.std(errors_arr)) * len(errors_arr) * (bin_edges[1] - bin_edges[0])

        return {
            "sample_points": len(errors_arr),
            "rmse": round(rmse, 4),
            "mae": round(mae, 4),
            "mape": round(mape, 2),
            "mean_bias": round(mean_bias, 4),
            "skewness": round(sk, 3),
            "kurtosis": round(kt, 3),
            "jarque_bera_stat": round(float(jb_stat), 2),
            "jarque_bera_pvalue": round(float(jb_pvalue), 4),
            "is_normal": bool(jb_pvalue > 0.05),
            "durbin_watson": round(dw_stat, 3),
            "autocorrelation_status": (
                "Sin autocorrelacion sustancial (DW ~ 2)" if 1.7 <= dw_stat <= 2.3
                else ("Autocorrelacion positiva (DW < 1.7)" if dw_stat < 1.7 else "Autocorrelacion negativa (DW > 2.3)")
            ),
            "hist_labels": [round(float(b), 2) for b in bin_centers],
            "hist_counts": [int(c) for c in counts],
            "hist_normal_fit": [round(float(n), 2) for n in normal_curve],
            "dates": dates_series,
            "theor_series": theoretical_series,
            "real_series": realized_series,
            "residuals": [round(float(e), 2) for e in errors]
        }
