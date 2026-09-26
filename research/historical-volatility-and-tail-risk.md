# Historical Volatility, Hedging Error, and Nonlinear Portfolio Tail Risk

### A Reproducible Study of Realized Paths, VaR Backtesting, and Full Revaluation

**Status**: AUTHORITATIVE (v2). Supersedes `options_historical_risk_study_v1.yaml` /
`historical_risk_study.py`, which is labeled **EXPLORATORY /
NON-CONFORMING TO THE PRE-REGISTERED SPEC v2** (wrong dataset IDs, no FRED integration,
GBM-simulated hedging instead of real historical-path replay, no standardized
nonlinear portfolio, no Monte Carlo VaR, a single confidence level, a single
HS lookback). v1's artifacts remain committed, unmodified, for audit trail;
none of its numbers are reused here.

**Config**: `configs/experiments/options_historical_risk_study_v2.yaml`
(`status: frozen-for-holdout`, frozen on creation — see "Freeze basis" below).
**Code**: `src/options_risk/historical_risk_study_v2.py`.
**Runner**: `scripts/run_historical_risk_study_v2.py`.
**Tests**: `tests/test_historical_risk_study_v2.py` (34 tests, all passing).
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
the exact methodology and required labels specified by the pre-registered
spec v2:

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
repository `Advanced_Algorithmic_Trading_Simulator_public` (statistical
arbitrage study), whose own SPY acquisition was already independently
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

## 3. 2025 labeling discipline

Per the pre-registered labeling rules: SPY's 2025 price history was **already
inspected** once under v1 (`options_hist_risk_v1_holdout_2025`, same
underlying series in substance). The 2025 result in this v2 study is
therefore labeled **`HISTORICAL EVALUATION`**, never `UNTOUCHED FINAL
HOLDOUT`. This study does not shift to 2026 to manufacture an untouched
window — 2026 is reserved program-wide and `no_2026_use_yet: true` is
enforced in the frozen config.

## 4. Freeze basis

This config's methodology (hedging mechanics, standardized portfolio
composition, VaR/ES methods, confidence levels, lookback windows, cost
scenarios) is taken directly from the pre-registered spec v2 text — none
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
  approximation, using the same **daily** (one-period) factor vol as the
  Monte Carlo leg — see the volatility-units provenance note in §6.2.
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

**Corrected 2026-09-18 — volatility-units defect (independent review,
tracker Issue #3).** `trailing_realized_vol()` returns **annualized**
volatility (`std(daily log returns) * sqrt(252)`) — correct as-is for the
Black-Scholes option pricing used to build the standardized portfolio
above (paired with maturity `T` already in years) — but the Delta-Normal
and 1-day Monte Carlo legs were being fed that same annualized figure
directly as their factor vol. Both `delta_normal_var` and
`full_revaluation_mc_var_es`'s own docstrings state their vol parameter is
**per one period** (one trading day) and scale it to the horizon
internally via `sqrt(horizon)`; at `horizon=1` this means they expected a
*daily* figure and instead received one inflated by `sqrt(252) ≈ 15.87`.
Historical Simulation never consumes a vol parameter at all (it resamples
observed daily log returns directly), so it — and the Kupiec/Christoffersen
backtest, which draws its forecast from Historical Simulation — was never
affected; this was verified, not assumed, by a full field-level diff
against the pre-fix artifacts (every field outside
`var_es.{primary,secondary}.{delta_normal,monte_carlo}` and the new
`daily_factor_vol_20d` provenance field is byte-identical). Fixed at the
call site only (`run_nonlinear_portfolio_study`): the BSM-pricing sigma is
untouched (still `annualized_vol20`); Delta-Normal and the Monte Carlo
factor draw now receive `daily_factor_vol20 = annualized_vol20 /
sqrt(252)` instead. See `src/options_risk/historical_risk_study_v2.py` and
the 8 regression tests in
`tests/test_historical_risk_study_v2.py::TestVolatilityUnitsFix`, including
a deterministic linear-portfolio proof that pre-fix and post-fix
Delta-Normal VaR differ by exactly `sqrt(252)`.

Dollar VaR/ES, mean across each period's roll snapshots — **corrected
figures** (pre-fix figures preserved for comparison, not deleted):

| Period | Confidence | Method | Mean VaR (corrected) | Mean ES (corrected) | Mean VaR (pre-fix, superseded) | Mean ES (pre-fix, superseded) |
|---|---|---|---:|---:|---:|---:|
| DEV | 95% | Historical Simulation (252d) | 226.8 | 366.9 | 226.8 | 366.9 |
| DEV | 95% | Delta-Normal | 201.2 | 252.3 | 3,193.6 | 4,005.0 |
| DEV | 95% | Monte Carlo (50k) | 227.8 | 298.5 | 8,403.7 | 11,816.8 |
| DEV | 99% | Historical Simulation (252d) | 423.5 | 588.5 | 423.5 | 588.5 |
| DEV | 99% | Delta-Normal | 284.5 | 326.0 | 4,516.8 | 5,174.8 |
| DEV | 99% | Monte Carlo (50k) | 344.0 | 405.3 | 13,917.9 | 17,342.5 |
| VAL 2024 | 95% | Historical Simulation (252d) | 259.3 | 350.7 | 259.3 | 350.7 |
| VAL 2024 | 95% | Delta-Normal | 201.1 | 252.2 | 3,192.1 | 4,003.0 |
| VAL 2024 | 95% | Monte Carlo (50k) | 249.3 | 333.6 | 10,043.1 | 13,453.3 |
| VAL 2024 | 99% | Historical Simulation (252d) | 418.9 | 471.7 | 418.9 | 471.7 |
| VAL 2024 | 99% | Delta-Normal | 284.4 | 325.8 | 4,514.6 | 5,172.3 |
| VAL 2024 | 99% | Monte Carlo (50k) | 387.7 | 462.9 | 15,645.0 | 18,581.9 |
| 2025 HIST. EVAL | 95% | Historical Simulation (252d) | 408.6 | 814.3 | 408.6 | 814.3 |
| 2025 HIST. EVAL | 95% | Delta-Normal | 455.2 | 570.8 | 7,225.7 | 9,061.3 |
| 2025 HIST. EVAL | 95% | Monte Carlo (50k) | 513.0 | 671.2 | 18,083.9 | 25,318.9 |
| 2025 HIST. EVAL | 99% | Historical Simulation (252d) | 701.1 | 1,789.1 | 701.1 | 1,789.1 |
| 2025 HIST. EVAL | 99% | Delta-Normal | 643.8 | 737.5 | 10,219.4 | 11,708.0 |
| 2025 HIST. EVAL | 99% | Monte Carlo (50k) | 773.0 | 909.4 | 29,831.6 | 36,893.3 |

(Historical Simulation is repeated unchanged in both column pairs as a
visual confirmation that it was genuinely unaffected, not omitted from the
comparison. Full corrected artifacts:
`results/historical_risk/options_hist_risk_v2_{dev_formation,val_2024,historical_evaluation_2025}.json`;
pre-fix artifacts preserved at
`results/historical_risk/superseded_volatility_units_fix/`.)

**Prior interpretive claim withdrawn: the "order of magnitude" divergence
was not a genuine methodological finding.** The previous version of this
section reported Delta-Normal at roughly 14x Historical Simulation's VaR
and Monte Carlo at roughly 35–45x, and offered two explanations — a
20-session-vs-252-session volatility-window mismatch, and Delta-Normal's
linear treatment discarding convexity. Both explanations were plausible
*in kind* but wrong *in magnitude*: Delta-Normal's VaR/ES fell by exactly
`sqrt(252) ≈ 15.87` at every single roll and confidence level once the
units defect was corrected (a deterministic, portfolio-independent ratio —
confirmed both in this artifact-level table and in the dedicated
`test_deterministic_linear_portfolio_var_scales_by_sqrt_252` regression
test), and Monte Carlo's VaR fell by a comparable ~40–50x. That leaves only
a residual, much smaller gap between methods to actually explain — the
claim that recent (20-day) vol was running "hot" broadly enough to explain
an order-of-magnitude gap is **withdrawn**; it was never the dominant
effect, the volatility-units defect was.

**What the corrected numbers actually show**, now that all three methods
sit within the same order of magnitude in every period and confidence
level:

1. **The 20-session-vs-252-session vol-window difference is real but
   small, and its sign is not consistent across periods.** In DEV and VAL
   2024, Delta-Normal (driven by the shorter 20-session window) is
   modestly *below* Historical Simulation (e.g. DEV 95%: 201.2 vs.
   226.8) — the opposite direction from the old narrative. In the 2025
   HISTORICAL EVALUATION period, Delta-Normal is modestly *above*
   Historical Simulation (455.2 vs. 408.6 at 95%), consistent with 2025's
   mean 20-session annualized realized vol (16.33%) running somewhat
   hotter than DEV's 9-year average (15.15%) and VAL 2024's (11.84%) — but
   this is now correctly sized as an ~11% effect, not the order-of-magnitude
   effect previously (mis)attributed to it. **Audited per the critical
   reporting rule: no sentence in this report now claims 2025 realized vol
   explains a VaR difference of more than this modest, correctly-scaled
   amount.**
2. **Convexity survives as a real, still-supported finding, at its true
   scale.** Monte Carlo's ES exceeds Delta-Normal's ES in every single
   period/confidence row post-correction (e.g. DEV 95%: 298.5 vs. 252.3;
   2025 95%: 671.2 vs. 570.8) — full revaluation continues to price in
   more tail risk than the linear approximation, as expected from a book
   with genuine gamma. This part of the original claim is **retained**,
   simply no longer conflated with the units defect's much larger effect.
3. **New finding, visible only after correction: in the 2025 period at
   99% confidence, Historical Simulation's ES (1,789.1) is nearly 2.5x
   Monte Carlo's (909.4) and over 2x Delta-Normal's (737.5) — the
   opposite ranking from every other row in this table.** Historical
   Simulation draws real historical daily returns, including whatever
   single worst days actually occurred in the trailing 252-session window
   feeding each 2025 roll; Monte Carlo and Delta-Normal both assume an
   i.i.d.-normal daily return around a smoothly-estimated 20-session
   vol, which cannot reproduce a fat realized tail the way resampling
   actual history can. This was invisible pre-fix (Delta-Normal/Monte
   Carlo's VaR/ES were inflated ~16–45x by the units defect, dwarfing this
   effect); it is a genuine, previously-unreported tail-risk finding about
   this book in this period, not an artifact of the correction itself
   (Historical Simulation's own numbers did not change).

**Revised conclusion:** running all three methods side-by-side is still
useful — DEV/VAL show Delta-Normal is not systematically conservative
relative to Historical Simulation, and 2025 shows Historical Simulation's
tail (ES at 99%) can be fatter than either parametric method captures. But
the previously reported "order of magnitude, book-should-not-be-risk-managed-
off-Delta-Normal-alone" framing significantly overstated the case; the
methods now agree far more closely than they disagreed under the pre-fix
numbers, and the genuinely interesting residual finding is the 2025 ES tail
divergence in item 3 above, not a blanket convexity/vol-window story.

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

**Study 1 (hedging error) claim unaffected by the §6.2 volatility-units
fix** (Study 1's discrete-hedging simulator never calls the code path that
fix touched): 2025 realized volatility over each 30-day option's life ran
meaningfully hotter than what the trailing 20 sessions had priced in at
initiation (§5.2's realized-vs-assumed vol gap), which mechanically
increases the hedging replication error relative to DEV/VAL.

**Study 2 (VaR/ES) claim corrected 2026-09-18, audited per the
volatility-units fix's reporting rule.** The prior version of this section
extended the same "2025 realized vol ran hot" explanation to the
Delta-Normal/Monte Carlo VaR/ES levels in §6.2, implying a comparably large
effect. §6.2's correction shows that framing overstated the case: the
VaR/ES levels reported pre-fix were inflated up to ~16–45x by the
volatility-units defect, not primarily by 2025's vol regime. The genuine,
corrected effect is real but modest — 2025's mean 20-session annualized
realized vol (16.33%) does run somewhat hotter than DEV's (15.15%) and VAL
2024's (11.84%), consistent with Delta-Normal/Monte Carlo sitting modestly
above (not below, as in DEV/VAL) Historical Simulation's VaR in the 2025
period (§6.2, item 1) — an ~11% effect at 95% VaR, not an order-of-magnitude
one. No claim is made here about *why* 2025 realized vol ran hot (e.g.,
specific macro events) — this study only characterizes the downstream
effect on hedging error and tail-risk estimates, using the data and
methodology in scope, and this section now states that effect's corrected
size rather than repeating the pre-fix magnitude.

## 8. Constraints and disclosed limitations (complete list)

- No paid options tapes; no invented option panels. Every option price in
  this study comes from Black-Scholes-Merton off realized volatility.
- DGS3MO is a short-term Treasury constant-maturity yield proxy, never a
  full option discount curve; used point-in-time, carry-forward only,
  never future-backfilled.
- **DGS3MO vintage disclosure (added 2026-09-17):** this study uses
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
  repository's already-verified acquisition, not freshly
  pulled in this repository — disclosed in the dataset manifest.
- The Monte Carlo VaR/ES leg uses `full_revaluation_mc_var_es`, a
  vectorized reimplementation of this codebase's existing
  `monte_carlo_var`, validated to match it to floating-point tolerance —
  not an approximation, but a distinct code path from the one used
  elsewhere in this repository's stress-testing module.
- **Volatility-units defect disclosure (corrected 2026-09-18):** §6.2
  discloses in full that Delta-Normal and Monte Carlo VaR/ES were
  previously computed against an annualized (not daily/per-period)
  volatility input, overstating both by ~16–45x, while BSM option pricing
  and Historical Simulation were unaffected throughout. Included here for
  completeness alongside this section's other disclosed limitations, not
  as a substitute for §6.2's full explanation.

## 9. Reproducibility

```
# From the repo root, with data/raw/{yf_spy_daily_2015_2025_v1,
# fred_dgs3mo_daily_2015_2025_v1, fred_vixcls_daily_2015_2025_v1}/ populated:

python scripts/run_historical_risk_study_v2.py
python scripts/run_historical_risk_study_v2.py --skip-dev --skip-validation --allow-2025

pytest tests/test_historical_risk_study_v2.py   # 34 tests
```

All runs are fully seeded (`seed: 0` in the frozen config; Monte Carlo
uses `mc_seed=0` throughout). Every artifact's `dataset_canonical_sha256`
field ties its numbers back to the exact frozen input bytes listed in §2.
