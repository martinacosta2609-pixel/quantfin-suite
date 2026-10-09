"""
Monte Carlo Valuation Engine (Pure Implied IRR Distribution)
Projects 5,000 to 10,000 free cash flow trajectories over a 5-year horizon plus
sustainable terminal value, then numerically solves for the implied Internal Rate
of Return (TIR) equating the PV of cash flows to current market price (P_0).
Strictly objective: No subjective hurdle rate k, no buy/sell labels.
"""

import zlib
import numpy as np
from typing import Dict, Any, Optional

MIN_CONVERGED_PATHS = 500


class SimulationError(ValueError):
    """Raised when too few trajectories yield a finite, plausible IRR."""


def stable_seed(key: str) -> int:
    """Deterministic per-ticker seed (the built-in hash() is randomized on every process start)."""
    return zlib.crc32(key.strip().upper().encode("utf-8")) % 100000


def run_monte_carlo_simulation(
    p0: float,
    current_revenue_ps: float,
    historical_growth_mean: float,
    historical_growth_std: float,
    historical_margin_mean: float,
    historical_margin_std: float,
    tax_rate: float = 0.21,
    reinvestment_rate_mean: float = 0.35,
    reinvestment_rate_std: float = 0.10,
    exit_multiple_mean: float = 18.0,
    exit_multiple_std: float = 4.0,
    num_simulations: int = 5000,
    random_seed: Optional[int] = 42
) -> Dict[str, Any]:
    """
    Executes 5,000 to 10,000 Monte Carlo trajectories.
    Uses a private Generator, so concurrent requests never share or reseed global RNG state
    and the same inputs always give the same output.
    Returns:
    - percentiles: P10, P25, P50 (median), P75, P90
    - moments: mean, std, skewness, kurtosis
    - distribution: histogram bins & frequencies
    - trajectory_fan: year-by-year 10th, 50th, 90th percentile cash flow bands
    - sample_trajectories: 35 randomly sampled trajectory paths for charting
    Raises SimulationError if fewer than MIN_CONVERGED_PATHS trajectories yield a valid IRR
    (no synthetic distribution is substituted).
    """
    rng = np.random.default_rng(random_seed)

    # Sanitize inputs
    p0 = max(1.0, float(p0))
    current_revenue_ps = max(0.5, float(current_revenue_ps))
    num_simulations = max(1000, min(int(num_simulations), 10000))
    shape = (num_simulations, 5)

    # Stochastic shocks, bounded to avoid astronomical extremes
    growth_shocks = np.clip(
        rng.normal(historical_growth_mean, max(0.01, historical_growth_std), shape), -0.40, 0.60)
    margin_shocks = np.clip(
        rng.normal(historical_margin_mean, max(0.01, historical_margin_std), shape), 0.02, 0.65)
    reinvest_shocks = np.clip(
        rng.normal(reinvestment_rate_mean, max(0.01, reinvestment_rate_std), shape), 0.05, 0.85)
    exit_multiples = np.clip(
        rng.normal(exit_multiple_mean, max(1.0, exit_multiple_std), num_simulations), 6.0, 35.0)

    # Simulate 5-year paths for Free Cash Flows per share (vectorized over paths)
    fcf_paths = np.empty(shape)
    rev_prev = np.full(num_simulations, current_revenue_ps)
    effective_tax = max(0.0, min(tax_rate, 0.35))

    for t in range(5):
        rev_t = rev_prev * (1.0 + growth_shocks[:, t])
        nopat_t = rev_t * margin_shocks[:, t] * (1.0 - effective_tax)
        fcf_t = nopat_t * (1.0 - reinvest_shocks[:, t])
        # Floor FCF above severe bankruptcy
        fcf_paths[:, t] = np.maximum(fcf_t, -0.2 * rev_t)
        rev_prev = rev_t

    # Cash flows: [-P0, FCF_1, FCF_2, FCF_3, FCF_4, FCF_5 + TV]
    cf_matrix = np.zeros((num_simulations, 6))
    cf_matrix[:, 0] = -p0
    cf_matrix[:, 1:5] = fcf_paths[:, :4]
    cf_matrix[:, 5] = fcf_paths[:, 4] + np.maximum(fcf_paths[:, 4] * exit_multiples, 0.0)

    # Newton-Raphson, vectorized across all paths
    r_est = np.full(num_simulations, 0.08)  # Initial guess: 8%
    years = np.arange(6)
    for _ in range(25):
        denom = np.maximum(1.0 + r_est[:, None], 0.001)
        discounts = denom ** years
        npv = np.sum(cf_matrix / discounts, axis=1)
        d_npv = -np.sum((years * cf_matrix) / (discounts * denom), axis=1)
        step = np.clip(npv / np.where(np.abs(d_npv) < 1e-7, 1e-7, d_npv), -0.15, 0.15)
        r_est -= step
        if np.max(np.abs(step)) < 1e-4:
            break

    # Keep only convergent, plausible IRRs
    valid_mask = (r_est > -0.50) & (r_est < 1.50) & np.isfinite(r_est)
    valid_tirs = r_est[valid_mask]
    if len(valid_tirs) < MIN_CONVERGED_PATHS:
        raise SimulationError(
            f"Solo {len(valid_tirs)} de {num_simulations} trayectorias convergieron a una TIR válida "
            f"(mínimo {MIN_CONVERGED_PATHS}); revise los parámetros de la simulación."
        )

    p10, p25, p50, p75, p90 = (float(v) for v in np.percentile(valid_tirs, [10, 25, 50, 75, 90]))
    mean_tir = float(np.mean(valid_tirs))
    std_tir = float(np.std(valid_tirs))
    diff = valid_tirs - mean_tir
    skewness = float(np.mean(diff ** 3) / (std_tir ** 3 + 1e-9))
    kurtosis = float(np.mean(diff ** 4) / (std_tir ** 4 + 1e-9))

    prob_positive = float(np.mean(valid_tirs > 0.0))
    prob_gt_5 = float(np.mean(valid_tirs > 0.05))
    prob_gt_10 = float(np.mean(valid_tirs > 0.10))

    # Histogram (40 bins)
    hist_counts, bin_edges = np.histogram(valid_tirs, bins=40)
    n_valid = len(valid_tirs)
    histogram = [
        {
            "bin_min": float(bin_edges[i] * 100.0),
            "bin_max": float(bin_edges[i + 1] * 100.0),
            "bin_mid": round(float((bin_edges[i] + bin_edges[i + 1]) / 2.0 * 100.0), 2),
            "count": int(hist_counts[i]),
            "pct": round(float(hist_counts[i] / n_valid * 100.0), 2),
        }
        for i in range(len(hist_counts))
    ]

    # Trajectory fan chart (years 1 to 5): one percentile pass over all years
    fan_pcts = np.percentile(fcf_paths, [10, 50, 90], axis=0)
    fan_chart = [
        {
            "year": f"Año {y + 1}",
            "p10": round(float(fan_pcts[0, y]), 2),
            "p50": round(float(fan_pcts[1, y]), 2),
            "p90": round(float(fan_pcts[2, y]), 2),
        }
        for y in range(5)
    ]

    # Sample of individual trajectory paths for the fan visualisation
    sample_indices = rng.choice(num_simulations, size=min(35, num_simulations), replace=False)
    sample_trajectories = [
        {
            "id": int(idx),
            "path": [round(float(v), 2) for v in fcf_paths[idx]],
            "tir": round(float(r_est[idx] * 100.0), 2),
        }
        for idx in sample_indices
    ]

    return {
        "num_simulations": int(n_valid),
        "requested_simulations": int(num_simulations),
        "converged_pct": round(n_valid / num_simulations * 100.0, 1),
        "current_price": round(p0, 2),
        "percentiles": {
            "p10": round(p10 * 100.0, 2),
            "p25": round(p25 * 100.0, 2),
            "p50": round(p50 * 100.0, 2),
            "p75": round(p75 * 100.0, 2),
            "p90": round(p90 * 100.0, 2),
        },
        "moments": {
            "mean": round(mean_tir * 100.0, 2),
            "std": round(std_tir * 100.0, 2),
            "skewness": round(skewness, 3),
            "kurtosis": round(kurtosis, 3),
        },
        "probabilities": {
            "prob_positive": round(prob_positive * 100.0, 1),
            "prob_gt_5": round(prob_gt_5 * 100.0, 1),
            "prob_gt_10": round(prob_gt_10 * 100.0, 1),
        },
        "histogram": histogram,
        "fan_chart": fan_chart,
        "sample_trajectories": sample_trajectories,
    }
