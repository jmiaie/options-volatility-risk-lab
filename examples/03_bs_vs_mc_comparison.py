"""Compare Black-Scholes analytic price against Monte Carlo across path counts.

Shows the MC standard error shrinking (roughly as 1/sqrt(N)) and the
confidence interval bracketing the analytic price, with a fixed seed for
reproducibility.

Run: python examples/03_bs_vs_mc_comparison.py
"""

from __future__ import annotations

import json
from pathlib import Path

from options_risk.pricing.black_scholes import bsm_price
from options_risk.simulation.monte_carlo import mc_european_price

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results" / "monte_carlo"


def main() -> None:
    config = dict(S=100.0, K=100.0, T=1.0, r=0.03, sigma=0.25, option_type="call", q=0.0)
    analytic = bsm_price(**config)

    rows = []
    for n_paths in (1_000, 10_000, 100_000, 1_000_000):
        mc = mc_european_price(
            **config, n_paths=n_paths, seed=42, antithetic=True, control_variate=True
        )
        rows.append(
            {
                "n_paths": n_paths,
                "mc_price": mc.price,
                "standard_error": mc.standard_error,
                "ci_low": mc.ci_low,
                "ci_high": mc.ci_high,
                "analytic_in_ci": mc.ci_low <= analytic <= mc.ci_high,
                "abs_error_vs_analytic": abs(mc.price - analytic),
            }
        )

    result = {
        "inputs": config,
        "analytic_price": analytic,
        "seed": 42,
        "variance_reduction": {"antithetic": True, "control_variate": True},
        "convergence_table": rows,
    }
    print(json.dumps(result, indent=2))

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "bs_vs_mc_convergence.json").write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
