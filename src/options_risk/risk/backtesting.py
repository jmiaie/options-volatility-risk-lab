"""VaR backtesting: Kupiec proportion-of-failures and Christoffersen independence tests.

A VaR "breach" (a.k.a. exceedance/violation) is a period where the
realized loss exceeded the VaR forecast for that period, using the same
loss-sign convention as :mod:`options_risk.risk.var` (``loss = -(P&L)``).
For a correctly calibrated VaR model at confidence level ``alpha``, breaches
should occur independently with probability ``1 - alpha``.

Two tests are implemented:

* **Kupiec (1995) Proportion-of-Failures (POF) test** — a likelihood-ratio
  test of whether the *observed breach rate* matches the *expected* rate
  ``1 - alpha``. Tests only the unconditional frequency, not clustering.
* **Christoffersen (1998) independence test** — a likelihood-ratio test of
  whether breaches are *independent* over time (a good model should not
  have breaches cluster, e.g. several in a row during a crisis) — this is
  the complement to Kupiec, which cannot detect clustering at all (a model
  with exactly the right unconditional breach rate but all its breaches
  clustered in one crisis month would pass Kupiec and fail Christoffersen).
* Their sum, the **Conditional Coverage test**, is exposed too.

None of these tests "declares a model valid" from a single p-value — the
result carries the sample size and a plain-language caveat, because with
the sample sizes typical of a VaR backtest (a year or two of daily
observations, a few dozen breaches at most for a 99% VaR), these tests have
low power: failing to reject is weak evidence of correctness, not proof.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import chi2

_MIN_OBS_FOR_RELIABLE_TEST = 250  # roughly one trading year of daily observations


@dataclass(frozen=True)
class BacktestResult:
    test_name: str
    n_obs: int
    n_breaches: int
    expected_breaches: float
    breach_rate: float
    expected_breach_rate: float
    lr_statistic: float
    degrees_of_freedom: int
    p_value: float
    significance_level: float
    reject_null: bool
    conclusion: str
    sample_size_caveat: str


def _sample_size_caveat(n_obs: int) -> str:
    if n_obs < _MIN_OBS_FOR_RELIABLE_TEST:
        return (
            f"n_obs={n_obs} is below the ~{_MIN_OBS_FOR_RELIABLE_TEST}-observation "
            "(roughly one trading year) rule of thumb for reasonable test power; "
            "failing to reject the null here is weak evidence, not proof of a correct model."
        )
    return (
        f"n_obs={n_obs} observations: even at this sample size, VaR backtests have limited "
        "power to detect small calibration errors — treat any conclusion as provisional."
    )


def breaches_from_losses(losses: np.ndarray, var: np.ndarray | float) -> np.ndarray:
    """Boolean breach indicator: loss_t > VaR_t (VaR may be a scalar or a per-period array)."""
    return np.asarray(losses) > np.asarray(var)


def kupiec_pof_test(
    breaches: np.ndarray,
    confidence_level: float,
    *,
    significance_level: float = 0.05,
) -> BacktestResult:
    """Kupiec (1995) unconditional-coverage (proportion-of-failures) likelihood-ratio test.

    Null hypothesis: the true breach probability equals ``1 - confidence_level``.
    """
    breaches = np.asarray(breaches, dtype=bool)
    n = len(breaches)
    if n == 0:
        raise ValueError("need at least 1 observation")
    x = int(breaches.sum())
    p_expected = 1 - confidence_level
    p_observed = x / n

    def _binom_log_lik(p: float) -> float:
        # x*log(p) + (n-x)*log(1-p), with the 0*log(0) := 0 convention.
        term_x = x * np.log(p) if x > 0 else 0.0
        term_n_minus_x = (n - x) * np.log(1 - p) if x < n else 0.0
        return term_x + term_n_minus_x

    log_lik_null = _binom_log_lik(p_expected)
    log_lik_unrestricted = _binom_log_lik(p_observed)

    lr = -2 * (log_lik_null - log_lik_unrestricted)
    lr = max(lr, 0.0)  # guard against tiny negative values from floating-point cancellation
    p_value = float(1 - chi2.cdf(lr, df=1))
    reject = p_value < significance_level

    conclusion = (
        f"Reject H0 (breach rate {p_observed:.4f} inconsistent with expected "
        f"{p_expected:.4f}) at the {significance_level:.0%} level."
        if reject
        else (
            f"Fail to reject H0: observed breach rate {p_observed:.4f} is not "
            f"statistically distinguishable from the expected {p_expected:.4f} "
            f"at the {significance_level:.0%} level."
        )
    )

    return BacktestResult(
        test_name="Kupiec POF",
        n_obs=n,
        n_breaches=x,
        expected_breaches=p_expected * n,
        breach_rate=p_observed,
        expected_breach_rate=p_expected,
        lr_statistic=float(lr),
        degrees_of_freedom=1,
        p_value=p_value,
        significance_level=significance_level,
        reject_null=reject,
        conclusion=conclusion,
        sample_size_caveat=_sample_size_caveat(n),
    )


def christoffersen_independence_test(
    breaches: np.ndarray,
    confidence_level: float,
    *,
    significance_level: float = 0.05,
) -> BacktestResult:
    """Christoffersen (1998) test of independence of breaches (no clustering).

    Models breaches as a two-state Markov chain and tests whether the
    transition probabilities ``P(breach | breach)`` and
    ``P(breach | no breach)`` are equal (independence) via a likelihood-
    ratio test against the unrestricted (empirical transition-matrix)
    likelihood.
    """
    breaches = np.asarray(breaches, dtype=bool).astype(int)
    n = len(breaches)
    if n < 2:
        raise ValueError("need at least 2 observations to test transitions")

    n00 = int(np.sum((breaches[:-1] == 0) & (breaches[1:] == 0)))
    n01 = int(np.sum((breaches[:-1] == 0) & (breaches[1:] == 1)))
    n10 = int(np.sum((breaches[:-1] == 1) & (breaches[1:] == 0)))
    n11 = int(np.sum((breaches[:-1] == 1) & (breaches[1:] == 1)))

    n0, n1 = n00 + n01, n10 + n11
    pi01 = n01 / n0 if n0 > 0 else 0.0
    pi11 = n11 / n1 if n1 > 0 else 0.0
    pi = (n01 + n11) / (n0 + n1) if (n0 + n1) > 0 else 0.0

    def _log_lik_term(p: float, successes: int, trials: int) -> float:
        if trials == 0:
            return 0.0
        if p <= 0:
            return 0.0 if successes == 0 else -np.inf
        if p >= 1:
            return 0.0 if successes == trials else -np.inf
        return successes * np.log(p) + (trials - successes) * np.log(1 - p)

    log_lik_restricted = _log_lik_term(pi, n01, n0) + _log_lik_term(pi, n11, n1)
    log_lik_unrestricted = _log_lik_term(pi01, n01, n0) + _log_lik_term(pi11, n11, n1)

    lr = -2 * (log_lik_restricted - log_lik_unrestricted)
    lr = max(lr, 0.0) if np.isfinite(lr) else 0.0
    p_value = float(1 - chi2.cdf(lr, df=1))
    reject = p_value < significance_level

    conclusion = (
        f"Reject H0 of independent breaches (pi01={pi01:.4f} vs pi11={pi11:.4f} differ "
        f"significantly) at the {significance_level:.0%} level -> breaches appear to cluster."
        if reject
        else (
            f"Fail to reject H0: no statistically significant clustering detected "
            f"(pi01={pi01:.4f}, pi11={pi11:.4f}) at the {significance_level:.0%} level."
        )
    )

    return BacktestResult(
        test_name="Christoffersen independence",
        n_obs=n,
        n_breaches=int(breaches.sum()),
        expected_breaches=(1 - confidence_level) * n,
        breach_rate=float(breaches.mean()),
        expected_breach_rate=1 - confidence_level,
        lr_statistic=float(lr),
        degrees_of_freedom=1,
        p_value=p_value,
        significance_level=significance_level,
        reject_null=reject,
        conclusion=conclusion,
        sample_size_caveat=_sample_size_caveat(n),
    )


def conditional_coverage_test(
    breaches: np.ndarray,
    confidence_level: float,
    *,
    significance_level: float = 0.05,
) -> BacktestResult:
    """Conditional coverage test: Kupiec LR + Christoffersen LR, chi2 with 2 df.

    Jointly tests correct unconditional breach frequency *and* independence.
    """
    pof = kupiec_pof_test(breaches, confidence_level, significance_level=significance_level)
    indep = christoffersen_independence_test(
        breaches, confidence_level, significance_level=significance_level
    )
    lr = pof.lr_statistic + indep.lr_statistic
    p_value = float(1 - chi2.cdf(lr, df=2))
    reject = p_value < significance_level

    conclusion = (
        f"Reject H0 of correct conditional coverage at the {significance_level:.0%} level "
        "(model fails on frequency and/or independence)."
        if reject
        else (
            f"Fail to reject H0: no statistically significant evidence against correct "
            f"conditional coverage at the {significance_level:.0%} level."
        )
    )

    return BacktestResult(
        test_name="Conditional coverage (Kupiec + Christoffersen)",
        n_obs=pof.n_obs,
        n_breaches=pof.n_breaches,
        expected_breaches=pof.expected_breaches,
        breach_rate=pof.breach_rate,
        expected_breach_rate=pof.expected_breach_rate,
        lr_statistic=float(lr),
        degrees_of_freedom=2,
        p_value=p_value,
        significance_level=significance_level,
        reject_null=reject,
        conclusion=conclusion,
        sample_size_caveat=_sample_size_caveat(pof.n_obs),
    )
