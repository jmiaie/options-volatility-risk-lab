"""Run a discrete delta-hedging simulation and summarize hedging error across rebalance frequencies.

Run: python examples/05_delta_hedge_sim.py
"""

from __future__ import annotations

import json
from pathlib import Path

from options_risk.hedging.delta_hedge import simulate_delta_hedge
from options_risk.hedging.experiments import (
    rebalance_frequency_experiment,
    transaction_cost_experiment,
    vol_misspecification_experiment,
)

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results" / "hedging"

BASE = dict(S0=100.0, K=100.0, T=0.5, r=0.03, sigma=0.25, option_type="call", q=0.0)


def main() -> None:
    single_run = simulate_delta_hedge(
        S0=BASE["S0"],
        K=BASE["K"],
        T=BASE["T"],
        r=BASE["r"],
        sigma_pricing=BASE["sigma"],
        option_type=BASE["option_type"],
        q=BASE["q"],
        option_qty=-1.0,
        n_steps=52,
        cost_rate=0.001,
        seed=0,
    )

    freq_df = rebalance_frequency_experiment(**BASE, step_counts=(12, 52, 252), n_seeds=300)
    cost_df = transaction_cost_experiment(
        **BASE, cost_rates=(0.0, 0.0005, 0.002, 0.01), n_steps=52, n_seeds=300
    )
    vol_df = vol_misspecification_experiment(
        S0=BASE["S0"],
        K=BASE["K"],
        T=BASE["T"],
        r=BASE["r"],
        sigma_pricing=BASE["sigma"],
        option_type=BASE["option_type"],
        q=BASE["q"],
        n_steps=52,
        n_seeds=300,
    )

    result = {
        "config": {**BASE, "option_qty": -1.0, "seed": 0},
        "single_run_summary": {
            "final_wealth": single_run.final_wealth,
            "total_transaction_costs": single_run.total_transaction_costs,
            "n_rebalances": single_run.n_rebalances,
        },
        "rebalance_frequency_experiment": freq_df.to_dict(orient="records"),
        "transaction_cost_experiment": cost_df.to_dict(orient="records"),
        "vol_misspecification_experiment": vol_df.to_dict(orient="records"),
        "note": "final_wealth is hedging P&L (replication error) net of the initial option "
        "premium; 0 would mean perfect replication. See docs/model-risk.md #4.",
    }
    print(json.dumps(result, indent=2))

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "delta_hedge_experiments.json").write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
