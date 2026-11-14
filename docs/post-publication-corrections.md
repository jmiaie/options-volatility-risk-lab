# Post-publication corrections and known limitations (2026-11-14)

This note records corrections to statements in the historical-study write-up
(`publication/options-risk-study/`). The frozen pack, its result files and its hashes are
**unchanged**: nothing was re-run or regenerated. Where the pack text and this note disagree, this
note is the current position. Every number below is recomputed from the committed result files
`results/historical_risk/options_hist_risk_v2_*.json` (field `episodes`, one row per initiation date).

## 1. "Persistently low-biased" realised volatility: not supported

The technical paper (§2.1 and the limitations list) says trailing-20-session realised volatility is
"a persistently low-biased estimate of the option's own realized vol over its life in all three
periods, and this bias grows by 2025".

The committed episodes do not support "persistently" or "biased":

| Period | Episodes | Mean (realised − assumed) | Median | t-statistic | Share positive |
|---|---|---|---|---|---|
| Development | 106 | +0.0051 | −0.0023 | 0.45 | 47% |
| Validation 2024 | 12 | +0.0073 | −0.0023 | 0.53 | 50% |
| Evaluation 2025 | 11 | +0.0169 | +0.0078 | 0.32 | 55% |

The means are positive because a few large-volatility episodes pull them up (right skew). The
medians are near zero and about half the episodes are negative. The mean differences are not
statistically distinguishable from zero in any period.

**Corrected statement:** the assumed volatility was close to unbiased on average; a small number of
episodes with much higher realised volatility dominate the mean. The 2025 sample (11 episodes) is too
small to say the gap grew.

## 2. Hedging-error increase in 2025: about half is the price level

The paper reports mean absolute replication error in dollars per share. SPY's average price at
initiation rose from about 285 (development) to about 602 (2025), so dollar errors are not comparable
across periods.

| Period (daily rebalancing, base costs) | Mean abs. error ($) | Median ($) | Mean error ÷ price |
|---|---|---|---|
| Development | 1.877 | 1.199 | 0.69% |
| Validation 2024 | 2.110 | 1.032 | 0.40% |
| Evaluation 2025 | 6.646 | 3.290 | 1.14% |

In dollars the 2025 mean is 3.5 times the development mean. As a share of price it is 1.7 times.
About 2.1× of the dollar increase is the price level. The 2025 mean is also about twice its median,
so a few episodes drive it.

**Corrected statement:** relative to price, 2025 mean hedging error was about 1.7 times the
development level, on 11 episodes.

## 3. What the VaR backtest tests

The one-day backtest revalues the option book under the next session's **spot move only**
(`src/options_risk/historical_risk_study_v2.py`, the `Scenario(name="next_day", spot_shock_pct=...)`
step). Implied volatility and time decay are held fixed. It is therefore a test of how well each
method forecasts the spot-driven loss of the book, not a test of a full option-risk model.

The three VaR methods are also not fully independent: Delta-Normal and Monte Carlo use the same
normal distribution and the same 20-session volatility estimate. Historical simulation is the only
method with a different distributional input.

## 4. Known code limitations (not fixed here, to keep cited line numbers stable)

- `breaches_from_losses` (`src/options_risk/risk/backtesting.py`) compares with `>`, so a NaN loss
  or NaN VaR is counted as "no breach" instead of raising. `compute_var_es`
  (`src/options_risk/risk/var.py`) returns NaN for NaN input without an error. The committed study
  inputs contain no NaN values, so the published numbers are not affected.
- The internal attribute `staleness_sessions` (`historical_risk_study_v2.py`) holds **calendar
  days**, not sessions. The result files label it correctly as `rate_staleness_days`; only the
  attribute name is misleading.
- Power: with 12 forecasts a year, the Kupiec test detects only large miscalibration. A power
  study quantifies this (see the open pull request "power / null-calibration study for the VaR
  backtests").

## 5. Data sources and citation

- SPY daily prices: Yahoo Finance, retrieved with `yfinance`. Raw files are not redistributed; the
  repository holds hashes and manifests. Result files do contain individual initiation-date closing
  prices (`S0`).
- VIX: Chicago Board Options Exchange, CBOE Volatility Index: VIX [VIXCLS], retrieved from FRED,
  Federal Reserve Bank of St. Louis; https://fred.stlouisfed.org/series/VIXCLS. Copyright Cboe;
  FRED marks this series "Copyrighted: Citation Required".
- 3-month Treasury rate: Board of Governors of the Federal Reserve System (US), Market Yield on
  U.S. Treasury Securities at 3-Month Constant Maturity [DGS3MO], retrieved from FRED.
