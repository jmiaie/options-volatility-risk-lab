# Historical Volatility, Hedging Error, and Nonlinear Portfolio Tail Risk

### A Reproducible Study of Realized Paths, VaR Backtesting, and Full Revaluation

**Status**: AUTHORITATIVE (v2). Supersedes `options_historical_risk_study_v1.yaml` /
`historical_risk_study.py`, which Directive #9 itself labels **EXPLORATORY /
NON-CONFORMING TO FINAL D9-C SPEC** (wrong dataset IDs, no FRED integration,
GBM-simulated hedging instead of real historical-path replay, no standardized
nonlinear portfolio, no Monte Carlo VaR, a single confidence level, a single
HS lookback). v1's artifacts remain committed, unmodified, for audit trail;
none of its numbers are reused here.

**Config**: `configs/experiments/options_historical_risk_study_v2.yaml`
(`status: frozen-for-holdout`, frozen on creation — see "Freeze basis" below).
**Code**: `src/options_risk/historical_risk_study_v2.py`.
**Runner**: `scripts/run_historical_risk_study_v2.py`.
**Tests**: `tests/test_historical_risk_study_v2.py` (21 tests, all passing).
**Result artifacts**: `results/historical_risk/options_hist_risk_v2_{dev_formation,val_2024,historical_evaluation_2025}.json`.

Every number in this report is read directly from those three committed JSON
artifacts, reproducible by re-running:

```
python scripts/run_historical_risk_study_v2.py                    # DEV + 2024
python scripts/run_historical_risk_study_v2.py --skip-dev --skip-validation --allow-2025
```

## 1. Purpose and scope

This is **not** a historical options-trading alpha study. No paid options
tapes were used, and no option panel is invented: the underlying (SPY) is
the only real market series, and every option in this study is priced with
Black-Scholes-Merton off **realized volatility**, never a fabricated implied
volatility surface. The two questions this study actually answers, using
the exact methodology and required labels specified by Directive #9's D9-C
section:

1. **"Historical underlying-path hypothetical option hedging experiment"** —
   replaying real SPY daily closes through discrete delta-hedging mechanics:
   how large is the replication error of a textbook hedge against what
   actually happened, at daily vs. weekly rebalancing and across three
   transaction-cost regimes?
2. **"Hypothetical nonlinear portfolio evaluated on historical risk-factor
   paths"** — marking a standardized, convex/concave options book to real
   historical risk factors (SPY spot, DGS3MO short rate, realized vol) and
   backtesting three independent VaR methodologies against what actually
   happened next.

Both labels are used verbatim wherever these results are reported, per
spec. Neither construct is presented as an observed historical position or
trading strategy.

## 2. Datasets and point-in-time discipline

| Dataset ID | Source | Role | Status | `dataset_canonical` sha256 |
|---|---|---|---|---|
| `yf_spy_daily_2015_2025_v1` | Yahoo Finance, daily OHLCV | Underlying | DATA FROZEN | `0c83ab20bf76ec39b97855ac393b7bc74363bd4ff373381f0a92842a2c7c6a63` |
| `fred_dgs3mo_daily_2015_2025_v1` | FRED, 3-Month Treasury Bill Secondary Market Rate | Short rate proxy | DATA FROZEN | `31ad77f46517b4a51a2313ad86524d3f0f07634e4ca450ba2c387adbddf42a9f` |
| `fred_vixcls_daily_2015_2025_v1` | FRED, CBOE VIX Close | Vol context only | DATA FROZEN | `b727ab1751d4c9c180159cc1eb3358a2fef6ebf1abe15c74adb46f93019753b1` |

**Acquisition provenance (disclosed, not fabricated as fresh acquisition)**:
`yf_spy_daily_2015_2025_v1`'s raw bytes are **reused** from the sibling
Directive #9 repository (`Advanced_Algorithmic_Trading_Simulator_public`,
Stat-Arb D9-B), whose own SPY acquisition was already independently
verified there (sha256-matched, same source, same date range). This repo
did not freshly hit Yahoo Finance for SPY. Full disclosure is in
`data/manifests/yf_spy_daily_2015_2025_v1.json`'s `acquisition_provenance`
field. The two FRED series were repackaged from a provisional combined
snapshot (`fred_macro_daily_2015_2025_v1`) into these two authoritative,
per-series dataset IDs; the underlying bytes are unchanged from that prior
acquisition — only documentation (dataset IDs, and a corrected
`missing_value_representation` field, verified directly against the raw
CSV bytes via Python's `csv` module rather than copied from the prior
documentation) was corrected. Raw CSVs live in gitignored `data/raw/`, not
committed to this **public** repository — a deliberate scoping choice
distinct from committing raw vendor snapshots to a tracked path.

**Point-in-time rules, exactly as specified and as implemented**
(`point_in_time_value` in `historical_risk_study_v2.py`):

- **DGS3MO**: the latest observation known *at or before* the decision
  date — carry-forward only, **never future-backfilled**. Staleness (days
  since the last known observation) is recorded on every use. Labeled
  throughout as a **"short-term Treasury constant-maturity yield proxy,"**
  never as a full option discount curve.
- **VIXCLS**: used only as **market-volatility context** attached to each
  monthly snapshot (`vixcls_context`) — never as a pricing input, and never
  described as the exact implied volatility of the modeled SPY option.
- **Realized volatility**: close-to-close log-return standard deviation ×
  √252, computed causally (`trailing_realized_vol` excludes the decision
  day's own not-yet-realized return) — 20-session primary, 60-session
  secondary/sensitivity.

## 3. 2025 labeling discipline (Addendum 13)

Per Directive #9 Addendum 13: SPY's 2025 price history was **already
inspected** once under v1 (`options_hist_risk_v1_holdout_2025`, same
underlying series in substance). The 2025 result in this v2 study is
therefore labeled **`HISTORICAL EVALUATION`**, never `UNTOUCHED FINAL
HOLDOUT`. This study does not shift to 2026 to manufacture an untouched
window — 2026 is reserved program-wide and `no_2026_use_yet: true` is
enforced in the frozen config.

## 4. Freeze basis

This config's methodology (hedging mechanics, standardized portfolio
composition, VaR/ES methods, confidence levels, lookback windows, cost
scenarios) is taken directly from Directive #9's own D9-C spec text — none
of it was derived from, or tuned against, any observed result in this
repository. It was therefore frozen **on creation** (`frozen_for_holdout_utc:
2026-09-17T00:00:00Z` in the config's own `freeze_record`), rather than
staged through a separate development/validation freeze gate. No retune
after freeze; no universe change after dataset freeze; no CI network
fetch; no paid options tapes; no invented option panels.

## 5. Study 1 — Historical underlying-path hedging experiment

**Mechanics** (`simulate_delta_hedge_on_price_path`): a standardized,
short, one-lot, at-the-money 30-trading-day European call is delta-hedged
by replaying the *actual* subsequent 30 SPY daily closes — not a
GBM-simulated path. The hedge uses the same self-financing cash-account,
transaction-cost, and dividend-accrual mechanics as this codebase's
existing GBM-based hedge simulator, but is driven entirely by real
historical prices (deterministic given the path — no internal RNG). Pricing
volatility is the **trailing 20-session realized vol known before
initiation** (never called implied volatility). One episode initiates on
the first eligible session of every calendar month in each period; each
episode is run at **daily and weekly** rebalancing, crossed with **GROSS
(0bp) / BASE (1bp) / STRESS (5bp)** transaction-cost scenarios.

**Disclosed limitations, stated up front, not hidden**: consecutive
monthly episodes' 30-session windows overlap (a ~30-trading-day option
spans more than one calendar month), so cross-episode statistics below are
means over overlapping, serially dependent samples — no independence claim
is made. Dividend yield `q=0.0` is used uniformly; this engine does not
model discrete SPY dividend dates, so no dividend carry is modeled for any
of these results.

### 5.1 Episode counts

| Period | Episodes initiated | Skipped (insufficient warm-up/tail data) |
|---|---|---|
| DEV (2015-01-01 – 2023-12-31) | 108 | 2 |
| VAL (2024-01-01 – 2024-12-31) | 12 | 0 |
| 2025 HISTORICAL EVALUATION | 12 | 1 |

### 5.2 Replication error, transaction cost, and vol assumption error

All figures are means across each period's episodes, per-episode units are
dollars per 1-lot (100-share-equivalent) short call.

| Period | Freq | Scenario | n | Mean \|replication error\| | Mean txn cost | Mean n rebalances | Mean (realized − assumed) vol |
|---|---|---|---:|---:|---:|---:|---:|
| DEV | daily | GROSS | 106 | 1.867 | 0.000 | 30.9 | +0.0051 |
| DEV | daily | BASE | 106 | 1.877 | 0.080 | 30.9 | +0.0051 |
| DEV | daily | STRESS | 106 | 1.973 | 0.402 | 30.9 | +0.0051 |
| DEV | weekly | GROSS | 106 | 2.173 | 0.000 | 7.0 | +0.0051 |
| DEV | weekly | BASE | 106 | 2.177 | 0.053 | 7.0 | +0.0051 |
| DEV | weekly | STRESS | 106 | 2.197 | 0.265 | 7.0 | +0.0051 |
| VAL 2024 | daily | GROSS | 12 | 2.019 | 0.000 | 31.0 | +0.0073 |
| VAL 2024 | daily | BASE | 12 | 2.110 | 0.151 | 31.0 | +0.0073 |
| VAL 2024 | daily | STRESS | 12 | 2.503 | 0.754 | 31.0 | +0.0073 |
| VAL 2024 | weekly | GROSS | 12 | 3.064 | 0.000 | 7.0 | +0.0073 |
| VAL 2024 | weekly | BASE | 12 | 3.088 | 0.100 | 7.0 | +0.0073 |
| VAL 2024 | weekly | STRESS | 12 | 3.189 | 0.498 | 7.0 | +0.0073 |
| 2025 HIST. EVAL | daily | GROSS | 11 | 6.612 | 0.000 | 30.9 | +0.0169 |
| 2025 HIST. EVAL | daily | BASE | 11 | 6.646 | 0.177 | 30.9 | +0.0169 |
| 2025 HIST. EVAL | daily | STRESS | 11 | 6.781 | 0.884 | 30.9 | +0.0169 |
| 2025 HIST. EVAL | weekly | GROSS | 11 | 7.465 | 0.000 | 7.0 | +0.0169 |
| 2025 HIST. EVAL | weekly | BASE | 11 | 7.455 | 0.116 | 7.0 | +0.0169 |
| 2025 HIST. EVAL | weekly | STRESS | 11 | 7.476 | 0.578 | 7.0 | +0.0169 |

Mean max intra-episode cash requirement (daily/BASE): $246.71 (DEV),
$477.99 (VAL 2024), $546.56 (2025).

**Reading these numbers honestly**:

- **Daily rebalancing has lower mean absolute replication error than
  weekly in every period**, as expected — more frequent rebalancing tracks
  the option's delta more closely between price moves. The gap is modest
  in DEV (1.87 vs 2.17) and widens in 2025 (6.61 vs 7.47).
- **Transaction cost scales linearly with the cost-rate assumption**, as
  it must: STRESS (5bp) costs are consistently ~5x BASE (1bp) costs at
  matched frequency (e.g., DEV daily: 0.080 → 0.402), and weekly incurs
  roughly a quarter of daily's transaction cost at BASE (fewer trades),
  consistent with ~7 rebalances/episode vs ~31.
- **Trailing-20-session realized vol is a persistently low-biased
  estimate of the option's own realized vol over its life** in all three
  periods (realized − assumed is positive throughout), and the bias grows
  markedly by 2025 (+0.005 in DEV, +0.007 in 2024, +0.017 in 2025) — a
  volatility-regime effect (2025 realized vol over each 30-day option life
  ran meaningfully hotter than what the trailing 20 sessions had priced
  in at initiation), not a hedging-mechanics defect. This directly
  explains why 2025's mean absolute replication error (~6.6–7.5) is
  roughly 3x DEV's (~1.9–2.2): a bigger realized-vs-assumed vol gap means
  the ATM call was systematically under-priced at initiation relative to
  what actually happened, and the resulting under-hedge shows up as
  replication error regardless of rebalancing frequency.

## 6. Study 2 — Standardized nonlinear portfolio, VaR/ES, and backtesting

**Composition** (`build_standardized_portfolio`), rolled monthly on the
first eligible session of each calendar month: **+100 SPY-equivalent
shares, −2 at-the-money 30-trading-day calls (K=S₀), +2 95%-moneyness
30-trading-day puts**. Pricing vol is the 20-session realized vol (primary)
with the 60-session window carried as a sensitivity figure
(`realized_vol_60d_sensitivity`) on every snapshot. This is a standardized
construct evaluated on real historical risk-factor paths — never presented
as an observed historical position.

**VaR/ES methodology, at every eligible monthly roll** — all three methods
required by spec, at **both** 95% (primary) and 99% (secondary) confidence,
1-day horizon:

- **Historical Simulation**: full revaluation under the actual trailing
  252-session (primary) and 504-session (sensitivity) return distribution.
- **Delta-Normal**: linear (dollar-delta × factor-vol) parametric
  approximation, using the same 20-session realized vol as the Monte
  Carlo leg.
- **Monte Carlo full revaluation**: 50,000 simulated iid-normal
  single-factor draws (fixed seed 0), **every draw fully repriced** through
  the same Black-Scholes formula (option convexity captured, not
  linearized) — no antithetic sampling, disclosed as **"not included in
  this release"** per spec rather than silently assumed.

**A performance note that changed the implementation, not the
methodology**: the reference Monte Carlo implementation already in this
codebase (`options_risk.risk.var.monte_carlo_var`) reprices each of the
50,000 draws as a distinct Python object (`Scenario` →
`dataclasses.replace` → `Portfolio.market_value()`), which benchmarks at
~110 seconds for a single 50,000-sim/one-confidence-level call. At this
study's monthly-roll cadence across a 9-year formation window, that would
make the full study computationally impractical. `historical_risk_study_v2.py`
therefore adds `full_revaluation_mc_var_es`: a vectorized reimplementation
of the **identical** methodology — same `np.random.default_rng(seed)` draw
sequence, same closed-form Black-Scholes full revaluation applied to every
position, same `compute_var_es` used by every other method in this study —
that full-revalues all 50,000 draws in one array operation (~20
milliseconds instead of ~110 seconds). `tests/test_historical_risk_study_v2.py::
TestFullRevaluationMcVarEs` proves this is not an approximation: it
reproduces the reference scalar `monte_carlo_var`'s VaR, ES, and full loss
distribution to `1e-9` relative tolerance on a matched seed. **No cadence
reduction was needed as a result** — every eligible monthly roll in every
period gets the full three-method, two-confidence-level snapshot, matching
the spec's literal monthly cadence exactly.

### 6.1 Roll counts

| Period | Eligible monthly roll snapshots |
|---|---:|
| DEV (2015–2023) | 95 |
| VAL (2024) | 12 |
| 2025 HISTORICAL EVALUATION | 12 |

(Fewer eligible rolls than hedging episodes in DEV — 95 vs. 108 — because
the nonlinear-portfolio study requires a full 252-session historical
-simulation warm-up window, a stricter eligibility bar than the hedging
experiment's 20-session vol warm-up.)

### 6.2 VaR / ES by method, confidence level, and period

Dollar VaR/ES, mean across each period's roll snapshots:

| Period | Confidence | Method | Mean VaR | Mean ES |
|---|---|---|---:|---:|
| DEV | 95% | Historical Simulation (252d) | 226.8 | 366.9 |
| DEV | 95% | Delta-Normal | 3,193.6 | 4,005.0 |
| DEV | 95% | Monte Carlo (50k) | 8,403.7 | 11,816.8 |
| DEV | 99% | Historical Simulation (252d) | 423.5 | 588.5 |
| DEV | 99% | Delta-Normal | 4,516.8 | 5,174.8 |
| DEV | 99% | Monte Carlo (50k) | 13,917.9 | 17,342.5 |
| VAL 2024 | 95% | Historical Simulation (252d) | 259.3 | 350.7 |
| VAL 2024 | 95% | Delta-Normal | 3,192.1 | 4,003.0 |
| VAL 2024 | 95% | Monte Carlo (50k) | 10,043.1 | 13,453.3 |
| VAL 2024 | 99% | Historical Simulation (252d) | 418.9 | 471.7 |
| VAL 2024 | 99% | Delta-Normal | 4,514.6 | 5,172.3 |
| VAL 2024 | 99% | Monte Carlo (50k) | 15,645.0 | 18,581.9 |
| 2025 HIST. EVAL | 95% | Historical Simulation (252d) | 408.6 | 814.3 |
| 2025 HIST. EVAL | 95% | Delta-Normal | 7,225.7 | 9,061.3 |
| 2025 HIST. EVAL | 95% | Monte Carlo (50k) | 18,083.9 | 25,318.9 |
| 2025 HIST. EVAL | 99% | Historical Simulation (252d) | 701.1 | 1,789.1 |
| 2025 HIST. EVAL | 99% | Delta-Normal | 10,219.4 | 11,708.0 |
| 2025 HIST. EVAL | 99% | Monte Carlo (50k) | 29,831.6 | 36,893.3 |

**The three methods diverge sharply, and this is a real finding, not
noise to explain away.** Historical Simulation's mean VaR is roughly an
order of magnitude below Delta-Normal's, which is itself well below Monte
Carlo's, in every period. Two distinct, verifiable causes:

1. **Different volatility inputs.** Historical Simulation resamples the
   *actual* trailing 252-session (roughly one-year) empirical return
   distribution ending at each roll date. Delta-Normal and Monte Carlo
   instead both use that roll's own **20-session trailing realized vol** —
   a much shorter, more reactive window. Over a 9-year DEV period spanning
   very different volatility regimes, a roll's most-recent 20 sessions can
   run hotter or cooler than the trailing year as a whole; empirically
   here it runs hotter often enough that the 20-day-vol-driven methods
   (Delta-Normal, Monte Carlo) price in more risk than the 252-day
   empirical resample does.
2. **Linear vs. convex treatment of a genuinely nonlinear book.**
   Delta-Normal collapses the whole position to a single linear
   dollar-delta exposure, discarding the calls' and puts' gamma entirely.
   Monte Carlo and Historical Simulation both fully reprice the book
   (capturing convexity), which is why Monte Carlo's ES consistently
   exceeds Delta-Normal's ES by a wide margin at the same confidence level
   despite sharing the same vol input — full revaluation captures the fat
   tail that a linear approximation cannot.

This divergence is exactly the kind of finding these three methods being
run side-by-side is supposed to surface: **a book with meaningful options
convexity should not be risk-managed off a Delta-Normal VaR alone**, and a
252-day historical resample can materially understate forward-looking
tail risk when recent realized vol has moved well above the trailing
year's norm (as it had by the 2025 evaluation window, consistent with
Study 1's realized-vol finding above).

### 6.3 Kupiec / Christoffersen backtesting

One forecast per monthly roll's own next trading session (HS-primary
252-day 95% VaR vs. realized full-revaluation P&L) — a small,
monthly-cadence sample, not a daily rolling backtest.

**Corrected 2026-09-17 (independent review): the realized-return side of
this comparison was off by one trading session.** The code compared each
roll's VaR forecast against the return ENDING ON the roll date itself
(already realized before the roll, not a next-session outcome at all) —
`returns.iloc[ret_pos_val]`, where positional arithmetic on the
`log_returns`-shifted index landed one session too early. The VaR forecast
inputs were never affected (they were always computed strictly from
history before the roll), so this was a backtest-alignment defect, not a
future-leak in the risk model. Fixed with a date-keyed lookup
(`full_prices.index[idx_pos + 1]` → `returns.loc[that date]`, with a
strict existence check and no silent fallback) — see
`src/options_risk/historical_risk_study_v2.py` and the regression tests in
`tests/test_historical_risk_study_v2.py::TestNextSessionBacktestAlignment`.
Every other field in every artifact (VaR/ES values at every roll, method
methodology, confidence levels, lookbacks, Monte Carlo sims/seed, portfolio
construction, costs, realized-vol inputs, DGS3MO/VIX usage) is
byte-identical before and after this fix — verified by diffing the
corrected artifacts against the preserved pre-fix ones field by field; only
the breach sequence and the two backtest statistics below changed. Pre-fix
artifacts are preserved, not deleted, at
`results/historical_risk/superseded_next_session_backtest_fix/`.

| Period | n forecasts | Breaches (before → after) | Kupiec p-value (before → after) | Kupiec conclusion (after fix) | Christoffersen p-value (before → after) |
|---|---:|---:|---:|---|---:|
| DEV | 95 | 4 → 9 | 0.717 → 0.073 | Fail to reject H0 (observed 9.47% vs. expected 5.00%) | 0.551 → 0.167 |
| VAL 2024 | 12 | 0 → 0 | 0.267 → 0.267 (unchanged) | Fail to reject H0 (observed 0.00% vs. expected 5.00%) | 1.000 → 1.000 (unchanged) |
| 2025 HISTORICAL EVALUATION | 12 | 0 → 1 | 0.267 → 0.627 | Fail to reject H0 (observed 8.33% vs. expected 5.00%) | 1.000 → 1.000 (unchanged) |

**VAL 2024's breach count and p-value are genuinely unchanged by the fix**
— not a leftover from the pre-fix numbers. All 12 rolls in that period
happen to show zero breaches under both the old (wrong) and the new
(correct) realized-return definition; since Kupiec and Christoffersen are
both deterministic functions of the breach/no-breach sequence alone (not
of the underlying P&L magnitudes), a period where every roll's
classification happens to land the same way under both definitions
produces byte-identical backtest statistics even though the two
definitions genuinely compare against different daily returns underneath.
This is a property of this specific period's realized 2024 path, not
evidence the fix was a no-op elsewhere: DEV's breach count more than
doubled (4 → 9) and 2025 picked up its first breach (0 → 1).

**None of the three periods reject the null of correct VaR coverage or
independence at the 5% level, even after the correction** — but DEV's
Kupiec p-value dropped from 0.717 to 0.073, materially closer to the 5%
rejection boundary than the pre-fix number suggested. This is reported
factually, not smoothed over: the corrected DEV observed breach rate
(9.47%) sits well above the expected 5.00%, and while the test still fails
to reject at the conventional 5% significance level, it would reject at a
10% level. Combined with the small-sample caveat below, this is weaker
evidence for correct coverage than the pre-fix numbers implied, not
stronger. DEV's 95 observations sit below the ~250-observation (roughly
one trading year of *daily* observations) rule of thumb this codebase's
own `kupiec_pof_test` documents for reasonable test power, and VAL/2025's
12-observation samples are far below it — `sample_size_caveat` on every
backtest result says so explicitly. No parameter, threshold, or
methodology choice was changed in response to these corrected numbers.

## 7. Cross-study comparison: 2025 vs. DEV/VAL

Both studies point the same direction for 2025: **realized volatility ran
meaningfully hotter than what a 20-session trailing window (Study 1) or a
252-session historical resample (Study 2, HS leg) would have priced in**,
which mechanically increases both the hedging replication error (Study 1
§5.2) and the Delta-Normal/Monte Carlo VaR/ES levels (Study 2 §6.2)
relative to DEV/VAL. No claim is made here about *why* 2025 realized vol
ran hot (e.g., specific macro events) — this study only characterizes the
downstream effect on hedging error and tail-risk estimates, using the
data and methodology in scope.

## 8. Constraints and disclosed limitations (complete list)

- No paid options tapes; no invented option panels. Every option price in
  this study comes from Black-Scholes-Merton off realized volatility.
- DGS3MO is a short-term Treasury constant-maturity yield proxy, never a
  full option discount curve; used point-in-time, carry-forward only,
  never future-backfilled.
- **DGS3MO vintage disclosure (added 2026-09-17, P2):** this study uses
  FRED's standard `DGS3MO` series, keyed by its recorded
  `observation_date`, with causal carry-forward to the latest observation
  at or before each decision date (§2). This is **not** an ALFRED
  real-time vintage / release-calendar series. Concretely: no future
  observation is ever backfilled (the causal carry-forward guarantees
  that), but this study does **not** separately model the publication or
  revision lag between an observation's dated value and when that value
  actually became publicly available — a real point-in-time-correct
  pipeline would additionally need ALFRED's release-date metadata to rule
  that out. This does not change the dataset or methodology; it narrows
  what "point-in-time" is actually claimed to mean here.
- VIXCLS is market-volatility context/reference only — attached to every
  nonlinear-portfolio snapshot but never used as a pricing input and never
  described as this study's option's implied volatility.
- No discrete dividend modeling (`q=0.0` throughout, disclosed, not
  silently assumed to be some nonzero market yield).
- No antithetic sampling in the Monte Carlo leg — not implemented in this
  release, disclosed per spec rather than silently omitted.
- Hedging episodes' 30-session windows overlap month-to-month; reported
  cross-episode means are over serially dependent, not independent,
  samples.
- The Kupiec/Christoffersen backtest's monthly cadence yields small
  samples (12–95 observations) well below the ~250-observation rule of
  thumb for reasonable test power, especially in the two one-year
  periods — "fail to reject" there is weak evidence, not proof of correct
  VaR coverage.
- `yf_spy_daily_2015_2025_v1`'s raw bytes were reused from a sibling
  Directive #9 repository's already-verified acquisition, not freshly
  pulled in this repository — disclosed in the dataset manifest.
- The Monte Carlo VaR/ES leg uses `full_revaluation_mc_var_es`, a
  vectorized reimplementation of this codebase's existing
  `monte_carlo_var`, validated to match it to floating-point tolerance —
  not an approximation, but a distinct code path from the one used
  elsewhere in this repository's stress-testing module.

## 9. Reproducibility

```
# From the repo root, with data/raw/{yf_spy_daily_2015_2025_v1,
# fred_dgs3mo_daily_2015_2025_v1, fred_vixcls_daily_2015_2025_v1}/ populated:

python scripts/run_historical_risk_study_v2.py
python scripts/run_historical_risk_study_v2.py --skip-dev --skip-validation --allow-2025

pytest tests/test_historical_risk_study_v2.py   # 21 tests
```

All runs are fully seeded (`seed: 0` in the frozen config; Monte Carlo
uses `mc_seed=0` throughout). Every artifact's `dataset_canonical_sha256`
field ties its numbers back to the exact frozen input bytes listed in §2.
