"""Rolling-window historical VaR backtest with Kupiec / Christoffersen / conditional coverage.

Uses a synthetic daily return series (clearly labeled as such). At each test
day, VaR is estimated from a rolling window of *strictly prior* returns
only (no lookahead), then compared against that day's *actual* realized
loss to form the breach indicator the backtests consume.

Run: python examples/09_var_backtest.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from _common import build_example_portfolio

from options_risk.risk.backtesting import (
    christoffersen_independence_test,
    conditional_coverage_test,
    kupiec_pof_test,
)
from options_risk.risk.var import historical_simulation_var
from options_risk.stress.scenario import Scenario, revalue_portfolio

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results" / "var"


def main() -> None:
    portfolio = build_example_portfolio()
    confidence_level = 0.95
    window = 60
    n_total_days = 210  # window + test period

    rng = np.random.default_rng(99)
    daily_log_returns = rng.normal(0.0, 0.014, size=n_total_days)  # SYNTHETIC returns

    breaches = []
    var_forecasts = []
    realized_losses = []
    for t in range(window, n_total_days):
        estimation_window = daily_log_returns[t - window : t]  # strictly prior returns only
        var_summary = historical_simulation_var(
            portfolio, estimation_window, confidence_level=confidence_level, return_type="log"
        )
        realized_result = revalue_portfolio(
            portfolio,
            Scenario(name=f"day_{t}", spot_shock_pct=float(np.exp(daily_log_returns[t]) - 1)),
        )
        realized_loss = -realized_result.pnl

        var_forecasts.append(var_summary.var)
        realized_losses.append(realized_loss)
        breaches.append(realized_loss > var_summary.var)

    breaches_arr = np.array(breaches)
    kupiec = kupiec_pof_test(breaches_arr, confidence_level)
    christoffersen = christoffersen_independence_test(breaches_arr, confidence_level)
    cc = conditional_coverage_test(breaches_arr, confidence_level)

    def _summarize(r):  # noqa: ANN001, ANN202
        return {
            "test_name": r.test_name,
            "n_obs": r.n_obs,
            "n_breaches": r.n_breaches,
            "expected_breaches": r.expected_breaches,
            "breach_rate": r.breach_rate,
            "lr_statistic": r.lr_statistic,
            "p_value": r.p_value,
            "reject_null": r.reject_null,
            "conclusion": r.conclusion,
            "sample_size_caveat": r.sample_size_caveat,
        }

    result = {
        "data_note": "SYNTHETIC daily log returns (mean 0, vol 1.4%), seed=99 "
        "-- not real market data",
        "confidence_level": confidence_level,
        "rolling_window_days": window,
        "n_test_days": n_total_days - window,
        "kupiec_pof_test": _summarize(kupiec),
        "christoffersen_independence_test": _summarize(christoffersen),
        "conditional_coverage_test": _summarize(cc),
    }
    print(json.dumps(result, indent=2))

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "var_backtest.json").write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
