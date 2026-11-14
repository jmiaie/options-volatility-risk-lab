# Study B protocol: power / null calibration of the VaR backtests

Version 1.0, frozen 2026-10-20 in the design-freeze commit (commit 1 on branch
`research/power-calibration`), pushed BEFORE the full computation was run.
Any later change is recorded under **Amendments** at the end of this file, with
a date and a reason.

## 1. Question

The published historical study (`publication/options-risk-study/`, §2.3;
`tables/kupiec_christoffersen.csv`) backtests a one-day 95% historical-simulation
VaR on one forecast per monthly roll and reports non-rejections in every period:

| Period | n forecasts | Breaches | Kupiec p | Christoffersen p |
|---|---:|---:|---:|---:|
| DEV 2016-2023 | 95 | 9 | 0.073 | 0.167 |
| VAL 2024 | 12 | 0 | 0.267 | 1.000 |
| 2025 HISTORICAL EVALUATION | 12 | 1 | 0.627 | 1.000 |

For each design (n = 12, n = 95, and larger counterfactual n), what mis-calibration
could the repo's own tests have detected? This is a calibration of the existing
design. It is not a new evaluation of 2025 data, it changes no frozen artifact, and
it changes no published conclusion.

## 2. Tests calibrated (production code, not re-implementations)

All accept/reject decisions come from `src/options_risk/risk/backtesting.py`:

- `kupiec_pof_test`: Kupiec POF, LR ~ chi2(1).
- `christoffersen_independence_test`: first-order Markov independence LR ~ chi2(1).
- `conditional_coverage_test`: Kupiec LR + independence LR ~ chi2(2).

The published study calls the first two with `CONFIDENCE_LEVELS["primary"] = 0.95`
(`src/options_risk/historical_risk_study_v2.py`, `run_nonlinear_portfolio_study`) and
the production default `significance_level = 0.05`. Conditional coverage is not in
the published table. It is calibrated here because it is the repo's implemented
joint test.

## 3. Fixed parameters

| Parameter | Value |
|---|---|
| VaR confidence level (primary) | 0.95 → nominal breach rate p0 = 0.05 |
| VaR confidence level (supplementary, Kupiec exact only) | 0.99 (the config's secondary level; computed in the study but never backtested) |
| Test size | 0.05 (passed explicitly; equal to the production default) |
| n grid | {12, 95, 250, 1000, 2500} |
| True breach-rate multiples | {1.0, 1.5, 2.0, 3.0} × p0, i.e. 5%, 7.5%, 10%, 15% |
| Persistence (Christoffersen simulation) | ρ ∈ {0, 0.2, 0.5} |
| Replications per simulated cell | 20,000 (≥ 10,000 required). Monte Carlo SE ≤ 0.0036 |
| Master seed | 20261020 |
| Per-cell seed | `SeedSequence([20261020, 0, multiple_idx, persistence_idx, n])`, independent of grid order and worker count |
| Power target for MDE | 0.80 |
| Fine multiple grid (Kupiec MDE) | 1.00 to 1/p0 in steps of 0.01 (20.00 at 95%, 100.00 at 99%) |
| n search range (Kupiec n needed) | n = 1 … 10,000, for multiples {1.5, 2.0, 3.0} |
| Size classification band | conservative < 0.04 ≤ approximately nominal ≤ 0.06 < liberal |

## 4. Methods

### 4.1 Kupiec POF: exact binomial enumeration

For each n and level, call `kupiec_pof_test` on a breach vector with x breaches
for every x = 0 … n. The test depends only on (n, x), so ordering does not matter.
The calls give the exact rejection set R(n). Then

power(n, m) = Σ_{x ∈ R(n)} Binom(x; n, m·p0).

At m = 1.0 this is the exact size. For the n search (1 … 10,000) and the
power-vs-n curve, R(n) is found as two tails {x ≤ x_lo} ∪ {x ≥ x_hi}, by bisection
on the production decision on each side of ⌊n·p0⌋. This relies on the Kupiec LR
being convex in x. It is checked against full enumeration in the unit tests
(n = 1 … 150, 251, 499, at both levels) and at every grid n in the run. A mismatch
is recorded in the JSON (`enumeration_matches_threshold_form`).

### 4.2 Christoffersen and conditional coverage: simulation

Breaches follow a stationary two-state Markov chain with marginal rate p = m·p0
and lag-1 autocorrelation ρ ("persistence"):
π01 = P(breach | no breach) = p(1 − ρ), π11 = P(breach | breach) = p + ρ(1 − p).
The first state is drawn from Bernoulli(p). ρ = 0 gives i.i.d. Bernoulli(p).
In each of the 4 × 3 × 5 = 60 cells, 20,000 sequences are drawn. Each sequence is
passed to all three production functions. Rejection counts are recorded for:
independence, conditional coverage, Kupiec (simulated), and "either Kupiec or
independence rejects" (the published table reports both tests side by side).

### 4.3 Metrics

- Power per (test, n, multiple, ρ), with Monte Carlo SE √(p̂(1−p̂)/R) for simulated cells.
- Size check: rejection rate at multiple 1.0 (and ρ = 0 for the simulated tests).
  Exact for Kupiec. Classified with the §3 band.
- Kupiec rejection region per n, including whether zero breaches can ever reject,
  and the smallest n at which they can.
- Under ρ > 0 at multiple 1.0, the Kupiec rejection rate is reported as a
  false-rejection rate under clustering. The marginal rate is still correct there.

### 4.4 MDE definitions (fixed before results)

1. **Kupiec MDE(n)**: the smallest multiple m on the fine grid with exact power
   ≥ 0.80 that stays ≥ 0.80 for every larger grid multiple ("sustained").
   The first crossing is reported as a secondary figure. Headline at n = 12 and
   n = 95. Reported for every grid n and both levels.
2. **Simulated-test MDE(n, ρ)** (conditional coverage, independence): the smallest
   multiple in {1.0, 1.5, 2.0, 3.0} with power ≥ 0.80 (m = 1.0 is excluded at ρ = 0
   because it is the null), else "> 3". A cell within 2 SE of 0.80 is flagged
   "borderline".
3. **n needed to detect 2×**: Kupiec uses the smallest n in 1 … 10,000 with exact
   power ≥ 0.80 for that n and every larger n in range (sustained; headline). The
   first crossing is secondary. Also reported for 1.5× and 3×. Conditional coverage
   and independence use the smallest grid n with power ≥ 0.80, at grid resolution
   only.

### 4.5 Interpretation aids from committed artifacts (read-only)

- **Published periods**: n and breach counts are read from the three committed v2
  result JSONs, with their sha256 recorded. The production Kupiec p-value is
  recomputed and must match the published value. The production Kupiec test is
  inverted over hypothesised rates p_h = m·p0 (m = 0.01 … 19.99, step 0.01;
  `confidence_level = 1 − p_h`). The non-rejected range of m is the set of true
  breach rates the observed count is compatible with.
- **Daily-backtest counterfactual**: daily forecast counts for the same SPY history
  are taken from the committed v1 daily backtests (`equity_rolling_hs_var_backtest.n_forecasts`:
  DEV 2011, VAL 2024 251, 2025 249, total 2511 ≈ 2,500). They are used only as n.
  Exact Kupiec power and MDE are computed at those n.

### 4.6 Internal checks (fixed before results)

(a) Every production result has a finite p-value, and `reject_null == (p_value < 0.05)`.
(b) The conditional-coverage LR equals Kupiec LR + independence LR (to 1e-9).
(c) Simulated Kupiec power at ρ = 0 agrees with exact power within 4 SE in every
cell. This validates the harness, not the production code.
(d) Threshold form = full enumeration at every grid n.
A failure of (a) or (b), or any other production-code anomaly, is reported as a
finding with evidence. Production code is not changed in this study.

## 5. Interpretation rules (written before any results)

- **I1 (what a null rules out).** A published non-rejection at sample size n counts
  as evidence against a true multiple m only if the production test's power at
  (n, m) ≥ 0.80. If power < 0.80, the report must say the non-rejection "does not
  rule out" m. If power < 0.50, it must also say the test was "more likely than not
  to miss" m.
- **I2 (size).** Each test's size at multiple 1.0 is labelled conservative,
  approximately nominal, or liberal per §3. A conservative test is noted as further
  reducing power.
- **I3 (low side).** If the Kupiec lower rejection region at n is empty, the report
  states that at that n the test cannot flag an over-conservative VaR (too few
  breaches), however conservative it is.
- **I4 (compatibility).** For each published period, the report states the range of
  true breach-rate multiples that the production Kupiec test does not reject given
  the observed count.
- **I5 (clustering).** If independence-test power at n ≤ 95 is below 0.80 for every
  multiple and persistence, the report states that the published Christoffersen
  non-rejections carry essentially no information about clustering at that n.
- **I6 (no change to conclusions).** The report adds power statements only. It does
  not re-label, re-tune or overturn any published result.

## 6. Outputs and reproduction

- `results/power/var_backtest_power.json`: all grid cells, seeds, counts, checks.
  `run_info` (git SHA, versions, wall time) is excluded from the determinism claim.
- `results/power/var_backtest_power.png`: one figure, power vs n per multiple
  (A Kupiec exact; B conditional coverage; C independence; ρ = 0 solid, ρ = 0.5 dashed).
- `research/power/REPORT.md`.
- Full run, from the repo root: `python -m research.power.var_backtest_power --workers 4`
  (`--workers` changes only wall time, not results).
- Smoke run (in the fast test suite, under 30 s): `tests/test_power_var_backtest.py::test_smoke_run_under_30s`
  (n ∈ {12, 95}, 500 reps, n search up to 300).

## Amendments

**A1 (2026-10-20, after the first full run, before any results were committed).**
Harness bug, not a design change. At the top of the fine multiple grid,
`m * (1 - 0.95)` evaluates to 1.0000000000000009 because `1 - 0.95` is
0.050000000000000044 in floating point. `scipy.stats.binom` returns NaN for
p > 1. The NaN made the "sustained" Kupiec MDE (§4.4 item 1) come out empty
(`null`) in every cell. `power_from_thresholds` now clips p to [0, 1], which is
exact because the intended rate is 1.0, and a regression test covers the case.
Nothing else in the design changed: grids, seeds, replications, definitions and
rules are untouched. The full run was repeated in full. All simulated counts
were byte-identical to the first run, as the per-cell seeds guarantee. The
first-crossing MDEs, all power values at the grid multiples, and the n-search
results did not depend on the top grid point and were unchanged.
