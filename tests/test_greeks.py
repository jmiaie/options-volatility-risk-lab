"""Analytic Greek sanity tests (units documented in options_risk.pricing.greeks)."""

from __future__ import annotations

import pytest

from options_risk.pricing.greeks import greeks


@pytest.mark.parametrize("option_type", ["call", "put"])
def test_gamma_is_positive(option_type: str) -> None:
    g = greeks(100, 100, 1.0, 0.05, 0.2, option_type)  # type: ignore[arg-type]
    assert g.gamma > 0


@pytest.mark.parametrize("option_type", ["call", "put"])
def test_vega_is_positive(option_type: str) -> None:
    g = greeks(100, 100, 1.0, 0.05, 0.2, option_type)  # type: ignore[arg-type]
    assert g.vega > 0


def test_call_delta_in_zero_one() -> None:
    g = greeks(100, 100, 1.0, 0.05, 0.2, "call")
    assert 0.0 < g.delta < 1.0


def test_put_delta_in_minus_one_zero() -> None:
    g = greeks(100, 100, 1.0, 0.05, 0.2, "put")
    assert -1.0 < g.delta < 0.0


def test_deep_itm_call_delta_near_one() -> None:
    g = greeks(200, 100, 1.0, 0.05, 0.2, "call")
    assert g.delta > 0.95


def test_deep_otm_call_delta_near_zero() -> None:
    g = greeks(50, 100, 1.0, 0.05, 0.2, "call")
    assert g.delta < 0.05


def test_put_call_delta_relationship_with_dividends() -> None:
    # call_delta - put_delta == exp(-qT) for the same S,K,T,sigma
    import math

    S, K, T, r, sigma, q = 100.0, 100.0, 1.0, 0.05, 0.2, 0.02
    call_delta = greeks(S, K, T, r, sigma, "call", q).delta
    put_delta = greeks(S, K, T, r, sigma, "put", q).delta
    assert call_delta - put_delta == pytest.approx(math.exp(-q * T), abs=1e-10)


def test_expiry_greeks_are_degenerate() -> None:
    g_itm = greeks(110, 100, 0.0, 0.05, 0.2, "call")
    assert g_itm.delta == 1.0
    assert g_itm.gamma == 0.0
    assert g_itm.vega == 0.0
    assert g_itm.theta == 0.0
    assert g_itm.rho == 0.0

    g_otm = greeks(90, 100, 0.0, 0.05, 0.2, "call")
    assert g_otm.delta == 0.0


def test_theta_is_negative_for_atm_long_option() -> None:
    # Long ATM options typically lose value as time passes (theta decay).
    call_theta = greeks(100, 100, 0.5, 0.03, 0.25, "call").theta
    put_theta = greeks(100, 100, 0.5, 0.03, 0.25, "put").theta
    assert call_theta < 0
    assert put_theta < 0


@pytest.mark.parametrize(
    ("S", "K", "option_type"),
    [(120.0, 100.0, "call"), (80.0, 100.0, "put"), (80.0, 100.0, "call"), (120.0, 100.0, "put")],
)
def test_zero_vol_greeks_match_small_sigma_limit(S: float, K: float, option_type: str) -> None:
    """sigma == 0 Greeks equal the sigma -> 0 limit of the analytic formulas."""
    T, r, q = 0.5, 0.05, 0.02
    exact = greeks(S, K, T, r, 0.0, option_type, q=q)  # type: ignore[arg-type]
    limit = greeks(S, K, T, r, 1e-6, option_type, q=q)  # type: ignore[arg-type]
    for name in ("delta", "theta", "rho"):
        assert getattr(exact, name) == pytest.approx(getattr(limit, name), abs=1e-6)
    assert exact.gamma == 0.0 and exact.vega == 0.0


def test_expiry_atm_delta_is_half() -> None:
    assert greeks(100.0, 100.0, 0.0, 0.05, 0.2, "call").delta == 0.5
    assert greeks(100.0, 100.0, 0.0, 0.05, 0.2, "put").delta == -0.5
