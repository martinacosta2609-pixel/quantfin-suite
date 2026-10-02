"""
QuantFin Cloud Suite - Unified Quantitative & Econometrics Server
Integrates:
  1. Terminal Bonos Argentinos (BYMA & BCRA Fixed Income)
  2. Valoracion de Acciones & DCF (Equity Valuation & Monte Carlo)
  3. FAMA-FRENCH Institutional Terminal (Multi-Factor Asset Pricing & Backtesting)
  4. QUANT BSM Terminal (Commodities & Options Analytics)
"""

import sys
import os
import io
import time
import json
import threading
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Response, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

# Base Directory
BASE_DIR = Path(__file__).resolve().parent

# Add sub-application paths into sys.path
sys.path.insert(0, str(BASE_DIR / "apps" / "bonos"))
sys.path.insert(0, str(BASE_DIR / "apps" / "fama"))
sys.path.insert(0, str(BASE_DIR / "apps" / "bsm"))
sys.path.insert(0, str(BASE_DIR / "apps" / "valoracion"))

# ==================== IMPORT MODULES ====================
# 1. Bonos
from data_feed import MarketDataFeed

# 2. Fama-French
from core.data_fetcher import DataFetcher
from core.fama_french_engine import FamaFrenchEngine
from core.valuation import ValuationEngine
from core.backtester import FamaFrenchBacktester
from core.sector_analyzer import SectorAnalyzer

# 3. BSM
from backend.bridge import ApiBridge

# 4. Valoracion de Acciones
from engine.database import (
    init_db,
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


# ==================== ENGINE INSTANCES ====================
bonos_feed = MarketDataFeed()
cached_bonos_payload = {"bonds": [], "macro": {}}

bsm_bridge = ApiBridge()

class FamaController:
    def __init__(self):
        self.fetcher = DataFetcher()
        self.sector_analyzer = SectorAnalyzer(self.fetcher)
        self.ff_factors_df = None
        self.current_stock_df = None
        self.current_aligned_df = None
        self.current_stock_info = None
        self.current_ticker = None
        self.current_model_type = "FF5"

    def ensure_factors(self, force_refresh: bool = False):
        if self.ff_factors_df is None or force_refresh:
            self.ff_factors_df = self.fetcher.get_fama_french_factors(force_refresh=force_refresh)
        return self.ff_factors_df

    def get_factors_info(self):
        df = self.ensure_factors()
        return {
            "latest_date": df["Date"].max().strftime("%Y-%m-%d"),
            "earliest_date": df["Date"].min().strftime("%Y-%m-%d"),
            "observations": len(df),
            "is_cached": True
        }

    def refresh_factors(self):
        df = self.ensure_factors(force_refresh=True)
        return {
            "success": True,
            "latest_date": df["Date"].max().strftime("%Y-%m-%d"),
            "observations": len(df)
        }

    def analyze_stock(self, ticker: str, model_type: str = "FF5", period: str = "3y"):
        ticker_clean = ticker.strip().upper()
        self.ensure_factors()
        self.current_ticker = ticker_clean
        self.current_model_type = model_type

        stock_res = self.fetcher.get_stock_data(ticker_clean, period=period)
        self.current_stock_df = stock_res["history"]
        self.current_stock_info = stock_res["info"]

        aligned = self.fetcher.align_stock_and_factors(self.current_stock_df, self.ff_factors_df)
        self.current_aligned_df = aligned

        if len(aligned) < 30:
            return {"error": f"Datos insuficientes para {ticker_clean} (menos de 30 dias comunes)."}

        engine = FamaFrenchEngine(model_type=model_type)
        estimation_res = engine.estimate(aligned, cov_type="HAC")

        valuation_res = ValuationEngine.compute_valuation(
            current_price=estimation_res["current_price"],
            cost_of_equity=estimation_res["cost_of_equity"],
            alpha_annual=estimation_res["alpha_annual"],
            alpha_pvalue=estimation_res["alpha_pvalue"],
            residual_std_error=estimation_res["econometrics"]["summary_metrics"]["residual_std_error"],
            stock_info=self.current_stock_info
        )

        estimation_res["econometrics"].pop("statsmodels_result", None)
        raw_resids = estimation_res["econometrics"].pop("raw_residuals", None)
        estimation_res["econometrics"].pop("raw_fitted", None)

        timeline_dates = [d.strftime("%Y-%m-%d") for d in aligned["Date"]]
        timeline_prices = [float(p) for p in aligned["Close"]]
        resids_list = [float(r) for r in raw_resids] if raw_resids is not None else []

        return {
            "ticker": ticker_clean,
            "stock_info": self.current_stock_info,
            "dates": timeline_dates,
            "prices": timeline_prices,
            "residuals": resids_list,
            "estimation": estimation_res,
            "valuation": valuation_res
        }

    def run_backtest(self, cutoff_date: str, train_window_days: int = 252, test_horizon_days: int = 63, model_type: str = "FF5"):
        if self.current_aligned_df is None or self.current_aligned_df.empty:
            return {"error": "Primero debes analizar un ticker antes de ejecutar el backtest."}

        engine = FamaFrenchEngine(model_type=model_type)
        factors = engine.factors
        return FamaFrenchBacktester.run_backtest(
            aligned_df=self.current_aligned_df,
            cutoff_date=cutoff_date,
            train_window_days=int(train_window_days),
            test_horizon_days=int(test_horizon_days),
            factors=factors,
            cov_type="HAC"
        )

    def analyze_sector(self, sector_id: str, model_type: str = "FF5", period: str = "2y"):
        self.ensure_factors()
        return self.sector_analyzer.analyze_sector(sector_id, model_type, period)

fama_ctrl = FamaController()


# ==================== LIFESPAN BACKGROUND WORKERS ====================
def update_bonos_worker():
    global cached_bonos_payload
    try:
        bonds, macro = bonos_feed.process_market_data()
        cached_bonos_payload = {"bonds": bonds, "macro": macro}
        print(f"[OK] Bonos actualizados: {len(bonds)} activos en memoria.")
    except Exception as e:
        print("[AVISO] Fallback al cargar bonos:", e)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Valoracion database
    try:
        init_db()
        print("[OK] Base de datos de Valoracion inicializada.")
    except Exception as e:
        print("[AVISO] Error al inicializar DB:", e)

    # Initial Bonos load in background thread
    t = threading.Thread(target=update_bonos_worker, daemon=True)
    t.start()

    yield

    print("[INFO] Deteniendo servicios...")


# ==================== FASTAPI APP ====================
app = FastAPI(
    title="QuantFin Cloud Suite",
    description="Unified Quantitative Finance, Econometrics & Market Terminal",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== 1. BONOS API ENDPOINTS ====================
@app.get("/api/data")
def get_bonos_data():
    global cached_bonos_payload
    if not cached_bonos_payload.get("bonds"):
        update_bonos_worker()
    return cached_bonos_payload

@app.get("/api/refresh")
def refresh_bonos_data():
    update_bonos_worker()
    return cached_bonos_payload

@app.get("/api/info")
def get_bonos_info(request: Request):
    return {
        "server": "QuantFin Cloud Suite",
        "status": "online",
        "timestamp": time.time()
    }

@app.get("/api/van")
def calculate_bonos_van(
    symbol: str = "AL30D",
    investment: float = 1000.0,
    k: float = 12.0,
    vt: str = "1"
):
    global cached_bonos_payload
    inc_vt = vt.lower() in ["1", "true", "yes"]
    bond_item = next((b for b in cached_bonos_payload.get("bonds", []) if b["symbol"].upper() == symbol.upper()), None)
    if not bond_item:
        bond_item = next((b for b in cached_bonos_payload.get("bonds", []) if symbol.upper() in b["symbol"].upper()), None)
    if not bond_item:
        return {"error": f"Bono {symbol} no encontrado"}
    return bonos_feed.engine.calculate_van(bond_item, investment, k, inc_vt)

@app.get("/api/horizon")
def calculate_bonos_horizon(years: float = 5.0):
    global cached_bonos_payload
    results = []
    seen_base = set()
    for b in cached_bonos_payload.get("bonds", []):
        sym = b["symbol"]
        if not b.get("cashflows"):
            continue
        if not (sym.endswith("D") or sym in ["AL29", "GD29", "AL30", "GD30", "AL35", "GD35", "AE38", "GD38", "AL41", "GD41"]):
            continue
        base_code = sym[:4]
        if base_code in seen_base and not sym.endswith("D"):
            continue
        seen_base.add(base_code)

        h_res = bonos_feed.engine.calculate_horizon_metrics(b, years)
        if h_res and h_res.get("eligible"):
            results.append({
                "symbol": sym,
                "name": b.get("name", sym),
                "type": b.get("type", "Soberano"),
                "price": b.get("eval_price", b.get("price", 0.0)),
                "tir_market": b.get("tir", 0.0),
                "parity": b.get("parity", 0.0),
                "maturity_date": b.get("maturity_date", ""),
                "maturity_years": h_res["maturity_years"],
                "cash_collected": h_res["cash_collected"],
                "terminal_price": h_res["terminal_price"],
                "total_inflow": h_res["total_inflow"],
                "hpr_pct": h_res["hpr_pct"],
                "horizon_tir": h_res["horizon_tir"]
            })
    results.sort(key=lambda x: x["horizon_tir"], reverse=True)
    return {"horizon_years": years, "results": results}


# ==================== 2. VALORACION DE ACCIONES API ====================
class MonteCarloRequest(BaseModel):
    num_simulations: int = Field(default=5000, ge=1000, le=10000)
    rev_growth_mean: Optional[float] = None
    rev_growth_std: Optional[float] = None
    margin_mean: Optional[float] = None
    margin_std: Optional[float] = None
    tax_rate: Optional[float] = None
    reinvestment_rate: Optional[float] = None

@app.get("/api/sectors")
def list_sectors():
    return get_all_sectors()

@app.get("/api/sectors/{sector_name}")
def sector_stocks(sector_name: str):
    data = get_sector_data(sector_name)
    if not data["stocks"] and sector_name.lower() != "all":
        raise HTTPException(status_code=404, detail=f"Sector '{sector_name}' no encontrado.")
    return data

@app.get("/api/stocks/{ticker}")
def stock_detail(ticker: str):
    stock = get_stock_by_ticker(ticker)
    if not stock:
        raise HTTPException(status_code=404, detail=f"Ticker '{ticker}' no encontrado en la base de datos.")
    return stock

@app.post("/api/stocks/{ticker}/monte-carlo")
def run_monte_carlo(ticker: str, params: Optional[MonteCarloRequest] = None):
    stock = get_stock_by_ticker(ticker)
    if not stock:
        raise HTTPException(status_code=404, detail=f"Ticker '{ticker}' no encontrado.")

    if params is None or (
        params.rev_growth_mean is None and 
        params.margin_mean is None and 
        params.num_simulations == 5000
    ):
        cached = get_cached_monte_carlo(ticker)
        if cached:
            return cached

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
    df = get_stock_history_df(ticker)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No hay series temporales historicas para '{ticker}'.")
    try:
        return run_econometric_audit(df, ticker)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en auditoria econometrica: {str(e)}")

@app.get("/api/stocks/{ticker}/export-csv")
def export_estimation_csv(ticker: str):
    df = get_stock_history_df(ticker)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No hay datos para exportar de '{ticker}'.")
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
    return Response(
        content=stream.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={ticker.upper()}_econometric_dataset.csv"}
    )

@app.post("/api/stocks/{ticker}/refresh")
def refresh_stock_market_data(ticker: str):
    return fetch_and_update_stock(ticker)


# ==================== 3. FAMA-FRENCH API ====================
@app.get("/api/fama/get_factors_info")
def fama_factors_info():
    try:
        return fama_ctrl.get_factors_info()
    except Exception as e:
        return {"error": str(e), "is_cached": False}

@app.post("/api/fama/refresh_factors")
def fama_refresh_factors():
    try:
        return fama_ctrl.refresh_factors()
    except Exception as e:
        return {"error": str(e), "success": False}

@app.post("/api/fama/analyze_stock")
def fama_analyze_stock(payload: Dict[str, Any] = Body(...)):
    try:
        ticker = payload.get("ticker", "AAPL")
        model = payload.get("model_type", "FF5")
        period = payload.get("period", "3y")
        return fama_ctrl.analyze_stock(ticker, model, period)
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/fama/run_backtest")
def fama_run_backtest(payload: Dict[str, Any] = Body(...)):
    try:
        cutoff = payload.get("cutoff_date", "2025-06-01")
        train_window = int(payload.get("train_window_days", 252))
        test_horizon = int(payload.get("test_horizon_days", 63))
        model = payload.get("model_type", "FF5")
        return fama_ctrl.run_backtest(cutoff, train_window, test_horizon, model)
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/fama/analyze_sector")
def fama_analyze_sector(payload: Dict[str, Any] = Body(...)):
    try:
        sector_id = payload.get("sector_id", "technology")
        model = payload.get("model_type", "FF5")
        period = payload.get("period", "2y")
        return fama_ctrl.analyze_sector(sector_id, model, period)
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/fama/get_sp500_sectors")
def fama_get_sp500_sectors():
    try:
        return fama_ctrl.sector_analyzer.get_all_sectors_metadata()
    except Exception as e:
        return {"error": str(e)}


# ==================== 4. BSM (BLACK-SCHOLES) API ====================
@app.get("/api/bsm/get_commodities")
def bsm_get_commodities():
    return bsm_bridge.get_commodities()

@app.post("/api/bsm/get_quote")
def bsm_get_quote(payload: Dict[str, Any] = Body(...)):
    comm_id = payload.get("comm_id", "gold")
    return bsm_bridge.get_quote(comm_id)

@app.post("/api/bsm/get_options_chain")
def bsm_get_options_chain(payload: Dict[str, Any] = Body(...)):
    comm_id = payload.get("comm_id", "gold")
    expiry = payload.get("expiry")
    return bsm_bridge.get_options_chain(comm_id, expiry)

@app.post("/api/bsm/calculate_single_option")
def bsm_calculate_single_option(payload: Dict[str, Any] = Body(...)):
    params = payload.get("params", payload)
    return bsm_bridge.calculate_single_option(params)

@app.post("/api/bsm/run_econometric_backtest")
def bsm_run_econometric_backtest(payload: Dict[str, Any] = Body(...)):
    params = payload.get("params", payload)
    return bsm_bridge.run_econometric_backtest(params)

@app.post("/api/bsm/get_historical_series")
def bsm_get_historical_series(payload: Dict[str, Any] = Body(...)):
    comm_id = payload.get("comm_id", "gold")
    period = payload.get("period", "1y")
    return bsm_bridge.get_historical_series(comm_id, period)


# ==================== STATIC & ROUTING ====================
# Shared resources (Navbar, banners)
app.mount("/shared", StaticFiles(directory=str(BASE_DIR / "portal")), name="shared")

# React bundle assets for Valoracion
app.mount("/assets", StaticFiles(directory=str(BASE_DIR / "apps" / "valoracion" / "dist" / "assets")), name="assets")

# Dedicated Frontends
app.mount("/bonos", StaticFiles(directory=str(BASE_DIR / "apps" / "bonos" / "web"), html=True), name="bonos")
app.mount("/fama", StaticFiles(directory=str(BASE_DIR / "apps" / "fama" / "gui"), html=True), name="fama")
app.mount("/bsm", StaticFiles(directory=str(BASE_DIR / "apps" / "bsm" / "frontend"), html=True), name="bsm")

@app.get("/valoracion")
@app.get("/valoracion/")
def serve_valoracion_index():
    return FileResponse(BASE_DIR / "apps" / "valoracion" / "dist" / "index.html")

@app.get("/valoracion/{full_path:path}")
def serve_valoracion_catchall(full_path: str):
    fpath = BASE_DIR / "apps" / "valoracion" / "dist" / full_path
    if fpath.is_file():
        return FileResponse(fpath)
    return FileResponse(BASE_DIR / "apps" / "valoracion" / "dist" / "index.html")

# Root landing hub
@app.get("/")
def serve_root():
    return FileResponse(BASE_DIR / "portal" / "index.html")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"\n=======================================================")
    print(f"🚀 QuantFin Cloud Suite activa en: http://localhost:{port}")
    print(f"   - Hub Principal: http://localhost:{port}/")
    print(f"   - Bonos Argentinos: http://localhost:{port}/bonos/")
    print(f"   - Valoracion Acciones: http://localhost:{port}/valoracion/")
    print(f"   - FAMA-FRENCH: http://localhost:{port}/fama/")
    print(f"   - Black-Scholes BSM: http://localhost:{port}/bsm/")
    print(f"=======================================================\n")
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
