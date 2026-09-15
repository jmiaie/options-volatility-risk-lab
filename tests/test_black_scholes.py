"""Financial-invariant tests for BSM pricing (P0 item 6)."""

from __future__ import annotations

import math

import pytest

from options_risk.pricing.black_scholes import (
    bsm_price,
    call_lower_bound,
    call_upper_bound,
    intrinsic_value,
    is_within_arbitrage_bounds,
    put_lower_bound,
    put_upper_bound,
)
from options_risk.pricing.exceptions import OptionInputError


def test_known_reference_price_call() -> None:
    # Hull's textbook reference case: S=42, K=40, T=0.5, r=0.10, sigma=0.20 -> call ~= 4.76
    price = bsm_price(S=42, K=40, T=0.5, r=0.10, sigma=0.20, option_type="call")
    assert price == pytest.approx(4.76, abs=0.01)


def test_known_reference_price_put() -> None:
    # Same market: put ~= 0.81
    price = bsm_price(S=42, K=40, T=0.5, r=0.10, sigma=0.20, option_type="put")
    assert price == pytest.approx(0.81, abs=0.01)


@pytest.mark.parametrize(
    "S,K,T,r,sigma,q",
    [
        (100, 100, 1.0, 0.05, 0.2, 0.0),
        (100, 90, 0.25, 0.03, 0.35, 0.02),
        (50, 60, 2.0, 0.01, 0.5, 0.0),
        (120, 100, 0.1, 0.0, 0.15, 0.01),
    ],
)
def test_put_call_parity(S: float, K: float, T: float, r: float, sigma: float, q: float) -> None:
    call = bsm_price(S, K, T, r, sigma, "call", q)
    put = bsm_price(S, K, T, r, sigma, "put", q)
    lhs = call - put
    rhs = S * math.exp(-q * T) - K * math.exp(-r * T)
    assert lhs == pytest.approx(rhs, abs=1e-8)


def test_call_monotonic_increasing_in_spot() -> None:
    prices = [bsm_price(S, 100, 1.0, 0.05, 0.2, "call") for S in (80, 90, 100, 110, 120)]
    assert prices == sorted(prices)


def test_put_monotonic_increasing_in_strike() -> None:
    prices = [bsm_price(100, K, 1.0, 0.05, 0.2, "put") for K in (80, 90, 100, 110, 120)]
    assert prices == sorted(prices)


def test_call_monotonic_decreasing_in_strike() -> None:
    prices = [bsm_price(100, K, 1.0, 0.05, 0.2, "call") for K in (80, 90, 100, 110, 120)]
    assert prices == sorted(prices, reverse=True)


@pytest.mark.parametrize("option_type", ["call", "put"])
def test_positive_gamma_implies_convexity_in_spot(option_type: str) -> None:
    # Second finite difference in S should be positive (convex payoff) away from expiry.
    S0, K, T, r, sigma = 100.0, 100.0, 1.0, 0.05, 0.2
    h = 1.0
    p_dn = bsm_price(S0 - h, K, T, r, sigma, option_type)  # type: ignore[arg-type]
    p_mid = bsm_price(S0, K, T, r, sigma, option_type)  # type: ignore[arg-type]
    p_up = bsm_price(S0 + h, K, T, r, sigma, option_type)  # type: ignore[arg-type]
    second_diff = p_up - 2 * p_mid + p_dn
    assert second_diff > 0


def test_expiry_behavior_is_intrinsic_value() -> None:
    assert bsm_price(110, 100, 0.0, 0.05, 0.2, "call") == pytest.approx(10.0)
    assert bsm_price(90, 100, 0.0, 0.05, 0.2, "call") == pytest.approx(0.0)
    assert bsm_price(90, 100, 0.0, 0.05, 0.2, "put") == pytest.approx(10.0)
    assert bsm_price(110, 100, 0.0, 0.05, 0.2, "put") == pytest.approx(0.0)


@pytest.mark.parametrize(
    "S,K,T,r,q", [(100, 100, 1.0, 0.05, 0.0), (100, 80, 0.5, 0.02, 0.01), (60, 100, 2.0, 0.0, 0.0)]
)
def test_call_price_within_arbitrage_bounds(
    S: float, K: float, T: float, r: float, q: float
) -> None:
    price = bsm_price(S, K, T, r, 0.3, "call", q)
    lo = call_lower_bound(S, K, T, r, q)
    hi = call_upper_bound(S, q, T)
    assert lo - 1e-9 <= price <= hi + 1e-9


@pytest.mark.parametrize(
    "S,K,T,r,q", [(100, 100, 1.0, 0.05, 0.0), (100, 80, 0.5, 0.02, 0.01), (60, 100, 2.0, 0.0, 0.0)]
)
def test_put_price_within_arbitrage_bounds(
    S: float, K: float, T: float, r: float, q: float
) -> None:
    price = bsm_price(S, K, T, r, 0.3, "put", q)
    lo = put_lower_bound(S, K, T, r, q)
    hi = put_upper_bound(K, r, T)
    assert lo - 1e-9 <= price <= hi + 1e-9


def test_is_within_arbitrage_bounds_rejects_impossible_price() -> None:
    # A call priced above spot itself (with q=0) is above the upper bound.
    assert not is_within_arbitrage_bounds(150, 100, 100, 1.0, 0.05, "call")
    # A call priced below the lower bound is impossible.
    assert not is_within_arbitrage_bounds(0.0, 150, 50, 1.0, 0.10, "call")


def test_intrinsic_value() -> None:
    assert intrinsic_value(110, 100, "call") == 10
    assert intrinsic_value(90, 100, "call") == 0
    assert intrinsic_value(90, 100, "put") == 10
    assert intrinsic_value(110, 100, "put") == 0


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(S=0, K=100, T=1, r=0.05, sigma=0.2, option_type="call"),
        dict(S=-5, K=100, T=1, r=0.05, sigma=0.2, option_type="call"),
        dict(S=100, K=0, T=1, r=0.05, sigma=0.2, option_type="call"),
        dict(S=100, K=100, T=-1, r=0.05, sigma=0.2, option_type="call"),
        dict(S=100, K=100, T=1, r=0.05, sigma=-0.1, option_type="call"),
    ],
)
def test_invalid_inputs_raise(kwargs: dict) -> None:
    with pytest.raises(OptionInputError):
        bsm_price(**kwargs)


def test_invalid_option_type_raises() -> None:
    with pytest.raises(OptionInputError):
        bsm_price(100, 100, 1, 0.05, 0.2, "straddle")  # type: ignore[arg-type]


def test_zero_vol_is_deterministic_discounted_forward() -> None:
    S, K, T, r, q = 100.0, 90.0, 1.0, 0.05, 0.0
    forward = S * math.exp((r - q) * T)
    expected_call = math.exp(-r * T) * max(forward - K, 0.0)
    assert bsm_price(S, K, T, r, 0.0, "call", q) == pytest.approx(expected_call)
