"""
Accounting Quality & Multiples Engine
Provides strictly computed financial metrics and ratios according to institutional standards.
"""

from typing import Dict, Any, Optional

def calculate_nopat(ebit: float, effective_tax_rate: float) -> float:
    """
    NOPAT (Net Operating Profit After Tax)
    NOPAT = EBIT * (1 - Effective Tax Rate)
    """
    tax_rate = max(0.0, min(effective_tax_rate, 0.45))
    return float(ebit * (1.0 - tax_rate))

def calculate_invested_capital(
    total_debt: float,
    total_equity: float,
    cash_and_equivalents: float
) -> float:
    """
    Invested Capital = Total Debt + Total Shareholders' Equity - Cash and Cash Equivalents
    Reflects the net operating capital supplied by both debt and equity holders.
    """
    invested_cap = total_debt + total_equity - cash_and_equivalents
    return float(max(invested_cap, 1.0))

def calculate_real_roic(nopat: float, invested_capital: float) -> Optional[float]:
    """
    ROIC Real = NOPAT / Invested Capital
    Strict measure of core business operating profitability.
    """
    if invested_capital <= 0:
        return None
    return float(nopat / invested_capital)

def calculate_fcf(operating_cash_flow: float, capex: float) -> float:
    """
    Free Cash Flow = Operating Cash Flow - Capital Expenditures
    """
    return float(operating_cash_flow - abs(capex))

def calculate_fcf_yield(fcf: float, market_cap: float) -> Optional[float]:
    """
    FCF Yield = Free Cash Flow / Market Capitalization
    Represents the unencumbered cash yield relative to equity price.
    """
    if market_cap <= 0:
        return None
    return float(fcf / market_cap)

def calculate_enterprise_value(
    market_cap: float,
    total_debt: float,
    cash_and_equivalents: float,
    minority_interest: float = 0.0,
    preferred_stock: float = 0.0
) -> float:
    """
    Enterprise Value = Market Cap + Total Debt - Cash & Cash Eq. + Minority Interest + Preferred Stock
    """
    return float(market_cap + total_debt - cash_and_equivalents + minority_interest + preferred_stock)

def calculate_ev_ebitda(enterprise_value: float, ebitda: float) -> Optional[float]:
    """
    EV / EBITDA = Enterprise Value / EBITDA
    """
    if ebitda <= 0:
        return None
    return float(enterprise_value / ebitda)

def calculate_net_debt(total_debt: float, cash_and_equivalents: float) -> float:
    """
    Net Debt = Total Debt - Cash & Cash Equivalents
    """
    return float(total_debt - cash_and_equivalents)

def calculate_net_debt_ebitda(net_debt: float, ebitda: float) -> Optional[float]:
    """
    Net Debt / EBITDA = (Total Debt - Cash) / EBITDA
    Key operational solvency ratio.
    """
    if ebitda <= 0:
        return None
    return float(net_debt / ebitda)

def calculate_trailing_pe(market_price: float, trailing_eps: float) -> Optional[float]:
    """
    Trailing P/E = Market Price / Diluted Trailing 12M EPS
    """
    if trailing_eps <= 0:
        return None
    return float(market_price / trailing_eps)

def calculate_forward_pe(market_price: float, forward_eps: float) -> Optional[float]:
    """
    Forward P/E = Market Price / Consensus Estimated Next 12M EPS
    """
    if forward_eps <= 0:
        return None
    return float(market_price / forward_eps)


def compute_all_metrics(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Takes raw company financial data and computes all institutional metrics.
    """
    market_price = float(raw_data.get("market_price", 0.0))
    shares = float(raw_data.get("shares_outstanding", 1.0))
    market_cap = float(raw_data.get("market_cap", market_price * shares))
    
    ebit = float(raw_data.get("ebit", 0.0))
    tax_rate = float(raw_data.get("tax_rate", 0.21))
    nopat = calculate_nopat(ebit, tax_rate)
    
    total_debt = float(raw_data.get("total_debt", 0.0))
    total_equity = float(raw_data.get("total_equity", 1.0))
    cash = float(raw_data.get("cash_and_equivalents", 0.0))
    invested_capital = calculate_invested_capital(total_debt, total_equity, cash)
    
    roic = calculate_real_roic(nopat, invested_capital)
    
    ocf = float(raw_data.get("operating_cash_flow", 0.0))
    capex = float(raw_data.get("capex", 0.0))
    fcf = calculate_fcf(ocf, capex)
    fcf_yield = calculate_fcf_yield(fcf, market_cap)
    
    ebitda = float(raw_data.get("ebitda", ebit * 1.15))
    ev = calculate_enterprise_value(market_cap, total_debt, cash)
    ev_ebitda = calculate_ev_ebitda(ev, ebitda)
    
    net_debt = calculate_net_debt(total_debt, cash)
    net_debt_ebitda = calculate_net_debt_ebitda(net_debt, ebitda)
    
    trailing_eps = float(raw_data.get("trailing_eps", 0.0))
    forward_eps = float(raw_data.get("forward_eps", 0.0))
    
    trailing_pe = calculate_trailing_pe(market_price, trailing_eps)
    forward_pe = calculate_forward_pe(market_price, forward_eps)
    
    return {
        "market_price": market_price,
        "market_cap": market_cap,
        "nopat": nopat,
        "invested_capital": invested_capital,
        "roic": roic,
        "fcf": fcf,
        "fcf_yield": fcf_yield,
        "ev": ev,
        "ebitda": ebitda,
        "ev_ebitda": ev_ebitda,
        "net_debt": net_debt,
        "net_debt_ebitda": net_debt_ebitda,
        "trailing_pe": trailing_pe,
        "forward_pe": forward_pe,
    }
