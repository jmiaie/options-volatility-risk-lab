from __future__ import annotations

import json
from pathlib import Path

from options_risk import (
    black_scholes_price,
    finite_difference_greeks,
    greeks,
    implied_volatility,
    monte_carlo_european_price,
)


def build_summary() -> dict[str, float | dict[str, float] | str]:
    params = {
        "option_type": "call",
        "spot": 100.0,
        "strike": 100.0,
        "time_to_expiry": 1.0,
        "volatility": 0.2,
        "rate": 0.05,
        "dividend_yield": 0.02,
    }
    price = black_scholes_price(**params)
    analytic = greeks(**params)
    numeric = finite_difference_greeks(**params)
    iv = implied_volatility("call", price, 100.0, 100.0, 1.0, 0.05, 0.02)
    mc = monte_carlo_european_price(**params, n_paths=100_000, seed=42)
    return {
        "note": "Synthetic deterministic example only",
        "price": round(price, 6),
        "delta": round(analytic.delta, 6),
        "gamma": round(analytic.gamma, 6),
        "vega": round(analytic.vega, 6),
        "theta": round(analytic.theta, 6),
        "rho": round(analytic.rho, 6),
        "fd_delta": round(numeric.delta, 6),
        "implied_volatility": round(iv.implied_volatility or 0.0, 6),
        "mc_price": round(mc.price, 6),
        "mc_standard_error": round(mc.standard_error, 6),
        "mc_ci_low": round(mc.confidence_interval[0], 6),
        "mc_ci_high": round(mc.confidence_interval[1], 6),
    }


def main() -> None:
    summary = build_summary()
    output_path = Path("research/results/pricing_demo.json")
    output_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
