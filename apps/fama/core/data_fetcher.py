import os
import io
import time
import zipfile
import urllib.request
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data_cache")

KENNETH_FRENCH_URLS = {
    "ff3_daily": "http://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_daily_CSV.zip",
    "ff5_daily": "http://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_5_Factors_2x3_daily_CSV.zip",
    "mom_daily": "http://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Momentum_Factor_daily_CSV.zip",
}

class DataFetcher:
    def __init__(self, cache_dir=CACHE_DIR):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        self._factors_cache = None

    def _fetch_zip_csv(self, url: str) -> pd.DataFrame:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read()
        z = zipfile.ZipFile(io.BytesIO(content))
        filename = z.namelist()[0]
        with z.open(filename) as f:
            lines = f.readlines()
        
        # Locate header line
        header_idx = 0
        for idx, line in enumerate(lines[:30]):
            decoded = line.decode("utf-8", errors="ignore").strip()
            if decoded.startswith(",Mkt-RF") or decoded.startswith(",Mom") or "Mkt-RF" in decoded:
                header_idx = idx
                break

        df = pd.read_csv(io.BytesIO(b"".join(lines[header_idx:])))
        df.columns = [c.strip() for c in df.columns]
        df = df.rename(columns={df.columns[0]: "Date"})
        # Keep only valid 8-digit date rows YYYYMMDD
        df = df[df["Date"].astype(str).str.strip().str.match(r"^\d{8}$")]
        df["Date"] = pd.to_datetime(df["Date"].astype(str).str.strip(), format="%Y%m%d")
        
        # Convert percentages (e.g. 1.25 -> 0.0125)
        for col in df.columns:
            if col != "Date":
                df[col] = pd.to_numeric(df[col], errors="coerce") / 100.0
                
        df = df.dropna().sort_values("Date").reset_index(drop=True)
        return df

    def get_fama_french_factors(self, force_refresh: bool = False) -> pd.DataFrame:
        """
        Retrieves the merged F-F 5-Factor + Momentum daily dataset from Kenneth French Library.
        Cached locally in CSV/feather format for high performance.
        """
        cache_file = os.path.join(self.cache_dir, "fama_french_factors_combined.csv")
        
        # Check cache validity (7 days)
        if not force_refresh and os.path.exists(cache_file):
            file_mtime = os.path.getmtime(cache_file)
            if time.time() - file_mtime < 7 * 86400:
                try:
                    df = pd.read_csv(cache_file, parse_dates=["Date"])
                    self._factors_cache = df
                    return df
                except Exception:
                    pass

        try:
            # Download 5 factors and momentum
            ff5_df = self._fetch_zip_csv(KENNETH_FRENCH_URLS["ff5_daily"])
            try:
                mom_df = self._fetch_zip_csv(KENNETH_FRENCH_URLS["mom_daily"])
                mom_df = mom_df.rename(columns={"Mom": "MOM"})
                merged = pd.merge(ff5_df, mom_df[["Date", "MOM"]], on="Date", how="left")
            except Exception:
                merged = ff5_df
                merged["MOM"] = 0.0

            # Fill any missing momentum values
            merged["MOM"] = merged["MOM"].fillna(0.0)

            # Check if we need to supplement recent days with market proxies
            merged = self._append_recent_proxies(merged)

            # Save to cache
            merged.to_csv(cache_file, index=False)
            self._factors_cache = merged
            return merged
        except Exception as e:
            if os.path.exists(cache_file):
                return pd.read_csv(cache_file, parse_dates=["Date"])
            raise RuntimeError(f"Error descargando factores de Kenneth French: {str(e)}")

    def _append_recent_proxies(self, ff_df: pd.DataFrame) -> pd.DataFrame:
        """
        Kenneth French library is updated monthly. If today's date is ahead of the last entry,
        estimate factor proxies for the missing recent days using SPY, IWM, IWN, IWO, and ^IRX.
        """
        last_date = ff_df["Date"].max()
        today = datetime.now()
        
        # If last factor date is within 2 days (excluding weekends), no proxy needed
        if (today - last_date).days <= 3:
            return ff_df

        try:
            start_str = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
            tickers = ["SPY", "IWM", "IWN", "IWO", "^IRX"]
            proxies = yf.download(tickers, start=start_str, progress=False)
            if proxies.empty or "Close" not in proxies:
                return ff_df
                
            closes = proxies["Close"].dropna()
            if closes.empty:
                return ff_df

            # Calculate daily returns
            pct = closes.pct_change().dropna()
            if pct.empty:
                return ff_df

            rf_series = closes["^IRX"] / 100.0 / 252.0 if "^IRX" in closes else pd.Series(0.04 / 252.0, index=pct.index)
            
            new_rows = []
            for dt, row in pct.iterrows():
                dt_clean = pd.to_datetime(dt).tz_localize(None)
                if dt_clean <= last_date:
                    continue
                
                rf = float(rf_series.get(dt, 0.04 / 252.0))
                mkt_rf = float(row.get("SPY", 0.0)) - rf
                smb = float(row.get("IWM", 0.0)) - float(row.get("SPY", 0.0))
                hml = float(row.get("IWN", 0.0)) - float(row.get("IWO", 0.0))
                rmw = 0.0  # Quality/profitability neutral proxy
                cma = 0.0  # Investment neutral proxy
                mom = float(row.get("SPY", 0.0)) * 0.5  # Momentum approximation

                new_rows.append({
                    "Date": dt_clean,
                    "Mkt-RF": mkt_rf,
                    "SMB": smb,
                    "HML": hml,
                    "RMW": rmw,
                    "CMA": cma,
                    "RF": rf,
                    "MOM": mom
                })

            if new_rows:
                proxy_df = pd.DataFrame(new_rows)
                combined = pd.concat([ff_df, proxy_df], ignore_index=True).sort_values("Date").reset_index(drop=True)
                return combined
        except Exception:
            pass

        return ff_df

    def get_stock_data(self, ticker: str, start_date: str = None, end_date: str = None, period: str = "5y") -> dict:
        """
        Fetches stock historical prices, volume, and company information from Yahoo Finance.
        """
        ticker_clean = ticker.strip().upper()
        t = yf.Ticker(ticker_clean)
        
        if start_date:
            hist = t.history(start=start_date, end=end_date, auto_adjust=True)
        else:
            hist = t.history(period=period, auto_adjust=True)

        if hist.empty:
            raise ValueError(f"No se encontraron datos de cotización para el símbolo: '{ticker_clean}'")

        # Clean index timezone
        hist.index = pd.to_datetime(hist.index.date)
        hist.index.name = "Date"
        hist["Return"] = hist["Close"].pct_change()

        # Company profile information
        info = {}
        try:
            raw_info = t.info
            info = {
                "shortName": raw_info.get("shortName") or raw_info.get("longName") or ticker_clean,
                "symbol": ticker_clean,
                "sector": raw_info.get("sector", "N/A"),
                "industry": raw_info.get("industry", "N/A"),
                "currentPrice": float(raw_info.get("currentPrice") or raw_info.get("regularMarketPrice") or hist["Close"].iloc[-1]),
                "marketCap": raw_info.get("marketCap", 0),
                "trailingPE": raw_info.get("trailingPE", None),
                "forwardPE": raw_info.get("forwardPE", None),
                "dividendYield": raw_info.get("dividendYield", 0.0),
                "fiftyTwoWeekHigh": raw_info.get("fiftyTwoWeekHigh", hist["Close"].max()),
                "fiftyTwoWeekLow": raw_info.get("fiftyTwoWeekLow", hist["Close"].min()),
                "currency": raw_info.get("currency", "USD"),
                "exchange": raw_info.get("exchange", "US Market")
            }
        except Exception:
            info = {
                "shortName": ticker_clean,
                "symbol": ticker_clean,
                "sector": "US Equity",
                "industry": "N/A",
                "currentPrice": float(hist["Close"].iloc[-1]),
                "marketCap": 0,
                "trailingPE": None,
                "forwardPE": None,
                "dividendYield": 0.0,
                "fiftyTwoWeekHigh": float(hist["Close"].max()),
                "fiftyTwoWeekLow": float(hist["Close"].min()),
                "currency": "USD",
                "exchange": "US Market"
            }

        return {
            "ticker": ticker_clean,
            "info": info,
            "history": hist
        }

    def align_stock_and_factors(self, stock_df: pd.DataFrame, ff_df: pd.DataFrame) -> pd.DataFrame:
        """
        Merges stock price/return history with F-F factors on matching trading dates.
        """
        stock_subset = stock_df[["Close", "Volume", "Return"]].copy()
        stock_subset = stock_subset.reset_index()
        
        merged = pd.merge(stock_subset, ff_df, on="Date", how="inner")
        merged = merged.dropna().sort_values("Date").reset_index(drop=True)
        merged["Stock_Excess_Return"] = merged["Return"] - merged["RF"]
        return merged
