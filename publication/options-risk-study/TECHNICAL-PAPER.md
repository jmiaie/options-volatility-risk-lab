# Historical Volatility, Hedging Error, and Nonlinear Portfolio Tail Risk

### A publication-pack writeup of already-accepted, already-computed Directive #9 (D9-C) evidence

**Status**: D10-C publication/communication artifact. This paper writes up
results that were already computed, reviewed, and accepted under D9-C. It
performs no new empirical work: no retraining, no retuning, no re-acquiring
data, and no rerun of any evaluation period, including 2025. Every number in
this paper is read from a committed result artifact and cross-checked
against `RESULT-SOURCE-MAP.md`. Source repository:
`jmiaie/options-volatility-risk-lab`, commit `db9cf44a04f1282f81ed11c7d145b5afe2db8d95`.

---

## Abstract

We study two hypothetical, standardized options constructs evaluated on
real historical SPY, short-rate (FRED DGS3MO), and volatility-context (FRED
VIXCLS) paths from 2015 through 2025: (1) the **"Historical underlying-path
hypothetical option hedging experiment"** — discrete delta-hedging of a
short ATM 30-session call replayed against actual subsequent SPY closes —
and (2) the **"Hypothetical nonlinear portfolio evaluated on historical
risk-factor paths"** — a standardized long-equity/short-call/long-put book
marked monthly and risk-managed with three independent VaR/ES methodologies
(Historical Simulation, Delta-Normal, Monte Carlo full revaluation) at two
confidence levels, backtested with Kupiec/Christoffersen coverage tests.
Neither construct reflects a deployed trading strategy or real historical
options P&L; every option price is Black-Scholes-Merton off realized
volatility, never a fabricated implied-volatility surface or a paid options
tape.

A defect found and fixed under D9-C (commit `db9cf44`) had fed the
Delta-Normal and Monte Carlo VaR/ES legs an **annualized** volatility figure
where both methods' own documented contracts required a **daily** (one-
period) figure — inflating Delta-Normal VaR by exactly `sqrt(252) ≈ 15.87x`
and Monte Carlo VaR by a comparable ~35–41x. **This paper explicitly
withdraws the prior report's interpretive claim that the resulting
order-of-magnitude divergence between methods was a genuine finding
explained by "recent realized vol running hot" and convexity.** It was not:
most of that divergence was the units defect. The corrected numbers show all
three methods sitting within the same order of magnitude at every period and
confidence level, with two much smaller, genuine residual findings that
survive correction: full-revaluation Monte Carlo's ES exceeds Delta-Normal's
ES in every period/confidence row (a persistent nonlinear-revaluation
difference consistent with the book's convexity, at its true, much smaller
scale), and 2025's realized volatility ran modestly — not
dramatically — hotter than DEV/VAL, producing an ~11% (not order-of-
magnitude) shift in Delta-Normal's relative position. Historical Simulation
and the Kupiec/Christoffersen backtest were never affected by the units
defect and are confirmed byte-identical pre- and post-fix.

---

## 1. Methodology

### 1.1 Standardized nonlinear portfolio and hedging construct

Both studies are evaluated on the frozen `options_hist_risk_v2` experiment
(`configs/experiments/options_historical_risk_study_v2.yaml`,
sha256 `4bd18561466b5f85b09031868322929c8ad28bd9c2da9358ac3a106fdb725181`),
run once per period (DEV, VAL 2024, 2025 HISTORICAL EVALUATION) against
real SPY daily closes, FRED DGS3MO, and FRED VIXCLS
(`data/manifests/` — see `SOURCE-GATE.md`'s "Additional dataset provenance"
section for the reuse-provenance disclosure on SPY). Neither the SPY
underlying path, the option contracts,
the rolling schedule, nor the rate/vol handling was altered for this
publication pack.

**Study 1 — "Historical underlying-path hypothetical option hedging
experiment."** A standardized, short, one-lot, at-the-money 30-trading-day
European call is delta-hedged by replaying the *actual* subsequent 30 SPY
daily closes (`simulate_delta_hedge_on_price_path`,
`src/options_risk/historical_risk_study_v2.py:178`) — deterministic given
the historical path, no GBM simulation and no internal RNG. Pricing
volatility is the trailing 20-session realized vol known before initiation
(never called implied volatility). One episode initiates on the first
eligible session of every calendar month; each episode runs at **daily**
and **weekly** rebalancing, crossed with **GROSS (0bp) / BASE (1bp) / STRESS
(5bp)** transaction-cost scenarios. Dividend yield `q=0.0` throughout
(disclosed, not modeled as a nonzero market yield).

**Study 2 — "Hypothetical nonlinear portfolio evaluated on historical
risk-factor paths."** A standardized book —
**+100 SPY-equivalent shares, −2 at-the-money 30-session calls (K=S₀), +2
95%-moneyness 30-session puts** — is built and marked at the first eligible
session of every calendar month (`build_standardized_portfolio`,
`historical_risk_study_v2.py:419`). Both legs are convex/concave enough to
give the book genuine gamma, which is what makes the Delta-Normal vs. full-
revaluation comparison below informative rather than trivial.

### 1.2 VaR/ES three-method framework

At every eligible monthly roll, all three VaR/ES methods required by spec
run at **both** 95% (primary) and 99% (secondary) confidence, 1-day horizon
(`run_nonlinear_portfolio_study`, `historical_risk_study_v2.py:628`):

1. **Historical Simulation** (`historical_simulation_var`,
   `src/options_risk/risk/var.py:104`) — full revaluation of the
   standardized book under the actual trailing 252-session (primary) return
   distribution (504-session carried as a sensitivity figure). Consumes no
   vol parameter — it resamples real observed daily log returns directly.
2. **Delta-Normal** (`delta_normal_var`, `src/options_risk/risk/var.py:146`)
   — a deliberately simplistic linear (dollar-delta × factor-vol,
   normal-tail) parametric baseline. By its own docstring: "no
   Gamma/convexity is modeled at all... will systematically mis-price tail
   risk for an option-heavy (convex) book." `factor_vol` is documented as
   **per one period** (one trading day), scaled to the horizon via
   `sqrt(horizon)` internally.
3. **Monte Carlo full revaluation** (`full_revaluation_mc_var_es`,
   `historical_risk_study_v2.py:472`) — 50,000 simulated iid-normal
   single-factor draws (fixed seed 0), every draw fully repriced through the
   same Black-Scholes formula (option convexity captured, not linearized).
   A vectorized reimplementation of this codebase's reference
   `monte_carlo_var` (`src/options_risk/risk/var.py:190`), validated to
   `1e-9` relative tolerance on a matched seed
   (`tests/test_historical_risk_study_v2.py::TestFullRevaluationMcVarEs`) —
   not an approximation, a distinct code path chosen purely for
   computational tractability at this study's cadence (~20ms vs. ~110s per
   call). No antithetic sampling (disclosed, not silently omitted). Also
   documents its vol parameter as **per one period**.
4. **Kupiec / Christoffersen backtest** (`kupiec_pof_test`,
   `christoffersen_independence_test`, `src/options_risk/risk/backtesting.py:74`,
   `:134`) — one forecast per monthly roll's own next trading session
   (HS-primary 95% VaR vs. realized full-revaluation P&L); a small,
   monthly-cadence sample, not a daily rolling backtest.

### 1.3 Volatility-units provenance — explained for a reader who has never seen the defect

The single most consequential implementation detail in this study is which
of two volatility figures feeds which downstream calculation, and why they
must differ.

`trailing_realized_vol()` (`historical_risk_study_v2.py:144`) computes
close-to-close log-return standard deviation over a trailing window and
**annualizes it**: `std(daily log returns, ddof=1) * sqrt(252)`. This
annualized figure is exactly what Black-Scholes-Merton option pricing wants,
because BSM's own volatility parameter is conventionally annualized and is
paired with maturity `T` expressed in years (`T = 30/252` here). Using the
annualized figure to price the standardized portfolio's options is correct
and was never wrong.

But the same study also needs a **one-day** (per-period) volatility figure
for two different calculations: the Delta-Normal VaR formula and the Monte
Carlo factor draw, both of which model a **one-day** return distribution and
scale it to the horizon themselves via `sqrt(horizon)` (both functions'
docstrings say so explicitly — see `src/options_risk/risk/var.py:146` and
`historical_risk_study_v2.py:472`). At `horizon=1`, feeding either function
the **annualized** figure instead of the daily one silently substitutes a
volatility number that is too large by a factor of `sqrt(252) ≈ 15.87` — the
exact conversion factor between an annualized and a daily standard
deviation under the standard iid-normal-returns scaling convention.

This is precisely the mistake the D9-C review found and fixed at commit
`db9cf44`: `run_nonlinear_portfolio_study` was passing `annualized_vol20`
(the correct BSM-pricing figure) into the Delta-Normal and Monte Carlo legs
as well, where it should have passed
`daily_factor_vol20 = annualized_vol20 / sqrt(252)`. The fix touches only
the call site — neither `trailing_realized_vol()` nor `delta_normal_var()`/
`full_revaluation_mc_var_es()` themselves needed to change, because each was
already internally correct and correctly documented; only the value handed
between them was wrong. Historical Simulation was never in scope for this
defect at all, because it never consumes a volatility parameter — it
resamples real historical daily log returns directly — and the
Kupiec/Christoffersen backtest draws its forecast from Historical
Simulation, so it too was unaffected throughout.

**Concrete verified example.** See `CASE-STUDY.md` for the full,
field-by-field trace of the DEV period's first eligible roll
(2016-02-01): `realized_vol_20d` (annualized) = 0.235506,
`daily_factor_vol_20d` = 0.014835 = 0.235506 / √252 (0.01483546539740085), and the
resulting 95%-confidence Delta-Normal VaR/ES move from a pre-fix
3,382.80 / 4,242.17 to a corrected 213.10 / 267.23 — a ratio of exactly
15.8745 (to 6 significant figures), matching `sqrt(252) = 15.8745...`
deterministically, because Delta-Normal VaR is linear in factor vol. Monte
Carlo's VaR at the same roll falls from 7,039.23 to 226.61, a ~31.1x
reduction — super-linear relative to Delta-Normal's exact `sqrt(252)` ratio of 15.875,
consistent with (not a formal decomposition proving) the full-revaluation
book's nonlinearity/convexity. Historical Simulation's VaR/ES at that same
roll (137.71 / 192.51) is byte-identical before and after.

---

## 2. Results

All figures below are read directly from
`results/historical_risk/options_hist_risk_v2_{dev_formation,val_2024,historical_evaluation_2025}.json`
via `publication/options-risk-study/scripts/build_tables.py`, and cross-
referenced to exact JSON key paths in `RESULT-SOURCE-MAP.md`.

### 2.1 Study 1 — hedging replication error

Mean values across each period's episodes, dollars per configured contract unit `option_qty`
(multiplied directly into per-share Black-Scholes values, with no ×100 lot multiplier:
these are **not** 100-share-lot dollars) short call. Source:
`hedging_experiment.summary_by_frequency_and_cost_scenario` in each current
artifact; full table in `tables/hedging_experiment_summary.csv`.

| Period | Freq | Scenario | n | Mean \|repl. error\| | Mean txn cost | Mean n rebal. | Mean (realized − assumed) vol |
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
| 2025 HIST. EVAL | daily | STRESS | 11 | 6.781 | 0.883 | 30.9 | +0.0169 |
| 2025 HIST. EVAL | weekly | GROSS | 11 | 7.465 | 0.000 | 7.0 | +0.0169 |
| 2025 HIST. EVAL | weekly | BASE | 11 | 7.455 | 0.116 | 7.0 | +0.0169 |
| 2025 HIST. EVAL | weekly | STRESS | 11 | 7.476 | 0.578 | 7.0 | +0.0169 |

Mean max intra-episode cash requirement (daily/BASE): $246.71 (DEV), $477.99
(VAL 2024), $546.56 (2025).

Daily rebalancing has lower mean absolute replication error than weekly in
every period, as expected. Transaction cost scales linearly with the
cost-rate assumption. Trailing-20-session realized vol is a persistently
low-biased estimate of the option's own realized vol over its life in all
three periods, and this bias grows by 2025 — this is the mechanism behind
2025's larger hedging error, and it is a Study-1-specific effect
independent of the volatility-units defect described in §1.3, because
Study 1's hedge simulator never calls the code path that defect touched.

### 2.2 Study 2 — corrected VaR/ES by method, confidence, and period

Dollar VaR/ES, mean across each period's roll snapshots. Source:
`nonlinear_portfolio_study.snapshots[*].var_es.{primary,secondary}.{method}`
in each current artifact; full table with per-row source hashes in
`tables/var_es_corrected_vs_prefix.csv`.

| Period | Confidence | Method | Mean VaR (corrected) | Mean ES (corrected) |
|---|---|---|---:|---:|
| DEV | 95% | Historical Simulation (252d) | 226.8 | 366.9 |
| DEV | 95% | Delta-Normal | 201.2 | 252.3 |
| DEV | 95% | Monte Carlo (50k) | 227.8 | 298.5 |
| DEV | 99% | Historical Simulation (252d) | 423.5 | 588.5 |
| DEV | 99% | Delta-Normal | 284.5 | 326.0 |
| DEV | 99% | Monte Carlo (50k) | 344.0 | 405.3 |
| VAL 2024 | 95% | Historical Simulation (252d) | 259.3 | 350.7 |
| VAL 2024 | 95% | Delta-Normal | 201.1 | 252.2 |
| VAL 2024 | 95% | Monte Carlo (50k) | 249.3 | 333.6 |
| VAL 2024 | 99% | Historical Simulation (252d) | 418.9 | 471.7 |
| VAL 2024 | 99% | Delta-Normal | 284.4 | 325.8 |
| VAL 2024 | 99% | Monte Carlo (50k) | 387.7 | 462.9 |
| 2025 HIST. EVAL | 95% | Historical Simulation (252d) | 408.6 | 814.3 |
| 2025 HIST. EVAL | 95% | Delta-Normal | 455.2 | 570.8 |
| 2025 HIST. EVAL | 95% | Monte Carlo (50k) | 513.0 | 671.2 |
| 2025 HIST. EVAL | 99% | Historical Simulation (252d) | 701.1 | 1,789.1 |
| 2025 HIST. EVAL | 99% | Delta-Normal | 643.8 | 737.5 |
| 2025 HIST. EVAL | 99% | Monte Carlo (50k) | 773.0 | 909.4 |

### 2.3 Kupiec / Christoffersen backtest results (all periods)

Source: `nonlinear_portfolio_study.kupiec_christoffersen_backtest` in each
current artifact; full table in `tables/kupiec_christoffersen.csv`.

| Period | n forecasts | Breaches | Kupiec p-value | Kupiec conclusion | Christoffersen p-value |
|---|---:|---:|---:|---|---:|
| DEV | 95 | 9 | 0.073 | Fail to reject H0 (observed 9.47% vs. expected 5.00%) | 0.167 |
| VAL 2024 | 12 | 0 | 0.267 | Fail to reject H0 (observed 0.00% vs. expected 5.00%) | 1.000 |
| 2025 HIST. EVAL | 12 | 1 | 0.627 | Fail to reject H0 (observed 8.33% vs. expected 5.00%) | 1.000 |

**These backtest results are confirmed byte-identical pre- and post- the
volatility-units fix** in all three periods — the volatility-units fix
never touches the Kupiec/Christoffersen backtest's inputs (Historical
Simulation's own VaR/ES, or the realized next-session P&L), since it draws
its forecast from Historical Simulation, never from the vol-units-affected
Delta-Normal/Monte Carlo legs. (These numbers *do* differ from an earlier,
separate, already-corrected defect — the next-session backtest-alignment
off-by-one fixed at commit `5327719`, one commit before this branch's base;
see `tables/kupiec_christoffersen.csv`'s `*_before`/`*_after` columns for
that unrelated correction's own before/after figures, and
`research/historical-volatility-and-tail-risk.md` §6.3 for its full
explanation. That fix is orthogonal to this paper's central correction and
is not being re-litigated here.)

---

## 3. The corrected VaR/ES comparison — withdrawal of the prior narrative

**This section states plainly, as required, that the previous version of
this study's narrative is withdrawn, not merely superseded by a silently
adjacent table.**

The prior version of `research/historical-volatility-and-tail-risk.md`'s
VaR/ES section (visible in git history, and reproduced for comparison in
`tables/var_es_corrected_vs_prefix.csv`'s `*_prefix_superseded` columns)
reported Delta-Normal at roughly 14x Historical Simulation's VaR and Monte
Carlo at roughly 35–45x, and explained that order-of-magnitude divergence as
a **"genuine finding"** attributable to two effects: (a) recent (20-session)
realized volatility running "hot" relative to the 252-session Historical
Simulation window, and (b) Delta-Normal's linear treatment discarding
convexity that the full-revaluation methods captured.

**That explanation is withdrawn. It was wrong in magnitude, even though
both named mechanisms are real in kind.** Once the volatility-units defect
(§1.3) was corrected, Delta-Normal's VaR/ES fell by **exactly**
`sqrt(252) ≈ 15.87x` at every single roll and confidence level — a
deterministic, portfolio-independent ratio, confirmed both in
`tables/var_es_corrected_vs_prefix.csv`'s `var_ratio_prefix_over_corrected`
column (15.875 in every Delta-Normal row, to 3 decimal places) and in the
dedicated regression test
`tests/test_historical_risk_study_v2.py::test_deterministic_linear_portfolio_var_scales_by_sqrt_252`.
Monte Carlo's VaR fell by a comparable ~35–41x across periods and
confidence levels (super-linear relative to Delta-Normal's exact ratio of 15.875, consistent with the
full-revaluation book's nonlinearity rather than Delta-Normal's exact
linear scaling, but still overwhelmingly dominated by the same units error,
not by vol-regime or convexity effects). **The
"recent vol running hot" and "convexity" explanations were never the
dominant effect on the size of the gap reported pre-fix — the
volatility-units defect was.** This publication pack does not repeat, soften,
or present side-by-side without comment the pre-fix "order of magnitude,
explained by recent vol + convexity" framing as if it were still a live
interpretation. It is superseded and withdrawn.

### 3.1 What the corrected numbers actually show

Now that all three methods sit within the same order of magnitude in every
period and confidence level:

1. **The 20-session-vs-252-session vol-window difference is real but
   small, and its sign is not consistent across periods.** In DEV and VAL
   2024, Delta-Normal (driven by the shorter 20-session window) sits
   modestly *below* Historical Simulation (e.g. DEV 95%: 201.2 vs. 226.8).
   In the 2025 HISTORICAL EVALUATION period, Delta-Normal sits modestly
   *above* Historical Simulation (455.2 vs. 408.6 at 95%) — an **~11%**
   effect (455.2 / 408.6 = 1.114, computed directly from the table above),
   not an order-of-magnitude one, and consistent with 2025's mean
   20-session annualized realized vol (16.33%, computed as the mean of
   `realized_vol_20d` across all 12 of 2025's roll snapshots) running
   somewhat hotter than DEV's 9-year average (15.15%) and VAL 2024's
   (11.84%) — both means independently recomputed in this session from the
   same artifacts (see `tables/dataset_and_artifact_hashes.json` for source
   hashes). No sentence in this paper attributes more than this modest,
   correctly-scaled amount to 2025's realized-vol level.

2. **A persistent nonlinear-revaluation difference survives, at its true
   (much smaller) scale, consistent with convexity.** Monte Carlo's ES
   exceeds Delta-Normal's ES in **every single** period/confidence row
   post-correction: DEV 95% (298.5 vs. 252.3), DEV 99% (405.3 vs. 326.0),
   VAL 2024 95% (333.6 vs. 252.2), VAL 2024 99% (462.9 vs. 325.8), 2025 95%
   (671.2 vs. 570.8), 2025 99% (909.4 vs. 737.5) — full revaluation prices
   in more tail risk than the linear approximation in every single row.
   This is compatible with, and expected from, the book's convexity (every
   roll's standardized portfolio has genuine, nonzero gamma — see each
   snapshot's own `portfolio_greeks.gamma` field), but this pack has not run
   a separate gamma/attribution decomposition isolating convexity as the
   sole or dominant cause of this specific gap, so it is reported here as an
   observed, persistent difference between the two methods that is
   consistent with convexity, not as a proven causal decomposition. This
   part of the original claim is retained at its correct, much smaller
   scale and reframed accordingly; it is no longer conflated with the units
   defect's much larger effect.

3. **A genuine finding visible only after correction: in the 2025 period at
   99% confidence, Historical Simulation's ES (1,789.1) exceeds both
   full-revaluation Monte Carlo's ES (909.4, a ratio of 1789.1/909.4 ≈
   1.97x) and Delta-Normal's ES (737.5, a ratio of 1789.1/737.5 ≈ 2.43x) —
   the widest such gap in the table, not a single-row inversion: Historical Simulation’s ES is
   the highest of the three methods in every period and confidence cell (6 of 6, measured from
   the cited CSV).**
   Historical Simulation draws real historical daily returns, including
   whatever single worst days actually occurred in the trailing 252-session
   window feeding each 2025 roll; Monte Carlo and Delta-Normal both assume
   an iid-normal daily return around a smoothly estimated 20-session vol,
   which cannot reproduce a fat realized tail the way resampling actual
   history can. This effect was invisible pre-fix, because the units defect
   inflated Delta-Normal/Monte Carlo's VaR/ES by ~16–43x, dwarfing it; it is
   a genuine, previously-unreported tail-risk finding about this book in
   this period, not an artifact of the correction itself — Historical
   Simulation's own numbers did not change at all across the fix. (Note on
   precision: `research/historical-volatility-and-tail-risk.md` §6.2 item 3
   describes these same three numbers with the qualitative phrases "nearly
   2.5x Monte Carlo's" and "over 2x Delta-Normal's"; recomputing the ratios
   directly from the cited figures in this session gives ≈1.97x for Monte
   Carlo and ≈2.43x for Delta-Normal — i.e., the "nearly 2.5x" description
   fits the Delta-Normal ratio and "just under 2x" fits the Monte Carlo
   ratio more precisely than the original phrasing's pairing. The underlying
   VaR/ES values themselves (1,789.1 / 909.4 / 737.5) are unchanged and
   correctly cited in both places; this is a restatement of the ratio
   language, not a correction to any number. See `CITATION-REDTEAM.md`
   finding CIT-1.)

**Revised conclusion.** Running all three methods side-by-side remains
useful: DEV/VAL show Delta-Normal is not systematically conservative
relative to Historical Simulation, and 2025 shows Historical Simulation's
tail (ES at 99%) can be fatter than either parametric method captures. The
previously reported "order of magnitude, book-should-not-be-risk-managed-
off-Delta-Normal-alone" framing significantly overstated the case — that
framing is withdrawn. The methods now agree far more closely than the
pre-fix numbers implied, and the genuinely interesting residual finding is
the 2025 ES tail divergence in item 3 above, not a blanket
convexity/vol-window story.

---

## 4. Genuine surviving findings, at corrected scale

Consolidating §3.1 and §2.1:

- **Nonlinear-revaluation ES premium, consistent with convexity (Study 2,
  retained, correctly scaled)**: full-revaluation Monte Carlo's ES exceeds
  the linear Delta-Normal approximation's ES in all 6 period × confidence
  rows, by amounts ranging from roughly +18% (2025 95%: 671.2 vs. 570.8,
  the smallest gap in the table) to roughly +42% (VAL 2024 99%: 462.9 vs.
  325.8, the largest) — a real, modest, and consistent effect, not the
  multi-thousand-percent gap the pre-fix numbers implied. This is reported
  as an observed, persistent difference between the two methods that is
  compatible with the book's convexity; no separate gamma/attribution
  decomposition was performed to isolate convexity as its sole cause.
- **2025 realized vol running modestly hotter (Study 1 and Study 2,
  retained, correctly scaled)**: 2025's mean 20-session annualized realized
  vol (16.33%) exceeds DEV's (15.15%) by a low-single-digit amount (+7.8%) and VAL 2024's
  (11.84%) by a double-digit amount (+37.9%) — in neither case order-of-magnitude. This is the
  correctly-scaled mechanism behind (a) Study 1's larger 2025 hedging
  replication error (§2.1's realized-minus-assumed vol bias grows from
  +0.0051 in DEV to +0.0169 in 2025) and (b) Study 2's Delta-Normal sitting
  modestly above, rather than below, Historical Simulation in 2025 only
  (§2.1 mean-realized-vol figures section of `RESULT-SOURCE-MAP.md`).
- **2025's fat realized tail at 99% ES (Study 2, new finding, correctly
  visible only post-fix)**: Historical Simulation's ES is the highest of the
  three methods in **all six** period/confidence cells (§3.1 item 3). What is
  unique to 2025-99% is the *size* of the gap — ≈1.97x Monte Carlo's and
  ≈2.43x Delta-Normal's ES — not the ranking direction.
- **No claim is made about *why* 2025 realized vol ran hot** (e.g., specific
  macro events) — this study characterizes the downstream effect on
  hedging error and tail-risk estimates using the data and methodology in
  scope, nothing more.

---

## 5. Limitations

Reproduced from `SOURCE-GATE.md`'s "Known limitations and caveats (full
list)" section (field 14 gives the concise version) /
`research/historical-volatility-and-tail-risk.md` §8, not softened:

- No paid options tapes; no invented option panels.
- DGS3MO is a short-term Treasury constant-maturity yield proxy, not a full
  option discount curve; carry-forward point-in-time use only.
- DGS3MO vintage disclosure: standard (non-ALFRED) series; publication/
  revision lag is not separately modeled.
- VIXCLS is context only, never a pricing input.
- No discrete dividend modeling (`q=0.0` throughout).
- No antithetic sampling in the Monte Carlo leg.
- Hedging episodes' 30-session windows overlap month-to-month — reported
  cross-episode means are over serially dependent samples.
- Kupiec/Christoffersen sample sizes (12–95 observations) are well below
  the ~250-observation rule of thumb for reasonable test power; "fail to
  reject" is weak evidence, not proof of correct coverage. DEV's corrected
  Kupiec p-value (0.073) sits materially closer to the 5% rejection
  boundary than the pre-fix figure (0.717) suggested — this is weaker, not
  stronger, evidence for correct coverage than the pre-fix numbers implied.
- SPY's raw bytes are reused from a sibling repository's already-verified
  acquisition, not freshly pulled here (§1.1 / `SOURCE-GATE.md`'s
  "Additional dataset provenance" section).
- The Monte Carlo leg's vectorized implementation, while validated to
  floating-point tolerance against the reference implementation, is a
  distinct code path from this repository's stress-testing module.
- 2025 is a **HISTORICAL EVALUATION**, not an untouched holdout — SPY's
  2025 price history was already inspected once under this repository's
  superseded v1 study.

---

## 6. Conclusion

Both studies are standardized, hypothetical constructs evaluated on real
historical risk-factor paths, never a claim about deployed trading or real
historical options P&L. The central methodological contribution of this
publication pack is not a new empirical result but an accurate accounting
of a previously-reported empirical claim: the large Delta-Normal/Monte
Carlo-vs-Historical-Simulation divergence originally attributed to vol
regime and convexity was, in fact, mostly a units-conversion defect. With
that defect corrected, all three VaR/ES methods agree to within a
comparable order of magnitude, and the residual findings that survive
correction — a modest, persistent nonlinear-revaluation premium in Monte
Carlo's ES consistent with convexity, and a modest 2025 vol elevation with
a genuinely fat realized 99% tail — are smaller, more defensible, and more
useful than the withdrawn narrative they replace. Every number in this paper traces to a committed artifact listed
in `RESULT-SOURCE-MAP.md`.
