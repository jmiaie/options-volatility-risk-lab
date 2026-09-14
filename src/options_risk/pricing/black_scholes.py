"""Black-Scholes-Merton pricing for European options.

Conventions (documented once here; every other module in this package
follows them):

* ``S``: spot price of the underlying, must be > 0.
* ``K``: strike price, must be > 0.
* ``T``: time to expiry in **years** (act/365 or act/act is a data-layer
  choice, not a pricing-layer one), must be >= 0. ``T == 0`` returns
  intrinsic value rather than evaluating ``d1``/``d2`` (which are undefined
  at T=0).
* ``r``: continuously-compounded, annualized risk-free rate (e.g. 0.05 for
  5%). Discount factor is ``exp(-r*T)``.
* ``sigma``: annualized volatility of log-returns, in decimal (0.20 = 20
  vol), must be >= 0. ``sigma == 0`` is a degenerate (no-diffusion) case
  handled as a limit, not silently divided-by-zero.
* ``q``: continuously-compounded, annualized dividend/borrow yield. Enters
  the model exactly like a negative rate applied to the spot leg
  (Merton 1973 extension): the forward is ``F = S * exp((r - q) * T)``.

All functions raise :class:`OptionInputError` for inputs that violate these
preconditions instead of returning NaN, so a bad input fails loudly at the
point of the mistake rather than propagating into a Greek, an IV solve, or a
portfolio aggregate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from scipy.stats import norm

from options_risk.pricing.exceptions import OptionInputError

OptionType = Literal["call", "put"]


def _validate_common(S: float, K: float, T: float, sigma: float) -> None:
    if not np.isfinite(S) or S <= 0:
        raise OptionInputError(f"S (spot) must be > 0, got {S!r}")
    if not np.isfinite(K) or K <= 0:
        raise OptionInputError(f"K (strike) must be > 0, got {K!r}")
    if not np.isfinite(T) or T < 0:
        raise OptionInputError(f"T (time to expiry, years) must be >= 0, got {T!r}")
    if not np.isfinite(sigma) or sigma < 0:
        raise OptionInputError(f"sigma (volatility) must be >= 0, got {sigma!r}")


def _validate_option_type(option_type: str) -> None:
    if option_type not in ("call", "put"):
        raise OptionInputError(f"option_type must be 'call' or 'put', got {option_type!r}")


def intrinsic_value(S: float, K: float, option_type: OptionType) -> float:
    """Payoff if exercised immediately: max(S-K,0) for a call, max(K-S,0) for a put."""
    _validate_option_type(option_type)
    if option_type == "call":
        return max(S - K, 0.0)
    return max(K - S, 0.0)


@dataclass(frozen=True)
class D1D2:
    d1: float
    d2: float


def d1_d2(S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0) -> D1D2:
    """Compute the standard BSM d1, d2 terms. Requires T > 0 and sigma > 0.

    d1 = [ln(S/K) + (r - q + sigma^2/2) * T] / (sigma * sqrt(T))
    d2 = d1 - sigma * sqrt(T)
    """
    _validate_common(S, K, T, sigma)
    if T == 0:
        raise OptionInputError("d1/d2 are undefined at T=0; use intrinsic_value instead")
    if sigma == 0:
        raise OptionInputError("d1/d2 are undefined at sigma=0; price is deterministic forward")
    sqrt_t = np.sqrt(T)
    d1 = (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * sqrt_t)
    d2 = d1 - sigma * sqrt_t
    return D1D2(d1=d1, d2=d2)


def bsm_price(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: OptionType,
    q: float = 0.0,
) -> float:
    """European option price under Black-Scholes-Merton.

    Handles two boundary cases explicitly rather than letting them fall
    through to NaN:

    * ``T == 0`` -> intrinsic value.
    * ``sigma == 0`` (T > 0) -> discounted deterministic payoff of the
      forward price, i.e. the price a zero-vol market would assign.
    """
    _validate_common(S, K, T, sigma)
    _validate_option_type(option_type)

    if T == 0:
        return intrinsic_value(S, K, option_type)

    df_r = np.exp(-r * T)
    df_q = np.exp(-q * T)

    if sigma == 0:
        forward = S * np.exp((r - q) * T)
        payoff = max(forward - K, 0.0) if option_type == "call" else max(K - forward, 0.0)
        return float(df_r * payoff)

    d = d1_d2(S, K, T, r, sigma, q)
    if option_type == "call":
        return float(S * df_q * norm.cdf(d.d1) - K * df_r * norm.cdf(d.d2))
    return float(K * df_r * norm.cdf(-d.d2) - S * df_q * norm.cdf(-d.d1))


def call_lower_bound(S: float, K: float, T: float, r: float, q: float = 0.0) -> float:
    """No-arbitrage lower bound: max(S*exp(-qT) - K*exp(-rT), 0)."""
    return max(S * np.exp(-q * T) - K * np.exp(-r * T), 0.0)


def call_upper_bound(S: float, q: float = 0.0, T: float = 0.0) -> float:
    """No-arbitrage upper bound for a call: S*exp(-qT) (cannot be worth more than the stock)."""
    return S * np.exp(-q * T)


def put_lower_bound(S: float, K: float, T: float, r: float, q: float = 0.0) -> float:
    """No-arbitrage lower bound: max(K*exp(-rT) - S*exp(-qT), 0)."""
    return max(K * np.exp(-r * T) - S * np.exp(-q * T), 0.0)


def put_upper_bound(K: float, r: float, T: float) -> float:
    """No-arbitrage upper bound for a put: K*exp(-rT) (cannot exceed the discounted strike)."""
    return K * np.exp(-r * T)


def is_within_arbitrage_bounds(
    price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    option_type: OptionType,
    q: float = 0.0,
) -> bool:
    """Check whether an observed price lies within static no-arbitrage bounds."""
    _validate_option_type(option_type)
    if option_type == "call":
        lo, hi = call_lower_bound(S, K, T, r, q), call_upper_bound(S, q, T)
    else:
        lo, hi = put_lower_bound(S, K, T, r, q), put_upper_bound(K, r, T)
    return lo - 1e-10 <= price <= hi + 1e-10
