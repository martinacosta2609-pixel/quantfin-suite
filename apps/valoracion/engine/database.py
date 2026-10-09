"""
Embedded SQLite Database & Cache Layer
Guarantees local persistence, sub-millisecond retrieval, and zero bloat (<500MB).

Connections are short-lived and *really* closed on exit (sqlite3's own context manager only
commits), run in WAL mode and are paired with an in-process read cache that is invalidated
on every write.
"""

import sqlite3
import json
import os
import threading
import time
from typing import Dict, Any, List, Optional
import pandas as pd

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "quant_valuation.db")

# Columns whose per-sector median is reported (name -> scale applied to the stored value)
_SECTOR_MEDIAN_COLS = {
    "median_pe_trailing": ("trailing_pe", 1.0),
    "median_pe_forward": ("forward_pe", 1.0),
    "median_ev_ebitda": ("ev_ebitda", 1.0),
    "median_roic": ("roic", 100.0),
    "median_fcf_yield": ("fcf_yield", 100.0),
    "median_net_debt_ebitda": ("net_debt_ebitda", 1.0),
    "median_mc_p50": ("mc_p50", 1.0),
}


class _Connection(sqlite3.Connection):
    """`with get_db_connection() as conn:` commits/rolls back AND closes the connection."""

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def get_db_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, factory=_Connection, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA cache_size = -16000")  # 16 MB page cache
    return conn


# --------------------------------------------------------------------------- read cache
_cache: Dict[Any, Any] = {}
_cache_lock = threading.Lock()
_BOOT_TOKEN = format(int(time.time()), "x")
_data_version = 0


def invalidate_cache() -> None:
    """Drops every cached read. Must be called after any write to stocks/MC results."""
    global _data_version
    with _cache_lock:
        _cache.clear()
        _data_version += 1


def get_data_version() -> str:
    """Opaque token that changes whenever stored data changes (usable as an ETag)."""
    return f"{_BOOT_TOKEN}-{_data_version}"


def _cached(key, builder):
    with _cache_lock:
        if key in _cache:
            return _cache[key]
        version = _data_version
    value = builder()
    with _cache_lock:
        if version == _data_version:  # don't publish a result computed before an invalidation
            _cache[key] = value
    return value


# --------------------------------------------------------------------------- schema
def init_db():
    """
    Initializes SQLite tables if they do not exist, applies lightweight migrations and indexes.
    Idempotent and cheap: safe to call on every start.
    """
    with get_db_connection() as conn:
        conn.execute("PRAGMA journal_mode = WAL")  # persistent; readers never block the writer
        cursor = conn.cursor()

        # Sectors Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sectors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                code TEXT UNIQUE NOT NULL,
                description TEXT
            )
        """)

        # Stocks Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stocks (
                ticker TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                sector TEXT NOT NULL,
                industry TEXT NOT NULL,
                market_price REAL NOT NULL,
                shares_outstanding REAL NOT NULL,
                market_cap REAL NOT NULL,
                ebit REAL,
                tax_rate REAL DEFAULT 0.21,
                nopat REAL,
                total_debt REAL,
                total_equity REAL,
                cash_and_equivalents REAL,
                invested_capital REAL,
                roic REAL,
                operating_cash_flow REAL,
                capex REAL,
                fcf REAL,
                fcf_yield REAL,
                ebitda REAL,
                ev REAL,
                ev_ebitda REAL,
                net_debt REAL,
                net_debt_ebitda REAL,
                trailing_eps REAL,
                forward_eps REAL,
                trailing_pe REAL,
                forward_pe REAL,
                rev_growth_mean REAL DEFAULT 0.08,
                rev_growth_std REAL DEFAULT 0.05,
                margin_mean REAL DEFAULT 0.20,
                margin_std REAL DEFAULT 0.03,
                reinvestment_rate_mean REAL DEFAULT 0.35,
                revenue_ps REAL,
                mc_p10 REAL,
                mc_p50 REAL,
                mc_p90 REAL,
                last_updated TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Migration: databases created before revenue_ps existed
        existing_cols = {row["name"] for row in cursor.execute("PRAGMA table_info(stocks)")}
        if "revenue_ps" not in existing_cols:
            cursor.execute("ALTER TABLE stocks ADD COLUMN revenue_ps REAL")

        # Historical Series Table (for econometric audit & CSV export)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historical_series (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                date TEXT NOT NULL,
                stock_price REAL,
                stock_return REAL,
                market_return REAL,
                sector_return REAL,
                rate_change_10y REAL,
                stock_excess_return REAL,
                market_excess_return REAL,
                sector_excess_return REAL,
                UNIQUE(ticker, date)
            )
        """)

        # Monte Carlo Cache
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS monte_carlo_cache (
                ticker TEXT PRIMARY KEY,
                simulation_json TEXT NOT NULL,
                calculated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_stocks_sector_cap ON stocks(sector, market_cap DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_stocks_cap ON stocks(market_cap DESC)")
        conn.commit()
    invalidate_cache()


def has_missing_revenue_ps() -> bool:
    """True when some stock still lacks the per-share revenue baseline (pre-migration databases)."""
    with get_db_connection() as conn:
        return conn.execute("SELECT 1 FROM stocks WHERE revenue_ps IS NULL LIMIT 1").fetchone() is not None


# --------------------------------------------------------------------------- reads
def _num(value, scale: float = 1.0) -> Optional[float]:
    if value is None or pd.isna(value):
        return None
    return round(float(value) * scale, 2)


def get_all_sectors() -> List[Dict[str, Any]]:
    """
    Returns all sectors with count of companies and calculated sector medians
    (one query for the stocks instead of one per sector).
    """
    return _cached("sectors", _build_all_sectors)


def _build_all_sectors() -> List[Dict[str, Any]]:
    stock_cols = sorted({col for col, _ in _SECTOR_MEDIAN_COLS.values()})
    with get_db_connection() as conn:
        sectors = [dict(row) for row in conn.execute("SELECT * FROM sectors ORDER BY name ASC")]
        df = pd.read_sql_query(f"SELECT sector, {', '.join(stock_cols)} FROM stocks", conn)

    grouped = df.groupby("sector")
    counts = grouped.size()
    medians = grouped[stock_cols].median()

    for sec in sectors:
        name = sec["name"]
        sec["stock_count"] = int(counts.get(name, 0))
        has_rows = name in medians.index
        for out_key, (col, scale) in _SECTOR_MEDIAN_COLS.items():
            sec[out_key] = _num(medians.at[name, col], scale) if has_rows else None
    return sectors


def get_sector_data(sector_name: str) -> Dict[str, Any]:
    """
    Retrieves all stocks in a sector, plus the computed Sector Median reference row.
    """
    key = "all" if sector_name.strip() == "" or sector_name.lower() == "all" else sector_name
    return _cached(("sector", key), lambda: _build_sector_data(sector_name, key))


def _build_sector_data(sector_name: str, key: str) -> Dict[str, Any]:
    with get_db_connection() as conn:
        if key == "all":
            rows = conn.execute("SELECT * FROM stocks ORDER BY market_cap DESC").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM stocks WHERE sector = ? ORDER BY market_cap DESC", (sector_name,)
            ).fetchall()
    stocks = [dict(r) for r in rows]

    if not stocks:
        return {"stocks": [], "sector_median": None}

    df = pd.DataFrame(stocks)

    def med(col, scale=1.0):
        # NaN-skipping; None when the column is empty
        return _num(pd.to_numeric(df[col], errors="coerce").median(), scale)

    sector_median = {
        "ticker": "MEDIANA",
        "name": f"Mediana del Sector ({sector_name})",
        "sector": sector_name,
        "industry": "Consenso Sectorial",
        "is_median_row": True,
        "market_price": None,
        "market_cap": med("market_cap"),
        "trailing_pe": med("trailing_pe"),
        "forward_pe": med("forward_pe"),
        "ev_ebitda": med("ev_ebitda"),
        "roic": med("roic", 100.0),  # in %
        "fcf_yield": med("fcf_yield", 100.0),  # in %
        "net_debt_ebitda": med("net_debt_ebitda"),
        "mc_p10": med("mc_p10"),
        "mc_p50": med("mc_p50"),
        "mc_p90": med("mc_p90"),
    }

    # Percentage fields scaled for the UI
    for s in stocks:
        s["is_median_row"] = False
        if s["roic"] is not None:
            s["roic"] = round(s["roic"] * 100.0, 2)
        if s["fcf_yield"] is not None:
            s["fcf_yield"] = round(s["fcf_yield"] * 100.0, 2)

    return {"stocks": stocks, "sector_median": sector_median}


def get_stock_by_ticker(ticker: str) -> Optional[Dict[str, Any]]:
    """
    Returns single stock record.
    """
    with get_db_connection() as conn:
        row = conn.execute("SELECT * FROM stocks WHERE ticker = ?", (ticker.upper(),)).fetchone()
    if not row:
        return None
    res = dict(row)
    if res.get("roic") is not None:
        res["roic_pct"] = round(res["roic"] * 100.0, 2)
    if res.get("fcf_yield") is not None:
        res["fcf_yield_pct"] = round(res["fcf_yield"] * 100.0, 2)
    return res


def get_stock_history_df(ticker: str) -> pd.DataFrame:
    """
    Retrieves historical series DataFrame for econometric modeling.
    """
    with get_db_connection() as conn:
        return pd.read_sql_query(
            "SELECT * FROM historical_series WHERE ticker = ? ORDER BY date ASC",
            conn, params=(ticker.upper(),),
        )


# --------------------------------------------------------------------------- Monte Carlo persistence
def save_monte_carlo_result(ticker: str, sim_result: Dict[str, Any]):
    """Stores the baseline simulation and refreshes the P10/P50/P90 summary shown in the table."""
    with get_db_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO monte_carlo_cache (ticker, simulation_json, calculated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (ticker.upper(), json.dumps(sim_result)))
        conn.execute("""
            UPDATE stocks SET mc_p10 = ?, mc_p50 = ?, mc_p90 = ? WHERE ticker = ?
        """, (
            sim_result["percentiles"]["p10"],
            sim_result["percentiles"]["p50"],
            sim_result["percentiles"]["p90"],
            ticker.upper(),
        ))
        conn.commit()
    invalidate_cache()


def get_cached_monte_carlo(ticker: str) -> Optional[Dict[str, Any]]:
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT simulation_json FROM monte_carlo_cache WHERE ticker = ?", (ticker.upper(),)
        ).fetchone()
    return json.loads(row["simulation_json"]) if row else None
