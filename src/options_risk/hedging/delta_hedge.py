"""Discrete delta-hedging simulator for a European option under GBM.

Setup and sign conventions:

* ``option_qty``: signed position in the option, e.g. ``+1`` = long one
  option, ``-1`` = short (written) one option.
* At each rebalance time, the hedger holds ``shares_held = -option_qty *
  delta`` shares of the underlying, where ``delta`` is the option's
  Black-Scholes delta computed at the **pricing volatility** (the vol the
  trader believes in / used to price the option) — this is the delta that
  makes the combined position ``option_qty * option_value + shares_held *
  S`` instantaneously flat in ``S`` under that pricing model.
* The underlying itself is simulated under **realized volatility**
  (``sigma_realized``), which may differ from ``sigma_pricing`` — this is
  the deliberate lever for studying model/vol misspecification. Both use
  the same risk-neutral drift ``(r - q)`` (this is a hedging-error study,
  not a real-world P&L study, so no separate real-world drift is modeled).
* ``cash`` accrues interest at the continuously-compounded rate ``r`` over
  each rebalance interval, then absorbs the cash flow from any hedge trade
  (buy = cash outflow, sell = cash inflow) net of a proportional
  transaction cost (``cost_rate`` as a fraction of traded notional).
* The account is **self-financing except for the initial option premium
  cash flow**: entering the option position at ``t=0`` costs
  ``-option_qty * price_0`` in cash (this is the one explicit external cash
  flow — buying/selling the option itself, not a hedge trade); every
  subsequent hedge trade and financing flow is internal to the cash
  account.
* At expiry, the hedge is unwound (shares sold/bought back to zero,
  incurring one final transaction cost) and the option settles at
  intrinsic value. **Hedging P&L** (a.k.a. replication error) is the
  resulting terminal cash balance: 0 would mean the discrete hedge
  perfectly replicated the option's payoff net of its initial premium;
  in general it will not be exactly 0, and that gap is the object of
  study, not a bug. Continuous, frictionless, correctly-specified
  Black-Scholes replication is a limiting idealization — this simulator
  exists specifically to show the size of the gap between that
  idealization and discrete, costly, and potentially mis-specified hedging.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from options_risk.pricing.black_scholes import OptionType, bsm_price, intrinsic_value
from options_risk.pricing.greeks import greeks


@dataclass(frozen=True)
class HedgeSimResult:
    path: pd.DataFrame
    final_wealth: float
    total_transaction_costs: float
    n_rebalances: int
    option_qty: float
    sigma_pricing: float
    sigma_realized: float


def simulate_delta_hedge(
    S0: float,
    K: float,
    T: float,
    r: float,
    sigma_pricing: float,
    option_type: OptionType,
    q: float = 0.0,
    *,
    sigma_realized: float | None = None,
    option_qty: float = -1.0,
    n_steps: int = 52,
    cost_rate: float = 0.0,
    seed: int | None = None,
) -> HedgeSimResult:
    """Simulate a discretely-rebalanced delta hedge of a European option.

    ``sigma_realized`` defaults to ``sigma_pricing`` (no vol misspecification).
    ``n_steps`` is the number of equally-spaced rebalance intervals (e.g. 52
    for weekly rebalancing over a 1-year option, 252 for daily).
    """
    if n_steps < 1:
        raise ValueError(f"n_steps must be >= 1, got {n_steps}")
    if T <= 0:
        raise ValueError(f"T must be > 0, got {T}")
    if cost_rate < 0:
        raise ValueError(f"cost_rate must be >= 0, got {cost_rate}")
    sigma_realized = sigma_pricing if sigma_realized is None else sigma_realized

    rng = np.random.default_rng(seed)
    dt = T / n_steps
    drift = (r - q - 0.5 * sigma_realized**2) * dt
    vol = sigma_realized * np.sqrt(dt)
    z = rng.standard_normal(n_steps)
    log_returns = drift + vol * z

    S_path = np.empty(n_steps + 1)
    S_path[0] = S0
    S_path[1:] = S0 * np.exp(np.cumsum(log_returns))

    rows = []
    cash = -option_qty * bsm_price(S0, K, T, r, sigma_pricing, option_type, q)
    shares_held = 0.0
    total_costs = 0.0

    for i in range(n_steps + 1):
        S_i = S_path[i]
        T_remaining = T - i * dt
        if T_remaining > 1e-12:
            option_value = bsm_price(S_i, K, T_remaining, r, sigma_pricing, option_type, q)
            delta = greeks(S_i, K, T_remaining, r, sigma_pricing, option_type, q).delta
        else:
            option_value = intrinsic_value(S_i, K, option_type)
            delta = 0.0  # position is closed out below; no more hedging needed

        target_shares = 0.0 if i == n_steps else -option_qty * delta
        shares_traded = target_shares - shares_held
        trade_notional = abs(shares_traded) * S_i
        trade_cost = cost_rate * trade_notional
        total_costs += trade_cost

        # Cash flow from the trade: buying shares (shares_traded > 0) costs cash.
        cash -= shares_traded * S_i + trade_cost
        shares_held = target_shares

        portfolio_value = option_qty * option_value + shares_held * S_i + cash

        rows.append(
            {
                "step": i,
                "time": i * dt,
                "S": S_i,
                "option_value": option_value,
                "delta": delta,
                "shares_held": shares_held,
                "shares_traded": shares_traded,
                "trade_cost": trade_cost,
                "cash": cash,
                "portfolio_value": portfolio_value,
            }
        )

        if i < n_steps:
            cash *= np.exp(r * dt)  # financing/interest accrual over the next interval

    path = pd.DataFrame(rows)
    # At expiry, shares_held == 0 (hedge unwound above) and option_value ==
    # intrinsic value (the settlement payoff), so portfolio_value at the
    # final row already nets the option settlement into the cash position:
    # final_wealth = option_qty * payoff + 0 + cash.
    final_wealth = float(path.iloc[-1]["portfolio_value"])

    return HedgeSimResult(
        path=path,
        final_wealth=final_wealth,
        total_transaction_costs=total_costs,
        n_rebalances=n_steps,
        option_qty=option_qty,
        sigma_pricing=sigma_pricing,
        sigma_realized=sigma_realized,
    )
