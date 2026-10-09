"""
Database and schedules for Argentine Government & Central Bank Bonds.
Includes Bonares (AL), Globales (GD), Bopreales (BCRA), Boncer (CER), and Lecaps.
"""
from datetime import date, datetime

SOVEREIGN_BONDS = {
    # ----------------------------------------------------
    # BONARES & GLOBALES (USD Ley Argentina & Ley Nueva York)
    # ----------------------------------------------------
    "AL29": {
        "name": "Bonar 2029 (Ley Arg)",
        "isin": "ARARGE3209X6",
        "currency": "USD",
        "type": "Soberano USD",
        "law": "Argentina",
        "issue_date": "2020-09-04",
        "maturity_date": "2029-07-09",
        "frequency": 2,  # Semestral
        "schedule": [
            ("2021-07-09", 0.005, 0.0),
            ("2022-01-09", 0.005, 0.0),
            ("2022-07-09", 0.005, 0.0),
            ("2023-01-09", 0.005, 0.0),
            ("2023-07-09", 0.005, 0.0),
            ("2024-01-09", 0.010, 0.0),
            ("2024-07-09", 0.010, 0.0),
            ("2025-01-09", 0.010, 10.0),
            ("2025-07-09", 0.010, 10.0),
            ("2026-01-09", 0.010, 10.0),
            ("2026-07-09", 0.010, 10.0),
            ("2027-01-09", 0.010, 10.0),
            ("2027-07-09", 0.010, 10.0),
            ("2028-01-09", 0.010, 10.0),
            ("2028-07-09", 0.010, 10.0),
            ("2029-01-09", 0.010, 10.0),
            ("2029-07-09", 0.010, 10.0),
        ]
    },
    "GD29": {
        "name": "Global 2029 (Ley NY)",
        "isin": "US040114HW38",
        "currency": "USD",
        "type": "Soberano USD",
        "law": "Nueva York",
        "issue_date": "2020-09-04",
        "maturity_date": "2029-07-09",
        "frequency": 2,
        # Same schedule as AL29
        "ref": "AL29"
    },
    "AL30": {
        "name": "Bonar 2030 (Ley Arg)",
        "isin": "ARARGE3209Y4",
        "currency": "USD",
        "type": "Soberano USD",
        "law": "Argentina",
        "issue_date": "2020-09-04",
        "maturity_date": "2030-07-09",
        "frequency": 2,
        "schedule": [
            ("2021-07-09", 0.005, 0.0),
            ("2022-01-09", 0.005, 0.0),
            ("2022-07-09", 0.005, 0.0),
            ("2023-01-09", 0.005, 0.0),
            ("2023-07-09", 0.005, 0.0),
            ("2024-01-09", 0.0075, 0.0),
            ("2024-07-09", 0.0075, 4.0),
            ("2025-01-09", 0.0075, 8.0),
            ("2025-07-09", 0.0075, 8.0),
            ("2026-01-09", 0.0075, 8.0),
            ("2026-07-09", 0.0075, 8.0),
            ("2027-01-09", 0.0075, 8.0),
            ("2027-07-09", 0.0075, 8.0),
            ("2028-01-09", 0.0175, 8.0),
            ("2028-07-09", 0.0175, 8.0),
            ("2029-01-09", 0.0175, 8.0),
            ("2029-07-09", 0.0175, 8.0),
            ("2030-01-09", 0.0175, 8.0),
            ("2030-07-09", 0.0175, 8.0),
        ]
    },
    "GD30": {
        "name": "Global 2030 (Ley NY)",
        "isin": "US040114HX11",
        "currency": "USD",
        "type": "Soberano USD",
        "law": "Nueva York",
        "issue_date": "2020-09-04",
        "maturity_date": "2030-07-09",
        "frequency": 2,
        "ref": "AL30"
    },
    "AL35": {
        "name": "Bonar 2035 (Ley Arg)",
        "isin": "ARARGE3209Z1",
        "currency": "USD",
        "type": "Soberano USD",
        "law": "Argentina",
        "issue_date": "2020-09-04",
        "maturity_date": "2035-07-09",
        "frequency": 2,
        "schedule": [
            ("2021-07-09", 0.00125, 0.0),
            ("2022-01-09", 0.00125, 0.0),
            ("2022-07-09", 0.005, 0.0),
            ("2023-01-09", 0.005, 0.0),
            ("2023-07-09", 0.005, 0.0),
            ("2024-01-09", 0.015, 0.0),
            ("2024-07-09", 0.015, 0.0),
            ("2025-01-09", 0.015, 0.0),
            ("2025-07-09", 0.03625, 0.0),
            ("2026-01-09", 0.03625, 0.0),
            ("2026-07-09", 0.03625, 0.0),
            ("2027-01-09", 0.03625, 0.0),
            ("2027-07-09", 0.03625, 0.0),
            ("2028-01-09", 0.04125, 0.0),
            ("2028-07-09", 0.04125, 0.0),
            ("2029-01-09", 0.04125, 0.0),
            ("2029-07-09", 0.04125, 0.0),
            ("2030-01-09", 0.04125, 0.0),
            ("2030-07-09", 0.04125, 0.0),
            ("2031-01-09", 0.04125, 10.0),
            ("2031-07-09", 0.04125, 10.0),
            ("2032-01-09", 0.04125, 10.0),
            ("2032-07-09", 0.04125, 10.0),
            ("2033-01-09", 0.04125, 10.0),
            ("2033-07-09", 0.04125, 10.0),
            ("2034-01-09", 0.04125, 10.0),
            ("2034-07-09", 0.04125, 10.0),
            ("2035-01-09", 0.04125, 10.0),
            ("2035-07-09", 0.04125, 10.0),
        ]
    },
    "GD35": {
        "name": "Global 2035 (Ley NY)",
        "isin": "US040114HY93",
        "currency": "USD",
        "type": "Soberano USD",
        "law": "Nueva York",
        "issue_date": "2020-09-04",
        "maturity_date": "2035-07-09",
        "frequency": 2,
        "ref": "AL35"
    },
    "AE38": {
        "name": "Bonar 2038 (Ley Arg)",
        "isin": "ARARGE320A06",
        "currency": "USD",
        "type": "Soberano USD",
        "law": "Argentina",
        "issue_date": "2020-09-04",
        "maturity_date": "2038-01-09",
        "frequency": 2,
        "schedule": [
            ("2021-07-09", 0.00125, 0.0),
            ("2022-01-09", 0.00125, 0.0),
            ("2022-07-09", 0.020, 0.0),
            ("2023-01-09", 0.020, 0.0),
            ("2023-07-09", 0.020, 0.0),
            ("2024-01-09", 0.03875, 0.0),
            ("2024-07-09", 0.03875, 0.0),
            ("2025-01-09", 0.03875, 0.0),
            ("2025-07-09", 0.0425, 0.0),
            ("2026-01-09", 0.0425, 0.0),
            ("2026-07-09", 0.0425, 0.0),
            ("2027-01-09", 0.0425, 0.0),
            ("2027-07-09", 0.050, 4.545),
            ("2028-01-09", 0.050, 4.545),
            ("2028-07-09", 0.050, 4.545),
            ("2029-01-09", 0.050, 4.545),
            ("2029-07-09", 0.050, 4.545),
            ("2030-01-09", 0.050, 4.545),
            ("2030-07-09", 0.050, 4.545),
            ("2031-01-09", 0.050, 4.545),
            ("2031-07-09", 0.050, 4.545),
            ("2032-01-09", 0.050, 4.545),
            ("2032-07-09", 0.050, 4.545),
            ("2033-01-09", 0.050, 4.545),
            ("2033-07-09", 0.050, 4.545),
            ("2034-01-09", 0.050, 4.545),
            ("2034-07-09", 0.050, 4.545),
            ("2035-01-09", 0.050, 4.545),
            ("2035-07-09", 0.050, 4.545),
            ("2036-01-09", 0.050, 4.545),
            ("2036-07-09", 0.050, 4.545),
            ("2037-01-09", 0.050, 4.545),
            ("2037-07-09", 0.050, 4.545),
            ("2038-01-09", 0.050, 4.555),
        ]
    },
    "GD38": {
        "name": "Global 2038 (Ley NY)",
        "isin": "US040114HZ68",
        "currency": "USD",
        "type": "Soberano USD",
        "law": "Nueva York",
        "issue_date": "2020-09-04",
        "maturity_date": "2038-01-09",
        "frequency": 2,
        "ref": "AE38"
    },
    "AL41": {
        "name": "Bonar 2041 (Ley Arg)",
        "isin": "ARARGE320A14",
        "currency": "USD",
        "type": "Soberano USD",
        "law": "Argentina",
        "issue_date": "2020-09-04",
        "maturity_date": "2041-07-09",
        "frequency": 2,
        "schedule": [
            ("2021-07-09", 0.00125, 0.0),
            ("2022-01-09", 0.00125, 0.0),
            ("2022-07-09", 0.025, 0.0),
            ("2023-01-09", 0.025, 0.0),
            ("2023-07-09", 0.025, 0.0),
            ("2024-01-09", 0.035, 0.0),
            ("2024-07-09", 0.035, 0.0),
            ("2025-01-09", 0.035, 0.0),
            ("2025-07-09", 0.035, 0.0),
            ("2026-01-09", 0.035, 0.0),
            ("2026-07-09", 0.035, 0.0),
            ("2027-01-09", 0.035, 0.0),
            ("2027-07-09", 0.035, 0.0),
            ("2028-01-09", 0.04875, 3.57),
            ("2028-07-09", 0.04875, 3.57),
            ("2029-01-09", 0.04875, 3.57),
            ("2029-07-09", 0.04875, 3.57),
            ("2030-01-09", 0.04875, 3.57),
            ("2030-07-09", 0.04875, 3.57),
            ("2031-01-09", 0.04875, 3.57),
            ("2031-07-09", 0.04875, 3.57),
            ("2032-01-09", 0.04875, 3.57),
            ("2032-07-09", 0.04875, 3.57),
            ("2033-01-09", 0.04875, 3.57),
            ("2033-07-09", 0.04875, 3.57),
            ("2034-01-09", 0.04875, 3.57),
            ("2034-07-09", 0.04875, 3.57),
            ("2035-01-09", 0.04875, 3.57),
            ("2035-07-09", 0.04875, 3.57),
            ("2036-01-09", 0.04875, 3.57),
            ("2036-07-09", 0.04875, 3.57),
            ("2037-01-09", 0.04875, 3.57),
            ("2037-07-09", 0.04875, 3.57),
            ("2038-01-09", 0.04875, 3.57),
            ("2038-07-09", 0.04875, 3.57),
            ("2039-01-09", 0.04875, 3.57),
            ("2039-07-09", 0.04875, 3.57),
            ("2040-01-09", 0.04875, 3.57),
            ("2040-07-09", 0.04875, 3.57),
            ("2041-01-09", 0.04875, 3.57),
            ("2041-07-09", 0.04875, 3.61),
        ]
    },
    "GD41": {
        "name": "Global 2041 (Ley NY)",
        "isin": "US040114JA00",
        "currency": "USD",
        "type": "Soberano USD",
        "law": "Nueva York",
        "issue_date": "2020-09-04",
        "maturity_date": "2041-07-09",
        "frequency": 2,
        "ref": "AL41"
    },

    # ----------------------------------------------------
    # BOPREALES (Banco Central de la República Argentina)
    # ----------------------------------------------------
    "BPOD7": {
        "name": "Bopreal Serie 1 Strip D (BCRA)",
        "isin": "ARBCRA320019",
        "currency": "USD",
        "type": "Bopreal BCRA",
        "law": "Argentina",
        "issue_date": "2024-01-11",
        "maturity_date": "2027-10-31",
        "frequency": 2,
        "schedule": [
            ("2024-10-31", 0.05, 0.0),
            ("2025-04-30", 0.05, 0.0),
            ("2025-10-31", 0.05, 0.0),
            ("2026-04-30", 0.05, 0.0),
            ("2026-10-31", 0.05, 0.0),
            ("2027-04-30", 0.05, 0.0),
            ("2027-10-31", 0.05, 100.0),
        ]
    },
    "BPD7": {
        "name": "Bopreal Serie 1 Strip D",
        "ref": "BPOD7"
    },
    "BPOC7": {
        "name": "Bopreal Serie 1 Strip C (BCRA)",
        "ref": "BPOD7"
    },
    "BPC7": {
        "name": "Bopreal Serie 1 Strip C",
        "ref": "BPOD7"
    },
    "BPOA7": {
        "name": "Bopreal Serie 1 Strip A (BCRA)",
        "ref": "BPOD7"
    },
    "BPA7": {
        "name": "Bopreal Serie 1 Strip A",
        "ref": "BPOD7"
    },
    # Strip B is BPOB7 (vence 2027-10-31). BPOB8 is another series (BYMA: vence 2028-10-31) and
    # was wrongly mapped here, which produced a fake ~16% TIR for it.
    "BPOB7": {
        "name": "Bopreal Serie 1 Strip B (BCRA)",
        "ref": "BPOD7"
    },
    "BPB7": {
        "name": "Bopreal Serie 1 Strip B",
        "ref": "BPOD7"
    },
    "BPO27": {
        "name": "Bopreal Serie 1 (BCRA)",
        "ref": "BPOD7"
    },
    "BPJ25": {
        "name": "Bopreal Serie 2 (BCRA)",
        "isin": "ARBCRA320027",
        "currency": "USD",
        "type": "Bopreal BCRA",
        "law": "Argentina",
        "issue_date": "2024-02-15",
        "maturity_date": "2025-06-30",
        "frequency": 12,  # Mensual amortizable
        "schedule": [
            ("2024-07-31", 0.0, 8.33),
            ("2024-08-31", 0.0, 8.33),
            ("2024-09-30", 0.0, 8.33),
            ("2024-10-31", 0.0, 8.33),
            ("2024-11-30", 0.0, 8.33),
            ("2024-12-31", 0.0, 8.33),
            ("2025-01-31", 0.0, 8.33),
            ("2025-02-28", 0.0, 8.33),
            ("2025-03-31", 0.0, 8.33),
            ("2025-04-30", 0.0, 8.33),
            ("2025-05-31", 0.0, 8.33),
            ("2025-06-30", 0.0, 8.37),
        ]
    },
    "BPY26": {
        "name": "Bopreal Serie 3 (BCRA)",
        "isin": "ARBCRA320035",
        "currency": "USD",
        "type": "Bopreal BCRA",
        "law": "Argentina",
        "issue_date": "2024-02-29",
        "maturity_date": "2026-05-31",
        "frequency": 4,  # Trimestral
        "schedule": [
            ("2024-05-31", 0.03, 0.0),
            ("2024-08-31", 0.03, 0.0),
            ("2024-11-30", 0.03, 0.0),
            ("2025-02-28", 0.03, 0.0),
            ("2025-05-31", 0.03, 0.0),
            ("2025-08-31", 0.03, 0.0),
            ("2025-11-30", 0.03, 33.33),
            ("2026-02-28", 0.03, 33.33),
            ("2026-05-31", 0.03, 33.34),
        ]
    },

    # ----------------------------------------------------
    # BONOS CER (Ajustables por Inflación)
    # ----------------------------------------------------
    "TX26": {
        "name": "Boncer 2026 (CER + 2.0%)",
        "currency": "ARS",
        "type": "Boncer (CER)",
        "law": "Argentina",
        "issue_date": "2020-09-04",
        "maturity_date": "2026-11-09",
        "coupon_rate": 0.02,
        "frequency": 2,
        "is_cer": True,
        # CER base = CER del 21-08-2020 (10 días hábiles antes de la emisión 04-09-2020).
        # Fuente: BCRA API v4 monetarias/30. El valor previo (23.47) subvaluaba el VT un 4.1%.
        "base_cer": 22.54395108959,
        "schedule": [
            ("2021-05-09", 0.02, 0.0),
            ("2021-11-09", 0.02, 0.0),
            ("2022-05-09", 0.02, 0.0),
            ("2022-11-09", 0.02, 0.0),
            ("2023-05-09", 0.02, 0.0),
            ("2023-11-09", 0.02, 0.0),
            ("2024-05-09", 0.02, 0.0),
            ("2024-11-09", 0.02, 20.0),
            ("2025-05-09", 0.02, 20.0),
            ("2025-11-09", 0.02, 20.0),
            ("2026-05-09", 0.02, 20.0),
            ("2026-11-09", 0.02, 20.0),
        ]
    },
    "TX28": {
        "name": "Boncer 2028 (CER + 2.25%)",
        "currency": "ARS",
        "type": "Boncer (CER)",
        "law": "Argentina",
        "issue_date": "2020-09-04",
        "maturity_date": "2028-11-09",
        "coupon_rate": 0.0225,
        "frequency": 2,
        "is_cer": True,
        # Misma emisión que TX26: CER del 21-08-2020 (BCRA API v4 monetarias/30).
        "base_cer": 22.54395108959,
        "schedule": [
            ("2021-05-09", 0.0225, 0.0),
            ("2021-11-09", 0.0225, 0.0),
            ("2022-05-09", 0.0225, 0.0),
            ("2022-11-09", 0.0225, 0.0),
            ("2023-05-09", 0.0225, 0.0),
            ("2023-11-09", 0.0225, 0.0),
            ("2024-05-09", 0.0225, 10.0),
            ("2024-11-09", 0.0225, 10.0),
            ("2025-05-09", 0.0225, 10.0),
            ("2025-11-09", 0.0225, 10.0),
            ("2026-05-09", 0.0225, 10.0),
            ("2026-11-09", 0.0225, 10.0),
            ("2027-05-09", 0.0225, 10.0),
            ("2027-11-09", 0.0225, 10.0),
            ("2028-05-09", 0.0225, 10.0),
            ("2028-11-09", 0.0225, 10.0),
        ]
    },
    "TZX28": {
        "name": "Boncer Cero Cupón (Jun 2028)",
        "currency": "ARS",
        "type": "Boncer Cero Cupón",
        "law": "Argentina",
        "issue_date": "2024-03-01",
        "maturity_date": "2028-06-30",
        "frequency": 1,
        "is_cer": True,
        # base_cer intentionally omitted: the previous value (558.12) was a placeholder,
        # not the prospectus CER base. Without it the engine refuses to value the bond
        # (it yielded parity 236% / TIR -39%). Add the official base CER to re-enable it.
        "schedule": [
            ("2028-06-30", 0.0, 100.0)
        ]
    },
    "TZXD8": {
        "name": "Boncer Cero Cupón (Dic 2028)",
        "currency": "ARS",
        "type": "Boncer Cero Cupón",
        "law": "Argentina",
        "issue_date": "2024-04-01",
        "maturity_date": "2028-12-15",
        "frequency": 1,
        "is_cer": True,
        # base_cer intentionally omitted (previous 625.00 was a placeholder). See TZX28.
        "schedule": [
            ("2028-12-15", 0.0, 100.0)
        ]
    },
    "T2X5": {
        "name": "Boncer 2025 (CER + 4.0%)",
        "currency": "ARS",
        "type": "Boncer (CER)",
        "law": "Argentina",
        "issue_date": "2022-06-30",
        "maturity_date": "2025-06-30",
        "coupon_rate": 0.04,
        "frequency": 2,
        "is_cer": True,
        "base_cer": 48.02,
        "schedule": [
            ("2022-12-30", 0.04, 0.0),
            ("2023-06-30", 0.04, 0.0),
            ("2023-12-30", 0.04, 0.0),
            ("2024-06-30", 0.04, 0.0),
            ("2024-12-30", 0.04, 0.0),
            ("2025-06-30", 0.04, 100.0),
        ]
    },
    "DICP": {
        "name": "Bono Descuento Pesos CER 2033",
        "currency": "ARS",
        "type": "Boncer (CER)",
        "law": "Argentina",
        "issue_date": "2005-04-28",
        "maturity_date": "2033-12-31",
        "coupon_rate": 0.0583,
        "frequency": 2,
        "is_cer": True,
        # base_cer intentionally omitted: 1.40 was a placeholder (BCRA publica CER 31-12-2003 = 1.4568)
        # and this schedule ignores the interest capitalized until 2013, so the residual value is
        # understated. Both errors offset by chance. Load the prospectus CER base + capitalized VR
        # to re-enable it; until then the engine refuses to value it (see TZX28).
        "schedule": [
            ("2024-06-30", 0.0583, 5.0),
            ("2024-12-31", 0.0583, 5.0),
            ("2025-06-30", 0.0583, 5.0),
            ("2025-12-31", 0.0583, 5.0),
            ("2026-06-30", 0.0583, 5.0),
            ("2026-12-31", 0.0583, 5.0),
            ("2027-06-30", 0.0583, 5.0),
            ("2027-12-31", 0.0583, 5.0),
            ("2028-06-30", 0.0583, 5.0),
            ("2028-12-31", 0.0583, 5.0),
            ("2029-06-30", 0.0583, 5.0),
            ("2029-12-31", 0.0583, 5.0),
            ("2030-06-30", 0.0583, 5.0),
            ("2030-12-31", 0.0583, 5.0),
            ("2031-06-30", 0.0583, 5.0),
            ("2031-12-31", 0.0583, 5.0),
            ("2032-06-30", 0.0583, 5.0),
            ("2032-12-31", 0.0583, 5.0),
            ("2033-06-30", 0.0583, 5.0),
            ("2033-12-31", 0.0583, 5.0),
        ]
    }
}

def get_base_ticker(symbol: str) -> str:
    """Extracts base ticker removing D, C, X, Y, Z suffixes."""
    s = symbol.strip().upper()
    # Check known keys directly
    if s in SOVEREIGN_BONDS:
        return s
    # Check if ends with standard currency/clearing suffixes
    for suffix in ["D", "C", "X", "Y", "Z"]:
        if s.endswith(suffix):
            cand = s[:-len(suffix)]
            if cand in SOVEREIGN_BONDS:
                return cand
    return s

def get_bond_definition(symbol: str):
    base = get_base_ticker(symbol)
    if base in SOVEREIGN_BONDS:
        info = dict(SOVEREIGN_BONDS[base])
        if "ref" in info:
            ref_info = SOVEREIGN_BONDS[info["ref"]]
            for k, v in ref_info.items():
                if k not in info:
                    info[k] = v
        return info
    return None
