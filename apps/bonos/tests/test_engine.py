"""
Regression tests for the financial math and the BYMA unit handling.
Run from the project folder:  python -m unittest discover tests
"""
import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from bonos_engine import BondEngine
except ImportError:
    from engine import BondEngine
from data_feed import MarketDataFeed

SETTLE = date(2026, 10, 8)


class BulletAndGenericTests(unittest.TestCase):
    def setUp(self):
        self.engine = BondEngine()

    def test_bullet_tea_is_effective_annual(self):
        m = self.engine.calculate_bullet_metrics("S00X0", 100.0, 110.0, "2027-10-08", 365)
        self.assertAlmostEqual(m["tir_tea"], 10.0, places=2)
        # Same yield expressed as TNA with semiannual compounding
        self.assertAlmostEqual(m["tir"], ((1.10 ** 0.5) - 1.0) * 200.0, places=2)
        self.assertEqual(m["cashflows"][0]["total"], 110.0)

    def test_bullet_too_short_is_not_annualized(self):
        m = self.engine.calculate_bullet_metrics("S00X0", 104.9, 105.0, "2026-10-09", 1)
        self.assertIsNone(m["tir"])
        self.assertEqual(m["cashflows"], [])

    def test_on_without_schedule_never_gets_a_yield(self):
        m = self.engine.calculate_generic_metrics("YMCXD", 95.0, "USD", "2031-09-11", 1799, "on", "Obligación Negociable")
        self.assertIsNone(m["tir"])
        self.assertIsNone(m["tir_tea"])
        self.assertEqual(m["cashflows"], [])
        self.assertTrue(m["data_gap"])
        self.assertIn("No hay información suficiente desde la API pública de BYMA", m["tir_reason"])

    def test_short_maturity_is_not_reported_as_missing_data(self):
        m = self.engine.calculate_generic_metrics("LXXX", 99.9, "ARS", "2026-10-19", 4, "letra", "Letra")
        self.assertIsNone(m["tir"])
        self.assertFalse(m["data_gap"])

    def test_capitalizing_letter_without_redemption_gets_no_yield(self):
        # Price above par: "pays 100" would give a negative yield, so nothing is published
        m = self.engine.calculate_generic_metrics("S30O6", 133.6, "ARS", "2026-10-30", 22, "letra", "Lecap")
        self.assertIsNone(m["tir"])

    def test_short_dated_estimate_cannot_explode(self):
        # 8 days at 95: annualizing the par assumption gives ~940% TEA -> rejected, not published
        m = self.engine.calculate_generic_metrics("LXXX", 95.0, "ARS", "2026-10-16", 8, "letra", "Letra")
        self.assertIsNone(m["tir"])
        self.assertTrue(m["tir_reason"].startswith(BondEngine.INFO_GAP))
        self.assertTrue(m["data_gap"])

    def test_discount_letter_estimate_is_flagged_and_has_no_cashflows(self):
        m = self.engine.calculate_generic_metrics("LXXX", 95.0, "ARS", "2027-04-06", 180, "letra", "Letra")
        self.assertEqual(m["tir_quality"], "estimada")
        self.assertAlmostEqual(m["tir_tea"], ((100.0 / 95.0) ** (365.0 / 180.0) - 1.0) * 100.0, places=2)
        self.assertEqual(m["cashflows"], [])

    def test_caucion_rate_in_percent(self):
        m = self.engine.calculate_caucion("PESOS-X", 22.0, 30, "ARS")
        self.assertEqual(m["tir"], 22.0)
        self.assertAlmostEqual(m["tir_tea"], ((1.0 + 0.22 * 30 / 365.0) ** (365.0 / 30) - 1.0) * 100.0, places=2)


class ScheduleBondTests(unittest.TestCase):
    def setUp(self):
        self.engine = BondEngine()

    def test_tir_reprices_the_bond(self):
        m = self.engine.calculate_sovereign_metrics("AL30D", 56.05, "USD", SETTLE, 1500.0)
        y = m["tir"] / 100.0
        pv = sum(cf["total"] / (1.0 + y / 2.0) ** (2.0 * (date.fromisoformat(cf["date"]) - SETTLE).days / 365.0)
                 for cf in m["cashflows"])
        self.assertAlmostEqual(pv, m["eval_price"], delta=0.02)
        self.assertAlmostEqual(m["tir_tea"], ((1.0 + y / 2.0) ** 2 - 1.0) * 100.0, places=1)

    def test_peso_quote_of_dollar_bond_is_converted_at_mep(self):
        usd = self.engine.calculate_sovereign_metrics("AL30D", 56.05, "USD", SETTLE, 1500.0)
        ars = self.engine.calculate_sovereign_metrics("AL30", 56.05 * 1500.0, "ARS", SETTLE, 1500.0)
        self.assertAlmostEqual(usd["tir"], ars["tir"], places=2)

    def test_cer_bond_technical_value_uses_prospectus_base(self):
        base = 22.54395108959
        m = self.engine.calculate_sovereign_metrics("TX26", 100.0, "ARS", SETTLE, 1500.0, base * 10.0)
        # 20% residual, CER factor 10x -> VR 200 per 100 VN
        self.assertAlmostEqual(m["vr"], 200.0, places=2)
        self.assertTrue(m["is_cer"])

    def test_cer_bond_without_verified_base_is_not_valued(self):
        self.assertIsNone(self.engine.calculate_sovereign_metrics("DICP", 49000.0, "ARS", SETTLE, 1500.0, 850.0))


class FeedUnitTests(unittest.TestCase):
    def setUp(self):
        self.feed = MarketDataFeed()

    def build(self, sym, row):
        return self.feed._build_item(sym, row, SETTLE, 1500.0, 1560.0, 844.0)

    def test_caucion_decimal_rate_becomes_percent(self):
        row = {"trade": 0.223, "denominationCcy": "ARS", "daysToMaturity": 25, "_family": "caucion"}
        item = self.build("PESOS-0211-U-CT-ARS", row)
        self.assertEqual(item["family"], "caucion")
        self.assertAlmostEqual(item["tir"], 22.3, places=2)
        self.assertLess(item["tir_tea"], 30.0)

    def test_daily_change_decimal_becomes_percent(self):
        row = {"trade": 56.05, "imbalance": 0.0052, "denominationCcy": "USD", "maturityDate": "2030-07-09",
               "daysToMaturity": 1370, "_family": "bono"}
        self.assertAlmostEqual(self.build("AL30D", row)["change_pct"], 0.52, places=2)

    def test_native_quote_flags(self):
        base = {"maturityDate": "2030-07-09", "daysToMaturity": 1370, "_family": "bono"}
        usd = self.build("AL30D", {**base, "trade": 56.05, "denominationCcy": "USD"})
        ars = self.build("AL30", {**base, "trade": 84075.0, "denominationCcy": "ARS"})
        self.assertTrue(usd["is_native_quote"])
        self.assertFalse(ars["is_native_quote"])
        self.assertEqual(ars["currency"], "USD")

    def test_schedule_is_rejected_when_maturity_disagrees_with_byma(self):
        row = {"trade": 104.0, "denominationCcy": "USD", "maturityDate": "2028-10-31", "daysToMaturity": 754, "_family": "bono"}
        item = self.build("BPOD7", row)
        self.assertIsNone(item["tir"])
        self.assertEqual(item["cashflows"], [])

    def test_reference_price_falls_back_to_close(self):
        self.assertEqual(self.feed.reference_price({"trade": 0, "closingPrice": 97.2}), (97.2, "cierre"))
        self.assertEqual(self.feed.reference_price({"trade": 0, "closingPrice": 0}), (0.0, ""))


if __name__ == "__main__":
    unittest.main()
