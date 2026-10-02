"""
FastAPI Quantitative Valuation & Econometrics API
Provides structured JSON endpoints for high-speed desktop consumption.
"""

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import io
import pandas as pd

from engine.database import (
    get_all_sectors,
    get_sector_data,
    get_stock_by_ticker,
    get_stock_history_df,
    get_cached_monte_carlo,
    save_monte_carlo_result
)
from engine.monte_carlo import run_monte_carlo_simulation
from engine.econometrics import run_econometric_audit
from engine.market_data import fetch_and_update_stock

app = FastAPI(
    title="Institutional Valuation & Econometrics Engine",
    description="Quantitative S&P 500 / NYSE / NASDAQ Valuation Dashboard API",
    version="1.0.0"
)

# CORS middleware for local frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class MonteCarloRequest(BaseModel):
    num_simulations: int = Field(default=5000, ge=1000, le=10000)
    rev_growth_mean: Optional[float] = None
    rev_growth_std: Optional[float] = None
    margin_mean: Optional[float] = None
    margin_std: Optional[float] = None
    tax_rate: Optional[float] = None
    reinvestment_rate: Optional[float] = None


@app.get("/api/health")
def health_check():
    return {"status": "online", "version": "1.0.0", "engine": "Python/NumPy/SciPy/Statsmodels"}


@app.get("/api/sectors")
def list_sectors():
    """
    Returns all 11 GICS sectors with company counts and aggregate sector medians.
    """
    return get_all_sectors()


@app.get("/api/sectors/{sector_name}")
def sector_stocks(sector_name: str):
    """
    Returns all stocks within the specified sector, along with the fixed Sector Median reference.
    """
    data = get_sector_data(sector_name)
    if not data["stocks"] and sector_name.lower() != "all":
        raise HTTPException(status_code=404, detail=f"Sector '{sector_name}' no encontrado.")
    return data


@app.get("/api/stocks/{ticker}")
def stock_detail(ticker: str):
    """
    Returns accounting quality, multiples, and balance sheet parameters for a single stock.
    """
    stock = get_stock_by_ticker(ticker)
    if not stock:
        raise HTTPException(status_code=404, detail=f"Ticker '{ticker}' no encontrado en la base de datos.")
    return stock


@app.post("/api/stocks/{ticker}/monte-carlo")
def run_monte_carlo(ticker: str, params: Optional[MonteCarloRequest] = None):
    """
    Executes or returns cached 5,000-10,000 Monte Carlo trajectories.
    Solves for the empirical implied IRR distribution without subjective k.
    """
    stock = get_stock_by_ticker(ticker)
    if not stock:
        raise HTTPException(status_code=404, detail=f"Ticker '{ticker}' no encontrado.")

    # If no custom parameters provided, check cache first
    if params is None or (
        params.rev_growth_mean is None and 
        params.margin_mean is None and 
        params.num_simulations == 5000
    ):
        cached = get_cached_monte_carlo(ticker)
        if cached:
            return cached

    # Run fresh simulation
    growth_mean = params.rev_growth_mean if params and params.rev_growth_mean is not None else stock.get("rev_growth_mean", 0.08)
    growth_std = params.rev_growth_std if params and params.rev_growth_std is not None else stock.get("rev_growth_std", 0.04)
    margin_mean = params.margin_mean if params and params.margin_mean is not None else stock.get("margin_mean", 0.20)
    margin_std = params.margin_std if params and params.margin_std is not None else stock.get("margin_std", 0.03)
    tax_rate = params.tax_rate if params and params.tax_rate is not None else stock.get("tax_rate", 0.21)
    reinv = params.reinvestment_rate if params and params.reinvestment_rate is not None else stock.get("reinvestment_rate_mean", 0.35)
    nsim = params.num_simulations if params else 5000

    sim_res = run_monte_carlo_simulation(
        p0=stock["market_price"],
        current_revenue_ps=stock["market_price"] * 0.25,
        historical_growth_mean=growth_mean,
        historical_growth_std=growth_std,
        historical_margin_mean=margin_mean,
        historical_margin_std=margin_std,
        tax_rate=tax_rate,
        reinvestment_rate_mean=reinv,
        num_simulations=nsim,
        random_seed=abs(hash(ticker)) % 100000
    )

    save_monte_carlo_result(ticker, sim_res)
    return sim_res


@app.get("/api/stocks/{ticker}/econometrics")
def econometric_audit(ticker: str):
    """
    Performs full econometric diagnostic battery on the stock's historical time series:
    - OLS model summary
    - Residuals time series and Q-Q normality plot
    - Durbin-Watson & Breusch-Godfrey autocorrelation tests
    - Breusch-Pagan & White heteroskedasticity tests
    - Variance Inflation Factor (VIF) multicollinearity
    - CUSUM parameter stability path with 5% bounds
    """
    df = get_stock_history_df(ticker)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No hay series temporales históricas para '{ticker}'.")

    try:
        audit_res = run_econometric_audit(df, ticker)
        return audit_res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en auditoría econométrica: {str(e)}")


@app.get("/api/stocks/{ticker}/export-csv")
def export_estimation_csv(ticker: str):
    """
    Exports clean raw time series dataset with model predictions and residuals
    for external statistical replication in R, Stata, or Python.
    """
    df = get_stock_history_df(ticker)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No hay datos para exportar de '{ticker}'.")

    # Run audit to append fitted values and residuals
    try:
        audit_res = run_econometric_audit(df, ticker)
        res_list = audit_res["residual_series"]
        df["fitted_value"] = [item["fitted"] for item in res_list]
        df["residual_error"] = [item["residual"] for item in res_list]
        df["std_residual"] = [item["std_residual"] for item in res_list]
    except Exception:
        pass

    stream = io.StringIO()
    df.to_csv(stream, index=False)
    csv_content = stream.getvalue()

    filename = f"{ticker.upper()}_econometric_dataset.csv"
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.post("/api/stocks/{ticker}/refresh")
def refresh_stock(ticker: str):
    """
    Refreshes stock data from live financial APIs with fallback to local database.
    """
    result = fetch_and_update_stock(ticker)
    return result
