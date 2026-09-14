"""Stress engine and P&L attribution tests (P1 items 12, 19, 20)."""

from __future__ import annotations

import pytest

from options_risk.attribution.pnl_explain import explain_pnl
from options_risk.portfolio import OptionPosition, Portfolio
from options_risk.stress.scenario import (
    STANDARD_STRESS_SCENARIOS,
    Scenario,
    revalue_portfolio,
    run_standard_stress_suite,
    spot_vol_matrix,
)


def _single_option_portfolio(option_type: str = "call") -> Portfolio:
    portfolio = Portfolio()
    portfolio.add(
        OptionPosition("ABC", option_type, 1, 100, 1.0, 100.0, 0.05, 0.20, multiplier=100)  # type: ignore[arg-type]
    )
    return portfolio


def test_zero_scenario_leaves_portfolio_unchanged() -> None:
    portfolio = _single_option_portfolio()
    result = revalue_portfolio(portfolio, Scenario(name="no-op"))
    assert result.mv_after == pytest.approx(result.mv_before)
    assert result.pnl == pytest.approx(0.0)


def test_spot_shock_moves_call_value_up() -> None:
    portfolio = _single_option_portfolio("call")
    result = revalue_portfolio(portfolio, Scenario(name="up", spot_shock_pct=0.10))
    assert result.mv_after > result.mv_before


def test_spot_shock_moves_put_value_up_on_decline() -> None:
    portfolio = _single_option_portfolio("put")
    result = revalue_portfolio(portfolio, Scenario(name="down", spot_shock_pct=-0.10))
    assert result.mv_after > result.mv_before


def test_vol_shock_increases_long_option_value() -> None:
    portfolio = _single_option_portfolio("call")
    result = revalue_portfolio(portfolio, Scenario(name="vol up", vol_shock_abs=0.10))
    assert result.mv_after > result.mv_before


def test_vol_doubling_increases_long_option_value() -> None:
    portfolio = _single_option_portfolio("call")
    result = revalue_portfolio(portfolio, Scenario(name="vol double", vol_shock_mult=2.0))
    assert result.mv_after > result.mv_before


def test_time_decay_reduces_long_atm_option_value() -> None:
    portfolio = _single_option_portfolio("call")
    result = revalue_portfolio(portfolio, Scenario(name="decay", time_decay_years=0.5))
    assert result.mv_after < result.mv_before


def test_standard_stress_suite_runs_all_scenarios() -> None:
    portfolio = _single_option_portfolio()
    results = run_standard_stress_suite(portfolio)
    assert len(results) == len(STANDARD_STRESS_SCENARIOS)
    for r in results:
        assert isinstance(r.pnl, float)


def test_spot_vol_matrix_shape() -> None:
    portfolio = _single_option_portfolio()
    spot_shocks = (-0.1, 0.0, 0.1)
    vol_shocks = (-0.05, 0.0, 0.05)
    results = spot_vol_matrix(portfolio, spot_shocks, vol_shocks)
    assert len(results) == len(spot_shocks) * len(vol_shocks)


def test_spot_vol_matrix_shows_convexity() -> None:
    # For a long call, P&L should be convex in spot: a +10% move should help
    # more than twice a +5% move hurts... more simply: check P&L(+10%) >
    # 2*P&L(+5%) - small tolerance is not needed since gamma makes this strict.
    portfolio = _single_option_portfolio("call")
    pnl_5 = revalue_portfolio(portfolio, Scenario(name="+5", spot_shock_pct=0.05)).pnl
    pnl_10 = revalue_portfolio(portfolio, Scenario(name="+10", spot_shock_pct=0.10)).pnl
    assert pnl_10 > 2 * pnl_5


def test_explain_pnl_small_shock_tracks_closely() -> None:
    portfolio = _single_option_portfolio("call")
    S0 = 100.0
    small_dS = 0.10  # 10 cents on a $100 stock: tiny relative move
    attribution = explain_pnl(portfolio, dS=small_dS)
    assert attribution.residual == pytest.approx(0.0, abs=0.01)
    assert abs(attribution.residual) < 0.05 * abs(attribution.actual_pnl) + 1e-6
    assert S0 == 100.0  # sanity anchor for the comment above


def test_explain_pnl_large_shock_shows_growing_residual() -> None:
    portfolio = _single_option_portfolio("call")
    small = explain_pnl(portfolio, dS=1.0)
    large = explain_pnl(portfolio, dS=20.0)
    assert abs(large.residual) > abs(small.residual)


def test_explain_pnl_components_sum_to_explained() -> None:
    portfolio = _single_option_portfolio("call")
    attribution = explain_pnl(portfolio, dS=5.0, dSigma=0.02, dt=1 / 365, dr=0.001)
    total = (
        attribution.delta_pnl
        + attribution.gamma_pnl
        + attribution.vega_pnl
        + attribution.theta_pnl
        + attribution.rho_pnl
    )
    assert total == pytest.approx(attribution.explained_pnl)
    assert attribution.residual == pytest.approx(attribution.actual_pnl - attribution.explained_pnl)


def test_explain_pnl_rejects_multi_underlying_portfolio() -> None:
    portfolio = Portfolio()
    portfolio.add(OptionPosition("ABC", "call", 1, 100, 1.0, 100.0, 0.05, 0.2))
    portfolio.add(OptionPosition("XYZ", "call", 1, 50, 1.0, 55.0, 0.05, 0.2))
    with pytest.raises(ValueError):
        explain_pnl(portfolio, dS=1.0)
