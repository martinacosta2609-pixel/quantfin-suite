"""
Live Market Data & Yahoo Finance Integration
Fetches tabular data only (JSON/DataFrames, strictly no PDFs/unstructured files).
Includes batch sector price sync, live market overview (S&P 500, NASDAQ, US 10Y, VIX),
real 5-year monthly series for econometric auditing, and a 30-second background sync daemon.

Unit convention (same as the seeded database): every monetary aggregate is stored in
USD millions; per-share figures and prices are in USD.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import json
import math
import threading
import time
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
import pandas as pd

from engine.accounting import compute_all_metrics
from engine.monte_carlo import run_monte_carlo_simulation, stable_seed, SimulationError
from engine.database import (
    get_db_connection,
    save_monte_carlo_result,
    get_stock_by_ticker,
    invalidate_cache,
)

MILLION = 1e6
SECTOR_SYNC_TTL = 25.0  # seconds between automatic batch refreshes per sector
MARKET_OVERVIEW_TTL = 25.0  # seconds between automatic index refreshes
HISTORY_SYNC_TTL = 3600.0  # 1 hour cache for 5Y monthly econometric series

# Official SPDR Sector ETFs for each GICS sector
SECTOR_ETFS: Dict[str, str] = {
    "Information Technology": "XLK",
    "Health Care": "XLV",
    "Financials": "XLF",
    "Consumer Discretionary": "XLY",
    "Communication Services": "XLC",
    "Industrials": "XLI",
    "Consumer Staples": "XLP",
    "Energy": "XLE",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Materials": "XLB",
}

_sector_sync_times: Dict[str, float] = {}
_sector_locks: Dict[str, threading.Lock] = {}
_global_sync_lock = threading.Lock()

_history_sync_times: Dict[str, float] = {}

_market_overview_lock = threading.Lock()
_market_overview_cache: Dict[str, Any] = {
    "timestamp": 0.0,
    "data": {
        "sp500": {"price": 5842.47, "change_pct": 0.38},
        "nasdaq": {"price": 18518.61, "change_pct": 0.64},
        "us10y": {"price": 4.08, "change_pct": -0.24},
        "vix": {"price": 18.14, "change_pct": -1.45},
        "updated_at": datetime.now().strftime("%H:%M:%S"),
        "source": "cache",
    },
}

_active_sector_lock = threading.Lock()
_active_sector: str = "Information Technology"
_bg_thread_started = False


def mark_active_sector(sector_name: str) -> None:
    """Records the sector currently viewed by the user so the 30s daemon prioritizes it."""
    global _active_sector
    if sector_name and sector_name.strip():
        with _active_sector_lock:
            _active_sector = sector_name.strip()


def _get_sector_lock(key: str) -> threading.Lock:
    with _global_sync_lock:
        if key not in _sector_locks:
            _sector_locks[key] = threading.Lock()
        return _sector_locks[key]


def _finite(value) -> Optional[float]:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _live_millions(info: Dict[str, Any], *keys: str) -> Optional[float]:
    """First finite value among `keys` of the Yahoo payload (USD), converted to millions."""
    for key in keys:
        v = _finite(info.get(key))
        if v is not None:
            return v / MILLION
    return None


def _first(*values: Optional[float]) -> Optional[float]:
    for v in values:
        if v is not None:
            return v
    return None


def _extract_close_prices(df: pd.DataFrame, tickers: List[str]) -> Dict[str, float]:
    """Extracts the latest non-NaN close price per ticker from a `yf.download` DataFrame."""
    prices: Dict[str, float] = {}
    if df is None or df.empty:
        return prices

    try:
        close_obj = df["Close"] if "Close" in df else df
    except Exception:
        return prices

    if isinstance(close_obj, pd.Series):
        s = close_obj.dropna()
        if not s.empty and len(tickers) == 1:
            val = _finite(s.iloc[-1])
            if val and val > 0:
                prices[tickers[0]] = round(val, 2)
        return prices

    for sym in tickers:
        if sym in close_obj.columns:
            s = close_obj[sym].dropna()
            if not s.empty:
                val = _finite(s.iloc[-1])
                if val and val > 0:
                    prices[sym] = round(val, 2)
    return prices


def get_market_overview(force: bool = False) -> Dict[str, Any]:
    """
    Fetches live market snapshot for S&P 500 (^GSPC), NASDAQ (^IXIC), US 10Y (^TNX), and VIX (^VIX).
    Cached for 25 seconds unless `force=True`.
    """
    now = time.time()
    if not force and (now - _market_overview_cache["timestamp"]) < MARKET_OVERVIEW_TTL:
        return _market_overview_cache["data"]

    with _market_overview_lock:
        now = time.time()
        if not force and (now - _market_overview_cache["timestamp"]) < MARKET_OVERVIEW_TTL:
            return _market_overview_cache["data"]

        symbols = ["^GSPC", "^IXIC", "^TNX", "^VIX"]
        key_map = {
            "^GSPC": "sp500",
            "^IXIC": "nasdaq",
            "^TNX": "us10y",
            "^VIX": "vix",
        }
        try:
            import yfinance as yf

            df = yf.download(
                symbols,
                period="5d",
                interval="1d",
                auto_adjust=True,
                progress=False,
                threads=True,
            )
            if df is not None and not df.empty and "Close" in df:
                close_df = df["Close"]
                updated = dict(_market_overview_cache["data"])
                got_any = False
                for sym, out_key in key_map.items():
                    if sym in close_df.columns:
                        s = close_df[sym].dropna()
                        if len(s) >= 2:
                            last_val = float(s.iloc[-1])
                            prev_val = float(s.iloc[-2])
                            chg = ((last_val - prev_val) / prev_val * 100.0) if prev_val != 0 else 0.0
                            updated[out_key] = {
                                "price": round(last_val, 2),
                                "change_pct": round(chg, 2),
                            }
                            got_any = True
                        elif len(s) == 1:
                            last_val = float(s.iloc[-1])
                            updated[out_key] = {
                                "price": round(last_val, 2),
                                "change_pct": 0.0,
                            }
                            got_any = True
                if got_any:
                    updated["updated_at"] = datetime.now().strftime("%H:%M:%S")
                    updated["source"] = "live"
                    _market_overview_cache["data"] = updated
                    _market_overview_cache["timestamp"] = time.time()
        except Exception as exc:
            print(f"[WARN] Market overview live fetch fallback: {exc}")

        return _market_overview_cache["data"]


def _build_updated_stock_payload(
    ticker_clean: str,
    ex: Dict[str, Any],
    info: Dict[str, Any],
    fallback_price: Optional[float] = None,
) -> Optional[Tuple[Tuple[Any, ...], Dict[str, Any]]]:
    """
    Merges live Yahoo `.info` (and/or `fallback_price`) with existing database row `ex`,
    recomputing accounting quality ratios and 5,000-path Monte Carlo simulation.
    """
    price = (
        _finite(info.get("currentPrice"))
        or _finite(info.get("regularMarketPrice"))
        or _finite(info.get("previousClose"))
        or _finite(fallback_price)
    )
    if not price or price <= 0:
        return None

    price = round(price, 2)
    old_price = _finite(ex.get("market_price")) or price
    price_scale = max(0.25, min(4.0, price / old_price)) if old_price > 0 else 1.0

    def scaled_ex(col: str) -> Optional[float]:
        v = _finite(ex.get(col))
        return round(v * price_scale, 2) if v is not None else None

    shares = _first(
        _live_millions(info, "sharesOutstanding", "impliedSharesOutstanding"),
        _finite(ex.get("shares_outstanding")),
        100.0,
    )
    market_cap = _first(_live_millions(info, "marketCap"), price * shares)

    # Preserve our canonical GICS sector assignment if already in DB
    sector = ex.get("sector") or info.get("sector") or "Information Technology"
    industry = info.get("industry") or ex.get("industry") or "Diversified"
    long_name = ex.get("name") or info.get("shortName") or info.get("longName") or ticker_clean

    ebit_live = _live_millions(info, "operatingIncome", "ebit")
    ebit = _first(ebit_live if (ebit_live is not None and ebit_live > 0) else None, scaled_ex("ebit"), market_cap * 0.08)

    total_debt = _first(_live_millions(info, "totalDebt"), scaled_ex("total_debt"), market_cap * 0.15)
    cash = _first(_live_millions(info, "totalCash"), scaled_ex("cash_and_equivalents"), market_cap * 0.05)

    book_value_ps = _finite(info.get("bookValue"))
    live_equity = (book_value_ps * shares) if (book_value_ps is not None and book_value_ps > 0) else None
    total_equity = _first(live_equity, scaled_ex("total_equity"), market_cap * 0.35)

    ebitda_live = _live_millions(info, "ebitda")
    ebitda = _first(ebitda_live if (ebitda_live is not None and ebitda_live > 0) else None, scaled_ex("ebitda"), ebit * 1.18)

    ocf_live = _live_millions(info, "operatingCashflow")
    ocf = _first(ocf_live if (ocf_live is not None and ocf_live > 0) else None, scaled_ex("operating_cash_flow"), ebit * 0.95)

    fcf_live = _live_millions(info, "freeCashflow")
    if ocf_live is not None and fcf_live is not None and ocf_live > fcf_live:
        capex = max(0.0, ocf_live - fcf_live)
    else:
        capex = _first(scaled_ex("capex"), max(0.0, ocf * 0.25))

    trailing_pe = _finite(info.get("trailingPE"))
    forward_pe = _finite(info.get("forwardPE"))

    eps_ttm_live = _finite(info.get("trailingEps"))
    trailing_eps = _first(
        eps_ttm_live if (eps_ttm_live is not None and eps_ttm_live > 0) else None,
        (price / trailing_pe) if (trailing_pe and trailing_pe > 0) else None,
        scaled_ex("trailing_eps"),
        round(price / 22.0, 2),
    )

    eps_fwd_live = _finite(info.get("forwardEps"))
    forward_eps = _first(
        eps_fwd_live if (eps_fwd_live is not None and eps_fwd_live > 0) else None,
        (price / forward_pe) if (forward_pe and forward_pe > 0) else None,
        scaled_ex("forward_eps"),
        round(trailing_eps * 1.10, 2),
    )

    rev_ps_live = _finite(info.get("revenuePerShare"))
    tot_rev_m = _live_millions(info, "totalRevenue")
    if (rev_ps_live is None or rev_ps_live <= 0) and tot_rev_m and shares > 0:
        rev_ps_live = tot_rev_m / shares
    revenue_ps = _first(
        round(rev_ps_live, 2) if (rev_ps_live is not None and rev_ps_live > 0) else None,
        scaled_ex("revenue_ps"),
        round(price * 0.25, 2),
    )

    tax_rate = _finite(ex.get("tax_rate")) or 0.21
    rev_growth_mean = _first(_finite(ex.get("rev_growth_mean")), 0.08)
    rev_growth_std = _first(_finite(ex.get("rev_growth_std")), 0.05)
    margin_mean = _first(_finite(ex.get("margin_mean")), 0.20)
    margin_std = _first(_finite(ex.get("margin_std")), 0.03)
    reinvestment_rate_mean = _first(_finite(ex.get("reinvestment_rate_mean")), 0.35)

    metrics = compute_all_metrics({
        "market_price": price,
        "shares_outstanding": shares,
        "market_cap": market_cap,
        "ebit": ebit,
        "tax_rate": tax_rate,
        "total_debt": total_debt,
        "total_equity": total_equity,
        "cash_and_equivalents": cash,
        "operating_cash_flow": ocf,
        "capex": capex,
        "ebitda": ebitda,
        "trailing_eps": trailing_eps,
        "forward_eps": forward_eps,
    })

    mc_result = run_monte_carlo_simulation(
        p0=price,
        current_revenue_ps=revenue_ps,
        historical_growth_mean=rev_growth_mean,
        historical_growth_std=rev_growth_std,
        historical_margin_mean=margin_mean,
        historical_margin_std=margin_std,
        tax_rate=tax_rate,
        reinvestment_rate_mean=reinvestment_rate_mean,
        num_simulations=5000,
        random_seed=stable_seed(ticker_clean),
    )

    p10 = mc_result["percentiles"]["p10"]
    p50 = mc_result["percentiles"]["p50"]
    p90 = mc_result["percentiles"]["p90"]

    stock_tuple = (
        ticker_clean,
        long_name,
        sector,
        industry,
        price,
        round(shares, 2),
        metrics["market_cap"],
        round(ebit, 2),
        tax_rate,
        metrics["nopat"],
        round(total_debt, 2),
        round(total_equity, 2),
        round(cash, 2),
        metrics["invested_capital"],
        metrics["roic"],
        round(ocf, 2),
        round(capex, 2),
        metrics["fcf"],
        metrics["fcf_yield"],
         metrics["ebitda"],
        metrics["ev"],
        metrics["ev_ebitda"],
        metrics["net_debt"],
        metrics["net_debt_ebitda"],
        round(trailing_eps, 2),
        round(forward_eps, 2),
        metrics["trailing_pe"],
        metrics["forward_pe"],
        rev_growth_mean,
        rev_growth_std,
        margin_mean,
        margin_std,
        reinvestment_rate_mean,
        round(revenue_ps, 2),
        p10,
        p50,
        p90,
    )
    return stock_tuple, mc_result


def fetch_and_update_stock(ticker: str) -> Dict[str, Any]:
    """
    Fetches real-time market data and financials for a single ticker using yfinance.
    Gracefully handles offline or rate-limited environments.
    """
    ticker_clean = ticker.strip().upper()
    existing = get_stock_by_ticker(ticker_clean)

    def from_cache(message: str) -> Dict[str, Any]:
        return {"success": True, "source": "cache", "message": message, "stock": existing}

    try:
        import yfinance as yf

        info: Dict[str, Any] = {}
        try:
            info = yf.Ticker(ticker_clean).info or {}
        except Exception:
            info = {}

        fallback_price: Optional[float] = None
        if not (_finite(info.get("currentPrice")) or _finite(info.get("regularMarketPrice"))):
            df_p = yf.download([ticker_clean], period="5d", interval="1d", auto_adjust=True, progress=False)
            prices = _extract_close_prices(df_p, [ticker_clean])
            fallback_price = prices.get(ticker_clean)

        built = _build_updated_stock_payload(ticker_clean, existing or {}, info, fallback_price)
        if built is None:
            if existing:
                return from_cache("Datos de mercado obtenidos desde la base local (API ocupada).")
            raise ValueError(f"No fue posible obtener información de mercado para '{ticker_clean}'.")

        stock_tuple, mc_result = built

        with get_db_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO stocks (
                    ticker, name, sector, industry, market_price, shares_outstanding, market_cap,
                    ebit, tax_rate, nopat, total_debt, total_equity, cash_and_equivalents,
                    invested_capital, roic, operating_cash_flow, capex, fcf, fcf_yield,
                    ebitda, ev, ev_ebitda, net_debt, net_debt_ebitda,
                    trailing_eps, forward_eps, trailing_pe, forward_pe,
                    rev_growth_mean, rev_growth_std, margin_mean, margin_std,
                    reinvestment_rate_mean, revenue_ps, mc_p10, mc_p50, mc_p90, last_updated
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, CURRENT_TIMESTAMP
                )
            """, stock_tuple)
            conn.commit()

        save_monte_carlo_result(ticker_clean, mc_result)

        return {
            "success": True,
            "source": "live",
            "message": f"Información de mercado actualizada exitosamente para {ticker_clean}.",
            "stock": get_stock_by_ticker(ticker_clean),
        }

    except Exception as e:
        if existing:
            return from_cache(f"Datos cargados desde base local: {str(e)}")
        return {
            "success": False,
            "source": "error",
            "message": f"Error al consultar API de mercado: {str(e)}",
            "stock": None,
        }


def refresh_sector_stocks(sector_name: str, force: bool = False) -> Dict[str, Any]:
    """
    Batch-refreshes live market prices for all stocks in `sector_name` (or all sectors if 'all')
    using a single vectorized `yf.download` call, then recomputes multiples and Monte Carlo IRRs
    for any stock whose price changed.
    """
    key = "all" if not sector_name or sector_name.strip().lower() == "all" else sector_name.strip()
    mark_active_sector(key)

    now = time.time()
    if not force and (now - _sector_sync_times.get(key, 0.0)) < SECTOR_SYNC_TTL:
        return {"success": True, "source": "cache", "sector": key, "updated_count": 0}

    lock = _get_sector_lock(key)
    with lock:
        now = time.time()
        if not force and (now - _sector_sync_times.get(key, 0.0)) < SECTOR_SYNC_TTL:
            return {"success": True, "source": "cache", "sector": key, "updated_count": 0}

        with get_db_connection() as conn:
            if key == "all":
                rows = [dict(r) for r in conn.execute("SELECT * FROM stocks").fetchall()]
            else:
                rows = [dict(r) for r in conn.execute("SELECT * FROM stocks WHERE sector = ?", (key,)).fetchall()]

        if not rows:
            return {"success": False, "source": "empty", "sector": key, "updated_count": 0}

        tickers = [r["ticker"] for r in rows]
        try:
            import yfinance as yf

            # Download in chunks of up to 100 tickers for reliability
            live_prices: Dict[str, float] = {}
            chunk_size = 100
            for i in range(0, len(tickers), chunk_size):
                chunk = tickers[i : i + chunk_size]
                df = yf.download(
                    chunk,
                    period="5d",
                    interval="1d",
                    auto_adjust=True,
                    progress=False,
                    threads=True,
                )
                live_prices.update(_extract_close_prices(df, chunk))

            if not live_prices:
                _sector_sync_times[key] = time.time()
                return {"success": True, "source": "cache", "sector": key, "updated_count": 0}

            stock_updates: List[Tuple[Any, ...]] = []
            mc_updates: List[Tuple[str, str]] = []

            for r in rows:
                sym = r["ticker"]
                new_price = live_prices.get(sym)
                if not new_price or new_price <= 0:
                    continue
                old_price = _finite(r.get("market_price")) or 0.0
                if not force and abs(new_price - old_price) < 0.005 and r.get("mc_p50") is not None:
                    continue

                shares = _finite(r.get("shares_outstanding")) or 100.0
                tax_rate = _finite(r.get("tax_rate")) or 0.21
                ebit = _finite(r.get("ebit")) or 0.0
                total_debt = _finite(r.get("total_debt")) or 0.0
                total_equity = _finite(r.get("total_equity")) or 0.0
                cash = _finite(r.get("cash_and_equivalents")) or 0.0
                ocf = _finite(r.get("operating_cash_flow")) or 0.0
                capex = _finite(r.get("capex")) or 0.0
                ebitda = _finite(r.get("ebitda")) or 0.0
                trailing_eps = _finite(r.get("trailing_eps"))
                forward_eps = _finite(r.get("forward_eps"))
                revenue_ps = _finite(r.get("revenue_ps")) or (new_price * 0.25)

                metrics = compute_all_metrics({
                    "market_price": new_price,
                    "shares_outstanding": shares,
                    "ebit": ebit,
                    "tax_rate": tax_rate,
                    "total_debt": total_debt,
                    "total_equity": total_equity,
                    "cash_and_equivalents": cash,
                    "operating_cash_flow": ocf,
                    "capex": capex,
                    "ebitda": ebitda,
                    "trailing_eps": trailing_eps,
                    "forward_eps": forward_eps,
                })

                p10 = r.get("mc_p10")
                p50 = r.get("mc_p50")
                p90 = r.get("mc_p90")
                try:
                    mc_res = run_monte_carlo_simulation(
                        p0=new_price,
                        current_revenue_ps=revenue_ps,
                        historical_growth_mean=_first(_finite(r.get("rev_growth_mean")), 0.08),
                        historical_growth_std=_first(_finite(r.get("rev_growth_std")), 0.05),
                        historical_margin_mean=_first(_finite(r.get("margin_mean")), 0.20),
                        historical_margin_std=_first(_finite(r.get("margin_std")), 0.03),
                        tax_rate=tax_rate,
                        reinvestment_rate_mean=_first(_finite(r.get("reinvestment_rate_mean")), 0.35),
                        num_simulations=5000,
                        random_seed=stable_seed(sym),
                    )
                    p10 = mc_res["percentiles"]["p10"]
                    p50 = mc_res["percentiles"]["p50"]
                    p90 = mc_res["percentiles"]["p90"]
                    mc_updates.append((sym, json.dumps(mc_res)))
                except SimulationError:
                    pass

                stock_updates.append((
                    new_price,
                    metrics["market_cap"],
                    metrics["ev"],
                    metrics["ev_ebitda"],
                    metrics["fcf_yield"],
                    metrics["trailing_pe"],
                    metrics["forward_pe"],
                    p10,
                    p50,
                    p90,
                    sym,
                ))

            if stock_updates:
                with get_db_connection() as conn:
                    conn.executemany("""
                        UPDATE stocks SET
                            market_price = ?,
                            market_cap = ?,
                            ev = ?,
                            ev_ebitda = ?,
                            fcf_yield = ?,
                            trailing_pe = ?,
                            forward_pe = ?,
                            mc_p10 = ?,
                            mc_p50 = ?,
                            mc_p90 = ?,
                            last_updated = CURRENT_TIMESTAMP
                        WHERE ticker = ?
                    """, stock_updates)
                    if mc_updates:
                        conn.executemany("""
                            INSERT OR REPLACE INTO monte_carlo_cache (ticker, simulation_json, calculated_at)
                            VALUES (?, ?, CURRENT_TIMESTAMP)
                        """, mc_updates)
                    conn.commit()
                invalidate_cache()

            _sector_sync_times[key] = time.time()
            return {
                "success": True,
                "source": "live",
                "sector": key,
                "updated_count": len(stock_updates),
                "total_checked": len(live_prices),
                "updated_at": datetime.now().strftime("%H:%M:%S"),
            }

        except Exception as exc:
            print(f"[WARN] refresh_sector_stocks({key}) fallback: {exc}")
            return {"success": True, "source": "cache", "sector": key, "updated_count": 0}


def refresh_stock_history_live(ticker: str, force: bool = False) -> bool:
    """
    Downloads real 5-year monthly prices for `[ticker, '^GSPC', sector_etf, '^TNX']` from Yahoo Finance
    and updates `historical_series` in SQLite for econometric auditing.
    Returns True if live series were updated, False if falling back to stored series.
    """
    ticker_clean = ticker.strip().upper()
    now = time.time()
    if not force and (now - _history_sync_times.get(ticker_clean, 0.0)) < HISTORY_SYNC_TTL:
        return True

    stock = get_stock_by_ticker(ticker_clean)
    sector = (stock or {}).get("sector", "Information Technology")
    sector_etf = SECTOR_ETFS.get(sector, "XLK")

    try:
        import yfinance as yf

        symbols = list(dict.fromkeys([ticker_clean, "^GSPC", sector_etf, "^TNX"]))
        df = yf.download(
            symbols,
            period="5y",
            interval="1mo",
            auto_adjust=True,
            progress=False,
            threads=True,
        )
        if df is None or df.empty or "Close" not in df:
            return False

        close_df = df["Close"].dropna(how="all")
        if ticker_clean not in close_df.columns or "^GSPC" not in close_df.columns:
            return False

        sub = pd.DataFrame({
            "stock_price": close_df[ticker_clean],
            "mkt_price": close_df["^GSPC"],
            "sec_price": close_df[sector_etf] if sector_etf in close_df.columns else close_df["^GSPC"],
            "tnx": close_df["^TNX"] if "^TNX" in close_df.columns else 4.0,
        }).dropna(subset=["stock_price", "mkt_price"])

        if len(sub) < 30:
            return False

        sub["tnx"] = sub["tnx"].ffill().bfill().fillna(4.0)
        sub["sec_price"] = sub["sec_price"].ffill().bfill()

        sub["stock_return"] = sub["stock_price"].pct_change()
        sub["market_return"] = sub["mkt_price"].pct_change()
        sub["sector_return"] = sub["sec_price"].pct_change()
        sub["rate_change_10y"] = (sub["tnx"] / 100.0).diff()
        # Monthly risk-free rate derived from annualized 10Y Treasury yield
        rf_monthly = (sub["tnx"].shift(1).fillna(4.0) / 100.0) / 12.0
        sub["stock_excess_return"] = sub["stock_return"] - rf_monthly
        sub["market_excess_return"] = sub["market_return"] - rf_monthly
        sub["sector_excess_return"] = sub["sector_return"] - rf_monthly

        sub = sub.dropna(subset=["stock_return", "market_return", "sector_return", "rate_change_10y"])
        if len(sub) < 25:
            return False

        records = []
        for idx, row in sub.iterrows():
            date_str = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
            records.append((
                ticker_clean,
                date_str,
                round(float(row["stock_price"]), 2),
                round(float(row["stock_return"]), 5),
                round(float(row["market_return"]), 5),
                round(float(row["sector_return"]), 5),
                round(float(row["rate_change_10y"]), 5),
                round(float(row["stock_excess_return"]), 5),
                round(float(row["market_excess_return"]), 5),
                round(float(row["sector_excess_return"]), 5),
            ))

        with get_db_connection() as conn:
            conn.execute("DELETE FROM historical_series WHERE ticker = ?", (ticker_clean,))
            conn.executemany("""
                INSERT INTO historical_series (
                    ticker, date, stock_price, stock_return, market_return,
                    sector_return, rate_change_10y, stock_excess_return,
                    market_excess_return, sector_excess_return
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, records)
            conn.commit()

        _history_sync_times[ticker_clean] = time.time()
        return True
    except Exception as exc:
        print(f"[WARN] refresh_stock_history_live({ticker_clean}) fallback: {exc}")
        return False


def sync_all_stocks_live(max_workers: int = 16) -> Dict[str, Any]:
    """
    Synchronizes live prices and fundamental metrics from Yahoo Finance for every stock
    in the database. Uses a single-ticker warmup call followed by a thread pool to avoid
    Yahoo Finance crumb/cookie race conditions.
    """
    import yfinance as yf

    with get_db_connection() as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM stocks ORDER BY ticker ASC").fetchall()]

    if not rows:
        return {"updated": 0, "total": 0}

    tickers = [r["ticker"] for r in rows]
    row_map = {r["ticker"]: r for r in rows}

    print(f"[LIVE SYNC] Descargando precios actuales en bloque para {len(tickers)} acciones...")
    batch_prices: Dict[str, float] = {}
    for i in range(0, len(tickers), 100):
        chunk = tickers[i : i + 100]
        df = yf.download(chunk, period="5d", interval="1d", auto_adjust=True, progress=False, threads=True)
        batch_prices.update(_extract_close_prices(df, chunk))

    def fetch_info(sym: str) -> Tuple[str, Dict[str, Any]]:
        try:
            return sym, (yf.Ticker(sym).info or {})
        except Exception:
            return sym, {}

    print(f"[LIVE SYNC] Descargando fundamentales en vivo (.info) con {max_workers} hilos...")
    infos: Dict[str, Dict[str, Any]] = {}
    # Warm up Yahoo session/crumb on first ticker before parallel threads
    first_sym, first_info = fetch_info(tickers[0])
    infos[first_sym] = first_info

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(fetch_info, sym): sym for sym in tickers[1:]}
        for fut in as_completed(futures):
            sym, inf = fut.result()
            infos[sym] = inf

    stock_records: List[Tuple[Any, ...]] = []
    mc_records: List[Tuple[str, str]] = []

    for sym in tickers:
        ex = row_map[sym]
        info = infos.get(sym, {})
        fb_price = batch_prices.get(sym)
        built = _build_updated_stock_payload(sym, ex, info, fb_price)
        if built is not None:
            st_tuple, mc_res = built
            stock_records.append(st_tuple)
            mc_records.append((sym, json.dumps(mc_res)))

    if stock_records:
        with get_db_connection() as conn:
            conn.executemany("""
                INSERT OR REPLACE INTO stocks (
                    ticker, name, sector, industry, market_price, shares_outstanding, market_cap,
                    ebit, tax_rate, nopat, total_debt, total_equity, cash_and_equivalents,
                    invested_capital, roic, operating_cash_flow, capex, fcf, fcf_yield,
                    ebitda, ev, ev_ebitda, net_debt, net_debt_ebitda,
                    trailing_eps, forward_eps, trailing_pe, forward_pe,
                    rev_growth_mean, rev_growth_std, margin_mean, margin_std,
                    reinvestment_rate_mean, revenue_ps, mc_p10, mc_p50, mc_p90, last_updated
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, CURRENT_TIMESTAMP
                )
            """, stock_records)
            conn.executemany("""
                INSERT OR REPLACE INTO monte_carlo_cache (ticker, simulation_json, calculated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, mc_records)
            conn.commit()
        invalidate_cache()

    print(f"[LIVE SYNC] {len(stock_records)}/{len(tickers)} acciones actualizadas con datos en vivo de Yahoo Finance.")
    return {"updated": len(stock_records), "total": len(tickers)}


def start_background_market_sync(interval_seconds: float = 30.0) -> None:
    """
    Starts a daemon thread that refreshes market indices and the currently active GICS sector
    every `interval_seconds` (30s default), plus rotates through all sectors in the background.
    """
    global _bg_thread_started
    if _bg_thread_started:
        return
    _bg_thread_started = True

    all_sectors = list(SECTOR_ETFS.keys())

    def _loop() -> None:
        rotation_idx = 0
        # Initial warmup right after server boot
        time.sleep(1.5)
        try:
            get_market_overview(force=True)
            with _active_sector_lock:
                current_sec = _active_sector
            refresh_sector_stocks(current_sec, force=False)
        except Exception as exc:
            print(f"[WARN] initial background sync: {exc}")

        while True:
            time.sleep(interval_seconds)
            try:
                get_market_overview(force=True)
                with _active_sector_lock:
                    current_sec = _active_sector
                refresh_sector_stocks(current_sec, force=True)

                # Also refresh one background sector per cycle so all 11 sectors stay warm
                bg_sec = all_sectors[rotation_idx % len(all_sectors)]
                rotation_idx += 1
                if bg_sec != current_sec:
                    refresh_sector_stocks(bg_sec, force=False)
            except Exception as exc:
                print(f"[WARN] background sync loop: {exc}")

    threading.Thread(target=_loop, daemon=True, name="market-sync-30s").start()
