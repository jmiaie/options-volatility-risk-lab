"""Portfolio aggregation tests (P1 item 11): market value and Greek accounting."""

from __future__ import annotations

import pytest

from options_risk.portfolio import CashPosition, EquityPosition, OptionPosition, Portfolio
from options_risk.pricing.greeks import greeks


def test_equity_position_market_value_and_delta() -> None:
    pos = EquityPosition(symbol="ABC", quantity=100, price=50.0)
    assert pos.market_value() == 5000.0
    assert pos.position_greeks().delta == 100
    assert pos.position_greeks().gamma == 0
    assert pos.position_greeks().vega == 0


def test_short_equity_position_has_negative_delta() -> None:
    pos = EquityPosition(symbol="ABC", quantity=-100, price=50.0)
    assert pos.market_value() == -5000.0
    assert pos.position_greeks().delta == -100


def test_option_position_scales_by_quantity_and_multiplier() -> None:
    pos = OptionPosition(
        symbol="ABC",
        option_type="call",
        quantity=2,
        strike=100,
        T=1.0,
        S=100,
        r=0.05,
        sigma=0.2,
        multiplier=100,
    )
    unit_g = greeks(100, 100, 1.0, 0.05, 0.2, "call")
    pg = pos.position_greeks()
    assert pg.delta == pytest.approx(2 * 100 * unit_g.delta)
    assert pg.gamma == pytest.approx(2 * 100 * unit_g.gamma)
    assert pg.vega == pytest.approx(2 * 100 * unit_g.vega)
    assert pos.market_value() == pytest.approx(2 * 100 * pos.unit_price())


def test_cash_position_has_no_greeks() -> None:
    pos = CashPosition(amount=10_000)
    g = pos.position_greeks()
    assert g.delta == g.gamma == g.vega == g.theta == g.rho == 0.0
    assert pos.market_value() == 10_000


def test_portfolio_aggregates_market_value() -> None:
    portfolio = Portfolio()
    portfolio.add(EquityPosition("ABC", 100, 50.0))
    portfolio.add(CashPosition(1000.0))
    assert portfolio.market_value() == pytest.approx(5000.0 + 1000.0)


def test_portfolio_aggregates_greeks_across_position_types() -> None:
    portfolio = Portfolio()
    portfolio.add(EquityPosition("ABC", 100, 50.0))
    portfolio.add(OptionPosition("ABC", "put", -1, 50, 0.5, 50.0, 0.03, 0.25, multiplier=100))
    portfolio.add(CashPosition(5000.0))

    equity_delta = 100
    option_greeks = greeks(50.0, 50, 0.5, 0.03, 0.25, "put")
    expected_delta = equity_delta + (-1 * 100 * option_greeks.delta)

    pg = portfolio.greeks()
    assert pg.delta == pytest.approx(expected_delta)
    assert pg.gamma == pytest.approx(-1 * 100 * option_greeks.gamma)
    assert pg.vega == pytest.approx(-1 * 100 * option_greeks.vega)


def test_delta_hedged_portfolio_is_approximately_flat() -> None:
    # Long 1 call contract (100 shares of exposure), short enough stock to flatten delta.
    S, K, T, r, sigma = 100.0, 100.0, 1.0, 0.05, 0.2
    option = OptionPosition("ABC", "call", 1, K, T, S, r, sigma, multiplier=100)
    option_delta = option.position_greeks().delta
    hedge_shares = -option_delta  # short this many shares to flatten delta

    portfolio = Portfolio()
    portfolio.add(option)
    portfolio.add(EquityPosition("ABC", hedge_shares, S))

    assert portfolio.greeks().delta == pytest.approx(0.0, abs=1e-8)


def test_portfolio_helpers_filter_by_type() -> None:
    portfolio = Portfolio()
    equity = EquityPosition("ABC", 10, 50.0)
    option = OptionPosition("ABC", "call", 1, 100, 1.0, 100, 0.05, 0.2)
    cash = CashPosition(100.0)
    portfolio.add(equity)
    portfolio.add(option)
    portfolio.add(cash)

    assert portfolio.equities() == [equity]
    assert portfolio.options() == [option]
    assert portfolio.cash_positions() == [cash]
    assert portfolio.total_cash() == 100.0


def test_empty_portfolio_has_zero_value_and_greeks() -> None:
    portfolio = Portfolio()
    assert portfolio.market_value() == 0.0
    g = portfolio.greeks()
    assert g.delta == g.gamma == g.vega == g.theta == g.rho == 0.0
