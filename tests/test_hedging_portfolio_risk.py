import numpy as np
import pandas as pd
import pytest

from options_risk.hedging import simulate_delta_hedge
from options_risk.portfolio import (
    CashPosition,
    EquityPosition,
    EuropeanOptionPosition,
    MarketState,
    Portfolio,
)
from options_risk.risk import (
    StressScenario,
    delta_normal_var,
    historical_var_es,
    kupiec_pof_test,
    monte_carlo_var_es,
    portfolio_historical_pnl,
    stress_test,
)


def test_delta_hedge_self_financing_ledger_and_costs() -> None:
    times = np.linspace(0.0, 1.0, 6)
    spots = np.array([100.0, 102.0, 99.0, 103.0, 101.0, 100.5])
    result = simulate_delta_hedge(
        "call",
        spots,
        times,
        strike=100.0,
        maturity=1.0,
        volatility=0.2,
        rate=0.01,
        dividend_yield=0.0,
        option_position=1,
        transaction_cost_rate=0.001,
    )
    assert result.ledger["portfolio_value"].iloc[0] == pytest.approx(
        -result.ledger["transaction_cost"].iloc[0]
    )
    assert result.total_transaction_costs == pytest.approx(result.ledger["transaction_cost"].sum())
    assert result.total_transaction_costs > 0.0


def test_portfolio_greeks_repricing_and_stress_matrix() -> None:
    market = MarketState(spot=100.0, rate=0.02, dividend_yield=0.01, volatility=0.2)
    portfolio = Portfolio(
        positions=(
            CashPosition(10.0),
            EquityPosition(5.0),
            EuropeanOptionPosition("call", 100.0, 1.0, 2.0),
            EuropeanOptionPosition("put", 95.0, 0.5, -1.0),
        )
    )
    greeks_map = portfolio.greeks(market)
    assert greeks_map["gamma"] > 0.0
    explain = portfolio.pnl_explain(
        market, spot_shift=2.0, vol_shift=0.01, rate_shift=0.001, time_shift=1 / 365
    )
    assert explain["repriced_value"] != explain["base_value"]
    matrix = portfolio.spot_vol_matrix(
        market, spot_shifts=[-5.0, 0.0, 5.0], vol_shifts=[-0.02, 0.0, 0.02]
    )
    assert len(matrix) == 9
    stresses = stress_test(
        portfolio, market, [StressScenario("down", spot_return=np.log(0.9), vol_shift=0.03)]
    )
    assert list(stresses["scenario"]) == ["down"]


def test_var_es_and_kupiec_use_positive_loss_convention() -> None:
    pnl = np.array([1.0, -2.0, 0.5, -4.0, 3.0, -1.5])
    summary = historical_var_es(pnl, 0.8)
    assert summary.var >= 0.0
    assert summary.expected_shortfall >= summary.var
    kupiec = kupiec_pof_test(
        np.array([False, True, False, False, True]), expected_exceedance_rate=0.2
    )
    assert kupiec.observed_exceedances == 2
    assert 0.0 <= kupiec.p_value <= 1.0


def test_portfolio_historical_and_monte_carlo_var() -> None:
    market = MarketState(spot=100.0, rate=0.02, dividend_yield=0.0, volatility=0.2)
    portfolio = Portfolio((EquityPosition(1.0), EuropeanOptionPosition("put", 100.0, 1.0, 1.0)))
    scenarios = pd.DataFrame(
        {
            "spot_return": [np.log(0.95), np.log(1.0), np.log(1.05), np.log(0.9)],
            "vol_shift": [0.01, 0.0, -0.01, 0.03],
            "rate_shift": [0.0, 0.0, 0.001, -0.001],
        }
    )
    pnl = portfolio_historical_pnl(portfolio, market, scenarios)
    assert pnl.shape == (4,)
    covariance = np.array(
        [
            [0.04 / 252.0, 0.0, 0.0],
            [0.0, 0.02**2 / 252.0, 0.0],
            [0.0, 0.0, 0.005**2 / 252.0],
        ]
    )
    dn = delta_normal_var(portfolio, market, covariance, confidence_level=0.95)
    mc = monte_carlo_var_es(
        portfolio, market, covariance, confidence_level=0.95, n_sims=2000, seed=11
    )
    assert dn.var >= 0.0
    assert mc.var >= 0.0
    assert mc.expected_shortfall >= mc.var
