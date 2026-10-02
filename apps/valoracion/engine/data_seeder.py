"""
Data Seeder for S&P 500 / NYSE / NASDAQ Institutional Universe
Covers all 11 GICS sectors with verified financial profiles, balance sheet items,
pre-run Monte Carlo simulations, and 60-period econometric historical time series.
"""

import numpy as np
import pandas as pd
from datetime import datetime
from engine.database import (
    init_db,
    get_db_connection,
    save_monte_carlo_result
)
from engine.accounting import compute_all_metrics
from engine.monte_carlo import run_monte_carlo_simulation

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

# Baseline stock specifications across 11 sectors
STOCKS_DATA = [
    # Information Technology
    {
        "ticker": "AAPL", "name": "Apple Inc.", "sector": "Information Technology", "industry": "Consumer Electronics",
        "market_price": 224.23, "shares_outstanding": 15200.0,
        "ebit": 123200.0, "tax_rate": 0.15, "total_debt": 106000.0, "total_equity": 66800.0, "cash_and_equivalents": 61500.0,
        "operating_cash_flow": 118000.0, "capex": 9500.0, "ebitda": 134500.0,
        "trailing_eps": 6.57, "forward_eps": 7.45,
        "rev_growth_mean": 0.075, "rev_growth_std": 0.035, "margin_mean": 0.31, "margin_std": 0.02,
        "reinvestment_rate_mean": 0.18, "revenue_ps": 25.7
    },
    {
        "ticker": "MSFT", "name": "Microsoft Corporation", "sector": "Information Technology", "industry": "Systems Software & Cloud",
        "market_price": 428.50, "shares_outstanding": 7430.0,
        "ebit": 109400.0, "tax_rate": 0.18, "total_debt": 77000.0, "total_equity": 268000.0, "cash_and_equivalents": 75500.0,
        "operating_cash_flow": 118500.0, "capex": 44500.0, "ebitda": 130000.0,
        "trailing_eps": 11.80, "forward_eps": 13.25,
        "rev_growth_mean": 0.14, "rev_growth_std": 0.03, "margin_mean": 0.44, "margin_std": 0.025,
        "reinvestment_rate_mean": 0.38, "revenue_ps": 33.0
    },
    {
        "ticker": "NVDA", "name": "NVIDIA Corporation", "sector": "Information Technology", "industry": "Semiconductors & AI Hardware",
        "market_price": 128.40, "shares_outstanding": 24500.0,
        "ebit": 72500.0, "tax_rate": 0.14, "total_debt": 11000.0, "total_equity": 58000.0, "cash_and_equivalents": 34800.0,
        "operating_cash_flow": 60500.0, "capex": 3200.0, "ebitda": 75000.0,
        "trailing_eps": 2.55, "forward_eps": 4.10,
        "rev_growth_mean": 0.35, "rev_growth_std": 0.15, "margin_mean": 0.58, "margin_std": 0.06,
        "reinvestment_rate_mean": 0.15, "revenue_ps": 4.9
    },
    {
        "ticker": "AVGO", "name": "Broadcom Inc.", "sector": "Information Technology", "industry": "Semiconductors",
        "market_price": 172.80, "shares_outstanding": 4680.0,
        "ebit": 19800.0, "tax_rate": 0.12, "total_debt": 71500.0, "total_equity": 69000.0, "cash_and_equivalents": 10000.0,
        "operating_cash_flow": 21000.0, "capex": 1900.0, "ebitda": 26500.0,
        "trailing_eps": 4.10, "forward_eps": 6.15,
        "rev_growth_mean": 0.18, "rev_growth_std": 0.05, "margin_mean": 0.45, "margin_std": 0.03,
        "reinvestment_rate_mean": 0.22, "revenue_ps": 11.0
    },
    {
        "ticker": "CRM", "name": "Salesforce Inc.", "sector": "Information Technology", "industry": "Application Software",
        "market_price": 284.10, "shares_outstanding": 965.0,
        "ebit": 6500.0, "tax_rate": 0.20, "total_debt": 12500.0, "total_equity": 59500.0, "cash_and_equivalents": 14200.0,
        "operating_cash_flow": 12400.0, "capex": 800.0, "ebitda": 9500.0,
        "trailing_eps": 5.60, "forward_eps": 10.20,
        "rev_growth_mean": 0.10, "rev_growth_std": 0.02, "margin_mean": 0.20, "margin_std": 0.03,
        "reinvestment_rate_mean": 0.15, "revenue_ps": 37.0
    },
    # Health Care
    {
        "ticker": "UNH", "name": "UnitedHealth Group Inc.", "sector": "Health Care", "industry": "Managed Healthcare",
        "market_price": 574.60, "shares_outstanding": 920.0,
        "ebit": 32800.0, "tax_rate": 0.22, "total_debt": 74000.0, "total_equity": 98000.0, "cash_and_equivalents": 31000.0,
        "operating_cash_flow": 29000.0, "capex": 3300.0, "ebitda": 36500.0,
        "trailing_eps": 24.80, "forward_eps": 27.60,
        "rev_growth_mean": 0.08, "rev_growth_std": 0.02, "margin_mean": 0.088, "margin_std": 0.008,
        "reinvestment_rate_mean": 0.20, "revenue_ps": 405.0
    },
    {
        "ticker": "LLY", "name": "Eli Lilly and Company", "sector": "Health Care", "industry": "Pharmaceuticals",
        "market_price": 892.40, "shares_outstanding": 950.0,
        "ebit": 13500.0, "tax_rate": 0.14, "total_debt": 28000.0, "total_equity": 14500.0, "cash_and_equivalents": 3200.0,
        "operating_cash_flow": 8900.0, "capex": 4200.0, "ebitda": 15800.0,
        "trailing_eps": 8.70, "forward_eps": 21.50,
        "rev_growth_mean": 0.24, "rev_growth_std": 0.06, "margin_mean": 0.35, "margin_std": 0.04,
        "reinvestment_rate_mean": 0.35, "revenue_ps": 42.0
    },
    {
        "ticker": "JNJ", "name": "Johnson & Johnson", "sector": "Health Care", "industry": "Pharmaceuticals & MedTech",
        "market_price": 161.20, "shares_outstanding": 2400.0,
        "ebit": 23500.0, "tax_rate": 0.16, "total_debt": 36000.0, "total_equity": 75000.0, "cash_and_equivalents": 24000.0,
        "operating_cash_flow": 22800.0, "capex": 4600.0, "ebitda": 28200.0,
        "trailing_eps": 6.80, "forward_eps": 10.05,
        "rev_growth_mean": 0.045, "rev_growth_std": 0.02, "margin_mean": 0.27, "margin_std": 0.015,
        "reinvestment_rate_mean": 0.25, "revenue_ps": 36.0
    },
    {
        "ticker": "ABBV", "name": "AbbVie Inc.", "sector": "Health Care", "industry": "Biotechnology",
        "market_price": 188.50, "shares_outstanding": 1765.0,
        "ebit": 18200.0, "tax_rate": 0.15, "total_debt": 64000.0, "total_equity": 12000.0, "cash_and_equivalents": 13000.0,
        "operating_cash_flow": 22000.0, "capex": 1100.0, "ebitda": 22500.0,
        "trailing_eps": 4.25, "forward_eps": 11.20,
        "rev_growth_mean": 0.05, "rev_growth_std": 0.03, "margin_mean": 0.34, "margin_std": 0.03,
        "reinvestment_rate_mean": 0.18, "revenue_ps": 31.0
    },
    # Financials
    {
        "ticker": "JPM", "name": "JPMorgan Chase & Co.", "sector": "Financials", "industry": "Diversified Banking",
        "market_price": 218.40, "shares_outstanding": 2860.0,
        "ebit": 65000.0, "tax_rate": 0.20, "total_debt": 380000.0, "total_equity": 328000.0, "cash_and_equivalents": 540000.0,
        "operating_cash_flow": 52000.0, "capex": 4500.0, "ebitda": 68000.0,
        "trailing_eps": 17.80, "forward_eps": 18.50,
        "rev_growth_mean": 0.07, "rev_growth_std": 0.03, "margin_mean": 0.38, "margin_std": 0.03,
        "reinvestment_rate_mean": 0.20, "revenue_ps": 58.0
    },
    {
        "ticker": "BAC", "name": "Bank of America Corporation", "sector": "Financials", "industry": "Major Commercial Banks",
        "market_price": 41.20, "shares_outstanding": 7820.0,
        "ebit": 31000.0, "tax_rate": 0.18, "total_debt": 290000.0, "total_equity": 292000.0, "cash_and_equivalents": 380000.0,
        "operating_cash_flow": 28000.0, "capex": 2800.0, "ebitda": 33500.0,
        "trailing_eps": 3.25, "forward_eps": 3.60,
        "rev_growth_mean": 0.05, "rev_growth_std": 0.03, "margin_mean": 0.30, "margin_std": 0.03,
        "reinvestment_rate_mean": 0.22, "revenue_ps": 13.0
    },
    {
        "ticker": "V", "name": "Visa Inc.", "sector": "Financials", "industry": "Transaction & Payment Processing",
        "market_price": 282.60, "shares_outstanding": 2010.0,
        "ebit": 23400.0, "tax_rate": 0.19, "total_debt": 21500.0, "total_equity": 38800.0, "cash_and_equivalents": 19200.0,
        "operating_cash_flow": 20800.0, "capex": 1100.0, "ebitda": 24800.0,
        "trailing_eps": 9.35, "forward_eps": 11.10,
        "rev_growth_mean": 0.10, "rev_growth_std": 0.02, "margin_mean": 0.67, "margin_std": 0.02,
        "reinvestment_rate_mean": 0.12, "revenue_ps": 17.5
    },
    {
        "ticker": "MA", "name": "Mastercard Incorporated", "sector": "Financials", "industry": "Payment Networks",
        "market_price": 496.30, "shares_outstanding": 925.0,
        "ebit": 15200.0, "tax_rate": 0.18, "total_debt": 16500.0, "total_equity": 7200.0, "cash_and_equivalents": 9500.0,
        "operating_cash_flow": 13100.0, "capex": 600.0, "ebitda": 16100.0,
        "trailing_eps": 12.80, "forward_eps": 14.50,
        "rev_growth_mean": 0.11, "rev_growth_std": 0.025, "margin_mean": 0.58, "margin_std": 0.02,
        "reinvestment_rate_mean": 0.14, "revenue_ps": 28.0
    },
    # Consumer Discretionary
    {
        "ticker": "AMZN", "name": "Amazon.com Inc.", "sector": "Consumer Discretionary", "industry": "Broadline Retail & Cloud",
        "market_price": 186.50, "shares_outstanding": 10500.0,
        "ebit": 48500.0, "tax_rate": 0.19, "total_debt": 135000.0, "total_equity": 230000.0, "cash_and_equivalents": 89000.0,
        "operating_cash_flow": 108000.0, "capex": 58000.0, "ebitda": 86000.0,
        "trailing_eps": 4.15, "forward_eps": 5.80,
        "rev_growth_mean": 0.12, "rev_growth_std": 0.03, "margin_mean": 0.085, "margin_std": 0.02,
        "reinvestment_rate_mean": 0.45, "revenue_ps": 58.0
    },
    {
        "ticker": "TSLA", "name": "Tesla Inc.", "sector": "Consumer Discretionary", "industry": "Automobiles & EV",
        "market_price": 242.10, "shares_outstanding": 3190.0,
        "ebit": 8900.0, "tax_rate": 0.15, "total_debt": 7500.0, "total_equity": 66000.0, "cash_and_equivalents": 30500.0,
        "operating_cash_flow": 12500.0, "capex": 9800.0, "ebitda": 14200.0,
        "trailing_eps": 2.20, "forward_eps": 3.10,
        "rev_growth_mean": 0.15, "rev_growth_std": 0.08, "margin_mean": 0.09, "margin_std": 0.03,
        "reinvestment_rate_mean": 0.50, "revenue_ps": 30.5
    },
    {
        "ticker": "HD", "name": "The Home Depot Inc.", "sector": "Consumer Discretionary", "industry": "Home Improvement Retail",
        "market_price": 402.30, "shares_outstanding": 995.0,
        "ebit": 21800.0, "tax_rate": 0.23, "total_debt": 52000.0, "total_equity": 1500.0, "cash_and_equivalents": 3800.0,
        "operating_cash_flow": 21200.0, "capex": 3200.0, "ebitda": 24800.0,
        "trailing_eps": 15.10, "forward_eps": 16.20,
        "rev_growth_mean": 0.04, "rev_growth_std": 0.02, "margin_mean": 0.145, "margin_std": 0.01,
        "reinvestment_rate_mean": 0.20, "revenue_ps": 153.0
    },
    {
        "ticker": "MCD", "name": "McDonald's Corporation", "sector": "Consumer Discretionary", "industry": "Restaurants",
        "market_price": 298.40, "shares_outstanding": 720.0,
        "ebit": 11600.0, "tax_rate": 0.21, "total_debt": 51000.0, "total_equity": -4500.0, "cash_and_equivalents": 2100.0,
        "operating_cash_flow": 9600.0, "capex": 2400.0, "ebitda": 13500.0,
        "trailing_eps": 11.50, "forward_eps": 12.60,
        "rev_growth_mean": 0.055, "rev_growth_std": 0.02, "margin_mean": 0.45, "margin_std": 0.02,
        "reinvestment_rate_mean": 0.25, "revenue_ps": 35.5
    },
    # Communication Services
    {
        "ticker": "GOOGL", "name": "Alphabet Inc.", "sector": "Communication Services", "industry": "Interactive Media & Services",
        "market_price": 165.20, "shares_outstanding": 12400.0,
        "ebit": 98500.0, "tax_rate": 0.16, "total_debt": 28000.0, "total_equity": 305000.0, "cash_and_equivalents": 110000.0,
        "operating_cash_flow": 105000.0, "capex": 42000.0, "ebitda": 118000.0,
        "trailing_eps": 6.85, "forward_eps": 7.90,
        "rev_growth_mean": 0.13, "rev_growth_std": 0.03, "margin_mean": 0.30, "margin_std": 0.02,
        "reinvestment_rate_mean": 0.35, "revenue_ps": 26.5
    },
    {
        "ticker": "META", "name": "Meta Platforms Inc.", "sector": "Communication Services", "industry": "Social Media & VR",
        "market_price": 585.10, "shares_outstanding": 2540.0,
        "ebit": 56000.0, "tax_rate": 0.17, "total_debt": 37000.0, "total_equity": 160000.0, "cash_and_equivalents": 58000.0,
        "operating_cash_flow": 76000.0, "capex": 37000.0, "ebitda": 68000.0,
        "trailing_eps": 19.80, "forward_eps": 24.30,
        "rev_growth_mean": 0.18, "rev_growth_std": 0.05, "margin_mean": 0.38, "margin_std": 0.03,
        "reinvestment_rate_mean": 0.40, "revenue_ps": 56.0
    },
    {
        "ticker": "NFLX", "name": "Netflix Inc.", "sector": "Communication Services", "industry": "Entertainment Streaming",
        "market_price": 708.20, "shares_outstanding": 432.0,
        "ebit": 8200.0, "tax_rate": 0.15, "total_debt": 14000.0, "total_equity": 22000.0, "cash_and_equivalents": 7200.0,
        "operating_cash_flow": 7300.0, "capex": 400.0, "ebitda": 9500.0,
        "trailing_eps": 16.50, "forward_eps": 21.00,
        "rev_growth_mean": 0.14, "rev_growth_std": 0.03, "margin_mean": 0.23, "margin_std": 0.02,
        "reinvestment_rate_mean": 0.15, "revenue_ps": 83.0
    },
    {
        "ticker": "DIS", "name": "The Walt Disney Company", "sector": "Communication Services", "industry": "Entertainment & Theme Parks",
        "market_price": 96.40, "shares_outstanding": 1820.0,
        "ebit": 11500.0, "tax_rate": 0.22, "total_debt": 47000.0, "total_equity": 102000.0, "cash_and_equivalents": 6200.0,
        "operating_cash_flow": 14000.0, "capex": 5100.0, "ebitda": 15800.0,
        "trailing_eps": 3.80, "forward_eps": 5.20,
        "rev_growth_mean": 0.06, "rev_growth_std": 0.03, "margin_mean": 0.13, "margin_std": 0.02,
        "reinvestment_rate_mean": 0.35, "revenue_ps": 49.0
    },
    # Industrials
    {
        "ticker": "CAT", "name": "Caterpillar Inc.", "sector": "Industrials", "industry": "Heavy Construction Machinery",
        "market_price": 388.50, "shares_outstanding": 485.0,
        "ebit": 13900.0, "tax_rate": 0.22, "total_debt": 37000.0, "total_equity": 21000.0, "cash_and_equivalents": 6500.0,
        "operating_cash_flow": 12800.0, "capex": 2100.0, "ebitda": 16200.0,
        "trailing_eps": 21.60, "forward_eps": 22.80,
        "rev_growth_mean": 0.06, "rev_growth_std": 0.04, "margin_mean": 0.21, "margin_std": 0.025,
        "reinvestment_rate_mean": 0.25, "revenue_ps": 138.0
    },
    {
        "ticker": "GE", "name": "GE Aerospace", "sector": "Industrials", "industry": "Aerospace & Defense Engines",
        "market_price": 182.30, "shares_outstanding": 1090.0,
        "ebit": 6800.0, "tax_rate": 0.20, "total_debt": 21000.0, "total_equity": 28000.0, "cash_and_equivalents": 13500.0,
        "operating_cash_flow": 6400.0, "capex": 1200.0, "ebitda": 8100.0,
        "trailing_eps": 4.85, "forward_eps": 5.70,
        "rev_growth_mean": 0.09, "rev_growth_std": 0.03, "margin_mean": 0.17, "margin_std": 0.02,
        "reinvestment_rate_mean": 0.22, "revenue_ps": 34.0
    },
    {
        "ticker": "UNP", "name": "Union Pacific Corporation", "sector": "Industrials", "industry": "Rail Transportation",
        "market_price": 241.60, "shares_outstanding": 610.0,
        "ebit": 9800.0, "tax_rate": 0.23, "total_debt": 34000.0, "total_equity": 16500.0, "cash_and_equivalents": 1200.0,
        "operating_cash_flow": 9100.0, "capex": 3600.0, "ebitda": 12400.0,
        "trailing_eps": 10.90, "forward_eps": 11.90,
        "rev_growth_mean": 0.045, "rev_growth_std": 0.02, "margin_mean": 0.40, "margin_std": 0.015,
        "reinvestment_rate_mean": 0.35, "revenue_ps": 40.0
    },
    {
        "ticker": "DE", "name": "Deere & Company", "sector": "Industrials", "industry": "Agricultural Equipment",
        "market_price": 408.20, "shares_outstanding": 275.0,
        "ebit": 10200.0, "tax_rate": 0.22, "total_debt": 62000.0, "total_equity": 23500.0, "cash_and_equivalents": 5400.0,
        "operating_cash_flow": 8200.0, "capex": 1400.0, "ebitda": 11800.0,
        "trailing_eps": 27.50, "forward_eps": 25.20,
        "rev_growth_mean": 0.05, "rev_growth_std": 0.06, "margin_mean": 0.20, "margin_std": 0.03,
        "reinvestment_rate_mean": 0.25, "revenue_ps": 190.0
    },
    # Consumer Staples
    {
        "ticker": "PG", "name": "The Procter & Gamble Company", "sector": "Consumer Staples", "industry": "Household & Personal Products",
        "market_price": 172.50, "shares_outstanding": 2360.0,
        "ebit": 19800.0, "tax_rate": 0.21, "total_debt": 35000.0, "total_equity": 48500.0, "cash_and_equivalents": 8500.0,
        "operating_cash_flow": 18600.0, "capex": 3300.0, "ebitda": 22600.0,
        "trailing_eps": 6.20, "forward_eps": 6.95,
        "rev_growth_mean": 0.04, "rev_growth_std": 0.015, "margin_mean": 0.24, "margin_std": 0.01,
        "reinvestment_rate_mean": 0.20, "revenue_ps": 35.5
    },
    {
        "ticker": "KO", "name": "The Coca-Cola Company", "sector": "Consumer Staples", "industry": "Non-Alcoholic Beverages",
        "market_price": 68.40, "shares_outstanding": 4310.0,
        "ebit": 13200.0, "tax_rate": 0.20, "total_debt": 42000.0, "total_equity": 27500.0, "cash_and_equivalents": 13500.0,
        "operating_cash_flow": 11800.0, "capex": 1900.0, "ebitda": 14700.0,
        "trailing_eps": 2.50, "forward_eps": 2.85,
        "rev_growth_mean": 0.05, "rev_growth_std": 0.02, "margin_mean": 0.29, "margin_std": 0.015,
        "reinvestment_rate_mean": 0.22, "revenue_ps": 10.7
    },
    {
        "ticker": "PEP", "name": "PepsiCo Inc.", "sector": "Consumer Staples", "industry": "Food & Snacks",
        "market_price": 171.80, "shares_outstanding": 1375.0,
        "ebit": 13800.0, "tax_rate": 0.21, "total_debt": 44000.0, "total_equity": 19200.0, "cash_and_equivalents": 8200.0,
        "operating_cash_flow": 13400.0, "capex": 5100.0, "ebitda": 16500.0,
        "trailing_eps": 6.65, "forward_eps": 8.15,
        "rev_growth_mean": 0.045, "rev_growth_std": 0.02, "margin_mean": 0.15, "margin_std": 0.01,
        "reinvestment_rate_mean": 0.32, "revenue_ps": 67.0
    },
    {
        "ticker": "COST", "name": "Costco Wholesale Corporation", "sector": "Consumer Staples", "industry": "Wholesale Clubs",
        "market_price": 894.20, "shares_outstanding": 443.0,
        "ebit": 9200.0, "tax_rate": 0.24, "total_debt": 9100.0, "total_equity": 26000.0, "cash_and_equivalents": 11500.0,
        "operating_cash_flow": 11200.0, "capex": 4800.0, "ebitda": 11400.0,
        "trailing_eps": 16.55, "forward_eps": 17.80,
        "rev_growth_mean": 0.08, "rev_growth_std": 0.02, "margin_mean": 0.037, "margin_std": 0.003,
        "reinvestment_rate_mean": 0.35, "revenue_ps": 570.0
    },
    # Energy
    {
        "ticker": "XOM", "name": "Exxon Mobil Corporation", "sector": "Energy", "industry": "Integrated Oil & Gas",
        "market_price": 116.80, "shares_outstanding": 4450.0,
        "ebit": 51000.0, "tax_rate": 0.28, "total_debt": 41500.0, "total_equity": 215000.0, "cash_and_equivalents": 31000.0,
        "operating_cash_flow": 55000.0, "capex": 23000.0, "ebitda": 69000.0,
        "trailing_eps": 8.90, "forward_eps": 8.40,
        "rev_growth_mean": 0.03, "rev_growth_std": 0.12, "margin_mean": 0.15, "margin_std": 0.05,
        "reinvestment_rate_mean": 0.45, "revenue_ps": 78.0
    },
    {
        "ticker": "CVX", "name": "Chevron Corporation", "sector": "Energy", "industry": "Integrated Oil & Gas",
        "market_price": 151.20, "shares_outstanding": 1840.0,
        "ebit": 26800.0, "tax_rate": 0.26, "total_debt": 22000.0, "total_equity": 162000.0, "cash_and_equivalents": 6800.0,
        "operating_cash_flow": 32000.0, "capex": 15500.0, "ebitda": 38500.0,
        "trailing_eps": 10.40, "forward_eps": 11.50,
        "rev_growth_mean": 0.035, "rev_growth_std": 0.11, "margin_mean": 0.14, "margin_std": 0.045,
        "reinvestment_rate_mean": 0.48, "revenue_ps": 109.0
    },
    {
        "ticker": "SLB", "name": "SLB (Schlumberger Limited)", "sector": "Energy", "industry": "Oil & Gas Equipment & Services",
        "market_price": 43.80, "shares_outstanding": 1420.0,
        "ebit": 5600.0, "tax_rate": 0.20, "total_debt": 11800.0, "total_equity": 20500.0, "cash_and_equivalents": 3800.0,
        "operating_cash_flow": 6100.0, "capex": 2500.0, "ebitda": 7800.0,
        "trailing_eps": 3.10, "forward_eps": 3.75,
        "rev_growth_mean": 0.08, "rev_growth_std": 0.08, "margin_mean": 0.16, "margin_std": 0.03,
        "reinvestment_rate_mean": 0.40, "revenue_ps": 24.0
    },
    # Utilities
    {
        "ticker": "NEE", "name": "NextEra Energy Inc.", "sector": "Utilities", "industry": "Electric Utilities & Clean Power",
        "market_price": 82.50, "shares_outstanding": 2060.0,
        "ebit": 9800.0, "tax_rate": 0.12, "total_debt": 78000.0, "total_equity": 44000.0, "cash_and_equivalents": 2900.0,
        "operating_cash_flow": 11400.0, "capex": 21000.0, "ebitda": 15200.0,
        "trailing_eps": 3.40, "forward_eps": 3.65,
        "rev_growth_mean": 0.075, "rev_growth_std": 0.03, "margin_mean": 0.35, "margin_std": 0.02,
        "reinvestment_rate_mean": 0.75, "revenue_ps": 13.5
    },
    {
        "ticker": "SO", "name": "The Southern Company", "sector": "Utilities", "industry": "Regulated Electric Utilities",
        "market_price": 89.10, "shares_outstanding": 1095.0,
        "ebit": 6800.0, "tax_rate": 0.15, "total_debt": 61000.0, "total_equity": 32500.0, "cash_and_equivalents": 1800.0,
        "operating_cash_flow": 7900.0, "capex": 8600.0, "ebitda": 10200.0,
        "trailing_eps": 3.85, "forward_eps": 4.10,
        "rev_growth_mean": 0.04, "rev_growth_std": 0.015, "margin_mean": 0.26, "margin_std": 0.015,
        "reinvestment_rate_mean": 0.65, "revenue_ps": 24.0
    },
    {
        "ticker": "DUK", "name": "Duke Energy Corporation", "sector": "Utilities", "industry": "Electric Power Distribution",
        "market_price": 112.40, "shares_outstanding": 772.0,
        "ebit": 7400.0, "tax_rate": 0.14, "total_debt": 81000.0, "total_equity": 50000.0, "cash_and_equivalents": 800.0,
        "operating_cash_flow": 9800.0, "capex": 11800.0, "ebitda": 12800.0,
        "trailing_eps": 5.40, "forward_eps": 6.10,
        "rev_growth_mean": 0.04, "rev_growth_std": 0.015, "margin_mean": 0.25, "margin_std": 0.015,
        "reinvestment_rate_mean": 0.70, "revenue_ps": 38.0
    },
    # Real Estate
    {
        "ticker": "PLD", "name": "Prologis Inc.", "sector": "Real Estate", "industry": "Industrial Logistics REIT",
        "market_price": 118.60, "shares_outstanding": 925.0,
        "ebit": 4200.0, "tax_rate": 0.04, "total_debt": 31000.0, "total_equity": 58000.0, "cash_and_equivalents": 1400.0,
        "operating_cash_flow": 5200.0, "capex": 1200.0, "ebitda": 6100.0,
        "trailing_eps": 3.45, "forward_eps": 5.50,
        "rev_growth_mean": 0.08, "rev_growth_std": 0.03, "margin_mean": 0.52, "margin_std": 0.02,
        "reinvestment_rate_mean": 0.35, "revenue_ps": 8.7
    },
    {
        "ticker": "AMT", "name": "American Tower Corporation", "sector": "Real Estate", "industry": "Telecom Tower REIT",
        "market_price": 218.70, "shares_outstanding": 468.0,
        "ebit": 4600.0, "tax_rate": 0.05, "total_debt": 41000.0, "total_equity": 13500.0, "cash_and_equivalents": 2100.0,
        "operating_cash_flow": 4800.0, "capex": 1500.0, "ebitda": 7200.0,
        "trailing_eps": 4.10, "forward_eps": 10.20,
        "rev_growth_mean": 0.065, "rev_growth_std": 0.025, "margin_mean": 0.42, "margin_std": 0.02,
        "reinvestment_rate_mean": 0.30, "revenue_ps": 24.0
    },
    {
        "ticker": "EQIX", "name": "Equinix Inc.", "sector": "Real Estate", "industry": "Data Center REIT",
        "market_price": 862.50, "shares_outstanding": 95.0,
        "ebit": 2100.0, "tax_rate": 0.06, "total_debt": 18500.0, "total_equity": 14200.0, "cash_and_equivalents": 2800.0,
        "operating_cash_flow": 3400.0, "capex": 2800.0, "ebitda": 4100.0,
        "trailing_eps": 11.20, "forward_eps": 35.80,
        "rev_growth_mean": 0.11, "rev_growth_std": 0.03, "margin_mean": 0.25, "margin_std": 0.02,
        "reinvestment_rate_mean": 0.45, "revenue_ps": 88.0
    },
    # Materials
    {
        "ticker": "LIN", "name": "Linde plc", "sector": "Materials", "industry": "Industrial Gases",
        "market_price": 458.20, "shares_outstanding": 480.0,
        "ebit": 9400.0, "tax_rate": 0.22, "total_debt": 19500.0, "total_equity": 39000.0, "cash_and_equivalents": 4800.0,
        "operating_cash_flow": 9800.0, "capex": 3900.0, "ebitda": 12800.0,
        "trailing_eps": 13.10, "forward_eps": 15.60,
        "rev_growth_mean": 0.065, "rev_growth_std": 0.02, "margin_mean": 0.28, "margin_std": 0.015,
        "reinvestment_rate_mean": 0.35, "revenue_ps": 70.0
    },
    {
        "ticker": "SHW", "name": "The Sherwin-Williams Company", "sector": "Materials", "industry": "Paints & Coatings",
        "market_price": 372.40, "shares_outstanding": 252.0,
        "ebit": 3700.0, "tax_rate": 0.21, "total_debt": 12200.0, "total_equity": 4100.0, "cash_and_equivalents": 600.0,
        "operating_cash_flow": 3500.0, "capex": 950.0, "ebitda": 4400.0,
        "trailing_eps": 9.80, "forward_eps": 11.50,
        "rev_growth_mean": 0.05, "rev_growth_std": 0.025, "margin_mean": 0.16, "margin_std": 0.015,
        "reinvestment_rate_mean": 0.28, "revenue_ps": 91.0
    },
    {
        "ticker": "FCX", "name": "Freeport-McMoRan Inc.", "sector": "Materials", "industry": "Copper & Gold Mining",
        "market_price": 46.80, "shares_outstanding": 1440.0,
        "ebit": 5900.0, "tax_rate": 0.32, "total_debt": 9800.0, "total_equity": 17500.0, "cash_and_equivalents": 6400.0,
        "operating_cash_flow": 6800.0, "capex": 4600.0, "ebitda": 8500.0,
        "trailing_eps": 1.45, "forward_eps": 2.25,
        "rev_growth_mean": 0.08, "rev_growth_std": 0.12, "margin_mean": 0.25, "margin_std": 0.07,
        "reinvestment_rate_mean": 0.50, "revenue_ps": 16.0
    }
]


def generate_synthetic_history(ticker: str, current_price: float, beta: float = 1.1) -> pd.DataFrame:
    """
    Generates 60 monthly periods of realistic market and excess returns for econometric testing.
    """
    np.random.seed(abs(hash(ticker)) % 10000)
    n = 60
    dates = pd.date_range(end=datetime.now(), periods=n, freq="30D").strftime("%Y-%m-%d").tolist()
    
    # Market return (S&P 500)
    mkt_ret = np.random.normal(0.009, 0.042, n)
    # Risk-free rate change
    rate_change = np.random.normal(0.0003, 0.004, n)
    # Sector specific factor
    sec_ret = 0.85 * mkt_ret + np.random.normal(0.001, 0.025, n)
    # Alpha and idiosyncratic shock
    alpha = np.random.normal(0.0015, 0.003)
    residual = np.random.normal(0.0, 0.028, n)
    
    stock_ret = alpha + beta * mkt_ret + 0.2 * sec_ret - 0.4 * rate_change + residual
    
    # Reconstruct prices backwards
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
    Seeds database with all sectors, stocks, computed metrics, MC simulations, and history.
    """
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Insert Sectors
    for sec in GICS_SECTORS:
        cursor.execute("""
            INSERT OR REPLACE INTO sectors (name, code, description)
            VALUES (?, ?, ?)
        """, (sec["name"], sec["code"], sec["description"]))
    conn.commit()

    # 2. Insert Stocks with metrics and simulations
    for s in STOCKS_DATA:
        ticker = s["ticker"]
        metrics = compute_all_metrics(s)
        
        # Run Monte Carlo simulation (5,000 trajectories)
        mc_result = run_monte_carlo_simulation(
            p0=s["market_price"],
            current_revenue_ps=s.get("revenue_ps", s["market_price"] * 0.25),
            historical_growth_mean=s.get("rev_growth_mean", 0.08),
            historical_growth_std=s.get("rev_growth_std", 0.04),
            historical_margin_mean=s.get("margin_mean", 0.20),
            historical_margin_std=s.get("margin_std", 0.03),
            tax_rate=s.get("tax_rate", 0.21),
            reinvestment_rate_mean=s.get("reinvestment_rate_mean", 0.30),
            num_simulations=5000,
            random_seed=abs(hash(ticker)) % 100000
        )
        
        p10 = mc_result["percentiles"]["p10"]
        p50 = mc_result["percentiles"]["p50"]
        p90 = mc_result["percentiles"]["p90"]

        cursor.execute("""
            INSERT OR REPLACE INTO stocks (
                ticker, name, sector, industry, market_price, shares_outstanding, market_cap,
                ebit, tax_rate, nopat, total_debt, total_equity, cash_and_equivalents,
                invested_capital, roic, operating_cash_flow, capex, fcf, fcf_yield,
                ebitda, ev, ev_ebitda, net_debt, net_debt_ebitda,
                trailing_eps, forward_eps, trailing_pe, forward_pe,
                rev_growth_mean, rev_growth_std, margin_mean, margin_std,
                reinvestment_rate_mean, mc_p10, mc_p50, mc_p90
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?
            )
        """, (
            ticker, s["name"], s["sector"], s["industry"], s["market_price"], s["shares_outstanding"], metrics["market_cap"],
            s.get("ebit"), s.get("tax_rate", 0.21), metrics["nopat"], s.get("total_debt"), s.get("total_equity"), s.get("cash_and_equivalents"),
            metrics["invested_capital"], metrics["roic"], s.get("operating_cash_flow"), s.get("capex"), metrics["fcf"], metrics["fcf_yield"],
            metrics["ebitda"], metrics["ev"], metrics["ev_ebitda"], metrics["net_debt"], metrics["net_debt_ebitda"],
            s.get("trailing_eps"), s.get("forward_eps"), metrics["trailing_pe"], metrics["forward_pe"],
            s.get("rev_growth_mean"), s.get("rev_growth_std"), s.get("margin_mean"), s.get("margin_std"),
            s.get("reinvestment_rate_mean"), p10, p50, p90
        ))
        conn.commit()

        # Cache Monte Carlo
        save_monte_carlo_result(ticker, mc_result)

        # 3. Insert Historical Series
        df_hist = generate_synthetic_history(ticker, s["market_price"])
        for _, row in df_hist.iterrows():
            cursor.execute("""
                INSERT OR REPLACE INTO historical_series (
                    ticker, date, stock_price, stock_return, market_return,
                    sector_return, rate_change_10y, stock_excess_return,
                    market_excess_return, sector_excess_return
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ticker, row["date"], row["stock_price"], row["stock_return"], row["market_return"],
                row["sector_return"], row["rate_change_10y"], row["stock_excess_return"],
                row["market_excess_return"], row["sector_excess_return"]
            ))
        conn.commit()

    conn.close()
    print("Database successfully seeded with 11 GICS sectors and quantitative datasets.")


if __name__ == "__main__":
    seed_database()
