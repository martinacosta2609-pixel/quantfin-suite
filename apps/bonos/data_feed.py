"""
Real-time Data Feed Manager.
Fetches official market quotes from BYMA (Bolsas y Mercados Argentinos)
and monetary indicators from BCRA (Banco Central de la República Argentina).

What the sources actually send (audited 2026-10-08, see `qa` block in the payload):
  * BYMA  -> prices only (trade / closingPrice / previousClosingPrice per 100 VN), `denominationCcy`
             (QUOTE currency: ARS, USD=MEP, EXT=cable), `maturityDate`, `daysToMaturity` and `imbalance`
             (daily change as a DECIMAL). It never sends TIR, coupon, VT or the payment currency.
  * BYMA cauciones -> `trade` is the rate as a DECIMAL TNA (0.223 = 22.3% TNA), not a price.
  * BCRA  -> `ultValorInformado` already in PERCENT for rates/inflation; CER/UVA as index levels.
Every yield published by this module is therefore computed by bonos_engine.py, always in PERCENT.
"""
import json
import os
import re
import tempfile
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

import requests
import urllib3

from bonos_engine import BondEngine
from bond_db import SOVEREIGN_BONDS, get_bond_definition

urllib3.disable_warnings()

BYMA_BASE = "https://open.bymadata.com.ar/vanoms-be-core/rest/api/bymadata/free/"
BCRA_BASE = "https://api.bcra.gob.ar/estadisticas/v4.0/monetarias"
LETRAS_URL = "https://api.argentinadatos.com/v1/finanzas/letras"

# BYMA free endpoints that carry fixed income. (endpoint, source family)
# Fideicomisos financieros and MAE-only instruments have no free BYMA endpoint.
BYMA_ENDPOINTS = (
    ("public-bonds", "bono"),             # soberanos, Bopreales, CER, duales, provinciales
    ("lebacs", "letra"),                  # Lecaps, Lecer, letras dólar linked, letras provinciales
    ("negociable-obligations", "on"),     # ONs corporativas
    ("cauciones", "caucion"),
)
PAGE_SIZE = 10000
MAX_PAGES = 30

QUOTES_TTL = 20          # s - BYMA delayed quotes
MACRO_TTL = 600          # s - BCRA principales variables
SLOW_TTL = 6 * 3600      # s - CER series and Lecap redemption values

# Lecap (S) / Boncap (T) capitalizables: S30O6, T15E7...
LECAP_RE = re.compile(r"^[ST]\d{2}[A-Z]\d$")
# National CER tickers without a schedule in bond_db (classification only, never used to price).
CER_RE = re.compile(r"^(TX\d\d|TZX|TC\d\d|DICP|DIP0|PARP|PAP0|CUAP)")
BOPREAL_RE = re.compile(r"^BP[A-Z0-9]")
SOV_USD_RE = re.compile(r"^(AL|GD|AE|AN|AO)\d\d")
# Provincial / municipal issuers (inferred from the ticker: BYMA has no issuer field).
SUBSOV_RE = re.compile(
    r"^(PBA|PBM|PBY|BA37|BB37|BC37|BA7D|BB7D|BC7D|BDC|BC\d\d|CO\d|CO2|CO3|COD|COY|CY27|NDT|NDG|SFD|SFN|SA24|S24D|"
    r"SJO|ERF|ERM|ERE|EE27|CH24|CHAQ|PMM|PMD|PMA|PM29|PUL|PUA|TFU|JUS|RNG|RNA|TUC|FOR|MIS|CABA)")

FAMILY_LABEL = {
    "soberano_usd": "Soberano USD",
    "bopreal": "Bopreal BCRA",
    "cer": "Boncer (CER)",
    "letra": "Letra",
    "subsoberano": "Subsoberano (inferido)",
    "bono_otro": "Título público",
    "on": "Obligación Negociable",
    "caucion": "Caución",
}


def _f(value, default=0.0):
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def business_days_back(d: date, n: int) -> date:
    """n business days before d (weekends only; local holidays shift it by at most a few days)."""
    while n > 0:
        d -= timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


class MarketDataFeed:
    def __init__(self):
        self.engine = BondEngine()
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
        self._lock = threading.Lock()
        self._last_quotes_ts = 0.0
        self._last_macro_ts = 0.0
        self._last_cer_ts = 0.0
        self._last_letras_ts = 0.0
        self._cer_series = {}          # "YYYY-MM-DD" -> CER
        self._letras_rescate = {}      # ticker -> redemption per 100 VN
        self._errors = []
        self._snapshot_path = os.path.join(tempfile.gettempdir(), "bonos_ar_last_payload.json")
        self._last_snapshot_ts = 0.0

    # ------------------------------------------------------------------ BCRA
    def fetch_bcra_indicators(self):
        """Fetches macro variables from official BCRA v4 API (values already in % / index level)."""
        try:
            resp = requests.get(BCRA_BASE, params={"limit": 2000}, headers=self.headers, verify=False, timeout=8)
            if resp.status_code == 200:
                wanted = {
                    4: "dolar_oficial",            # TC minorista
                    7: "tasa_badlar",              # % TNA
                    44: "tasa_tamar",              # % TNA
                    27: "inflacion_mensual",       # % mensual
                    28: "inflacion_interanual",    # % i.a.
                    29: "inflacion_esperada_12m",  # % REM próximos 12 meses
                    30: "cer",
                    31: "uva",
                }
                mayorista = 0.0
                for item in resp.json().get("results", []):
                    var_id = item.get("idVariable")
                    if var_id in wanted:
                        self.macro_summary[wanted[var_id]] = _f(item.get("ultValorInformado"))
                    elif var_id == 5:
                        mayorista = _f(item.get("ultValorInformado"))
                if not self.macro_summary.get("dolar_oficial"):
                    self.macro_summary["dolar_oficial"] = mayorista
                self._last_macro_ts = time.time()
        except Exception as e:
            self._errors.append(f"BCRA: {e}")
            print("BCRA fetch warning:", e)

    def fetch_cer_series(self, settle: date):
        """Daily CER around the settlement date, to apply the prospectus lag (t - 10 business days)."""
        try:
            params = {"desde": (settle - timedelta(days=30)).isoformat(), "hasta": settle.isoformat(), "limit": 100}
            resp = requests.get(f"{BCRA_BASE}/30", params=params, headers=self.headers, verify=False, timeout=8)
            if resp.status_code == 200:
                results = resp.json().get("results", [])
                detalle = results[0].get("detalle", []) if results else []
                series = {d["fecha"]: _f(d["valor"]) for d in detalle if d.get("valor")}
                if series:
                    self._cer_series = series
                    self._last_cer_ts = time.time()
        except Exception as e:
            self._errors.append(f"BCRA CER: {e}")
            print("BCRA CER series warning:", e)

    def cer_for_valuation(self, settle: date):
        """CER applicable to a settlement date: published value of t-10 business days. Returns (cer, date_str)."""
        target = business_days_back(settle, 10)
        for back in range(0, 7):
            key = (target - timedelta(days=back)).isoformat()
            if key in self._cer_series:
                return self._cer_series[key], key
        return self.macro_summary.get("cer", 0.0), "último publicado (sin rezago)"

    # ------------------------------------------------------- Lecap redemption
    def fetch_letras_rescate(self):
        """
        Redemption value per 100 VN of capitalizing Lecaps/Boncaps. BYMA does not publish it, so it is
        derived from argentinadatos.com (price, TNA simple base 360 and days of the same snapshot):
        rescate = precio * (1 + TNA * días / 360). It is a constant of the instrument; the live yield
        is then recomputed here against BYMA's price.
        """
        try:
            resp = requests.get(LETRAS_URL, headers=self.headers, timeout=10)
            if resp.status_code != 200:
                return
            table = {}
            for l in resp.json().get("letras", []):
                ticker = str(l.get("ticker", "")).upper()
                px, tna, tem, days = _f(l.get("precioArs")), _f(l.get("tnaPorcentaje")), _f(l.get("temPorcentaje")), int(_f(l.get("diasAlVencimiento")))
                if not LECAP_RE.match(ticker) or px <= 0 or tna <= 0 or tem <= 0 or days <= 0:
                    continue
                by_tna = px * (1.0 + tna / 100.0 * days / 360.0)
                by_tem = px * (1.0 + tem / 100.0) ** (days / 30.0)
                # Both published rates must describe the same redemption, otherwise it is not a bullet.
                if abs(by_tna / by_tem - 1.0) < 0.002:
                    table[ticker] = by_tna
            if table:
                self._letras_rescate = table
                self._last_letras_ts = time.time()
        except Exception as e:
            self._errors.append(f"Letras: {e}")
            print("Letras rescate warning:", e)

    # ------------------------------------------------------------------ BYMA
    def fetch_byma_bulk(self, endpoint: str, family: str = ""):
        """Fetches ALL rows of a BYMA endpoint, following pagination until `page_count` is exhausted."""
        url = BYMA_BASE + endpoint
        rows, seen = [], set()
        try:
            for page in range(1, MAX_PAGES + 1):
                body = {"excludeZeroPxAndQty": False, "page_number": page, "page_size": PAGE_SIZE}
                resp = requests.post(url, json=body, headers=self.headers, verify=False, timeout=25)
                if resp.status_code != 200:
                    self._errors.append(f"BYMA {endpoint}: HTTP {resp.status_code}")
                    break
                data = resp.json()
                chunk = (data.get("data") or []) if isinstance(data, dict) else (data or [])
                meta = (data.get("content") or {}) if isinstance(data, dict) else {}
                new_rows = 0
                for r in chunk:
                    key = (r.get("symbol"), r.get("settlementType"), r.get("denominationCcy"))
                    if key in seen:
                        continue
                    seen.add(key)
                    r["_family"] = family
                    rows.append(r)
                    new_rows += 1
                page_count = int(meta.get("page_count") or 0)
                if new_rows == 0 or (page_count and page >= page_count) or (not page_count and len(chunk) < PAGE_SIZE):
                    break
        except Exception as e:
            self._errors.append(f"BYMA {endpoint}: {e}")
            print(f"BYMA bulk fetch error ({endpoint}):", e)
        return rows

    def fetch_all_byma_bonds(self):
        """Fetches the complete fixed-income market from all BYMA endpoints in parallel."""
        all_raw, counts = [], {}
        with ThreadPoolExecutor(max_workers=len(BYMA_ENDPOINTS)) as executor:
            futures = [(ep, executor.submit(self.fetch_byma_bulk, ep, fam)) for ep, fam in BYMA_ENDPOINTS]
            for ep, fut in futures:
                res = fut.result() or []
                counts[ep] = len(res)
                all_raw.extend(res)
        return all_raw, counts

    # --------------------------------------------------------- classification
    @staticmethod
    def reference_price(row: dict):
        """Last trade, else today's close, else previous close. Returns (price, source)."""
        for field, source in (("trade", "ultimo"), ("closingPrice", "cierre"), ("previousClosingPrice", "cierre_anterior")):
            px = _f(row.get(field))
            if px > 0:
                return px, source
        return 0.0, ""

    @staticmethod
    def _row_score(row: dict):
        """Among T+0 / T+1 rows of one symbol: traded today first, then volume, then 24hs."""
        return (1 if _f(row.get("trade")) > 0 else 0, _f(row.get("volumeAmount")), 1 if str(row.get("settlementType")) == "2" else 0)

    @staticmethod
    def segment_of(symbol: str, ccy: str) -> str:
        """BYMA bilateral segment (SENEBI) tickers end in X (ARS), Y (USD) or Z (cable)."""
        if symbol in SOVEREIGN_BONDS:
            return "PPT"
        last = symbol[-1:]
        if (ccy == "ARS" and last == "X") or (ccy == "USD" and last == "Y") or (ccy == "EXT" and last == "Z"):
            return "SENEBI"
        return "PPT"

    @staticmethod
    def _schedule_matches(info: dict, byma_maturity: str) -> bool:
        """A prospectus schedule is only trusted if its maturity agrees with BYMA's (±10 days)."""
        try:
            db_mat = datetime.strptime(info.get("maturity_date", "")[:10], "%Y-%m-%d").date()
            byma_mat = datetime.strptime((byma_maturity or "")[:10], "%Y-%m-%d").date()
        except ValueError:
            return True   # nothing to compare against
        return abs((db_mat - byma_mat).days) <= 10

    def classify(self, symbol: str, source_family: str, info: dict):
        """Returns (family, type_label). Uses the prospectus DB first, then the endpoint, then the ticker."""
        if source_family == "caucion":
            return "caucion", FAMILY_LABEL["caucion"]
        if source_family == "on":
            return "on", FAMILY_LABEL["on"]
        if info:
            if info.get("is_cer"):
                return "cer", info.get("type", FAMILY_LABEL["cer"])
            if "Bopreal" in info.get("type", ""):
                return "bopreal", info["type"]
            if info.get("currency") == "USD":
                return "soberano_usd", info.get("type", FAMILY_LABEL["soberano_usd"])
        if symbol in self._letras_rescate or LECAP_RE.match(symbol):
            return "letra", "Boncap (tasa fija)" if symbol.startswith("T") else "Lecap (tasa fija)"
        if source_family == "letra":
            sub = {"S": "Lecap", "X": "Lecer (CER)", "D": "Letra dólar linked"}.get(symbol[:1], "Letra (provincial / otra)")
            return "letra", sub
        if CER_RE.match(symbol):
            return "cer", "Título CER (sin cronograma)"
        if BOPREAL_RE.match(symbol):
            return "bopreal", "Bopreal BCRA (sin cronograma)"
        if SOV_USD_RE.match(symbol):
            return "soberano_usd", "Soberano USD (sin cronograma)"
        if SUBSOV_RE.match(symbol):
            return "subsoberano", FAMILY_LABEL["subsoberano"]
        return "bono_otro", FAMILY_LABEL["bono_otro"]

    # ---------------------------------------------------------------- pipeline
    def process_market_data(self, force: bool = False):
        """
        Consolidates quotes, determines MEP/CCL, calculates parity, TIR, duration and returns
        (bonds, macro). Results are reused for QUOTES_TTL seconds so several clients (desktop window,
        phone, browser) polling every 30s do not multiply the calls to BYMA / BCRA.
        """
        with self._lock:
            now = time.time()
            if not force and self.cached_bonds and (now - self._last_quotes_ts) < QUOTES_TTL:
                return self.cached_bonds, self.macro_summary
            self._errors = []
            settle_date = date.today()

            # 1. Slow-moving references
            if now - self._last_macro_ts > MACRO_TTL:
                self.fetch_bcra_indicators()
            if now - self._last_cer_ts > SLOW_TTL:
                self.fetch_cer_series(settle_date)
            if now - self._last_letras_ts > SLOW_TTL:
                self.fetch_letras_rescate()

            # 2. Raw quotes from BYMA (every endpoint, every page)
            raw_rows, raw_counts = self.fetch_all_byma_bonds()
            if not raw_rows:
                return self._serve_stale("BYMA no devolvió datos")

            # 3. One row per symbol
            symbol_map = {}
            for r in raw_rows:
                sym = str(r.get("symbol", "")).strip()
                if not sym:
                    continue
                curr = symbol_map.get(sym)
                if curr is None or self._row_score(r) > self._row_score(curr):
                    symbol_map[sym] = r

            # 4. Implied FX (MEP & CCL) from liquid benchmark pairs
            def px(sym):
                return self.reference_price(symbol_map.get(sym, {}))[0]

            mep = 0.0
            for ars_sym, usd_sym in (("AL30", "AL30D"), ("GD30", "GD30D")):
                if px(ars_sym) > 0 and px(usd_sym) > 0:
                    mep = px(ars_sym) / px(usd_sym)
                    break
            ccl = 0.0
            for ars_sym, ext_sym in (("GD30", "GD30C"), ("AL30", "AL30C")):
                if px(ars_sym) > 0 and px(ext_sym) > 0:
                    ccl = px(ars_sym) / px(ext_sym)
                    break
            if mep <= 0:
                return self._serve_stale("Sin par AL30/AL30D ni GD30/GD30D para calcular el dólar MEP")
            if ccl <= 0:
                ccl = mep

            self.macro_summary["dolar_mep"] = round(mep, 2)
            self.macro_summary["dolar_ccl"] = round(ccl, 2)
            oficial = self.macro_summary.get("dolar_oficial", 0.0)
            if oficial > 0:
                self.macro_summary["brecha_mep"] = round(((mep / oficial) - 1.0) * 100.0, 2)

            cer_val, cer_date = self.cer_for_valuation(settle_date)
            self.macro_summary["cer_valuacion"] = cer_val
            self.macro_summary["cer_valuacion_fecha"] = cer_date

            # 5. Valuation metrics
            processed_list = []
            dropped_no_price = 0
            for sym, b in symbol_map.items():
                item = self._build_item(sym, b, settle_date, mep, ccl, cer_val)
                if item is None:
                    dropped_no_price += 1
                    continue
                processed_list.append(item)

            processed_list.sort(key=lambda x: x["volume_amount"], reverse=True)

            self.macro_summary["updated_at"] = datetime.now().strftime("%H:%M:%S")
            self.macro_summary["data_status"] = "live"
            self.macro_summary["qa"] = {
                "byma_filas_crudas": raw_counts,
                "simbolos_unicos": len(symbol_map),
                "descartados_sin_precio": dropped_no_price,
                "publicados": len(processed_list),
                "por_familia": dict(Counter(i["family"] for i in processed_list)),
                "con_tir": dict(Counter(i["family"] for i in processed_list if i["tir"] is not None)),
                "con_flujos": sum(1 for i in processed_list if i["cashflows"]),
                "calidad_tir": dict(Counter(i["tir_quality"] for i in processed_list)),
                "lecaps_con_rescate": sorted(self._letras_rescate.keys()),
                "cer_valuacion": f"{cer_val:.4f} ({cer_date})",
                "errores": list(self._errors),
            }
            self._qa_print(processed_list)

            self.cached_bonds = processed_list
            self._last_quotes_ts = time.time()
            self._save_snapshot()
            return processed_list, self.macro_summary

    def _build_item(self, sym: str, b: dict, settle_date: date, mep: float, ccl: float, cer_val: float):
        price, price_source = self.reference_price(b)
        if price <= 0:
            return None

        ccy = b.get("denominationCcy") or "ARS"
        source_family = b.get("_family", "bono")
        maturity_str = b.get("maturityDate") or ""
        days_to_mat = int(_f(b.get("daysToMaturity")))
        info = get_bond_definition(sym)
        if info and not self._schedule_matches(info, maturity_str):
            # The ticker resolved to a prospectus whose maturity is not the one BYMA reports:
            # it is a different instrument, so its schedule must not be used.
            self._errors.append(f"{sym}: cronograma cargado vence {info.get('maturity_date')} pero BYMA informa {maturity_str}")
            info = None
        family, type_label = self.classify(sym, source_family, info)

        calc = None
        is_sovereign = False
        currency_source = "inferida_cotizacion"
        base_currency = "ARS" if ccy == "ARS" else "USD"   # EXT (cable) settles in USD abroad

        if family == "caucion":
            # BYMA publishes the caución rate as a DECIMAL TNA. Guard against a future change to percent.
            rate_pct = price * 100.0 if price <= 5.0 else price
            calc = self.engine.calculate_caucion(sym, rate_pct, days_to_mat, "ARS" if ccy == "ARS" else "USD")
            price = round(rate_pct, 3)
            currency_source = "cotizacion"
        else:
            if info:
                calc = self.engine.calculate_sovereign_metrics(sym, price, ccy, settle_date, mep, cer_val, ccl)
                is_sovereign = bool(calc)
                if info.get("currency"):
                    base_currency, currency_source = info["currency"], "prospecto"
            if not calc and ccy == "ARS" and sym in self._letras_rescate:
                calc = self.engine.calculate_bullet_metrics(sym, price, self._letras_rescate[sym], maturity_str, days_to_mat,
                                                            type_label, "derivado de argentinadatos.com")
                base_currency, currency_source = "ARS", "prospecto"
            if not calc:
                calc = self.engine.calculate_generic_metrics(sym, price, ccy, maturity_str, days_to_mat, family, type_label)
        if not calc:
            return None

        segment = self.segment_of(sym, ccy)
        eval_price = calc.get("eval_price", price)
        eval_usd = (eval_price / mep) if base_currency == "ARS" else eval_price
        display_price = price if family == "caucion" else (round(price, 2) if ccy == "ARS" else round(price, 3))

        item = {
            "symbol": sym,
            "name": calc.get("name", sym),
            "family": family,
            "type": calc.get("type") if is_sovereign else type_label,
            "law": calc.get("law", "Argentina"),
            "ccy": ccy,                               # quote currency as sent by BYMA
            "currency": base_currency,                # payment currency of the cashflows
            "currency_source": currency_source,
            "segment": segment,
            # True when the species is quoted in the same currency it pays (AL30D, TX26, S30O6...)
            "is_native_quote": segment == "PPT" and ccy == base_currency,
            "price": display_price,
            "price_source": price_source,
            "eval_price": eval_price,
            "eval_price_usd": eval_usd,
            "change_pct": round(_f(b.get("imbalance")) * 100.0, 2),   # BYMA: decimal -> %
            "vt": calc.get("vt"),
            "vr": calc.get("vr"),
            "accrued": calc.get("accrued"),
            "parity": calc.get("parity"),
            "redemption": calc.get("redemption"),
            "tir": calc.get("tir"),                   # % TNA cap. semestral (cauciones: TNA simple)
            "tir_tea": calc.get("tir_tea"),           # % efectiva anual, Act/365 - comparable entre familias
            "tir_quality": calc.get("tir_quality", "no_disponible"),
            "tir_reason": calc.get("tir_reason", ""),
            "tir_basis": calc.get("tir_basis", ""),
            "is_cer": bool(calc.get("is_cer")),
            "duration": calc.get("macaulay_duration", 0.0),
            "mod_duration": calc.get("modified_duration", 0.0),
            "current_yield": calc.get("current_yield", 0.0),
            "maturity_date": calc.get("maturity_date") or maturity_str,
            "days_to_maturity": days_to_mat,
            "next_payment": calc.get("next_payment_date", "-"),
            "volume_amount": round(_f(b.get("volumeAmount")), 2),
            "volume_nom": int(_f(b.get("volume"))),
            "trade_hour": b.get("tradeHour") or "Cierre",
            "settlement": "24hs" if str(b.get("settlementType")) == "2" else "CI",
            "is_sovereign": is_sovereign,
            "cashflows": calc.get("cashflows", [])
        }
        van_ok, van_reason = self.engine.van_eligibility(item)
        item["van_eligible"] = van_ok
        item["van_exclusion_reason"] = van_reason
        return item

    # ------------------------------------------------------------ resilience
    def _save_snapshot(self):
        """Keeps the last good payload on disk so a BYMA outage never shows invented quotes."""
        if time.time() - self._last_snapshot_ts < 600:
            return
        try:
            with open(self._snapshot_path, "w", encoding="utf-8") as fh:
                json.dump({"bonds": self.cached_bonds, "macro": self.macro_summary}, fh, ensure_ascii=False)
            self._last_snapshot_ts = time.time()
        except Exception as e:
            print("Snapshot warning:", e)

    def _serve_stale(self, reason: str):
        """BYMA unavailable: serve the last real payload (memory, then disk), clearly flagged."""
        if not self.cached_bonds:
            try:
                with open(self._snapshot_path, encoding="utf-8") as fh:
                    snap = json.load(fh)
                self.cached_bonds = snap.get("bonds", [])
                self.macro_summary = {**snap.get("macro", {}), **{k: v for k, v in self.macro_summary.items() if v}}
            except Exception:
                pass
        self.macro_summary["data_status"] = "cache" if self.cached_bonds else "sin_datos"
        self.macro_summary["data_status_reason"] = reason
        print(f"[QA Trace][feed] {reason} -> sirviendo {len(self.cached_bonds)} instrumentos del último snapshot válido")
        self._last_quotes_ts = time.time()
        return self.cached_bonds, self.macro_summary

    def _qa_print(self, items: list):
        qa = self.macro_summary["qa"]
        print(f"[QA Trace][feed] BYMA filas crudas {qa['byma_filas_crudas']} -> {qa['simbolos_unicos']} símbolos "
              f"-> {qa['publicados']} publicados ({qa['descartados_sin_precio']} sin precio de referencia)")
        print(f"[QA Trace][feed] por familia {qa['por_familia']} | con TIR {qa['con_tir']} | calidad {qa['calidad_tir']}")
        print(f"[QA Trace][feed] CER valuación {qa['cer_valuacion']} | MEP {self.macro_summary['dolar_mep']} | CCL {self.macro_summary['dolar_ccl']}")
        teas = [i["tir_tea"] for i in items if i["tir_tea"] is not None]
        if teas:
            print(f"[QA Trace][feed] TEA min {min(teas):.2f}% / max {max(teas):.2f}% sobre {len(teas)} instrumentos con rendimiento")
        if qa["errores"]:
            print(f"[QA Trace][feed] errores de fuente: {qa['errores']}")
