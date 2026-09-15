"""Full-revaluation scenario engine.

A :class:`Scenario` describes a shock to market risk factors. Applying it
to a portfolio **reprices every position from scratch** with the actual
Black-Scholes pricing model under the shocked inputs (full revaluation) —
this is deliberately distinct from, and always compared against, the
Greek-based (Taylor) approximation in
:mod:`options_risk.attribution.pnl_explain`, since the whole point of this
module is to show where the linear/quadratic approximation breaks down for
convex option payoffs.

Shock semantics (applied uniformly to every position — this engine assumes
a single-underlying book; a portfolio spanning multiple underlyings would
need the shock applied per-symbol, which is out of scope here and
documented as a limitation):

* ``spot_shock_pct``: fractional change to every position's spot, e.g.
  ``-0.10`` for a 10% decline.
* ``vol_shock_abs``: additive change to every option's volatility, in vol
  points (decimal), e.g. ``0.05`` for +5 vol points.
* ``vol_shock_mult``: multiplicative change to every option's volatility,
  applied before the additive shock (``sigma_new = sigma * mult + abs``),
  e.g. ``2.0`` to double vol.
* ``rate_shock_abs``: additive change to the continuously-compounded rate,
  e.g. ``0.01`` for +100bps.
* ``time_decay_years``: amount of time assumed to pass (shrinks each
  option's T, floored at 0 -> intrinsic value).
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

from options_risk.portfolio.portfolio import AnyPosition, Portfolio, PortfolioGreeks
from options_risk.portfolio.positions import CashPosition, EquityPosition, OptionPosition


@dataclass(frozen=True)
class Scenario:
    name: str
    spot_shock_pct: float = 0.0
    vol_shock_abs: float = 0.0
    vol_shock_mult: float = 1.0
    rate_shock_abs: float = 0.0
    time_decay_years: float = 0.0


def apply_scenario_to_position(position: AnyPosition, scenario: Scenario) -> AnyPosition:
    """Return a new position reflecting the scenario's shocks (full reprice inputs)."""
    if isinstance(position, EquityPosition):
        return dataclasses.replace(position, price=position.price * (1 + scenario.spot_shock_pct))
    if isinstance(position, OptionPosition):
        new_sigma = max(position.sigma * scenario.vol_shock_mult + scenario.vol_shock_abs, 0.0)
        new_T = max(position.T - scenario.time_decay_years, 0.0)
        return dataclasses.replace(
            position,
            S=position.S * (1 + scenario.spot_shock_pct),
            sigma=new_sigma,
            r=position.r + scenario.rate_shock_abs,
            T=new_T,
        )
    if isinstance(position, CashPosition):
        return position
    raise TypeError(f"unsupported position type: {type(position)!r}")


def apply_scenario(portfolio: Portfolio, scenario: Scenario) -> Portfolio:
    """Return a new, fully-repriced :class:`Portfolio` under the given scenario."""
    shocked = [apply_scenario_to_position(p, scenario) for p in portfolio.positions]
    return Portfolio(positions=shocked)


@dataclass(frozen=True)
class ScenarioResult:
    scenario: Scenario
    mv_before: float
    mv_after: float
    greeks_before: PortfolioGreeks
    greeks_after: PortfolioGreeks

    @property
    def pnl(self) -> float:
        return self.mv_after - self.mv_before

    @property
    def pnl_pct(self) -> float:
        return self.pnl / self.mv_before if self.mv_before != 0 else float("nan")


def revalue_portfolio(portfolio: Portfolio, scenario: Scenario) -> ScenarioResult:
    """Full-revaluation P&L and Greek changes for a portfolio under a scenario."""
    shocked = apply_scenario(portfolio, scenario)
    return ScenarioResult(
        scenario=scenario,
        mv_before=portfolio.market_value(),
        mv_after=shocked.market_value(),
        greeks_before=portfolio.greeks(),
        greeks_after=shocked.greeks(),
    )


STANDARD_STRESS_SCENARIOS: tuple[Scenario, ...] = (
    Scenario(name="equity -5%", spot_shock_pct=-0.05),
    Scenario(name="equity -10%", spot_shock_pct=-0.10),
    Scenario(name="equity -20%", spot_shock_pct=-0.20),
    Scenario(name="equity +5%", spot_shock_pct=0.05),
    Scenario(name="equity +10%", spot_shock_pct=0.10),
    Scenario(name="vol +5pts", vol_shock_abs=0.05),
    Scenario(name="vol +10pts", vol_shock_abs=0.10),
    Scenario(name="vol doubling", vol_shock_mult=2.0),
    Scenario(name="rates +100bps", rate_shock_abs=0.01),
    Scenario(name="rates -100bps", rate_shock_abs=-0.01),
    Scenario(name="crash + vol spike", spot_shock_pct=-0.20, vol_shock_abs=0.10),
)


def run_standard_stress_suite(
    portfolio: Portfolio, scenarios: tuple[Scenario, ...] = STANDARD_STRESS_SCENARIOS
) -> list[ScenarioResult]:
    """Run every scenario in ``scenarios`` (default: the standard stress suite) via full reval."""
    return [revalue_portfolio(portfolio, s) for s in scenarios]


def spot_vol_matrix(
    portfolio: Portfolio,
    spot_shocks_pct: tuple[float, ...] = (-0.20, -0.10, -0.05, 0.0, 0.05, 0.10, 0.20),
    vol_shocks_abs: tuple[float, ...] = (-0.10, -0.05, 0.0, 0.05, 0.10),
) -> list[ScenarioResult]:
    """Full-revaluation P&L across a grid of joint spot x vol shocks.

    This is the convexity demonstration: for an option-heavy book, P&L
    across this grid is visibly nonlinear in spot (curvature from Gamma)
    and cross-coupled with vol (Vega), which a single-point Greek summary
    cannot show.
    """
    return [
        revalue_portfolio(
            portfolio,
            Scenario(
                name=f"S{spot_pct:+.0%}/V{vol_abs:+.2f}",
                spot_shock_pct=spot_pct,
                vol_shock_abs=vol_abs,
            ),
        )
        for spot_pct in spot_shocks_pct
        for vol_abs in vol_shocks_abs
    ]
