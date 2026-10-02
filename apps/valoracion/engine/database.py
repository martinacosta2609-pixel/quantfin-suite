"""
Embedded SQLite Database & Cache Layer
Guarantees local persistence, sub-millisecond retrieval, and zero bloat (<500MB).
"""

import sqlite3
import json
import os
from typing import Dict, Any, List, Optional
import pandas as pd

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "quant_valuation.db")


def get_db_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """
    Initializes SQLite tables if they do not exist.
    """
    with get_db_connection() as conn:
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
                mc_p10 REAL,
                mc_p50 REAL,
                mc_p90 REAL,
                last_updated TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

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
        conn.commit()


def get_all_sectors() -> List[Dict[str, Any]]:
    """
    Returns all sectors with count of companies and calculated sector medians.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sectors ORDER BY name ASC")
        sectors = [dict(row) for row in cursor.fetchall()]

        # Attach stats for each sector
        for sec in sectors:
            cursor.execute("SELECT * FROM stocks WHERE sector = ?", (sec["name"],))
            stocks = [dict(r) for r in cursor.fetchall()]
            sec["stock_count"] = len(stocks)
            
            if stocks:
                df = pd.DataFrame(stocks)
                sec["median_pe_trailing"] = round(float(df["trailing_pe"].dropna().median()), 2) if not df["trailing_pe"].dropna().empty else None
                sec["median_pe_forward"] = round(float(df["forward_pe"].dropna().median()), 2) if not df["forward_pe"].dropna().empty else None
                sec["median_ev_ebitda"] = round(float(df["ev_ebitda"].dropna().median()), 2) if not df["ev_ebitda"].dropna().empty else None
                sec["median_roic"] = round(float(df["roic"].dropna().median() * 100.0), 2) if not df["roic"].dropna().empty else None
                sec["median_fcf_yield"] = round(float(df["fcf_yield"].dropna().median() * 100.0), 2) if not df["fcf_yield"].dropna().empty else None
                sec["median_net_debt_ebitda"] = round(float(df["net_debt_ebitda"].dropna().median()), 2) if not df["net_debt_ebitda"].dropna().empty else None
                sec["median_mc_p50"] = round(float(df["mc_p50"].dropna().median()), 2) if not df["mc_p50"].dropna().empty else None
            else:
                sec["median_pe_trailing"] = None
                sec["median_pe_forward"] = None
                sec["median_ev_ebitda"] = None
                sec["median_roic"] = None
                sec["median_fcf_yield"] = None
                sec["median_net_debt_ebitda"] = None
                sec["median_mc_p50"] = None

        return sectors


def get_sector_data(sector_name: str) -> Dict[str, Any]:
    """
    Retrieves all stocks in a sector, plus the computed Sector Median reference row.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if sector_name.lower() == "all" or sector_name.strip() == "":
            cursor.execute("SELECT * FROM stocks ORDER BY market_cap DESC")
        else:
            cursor.execute("SELECT * FROM stocks WHERE sector = ? ORDER BY market_cap DESC", (sector_name,))
        stocks = [dict(r) for r in cursor.fetchall()]

        if not stocks:
            return {"stocks": [], "sector_median": None}

        # Convert to DataFrame to accurately compute medians
        df = pd.DataFrame(stocks)

        # Build Sector Median row
        def safe_median(col, scale=1.0):
            s = df[col].dropna()
            if s.empty:
                return None
            return round(float(s.median() * scale), 2)

        sector_median = {
            "ticker": "MEDIANA",
            "name": f"Mediana del Sector ({sector_name})",
            "sector": sector_name,
            "industry": "Consenso Sectorial",
            "is_median_row": True,
            "market_price": None,
            "market_cap": safe_median("market_cap"),
            "trailing_pe": safe_median("trailing_pe"),
            "forward_pe": safe_median("forward_pe"),
            "ev_ebitda": safe_median("ev_ebitda"),
            "roic": safe_median("roic", scale=100.0), # in %
            "fcf_yield": safe_median("fcf_yield", scale=100.0), # in %
            "net_debt_ebitda": safe_median("net_debt_ebitda"),
            "mc_p10": safe_median("mc_p10"),
            "mc_p50": safe_median("mc_p50"),
            "mc_p90": safe_median("mc_p90"),
        }

        # Format individual stock percentage fields for easy UI rendering
        formatted_stocks = []
        for s in stocks:
            s_dict = dict(s)
            s_dict["is_median_row"] = False
            if s_dict["roic"] is not None:
                s_dict["roic"] = round(s_dict["roic"] * 100.0, 2)
            if s_dict["fcf_yield"] is not None:
                s_dict["fcf_yield"] = round(s_dict["fcf_yield"] * 100.0, 2)
            formatted_stocks.append(s_dict)

        return {
            "stocks": formatted_stocks,
            "sector_median": sector_median
        }


def get_stock_by_ticker(ticker: str) -> Optional[Dict[str, Any]]:
    """
    Returns single stock record.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM stocks WHERE ticker = ?", (ticker.upper(),))
        row = cursor.fetchone()
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
        query = "SELECT * FROM historical_series WHERE ticker = ? ORDER BY date ASC"
        df = pd.read_sql_query(query, conn, params=(ticker.upper(),))
        return df


def save_monte_carlo_result(ticker: str, sim_result: Dict[str, Any]):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO monte_carlo_cache (ticker, simulation_json, calculated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (ticker.upper(), json.dumps(sim_result)))
        
        # Also update stock table summary percentiles
        p10 = sim_result["percentiles"]["p10"]
        p50 = sim_result["percentiles"]["p50"]
        p90 = sim_result["percentiles"]["p90"]
        cursor.execute("""
            UPDATE stocks
            SET mc_p10 = ?, mc_p50 = ?, mc_p90 = ?
            WHERE ticker = ?
        """, (p10, p50, p90, ticker.upper()))
        conn.commit()


def get_cached_monte_carlo(ticker: str) -> Optional[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT simulation_json FROM monte_carlo_cache WHERE ticker = ?", (ticker.upper(),))
        row = cursor.fetchone()
        if row:
            return json.loads(row["simulation_json"])
        return None
