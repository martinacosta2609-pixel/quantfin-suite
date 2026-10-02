"""
Real-time Data Feed Manager.
Fetches official market quotes from BYMA (Bolsas y Mercados Argentinos)
and monetary indicators from BCRA (Banco Central de la República Argentina).
"""
import requests
import urllib3
from datetime import date, datetime
from concurrent.futures import ThreadPoolExecutor
from bonos_engine import BondEngine
from bond_db import get_bond_definition

urllib3.disable_warnings()

class MarketDataFeed:
    def __init__(self):
        self.engine = BondEngine()
        self.bcra_data = {}
        self.macro_summary = {
            "dolar_oficial": 0.0,
            "dolar_mep": 0.0,
            "dolar_ccl": 0.0,
            "brecha_mep": 0.0,
            "tasa_badlar": 0.0,
            "cer": 0.0,
            "uva": 0.0,
            "updated_at": ""
        }
        self.cached_bonds = []
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8"
        }

    def fetch_bcra_indicators(self):
        """Fetches macro variables from official BCRA v4 API."""
        try:
            url = "https://api.bcra.gob.ar/estadisticas/v4.0/monetarias"
            resp = requests.get(url, params={"limit": 2000}, headers=self.headers, verify=False, timeout=8)
            if resp.status_code == 200:
                results = resp.json().get("results", [])
                for item in results:
                    var_id = item.get("idVariable")
                    val = float(item.get("ultValorInformado", 0.0))
                    if var_id == 4:  # TC Minorista
                        self.macro_summary["dolar_oficial"] = val
                    elif var_id == 5 and self.macro_summary["dolar_oficial"] == 0:  # TC Mayorista
                        self.macro_summary["dolar_oficial"] = val
                    elif var_id == 7:  # Tasa BADLAR
                        self.macro_summary["tasa_badlar"] = val
                    elif var_id == 30:  # Coeficiente CER
                        self.macro_summary["cer"] = val
                    elif var_id == 31:  # Unidad UVA
                        self.macro_summary["uva"] = val
                    elif var_id == 27:  # Inflacion Mensual
                        self.macro_summary["inflacion_mensual"] = val
        except Exception as e:
            print("BCRA fetch warning:", e)

    def fetch_byma_page(self, endpoint: str, page: int):
        """Fetches a single page of bonds from BYMA Data."""
        try:
            url = f"https://open.bymadata.com.ar/vanoms-be-core/rest/api/bymadata/free/{endpoint}"
            resp = requests.post(url, json={"page_number": page}, headers=self.headers, timeout=10)
            if resp.status_code == 200:
                return resp.json().get("data", [])
        except Exception as e:
            print(f"BYMA page {page} error ({endpoint}):", e)
        return []

    def fetch_all_byma_bonds(self):
        """Fetches all pages of public bonds and lebacs from BYMA in parallel."""
        all_raw = []
        with ThreadPoolExecutor(max_workers=6) as executor:
            # 6 pages for public-bonds
            futures = [executor.submit(self.fetch_byma_page, "public-bonds", p) for p in range(1, 7)]
            # 2 pages for lebacs
            futures.extend([executor.submit(self.fetch_byma_page, "lebacs", p) for p in range(1, 3)])

            for fut in futures:
                res = fut.result()
                if res:
                    all_raw.extend(res)
        return all_raw

    def process_market_data(self):
        """
        Consolidates quotes, determines MEP/CCL, calculates parity, duration, and returns list.
        """
        # 1. Update BCRA macro
        self.fetch_bcra_indicators()

        # 2. Fetch raw quotes from BYMA
        raw_bonds = self.fetch_all_byma_bonds()
        if not raw_bonds and self.cached_bonds:
            return self.cached_bonds, self.macro_summary

        # 3. Deduplicate / aggregate by symbol preferring 24hs/highest volume
        symbol_map = {}
        for b in raw_bonds:
            sym = b.get("symbol", "").strip()
            if not sym:
                continue
            # If seen, keep the one with higher volumeAmount or active trade
            if sym in symbol_map:
                curr = symbol_map[sym]
                if b.get("volumeAmount", 0) > curr.get("volumeAmount", 0):
                    symbol_map[sym] = b
            else:
                symbol_map[sym] = b

        # 4. Calculate Implied FX (MEP & CCL) from liquid benchmark pairs
        al30_ars = symbol_map.get("AL30", {}).get("trade", 0)
        al30_usd = symbol_map.get("AL30D", {}).get("trade", 0)
        gd30_ars = symbol_map.get("GD30", {}).get("trade", 0)
        gd30_usd = symbol_map.get("GD30D", {}).get("trade", 0)
        gd30_ccl = symbol_map.get("GD30C", {}).get("trade", 0)

        mep = 0.0
        if al30_ars > 0 and al30_usd > 0:
            mep = al30_ars / al30_usd
        elif gd30_ars > 0 and gd30_usd > 0:
            mep = gd30_ars / gd30_usd
        else:
            mep = 1550.0  # Safe fallback if market closed

        ccl = 0.0
        if gd30_ars > 0 and gd30_ccl > 0:
            ccl = gd30_ars / gd30_ccl
        elif mep > 0:
            ccl = mep * 1.025  # Normal typical spread

        self.macro_summary["dolar_mep"] = round(mep, 2)
        self.macro_summary["dolar_ccl"] = round(ccl, 2)
        oficial = self.macro_summary.get("dolar_oficial", 0.0)
        if oficial > 0 and mep > 0:
            self.macro_summary["brecha_mep"] = round(((mep / oficial) - 1.0) * 100.0, 2)

        self.macro_summary["updated_at"] = datetime.now().strftime("%H:%M:%S")

        # 5. Calculate Valuation Metrics for all bonds
        settle_date = date.today()
        processed_list = []

        for sym, b in symbol_map.items():
            trade_price = float(b.get("trade", 0) or b.get("closingPrice", 0) or 0)
            if trade_price <= 0:
                continue

            ccy = b.get("denominationCcy", "ARS")
            vol_amount = float(b.get("volumeAmount", 0) or 0)
            vol_nom = float(b.get("volume", 0) or 0)
            change_pct = float(b.get("imbalance", 0) or 0) * 100.0
            trade_hour = b.get("tradeHour") or "Cierre"
            maturity_str = b.get("maturityDate") or ""
            days_to_mat = int(b.get("daysToMaturity") or 0)

            # Check if bond has known full schedule
            calc = self.engine.calculate_sovereign_metrics(sym, trade_price, ccy, settle_date, mep)
            is_sovereign = bool(calc)

            if not calc:
                # Generic calculation for Letras / Lebacs / Boncer / other issues
                calc = self.engine.calculate_generic_metrics(sym, trade_price, ccy, maturity_str, days_to_mat)

            if not calc:
                continue

            bond_item = {
                "symbol": sym,
                "name": calc.get("name", sym),
                "type": calc.get("type", "Bono Público"),
                "law": calc.get("law", "Argentina"),
                "ccy": ccy,
                "currency": ccy,
                "price": round(trade_price, 2) if ccy == "ARS" else round(trade_price, 3),
                "eval_price": calc.get("eval_price", trade_price),
                "eval_price_usd": calc.get("eval_price", trade_price),
                "change_pct": round(change_pct, 2),
                "vt": calc.get("vt", 100.0),
                "vr": calc.get("vr", 100.0),
                "accrued": calc.get("accrued", 0.0),
                "parity": calc.get("parity", 0.0),
                "tir": calc.get("tir", 0.0),
                "duration": calc.get("macaulay_duration", 0.0),
                "mod_duration": calc.get("modified_duration", 0.0),
                "current_yield": calc.get("current_yield", 0.0),
                "maturity_date": calc.get("maturity_date", maturity_str),
                "next_payment": calc.get("next_payment_date", "-"),
                "volume_amount": round(vol_amount, 2),
                "volume_nom": int(vol_nom),
                "trade_hour": trade_hour,
                "is_sovereign": is_sovereign,
                "cashflows": calc.get("cashflows", [])
            }
            processed_list.append(bond_item)

        # Sort by volume amount descending by default
        processed_list.sort(key=lambda x: x["volume_amount"], reverse=True)
        self.cached_bonds = processed_list
        return processed_list, self.macro_summary
