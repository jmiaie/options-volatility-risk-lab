from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .bsm import OptionType, black_scholes_price, greeks


@dataclass(frozen=True)
class DeltaHedgeResult:
    ledger: pd.DataFrame
    final_pnl: float
    replication_error: float
    total_transaction_costs: float


def simulate_delta_hedge(
    option_type: OptionType,
    spot_path: np.ndarray,
    observation_times: np.ndarray,
    strike: float,
    maturity: float,
    volatility: float,
    rate: float = 0.0,
    dividend_yield: float = 0.0,
    *,
    option_position: int = 1,
    transaction_cost_rate: float = 0.0,
) -> DeltaHedgeResult:
    if option_position not in {-1, 1}:
        raise ValueError("option_position must be +1 (long) or -1 (short)")
    spots = np.asarray(spot_path, dtype=float)
    times = np.asarray(observation_times, dtype=float)
    if spots.ndim != 1 or times.ndim != 1 or spots.size != times.size:
        raise ValueError(
            "spot_path and observation_times must be one-dimensional arrays of equal length"
        )
    if spots.size < 2:
        raise ValueError("At least two observations are required")
    if not np.isclose(times[0], 0.0):
        raise ValueError("observation_times must start at 0.0")
    if np.any(np.diff(times) <= 0.0):
        raise ValueError("observation_times must be strictly increasing")
    if times[-1] > maturity + 1e-12:
        raise ValueError("observation_times cannot extend beyond maturity")
    if (spots <= 0.0).any():
        raise ValueError("spot_path must stay strictly positive")
    if transaction_cost_rate < 0.0:
        raise ValueError("transaction_cost_rate must be non-negative")

    rows: list[dict[str, float]] = []
    total_costs = 0.0
    shares = 0.0
    cash = 0.0
    previous_time = 0.0

    for index, (time_now, spot_now) in enumerate(zip(times, spots, strict=True)):
        if index > 0:
            cash *= math.exp(rate * (time_now - previous_time))
        remaining = max(maturity - time_now, 0.0)
        option_value = option_position * black_scholes_price(
            option_type,
            float(spot_now),
            strike,
            remaining,
            volatility,
            rate,
            dividend_yield,
        )
        if index == len(times) - 1 or remaining == 0.0:
            target_shares = 0.0
            hedge_delta = 0.0
        else:
            hedge_delta = greeks(
                option_type,
                float(spot_now),
                strike,
                remaining,
                volatility,
                rate,
                dividend_yield,
            ).delta
            target_shares = -option_position * hedge_delta
        traded_shares = target_shares - shares
        transaction_cost = abs(traded_shares) * float(spot_now) * transaction_cost_rate
        total_costs += transaction_cost

        if index == 0:
            cash = -(option_value + target_shares * float(spot_now) + transaction_cost)
        else:
            cash -= traded_shares * float(spot_now) + transaction_cost
        shares = target_shares
        portfolio_value = option_value + shares * float(spot_now) + cash
        rows.append(
            {
                "time": float(time_now),
                "spot": float(spot_now),
                "remaining_maturity": remaining,
                "option_value": option_value,
                "hedge_delta": hedge_delta,
                "shares": shares,
                "traded_shares": traded_shares,
                "transaction_cost": transaction_cost,
                "cash": cash,
                "portfolio_value": portfolio_value,
            }
        )
        previous_time = float(time_now)

    ledger = pd.DataFrame(rows)
    final_pnl = float(ledger["portfolio_value"].iloc[-1])
    return DeltaHedgeResult(
        ledger=ledger,
        final_pnl=final_pnl,
        replication_error=final_pnl,
        total_transaction_costs=float(total_costs),
    )
