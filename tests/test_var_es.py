"""VaR/ES tests (P1 items 13, 17): sign convention, toy-distribution answers, model comparison."""

from __future__ import annotations

import numpy as np
import pytest
from scipy.stats import norm

from options_risk.portfolio import OptionPosition, Portfolio
from options_risk.risk.var import (
    compute_var_es,
    delta_normal_var,
    historical_simulation_var,
    monte_carlo_var,
)


def test_compute_var_es_on_known_uniform_distribution() -> None:
    # Losses uniform on [0, 100]: 95th percentile is 95, ES (mean above 95) ~= 97.5.
    losses = np.linspace(0, 100, 100_001)
    var, es = compute_var_es(losses, 0.95)
    assert var == pytest.approx(95.0, abs=0.1)
    assert es == pytest.approx(97.5, abs=0.1)


def test_compute_var_es_on_known_normal_distribution() -> None:
    rng = np.random.default_rng(0)
    mu, sigma = 0.0, 10.0
    losses = rng.normal(mu, sigma, size=2_000_000)
    var, es = compute_var_es(losses, 0.99)

    z = norm.ppf(0.99)
    expected_var = mu + z * sigma
    expected_es = mu + sigma * norm.pdf(z) / 0.01

    assert var == pytest.approx(expected_var, abs=0.1)
    assert es == pytest.approx(expected_es, abs=0.2)


def test_es_always_at_least_as_large_as_var_for_upper_tail() -> None:
    rng = np.random.default_rng(1)
    losses = rng.standard_t(df=4, size=100_000) * 5
    var, es = compute_var_es(losses, 0.95)
    assert es >= var


def test_compute_var_es_rejects_bad_confidence_level() -> None:
    with pytest.raises(ValueError):
        compute_var_es(np.array([1.0, 2.0, 3.0]), 1.5)
    with pytest.raises(ValueError):
        compute_var_es(np.array([1.0, 2.0, 3.0]), 0.0)


def test_delta_normal_var_closed_form_matches_manual_calc() -> None:
    dollar_delta = 100_000.0
    factor_vol = 0.02
    result = delta_normal_var(dollar_delta, factor_vol, confidence_level=0.99, horizon=1)
    pnl_std = dollar_delta * factor_vol
    z = norm.ppf(0.99)
    assert result.var == pytest.approx(z * pnl_std)
    assert result.es == pytest.approx(pnl_std * norm.pdf(z) / 0.01)


def test_delta_normal_var_scales_with_sqrt_horizon() -> None:
    r1 = delta_normal_var(100_000.0, 0.02, horizon=1)
    r4 = delta_normal_var(100_000.0, 0.02, horizon=4)
    assert r4.var == pytest.approx(r1.var * 2, rel=1e-6)  # sqrt(4) = 2


def _single_underlying_option_portfolio() -> Portfolio:
    portfolio = Portfolio()
    portfolio.add(OptionPosition("ABC", "call", -1, 100, 0.25, 100.0, 0.03, 0.25, multiplier=100))
    return portfolio


def test_historical_var_full_revalues_nonlinear_portfolio() -> None:
    portfolio = _single_underlying_option_portfolio()
    rng = np.random.default_rng(2)
    returns = rng.normal(0, 0.02, size=500)
    summary = historical_simulation_var(portfolio, returns, confidence_level=0.95)
    assert summary.n_obs == 500
    assert summary.es >= summary.var
    assert summary.var > 0  # short-option book has meaningful downside


def test_historical_var_rejects_bad_return_type() -> None:
    portfolio = _single_underlying_option_portfolio()
    with pytest.raises(ValueError):
        historical_simulation_var(portfolio, np.array([0.01, -0.01, 0.02]), return_type="bogus")


def test_monte_carlo_var_reproducible_with_seed() -> None:
    portfolio = _single_underlying_option_portfolio()
    r1 = monte_carlo_var(portfolio, mean_return=0.0, vol=0.02, n_sims=2000, seed=7)
    r2 = monte_carlo_var(portfolio, mean_return=0.0, vol=0.02, n_sims=2000, seed=7)
    assert r1.var == r2.var
    assert r1.es == r2.es


def test_monte_carlo_var_es_at_least_var() -> None:
    portfolio = _single_underlying_option_portfolio()
    summary = monte_carlo_var(portfolio, mean_return=0.0, vol=0.02, n_sims=5000, seed=8)
    assert summary.es >= summary.var


def test_linear_var_disagrees_with_full_reval_for_nonlinear_book() -> None:
    # A short-option book has negative gamma: full-revaluation (historical/MC) VaR
    # should differ meaningfully from the delta-normal linear approximation,
    # since delta-normal cannot see the convexity risk.
    portfolio = _single_underlying_option_portfolio()
    dollar_delta = portfolio.greeks().delta * 100.0  # dollar delta per unit return (delta * S)

    dn = delta_normal_var(dollar_delta, factor_vol=0.02, confidence_level=0.99)

    rng = np.random.default_rng(3)
    returns = rng.normal(0, 0.02, size=2000)
    hist = historical_simulation_var(portfolio, returns, confidence_level=0.99)

    # They should not coincide (within a tight tolerance) for a short-gamma book.
    assert dn.var != pytest.approx(hist.var, rel=0.05)
