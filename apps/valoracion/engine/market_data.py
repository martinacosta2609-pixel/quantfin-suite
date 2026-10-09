"""
Live Market Data & Yahoo Finance Integration
Fetches tabular data only (JSON/DataFrames, strictly no PDFs/unstructured files).
Includes error handling, rate-limit recovery, and fallback to local cache.

Unit convention (same as the seeded database): every monetary aggregate is stored in
USD millions; per-share figures and prices are in USD.
"""

import math
from typing import Dict, Any, Optional

from engine.accounting import compute_all_metrics
from engine.monte_carlo import run_monte_carlo_simulation, stable_seed, SimulationError
from engine.database import (
    get_db_connection,
    save_monte_carlo_result,
    get_stock_by_ticker,
    invalidate_cache,
)

MILLION = 1e6


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


def fetch_and_update_stock(ticker: str) -> Dict[str, Any]:
    """
    Fetches real-time market data and financials for a ticker using yfinance.
    Gracefully handles offline or rate-limited environments.
    """
    ticker_clean = ticker.strip().upper()
    existing = get_stock_by_ticker(ticker_clean)

    def from_cache(message: str) -> Dict[str, Any]:
        return {"success": True, "source": "cache", "message": message, "stock": existing}

    try:
        import yfinance as yf  # imported lazily: it is slow to import and only needed here

        info = yf.Ticker(ticker_clean).info or {}
        price = _finite(info.get("currentPrice")) or _finite(info.get("regularMarketPrice"))
        if not price or price <= 0:
            if existing:
                return from_cache("Datos de mercado obtenidos desde la base de datos local (Modo offline / API concurrida).")
            raise ValueError(f"No fue posible obtener información de mercado para '{ticker_clean}'.")

        ex = existing or {}
        shares = _first(_live_millions(info, "sharesOutstanding"), _finite(ex.get("shares_outstanding")), 1.0)
        market_cap = _first(_live_millions(info, "marketCap"), price * shares)

        sector = info.get("sector") or ex.get("sector") or "General"
        industry = info.get("industry") or ex.get("industry") or "Diversified"
        long_name = info.get("longName") or info.get("shortName") or ex.get("name") or ticker_clean

        # Financials (millions). Preference: live -> previously stored -> proportional proxy of market cap.
        ebit = _first(_live_millions(info, "operatingIncome", "ebit"), _finite(ex.get("ebit")), market_cap * 0.08)
        total_debt = _first(_live_millions(info, "totalDebt"), _finite(ex.get("total_debt")), market_cap * 0.15)
        cash = _first(_live_millions(info, "totalCash"), _finite(ex.get("cash_and_equivalents")), market_cap * 0.05)
        book_value_ps = _finite(info.get("bookValue"))
        total_equity = _first(
            book_value_ps * shares if book_value_ps is not None else None,
            _finite(ex.get("total_equity")),
            market_cap * 0.40,
        )
        ebitda = _first(_live_millions(info, "ebitda"), _finite(ex.get("ebitda")), ebit * 1.15)
        ocf = _first(_live_millions(info, "operatingCashflow"), _finite(ex.get("operating_cash_flow")), ebit * 0.95)
        fcf_live = _live_millions(info, "freeCashflow")
        capex = abs(ocf - fcf_live) if fcf_live is not None else _first(_finite(ex.get("capex")), ocf * 0.30)

        trailing_pe = _finite(info.get("trailingPE"))
        forward_pe = _finite(info.get("forwardPE"))
        trailing_eps = _first(
            _finite(info.get("trailingEps")), price / trailing_pe if trailing_pe else None,
            _finite(ex.get("trailing_eps")), 5.0)
        forward_eps = _first(
            _finite(info.get("forwardEps")), price / forward_pe if forward_pe else None,
            _finite(ex.get("forward_eps")), 5.5)

        tax_rate = _finite(ex.get("tax_rate")) or 0.21
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

        # Baseline simulation with the stock's own stored assumptions
        mc_result = None
        try:
            mc_result = run_monte_carlo_simulation(
                p0=price,
                current_revenue_ps=_first(_finite(ex.get("revenue_ps")), price * 0.25),
                historical_growth_mean=_first(_finite(ex.get("rev_growth_mean")), 0.08),
                historical_growth_std=_first(_finite(ex.get("rev_growth_std")), 0.04),
                historical_margin_mean=_first(_finite(ex.get("margin_mean")), 0.20),
                historical_margin_std=_first(_finite(ex.get("margin_std")), 0.03),
                tax_rate=tax_rate,
                reinvestment_rate_mean=_first(_finite(ex.get("reinvestment_rate_mean")), 0.35),
                num_simulations=5000,
                random_seed=stable_seed(ticker_clean),
            )
        except SimulationError:
            mc_result = None  # keep the previous MC summary rather than inventing one

        # UPSERT: refresh market-driven columns only; analyst assumptions (growth, margins, ...) are preserved
        with get_db_connection() as conn:
            conn.execute("""
                INSERT INTO stocks (
                    ticker, name, sector, industry, market_price, shares_outstanding, market_cap,
                    ebit, tax_rate, nopat, total_debt, total_equity, cash_and_equivalents,
                    invested_capital, roic, operating_cash_flow, capex, fcf, fcf_yield,
                    ebitda, ev, ev_ebitda, net_debt, net_debt_ebitda,
                    trailing_eps, forward_eps, trailing_pe, forward_pe, revenue_ps, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(ticker) DO UPDATE SET
                    name = excluded.name, sector = excluded.sector, industry = excluded.industry,
                    market_price = excluded.market_price, shares_outstanding = excluded.shares_outstanding,
                    market_cap = excluded.market_cap, ebit = excluded.ebit, tax_rate = excluded.tax_rate,
                    nopat = excluded.nopat, total_debt = excluded.total_debt, total_equity = excluded.total_equity,
                    cash_and_equivalents = excluded.cash_and_equivalents, invested_capital = excluded.invested_capital,
                    roic = excluded.roic, operating_cash_flow = excluded.operating_cash_flow, capex = excluded.capex,
                    fcf = excluded.fcf, fcf_yield = excluded.fcf_yield, ebitda = excluded.ebitda, ev = excluded.ev,
                    ev_ebitda = excluded.ev_ebitda, net_debt = excluded.net_debt,
                    net_debt_ebitda = excluded.net_debt_ebitda, trailing_eps = excluded.trailing_eps,
                    forward_eps = excluded.forward_eps, trailing_pe = excluded.trailing_pe,
                    forward_pe = excluded.forward_pe, revenue_ps = COALESCE(stocks.revenue_ps, excluded.revenue_ps),
                    last_updated = CURRENT_TIMESTAMP
            """, (
                ticker_clean, long_name, sector, industry, price, shares, metrics["market_cap"],
                ebit, tax_rate, metrics["nopat"], total_debt, total_equity, cash,
                metrics["invested_capital"], metrics["roic"], ocf, capex, metrics["fcf"], metrics["fcf_yield"],
                metrics["ebitda"], metrics["ev"], metrics["ev_ebitda"], metrics["net_debt"], metrics["net_debt_ebitda"],
                trailing_eps, forward_eps, metrics["trailing_pe"], metrics["forward_pe"],
                _first(_finite(ex.get("revenue_ps")), price * 0.25),
            ))
            conn.commit()

        if mc_result is not None:
            save_monte_carlo_result(ticker_clean, mc_result)
        else:
            invalidate_cache()

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
