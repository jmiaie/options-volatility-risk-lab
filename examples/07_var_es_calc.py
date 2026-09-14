"""Compute Historical, Delta-Normal, and Monte Carlo VaR/ES for the example portfolio.

Run: python examples/07_var_es_calc.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from _common import build_example_portfolio

from options_risk.risk.var import delta_normal_var, historical_simulation_var, monte_carlo_var

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results" / "var"


def main() -> None:
    portfolio = build_example_portfolio()
    confidence_level = 0.95

    rng = np.random.default_rng(2024)
    synthetic_daily_log_returns = rng.normal(
        0.0002, 0.015, size=500
    )  # SYNTHETIC, not real market data

    hist = historical_simulation_var(
        portfolio, synthetic_daily_log_returns, confidence_level=confidence_level, return_type="log"
    )

    dollar_delta = portfolio.greeks().delta * 100.0  # per-unit-return dollar exposure (delta * S)
    dn = delta_normal_var(dollar_delta, factor_vol=0.015, confidence_level=confidence_level)

    mc = monte_carlo_var(
        portfolio,
        mean_return=0.0002,
        vol=0.015,
        n_sims=20_000,
        confidence_level=confidence_level,
        seed=2024,
    )

    result = {
        "portfolio_market_value": portfolio.market_value(),
        "confidence_level": confidence_level,
        "return_series_note": "SYNTHETIC daily log returns (mean 0.02%, vol 1.5%), seed=2024 "
        "-- not real market data",
        "historical_simulation_var": {
            "var": hist.var,
            "es": hist.es,
            "n_obs": hist.n_obs,
            "mean_loss": hist.mean_loss,
            "std_loss": hist.std_loss,
        },
        "delta_normal_var": {
            "var": dn.var,
            "es": dn.es,
            "portfolio_dollar_delta": dn.portfolio_dollar_delta,
            "assumption": "linear P&L, normal returns -- see docs/model-risk.md #5",
        },
        "monte_carlo_var": {
            "var": mc.var,
            "es": mc.es,
            "n_obs": mc.n_obs,
            "seed": 2024,
        },
        "model_disagreement": {
            "historical_vs_delta_normal_var_ratio": hist.var / dn.var if dn.var else None,
            "note": "Delta-Normal ignores Gamma; for this short-put/long-call convex book its "
            "VaR is expected to differ materially from full-revaluation historical/MC VaR.",
        },
    }
    print(json.dumps(result, indent=2))

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "var_es_comparison.json").write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
