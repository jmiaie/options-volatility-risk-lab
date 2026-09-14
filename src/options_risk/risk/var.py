"""Value-at-Risk and Expected Shortfall.

**Loss/sign convention** (used consistently by every VaR/ES function in this
module): ``loss = -(P&L)``, so a positive number is an adverse outcome. At
confidence level ``alpha`` (e.g. 0.95),

* ``VaR_alpha`` is the ``alpha``-quantile of the loss distribution — a
  positive VaR of $X means losses exceed $X with probability ``1-alpha``.
* ``ES_alpha`` (Expected Shortfall / CVaR) is the conditional mean loss
  *given* the loss exceeds ``VaR_alpha`` — the average size of the tail
  losses VaR itself is silent about.

Three models are implemented, each with a different, deliberately
transparent set of assumptions:

1. :func:`historical_simulation_var` — full revaluation of the actual
   portfolio (via :mod:`options_risk.stress.scenario`) under each
   historically-observed return, so a nonlinear option book is genuinely
   repriced under each scenario rather than approximated by a linear
   return. Uses only a rolling window of *past* returns — see the
   ``as_of``/window handling in :mod:`options_risk.risk.backtesting` for
   how this is kept point-in-time in a backtest.
2. :func:`delta_normal_var` — a deliberately simplistic linear/parametric
   baseline: it assumes portfolio P&L is a linear function of normally
   distributed factor returns (``dollar_delta @ returns``), entirely
   ignoring Gamma/convexity. It is included specifically to demonstrate its
   limitation for option-heavy portfolios (see
   ``research/portfolio-tail-risk.md``), not as a recommended model.
3. :func:`monte_carlo_var` — simulates a single risk factor's returns from
   a normal distribution with a configurable mean/vol/horizon/sample count
   and seed, then **full-revalues** the portfolio under each simulated
   return (like historical simulation, but with a parametric return model
   instead of empirical history).

All three report VaR **and** ES **and** a small loss-distribution summary —
never a bare VaR number — because a single quantile without its tail
context is exactly the kind of "model output presented as guarantee" this
project's brief warns against. VaR is a modeled quantile of a modeled loss
distribution, not a promise about the worst that can happen.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import norm

from options_risk.portfolio.portfolio import Portfolio
from options_risk.stress.scenario import Scenario, revalue_portfolio


@dataclass(frozen=True)
class LossDistributionSummary:
    confidence_level: float
    horizon: int
    n_obs: int
    var: float
    es: float
    mean_loss: float
    std_loss: float
    min_loss: float
    max_loss: float
    losses: np.ndarray

    def __repr__(self) -> str:  # keep the (potentially large) raw array out of default repr
        return (
            f"LossDistributionSummary(confidence_level={self.confidence_level}, "
            f"horizon={self.horizon}, n_obs={self.n_obs}, var={self.var:.4f}, "
            f"es={self.es:.4f}, mean_loss={self.mean_loss:.4f}, std_loss={self.std_loss:.4f})"
        )


def compute_var_es(losses: np.ndarray, confidence_level: float) -> tuple[float, float]:
    """VaR and ES from a raw sample of losses, under this module's sign convention."""
    if not (0 < confidence_level < 1):
        raise ValueError(f"confidence_level must be in (0, 1), got {confidence_level}")
    if len(losses) < 2:
        raise ValueError("need at least 2 loss observations to estimate VaR/ES")
    var = float(np.quantile(losses, confidence_level))
    tail = losses[losses >= var]
    es = float(tail.mean()) if len(tail) > 0 else var
    return var, es


def _summarize(
    losses: np.ndarray, confidence_level: float, horizon: int
) -> LossDistributionSummary:
    var, es = compute_var_es(losses, confidence_level)
    return LossDistributionSummary(
        confidence_level=confidence_level,
        horizon=horizon,
        n_obs=len(losses),
        var=var,
        es=es,
        mean_loss=float(losses.mean()),
        std_loss=float(losses.std(ddof=1)),
        min_loss=float(losses.min()),
        max_loss=float(losses.max()),
        losses=losses,
    )


def historical_simulation_var(
    portfolio: Portfolio,
    historical_returns: np.ndarray,
    *,
    confidence_level: float = 0.95,
    return_type: str = "log",
    horizon: int = 1,
) -> LossDistributionSummary:
    """Historical Simulation VaR/ES via full revaluation of the portfolio.

    ``historical_returns`` is a 1-D array of single-underlying returns
    (already at the desired ``horizon``'s frequency — this function does
    not resample). ``return_type`` is either ``"log"`` (``S_new = S *
    exp(r)``) or ``"arithmetic"`` (``S_new = S * (1 + r)``); this must
    match how ``historical_returns`` was computed upstream.
    """
    if return_type not in ("log", "arithmetic"):
        raise ValueError(f"return_type must be 'log' or 'arithmetic', got {return_type!r}")
    if len(historical_returns) < 2:
        raise ValueError("need at least 2 historical returns")

    losses = np.empty(len(historical_returns))
    for i, r in enumerate(historical_returns):
        spot_shock_pct = (np.exp(r) - 1.0) if return_type == "log" else r
        scenario = Scenario(name=f"hist_{i}", spot_shock_pct=float(spot_shock_pct))
        result = revalue_portfolio(portfolio, scenario)
        losses[i] = -result.pnl

    return _summarize(losses, confidence_level, horizon)


@dataclass(frozen=True)
class DeltaNormalVaRResult:
    confidence_level: float
    horizon: int
    var: float
    es: float
    portfolio_dollar_delta: float
    factor_vol: float
    pnl_std: float


def delta_normal_var(
    dollar_delta: float,
    factor_vol: float,
    *,
    confidence_level: float = 0.95,
    horizon: int = 1,
) -> DeltaNormalVaRResult:
    """Delta-Normal (parametric) VaR/ES: a deliberately simplistic linear baseline.

    Assumptions (stated explicitly, not hidden):

    * The portfolio's P&L over the horizon is approximated as
      ``dollar_delta * return``, i.e. **linear** in the underlying's return
      — no Gamma/convexity is modeled at all, so this will systematically
      mis-price tail risk for an option-heavy (convex) book.
    * The underlying's return is assumed **normally distributed** with
      volatility ``factor_vol`` (per one period) at zero mean, scaled to
      the horizon via ``sqrt(horizon)`` (the standard iid-normal-returns
      scaling assumption).
    * ``factor_vol`` is taken as given (e.g. an estimated covariance/vol
      from historical data) — estimation error and vol clustering are not
      modeled.

    Under these assumptions, P&L ~ Normal(0, (dollar_delta * factor_vol *
    sqrt(horizon))^2), and VaR/ES have closed forms for the normal
    distribution (no simulation needed).
    """
    if not (0 < confidence_level < 1):
        raise ValueError(f"confidence_level must be in (0, 1), got {confidence_level}")
    pnl_std = abs(dollar_delta) * factor_vol * np.sqrt(horizon)
    z = norm.ppf(confidence_level)
    var = float(z * pnl_std)
    es = float(pnl_std * norm.pdf(z) / (1 - confidence_level))
    return DeltaNormalVaRResult(
        confidence_level=confidence_level,
        horizon=horizon,
        var=var,
        es=es,
        portfolio_dollar_delta=dollar_delta,
        factor_vol=factor_vol,
        pnl_std=pnl_std,
    )


def monte_carlo_var(
    portfolio: Portfolio,
    mean_return: float,
    vol: float,
    *,
    n_sims: int = 50_000,
    horizon: int = 1,
    confidence_level: float = 0.95,
    seed: int | None = None,
) -> LossDistributionSummary:
    """Monte Carlo VaR/ES: simulate normal single-factor returns, full-revalue each draw.

    ``mean_return``/``vol`` are per-period; both are scaled to ``horizon``
    (mean by ``horizon``, vol by ``sqrt(horizon)``), matching the classic
    iid-normal-returns scaling convention. Every simulated return is
    applied to the actual portfolio via full revaluation (like
    :func:`historical_simulation_var`, but with simulated rather than
    historical returns), so option convexity is captured, not linearized.
    """
    if n_sims < 2:
        raise ValueError(f"n_sims must be >= 2, got {n_sims}")
    rng = np.random.default_rng(seed)
    horizon_mean = mean_return * horizon
    horizon_vol = vol * np.sqrt(horizon)
    simulated_returns = rng.normal(horizon_mean, horizon_vol, size=n_sims)

    losses = np.empty(n_sims)
    for i, r in enumerate(simulated_returns):
        spot_shock_pct = float(np.exp(r) - 1.0)
        scenario = Scenario(name=f"mc_{i}", spot_shock_pct=spot_shock_pct)
        result = revalue_portfolio(portfolio, scenario)
        losses[i] = -result.pnl

    return _summarize(losses, confidence_level, horizon)
