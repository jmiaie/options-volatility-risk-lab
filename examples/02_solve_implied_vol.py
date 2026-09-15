"""Round-trip a Black-Scholes price through the implied-vol solver.

Demonstrates the primary Brent solve, the Newton-Raphson secondary
cross-check, and the solver's refusal to return an IV for an
arbitrage-violating price.

Run: python examples/02_solve_implied_vol.py
"""

from __future__ import annotations

import json
from pathlib import Path

from options_risk.pricing.black_scholes import bsm_price
from options_risk.pricing.implied_vol import solve_iv, solve_iv_newton

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results" / "pricing"


def main() -> None:
    config = dict(S=100.0, K=100.0, T=0.75, r=0.04, sigma=0.27, option_type="put", q=0.0)
    true_sigma = config.pop("sigma")
    price = bsm_price(**config, sigma=true_sigma)

    brent = solve_iv(price, **config)
    newton = solve_iv_newton(price, **config)

    # An impossible (arbitrage-violating) price: refused, not silently solved.
    impossible_price = config["S"] * 5  # way above the call/put upper bound region
    refused = solve_iv(impossible_price, **config)

    result = {
        "true_sigma": true_sigma,
        "price_from_true_sigma": price,
        "brent_result": {
            "iv": brent.iv,
            "converged": brent.converged,
            "iterations": brent.iterations,
        },
        "newton_result": {
            "iv": newton.iv,
            "converged": newton.converged,
            "iterations": newton.iterations,
        },
        "recovered_sigma_matches_true": abs((brent.iv or 0) - true_sigma) < 1e-6,
        "arbitrage_violating_price_refused": {
            "price_tried": impossible_price,
            "converged": refused.converged,
            "failure_reason": refused.failure_reason,
        },
    }
    print(json.dumps(result, indent=2))

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "implied_vol_round_trip.json").write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
