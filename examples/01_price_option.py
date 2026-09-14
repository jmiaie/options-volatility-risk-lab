"""Price a European option under Black-Scholes-Merton and print its Greeks.

Run: python examples/01_price_option.py
"""

from __future__ import annotations

import json
from pathlib import Path

from options_risk.pricing.black_scholes import bsm_price
from options_risk.pricing.greeks import greeks

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results" / "pricing"


def main() -> None:
    config = dict(S=100.0, K=105.0, T=0.5, r=0.03, sigma=0.22, option_type="call", q=0.01)
    price = bsm_price(**config)
    g = greeks(**config)

    result = {
        "model": "Black-Scholes-Merton (European)",
        "inputs": config,
        "price": price,
        "greeks": {
            "delta": g.delta,
            "gamma": g.gamma,
            "vega": g.vega,
            "theta": g.theta,
            "rho": g.rho,
        },
        "units": {
            "vega": "price change per 1.00 (100 vol pts) change in sigma; "
            "divide by 100 for per-vol-point",
            "theta": "price change per year of elapsed time; divide by 365 for per-calendar-day",
            "rho": "price change per 1.00 (100pp) change in r; divide by 100 for per-100bps",
        },
    }
    print(json.dumps(result, indent=2))

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "single_option_price.json").write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
