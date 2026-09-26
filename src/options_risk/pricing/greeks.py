"""Analytic Black-Scholes-Merton Greeks.

Unit conventions (chosen once, documented, and tested — see
``tests/test_greeks.py`` and the independent finite-difference check in
``options_risk.pricing.greeks_fd``):

* **Delta** (dV/dS): unitless, price change per 1.00 change in spot.
* **Gamma** (d^2V/dS^2): price-change-in-delta per 1.00 change in spot.
* **Vega** (dV/dsigma): price change per 1.00 change in volatility (i.e.
  per 100 vol points, since sigma is in decimal form). To get the more
  commonly quoted "per 1 vol point" (e.g. 20% -> 21%) sensitivity, divide
  by 100.
* **Theta** (dV/dt, annualized): reported as the derivative with respect to
  the **passage of time** (not time-to-expiry), i.e.
  ``theta = -dV/dT``, annual units. A long option's theta is typically
  negative (value decays as time passes). To get the commonly quoted
  "per calendar day" decay, divide by 365.
* **Rho** (dV/dr): price change per 1.00 (100 percentage points) change in
  the continuously-compounded rate. Divide by 100 for a "per 1% (100bps)"
  sensitivity.

All Greeks include continuous dividend yield ``q``. At ``T == 0`` all
Greeks except Delta are zero (the position is now pure stock/cash) and
Delta is 1.0 (call, if ITM) / -1.0 (put, if ITM) / 0.0 (if OTM), and
+0.5 (call) / -0.5 (put) at exact-ATM expiry (the midpoint of the
subgradient at the kink).

At ``sigma == 0`` (with ``T > 0``) the option value is the deterministic
discounted forward payoff, and the Greeks are the ``sigma -> 0`` limits of
the BSM formulas: Gamma and Vega are 0; for an in-the-money-forward call
(``S e^{(r-q)T} > K``) Delta is ``e^{-qT}``, Theta is
``q S e^{-qT} - r K e^{-rT}`` and Rho is ``K T e^{-rT}``; for an
in-the-money-forward put Delta is ``-e^{-qT}``, Theta is
``r K e^{-rT} - q S e^{-qT}`` and Rho is ``-K T e^{-rT}``. Out of the money
(or exactly at the forward, where the limit is not defined) all are 0.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import norm

from options_risk.pricing.black_scholes import (
    D1D2,
    OptionType,
    _validate_common,
    _validate_option_type,
    d1_d2,
)


@dataclass(frozen=True)
class Greeks:
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float


def _expiry_greeks(S: float, K: float, option_type: OptionType) -> Greeks:
    if option_type == "call":
        delta = 1.0 if S > K else (0.5 if S == K else 0.0)
    else:
        delta = -1.0 if S < K else (-0.5 if S == K else 0.0)
    return Greeks(delta=delta, gamma=0.0, vega=0.0, theta=0.0, rho=0.0)


def greeks(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: OptionType,
    q: float = 0.0,
) -> Greeks:
    """Analytic Delta/Gamma/Vega/Theta/Rho. See module docstring for units."""
    _validate_common(S, K, T, sigma)
    _validate_option_type(option_type)

    if T == 0:
        return _expiry_greeks(S, K, option_type)
    if sigma == 0:
        # Degenerate zero-vol case: price is a deterministic discounted
        # forward payoff, piecewise linear in S with a kink at K -> Gamma
        # and Vega are formally singular there; report 0 Gamma/Vega and the
        # one-sided Delta of the (locally linear) payoff.
        # Theta = -dV/dT and Rho = dV/dr of V = +/-(S e^{-qT} - K e^{-rT}).
        forward = S * np.exp((r - q) * T)
        df_r = np.exp(-r * T)
        df_q = np.exp(-q * T)
        delta = theta = rho = 0.0
        if option_type == "call" and forward > K:
            delta = df_q
            theta = q * S * df_q - r * K * df_r
            rho = K * T * df_r
        elif option_type == "put" and forward < K:
            delta = -df_q
            theta = r * K * df_r - q * S * df_q
            rho = -K * T * df_r
        return Greeks(delta=float(delta), gamma=0.0, vega=0.0, theta=float(theta), rho=float(rho))

    d1d2: D1D2 = d1_d2(S, K, T, r, sigma, q)
    d1, d2 = d1d2.d1, d1d2.d2
    sqrt_t = np.sqrt(T)
    df_r = np.exp(-r * T)
    df_q = np.exp(-q * T)
    pdf_d1 = norm.pdf(d1)

    gamma = df_q * pdf_d1 / (S * sigma * sqrt_t)
    vega = S * df_q * pdf_d1 * sqrt_t

    if option_type == "call":
        delta = df_q * norm.cdf(d1)
        theta = (
            -S * df_q * pdf_d1 * sigma / (2 * sqrt_t)
            - r * K * df_r * norm.cdf(d2)
            + q * S * df_q * norm.cdf(d1)
        )
        rho = K * T * df_r * norm.cdf(d2)
    else:
        delta = -df_q * norm.cdf(-d1)
        theta = (
            -S * df_q * pdf_d1 * sigma / (2 * sqrt_t)
            + r * K * df_r * norm.cdf(-d2)
            - q * S * df_q * norm.cdf(-d1)
        )
        rho = -K * T * df_r * norm.cdf(-d2)

    return Greeks(
        delta=float(delta),
        gamma=float(gamma),
        vega=float(vega),
        theta=float(theta),
        rho=float(rho),
    )
