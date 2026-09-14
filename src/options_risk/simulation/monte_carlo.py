"""Monte Carlo pricing for European options under risk-neutral GBM.

Model: ``dS/S = (r - q) dt + sigma dW`` under the risk-neutral measure, so
the discounted price process is a martingale and simulated paths can be
priced by discounting the average simulated payoff. The log-price update
used here (``log S_{t+dt} = log S_t + (r - q - sigma^2/2) dt + sigma
sqrt(dt) Z``) is the *exact* transition density of GBM, not an Euler
approximation — so increasing ``n_steps`` reduces nothing for a European
payoff (which depends only on ``S_T``); ``n_steps`` is exposed for
path-shape realism and reuse by path-dependent tools (e.g. the hedging
simulator), not because it changes the terminal-price bias.

Variance reduction:

* **Antithetic variates** (default on): each standard-normal draw ``Z`` is
  paired with ``-Z``. The pair-averaged payoff is used as the unit of
  resampling for the standard error, which is what actually captures the
  variance reduction (treating all raw paths as independent would
  understate how correlated the antithetic pairs are).
* **Control variate** (default on): the discounted terminal stock price
  ``exp(-rT) * S_T`` has a known risk-neutral mean, ``S * exp(-qT)``. The
  simulated payoff is adjusted by the sample-estimated optimal coefficient
  ``beta = Cov(payoff, S_T) / Var(S_T)`` against that control, which
  removes the part of the payoff's variance explained by moves in the
  underlying itself.

The result always reports a standard error and a confidence interval —
never a bare point estimate — because a Monte Carlo price without
uncertainty is not a claim this library will make.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import norm

from options_risk.pricing.black_scholes import (
    OptionType,
    _validate_common,
    _validate_option_type,
    intrinsic_value,
)


@dataclass(frozen=True)
class MonteCarloResult:
    price: float
    standard_error: float
    ci_low: float
    ci_high: float
    confidence_level: float
    n_paths: int
    n_steps: int
    seed: int | None
    antithetic: bool
    control_variate: bool


def simulate_terminal_gbm(
    S: float,
    T: float,
    r: float,
    sigma: float,
    q: float,
    n_paths: int,
    n_steps: int,
    seed: int | None,
    antithetic: bool,
) -> np.ndarray:
    """Simulate terminal underlying prices S_T under risk-neutral GBM.

    Returns an array of length ``n_paths`` (or the next even number, when
    ``antithetic=True`` and ``n_paths`` is odd, since antithetic pairs come
    in twos).
    """
    rng = np.random.default_rng(seed)
    dt = T / n_steps
    drift = (r - q - 0.5 * sigma**2) * dt
    vol = sigma * np.sqrt(dt)

    if antithetic:
        n_pairs = (n_paths + 1) // 2
        z = rng.standard_normal((n_pairs, n_steps))
        z = np.concatenate([z, -z], axis=0)
    else:
        z = rng.standard_normal((n_paths, n_steps))

    log_increments = drift + vol * z
    cumulative_log_return = np.cumsum(log_increments, axis=1)[:, -1]
    return S * np.exp(cumulative_log_return)


def mc_european_price(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: OptionType,
    q: float = 0.0,
    *,
    n_paths: int = 100_000,
    n_steps: int = 1,
    seed: int | None = None,
    antithetic: bool = True,
    control_variate: bool = True,
    confidence_level: float = 0.95,
) -> MonteCarloResult:
    """Price a European option by Monte Carlo simulation of risk-neutral GBM.

    Always reports a standard error and a ``confidence_level`` confidence
    interval alongside the point estimate. At ``T == 0`` the payoff is
    deterministic (intrinsic value), so SE is reported as exactly 0.
    """
    _validate_common(S, K, T, sigma)
    _validate_option_type(option_type)
    if n_paths < 2:
        raise ValueError(f"n_paths must be >= 2, got {n_paths}")
    if n_steps < 1:
        raise ValueError(f"n_steps must be >= 1, got {n_steps}")

    if T == 0:
        value = intrinsic_value(S, K, option_type)
        return MonteCarloResult(
            price=value,
            standard_error=0.0,
            ci_low=value,
            ci_high=value,
            confidence_level=confidence_level,
            n_paths=n_paths,
            n_steps=n_steps,
            seed=seed,
            antithetic=antithetic,
            control_variate=control_variate,
        )

    S_T = simulate_terminal_gbm(S, T, r, sigma, q, n_paths, n_steps, seed, antithetic)
    payoff = np.maximum(S_T - K, 0.0) if option_type == "call" else np.maximum(K - S_T, 0.0)
    discounted_payoff = np.exp(-r * T) * payoff

    if antithetic:
        # Resample at the pair level: this is the unit that is actually
        # independent, and is what correctly reflects the variance reduction.
        n_pairs = discounted_payoff.shape[0] // 2
        estimator_sample = 0.5 * (discounted_payoff[:n_pairs] + discounted_payoff[n_pairs:])
        control_full = np.exp(-r * T) * S_T
        control_sample = 0.5 * (control_full[:n_pairs] + control_full[n_pairs:])
    else:
        estimator_sample = discounted_payoff
        control_sample = np.exp(-r * T) * S_T

    if control_variate and estimator_sample.shape[0] > 1:
        control_mean = S * np.exp(-q * T)
        cov_matrix = np.cov(estimator_sample, control_sample, ddof=1)
        control_var = cov_matrix[1, 1]
        beta = cov_matrix[0, 1] / control_var if control_var > 0 else 0.0
        estimator_sample = estimator_sample - beta * (control_sample - control_mean)

    n_eff = estimator_sample.shape[0]
    price = float(estimator_sample.mean())
    standard_error = float(estimator_sample.std(ddof=1) / np.sqrt(n_eff)) if n_eff > 1 else 0.0
    z = float(norm.ppf(0.5 + confidence_level / 2))
    ci_low = price - z * standard_error
    ci_high = price + z * standard_error

    return MonteCarloResult(
        price=price,
        standard_error=standard_error,
        ci_low=ci_low,
        ci_high=ci_high,
        confidence_level=confidence_level,
        n_paths=S_T.shape[0],
        n_steps=n_steps,
        seed=seed,
        antithetic=antithetic,
        control_variate=control_variate,
    )
