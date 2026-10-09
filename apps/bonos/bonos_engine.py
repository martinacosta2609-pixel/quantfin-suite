"""
High-Performance Financial Mathematics Engine for Argentine Bonds.
Calculates Technical Value (VT), Parity (%), TIR / YTM (%),
Macaulay Duration, and Modified Duration.
"""
from datetime import date, datetime
import numpy as np
from scipy.optimize import brentq
from bond_db import get_bond_definition, get_base_ticker

class BondEngine:
    def __init__(self):
        pass

    @staticmethod
    def days_30_360(d1: date, d2: date) -> int:
        """US 30/360 day count (prospectus convention for Bonares/Globales coupon accrual)."""
        day1 = min(d1.day, 30)
        day2 = d2.day
        if day1 == 30 and day2 == 31:
            day2 = 30
        return (d2.year - d1.year) * 360 + (d2.month - d1.month) * 30 + (day2 - day1)

    @staticmethod
    def tna_to_tea(tna_pct: float, freq: float = 2.0):
        """Converts a nominal annual rate compounded `freq` times/yr (in %) to an effective annual rate (in %)."""
        if tna_pct is None:
            return None
        base = 1.0 + (tna_pct / 100.0) / freq
        if base <= 0:
            return None
        return (base ** freq - 1.0) * 100.0

    def calculate_sovereign_metrics(self, symbol: str, price: float, ccy: str, settle_date: date, mep_rate: float = None, cer_index: float = None, ccl_rate: float = None):
        """
        Calculates exact metrics for recognized sovereign bonds with defined cashflow schedules.
        `ccy` is the QUOTE currency reported by BYMA: ARS (pesos), USD (dólar MEP) or EXT (dólar cable/CCL).
        """
        info = get_bond_definition(symbol)
        if not info or "schedule" not in info:
            return None

        # CER bonds can only be valued with the prospectus base CER. Never guess it.
        if info.get("is_cer") and (not info.get("base_cer") or not cer_index):
            return None

        schedule_raw = info["schedule"]
        # Convert schedule entries to date objects
        schedule = []
        for d_str, c, a in schedule_raw:
            d = datetime.strptime(d_str, "%Y-%m-%d").date()
            schedule.append((d, float(c), float(a)))

        # Settle date defaults to today if None
        if not settle_date:
            settle_date = date.today()

        # Always evaluate the bond in its original/base (payment) currency
        eval_price = price
        base_ccy = info.get("currency", "ARS")
        mep = mep_rate if (mep_rate and mep_rate > 0) else 1500.0
        ccl = ccl_rate if (ccl_rate and ccl_rate > 0) else mep

        if ccy == "ARS" and base_ccy == "USD":
            eval_price = price / mep
        elif ccy == "USD" and base_ccy == "ARS":
            eval_price = price * mep
        elif ccy == "EXT" and base_ccy == "ARS":
            # Peso bond quoted in cable dollars (e.g. TX26C, DICPC): convert at CCL
            eval_price = price * ccl
        # ccy == "EXT" and base USD: cable USD price, already in the payment currency

        # Handle CER Indexation
        cer_factor = 1.0
        if info.get("is_cer"):
            # The current technical value scales by CER_hoy / CER_emision
            cer_factor = cer_index / info["base_cer"]

        # 1. Amortization and Remaining Nominal / Residual Value (VR)
        amort_paid = sum(a for d, c, a in schedule if d <= settle_date)
        vr_nominal = max(0.0, 100.0 - amort_paid)
        vr = vr_nominal * cer_factor

        if vr <= 0:
            return None

        # 2. Last and next payment dates
        past_dates = [d for d, c, a in schedule if d <= settle_date]
        issue_d = datetime.strptime(info.get("issue_date", "2020-09-04"), "%Y-%m-%d").date()
        last_date = max(past_dates) if past_dates else issue_d

        future_payments = [(d, c, a) for d, c, a in schedule if d > settle_date]
        if not future_payments:
            return None

        next_date, next_coupon, _ = future_payments[0]

        # 3. Accrued Interest (Intereses Corridos) - 30/360 convention standard
        days_accrued = max(0, self.days_30_360(last_date, settle_date))
        accrued = vr * next_coupon * (days_accrued / 360.0)

        # 4. Technical Value (Valor Técnico)
        vt = vr + accrued

        # 5. Parity (%)
        # Price is assumed to be per 100 nominals for both ARS and USD bonds.
        parity = (eval_price / vt * 100.0) if vt > 0 else 0.0

        # If market quotes it as clean price, our eval_price for TIR and PV needs to include accrued!
        if info.get("is_clean_price", False):
            eval_price += accrued

        # 6. Future Cashflow Streams
        temp_vr_nom = vr_nominal
        cfs = []
        times = []
        cf_details = []

        for d, c, a in future_payments:
            coupon_cash = temp_vr_nom * cer_factor * c / float(info.get("frequency", 2))
            amort_cash = a * cer_factor
            total_cf = coupon_cash + amort_cash
            t = max(0.001, (d - settle_date).days / 365.0)

            cfs.append(total_cf)
            times.append(t)
            cf_details.append({
                "date": d.isoformat(),
                "coupon": round(coupon_cash, 4),
                "amort": round(amort_cash, 4),
                "total": round(total_cf, 4),
                "remaining_vr": round(max(0.0, (temp_vr_nom - a) * cer_factor), 2),
                "years": round(t, 2)
            })
            temp_vr_nom -= a

        cfs_arr = np.array(cfs)
        times_arr = np.array(times)

        # 7. TIR / YTM (%) via Brent's method root finding
        freq = float(info.get("frequency", 2))
        def price_diff(y):
            # Standard semiannual compounding: CF / (1 + y/freq)^(freq * t)
            return np.sum(cfs_arr / ((1.0 + y / freq) ** (freq * times_arr))) - eval_price

        tir = None
        y = 0.0
        if eval_price > 0 and len(cfs_arr) > 0:
            try:
                # Search across valid yield range [-49%, 300%]
                y = brentq(price_diff, -0.49, 3.0, xtol=1e-6, maxiter=100)
                tir = y * 100.0
            except Exception:
                try:
                    # Wider fallback search if deeply distressed
                    y = brentq(price_diff, -0.49, 10.0, xtol=1e-5, maxiter=100)
                    tir = y * 100.0
                except Exception:
                    tir = None  # No root: never publish a fake 0% or boundary value
                    y = 0.0

        # 8. Macaulay Duration and Modified Duration
        if tir is not None and eval_price > 0 and len(cfs_arr) > 0:
            discount_factors = (1.0 + y / freq) ** (freq * times_arr)
            pv_cfs = cfs_arr / discount_factors
            macaulay_duration = float(np.sum(times_arr * pv_cfs) / eval_price)
            # MD = MacDur / (1 + y / freq)
            mod_factor = (1.0 + y / freq)
            modified_duration = (macaulay_duration / mod_factor) if mod_factor > 0 else macaulay_duration
        else:
            macaulay_duration = 0.0
            modified_duration = 0.0

        # Current Yield: annual coupon / price
        current_yield = (vr * next_coupon / eval_price * 100.0) if eval_price > 0 else 0.0

        return {
            "name": info.get("name", symbol),
            "type": info.get("type", "Soberano"),
            "law": info.get("law", "N/A"),
            "maturity_date": info.get("maturity_date", next_date.isoformat()),
            "vr": round(vr, 4),
            "accrued": round(accrued, 4),
            "vt": round(vt, 4),
            "parity": round(parity, 2),
            "tir": round(tir, 2) if tir is not None else None,
            "tir_tea": round(self.tna_to_tea(tir, freq), 2) if tir is not None else None,
            "tir_quality": "cronograma" if tir is not None else "no_disponible",
            "tir_reason": "" if tir is not None else "Sin raíz de TIR en [-49%, 1000%]",
            "tir_basis": ("REAL (sobre CER)" if info.get("is_cer") else "NOMINAL") + f" · TNA cap. {int(freq)}x/año",
            "is_cer": bool(info.get("is_cer")),
            "has_schedule": True,
            "macaulay_duration": round(max(0.0, macaulay_duration), 2),
            "modified_duration": round(max(0.0, modified_duration), 2),
            "current_yield": round(current_yield, 2),
            "next_payment_date": next_date.isoformat(),
            "eval_price": round(eval_price, 2),
            "cashflows": cf_details
        }

    # Above this TEA, "redemption at par" is not a credible assumption for an ESTIMATED letter.
    # It validates the assumption (pays 100), it is not a cap on real market data.
    GENERIC_TEA_MAX = 100.0
    # Below this term, annualizing a price move is noise (1 tick = hundreds of % of TEA).
    MIN_DAYS_TO_ANNUALIZE = 3

    @staticmethod
    def _years_to_maturity(maturity_str: str, days_to_mat: int) -> float:
        """Actual/365 term from BYMA `daysToMaturity` (calendar days) or the maturity date."""
        if days_to_mat and days_to_mat > 0:
            return days_to_mat / 365.0
        if maturity_str:
            try:
                m_date = datetime.strptime(maturity_str[:10], "%Y-%m-%d").date()
                return max(0.0, (m_date - date.today()).days / 365.0)
            except Exception:
                return 0.0
        return 0.0

    def calculate_bullet_metrics(self, symbol: str, price: float, redemption: float, maturity_str: str,
                                 days_to_mat: int, type_label: str = "Lecap / Boncap", source: str = ""):
        """
        Zero-coupon instrument with a KNOWN redemption value per 100 VN (Lecap / Boncap capitalizables).
        TEA = (rescate / precio)^(365/días) - 1  (Actual/365). `tir` is the same yield expressed as
        TNA with semiannual compounding, so every instrument in the payload shares one convention.
        """
        if not price or price <= 0 or not redemption or redemption <= 0:
            return None
        years = self._years_to_maturity(maturity_str, days_to_mat)
        days = int(round(years * 365.0))

        tir = tea = tem = None
        reason = ""
        if days < self.MIN_DAYS_TO_ANNUALIZE:
            reason = f"Vence en {days} día(s): la anualización no es informativa"
        else:
            growth = redemption / price
            tea = (growth ** (1.0 / years) - 1.0) * 100.0
            tem = (growth ** (30.0 / days) - 1.0) * 100.0
            tir = ((1.0 + tea / 100.0) ** 0.5 - 1.0) * 200.0

        cfs = []
        if tir is not None:
            cfs = [{
                "date": maturity_str[:10] if (maturity_str and len(maturity_str) >= 10) else "Vencimiento",
                "coupon": round(redemption - 100.0, 4),   # intereses capitalizados
                "amort": 100.0,
                "total": round(redemption, 4),
                "remaining_vr": 0.0,
                "years": round(years, 4)
            }]

        return {
            "name": f"{type_label} {maturity_str[:10] if maturity_str else ''}".strip(),
            "type": type_label,
            "law": "Argentina",
            "maturity_date": maturity_str or "N/A",
            "vr": 100.0,
            "accrued": 0.0,
            "vt": None,
            "parity": None,
            "redemption": round(redemption, 4),
            "tir": round(tir, 2) if tir is not None else None,
            "tir_tea": round(tea, 2) if tea is not None else None,
            "tem": round(tem, 3) if tem is not None else None,
            "tir_quality": "rescate_derivado" if tir is not None else "no_disponible",
            "tir_reason": (f"Rescate {redemption:.3f} c/100 VN ({source})" if tir is not None else reason),
            "tir_basis": "NOMINAL (tasa fija ARS) · Act/365",
            "is_cer": False,
            "has_schedule": tir is not None,
            "macaulay_duration": round(years, 2) if tir is not None else 0.0,
            "modified_duration": round(years / (1.0 + tir / 200.0), 2) if tir is not None else 0.0,
            "current_yield": 0.0,
            "eval_price": price,
            "cashflows": cfs
        }

    NO_TIR_REASON = {
        "on": "ON: BYMA no publica cupón ni amortizaciones y no hay cronograma cargado",
        "subsoberano": "Título provincial/municipal sin cronograma de prospecto cargado",
        "cer": "Título CER sin CER base ni cronograma de prospecto cargado",
        "bono_otro": "Título público sin cronograma de prospecto cargado",
        "soberano_usd": "Título en USD sin cronograma de prospecto cargado",
        "bopreal": "Bopreal sin cronograma de prospecto cargado",
    }

    def calculate_generic_metrics(self, symbol: str, price: float, ccy: str, maturity_str: str, days_to_mat: int,
                                  family: str = "bono_otro", type_label: str = "Título público"):
        """
        Instruments WITHOUT a prospectus schedule. BYMA only sends prices (no TIR, coupon or VT), so a
        yield cannot be computed. The only estimate kept is for discount LETTERS (family 'letra', price
        below par): "pays 100 at maturity", flagged as `estimada` and never used for DCF (no cashflows).
        """
        if not price or price <= 0:
            return None

        years_to_mat = self._years_to_maturity(maturity_str, days_to_mat)
        days = int(round(years_to_mat * 365.0))

        tir, tea, reason = None, None, ""
        if family != "letra":
            reason = self.NO_TIR_REASON.get(family, "Sin cronograma de flujos cargado")
        elif days < 7:
            reason = "Vence en menos de 1 semana"
        elif price >= 100.0:
            reason = "Precio ≥ 100: letra capitalizable, CER o dólar linked. Requiere valor de rescate del prospecto"
        elif price < 50.0:
            reason = "Precio fuera de escala de letra a descuento (no rescata a 100)"
        else:
            tea_est = ((100.0 / price) ** (1.0 / years_to_mat) - 1.0) * 100.0
            if 0.0 <= tea_est <= self.GENERIC_TEA_MAX:
                tea = tea_est
                tir = ((1.0 + tea / 100.0) ** 0.5 - 1.0) * 200.0
            else:
                reason = f"Supuesto 'rescata a 100' no creíble (daría TEA {tea_est:.0f}%)"

        return {
            "name": symbol,
            "type": type_label,
            "law": "Argentina",
            "maturity_date": maturity_str or "N/A",
            "vr": None,
            "accrued": None,
            "vt": None,
            "parity": None,
            "tir": round(tir, 2) if tir is not None else None,
            "tir_tea": round(tea, 2) if tea is not None else None,
            "tir_quality": "estimada" if tir is not None else "no_disponible",
            "tir_reason": "Estimada: supone letra a descuento que rescata 100 al vencimiento" if tir is not None else reason,
            "tir_basis": "NOMINAL · Act/365 (estimada)" if tir is not None else "",
            "is_cer": False,
            "has_schedule": False,
            "macaulay_duration": round(years_to_mat, 2) if tir is not None else 0.0,
            "modified_duration": round(years_to_mat / (1.0 + tir / 200.0), 2) if tir is not None else 0.0,
            "current_yield": 0.0,
            "eval_price": price,
            "cashflows": []
        }

    def calculate_caucion(self, symbol: str, rate_tna_pct: float, days: int, ccy: str):
        """Caución bursátil. `rate_tna_pct` is the TNA in PERCENT (the feed converts BYMA's decimal)."""
        if rate_tna_pct is None or rate_tna_pct <= 0:
            return None
        d = max(1, int(days or 1))
        tea = ((1.0 + (rate_tna_pct / 100.0) * d / 365.0) ** (365.0 / d) - 1.0) * 100.0
        return {
            "name": f"Caución {ccy} {d} día(s)",
            "type": "Caución",
            "law": "BYMA",
            "maturity_date": "",
            "vr": None, "accrued": None, "vt": None, "parity": None,
            "tir": round(rate_tna_pct, 2),
            "tir_tea": round(tea, 2),
            "tir_quality": "tasa_mercado",
            "tir_reason": f"TNA {rate_tna_pct:.2f}% a {d} día(s) → TEA {tea:.2f}% (capitalizando cada {d} día(s))",
            "tir_basis": f"TNA (Act/365, plazo {d}d)",
            "is_cer": False,
            "has_schedule": False,
            "macaulay_duration": round(d / 365.0, 4),
            "modified_duration": 0.0,
            "current_yield": 0.0,
            "eval_price": 0.0,
            "cashflows": []
        }

    # Plausible ranges for a priced instrument with a real prospectus schedule
    VAN_TIR_MIN = -80.0
    VAN_TIR_MAX = 80.0
    VAN_PARITY_MIN = 15.0
    VAN_PARITY_MAX = 150.0

    def van_eligibility(self, bond_item: dict):
        """
        Decides whether an instrument can be valued by DCF / VAN.
        Any instrument with a cashflow schedule and active market price qualifies.
        Returns (eligible: bool, reason: str).
        """
        if not bond_item:
            return False, "Sin datos"
        cfs = bond_item.get("cashflows") or []
        if not cfs:
            return False, "Sin cronograma de flujos futuros"
        eval_price = bond_item.get("eval_price") or bond_item.get("eval_price_usd") or 0.0
        if eval_price <= 0:
            return False, "Sin precio de cotización válido"
        return True, ""

    def calculate_van(self, bond_metrics: dict, investment_amount: float, k_rate_pct: float, include_terminal_vt: bool = True):
        """
        Calculates Net Present Value (VAN / NPV) for an investment amount
        and required cost of capital rate k (%).
        The invested capital (VR) is returned exactly once, following the prospectus:
        amortization installments + the final redemption on the maturity date.
        If include_terminal_vt is True and the schedule leaves any principal unamortized,
        that residual is added on the final maturity date so the capital is always recovered.
        """
        if not bond_metrics or "cashflows" not in bond_metrics:
            return None

        cfs = bond_metrics.get("cashflows", [])
        eval_price = bond_metrics.get("eval_price") or bond_metrics.get("eval_price_usd") or bond_metrics.get("price", 0.0)
        vt = bond_metrics.get("vt", 100.0)
        if eval_price <= 0 or not cfs:
            return None

        k_annual = k_rate_pct / 100.0
        freq = 2.0  # Semiannual standard for Argentine sovereign & corporate bonds

        pv_cfs = []
        theoretical_price = 0.0
        cum_pv = 0.0
        n_cfs = len(cfs)

        for i, cf in enumerate(cfs):
            is_last = (i == n_cfs - 1)
            t = max(0.001, cf["years"])
            # Residual principal not covered by the schedule (0 for complete schedules)
            residual = max(0.0, cf.get("remaining_vr", 0.0)) if is_last else 0.0
            terminal_capital = residual if include_terminal_vt else 0.0
            total_period_cf = cf["total"] + terminal_capital

            df = 1.0 / ((1.0 + k_annual / freq) ** (freq * t)) if (1.0 + k_annual / freq) > 0 else 1.0
            pv = total_period_cf * df
            cum_pv += pv
            pv_cfs.append({
                "date": cf["date"],
                "coupon": cf["coupon"],
                "amort": cf["amort"],
                "terminal_capital": round(terminal_capital, 4),
                "total": round(total_period_cf, 4),
                "years": cf["years"],
                "discount_factor": round(df, 6),
                "pv": round(pv, 4),
                "cum_pv": round(cum_pv, 4)
            })
            theoretical_price += pv

        scale = (investment_amount / eval_price) if eval_price > 0 else 1.0
        total_pv = theoretical_price * scale
        total_van = total_pv - investment_amount
        van_pct = (total_van / investment_amount * 100.0) if investment_amount > 0 else 0.0
        margin_pct = ((theoretical_price - eval_price) / eval_price * 100.0) if eval_price > 0 else 0.0

        if total_van > 0.5:
            verdict = "Subvaluado / Oportunidad (Rinde > k)"
            verdict_badge = "success"
        elif total_van < -0.5:
            verdict = "Sobrevaluado (Rinde < k)"
            verdict_badge = "danger"
        else:
            verdict = "En Precio Teórico (Rinde ~ k)"
            verdict_badge = "neutral"

        return {
            "investment_amount": round(investment_amount, 2),
            "k_rate_pct": round(k_rate_pct, 2),
            "eval_price": round(eval_price, 2),
            "vt": round(vt, 2),
            "include_terminal_vt": include_terminal_vt,
            "theoretical_price": round(theoretical_price, 2),
            "total_pv": round(total_pv, 2),
            "total_van": round(total_van, 2),
            "van_pct": round(van_pct, 2),
            "margin_pct": round(margin_pct, 2),
            "verdict": verdict,
            "verdict_badge": verdict_badge,
            "tir_market": bond_metrics.get("tir", 0.0),
            "cashflows_pv": pv_cfs
        }

    def calculate_horizon_metrics(self, bond_metrics: dict, horizon_years: float, exit_yield_pct: float = None):
        """
        Calculates annualized TIR (Holding Period IRR) and total cash return
        for holding the bond until horizon_years.
        Eliminates bonds that mature BEFORE the target horizon.
        """
        if not bond_metrics or "cashflows" not in bond_metrics:
            return None

        cfs = bond_metrics.get("cashflows", [])
        if not cfs:
            return None

        eval_price = bond_metrics.get("eval_price") or bond_metrics.get("eval_price_usd") or bond_metrics.get("price", 0.0)
        if eval_price <= 0:
            return None

        # Apply transaction frictions (0.5% in and out)
        FEE_RATE = 0.005
        eval_price_neto = eval_price * (1.0 + FEE_RATE)

        max_year = max(cf["years"] for cf in cfs)
        if max_year < (horizon_years - 0.05):
            return {
                "eligible": False,
                "reason": f"Vence en {max_year:.1f} años (antes de los {horizon_years:.1f} años solicitados)"
            }

        cfs_during = [cf for cf in cfs if cf["years"] <= (horizon_years + 0.01)]
        cfs_after = [cf for cf in cfs if cf["years"] > (horizon_years + 0.01)]

        cash_collected = sum(cf["total"] for cf in cfs_during)
        coupons_collected = sum(cf["coupon"] for cf in cfs_during)
        amorts_collected = sum(cf["amort"] for cf in cfs_during)

        y_exit = (exit_yield_pct if exit_yield_pct is not None else (bond_metrics.get("tir") or 0.0)) / 100.0
        y_exit = max(0.001, y_exit)
        freq = 2.0

        if not cfs_after:
            terminal_price = 0.0
            terminal_price_neto = 0.0
        else:
            terminal_price = 0.0
            for cf in cfs_after:
                t_remaining = cf["years"] - horizon_years
                df_exit = 1.0 / ((1.0 + y_exit / freq) ** (freq * t_remaining))
                terminal_price += cf["total"] * df_exit
            terminal_price_neto = terminal_price * (1.0 - FEE_RATE)

        total_inflow = cash_collected + terminal_price_neto
        hpr_pct = ((total_inflow - eval_price_neto) / eval_price_neto * 100.0) if eval_price_neto > 0 else 0.0

        def horizon_diff(r):
            pv_during = sum(cf["total"] / ((1.0 + r / freq) ** (freq * cf["years"])) for cf in cfs_during)
            pv_terminal = terminal_price_neto / ((1.0 + r / freq) ** (freq * horizon_years))
            return (pv_during + pv_terminal) - eval_price_neto

        horizon_tir = 0.0
        try:
            r_root = brentq(horizon_diff, -0.49, 3.0, xtol=1e-6, maxiter=100)
            horizon_tir = r_root * 100.0
        except Exception:
            try:
                r_root = brentq(horizon_diff, -0.49, 10.0, xtol=1e-5, maxiter=100)
                horizon_tir = r_root * 100.0
            except Exception:
                if horizon_years > 0 and total_inflow > 0:
                    horizon_tir = (((total_inflow / eval_price_neto) ** (1.0 / horizon_years)) - 1.0) * 100.0

        return {
            "eligible": True,
            "horizon_years": round(horizon_years, 2),
            "cash_collected": round(cash_collected, 2),
            "coupons_collected": round(coupons_collected, 2),
            "amorts_collected": round(amorts_collected, 2),
            "terminal_price": round(terminal_price, 2),
            "total_inflow": round(total_inflow, 2),
            "hpr_pct": round(hpr_pct, 2),
            "horizon_tir": round(horizon_tir, 2),
            "maturity_years": round(max_year, 2),
            "cfs_count_during": len(cfs_during),
            "cfs_count_after": len(cfs_after)
        }
