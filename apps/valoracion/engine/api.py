"""
FastAPI Quantitative Valuation & Econometrics API
Provides structured JSON endpoints for high-speed desktop consumption.

Read endpoints are served from a pre-serialised response cache with ETag / 304 support and
gzip compression; the cache is keyed on the database data-version, so any write invalidates it.
"""

import hashlib
import io
import json
import threading
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Any, Callable, Dict, Optional

from fastapi import FastAPI, HTTPException, Path, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, Field

from engine.database import (
    init_db,
    get_all_sectors,
    get_sector_data,
    get_stock_by_ticker,
    get_stock_history_df,
    get_cached_monte_carlo,
    save_monte_carlo_result,
    get_data_version,
    has_missing_revenue_ps,
)
from engine.monte_carlo import run_monte_carlo_simulation, stable_seed, SimulationError
from engine.market_data import fetch_and_update_stock

API_VERSION = "1.1.0"
TICKER_PATTERN = r"^[A-Za-z0-9.\-^]{1,12}$"
BASELINE_SIMULATIONS = 5000


def _warm_up_econometrics() -> None:
    """statsmodels takes ~1.5 s to import and is only needed by the audit tab: load it after the API is up."""
    try:
        import engine.econometrics  # noqa: F401
    except Exception as exc:
        print(f"[WARN] econometrics warm-up: {exc}")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()  # idempotent: schema, migrations, indexes, WAL
    try:
        if has_missing_revenue_ps():
            from engine.data_seeder import backfill_revenue_ps
            backfill_revenue_ps()
    except Exception as exc:  # never block startup on a data migration
        print(f"[WARN] backfill revenue_ps: {exc}")
    threading.Thread(target=_warm_up_econometrics, daemon=True).start()
    yield


app = FastAPI(
    title="Institutional Valuation & Econometrics Engine",
    description="Quantitative S&P 500 / NYSE / NASDAQ Valuation Dashboard API",
    version=API_VERSION,
    lifespan=lifespan,
)

app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=5)
# The UI is served by this same server (same origin); only the Vite dev server needs CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "If-None-Match"],
)


# --------------------------------------------------------------------------- response cache
_response_cache: Dict[Any, Any] = {}
_response_lock = threading.Lock()


def _json_default(obj):
    if hasattr(obj, "item"):  # numpy scalars
        return obj.item()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _cached_json(request: Request, key: Any, builder: Callable[[], Any], data_dependent: bool = True) -> Response:
    """
    Serves `builder()` as JSON, remembering the encoded body per (key, data-version).
    Clients revalidate with If-None-Match and receive an empty 304 when nothing changed.
    """
    version = get_data_version() if data_dependent else "static"
    with _response_lock:
        entry = _response_cache.get(key)
    if entry is None or entry[0] != version:
        body = json.dumps(builder(), default=_json_default, allow_nan=False,
                          ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        etag = 'W/"' + hashlib.sha1(body).hexdigest()[:20] + '"'
        entry = (version, etag, body)
        with _response_lock:
            if len(_response_cache) > 600:  # bound memory: drop everything, entries are cheap to rebuild
                _response_cache.clear()
            _response_cache[key] = entry

    _, etag, body = entry
    headers = {"ETag": etag, "Cache-Control": "no-cache"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(content=body, media_type="application/json", headers=headers)


# --------------------------------------------------------------------------- models
class MonteCarloRequest(BaseModel):
    num_simulations: int = Field(default=BASELINE_SIMULATIONS, ge=1000, le=10000)
    rev_growth_mean: Optional[float] = Field(default=None, ge=-0.5, le=1.0)
    rev_growth_std: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    margin_mean: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    margin_std: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    tax_rate: Optional[float] = Field(default=None, ge=0.0, le=0.5)
    reinvestment_rate: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    def is_baseline(self) -> bool:
        """True when the request asks for the stock's own stored assumptions (cacheable / persistable)."""
        return self.num_simulations == BASELINE_SIMULATIONS and all(
            getattr(self, f) is None
            for f in ("rev_growth_mean", "rev_growth_std", "margin_mean", "margin_std", "tax_rate", "reinvestment_rate")
        )


TickerParam = Path(..., pattern=TICKER_PATTERN, description="Ticker symbol")


# --------------------------------------------------------------------------- endpoints
@app.get("/api/health")
def health_check():
    return {"status": "online", "version": API_VERSION, "engine": "Python/NumPy/SciPy/Statsmodels"}


@app.get("/api/sectors")
def list_sectors(request: Request):
    """
    Returns all 11 GICS sectors with company counts and aggregate sector medians.
    """
    return _cached_json(request, "sectors", get_all_sectors)


@app.get("/api/sectors/{sector_name}")
def sector_stocks(request: Request, sector_name: str = Path(..., max_length=80)):
    """
    Returns all stocks within the specified sector, along with the fixed Sector Median reference.
    """
    data = get_sector_data(sector_name)
    if not data["stocks"] and sector_name.lower() != "all":
        raise HTTPException(status_code=404, detail=f"Sector '{sector_name}' no encontrado.")
    return _cached_json(request, ("sector", sector_name.lower()), lambda: data)


@app.get("/api/stocks/{ticker}")
def stock_detail(ticker: str = TickerParam):
    """
    Returns accounting quality, multiples, and balance sheet parameters for a single stock.
    """
    stock = get_stock_by_ticker(ticker)
    if not stock:
        raise HTTPException(status_code=404, detail=f"Ticker '{ticker}' no encontrado en la base de datos.")
    return stock


def _simulate(stock: Dict[str, Any], params: MonteCarloRequest) -> Dict[str, Any]:
    """Runs a simulation from the stock's own stored assumptions, overridden by any explicit params."""
    def pick(override, key, default):
        if override is not None:
            return override
        stored = stock.get(key)
        return stored if stored is not None else default

    price = stock["market_price"]
    return run_monte_carlo_simulation(
        p0=price,
        current_revenue_ps=pick(None, "revenue_ps", price * 0.25),
        historical_growth_mean=pick(params.rev_growth_mean, "rev_growth_mean", 0.08),
        historical_growth_std=pick(params.rev_growth_std, "rev_growth_std", 0.04),
        historical_margin_mean=pick(params.margin_mean, "margin_mean", 0.20),
        historical_margin_std=pick(params.margin_std, "margin_std", 0.03),
        tax_rate=pick(params.tax_rate, "tax_rate", 0.21),
        reinvestment_rate_mean=pick(params.reinvestment_rate, "reinvestment_rate_mean", 0.35),
        num_simulations=params.num_simulations,
        random_seed=stable_seed(stock["ticker"]),
    )


@app.post("/api/stocks/{ticker}/monte-carlo")
def run_monte_carlo(ticker: str = TickerParam, params: Optional[MonteCarloRequest] = None):
    """
    Returns the stock's baseline simulation (cached) or runs a what-if simulation with the given
    overrides. Only the baseline is persisted: what-if runs never overwrite the table summary.
    """
    stock = get_stock_by_ticker(ticker)
    if not stock:
        raise HTTPException(status_code=404, detail=f"Ticker '{ticker}' no encontrado.")

    params = params or MonteCarloRequest()
    baseline = params.is_baseline()

    if baseline:
        cached = get_cached_monte_carlo(ticker)
        if cached:
            return cached

    try:
        result = _simulate(stock, params)
    except SimulationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    if baseline:
        save_monte_carlo_result(ticker, result)
    return result


@lru_cache(maxsize=256)
def _audit_for(ticker: str) -> Dict[str, Any]:
    """Econometric audit per ticker. The historical series is immutable at runtime, so it is memoised."""
    from engine.econometrics import run_econometric_audit  # lazy: see _warm_up_econometrics

    df = get_stock_history_df(ticker)
    if df.empty:
        raise LookupError(ticker)
    return run_econometric_audit(df, ticker)


@app.get("/api/stocks/{ticker}/econometrics")
def econometric_audit(request: Request, ticker: str = TickerParam):
    """
    Performs full econometric diagnostic battery on the stock's historical time series:
    - OLS model summary
    - Residuals time series and Q-Q normality plot
    - Durbin-Watson & Breusch-Godfrey autocorrelation tests
    - Breusch-Pagan & White heteroskedasticity tests
    - Variance Inflation Factor (VIF) multicollinearity
    - CUSUM parameter stability path with 5% bounds
    """
    ticker = ticker.upper()

    def build():
        try:
            return _audit_for(ticker)
        except LookupError:
            raise HTTPException(status_code=404, detail=f"No hay series temporales históricas para '{ticker}'.")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error en auditoría econométrica: {str(e)}")

    return _cached_json(request, ("audit", ticker), build, data_dependent=False)


@app.get("/api/stocks/{ticker}/export-csv")
def export_estimation_csv(ticker: str = TickerParam):
    """
    Exports clean raw time series dataset with model predictions and residuals
    for external statistical replication in R, Stata, or Python.
    """
    ticker = ticker.upper()
    df = get_stock_history_df(ticker)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No hay datos para exportar de '{ticker}'.")

    try:
        res_list = _audit_for(ticker)["residual_series"]
        df["fitted_value"] = [item["fitted"] for item in res_list]
        df["residual_error"] = [item["residual"] for item in res_list]
        df["std_residual"] = [item["std_residual"] for item in res_list]
    except Exception:
        pass  # export the raw series even if the model cannot be fitted (e.g. < 25 observations)

    stream = io.StringIO()
    df.to_csv(stream, index=False)
    return Response(
        content=stream.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={ticker}_econometric_dataset.csv"},
    )


@app.post("/api/stocks/{ticker}/refresh")
def refresh_stock(ticker: str = TickerParam):
    """
    Refreshes stock data from live financial APIs with fallback to local database.
    """
    return fetch_and_update_stock(ticker)
