"""VaR backtesting tests (P1 item 18): Kupiec, Christoffersen, conditional coverage."""

from __future__ import annotations

import numpy as np
import pytest

from options_risk.risk.backtesting import (
    breaches_from_losses,
    christoffersen_independence_test,
    conditional_coverage_test,
    kupiec_pof_test,
)


def test_breaches_from_losses() -> None:
    losses = np.array([1.0, 5.0, 2.0, 10.0])
    breaches = breaches_from_losses(losses, var=3.0)
    assert list(breaches) == [False, True, False, True]


def test_kupiec_fails_to_reject_well_calibrated_model() -> None:
    rng = np.random.default_rng(0)
    n = 2000
    confidence_level = 0.95
    # Exactly the expected breach rate, i.i.d.
    breaches = rng.random(n) > confidence_level
    result = kupiec_pof_test(breaches, confidence_level)
    assert not result.reject_null
    assert result.n_obs == n
    assert result.expected_breaches == pytest.approx(n * 0.05)


def test_kupiec_rejects_badly_miscalibrated_model() -> None:
    rng = np.random.default_rng(1)
    n = 1000
    # Actual breach rate way higher (20%) than the claimed 95% VaR (5% expected).
    breaches = rng.random(n) > 0.80
    result = kupiec_pof_test(breaches, confidence_level=0.95)
    assert result.reject_null
    assert result.p_value < 0.05


def test_kupiec_handles_zero_breaches() -> None:
    breaches = np.zeros(300, dtype=bool)
    result = kupiec_pof_test(breaches, confidence_level=0.95)
    assert result.n_breaches == 0
    assert np.isfinite(result.lr_statistic)
    assert 0 <= result.p_value <= 1


def test_kupiec_handles_all_breaches() -> None:
    breaches = np.ones(50, dtype=bool)
    result = kupiec_pof_test(breaches, confidence_level=0.95)
    assert result.n_breaches == 50
    assert np.isfinite(result.lr_statistic)
    assert result.reject_null


def test_christoffersen_fails_to_reject_independent_breaches() -> None:
    rng = np.random.default_rng(2)
    n = 2000
    breaches = rng.random(n) > 0.95
    result = christoffersen_independence_test(breaches, confidence_level=0.95)
    assert not result.reject_null


def test_christoffersen_rejects_clustered_breaches() -> None:
    # Construct obviously clustered breaches: bursts of consecutive breaches.
    n = 1000
    breaches = np.zeros(n, dtype=bool)
    rng = np.random.default_rng(3)
    burst_starts = rng.choice(np.arange(0, n - 10), size=20, replace=False)
    for start in burst_starts:
        breaches[start : start + 5] = True
    result = christoffersen_independence_test(breaches, confidence_level=0.95)
    assert result.reject_null


def test_christoffersen_requires_min_two_obs() -> None:
    with pytest.raises(ValueError):
        christoffersen_independence_test(np.array([True]), confidence_level=0.95)


def test_conditional_coverage_combines_both_lr_statistics() -> None:
    rng = np.random.default_rng(4)
    n = 1500
    breaches = rng.random(n) > 0.95
    pof = kupiec_pof_test(breaches, 0.95)
    indep = christoffersen_independence_test(breaches, 0.95)
    cc = conditional_coverage_test(breaches, 0.95)
    assert cc.lr_statistic == pytest.approx(pof.lr_statistic + indep.lr_statistic)
    assert cc.degrees_of_freedom == 2


def test_backtest_results_carry_sample_size_caveat() -> None:
    small_breaches = np.random.default_rng(5).random(30) > 0.95
    result = kupiec_pof_test(small_breaches, confidence_level=0.95)
    assert "n_obs=30" in result.sample_size_caveat
    assert len(result.sample_size_caveat) > 0


def test_backtest_never_silently_claims_validity() -> None:
    # A single p-value pass should not be over-interpreted: conclusion text
    # must be hedged ("fail to reject"), never an unconditional "model is valid".
    rng = np.random.default_rng(6)
    breaches = rng.random(500) > 0.95
    result = kupiec_pof_test(breaches, 0.95)
    assert "valid" not in result.conclusion.lower()
