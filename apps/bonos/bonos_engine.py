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

    def calculate_sovereign_metrics(self, symbol: str, price: float, ccy: str, settle_date: date, mep_rate: float = None):
        """
        Calculates exact metrics for recognized sovereign bonds with defined cashflow schedules.
        """
        info = get_bond_definition(symbol)
        if not info or "schedule" not in info:
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

        # If price is in ARS and bond is original USD, convert to USD price for valuation
        eval_price = price
        if ccy == "ARS" and info.get("currency") == "USD":
            if mep_rate and mep_rate > 0:
                eval_price = price / mep_rate
            else:
                eval_price = price / 1500.0  # Fallback approximate FX if not yet loaded

        # 1. Amortization and Remaining Nominal / Residual Value (VR)
        amort_paid = sum(a for d, c, a in schedule if d <= settle_date)
        vr = max(0.0, 100.0 - amort_paid)

        if vr <= 0:
            return {
                "vr": 0.0,
                "accrued": 0.0,
                "vt": 0.0,
                "parity": 0.0,
                "tir": 0.0,
                "macaulay_duration": 0.0,
                "modified_duration": 0.0,
                "current_yield": 0.0,
                "cashflows": []
            }

        # 2. Last and next payment dates
        past_dates = [d for d, c, a in schedule if d <= settle_date]
        issue_d = datetime.strptime(info.get("issue_date", "2020-09-04"), "%Y-%m-%d").date()
        last_date = max(past_dates) if past_dates else issue_d

        future_payments = [(d, c, a) for d, c, a in schedule if d > settle_date]
        if not future_payments:
            return None

        next_date, next_coupon, _ = future_payments[0]

        # 3. Accrued Interest (Intereses Corridos) - 30/360 convention standard
        days_accrued = max(0, (settle_date - last_date).days)
        accrued = vr * next_coupon * (days_accrued / 360.0)

        # 4. Technical Value (Valor Técnico)
        vt = vr + accrued

        # 5. Parity (%)
        parity = (eval_price / vt * 100.0) if vt > 0 else 0.0

        # 6. Future Cashflow Streams
        temp_vr = vr
        cfs = []
        times = []
        cf_details = []

        for d, c, a in future_payments:
            coupon_cash = temp_vr * c / float(info.get("frequency", 2))
            amort_cash = a
            total_cf = coupon_cash + amort_cash
            t = max(0.001, (d - settle_date).days / 365.0)

            cfs.append(total_cf)
            times.append(t)
            cf_details.append({
                "date": d.isoformat(),
                "coupon": round(coupon_cash, 4),
                "amort": round(amort_cash, 4),
                "total": round(total_cf, 4),
                "remaining_vr": round(max(0.0, temp_vr - a), 2),
                "years": round(t, 2)
            })
            temp_vr -= a

        cfs_arr = np.array(cfs)
        times_arr = np.array(times)

        # 7. TIR / YTM (%) via Brent's method root finding
        freq = float(info.get("frequency", 2))
        def price_diff(y):
            # Standard semiannual compounding: CF / (1 + y/freq)^(freq * t)
            return np.sum(cfs_arr / ((1.0 + y / freq) ** (freq * times_arr))) - eval_price

        tir = 0.0
        y = 0.0
        if eval_price > 0 and len(cfs_arr) > 0:
            try:
                # Search across valid yield range [-50%, 300%]
                y = brentq(price_diff, -0.49, 3.0, xtol=1e-6, maxiter=100)
                tir = y * 100.0
            except Exception:
                try:
                    # Wider fallback search if deeply distressed
                    y = brentq(price_diff, -0.49, 10.0, xtol=1e-5, maxiter=100)
                    tir = y * 100.0
                except Exception:
                    tir = 0.0
                    y = 0.0

        # 8. Macaulay Duration and Modified Duration
        if eval_price > 0 and len(cfs_arr) > 0:
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
            "tir": round(tir, 2),
            "macaulay_duration": round(max(0.0, macaulay_duration), 2),
            "modified_duration": round(max(0.0, modified_duration), 2),
            "current_yield": round(current_yield, 2),
            "next_payment_date": next_date.isoformat(),
            "eval_price": round(eval_price, 2),
            "cashflows": cf_details
        }

    def calculate_generic_metrics(self, symbol: str, price: float, ccy: str, maturity_str: str, days_to_mat: int):
        """
        Calculates approximate metrics for generic public bonds / treasury notes / lecaps.
        """
        if not price or price <= 0:
            return None

        # Maturity parsing
        years_to_mat = 0.0
        if days_to_mat and days_to_mat > 0:
            years_to_mat = days_to_mat / 365.0
        elif maturity_str:
            try:
                m_date = datetime.strptime(maturity_str[:10], "%Y-%m-%d").date()
                years_to_mat = max(0.01, (m_date - date.today()).days / 365.0)
            except Exception:
                years_to_mat = 1.0

        # For zero-coupon / bullet bonds (Lecaps, Letras):
        # Face value is 100.
        # Parity = price / 100 * 100 = price% (if priced in nominal 100)
        vt = 100.0
        parity = (price / vt * 100.0) if price < 200 else (price / 1000.0)  # Handle 100 or 1000 nominals
        
        # Approximate annualized TNA/TIR for bullet: (100 / price - 1) / years
        tir = 0.0
        if years_to_mat > 0 and price > 0 and price < 100:
            tir = ((100.0 / price) ** (1.0 / years_to_mat) - 1.0) * 100.0

        mac_dur = years_to_mat
        y = tir / 100.0
        mod_dur = mac_dur / (1.0 + y) if (1.0 + y) > 0 else mac_dur

        # Bullet bond cashflow (pays VT at maturity)
        cfs = [{
            "date": maturity_str[:10] if (maturity_str and len(maturity_str) >= 10) else "Vencimiento",
            "coupon": 0.0,
            "amort": round(vt, 4),
            "total": round(vt, 4),
            "remaining_vr": 0.0,
            "years": round(years_to_mat, 2)
        }]

        return {
            "name": symbol,
            "type": "Letra / Genérico",
            "law": "Argentina",
            "maturity_date": maturity_str or "N/A",
            "vr": 100.0,
            "accrued": 0.0,
            "vt": vt,
            "parity": round(parity, 2),
            "tir": round(tir, 2),
            "macaulay_duration": round(mac_dur, 2),
            "modified_duration": round(mod_dur, 2),
            "current_yield": 0.0,
            "eval_price": price,
            "cashflows": cfs
        }

    # Plausible ranges for a priced instrument with a real prospectus schedule
    VAN_TIR_MIN = -5.0
    VAN_TIR_MAX = 50.0
    VAN_PARITY_MIN = 15.0
    VAN_PARITY_MAX = 150.0

    def van_eligibility(self, bond_item: dict):
        """
        Decides whether an instrument can be valued by DCF / VAN.
        Only instruments with a real prospectus cashflow schedule (bond_db) qualify.
        Generic instruments (Lecaps, Boncer CER, letras, ONs) only have an invented
        bullet flow of 100 at maturity, which yields meaningless TIR/VAN, so they are excluded.
        Returns (eligible: bool, reason: str).
        """
        if not bond_item:
            return False, "Sin datos"
        if not bond_item.get("is_sovereign"):
            return False, "Sin cronograma de flujos real (instrumento genérico)"
        cfs = bond_item.get("cashflows") or []
        if not cfs:
            return False, "Sin flujos futuros"
        eval_price = bond_item.get("eval_price") or bond_item.get("eval_price_usd") or 0.0
        if eval_price <= 0:
            return False, "Sin precio"
        tir = bond_item.get("tir", 0.0) or 0.0
        if not (self.VAN_TIR_MIN <= tir <= self.VAN_TIR_MAX) or tir == 0.0:
            return False, f"TIR no confiable ({tir:.2f}%)"
        parity = bond_item.get("parity", 0.0) or 0.0
        if not (self.VAN_PARITY_MIN <= parity <= self.VAN_PARITY_MAX):
            return False, f"Paridad fuera de rango ({parity:.1f}%)"
        # Schedule must return the outstanding principal (VR) exactly once
        vr = bond_item.get("vr", 0.0) or 0.0
        sum_amort = sum(cf.get("amort", 0.0) for cf in cfs)
        if vr > 0 and abs(sum_amort - vr) > 0.5:
            return False, "Cronograma de amortización incompleto"
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

        y_exit = (exit_yield_pct if exit_yield_pct is not None else bond_metrics.get("tir", 0.0)) / 100.0
        y_exit = max(0.001, y_exit)
        freq = 2.0

        if not cfs_after:
            terminal_price = 0.0
        else:
            terminal_price = 0.0
            for cf in cfs_after:
                t_remaining = cf["years"] - horizon_years
                df_exit = 1.0 / ((1.0 + y_exit / freq) ** (freq * t_remaining))
                terminal_price += cf["total"] * df_exit

        total_inflow = cash_collected + terminal_price
        hpr_pct = ((total_inflow - eval_price) / eval_price * 100.0) if eval_price > 0 else 0.0

        def horizon_diff(r):
            pv_during = sum(cf["total"] / ((1.0 + r / freq) ** (freq * cf["years"])) for cf in cfs_during)
            pv_terminal = terminal_price / ((1.0 + r / freq) ** (freq * horizon_years))
            return (pv_during + pv_terminal) - eval_price

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
                    horizon_tir = (((total_inflow / eval_price) ** (1.0 / horizon_years)) - 1.0) * 100.0

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
