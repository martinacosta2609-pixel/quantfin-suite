"""
Live Market Data & Yahoo Finance Integration
Fetches tabular data only (JSON/DataFrames, strictly no PDFs/unstructured files).
Includes error handling, rate-limit recovery, and fallback to local cache.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from engine.accounting import compute_all_metrics
from engine.monte_carlo import run_monte_carlo_simulation
from engine.database import (
    get_db_connection,
    save_monte_carlo_result,
    get_stock_by_ticker
)

def fetch_and_update_stock(ticker: str) -> Dict[str, Any]:
    """
    Fetches real-time market data and financials for a ticker using yfinance.
    Gracefully handles offline or rate-limited environments.
    """
    ticker_clean = ticker.strip().upper()
    existing_stock = get_stock_by_ticker(ticker_clean)

    try:
        ticker_obj = yf.Ticker(ticker_clean)
        info = ticker_obj.info or {}
        
        # If yfinance returned empty or invalid
        if not info or "regularMarketPrice" not in info and "currentPrice" not in info:
            if existing_stock:
                return {
                    "success": True,
                    "source": "cache",
                    "message": "Datos de mercado obtenidos desde la base de datos local (Modo offline / API concurrida).",
                    "stock": existing_stock
                }
            raise ValueError(f"No fue posible obtener información de mercado para '{ticker_clean}'.")

        price = float(info.get("currentPrice") or info.get("regularMarketPrice") or 0.0)
        shares = float(info.get("sharesOutstanding") or 1.0)
        market_cap = float(info.get("marketCap") or (price * shares))
        sector = info.get("sector", existing_stock.get("sector") if existing_stock else "General")
        industry = info.get("industry", existing_stock.get("industry") if existing_stock else "Diversified")
        long_name = info.get("longName") or info.get("shortName") or ticker_clean

        # Financial statements (income, balance, cashflow)
        ebit = float(info.get("operatingIncome") or info.get("ebit") or (existing_stock.get("ebit") if existing_stock else market_cap * 0.08))
        total_debt = float(info.get("totalDebt") or (existing_stock.get("total_debt") if existing_stock else market_cap * 0.15))
        total_cash = float(info.get("totalCash") or (existing_stock.get("cash_and_equivalents") if existing_stock else market_cap * 0.05))
        total_equity = float(existing_stock.get("total_equity") if existing_stock else market_cap * 0.40)
        ebitda = float(info.get("ebitda") or (ebit * 1.15))
        ocf = float(info.get("operatingCashflow") or (ebit * 0.95))
        fcf_val = float(info.get("freeCashflow") or (ocf * 0.70))
        capex = abs(ocf - fcf_val)

        trailing_pe = info.get("trailingPE")
        forward_pe = info.get("forwardPE")
        trailing_eps = float(info.get("trailingEps") or (price / trailing_pe if trailing_pe else 5.0))
        forward_eps = float(info.get("forwardEps") or (price / forward_pe if forward_pe else 5.5))

        raw_data = {
            "market_price": price,
            "shares_outstanding": shares / 1e6, # in millions
            "market_cap": market_cap / 1e6,
            "ebit": ebit / 1e6,
            "tax_rate": 0.21,
            "total_debt": total_debt / 1e6,
            "total_equity": total_equity,
            "cash_and_equivalents": total_cash / 1e6,
            "operating_cash_flow": ocf / 1e6,
            "capex": capex / 1e6,
            "ebitda": ebitda / 1e6,
            "trailing_eps": trailing_eps,
            "forward_eps": forward_eps
        }

        metrics = compute_all_metrics(raw_data)

        # Run fresh Monte Carlo simulation (5000 runs)
        revenue_ps = (price * 0.25)
        mc_result = run_monte_carlo_simulation(
            p0=price,
            current_revenue_ps=revenue_ps,
            historical_growth_mean=0.08,
            historical_growth_std=0.04,
            historical_margin_mean=0.20,
            historical_margin_std=0.03,
            tax_rate=0.21,
            num_simulations=5000,
            random_seed=42
        )

        p10 = mc_result["percentiles"]["p10"]
        p50 = mc_result["percentiles"]["p50"]
        p90 = mc_result["percentiles"]["p90"]

        # Update Database
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO stocks (
                    ticker, name, sector, industry, market_price, shares_outstanding, market_cap,
                    ebit, tax_rate, nopat, total_debt, total_equity, cash_and_equivalents,
                    invested_capital, roic, operating_cash_flow, capex, fcf, fcf_yield,
                    ebitda, ev, ev_ebitda, net_debt, net_debt_ebitda,
                    trailing_eps, forward_eps, trailing_pe, forward_pe,
                    mc_p10, mc_p50, mc_p90, last_updated
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, CURRENT_TIMESTAMP
                )
            """, (
                ticker_clean, long_name, sector, industry, price, raw_data["shares_outstanding"], metrics["market_cap"],
                raw_data["ebit"], 0.21, metrics["nopat"], raw_data["total_debt"], total_equity, raw_data["cash_and_equivalents"],
                metrics["invested_capital"], metrics["roic"], raw_data["operating_cash_flow"], raw_data["capex"], metrics["fcf"], metrics["fcf_yield"],
                metrics["ebitda"], metrics["ev"], metrics["ev_ebitda"], metrics["net_debt"], metrics["net_debt_ebitda"],
                trailing_eps, forward_eps, metrics["trailing_pe"], metrics["forward_pe"],
                p10, p50, p90
            ))
            conn.commit()

        save_monte_carlo_result(ticker_clean, mc_result)
        updated_stock = get_stock_by_ticker(ticker_clean)

        return {
            "success": True,
            "source": "live",
            "message": f"Información de mercado actualizada exitosamente para {ticker_clean}.",
            "stock": updated_stock
        }

    except Exception as e:
        if existing_stock:
            return {
                "success": True,
                "source": "cache",
                "message": f"Datos cargados desde base local: {str(e)}",
                "stock": existing_stock
            }
        return {
            "success": False,
            "source": "error",
            "message": f"Error al consultar API de mercado: {str(e)}",
            "stock": None
        }
