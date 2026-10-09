"""
Maintenance utilities.

    py -m engine.maintenance rebuild-baselines

rebuild-baselines recomputes every stock's baseline Monte Carlo (from its own stored assumptions,
with a deterministic per-ticker seed) and refreshes the P10/P50/P90 summary shown in the table.
Use it after changing the simulation model, or to repair baselines that were overwritten by
what-if runs in earlier versions of the app.
"""

import sys

from engine.database import init_db, get_db_connection, get_stock_by_ticker, save_monte_carlo_result
from engine.data_seeder import backfill_revenue_ps
from engine.monte_carlo import SimulationError
from engine.api import _simulate, MonteCarloRequest


def rebuild_baselines() -> dict:
    init_db()
    backfill_revenue_ps()
    with get_db_connection() as conn:
        tickers = [r["ticker"] for r in conn.execute("SELECT ticker FROM stocks ORDER BY ticker")]

    ok, failed = 0, []
    params = MonteCarloRequest()
    for ticker in tickers:
        try:
            save_monte_carlo_result(ticker, _simulate(get_stock_by_ticker(ticker), params))
            ok += 1
        except SimulationError as exc:
            failed.append((ticker, str(exc)))
    return {"total": len(tickers), "rebuilt": ok, "failed": failed}


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "rebuild-baselines":
        result = rebuild_baselines()
        print(f"[OK] {result['rebuilt']}/{result['total']} simulaciones base recalculadas.")
        for ticker, msg in result["failed"]:
            print(f"[FALLO] {ticker}: {msg}")
    else:
        print(__doc__)
        sys.exit(1)
