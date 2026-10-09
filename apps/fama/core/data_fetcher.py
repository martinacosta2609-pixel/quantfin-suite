import io
import json
import logging
import os
import threading
import time
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Dict, Iterable, Optional

import numpy as np
import pandas as pd
import yfinance as yf

from core.cache import TTLCache

log = logging.getLogger(__name__)

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data_cache")
FACTORS_FILE = "fama_french_factors_combined.csv"
META_FILE = "factors_meta.json"

_FRENCH_BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp"
KENNETH_FRENCH_URLS = {
    "ff5_daily": f"{_FRENCH_BASE}/F-F_Research_Data_5_Factors_2x3_daily_CSV.zip",
    "mom_daily": f"{_FRENCH_BASE}/F-F_Momentum_Factor_daily_CSV.zip",
}

OFFICIAL_TTL = 7 * 86400   # los datos oficiales se publican una vez por mes
PROXY_TTL = 6 * 3600       # los días recientes se re-estiman con ETFs cada pocas horas
STOCK_TTL = 10 * 60
INFO_TTL = 30 * 60

# ETFs usados para estimar los días que Kenneth French aún no publicó.
PROXY_ETFS = ["SPY", "IWM", "IWN", "IWO", "MTUM", "QUAL"]
FACTOR_COLUMNS = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "RF", "MOM"]


class DataFetcher:
    def __init__(self, cache_dir: str = CACHE_DIR):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        self._factors_cache: Optional[pd.DataFrame] = None
        self._factors_lock = threading.Lock()
        self._stock_cache = TTLCache(STOCK_TTL, maxsize=64)
        self._info_cache = TTLCache(INFO_TTL, maxsize=512)

    # ------------------------------------------------------------------ #
    # Factores de Kenneth French
    # ------------------------------------------------------------------ #
    @staticmethod
    def _download_bytes(url: str, attempts: int = 3, timeout: int = 20) -> bytes:
        last_error: Optional[Exception] = None
        for attempt in range(attempts):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return resp.read()
            except Exception as exc:
                last_error = exc
                time.sleep(0.6 * (attempt + 1))
        raise RuntimeError(f"No se pudo descargar {url}: {last_error}")

    def _fetch_zip_csv(self, url: str) -> pd.DataFrame:
        content = self._download_bytes(url)
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            with z.open(z.namelist()[0]) as f:
                lines = f.readlines()

        header_idx = 0
        for idx, line in enumerate(lines[:30]):
            decoded = line.decode("utf-8", errors="ignore").strip()
            if "Mkt-RF" in decoded or decoded.startswith(",Mom"):
                header_idx = idx
                break

        df = pd.read_csv(io.BytesIO(b"".join(lines[header_idx:])))
        df.columns = [c.strip() for c in df.columns]
        df = df.rename(columns={df.columns[0]: "Date"})
        df = df[df["Date"].astype(str).str.strip().str.match(r"^\d{8}$")].copy()
        df["Date"] = pd.to_datetime(df["Date"].astype(str).str.strip(), format="%Y%m%d")

        value_cols = [c for c in df.columns if c != "Date"]
        df[value_cols] = df[value_cols].apply(pd.to_numeric, errors="coerce") / 100.0
        return df.dropna().sort_values("Date").reset_index(drop=True)

    def _download_official(self) -> pd.DataFrame:
        ff5 = self._fetch_zip_csv(KENNETH_FRENCH_URLS["ff5_daily"])
        try:
            mom = self._fetch_zip_csv(KENNETH_FRENCH_URLS["mom_daily"]).rename(columns={"Mom": "MOM"})
            merged = ff5.merge(mom[["Date", "MOM"]], on="Date", how="left")
        except Exception as exc:
            log.warning("Momentum no disponible, se usa 0: %s", exc)
            merged = ff5.copy()
            merged["MOM"] = 0.0
        merged["MOM"] = merged["MOM"].fillna(0.0)
        merged["Is_Proxy"] = False
        return merged

    def _read_meta(self) -> dict:
        try:
            with open(os.path.join(self.cache_dir, META_FILE), "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _write_factors(self, df: pd.DataFrame, meta: dict) -> None:
        """Escritura atómica: nunca deja un CSV a medias si la app se cierra."""
        cache_file = os.path.join(self.cache_dir, FACTORS_FILE)
        tmp_file = cache_file + ".tmp"
        df.to_csv(tmp_file, index=False)
        os.replace(tmp_file, cache_file)
        meta_file = os.path.join(self.cache_dir, META_FILE)
        with open(meta_file + ".tmp", "w", encoding="utf-8") as f:
            json.dump(meta, f)
        os.replace(meta_file + ".tmp", meta_file)

    def _read_cached_factors(self) -> Optional[pd.DataFrame]:
        cache_file = os.path.join(self.cache_dir, FACTORS_FILE)
        if not os.path.exists(cache_file):
            return None
        try:
            df = pd.read_csv(cache_file, parse_dates=["Date"])
        except Exception as exc:
            log.warning("Caché de factores ilegible: %s", exc)
            return None
        if "Is_Proxy" not in df.columns:
            # Cachés antiguos: los proxies eran filas con RMW=CMA=0 posteriores al último dato oficial.
            real = df.loc[~((df["RMW"] == 0) & (df["CMA"] == 0)), "Date"]
            last_real = real.max() if not real.empty else df["Date"].max()
            df["Is_Proxy"] = df["Date"] > last_real
        df["Is_Proxy"] = df["Is_Proxy"].astype(bool)
        return df

    def get_fama_french_factors(self, force_refresh: bool = False) -> pd.DataFrame:
        """
        Devuelve factores diarios FF5 + Momentum. Los datos oficiales se cachean 7 días;
        los días recientes aún no publicados se re-estiman con ETFs cada 6 horas.
        """
        with self._factors_lock:
            now = time.time()
            cached = self._read_cached_factors()
            cache_file = os.path.join(self.cache_dir, FACTORS_FILE)
            meta = self._read_meta()
            if cached is not None and not meta:
                mtime = os.path.getmtime(cache_file)
                # Caché heredada: los datos oficiales valen, pero sus proxies eran aproximaciones viejas.
                meta = {"official_ts": mtime, "proxy_ts": 0}

            official_fresh = (
                cached is not None
                and not force_refresh
                and now - meta.get("official_ts", 0) < OFFICIAL_TTL
            )

            if official_fresh:
                if now - meta.get("proxy_ts", 0) < PROXY_TTL:
                    self._factors_cache = cached
                    return cached
                official = cached[~cached["Is_Proxy"]].reset_index(drop=True)
                df = self._append_recent_proxies(official)
                meta["proxy_ts"] = now
                self._write_factors(df, meta)
                self._factors_cache = df
                return df

            try:
                official = self._download_official()
                df = self._append_recent_proxies(official)
                self._write_factors(df, {"official_ts": now, "proxy_ts": now})
                self._factors_cache = df
                return df
            except Exception as exc:
                if cached is not None:
                    log.warning("Sin conexión con Dartmouth, se usa la caché local: %s", exc)
                    self._factors_cache = cached
                    return cached
                raise RuntimeError(f"Error descargando factores de Kenneth French: {exc}") from exc

    def factors_status(self, df: pd.DataFrame) -> dict:
        proxy_mask = df["Is_Proxy"] if "Is_Proxy" in df.columns else pd.Series(False, index=df.index)
        official = df.loc[~proxy_mask, "Date"]
        return {
            "latest_date": df["Date"].max().strftime("%Y-%m-%d"),
            "earliest_date": df["Date"].min().strftime("%Y-%m-%d"),
            "observations": int(len(df)),
            "last_official_date": official.max().strftime("%Y-%m-%d") if not official.empty else None,
            "proxy_days": int(proxy_mask.sum()),
        }

    def _append_recent_proxies(self, official: pd.DataFrame) -> pd.DataFrame:
        """
        Kenneth French publica con meses de rezago. Para los días faltantes se estiman factores con ETFs:
          Mkt-RF = SPY - Rf        SMB = IWM - SPY        HML = IWN - IWO
          RMW    = QUAL - SPY      MOM = MTUM - SPY       CMA = 0 (no existe un ETF razonable)
        Las filas quedan marcadas con Is_Proxy=True para que la interfaz pueda advertirlo.
        """
        last_official = official["Date"].max()
        if (datetime.now() - last_official).days <= 3:
            return official

        try:
            start = (last_official - timedelta(days=7)).strftime("%Y-%m-%d")
            raw = yf.download(PROXY_ETFS + ["^IRX"], start=start, progress=False, auto_adjust=True)
            if raw.empty or "Close" not in raw:
                return official

            closes = raw["Close"].sort_index()
            closes.index = pd.to_datetime(closes.index).tz_localize(None).normalize()
            rets = closes[[c for c in PROXY_ETFS if c in closes.columns]].pct_change()
            if "SPY" not in rets or "IWM" not in rets:
                return official

            if "^IRX" in closes:
                rf = closes["^IRX"].ffill().bfill() / 100.0 / 252.0
            else:
                rf = pd.Series(0.04 / 252.0, index=rets.index)

            spy = rets["SPY"]
            proxy = pd.DataFrame(index=rets.index)
            proxy["Mkt-RF"] = spy - rf
            proxy["SMB"] = rets["IWM"] - spy
            proxy["HML"] = rets["IWN"] - rets["IWO"] if {"IWN", "IWO"} <= set(rets.columns) else 0.0
            proxy["RMW"] = (rets["QUAL"] - spy) if "QUAL" in rets else 0.0
            proxy["CMA"] = 0.0
            proxy["RF"] = rf
            proxy["MOM"] = (rets["MTUM"] - spy) if "MTUM" in rets else 0.0

            proxy = proxy[proxy.index > last_official].dropna(subset=["Mkt-RF", "SMB", "HML"])
            proxy = proxy.fillna(0.0)
            if proxy.empty:
                return official

            proxy = proxy.rename_axis("Date").reset_index()
            proxy["Is_Proxy"] = True
            proxy = proxy[["Date"] + FACTOR_COLUMNS + ["Is_Proxy"]]
            return pd.concat([official, proxy], ignore_index=True).sort_values("Date").reset_index(drop=True)
        except Exception as exc:
            log.warning("No se pudieron estimar los factores recientes con ETFs: %s", exc)
            return official

    # ------------------------------------------------------------------ #
    # Acciones
    # ------------------------------------------------------------------ #
    @staticmethod
    def _fetch_history(ticker: str, start_date, end_date, period: str) -> pd.DataFrame:
        t = yf.Ticker(ticker)
        if start_date:
            hist = t.history(start=start_date, end=end_date, auto_adjust=True)
        else:
            hist = t.history(period=period, auto_adjust=True)
        if hist.empty:
            raise ValueError(f"No se encontraron datos de cotización para el símbolo: '{ticker}'")
        hist.index = pd.to_datetime(hist.index.date)
        hist.index.name = "Date"
        hist["Return"] = hist["Close"].pct_change()
        return hist

    @staticmethod
    def _dividend_yield_fraction(raw_info: dict, price: float) -> float:
        """Yahoo devuelve dividendYield en PORCENTAJE (0.32 = 0,32 %). Se normaliza a fracción."""
        rate = raw_info.get("dividendRate")
        if rate and price and price > 0:
            return float(rate) / float(price)
        pct = raw_info.get("dividendYield")
        return float(pct) / 100.0 if pct else 0.0

    def _build_info(self, ticker: str, raw_info: Optional[dict], hist: Optional[pd.DataFrame]) -> dict:
        last_close = float(hist["Close"].iloc[-1]) if hist is not None and not hist.empty else 0.0
        raw = raw_info or {}
        price = float(raw.get("currentPrice") or raw.get("regularMarketPrice") or last_close)
        return {
            "shortName": raw.get("shortName") or raw.get("longName") or ticker,
            "symbol": ticker,
            "sector": raw.get("sector") or "US Equity",
            "industry": raw.get("industry") or "N/A",
            "currentPrice": price,
            "marketCap": raw.get("marketCap", 0),
            "trailingPE": raw.get("trailingPE"),
            "forwardPE": raw.get("forwardPE"),
            "dividendYield": self._dividend_yield_fraction(raw, price),
            "fiftyTwoWeekHigh": raw.get("fiftyTwoWeekHigh") or (float(hist["Close"].max()) if hist is not None else None),
            "fiftyTwoWeekLow": raw.get("fiftyTwoWeekLow") or (float(hist["Close"].min()) if hist is not None else None),
            "currency": raw.get("currency", "USD"),
            "exchange": raw.get("exchange", "US Market"),
        }

    def _fetch_raw_info(self, ticker: str) -> dict:
        cached = self._info_cache.get(ticker)
        if cached is not None:
            return cached
        raw = yf.Ticker(ticker).info or {}
        self._info_cache.set(ticker, raw)
        return raw

    def get_stock_data(self, ticker: str, start_date: str = None, end_date: str = None, period: str = "5y") -> dict:
        """Historial de precios + ficha de la compañía. Descarga ambos en paralelo y cachea 10 minutos."""
        ticker_clean = ticker.strip().upper()
        key = (ticker_clean, start_date, end_date, period)
        cached = self._stock_cache.get(key)
        if cached is not None:
            return cached

        with ThreadPoolExecutor(max_workers=2) as pool:
            hist_future = pool.submit(self._fetch_history, ticker_clean, start_date, end_date, period)
            info_future = pool.submit(self._fetch_raw_info, ticker_clean)
            hist = hist_future.result()
            try:
                raw_info = info_future.result()
            except Exception:
                # Típico en arranque en frío: la cookie/crumb de Yahoo aún no existía. Un reintento ya la encuentra.
                try:
                    raw_info = self._fetch_raw_info(ticker_clean)
                except Exception as exc:
                    log.warning("Sin ficha de compañía para %s: %s", ticker_clean, exc)
                    raw_info = None

        result = {"ticker": ticker_clean, "info": self._build_info(ticker_clean, raw_info, hist), "history": hist}
        self._stock_cache.set(key, result)
        return result

    def get_valuation_snapshot(self, symbols: Iterable[str], max_workers: int = 8) -> Dict[str, dict]:
        """P/E y dividend yield de varias acciones, consultados en paralelo."""

        def one(sym: str):
            raw = None
            for attempt in range(2):
                try:
                    raw = self._fetch_raw_info(sym)
                    break
                except Exception as exc:
                    if attempt == 1:
                        log.warning("Sin fundamentales para %s: %s", sym, exc)
                    else:
                        time.sleep(0.5)
            if raw is None:
                return sym, {"pe_ratio": None, "dividend_yield": 0.0}
            price = raw.get("currentPrice") or raw.get("regularMarketPrice") or 0.0
            pe = raw.get("trailingPE")
            return sym, {
                "pe_ratio": float(pe) if isinstance(pe, (int, float)) and np.isfinite(pe) and pe > 0 else None,
                "dividend_yield": self._dividend_yield_fraction(raw, price),
            }

        symbols = list(symbols)
        if not symbols:
            return {}
        # La primera consulta inicializa la cookie/crumb de Yahoo; en paralelo desde cero compiten y fallan con 401.
        results = dict([one(symbols[0])])
        rest = symbols[1:]
        if rest:
            with ThreadPoolExecutor(max_workers=min(max_workers, len(rest))) as pool:
                results.update(pool.map(one, rest))
        return results

    def align_stock_and_factors(self, stock_df: pd.DataFrame, ff_df: pd.DataFrame) -> pd.DataFrame:
        """Une retornos de la acción con los factores en las fechas de negociación en común."""
        stock_subset = stock_df[["Close", "Volume", "Return"]].reset_index()
        merged = stock_subset.merge(ff_df, on="Date", how="inner")
        merged = merged.dropna().sort_values("Date").reset_index(drop=True)
        merged["Stock_Excess_Return"] = merged["Return"] - merged["RF"]
        return merged
