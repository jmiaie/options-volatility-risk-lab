"""Delta-hedging simulator tests (P1 item 10): accounting invariants and experiments."""

from __future__ import annotations

import numpy as np
import pytest

from options_risk.hedging.delta_hedge import simulate_delta_hedge
from options_risk.hedging.experiments import (
    rebalance_frequency_experiment,
    transaction_cost_experiment,
    vol_misspecification_experiment,
)

BASE = dict(S0=100.0, K=100.0, T=0.5, r=0.03, sigma_pricing=0.2, option_type="call", q=0.0)


def test_portfolio_value_identity_holds_every_row() -> None:
    result = simulate_delta_hedge(**BASE, option_qty=-1.0, n_steps=20, cost_rate=0.001, seed=1)
    path = result.path
    recomputed = (
        result.option_qty * path["option_value"] + path["shares_held"] * path["S"] + path["cash"]
    )
    assert np.allclose(recomputed.to_numpy(), path["portfolio_value"].to_numpy())


def test_hedge_is_closed_out_at_expiry() -> None:
    result = simulate_delta_hedge(**BASE, option_qty=-1.0, n_steps=20, seed=2)
    assert result.path.iloc[-1]["shares_held"] == pytest.approx(0.0)


def test_final_wealth_equals_terminal_cash() -> None:
    result = simulate_delta_hedge(**BASE, option_qty=-1.0, n_steps=20, seed=3)
    assert result.final_wealth == pytest.approx(result.path.iloc[-1]["cash"])


def test_zero_cost_zero_vol_gives_near_perfect_replication_in_continuum_limit() -> None:
    # With realized == pricing vol and many rebalances, the average hedging
    # error across seeds should be small relative to the option premium.
    from options_risk.pricing.black_scholes import bsm_price

    premium = bsm_price(
        S=BASE["S0"],
        K=BASE["K"],
        T=BASE["T"],
        r=BASE["r"],
        sigma=BASE["sigma_pricing"],
        option_type=BASE["option_type"],
        q=BASE["q"],
    )
    errors = [
        simulate_delta_hedge(
            **BASE, option_qty=-1.0, n_steps=252, cost_rate=0.0, seed=s
        ).final_wealth
        for s in range(100)
    ]
    assert abs(np.mean(errors)) < 0.05 * premium


def test_transaction_costs_are_nonnegative_and_zero_when_cost_rate_zero() -> None:
    result_free = simulate_delta_hedge(**BASE, option_qty=-1.0, n_steps=20, cost_rate=0.0, seed=4)
    assert result_free.total_transaction_costs == pytest.approx(0.0)

    result_costly = simulate_delta_hedge(
        **BASE, option_qty=-1.0, n_steps=20, cost_rate=0.005, seed=4
    )
    assert result_costly.total_transaction_costs > 0


def test_long_and_short_positions_are_mirror_images_of_hedge_shares() -> None:
    long_result = simulate_delta_hedge(**BASE, option_qty=1.0, n_steps=10, seed=5)
    short_result = simulate_delta_hedge(**BASE, option_qty=-1.0, n_steps=10, seed=5)
    assert np.allclose(
        long_result.path["shares_held"].to_numpy(), -short_result.path["shares_held"].to_numpy()
    )


def test_invalid_inputs_raise() -> None:
    with pytest.raises(ValueError):
        simulate_delta_hedge(**BASE, n_steps=0)
    with pytest.raises(ValueError):
        simulate_delta_hedge(**{**BASE, "T": 0.0}, n_steps=10)
    with pytest.raises(ValueError):
        simulate_delta_hedge(**BASE, n_steps=10, cost_rate=-0.01)


def test_rebalance_frequency_experiment_reduces_dispersion_with_more_steps() -> None:
    df = rebalance_frequency_experiment(
        S0=BASE["S0"],
        K=BASE["K"],
        T=BASE["T"],
        r=BASE["r"],
        sigma=BASE["sigma_pricing"],
        option_type=BASE["option_type"],
        q=BASE["q"],
        step_counts=(12, 252),
        n_seeds=150,
        cost_rate=0.0,
    )
    std_12 = df.loc[df["n_steps"] == 12, "std_final_wealth"].iloc[0]
    std_252 = df.loc[df["n_steps"] == 252, "std_final_wealth"].iloc[0]
    assert std_252 < std_12


def test_transaction_cost_experiment_costs_increase_with_rate() -> None:
    df = transaction_cost_experiment(
        S0=BASE["S0"],
        K=BASE["K"],
        T=BASE["T"],
        r=BASE["r"],
        sigma=BASE["sigma_pricing"],
        option_type=BASE["option_type"],
        q=BASE["q"],
        cost_rates=(0.0, 0.005),
        n_steps=52,
        n_seeds=100,
    )
    zero_cost = df.loc[df["cost_rate"] == 0.0, "mean_total_costs"].iloc[0]
    high_cost = df.loc[df["cost_rate"] == 0.005, "mean_total_costs"].iloc[0]
    assert high_cost > zero_cost
    assert zero_cost == pytest.approx(0.0)


def test_vol_misspecification_experiment_matched_vol_has_smallest_mean_error() -> None:
    df = vol_misspecification_experiment(
        S0=BASE["S0"],
        K=BASE["K"],
        T=BASE["T"],
        r=BASE["r"],
        sigma_pricing=BASE["sigma_pricing"],
        option_type=BASE["option_type"],
        q=BASE["q"],
        realized_vol_multipliers=(1.0, 2.0),
        n_steps=52,
        n_seeds=150,
    )
    matched = df.loc[df["realized_vol_multiplier"] == 1.0, "mean_final_wealth"].iloc[0]
    mismatched = df.loc[df["realized_vol_multiplier"] == 2.0, "mean_final_wealth"].iloc[0]
    assert abs(matched) < abs(mismatched)
