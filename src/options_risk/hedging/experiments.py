"""Batch hedging experiments: rebalance frequency, transaction costs, vol misspecification.

Each function runs :func:`simulate_delta_hedge` across many seeds and
summarizes the distribution of hedging P&L (final wealth) and total
transaction costs. These are the experiments referenced in the P1 hedging
brief: they exist to *show* the size of discrete-hedging error under
different conditions, not to claim continuous-time replication is
achievable.
"""

from __future__ import annotations

import pandas as pd

from options_risk.hedging.delta_hedge import simulate_delta_hedge
from options_risk.pricing.black_scholes import OptionType


def _run_batch(
    n_seeds: int,
    **sim_kwargs: object,
) -> pd.DataFrame:
    rows = []
    for seed in range(n_seeds):
        result = simulate_delta_hedge(**sim_kwargs, seed=seed)  # type: ignore[arg-type]
        rows.append(
            {
                "seed": seed,
                "final_wealth": result.final_wealth,
                "total_transaction_costs": result.total_transaction_costs,
            }
        )
    return pd.DataFrame(rows)


def rebalance_frequency_experiment(
    S0: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: OptionType,
    q: float = 0.0,
    *,
    step_counts: tuple[int, ...] = (12, 52, 252),
    n_seeds: int = 200,
    cost_rate: float = 0.0,
) -> pd.DataFrame:
    """Compare hedging-error dispersion across rebalance frequencies.

    With ``sigma_realized == sigma_pricing`` and ``cost_rate == 0``, more
    frequent rebalancing is expected to *shrink* the standard deviation of
    hedging P&L across seeds (closer to continuous replication) — this is
    the classic discrete-hedging result, shown empirically here rather than
    asserted analytically.
    """
    summaries = []
    for n_steps in step_counts:
        batch = _run_batch(
            n_seeds,
            S0=S0,
            K=K,
            T=T,
            r=r,
            sigma_pricing=sigma,
            option_type=option_type,
            q=q,
            n_steps=n_steps,
            cost_rate=cost_rate,
        )
        summaries.append(
            {
                "n_steps": n_steps,
                "mean_final_wealth": batch["final_wealth"].mean(),
                "std_final_wealth": batch["final_wealth"].std(ddof=1),
                "mean_total_costs": batch["total_transaction_costs"].mean(),
            }
        )
    return pd.DataFrame(summaries)


def transaction_cost_experiment(
    S0: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: OptionType,
    q: float = 0.0,
    *,
    cost_rates: tuple[float, ...] = (0.0, 0.0005, 0.002, 0.01),
    n_steps: int = 52,
    n_seeds: int = 200,
) -> pd.DataFrame:
    """Compare hedging-error mean/dispersion and total costs across transaction cost rates.

    Higher costs are expected to bias mean hedging P&L downward (costs are
    always a drag, regardless of direction of trade) and increase its
    dispersion, illustrating the daily-vs-weekly-rebalance/cost trade-off.
    """
    summaries = []
    for cost_rate in cost_rates:
        batch = _run_batch(
            n_seeds,
            S0=S0,
            K=K,
            T=T,
            r=r,
            sigma_pricing=sigma,
            option_type=option_type,
            q=q,
            n_steps=n_steps,
            cost_rate=cost_rate,
        )
        summaries.append(
            {
                "cost_rate": cost_rate,
                "mean_final_wealth": batch["final_wealth"].mean(),
                "std_final_wealth": batch["final_wealth"].std(ddof=1),
                "mean_total_costs": batch["total_transaction_costs"].mean(),
            }
        )
    return pd.DataFrame(summaries)


def vol_misspecification_experiment(
    S0: float,
    K: float,
    T: float,
    r: float,
    sigma_pricing: float,
    option_type: OptionType,
    q: float = 0.0,
    *,
    realized_vol_multipliers: tuple[float, ...] = (0.5, 0.8, 1.0, 1.25, 2.0),
    n_steps: int = 52,
    n_seeds: int = 200,
    cost_rate: float = 0.0,
) -> pd.DataFrame:
    """Compare hedging P&L when realized vol differs from the pricing (hedging) vol.

    A multiplier of 1.0 is the correctly-specified case (realized == pricing).
    Hedging with the "wrong" vol (multiplier != 1.0) is expected to bias
    mean hedging P&L: a short-gamma writer who under-hedges realized vol
    (multiplier > 1) tends to lose on average, and vice versa.
    """
    summaries = []
    for mult in realized_vol_multipliers:
        batch = _run_batch(
            n_seeds,
            S0=S0,
            K=K,
            T=T,
            r=r,
            sigma_pricing=sigma_pricing,
            option_type=option_type,
            q=q,
            sigma_realized=sigma_pricing * mult,
            n_steps=n_steps,
            cost_rate=cost_rate,
        )
        summaries.append(
            {
                "realized_vol_multiplier": mult,
                "realized_vol": sigma_pricing * mult,
                "mean_final_wealth": batch["final_wealth"].mean(),
                "std_final_wealth": batch["final_wealth"].std(ddof=1),
            }
        )
    return pd.DataFrame(summaries)


__all__ = [
    "rebalance_frequency_experiment",
    "transaction_cost_experiment",
    "vol_misspecification_experiment",
]
