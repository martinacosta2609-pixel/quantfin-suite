"""
Data Seeder for S&P 500 / NYSE / NASDAQ Institutional Universe
Covers all 11 GICS sectors with 380+ constituents, verified financial profiles,
balance sheet items, pre-run Monte Carlo simulations, and 60-period econometric historical time series.
"""

import numpy as np
import pandas as pd
from datetime import datetime
import json
from engine.database import (
    init_db,
    get_db_connection,
    invalidate_cache,
)
from engine.accounting import compute_all_metrics
from engine.monte_carlo import run_monte_carlo_simulation, stable_seed

GICS_SECTORS = [
    {"name": "Information Technology", "code": "XLK", "description": "Software, hardware, semiconductors, and technology services."},
    {"name": "Health Care", "code": "XLV", "description": "Pharmaceuticals, biotechnology, medical devices, and healthcare providers."},
    {"name": "Financials", "code": "XLF", "description": "Commercial banking, investment banking, asset management, and payment networks."},
    {"name": "Consumer Discretionary", "code": "XLY", "description": "E-commerce, automotive, retail, restaurants, and luxury consumer goods."},
    {"name": "Communication Services", "code": "XLC", "description": "Search engines, social media, entertainment, streaming, and telecom."},
    {"name": "Industrials", "code": "XLI", "description": "Aerospace, defense, machinery, transportation, and industrial conglomerates."},
    {"name": "Consumer Staples", "code": "XLP", "description": "Food, beverage, household products, hypermarkets, and non-cyclical retail."},
    {"name": "Energy", "code": "XLE", "description": "Integrated oil & gas, exploration & production, refining, and oilfield services."},
    {"name": "Utilities", "code": "XLU", "description": "Electric utilities, renewable energy generators, water, and regulated gas."},
    {"name": "Real Estate", "code": "XLRE", "description": "Industrial REITs, cell towers, data centers, logistics, and retail properties."},
    {"name": "Materials", "code": "XLB", "description": "Industrial gases, specialty chemicals, mining, metals, and packaging."}
]

# Comprehensive institutional universe across 11 GICS sectors (380+ stocks)
STOCKS_RAW = [
    # =========================================================================
    # 1. INFORMATION TECHNOLOGY (45 stocks)
    # =========================================================================
    ("AAPL", "Apple Inc.", "Information Technology", "Consumer Electronics", 224.23, 15200.0, 123200.0, 0.15, 106000.0, 66800.0, 61500.0, 118000.0, 9500.0, 134500.0, 6.57, 7.45, 0.075, 0.035, 0.31, 0.02, 0.18, 25.7),
    ("MSFT", "Microsoft Corporation", "Information Technology", "Systems Software & Cloud", 428.50, 7430.0, 109400.0, 0.18, 77000.0, 268000.0, 75500.0, 118500.0, 44500.0, 130000.0, 11.80, 13.25, 0.14, 0.03, 0.44, 0.025, 0.38, 33.0),
    ("NVDA", "NVIDIA Corporation", "Information Technology", "Semiconductors & AI Hardware", 128.40, 24500.0, 72500.0, 0.14, 11000.0, 58000.0, 34800.0, 60500.0, 3200.0, 75000.0, 2.55, 4.10, 0.35, 0.15, 0.58, 0.06, 0.15, 4.9),
    ("AVGO", "Broadcom Inc.", "Information Technology", "Semiconductors", 172.80, 4680.0, 19800.0, 0.12, 71500.0, 69000.0, 10000.0, 21000.0, 1900.0, 26500.0, 4.10, 6.15, 0.18, 0.05, 0.45, 0.03, 0.22, 11.0),
    ("ORCL", "Oracle Corporation", "Information Technology", "Database & Enterprise Software", 174.50, 2760.0, 15400.0, 0.16, 87000.0, 13500.0, 10500.0, 18700.0, 6900.0, 20100.0, 3.85, 6.20, 0.09, 0.03, 0.30, 0.025, 0.35, 19.2),
    ("ADBE", "Adobe Inc.", "Information Technology", "Creative Software", 512.40, 445.0, 6600.0, 0.18, 6200.0, 16000.0, 7800.0, 7300.0, 450.0, 7400.0, 12.20, 18.10, 0.11, 0.025, 0.34, 0.02, 0.15, 48.0),
    ("CRM", "Salesforce Inc.", "Information Technology", "Application Software", 284.10, 965.0, 6500.0, 0.20, 12500.0, 59500.0, 14200.0, 12400.0, 800.0, 9500.0, 5.60, 10.20, 0.10, 0.02, 0.20, 0.03, 0.15, 37.0),
    ("AMD", "Advanced Micro Devices", "Information Technology", "Semiconductors & CPU", 154.20, 1620.0, 2100.0, 0.15, 3000.0, 56000.0, 5300.0, 2900.0, 550.0, 3900.0, 1.25, 3.40, 0.17, 0.08, 0.18, 0.04, 0.25, 14.5),
    ("CSCO", "Cisco Systems Inc.", "Information Technology", "Networking Equipment", 53.60, 4010.0, 14200.0, 0.19, 31000.0, 44000.0, 17800.0, 13800.0, 850.0, 16100.0, 2.70, 3.55, 0.04, 0.02, 0.28, 0.02, 0.15, 13.5),
    ("ACN", "Accenture plc", "Information Technology", "IT Consulting & Services", 348.70, 628.0, 9800.0, 0.23, 3800.0, 28000.0, 8900.0, 9500.0, 600.0, 11200.0, 11.10, 12.80, 0.06, 0.02, 0.15, 0.015, 0.15, 103.0),
    ("INTU", "Intuit Inc.", "Information Technology", "Financial Software", 642.10, 281.0, 3800.0, 0.21, 6100.0, 18500.0, 4100.0, 4900.0, 350.0, 4600.0, 10.50, 19.20, 0.12, 0.03, 0.26, 0.02, 0.18, 58.0),
    ("IBM", "International Business Machines", "Information Technology", "IT Infrastructure & Cloud", 218.40, 920.0, 10200.0, 0.14, 57000.0, 24000.0, 13200.0, 13900.0, 1300.0, 13800.0, 8.80, 10.30, 0.04, 0.02, 0.17, 0.015, 0.20, 67.0),
    ("TXN", "Texas Instruments", "Information Technology", "Analog Semiconductors", 201.50, 915.0, 6400.0, 0.13, 13800.0, 17500.0, 8500.0, 6400.0, 4800.0, 8200.0, 5.80, 5.60, 0.05, 0.04, 0.40, 0.03, 0.45, 18.0),
    ("QCOM", "QUALCOMM Incorporated", "Information Technology", "Wireless Chips", 168.30, 1115.0, 10800.0, 0.14, 15000.0, 23000.0, 12000.0, 11500.0, 1400.0, 12400.0, 8.70, 10.10, 0.08, 0.04, 0.30, 0.03, 0.18, 34.0),
    ("AMAT", "Applied Materials Inc.", "Information Technology", "Semiconductor Equipment", 204.60, 825.0, 7800.0, 0.12, 6400.0, 17800.0, 8700.0, 8500.0, 1100.0, 8600.0, 8.60, 9.40, 0.09, 0.04, 0.29, 0.025, 0.20, 32.0),
    ("NOW", "ServiceNow Inc.", "Information Technology", "Workflow Automation", 894.20, 206.0, 1450.0, 0.18, 1500.0, 8500.0, 4800.0, 3400.0, 600.0, 2800.0, 5.10, 13.80, 0.21, 0.03, 0.22, 0.02, 0.20, 48.0),
    ("LRCX", "Lam Research Corporation", "Information Technology", "Wafer Fabrication Equipment", 79.50, 1300.0, 4500.0, 0.11, 5000.0, 8400.0, 5600.0, 4800.0, 450.0, 4900.0, 3.20, 3.65, 0.10, 0.05, 0.31, 0.03, 0.18, 11.5),
    ("MU", "Micron Technology Inc.", "Information Technology", "Memory & Storage", 102.80, 1110.0, 1800.0, 0.12, 14000.0, 44000.0, 8500.0, 6200.0, 6800.0, 5800.0, 1.45, 8.80, 0.18, 0.14, 0.22, 0.08, 0.60, 22.0),
    ("PANW", "Palo Alto Networks", "Information Technology", "Cybersecurity", 348.60, 325.0, 1100.0, 0.17, 2100.0, 4500.0, 3800.0, 3100.0, 200.0, 2200.0, 3.80, 6.20, 0.16, 0.03, 0.19, 0.02, 0.15, 25.0),
    ("SNPS", "Synopsys Inc.", "Information Technology", "Electronic Design Automation", 518.20, 154.0, 1600.0, 0.16, 120.0, 7200.0, 1800.0, 1700.0, 220.0, 1900.0, 8.50, 13.20, 0.13, 0.02, 0.27, 0.02, 0.18, 39.0),
    ("CDNS", "Cadence Design Systems", "Information Technology", "EDA Software & IP", 274.50, 272.0, 1300.0, 0.18, 650.0, 3900.0, 1100.0, 1350.0, 120.0, 1500.0, 3.90, 5.90, 0.12, 0.02, 0.30, 0.02, 0.15, 15.0),
    ("KLAC", "KLA Corporation", "Information Technology", "Process Control Metrology", 712.40, 134.0, 3800.0, 0.13, 6200.0, 3500.0, 4200.0, 3400.0, 310.0, 4100.0, 20.80, 28.50, 0.11, 0.04, 0.38, 0.03, 0.16, 73.0),
    ("ADI", "Analog Devices Inc.", "Information Technology", "Semiconductor Processing", 228.10, 495.0, 3400.0, 0.14, 7600.0, 34000.0, 2400.0, 3600.0, 950.0, 4600.0, 4.30, 6.70, 0.07, 0.04, 0.35, 0.03, 0.25, 21.0),
    ("CRWD", "CrowdStrike Holdings", "Information Technology", "Endpoint Security", 298.50, 244.0, 420.0, 0.15, 780.0, 2600.0, 3700.0, 1150.0, 120.0, 850.0, 1.40, 4.10, 0.24, 0.05, 0.18, 0.03, 0.15, 14.5),
    ("APH", "Amphenol Corporation", "Information Technology", "Connectors & Sensors", 64.80, 1210.0, 2600.0, 0.22, 5400.0, 8600.0, 1900.0, 2400.0, 420.0, 3100.0, 1.70, 1.95, 0.09, 0.025, 0.21, 0.015, 0.20, 11.5),
    ("NXPI", "NXP Semiconductors", "Information Technology", "Automotive Semiconductors", 236.40, 255.0, 4200.0, 0.14, 11200.0, 9200.0, 3800.0, 3500.0, 1100.0, 4800.0, 11.20, 13.80, 0.06, 0.03, 0.34, 0.025, 0.25, 52.0),
    ("MCHP", "Microchip Technology", "Information Technology", "Microcontrollers", 78.20, 538.0, 2100.0, 0.13, 5800.0, 6700.0, 450.0, 2100.0, 420.0, 2800.0, 2.50, 2.65, 0.05, 0.04, 0.36, 0.03, 0.22, 12.0),
    ("FTNT", "Fortinet Inc.", "Information Technology", "Network Security", 78.90, 765.0, 1450.0, 0.17, 980.0, -180.0, 3100.0, 1900.0, 190.0, 1650.0, 1.65, 2.05, 0.13, 0.03, 0.28, 0.025, 0.12, 7.2),
    ("TEL", "TE Connectivity Ltd.", "Information Technology", "Electronic Components", 146.50, 305.0, 2400.0, 0.18, 4200.0, 11500.0, 1400.0, 2600.0, 680.0, 3100.0, 7.30, 8.40, 0.05, 0.02, 0.17, 0.015, 0.25, 52.0),
    ("HPQ", "HP Inc.", "Information Technology", "PC & Printing Hardware", 35.80, 975.0, 3800.0, 0.21, 10200.0, -1200.0, 2800.0, 3400.0, 600.0, 4300.0, 3.10, 3.50, 0.03, 0.02, 0.08, 0.01, 0.18, 54.0),
    ("GLW", "Corning Incorporated", "Information Technology", "Specialty Glass & Display", 45.20, 855.0, 1800.0, 0.19, 7800.0, 12800.0, 1500.0, 2000.0, 1200.0, 2700.0, 1.80, 2.25, 0.06, 0.025, 0.16, 0.02, 0.40, 16.0),
    ("KEYS", "Keysight Technologies", "Information Technology", "Electronic Test Instruments", 158.40, 174.0, 1100.0, 0.14, 1800.0, 4800.0, 1600.0, 1200.0, 220.0, 1400.0, 6.10, 6.80, 0.06, 0.03, 0.24, 0.02, 0.20, 29.0),
    ("WDC", "Western Digital Corp.", "Information Technology", "Hard Drives & Flash", 68.90, 335.0, 950.0, 0.16, 7400.0, 10200.0, 2100.0, 1400.0, 850.0, 1900.0, 1.80, 5.20, 0.12, 0.08, 0.15, 0.05, 0.40, 38.0),
    ("STX", "Seagate Technology", "Information Technology", "Mass Data Storage", 104.20, 210.0, 820.0, 0.12, 5700.0, -850.0, 890.0, 1100.0, 320.0, 1300.0, 2.10, 5.80, 0.10, 0.06, 0.16, 0.04, 0.30, 34.0),
    ("MPWR", "Monolithic Power Systems", "Information Technology", "Power Semiconductor ICs", 845.00, 48.0, 620.0, 0.13, 0.0, 2400.0, 1200.0, 680.0, 80.0, 720.0, 11.20, 15.60, 0.16, 0.04, 0.31, 0.03, 0.15, 41.0),
    ("ON", "ON Semiconductor", "Information Technology", "Power & Sensing Chips", 72.40, 428.0, 2300.0, 0.15, 3400.0, 7800.0, 2500.0, 2100.0, 1400.0, 3100.0, 4.40, 4.80, 0.06, 0.04, 0.31, 0.03, 0.45, 18.0),
    ("TER", "Teradyne Inc.", "Information Technology", "Automated Test Systems", 122.60, 155.0, 680.0, 0.16, 80.0, 2900.0, 850.0, 710.0, 140.0, 820.0, 3.10, 3.90, 0.08, 0.04, 0.24, 0.03, 0.20, 17.5),
    ("ZBRA", "Zebra Technologies", "Information Technology", "Enterprise Barcode & RFID", 364.50, 51.0, 720.0, 0.17, 2100.0, 3200.0, 240.0, 780.0, 85.0, 920.0, 8.80, 13.80, 0.07, 0.03, 0.16, 0.02, 0.15, 96.0),
    ("SMCI", "Super Micro Computer", "Information Technology", "Server & Storage Systems", 44.20, 585.0, 1200.0, 0.16, 2100.0, 4800.0, 1500.0, 850.0, 180.0, 1350.0, 2.15, 3.40, 0.25, 0.12, 0.09, 0.03, 0.30, 28.0),
    ("ANSS", "ANSYS Inc.", "Information Technology", "Engineering Simulation", 328.00, 87.0, 620.0, 0.18, 750.0, 4900.0, 820.0, 740.0, 80.0, 790.0, 5.80, 9.80, 0.09, 0.02, 0.35, 0.02, 0.15, 26.0),
    ("TYL", "Tyler Technologies", "Information Technology", "Public Sector Software", 584.20, 42.5, 320.0, 0.20, 620.0, 3100.0, 290.0, 450.0, 55.0, 460.0, 4.80, 10.40, 0.09, 0.02, 0.18, 0.02, 0.15, 50.0),
    ("FICO", "Fair Isaac Corporation", "Information Technology", "Analytics & Credit Scores", 1890.00, 24.5, 780.0, 0.24, 2100.0, -800.0, 210.0, 580.0, 40.0, 840.0, 21.00, 27.50, 0.12, 0.02, 0.45, 0.02, 0.10, 71.0),
    ("NTAP", "NetApp Inc.", "Information Technology", "Cloud Data Management", 124.60, 208.0, 1400.0, 0.19, 2900.0, 1100.0, 3100.0, 1600.0, 210.0, 1650.0, 5.40, 7.10, 0.06, 0.025, 0.22, 0.02, 0.15, 31.0),
    ("AKAM", "Akamai Technologies", "Information Technology", "CDN & Cloud Security", 98.40, 151.0, 740.0, 0.18, 3800.0, 4400.0, 680.0, 1100.0, 480.0, 1200.0, 3.80, 6.40, 0.07, 0.02, 0.20, 0.02, 0.35, 26.0),
    ("FFIV", "F5 Inc.", "Information Technology", "Application Delivery & Security", 218.00, 59.0, 680.0, 0.18, 350.0, 2900.0, 950.0, 820.0, 75.0, 850.0, 9.20, 13.50, 0.06, 0.02, 0.24, 0.02, 0.12, 49.0),

    # =========================================================================
    # 2. HEALTH CARE (45 stocks)
    # =========================================================================
    ("LLY", "Eli Lilly and Company", "Health Care", "Pharmaceuticals", 892.40, 950.0, 13500.0, 0.14, 28000.0, 14500.0, 3200.0, 8900.0, 4200.0, 15800.0, 8.70, 21.50, 0.24, 0.06, 0.35, 0.04, 0.35, 42.0),
    ("UNH", "UnitedHealth Group Inc.", "Health Care", "Managed Healthcare", 574.60, 920.0, 32800.0, 0.22, 74000.0, 98000.0, 31000.0, 29000.0, 3300.0, 36500.0, 24.80, 27.60, 0.08, 0.02, 0.088, 0.008, 0.20, 405.0),
    ("JNJ", "Johnson & Johnson", "Health Care", "Pharmaceuticals & MedTech", 161.20, 2400.0, 23500.0, 0.16, 36000.0, 75000.0, 24000.0, 22800.0, 4600.0, 28200.0, 6.80, 10.05, 0.045, 0.02, 0.27, 0.015, 0.25, 36.0),
    ("ABBV", "AbbVie Inc.", "Health Care", "Biotechnology", 188.50, 1765.0, 18200.0, 0.15, 64000.0, 12000.0, 13000.0, 22000.0, 1100.0, 22500.0, 4.25, 11.20, 0.05, 0.03, 0.34, 0.03, 0.18, 31.0),
    ("MRK", "Merck & Co. Inc.", "Health Care", "Oncology & Vaccines", 112.40, 2530.0, 17800.0, 0.15, 38000.0, 42000.0, 9500.0, 16500.0, 4900.0, 21000.0, 5.40, 8.20, 0.06, 0.03, 0.30, 0.025, 0.30, 24.0),
    ("TMO", "Thermo Fisher Scientific", "Health Care", "Life Sciences Tools", 584.50, 382.0, 7800.0, 0.14, 35000.0, 48000.0, 7400.0, 8400.0, 1500.0, 10200.0, 15.60, 22.80, 0.07, 0.03, 0.22, 0.02, 0.22, 112.0),
    ("ABT", "Abbott Laboratories", "Health Care", "Medical Devices & Diagnostics", 116.80, 1740.0, 7600.0, 0.15, 15500.0, 39000.0, 7200.0, 8100.0, 1900.0, 9800.0, 3.80, 4.65, 0.055, 0.02, 0.19, 0.015, 0.25, 23.5),
    ("DHR", "Danaher Corporation", "Health Care", "Bioprocessing & Diagnostics", 268.40, 740.0, 5400.0, 0.16, 18500.0, 52000.0, 6800.0, 6400.0, 1200.0, 7200.0, 6.20, 7.80, 0.065, 0.03, 0.25, 0.02, 0.22, 32.0),
    ("PFE", "Pfizer Inc.", "Health Care", "Biopharmaceuticals", 28.90, 5660.0, 6800.0, 0.14, 62000.0, 88000.0, 11500.0, 12500.0, 3800.0, 11500.0, 1.20, 2.80, 0.04, 0.03, 0.18, 0.03, 0.30, 10.2),
    ("ISRG", "Intuitive Surgical Inc.", "Health Care", "Robotic Surgery Systems", 498.20, 355.0, 2200.0, 0.17, 0.0, 15500.0, 8200.0, 2400.0, 1100.0, 2600.0, 5.20, 6.80, 0.14, 0.03, 0.30, 0.025, 0.35, 21.0),
    ("AMGN", "Amgen Inc.", "Health Care", "Biotechnology", 318.50, 535.0, 10200.0, 0.14, 61000.0, 11500.0, 9800.0, 11200.0, 1100.0, 13200.0, 8.20, 19.50, 0.07, 0.025, 0.37, 0.025, 0.15, 52.0),
    ("BMY", "Bristol-Myers Squibb", "Health Care", "Biopharmaceuticals", 51.40, 2030.0, 8200.0, 0.16, 42000.0, 18000.0, 8900.0, 13400.0, 950.0, 10500.0, 2.10, 3.80, 0.035, 0.025, 0.22, 0.025, 0.15, 22.0),
    ("ELV", "Elevance Health Inc.", "Health Care", "Health Insurance", 412.00, 232.0, 9100.0, 0.22, 28000.0, 41000.0, 12500.0, 8200.0, 1400.0, 10500.0, 27.50, 35.80, 0.07, 0.02, 0.055, 0.008, 0.18, 730.0),
    ("SYK", "Stryker Corporation", "Health Care", "Orthopedics & MedTech", 362.40, 381.0, 4200.0, 0.16, 13500.0, 19800.0, 2400.0, 3900.0, 850.0, 4900.0, 8.80, 12.20, 0.09, 0.025, 0.21, 0.015, 0.22, 54.0),
    ("GILD", "Gilead Sciences Inc.", "Health Care", "Virology & Oncology", 84.50, 1245.0, 8900.0, 0.15, 25000.0, 22000.0, 8200.0, 8800.0, 650.0, 10500.0, 4.60, 7.40, 0.045, 0.02, 0.36, 0.025, 0.12, 22.0),
    ("MDT", "Medtronic plc", "Health Care", "Cardiovascular & Medical Devices", 89.20, 1290.0, 6100.0, 0.15, 27000.0, 51000.0, 7800.0, 6800.0, 1400.0, 8200.0, 3.45, 5.50, 0.045, 0.02, 0.20, 0.015, 0.22, 25.0),
    ("VRTX", "Vertex Pharmaceuticals", "Health Care", "Cystic Fibrosis & Gene Editing", 468.20, 258.0, 4100.0, 0.16, 1200.0, 18500.0, 11200.0, 4200.0, 420.0, 4600.0, 14.20, 17.50, 0.11, 0.03, 0.42, 0.03, 0.15, 38.0),
    ("CI", "The Cigna Group", "Health Care", "Pharmacy Services & Care", 342.10, 285.0, 7800.0, 0.22, 32000.0, 45000.0, 8500.0, 9400.0, 1200.0, 9200.0, 18.50, 28.40, 0.08, 0.02, 0.042, 0.006, 0.15, 710.0),
    ("REGN", "Regeneron Pharmaceuticals", "Health Care", "Biotechnology & Eye Care", 984.00, 108.0, 4800.0, 0.14, 2700.0, 26000.0, 17500.0, 4600.0, 680.0, 5400.0, 36.50, 44.80, 0.085, 0.03, 0.37, 0.03, 0.18, 122.0),
    ("BDX", "Becton Dickinson and Co.", "Health Care", "Medical Supplies & Systems", 238.40, 290.0, 2900.0, 0.15, 18500.0, 26000.0, 2200.0, 3100.0, 1100.0, 4100.0, 6.20, 13.50, 0.05, 0.02, 0.15, 0.015, 0.35, 68.0),
    ("ZTS", "Zoetis Inc.", "Health Care", "Animal Health", 188.20, 456.0, 3100.0, 0.21, 6800.0, 5200.0, 2100.0, 2800.0, 600.0, 3600.0, 5.20, 5.80, 0.08, 0.025, 0.37, 0.02, 0.20, 18.5),
    ("HCA", "HCA Healthcare Inc.", "Health Care", "Hospital Networks", 382.50, 258.0, 8100.0, 0.23, 41000.0, 420.0, 1800.0, 8600.0, 4800.0, 11400.0, 21.00, 22.80, 0.07, 0.02, 0.12, 0.01, 0.45, 250.0),
    ("BSX", "Boston Scientific Corp.", "Health Care", "Interventional Cardiology", 84.60, 1470.0, 2800.0, 0.14, 11500.0, 21000.0, 1600.0, 2900.0, 680.0, 3600.0, 1.45, 2.45, 0.11, 0.025, 0.20, 0.02, 0.25, 10.0),
    ("MCK", "McKesson Corporation", "Health Care", "Pharmaceutical Distribution", 534.00, 131.0, 4100.0, 0.21, 6200.0, -1800.0, 3200.0, 4500.0, 580.0, 4600.0, 24.50, 32.10, 0.08, 0.015, 0.014, 0.002, 0.15, 2350.0),
    ("COR", "Cencora Inc.", "Health Care", "Drug Wholesaling", 238.50, 198.0, 3400.0, 0.22, 4800.0, -1200.0, 2800.0, 3600.0, 480.0, 3900.0, 10.20, 13.80, 0.08, 0.015, 0.013, 0.002, 0.15, 1450.0),
    ("EW", "Edwards Lifesciences", "Health Care", "Heart Valves & Hemodynamic", 68.20, 595.0, 1700.0, 0.15, 620.0, 6400.0, 1900.0, 1600.0, 310.0, 1950.0, 2.45, 2.75, 0.08, 0.025, 0.28, 0.02, 0.20, 10.2),
    ("DXCM", "DexCom Inc.", "Health Care", "Continuous Glucose Monitors", 74.50, 388.0, 720.0, 0.18, 2400.0, 2800.0, 3100.0, 920.0, 280.0, 980.0, 1.40, 1.75, 0.14, 0.04, 0.20, 0.03, 0.30, 9.8),
    ("IDXX", "IDEXX Laboratories", "Health Care", "Veterinary Diagnostics", 428.00, 82.5, 1150.0, 0.21, 850.0, 1800.0, 520.0, 1050.0, 180.0, 1280.0, 10.80, 11.60, 0.08, 0.02, 0.31, 0.02, 0.16, 45.0),
    ("CNC", "Centene Corporation", "Health Care", "Medicaid & Managed Care", 74.80, 525.0, 3800.0, 0.23, 17500.0, 26000.0, 14200.0, 4200.0, 950.0, 4600.0, 5.20, 6.85, 0.05, 0.02, 0.028, 0.004, 0.22, 280.0),
    ("IQV", "IQVIA Holdings Inc.", "Health Care", "Clinical Research & Data", 228.40, 181.0, 2100.0, 0.19, 13800.0, 6400.0, 1400.0, 2100.0, 650.0, 3400.0, 7.80, 11.20, 0.065, 0.02, 0.15, 0.015, 0.28, 82.0),
    ("MTD", "Mettler-Toledo International", "Health Care", "Precision Instruments", 1245.00, 21.4, 1100.0, 0.18, 2100.0, -220.0, 210.0, 920.0, 85.0, 1200.0, 38.50, 42.00, 0.06, 0.02, 0.29, 0.02, 0.10, 175.0),
    ("RMD", "ResMed Inc.", "Health Care", "Sleep Apnea & Respiratory", 242.00, 146.0, 1350.0, 0.19, 980.0, 4800.0, 350.0, 1380.0, 140.0, 1550.0, 7.10, 8.80, 0.09, 0.025, 0.31, 0.02, 0.12, 32.0),
    ("ALGN", "Align Technology Inc.", "Health Care", "Invisalign Orthodontics", 238.00, 75.0, 620.0, 0.21, 120.0, 3800.0, 1100.0, 850.0, 160.0, 880.0, 6.20, 9.50, 0.07, 0.03, 0.18, 0.02, 0.20, 52.0),
    ("BIIB", "Biogen Inc.", "Health Care", "Neurology & Alzheimer", 188.00, 145.0, 2200.0, 0.16, 6200.0, 14200.0, 1800.0, 2100.0, 310.0, 2800.0, 8.40, 15.60, 0.03, 0.025, 0.23, 0.03, 0.15, 68.0),
    ("BAX", "Baxter International Inc.", "Health Care", "Renal Care & Infusion", 36.20, 508.0, 1600.0, 0.17, 14200.0, 6200.0, 1400.0, 1700.0, 720.0, 2500.0, 1.90, 2.95, 0.04, 0.02, 0.12, 0.015, 0.40, 29.0),
    ("STE", "STERIS plc", "Health Care", "Infection Prevention & Sterilization", 224.00, 98.0, 980.0, 0.19, 3100.0, 6400.0, 380.0, 920.0, 310.0, 1280.0, 6.20, 9.20, 0.07, 0.02, 0.19, 0.015, 0.32, 54.0),
    ("WST", "West Pharmaceutical Services", "Health Care", "Injectable Drug Packaging", 312.00, 73.0, 720.0, 0.20, 350.0, 2900.0, 780.0, 680.0, 290.0, 880.0, 6.50, 7.80, 0.065, 0.025, 0.25, 0.02, 0.35, 39.0),
    ("CAH", "Cardinal Health Inc.", "Health Care", "Medical Supply Distribution", 108.40, 242.0, 2400.0, 0.22, 4800.0, -1800.0, 3800.0, 3200.0, 510.0, 2900.0, 5.20, 7.50, 0.08, 0.015, 0.012, 0.002, 0.15, 920.0),
    ("LH", "Labcorp (Laboratory Corp)", "Health Care", "Clinical Diagnostic Labs", 226.00, 84.0, 1400.0, 0.22, 5800.0, 9800.0, 520.0, 1500.0, 480.0, 2100.0, 9.80, 14.50, 0.05, 0.02, 0.11, 0.01, 0.32, 150.0),
    ("MOH", "Molina Healthcare Inc.", "Health Care", "Medicaid Managed Care", 318.00, 58.0, 1500.0, 0.24, 2900.0, 4200.0, 4800.0, 1600.0, 220.0, 1750.0, 18.50, 23.50, 0.08, 0.02, 0.045, 0.006, 0.15, 580.0),
    ("VTRS", "Viatris Inc.", "Health Care", "Generic Pharmaceuticals", 11.80, 1190.0, 2400.0, 0.16, 17500.0, 19500.0, 1200.0, 2900.0, 820.0, 4200.0, 0.95, 2.70, 0.02, 0.02, 0.17, 0.02, 0.25, 12.8),
    ("TECH", "Bio-Techne Corporation", "Health Care", "Proteins & Antibodies", 72.50, 158.0, 320.0, 0.18, 520.0, 2100.0, 210.0, 310.0, 55.0, 410.0, 1.40, 1.95, 0.07, 0.025, 0.28, 0.02, 0.15, 7.2),
    ("HOLX", "Hologic Inc.", "Health Care", "Women's Health & Mammography", 81.20, 234.0, 1200.0, 0.20, 2800.0, 4800.0, 2200.0, 1300.0, 180.0, 1550.0, 3.40, 4.10, 0.055, 0.02, 0.30, 0.02, 0.15, 17.0),
    ("TFX", "Teleflex Incorporated", "Health Care", "Specialty Medical Devices", 232.00, 46.5, 620.0, 0.17, 2100.0, 4400.0, 310.0, 580.0, 110.0, 780.0, 7.80, 13.80, 0.05, 0.02, 0.21, 0.015, 0.20, 64.0),
    ("PODD", "Insulet Corporation", "Health Care", "Tubeless Insulin Pumps", 258.00, 70.0, 380.0, 0.18, 1400.0, 950.0, 820.0, 410.0, 210.0, 520.0, 2.80, 3.20, 0.18, 0.04, 0.19, 0.03, 0.45, 27.0),

    # =========================================================================
    # 3. FINANCIALS (45 stocks)
    # =========================================================================
    ("JPM", "JPMorgan Chase & Co.", "Financials", "Diversified Banking", 218.40, 2860.0, 65000.0, 0.20, 380000.0, 328000.0, 540000.0, 52000.0, 4500.0, 68000.0, 17.80, 18.50, 0.07, 0.03, 0.38, 0.03, 0.20, 58.0),
    ("V", "Visa Inc.", "Financials", "Transaction & Payment Processing", 282.60, 2010.0, 23400.0, 0.19, 21500.0, 38800.0, 19200.0, 20800.0, 1100.0, 24800.0, 9.35, 11.10, 0.10, 0.02, 0.67, 0.02, 0.12, 17.5),
    ("MA", "Mastercard Incorporated", "Financials", "Payment Networks", 496.30, 925.0, 15200.0, 0.18, 16500.0, 7200.0, 9500.0, 13100.0, 600.0, 16100.0, 12.80, 14.50, 0.11, 0.025, 0.58, 0.02, 0.14, 28.0),
    ("BAC", "Bank of America Corp.", "Financials", "Major Commercial Banks", 41.20, 7820.0, 31000.0, 0.18, 290000.0, 292000.0, 380000.0, 28000.0, 2800.0, 33500.0, 3.25, 3.60, 0.05, 0.03, 0.30, 0.03, 0.22, 13.0),
    ("WFC", "Wells Fargo & Company", "Financials", "Retail & Commercial Banking", 58.40, 3450.0, 23000.0, 0.19, 180000.0, 182000.0, 165000.0, 21000.0, 2100.0, 25500.0, 4.80, 5.40, 0.045, 0.03, 0.29, 0.025, 0.20, 23.5),
    ("MS", "Morgan Stanley", "Financials", "Investment Banking & Wealth", 108.50, 1620.0, 14500.0, 0.21, 240000.0, 102000.0, 115000.0, 12800.0, 1400.0, 15800.0, 6.20, 7.80, 0.065, 0.03, 0.26, 0.025, 0.18, 35.0),
    ("GS", "The Goldman Sachs Group", "Financials", "Global Investment Banking", 504.00, 324.0, 15800.0, 0.21, 310000.0, 118000.0, 185000.0, 14200.0, 1800.0, 17200.0, 28.50, 38.00, 0.075, 0.04, 0.28, 0.035, 0.18, 145.0),
    ("BLK", "BlackRock Inc.", "Financials", "Asset Management & ETFs", 955.00, 148.0, 6800.0, 0.21, 11200.0, 42000.0, 9200.0, 6200.0, 480.0, 7400.0, 38.00, 43.50, 0.08, 0.025, 0.36, 0.02, 0.15, 128.0),
    ("SPGI", "S&P Global Inc.", "Financials", "Financial Ratings & Benchmarks", 512.00, 310.0, 5400.0, 0.21, 11800.0, 35000.0, 1800.0, 4600.0, 220.0, 6100.0, 11.20, 14.80, 0.09, 0.02, 0.44, 0.02, 0.12, 40.0),
    ("C", "Citigroup Inc.", "Financials", "Global Consumer & Institutional", 64.20, 1910.0, 16500.0, 0.22, 295000.0, 208000.0, 280000.0, 14500.0, 2200.0, 18500.0, 4.40, 6.80, 0.04, 0.03, 0.22, 0.03, 0.25, 41.0),
    ("AXP", "American Express Company", "Financials", "Consumer & Corporate Credit", 274.50, 715.0, 11200.0, 0.21, 52000.0, 31000.0, 34000.0, 13800.0, 1500.0, 12500.0, 12.20, 13.80, 0.09, 0.025, 0.20, 0.02, 0.20, 85.0),
    ("PGR", "The Progressive Corp.", "Financials", "Property & Casualty Insurance", 248.00, 585.0, 8500.0, 0.21, 7400.0, 24000.0, 4800.0, 9200.0, 450.0, 9100.0, 11.50, 13.20, 0.12, 0.03, 0.14, 0.02, 0.10, 112.0),
    ("CB", "Chubb Limited", "Financials", "Global Commercial Insurance", 284.00, 404.0, 11500.0, 0.18, 15500.0, 61000.0, 2800.0, 12800.0, 550.0, 12200.0, 21.00, 22.80, 0.07, 0.02, 0.21, 0.02, 0.12, 130.0),
    ("MMC", "Marsh & McLennan Companies", "Financials", "Insurance Brokerage & Risk", 224.50, 492.0, 5100.0, 0.24, 14200.0, 13500.0, 2200.0, 4100.0, 480.0, 5800.0, 7.80, 8.90, 0.075, 0.02, 0.24, 0.015, 0.15, 46.0),
    ("AON", "Aon plc", "Financials", "Insurance Broking & Analytics", 354.00, 218.0, 3800.0, 0.19, 16800.0, -1200.0, 1100.0, 3200.0, 280.0, 4400.0, 12.50, 16.20, 0.07, 0.02, 0.27, 0.015, 0.12, 62.0),
    ("MCO", "Moody's Corporation", "Financials", "Credit Ratings & Analytics", 478.00, 182.0, 2600.0, 0.22, 7800.0, 3800.0, 2400.0, 2400.0, 190.0, 3100.0, 9.80, 12.50, 0.09, 0.02, 0.42, 0.02, 0.12, 35.0),
    ("BK", "The Bank of New York Mellon", "Financials", "Custody Banking & Securities", 72.80, 742.0, 4800.0, 0.21, 62000.0, 41000.0, 55000.0, 4200.0, 850.0, 5400.0, 4.80, 5.80, 0.05, 0.02, 0.27, 0.02, 0.22, 24.0),
    ("CME", "CME Group Inc.", "Financials", "Financial Derivatives Exchange", 218.00, 360.0, 3600.0, 0.23, 3400.0, 27000.0, 2800.0, 3400.0, 120.0, 4100.0, 8.80, 9.80, 0.06, 0.02, 0.62, 0.02, 0.08, 16.0),
    ("ICE", "Intercontinental Exchange", "Financials", "Exchanges, Clearing & Mortgage", 162.00, 574.0, 4100.0, 0.22, 21000.0, 28000.0, 1800.0, 3600.0, 420.0, 5200.0, 4.40, 6.20, 0.07, 0.02, 0.48, 0.02, 0.15, 15.8),
    ("AJG", "Arthur J. Gallagher & Co.", "Financials", "Insurance Brokerage Services", 284.00, 222.0, 1900.0, 0.23, 7200.0, 11500.0, 1100.0, 1700.0, 180.0, 2400.0, 6.20, 10.20, 0.10, 0.025, 0.20, 0.015, 0.15, 46.0),
    ("USB", "U.S. Bancorp", "Financials", "Regional Banking", 46.20, 1560.0, 8200.0, 0.20, 64000.0, 54000.0, 58000.0, 7100.0, 980.0, 9600.0, 3.60, 4.20, 0.04, 0.025, 0.30, 0.025, 0.25, 17.5),
    ("PNC", "The PNC Financial Services", "Financials", "Diversified Financial Services", 182.40, 398.0, 7100.0, 0.19, 58000.0, 51000.0, 48000.0, 6400.0, 820.0, 8200.0, 13.50, 14.80, 0.045, 0.025, 0.32, 0.025, 0.22, 53.0),
    ("TRV", "The Travelers Companies", "Financials", "Commercial & Personal Property", 238.00, 228.0, 4800.0, 0.20, 7800.0, 23000.0, 1800.0, 5400.0, 320.0, 5200.0, 14.20, 18.50, 0.07, 0.025, 0.12, 0.02, 0.10, 185.0),
    ("AFL", "Aflac Incorporated", "Financials", "Supplemental Health Insurance", 108.00, 565.0, 5400.0, 0.21, 6800.0, 26000.0, 4200.0, 4200.0, 150.0, 5600.0, 6.80, 6.90, 0.03, 0.02, 0.28, 0.02, 0.08, 33.0),
    ("COF", "Capital One Financial", "Financials", "Credit Cards & Banking", 152.00, 381.0, 6400.0, 0.21, 54000.0, 58000.0, 42000.0, 7800.0, 1200.0, 8400.0, 12.80, 14.50, 0.06, 0.03, 0.24, 0.03, 0.22, 98.0),
    ("PRU", "Prudential Financial Inc.", "Financials", "Life Insurance & Asset Mgt", 122.50, 358.0, 5200.0, 0.19, 21000.0, 28000.0, 18000.0, 4800.0, 280.0, 5900.0, 9.40, 13.20, 0.04, 0.02, 0.10, 0.015, 0.10, 152.0),
    ("MET", "MetLife Inc.", "Financials", "Life Insurance & Employee Benefits", 82.40, 712.0, 5400.0, 0.20, 18500.0, 31000.0, 21000.0, 5100.0, 350.0, 6200.0, 6.20, 8.80, 0.045, 0.02, 0.08, 0.015, 0.10, 96.0),
    ("ALL", "The Allstate Corporation", "Financials", "Auto & Homeowners Insurance", 192.00, 262.0, 4600.0, 0.21, 8200.0, 18500.0, 3100.0, 5400.0, 410.0, 5100.0, 9.80, 16.50, 0.08, 0.03, 0.08, 0.02, 0.12, 220.0),
    ("HIG", "The Hartford Financial Services", "Financials", "Commercial P&C Insurance", 116.00, 298.0, 3600.0, 0.21, 4800.0, 15200.0, 1600.0, 3800.0, 180.0, 3900.0, 9.20, 10.80, 0.06, 0.02, 0.15, 0.015, 0.08, 85.0),
    ("AIG", "American International Group", "Financials", "General Insurance", 74.80, 672.0, 4800.0, 0.21, 14000.0, 42000.0, 2800.0, 4100.0, 320.0, 5200.0, 5.40, 6.90, 0.035, 0.02, 0.11, 0.02, 0.10, 72.0),
    ("ACGL", "Arch Capital Group Ltd.", "Financials", "Reinsurance & Mortgage Specialty", 104.00, 372.0, 4400.0, 0.14, 3800.0, 19200.0, 2200.0, 4600.0, 120.0, 4600.0, 9.80, 9.40, 0.10, 0.03, 0.28, 0.025, 0.08, 41.0),
    ("FITB", "Fifth Third Bancorp", "Financials", "Commercial Banking", 44.50, 680.0, 3100.0, 0.20, 21000.0, 18500.0, 14000.0, 2800.0, 380.0, 3600.0, 3.40, 3.80, 0.04, 0.025, 0.32, 0.025, 0.20, 12.8),
    ("MTB", "M&T Bank Corporation", "Financials", "Commercial Banking & Wealth", 188.00, 165.0, 3800.0, 0.22, 14500.0, 26000.0, 19000.0, 3200.0, 280.0, 4200.0, 14.80, 16.20, 0.04, 0.02, 0.38, 0.025, 0.15, 58.0),
    ("TFC", "Truist Financial Corporation", "Financials", "Regional Banking", 44.80, 1330.0, 5400.0, 0.21, 56000.0, 58000.0, 42000.0, 4800.0, 720.0, 6800.0, 2.80, 3.70, 0.035, 0.025, 0.26, 0.025, 0.20, 17.5),
    ("DFS", "Discover Financial Services", "Financials", "Direct Banking & Payments", 154.00, 250.0, 3800.0, 0.22, 28000.0, 16000.0, 19000.0, 4200.0, 450.0, 4600.0, 12.50, 13.50, 0.06, 0.03, 0.25, 0.03, 0.20, 62.0),
    ("STT", "State Street Corporation", "Financials", "Investment Servicing & Custody", 92.50, 304.0, 3100.0, 0.18, 28000.0, 25000.0, 24000.0, 2800.0, 420.0, 3600.0, 6.50, 8.40, 0.045, 0.02, 0.25, 0.02, 0.20, 39.0),
    ("AMP", "Ameriprise Financial Inc.", "Financials", "Wealth & Asset Management", 524.00, 99.0, 3900.0, 0.20, 4800.0, 4500.0, 3800.0, 3400.0, 180.0, 4200.0, 32.00, 37.50, 0.07, 0.02, 0.26, 0.02, 0.10, 160.0),
    ("WTW", "Willis Towers Watson", "Financials", "Advisory, Broking & Solutions", 308.00, 101.0, 1800.0, 0.19, 5400.0, 9800.0, 1200.0, 1600.0, 210.0, 2400.0, 11.20, 16.80, 0.06, 0.02, 0.18, 0.015, 0.15, 94.0),
    ("BRO", "Brown & Brown Inc.", "Financials", "Insurance Intermediary", 108.00, 285.0, 1250.0, 0.24, 4800.0, 5800.0, 820.0, 1100.0, 95.0, 1600.0, 3.20, 3.85, 0.09, 0.02, 0.28, 0.015, 0.12, 16.0),
    ("NTRS", "Northern Trust Corporation", "Financials", "Wealth & Asset Servicing", 98.40, 202.0, 2200.0, 0.22, 18500.0, 12500.0, 16000.0, 1800.0, 310.0, 2400.0, 5.80, 7.20, 0.05, 0.02, 0.28, 0.02, 0.18, 36.0),
    ("RJF", "Raymond James Financial", "Financials", "Wealth Management & Capital", 126.00, 208.0, 2600.0, 0.22, 3800.0, 11500.0, 2800.0, 2400.0, 210.0, 2900.0, 8.80, 10.20, 0.07, 0.025, 0.21, 0.02, 0.15, 62.0),
    ("HBAN", "Huntington Bancshares", "Financials", "Regional Banking", 15.80, 1450.0, 2400.0, 0.20, 16000.0, 18200.0, 12500.0, 2100.0, 290.0, 2800.0, 1.25, 1.45, 0.04, 0.02, 0.32, 0.02, 0.20, 5.1),
    ("RF", "Regions Financial Corporation", "Financials", "Commercial & Retail Banking", 23.40, 915.0, 2600.0, 0.21, 14000.0, 17500.0, 11000.0, 2200.0, 320.0, 2900.0, 1.95, 2.25, 0.04, 0.02, 0.34, 0.02, 0.20, 8.0),
    ("KEY", "KeyCorp", "Financials", "Commercial Banking", 17.20, 960.0, 1800.0, 0.20, 19000.0, 15000.0, 12000.0, 1500.0, 250.0, 2200.0, 1.10, 1.55, 0.035, 0.025, 0.28, 0.02, 0.20, 7.2),
    ("CFG", "Citizens Financial Group", "Financials", "Retail Banking", 42.50, 465.0, 2400.0, 0.21, 18000.0, 22500.0, 14500.0, 1900.0, 310.0, 2800.0, 3.10, 3.80, 0.04, 0.025, 0.31, 0.02, 0.20, 17.5),

    # =========================================================================
    # 4. CONSUMER DISCRETIONARY (42 stocks)
    # =========================================================================
    ("AMZN", "Amazon.com Inc.", "Consumer Discretionary", "Broadline Retail & Cloud", 186.50, 10500.0, 48500.0, 0.19, 135000.0, 230000.0, 89000.0, 108000.0, 58000.0, 86000.0, 4.15, 5.80, 0.12, 0.03, 0.085, 0.02, 0.45, 58.0),
    ("TSLA", "Tesla Inc.", "Consumer Discretionary", "Automobiles & EV", 242.10, 3190.0, 8900.0, 0.15, 7500.0, 66000.0, 30500.0, 12500.0, 9800.0, 14200.0, 2.20, 3.10, 0.15, 0.08, 0.09, 0.03, 0.50, 30.5),
    ("HD", "The Home Depot Inc.", "Consumer Discretionary", "Home Improvement Retail", 402.30, 995.0, 21800.0, 0.23, 52000.0, 1500.0, 3800.0, 21200.0, 3200.0, 24800.0, 15.10, 16.20, 0.04, 0.02, 0.145, 0.01, 0.20, 153.0),
    ("MCD", "McDonald's Corporation", "Consumer Discretionary", "Restaurants", 298.40, 720.0, 11600.0, 0.21, 51000.0, -4500.0, 2100.0, 9600.0, 2400.0, 13500.0, 11.50, 12.60, 0.055, 0.02, 0.45, 0.02, 0.25, 35.5),
    ("NKE", "NIKE Inc.", "Consumer Discretionary", "Footwear & Athletic Apparel", 84.20, 1510.0, 6800.0, 0.16, 12100.0, 14400.0, 8200.0, 7400.0, 950.0, 7600.0, 3.70, 3.10, 0.04, 0.03, 0.13, 0.015, 0.18, 34.0),
    ("LOW", "Lowe's Companies Inc.", "Consumer Discretionary", "Home Improvement Retail", 268.00, 568.0, 11800.0, 0.23, 36000.0, -14500.0, 1800.0, 9800.0, 1900.0, 13400.0, 13.20, 12.80, 0.035, 0.02, 0.135, 0.01, 0.22, 148.0),
    ("BKNG", "Booking Holdings Inc.", "Consumer Discretionary", "Online Travel Agency", 4380.00, 34.5, 6200.0, 0.18, 14500.0, -2100.0, 14200.0, 7800.0, 420.0, 7200.0, 132.00, 178.00, 0.09, 0.03, 0.29, 0.02, 0.10, 620.0),
    ("SBUX", "Starbucks Corporation", "Consumer Discretionary", "Specialty Coffee Retail", 97.50, 1130.0, 5400.0, 0.22, 24000.0, -7800.0, 3100.0, 6200.0, 2800.0, 7100.0, 3.60, 3.90, 0.05, 0.025, 0.15, 0.02, 0.35, 32.0),
    ("TJX", "The TJX Companies Inc.", "Consumer Discretionary", "Apparel & Home Fashions", 121.00, 1140.0, 6100.0, 0.24, 7800.0, 7500.0, 4800.0, 6100.0, 1700.0, 7200.0, 4.10, 4.45, 0.065, 0.02, 0.11, 0.01, 0.25, 48.0),
    ("ABNB", "Airbnb Inc.", "Consumer Discretionary", "Vacation Rental Platform", 132.00, 635.0, 2800.0, 0.14, 2100.0, 8400.0, 11000.0, 4100.0, 50.0, 3400.0, 3.80, 4.40, 0.11, 0.03, 0.28, 0.025, 0.08, 16.0),
    ("ORLY", "O'Reilly Automotive", "Consumer Discretionary", "Automotive Aftermarket Parts", 1180.00, 58.0, 3400.0, 0.23, 5600.0, -1800.0, 280.0, 3100.0, 1100.0, 3800.0, 41.50, 44.80, 0.06, 0.015, 0.21, 0.01, 0.28, 275.0),
    ("MAR", "Marriott International", "Consumer Discretionary", "Hotels & Lodging", 262.00, 286.0, 4100.0, 0.23, 13000.0, 850.0, 620.0, 3200.0, 350.0, 4600.0, 9.80, 10.40, 0.06, 0.02, 0.17, 0.015, 0.15, 84.0),
    ("GM", "General Motors Company", "Consumer Discretionary", "Automotive Manufacturing", 48.60, 1140.0, 12500.0, 0.18, 118000.0, 72000.0, 24000.0, 19500.0, 11200.0, 18500.0, 8.80, 9.90, 0.04, 0.03, 0.075, 0.015, 0.55, 152.0),
    ("F", "Ford Motor Company", "Consumer Discretionary", "Automobiles & Commercial", 11.20, 3980.0, 7200.0, 0.18, 142000.0, 44000.0, 26000.0, 15200.0, 8400.0, 13500.0, 1.10, 1.85, 0.035, 0.03, 0.045, 0.015, 0.60, 44.0),
    ("AZO", "AutoZone Inc.", "Consumer Discretionary", "Auto Replacement Parts", 3140.00, 17.2, 3500.0, 0.21, 8800.0, -4800.0, 280.0, 3200.0, 980.0, 3900.0, 151.00, 162.00, 0.06, 0.015, 0.20, 0.01, 0.26, 1020.0),
    ("LULU", "Lululemon Athletica", "Consumer Discretionary", "Athletic Apparel", 284.00, 124.0, 2400.0, 0.28, 0.0, 4100.0, 1500.0, 2200.0, 680.0, 2700.0, 12.80, 14.10, 0.08, 0.03, 0.23, 0.02, 0.28, 78.0),
    ("CMG", "Chipotle Mexican Grill", "Consumer Discretionary", "Fast-Casual Restaurants", 58.40, 1370.0, 1800.0, 0.23, 4200.0, 3400.0, 780.0, 1950.0, 580.0, 2200.0, 1.05, 1.15, 0.13, 0.02, 0.17, 0.015, 0.30, 7.8),
    ("ROST", "Ross Stores Inc.", "Consumer Discretionary", "Off-Price Retail", 152.00, 332.0, 2400.0, 0.24, 4500.0, 4800.0, 4800.0, 2300.0, 850.0, 2900.0, 5.80, 6.20, 0.06, 0.02, 0.12, 0.01, 0.32, 62.0),
    ("HLT", "Hilton Worldwide Holdings", "Consumer Discretionary", "Hospitality Management", 238.00, 250.0, 2800.0, 0.24, 11200.0, -2800.0, 1100.0, 2400.0, 320.0, 3200.0, 4.60, 7.10, 0.07, 0.02, 0.26, 0.02, 0.12, 42.0),
    ("DHI", "D.R. Horton Inc.", "Consumer Discretionary", "Residential Homebuilding", 188.00, 328.0, 6800.0, 0.22, 5900.0, 23500.0, 3100.0, 4200.0, 280.0, 7100.0, 15.20, 15.60, 0.07, 0.04, 0.18, 0.02, 0.15, 112.0),
    ("LEN", "Lennar Corporation", "Consumer Discretionary", "Home Construction", 182.00, 275.0, 5600.0, 0.23, 4800.0, 27000.0, 4200.0, 4100.0, 210.0, 5900.0, 14.50, 15.20, 0.065, 0.04, 0.16, 0.02, 0.15, 128.0),
    ("YUM", "Yum! Brands Inc.", "Consumer Discretionary", "KFC, Taco Bell, Pizza Hut", 136.00, 281.0, 2400.0, 0.20, 12200.0, -7800.0, 820.0, 1800.0, 280.0, 2600.0, 5.40, 5.85, 0.05, 0.015, 0.33, 0.02, 0.15, 25.5),
    ("RCL", "Royal Caribbean Cruises", "Consumer Discretionary", "Cruise Vacation Line", 192.00, 260.0, 3600.0, 0.10, 21000.0, 7800.0, 950.0, 4800.0, 3200.0, 4800.0, 9.80, 11.60, 0.09, 0.04, 0.25, 0.03, 0.65, 58.0),
    ("CCL", "Carnival Corporation", "Consumer Discretionary", "Global Cruise Operator", 18.90, 1310.0, 2600.0, 0.05, 29000.0, 8500.0, 2200.0, 4100.0, 2400.0, 4600.0, 0.85, 1.45, 0.07, 0.04, 0.13, 0.025, 0.55, 18.0),
    ("NVR", "NVR Inc.", "Consumer Discretionary", "Homebuilding & Mortgage", 9240.00, 3.1, 2100.0, 0.23, 1100.0, 4800.0, 2800.0, 1850.0, 45.0, 2150.0, 485.00, 510.00, 0.06, 0.03, 0.20, 0.02, 0.05, 3350.0),
    ("EBAY", "eBay Inc.", "Consumer Discretionary", "E-Commerce Marketplace", 64.20, 498.0, 2400.0, 0.19, 7800.0, 6200.0, 2100.0, 2600.0, 520.0, 2800.0, 4.20, 4.80, 0.035, 0.015, 0.23, 0.015, 0.22, 20.5),
    ("DRI", "Darden Restaurants", "Consumer Discretionary", "Olive Garden & LongHorn", 172.00, 118.0, 1500.0, 0.14, 6200.0, 2400.0, 450.0, 1600.0, 620.0, 1950.0, 8.80, 9.50, 0.055, 0.02, 0.13, 0.01, 0.38, 96.0),
    ("GPC", "Genuine Parts Company", "Consumer Discretionary", "NAPA Auto Parts", 142.00, 139.0, 1800.0, 0.24, 3800.0, 4200.0, 1100.0, 1400.0, 510.0, 2200.0, 8.90, 9.40, 0.04, 0.015, 0.08, 0.01, 0.35, 165.0),
    ("TSCO", "Tractor Supply Company", "Consumer Discretionary", "Rural Lifestyle Retail", 298.00, 107.0, 1500.0, 0.23, 4800.0, 2400.0, 420.0, 1600.0, 720.0, 1900.0, 10.40, 10.80, 0.05, 0.02, 0.10, 0.01, 0.45, 138.0),
    ("ULTA", "Ulta Beauty Inc.", "Consumer Discretionary", "Cosmetics & Salon Retail", 384.00, 48.0, 1700.0, 0.24, 1800.0, 2200.0, 480.0, 1500.0, 480.0, 1980.0, 25.80, 23.50, 0.045, 0.025, 0.15, 0.015, 0.30, 235.0),
    ("PHM", "PulteGroup Inc.", "Consumer Discretionary", "Homebuilder", 138.00, 208.0, 3900.0, 0.23, 3100.0, 12500.0, 1800.0, 2200.0, 120.0, 4100.0, 13.50, 13.90, 0.065, 0.035, 0.22, 0.02, 0.10, 78.0),
    ("DECK", "Deckers Outdoor Corp.", "Consumer Discretionary", "HOKA & UGG Footwear", 158.00, 152.0, 1100.0, 0.21, 0.0, 2100.0, 1400.0, 1150.0, 120.0, 1200.0, 5.20, 5.80, 0.12, 0.03, 0.24, 0.02, 0.12, 28.0),
    ("GRMN", "Garmin Ltd.", "Consumer Discretionary", "GPS Navigation & Fitness", 178.00, 191.0, 1350.0, 0.15, 0.0, 7800.0, 3200.0, 1450.0, 190.0, 1550.0, 6.20, 6.45, 0.08, 0.02, 0.23, 0.02, 0.15, 29.0),
    ("EXPE", "Expedia Group Inc.", "Consumer Discretionary", "Online Travel Services", 152.00, 132.0, 1400.0, 0.22, 6200.0, 1800.0, 5800.0, 2400.0, 780.0, 2800.0, 6.80, 11.20, 0.06, 0.025, 0.11, 0.015, 0.45, 98.0),
    ("BBY", "Best Buy Co. Inc.", "Consumer Discretionary", "Consumer Electronics Retail", 98.00, 214.0, 1600.0, 0.23, 3400.0, 3100.0, 1400.0, 1700.0, 750.0, 2300.0, 5.80, 6.30, 0.02, 0.015, 0.04, 0.008, 0.40, 202.0),
    ("KMX", "CarMax Inc.", "Consumer Discretionary", "Used Vehicle Retail", 78.50, 155.0, 850.0, 0.24, 18500.0, 6100.0, 480.0, 750.0, 350.0, 1100.0, 3.20, 3.65, 0.04, 0.03, 0.035, 0.008, 0.40, 175.0),
    ("BWA", "BorgWarner Inc.", "Consumer Discretionary", "Automotive Propulsion", 34.50, 228.0, 1200.0, 0.22, 4200.0, 7400.0, 1200.0, 1400.0, 850.0, 1800.0, 3.80, 4.10, 0.045, 0.025, 0.09, 0.015, 0.55, 62.0),
    ("TPR", "Tapestry Inc.", "Consumer Discretionary", "Coach & Luxury Accessories", 44.20, 230.0, 1200.0, 0.20, 5800.0, 2400.0, 740.0, 1100.0, 220.0, 1450.0, 3.85, 4.45, 0.04, 0.02, 0.18, 0.02, 0.20, 28.5),
    ("HAS", "Hasbro Inc.", "Consumer Discretionary", "Toys, Games & Entertainment", 71.20, 138.0, 620.0, 0.21, 3800.0, 1400.0, 580.0, 780.0, 140.0, 920.0, 3.40, 4.10, 0.035, 0.03, 0.14, 0.02, 0.20, 32.0),
    ("WHR", "Whirlpool Corporation", "Consumer Discretionary", "Home Appliances", 108.00, 54.5, 1100.0, 0.22, 7800.0, 3200.0, 1200.0, 1150.0, 520.0, 1650.0, 8.50, 11.20, 0.02, 0.02, 0.065, 0.015, 0.45, 340.0),
    ("POOL", "Pool Corporation", "Consumer Discretionary", "Swimming Pool Equipment", 358.00, 38.5, 680.0, 0.24, 1400.0, 1400.0, 85.0, 640.0, 55.0, 780.0, 11.80, 12.50, 0.04, 0.02, 0.12, 0.015, 0.10, 142.0),
    ("RL", "Ralph Lauren Corporation", "Consumer Discretionary", "Premium Apparel & Lifestyle", 192.00, 62.0, 780.0, 0.22, 1600.0, 2800.0, 1800.0, 850.0, 220.0, 1020.0, 9.80, 11.20, 0.05, 0.02, 0.12, 0.015, 0.25, 105.0),

    # =========================================================================
    # 5. COMMUNICATION SERVICES (22 stocks - complete sector)
    # =========================================================================
    ("GOOGL", "Alphabet Inc. (Class A)", "Communication Services", "Interactive Media & Services", 165.20, 12400.0, 98500.0, 0.16, 28000.0, 305000.0, 110000.0, 105000.0, 42000.0, 118000.0, 6.85, 7.90, 0.13, 0.03, 0.30, 0.02, 0.35, 26.5),
    ("GOOG", "Alphabet Inc. (Class C)", "Communication Services", "Search & Cloud Infrastructure", 166.80, 5600.0, 98500.0, 0.16, 28000.0, 305000.0, 110000.0, 105000.0, 42000.0, 118000.0, 6.85, 7.90, 0.13, 0.03, 0.30, 0.02, 0.35, 26.5),
    ("META", "Meta Platforms Inc.", "Communication Services", "Social Media & VR", 585.10, 2540.0, 56000.0, 0.17, 37000.0, 160000.0, 58000.0, 76000.0, 37000.0, 68000.0, 19.80, 24.30, 0.18, 0.05, 0.38, 0.03, 0.40, 56.0),
    ("NFLX", "Netflix Inc.", "Communication Services", "Entertainment Streaming", 708.20, 432.0, 8200.0, 0.15, 14000.0, 22000.0, 7200.0, 7300.0, 400.0, 9500.0, 16.50, 21.00, 0.14, 0.03, 0.23, 0.02, 0.15, 83.0),
    ("DIS", "The Walt Disney Company", "Communication Services", "Entertainment & Theme Parks", 96.40, 1820.0, 11500.0, 0.22, 47000.0, 102000.0, 6200.0, 14000.0, 5100.0, 15800.0, 3.80, 5.20, 0.06, 0.03, 0.13, 0.02, 0.35, 49.0),
    ("CMCSA", "Comcast Corporation", "Communication Services", "Cable, Broadband & Media", 41.50, 3880.0, 24000.0, 0.24, 98000.0, 82000.0, 6500.0, 28000.0, 12000.0, 38000.0, 3.90, 4.40, 0.035, 0.02, 0.20, 0.015, 0.42, 31.0),
    ("T", "AT&T Inc.", "Communication Services", "Telecommunications", 21.80, 7150.0, 24500.0, 0.21, 138000.0, 118000.0, 3800.0, 38000.0, 18000.0, 42000.0, 2.10, 2.25, 0.025, 0.015, 0.20, 0.015, 0.45, 17.0),
    ("VZ", "Verizon Communications", "Communication Services", "Wireless Telecom Services", 44.50, 4210.0, 31000.0, 0.23, 148000.0, 98000.0, 2800.0, 37500.0, 17500.0, 48000.0, 4.60, 4.70, 0.025, 0.015, 0.23, 0.015, 0.46, 31.5),
    ("TMUS", "T-Mobile US Inc.", "Communication Services", "5G Wireless Communications", 204.00, 1170.0, 16800.0, 0.22, 78000.0, 68000.0, 5800.0, 21000.0, 9200.0, 29000.0, 8.40, 10.80, 0.065, 0.025, 0.21, 0.02, 0.40, 67.0),
    ("CHTR", "Charter Communications", "Communication Services", "Broadband Cable Provider", 362.00, 144.0, 12800.0, 0.23, 98000.0, 12500.0, 680.0, 14500.0, 11500.0, 22000.0, 32.00, 36.50, 0.03, 0.02, 0.23, 0.015, 0.80, 380.0),
    ("EA", "Electronic Arts Inc.", "Communication Services", "Interactive Gaming Software", 146.00, 265.0, 1650.0, 0.18, 1900.0, 7800.0, 2800.0, 2200.0, 210.0, 2100.0, 4.20, 7.80, 0.06, 0.02, 0.22, 0.02, 0.10, 28.5),
    ("WBD", "Warner Bros. Discovery", "Communication Services", "Media Networks & Max", 8.20, 2450.0, 3800.0, 0.20, 41000.0, 44000.0, 3100.0, 6800.0, 1100.0, 9500.0, -1.20, 0.20, 0.02, 0.04, 0.10, 0.03, 0.15, 17.0),
    ("TTWO", "Take-Two Interactive", "Communication Services", "GTA & 2K Video Games", 154.00, 175.0, 650.0, 0.17, 3100.0, 6200.0, 980.0, 1200.0, 180.0, 1100.0, -2.10, 6.40, 0.14, 0.06, 0.12, 0.04, 0.15, 31.0),
    ("OMN", "Omnicom Group Inc.", "Communication Services", "Advertising & Marketing", 102.00, 196.0, 2400.0, 0.25, 5800.0, 3800.0, 3400.0, 2100.0, 140.0, 2600.0, 7.40, 7.90, 0.045, 0.02, 0.16, 0.01, 0.08, 75.0),
    ("LYV", "Live Nation Entertainment", "Communication Services", "Concerts & Ticketmaster", 108.00, 230.0, 1100.0, 0.22, 6200.0, 1200.0, 6200.0, 1900.0, 520.0, 2100.0, 2.10, 2.80, 0.09, 0.035, 0.05, 0.015, 0.25, 98.0),
    ("FOXA", "Fox Corporation (Class A)", "Communication Services", "Fox News & Sports Media", 41.20, 468.0, 2100.0, 0.23, 7200.0, 11500.0, 4200.0, 2200.0, 480.0, 2900.0, 3.40, 3.85, 0.04, 0.02, 0.15, 0.015, 0.22, 32.0),
    ("FOX", "Fox Corporation (Class B)", "Communication Services", "Broadcast Television", 38.40, 215.0, 2100.0, 0.23, 7200.0, 11500.0, 4200.0, 2200.0, 480.0, 2900.0, 3.40, 3.85, 0.04, 0.02, 0.15, 0.015, 0.22, 32.0),
    ("NWSA", "News Corporation (Class A)", "Communication Services", "Dow Jones, WSJ, Publishing", 27.80, 570.0, 1100.0, 0.22, 3100.0, 7800.0, 1900.0, 1300.0, 480.0, 1400.0, 0.70, 0.95, 0.04, 0.02, 0.11, 0.015, 0.35, 17.5),
    ("NWS", "News Corporation (Class B)", "Communication Services", "Global Media Information", 28.50, 190.0, 1100.0, 0.22, 3100.0, 7800.0, 1900.0, 1300.0, 480.0, 1400.0, 0.70, 0.95, 0.04, 0.02, 0.11, 0.015, 0.35, 17.5),
    ("IPG", "The Interpublic Group", "Communication Services", "Advertising Agencies", 31.40, 376.0, 1400.0, 0.24, 3400.0, 3800.0, 2100.0, 1200.0, 180.0, 1800.0, 2.80, 2.90, 0.035, 0.015, 0.13, 0.01, 0.15, 29.0),
    ("MTCH", "Match Group Inc.", "Communication Services", "Tinder & Hinge Dating Apps", 37.80, 260.0, 920.0, 0.18, 3800.0, -180.0, 850.0, 980.0, 60.0, 1100.0, 2.45, 3.10, 0.06, 0.025, 0.27, 0.02, 0.08, 13.0),
    ("PARA", "Paramount Global", "Communication Services", "CBS, Studios & Paramount+", 11.40, 690.0, 1800.0, 0.20, 14500.0, 21000.0, 2400.0, 2100.0, 410.0, 2400.0, 0.80, 1.40, 0.03, 0.03, 0.06, 0.02, 0.20, 44.0),

    # =========================================================================
    # 6. INDUSTRIALS (45 stocks)
    # =========================================================================
    ("CAT", "Caterpillar Inc.", "Industrials", "Heavy Construction Machinery", 388.50, 485.0, 13900.0, 0.22, 37000.0, 21000.0, 6500.0, 12800.0, 2100.0, 16200.0, 21.60, 22.80, 0.06, 0.04, 0.21, 0.025, 0.25, 138.0),
    ("GE", "GE Aerospace", "Industrials", "Aerospace & Defense Engines", 182.30, 1090.0, 6800.0, 0.20, 21000.0, 28000.0, 13500.0, 6400.0, 1200.0, 8100.0, 4.85, 5.70, 0.09, 0.03, 0.17, 0.02, 0.22, 34.0),
    ("UNP", "Union Pacific Corporation", "Industrials", "Rail Transportation", 241.60, 610.0, 9800.0, 0.23, 34000.0, 16500.0, 1200.0, 9100.0, 3600.0, 12400.0, 10.90, 11.90, 0.045, 0.02, 0.40, 0.015, 0.35, 40.0),
    ("DE", "Deere & Company", "Industrials", "Agricultural Equipment", 408.20, 275.0, 10200.0, 0.22, 62000.0, 23500.0, 5400.0, 8200.0, 1400.0, 11800.0, 27.50, 25.20, 0.05, 0.06, 0.20, 0.03, 0.25, 190.0),
    ("RTX", "RTX Corporation", "Industrials", "Aerospace & Defense Systems", 122.40, 1330.0, 7800.0, 0.18, 44000.0, 61000.0, 5600.0, 9200.0, 2800.0, 10800.0, 3.40, 6.10, 0.075, 0.025, 0.11, 0.015, 0.35, 56.0),
    ("HON", "Honeywell International", "Industrials", "Diversified Industrial Conglomerate", 212.00, 650.0, 8200.0, 0.20, 21000.0, 16000.0, 8200.0, 6400.0, 1100.0, 9800.0, 8.80, 10.50, 0.055, 0.02, 0.22, 0.015, 0.18, 59.0),
    ("BA", "The Boeing Company", "Industrials", "Commercial Aircraft & Defense", 154.00, 618.0, 2100.0, 0.15, 58000.0, -18000.0, 12500.0, 3800.0, 2100.0, 4800.0, -5.20, 3.80, 0.10, 0.08, 0.06, 0.04, 0.50, 122.0),
    ("LMT", "Lockheed Martin Corp.", "Industrials", "Defense Aeronautics & Missiles", 584.00, 238.0, 8800.0, 0.15, 21000.0, 6800.0, 2800.0, 7400.0, 1700.0, 9800.0, 27.80, 28.50, 0.05, 0.02, 0.13, 0.01, 0.20, 298.0),
    ("ETN", "Eaton Corporation plc", "Industrials", "Electrical Power Management", 348.00, 398.0, 4200.0, 0.16, 11000.0, 19500.0, 2400.0, 4100.0, 850.0, 5100.0, 9.80, 11.20, 0.09, 0.025, 0.18, 0.015, 0.22, 60.0),
    ("UPS", "United Parcel Service", "Industrials", "Package Delivery & Logistics", 132.00, 850.0, 9100.0, 0.22, 28000.0, 17800.0, 5600.0, 10200.0, 4100.0, 12800.0, 7.80, 8.50, 0.04, 0.02, 0.10, 0.015, 0.45, 108.0),
    ("PH", "Parker-Hannifin Corp.", "Industrials", "Motion & Control Technologies", 632.00, 128.0, 3800.0, 0.22, 11500.0, 11800.0, 620.0, 3400.0, 450.0, 4600.0, 21.00, 26.50, 0.06, 0.02, 0.19, 0.015, 0.15, 155.0),
    ("ITW", "Illinois Tool Works", "Industrials", "Engineered Fasteners & Systems", 258.00, 298.0, 4400.0, 0.23, 8200.0, 3800.0, 850.0, 3400.0, 420.0, 4800.0, 10.10, 10.45, 0.04, 0.015, 0.27, 0.015, 0.12, 54.0),
    ("WM", "Waste Management Inc.", "Industrials", "Environmental Waste Services", 214.00, 401.0, 4100.0, 0.24, 16800.0, 7800.0, 480.0, 5200.0, 2900.0, 6200.0, 6.20, 7.10, 0.06, 0.015, 0.19, 0.01, 0.55, 52.0),
    ("GD", "General Dynamics Corp.", "Industrials", "Aerospace & Submarines", 304.00, 273.0, 4600.0, 0.17, 12500.0, 21000.0, 1800.0, 4400.0, 1100.0, 5400.0, 12.80, 14.80, 0.07, 0.02, 0.11, 0.01, 0.25, 155.0),
    ("TDG", "TransDigm Group Inc.", "Industrials", "Proprietary Aerospace Components", 1340.00, 56.0, 3400.0, 0.21, 24000.0, -4200.0, 3400.0, 2100.0, 180.0, 3800.0, 32.00, 38.50, 0.12, 0.03, 0.48, 0.02, 0.08, 120.0),
    ("EMR", "Emerson Electric Co.", "Industrials", "Process Automation & Software", 112.00, 570.0, 3600.0, 0.20, 9500.0, 22000.0, 2800.0, 3200.0, 520.0, 4400.0, 4.40, 5.50, 0.06, 0.02, 0.21, 0.015, 0.18, 30.0),
    ("CSX", "CSX Corporation", "Industrials", "Eastern Rail Freight", 35.80, 1940.0, 5400.0, 0.23, 18500.0, 14200.0, 1100.0, 4800.0, 2400.0, 7100.0, 1.85, 2.05, 0.04, 0.02, 0.37, 0.015, 0.45, 7.6),
    ("NSC", "Norfolk Southern Corp.", "Industrials", "Railroad Carrier", 254.00, 226.0, 3800.0, 0.23, 17200.0, 13800.0, 850.0, 3900.0, 2200.0, 5200.0, 8.40, 13.80, 0.045, 0.02, 0.31, 0.02, 0.50, 54.0),
    ("CTAS", "Cintas Corporation", "Industrials", "Uniforms & Facility Services", 204.00, 405.0, 2100.0, 0.21, 3800.0, 4500.0, 180.0, 1900.0, 380.0, 2400.0, 3.80, 4.25, 0.075, 0.015, 0.21, 0.01, 0.20, 24.0),
    ("PCAR", "PACCAR Inc", "Industrials", "Commercial Heavy Trucks", 104.00, 524.0, 4800.0, 0.22, 14200.0, 17500.0, 8200.0, 4200.0, 680.0, 5400.0, 8.20, 8.10, 0.04, 0.04, 0.14, 0.02, 0.15, 68.0),
    ("JCI", "Johnson Controls International", "Industrials", "Building Technology & HVAC", 74.00, 672.0, 2900.0, 0.15, 12500.0, 16200.0, 1100.0, 2600.0, 780.0, 3800.0, 2.60, 3.65, 0.05, 0.02, 0.11, 0.015, 0.30, 40.0),
    ("FDX", "FedEx Corporation", "Industrials", "Express Courier Logistics", 284.00, 245.0, 5800.0, 0.23, 36000.0, 27000.0, 6800.0, 7400.0, 5200.0, 9200.0, 17.80, 20.20, 0.045, 0.025, 0.065, 0.01, 0.70, 360.0),
    ("CMI", "Cummins Inc.", "Industrials", "Diesel & Natural Gas Engines", 328.00, 137.0, 3800.0, 0.21, 6200.0, 11500.0, 2400.0, 3400.0, 1200.0, 4600.0, 18.50, 21.00, 0.05, 0.03, 0.11, 0.015, 0.32, 250.0),
    ("ROP", "Roper Technologies", "Industrials", "Software & Medical Products", 558.00, 107.0, 1800.0, 0.21, 7400.0, 18500.0, 480.0, 2100.0, 55.0, 2600.0, 13.50, 18.20, 0.08, 0.02, 0.28, 0.015, 0.05, 61.0),
    ("TT", "Trane Technologies plc", "Industrials", "Climate Control Solutions", 384.00, 226.0, 3100.0, 0.18, 5200.0, 7800.0, 1400.0, 2800.0, 350.0, 3600.0, 9.80, 11.10, 0.08, 0.02, 0.16, 0.015, 0.12, 85.0),
    ("CARR", "Carrier Global Corporation", "Industrials", "Heating & Refrigeration", 78.50, 890.0, 2800.0, 0.21, 14500.0, 9200.0, 2800.0, 2400.0, 480.0, 3600.0, 2.80, 3.10, 0.07, 0.02, 0.13, 0.015, 0.20, 25.0),
    ("ODFL", "Old Dominion Freight Line", "Industrials", "Less-Than-Truckload Motor", 204.00, 216.0, 1600.0, 0.24, 80.0, 4200.0, 420.0, 1650.0, 780.0, 1950.0, 5.80, 5.95, 0.06, 0.025, 0.28, 0.02, 0.45, 27.0),
    ("GWW", "W.W. Grainger Inc.", "Industrials", "MRO Equipment Distribution", 1042.00, 49.0, 2400.0, 0.24, 2800.0, 3600.0, 680.0, 2100.0, 420.0, 2700.0, 38.50, 41.50, 0.065, 0.015, 0.15, 0.01, 0.20, 345.0),
    ("FAST", "Fastenal Company", "Industrials", "Industrial Fasteners Supply", 72.50, 572.0, 1500.0, 0.24, 520.0, 3400.0, 280.0, 1300.0, 240.0, 1700.0, 2.05, 2.15, 0.055, 0.015, 0.20, 0.01, 0.18, 12.8),
    ("URI", "United Rentals Inc.", "Industrials", "Heavy Equipment Rental", 824.00, 66.5, 4100.0, 0.23, 12500.0, 7800.0, 380.0, 4800.0, 3200.0, 6800.0, 42.00, 47.00, 0.075, 0.03, 0.28, 0.02, 0.65, 225.0),
    ("CPRT", "Copart Inc.", "Industrials", "Online Vehicle Auctions", 54.20, 965.0, 1600.0, 0.19, 0.0, 7200.0, 2800.0, 1500.0, 480.0, 1850.0, 1.45, 1.65, 0.09, 0.02, 0.38, 0.02, 0.30, 4.4),
    ("DAL", "Delta Air Lines Inc.", "Industrials", "Commercial Passenger Airline", 51.40, 642.0, 5400.0, 0.21, 26000.0, 12000.0, 4200.0, 7200.0, 5100.0, 7800.0, 5.40, 6.50, 0.05, 0.03, 0.095, 0.02, 0.70, 92.0),
    ("LUV", "Southwest Airlines Co.", "Industrials", "Domestic Passenger Carrier", 30.20, 598.0, 850.0, 0.22, 11000.0, 10200.0, 9200.0, 2400.0, 2100.0, 2200.0, 0.85, 1.45, 0.04, 0.03, 0.035, 0.015, 0.85, 45.0),
    ("UAL", "United Airlines Holdings", "Industrials", "Global Air Transportation", 64.00, 328.0, 4200.0, 0.21, 34000.0, 10500.0, 5800.0, 6800.0, 4800.0, 6600.0, 8.20, 10.40, 0.055, 0.035, 0.075, 0.02, 0.70, 165.0),
    ("AAL", "American Airlines Group", "Industrials", "Network Air Travel", 12.80, 655.0, 2100.0, 0.21, 38000.0, -4800.0, 7800.0, 3600.0, 2800.0, 4400.0, 1.20, 1.70, 0.04, 0.03, 0.04, 0.015, 0.78, 81.0),
    ("EFX", "Equifax Inc.", "Industrials", "Workforce Solutions & Credit", 284.00, 123.0, 1100.0, 0.23, 5600.0, 4800.0, 240.0, 1250.0, 580.0, 1700.0, 5.20, 7.80, 0.08, 0.02, 0.20, 0.015, 0.45, 44.0),
    ("EXPD", "Expeditors International", "Industrials", "Air & Ocean Freight Forwarding", 124.00, 144.0, 980.0, 0.24, 0.0, 2400.0, 1600.0, 950.0, 55.0, 1100.0, 5.10, 5.50, 0.045, 0.03, 0.10, 0.02, 0.05, 68.0),
    ("AXON", "Axon Enterprise Inc.", "Industrials", "TASER & Public Safety Tech", 412.00, 76.0, 340.0, 0.18, 720.0, 2100.0, 1100.0, 450.0, 95.0, 460.0, 3.40, 4.80, 0.22, 0.04, 0.18, 0.02, 0.20, 24.0),
    ("HWM", "Howmet Aerospace Inc.", "Industrials", "Aerospace Titanium Components", 104.00, 408.0, 1400.0, 0.20, 3800.0, 4500.0, 620.0, 1200.0, 280.0, 1650.0, 2.25, 2.70, 0.11, 0.025, 0.20, 0.015, 0.22, 17.5),
    ("IR", "Ingersoll Rand Inc.", "Industrials", "Industrial Pumps & Compressors", 98.50, 402.0, 1600.0, 0.21, 4800.0, 9800.0, 1400.0, 1500.0, 140.0, 1950.0, 2.15, 3.35, 0.075, 0.02, 0.22, 0.015, 0.10, 17.0),
    ("DOV", "Dover Corporation", "Industrials", "Pumps, Process & Refrigeration", 188.00, 138.0, 1500.0, 0.21, 3200.0, 5400.0, 450.0, 1350.0, 210.0, 1750.0, 8.20, 9.20, 0.05, 0.02, 0.17, 0.015, 0.15, 62.0),
    ("SWK", "Stanley Black & Decker", "Industrials", "Hand Tools & Industrial", 92.50, 154.0, 1100.0, 0.20, 7800.0, 9500.0, 480.0, 1200.0, 410.0, 1550.0, 3.80, 4.60, 0.035, 0.02, 0.07, 0.015, 0.35, 102.0),
    ("NDSN", "Nordson Corporation", "Industrials", "Precision Dispensing Systems", 262.00, 56.5, 780.0, 0.21, 2400.0, 2600.0, 180.0, 680.0, 95.0, 920.0, 8.80, 9.80, 0.055, 0.02, 0.27, 0.015, 0.14, 48.0),
    ("AOS", "A. O. Smith Corporation", "Industrials", "Water Heating & Filtration", 84.00, 148.0, 680.0, 0.23, 240.0, 1950.0, 410.0, 640.0, 90.0, 760.0, 3.85, 4.10, 0.05, 0.015, 0.17, 0.01, 0.14, 27.0),
    ("GGG", "Graco Inc.", "Industrials", "Fluid Handling Equipment", 86.50, 168.0, 640.0, 0.20, 120.0, 2400.0, 680.0, 620.0, 120.0, 710.0, 2.95, 3.15, 0.055, 0.015, 0.29, 0.015, 0.18, 13.5),

    # =========================================================================
    # 7. CONSUMER STAPLES (35 stocks)
    # =========================================================================
    ("PG", "The Procter & Gamble Company", "Consumer Staples", "Household & Personal Care", 172.50, 2360.0, 19800.0, 0.21, 35000.0, 48500.0, 8500.0, 18600.0, 3300.0, 22600.0, 6.20, 6.95, 0.04, 0.015, 0.24, 0.01, 0.20, 35.5),
    ("COST", "Costco Wholesale Corporation", "Consumer Staples", "Wholesale Club Superstores", 894.20, 443.0, 9200.0, 0.24, 9100.0, 26000.0, 11500.0, 11200.0, 4800.0, 11400.0, 16.55, 17.80, 0.08, 0.02, 0.037, 0.003, 0.35, 570.0),
    ("WMT", "Walmart Inc.", "Consumer Staples", "Global Hypermarkets & Supercenters", 80.40, 8040.0, 28000.0, 0.24, 61000.0, 84000.0, 9800.0, 36000.0, 21000.0, 38000.0, 2.10, 2.45, 0.05, 0.015, 0.042, 0.004, 0.58, 82.0),
    ("KO", "The Coca-Cola Company", "Consumer Staples", "Non-Alcoholic Beverages", 68.40, 4310.0, 13200.0, 0.20, 42000.0, 27500.0, 13500.0, 11800.0, 1900.0, 14700.0, 2.50, 2.85, 0.05, 0.02, 0.29, 0.015, 0.22, 10.7),
    ("PEP", "PepsiCo Inc.", "Consumer Staples", "Snacks & Carbonated Drinks", 171.80, 1375.0, 13800.0, 0.21, 44000.0, 19200.0, 8200.0, 13400.0, 5100.0, 16500.0, 6.65, 8.15, 0.045, 0.02, 0.15, 0.01, 0.32, 67.0),
    ("PM", "Philip Morris International", "Consumer Staples", "Smoke-Free Products & Tobacco", 122.00, 1550.0, 14200.0, 0.21, 48000.0, -8900.0, 3800.0, 11200.0, 1400.0, 15800.0, 5.80, 6.70, 0.07, 0.02, 0.38, 0.02, 0.12, 23.0),
    ("MDLZ", "Mondelez International", "Consumer Staples", "Confectionery & Biscuits", 70.80, 1340.0, 5600.0, 0.22, 21000.0, 28000.0, 2400.0, 4800.0, 1200.0, 6400.0, 3.20, 3.55, 0.045, 0.02, 0.16, 0.015, 0.22, 27.0),
    ("MO", "Altria Group Inc.", "Consumer Staples", "Tobacco Products & Smokeless", 51.50, 1710.0, 11500.0, 0.23, 26000.0, -3200.0, 3200.0, 9200.0, 210.0, 12100.0, 4.80, 5.10, 0.025, 0.015, 0.56, 0.02, 0.03, 12.0),
    ("CL", "Colgate-Palmolive Company", "Consumer Staples", "Oral Care & Pet Nutrition", 101.40, 818.0, 4100.0, 0.22, 9200.0, 1400.0, 1200.0, 3800.0, 750.0, 4600.0, 3.40, 3.65, 0.05, 0.015, 0.21, 0.01, 0.20, 24.5),
    ("TGT", "Target Corporation", "Consumer Staples", "General Merchandise Retail", 154.00, 462.0, 5400.0, 0.22, 19000.0, 13800.0, 3800.0, 8400.0, 4800.0, 8200.0, 9.10, 9.50, 0.03, 0.02, 0.052, 0.008, 0.55, 230.0),
    ("STZ", "Constellation Brands", "Consumer Staples", "Corona & Modelo Premium Beer", 244.00, 181.0, 3400.0, 0.20, 12200.0, 9800.0, 140.0, 2900.0, 1200.0, 3900.0, 10.20, 13.80, 0.055, 0.02, 0.32, 0.02, 0.38, 56.0),
    ("KMB", "Kimberly-Clark Corporation", "Consumer Staples", "Personal Care & Kleenex", 142.50, 337.0, 3100.0, 0.23, 8500.0, 1100.0, 980.0, 3200.0, 850.0, 3600.0, 6.20, 7.10, 0.035, 0.015, 0.15, 0.01, 0.25, 61.0),
    ("ADM", "Archer-Daniels-Midland", "Consumer Staples", "Agricultural Processing & Oilseeds", 58.20, 492.0, 4100.0, 0.19, 11200.0, 24000.0, 1400.0, 3600.0, 1500.0, 4800.0, 5.80, 5.20, 0.03, 0.03, 0.045, 0.01, 0.40, 192.0),
    ("SYY", "Sysco Corporation", "Consumer Staples", "Foodservice Distribution", 76.80, 498.0, 3200.0, 0.23, 11500.0, 1800.0, 850.0, 3100.0, 780.0, 3900.0, 3.80, 4.60, 0.04, 0.015, 0.042, 0.006, 0.25, 156.0),
    ("GIS", "General Mills Inc.", "Consumer Staples", "Cheerios & Packaged Foods", 72.40, 565.0, 3400.0, 0.21, 13200.0, 10500.0, 620.0, 3200.0, 710.0, 3900.0, 4.30, 4.55, 0.03, 0.015, 0.17, 0.01, 0.22, 35.0),
    ("KDP", "Keurig Dr Pepper Inc.", "Consumer Staples", "Single-Serve Coffee & Sodas", 36.80, 1370.0, 3600.0, 0.22, 14500.0, 25500.0, 420.0, 2800.0, 520.0, 4400.0, 1.60, 1.95, 0.045, 0.015, 0.24, 0.015, 0.15, 11.2),
    ("HSY", "The Hershey Company", "Consumer Staples", "Chocolate & Confections", 188.00, 204.0, 2600.0, 0.21, 5400.0, 4500.0, 480.0, 2400.0, 680.0, 2900.0, 8.80, 9.40, 0.04, 0.02, 0.23, 0.015, 0.25, 55.0),
    ("KR", "The Kroger Co.", "Consumer Staples", "Supermarket Chain Operator", 54.00, 720.0, 3800.0, 0.22, 18000.0, 11200.0, 2100.0, 4600.0, 3400.0, 5200.0, 3.10, 4.45, 0.03, 0.015, 0.025, 0.005, 0.65, 205.0),
    ("MKC", "McCormick & Company", "Consumer Staples", "Spices, Seasonings & Flavors", 81.50, 268.0, 1100.0, 0.22, 4800.0, 5200.0, 180.0, 1100.0, 280.0, 1300.0, 2.60, 2.90, 0.04, 0.015, 0.16, 0.01, 0.25, 25.0),
    ("EL", "The Estée Lauder Companies", "Consumer Staples", "Prestige Beauty & Skincare", 88.50, 358.0, 1200.0, 0.24, 7800.0, 5800.0, 2400.0, 1800.0, 950.0, 2100.0, 1.20, 2.80, 0.045, 0.035, 0.08, 0.02, 0.50, 43.0),
    ("CLX", "The Clorox Company", "Consumer Staples", "Bleach & Cleaning Products", 162.00, 123.0, 950.0, 0.22, 2800.0, 450.0, 240.0, 1100.0, 280.0, 1200.0, 4.80, 6.60, 0.035, 0.015, 0.13, 0.01, 0.25, 58.0),
    ("CAG", "Conagra Brands Inc.", "Consumer Staples", "Frozen Foods & Grocery", 31.80, 478.0, 2100.0, 0.23, 9100.0, 8800.0, 95.0, 1800.0, 420.0, 2450.0, 2.20, 2.60, 0.025, 0.015, 0.17, 0.01, 0.20, 25.5),
    ("HRL", "Hormel Foods Corporation", "Consumer Staples", "Spam & Deli Meats", 32.40, 548.0, 1250.0, 0.22, 3400.0, 7800.0, 850.0, 1150.0, 280.0, 1450.0, 1.45, 1.60, 0.03, 0.015, 0.10, 0.01, 0.22, 22.0),
    ("SJM", "The J.M. Smucker Company", "Consumer Staples", "Jif Peanut Butter & Coffee", 118.00, 106.0, 1400.0, 0.23, 8500.0, 7400.0, 120.0, 1500.0, 550.0, 1800.0, 7.40, 9.80, 0.035, 0.02, 0.16, 0.015, 0.35, 78.0),
    ("TSN", "Tyson Foods Inc.", "Consumer Staples", "Poultry & Beef Processing", 61.20, 355.0, 1600.0, 0.22, 9800.0, 17500.0, 1400.0, 2400.0, 1400.0, 2600.0, 2.45, 3.65, 0.035, 0.025, 0.03, 0.015, 0.55, 148.0),
    ("CHD", "Church & Dwight Co.", "Consumer Staples", "Arm & Hammer Products", 102.00, 244.0, 1150.0, 0.23, 2400.0, 4100.0, 380.0, 1100.0, 220.0, 1300.0, 3.10, 3.40, 0.05, 0.015, 0.19, 0.01, 0.20, 24.5),
    ("BG", "Bunge Global SA", "Consumer Staples", "Agribusiness & Grain Origination", 98.00, 142.0, 2400.0, 0.18, 5400.0, 11500.0, 2400.0, 2800.0, 1100.0, 3100.0, 12.50, 9.50, 0.04, 0.03, 0.04, 0.01, 0.35, 420.0),
    ("CPB", "Campbell Soup Company", "Consumer Staples", "Soup, Snacks & Meals", 48.50, 301.0, 1300.0, 0.23, 7400.0, 3800.0, 180.0, 1200.0, 450.0, 1550.0, 2.80, 3.15, 0.03, 0.015, 0.13, 0.01, 0.35, 32.0),
    ("TAP", "Molson Coors Beverage Co.", "Consumer Staples", "Coors & Miller Beer", 56.40, 208.0, 1600.0, 0.21, 6200.0, 13800.0, 480.0, 1900.0, 720.0, 2100.0, 4.40, 5.60, 0.03, 0.015, 0.13, 0.015, 0.35, 56.0),
    ("DLTR", "Dollar Tree Inc.", "Consumer Staples", "Discount Variety Stores", 74.00, 215.0, 1800.0, 0.24, 7400.0, 5800.0, 720.0, 2400.0, 1700.0, 2700.0, 4.80, 5.40, 0.04, 0.02, 0.06, 0.01, 0.70, 142.0),
    ("DG", "Dollar General Corp.", "Consumer Staples", "Rural Value Retail", 84.50, 220.0, 2200.0, 0.23, 16800.0, 6800.0, 450.0, 2600.0, 1400.0, 3200.0, 6.20, 5.80, 0.04, 0.02, 0.055, 0.01, 0.55, 178.0),
    ("KVUE", "Kenvue Inc.", "Consumer Staples", "Tylenol, Band-Aid & Neutrogena", 22.80, 1910.0, 3100.0, 0.21, 8400.0, 11800.0, 1100.0, 2800.0, 620.0, 3800.0, 0.85, 1.15, 0.035, 0.015, 0.20, 0.01, 0.20, 8.1),
    ("LW", "Lamb Weston Holdings", "Consumer Staples", "Frozen Potato French Fries", 64.00, 144.0, 1100.0, 0.22, 3800.0, 1800.0, 110.0, 950.0, 920.0, 1300.0, 3.80, 4.30, 0.05, 0.025, 0.16, 0.02, 0.80, 45.0),
    ("K", "Kellanova (formerly Kellogg)", "Consumer Staples", "Pringles & MorningStar Farms", 81.00, 344.0, 1800.0, 0.22, 6100.0, 4100.0, 380.0, 1700.0, 640.0, 2200.0, 2.80, 3.60, 0.04, 0.015, 0.14, 0.01, 0.35, 37.0),
    ("HLF", "Herbalife Ltd.", "Consumer Staples", "Nutrition & Weight Management", 8.40, 102.0, 410.0, 0.24, 2400.0, -850.0, 420.0, 340.0, 140.0, 520.0, 1.45, 1.80, 0.02, 0.02, 0.08, 0.015, 0.35, 48.0),

    # =========================================================================
    # 8. ENERGY (24 stocks - complete sector)
    # =========================================================================
    ("XOM", "Exxon Mobil Corporation", "Energy", "Integrated Oil & Gas", 116.80, 4450.0, 51000.0, 0.28, 41500.0, 215000.0, 31000.0, 55000.0, 23000.0, 69000.0, 8.90, 8.40, 0.03, 0.12, 0.15, 0.05, 0.45, 78.0),
    ("CVX", "Chevron Corporation", "Energy", "Integrated Oil & Gas", 151.20, 1840.0, 26800.0, 0.26, 22000.0, 162000.0, 6800.0, 32000.0, 15500.0, 38500.0, 10.40, 11.50, 0.035, 0.11, 0.14, 0.045, 0.48, 109.0),
    ("COP", "ConocoPhillips", "Energy", "Exploration & Production", 108.40, 1170.0, 15800.0, 0.25, 19500.0, 48000.0, 6500.0, 19200.0, 11500.0, 22000.0, 7.80, 8.60, 0.04, 0.10, 0.27, 0.05, 0.60, 49.0),
    ("EOG", "EOG Resources Inc.", "Energy", "Shale Exploration & Production", 126.50, 575.0, 9400.0, 0.22, 4200.0, 28000.0, 5800.0, 10800.0, 6100.0, 11800.0, 12.10, 11.80, 0.045, 0.09, 0.38, 0.04, 0.55, 42.0),
    ("SLB", "SLB (Schlumberger Limited)", "Energy", "Oilfield Equipment & Services", 43.80, 1420.0, 5600.0, 0.20, 11800.0, 20500.0, 3800.0, 6100.0, 2500.0, 7800.0, 3.10, 3.75, 0.08, 0.08, 0.16, 0.03, 0.40, 24.0),
    ("MPC", "Marathon Petroleum Corp.", "Energy", "Refining & Marketing", 168.00, 345.0, 11200.0, 0.23, 27000.0, 24000.0, 8200.0, 13500.0, 3100.0, 14200.0, 16.50, 14.80, 0.025, 0.12, 0.07, 0.03, 0.25, 410.0),
    ("PSX", "Phillips 66", "Energy", "Petroleum Refining & Midstream", 136.00, 420.0, 7800.0, 0.22, 19500.0, 31000.0, 3400.0, 8800.0, 2600.0, 10200.0, 12.80, 11.20, 0.03, 0.11, 0.05, 0.02, 0.30, 355.0),
    ("VLO", "Valero Energy Corporation", "Energy", "Independent Oil Refining", 138.50, 315.0, 6800.0, 0.22, 11200.0, 25000.0, 4800.0, 8200.0, 2100.0, 8800.0, 15.20, 11.80, 0.025, 0.12, 0.05, 0.02, 0.25, 440.0),
    ("WMB", "The Williams Companies", "Energy", "Natural Gas Pipelines", 48.20, 1220.0, 3800.0, 0.24, 25000.0, 14500.0, 180.0, 4800.0, 2400.0, 5600.0, 2.45, 2.15, 0.05, 0.02, 0.35, 0.02, 0.50, 8.8),
    ("KMI", "Kinder Morgan Inc.", "Energy", "Energy Infrastructure & Midstream", 22.40, 2230.0, 4100.0, 0.23, 32000.0, 31000.0, 380.0, 5600.0, 2800.0, 6800.0, 1.15, 1.25, 0.045, 0.02, 0.26, 0.02, 0.50, 6.8),
    ("OXY", "Occidental Petroleum Corp.", "Energy", "Oil, Gas & Chemicals", 52.80, 940.0, 6800.0, 0.24, 28000.0, 24000.0, 1800.0, 11800.0, 6400.0, 12400.0, 3.80, 3.90, 0.04, 0.10, 0.23, 0.04, 0.55, 30.5),
    ("HES", "Hess Corporation", "Energy", "Offshore Guyana Exploration", 142.00, 308.0, 3600.0, 0.23, 8900.0, 9800.0, 1800.0, 5200.0, 4100.0, 5400.0, 7.80, 11.20, 0.08, 0.10, 0.32, 0.04, 0.75, 38.0),
    ("BKR", "Baker Hughes Company", "Energy", "Turbomachinery & Energy Tech", 36.80, 985.0, 3100.0, 0.21, 6200.0, 16800.0, 2800.0, 3400.0, 1400.0, 4200.0, 1.95, 2.65, 0.065, 0.06, 0.12, 0.02, 0.40, 27.5),
    ("FANG", "Diamondback Energy Inc.", "Energy", "Permian Basin E&P", 188.00, 290.0, 4400.0, 0.21, 6800.0, 18500.0, 850.0, 4100.0, 2600.0, 5400.0, 18.50, 19.80, 0.06, 0.09, 0.52, 0.04, 0.60, 29.0),
    ("ONEOK", "ONEOK Inc.", "Energy", "NGL Systems & Midstream", 92.40, 584.0, 3800.0, 0.22, 28000.0, 19800.0, 420.0, 4200.0, 2100.0, 5400.0, 4.40, 5.80, 0.06, 0.025, 0.18, 0.02, 0.50, 36.0),
    ("HAL", "Halliburton Company", "Energy", "Hydraulic Fracturing & Drilling", 31.20, 885.0, 3800.0, 0.22, 7800.0, 9800.0, 2200.0, 3600.0, 1400.0, 4600.0, 3.05, 3.55, 0.05, 0.07, 0.16, 0.02, 0.38, 26.0),
    ("DVN", "Devon Energy Corporation", "Energy", "Delaware Basin Oil & Gas", 41.50, 625.0, 4100.0, 0.22, 6200.0, 12500.0, 850.0, 4200.0, 3400.0, 5100.0, 5.20, 5.30, 0.045, 0.09, 0.28, 0.04, 0.78, 24.5),
    ("TRGP", "Targa Resources Corp.", "Energy", "NGL Gathering & Fractionation", 148.00, 224.0, 2400.0, 0.22, 13500.0, 4200.0, 280.0, 2900.0, 2200.0, 3800.0, 4.80, 6.40, 0.075, 0.03, 0.15, 0.02, 0.75, 75.0),
    ("CTRA", "Coterra Energy Inc.", "Energy", "Marcellus & Permian Gas", 25.40, 742.0, 2100.0, 0.21, 2100.0, 13800.0, 980.0, 3100.0, 1900.0, 3200.0, 2.10, 2.45, 0.05, 0.08, 0.38, 0.04, 0.60, 7.8),
    ("EQT", "EQT Corporation", "Energy", "Natural Gas Producer", 38.60, 595.0, 1800.0, 0.21, 12800.0, 14200.0, 120.0, 2400.0, 2100.0, 2800.0, 1.80, 2.80, 0.06, 0.09, 0.35, 0.05, 0.85, 8.5),
    ("MRO", "Marathon Oil Corporation", "Energy", "Resource Basins Oil", 28.50, 560.0, 2400.0, 0.22, 5400.0, 11800.0, 350.0, 3600.0, 2100.0, 3800.0, 2.50, 2.80, 0.04, 0.08, 0.36, 0.04, 0.58, 12.0),
    ("APA", "APA Corporation", "Energy", "Global Oil & Gas Reserves", 26.20, 370.0, 2600.0, 0.28, 6400.0, 4800.0, 210.0, 2800.0, 1900.0, 3400.0, 2.80, 3.90, 0.035, 0.09, 0.30, 0.04, 0.68, 25.0),
    ("CHK", "Expand Energy (Chesapeake)", "Energy", "Natural Gas Basin Asset", 82.00, 134.0, 1100.0, 0.21, 3800.0, 11500.0, 780.0, 1800.0, 1400.0, 2100.0, 4.20, 5.80, 0.05, 0.09, 0.28, 0.04, 0.75, 42.0),
    ("OII", "Oceaneering International", "Energy", "Subsea Robotics & Engineering", 24.50, 101.0, 210.0, 0.24, 750.0, 680.0, 480.0, 340.0, 120.0, 360.0, 1.30, 1.75, 0.08, 0.05, 0.09, 0.02, 0.35, 24.0),

    # =========================================================================
    # 9. UTILITIES (30 stocks - complete sector)
    # =========================================================================
    ("NEE", "NextEra Energy Inc.", "Utilities", "Electric Utilities & Clean Power", 82.50, 2060.0, 9800.0, 0.12, 78000.0, 44000.0, 2900.0, 11400.0, 21000.0, 15200.0, 3.40, 3.65, 0.075, 0.03, 0.35, 0.02, 0.75, 13.5),
    ("SO", "The Southern Company", "Utilities", "Regulated Electric Utilities", 89.10, 1095.0, 6800.0, 0.15, 61000.0, 32500.0, 1800.0, 7900.0, 8600.0, 10200.0, 3.85, 4.10, 0.04, 0.015, 0.26, 0.015, 0.65, 24.0),
    ("DUK", "Duke Energy Corporation", "Utilities", "Electric Power Distribution", 112.40, 772.0, 7400.0, 0.14, 81000.0, 50000.0, 800.0, 9800.0, 11800.0, 12800.0, 5.40, 6.10, 0.04, 0.015, 0.25, 0.015, 0.70, 38.0),
    ("CEG", "Constellation Energy Corp.", "Utilities", "Clean Nuclear Power Generation", 268.00, 314.0, 3200.0, 0.16, 8200.0, 13800.0, 3400.0, 4100.0, 2100.0, 4200.0, 6.80, 8.40, 0.12, 0.04, 0.14, 0.025, 0.50, 75.0),
    ("SRE", "Sempra", "Utilities", "Energy Infrastructure & Gas", 88.00, 635.0, 4200.0, 0.15, 34000.0, 31000.0, 820.0, 4900.0, 5600.0, 6200.0, 4.80, 5.05, 0.05, 0.02, 0.25, 0.015, 0.65, 26.0),
    ("AEP", "American Electric Power", "Utilities", "Electric Transmission & Grid", 102.50, 530.0, 4600.0, 0.14, 44000.0, 26000.0, 640.0, 6400.0, 8200.0, 7600.0, 5.20, 5.65, 0.045, 0.015, 0.23, 0.015, 0.70, 38.0),
    ("VST", "Vistra Corp.", "Utilities", "Retail Electricity & Gas Gen", 122.00, 345.0, 2800.0, 0.18, 14500.0, 6200.0, 1800.0, 3600.0, 1800.0, 4200.0, 3.80, 6.50, 0.14, 0.05, 0.18, 0.03, 0.50, 42.0),
    ("D", "Dominion Energy Inc.", "Utilities", "Regulated Electric Utility", 58.40, 842.0, 4100.0, 0.15, 41000.0, 28000.0, 520.0, 5800.0, 7100.0, 6800.0, 2.80, 3.40, 0.04, 0.015, 0.28, 0.015, 0.70, 17.5),
    ("PEG", "Public Service Enterprise", "Utilities", "Nuclear & Electric Transmission", 88.20, 500.0, 3100.0, 0.15, 21000.0, 18500.0, 680.0, 3900.0, 3800.0, 4600.0, 4.20, 4.10, 0.045, 0.015, 0.28, 0.015, 0.60, 22.0),
    ("EXC", "Exelon Corporation", "Utilities", "Regulated Transmission & Dist", 39.80, 1005.0, 4200.0, 0.14, 42000.0, 28000.0, 720.0, 6200.0, 7400.0, 7200.0, 2.35, 2.50, 0.04, 0.015, 0.19, 0.015, 0.70, 22.0),
    ("ED", "Consolidated Edison Inc.", "Utilities", "New York Metropolitan Utility", 102.00, 346.0, 3400.0, 0.16, 26000.0, 22000.0, 850.0, 4100.0, 4800.0, 4800.0, 5.10, 5.40, 0.035, 0.015, 0.22, 0.015, 0.65, 44.0),
    ("XEL", "Xcel Energy Inc.", "Utilities", "Regulated Wind & Solar Grid", 65.40, 560.0, 3200.0, 0.13, 27000.0, 18500.0, 340.0, 4200.0, 5800.0, 4800.0, 3.40, 3.65, 0.045, 0.015, 0.22, 0.015, 0.75, 25.5),
    ("PCG", "PG&E Corporation", "Utilities", "Northern California Utility", 19.80, 2150.0, 4100.0, 0.14, 58000.0, 26000.0, 450.0, 5800.0, 9800.0, 7200.0, 1.25, 1.45, 0.05, 0.02, 0.17, 0.015, 0.85, 11.2),
    ("WEC", "WEC Energy Group Inc.", "Utilities", "Midwest Gas & Electric", 92.50, 318.0, 2200.0, 0.14, 18500.0, 12500.0, 140.0, 2900.0, 3200.0, 3400.0, 4.60, 4.95, 0.04, 0.015, 0.24, 0.015, 0.65, 28.5),
    ("ETR", "Entergy Corporation", "Utilities", "Gulf Coast Electric Utility", 138.00, 215.0, 2800.0, 0.13, 26000.0, 14000.0, 380.0, 3800.0, 4800.0, 4600.0, 7.20, 7.50, 0.045, 0.015, 0.23, 0.015, 0.70, 56.0),
    ("AWK", "American Water Works Co.", "Utilities", "Regulated Water & Wastewater", 136.00, 195.0, 1600.0, 0.15, 12800.0, 9500.0, 210.0, 1900.0, 3100.0, 2400.0, 4.90, 5.35, 0.055, 0.015, 0.36, 0.015, 0.80, 22.0),
    ("DTE", "DTE Energy Company", "Utilities", "Michigan Electric & Gas", 124.50, 208.0, 2100.0, 0.14, 21000.0, 11500.0, 180.0, 2900.0, 4100.0, 3500.0, 6.20, 6.80, 0.04, 0.015, 0.16, 0.015, 0.70, 61.0),
    ("ES", "Eversource Energy", "Utilities", "New England Electric Grid", 64.20, 355.0, 2400.0, 0.15, 25000.0, 14500.0, 120.0, 3100.0, 4600.0, 3800.0, 3.40, 4.60, 0.04, 0.015, 0.20, 0.015, 0.75, 33.0),
    ("PPL", "PPL Corporation", "Utilities", "Pennsylvania & Kentucky Utility", 32.40, 738.0, 1800.0, 0.14, 16500.0, 14200.0, 420.0, 2400.0, 3200.0, 2900.0, 1.55, 1.75, 0.045, 0.015, 0.21, 0.015, 0.65, 11.5),
    ("FE", "FirstEnergy Corp.", "Utilities", "Electric Distribution Systems", 44.80, 574.0, 2400.0, 0.14, 24000.0, 11500.0, 240.0, 3100.0, 4400.0, 3800.0, 2.40, 2.70, 0.04, 0.015, 0.18, 0.015, 0.70, 22.0),
    ("AEE", "Ameren Corporation", "Utilities", "Missouri & Illinois Grid", 88.00, 266.0, 1900.0, 0.14, 16800.0, 11800.0, 110.0, 2600.0, 3800.0, 3200.0, 4.40, 4.80, 0.045, 0.015, 0.25, 0.015, 0.75, 28.0),
    ("CMS", "CMS Energy Corporation", "Utilities", "Consumers Energy Michigan", 68.40, 298.0, 1600.0, 0.14, 15500.0, 7800.0, 180.0, 2100.0, 3200.0, 2600.0, 3.10, 3.40, 0.045, 0.015, 0.21, 0.015, 0.70, 25.0),
    ("CNP", "CenterPoint Energy Inc.", "Utilities", "Houston Electric & Gas Grid", 28.50, 638.0, 1800.0, 0.15, 18500.0, 10200.0, 240.0, 2400.0, 3600.0, 2800.0, 1.45, 1.65, 0.04, 0.015, 0.20, 0.015, 0.75, 13.8),
    ("ATO", "Atmos Energy Corporation", "Utilities", "Regulated Natural Gas Utility", 138.00, 155.0, 1300.0, 0.15, 8400.0, 9800.0, 120.0, 1600.0, 2900.0, 1800.0, 6.20, 6.80, 0.05, 0.015, 0.31, 0.015, 0.85, 27.0),
    ("NI", "NiSource Inc.", "Utilities", "Gas & Electric Transmission", 34.20, 465.0, 1200.0, 0.14, 12500.0, 7400.0, 95.0, 1700.0, 3200.0, 2100.0, 1.60, 1.75, 0.045, 0.015, 0.22, 0.015, 0.80, 12.0),
    ("LNT", "Alliant Energy Corporation", "Utilities", "Iowa & Wisconsin Clean Energy", 58.60, 258.0, 1100.0, 0.14, 9800.0, 6800.0, 80.0, 1400.0, 2100.0, 1800.0, 2.90, 3.15, 0.045, 0.015, 0.27, 0.015, 0.75, 15.5),
    ("EVRG", "Evergy Inc.", "Utilities", "Kansas & Missouri Power", 59.80, 230.0, 1200.0, 0.14, 12200.0, 9800.0, 90.0, 1600.0, 2400.0, 2200.0, 3.40, 3.85, 0.04, 0.015, 0.22, 0.015, 0.70, 23.5),
    ("AES", "The AES Corporation", "Utilities", "Global Renewable & Storage", 19.40, 715.0, 2100.0, 0.16, 26000.0, 3800.0, 1400.0, 3200.0, 3100.0, 3800.0, 1.40, 1.90, 0.055, 0.025, 0.16, 0.02, 0.65, 17.5),
    ("PNW", "Pinnacle West Capital", "Utilities", "Arizona Public Service Grid", 88.40, 115.0, 850.0, 0.14, 8800.0, 6400.0, 60.0, 1200.0, 1900.0, 1400.0, 4.40, 4.85, 0.045, 0.015, 0.18, 0.015, 0.75, 38.0),
    ("NRG", "NRG Energy Inc.", "Utilities", "Competitive Energy & Smart Home", 92.00, 206.0, 2400.0, 0.18, 11500.0, 2800.0, 850.0, 2600.0, 680.0, 3400.0, 4.80, 7.20, 0.065, 0.025, 0.08, 0.015, 0.20, 138.0),

    # =========================================================================
    # 10. REAL ESTATE (31 stocks)
    # =========================================================================
    ("PLD", "Prologis Inc.", "Real Estate", "Industrial Logistics REIT", 118.60, 925.0, 4200.0, 0.04, 31000.0, 58000.0, 1400.0, 5200.0, 1200.0, 6100.0, 3.45, 5.50, 0.08, 0.03, 0.52, 0.02, 0.35, 8.7),
    ("AMT", "American Tower Corporation", "Real Estate", "Telecom Tower REIT", 218.70, 468.0, 4600.0, 0.05, 41000.0, 13500.0, 2100.0, 4800.0, 1500.0, 7200.0, 4.10, 10.20, 0.065, 0.025, 0.42, 0.02, 0.30, 24.0),
    ("EQIX", "Equinix Inc.", "Real Estate", "Data Center REIT", 862.50, 95.0, 2100.0, 0.06, 18500.0, 14200.0, 2800.0, 3400.0, 2800.0, 4100.0, 11.20, 35.80, 0.11, 0.03, 0.25, 0.02, 0.45, 88.0),
    ("WELL", "Welltower Inc.", "Real Estate", "Senior Housing & Healthcare REIT", 128.00, 605.0, 1800.0, 0.04, 17500.0, 34000.0, 3800.0, 2600.0, 1600.0, 3200.0, 2.10, 4.25, 0.08, 0.025, 0.26, 0.02, 0.45, 11.8),
    ("SPG", "Simon Property Group", "Real Estate", "Regional Malls & Outlets", 168.00, 326.0, 3200.0, 0.04, 26000.0, 2400.0, 1100.0, 4100.0, 850.0, 4500.0, 7.80, 12.80, 0.05, 0.02, 0.58, 0.02, 0.20, 17.5),
    ("DLR", "Digital Realty Trust", "Real Estate", "Cloud Colocation Data Centers", 158.00, 315.0, 1600.0, 0.05, 19000.0, 21000.0, 1800.0, 2400.0, 2800.0, 3100.0, 3.20, 6.70, 0.085, 0.025, 0.30, 0.02, 0.60, 17.5),
    ("PSA", "Public Storage", "Real Estate", "Self-Storage Facilities", 342.00, 176.0, 2400.0, 0.04, 9800.0, 18000.0, 450.0, 3100.0, 850.0, 3600.0, 11.80, 17.20, 0.06, 0.02, 0.54, 0.02, 0.25, 26.0),
    ("O", "Realty Income Corporation", "Real Estate", "Single-Tenant Triple Net Retail", 62.40, 870.0, 2400.0, 0.03, 24000.0, 38000.0, 420.0, 3800.0, 2400.0, 4600.0, 1.40, 4.20, 0.06, 0.02, 0.52, 0.02, 0.55, 5.8),
    ("CCI", "Crown Castle Inc.", "Real Estate", "Cell Towers & Fiber Solutions", 112.00, 435.0, 2200.0, 0.04, 23000.0, 6400.0, 210.0, 3200.0, 1100.0, 4100.0, 3.40, 6.80, 0.04, 0.02, 0.32, 0.02, 0.30, 16.5),
    ("CBRE", "CBRE Group Inc.", "Real Estate", "Real Estate Services & Advisory", 124.00, 305.0, 1800.0, 0.22, 6400.0, 11500.0, 1400.0, 1600.0, 280.0, 2400.0, 3.60, 4.80, 0.075, 0.025, 0.055, 0.01, 0.15, 110.0),
    ("EXR", "Extra Space Storage Inc.", "Real Estate", "Self-Storage REIT", 168.00, 212.0, 1400.0, 0.04, 12500.0, 16800.0, 180.0, 2100.0, 680.0, 2600.0, 4.80, 8.10, 0.065, 0.02, 0.48, 0.02, 0.28, 14.5),
    ("AVB", "AvalonBay Communities", "Real Estate", "Multifamily Residential REIT", 228.00, 142.0, 1200.0, 0.04, 8600.0, 12500.0, 480.0, 1800.0, 950.0, 2100.0, 6.80, 11.20, 0.055, 0.02, 0.42, 0.02, 0.45, 19.5),
    ("EQR", "Equity Residential", "Real Estate", "Urban Apartment Communities", 74.80, 388.0, 1100.0, 0.04, 9400.0, 11800.0, 140.0, 1650.0, 820.0, 2100.0, 2.80, 3.90, 0.05, 0.015, 0.38, 0.015, 0.45, 8.1),
    ("VICI", "VICI Properties Inc.", "Real Estate", "Gaming, Hospitality & Strip", 32.40, 1045.0, 2800.0, 0.02, 17500.0, 26000.0, 480.0, 3100.0, 620.0, 3600.0, 2.45, 2.65, 0.065, 0.02, 0.78, 0.02, 0.15, 3.8),
    ("INVH", "Invitation Homes Inc.", "Real Estate", "Single-Family Rental Homes", 34.80, 612.0, 780.0, 0.04, 9100.0, 11500.0, 420.0, 1200.0, 680.0, 1700.0, 0.95, 1.85, 0.06, 0.02, 0.32, 0.015, 0.45, 4.1),
    ("MAA", "Mid-America Apartment", "Real Estate", "Sunbelt Multifamily REIT", 162.00, 118.0, 740.0, 0.04, 5200.0, 6400.0, 95.0, 1100.0, 620.0, 1400.0, 4.60, 8.80, 0.05, 0.02, 0.36, 0.015, 0.45, 18.0),
    ("UDR", "UDR Inc.", "Real Estate", "Apartment Homes Operator", 43.50, 332.0, 480.0, 0.04, 5800.0, 4800.0, 80.0, 920.0, 420.0, 1100.0, 1.20, 2.45, 0.05, 0.015, 0.31, 0.015, 0.40, 5.1),
    ("ESS", "Essex Property Trust", "Real Estate", "West Coast Multifamily REIT", 298.00, 64.0, 680.0, 0.04, 6200.0, 6800.0, 90.0, 1150.0, 550.0, 1300.0, 8.40, 15.60, 0.05, 0.02, 0.41, 0.02, 0.42, 27.5),
    ("CPT", "Camden Property Trust", "Real Estate", "Multifamily Communities", 122.00, 107.0, 480.0, 0.04, 3800.0, 5200.0, 65.0, 840.0, 410.0, 980.0, 3.80, 6.70, 0.055, 0.02, 0.32, 0.015, 0.40, 14.5),
    ("ARE", "Alexandria Real Estate", "Real Estate", "Life Science Collaborative", 118.00, 174.0, 950.0, 0.04, 12500.0, 18500.0, 620.0, 1800.0, 1900.0, 2200.0, 2.10, 9.40, 0.065, 0.025, 0.32, 0.02, 0.85, 18.0),
    ("KIM", "Kimco Realty Corporation", "Real Estate", "Grocery-Anchored Shopping", 23.80, 672.0, 780.0, 0.04, 8200.0, 10200.0, 420.0, 1200.0, 520.0, 1500.0, 1.25, 1.65, 0.05, 0.015, 0.41, 0.02, 0.38, 2.8),
    ("REG", "Regency Centers Corp.", "Real Estate", "Suburban Shopping Centers", 72.50, 182.0, 580.0, 0.04, 4800.0, 7200.0, 210.0, 890.0, 380.0, 1100.0, 2.45, 4.25, 0.055, 0.015, 0.42, 0.02, 0.35, 7.8),
    ("HST", "Host Hotels & Resorts", "Real Estate", "Luxury Lodging REIT", 18.20, 708.0, 920.0, 0.04, 4800.0, 7100.0, 850.0, 1400.0, 680.0, 1700.0, 1.15, 1.95, 0.05, 0.03, 0.17, 0.02, 0.45, 7.6),
    ("BXP", "BXP Inc. (Boston Properties)", "Real Estate", "Premier Modern Workplaces", 81.00, 158.0, 850.0, 0.04, 15500.0, 5800.0, 1400.0, 1200.0, 1400.0, 1950.0, 2.80, 7.10, 0.045, 0.025, 0.28, 0.02, 0.85, 21.0),
    ("FRT", "Federal Realty Investment", "Real Estate", "Open-Air Retail Properties", 112.00, 84.0, 420.0, 0.04, 4600.0, 3100.0, 140.0, 580.0, 320.0, 760.0, 3.40, 6.80, 0.05, 0.015, 0.38, 0.015, 0.45, 13.8),
    ("NNN", "NNN REIT Inc.", "Real Estate", "Single-Tenant Retail", 46.50, 185.0, 620.0, 0.03, 4400.0, 4600.0, 95.0, 740.0, 380.0, 820.0, 2.15, 3.35, 0.055, 0.015, 0.72, 0.015, 0.45, 4.6),
    ("WY", "Weyerhaeuser Company", "Real Estate", "Timberlands & Wood Products", 32.40, 728.0, 1200.0, 0.15, 5200.0, 10200.0, 1100.0, 1600.0, 420.0, 1800.0, 1.25, 1.45, 0.04, 0.04, 0.16, 0.03, 0.25, 10.8),
    ("SBAC", "SBA Communications Corp.", "Real Estate", "Wireless Tower Infrastructure", 238.00, 107.0, 1100.0, 0.04, 12800.0, -4800.0, 310.0, 1500.0, 420.0, 1850.0, 5.20, 13.20, 0.055, 0.02, 0.41, 0.02, 0.25, 25.5),
    ("DOC", "Healthpeak Properties", "Real Estate", "Healthcare Discovery Labs", 21.80, 710.0, 740.0, 0.04, 9100.0, 14200.0, 340.0, 1100.0, 850.0, 1600.0, 0.65, 1.80, 0.055, 0.02, 0.31, 0.02, 0.65, 3.2),
    ("CUBE", "CubeSmart", "Real Estate", "Self-Storage Operating REIT", 47.80, 226.0, 480.0, 0.04, 3400.0, 2800.0, 55.0, 680.0, 240.0, 760.0, 1.85, 2.65, 0.055, 0.015, 0.45, 0.015, 0.32, 4.8),
    ("PEAK", "Broadstone Net Lease", "Real Estate", "Single-Tenant Commercial", 17.50, 198.0, 310.0, 0.04, 2100.0, 2600.0, 85.0, 360.0, 120.0, 420.0, 0.85, 1.45, 0.055, 0.015, 0.68, 0.02, 0.30, 2.2),

    # =========================================================================
    # 11. MATERIALS (28 stocks)
    # =========================================================================
    ("LIN", "Linde plc", "Materials", "Industrial Gases & Engineering", 458.20, 480.0, 9400.0, 0.22, 19500.0, 39000.0, 4800.0, 9800.0, 3900.0, 12800.0, 13.10, 15.60, 0.065, 0.02, 0.28, 0.015, 0.35, 70.0),
    ("SHW", "The Sherwin-Williams Company", "Materials", "Paints & Coatings", 372.40, 252.0, 3700.0, 0.21, 12200.0, 4100.0, 600.0, 3500.0, 950.0, 4400.0, 9.80, 11.50, 0.05, 0.025, 0.16, 0.015, 0.28, 91.0),
    ("APD", "Air Products and Chemicals", "Materials", "Atmospheric & Process Gases", 298.00, 222.0, 3100.0, 0.19, 14200.0, 15500.0, 2400.0, 3600.0, 5200.0, 4800.0, 10.40, 12.80, 0.065, 0.025, 0.25, 0.02, 0.85, 55.0),
    ("FCX", "Freeport-McMoRan Inc.", "Materials", "Copper & Gold Mining", 46.80, 1440.0, 5900.0, 0.32, 9800.0, 17500.0, 6400.0, 6800.0, 4600.0, 8500.0, 1.45, 2.25, 0.08, 0.12, 0.25, 0.07, 0.50, 16.0),
    ("ECL", "Ecolab Inc.", "Materials", "Water Treatment & Hygiene", 248.00, 285.0, 2400.0, 0.21, 8400.0, 8500.0, 950.0, 2600.0, 850.0, 3400.0, 6.40, 6.70, 0.065, 0.02, 0.15, 0.015, 0.32, 54.0),
    ("NEM", "Newmont Corporation", "Materials", "Gold & Silver Mining", 54.00, 1150.0, 3400.0, 0.28, 8900.0, 24000.0, 3100.0, 4600.0, 3400.0, 5200.0, 1.80, 3.10, 0.075, 0.12, 0.21, 0.06, 0.65, 14.5),
    ("CTVA", "Corteva Inc.", "Materials", "Agricultural Seeds & Crop Protection", 58.20, 695.0, 2100.0, 0.20, 3400.0, 24000.0, 2400.0, 2400.0, 780.0, 3400.0, 1.70, 2.80, 0.05, 0.03, 0.12, 0.02, 0.32, 24.5),
    ("DOW", "Dow Inc.", "Materials", "Packaging & Specialty Plastics", 52.40, 702.0, 2800.0, 0.22, 16500.0, 18500.0, 2800.0, 3800.0, 2400.0, 5100.0, 2.10, 3.20, 0.035, 0.04, 0.065, 0.02, 0.55, 62.0),
    ("NUE", "Nucor Corporation", "Materials", "Steel Mini-Mills & Recycled Scrap", 154.00, 238.0, 4200.0, 0.23, 7100.0, 21000.0, 5400.0, 4800.0, 3100.0, 5600.0, 12.80, 11.20, 0.045, 0.07, 0.12, 0.035, 0.55, 142.0),
    ("PPG", "PPG Industries Inc.", "Materials", "Industrial Coatings & Resins", 132.00, 234.0, 2200.0, 0.22, 6800.0, 7800.0, 1400.0, 2400.0, 550.0, 3100.0, 6.80, 8.40, 0.045, 0.02, 0.12, 0.015, 0.25, 78.0),
    ("EMN", "Eastman Chemical Company", "Materials", "Advanced Materials & Additives", 108.00, 117.0, 1250.0, 0.21, 5100.0, 5400.0, 520.0, 1400.0, 750.0, 1800.0, 7.40, 7.90, 0.04, 0.03, 0.13, 0.02, 0.45, 81.0),
    ("ALB", "Albemarle Corporation", "Materials", "Lithium & Specialty Chemicals", 94.00, 118.0, 850.0, 0.22, 3800.0, 9200.0, 1800.0, 1200.0, 1800.0, 1600.0, 1.80, 2.40, 0.09, 0.15, 0.14, 0.08, 0.90, 62.0),
    ("IFF", "International Flavors & Fragrances", "Materials", "Taste, Scent & Nutrition", 98.50, 256.0, 1400.0, 0.20, 10200.0, 14800.0, 720.0, 1600.0, 620.0, 2100.0, 2.45, 4.25, 0.045, 0.02, 0.12, 0.015, 0.38, 44.0),
    ("BALL", "Ball Corporation", "Materials", "Sustainable Aluminum Packaging", 64.20, 298.0, 1300.0, 0.21, 7400.0, 4800.0, 2100.0, 1400.0, 680.0, 1800.0, 2.80, 3.15, 0.04, 0.02, 0.10, 0.015, 0.45, 40.0),
    ("IP", "International Paper Company", "Materials", "Fiber-Based Packaging & Pulp", 48.00, 348.0, 1100.0, 0.22, 6200.0, 9800.0, 1100.0, 1800.0, 1100.0, 2200.0, 1.85, 2.40, 0.035, 0.025, 0.06, 0.015, 0.60, 54.0),
    ("PKG", "Packaging Corp. of America", "Materials", "Corrugated Containerboard", 212.00, 90.0, 1200.0, 0.23, 2600.0, 4200.0, 780.0, 1400.0, 520.0, 1700.0, 9.20, 9.10, 0.045, 0.02, 0.15, 0.015, 0.35, 92.0),
    ("AMCR", "Amcor plc", "Materials", "Flexible & Rigid Packaging", 10.40, 1440.0, 1500.0, 0.21, 6400.0, 4200.0, 680.0, 1550.0, 580.0, 2100.0, 0.70, 0.74, 0.035, 0.015, 0.11, 0.01, 0.35, 9.4),
    ("CF", "CF Industries Holdings", "Materials", "Nitrogen Fertilizer & Clean Ammonia", 84.50, 182.0, 2100.0, 0.22, 3100.0, 6800.0, 2200.0, 2400.0, 580.0, 2800.0, 7.80, 6.20, 0.045, 0.06, 0.34, 0.05, 0.25, 34.0),
    ("MOS", "The Mosaic Company", "Materials", "Potash & Phosphate Crop Nutrition", 28.50, 324.0, 1200.0, 0.24, 4200.0, 11500.0, 850.0, 1800.0, 1200.0, 2100.0, 2.20, 2.50, 0.04, 0.07, 0.10, 0.04, 0.60, 42.0),
    ("FMC", "FMC Corporation", "Materials", "Agricultural Sciences Insecticides", 62.40, 125.0, 780.0, 0.16, 3800.0, 3100.0, 480.0, 850.0, 140.0, 1100.0, 3.40, 3.65, 0.045, 0.03, 0.17, 0.02, 0.18, 36.0),
    ("CE", "Celanese Corporation", "Materials", "Engineered Polymers & Acetyls", 132.00, 109.0, 1400.0, 0.20, 12800.0, 5800.0, 1100.0, 1600.0, 580.0, 2400.0, 8.80, 11.20, 0.045, 0.03, 0.13, 0.02, 0.35, 98.0),
    ("SEE", "Sealed Air Corporation", "Materials", "Bubble Wrap & Cryovac Packaging", 36.80, 145.0, 720.0, 0.24, 4800.0, 850.0, 340.0, 820.0, 220.0, 1100.0, 2.45, 3.05, 0.04, 0.015, 0.13, 0.015, 0.25, 38.0),
    ("AVY", "Avery Dennison Corporation", "Materials", "Adhesive Labels & RFID Materials", 218.00, 80.5, 980.0, 0.23, 3100.0, 2400.0, 280.0, 1050.0, 280.0, 1300.0, 7.80, 9.40, 0.055, 0.015, 0.11, 0.01, 0.25, 105.0),
    ("VMC", "Vulcan Materials Company", "Materials", "Crushed Stone & Construction Aggregates", 274.00, 132.0, 1600.0, 0.22, 4200.0, 7800.0, 380.0, 1800.0, 680.0, 2100.0, 7.10, 8.80, 0.065, 0.02, 0.20, 0.015, 0.35, 59.0),
    ("MLM", "Martin Marietta Materials", "Materials", "Heavy Building Materials Aggregates", 584.00, 61.5, 1700.0, 0.22, 4800.0, 8200.0, 480.0, 1900.0, 740.0, 2200.0, 18.50, 21.00, 0.065, 0.02, 0.24, 0.015, 0.38, 110.0),
    ("DD", "DuPont de Nemours Inc.", "Materials", "Electronics & Water Protection", 84.50, 418.0, 1800.0, 0.21, 8400.0, 26000.0, 1400.0, 2200.0, 720.0, 3100.0, 3.40, 3.80, 0.05, 0.02, 0.15, 0.015, 0.32, 28.5),
    ("RPM", "RPM International Inc.", "Materials", "Rust-Oleum & Construction Sealants", 128.00, 129.0, 920.0, 0.23, 2800.0, 2400.0, 240.0, 1100.0, 250.0, 1200.0, 4.80, 5.40, 0.05, 0.015, 0.12, 0.01, 0.22, 56.0),
    ("OLN", "Olin Corporation", "Materials", "Chlor Alkali, Vinyls & Winchester", 44.50, 118.0, 620.0, 0.22, 3100.0, 2400.0, 180.0, 780.0, 280.0, 1100.0, 2.80, 3.90, 0.045, 0.035, 0.09, 0.025, 0.35, 58.0),
]


def generate_synthetic_history(ticker: str, current_price: float, beta: float = 1.1) -> pd.DataFrame:
    """
    Generates 60 monthly periods of realistic market and excess returns for econometric testing.
    """
    rng = np.random.default_rng(stable_seed(ticker))
    n = 60
    dates = pd.date_range(end=datetime.now(), periods=n, freq="30D").strftime("%Y-%m-%d").tolist()

    # Market return (S&P 500)
    mkt_ret = rng.normal(0.009, 0.042, n)
    rate_change = rng.normal(0.0003, 0.004, n)
    sec_ret = 0.85 * mkt_ret + rng.normal(0.001, 0.025, n)
    alpha = rng.normal(0.0015, 0.003)
    residual = rng.normal(0.0, 0.028, n)
    
    stock_ret = alpha + beta * mkt_ret + 0.2 * sec_ret - 0.4 * rate_change + residual
    
    prices = [current_price]
    for r in reversed(stock_ret[1:]):
        prev_p = prices[-1] / (1.0 + r)
        prices.append(prev_p)
    prices.reverse()

    df = pd.DataFrame({
        "ticker": [ticker] * n,
        "date": dates,
        "stock_price": [round(float(p), 2) for p in prices],
        "stock_return": [round(float(r), 5) for r in stock_ret],
        "market_return": [round(float(r), 5) for r in mkt_ret],
        "sector_return": [round(float(r), 5) for r in sec_ret],
        "rate_change_10y": [round(float(r), 5) for r in rate_change],
        "stock_excess_return": [round(float(r - 0.0035), 5) for r in stock_ret],
        "market_excess_return": [round(float(r - 0.0035), 5) for r in mkt_ret],
        "sector_excess_return": [round(float(r - 0.0035), 5) for r in sec_ret],
    })
    return df


def seed_database():
    """
    Seeds database with all 11 sectors, 380+ stocks, computed metrics, MC simulations, and history.
    """
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    print(f"[SEED] Insertando los 11 sectores GICS oficiales...")
    for sec in GICS_SECTORS:
        cursor.execute("""
            INSERT OR REPLACE INTO sectors (name, code, description)
            VALUES (?, ?, ?)
        """, (sec["name"], sec["code"], sec["description"]))
    conn.commit()

    total_stocks = len(STOCKS_RAW)
    print(f"[SEED] Procesando e insertando {total_stocks} acciones del S&P 500 / NYSE / NASDAQ...")

    stock_records = []
    history_records = []
    mc_cache_records = []

    for item in STOCKS_RAW:
        (
            ticker, name, sector, industry, market_price, shares_outstanding,
            ebit, tax_rate, total_debt, total_equity, cash_and_equivalents,
            operating_cash_flow, capex, ebitda, trailing_eps, forward_eps,
            rev_growth_mean, rev_growth_std, margin_mean, margin_std,
            reinvestment_rate_mean, revenue_ps
        ) = item

        raw_dict = {
            "market_price": market_price,
            "shares_outstanding": shares_outstanding,
            "ebit": ebit,
            "tax_rate": tax_rate,
            "total_debt": total_debt,
            "total_equity": total_equity,
            "cash_and_equivalents": cash_and_equivalents,
            "operating_cash_flow": operating_cash_flow,
            "capex": capex,
            "ebitda": ebitda,
            "trailing_eps": trailing_eps,
            "forward_eps": forward_eps
        }

        metrics = compute_all_metrics(raw_dict)

        # Fast Monte Carlo simulation (5000 runs)
        mc_result = run_monte_carlo_simulation(
            p0=market_price,
            current_revenue_ps=revenue_ps,
            historical_growth_mean=rev_growth_mean,
            historical_growth_std=rev_growth_std,
            historical_margin_mean=margin_mean,
            historical_margin_std=margin_std,
            tax_rate=tax_rate,
            reinvestment_rate_mean=reinvestment_rate_mean,
            num_simulations=5000,
            random_seed=stable_seed(ticker)
        )

        p10 = mc_result["percentiles"]["p10"]
        p50 = mc_result["percentiles"]["p50"]
        p90 = mc_result["percentiles"]["p90"]

        stock_records.append((
            ticker, name, sector, industry, market_price, shares_outstanding, metrics["market_cap"],
            ebit, tax_rate, metrics["nopat"], total_debt, total_equity, cash_and_equivalents,
            metrics["invested_capital"], metrics["roic"], operating_cash_flow, capex, metrics["fcf"], metrics["fcf_yield"],
            metrics["ebitda"], metrics["ev"], metrics["ev_ebitda"], metrics["net_debt"], metrics["net_debt_ebitda"],
            trailing_eps, forward_eps, metrics["trailing_pe"], metrics["forward_pe"],
            rev_growth_mean, rev_growth_std, margin_mean, margin_std,
            reinvestment_rate_mean, revenue_ps, p10, p50, p90
        ))

        mc_cache_records.append((ticker, json.dumps(mc_result)))

        # Historical series
        df_hist = generate_synthetic_history(ticker, market_price)
        for _, row in df_hist.iterrows():
            history_records.append((
                ticker, row["date"], row["stock_price"], row["stock_return"], row["market_return"],
                row["sector_return"], row["rate_change_10y"], row["stock_excess_return"],
                row["market_excess_return"], row["sector_excess_return"]
            ))

    # Batch insert into stocks
    cursor.executemany("""
        INSERT OR REPLACE INTO stocks (
            ticker, name, sector, industry, market_price, shares_outstanding, market_cap,
            ebit, tax_rate, nopat, total_debt, total_equity, cash_and_equivalents,
            invested_capital, roic, operating_cash_flow, capex, fcf, fcf_yield,
            ebitda, ev, ev_ebitda, net_debt, net_debt_ebitda,
            trailing_eps, forward_eps, trailing_pe, forward_pe,
            rev_growth_mean, rev_growth_std, margin_mean, margin_std,
            reinvestment_rate_mean, revenue_ps, mc_p10, mc_p50, mc_p90
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?, ?
        )
    """, stock_records)

    # Batch insert into monte_carlo_cache
    cursor.executemany("""
        INSERT OR REPLACE INTO monte_carlo_cache (ticker, simulation_json, calculated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
    """, mc_cache_records)

    # Batch insert into historical_series
    cursor.executemany("""
        INSERT OR REPLACE INTO historical_series (
            ticker, date, stock_price, stock_return, market_return,
            sector_return, rate_change_10y, stock_excess_return,
            market_excess_return, sector_excess_return
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, history_records)

    conn.commit()
    conn.close()
    invalidate_cache()
    print(f"[OK] Base de datos sembrada exitosamente con {total_stocks} acciones en los 11 sectores GICS.")


def backfill_revenue_ps() -> int:
    """
    One-time migration for databases created before `revenue_ps` was stored: copies the
    per-share revenue baseline from the seed table. Returns the number of rows updated.
    """
    with get_db_connection() as conn:
        rows = [(item[-1], item[0]) for item in STOCKS_RAW]
        cur = conn.executemany(
            "UPDATE stocks SET revenue_ps = ? WHERE ticker = ? AND revenue_ps IS NULL", rows
        )
        updated = cur.rowcount
        conn.commit()
    if updated > 0:
        invalidate_cache()
    return max(updated, 0)


if __name__ == "__main__":
    seed_database()
