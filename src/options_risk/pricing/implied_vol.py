"""Implied volatility solving.

Primary method: Brent's method (``scipy.optimize.brentq``) on a bracketed
root of ``bsm_price(sigma) - observed_price == 0``. Brent is used because it
is a bracketing, guaranteed-convergent method for a continuous, monotonic
(in sigma) function — unlike Newton-Raphson, it cannot diverge or overshoot
into a negative/absurd vol. Newton-Raphson is provided only as a secondary,
optional cross-check (see :func:`solve_iv_newton`), never as the default
solve path.

Before solving, the observed price is checked against the static
no-arbitrage bounds (:func:`options_risk.pricing.black_scholes.
is_within_arbitrage_bounds`). A price outside those bounds has no
consistent implied volatility under Black-Scholes (it would require
negative variance), so the solver refuses to return a number for it —
returning a plausible-looking IV for an arbitrage-violating price would be
silently wrong.
"""

from __future__ import annotations

from dataclasses import dataclass

from scipy.optimize import brentq

from options_risk.pricing.black_scholes import (
    OptionType,
    _validate_option_type,
    bsm_price,
    intrinsic_value,
    is_within_arbitrage_bounds,
)
from options_risk.pricing.greeks import greeks

_DEFAULT_SIGMA_LO = 1e-6
_DEFAULT_SIGMA_HI = 5.0  # 500% vol; generous upper bracket for equity/crypto-like inputs


@dataclass(frozen=True)
class ImpliedVolResult:
    iv: float | None
    converged: bool
    iterations: int
    failure_reason: str | None


def solve_iv(
    price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    option_type: OptionType,
    q: float = 0.0,
    *,
    sigma_lo: float = _DEFAULT_SIGMA_LO,
    sigma_hi: float = _DEFAULT_SIGMA_HI,
    max_iter: int = 100,
    xtol: float = 1e-8,
) -> ImpliedVolResult:
    """Solve for Black-Scholes implied volatility via bracketed Brent search.

    Returns an :class:`ImpliedVolResult` with ``converged=False`` and a
    ``failure_reason`` (never a numeric ``iv``) when:

    * the observed price violates static no-arbitrage bounds,
    * the observed price is not distinguishable from intrinsic value at
      ``T > 0`` (implies sigma -> 0, outside the search bracket), or
    * Brent fails to bracket/converge within ``max_iter``.
    """
    _validate_option_type(option_type)

    if T <= 0:
        return ImpliedVolResult(
            iv=None,
            converged=False,
            iterations=0,
            failure_reason=f"T must be > 0 to solve for implied volatility, got {T!r}",
        )

    if not is_within_arbitrage_bounds(price, S, K, T, r, option_type, q):
        return ImpliedVolResult(
            iv=None,
            converged=False,
            iterations=0,
            failure_reason=(
                "observed price violates static no-arbitrage bounds; "
                "no Black-Scholes volatility is consistent with this price"
            ),
        )

    intrinsic = intrinsic_value(S, K, option_type)
    if price <= intrinsic + 1e-12:
        return ImpliedVolResult(
            iv=None,
            converged=False,
            iterations=0,
            failure_reason=(
                "observed price is at or below intrinsic value; implied vol "
                "is at or below the solver's lower bound (near-zero vol)"
            ),
        )

    iteration_count = 0

    def objective(sigma: float) -> float:
        nonlocal iteration_count
        iteration_count += 1
        return bsm_price(S, K, T, r, sigma, option_type, q) - price

    f_lo = objective(sigma_lo)
    f_hi = objective(sigma_hi)
    if f_lo * f_hi > 0:
        return ImpliedVolResult(
            iv=None,
            converged=False,
            iterations=iteration_count,
            failure_reason=(
                f"price not bracketed by sigma in [{sigma_lo}, {sigma_hi}]; "
                "widen the search bracket or treat as unsolvable"
            ),
        )

    try:
        iv, results = brentq(
            objective, sigma_lo, sigma_hi, xtol=xtol, maxiter=max_iter, full_output=True
        )
    except (RuntimeError, ValueError) as exc:
        return ImpliedVolResult(
            iv=None, converged=False, iterations=iteration_count, failure_reason=str(exc)
        )

    if not results.converged:
        return ImpliedVolResult(
            iv=None,
            converged=False,
            iterations=iteration_count,
            failure_reason="brentq did not converge within max_iter",
        )

    return ImpliedVolResult(iv=iv, converged=True, iterations=iteration_count, failure_reason=None)


def solve_iv_newton(
    price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    option_type: OptionType,
    q: float = 0.0,
    *,
    sigma_init: float = 0.2,
    max_iter: int = 50,
    tol: float = 1e-8,
) -> ImpliedVolResult:
    """Newton-Raphson IV solve, for cross-checking :func:`solve_iv` only.

    Not used as the default/production solve path: Newton can diverge or
    walk sigma negative for poorly-conditioned starting points (deep
    ITM/OTM, near-expiry), whereas Brent is guaranteed to converge once a
    bracket is found. Vega-based Newton steps with a floor to keep sigma
    positive.
    """
    _validate_option_type(option_type)
    if T <= 0:
        return ImpliedVolResult(
            iv=None, converged=False, iterations=0, failure_reason="T must be > 0"
        )
    if not is_within_arbitrage_bounds(price, S, K, T, r, option_type, q):
        return ImpliedVolResult(
            iv=None,
            converged=False,
            iterations=0,
            failure_reason="observed price violates static no-arbitrage bounds",
        )

    sigma = sigma_init
    for i in range(1, max_iter + 1):
        model_price = bsm_price(S, K, T, r, sigma, option_type, q)
        diff = model_price - price
        if abs(diff) < tol:
            return ImpliedVolResult(iv=sigma, converged=True, iterations=i, failure_reason=None)
        vega = greeks(S, K, T, r, sigma, option_type, q).vega
        if vega < 1e-12:
            return ImpliedVolResult(
                iv=None, converged=False, iterations=i, failure_reason="vega too small near zero"
            )
        sigma = max(sigma - diff / vega, 1e-8)

    return ImpliedVolResult(
        iv=None, converged=False, iterations=max_iter, failure_reason="max_iter exceeded"
    )
