"""
MARKET DATA MODULE - Official US and European Commodity Feeds
Conexion con feeds de mercado (CME, NYMEX, CBOT, ICE Europe, Euronext)
a traves de tickers oficiales, tasas libres de riesgo (Treasury T-Bills)
y cadenas de opciones en tiempo real e historicas.

Optimizaciones: el historial OHLCV de cada ticker se descarga UNA sola vez y se comparte entre
cotizacion, grafico, cadena de opciones y backtest; las cadenas de opciones tienen cache TTL; y las
fallas de red se recuerdan unos segundos para no repetir llamadas lentas en cada clic.
"""

import math
import time
import datetime
import threading
import pandas as pd
import yfinance as yf
from typing import Dict, Any, List, Optional, Tuple
from backend.quant_engine import QuantEngine


COMMODITY_CATALOG = [
    # Metales
    {
        "id": "gold",
        "name": "Oro (Gold) COMEX/CME",
        "future_ticker": "GC=F",
        "option_ticker": "GLD",
        "category": "Metales",
        "exchange": "CME / COMEX (USA)",
        "currency": "USD",
        "unit": "USD/oz troy",
        "future_multiplier": 100
    },
    {
        "id": "silver",
        "name": "Plata (Silver) COMEX/CME",
        "future_ticker": "SI=F",
        "option_ticker": "SLV",
        "category": "Metales",
        "exchange": "CME / COMEX (USA)",
        "currency": "USD",
        "unit": "USD/oz troy",
        "future_multiplier": 5000
    },
    {
        "id": "copper",
        "name": "Cobre (Copper) COMEX",
        "future_ticker": "HG=F",
        "option_ticker": "CPER",
        "category": "Metales",
        "exchange": "CME / COMEX (USA)",
        "currency": "USD",
        "unit": "USD/lb",
        "future_multiplier": 25000
    },
    # Energia
    {
        "id": "wti",
        "name": "Petroleo Crudo WTI (NYMEX)",
        "future_ticker": "CL=F",
        "option_ticker": "USO",
        "category": "Energia",
        "exchange": "NYMEX / CME (USA)",
        "currency": "USD",
        "unit": "USD/barril",
        "future_multiplier": 1000
    },
    {
        "id": "brent",
        "name": "Petroleo Crudo Brent (ICE Europe)",
        "future_ticker": "BZ=F",
        "option_ticker": "BNO",
        "category": "Energia",
        "exchange": "ICE Futures Europe (Londres)",
        "currency": "USD",
        "unit": "USD/barril",
        "future_multiplier": 1000
    },
    {
        "id": "natgas",
        "name": "Gas Natural Henry Hub (NYMEX)",
        "future_ticker": "NG=F",
        "option_ticker": "UNG",
        "category": "Energia",
        "exchange": "NYMEX / CME (USA)",
        "currency": "USD",
        "unit": "USD/MMBtu",
        "future_multiplier": 10000
    },
    # Agricultura
    {
        "id": "corn",
        "name": "Maiz (Corn) CBOT",
        "future_ticker": "ZC=F",
        "option_ticker": "CORN",
        "category": "Agricultura",
        "exchange": "CBOT / CME (USA)",
        "currency": "USD",
        "unit": "US cent/bushel",
        "future_multiplier": 5000
    },
    {
        "id": "soybeans",
        "name": "Soja (Soybeans) CBOT",
        "future_ticker": "ZS=F",
        "option_ticker": "SOYB",
        "category": "Agricultura",
        "exchange": "CBOT / CME (USA)",
        "currency": "USD",
        "unit": "US cent/bushel",
        "future_multiplier": 5000
    },
    {
        "id": "wheat",
        "name": "Trigo (Wheat) CBOT",
        "future_ticker": "ZW=F",
        "option_ticker": "WEAT",
        "category": "Agricultura",
        "exchange": "CBOT / CME (USA)",
        "currency": "USD",
        "unit": "US cent/bushel",
        "future_multiplier": 5000
    },
    {
        "id": "coffee",
        "name": "Cafe Arabica (ICE US)",
        "future_ticker": "KC=F",
        "option_ticker": "JO",
        "category": "Agricultura",
        "exchange": "ICE Futures US",
        "currency": "USD",
        "unit": "US cent/lb",
        "future_multiplier": 37500
    }
]

_CATALOG_BY_ID = {c["id"]: c for c in COMMODITY_CATALOG}

# TTLs (segundos)
_TTL_QUOTE = 60
_TTL_HISTORY = 300
_TTL_CHAIN = 60
_TTL_RATE = 1800
_TTL_FAILURE = 45     # una falla de red se recuerda este tiempo para no reintentar en cada clic


def _num(value, default: float = 0.0) -> float:
    """float() tolerante a None / NaN (yfinance devuelve NaN en bid/ask fuera de horario)."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    return default if math.isnan(v) else v


class MarketDataProvider:
    def __init__(self):
        self._cache: Dict[str, Any] = {}
        self._cache_expiry: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._default_r = 0.040  # 4.0% fallback

    # ------------------------------------------------------------------ cache
    def _cget(self, key: str):
        with self._lock:
            if key in self._cache and time.time() < self._cache_expiry.get(key, 0):
                return self._cache[key]
        return None

    def _cset(self, key: str, value: Any, ttl: float):
        with self._lock:
            self._cache[key] = value
            self._cache_expiry[key] = time.time() + ttl

    # ----------------------------------------------------------- tasa libre riesgo
    def get_risk_free_rate(self) -> float:
        """
        Obtiene la tasa libre de riesgo oficial de mercado (13-week Treasury Bill ^IRX).
        """
        cached = self._cget("^IRX")
        if cached is not None:
            return cached

        r = self._default_r
        ttl = _TTL_FAILURE
        try:
            hist = yf.Ticker("^IRX").history(period="5d")
            if not hist.empty:
                candidate = float(hist['Close'].iloc[-1]) / 100.0
                if 0.0001 < candidate < 0.20:
                    r, ttl = candidate, _TTL_RATE
        except Exception:
            pass

        self._cset("^IRX", r, ttl)
        return r

    def get_catalog(self) -> List[Dict[str, Any]]:
        return COMMODITY_CATALOG

    def get_commodity_by_id(self, comm_id: str) -> Optional[Dict[str, Any]]:
        return _CATALOG_BY_ID.get(comm_id)

    # -------------------------------------------------------------- historiales
    def _fetch_ticker_history(self, ticker: str, period: str) -> pd.DataFrame:
        """Descarga OHLCV de un ticker con cache TTL (y cache negativo ante fallas)."""
        key = f"hist_{ticker}_{period}"
        cached = self._cget(key)
        if cached is not None:
            return cached

        df = pd.DataFrame()
        try:
            df = yf.Ticker(ticker).history(period=period)
        except Exception:
            df = pd.DataFrame()

        self._cset(key, df, _TTL_HISTORY if not df.empty else _TTL_FAILURE)
        return df

    def _fetch_history(self, comm: Dict[str, Any], period: str, min_rows: int = 1) -> pd.DataFrame:
        """Historial del futuro; si no hay datos suficientes, cae al ETF asociado."""
        df = self._fetch_ticker_history(comm["future_ticker"], period)
        if df.empty or len(df) < min_rows:
            alt = self._fetch_ticker_history(comm["option_ticker"], period)
            if not alt.empty:
                return alt
        return df

    # ------------------------------------------------------------- cotizacion
    def get_live_quote(self, comm_id: str) -> Dict[str, Any]:
        """
        Obtiene la cotizacion en vivo del contrato de futuros del commodity
        y sus estimadores de volatilidad historica.
        """
        comm = self.get_commodity_by_id(comm_id)
        if not comm:
            return {"error": "Commodity no encontrado"}

        future_ticker = comm["future_ticker"]
        cache_key = f"quote_{future_ticker}"
        cached = self._cget(cache_key)
        if cached is not None:
            return cached

        hist = self._fetch_history(comm, "1y")
        if hist.empty:
            fallback = self._generate_fallback_quote(comm)
            self._cset(cache_key, fallback, _TTL_FAILURE)
            return fallback

        try:
            last_close = float(hist['Close'].iloc[-1])
            prev_close = float(hist['Close'].iloc[-2]) if len(hist) > 1 else last_close
            change = last_close - prev_close
            change_pct = (change / prev_close) * 100.0 if prev_close > 0 else 0.0

            high_day = float(hist['High'].iloc[-1])
            low_day = float(hist['Low'].iloc[-1])
            volume = _num(hist['Volume'].iloc[-1]) if 'Volume' in hist else 0.0

            # Estimaciones de Volatilidad (ventana de 60 ruedas)
            close_arr = hist['Close'].to_numpy()[-60:]
            high_arr = hist['High'].to_numpy()[-60:]
            low_arr = hist['Low'].to_numpy()[-60:]
            open_arr = hist['Open'].to_numpy()[-60:]

            hv_cc = QuantEngine.estimate_historical_volatility(close_arr)
            hv_park = QuantEngine.estimate_parkinson_volatility(high_arr, low_arr)
            hv_gk = QuantEngine.estimate_garman_klass_volatility(open_arr, high_arr, low_arr, close_arr)

            r = self.get_risk_free_rate()

            result = {
                "id": comm["id"],
                "name": comm["name"],
                "ticker": future_ticker,
                "exchange": comm["exchange"],
                "currency": comm["currency"],
                "unit": comm["unit"],
                "price": round(last_close, 2),
                "change": round(change, 2),
                "change_pct": round(change_pct, 2),
                "high_day": round(high_day, 2),
                "low_day": round(low_day, 2),
                "volume": int(volume),
                "last_update": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "risk_free_rate": round(r * 100.0, 2),
                "vol_realized_pct": round(hv_cc * 100.0, 2),
                "vol_parkinson_pct": round(hv_park * 100.0, 2),
                "vol_garman_klass_pct": round(hv_gk * 100.0, 2),
                "is_offline": False
            }
            self._cset(cache_key, result, _TTL_QUOTE)
            return result

        except Exception:
            fallback = self._generate_fallback_quote(comm)
            self._cset(cache_key, fallback, _TTL_FAILURE)
            return fallback

    def get_historical_data(self, comm_id: str, period: str = "2y") -> pd.DataFrame:
        """
        Serie historica OHLCV para backtesting y analisis econometrico.
        """
        comm = self.get_commodity_by_id(comm_id)
        if not comm:
            return pd.DataFrame()
        return self._fetch_history(comm, period, min_rows=50)

    # ------------------------------------------------------- cadena de opciones
    def get_options_chain_data(self, comm_id: str, target_expiry: Optional[str] = None) -> Dict[str, Any]:
        """
        Descarga la cadena de opciones en tiempo real del ETF liquido asociado (GLD, USO, ...)
        y la enriquece con BSM y griegas. Si no hay cadena disponible, genera una cadena
        SIMULADA sobre el futuro con Black-76 (marcada con is_synthetic = True).
        """
        comm = self.get_commodity_by_id(comm_id)
        if not comm:
            return {"error": "Commodity invalido"}

        cache_key = f"chain_{comm_id}_{target_expiry}"
        cached = self._cget(cache_key)
        if cached is not None:
            return cached

        r = self.get_risk_free_rate()
        chain = self._build_live_chain(comm, target_expiry, r)
        if chain is None:
            chain = self._generate_futures_option_chain(comm, r, target_expiry)

        self._cset(cache_key, chain, _TTL_CHAIN)
        return chain

    def _build_live_chain(self, comm: Dict[str, Any], target_expiry: Optional[str], r: float) -> Optional[Dict[str, Any]]:
        opt_ticker = comm["option_ticker"]
        try:
            tk = yf.Ticker(opt_ticker)
            expiries = tk.options
            if not expiries:
                return None

            selected_expiry = target_expiry if (target_expiry and target_expiry in expiries) else expiries[0]
            chain = tk.option_chain(selected_expiry)
            hist = self._fetch_ticker_history(opt_ticker, "6mo")
            if hist.empty:
                return None
            current_spot = float(hist['Close'].iloc[-1])

            # Tiempo al vencimiento T (en anios calendario)
            exp_date = pd.to_datetime(selected_expiry).date()
            days_to_exp = max(1, (exp_date - datetime.date.today()).days)
            T = days_to_exp / 365.0

            # Volatilidad historica base (60 ruedas) del propio ETF. Se usa Close-to-Close y NO Garman-Klass /
            # Parkinson: un ETF solo cotiza en horario bursatil, asi que el grueso del movimiento ocurre en
            # los gaps nocturnos (ej. GLD: GK ~13% vs Close-to-Close ~24%), que los estimadores intradiarios
            # no ven. Los futuros operan ~23 h, por eso en ellos Garman-Klass si es adecuado.
            if len(hist) > 10:
                hv = QuantEngine.estimate_historical_volatility(hist['Close'].to_numpy()[-60:])
            else:
                hv = 0.22

            calls_list = self._process_chain_side(chain.calls, current_spot, T, r, hv, "call")
            puts_list = self._process_chain_side(chain.puts, current_spot, T, r, hv, "put")

            return {
                "commodity_id": comm["id"],
                "underlying_name": comm["name"],
                "ticker": opt_ticker,
                "underlying_ticker": opt_ticker,
                "is_synthetic": False,
                "model": "bsm",
                "vol_estimator": "close_to_close",
                "spot_price": round(current_spot, 2),
                "days_to_expiry": days_to_exp,
                "T": round(T, 4),
                "risk_free_rate_pct": round(r * 100.0, 2),
                "historical_vol_pct": round(hv * 100.0, 2),
                "expirations": list(expiries),
                "current_expiration": selected_expiry,
                "calls": calls_list,
                "puts": puts_list
            }
        except Exception:
            return None

    def _process_chain_side(
        self,
        df: pd.DataFrame,
        S: float,
        T: float,
        r: float,
        hv: float,
        option_type: str
    ) -> List[Dict[str, Any]]:
        """Procesa y enriquece cada contrato de la cadena con BSM, Griegas y evaluacion de prima."""
        items = []

        # Filtrar strikes alrededor de ATM (+- 35%)
        filtered = df[(df['strike'] >= S * 0.65) & (df['strike'] <= S * 1.35)]

        # Prima teorica con la vol. historica como benchmark de precio justo (igual para todos los strikes)
        for row in filtered.to_dict('records'):
            K = _num(row.get('strike'))
            bid = _num(row.get('bid'))
            ask = _num(row.get('ask'))
            last = _num(row.get('lastPrice'))

            mid = (bid + ask) / 2.0 if (bid > 0 and ask > 0) else last
            mkt_iv = _num(row.get('impliedVolatility'))
            vol = int(_num(row.get('volume')))
            oi = int(_num(row.get('openInterest')))

            theo_price = QuantEngine.bsm_price(S, K, T, r, hv, 0.0, option_type)

            # Griegas calculadas con volatilidad de mercado (o hv si no hay iv)
            calc_sigma = mkt_iv if (0.01 < mkt_iv < 3.0) else hv
            greeks = QuantEngine.calculate_greeks(S, K, T, r, calc_sigma, 0.0, "bsm", option_type)

            eval_res = QuantEngine.evaluate_fair_premium(
                market_price=mid,
                theoretical_price=theo_price,
                iv=mkt_iv if mkt_iv > 0.01 else None,
                hv=hv,
                option_type=option_type,
                delta=greeks["delta"],
                d2=greeks["d2"],
                underlying_price=S,
                strike=K
            )

            items.append(self._contract_row(
                K, str(row.get('contractSymbol', '')), bid, ask, last, mid, theo_price,
                eval_res, mkt_iv, greeks, vol, oi
            ))

        return sorted(items, key=lambda x: x["strike"])

    @staticmethod
    def _contract_row(K, symbol, bid, ask, last, mid, theo, eval_res, iv, greeks, volume, open_interest) -> Dict[str, Any]:
        """Fila normalizada de la cadena (misma estructura para cadenas reales y simuladas)."""
        return {
            "strike": round(K, 2),
            "contract_symbol": symbol,
            "bid": round(bid, 2),
            "ask": round(ask, 2),
            "last": round(last, 2),
            "mid": round(mid, 2),
            "theoretical": round(theo, 2),
            "intrinsic": round(eval_res["intrinsic_value"], 2),
            "time_value": round(eval_res["time_value"], 2),
            "diff_amount": round(eval_res["diff_amount"], 2),
            "diff_pct": eval_res["diff_pct"],
            "iv_pct": round(iv * 100.0, 2) if iv and iv > 0 else None,
            "delta": round(greeks["delta"], 3),
            "gamma": round(greeks["gamma"], 4),
            "theta": round(greeks["theta"], 3),
            "vega": round(greeks["vega"], 3),
            "volume": volume,
            "open_interest": open_interest,
            "fair_status": eval_res["valuation_status"],
            "recommendation": eval_res["valuation_status"],
            "edge_pct": eval_res["diff_pct"],
            "rec_color": eval_res["status_color"]
        }

    def _generate_futures_option_chain(
        self,
        comm: Dict[str, Any],
        r: float,
        target_expiry: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Genera una cadena SIMULADA de opciones sobre el futuro, valuada con Black-76 y una sonrisa
        de volatilidad sintetica. Se usa cuando el ETF no tiene opciones disponibles.
        Los precios "de mercado" son modelados (no son cotizaciones reales) y el volumen / open
        interest no existen en una simulacion, por eso se devuelven como None.
        """
        live_q = self.get_live_quote(comm["id"])
        F = live_q.get("price", 100.0)
        hv = (live_q.get("vol_garman_klass_pct", 22.0)) / 100.0

        today = datetime.date.today()
        exp_dates = [
            (today + datetime.timedelta(days=d)).strftime("%Y-%m-%d")
            for d in [14, 30, 60, 90, 180]
        ]
        curr_exp = target_expiry if target_expiry in exp_dates else exp_dates[1]
        days_to_exp = max(1, (datetime.datetime.strptime(curr_exp, "%Y-%m-%d").date() - today).days)
        T = days_to_exp / 365.0

        # Rango de strikes alrededor del precio del futuro (+- 20%)
        step = round(F * 0.02, 1) if F < 500 else round(F * 0.01, 0)
        if step <= 0:
            step = 1.0

        strikes = [round(F + i * step, 1) for i in range(-8, 9)]
        calls: List[Dict[str, Any]] = []
        puts: List[Dict[str, Any]] = []

        for K in strikes:
            # Sonrisa / sesgo de volatilidad sintetico
            moneyness = K / F
            smile_iv = hv + 0.15 * ((moneyness - 1.0) ** 2) - 0.05 * (moneyness - 1.0)
            smile_iv = max(0.08, min(smile_iv, 1.5))

            for side, bucket in (("call", calls), ("put", puts)):
                theo = QuantEngine.black76_price(F, K, T, r, hv, side)
                mkt = QuantEngine.black76_price(F, K, T, r, smile_iv, side)
                greeks = QuantEngine.calculate_greeks(F, K, T, r, smile_iv, 0.0, "black76", side)
                ev = QuantEngine.evaluate_fair_premium(mkt, theo, smile_iv, hv, side, greeks["delta"], greeks["d2"], F, K)
                spread = round(mkt * 0.02, 2)
                bucket.append(self._contract_row(
                    K, f"{comm['id'].upper()}-{side[0].upper()}-{K}",
                    max(0.05, mkt - spread), mkt + spread, mkt, mkt, theo,
                    ev, smile_iv, greeks, None, None
                ))

        return {
            "commodity_id": comm["id"],
            "underlying_name": comm["name"],
            "ticker": comm["future_ticker"],
            "underlying_ticker": comm["future_ticker"],
            "is_synthetic": True,
            "model": "black76",
            "vol_estimator": "garman_klass",
            "spot_price": round(F, 2),
            "days_to_expiry": days_to_exp,
            "T": round(T, 4),
            "risk_free_rate_pct": round(r * 100.0, 2),
            "historical_vol_pct": round(hv * 100.0, 2),
            "expirations": exp_dates,
            "current_expiration": curr_exp,
            "calls": calls,
            "puts": puts
        }

    def _generate_fallback_quote(self, comm: Dict[str, Any]) -> Dict[str, Any]:
        """Cotizacion de referencia (NO en vivo) para cuando cae la conexion."""
        base_prices = {
            "gold": 2650.0, "silver": 31.8, "copper": 4.45, "wti": 71.5,
            "brent": 75.2, "natgas": 2.85, "corn": 420.0, "soybeans": 1030.0,
            "wheat": 585.0, "coffee": 260.0
        }
        p = base_prices.get(comm["id"], 100.0)
        return {
            "id": comm["id"],
            "name": comm["name"],
            "ticker": comm["future_ticker"],
            "exchange": comm["exchange"],
            "currency": comm["currency"],
            "unit": comm["unit"],
            "price": p,
            "change": round(p * 0.004, 2),
            "change_pct": 0.40,
            "high_day": round(p * 1.012, 2),
            "low_day": round(p * 0.988, 2),
            "volume": 45200,
            "last_update": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S (Offline Cache)"),
            "risk_free_rate": 4.05,
            "vol_realized_pct": 19.5,
            "vol_parkinson_pct": 18.8,
            "vol_garman_klass_pct": 19.1,
            "is_offline": True
        }
