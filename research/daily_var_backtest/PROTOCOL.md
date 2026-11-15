# N2: daily VaR and ES backtest of the options book, with volatility and time risk

**Status: FROZEN 2026-11-15**, approved by the owner. This file was committed and pushed before
any data for this study was fetched and before any result was computed. Its commit hash and push
time are recorded in the report. Any later change is an amendment, dated and listed in the report.

Classification when run: **PREVIOUSLY INSPECTED / HISTORICAL EVALUATION.** Every SPY date was used
in the published study. Only the test design is new.

**Prior exposure.** Daily spot-only 252-day HS VaR breaches of SPY over these dates are already
known: the committed v1 results (`results/historical_risk/options_hist_risk_v1_*.json`, 2,511
forecasts). M1's spot quantile is therefore partly pre-inspected. Neither M2 nor any result with
volatility or time risk has been computed.

## 1. Why this study

The published options study backtests a one-day 95% Historical Simulation (HS) VaR with one forecast
per monthly roll: n = 95 (DEV), 12 (VAL 2024), 12 (2025). Two problems make its non-rejections
uninformative.

1. **Too few forecasts.** The power study (`research/power/REPORT.md`) shows the Kupiec test at
   n = 12 detects only a breach rate of about 6.5 times nominal, and at n = 95 about 2.6 times.
   A daily backtest over 2016–2025 (about 2,500 forecasts) detects about 1.26 times.
2. **Only spot moves.** Both the forecast (`risk/var.py:125-130`) and the realised P&L
   (`historical_risk_study_v2.py:744-756`) move spot only. Implied volatility and time to expiry stay fixed. The
   test therefore checks a quantile of SPY returns, not the risk of an option book (correction R8).

This study fixes both. The published n = 95 test had 48% power against a 2x breach rate (11% at
n = 12). This design has 80% power against about 1.3x (1.26x at size 0.05, 1.30x at the Holm
worst case of 0.05/3).

## 2. Question

For the published standardised book, re-marked daily with volatility and time decay, are one-day
VaR and ES forecasts correctly calibrated over 2016–2025?

- **Primary model M2 (two-factor HS):** full revaluation under the trailing 252 joint daily pairs of
  (SPY log return, change in log VIX), plus one day of time decay.
- **Reference model M1 (spot-only HS):** M2 with Δlog VIX_i = 0 and no time decay, the same book
  marked at VIX_t, scored against the same full realised P&L. This is the published method's
  scenario design applied to the new daily mark. It is expected to fail because it ignores
  volatility and time risk. It is not a test of the published study's own claim.

## 3. Data

| Series | Source | Use |
|---|---|---|
| SPY daily close | Yahoo Finance, dataset `yf_spy_daily_2015_2025_n2` (same price convention as the published study) | Spot |
| VIX close | FRED `VIXCLS`, dataset `fred_vixcls_daily_2015_2025_n2` | Implied-volatility proxy |
| 3-month Treasury | FRED `DGS3MO`, dataset `fred_dgs3mo_daily_2015_2025_n2` | Rate, point in time, as in the published study |

- The raw files are kept in a private repository. Public repositories get the manifest
  (source, retrieval time, sha256) and derived results only, never raw VIX or SPY values. This
  follows the approved data path and keeps new work clear of D3.
- Required citation: Chicago Board Options Exchange, CBOE Volatility Index: VIX [VIXCLS], retrieved
  from FRED, Federal Reserve Bank of St. Louis. FRED marks the series "Copyrighted: Citation
  Required" (checked 2026-11-14).
- Span: 2015-01-01 to 2025-12-31. 2015 is the 252-day warm-up. Forecast days run from the first day
  with 252 prior joint pairs to the last day with a next session.
- VIX is missing on some SPY trading days. A missing VIX is carried forward from the last
  observation known at the close of that day, as the published study does for DGS3MO, and counted
  in the report. A day with no VIX observation in the previous 5 sessions is dropped and counted.
  The book is held through a dropped day, whether it falls mid-life or on a roll day (the roll then
  moves to the next kept session). The next forecast's loss spans both sessions, and Christoffersen
  transitions across the gap are dropped.
- VIXCLS closes at 16:15 ET and SPY at 16:00 ET. The 15-minute mismatch is accepted and stated.

## 4. The book and the daily mark

- **Book (unchanged from the published study):** +100 SPY, −2 at-the-money calls and +2 95%-moneyness
  puts, 30 trading sessions to expiry, built on the first eligible session of each calendar month,
  q = 0, Black-Scholes pricing (`src/options_risk/pricing`).
- **Daily mark:** each option is priced at σ_t = VIX_t / 100, with the remaining time to expiry and
  r_t. The same σ is used for both strikes; skew is not modelled (see §9).
- **Holding:** the book is held from one roll to the next. A forecast is made at every close of its
  life except the roll day's own close, when the next book is built and forecast instead. One
  forecast per trading day.
- **Realised loss for day t:** L_t = −(V_{t+1} − V_t), with V repriced at S_{t+1}, σ_{t+1}, one
  session less to expiry and r_t (rate held fixed over the day, as in the forecasts).

## 5. Forecasts

On each forecast day t, with the trailing window W_t = the 252 most recent joint pairs ending at t
(including the pair ending on t, which is known at the close of t):

- **M2:** scenario i applies S·exp(r_i), σ·exp(Δlog VIX_i) and one session of time decay, and
  fully revalues the book. VaR_α and ES_α come from `compute_var_es` on the 252 scenario losses.
- **M1:** the same, with Δlog VIX_i = 0 and no decay.
- The published study's window ends at t−1 (`historical_risk_study_v2.py:445-450`). Only
  precondition P3 uses that window.
- `compute_var_es` takes the VaR as an interpolated quantile of 252 scenarios. Under a correct
  model the breach probability is therefore between 13/253 and 14/253 at 95% (5.41% in a 200,000-path
  simulation), and between 3/253 and 4/253 at 99% (1.37% simulated). P4 measures the resulting size
  directly.
- Levels: α = 95% (primary), 97.5% (ES, as in FRTB) and 99% (secondary).
- **No look-ahead.** A forecast at t uses only data dated t or earlier. Precondition P2 checks this.
- **NaN handling (fixes E2 for new code).** A NaN or non-finite VaR, ES or realised loss raises an
  error and stops the run. It is never counted as a non-breach.

## 6. Tests

Size 0.05 for every test. T1 and T2 are likelihood-ratio tests as implemented in production; T3 is
a two-sided z-test. Breach: L_t > VaR_t.

**Primary family (M2, pooled over all forecast days), Holm-adjusted across its three tests:**

| # | Test | Statistic |
|---|---|---|
| T1 | Kupiec POF, 95% | Production `kupiec_pof_test` |
| T2 | Christoffersen independence, 95% (as in the published study) | Production `christoffersen_independence_test` |
| T3 | Du–Escanciano (2017) unconditional ES backtest, 97.5% | Mean of H_t = (α′ − u_t)·1(u_t ≤ α′)/α′ with α′ = 0.025, against its null mean α′/2 and variance α′(1/3 − α′/4)/n |

**Randomised PIT for T3.** u_t = (R_t + V_t) / 253, where R_t is the number of day t's 252 scenario
losses at or above L_t and V_t ~ U(0, 1). Under a correct model u_t is exactly uniform. The
unrandomised share R_t/252 is biased: under a correct model it gives E[H] = 0.0145 against the null
of 0.0125, a size of about 22% at n = 2,500.

**Seeds** (numpy `SeedSequence`, fixed now): PIT draws V_t `[20261114, 1]`; Acerbi–Szekely Z2
simulation `[20261114, 2]`; P4 synthetic paths `[20261114, 3, path_index]`.

**Secondary (reported, not part of the primary decision):**

- M2 at 99%: Kupiec, and the Basel traffic-light zone over each 250-day block. Both are read
  against the model's own breach rate as well as 1%. The own rate is M2's pooled 99% breach rate on
  the P4 paths (about 1.37%, §5). The own-rate reading uses a two-sided exact binomial test, and
  zone thresholds recomputed at the own rate with the standard cumulative cut-offs (green below
  95%, yellow below 99.99%). Read against 1% alone, a correct model would be rejected far more
  often than 5% of the time.
- M2 conditional coverage at 95% (production `conditional_coverage_test`). It contains T1's
  statistic, so it is kept out of the primary family.
- Acerbi–Szekely Z2 at 97.5%, with its critical value simulated from each day's own scenario set
  (10,000 draws, fixed seed).
- M1 at 95% and 97.5%: T1–T3 against the same realised P&L.
- Each test by period: DEV (2016–2023), VAL 2024, 2025 HISTORICAL EVALUATION. Holm across the
  three periods within each test.
- Breach clustering by VIX regime (VIX below its 252-day median, or above). Descriptive only.

## 7. Preconditions (run first; if any fails, the study stops and the failure is reported)

- **P1 repricing.** With all shocks zero and no decay, scenario losses are 0 to 1e-9. With only
  decay, the loss equals a direct Black-Scholes reprice at T − 1/252 to 1e-9, and lies within 10% of
  the pricing module's annualised theta divided by 252. (Theta is instantaneous; a one-session
  reprice differs from it by a second-order term.)
- **P2 prefix invariance.** Forecasts computed on data truncated after forecast date number 1,500
  (the date is recorded) equal the first 1,500 forecasts of the full run exactly.
- **P3 published replication**, in two parts. The published SPY snapshot
  (`yf_spy_daily_2015_2025_v1`, sha256 `0c83ab20…6a63`) is not held in any repository, and a fresh
  Yahoo fetch does not hash-match it because Yahoo restates adjusted prices.
  - **P3a, code equivalence (required).** At every published roll date, with the published inputs
    (the book priced at trailing 20-session realised volatility, spot-only scenarios, the window
    ending at t−1), the harness's pricer and scenario code reproduce the production
    `historical_simulation_var` on the same data to 1e-6 relative. This ties the new code to the
    code that produced the frozen result.
  - **P3b, published values (required only with the published snapshot).** If the supplied SPY file
    has the sha256 above, the harness must also reproduce the published HS 95% VaR at every roll to
    1e-6 relative. Otherwise the differences are reported as data-vintage differences and are not a
    pass/fail condition.
- **P4 test calibration.** The full harness (book, daily mark, M2 forecasts, tests) runs on 2,000
  synthetic paths of 2,760 iid bivariate Student-t (ν = 4) pairs of (SPY log return, Δlog VIX),
  with correlation and scale fitted to DEV. Forecasts and realised losses are then exchangeable and
  continuous, so the check includes the 252-day estimation error and the discrete scenario set.
  P4 uses no realised loss from the real data. The rejection rates of T1, T2 and T3 are reported.
  - A test whose P4 rate lies in [0.03, 0.08] is used as specified.
  - A test whose rate falls outside that band is still run, but its p-value is replaced by its P4
    simulated p-value (the share of P4 statistics at least as extreme as the observed one). The
    switch is reported as a precondition outcome. The study does not stop.
  - If T3 is outside the band, the Acerbi–Szekely Z2 also moves into the primary family in its
    place, with its simulated p-value.

## 8. Decision and interpretation rules (fixed before any result)

- **D1.** M2 is "not rejected" if no Holm-adjusted primary p-value is below 0.05. It is "rejected"
  if any is.
- **D2.** A non-rejection counts as evidence against a breach-rate error of size m only where the
  power at the realised n is at least 0.80 (rule I1 of the power study). MDEs are reported at the
  Holm-adjusted level: for T1 from the exact binomial calculation at the realised n; for T3 from
  P4 paths in which losses above that day's 97.5% VaR are multiplied by k ∈ {1.5, 2}.
- **D3.** M1's results are read only as the size of the error from ignoring volatility and time risk
  together; the gap cannot be split between the two. They neither confirm nor withdraw anything in
  the published study.
- **D4.** Per-period results are secondary. A per-period rejection without a pooled one is reported
  as a lead, not a finding.
- **D5.** The study tests the risk model given the pricing convention in §4. It does not test real
  option P&L, because the book is marked at VIX rather than at traded option prices.

## 9. Known limits (stated in advance)

- VIX is a 30-day SPX variance-swap rate, not SPY's at-the-money or 95% implied volatility. With no
  skew, the puts are marked too cheap and their vega is misstated. Both the forecast and the
  realised P&L use the same convention, so the backtest is internally consistent but does not
  measure real hedging P&L.
- One book, one underlying, hypothetical positions.
- HS with a 252-day window reacts slowly to volatility shifts. A filtered-HS model is the obvious
  next comparison but is left out so the primary family stays at three tests.
- Data rest on Yahoo for SPY and FRED for VIX and rates. No second-source check for SPY (the Stooq
  check fails, see the 2026-11-14 status note).

## 10. Deliverables (options repository)

- `research/daily_var_backtest/PROTOCOL.md` (this document, frozen), `daily_var_backtest.py` (new
  harness that calls the production pricing and backtest functions), `run_daily_var_backtest.py`,
  `tests/test_daily_var_backtest.py` (preconditions P1, P2 and P4 on synthetic data, the NaN rule,
  and the Du–Escanciano statistic against a hand-computed case).
- `results/daily_var_backtest/daily_var_backtest.json`, `REPORT.md`, a README finding bullet and a
  hub correction entry. No frozen file changes.

## 11. Owner decisions (2026-11-15)

1. Run N2: approved.
2. VIX terms: research use with the citation; raw values kept private; only derived results and
   hashes are published. Accepted.
3. VIX as the implied-volatility proxy, with the limit in §9: accepted. No skew adjustment.
4. The published SPY snapshot is not available, so P3 rests on code equivalence (P3a). P3b is not
   run, and the differences to the published values are reported as data-vintage differences.

## References

- Kupiec, P. (1995). Techniques for verifying the accuracy of risk measurement models.
- Christoffersen, P. (1998). Evaluating interval forecasts.
- Du, Z. and Escanciano, J. C. (2017). Backtesting expected shortfall: accounting for tail risk.
  Management Science 63(4).
- Acerbi, C. and Szekely, B. (2014). Backtesting expected shortfall. Risk.
- Basel Committee on Banking Supervision (2019). Minimum capital requirements for market risk
  (FRTB), MAR32–MAR33.

## Review record

Draft reviewed 2026-11-14 from three angles (statistician, risk practitioner, research-integrity
sceptic) by an AI reviewer agent, with every code reference checked against the options
repository. Six blocking findings were applied: the randomised PIT, a P4 that includes estimation
error, the window and M1 definition, stated seeds, the P1 repricing check, and disclosure of the v1
daily results. The PIT bias (E[H] 0.0145 against 0.0125), the interpolated breach rates and the
Kupiec MDEs (1.26x; 1.30x at 0.05/3) were recomputed independently before being written here.
