"""Options pricing, hedging, and portfolio tail-risk utilities."""

from .bsm import (
    OptionGreeks,
    OptionType,
    black_scholes_price,
    finite_difference_greeks,
    greeks,
    implied_volatility,
    price_bounds,
)
from .chains import OptionChain
from .hedging import DeltaHedgeResult, simulate_delta_hedge
from .monte_carlo import MonteCarloResult, monte_carlo_european_price
from .portfolio import CashPosition, EquityPosition, EuropeanOptionPosition, MarketState, Portfolio
from .risk import (
    DeltaNormalVaRResult,
    MonteCarloVaRResult,
    RiskSummary,
    StressScenario,
    historical_var_es,
    kupiec_pof_test,
    monte_carlo_var_es,
    portfolio_historical_pnl,
    stress_test,
)

__all__ = [
    "CashPosition",
    "DeltaHedgeResult",
    "DeltaNormalVaRResult",
    "EquityPosition",
    "EuropeanOptionPosition",
    "MarketState",
    "MonteCarloResult",
    "MonteCarloVaRResult",
    "OptionChain",
    "OptionGreeks",
    "OptionType",
    "Portfolio",
    "RiskSummary",
    "StressScenario",
    "black_scholes_price",
    "finite_difference_greeks",
    "greeks",
    "historical_var_es",
    "implied_volatility",
    "kupiec_pof_test",
    "monte_carlo_european_price",
    "monte_carlo_var_es",
    "portfolio_historical_pnl",
    "price_bounds",
    "simulate_delta_hedge",
    "stress_test",
]
