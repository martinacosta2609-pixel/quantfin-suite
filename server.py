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
from fastapi.middleware.gzip import GZipMiddleware
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
from engine.database import init_db, has_missing_revenue_ps
# Los endpoints de Valoracion viven en engine/api.py (cache ETag/304, validacion de entradas,
# semilla estable por ticker): aqui solo se registran sus funciones, sin duplicar la logica.
import engine.api as valoracion_api


# ==================== ENGINE INSTANCES ====================
bonos_feed = MarketDataFeed()
cached_bonos_payload = {"bonds": [], "macro": {}}

bsm_bridge = ApiBridge()

class FamaController:
    """Mismo contrato que FamaFrenchAppAPI (apps/fama/app.py), expuesto por HTTP en lugar de pywebview."""

    def __init__(self):
        self.fetcher = DataFetcher()
        self.sector_analyzer = SectorAnalyzer(self.fetcher)
        self.ff_factors_df = None
        self.current_aligned_df = None
        self._state_lock = threading.Lock()

    def ensure_factors(self, force_refresh: bool = False):
        # El fetcher cachea en disco y serializa la descarga: es barato llamarlo en cada request.
        self.ff_factors_df = self.fetcher.get_fama_french_factors(force_refresh=force_refresh)
        return self.ff_factors_df

    def get_factors_info(self):
        df = self.ensure_factors()
        return {**self.fetcher.factors_status(df), "is_cached": True}

    def refresh_factors(self):
        df = self.ensure_factors(force_refresh=True)
        self.fetcher._stock_cache.clear()
        self.sector_analyzer.cache.clear()
        return {"success": True, **self.fetcher.factors_status(df)}

    def analyze_stock(self, ticker: str, model_type: str = "FF5", period: str = "3y"):
        ticker_clean = ticker.strip().upper()
        factors_df = self.ensure_factors()

        stock_res = self.fetcher.get_stock_data(ticker_clean, period=period)
        stock_info = stock_res["info"]
        aligned = self.fetcher.align_stock_and_factors(stock_res["history"], factors_df)

        if len(aligned) < 30:
            return {"error": f"Datos insuficientes para {ticker_clean} (menos de 30 dias habiles en comun)."}

        engine = FamaFrenchEngine(model_type=model_type)
        estimation_res = engine.estimate(aligned, cov_type="HAC")

        valuation_res = ValuationEngine.compute_valuation(
            current_price=estimation_res["current_price"],
            cost_of_equity=estimation_res["cost_of_equity"],
            alpha_annual=estimation_res["alpha_annual"],
            alpha_pvalue=estimation_res["alpha_pvalue"],
            residual_std_error=estimation_res["econometrics"]["summary_metrics"]["residual_std_error"],
            stock_info=stock_info
        )

        # Objetos de statsmodels/pandas que no se pueden serializar a JSON
        estimation_res["econometrics"].pop("statsmodels_result", None)
        raw_resids = estimation_res["econometrics"].pop("raw_residuals", None)
        estimation_res["econometrics"].pop("raw_fitted", None)

        with self._state_lock:
            self.current_aligned_df = aligned

        proxy_days = int(aligned["Is_Proxy"].sum()) if "Is_Proxy" in aligned.columns else 0

        return {
            "ticker": ticker_clean,
            "stock_info": stock_info,
            "dates": aligned["Date"].dt.strftime("%Y-%m-%d").tolist(),
            "prices": aligned["Close"].astype(float).tolist(),
            "residuals": [float(r) for r in raw_resids] if raw_resids is not None else [],
            "proxy_days": proxy_days,
            "estimation": estimation_res,
            "valuation": valuation_res
        }

    def run_backtest(self, cutoff_date: str, train_window_days: int = 252, test_horizon_days: int = 63, model_type: str = "FF5"):
        with self._state_lock:
            aligned = self.current_aligned_df
        if aligned is None or aligned.empty:
            return {"error": "Primero debes analizar un ticker antes de ejecutar el backtest."}

        engine = FamaFrenchEngine(model_type=model_type)
        return FamaFrenchBacktester.run_backtest(
            aligned_df=aligned,
            cutoff_date=cutoff_date,
            train_window_days=int(train_window_days),
            test_horizon_days=int(test_horizon_days),
            factors=engine.factors,
            cov_type="HAC"
        )

    def analyze_sector(self, sector_id: str, model_type: str = "FF5", period: str = "2y", force_refresh: bool = False):
        self.ensure_factors()
        return self.sector_analyzer.analyze_sector(sector_id, model_type, period, force_refresh=bool(force_refresh))

fama_ctrl = FamaController()


# ==================== LIFESPAN BACKGROUND WORKERS ====================
def update_bonos_worker(force: bool = False):
    """Punto unico de refresco de Bonos. El feed reutiliza su ultimo resultado unos segundos,
    asi que llamarlo en cada request no martilla a BYMA/BCRA."""
    global cached_bonos_payload
    try:
        bonds, macro = bonos_feed.process_market_data(force=force)
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
        if has_missing_revenue_ps():
            from engine.data_seeder import backfill_revenue_ps
            backfill_revenue_ps()
    except Exception as e:
        print("[AVISO] Error al inicializar DB:", e)
    # statsmodels tarda ~1.5 s en importar y solo lo usa la pestaña de auditoria
    threading.Thread(target=valoracion_api._warm_up_econometrics, daemon=True).start()

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

# La app no usa cookies ni sesiones: con origen "*" las credenciales deben ir desactivadas
# (la combinacion "*" + credentials es invalida segun la especificacion CORS).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Comprime HTML/JS/CSS/JSON (chart.min.js: ~205 KB -> ~70 KB). Las respuestas < 1 KB no se comprimen.
app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=6)

_VENDOR_LIBS = ("chart.min.js", "chart.umd.min.js")

@app.middleware("http")
async def add_cache_control_headers(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path in ["/", "/index.html"] or path.endswith(".html") or "/shared" in path:
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    elif path.endswith(_VENDOR_LIBS):
        # Librerias de terceros: no cambian, se pueden cachear un dia entero
        response.headers["Cache-Control"] = "public, max-age=86400"
    elif path.endswith((".js", ".css")):
        # Codigo propio: el navegador cachea pero REVALIDA con ETag (304 barato) -> nunca queda desactualizado
        response.headers["Cache-Control"] = "no-cache"
    return response


# ==================== 1. BONOS API ENDPOINTS ====================
@app.get("/api/data")
def get_bonos_data():
    update_bonos_worker()
    return cached_bonos_payload

@app.get("/api/refresh")
def refresh_bonos_data():
    update_bonos_worker(force=True)
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
    if not bond_item.get("van_eligible", False):
        return {"error": "Instrumento excluido del VAN", "reason": bond_item.get("van_exclusion_reason", "")}
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
# Handlers definidos en apps/valoracion/engine/api.py; se registran aqui para servirlos desde este unico servidor.
for _path, _handler, _method in (
    ("/api/health", valoracion_api.health_check, "GET"),
    ("/api/sectors", valoracion_api.list_sectors, "GET"),
    ("/api/sectors/{sector_name}", valoracion_api.sector_stocks, "GET"),
    ("/api/stocks/{ticker}", valoracion_api.stock_detail, "GET"),
    ("/api/stocks/{ticker}/monte-carlo", valoracion_api.run_monte_carlo, "POST"),
    ("/api/stocks/{ticker}/econometrics", valoracion_api.econometric_audit, "GET"),
    ("/api/stocks/{ticker}/export-csv", valoracion_api.export_estimation_csv, "GET"),
    ("/api/stocks/{ticker}/refresh", valoracion_api.refresh_stock, "POST"),
):
    app.add_api_route(_path, _handler, methods=[_method])


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
        return fama_ctrl.analyze_sector(sector_id, model, period, bool(payload.get("force_refresh", False)))
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
