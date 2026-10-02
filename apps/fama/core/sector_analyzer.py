import pandas as pd
import numpy as np
import yfinance as yf
from typing import Dict, Any, List
from core.data_fetcher import DataFetcher
from core.fama_french_engine import FamaFrenchEngine

SP500_SECTORS = {
    "tech": {
        "id": "tech",
        "name": "Tecnología de la Información",
        "etf": "XLK",
        "description": "Semiconductores, software empresarial, hardware y servicios cloud.",
        "tickers": [
            {"symbol": "AAPL", "name": "Apple Inc."},
            {"symbol": "MSFT", "name": "Microsoft Corp."},
            {"symbol": "NVDA", "name": "NVIDIA Corp."},
            {"symbol": "AVGO", "name": "Broadcom Inc."},
            {"symbol": "ORCL", "name": "Oracle Corp."},
            {"symbol": "CRM", "name": "Salesforce Inc."},
            {"symbol": "AMD", "name": "Advanced Micro Devices"},
            {"symbol": "QCOM", "name": "Qualcomm Inc."},
            {"symbol": "ADBE", "name": "Adobe Inc."},
            {"symbol": "INTC", "name": "Intel Corp."}
        ]
    },
    "financials": {
        "id": "financials",
        "name": "Finanzas & Banca",
        "etf": "XLF",
        "description": "Banca comercial, banca de inversión, seguros y servicios de pago.",
        "tickers": [
            {"symbol": "JPM", "name": "JPMorgan Chase & Co."},
            {"symbol": "BAC", "name": "Bank of America Corp."},
            {"symbol": "WFC", "name": "Wells Fargo & Co."},
            {"symbol": "GS", "name": "Goldman Sachs Group"},
            {"symbol": "MS", "name": "Morgan Stanley"},
            {"symbol": "BLK", "name": "BlackRock Inc."},
            {"symbol": "C", "name": "Citigroup Inc."},
            {"symbol": "AXP", "name": "American Express Co."},
            {"symbol": "V", "name": "Visa Inc."},
            {"symbol": "MA", "name": "Mastercard Inc."}
        ]
    },
    "healthcare": {
        "id": "healthcare",
        "name": "Salud & Farmacéutica",
        "etf": "XLV",
        "description": "Farmacéuticas, biotecnología, dispositivos médicos y seguros médicos.",
        "tickers": [
            {"symbol": "LLY", "name": "Eli Lilly and Co."},
            {"symbol": "UNH", "name": "UnitedHealth Group"},
            {"symbol": "JNJ", "name": "Johnson & Johnson"},
            {"symbol": "ABBV", "name": "AbbVie Inc."},
            {"symbol": "MRK", "name": "Merck & Co."},
            {"symbol": "TMO", "name": "Thermo Fisher Scientific"},
            {"symbol": "PFE", "name": "Pfizer Inc."},
            {"symbol": "ABT", "name": "Abbott Laboratories"},
            {"symbol": "AMGN", "name": "Amgen Inc."},
            {"symbol": "DHR", "name": "Danaher Corp."}
        ]
    },
    "consumer_disc": {
        "id": "consumer_disc",
        "name": "Consumo Discrecional",
        "etf": "XLY",
        "description": "Comercio electrónico, automotriz, restaurantes y venta minorista no esencial.",
        "tickers": [
            {"symbol": "AMZN", "name": "Amazon.com Inc."},
            {"symbol": "TSLA", "name": "Tesla Inc."},
            {"symbol": "HD", "name": "Home Depot Inc."},
            {"symbol": "MCD", "name": "McDonald's Corp."},
            {"symbol": "NKE", "name": "NIKE Inc."},
            {"symbol": "SBUX", "name": "Starbucks Corp."},
            {"symbol": "LOW", "name": "Lowe's Companies"},
            {"symbol": "BKNG", "name": "Booking Holdings"},
            {"symbol": "TJX", "name": "TJX Companies"},
            {"symbol": "TGT", "name": "Target Corp."}
        ]
    },
    "comm_services": {
        "id": "comm_services",
        "name": "Servicios de Comunicación",
        "etf": "XLC",
        "description": "Medios interactivos, redes sociales, streaming y telecomunicaciones.",
        "tickers": [
            {"symbol": "GOOGL", "name": "Alphabet Inc. (Google)"},
            {"symbol": "META", "name": "Meta Platforms Inc."},
            {"symbol": "NFLX", "name": "Netflix Inc."},
            {"symbol": "DIS", "name": "Walt Disney Co."},
            {"symbol": "CMCSA", "name": "Comcast Corp."},
            {"symbol": "VZ", "name": "Verizon Communications"},
            {"symbol": "T", "name": "AT&T Inc."},
            {"symbol": "TMUS", "name": "T-Mobile US"},
            {"symbol": "EA", "name": "Electronic Arts"},
            {"symbol": "CHTR", "name": "Charter Communications"}
        ]
    },
    "industrials": {
        "id": "industrials",
        "name": "Industriales & Manufactura",
        "etf": "XLI",
        "description": "Aeroespacial, defensa, transporte ferroviario, maquinaria pesada y logística.",
        "tickers": [
            {"symbol": "GE", "name": "GE Aerospace"},
            {"symbol": "CAT", "name": "Caterpillar Inc."},
            {"symbol": "UNP", "name": "Union Pacific Corp."},
            {"symbol": "HON", "name": "Honeywell International"},
            {"symbol": "BA", "name": "Boeing Co."},
            {"symbol": "RTX", "name": "RTX Corporation"},
            {"symbol": "DE", "name": "Deere & Co."},
            {"symbol": "LMT", "name": "Lockheed Martin Corp."},
            {"symbol": "UPS", "name": "United Parcel Service"},
            {"symbol": "EMR", "name": "Emerson Electric Co."}
        ]
    },
    "consumer_staples": {
        "id": "consumer_staples",
        "name": "Consumo Básico (Defensivo)",
        "etf": "XLP",
        "description": "Alimentos, bebidas, tabaco, hipermercados y productos de higiene.",
        "tickers": [
            {"symbol": "WMT", "name": "Walmart Inc."},
            {"symbol": "PG", "name": "Procter & Gamble Co."},
            {"symbol": "COST", "name": "Costco Wholesale Corp."},
            {"symbol": "KO", "name": "Coca-Cola Co."},
            {"symbol": "PEP", "name": "PepsiCo Inc."},
            {"symbol": "PM", "name": "Philip Morris International"},
            {"symbol": "MO", "name": "Altria Group Inc."},
            {"symbol": "CL", "name": "Colgate-Palmolive Co."},
            {"symbol": "MDLZ", "name": "Mondelez International"},
            {"symbol": "KMB", "name": "Kimberly-Clark Corp."}
        ]
    },
    "energy": {
        "id": "energy",
        "name": "Energía & Petróleo",
        "etf": "XLE",
        "description": "Exploración petrolera, refinación, gas natural y servicios petroleros.",
        "tickers": [
            {"symbol": "XOM", "name": "Exxon Mobil Corp."},
            {"symbol": "CVX", "name": "Chevron Corp."},
            {"symbol": "COP", "name": "ConocoPhillips"},
            {"symbol": "EOG", "name": "EOG Resources"},
            {"symbol": "SLB", "name": "Schlumberger Ltd."},
            {"symbol": "MPC", "name": "Marathon Petroleum"},
            {"symbol": "PSX", "name": "Phillips 66"},
            {"symbol": "VLO", "name": "Valero Energy Corp."},
            {"symbol": "OXY", "name": "Occidental Petroleum"},
            {"symbol": "WMB", "name": "Williams Companies"}
        ]
    },
    "utilities": {
        "id": "utilities",
        "name": "Servicios Públicos (Utilities)",
        "etf": "XLU",
        "description": "Generación y distribución eléctrica, agua y redes de gas.",
        "tickers": [
            {"symbol": "NEE", "name": "NextEra Energy"},
            {"symbol": "SO", "name": "Southern Company"},
            {"symbol": "DUK", "name": "Duke Energy Corp."},
            {"symbol": "CEG", "name": "Constellation Energy"},
            {"symbol": "SRE", "name": "Sempra"},
            {"symbol": "AEP", "name": "American Electric Power"},
            {"symbol": "D", "name": "Dominion Energy"},
            {"symbol": "PEG", "name": "Public Service Enterprise Group"},
            {"symbol": "EXC", "name": "Exelon Corp."},
            {"symbol": "ED", "name": "Consolidated Edison"}
        ]
    },
    "real_estate": {
        "id": "real_estate",
        "name": "Bienes Raíces (REITs)",
        "etf": "XLRE",
        "description": "Fideicomisos inmobiliarios, centros de datos, torres de telecomunicaciones y logística.",
        "tickers": [
            {"symbol": "PLD", "name": "Prologis Inc."},
            {"symbol": "AMT", "name": "American Tower Corp."},
            {"symbol": "EQIX", "name": "Equinix Inc."},
            {"symbol": "CCI", "name": "Crown Castle Inc."},
            {"symbol": "PSA", "name": "Public Storage"},
            {"symbol": "O", "name": "Realty Income Corp."},
            {"symbol": "SPG", "name": "Simon Property Group"},
            {"symbol": "WELL", "name": "Welltower Inc."},
            {"symbol": "DLR", "name": "Digital Realty Trust"},
            {"symbol": "SBAC", "name": "SBA Communications"}
        ]
    },
    "materials": {
        "id": "materials",
        "name": "Materiales Básicos",
        "etf": "XLB",
        "description": "Químicos industriales, minería, metales, gases industriales y envases.",
        "tickers": [
            {"symbol": "LIN", "name": "Linde plc"},
            {"symbol": "APD", "name": "Air Products and Chemicals"},
            {"symbol": "SHW", "name": "Sherwin-Williams Co."},
            {"symbol": "FCX", "name": "Freeport-McMoRan Inc."},
            {"symbol": "ECL", "name": "Ecolab Inc."},
            {"symbol": "NEM", "name": "Newmont Corp."},
            {"symbol": "CTVA", "name": "Corteva Inc."},
            {"symbol": "DD", "name": "DuPont de Nemours"},
            {"symbol": "DOW", "name": "Dow Inc."},
            {"symbol": "ALB", "name": "Albemarle Corp."}
        ]
    }
}

class SectorAnalyzer:
    def __init__(self, data_fetcher: DataFetcher):
        self.fetcher = data_fetcher
        self.cache = {}

    def get_all_sectors_metadata(self) -> List[Dict[str, Any]]:
        result = []
        for s_id, s_data in SP500_SECTORS.items():
            result.append({
                "id": s_id,
                "name": s_data["name"],
                "etf": s_data["etf"],
                "description": s_data["description"],
                "stocks_count": len(s_data["tickers"])
            })
        return result

    def analyze_sector(self, sector_id: str, model_type: str = "FF5", period: str = "2y") -> Dict[str, Any]:
        """
        Performs batch multi-factor Fama-French estimation and financial decision assessment
        for all constituent stocks in the selected S&P 500 sector.
        """
        if sector_id not in SP500_SECTORS:
            sector_id = "tech"

        sector_info = SP500_SECTORS[sector_id]
        tickers_list = [t["symbol"] for t in sector_info["tickers"]]
        name_map = {t["symbol"]: t["name"] for t in sector_info["tickers"]}

        # Check in-memory cache (valid for session or 15 mins)
        cache_key = f"{sector_id}_{model_type}_{period}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        # 1. Ensure Kenneth French factors are loaded
        ff_df = self.fetcher.get_fama_french_factors()

        # 2. Batch download historical close prices
        try:
            download_df = yf.download(tickers_list, period=period, auto_adjust=True, progress=False)
            if download_df.empty or "Close" not in download_df:
                raise ValueError("No se pudieron descargar los datos del sector.")
            closes = download_df["Close"]
        except Exception as e:
            raise RuntimeError(f"Error descargando datos del sector {sector_info['name']}: {str(e)}")

        engine = FamaFrenchEngine(model_type=model_type)
        stock_results = []

        buy_count = 0
        hold_count = 0
        sell_count = 0

        for symbol in tickers_list:
            try:
                if symbol not in closes.columns:
                    continue

                s_series = closes[symbol].dropna()
                if len(s_series) < 30:
                    continue

                current_price = float(s_series.iloc[-1])

                # Build stock df
                s_df = pd.DataFrame({
                    "Date": pd.to_datetime(s_series.index.date),
                    "Close": s_series.values
                })
                s_df["Return"] = s_df["Close"].pct_change()

                # Align with Fama-French factors
                merged = pd.merge(s_df, ff_df, on="Date", how="inner").dropna()
                merged["Stock_Excess_Return"] = merged["Return"] - merged["RF"]

                if len(merged) < 30:
                    continue

                # Estimate model
                est = engine.estimate(merged, cov_type="HAC")
                
                params_dict = {p["factor"]: p for p in est["econometrics"]["parameters"]}
                beta_mkt = params_dict.get("Mkt-RF", {}).get("coef", 1.0)
                beta_smb = params_dict.get("SMB", {}).get("coef", 0.0)
                beta_hml = params_dict.get("HML", {}).get("coef", 0.0)
                alpha_ann = est["alpha_annual"]
                alpha_pval = est["alpha_pvalue"]
                ke = est["cost_of_equity"]
                r2 = est["econometrics"]["summary_metrics"]["r_squared"]

                # Fetch basic valuation multiples (cached fast)
                pe_ratio = None
                div_yield = 0.0
                try:
                    t_obj = yf.Ticker(symbol)
                    fast_info = t_obj.fast_info
                    pe_ratio = fast_info.get("peRatio") or None
                except Exception:
                    pass

                # Quantitative Decision Algorithm
                decision = self._compute_financial_decision(
                    ke=ke,
                    alpha_ann=alpha_ann,
                    alpha_pval=alpha_pval,
                    beta_mkt=beta_mkt,
                    pe_ratio=pe_ratio
                )

                if decision["verdict"] == "COMPRAR":
                    buy_count += 1
                elif decision["verdict"] == "VENDER":
                    sell_count += 1
                else:
                    hold_count += 1

                stock_results.append({
                    "symbol": symbol,
                    "name": name_map.get(symbol, symbol),
                    "current_price": current_price,
                    "cost_of_equity": ke,
                    "cost_of_equity_pct": ke * 100.0,
                    "beta_mkt": beta_mkt,
                    "beta_smb": beta_smb,
                    "beta_hml": beta_hml,
                    "alpha_ann_pct": alpha_ann * 100.0,
                    "alpha_pval": alpha_pval,
                    "r_squared_pct": r2 * 100.0,
                    "pe_ratio": float(pe_ratio) if pe_ratio else None,
                    "dividend_yield": div_yield,
                    "decision": decision
                })

            except Exception:
                continue

        # Compute sector averages
        avg_ke = np.mean([s["cost_of_equity_pct"] for s in stock_results]) if stock_results else 0.0
        avg_beta = np.mean([s["beta_mkt"] for s in stock_results]) if stock_results else 1.0
        avg_alpha = np.mean([s["alpha_ann_pct"] for s in stock_results]) if stock_results else 0.0

        output = {
            "sector_id": sector_id,
            "sector_name": sector_info["name"],
            "etf": sector_info["etf"],
            "description": sector_info["description"],
            "total_stocks": len(stock_results),
            "summary": {
                "avg_cost_of_equity_pct": float(avg_ke),
                "avg_beta_mkt": float(avg_beta),
                "avg_alpha_pct": float(avg_alpha),
                "buy_count": buy_count,
                "hold_count": hold_count,
                "sell_count": sell_count
            },
            "stocks": stock_results
        }

        # Cache in memory
        self.cache[cache_key] = output
        return output

    def _compute_financial_decision(self, ke: float, alpha_ann: float, alpha_pval: float, 
                                    beta_mkt: float, pe_ratio: float = None) -> Dict[str, Any]:
        """
        Quantitative decision logic balancing Fama-French systematic risk compensation,
        alpha generation, market sensitivity, and valuation multiples.
        """
        is_alpha_sig = alpha_pval < 0.15

        # Rule 1: Significant positive alpha with solid expected return
        if is_alpha_sig and alpha_ann > 0.035 and ke > 0.08:
            return {
                "verdict": "COMPRAR",
                "color": "bullish",
                "badge": "COMPRAR",
                "reason": f"Genera Alpha anormal positivo significativo (+{alpha_ann*100:.1f}%, p={alpha_pval:.3f}) superando la compensación de factores."
            }

        # Rule 2: Attractive expected return with reasonable beta
        if ke > 0.14 and beta_mkt <= 1.25 and (alpha_ann >= -0.01 or not is_alpha_sig):
            return {
                "verdict": "COMPRAR",
                "color": "bullish",
                "badge": "COMPRAR",
                "reason": f"Alto retorno esperado ({ke*100:.1f}%) con beta controlado ({beta_mkt:.2f})."
            }

        # Rule 3: Significant negative alpha (underperforming systematic factor compensation)
        if is_alpha_sig and alpha_ann < -0.035:
            return {
                "verdict": "VENDER",
                "color": "bearish",
                "badge": "VENDER",
                "reason": f"Alpha negativo persistente ({alpha_ann*100:.1f}%, p={alpha_pval:.3f}). Retorno inferior a las primas de riesgo asumidas."
            }

        # Rule 4: Excessive volatility/beta with insufficient expected return
        if beta_mkt > 1.40 and ke < 0.10:
            return {
                "verdict": "VENDER",
                "color": "bearish",
                "badge": "VENDER",
                "reason": f"Alta sensibilidad al mercado (β={beta_mkt:.2f}) sin retorno esperado suficiente ({ke*100:.1f}%)."
            }

        # Default: Equilibrium / Hold
        return {
            "verdict": "MANTENER",
            "color": "neutral",
            "badge": "MANTENER",
            "reason": f"Retorno en equilibrio con factores de riesgo ({ke*100:.1f}%). Alpha neutro ({alpha_ann*100:+.1f}%)."
        }
