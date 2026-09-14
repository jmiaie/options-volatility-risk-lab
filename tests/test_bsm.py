import math

import pytest

from options_risk.bsm import (
    black_scholes_price,
    finite_difference_greeks,
    greeks,
    implied_volatility,
    price_bounds,
)

BASE_CASE = {
    "spot": 100.0,
    "strike": 100.0,
    "time_to_expiry": 1.0,
    "volatility": 0.2,
    "rate": 0.05,
    "dividend_yield": 0.02,
}


def test_reference_prices_and_put_call_parity() -> None:
    call = black_scholes_price("call", **BASE_CASE)
    put = black_scholes_price("put", **BASE_CASE)
    assert call == pytest.approx(9.2270055, rel=1e-7)
    assert put == pytest.approx(6.3300806, rel=1e-7)
    lhs = call - put
    rhs = BASE_CASE["spot"] * math.exp(
        -BASE_CASE["dividend_yield"] * BASE_CASE["time_to_expiry"]
    ) - BASE_CASE["strike"] * math.exp(-BASE_CASE["rate"] * BASE_CASE["time_to_expiry"])
    assert lhs == pytest.approx(rhs, rel=1e-10)


def test_greeks_match_finite_differences() -> None:
    analytic = greeks("call", **BASE_CASE)
    numeric = finite_difference_greeks("call", **BASE_CASE)
    assert analytic.delta == pytest.approx(numeric.delta, rel=1e-4)
    assert analytic.gamma == pytest.approx(numeric.gamma, rel=1e-4)
    assert analytic.vega == pytest.approx(numeric.vega, rel=1e-4)
    assert analytic.theta == pytest.approx(numeric.theta, rel=5e-4)
    assert analytic.rho == pytest.approx(numeric.rho, rel=1e-4)


@pytest.mark.parametrize("option_type", ["call", "put"])
def test_expiry_and_bounds_behavior(option_type: str) -> None:
    price = black_scholes_price(option_type, 95.0, 100.0, 0.0, 0.3, 0.01, 0.0)
    expected = 0.0 if option_type == "call" else 5.0
    assert price == pytest.approx(expected)
    lower, upper = price_bounds(option_type, 100.0, 100.0, 1.0, 0.05, 0.02)
    mid = black_scholes_price(option_type, **BASE_CASE)
    assert lower <= mid <= upper


def test_monotonicity_positive_gamma_and_zero_vol_limit() -> None:
    low = black_scholes_price("call", 90.0, 100.0, 1.0, 0.2, 0.05, 0.02)
    high = black_scholes_price("call", 110.0, 100.0, 1.0, 0.2, 0.05, 0.02)
    assert high > low
    gamma = greeks("put", **BASE_CASE).gamma
    assert gamma > 0.0
    zero_vol_call = black_scholes_price("call", 100.0, 95.0, 1.0, 0.0, 0.03, 0.01)
    assert zero_vol_call == pytest.approx(
        max(100.0 * math.exp(-0.01) - 95.0 * math.exp(-0.03), 0.0)
    )


def test_implied_volatility_round_trip_and_failure_status() -> None:
    for strike, maturity, vol in [(80.0, 0.25, 0.15), (100.0, 1.0, 0.2), (120.0, 2.0, 0.35)]:
        price = black_scholes_price("call", 100.0, strike, maturity, vol, 0.03, 0.01)
        result = implied_volatility("call", price, 100.0, strike, maturity, 0.03, 0.01)
        assert result.success
        assert result.implied_volatility == pytest.approx(vol, rel=1e-6)
    failed = implied_volatility("call", 200.0, 100.0, 100.0, 1.0, 0.01, 0.0)
    assert not failed.success
    assert failed.status == "out_of_bounds"
