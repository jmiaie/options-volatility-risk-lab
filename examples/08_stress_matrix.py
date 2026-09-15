"""Run the standard deterministic stress suite and a spot-vol convexity grid.

Run: python examples/08_stress_matrix.py
"""

from __future__ import annotations

import json
from pathlib import Path

from _common import build_example_portfolio

from options_risk.stress.scenario import run_standard_stress_suite, spot_vol_matrix

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results" / "stress"


def main() -> None:
    portfolio = build_example_portfolio()

    standard_results = run_standard_stress_suite(portfolio)
    grid_results = spot_vol_matrix(portfolio)

    result = {
        "portfolio_market_value_base": portfolio.market_value(),
        "standard_stress_suite": [
            {
                "scenario": r.scenario.name,
                "mv_before": r.mv_before,
                "mv_after": r.mv_after,
                "pnl": r.pnl,
                "pnl_pct": r.pnl_pct,
                "delta_before": r.greeks_before.delta,
                "delta_after": r.greeks_after.delta,
            }
            for r in standard_results
        ],
        "spot_vol_grid": [{"scenario": r.scenario.name, "pnl": r.pnl} for r in grid_results],
        "note": "All P&L figures are FULL REVALUATION (actual BSM repricing under the shocked "
        "inputs), not a Greek-based approximation. See docs/model-risk.md #6.",
    }
    print(json.dumps(result, indent=2))

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "stress_and_spot_vol_matrix.json").write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
