from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import chi2, norm

from .portfolio import MarketState, Portfolio


@dataclass(frozen=True)
class RiskSummary:
    confidence_level: float
    var: float
    expected_shortfall: float


@dataclass(frozen=True)
class DeltaNormalVaRResult:
    confidence_level: float
    var: float
    expected_shortfall: float
    portfolio_standard_deviation: float


@dataclass(frozen=True)
class MonteCarloVaRResult:
    confidence_level: float
    var: float
    expected_shortfall: float
    losses: np.ndarray


@dataclass(frozen=True)
class KupiecResult:
    observed_exceedances: int
    expected_exceedance_rate: float
    likelihood_ratio: float
    p_value: float


@dataclass(frozen=True)
class StressScenario:
    name: str
    spot_return: float = 0.0
    vol_shift: float = 0.0
    rate_shift: float = 0.0
    time_shift: float = 0.0


def _losses_from_pnl(pnl: np.ndarray) -> np.ndarray:
    return -np.asarray(pnl, dtype=float)


def historical_var_es(pnl: np.ndarray, confidence_level: float = 0.99) -> RiskSummary:
    losses = _losses_from_pnl(pnl)
    var = float(np.quantile(losses, confidence_level, method="higher"))
    tail_losses = losses[losses >= var]
    expected_shortfall = float(np.mean(tail_losses))
    return RiskSummary(
        confidence_level=confidence_level, var=var, expected_shortfall=expected_shortfall
    )


def portfolio_historical_pnl(
    portfolio: Portfolio,
    market: MarketState,
    scenarios: pd.DataFrame,
) -> np.ndarray:
    required = {"spot_return", "vol_shift", "rate_shift"}
    missing = required.difference(scenarios.columns)
    if missing:
        raise ValueError(f"Missing required scenario columns: {sorted(missing)}")
    base_value = portfolio.value(market)
    pnl: list[float] = []
    for _, row in scenarios.iterrows():
        shocked_spot = market.spot * math.exp(float(row["spot_return"]))
        shocked = portfolio.value(
            market,
            spot_shift=shocked_spot - market.spot,
            vol_shift=float(row["vol_shift"]),
            rate_shift=float(row["rate_shift"]),
            time_shift=float(row.get("time_shift", 0.0)),
        )
        pnl.append(shocked - base_value)
    return np.asarray(pnl, dtype=float)


def delta_normal_var(
    portfolio: Portfolio,
    market: MarketState,
    covariance: np.ndarray,
    confidence_level: float = 0.99,
) -> DeltaNormalVaRResult:
    covariance = np.asarray(covariance, dtype=float)
    if covariance.shape != (3, 3):
        raise ValueError(
            "covariance must be a 3x3 matrix for [log_spot_return, vol_shift, rate_shift]"
        )
    greeks_map = portfolio.greeks(market)
    exposures = np.asarray(
        [
            greeks_map["delta"] * market.spot,
            greeks_map["vega"],
            greeks_map["rho"],
        ]
    )
    portfolio_std = float(math.sqrt(exposures @ covariance @ exposures))
    z = float(norm.ppf(confidence_level))
    var = z * portfolio_std
    expected_shortfall = portfolio_std * float(norm.pdf(z) / (1.0 - confidence_level))
    return DeltaNormalVaRResult(confidence_level, var, expected_shortfall, portfolio_std)


def monte_carlo_var_es(
    portfolio: Portfolio,
    market: MarketState,
    covariance: np.ndarray,
    *,
    confidence_level: float = 0.99,
    n_sims: int = 50_000,
    seed: int | None = None,
    antithetic: bool = True,
) -> MonteCarloVaRResult:
    covariance = np.asarray(covariance, dtype=float)
    if covariance.shape != (3, 3):
        raise ValueError(
            "covariance must be a 3x3 matrix for [log_spot_return, vol_shift, rate_shift]"
        )
    rng = np.random.default_rng(seed)
    if antithetic:
        half = n_sims // 2
        draws = rng.multivariate_normal(np.zeros(3), covariance, size=half)
        draws = np.vstack([draws, -draws])
        if n_sims % 2 == 1:
            draws = np.vstack([draws, rng.multivariate_normal(np.zeros(3), covariance, size=1)])
    else:
        draws = rng.multivariate_normal(np.zeros(3), covariance, size=n_sims)
    base_value = portfolio.value(market)
    pnl = np.empty(draws.shape[0], dtype=float)
    for index, (spot_return, vol_shift, rate_shift) in enumerate(draws):
        shocked_spot = market.spot * math.exp(float(spot_return))
        shocked_value = portfolio.value(
            market,
            spot_shift=shocked_spot - market.spot,
            vol_shift=float(vol_shift),
            rate_shift=float(rate_shift),
        )
        pnl[index] = shocked_value - base_value
    summary = historical_var_es(pnl, confidence_level)
    return MonteCarloVaRResult(
        summary.confidence_level, summary.var, summary.expected_shortfall, -pnl
    )


def kupiec_pof_test(exceedances: np.ndarray, expected_exceedance_rate: float) -> KupiecResult:
    flags = np.asarray(exceedances, dtype=bool)
    n_obs = int(flags.size)
    n_exc = int(flags.sum())
    if n_obs == 0:
        raise ValueError("At least one exceedance observation is required")
    if not 0.0 < expected_exceedance_rate < 1.0:
        raise ValueError("expected_exceedance_rate must lie strictly between 0 and 1")
    observed_rate = n_exc / n_obs
    if n_exc == 0:
        log_observed = n_obs * math.log(1.0)
    elif n_exc == n_obs:
        log_observed = n_obs * math.log(1.0)
    else:
        log_observed = (n_obs - n_exc) * math.log(1.0 - observed_rate) + n_exc * math.log(
            observed_rate
        )
    log_expected = (n_obs - n_exc) * math.log(1.0 - expected_exceedance_rate) + n_exc * math.log(
        expected_exceedance_rate
    )
    likelihood_ratio = max(0.0, -2.0 * (log_expected - log_observed))
    p_value = float(1.0 - chi2.cdf(likelihood_ratio, df=1))
    return KupiecResult(n_exc, expected_exceedance_rate, likelihood_ratio, p_value)


def stress_test(
    portfolio: Portfolio, market: MarketState, scenarios: list[StressScenario]
) -> pd.DataFrame:
    base_value = portfolio.value(market)
    rows: list[dict[str, float | str]] = []
    for scenario in scenarios:
        shocked_spot = market.spot * math.exp(scenario.spot_return)
        shocked_value = portfolio.value(
            market,
            spot_shift=shocked_spot - market.spot,
            vol_shift=scenario.vol_shift,
            rate_shift=scenario.rate_shift,
            time_shift=scenario.time_shift,
        )
        rows.append(
            {
                "scenario": scenario.name,
                "repriced_value": shocked_value,
                "pnl": shocked_value - base_value,
                "spot_return": scenario.spot_return,
                "vol_shift": scenario.vol_shift,
                "rate_shift": scenario.rate_shift,
                "time_shift": scenario.time_shift,
            }
        )
    return pd.DataFrame(rows)
