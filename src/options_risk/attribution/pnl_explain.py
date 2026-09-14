"""Greek-based (Taylor) P&L attribution vs. full revaluation.

The second-order Taylor approximation to a portfolio's P&L under a market
move is:

    dP_approx = Delta*dS + 0.5*Gamma*dS^2 + Vega*dSigma + Theta*dt + Rho*dr

using the unit conventions documented in :mod:`options_risk.pricing.greeks`
(Vega per 1.00 vol, Theta per year of elapsed time so its contribution here
uses ``dt`` = years elapsed, Rho per 1.00 change in r). This is compared
against the **actual** P&L from full revaluation
(:mod:`options_risk.stress.scenario`); the difference is the **residual**
(unexplained P&L) — driven by higher-order terms (third-derivative/vol-of-vol
effects, cross Greeks like Vanna/Charm not modeled here) that grow with
shock size. This module makes no claim that the Greek approximation *is*
the P&L; it exists specifically to quantify how far apart they are.

Assumes a single-underlying portfolio (the same ``dS`` and ``dSigma``
apply to every position), matching the scope of
:mod:`options_risk.stress.scenario`.
"""

from __future__ import annotations

from dataclasses import dataclass

from options_risk.portfolio.portfolio import Portfolio, PortfolioGreeks
from options_risk.stress.scenario import Scenario, revalue_portfolio


@dataclass(frozen=True)
class PnLAttribution:
    delta_pnl: float
    gamma_pnl: float
    vega_pnl: float
    theta_pnl: float
    rho_pnl: float
    explained_pnl: float
    actual_pnl: float
    residual: float

    @property
    def residual_pct_of_actual(self) -> float:
        return self.residual / self.actual_pnl if self.actual_pnl != 0 else float("nan")


def taylor_pnl(greeks: PortfolioGreeks, dS: float, dSigma: float, dt: float, dr: float) -> dict:
    """Decompose the Taylor-approximated P&L into its per-Greek components."""
    return {
        "delta_pnl": greeks.delta * dS,
        "gamma_pnl": 0.5 * greeks.gamma * dS**2,
        "vega_pnl": greeks.vega * dSigma,
        "theta_pnl": greeks.theta * dt,
        "rho_pnl": greeks.rho * dr,
    }


def explain_pnl(
    portfolio: Portfolio,
    dS: float,
    dSigma: float = 0.0,
    dt: float = 0.0,
    dr: float = 0.0,
) -> PnLAttribution:
    """Compare a Greek-based P&L explain against full revaluation for a spot/vol/time/rate move.

    ``dS`` is an absolute price move (not a percentage) applied uniformly;
    internally this is converted to the equivalent
    :class:`options_risk.stress.scenario.Scenario` (as a percentage of each
    position's own spot) for the full-revaluation comparison, which is only
    exact when every position shares the same base spot (single-underlying
    assumption, as documented above).
    """
    base_greeks = portfolio.greeks()
    base_spots = {p.S for p in portfolio.options()} | {p.price for p in portfolio.equities()}
    if len(base_spots) > 1:
        raise ValueError(
            "explain_pnl assumes a single-underlying portfolio (all positions share one "
            f"base spot); found multiple base spots: {sorted(base_spots)}"
        )
    S0 = next(iter(base_spots)) if base_spots else None
    spot_shock_pct = (dS / S0) if S0 else 0.0

    scenario = Scenario(
        name="pnl_explain",
        spot_shock_pct=spot_shock_pct,
        vol_shock_abs=dSigma,
        rate_shock_abs=dr,
        time_decay_years=dt,
    )
    full_reval = revalue_portfolio(portfolio, scenario)

    components = taylor_pnl(base_greeks, dS, dSigma, dt, dr)
    explained = sum(components.values())
    actual = full_reval.pnl

    return PnLAttribution(
        **components,
        explained_pnl=explained,
        actual_pnl=actual,
        residual=actual - explained,
    )
