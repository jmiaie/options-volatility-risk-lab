"""Finite-difference Greeks, independent of the analytic implementation.

This module exists purely as a validation cross-check: it calls only
:func:`options_risk.pricing.black_scholes.bsm_price` (the same primitive an
end user would call) and never imports or shares code with
:mod:`options_risk.pricing.greeks`. Agreement between the two, within the
tolerances tested in ``tests/test_greeks_fd.py``, is evidence the closed-form
derivatives were transcribed correctly.

Same unit conventions as :mod:`options_risk.pricing.greeks` (Vega per 1.00
vol, Theta per year of elapsed time, Rho per 1.00 change in r).
"""

from __future__ import annotations

from dataclasses import dataclass

from options_risk.pricing.black_scholes import OptionType, bsm_price


@dataclass(frozen=True)
class FiniteDifferenceGreeks:
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float


def fd_greeks(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: OptionType,
    q: float = 0.0,
    *,
    h_S: float = 1e-4,
    h_sigma: float = 1e-6,
    h_r: float = 1e-6,
    h_T: float = 1e-6,
) -> FiniteDifferenceGreeks:
    """Bump-and-reprice Greeks via central (and one-sided time) differences.

    Bump sizes are relative to the natural scale of each input: ``h_S`` is a
    fraction of spot, the others are small absolute bumps in decimal units.
    Requires ``T > h_T`` so the theta bump stays on the T > 0 branch of the
    pricer (finite differences cannot probe the T=0 kink).
    """
    if T <= h_T:
        raise ValueError(
            f"T={T} too small for a stable finite-difference theta bump "
            f"(need T > h_T={h_T}); finite differences cannot probe the T=0 kink"
        )

    dS = h_S * S

    price_up_S = bsm_price(S + dS, K, T, r, sigma, option_type, q)
    price_dn_S = bsm_price(S - dS, K, T, r, sigma, option_type, q)
    price_mid = bsm_price(S, K, T, r, sigma, option_type, q)
    delta = (price_up_S - price_dn_S) / (2 * dS)
    gamma = (price_up_S - 2 * price_mid + price_dn_S) / (dS**2)

    price_up_sigma = bsm_price(S, K, T, r, sigma + h_sigma, option_type, q)
    price_dn_sigma = bsm_price(S, K, T, r, sigma - h_sigma, option_type, q)
    vega = (price_up_sigma - price_dn_sigma) / (2 * h_sigma)

    price_up_r = bsm_price(S, K, T, r + h_r, sigma, option_type, q)
    price_dn_r = bsm_price(S, K, T, r - h_r, sigma, option_type, q)
    rho = (price_up_r - price_dn_r) / (2 * h_r)

    # Theta is -dV/dT (value decays as time PASSES, i.e. T decreases toward
    # expiry), evaluated with a central difference in T away from expiry.
    price_up_T = bsm_price(S, K, T + h_T, r, sigma, option_type, q)
    price_dn_T = bsm_price(S, K, T - h_T, r, sigma, option_type, q)
    theta = -(price_up_T - price_dn_T) / (2 * h_T)

    return FiniteDifferenceGreeks(delta=delta, gamma=gamma, vega=vega, theta=theta, rho=rho)
