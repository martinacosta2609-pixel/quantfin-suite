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
    ("AAPL", "Apple Inc.", "Information Technology", "Consumer Electronics", 345.00, 14594.18, 189555.37, 0.15, 84344.00, 107413.16, 62399.00, 146724.00, 39002.12, 167959.00, 8.72, 9.57, 0.075, 0.035, 0.310, 0.020, 0.18, 31.71),
    ("MSFT", "Microsoft Corporation", "Information Technology", "Software - Infrastructure", 526.25, 7425.55, 134356.48, 0.18, 128813.00, 442302.62, 76843.00, 182934.99, 166389.49, 194237.01, 17.95, 23.70, 0.140, 0.030, 0.440, 0.025, 0.38, 44.67),
    ("NVDA", "NVIDIA Corporation", "Information Technology", "Semiconductors", 216.87, 24147.00, 122453.86, 0.14, 38860.00, 228986.00, 62469.00, 134360.00, 92550.12, 201266.00, 7.91, 15.91, 0.350, 0.150, 0.580, 0.060, 0.15, 12.48),
    ("AVGO", "Broadcom Inc.", "Information Technology", "Semiconductors", 330.31, 4773.63, 37848.02, 0.12, 59419.00, 99682.94, 23975.00, 40653.00, 10056.50, 52260.00, 7.83, 19.40, 0.180, 0.050, 0.450, 0.030, 0.22, 18.77),
    ("ORCL", "Oracle Corporation", "Information Technology", "Software - Infrastructure", 127.56, 3031.50, 11257.44, 0.16, 169142.99, 61969.95, 37077.00, 46940.00, 92793.63, 34433.00, 6.38, 11.00, 0.090, 0.030, 0.300, 0.025, 0.35, 24.79),
    ("ADBE", "Adobe Inc.", "Information Technology", "Software - Application", 260.35, 389.20, 3353.45, 0.18, 6787.00, 11709.86, 5642.00, 10806.00, 1460.87, 9917.00, 17.91, 27.51, 0.110, 0.025, 0.340, 0.020, 0.15, 63.95),
    ("CRM", "Salesforce Inc.", "Information Technology", "Software - Application", 244.76, 823.00, 5599.93, 0.20, 42376.00, 38378.14, 11403.00, 15750.00, 689.22, 12899.00, 10.93, 16.02, 0.100, 0.020, 0.200, 0.030, 0.15, 49.20),
    ("AMD", "Advanced Micro Devices", "Information Technology", "Semiconductors", 528.67, 1632.48, 7199.79, 0.15, 4276.00, 67243.28, 13111.00, 10080.00, 1238.50, 9562.00, 3.92, 15.76, 0.170, 0.080, 0.180, 0.040, 0.25, 25.36),
    ("CSCO", "Cisco Systems Inc.", "Information Technology", "Communication Equipment", 105.75, 3942.59, 28015.86, 0.19, 31185.00, 50240.38, 15918.00, 14177.00, 2994.38, 18642.00, 3.33, 5.62, 0.040, 0.020, 0.280, 0.020, 0.15, 16.02),
    ("ACN", "Accenture plc", "Information Technology", "Information Technology Services", 243.94, 611.94, 6855.78, 0.23, 13396.99, 32437.22, 12837.77, 12363.35, 1678.86, 13419.35, 13.56, 15.89, 0.060, 0.020, 0.150, 0.015, 0.15, 121.12),
    ("INTU", "Intuit Inc.", "Information Technology", "Software - Application", 344.36, 267.24, 2037.95, 0.21, 8421.00, 18910.69, 7200.00, 8838.00, 2484.37, 6849.00, 16.46, 26.94, 0.120, 0.030, 0.260, 0.020, 0.18, 77.71),
    ("IBM", "International Business Machines", "Information Technology", "Information Technology Services", 245.34, 942.13, 11458.19, 0.14, 65272.00, 32828.67, 8132.00, 14888.00, 2838.25, 16473.00, 11.72, 13.23, 0.040, 0.020, 0.170, 0.015, 0.20, 73.70),
    ("TXN", "Texas Instruments", "Information Technology", "Semiconductors", 284.23, 913.25, 9027.65, 0.13, 14052.00, 16385.49, 7001.00, 8667.00, 5121.75, 9520.00, 7.71, 11.45, 0.050, 0.040, 0.400, 0.030, 0.45, 21.38),
    ("QCOM", "QUALCOMM Incorporated", "Information Technology", "Semiconductors", 177.59, 1067.84, 11396.15, 0.14, 15270.00, 27942.16, 8304.00, 12401.00, 2160.00, 11999.00, 8.64, 10.19, 0.080, 0.040, 0.300, 0.030, 0.18, 41.28),
    ("AMAT", "Applied Materials Inc.", "Information Technology", "Semiconductor Equipment & Materials", 388.67, 793.60, 14817.33, 0.12, 7346.00, 25626.06, 9233.00, 8396.00, 5320.63, 10155.00, 11.59, 18.49, 0.090, 0.040, 0.290, 0.025, 0.20, 38.83),
    ("NOW", "ServiceNow Inc.", "Information Technology", "Software - Application", 155.32, 1033.86, 362.50, 0.18, 8453.00, 12515.93, 4664.00, 5308.00, 158.63, 2897.00, 1.60, 5.01, 0.210, 0.030, 0.220, 0.020, 0.20, 14.22),
    ("LRCX", "Lam Research Corporation", "Information Technology", "Semiconductor Equipment & Materials", 241.12, 1251.42, 13648.30, 0.11, 4121.56, 12472.95, 5579.17, 5857.66, 2767.17, 8641.33, 6.71, 12.11, 0.100, 0.050, 0.310, 0.030, 0.18, 18.51),
    ("MU", "Micron Technology Inc.", "Information Technology", "Semiconductors", 907.00, 1131.42, 7200.00, 0.12, 5179.00, 138429.63, 43434.00, 89675.00, 60534.75, 108843.00, 74.33, 206.85, 0.180, 0.140, 0.220, 0.080, 0.60, 118.18),
    ("PANW", "Palo Alto Networks", "Information Technology", "Software - Infrastructure", 360.14, 818.00, 1136.41, 0.17, 2567.00, 27593.59, 3071.00, 4553.00, 312.38, 1560.00, 0.40, 4.88, 0.160, 0.030, 0.190, 0.020, 0.15, 15.33),
    ("SNPS", "Synopsys Inc.", "Information Technology", "Software - Infrastructure", 439.97, 191.64, 1358.46, 0.16, 10841.79, 31157.63, 3607.67, 2938.34, 186.79, 2075.49, 5.66, 18.73, 0.130, 0.020, 0.270, 0.020, 0.18, 49.64),
    ("CDNS", "Cadence Design Systems", "Information Technology", "Software - Application", 314.25, 275.39, 1488.25, 0.18, 2651.36, 6857.84, 1531.84, 1854.87, 245.19, 2155.92, 5.03, 9.57, 0.120, 0.020, 0.300, 0.020, 0.15, 21.46),
    ("KLAC", "KLA Corporation", "Information Technology", "Semiconductor Equipment & Materials", 154.50, 1305.01, 950.00, 0.13, 6151.71, 6339.72, 4902.41, 4143.08, 1518.49, 6054.76, 3.66, 6.74, 0.110, 0.040, 0.380, 0.030, 0.16, 10.35),
    ("ADI", "Analog Devices Inc.", "Information Technology", "Semiconductors", 393.38, 484.57, 5863.62, 0.14, 9164.06, 33550.83, 2324.93, 5545.33, 1397.99, 6922.70, 8.42, 16.50, 0.070, 0.040, 0.350, 0.030, 0.25, 28.43),
    ("CRWD", "CrowdStrike Holdings", "Information Technology", "Software - Infrastructure", 239.46, 1023.93, 336.93, 0.15, 820.18, 5102.27, 5013.85, 2016.62, 21.23, 106.86, 0.06, 1.61, 0.240, 0.050, 0.180, 0.030, 0.15, 5.33),
    ("APH", "Amphenol Corporation", "Information Technology", "Electronic Components", 75.70, 2465.97, 3037.35, 0.22, 18811.30, 15496.14, 5419.10, 5871.70, 2053.33, 9463.70, 2.00, 3.33, 0.090, 0.025, 0.210, 0.015, 0.20, 11.82),
    ("NXPI", "NXP Semiconductors", "Information Technology", "Semiconductors", 241.85, 252.16, 4296.83, 0.14, 10976.00, 11394.54, 3222.00, 3129.00, 1125.36, 5068.00, 11.71, 18.30, 0.060, 0.030, 0.340, 0.025, 0.25, 52.23),
    ("MCHP", "Microchip Technology", "Information Technology", "Semiconductors", 75.55, 543.01, 2028.84, 0.13, 5398.70, 6450.94, 272.30, 1198.00, 405.77, 1506.10, 0.68, 4.60, 0.050, 0.040, 0.360, 0.030, 0.22, 9.46),
    ("FTNT", "Fortinet Inc.", "Information Technology", "Software - Infrastructure", 173.06, 733.71, 3180.44, 0.17, 561.40, 1551.07, 4069.60, 3396.10, 1130.51, 2595.80, 2.83, 3.79, 0.130, 0.030, 0.280, 0.025, 0.12, 10.14),
    ("TEL", "TE Connectivity Ltd.", "Information Technology", "Electronic Components", 210.29, 289.51, 3445.02, 0.18, 5818.00, 13226.41, 1239.00, 4418.00, 2081.12, 4951.00, 10.21, 12.97, 0.050, 0.020, 0.170, 0.015, 0.25, 65.89),
    ("HPQ", "HP Inc.", "Information Technology", "Computer Hardware", 32.43, 901.79, 3442.29, 0.21, 10339.00, -1087.04, 4169.00, 4668.00, 1278.13, 4636.00, 2.62, 3.15, 0.030, 0.020, 0.080, 0.010, 0.18, 63.85),
    ("GLW", "Corning Incorporated", "Information Technology", "Electronic Components", 128.63, 861.39, 5122.43, 0.19, 9379.00, 11941.43, 2504.00, 3915.00, 3180.50, 4085.00, 2.18, 4.40, 0.060, 0.025, 0.160, 0.020, 0.40, 19.78),
    ("KEYS", "Keysight Technologies", "Information Technology", "Scientific & Technical Instruments", 327.24, 170.24, 2272.50, 0.14, 2766.00, 6568.89, 2605.00, 1604.00, 454.50, 1698.00, 7.39, 13.93, 0.060, 0.030, 0.240, 0.020, 0.20, 38.44),
    ("WDC", "Western Digital Corp.", "Information Technology", "Computer Hardware", 365.99, 374.32, 3800.00, 0.16, 1191.00, 9191.13, 1579.00, 3929.00, 1660.25, 5002.00, 26.92, 33.80, 0.120, 0.080, 0.150, 0.050, 0.40, 37.45),
    ("STX", "Seagate Technology", "Information Technology", "Computer Hardware", 670.20, 227.39, 3280.00, 0.12, 3898.00, 2172.74, 1704.00, 3674.00, 1730.25, 4502.00, 13.90, 57.44, 0.100, 0.060, 0.160, 0.040, 0.30, 55.69),
    ("MPWR", "Monolithic Power Systems", "Information Technology", "Semiconductors", 1220.00, 49.14, 895.15, 0.13, 18.93, 3895.52, 1413.76, 822.34, 378.02, 1000.28, 16.44, 35.27, 0.160, 0.040, 0.310, 0.030, 0.15, 67.27),
    ("ON", "ON Semiconductor", "Information Technology", "Semiconductors", 75.18, 389.32, 2388.31, 0.15, 4709.00, 7219.14, 3864.50, 1672.00, 15.35, 2089.90, 1.55, 4.54, 0.060, 0.040, 0.310, 0.030, 0.45, 15.57),
    ("TER", "Teradyne Inc.", "Information Technology", "Semiconductor Equipment & Materials", 322.93, 156.34, 1791.13, 0.16, 100.13, 3436.37, 354.83, 1064.95, 627.57, 1504.89, 7.28, 11.75, 0.080, 0.040, 0.240, 0.030, 0.20, 28.44),
    ("ZBRA", "Zebra Technologies", "Information Technology", "Communication Equipment", 381.39, 47.31, 753.36, 0.17, 2962.00, 3429.31, 157.00, 979.00, 402.25, 1184.00, 10.91, 22.29, 0.070, 0.030, 0.160, 0.020, 0.15, 118.30),
    ("SMCI", "Super Micro Computer", "Information Technology", "Computer Hardware", 34.76, 656.97, 943.71, 0.16, 9259.89, 10254.57, 7544.58, 668.46, 1438.90, 2824.16, 3.26, 5.59, 0.250, 0.120, 0.090, 0.030, 0.30, 64.91),
    ("PLTR", "Palantir Technologies Inc.", "Information Technology", "Software - Infrastructure", 200.81, 2300.71, 1444.32, 0.18, 211.40, 9359.30, 9409.10, 3400.29, 1241.19, 2662.63, 1.16, 2.35, 0.240, 0.050, 0.320, 0.030, 0.12, 2.58),
    ("TYL", "Tyler Technologies", "Information Technology", "Software - Application", 385.22, 40.95, 211.01, 0.20, 1455.03, 3038.82, 970.04, 730.75, 136.31, 458.52, 7.60, 15.36, 0.090, 0.020, 0.180, 0.020, 0.15, 57.45),
    ("FICO", "Fair Isaac Corporation", "Information Technology", "Software - Application", 809.85, 21.60, 334.22, 0.24, 5598.01, -342.79, 248.44, 1001.55, 227.14, 1263.36, 34.54, 49.18, 0.120, 0.020, 0.450, 0.020, 0.10, 101.93),
    ("NTAP", "NetApp Inc.", "Information Technology", "Software - Infrastructure", 213.83, 196.42, 2402.58, 0.19, 2534.00, 1498.28, 3576.00, 1897.00, 725.62, 2095.00, 7.09, 11.16, 0.060, 0.025, 0.220, 0.020, 0.15, 37.38),
    ("AKAM", "Akamai Technologies", "Information Technology", "Software - Infrastructure", 90.71, 143.72, 682.17, 0.18, 9338.99, 4752.71, 3355.39, 1447.19, 737.13, 1079.90, 2.76, 6.84, 0.070, 0.020, 0.200, 0.020, 0.35, 29.93),
    ("FFIV", "F5 Inc.", "Information Technology", "Software - Infrastructure", 454.67, 56.63, 1418.24, 0.18, 252.38, 3842.21, 1605.78, 1049.44, 332.31, 923.30, 12.55, 18.08, 0.060, 0.020, 0.240, 0.020, 0.12, 57.87),
    # =========================================================================
    # 2. HEALTH CARE (45 stocks)
    # =========================================================================
    ("LLY", "Eli Lilly and Company", "Health Care", "Drug Manufacturers - General", 1301.31, 891.74, 19685.89, 0.14, 54908.00, 33887.96, 8950.00, 28083.00, 17017.10, 41707.00, 29.79, 47.22, 0.240, 0.060, 0.350, 0.040, 0.35, 89.02),
    ("UNH", "UnitedHealth Group Inc.", "Health Care", "Healthcare Plans", 421.83, 897.59, 24079.40, 0.22, 74331.00, 103620.14, 28549.00, 26195.00, 2422.62, 28903.00, 15.55, 23.27, 0.080, 0.020, 0.088, 0.008, 0.20, 498.13),
    ("JNJ", "Johnson & Johnson", "Health Care", "Drug Manufacturers - General", 262.19, 2409.90, 38222.49, 0.16, 49036.00, 85030.86, 20758.00, 37083.95, 7481.85, 34150.00, 6.59, 11.62, 0.045, 0.020, 0.270, 0.015, 0.25, 40.99),
    ("ABBV", "AbbVie Inc.", "Health Care", "Drug Manufacturers - General", 283.73, 1767.12, 27394.62, 0.15, 70885.00, 18062.39, 6569.00, 19507.00, 2636.75, 30763.00, 3.54, 16.19, 0.050, 0.030, 0.340, 0.030, 0.18, 36.39),
    ("MRK", "Merck & Co. Inc.", "Health Care", "Drug Manufacturers - General", 152.89, 2467.17, 24212.12, 0.15, 53911.00, 41907.38, 7141.00, 19967.00, 4795.50, 28871.00, 1.26, 9.26, 0.060, 0.030, 0.300, 0.025, 0.30, 26.85),
    ("TMO", "Thermo Fisher Scientific", "Health Care", "Diagnostics & Research", 686.82, 369.75, 9165.43, 0.14, 41370.00, 54729.62, 6061.00, 9324.00, 2864.63, 12217.00, 18.96, 27.70, 0.070, 0.030, 0.220, 0.020, 0.22, 127.37),
    ("ABT", "Abbott Laboratories", "Health Care", "Medical Devices", 100.09, 1730.38, 6512.71, 0.15, 13282.49, 51942.65, 6169.93, 6941.17, 1628.18, 11483.00, 2.69, 5.99, 0.055, 0.020, 0.190, 0.015, 0.25, 27.77),
    ("DHR", "Danaher Corporation", "Health Care", "Diagnostics & Research", 234.24, 702.99, 4712.73, 0.16, 26482.00, 53589.33, 5682.00, 6859.00, 1968.75, 8536.00, 6.04, 9.32, 0.065, 0.030, 0.250, 0.020, 0.22, 36.27),
    ("PFE", "Pfizer Inc.", "Health Care", "Drug Manufacturers - General", 30.21, 5699.67, 7108.24, 0.14, 63480.00, 85198.72, 11704.00, 13401.00, 915.38, 25383.00, 0.76, 2.88, 0.040, 0.030, 0.180, 0.030, 0.30, 11.19),
    ("ISRG", "Intuitive Surgical Inc.", "Health Care", "Medical Instruments & Supplies", 433.98, 353.28, 1916.41, 0.17, 0.00, 16315.44, 6800.40, 2090.63, 958.21, 4115.90, 8.27, 12.40, 0.140, 0.030, 0.300, 0.025, 0.35, 32.78),
    ("AMGN", "Amgen Inc.", "Health Care", "Drug Manufacturers - General", 446.23, 540.63, 14290.57, 0.14, 57304.00, 11688.46, 13989.00, 12478.00, 3832.38, 17268.00, 16.10, 24.48, 0.070, 0.025, 0.370, 0.025, 0.15, 70.68),
    ("BMY", "Bristol-Myers Squibb", "Health Care", "Drug Manufacturers - General", 61.84, 2042.71, 9865.53, 0.16, 45053.00, 22316.66, 11067.00, 12782.00, 4667.62, 18930.00, 4.54, 6.61, 0.035, 0.025, 0.220, 0.025, 0.15, 24.14),
    ("ELV", "Elevance Health Inc.", "Health Care", "Healthcare Plans", 439.00, 216.87, 9696.36, 0.22, 31044.00, 43115.57, 37514.00, 7464.00, 3157.62, 8324.00, 23.55, 30.11, 0.070, 0.020, 0.055, 0.008, 0.18, 912.91),
    ("SYK", "Stryker Corporation", "Health Care", "Medical Devices", 303.02, 383.57, 3511.82, 0.16, 15446.00, 23987.89, 3476.00, 5525.00, 1416.13, 7376.00, 9.65, 16.66, 0.090, 0.025, 0.210, 0.015, 0.22, 67.50),
    ("GILD", "Gilead Sciences Inc.", "Health Care", "Drug Manufacturers - General", 155.83, 1239.96, 16412.86, 0.15, 26246.00, 11819.25, 4882.00, 13552.00, 3783.12, 14601.00, 8.48, 9.98, 0.045, 0.020, 0.360, 0.025, 0.12, 24.51),
    ("MDT", "Medtronic plc", "Health Care", "Medical Devices", 93.94, 1279.14, 6424.15, 0.15, 28153.00, 50195.93, 8819.00, 8035.00, 2622.50, 10408.00, 4.07, 6.41, 0.045, 0.020, 0.200, 0.015, 0.22, 29.30),
    ("VRTX", "Vertex Pharmaceuticals", "Health Care", "Biotechnology", 529.54, 253.46, 4637.15, 0.16, 1977.60, 20256.85, 7852.40, 4292.90, 1665.01, 5100.50, 17.27, 20.22, 0.110, 0.030, 0.420, 0.030, 0.15, 49.51),
    ("CI", "The Cigna Group", "Health Care", "Healthcare Plans", 307.62, 264.24, 7013.84, 0.22, 31878.00, 42707.34, 7257.00, 10277.00, 2296.88, 12758.00, 24.19, 33.48, 0.080, 0.020, 0.042, 0.006, 0.15, 1069.94),
    ("REGN", "Regeneron Pharmaceuticals", "Health Care", "Biotechnology", 814.60, 101.14, 3973.66, 0.14, 2706.60, 31970.78, 7994.60, 4681.30, 1616.00, 4702.40, 40.44, 62.28, 0.085, 0.030, 0.370, 0.030, 0.18, 150.31),
    ("BDX", "Becton Dickinson and Co.", "Health Care", "Medical Instruments & Supplies", 195.65, 272.39, 2379.97, 0.15, 16808.00, 24415.94, 709.00, 3342.00, 902.75, 6121.00, 4.30, 13.30, 0.050, 0.020, 0.150, 0.015, 0.35, 79.76),
    ("ZTS", "Zoetis Inc.", "Health Care", "Drug Manufacturers - Specialty & Generic", 80.70, 413.22, 1329.28, 0.21, 9255.00, 3140.91, 1676.00, 2840.00, 823.00, 4066.00, 6.08, 6.45, 0.080, 0.025, 0.370, 0.020, 0.20, 22.14),
    ("HCA", "HCA Healthcare Inc.", "Health Care", "Medical Care Facilities", 457.38, 216.50, 9685.69, 0.23, 51552.00, 502.22, 1130.00, 11124.00, 7385.87, 15747.00, 29.83, 31.99, 0.070, 0.020, 0.120, 0.010, 0.45, 345.31),
    ("BSX", "Boston Scientific Corp.", "Health Care", "Medical Devices", 44.96, 1449.23, 1488.04, 0.14, 12624.00, 24973.12, 539.00, 4529.00, 2077.62, 5711.00, 2.47, 3.38, 0.110, 0.025, 0.200, 0.020, 0.25, 14.19),
    ("MCK", "McKesson Corporation", "Health Care", "Medical Distribution", 1018.02, 116.59, 7816.26, 0.21, 11796.00, -3431.53, 5164.00, 6853.00, 51.75, 7071.00, 37.31, 50.58, 0.080, 0.015, 0.014, 0.002, 0.15, 3367.33),
    ("COR", "Cencora Inc.", "Health Care", "Medical Distribution", 341.50, 190.83, 4868.34, 0.22, 14463.05, 3050.94, 2815.29, 4820.95, 2777.63, 5546.48, 13.47, 19.76, 0.080, 0.015, 0.013, 0.002, 0.15, 1715.73),
    ("EW", "Edwards Lifesciences", "Health Care", "Medical Devices", 88.98, 576.40, 2217.98, 0.15, 704.40, 10614.41, 4252.70, 1720.30, 487.89, 1996.80, 1.68, 3.38, 0.080, 0.025, 0.280, 0.020, 0.20, 11.22),
    ("DXCM", "DexCom Inc.", "Health Care", "Medical Devices", 79.69, 377.36, 770.16, 0.18, 1398.40, 2621.15, 1947.00, 1748.70, 727.54, 1403.20, 2.52, 3.12, 0.140, 0.040, 0.200, 0.030, 0.30, 12.87),
    ("IDXX", "IDEXX Laboratories", "Health Care", "Diagnostics & Research", 564.18, 78.78, 1515.90, 0.21, 1096.08, 1610.68, 196.93, 1371.51, 462.14, 1621.68, 14.23, 16.74, 0.080, 0.020, 0.310, 0.020, 0.16, 57.17),
    ("CNC", "Centene Corporation", "Health Care", "Healthcare Plans", 70.87, 494.00, 3600.35, 0.23, 16105.00, 22562.23, 27057.00, 9749.00, 109.38, 4606.00, 4.93, 5.35, 0.050, 0.020, 0.028, 0.004, 0.22, 366.37),
    ("IQV", "IQVIA Holdings Inc.", "Health Care", "Diagnostics & Research", 278.71, 164.60, 2562.57, 0.19, 16255.00, 6171.02, 2080.00, 2819.00, 669.25, 3048.00, 8.05, 14.39, 0.065, 0.020, 0.150, 0.015, 0.28, 100.70),
    ("MTD", "Mettler-Toledo International", "Health Care", "Diagnostics & Research", 1692.35, 20.04, 1495.25, 0.18, 2137.39, 12.82, 51.38, 975.17, 281.58, 1275.71, 44.37, 51.76, 0.060, 0.020, 0.290, 0.020, 0.10, 203.41),
    ("RMD", "ResMed Inc.", "Health Care", "Medical Instruments & Supplies", 247.53, 140.64, 1380.85, 0.19, 825.92, 6421.03, 1469.23, 1805.83, 866.58, 2095.77, 10.43, 13.23, 0.090, 0.025, 0.310, 0.020, 0.12, 38.85),
    ("ALGN", "Align Technology Inc.", "Health Care", "Medical Instruments & Supplies", 153.63, 71.04, 400.21, 0.21, 120.84, 4220.26, 1102.59, 755.70, 161.58, 925.66, 5.75, 12.40, 0.070, 0.030, 0.180, 0.020, 0.20, 57.70),
    ("BIIB", "Biogen Inc.", "Health Care", "Drug Manufacturers - General", 245.89, 147.75, 2877.44, 0.16, 8355.10, 18854.89, 1285.00, 2878.80, 1611.81, 3359.20, 5.63, 16.44, 0.030, 0.025, 0.230, 0.030, 0.15, 68.19),
    ("BAX", "Baxter International Inc.", "Health Care", "Medical Instruments & Supplies", 24.94, 517.00, 1102.32, 0.17, 9667.00, 6206.02, 2150.00, 1319.00, 318.63, 1884.00, 1.31, 2.04, 0.040, 0.020, 0.120, 0.015, 0.40, 22.27),
    ("STE", "STERIS plc", "Health Care", "Medical Devices", 224.51, 97.50, 982.23, 0.19, 2044.50, 7206.72, 482.30, 1288.50, 489.64, 1640.50, 8.18, 12.28, 0.070, 0.020, 0.190, 0.015, 0.32, 61.61),
    ("WST", "West Pharmaceutical Services", "Health Care", "Medical Instruments & Supplies", 392.62, 70.38, 906.05, 0.20, 316.50, 2989.14, 435.80, 662.20, 384.26, 912.20, 7.81, 10.00, 0.065, 0.025, 0.250, 0.020, 0.35, 46.30),
    ("CAH", "Cardinal Health Inc.", "Health Care", "Medical Distribution", 256.81, 231.56, 5685.83, 0.22, 9998.00, -4264.37, 4856.00, 5174.00, 421.50, 4244.00, 7.23, 14.06, 0.080, 0.015, 0.012, 0.002, 0.15, 1077.32),
    ("LH", "Labcorp (Laboratory Corp)", "Health Care", "Diagnostics & Research", 323.22, 81.10, 2002.25, 0.22, 6823.00, 8628.07, 141.80, 1638.40, 746.35, 2319.80, 12.09, 19.78, 0.050, 0.020, 0.110, 0.010, 0.32, 174.02),
    ("MOH", "Molina Healthcare Inc.", "Health Care", "Healthcare Plans", 209.78, 52.20, 989.53, 0.24, 3953.00, 4187.07, 8915.00, 365.00, 145.13, 390.00, 12.20, 9.75, 0.080, 0.020, 0.045, 0.006, 0.15, 828.66),
    ("VTRS", "Viatris Inc.", "Health Care", "Drug Manufacturers - Specialty & Generic", 18.59, 1148.59, 3781.02, 0.16, 13623.70, 14178.21, 1510.50, 2330.80, 1291.85, 4292.50, 1.50, 2.70, 0.020, 0.020, 0.170, 0.020, 0.25, 12.71),
    ("TECH", "Bio-Techne Corporation", "Health Care", "Biotechnology", 72.55, 156.82, 320.22, 0.18, 289.09, 2117.99, 265.48, 292.07, 62.42, 334.11, 1.16, 2.31, 0.070, 0.025, 0.280, 0.020, 0.15, 7.79),
    ("VEEV", "Veeva Systems Inc.", "Health Care", "Health Information Services", 318.16, 161.91, 900.19, 0.19, 151.70, 7434.85, 7242.95, 1665.46, 407.75, 1075.34, 6.10, 10.25, 0.140, 0.025, 0.300, 0.020, 0.10, 21.15),
    ("TFX", "Teleflex Incorporated", "Health Care", "Medical Instruments & Supplies", 132.65, 42.37, 354.50, 0.17, 2936.58, 2904.54, 323.94, 403.20, 223.65, 403.90, 4.46, 10.94, 0.050, 0.020, 0.210, 0.015, 0.20, 51.16),
    ("PODD", "Insulet Corporation", "Health Care", "Medical Devices", 144.31, 69.35, 212.55, 0.18, 948.40, 1422.25, 534.90, 511.20, 274.30, 614.90, 5.34, 7.72, 0.180, 0.040, 0.190, 0.030, 0.45, 43.62),
    # =========================================================================
    # 3. FINANCIALS (45 stocks)
    # =========================================================================
    ("JPM", "JPMorgan Chase & Co.", "Financials", "Banks - Diversified", 335.80, 2655.60, 99940.48, 0.20, 1326255.05, 351327.91, 1881473.94, 79952.38, 6918.96, 104553.11, 23.84, 25.53, 0.070, 0.030, 0.380, 0.030, 0.20, 70.51),
    ("V", "Visa Inc.", "Financials", "Credit Services", 410.34, 1704.11, 33977.20, 0.19, 23858.00, 32156.61, 13792.00, 22580.00, 2176.00, 31094.00, 11.75, 15.02, 0.100, 0.020, 0.670, 0.020, 0.12, 23.40),
    ("MA", "Mastercard Incorporated", "Financials", "Credit Services", 626.24, 869.46, 19179.63, 0.18, 24643.00, 5561.09, 11609.00, 17437.00, 475.75, 22201.00, 18.18, 23.07, 0.110, 0.025, 0.580, 0.020, 0.14, 39.27),
    ("BAC", "Bank of America Corp.", "Financials", "Banks - Diversified", 51.16, 6992.75, 38494.17, 0.18, 745580.99, 274500.34, 991028.97, 34768.93, 3476.89, 41598.54, 4.19, 5.19, 0.050, 0.030, 0.300, 0.030, 0.22, 15.94),
    ("WFC", "Wells Fargo & Company", "Financials", "Banks - Diversified", 83.19, 3001.64, 32763.18, 0.19, 441562.01, 158660.63, 601165.00, 29914.21, 2991.42, 36324.40, 7.09, 8.01, 0.045, 0.030, 0.290, 0.025, 0.20, 27.13),
    ("MS", "Morgan Stanley", "Financials", "Capital Markets", 186.35, 1570.57, 24903.92, 0.21, 607495.98, 106485.97, 739076.01, 21984.15, 2404.52, 27136.68, 12.61, 13.64, 0.065, 0.030, 0.260, 0.025, 0.18, 51.26),
    ("GS", "The Goldman Sachs Group", "Financials", "Capital Markets", 903.48, 291.17, 28323.38, 0.21, 839000.00, 108387.39, 1008999.99, 25455.19, 3226.71, 30833.05, 69.55, 73.85, 0.075, 0.040, 0.280, 0.035, 0.18, 235.47),
    ("BLK", "BlackRock Inc.", "Financials", "Asset Management", 1156.10, 154.87, 8231.92, 0.21, 14968.00, 57565.52, 13843.00, 7505.57, 581.08, 12006.00, 43.92, 64.83, 0.080, 0.025, 0.360, 0.020, 0.15, 183.98),
    ("SPGI", "S&P Global Inc.", "Financials", "Financial Data & Stock Exchanges", 451.97, 294.80, 4766.87, 0.21, 15748.00, 31500.85, 4134.00, 5729.00, 280.75, 8143.00, 16.43, 20.17, 0.090, 0.020, 0.440, 0.020, 0.12, 53.79),
    ("C", "Citigroup Inc.", "Financials", "Banks - Diversified", 123.70, 1677.44, 31792.06, 0.22, 817476.99, 193930.14, 1401245.01, 27938.47, 4238.94, 35645.64, 10.26, 13.05, 0.040, 0.030, 0.220, 0.030, 0.25, 48.41),
    ("AXP", "American Express Company", "Financials", "Credit Services", 325.59, 675.31, 13284.55, 0.21, 59092.00, 34295.61, 45752.00, 18475.00, 1779.18, 14826.50, 16.48, 20.15, 0.090, 0.025, 0.200, 0.020, 0.20, 103.45),
    ("PGR", "The Progressive Corp.", "Financials", "Insurance - Property & Casualty", 224.58, 580.40, 7697.30, 0.21, 8389.00, 34538.44, 2125.00, 8331.19, 407.50, 15336.00, 19.85, 16.30, 0.120, 0.030, 0.140, 0.020, 0.10, 157.05),
    ("CB", "Chubb Limited", "Financials", "Insurance - Property & Casualty", 358.74, 385.80, 14526.44, 0.18, 0.00, 72550.05, 3010.00, 16168.56, 694.74, 14197.00, 28.53, 29.33, 0.070, 0.020, 0.210, 0.020, 0.12, 159.54),
    ("MRSH", "Marsh & McLennan Companies", "Financials", "Insurance Brokers", 193.72, 477.21, 5113.73, 0.24, 22332.00, 14730.56, 1842.00, 4474.00, 152.62, 7885.00, 8.36, 11.45, 0.075, 0.020, 0.240, 0.015, 0.15, 59.04),
    ("AON", "Aon plc", "Financials", "Insurance Brokers", 301.89, 212.13, 3240.63, 0.19, 15874.00, 9603.77, 1097.00, 3531.00, 340.13, 5900.00, 18.14, 20.21, 0.070, 0.020, 0.270, 0.015, 0.12, 81.89),
    ("MCO", "Moody's Corporation", "Financials", "Financial Data & Stock Exchanges", 482.58, 173.18, 2624.91, 0.22, 7492.00, 3024.95, 1621.00, 3329.00, 803.75, 4047.00, 15.76, 18.82, 0.090, 0.020, 0.420, 0.020, 0.12, 46.61),
    ("KKR", "KKR & Co. Inc.", "Financials", "Asset Management", 92.11, 897.64, 5471.88, 0.20, 56163.96, 28499.93, 47556.55, 2488.48, 222.93, 5978.54, 3.13, 7.22, 0.120, 0.040, 0.320, 0.030, 0.15, 28.95),
    ("CME", "CME Group Inc.", "Financials", "Financial Data & Stock Exchanges", 304.00, 359.58, 5020.18, 0.23, 3425.10, 26675.87, 2329.50, 4741.28, 167.34, 4942.40, 12.20, 13.14, 0.060, 0.020, 0.620, 0.020, 0.08, 19.36),
    ("ICE", "Intercontinental Exchange", "Financials", "Financial Data & Stock Exchanges", 160.87, 561.39, 4071.40, 0.22, 20527.00, 29572.02, 1067.00, 5514.00, 1880.37, 6714.00, 7.09, 8.88, 0.070, 0.020, 0.480, 0.020, 0.15, 18.59),
    ("AJG", "Arthur J. Gallagher & Co.", "Financials", "Insurance Brokers", 265.11, 256.34, 1773.62, 0.23, 14106.00, 23720.77, 1386.00, 2449.00, 366.70, 4288.00, 6.03, 14.81, 0.100, 0.025, 0.200, 0.015, 0.15, 58.84),
    ("USB", "U.S. Bancorp", "Financials", "Banks - Regional", 59.84, 1558.05, 10620.95, 0.20, 73040.00, 59618.84, 49523.00, 9196.19, 1269.33, 12434.29, 5.14, 5.82, 0.040, 0.025, 0.300, 0.025, 0.25, 17.94),
    ("PNC", "The PNC Financial Services", "Financials", "Banks - Regional", 225.50, 398.94, 8777.69, 0.19, 79757.00, 62620.19, 6525.00, 7912.28, 1013.76, 10137.61, 18.78, 21.37, 0.045, 0.025, 0.320, 0.025, 0.22, 62.28),
    ("TRV", "The Travelers Companies", "Financials", "Insurance - Property & Casualty", 402.68, 208.58, 8121.28, 0.20, 9813.00, 29515.03, 6180.00, 10677.00, 541.42, 11520.00, 38.03, 31.01, 0.070, 0.025, 0.120, 0.020, 0.10, 229.49),
    ("AFL", "Aflac Incorporated", "Financials", "Insurance - Life", 120.94, 501.34, 6047.00, 0.21, 16176.00, 30257.07, 8935.00, 2647.00, 167.97, 6065.00, 9.30, 7.62, 0.030, 0.020, 0.280, 0.020, 0.08, 34.96),
    ("COF", "Capital One Financial", "Financials", "Credit Services", 207.59, 613.48, 8740.63, 0.21, 49774.00, 110481.87, 48889.00, 10652.64, 1638.87, 11472.08, 16.32, 23.82, 0.060, 0.030, 0.240, 0.030, 0.22, 78.74),
    ("PRU", "Prudential Financial Inc.", "Financials", "Insurance - Life", 115.47, 345.00, 4901.58, 0.19, 56685.00, 31557.50, 39136.00, 10969.00, 3441.25, 5206.00, 11.04, 14.07, 0.040, 0.020, 0.100, 0.015, 0.10, 187.18),
    ("MET", "MetLife Inc.", "Financials", "Insurance - Life", 102.26, 635.48, 6701.50, 0.20, 50311.00, 27343.30, 27317.00, 15558.00, 36512.00, 6040.00, 5.22, 11.16, 0.045, 0.020, 0.080, 0.015, 0.10, 121.35),
    ("ALL", "The Allstate Corporation", "Financials", "Insurance - Property & Casualty", 253.74, 252.86, 6079.19, 0.21, 7497.00, 31554.40, 5715.00, 12469.00, 541.84, 17116.00, 49.98, 28.11, 0.080, 0.030, 0.080, 0.020, 0.12, 269.76),
    ("HIG", "The Hartford Financial Services", "Financials", "Insurance - Diversified", 137.02, 270.87, 4252.34, 0.21, 4384.00, 19245.73, 3991.00, 5880.00, 372.50, 5586.00, 14.13, 13.78, 0.060, 0.020, 0.150, 0.015, 0.08, 105.75),
    ("AIG", "American International Group", "Financials", "Insurance - Diversified", 82.23, 522.89, 5276.79, 0.21, 9127.00, 40464.61, 10495.00, 3850.00, 351.79, 8146.00, 5.46, 8.81, 0.035, 0.020, 0.110, 0.020, 0.10, 49.49),
    ("ACGL", "Arch Capital Group Ltd.", "Financials", "Insurance - Diversified", 101.55, 341.23, 4296.35, 0.14, 4286.00, 23312.09, 4464.00, 6100.00, 1797.87, 5565.00, 12.78, 9.80, 0.100, 0.030, 0.280, 0.025, 0.08, 53.99),
    ("FITB", "Fifth Third Bancorp", "Financials", "Banks - Regional", 53.38, 906.89, 3718.61, 0.20, 18138.00, 31143.60, 5846.00, 3358.74, 455.83, 4318.38, 2.98, 4.95, 0.040, 0.025, 0.320, 0.025, 0.20, 12.27),
    ("MTB", "M&T Bank Corporation", "Financials", "Banks - Regional", 222.00, 144.42, 4487.23, 0.22, 20021.00, 25265.91, 16138.00, 3778.72, 330.64, 4959.57, 18.92, 21.08, 0.040, 0.020, 0.380, 0.025, 0.15, 63.97),
    ("TFC", "Truist Financial Corporation", "Financials", "Banks - Regional", 48.37, 1221.63, 5830.31, 0.21, 65788.00, 57142.79, 54593.00, 5182.50, 777.37, 7341.87, 3.88, 4.94, 0.035, 0.025, 0.260, 0.025, 0.20, 14.77),
    ("APO", "Apollo Global Management", "Financials", "Asset Management", 113.48, 590.54, 6265.15, 0.20, 41884.00, 20103.86, 47616.00, 9473.00, 282.94, 6871.45, 2.79, 10.65, 0.110, 0.035, 0.280, 0.030, 0.15, 60.07),
    ("STT", "State Street Corporation", "Financials", "Asset Management", 169.29, 274.70, 5673.50, 0.18, 26446.00, 24824.25, 151296.00, 5124.45, 768.67, 6588.58, 12.24, 15.51, 0.045, 0.020, 0.250, 0.020, 0.20, 55.90),
    ("AMP", "Ameriprise Financial Inc.", "Financials", "Asset Management", 493.16, 88.33, 3670.47, 0.20, 4302.00, 6357.70, 10299.00, 8218.00, 5314.87, 3952.81, 41.42, 51.50, 0.070, 0.020, 0.260, 0.020, 0.10, 210.94),
    ("WTW", "Willis Towers Watson", "Financials", "Insurance Brokers", 324.26, 92.87, 1895.03, 0.19, 7101.00, 7677.07, 1661.00, 1923.00, 507.38, 2816.00, 16.16, 22.93, 0.060, 0.020, 0.180, 0.015, 0.15, 105.78),
    ("BRO", "Brown & Brown Inc.", "Financials", "Insurance Brokers", 72.95, 334.61, 844.33, 0.24, 8066.00, 12758.69, 918.00, 1520.00, 64.17, 2892.00, 3.17, 4.83, 0.090, 0.020, 0.280, 0.015, 0.12, 20.10),
    ("NTRS", "Northern Trust Corporation", "Financials", "Asset Management", 166.85, 182.96, 3730.39, 0.22, 15964.00, 12540.88, 2096.20, 3052.13, 525.65, 4069.51, 12.75, 13.01, 0.050, 0.020, 0.280, 0.020, 0.18, 50.51),
    ("RJF", "Raymond James Financial", "Financials", "Asset Management", 156.67, 192.10, 3232.87, 0.22, 6084.00, 12697.43, 16020.00, 1639.00, 261.12, 3605.90, 11.47, 14.27, 0.070, 0.025, 0.210, 0.020, 0.15, 77.55),
    ("HBAN", "Huntington Bancshares", "Financials", "Banks - Regional", 15.84, 2020.41, 2406.08, 0.20, 22610.00, 29742.53, 16607.00, 3062.00, 290.73, 2807.09, 1.30, 1.76, 0.040, 0.020, 0.320, 0.020, 0.20, 5.32),
    ("RF", "Regions Financial Corporation", "Financials", "Banks - Regional", 28.45, 851.93, 3161.11, 0.21, 10482.00, 16515.51, 10329.00, 2674.79, 389.06, 3525.85, 2.55, 2.85, 0.040, 0.020, 0.340, 0.020, 0.20, 8.52),
    ("KEY", "KeyCorp", "Financials", "Banks - Regional", 21.24, 1067.13, 2222.79, 0.20, 16707.00, 15967.44, 2465.00, 1852.33, 308.72, 2716.74, 1.72, 2.17, 0.035, 0.025, 0.280, 0.020, 0.20, 7.03),
    ("CFG", "Citizens Financial Group", "Financials", "Banks - Regional", 65.80, 421.18, 3715.76, 0.21, 17832.00, 22949.50, 13558.00, 2941.65, 479.95, 4335.06, 4.59, 6.49, 0.040, 0.025, 0.310, 0.020, 0.20, 19.77),
    # =========================================================================
    # 4. CONSUMER DISCRETIONARY (42 stocks)
    # =========================================================================
    ("AMZN", "Amazon.com Inc.", "Consumer Discretionary", "Internet Retail", 253.70, 10786.31, 65975.60, 0.19, 251635.01, 551784.66, 122988.00, 161402.99, 158183.87, 168911.99, 12.43, 10.45, 0.120, 0.030, 0.085, 0.020, 0.45, 72.33),
    ("TSLA", "Tesla Inc.", "Consumer Discretionary", "Auto Manufacturers", 386.72, 3949.55, 14216.47, 0.15, 16080.00, 86483.24, 43524.00, 18685.00, 13849.00, 10755.00, 1.08, 2.18, 0.150, 0.080, 0.090, 0.030, 0.50, 32.05),
    ("HD", "The Home Depot Inc.", "Consumer Discretionary", "Home Improvement Retail", 321.06, 997.69, 17397.73, 0.23, 63188.00, 16611.53, 2085.00, 18779.00, 8016.38, 24648.00, 14.29, 15.99, 0.040, 0.020, 0.145, 0.010, 0.20, 170.20),
    ("MCD", "McDonald's Corporation", "Consumer Discretionary", "Restaurants", 248.53, 707.64, 9661.35, 0.21, 54604.00, -3747.94, 822.00, 11347.00, 5084.63, 14930.00, 12.31, 13.75, 0.055, 0.020, 0.450, 0.020, 0.25, 38.96),
    ("NKE", "NIKE Inc.", "Consumer Discretionary", "Footwear & Accessories", 37.74, 1203.92, 3047.89, 0.16, 11125.00, 12355.84, 8368.00, 2781.00, 1014.12, 4893.00, 2.08, 1.59, 0.040, 0.030, 0.130, 0.015, 0.18, 30.98),
    ("LOW", "Lowe's Companies Inc.", "Consumer Discretionary", "Home Improvement Retail", 200.00, 561.05, 8805.97, 0.23, 42031.00, -10820.90, 3172.00, 9263.00, 4647.62, 12729.00, 11.83, 13.00, 0.035, 0.020, 0.135, 0.010, 0.22, 161.78),
    ("BKNG", "Booking Holdings Inc.", "Consumer Discretionary", "Travel Services", 164.09, 751.38, 1550.00, 0.18, 20924.00, -525.00, 17214.00, 9859.00, 2133.13, 10413.00, 9.02, 12.37, 0.090, 0.030, 0.290, 0.020, 0.10, 35.64),
    ("SBUX", "Starbucks Corporation", "Consumer Discretionary", "Restaurants", 100.17, 1140.00, 5547.88, 0.22, 22453.10, -8013.60, 3610.30, 4985.90, 1920.36, 5642.30, 1.73, 3.13, 0.050, 0.025, 0.150, 0.020, 0.35, 33.67),
    ("TJX", "The TJX Companies Inc.", "Consumer Discretionary", "Apparel Retail", 146.59, 1099.97, 7390.07, 0.24, 14317.00, 10638.95, 6004.00, 8034.00, 3635.87, 8903.00, 5.40, 5.77, 0.065, 0.020, 0.110, 0.010, 0.25, 56.26),
    ("ABNB", "Airbnb Inc.", "Consumer Discretionary", "Travel Services", 175.30, 419.53, 3718.48, 0.14, 2496.00, 5545.76, 12069.00, 4860.00, 1653.13, 2761.00, 4.39, 6.20, 0.110, 0.030, 0.280, 0.025, 0.08, 21.88),
    ("ORLY", "O'Reilly Automotive", "Consumer Discretionary", "Auto Parts", 89.97, 808.96, 850.00, 0.23, 9587.43, -450.00, 262.18, 3289.44, 1718.71, 4169.74, 3.15, 3.66, 0.060, 0.015, 0.210, 0.010, 0.28, 22.14),
    ("MAR", "Marriott International", "Consumer Discretionary", "Lodging", 401.85, 260.77, 6288.49, 0.23, 17774.00, 1303.71, 462.00, 3728.00, 1667.62, 4814.00, 9.66, 13.16, 0.060, 0.020, 0.170, 0.015, 0.15, 27.59),
    ("GM", "General Motors Company", "Consumer Discretionary", "Auto Manufacturers", 77.66, 877.45, 19974.28, 0.18, 128743.00, 63198.45, 27805.00, 23415.00, 17896.95, 17771.00, 4.57, 14.81, 0.040, 0.030, 0.075, 0.015, 0.55, 207.49),
    ("F", "Ford Motor Company", "Consumer Discretionary", "Auto Manufacturers", 12.02, 3916.74, 7727.14, 0.18, 163296.00, 35086.19, 22120.00, 16947.00, 24887.25, 7643.00, 1.18, 1.92, 0.035, 0.030, 0.045, 0.015, 0.60, 47.15),
    ("AZO", "AutoZone Inc.", "Consumer Discretionary", "Auto Parts", 3187.97, 16.17, 3553.47, 0.21, 12864.77, -4873.33, 326.12, 3248.89, 994.97, 4342.15, 152.55, 192.85, 0.060, 0.015, 0.200, 0.010, 0.26, 1234.06),
    ("LULU", "Lululemon Athletica", "Consumer Discretionary", "Apparel Retail", 98.34, 105.59, 831.04, 0.28, 2141.13, 4529.99, 1389.74, 1982.03, 833.52, 2383.93, 12.15, 8.65, 0.080, 0.030, 0.230, 0.020, 0.28, 95.64),
    ("CMG", "Chipotle Mexican Grill", "Consumer Discretionary", "Restaurants", 28.25, 1265.42, 870.72, 0.23, 5419.20, 2195.50, 677.86, 2327.53, 1211.06, 2275.02, 1.09, 1.37, 0.130, 0.020, 0.170, 0.015, 0.30, 9.51),
    ("ROST", "Ross Stores Inc.", "Consumer Discretionary", "Apparel Retail", 236.61, 320.78, 3735.95, 0.24, 4739.15, 6766.56, 4288.12, 3660.57, 1658.53, 3657.10, 8.27, 8.97, 0.060, 0.020, 0.120, 0.010, 0.32, 76.74),
    ("HLT", "Hilton Worldwide Holdings", "Consumer Discretionary", "Lodging", 359.83, 225.06, 4233.29, 0.24, 14023.00, -4233.29, 1009.00, 2109.00, 715.12, 3088.00, 6.82, 10.42, 0.070, 0.020, 0.260, 0.020, 0.12, 22.14),
    ("DHI", "D.R. Horton Inc.", "Consumer Discretionary", "Residential Construction", 144.56, 279.70, 5228.77, 0.22, 7187.90, 23732.09, 2078.70, 3352.60, 938.70, 4127.40, 10.49, 11.26, 0.070, 0.040, 0.180, 0.020, 0.15, 115.16),
    ("LEN", "Lennar Corporation", "Consumer Discretionary", "Residential Construction", 80.69, 207.88, 2482.77, 0.23, 6118.69, 18838.16, 1200.95, 937.30, 93.10, 1982.13, 5.28, 5.22, 0.065, 0.040, 0.160, 0.020, 0.15, 131.13),
    ("YUM", "Yum! Brands Inc.", "Consumer Discretionary", "Restaurants", 151.92, 272.90, 2680.94, 0.20, 13414.00, -8713.06, 683.00, 2083.00, 1249.75, 3068.00, 7.94, 6.87, 0.050, 0.015, 0.330, 0.020, 0.15, 31.43),
    ("RCL", "Royal Caribbean Cruises", "Consumer Discretionary", "Travel Services", 289.37, 267.45, 5425.69, 0.10, 23518.00, 10236.19, 876.00, 6786.00, 8302.25, 6926.00, 16.20, 20.39, 0.090, 0.040, 0.250, 0.030, 0.65, 69.06),
    ("CCL", "Carnival Corporation", "Consumer Discretionary", "Travel Services", 27.55, 1344.61, 3789.95, 0.05, 25162.00, 14110.34, 1220.00, 6821.00, 5013.38, 7292.00, 2.27, 2.57, 0.070, 0.040, 0.130, 0.025, 0.55, 20.29),
    ("NVR", "NVR Inc.", "Consumer Discretionary", "Residential Construction", 5920.36, 2.68, 1345.54, 0.23, 1090.25, 3391.20, 1093.74, 1066.59, 148.28, 1536.61, 384.93, 392.74, 0.060, 0.030, 0.200, 0.020, 0.05, 3445.66),
    ("EBAY", "eBay Inc.", "Consumer Discretionary", "Internet Retail", 121.94, 445.00, 4558.50, 0.19, 7138.00, 4664.94, 3307.00, 3036.00, 1456.38, 3096.00, 4.75, 6.72, 0.035, 0.015, 0.230, 0.015, 0.22, 26.68),
    ("DRI", "Darden Restaurants", "Consumer Discretionary", "Restaurants", 215.47, 113.14, 1879.10, 0.14, 8590.10, 2065.54, 220.50, 1782.50, 987.71, 2142.30, 10.30, 12.40, 0.055, 0.020, 0.130, 0.010, 0.38, 116.51),
    ("GPC", "Genuine Parts Company", "Consumer Discretionary", "Auto Parts", 125.80, 137.86, 1594.65, 0.24, 6824.14, 4648.77, 763.15, 1196.72, 326.26, 2003.43, 0.26, 8.21, 0.040, 0.015, 0.080, 0.010, 0.35, 183.52),
    ("TSCO", "Tractor Supply Company", "Consumer Discretionary", "Specialty Retail", 30.82, 521.04, 375.00, 0.23, 6544.98, 2627.61, 231.59, 1285.82, 1182.65, 1931.48, 1.92, 2.04, 0.050, 0.020, 0.100, 0.010, 0.45, 29.89),
    ("ULTA", "Ulta Beauty Inc.", "Consumer Discretionary", "Specialty Retail", 620.21, 42.76, 2745.72, 0.24, 2524.03, 2640.79, 213.45, 1567.83, 653.74, 1934.35, 27.44, 32.09, 0.045, 0.025, 0.150, 0.015, 0.30, 294.80),
    ("PHM", "PulteGroup Inc.", "Consumer Discretionary", "Residential Construction", 117.34, 190.49, 3316.13, 0.23, 2481.01, 13208.90, 1337.08, 1626.32, 547.81, 2753.78, 9.80, 10.71, 0.065, 0.035, 0.220, 0.020, 0.10, 85.01),
    ("DECK", "Deckers Outdoor Corp.", "Consumer Discretionary", "Footwear & Accessories", 86.09, 136.18, 599.36, 0.21, 472.33, 2292.49, 1602.59, 1193.71, 322.29, 1326.98, 7.07, 8.33, 0.120, 0.030, 0.240, 0.020, 0.12, 38.73),
    ("GRMN", "Garmin Ltd.", "Consumer Discretionary", "Scientific & Technical Instruments", 290.57, 192.85, 2203.76, 0.15, 226.86, 9026.27, 2666.19, 1978.94, 935.29, 2311.47, 9.69, 11.13, 0.080, 0.020, 0.230, 0.020, 0.15, 39.84),
    ("EXPE", "Expedia Group Inc.", "Consumer Discretionary", "Travel Services", 292.02, 114.50, 2689.66, 0.22, 5690.00, 1153.57, 7127.00, 5216.00, 1781.63, 2890.00, 16.01, 24.54, 0.060, 0.025, 0.110, 0.015, 0.45, 128.58),
    ("BBY", "Best Buy Co. Inc.", "Consumer Discretionary", "Specialty Retail", 96.13, 209.73, 1569.47, 0.23, 4141.00, 3172.76, 2410.00, 2475.00, 1071.63, 2618.00, 6.01, 7.22, 0.020, 0.015, 0.040, 0.008, 0.40, 200.48),
    ("KMX", "CarMax Inc.", "Consumer Discretionary", "Auto & Truck Dealerships", 51.89, 141.94, 561.87, 0.24, 18070.31, 6304.96, 170.52, 1599.33, 967.03, 1127.09, 2.11, 3.57, 0.040, 0.030, 0.035, 0.008, 0.40, 206.22),
    ("BWA", "BorgWarner Inc.", "Consumer Discretionary", "Auto Parts", 56.02, 203.67, 1948.52, 0.22, 4065.00, 5620.99, 2448.00, 1725.00, 658.75, 2036.00, 2.00, 5.91, 0.045, 0.025, 0.090, 0.015, 0.55, 68.98),
    ("TPR", "Tapestry Inc.", "Consumer Discretionary", "Luxury Goods", 115.48, 198.44, 3135.20, 0.20, 3956.10, 685.40, 1152.00, 1978.50, 578.57, 2023.50, 7.27, 8.88, 0.040, 0.020, 0.180, 0.020, 0.20, 39.24),
    ("HAS", "Hasbro Inc.", "Consumer Discretionary", "Leisure", 114.72, 141.04, 998.97, 0.21, 3878.20, 541.05, 1378.20, 1288.20, 600.05, 1300.20, 5.59, 6.78, 0.035, 0.030, 0.140, 0.020, 0.20, 35.32),
    ("WHR", "Whirlpool Corporation", "Consumer Discretionary", "Furnishings, Fixtures & Appliances", 27.26, 65.20, 277.65, 0.22, 8057.00, 3944.04, 1239.00, 225.00, 710.38, 766.00, 3.04, 2.89, 0.020, 0.020, 0.065, 0.015, 0.45, 251.62),
    ("POOL", "Pool Corporation", "Consumer Discretionary", "Industrial Distribution", 190.26, 36.34, 361.39, 0.24, 1695.17, 1260.01, 35.03, 366.65, 153.72, 642.59, 10.89, 11.72, 0.040, 0.020, 0.120, 0.015, 0.10, 147.47),
    ("RL", "Ralph Lauren Corporation", "Consumer Discretionary", "Apparel Manufacturing", 383.02, 37.70, 1556.02, 0.22, 3003.90, 1721.58, 1941.60, 1317.40, 437.31, 1593.20, 15.87, 20.83, 0.050, 0.020, 0.120, 0.015, 0.25, 137.48),
    # =========================================================================
    # 5. COMMUNICATION SERVICES (22 stocks - complete sector)
    # =========================================================================
    ("GOOGL", "Alphabet Inc. (Class A)", "Communication Services", "Internet Content & Information", 328.06, 5867.16, 195604.78, 0.16, 120791.00, 298614.76, 242473.99, 185675.01, 163010.00, 173164.00, 19.93, 15.35, 0.130, 0.030, 0.300, 0.020, 0.35, 36.84),
    ("GOOG", "Alphabet Inc. (Class C)", "Communication Services", "Internet Content & Information", 324.26, 5527.00, 191484.47, 0.16, 120791.00, 281302.19, 242473.99, 185675.01, 163010.00, 173164.00, 19.93, 15.35, 0.130, 0.030, 0.300, 0.020, 0.35, 36.84),
    ("META", "Meta Platforms Inc.", "Communication Services", "Internet Content & Information", 658.92, 2205.13, 63065.32, 0.17, 112318.00, 189347.77, 90260.00, 130301.00, 108747.38, 109655.00, 29.31, 34.95, 0.180, 0.050, 0.380, 0.030, 0.40, 90.25),
    ("NFLX", "Netflix Inc.", "Communication Services", "Entertainment", 66.08, 4163.94, 2050.00, 0.15, 15132.39, 29493.18, 8222.95, 12307.94, 100.00, 15957.06, 3.46, 3.77, 0.140, 0.030, 0.230, 0.020, 0.15, 11.86),
    ("DIS", "The Walt Disney Company", "Communication Services", "Entertainment", 112.23, 1726.69, 13388.43, 0.22, 46041.00, 109820.74, 5185.00, 16989.00, 12128.62, 20963.00, 4.85, 7.50, 0.060, 0.030, 0.130, 0.020, 0.35, 55.80),
    ("CMCSA", "Comcast Corporation", "Communication Services", "Telecom Services", 22.91, 3539.19, 13249.16, 0.24, 90381.00, 89580.49, 7661.00, 32517.00, 19819.37, 34073.00, 3.10, 3.57, 0.035, 0.020, 0.200, 0.015, 0.42, 34.53),
    ("T", "AT&T Inc.", "Communication Services", "Telecom Services", 22.46, 6852.39, 25241.74, 0.21, 178147.00, 107047.97, 10767.00, 40432.00, 26881.63, 45966.00, 1.87, 2.59, 0.025, 0.015, 0.200, 0.015, 0.45, 18.48),
    ("VZ", "Verizon Communications", "Communication Services", "Telecom Services", 44.67, 4154.78, 31118.43, 0.23, 193646.00, 103919.24, 1796.00, 38799.00, 21332.38, 51082.00, 3.84, 5.27, 0.025, 0.015, 0.230, 0.015, 0.46, 33.01),
    ("TMUS", "T-Mobile US Inc.", "Communication Services", "Telecom Services", 157.19, 1072.67, 12945.06, 0.22, 120427.00, 56152.21, 2825.00, 28833.00, 17497.00, 34371.00, 9.57, 14.42, 0.065, 0.025, 0.210, 0.020, 0.40, 83.42),
    ("CHTR", "Charter Communications", "Communication Services", "Telecom Services", 109.95, 114.46, 3887.73, 0.23, 96710.00, 16266.94, 509.00, 16470.00, 14271.62, 21815.00, 38.41, 45.85, 0.030, 0.020, 0.230, 0.015, 0.80, 429.65),
    ("SPOT", "Spotify Technology S.A.", "Communication Services", "Internet Content & Information", 570.17, 205.58, 2371.59, 0.18, 466.00, 9412.87, 6985.00, 3337.00, 1795.62, 2683.00, 17.40, 17.20, 0.150, 0.035, 0.140, 0.025, 0.08, 88.01),
    ("PINS", "Pinterest Inc.", "Communication Services", "Internet Content & Information", 23.20, 492.20, 924.78, 0.18, 1196.64, 2518.58, 1274.90, 1333.77, 137.33, 316.56, 0.34, 2.39, 0.140, 0.035, 0.220, 0.025, 0.10, 7.16),
    ("TTWO", "Take-Two Interactive", "Communication Services", "Electronic Gaming & Multimedia", 210.81, 186.98, 889.78, 0.17, 2944.70, 3607.97, 1826.60, 500.20, 246.40, 766.50, -2.87, 10.32, 0.140, 0.060, 0.120, 0.040, 0.15, 36.09),
    ("OMC", "Omnicom Group Inc.", "Communication Services", "Advertising Agencies", 80.51, 274.35, 2397.32, 0.25, 11411.20, 9661.92, 3336.20, 2582.50, 139.84, 3676.50, 0.38, 11.61, 0.045, 0.020, 0.160, 0.010, 0.08, 88.95),
    ("LYV", "Live Nation Entertainment", "Communication Services", "Entertainment", 174.38, 232.96, 1776.09, 0.22, 11282.71, 83.17, 9071.95, 2608.70, 913.67, 1550.79, 3.39, 1.90, 0.090, 0.035, 0.050, 0.015, 0.25, 113.06),
    ("FOXA", "Fox Corporation (Class A)", "Communication Services", "Entertainment", 67.18, 201.42, 3424.22, 0.23, 7568.00, 5582.09, 4205.00, 1970.00, 1414.63, 3882.00, 3.84, 5.86, 0.040, 0.020, 0.150, 0.015, 0.22, 39.73),
    ("FOX", "Fox Corporation (Class B)", "Communication Services", "Entertainment", 59.75, 220.25, 3267.58, 0.23, 7568.00, 6103.75, 4205.00, 1970.00, 1414.63, 3882.00, 3.84, 6.13, 0.040, 0.020, 0.150, 0.015, 0.22, 39.73),
    ("NWSA", "News Corporation (Class A)", "Communication Services", "Entertainment", 30.82, 359.34, 1219.50, 0.22, 2915.00, 5637.61, 2101.00, 1231.00, 185.88, 1338.00, 1.03, 1.51, 0.040, 0.020, 0.110, 0.015, 0.35, 16.22),
    ("NWS", "News Corporation (Class B)", "Communication Services", "Entertainment", 33.71, 179.39, 1301.09, 0.22, 2915.00, 2814.53, 2101.00, 1231.00, 185.88, 1338.00, 1.03, 1.51, 0.040, 0.020, 0.110, 0.015, 0.35, 16.22),
    ("RBLX", "Roblox Corporation", "Communication Services", "Electronic Gaming & Multimedia", 53.66, 669.99, 523.51, 0.15, 1836.00, 142.71, 3014.00, 2100.36, 624.00, 785.27, 0.65, 1.16, 0.200, 0.045, 0.160, 0.030, 0.20, 8.04),
    ("MTCH", "Match Group Inc.", "Communication Services", "Internet Content & Information", 45.95, 233.27, 1118.36, 0.18, 3668.24, -218.81, 583.81, 1207.62, 276.96, 1188.93, 2.82, 4.58, 0.060, 0.025, 0.270, 0.020, 0.08, 14.91),
    ("PARA", "Paramount Global", "Communication Services", "Software - Application", 0.54, 4.36, 450.00, 0.20, 6.77, 19.81, 0.65, 525.00, 102.50, 600.00, 0.20, 0.35, 0.030, 0.030, 0.060, 0.020, 0.20, 14.40),
    # =========================================================================
    # 6. INDUSTRIALS (45 stocks)
    # =========================================================================
    ("CAT", "Caterpillar Inc.", "Industrials", "Farm & Heavy Construction Machinery", 716.07, 459.67, 25620.01, 0.22, 45146.00, 19395.06, 5945.00, 13569.00, 8520.00, 16251.00, 23.23, 32.59, 0.060, 0.040, 0.210, 0.025, 0.25, 160.78),
    ("GE", "GE Aerospace", "Industrials", "Aerospace & Defense", 289.34, 1037.56, 10792.72, 0.20, 19326.00, 17592.91, 8764.00, 9451.00, 3802.12, 11652.00, 8.48, 9.27, 0.090, 0.030, 0.170, 0.020, 0.22, 50.43),
    ("UNP", "Union Pacific Corporation", "Industrials", "Railroads", 292.83, 594.08, 11878.04, 0.23, 31169.00, 20677.39, 2114.00, 10263.00, 5542.25, 12884.00, 12.34, 14.25, 0.045, 0.020, 0.400, 0.015, 0.35, 42.86),
    ("DE", "Deere & Company", "Industrials", "Farm & Heavy Construction Machinery", 632.84, 269.63, 15813.25, 0.22, 64578.00, 27990.08, 6940.00, 7245.00, 2728.75, 8600.00, 17.99, 22.78, 0.050, 0.060, 0.200, 0.030, 0.25, 177.41),
    ("RTX", "RTX Corporation", "Industrials", "Aerospace & Defense", 192.01, 1347.76, 12235.93, 0.18, 38874.00, 69022.74, 9173.00, 12435.00, 4315.13, 16707.00, 6.15, 8.02, 0.075, 0.025, 0.110, 0.015, 0.35, 71.16),
    ("HON", "Honeywell International", "Industrials", "Conglomerates", 209.19, 316.94, 8091.31, 0.20, 34955.00, 18536.87, 9196.00, 5118.00, 2507.63, 8512.00, 27.09, 9.81, 0.055, 0.020, 0.220, 0.015, 0.18, 119.90),
    ("BA", "The Boeing Company", "Industrials", "Aerospace & Defense", 191.21, 790.37, 2607.41, 0.15, 48362.00, 6098.50, 19295.00, 3639.00, 2607.41, 5959.79, 2.80, 3.76, 0.100, 0.080, 0.060, 0.040, 0.50, 120.99),
    ("LMT", "Lockheed Martin Corp.", "Industrials", "Aerospace & Defense", 586.63, 230.79, 8839.63, 0.15, 20538.00, 8798.21, 3791.00, 10402.00, 4839.37, 9680.00, 27.13, 32.64, 0.050, 0.020, 0.130, 0.010, 0.20, 333.75),
    ("ETN", "Eaton Corporation plc", "Industrials", "Specialty Industrial Machinery", 375.11, 388.40, 4527.19, 0.16, 21326.00, 20253.89, 695.00, 4950.00, 1843.88, 6639.00, 9.83, 16.30, 0.090, 0.025, 0.180, 0.015, 0.22, 77.29),
    ("UPS", "United Parcel Service", "Industrials", "Integrated Freight & Logistics", 100.84, 749.35, 6951.85, 0.22, 28673.00, 13267.23, 4653.00, 8867.00, 3273.00, 12084.00, 5.38, 8.06, 0.040, 0.020, 0.100, 0.015, 0.45, 105.86),
    ("PH", "Parker-Hannifin Corp.", "Industrials", "Specialty Industrial Machinery", 908.71, 126.11, 5463.76, 0.22, 8733.00, 15405.51, 501.00, 4364.00, 1402.25, 5664.00, 28.48, 39.75, 0.060, 0.020, 0.190, 0.015, 0.15, 170.22),
    ("ITW", "Illinois Tool Works", "Industrials", "Specialty Industrial Machinery", 272.40, 284.80, 4645.58, 0.23, 9694.00, 2894.14, 839.00, 3330.00, 897.00, 4806.00, 11.03, 12.34, 0.040, 0.015, 0.270, 0.015, 0.12, 57.05),
    ("WM", "Waste Management Inc.", "Industrials", "Waste Management", 236.52, 399.72, 4531.46, 0.24, 23356.00, 9918.93, 557.00, 6517.00, 4168.63, 7774.00, 7.06, 9.09, 0.060, 0.015, 0.190, 0.010, 0.55, 63.75),
    ("GD", "General Dynamics Corp.", "Industrials", "Aerospace & Defense", 345.57, 270.56, 5229.02, 0.17, 9479.00, 26866.33, 4333.00, 7694.00, 3293.88, 6633.00, 16.39, 18.62, 0.070, 0.020, 0.110, 0.010, 0.25, 203.29),
    ("TDG", "TransDigm Group Inc.", "Industrials", "Aerospace & Defense", 1112.00, 55.28, 2821.49, 0.21, 33485.00, -3485.37, 2780.00, 2198.00, 740.63, 5095.00, 32.97, 48.63, 0.120, 0.030, 0.480, 0.020, 0.08, 172.59),
    ("EMR", "Emerson Electric Co.", "Industrials", "Specialty Industrial Machinery", 158.39, 557.80, 5091.11, 0.20, 13802.00, 20379.22, 2180.00, 3912.00, 205.75, 6058.00, 4.57, 7.28, 0.060, 0.020, 0.210, 0.015, 0.18, 33.22),
    ("CSX", "CSX Corporation", "Industrials", "Railroads", 51.58, 1852.47, 7780.22, 0.23, 19451.00, 13104.41, 1390.00, 5322.00, 3368.75, 6831.00, 1.92, 2.32, 0.040, 0.020, 0.370, 0.015, 0.45, 7.80),
    ("NSC", "Norfolk Southern Corp.", "Industrials", "Railroads", 330.81, 224.61, 4949.13, 0.23, 17150.00, 16253.11, 1069.00, 3732.00, 2349.75, 5663.00, 11.72, 14.32, 0.045, 0.020, 0.310, 0.020, 0.50, 55.86),
    ("CTAS", "Cintas Corporation", "Industrials", "Specialty Business Services", 221.54, 397.08, 2280.56, 0.21, 2711.37, 5172.70, 364.58, 2434.13, 690.14, 3104.72, 5.07, 6.16, 0.075, 0.015, 0.210, 0.010, 0.20, 28.87),
    ("PCAR", "PACCAR Inc", "Industrials", "Farm & Heavy Construction Machinery", 109.59, 526.36, 5058.00, 0.22, 14816.30, 20321.37, 8667.40, 4344.70, 2401.05, 3271.60, 4.75, 7.16, 0.040, 0.040, 0.140, 0.020, 0.15, 52.85),
    ("JCI", "Johnson Controls International", "Industrials", "Building Products & Equipment", 146.57, 605.74, 5743.96, 0.15, 9475.00, 13481.99, 641.00, 2032.00, 1544.93, 4325.00, 3.54, 6.13, 0.050, 0.020, 0.110, 0.015, 0.30, 40.64),
    ("FDX", "FedEx Corporation", "Industrials", "Integrated Freight & Logistics", 301.13, 236.67, 6149.84, 0.23, 42944.00, 31208.07, 13551.00, 8925.00, 3268.37, 11844.00, 18.55, 20.86, 0.045, 0.025, 0.065, 0.010, 0.70, 399.66),
    ("CMI", "Cummins Inc.", "Industrials", "Specialty Industrial Machinery", 525.62, 137.66, 6089.50, 0.21, 8286.00, 12846.99, 3924.00, 4647.00, 2417.63, 5020.00, 19.57, 34.81, 0.050, 0.030, 0.110, 0.015, 0.32, 251.32),
    ("ROP", "Roper Technologies", "Industrials", "Software - Application", 414.71, 98.90, 1337.77, 0.21, 11319.40, 18700.47, 364.90, 2669.10, 403.41, 3238.00, 24.00, 24.38, 0.080, 0.020, 0.280, 0.015, 0.05, 79.01),
    ("TT", "Trane Technologies plc", "Industrials", "Building Products & Equipment", 451.71, 220.02, 3646.62, 0.18, 4616.80, 8612.15, 1318.30, 3876.80, 755.11, 4308.40, 13.42, 17.66, 0.080, 0.020, 0.160, 0.015, 0.12, 100.16),
    ("CARR", "Carrier Global Corporation", "Industrials", "Building Products & Equipment", 55.73, 824.33, 1987.82, 0.21, 12394.00, 13135.62, 1344.00, 2387.00, 1525.25, 3093.00, 1.38, 3.31, 0.070, 0.020, 0.130, 0.015, 0.20, 26.39),
    ("ODFL", "Old Dominion Freight Line", "Industrials", "Trucking", 191.38, 207.97, 1501.02, 0.24, 20.00, 4558.25, 283.94, 1394.10, 423.33, 1793.24, 5.20, 6.72, 0.060, 0.025, 0.280, 0.020, 0.45, 26.85),
    ("GWW", "W.W. Grainger Inc.", "Industrials", "Industrial Distribution", 1322.25, 47.10, 3045.49, 0.24, 2797.00, 4131.04, 589.00, 2175.00, 927.25, 3216.00, 39.21, 51.06, 0.065, 0.015, 0.150, 0.010, 0.20, 396.74),
    ("FAST", "Fastenal Company", "Industrials", "Industrial Distribution", 51.39, 1147.50, 1063.24, 0.24, 451.70, 4150.50, 211.90, 1433.80, 517.36, 2044.10, 1.23, 1.41, 0.055, 0.015, 0.200, 0.010, 0.18, 7.91),
    ("URI", "United Rentals Inc.", "Industrials", "Rental & Leasing Services", 1103.34, 62.24, 5489.92, 0.23, 15385.00, 9209.90, 112.00, 5742.00, 4035.75, 4691.00, 41.57, 57.78, 0.075, 0.030, 0.280, 0.020, 0.65, 266.11),
    ("CPRT", "Copart Inc.", "Industrials", "Specialty Business Services", 28.22, 926.33, 833.06, 0.19, 88.37, 9097.49, 4489.80, 1604.49, 719.37, 1866.26, 1.55, 1.81, 0.090, 0.020, 0.380, 0.020, 0.30, 4.91),
    ("DAL", "Delta Air Lines Inc.", "Industrials", "Airlines", 78.83, 657.91, 8281.75, 0.21, 19935.00, 22635.48, 3787.00, 8000.00, 5507.88, 7507.00, 5.01, 7.33, 0.050, 0.030, 0.095, 0.020, 0.70, 110.04),
    ("LUV", "Southwest Airlines Co.", "Industrials", "Airlines", 41.06, 489.21, 1155.66, 0.22, 6889.00, 7572.94, 3791.00, 2528.00, 3362.75, 2338.00, 2.05, 4.28, 0.040, 0.030, 0.035, 0.015, 0.85, 59.37),
    ("UAL", "United Airlines Holdings", "Industrials", "Airlines", 102.33, 324.58, 6715.41, 0.21, 34294.00, 17601.20, 14653.00, 8160.00, 8728.63, 7054.00, 10.92, 12.05, 0.055, 0.035, 0.075, 0.020, 0.70, 202.75),
    ("AAL", "American Airlines Group", "Industrials", "Airlines", 12.53, 661.97, 2055.70, 0.21, 35729.00, -4698.75, 8361.00, 4374.00, 3854.75, 3372.00, 1.17, 1.32, 0.040, 0.030, 0.040, 0.015, 0.78, 88.25),
    ("EFX", "Equifax Inc.", "Industrials", "Consulting Services", 182.41, 117.48, 706.52, 0.23, 5206.70, 4487.45, 192.90, 1612.90, 668.30, 2026.60, 6.18, 9.60, 0.080, 0.020, 0.200, 0.015, 0.45, 55.22),
    ("EXPD", "Expeditors International", "Industrials", "Integrated Freight & Logistics", 198.93, 129.99, 1572.19, 0.24, 567.28, 2118.20, 1031.45, 972.54, 174.98, 1263.71, 6.87, 8.10, 0.045, 0.030, 0.100, 0.020, 0.05, 90.22),
    ("AXON", "Axon Enterprise Inc.", "Industrials", "Aerospace & Defense", 402.73, 81.24, 332.35, 0.18, 1850.61, 3674.61, 692.53, 265.81, 43.65, 165.11, 2.41, 10.51, 0.220, 0.040, 0.180, 0.020, 0.20, 40.47),
    ("HWM", "Howmet Aerospace Inc.", "Industrials", "Aerospace & Defense", 196.92, 398.80, 2650.85, 0.20, 4664.00, 5714.82, 563.00, 2221.00, 1031.12, 2794.00, 4.64, 6.50, 0.110, 0.025, 0.200, 0.015, 0.22, 22.68),
    ("IR", "Ingersoll Rand Inc.", "Industrials", "Specialty Industrial Machinery", 74.75, 388.00, 1214.21, 0.21, 4906.70, 10177.61, 1181.70, 1349.20, 241.77, 2014.70, 2.43, 3.91, 0.075, 0.020, 0.220, 0.015, 0.10, 20.27),
    ("DOV", "Dover Corporation", "Industrials", "Specialty Industrial Machinery", 193.60, 134.68, 1544.68, 0.21, 3259.99, 7703.98, 1755.97, 1390.41, 483.93, 1908.99, 8.27, 11.64, 0.050, 0.020, 0.170, 0.015, 0.15, 62.03),
    ("SWK", "Stanley Black & Decker", "Industrials", "Tools & Accessories", 95.85, 151.02, 1139.84, 0.20, 5211.50, 8959.06, 592.40, 1551.20, 132.15, 1791.00, 4.09, 6.31, 0.035, 0.020, 0.070, 0.015, 0.35, 100.91),
    ("NDSN", "Nordson Corporation", "Industrials", "Specialty Industrial Machinery", 319.44, 55.70, 951.00, 0.21, 1818.21, 3269.05, 113.92, 773.38, 159.58, 957.89, 9.88, 12.98, 0.055, 0.020, 0.270, 0.015, 0.14, 53.36),
    ("AOS", "A. O. Smith Corporation", "Industrials", "Specialty Industrial Machinery", 60.37, 110.05, 488.71, 0.23, 677.20, 1491.36, 181.30, 692.30, 207.69, 783.70, 3.59, 4.03, 0.050, 0.015, 0.170, 0.010, 0.14, 27.45),
    ("GGG", "Graco Inc.", "Industrials", "Specialty Industrial Machinery", 71.34, 161.95, 527.83, 0.20, 52.21, 2602.60, 507.58, 673.45, 136.83, 735.00, 3.10, 3.52, 0.055, 0.015, 0.290, 0.015, 0.18, 13.73),
    # =========================================================================
    # 7. CONSUMER STAPLES (35 stocks)
    # =========================================================================
    ("PG", "The Procter & Gamble Company", "Consumer Staples", "Household & Personal Products", 165.26, 2322.67, 18968.97, 0.21, 35025.00, 53298.36, 9942.00, 19556.00, 6275.13, 24752.00, 6.62, 7.39, 0.040, 0.015, 0.240, 0.010, 0.20, 37.29),
    ("COST", "Costco Wholesale Corporation", "Consumer Staples", "Discount Stores", 1003.56, 443.13, 10325.15, 0.24, 10181.00, 35792.00, 21301.00, 15817.00, 9064.25, 14185.00, 20.76, 25.03, 0.080, 0.020, 0.037, 0.003, 0.35, 682.85),
    ("WMT", "Walmart Inc.", "Consumer Staples", "Discount Stores", 118.05, 7958.08, 41111.94, 0.24, 75092.00, 98433.48, 11529.00, 42923.00, 35795.37, 44073.00, 2.76, 3.23, 0.050, 0.015, 0.042, 0.004, 0.58, 92.36),
    ("KO", "The Coca-Cola Company", "Consumer Staples", "Beverages - Non-Alcoholic", 93.82, 4302.55, 18105.61, 0.20, 44261.00, 36145.72, 16371.00, 16342.00, 11123.25, 16998.00, 3.33, 3.52, 0.050, 0.020, 0.290, 0.015, 0.22, 11.65),
    ("PEP", "PepsiCo Inc.", "Consumer Staples", "Beverages - Non-Alcoholic", 136.25, 1362.74, 10944.41, 0.21, 51881.00, 22271.28, 11163.00, 14569.00, 5524.75, 19171.00, 7.95, 8.64, 0.045, 0.020, 0.150, 0.010, 0.32, 71.92),
    ("PM", "Philip Morris International", "Consumer Staples", "Tobacco", 198.61, 1558.61, 23116.90, 0.21, 47562.00, -14488.76, 6683.00, 18233.05, 2279.13, 20489.00, 6.85, 9.14, 0.070, 0.020, 0.380, 0.020, 0.12, 27.72),
    ("MDLZ", "Mondelez International", "Consumer Staples", "Confectioners", 63.43, 1276.31, 5017.06, 0.22, 22059.00, 26551.04, 1716.00, 4436.00, 2183.62, 6080.00, 2.72, 3.36, 0.045, 0.020, 0.160, 0.015, 0.22, 30.84),
    ("MO", "Altria Group Inc.", "Consumer Staples", "Tobacco", 74.47, 1669.74, 16629.22, 0.23, 24577.00, -4627.26, 2367.00, 9408.00, 2246.50, 12770.00, 4.75, 5.86, 0.025, 0.015, 0.560, 0.020, 0.03, 12.20),
    ("CL", "Colgate-Palmolive Company", "Consumer Staples", "Household & Personal Products", 95.74, 797.17, 3871.14, 0.22, 7857.00, 235.96, 1453.00, 4456.00, 997.63, 4983.00, 2.54, 4.09, 0.050, 0.015, 0.210, 0.010, 0.20, 26.19),
    ("TGT", "Target Corporation", "Consumer Staples", "Discount Stores", 153.30, 454.30, 5375.45, 0.22, 19196.00, 17843.41, 5411.00, 8723.00, 5290.00, 8593.00, 9.63, 9.55, 0.030, 0.020, 0.052, 0.008, 0.55, 237.37),
    ("STZ", "Constellation Brands", "Consumer Staples", "Beverages - Brewers", 134.72, 169.20, 1877.25, 0.20, 10315.70, 8556.20, 98.50, 2658.30, 1539.90, 3425.90, 11.17, 12.10, 0.055, 0.020, 0.320, 0.020, 0.38, 53.33),
    ("KMB", "Kimberly-Clark Corporation", "Consumer Staples", "Household & Personal Products", 108.73, 332.58, 2365.35, 0.23, 6539.00, 1750.03, 956.00, 3333.00, 2391.87, 3481.00, 5.07, 7.41, 0.035, 0.015, 0.150, 0.010, 0.25, 49.95),
    ("ADM", "Archer-Daniels-Midland", "Consumer Staples", "Farm Products", 78.65, 481.96, 5540.64, 0.19, 9342.00, 23571.20, 1093.00, 2795.00, 1630.38, 2995.00, 3.65, 5.67, 0.030, 0.030, 0.045, 0.010, 0.40, 169.28),
    ("SYY", "Sysco Corporation", "Consumer Staples", "Food Distribution", 83.07, 491.91, 3461.25, 0.23, 15052.00, 2740.45, 1787.00, 2638.00, 724.00, 4493.00, 3.66, 5.35, 0.040, 0.015, 0.042, 0.006, 0.25, 176.48),
    ("GIS", "General Mills Inc.", "Consumer Staples", "Packaged Foods", 33.59, 534.69, 1577.43, 0.21, 13615.60, 7450.33, 433.10, 2067.00, 764.39, 3415.00, 1.99, 3.15, 0.030, 0.015, 0.170, 0.010, 0.22, 34.09),
    ("KDP", "Keurig Dr Pepper Inc.", "Consumer Staples", "Beverages - Non-Alcoholic", 34.84, 1360.83, 3408.26, 0.22, 33528.00, 25032.39, 1526.00, 2527.00, 492.30, 4807.00, 0.99, 2.53, 0.045, 0.015, 0.240, 0.015, 0.15, 14.78),
    ("HSY", "The Hershey Company", "Consumer Staples", "Confectioners", 171.74, 146.31, 2375.13, 0.21, 5923.31, 3322.60, 791.21, 2656.59, 912.95, 2721.62, 7.32, 9.84, 0.040, 0.020, 0.230, 0.015, 0.25, 59.98),
    ("KR", "The Kroger Co.", "Consumer Staples", "Grocery Stores", 65.06, 590.59, 4578.30, 0.22, 24158.00, 5787.18, 1676.00, 6708.00, 4172.50, 8043.00, 1.80, 5.48, 0.030, 0.015, 0.025, 0.005, 0.65, 238.35),
    ("MKC", "McCormick & Company", "Consumer Staples", "Packaged Foods", 47.20, 254.54, 637.06, 0.22, 5018.20, 6625.21, 331.10, 1140.80, 398.80, 1504.10, 5.53, 3.22, 0.040, 0.015, 0.160, 0.010, 0.25, 28.58),
    ("EL", "The Estée Lauder Companies", "Consumer Staples", "Household & Personal Products", 106.35, 247.82, 1442.03, 0.24, 9246.00, 2607.02, 3498.00, 1773.00, 1141.61, 2455.00, 0.50, 3.93, 0.045, 0.035, 0.080, 0.020, 0.50, 41.54),
    ("CLX", "The Clorox Company", "Consumer Staples", "Household & Personal Products", 86.37, 120.94, 506.49, 0.22, 5598.00, 89.98, 143.00, 612.00, 501.62, 1140.00, 4.81, 6.13, 0.035, 0.015, 0.130, 0.010, 0.25, 55.18),
    ("CAG", "Conagra Brands Inc.", "Consumer Staples", "Packaged Foods", 14.34, 477.41, 946.98, 0.23, 7760.10, 6404.95, 371.60, 1277.30, 857.67, 1657.90, 0.99, 1.50, 0.025, 0.015, 0.170, 0.010, 0.20, 23.47),
    ("HRL", "Hormel Foods Corporation", "Consumer Staples", "Packaged Foods", 20.75, 550.35, 800.54, 0.22, 2855.12, 7843.60, 868.45, 1091.66, 470.11, 1264.93, 0.62, 1.57, 0.030, 0.015, 0.100, 0.010, 0.22, 22.06),
    ("SJM", "The J.M. Smucker Company", "Consumer Staples", "Packaged Foods", 129.61, 106.82, 1537.75, 0.23, 6940.20, 5750.72, 43.20, 1909.90, 445.56, 2263.90, 2.14, 10.99, 0.035, 0.020, 0.160, 0.015, 0.35, 85.78),
    ("TSN", "Tyson Foods Inc.", "Consumer Staples", "Farm Products", 56.30, 281.79, 1471.90, 0.22, 8006.00, 14481.32, 740.00, 2004.00, 812.75, 2772.00, 1.62, 3.90, 0.035, 0.025, 0.030, 0.015, 0.55, 157.00),
    ("CHD", "Church & Dwight Co.", "Consumer Staples", "Household & Personal Products", 106.78, 237.20, 1203.89, 0.23, 2428.30, 4349.13, 254.80, 1260.50, 321.24, 1354.80, 3.12, 4.03, 0.050, 0.015, 0.190, 0.010, 0.20, 26.13),
    ("BG", "Bunge Global SA", "Consumer Staples", "Farm Products", 101.72, 192.12, 2491.10, 0.18, 17061.00, 15953.96, 788.00, 1075.00, 7550.38, 3126.00, 5.02, 11.23, 0.040, 0.030, 0.040, 0.010, 0.35, 471.47),
    ("CPB", "Campbell Soup Company", "Consumer Staples", "Packaged Foods", 20.25, 298.23, 542.78, 0.23, 7450.00, 3852.89, 394.00, 1039.00, 404.50, 1620.00, 1.31, 1.84, 0.030, 0.015, 0.130, 0.010, 0.35, 32.70),
    ("TAP", "Molson Coors Beverage Co.", "Consumer Staples", "Beverages - Brewers", 40.24, 174.12, 1141.56, 0.21, 7913.70, 9427.44, 2128.10, 1977.20, 1042.06, 2263.40, 3.14, 4.80, 0.030, 0.015, 0.130, 0.015, 0.35, 57.62),
    ("DLTR", "Dollar Tree Inc.", "Consumer Staples", "Discount Stores", 125.99, 187.63, 3064.62, 0.24, 7670.80, 3424.44, 1058.10, 3117.00, 2067.41, 2503.80, 8.21, 7.91, 0.040, 0.020, 0.060, 0.010, 0.70, 101.64),
    ("DG", "Dollar General Corp.", "Consumer Staples", "Discount Stores", 134.24, 220.62, 3495.01, 0.23, 15773.10, 9288.63, 1589.59, 3316.35, 1578.33, 3581.93, 7.70, 8.31, 0.040, 0.020, 0.055, 0.010, 0.55, 198.08),
    ("KVUE", "Kenvue Inc.", "Consumer Staples", "Household & Personal Products", 19.35, 1920.77, 2630.92, 0.21, 8613.00, 10556.57, 1110.00, 2325.00, 417.50, 3481.00, 0.86, 1.24, 0.035, 0.015, 0.200, 0.010, 0.20, 8.04),
    ("LW", "Lamb Weston Holdings", "Consumer Staples", "Packaged Foods", 53.43, 137.78, 918.33, 0.22, 3956.70, 1806.99, 166.30, 825.70, 493.92, 1069.10, 1.83, 3.53, 0.050, 0.025, 0.160, 0.020, 0.80, 47.85),
    ("CASY", "Casey's General Stores", "Consumer Staples", "Specialty Retail", 701.38, 36.96, 921.81, 0.22, 2888.15, 4091.79, 524.06, 1389.20, 885.89, 1564.25, 20.76, 23.44, 0.080, 0.020, 0.062, 0.008, 0.45, 504.39),
    ("HLF", "Herbalife Ltd.", "Consumer Staples", "Packaged Foods", 13.95, 103.67, 680.89, 0.24, 2203.80, -1411.61, 370.50, 383.80, 65.90, 625.10, 1.57, 3.08, 0.020, 0.020, 0.080, 0.015, 0.35, 50.15),
    # =========================================================================
    # 8. ENERGY (24 stocks - complete sector)
    # =========================================================================
    ("XOM", "Exxon Mobil Corporation", "Energy", "Oil & Gas Integrated", 176.72, 4111.91, 77163.70, 0.28, 42368.00, 259379.41, 10588.00, 59727.00, 39056.00, 67937.00, 7.77, 12.28, 0.030, 0.120, 0.150, 0.050, 0.45, 85.49),
    ("CVX", "Chevron Corporation", "Energy", "Oil & Gas Integrated", 225.38, 1961.60, 39948.31, 0.26, 37075.00, 189883.20, 8530.00, 45321.00, 23387.00, 50662.00, 10.39, 15.72, 0.035, 0.110, 0.140, 0.045, 0.48, 106.25),
    ("COP", "ConocoPhillips", "Energy", "Oil & Gas E&P", 144.94, 1201.34, 21125.94, 0.25, 23290.00, 65349.15, 7692.00, 21925.00, 14233.62, 26780.00, 7.55, 10.68, 0.040, 0.100, 0.270, 0.050, 0.60, 52.46),
    ("EOG", "EOG Resources Inc.", "Energy", "Oil & Gas E&P", 156.97, 524.53, 11664.17, 0.22, 8250.00, 31805.35, 4907.00, 13358.00, 8879.25, 14495.00, 12.85, 16.13, 0.045, 0.090, 0.380, 0.040, 0.55, 50.04),
    ("SLB", "SLB (Schlumberger Limited)", "Energy", "Oil & Gas Equipment & Services", 49.70, 1484.14, 6354.34, 0.20, 12810.00, 26073.43, 4124.00, 6533.00, 3577.88, 7383.00, 2.07, 3.15, 0.080, 0.080, 0.160, 0.030, 0.40, 24.43),
    ("MPC", "Marathon Petroleum Corp.", "Energy", "Oil & Gas Refining & Marketing", 461.46, 280.82, 30764.00, 0.23, 34292.00, 18930.40, 7768.00, 17126.00, 7876.62, 15397.00, 28.88, 58.44, 0.025, 0.120, 0.070, 0.030, 0.25, 520.76),
    ("PSX", "Phillips 66", "Energy", "Oil & Gas Refining & Marketing", 286.27, 400.94, 16418.43, 0.22, 20565.00, 31657.03, 4099.00, 8925.00, 4379.62, 9925.00, 17.50, 30.35, 0.030, 0.110, 0.050, 0.020, 0.30, 377.80),
    ("VLO", "Valero Energy Corporation", "Energy", "Oil & Gas Refining & Marketing", 427.72, 287.93, 20999.97, 0.22, 11349.00, 25000.74, 7874.00, 10908.00, 2491.63, 13379.00, 23.99, 49.22, 0.025, 0.120, 0.050, 0.020, 0.25, 440.70),
    ("WMB", "The Williams Companies", "Energy", "Oil & Gas Midstream", 70.64, 1223.17, 5569.13, 0.24, 30793.00, 13156.39, 203.00, 5994.00, 7510.75, 7033.00, 2.51, 2.65, 0.050, 0.020, 0.350, 0.020, 0.50, 10.08),
    ("KMI", "Kinder Morgan Inc.", "Energy", "Oil & Gas Midstream", 32.92, 2226.80, 6025.54, 0.23, 32425.00, 31658.45, 91.00, 6557.00, 5482.00, 7635.00, 1.62, 1.55, 0.045, 0.020, 0.260, 0.020, 0.50, 8.07),
    ("OXY", "Occidental Petroleum Corp.", "Energy", "Oil & Gas E&P", 62.49, 999.64, 8047.95, 0.24, 14626.00, 33456.86, 4150.00, 10976.00, 7187.88, 13718.00, 3.52, 4.96, 0.040, 0.100, 0.230, 0.040, 0.55, 24.15),
    ("OVV", "Ovintiv Inc.", "Energy", "Oil & Gas E&P", 69.62, 276.60, 2380.17, 0.22, 5029.00, 11499.09, 700.00, 4454.00, 3223.50, 4882.00, 3.59, 8.18, 0.050, 0.080, 0.280, 0.040, 0.58, 36.02),
    ("BKR", "Baker Hughes Company", "Energy", "Oil & Gas Equipment & Services", 54.20, 992.67, 4565.76, 0.21, 16253.00, 19915.03, 17024.00, 4436.00, 21.00, 4839.00, 3.11, 2.94, 0.065, 0.060, 0.120, 0.020, 0.40, 28.05),
    ("FANG", "Diamondback Energy Inc.", "Energy", "Oil & Gas E&P", 198.94, 280.02, 4656.04, 0.21, 12614.00, 37825.91, 462.00, 10143.00, 5107.50, 11780.00, 5.25, 19.08, 0.060, 0.090, 0.520, 0.040, 0.60, 57.08),
    ("OKE", "ONEOK Inc.", "Energy", "Oil & Gas Midstream", 91.37, 630.41, 3689.76, 0.22, 33022.00, 22938.70, 161.00, 6157.00, 5257.13, 7670.00, 5.79, 6.12, 0.060, 0.025, 0.180, 0.020, 0.50, 62.43),
    ("HAL", "Halliburton Company", "Energy", "Oil & Gas Equipment & Services", 33.20, 833.13, 4043.59, 0.22, 8198.00, 11146.45, 1843.00, 2630.00, 631.38, 4729.00, 1.90, 2.95, 0.050, 0.070, 0.160, 0.020, 0.38, 26.87),
    ("DVN", "Devon Energy Corporation", "Energy", "Oil & Gas E&P", 49.45, 1100.00, 4885.42, 0.22, 11893.00, 39935.50, 950.00, 8553.00, 7770.37, 8924.00, 4.59, 5.39, 0.045, 0.090, 0.280, 0.040, 0.78, 26.79),
    ("TRGP", "Targa Resources Corp.", "Energy", "Oil & Gas Midstream", 286.69, 214.43, 4649.03, 0.22, 19578.00, 3656.69, 132.30, 4285.50, 4219.66, 5497.70, 10.46, 12.12, 0.075, 0.030, 0.150, 0.020, 0.75, 77.92),
    ("LNG", "Cheniere Energy Inc.", "Energy", "Oil & Gas Midstream", 282.66, 206.53, 5517.24, 0.21, 27969.00, 6150.38, 1116.00, 6138.00, 5417.12, 7828.00, 13.21, 20.72, 0.070, 0.040, 0.350, 0.030, 0.35, 98.10),
    ("EQT", "EQT Corporation", "Energy", "Oil & Gas E&P", 53.63, 625.52, 2500.88, 0.21, 5655.71, 25258.96, 112.86, 6246.15, 3785.24, 6995.36, 4.31, 3.62, 0.060, 0.090, 0.350, 0.050, 0.85, 14.87),
    ("PR", "Permian Resources Corp.", "Energy", "Oil & Gas E&P", 24.68, 837.56, 2180.56, 0.21, 3150.87, 12006.38, 131.72, 3991.58, 3533.21, 4255.12, 1.52, 2.43, 0.080, 0.080, 0.420, 0.040, 0.60, 7.38),
    ("APA", "APA Corporation", "Energy", "Oil & Gas E&P", 49.06, 350.35, 4868.55, 0.28, 3881.00, 7014.74, 444.00, 4528.00, 2381.25, 5720.00, 4.73, 5.17, 0.035, 0.090, 0.300, 0.040, 0.68, 24.18),
    ("EXE", "Expand Energy Corporation", "Energy", "Oil & Gas E&P", 92.56, 231.50, 1791.48, 0.21, 3728.00, 19174.30, 663.00, 5655.00, 4188.75, 6721.00, 11.60, 9.09, 0.060, 0.090, 0.280, 0.040, 0.60, 53.03),
    ("OII", "Oceaneering International", "Energy", "Oil & Gas Equipment & Services", 37.30, 99.53, 319.71, 0.24, 822.16, 1164.20, 636.47, 318.48, 80.64, 404.92, 3.46, 2.32, 0.080, 0.050, 0.090, 0.020, 0.35, 28.81),
    # =========================================================================
    # 9. UTILITIES (30 stocks - complete sector)
    # =========================================================================
    ("NEE", "NextEra Energy Inc.", "Utilities", "Utilities - Regulated Electric", 80.00, 2085.98, 9503.03, 0.12, 110197.00, 54686.00, 2866.00, 13803.00, 31569.87, 14593.00, 5.55, 4.38, 0.075, 0.030, 0.350, 0.020, 0.75, 13.81),
    ("SO", "The Southern Company", "Utilities", "Utilities - Regulated Electric", 91.61, 1150.36, 6991.56, 0.15, 77087.00, 39570.19, 2984.00, 10651.00, 14564.37, 14258.00, 4.15, 4.92, 0.040, 0.015, 0.260, 0.015, 0.65, 26.99),
    ("DUK", "Duke Energy Corporation", "Utilities", "Utilities - Regulated Electric", 121.89, 779.70, 8024.79, 0.14, 92206.00, 53757.35, 673.00, 11562.00, 16039.38, 16617.00, 6.64, 7.17, 0.040, 0.015, 0.250, 0.015, 0.70, 42.16),
    ("CEG", "Constellation Energy Corp.", "Utilities", "Utilities - Independent Power Producers", 263.55, 354.31, 3146.87, 0.16, 24700.00, 31887.31, 697.00, 4206.00, 10831.12, 7952.00, 10.23, 13.30, 0.120, 0.040, 0.140, 0.025, 0.50, 93.48),
    ("SRE", "Sempra", "Utilities", "Utilities - Diversified", 83.96, 653.90, 4007.18, 0.15, 36664.00, 32692.40, 48.00, 5416.00, 33073.75, 5874.00, 3.46, 5.54, 0.050, 0.020, 0.250, 0.015, 0.65, 20.74),
    ("AEP", "American Electric Power", "Utilities", "Utilities - Regulated Electric", 128.55, 544.40, 5769.07, 0.14, 53525.00, 32080.79, 603.00, 7694.00, 13689.95, 9029.00, 5.77, 6.87, 0.045, 0.015, 0.230, 0.015, 0.70, 42.27),
    ("VST", "Vistra Corp.", "Utilities", "Utilities - Independent Power Producers", 149.19, 335.64, 3424.03, 0.18, 20508.00, 3002.93, 435.00, 5121.00, 5083.87, 6646.00, 5.93, 10.42, 0.140, 0.050, 0.180, 0.030, 0.50, 56.84),
    ("D", "Dominion Energy Inc.", "Utilities", "Utilities - Regulated Electric", 63.59, 879.53, 4464.37, 0.15, 53932.00, 27916.15, 298.00, 5389.00, 14570.12, 8341.00, 2.89, 3.82, 0.040, 0.015, 0.280, 0.015, 0.70, 20.89),
    ("PEG", "Public Service Enterprise", "Utilities", "Utilities - Regulated Electric", 71.52, 498.42, 2513.74, 0.15, 24678.00, 17343.52, 192.00, 3592.00, 3484.25, 4463.00, 4.02, 4.64, 0.045, 0.015, 0.280, 0.015, 0.60, 25.16),
    ("EXC", "Exelon Corporation", "Utilities", "Utilities - Regulated Electric", 43.52, 1030.25, 4592.56, 0.14, 52673.00, 29640.41, 1813.00, 7212.00, 9897.13, 8355.00, 2.72, 3.03, 0.040, 0.015, 0.190, 0.015, 0.70, 24.85),
    ("ED", "Consolidated Edison Inc.", "Utilities", "Utilities - Regulated Electric", 113.09, 369.83, 3769.67, 0.16, 28320.00, 25707.16, 1470.00, 3955.00, 4799.88, 6162.00, 6.07, 6.50, 0.035, 0.015, 0.220, 0.015, 0.65, 48.74),
    ("XEL", "Xcel Energy Inc.", "Utilities", "Utilities - Regulated Electric", 77.69, 624.63, 3801.35, 0.13, 41651.00, 24065.91, 2018.00, 4771.00, 12679.00, 6123.00, 3.65, 4.54, 0.045, 0.015, 0.220, 0.015, 0.75, 23.98),
    ("PCG", "PG&E Corporation", "Utilities", "Utilities - Regulated Electric", 12.86, 2202.37, 2662.93, 0.14, 64703.00, 32321.94, 972.00, 8147.00, 14297.12, 10453.00, 1.38, 1.80, 0.050, 0.020, 0.170, 0.015, 0.85, 11.75),
    ("WEC", "WEC Energy Group Inc.", "Utilities", "Utilities - Regulated Electric", 109.35, 325.85, 2600.76, 0.14, 23023.20, 14135.02, 50.00, 3574.20, 5927.84, 3965.20, 5.15, 6.01, 0.040, 0.015, 0.240, 0.015, 0.65, 31.18),
    ("ETR", "Entergy Corporation", "Utilities", "Utilities - Regulated Electric", 106.48, 477.78, 2160.46, 0.13, 34627.32, 18664.38, 3855.05, 6074.61, 10475.47, 5538.09, 3.91, 5.10, 0.045, 0.015, 0.230, 0.015, 0.70, 29.75),
    ("AWK", "American Water Works Co.", "Utilities", "Utilities - Regulated Water", 136.96, 198.73, 1611.29, 0.15, 16068.00, 11664.99, 227.00, 2334.00, 4119.38, 2913.00, 5.77, 6.57, 0.055, 0.015, 0.360, 0.015, 0.80, 27.03),
    ("DTE", "DTE Energy Company", "Utilities", "Utilities - Regulated Electric", 130.50, 208.09, 2201.20, 0.14, 27840.00, 12149.01, 42.00, 3359.00, 5955.62, 3617.00, 6.31, 8.32, 0.040, 0.015, 0.160, 0.015, 0.70, 79.35),
    ("ES", "Eversource Energy", "Utilities", "Utilities - Regulated Electric", 65.89, 376.67, 2463.18, 0.15, 29807.79, 16343.54, 1819.32, 4430.45, 3618.49, 4933.03, 3.86, 4.92, 0.040, 0.015, 0.200, 0.015, 0.75, 37.33),
    ("PPL", "PPL Corporation", "Utilities", "Utilities - Regulated Electric", 34.97, 752.54, 1942.78, 0.14, 20376.00, 15048.64, 332.00, 2654.00, 4592.38, 3759.00, 1.69, 2.12, 0.045, 0.015, 0.210, 0.015, 0.65, 12.60),
    ("FE", "FirstEnergy Corp.", "Utilities", "Utilities - Regulated Electric", 45.79, 578.64, 2453.04, 0.14, 28983.00, 12934.92, 63.00, 3118.00, 5132.63, 5422.00, 1.87, 2.95, 0.040, 0.015, 0.180, 0.015, 0.70, 27.07),
    ("AEE", "Ameren Corporation", "Utilities", "Utilities - Regulated Electric", 107.21, 276.84, 2314.76, 0.14, 21808.00, 13689.07, 12.00, 3251.00, 5037.25, 3910.00, 5.68, 5.80, 0.045, 0.015, 0.250, 0.015, 0.75, 30.73),
    ("CMS", "CMS Energy Corporation", "Utilities", "Utilities - Regulated Electric", 68.76, 313.58, 1608.42, 0.14, 19301.00, 9549.36, 241.00, 2148.00, 4346.87, 3018.00, 3.33, 4.15, 0.045, 0.015, 0.210, 0.015, 0.70, 28.86),
    ("CNP", "CenterPoint Energy Inc.", "Utilities", "Utilities - Regulated Electric", 40.55, 658.72, 2561.05, 0.15, 24642.00, 11720.61, 453.00, 2576.00, 7767.88, 3854.00, 1.69, 2.09, 0.040, 0.015, 0.200, 0.015, 0.75, 14.71),
    ("ATO", "Atmos Energy Corporation", "Utilities", "Utilities - Regulated Gas", 168.32, 168.99, 1585.62, 0.15, 10323.87, 15258.31, 520.95, 2019.59, 4240.55, 2624.30, 8.39, 9.03, 0.050, 0.015, 0.310, 0.015, 0.85, 29.89),
    ("NI", "NiSource Inc.", "Utilities", "Utilities - Regulated Gas", 43.40, 479.56, 1522.81, 0.14, 17443.00, 9575.86, 70.00, 2303.20, 4076.20, 3026.00, 1.88, 2.25, 0.045, 0.015, 0.220, 0.015, 0.80, 14.42),
    ("LNT", "Alliant Energy Corporation", "Utilities", "Utilities - Regulated Electric", 68.88, 259.28, 1292.97, 0.14, 12118.00, 7529.11, 25.00, 1158.00, 2296.63, 1829.00, 3.16, 3.68, 0.045, 0.015, 0.270, 0.015, 0.75, 17.20),
    ("EVRG", "Evergy Inc.", "Utilities", "Utilities - Regulated Electric", 83.83, 230.57, 1682.21, 0.14, 16498.00, 10223.35, 21.80, 1982.80, 3426.16, 2840.40, 3.93, 4.56, 0.040, 0.015, 0.220, 0.015, 0.70, 26.41),
    ("AES", "The AES Corporation", "Utilities", "Utilities - Diversified", 14.95, 713.44, 1618.30, 0.16, 32943.00, 4944.13, 1853.00, 5032.00, 8121.13, 4070.00, 2.67, 2.38, 0.055, 0.025, 0.160, 0.020, 0.65, 18.30),
    ("PNW", "Pinnacle West Capital", "Utilities", "Utilities - Regulated Electric", 104.75, 121.20, 1007.21, 0.14, 16505.29, 7035.14, 9.12, 1771.04, 2700.54, 2149.11, 5.21, 5.57, 0.045, 0.015, 0.180, 0.015, 0.75, 46.06),
    ("NRG", "NRG Energy Inc.", "Utilities", "Utilities - Independent Power Producers", 97.32, 210.21, 2538.78, 0.18, 23467.00, 4202.95, 162.00, 1555.00, 782.63, 3253.00, 3.82, 10.81, 0.065, 0.025, 0.080, 0.015, 0.20, 164.80),
    # =========================================================================
    # 10. REAL ESTATE (31 stocks)
    # =========================================================================
    ("PLD", "Prologis Inc.", "Real Estate", "REIT - Industrial", 127.26, 950.33, 4506.68, 0.04, 36832.48, 55906.21, 2273.50, 5579.70, 1287.62, 6843.43, 4.50, 3.21, 0.080, 0.030, 0.520, 0.020, 0.35, 10.61),
    ("AMT", "American Tower Corporation", "Real Estate", "REIT - Specialty", 181.07, 465.96, 3808.51, 0.05, 44979.90, 3719.76, 1762.50, 5774.90, 2854.89, 7044.40, 7.27, 6.98, 0.065, 0.025, 0.420, 0.020, 0.30, 23.43),
    ("EQIX", "Equinix Inc.", "Real Estate", "REIT - Specialty", 959.61, 98.67, 2336.44, 0.06, 23356.00, 14382.09, 979.00, 3942.00, 156.00, 4540.00, 15.54, 18.53, 0.110, 0.030, 0.250, 0.020, 0.45, 100.75),
    ("WELL", "Welltower Inc.", "Real Estate", "REIT - Healthcare Facilities", 234.66, 720.57, 3299.91, 0.04, 19720.80, 46522.29, 1965.16, 3186.32, 430.16, 3340.61, 2.23, 3.20, 0.080, 0.025, 0.260, 0.020, 0.45, 18.42),
    ("SPG", "Simon Property Group", "Real Estate", "REIT - Retail", 208.00, 323.55, 3961.90, 0.04, 29437.51, 4394.15, 1019.09, 4122.94, 1527.67, 5125.17, 14.17, 6.77, 0.050, 0.020, 0.580, 0.020, 0.20, 21.33),
    ("DLR", "Digital Realty Trust", "Real Estate", "REIT - Specialty", 172.03, 371.00, 1742.08, 0.05, 20074.99, 26774.24, 1907.73, 2967.04, 3048.63, 3210.31, 2.06, 2.76, 0.085, 0.025, 0.300, 0.020, 0.60, 19.53),
    ("PSA", "Public Storage", "Real Estate", "REIT - Industrial", 302.00, 186.85, 2119.30, 0.04, 10180.21, 5149.84, 259.94, 3171.92, 837.68, 3436.56, 10.47, 9.93, 0.060, 0.020, 0.540, 0.020, 0.25, 27.98),
    ("O", "Realty Income Corporation", "Real Estate", "REIT - Retail", 56.25, 946.22, 2163.46, 0.03, 31333.79, 39550.02, 569.95, 4166.15, 2584.07, 5357.64, 1.38, 1.55, 0.060, 0.020, 0.520, 0.020, 0.55, 6.56),
    ("CCI", "Crown Castle Inc.", "Real Estate", "REIT - Specialty", 80.20, 437.00, 1575.36, 0.04, 23404.00, 4582.86, 1042.00, 2624.00, 1587.75, 2690.00, 2.49, 2.94, 0.040, 0.020, 0.320, 0.020, 0.30, 9.58),
    ("CBRE", "CBRE Group Inc.", "Real Estate", "Real Estate Services", 130.25, 289.58, 1890.73, 0.22, 10806.00, 8390.15, 1489.00, 1361.00, 294.11, 2214.00, 4.37, 8.94, 0.075, 0.025, 0.055, 0.010, 0.15, 148.10),
    ("EXR", "Extra Space Storage Inc.", "Real Estate", "REIT - Industrial", 141.65, 211.27, 1180.42, 0.04, 14414.69, 13257.59, 696.60, 1901.19, 401.76, 2310.66, 4.53, 4.80, 0.065, 0.020, 0.480, 0.020, 0.28, 16.61),
    ("CSGP", "CoStar Group Inc.", "Real Estate", "Real Estate Services", 34.12, 405.20, 423.98, 0.21, 1155.00, 7939.85, 1266.00, 497.00, 84.30, 394.00, 0.18, 1.77, 0.110, 0.025, 0.160, 0.020, 0.15, 8.60),
    ("GLPI", "Gaming and Leisure Properties", "Real Estate", "REIT - Specialty", 38.98, 290.92, 1054.87, 0.04, 8379.89, 4983.46, 319.00, 1203.38, 696.63, 1647.78, 3.42, 3.33, 0.055, 0.015, 0.680, 0.015, 0.12, 5.83),
    ("VICI", "VICI Properties Inc.", "Real Estate", "REIT - Diversified", 23.57, 1101.08, 2036.91, 0.02, 17843.67, 29170.85, 300.95, 2638.28, 2371.25, 3639.22, 2.57, 2.99, 0.065, 0.020, 0.780, 0.020, 0.15, 3.82),
    ("INVH", "Invitation Homes Inc.", "Real Estate", "REIT - Residential", 27.17, 590.62, 608.98, 0.04, 8585.70, 9054.84, 113.06, 1199.92, 31.13, 1500.34, 1.09, 0.71, 0.060, 0.020, 0.320, 0.015, 0.45, 4.70),
    ("MAA", "Mid-America Apartment", "Real Estate", "REIT - Residential", 118.97, 116.02, 543.44, 0.04, 5715.27, 5434.35, 51.84, 1010.66, 89.47, 1238.05, 3.42, 3.28, 0.050, 0.020, 0.360, 0.015, 0.45, 19.02),
    ("UDR", "UDR Inc.", "Real Estate", "REIT - Residential", 35.65, 321.26, 393.38, 0.04, 5994.85, 2895.55, 2.83, 887.26, 107.43, 1040.78, 1.58, 0.56, 0.050, 0.015, 0.310, 0.015, 0.40, 5.39),
    ("ESS", "Essex Property Trust", "Real Estate", "REIT - Residential", 277.42, 64.27, 633.04, 0.04, 6748.25, 5323.10, 67.53, 1118.02, 74.10, 1230.55, 6.43, 6.23, 0.050, 0.020, 0.410, 0.020, 0.42, 30.77),
    ("CPT", "Camden Property Trust", "Real Estate", "REIT - Residential", 101.43, 115.73, 399.07, 0.04, 4873.03, 4291.02, 44.72, 807.44, 667.76, 893.97, 3.03, 0.75, 0.055, 0.020, 0.320, 0.015, 0.40, 14.94),
    ("ARE", "Alexandria Real Estate", "Real Estate", "REIT - Office", 42.67, 172.10, 343.53, 0.04, 13167.78, 15678.40, 470.45, 1279.45, 687.06, 1781.94, 0.76, 3.40, 0.065, 0.025, 0.320, 0.020, 0.85, 16.66),
    ("KIM", "Kimco Realty Corporation", "Real Estate", "REIT - Retail", 23.11, 670.79, 757.39, 0.04, 8858.84, 10273.81, 702.40, 1179.11, 307.62, 1332.12, 0.85, 0.90, 0.050, 0.015, 0.410, 0.020, 0.38, 3.25),
    ("REG", "Regency Centers Corp.", "Real Estate", "REIT - Retail", 73.37, 183.12, 586.96, 0.04, 5143.97, 6665.04, 193.28, 856.64, 113.28, 1071.21, 2.97, 2.50, 0.055, 0.015, 0.420, 0.020, 0.35, 9.23),
    ("HST", "Host Hotels & Resorts", "Real Estate", "REIT - Hotel & Motel", 25.20, 685.12, 1273.85, 0.04, 5645.00, 6389.47, 1953.00, 1606.00, 941.54, 1695.00, 1.48, 1.05, 0.050, 0.030, 0.170, 0.020, 0.45, 9.08),
    ("BXP", "BXP Inc. (Boston Properties)", "Real Estate", "REIT - Office", 59.48, 159.66, 624.17, 0.04, 16358.49, 5159.62, 495.53, 1284.50, 403.86, 1617.15, 1.86, 2.09, 0.045, 0.025, 0.280, 0.020, 0.85, 20.11),
    ("FRT", "Federal Realty Investment", "Real Estate", "REIT - Retail", 107.06, 86.89, 401.48, 0.04, 4851.82, 3204.91, 115.28, 630.97, 174.83, 837.70, 4.95, 3.23, 0.050, 0.015, 0.380, 0.015, 0.45, 15.52),
    ("NNN", "NNN REIT Inc.", "Real Estate", "REIT - Retail", 41.20, 190.25, 549.33, 0.03, 5001.27, 4421.56, 4.22, 673.01, 2044.82, 860.66, 2.02, 2.10, 0.055, 0.015, 0.720, 0.015, 0.45, 5.05),
    ("WY", "Weyerhaeuser Company", "Real Estate", "REIT - Specialty", 19.50, 720.74, 722.22, 0.15, 5449.00, 9456.78, 527.00, 547.00, 533.38, 688.00, 0.65, 0.59, 0.040, 0.040, 0.160, 0.030, 0.25, 9.50),
    ("SBAC", "SBA Communications Corp.", "Real Estate", "REIT - Specialty", 176.32, 106.09, 814.92, 0.04, 15209.07, -3556.03, 327.05, 1284.32, 532.26, 1833.55, 9.27, 8.07, 0.055, 0.020, 0.410, 0.020, 0.25, 26.99),
    ("DOC", "Healthpeak Properties", "Real Estate", "REIT - Healthcare Facilities", 18.68, 689.53, 634.09, 0.04, 10320.38, 7845.44, 1640.91, 1231.03, 728.35, 1570.76, 0.35, 0.14, 0.055, 0.020, 0.310, 0.020, 0.65, 4.25),
    ("CUBE", "CubeSmart", "Real Estate", "REIT - Industrial", 39.52, 225.16, 396.85, 0.04, 3541.50, 2575.18, 14.31, 597.88, 111.85, 705.23, 1.46, 1.59, 0.055, 0.015, 0.450, 0.015, 0.32, 5.00),
    ("REXR", "Rexford Industrial Realty", "Real Estate", "REIT - Industrial", 36.59, 222.99, 421.04, 0.04, 3271.31, 7406.77, 41.47, 509.33, 167.54, 677.24, 1.25, 1.60, 0.080, 0.020, 0.480, 0.020, 0.30, 4.32),
    # =========================================================================
    # 11. MATERIALS (28 stocks)
    # =========================================================================
    ("LIN", "Linde plc", "Materials", "Specialty Chemicals", 502.53, 460.98, 10309.43, 0.22, 28013.00, 39080.98, 4898.00, 10489.00, 6328.25, 13822.00, 15.49, 19.57, 0.065, 0.020, 0.280, 0.015, 0.35, 76.20),
    ("SHW", "The Sherwin-Williams Company", "Materials", "Specialty Chemicals", 340.08, 242.76, 3378.88, 0.21, 15031.70, 3877.58, 293.50, 3886.70, 1380.66, 4709.10, 10.85, 13.50, 0.050, 0.025, 0.160, 0.015, 0.28, 99.41),
    ("APD", "Air Products and Chemicals", "Materials", "Specialty Chemicals", 303.26, 222.69, 3154.72, 0.19, 18271.20, 13883.77, 1000.00, 4570.80, 6068.30, 4652.20, 10.58, 14.45, 0.065, 0.025, 0.250, 0.020, 0.85, 56.57),
    ("FCX", "Freeport-McMoRan Inc.", "Materials", "Copper", 66.37, 1436.02, 8367.16, 0.32, 10359.00, 20108.55, 4080.00, 5900.00, 3740.75, 9554.00, 2.03, 4.36, 0.080, 0.120, 0.250, 0.070, 0.50, 18.00),
    ("ECL", "Ecolab Inc.", "Materials", "Specialty Chemicals", 289.15, 280.33, 2798.23, 0.21, 13918.80, 10055.39, 5135.30, 3056.80, 1581.98, 4135.70, 7.45, 9.38, 0.065, 0.020, 0.150, 0.015, 0.32, 59.67),
    ("NEM", "Newmont Corporation", "Materials", "Gold", 113.93, 1053.69, 7173.37, 0.28, 5598.00, 35066.88, 9009.00, 12628.00, 3812.12, 17058.00, 7.93, 10.12, 0.075, 0.120, 0.210, 0.060, 0.65, 23.76),
    ("CTVA", "Corteva Inc.", "Materials", "Agricultural Inputs", 12.77, 667.20, 525.00, 0.20, 4774.00, 8102.43, 1905.00, 600.00, 195.00, 678.00, 1.62, 1.13, 0.050, 0.030, 0.120, 0.020, 0.32, 7.41),
    ("DOW", "Dow Inc.", "Materials", "Chemicals", 30.04, 722.34, 1605.19, 0.22, 19436.00, 15859.71, 4236.00, 3866.00, 3628.37, 3963.00, 1.20, 1.73, 0.035, 0.040, 0.065, 0.020, 0.55, 57.49),
    ("NUE", "Nucor Corporation", "Materials", "Steel", 254.18, 226.88, 6932.18, 0.23, 7099.00, 22109.03, 2692.00, 4424.00, 3740.63, 5681.00, 12.54, 20.95, 0.045, 0.070, 0.120, 0.035, 0.55, 157.54),
    ("PPG", "PPG Industries Inc.", "Materials", "Specialty Chemicals", 110.94, 222.30, 1849.00, 0.22, 7468.00, 8442.95, 1607.00, 2164.00, 1059.37, 2698.00, 6.96, 8.58, 0.045, 0.020, 0.120, 0.015, 0.25, 73.21),
    ("EMN", "Eastman Chemical Company", "Materials", "Specialty Chemicals", 64.17, 114.33, 742.71, 0.21, 5466.00, 6096.01, 693.00, 991.00, 446.37, 1393.00, 3.83, 6.64, 0.040, 0.030, 0.130, 0.020, 0.45, 77.59),
    ("ALB", "Albemarle Corporation", "Materials", "Specialty Chemicals", 92.16, 118.01, 833.36, 0.22, 1998.94, 8040.86, 1631.69, 1800.33, 465.99, 1482.47, 0.27, 10.80, 0.090, 0.150, 0.140, 0.080, 0.90, 50.15),
    ("IFF", "International Flavors & Fragrances", "Materials", "Specialty Chemicals", 91.66, 255.15, 1302.78, 0.20, 6279.00, 13967.67, 569.00, 1161.00, 2882.00, 1911.00, 1.01, 3.99, 0.045, 0.020, 0.120, 0.015, 0.38, 42.11),
    ("BALL", "Ball Corporation", "Materials", "Packaging & Containers", 65.11, 264.70, 1318.43, 0.21, 7582.00, 5748.03, 500.00, 1426.00, 1046.12, 2076.00, 3.51, 4.52, 0.040, 0.020, 0.100, 0.015, 0.45, 53.59),
    ("IP", "International Paper Company", "Materials", "Packaging & Containers", 33.97, 529.57, 778.48, 0.22, 9903.00, 14456.73, 726.00, 2647.00, 1000.50, 3934.00, 1.31, 3.06, 0.035, 0.025, 0.060, 0.015, 0.60, 45.77),
    ("PKG", "Packaging Corp. of America", "Materials", "Packaging & Containers", 246.89, 89.10, 1397.49, 0.23, 4404.30, 4623.13, 593.80, 1624.10, 1191.15, 2000.10, 7.69, 13.38, 0.045, 0.020, 0.150, 0.015, 0.35, 107.19),
    ("AMCR", "Amcor plc", "Materials", "Packaging & Containers", 45.99, 461.95, 6000.00, 0.21, 15140.00, 11789.78, 1115.00, 2151.00, 647.00, 3536.00, 2.38, 4.33, 0.035, 0.015, 0.110, 0.010, 0.35, 50.75),
    ("CF", "CF Industries Holdings", "Materials", "Agricultural Inputs", 116.66, 151.34, 2899.24, 0.22, 3613.00, 5738.29, 2480.00, 2977.00, 1700.25, 3873.00, 13.48, 11.30, 0.045, 0.060, 0.340, 0.050, 0.25, 49.56),
    ("MOS", "The Mosaic Company", "Materials", "Agricultural Inputs", 17.23, 317.90, 725.47, 0.24, 6079.10, 11463.95, 294.00, 444.00, 1190.28, 1718.70, 1.33, 1.54, 0.040, 0.070, 0.100, 0.040, 0.60, 38.56),
    ("FMC", "FMC Corporation", "Materials", "Agricultural Inputs", 5.01, 155.55, 195.00, 0.16, 4402.70, 2033.14, 476.60, 156.40, 35.00, 269.30, 0.85, 1.39, 0.045, 0.030, 0.170, 0.020, 0.18, 25.95),
    ("CE", "Celanese Corporation", "Materials", "Chemicals", 46.35, 109.75, 491.59, 0.20, 12397.00, 4167.06, 1364.00, 984.00, 34.12, 1677.00, 3.09, 6.03, 0.045, 0.030, 0.130, 0.020, 0.35, 88.57),
    ("SW", "Smurfit Westrock plc", "Materials", "Packaging & Containers", 42.23, 524.52, 2815.33, 0.22, 14164.00, 18060.37, 677.00, 3297.00, 2082.00, 4576.00, 0.95, 3.55, 0.050, 0.025, 0.110, 0.015, 0.45, 59.90),
    ("AVY", "Avery Dennison Corporation", "Materials", "Packaging & Containers", 180.64, 75.79, 812.05, 0.23, 3685.20, 2319.27, 274.70, 1233.60, 229.00, 1496.50, 9.13, 11.19, 0.055, 0.015, 0.110, 0.010, 0.25, 120.11),
    ("VMC", "Vulcan Materials Company", "Materials", "Building Materials", 265.94, 129.58, 1552.93, 0.22, 4942.10, 8476.39, 194.20, 1804.40, 960.80, 2340.30, 8.48, 10.22, 0.065, 0.020, 0.200, 0.015, 0.35, 61.98),
    ("MLM", "Martin Marietta Materials", "Materials", "Building Materials", 509.00, 71.02, 1481.68, 0.22, 6345.00, 13654.90, 112.00, 1519.00, 925.63, 2126.00, 15.38, 21.29, 0.065, 0.020, 0.240, 0.015, 0.38, 110.91),
    ("DD", "DuPont de Nemours Inc.", "Materials", "Specialty Chemicals", 132.09, 135.04, 2813.75, 0.21, 3179.00, 13769.39, 1740.00, 1195.00, 1125.50, 1583.00, 3.72, 7.99, 0.050, 0.020, 0.150, 0.015, 0.32, 50.82),
    ("RPM", "RPM International Inc.", "Materials", "Specialty Chemicals", 100.55, 127.53, 722.70, 0.23, 2741.25, 3478.23, 312.84, 925.13, 371.65, 1235.32, 5.41, 6.61, 0.050, 0.015, 0.120, 0.010, 0.22, 62.76),
    ("OLN", "Olin Corporation", "Materials", "Chemicals", 14.95, 113.98, 208.29, 0.22, 3407.50, 1711.45, 177.40, 307.20, 94.07, 628.60, 0.94, 0.46, 0.045, 0.035, 0.090, 0.025, 0.35, 58.83),
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

    # Purge any legacy/delisted tickers not in the current active universe
    active_tickers = [item[0] for item in STOCKS_RAW]
    placeholders = ",".join(["?"] * len(active_tickers))
    cursor.execute(f"DELETE FROM stocks WHERE ticker NOT IN ({placeholders})", active_tickers)
    cursor.execute(f"DELETE FROM monte_carlo_cache WHERE ticker NOT IN ({placeholders})", active_tickers)
    cursor.execute(f"DELETE FROM historical_series WHERE ticker NOT IN ({placeholders})", active_tickers)

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
