"""Implied-volatility solver tests: round-trip recovery and bounds rejection (P0 item 5)."""

from __future__ import annotations

import pytest

from options_risk.pricing.black_scholes import bsm_price
from options_risk.pricing.implied_vol import solve_iv, solve_iv_newton

ROUND_TRIP_CASES = [
    # (S, K, T, r, sigma, q, option_type) spanning ITM/ATM/OTM, short/long T, low/high vol
    (100, 100, 1.0, 0.05, 0.20, 0.0, "call"),  # ATM
    (100, 100, 1.0, 0.05, 0.20, 0.0, "put"),
    (120, 100, 1.0, 0.05, 0.20, 0.0, "call"),  # ITM call
    (80, 100, 1.0, 0.05, 0.20, 0.0, "call"),  # OTM call
    (100, 100, 0.02, 0.05, 0.20, 0.0, "call"),  # short maturity (~1 week)
    (100, 100, 5.0, 0.03, 0.20, 0.0, "put"),  # long maturity
    (100, 100, 1.0, 0.05, 0.05, 0.0, "call"),  # low vol
    (100, 100, 1.0, 0.05, 1.50, 0.0, "call"),  # high vol
    (100, 90, 0.5, 0.02, 0.30, 0.01, "put"),  # with dividend yield
]


@pytest.mark.parametrize("S,K,T,r,sigma,q,option_type", ROUND_TRIP_CASES)
def test_iv_round_trip_brent(
    S: float, K: float, T: float, r: float, sigma: float, q: float, option_type: str
) -> None:
    price = bsm_price(S, K, T, r, sigma, option_type, q)  # type: ignore[arg-type]
    result = solve_iv(price, S, K, T, r, option_type, q)  # type: ignore[arg-type]
    assert result.converged
    assert result.iv == pytest.approx(sigma, abs=1e-6)
    assert result.failure_reason is None
    assert result.iterations > 0


@pytest.mark.parametrize("S,K,T,r,sigma,q,option_type", ROUND_TRIP_CASES)
def test_iv_round_trip_newton_secondary_check(
    S: float, K: float, T: float, r: float, sigma: float, q: float, option_type: str
) -> None:
    price = bsm_price(S, K, T, r, sigma, option_type, q)  # type: ignore[arg-type]
    brent_result = solve_iv(price, S, K, T, r, option_type, q)  # type: ignore[arg-type]
    newton_result = solve_iv_newton(price, S, K, T, r, option_type, q)  # type: ignore[arg-type]
    assert brent_result.converged
    if newton_result.converged:
        assert newton_result.iv == pytest.approx(brent_result.iv, abs=1e-4)


def test_iv_rejects_price_above_upper_bound() -> None:
    # Call priced above spot itself violates the upper bound.
    result = solve_iv(price=150, S=100, K=100, T=1.0, r=0.05, option_type="call")
    assert not result.converged
    assert result.iv is None
    assert "arbitrage" in result.failure_reason.lower()


def test_iv_rejects_price_below_lower_bound() -> None:
    # Call priced below its no-arbitrage lower bound.
    lower_bound_violating_price = 0.0
    S, K, T, r = 150.0, 50.0, 1.0, 0.10
    result = solve_iv(lower_bound_violating_price, S, K, T, r, "call")
    assert not result.converged
    assert result.iv is None


def test_iv_rejects_at_or_below_intrinsic_value() -> None:
    S, K, T, r = 120.0, 100.0, 1.0, 0.05
    intrinsic = S - K
    result = solve_iv(intrinsic, S, K, T, r, "call")
    assert not result.converged
    assert result.failure_reason is not None


def test_iv_rejects_T_zero() -> None:
    result = solve_iv(price=10, S=100, K=100, T=0.0, r=0.05, option_type="call")
    assert not result.converged
    assert "T must be" in result.failure_reason


def test_iv_never_returns_iv_alongside_not_converged() -> None:
    # Invariant: converged=False must always pair with iv=None.
    for kwargs in [
        dict(price=150, S=100, K=100, T=1.0, r=0.05, option_type="call"),
        dict(price=10, S=100, K=100, T=0.0, r=0.05, option_type="call"),
    ]:
        result = solve_iv(**kwargs)  # type: ignore[arg-type]
        assert result.converged is False
        assert result.iv is None
