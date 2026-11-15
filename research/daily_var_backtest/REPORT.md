# Daily VaR and ES backtest of the options book, with volatility and time risk — report

Frozen design: [`PROTOCOL.md`](PROTOCOL.md), committed as `c201e2ccfd414dfe16f5f05a4b048757ed56f4c0` and
pushed 2026-11-15T06:44:14Z, before any data for this study was fetched (data retrieved
2026-11-15T07:38:53Z) and before any result was computed (run 2026-11-15T07:39:52Z to 08:16:00Z).
Results: `results/daily_var_backtest/daily_var_backtest.json`. No amendments to the design.

**Classification: PREVIOUSLY INSPECTED / HISTORICAL EVALUATION.** Every SPY date was used in the
published study, and daily spot-only HS breaches over these dates were already known (v1 results).
Only the test design is new.

## Summary

**The two-factor HS VaR (M2) is not rejected.** Over 2,513 daily forecasts (2016–2025), none of the
three primary tests rejects after the Holm adjustment, so under rule D1 the model is "not rejected".

- **Coverage: not rejected.** 129 breaches of the 95% VaR (5.13%), against about 5.4% expected for
  a correctly specified 252-scenario model (protocol §5). Kupiec p = 0.76.
- **Clustering: no evidence of it.** Christoffersen independence p = 0.35.
- **Expected shortfall: borderline.** The ES test (Acerbi–Szekely Z2, which replaced the
  Du–Escanciano test under the pre-specified P4 rule, see below) gives p = 0.017 before adjustment
  and **0.0501 after Holm**. Its statistic exceeds its simulated 5% critical value before adjustment;
  after Holm it is not rejected, by a margin of 0.0001.

**The spot-only reference model M1 is rejected.** M1 applies the published study's scenario design
(spot moves only, no volatility moves, no time decay) to the same daily mark. Scored against P&L
that includes volatility and time, it has too few breaches (98, 3.90%; Kupiec p = 0.009) and strongly
clustered breaches (independence p = 6×10⁻⁷). Under rule D3 this measures the size of the error from
ignoring volatility and time risk together; the gap cannot be split between the two, and it neither
confirms nor withdraws any published result.

**What the non-rejection is evidence against (rule D2).** With n = 2,513, the coverage test had 80%
power against a breach rate of 1.30 times nominal (6.5% instead of 5%) at the Holm level, so the
result counts as evidence against a 95% breach-rate error of that size or larger. It says nothing
about smaller errors. For the tail, the P4 runs with losses beyond the 97.5% VaR scaled by 1.5 and 2
gave a rejection rate of 1.0 for the Du–Escanciano test with its simulated p-value; the protocol
computes this detectable effect for that test, not for Z2, which made the decision here.

## Preconditions

All four passed, so the tests below are valid under the protocol.

| | Check | Result |
|---|---|---|
| P1 | Zero shocks give zero loss; one session of decay equals a direct Black-Scholes reprice | Max zero-shock loss 0.0; decay versus direct reprice 1.1×10⁻¹² (theta/252 within 1.1%) |
| P2 | Forecasts on data cut after forecast 1,500 (2021-12-15) equal the full run's | Identical |
| P3a | The new code reproduces production `historical_simulation_var` at every published roll | 119 of 119 rolls, difference 0.0 |
| P3b | Exact match to the published VaR values | Not run: the published SPY snapshot is not available (owner decision 4). The differences are at most 0.25% and reflect Yahoo's restated prices |
| P4 | Size of each test on 2,000 synthetic paths with a correctly specified model | T1 4.6%, T2 5.3% (both in the [3%, 8%] band); **T3 0.4% (outside)** |

**P4 outcome for T3.** The Du–Escanciano test rejected only 0.4% of the time on correctly specified
paths, so it is far too conservative with 252 discrete scenarios. As the protocol requires, the
Acerbi–Szekely Z2, with its p-value simulated from each day's own scenario set (10,000 draws),
replaced it in the primary family. For reference, T3's own analytic p-value was 0.078 and its
P4-simulated p-value 0.0055.

## Primary result (M2, pooled, 95%)

| Test | Statistic | p | Holm-adjusted p |
|---|---:|---:|---:|
| T1 Kupiec POF | 0.093 | 0.760 | 0.760 |
| T2 Christoffersen independence | 0.860 | 0.354 | 0.707 |
| Z2 Acerbi–Szekely ES (97.5%), replacing T3 | 0.4375 (5% critical value 0.3605) | 0.0167 | **0.0501** |

n = 2,513 forecasts; 129 breaches of the 95% VaR. **D1: not rejected.**

## Reference model M1 (spot-only, no decay), pooled

| Test | p | Holm-adjusted p |
|---|---:|---:|
| T1 Kupiec POF | 0.0086 | 0.017 |
| T2 Christoffersen independence | 6.3×10⁻⁷ | 1.9×10⁻⁶ |
| T3 Du–Escanciano ES | 0.243 | 0.243 |
| Z2 Acerbi–Szekely ES (reported for comparison) | 0.057 | — |

98 breaches (3.90%). Conditional coverage p = 1.3×10⁻⁷.

## Secondary results (not part of the decision)

**By period, M2.** No test rejects in any period, before or after the Holm adjustment across periods.

| Period | n | Breaches (95%) | Kupiec p | Independence p | Du–Escanciano p |
|---|---:|---:|---:|---:|---:|
| DEV 2016–2023 | 2,012 | 105 | 0.655 | 0.285 | 0.130 |
| VAL 2024 | 252 | 13 | 0.908 | 0.693 | 0.455 |
| 2025 | 249 | 11 | 0.667 | 0.312 | 0.487 |

**Conditional coverage at 95%.** M2 p = 0.62; M1 p = 1.3×10⁻⁷.

**99% VaR, M2.** 46 breaches (1.83%).

- Against 1%: Kupiec p = 0.0002, exact binomial p = 0.0002.
- Against the model's own breach rate of 1.37% (from P4): exact binomial p = 0.058.
- Basel zones per 250-day block. Read against 1%: two red, three yellow and five green. Read against
  the own rate (green up to 6, yellow up to 11): two red, one yellow and seven green.
- The two red blocks start 2017-12-27 (13 breaches) and 2021-12-16 (12 breaches). They cover the
  February 2018 volatility spike and the 2022 sell-off.

These are secondary results (rule D4). Against the model's own rate the 99% excess is not
significant (p = 0.058); the breaches are concentrated in two stress years.

**Breaches by VIX regime (descriptive only).** With VIX above its trailing 252-day median, 106
breaches in 1,147 forecasts (9.2%). Below the median, 23 in 1,366 (1.7%). The pooled
breach rate is close to nominal, but it differs sharply between regimes. This is consistent with a
252-day window that reacts slowly (VaR too low after volatility rises, too high after it falls). The
independence test looks only at consecutive days and would not capture it. This was not a
pre-specified test; it is a lead for a follow-up, not a finding.

## What this changes

- **This backtest can see errors the published one could not.** At n = 12 the published test could
  detect only a breach rate of about 6.5 times nominal. Here the coverage test is evidence against a
  95% breach-rate error of 1.3 times or more for the two-factor model.
- **Leaving out volatility and time risk matters for this book.** M1, which leaves them out, is
  rejected on coverage and independence against full P&L. This quantifies the limitation described in
  correction R8; by rule D3 it neither confirms nor withdraws R8 or any published result.
- **No published number changes.** The published study, its tables and its corrections are
  unaffected.

## Limits

- **Not a holdout.** All dates were inspected before; only the test design was pre-specified.
- **VIX as the volatility proxy.** Both strikes are marked at VIX/100 with no skew. The backtest is
  internally consistent but does not measure real option P&L (protocol §9, rule D5).
- **One hypothetical book on one underlying.**
- **Data.** Yahoo for SPY (no second-source check) and FRED for VIX and the 3-month rate. The SPY
  series does not hash-match the published snapshot. The VIX and rate files match the published
  study's row and missing-value counts exactly.
- **The ES result sits at the decision boundary** (Holm-adjusted p = 0.0501). It is a non-rejection
  under the pre-specified rule and should be read as weak evidence either way, not as a clean pass.

## Data

| Dataset | Source | Rows | sha256 of file |
|---|---|---:|---|
| `yf_spy_daily_2015_2025_n2` | Yahoo Finance, yfinance 1.7.0 | 2,766 | `8d92d36da4e3f12dbf4d9056ccce5bc8e9fb2e5eddec151e3e3dc722ec6a54f8` |
| `fred_vixcls_daily_2015_2025_n2` | FRED VIXCLS | 2,870 | `0644f7e79440fff2551b71d812e1fecc4e0d8e365c2ec32c855f1d6a7bda5ed2` |
| `fred_dgs3mo_daily_2015_2025_n2` | FRED DGS3MO | 2,870 | `1a9399ac815de5641fc8956cedb88b4a81c61344935af839b27f15ac02380888` |

Raw files are kept private; this repository holds only hashes and derived results.

Chicago Board Options Exchange, CBOE Volatility Index: VIX [VIXCLS], retrieved from FRED, Federal
Reserve Bank of St. Louis; https://fred.stlouisfed.org/series/VIXCLS. Copyright Cboe.
Board of Governors of the Federal Reserve System (US), Market Yield on U.S. Treasury Securities at
3-Month Constant Maturity [DGS3MO], retrieved from FRED, Federal Reserve Bank of St. Louis.

## Reproduce

```bash
python research/daily_var_backtest/run_daily_var_backtest.py \
    --raw-dir /path/to/dir/with/SPY.csv,VIXCLS.csv,DGS3MO.csv \
    --manifest /path/to/manifest.json
```

A fresh acquisition will not hash-match these snapshots, so late decimals may differ.
`pytest tests/test_daily_var_backtest.py` checks the harness on synthetic data.
