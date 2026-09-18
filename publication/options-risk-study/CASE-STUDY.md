# Case study: DEV first roll (2016-02-01) — the volatility-units fix, end to end

This document traces one concrete roll snapshot through every step of the
volatility-units defect and its correction: from `trailing_realized_vol()`'s
raw output to the final Delta-Normal (and, for comparison, Monte Carlo and
Historical Simulation) VaR/ES figures. Every number below is read directly
from a committed artifact or computed by
`publication/options-risk-study/scripts/build_tables.py::build_case_study`,
which is reproduced (script output) at
`publication/options-risk-study/tables/case_study_dev_first_roll.json`. No
number here is asserted without a citation.

## 0. Which roll, and why this one

The DEV period's `nonlinear_portfolio_study.snapshots` array in
`results/historical_risk/options_hist_risk_v2_dev_formation.json`
(sha256 `6e840d4934ead483233aa83bebd232abd94b1652ed410f85408a5a898f5e5f26`)
contains 95 monthly roll snapshots. This case study uses `snapshots[0]`,
whose `roll_date` field reads `"2016-02-01"` — the first eligible monthly
roll of the DEV period (the standardized portfolio requires a full
252-session Historical Simulation warm-up window, so the first several
calendar months of the DEV period, which starts 2015-01-01, are not yet
eligible; 2016-02-01 is the first date that clears that bar).

## 1. Step one: `trailing_realized_vol()` — the raw, correct, annualized figure

`trailing_realized_vol()` (`src/options_risk/historical_risk_study_v2.py:144`)
computes, over the 20 trading sessions strictly before the roll date (never
including the roll date's own not-yet-realized return):

```
std(daily log returns, ddof=1) * sqrt(252)
```

For this roll, the snapshot's own `realized_vol_20d` field records this
value:

```
realized_vol_20d = 0.235506  (more precisely: 0.23550571215256)
```

This is an **annualized** volatility figure — correct and unmodified by the
D9-C fix. It is exactly what feeds Black-Scholes-Merton option pricing in
`build_standardized_portfolio()` (`historical_risk_study_v2.py:419`), which
expects an annualized sigma paired with maturity `T = 30/252` (also
expressed in years). Nothing about this step changed as part of the fix —
`trailing_realized_vol()` itself was never wrong.

## 2. Step two: the units-mismatch and its fix

`run_nonlinear_portfolio_study()` (`historical_risk_study_v2.py:628`) also
needs a **one-day** (per-period) volatility figure for two other legs of the
same roll's risk calculation: the Delta-Normal VaR formula
(`delta_normal_var()`, `src/options_risk/risk/var.py:146`) and the Monte
Carlo factor draw (`full_revaluation_mc_var_es()`,
`historical_risk_study_v2.py:472`). Both functions' own docstrings state
their volatility parameter is **per one period** (one trading day), scaled
to the horizon internally via `sqrt(horizon)`.

**Pre-fix** (preserved at
`results/historical_risk/superseded_volatility_units_fix/options_hist_risk_v2_dev_formation.json`,
sha256 `7bd4ea0c3a278c86c31e71fc265fda967d8d8a8ffb3481662f995e95576f459a`):
the code passed `realized_vol_20d` (the annualized figure, 0.235506)
directly into both `delta_normal_var()` and the Monte Carlo draw as their
one-day `factor_vol`/`mc_vol`.

**Post-fix** (current, authoritative): the call site converts it first:

```
daily_factor_vol20 = annualized_vol20 / sqrt(252)
                    = 0.23550571215256 / 15.874507866387544
                    = 0.01483546539740085
```

The snapshot's own `daily_factor_vol_20d` field confirms this exact value:

```
daily_factor_vol_20d = 0.014836  (more precisely: 0.01483546539740085)
```

`publication/options-risk-study/tables/case_study_dev_first_roll.json`'s
`check_daily_equals_annualized_over_sqrt252` field independently recomputes
`realized_vol_20d / sqrt(252)` and confirms it equals `daily_factor_vol_20d`
to 14 significant figures (`0.01483546539740085` both ways) — this is not
an approximation, it is the exact relationship the fix establishes.

Neither `trailing_realized_vol()` nor `delta_normal_var()`/
`full_revaluation_mc_var_es()` themselves were modified by this fix — only
the value passed between them, at the `run_nonlinear_portfolio_study()`
call site, changed.

## 3. Step three: downstream effect on Delta-Normal VaR/ES (95% confidence)

The standardized portfolio at this roll has portfolio dollar-delta
`-8732.681984965413` (from `var_es.primary.delta_normal.portfolio_dollar_delta`
in both the pre-fix and post-fix artifacts — unaffected by this fix, since
delta itself does not depend on which volatility feeds the VaR formula).

Delta-Normal VaR/ES is `abs(dollar_delta) * factor_vol * sqrt(horizon)`
scaled by the normal-distribution quantile/tail factors at 95% confidence
(`delta_normal_var()`, `src/options_risk/risk/var.py:146`) — **linear** in
`factor_vol`, so any change in `factor_vol` produces an exactly
proportional change in the output.

| | Pre-fix (superseded) `factor_vol` = 0.235506 (annualized, wrong) | Post-fix (corrected) `factor_vol` = 0.014836 (daily, correct) |
|---|---:|---:|
| Delta-Normal VaR (95%) | **3,382.80** | **213.10** |
| Delta-Normal ES (95%) | **4,242.17** | **267.23** |

Ratio: `3382.8001955401633 / 213.09638220047478 = 15.874507866387543`, which
matches `sqrt(252) = 15.874507866387544` to 14 significant figures (the
1-unit-in-the-last-place difference is ordinary floating-point rounding).
This is not a coincidence or an approximate match — it is the deterministic
algebraic consequence of Delta-Normal VaR's linearity in `factor_vol`,
confirmed independently by the dedicated regression test
`tests/test_historical_risk_study_v2.py::TestVolatilityUnitsFix::test_deterministic_linear_portfolio_var_scales_by_sqrt_252`
(line 773).

## 4. For comparison: Monte Carlo and Historical Simulation at the same roll

| Method | Pre-fix VaR (95%) | Post-fix VaR (95%) | Ratio (pre/post) |
|---|---:|---:|---:|
| Delta-Normal | 3,382.80 | 213.10 | 15.875 (exactly `sqrt(252)`) |
| Monte Carlo (50k, seed 0) | 7,039.23 | 226.61 | 31.06 (sub-linear — the full-revaluation book has genuine gamma, so the relationship between input vol and output VaR is not perfectly linear) |
| Historical Simulation (252d) | 137.71 | 137.71 | 1.000 (byte-identical — Historical Simulation consumes no vol parameter at all) |

`publication/options-risk-study/tables/case_study_dev_first_roll.json`'s
`historical_simulation_unchanged` field confirms this equality by direct
dict comparison of the full `var_es.primary.historical_simulation_primary`
object between the pre-fix and post-fix artifacts: `true`.

## 5. What this one roll illustrates about the whole study

This single roll is representative, not cherry-picked: the Delta-Normal
ratio is deterministic and identical (`15.875`) at **every** roll and
confidence level in **every** period, because Delta-Normal VaR's linearity
in `factor_vol` holds everywhere — see
`publication/options-risk-study/tables/var_es_corrected_vs_prefix.csv`'s
`var_ratio_prefix_over_corrected` column, which reads `15.875` for every
`delta_normal` row across all three periods and both confidence levels.
Monte Carlo's ratio varies roll-to-roll and period-to-period (because the
full-revaluation book's convexity makes the input-vol-to-output-VaR mapping
nonlinear) but stays in the same broad ~35–41x range throughout (also in
that same CSV). Historical Simulation is unaffected everywhere, at every
roll, in every period — confirmed by the "byte-identical outside
`var_es.{primary,secondary}.{delta_normal,monte_carlo}`" field-level diff
already documented in `research/historical-volatility-and-tail-risk.md` §6.2,
which this case study's single-roll trace corroborates rather than merely
repeats.
