# Study B report: how much could the VaR backtests detect?

**Summary (for the hub findings table).** The published 95% VaR backtest uses
one forecast per monthly roll. Its non-rejections at n = 12 (VAL 2024, 2025)
come from a test that could not have detected the error sizes that matter in
practice. The repo's own Kupiec test at n = 12 rejects only if 3 or more of 12
forecasts breach. A VaR whose true breach rate is double the nominal 5% is
flagged 11% of the time; at triple the rate (15%), 26% of the time. 80% power
needs a true breach rate of about 6.5x nominal (32%). The test can never flag an
over-conservative VaR at n = 12, because zero breaches is not rejectable below
n = 38. At n = 95 (DEV), the minimum detectable effect (MDE) is 2.6x, and power
against 2x is 48%. Detecting 2x with 80% power takes n ≈ 224 forecasts. A daily
backtest over 2015–2025 (≈ 2,511 forecasts) would detect about 1.26x. On
clustering: the Christoffersen test at n = 12 has at most 14% power even under
strong persistence, so the published p = 1.000 values carry no information
about clustering. *Could have detected: a breach rate of roughly 6.5x nominal
(n = 12) or 2.6x nominal (n = 95). Did not detect anything. Smaller
mis-calibration is not ruled out.*

Design freeze: commit `b32632d2bde6708b1a856c77445868ae86f9c90e`, pushed to
`research/power-calibration` at 2026-10-20T06:47:54Z, before the full run.
Amendment A1 (harness bug, see `PROTOCOL.md`) is commit `7450b50`, pushed
before the reported run.

## 1. Question

The published study (`publication/options-risk-study/` §2.3) reports Kupiec and
Christoffersen non-rejections for a one-day 95% historical-simulation VaR,
with one forecast per monthly roll:

| Period | n | Breaches | Kupiec p | Christoffersen p |
|---|---:|---:|---:|---:|
| DEV | 95 | 9 | 0.073 | 0.167 |
| VAL 2024 | 12 | 0 | 0.267 | 1.000 |
| 2025 HISTORICAL EVALUATION | 12 | 1 | 0.627 | 1.000 |

What mis-calibration could these exact tests have detected at these n, and how
large would n need to be?

## 2. Design (frozen in `PROTOCOL.md`)

- **Tests.** The production functions `kupiec_pof_test`,
  `christoffersen_independence_test` and `conditional_coverage_test` from
  `src/options_risk/risk/backtesting.py` make every decision. Settings: confidence
  0.95 (the backtest's level), size 0.05. A supplementary Kupiec-only analysis
  covers 0.99.
- **Grid.** n ∈ {12, 95, 250, 1000, 2500}; true breach rate ∈ {1.0, 1.5, 2.0, 3.0}
  x 5%.
- **Kupiec.** Exact binomial enumeration: the production test is called for every
  possible breach count x = 0..n, and power is the sum of Binom(x; n, p) over the
  rejecting x. MDE is found on a 0.01 grid of multiples. The n needed is found by
  searching every n from 1 to 10,000.
- **Christoffersen / conditional coverage.** 20,000 simulated sequences per cell.
  Breaches follow a two-state Markov chain at the given marginal rate with lag-1
  autocorrelation ("persistence") ρ ∈ {0, 0.2, 0.5}. Seeds come from
  `SeedSequence([20261020, 0, multiple_idx, rho_idx, n])`.
- **Interpretation rules I1–I6** were fixed before the results (PROTOCOL §5).
  I1 is the key rule: a null counts as evidence against a multiple only if power
  ≥ 0.80 there.

## 3. Results

### 3.1 Kupiec POF, exact (95% VaR)

| n | Rejects iff breaches x | Size at 1.0x | Power 1.5x | Power 2x | Power 3x | MDE at 80% power |
|---:|---|---|---:|---:|---:|---|
| 12 | x ≥ 3 (zero breaches can never reject) | 0.020 (conservative) | 0.056 | 0.111 | 0.264 | 6.48x (32.4% breach rate) |
| 95 | x ≤ 1 or x ≥ 10 | 0.066 (liberal) | 0.180 | 0.482 | 0.919 | 2.59x (13.0%) |
| 250 | x ≤ 6 or x ≥ 20 | 0.059 (≈ nominal) | 0.416 | 0.879 | 1.000 | 1.88x (9.4%) |
| 1000 | x ≤ 37 or x ≥ 65 | 0.051 (≈ nominal) | 0.898 | 1.000 | 1.000 | 1.43x (7.2%) |
| 2500 | x ≤ 104 or x ≥ 147 | 0.054 (≈ nominal) | 0.999 | 1.000 | 1.000 | 1.26x (6.3%) |

At every grid n, the sustained MDE and the first-crossing MDE coincide.
Zero breaches first becomes rejectable at n = 38.

**n needed for 80% power** (exact search over n = 1..10,000). "Sustained" means
power stays ≥ 0.80 for every larger n. Power is saw-toothed in n because breach
counts are discrete.

| True multiple | n (sustained, headline) | n (first crossing) |
|---|---:|---:|
| 1.5x | 756 | 685 |
| **2x** | **224** | 191 |
| 3x | 67 | 59 |

Supplementary, 99% VaR (the config's secondary level, never backtested in the
study):

| n | Rejects iff | Size | Power 2x | Power 3x | MDE |
|---:|---|---:|---:|---:|---|
| 12 | x ≥ 2 (zero breaches can never reject) | 0.006 | 0.023 | 0.049 | 22.97x |
| 95 | x ≥ 4 (zero breaches can never reject) | 0.016 | 0.123 | 0.319 | 5.73x |
| 250 | x ≤ 0 or x ≥ 7 | 0.095 | 0.243 | 0.625 | 3.61x |
| 1000 | x ≤ 4 or x ≥ 17 | 0.055 | 0.782 | 0.997 | 2.03x |
| 2500 | x ≤ 15 or x ≥ 36 | 0.044 | 0.985 | 1.000 | 1.64x |

At 99%, n = 1,180 is needed for 80% power against 2x (sustained; first crossing
n = 1,015).

### 3.2 Christoffersen independence (simulated, 20,000 reps, MC SE ≤ 0.0036)

| Multiple | ρ | n=12 | n=95 | n=250 | n=1000 | n=2500 |
|---|---:|---:|---:|---:|---:|---:|
| 1x | 0 (size) | 0.002 | 0.012 | 0.015 | 0.087 | 0.052 |
| 1x | 0.2 | 0.019 | 0.240 | 0.543 | 0.977 | 1.000 |
| 1x | 0.5 | 0.063 | 0.580 | 0.922 | 1.000 | 1.000 |
| 2x | 0 | 0.009 | 0.033 | 0.077 | 0.052 | 0.049 |
| 2x | 0.2 | 0.032 | 0.328 | 0.698 | 0.998 | 1.000 |
| 2x | 0.5 | 0.111 | 0.817 | 0.991 | 1.000 | 1.000 |
| 3x | 0.5 | 0.144 | 0.910 | 0.999 | 1.000 | 1.000 |

The 1.5x rows and the 3x rows at ρ = 0 and 0.2 are in the JSON. At ρ = 0 the
independence test rejects at about its size whatever the multiple, as it should,
since it tests clustering only. Its size is very conservative at n ≤ 250
(0.002–0.016) and liberal at n = 1000 (0.087). Clustering is often untestable
at small n: 97.5% of null sequences at n = 12 contain no consecutive breach pair.

### 3.3 Conditional coverage (simulated)

| Multiple | ρ | n=12 | n=95 | n=250 | n=1000 | n=2500 |
|---|---:|---:|---:|---:|---:|---:|
| 1x | 0 (size) | 0.015 | 0.029 | 0.040 | 0.058 | 0.055 |
| 1x | 0.5 | 0.098 | 0.646 | 0.973 | 1.000 | 1.000 |
| 1.5x | 0 | 0.043 | 0.140 | 0.325 | 0.852 | 0.998 |
| 2x | 0 | 0.082 | 0.409 | 0.810 | 1.000 | 1.000 |
| 2x | 0.2 | 0.113 | 0.524 | 0.889 | 1.000 | 1.000 |
| 2x | 0.5 | 0.193 | 0.801 (borderline) | 0.988 | 1.000 | 1.000 |
| 3x | 0 | 0.200 | 0.885 | 0.999 | 1.000 | 1.000 |

CC MDE: at n = 12, > 3x at every ρ. At n = 95: 3x (ρ = 0, 0.2) and 2x (ρ = 0.5,
borderline at 0.801). Smallest grid n for 80% power against 2x at ρ = 0: 250.

### 3.4 Other pre-specified metrics

- **Kupiec under clustering.** At 1x with ρ = 0.5, Kupiec falsely rejects 26–30%
  of the time for n ≥ 95, against a nominal 5%. With ρ = 0.2 the rate is 11–13%.
  Clustering inflates the variance of the breach count. Kupiec's i.i.d. null does
  not allow for that, so its rejections are not clean evidence of a wrong rate
  when breaches cluster.
- **"Either test rejects"** (the published table reports Kupiec and independence
  side by side). Size at 1x with ρ = 0 is 0.022 / 0.080 / 0.071 / 0.137 / 0.103
  across the n grid. Reading "either rejects" as failure roughly doubles the
  false-alarm rate at large n.

### 3.5 Internal checks (PROTOCOL §4.6): all pass

- (a) All 3.6M production calls in the simulation, and every enumerated Kupiec
  call, return finite p-values with `reject_null == (p < 0.05)`.
- (b) In every replicate, the CC LR equals Kupiec LR + independence LR.
- (c) Simulated Kupiec power agrees with exact power (max |z| = 1.40, tolerance 4).
- (d) Full enumeration equals the two-tail threshold form at every grid n.
- **No production-code defect was found.** The off-nominal sizes above come from
  discreteness and the chi-square approximation at small n, not from coding errors.

## 4. Interpretation (rules I1–I6)

**Compatibility of the published counts** (I4). This inverts the production
Kupiec test over hypothesised breach rates: these are the true rates the test
would not reject given the observed count.

| Period | n | Breaches | Kupiec power at 2x / 3x | Compatible true breach-rate multiples |
|---|---:|---:|---|---|
| DEV | 95 | 9 | 0.482 / 0.919 | 0.94x – 3.28x (4.7% – 16.4%) |
| VAL 2024 | 12 | 0 | 0.111 / 0.264 | 0 – 2.95x (0% – 14.8%) |
| 2025 | 12 | 1 | 0.111 / 0.264 | 0.10x – 6.37x (0.5% – 31.9%) |

**What the 2024 and 2025 non-rejections do not establish.**
- They do not establish that the VaR is correctly calibrated.
- With 12 monthly forecasts, the Kupiec test was more likely than not to miss a
  true breach rate of 1.5x, 2x or 3x nominal (power 6%, 11%, 26%; I1). It does
  not rule out anything below about 6.5x.
- The test is conservative at this n (size 2.0%; I2).
- It cannot flag an over-conservative VaR at all, because zero breaches is not
  rejectable at n = 12 (I3). VAL 2024's 0/12 therefore says nothing against an
  overly cautious model.
- The 2025 count of 1/12 is consistent with true breach rates from 0.5% to 32%.
- The Christoffersen p = 1.000 values carry essentially no information about
  clustering (I5). Independence-test power at n = 12 is ≤ 0.144 in every cell.

**What they do establish.** They only exclude gross failure:
- The production test would have caught a true breach rate of about 32% or more
  (≈ 4 breaches in 12) with at least 80% probability.
- The 2025 data alone are incompatible, at the 5% level, with a rate above about
  6.4x nominal.

**DEV (n = 95).** Power against 2x is 48%, so the DEV non-rejection does not
rule out a doubled breach rate. It is evidence only against multiples of about
2.6x and above. The observed 9.5% breach rate and p = 0.073 sit inside a
compatible range of 0.94x–3.28x. In other words, the DEV data are compatible with
an accurate VaR and with a breach rate three times too high. The Kupiec test is
slightly liberal at this n (size 6.6%). For clustering at n = 95: the
independence test reaches 80% power only for strong persistence (ρ = 0.5)
combined with an elevated rate (≥ 2x). At ρ = 0.2 its power is ≤ 0.37.

**What a daily backtest would give.** The committed daily-cadence backtests of
the same SPY history have 2,011 (DEV), 251 (2024) and 249 (2025) forecasts,
2,511 in total. At these n the production Kupiec test has the following MDE
(80% power):

| Period | n | MDE | Power at 1.5x |
|---|---:|---|---:|
| DEV, daily | 2,011 | 1.30x | 0.996 |
| 2024, daily | 251 | 1.87x | 0.42 |
| 2025, daily | 249 | 1.89x | 0.41 |
| All periods, daily | 2,511 | 1.26x | 0.999 |

A single daily year (n ≈ 250) already detects 2x with about 88% power. That is
eight times the power of the monthly n = 12 design.

Per I6, none of this changes a published result. The non-rejections stand as
reported. This report adds the power statement they lacked.

## 5. Limitations

- **Breach model.** Breaches are modelled as a stationary first-order Markov chain.
  Real VaR failures can have regime-dependent rates, longer memory, or dependence
  on the VaR level. The monthly published sample is also 21 sessions apart, so
  lag-1 persistence at that spacing is probably weaker than the ρ values studied.
- **Power, not truth.** Power describes the test's ability under the stated
  alternatives. It does not estimate the published VaR model's actual breach rate.
- **Grid resolution.** Simulated MDEs and the n needed are at grid resolution
  only: multiples {1, 1.5, 2, 3} and the five n values. Kupiec results are exact
  on a 0.01-multiple grid and for every n up to 10,000.
- **ES not covered.** ES backtests are not part of the published design and are
  not calibrated here.
- **Size approximation.** Size is taken from the production chi-square p-values.
  An exact or Monte Carlo p-value would change both size and power at small n.
  Calibrating that alternative was out of scope.

## 6. Reproduction

From the repo root with the locked environment (Python 3.12,
`pip install -r requirements-lock.txt && pip install -e . --no-deps`):

```
python -m research.power.var_backtest_power --workers 4
```

This writes `results/power/var_backtest_power.json` and
`results/power/var_backtest_power.png` in about 5 minutes on 4 cores.
`--workers` affects wall time only. Every field except `run_info` is
deterministic. Smoke version (under 30 s, in the fast suite):
`python -m pytest -q tests/test_power_var_backtest.py`.

Figure: `results/power/var_backtest_power.png`. Panel A: Kupiec exact power for
every n from 1 to 2,500. Panel B: conditional coverage. Panel C: independence.
Lines show the 4 multiples; in B and C, solid is ρ = 0 and dashed is ρ = 0.5.
