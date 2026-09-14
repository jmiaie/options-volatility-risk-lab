"""Monte Carlo validation (P1 item 7): convergence, CI, reproducibility, variance reduction."""

from __future__ import annotations

import numpy as np
import pytest

from options_risk.pricing.black_scholes import bsm_price
from options_risk.simulation.monte_carlo import mc_european_price

BASE_CASE = dict(S=100.0, K=100.0, T=1.0, r=0.05, sigma=0.2, option_type="call", q=0.0)


def test_mc_converges_to_analytic_price() -> None:
    analytic = bsm_price(**BASE_CASE)
    result = mc_european_price(**BASE_CASE, n_paths=200_000, seed=42)
    # Analytic price should sit inside a wide (~6 SE) band of the MC estimate.
    assert abs(result.price - analytic) < 6 * result.standard_error


def test_confidence_interval_contains_analytic_price_typically() -> None:
    analytic = bsm_price(**BASE_CASE)
    # Run several independent seeds; the 95% CI should contain the true
    # analytic value in the large majority of runs (allow occasional misses).
    hits = 0
    n_runs = 20
    for seed in range(n_runs):
        result = mc_european_price(**BASE_CASE, n_paths=20_000, seed=seed)
        if result.ci_low <= analytic <= result.ci_high:
            hits += 1
    assert hits / n_runs >= 0.80


def test_ci_shrinks_with_more_paths() -> None:
    se_small = mc_european_price(**BASE_CASE, n_paths=2_000, seed=1).standard_error
    se_large = mc_european_price(**BASE_CASE, n_paths=200_000, seed=1).standard_error
    assert se_large < se_small
    # Roughly sqrt(N) scaling: 100x paths -> ~10x smaller SE.
    assert se_small / se_large > 5


def test_reproducible_under_fixed_seed() -> None:
    r1 = mc_european_price(**BASE_CASE, n_paths=5_000, seed=123)
    r2 = mc_european_price(**BASE_CASE, n_paths=5_000, seed=123)
    assert r1.price == r2.price
    assert r1.standard_error == r2.standard_error


def test_different_seeds_give_different_prices() -> None:
    r1 = mc_european_price(**BASE_CASE, n_paths=1_000, seed=1)
    r2 = mc_european_price(**BASE_CASE, n_paths=1_000, seed=2)
    assert r1.price != r2.price


def test_antithetic_variance_not_worse_than_naive() -> None:
    # Compare SE of antithetic (no CV) vs naive (no antithetic, no CV) at
    # matched path counts, averaged over several seeds to avoid one lucky draw.
    naive_ses = []
    anti_ses = []
    for seed in range(10):
        naive = mc_european_price(
            **BASE_CASE, n_paths=20_000, seed=seed, antithetic=False, control_variate=False
        )
        anti = mc_european_price(
            **BASE_CASE, n_paths=20_000, seed=seed, antithetic=True, control_variate=False
        )
        naive_ses.append(naive.standard_error)
        anti_ses.append(anti.standard_error)
    assert np.mean(anti_ses) < np.mean(naive_ses)


def test_control_variate_variance_not_worse_than_naive() -> None:
    naive_ses = []
    cv_ses = []
    for seed in range(10):
        naive = mc_european_price(
            **BASE_CASE, n_paths=20_000, seed=seed, antithetic=False, control_variate=False
        )
        cv = mc_european_price(
            **BASE_CASE, n_paths=20_000, seed=seed, antithetic=False, control_variate=True
        )
        naive_ses.append(naive.standard_error)
        cv_ses.append(cv.standard_error)
    assert np.mean(cv_ses) <= np.mean(naive_ses) * 1.05  # allow small slack, expect improvement


def test_t_zero_returns_intrinsic_with_zero_standard_error() -> None:
    result = mc_european_price(S=110, K=100, T=0.0, r=0.05, sigma=0.2, option_type="call")
    assert result.price == pytest.approx(10.0)
    assert result.standard_error == 0.0
    assert result.ci_low == result.ci_high == pytest.approx(10.0)


@pytest.mark.parametrize("option_type", ["call", "put"])
def test_mc_matches_analytic_across_moneyness(option_type: str) -> None:
    for K in (80, 100, 120):
        case = dict(S=100.0, K=float(K), T=0.5, r=0.03, sigma=0.25, option_type=option_type, q=0.01)
        analytic = bsm_price(**case)
        result = mc_european_price(**case, n_paths=100_000, seed=7)
        assert abs(result.price - analytic) < 5 * result.standard_error


def test_invalid_n_paths_raises() -> None:
    with pytest.raises(ValueError):
        mc_european_price(**BASE_CASE, n_paths=1)
