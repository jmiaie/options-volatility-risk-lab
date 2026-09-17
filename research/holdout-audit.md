# Holdout audit — Options Directive #9 (2025 calendar year)

**Repository:** `jmiaie/options-volatility-risk-lab`  
**Branch:** `research/historical-risk-validation`  
**Audit date (PT):** 2026-09-15  
**Holdout window under D9:** calendar **2025-01-01 ≤ t < 2026-01-01**  
**Dataset ID (planned):** `yf_options_risk_underlyings_daily_2015_2025_v1`

## CURRENT D9-C 2025 CLASSIFICATION (read this first)

**PREVIOUSLY INSPECTED / HISTORICAL EVALUATION.**

The original **CLEAR** verdict directly below was accurate on the date it
was written (2026-09-15, before this study's 2025 evaluation had been
executed at all). It is **no longer the current status** and is preserved
below as a dated historical record, not deleted or edited in place. Once
v1's `options_hist_risk_v1_holdout_2025` executed (see "Post-freeze holdout
execution" below) and v2 was built as the authoritative rebuild reusing the
same underlying SPY history, calendar-2025 outcomes for this study's
universe had already been inspected once. Per Directive #9's own
classification rules, that makes every subsequent 2025 result here —
including the corrected `options_hist_risk_v2_historical_evaluation_2025`
artifact (see the next-session backtest fix, 2026-09-17) — **`HISTORICAL
EVALUATION`**, never an untouched final holdout, and never re-labeled back
to `CLEAR`.

## Verdict (as of the original 2026-09-15 audit — historical record, superseded above)

**CLEAR** — no evidence that calendar-year **2025** market data was previously inspected, tuned against, or used for empirical evaluation / performance claims in this repository.

## Scope searched

| Surface | Method | Finding |
|---|---|---|
| Working tree (src, tests, docs, research, results, examples, README) | recursive text search for `2025` / `holdout` | Only this audit scaffold / D9 placeholders; no empirical 2025 metrics. Prior research reports use synthetic examples only. |
| Results tree | listed `results/*` | Synthetic example JSON under `results/` from D4 examples; no historical OOS/VaR packs for calendar 2025. |
| Research docs | `research/option-pricing-and-hedging.md`, `research/portfolio-tail-risk.md` | Synthetic-only methodology reports; no market 2025 evaluation. |
| Data loader | `options_risk.data.chain` | Synthetic chain helpers only; optional yfinance extra not previously exercised for a pinned 2015–2025 study. |
| Tests | `tests/` | Unit/synthetic fixtures for pricing, hedging, VaR/ES, backtesting — no real-market 2025 packs. |
| GitHub code search (session) | empirical 2025 evaluation artifacts | **null** |

## Classification rules applied

- **CLEAR:** holdout calendar window not used for model selection, hyperparameter tuning, benchmark cherry-picking, or reported historical performance.
- **PREVIOUSLY INSPECTED:** any committed notebook/result/config that evaluates or plots 2025 returns/vol/VaR for research decisions.

Copyright / changelog year strings do **not** count as empirical holdout inspection.

## Data scope (explicit; not expanded mid-study)

**Underlyings only** via free `yfinance` daily OHLCV for liquid index ETFs commonly used as options underlyings (**SPY, QQQ, IWM**). No paid options tapes, no invented option panels, no CBOE/OPRA reconstruction. Hedging-error studies use the existing GBM discrete-hedge simulator calibrated to **empirically estimated realized volatility** from underlyings — not historical listed-option paths.

## Restrictions until FINAL CONFIGURATION FROZEN

1. Do **not** evaluate models on 2025 for final claims.
2. Development / validation work uses **2015–2023** (formation/dev) and **2024** (validation) only, once data is frozen.
3. Pre-registered experiment configs under `configs/experiments/` remain **`not-yet-frozen-for-holdout`** until development+validation complete and a tracker `FINAL CONFIGURATION FROZEN` record exists on Issue #3.

## Sign-off

| Field | Value |
|---|---|
| Holdout status | **CLEAR** |
| Prior empirical 2025 evaluation artifacts | **null** (none found) |
| Ready for acquisition + pre-registration | **yes** |

## Post-freeze holdout execution

YAML status was set to `frozen-for-holdout` after formation+validation; calendar-2025 evaluation may then be run once under frozen config `options_hist_risk_v1` (experiment `options_hist_risk_v1_holdout_2025`). Tracker confirmation: **FINAL CONFIGURATION FROZEN — Options D9-C** on Issue #3 (https://github.com/jmiaie/quant-research-portfolio/issues/3#issuecomment-5691759004). No retune after freeze.

## Post-execution code defect found (2026-09-16) — partial, scoped correction

Independent code review of `src/options_risk/historical_risk_study.py` (after
the holdout above had already executed) found that
`equity_and_option_var_snapshot` — the one-shot HS + delta-normal VaR/ES on
the stylized equity+option book — shocked the book, and set its
delta-normal factor vol, using the **eval period's own returns**
(`eval_rets`), not a window of returns dated before the eval period's first
bar. `historical_simulation_var`'s own docstring documents the required
contract ("uses only a rolling window of *past* returns"); this call site
violated it. Concretely: the "as of the start of the 2025 holdout" VaR
estimate was partly computed from market moves realized *later in 2025* —
information a real position holder would not have had yet. This is a
look-ahead, not a retune-on-observed-outcomes issue (it was found by
reading the code against its own documented contract, not by inspecting or
reacting to the 2025 numbers themselves), but it means the
`stylized_option_book_var` component of the already-executed
`options_hist_risk_v1_holdout_2025` (and `_val_2024`, `_dev_formation`)
artifacts needs re-execution before its numbers can be trusted.

**Scope of the defect, precisely:**
- **Affected:** `stylized_option_book_var.historical_simulation.{var,es}` and
  `stylized_option_book_var.delta_normal.{var,es}` in all three committed
  result artifacts (dev_formation, val_2024, holdout_2025).
- **Not affected:** `realized_vol` (per-symbol and primary),
  `equity_rolling_hs_var_backtest` (the Kupiec/Christoffersen-tested rolling
  backtest was already correctly point-in-time — `hist = r.iloc[i-lookback:i]`
  never includes the day being forecast), and `discrete_hedging_error`
  (a separately-simulated GBM path study, not affected by this call site).

Fixed in commit `e6a2aa4` on this branch: shocks/factor-vol now come from
the trailing formation-period window (`seed_rets`, the same pre-eval-period
data already used to seed the rolling backtest), with a regression test
proving the snapshot no longer depends on the eval period's own returns.
**Re-execution of the three artifacts is blocked in this environment** (no
raw data locally — same acquisition constraint as the rest of Directive #9's
work); the existing artifacts' `stylized_option_book_var` numbers should be
treated as unreliable until regenerated under the fixed code.

## v2 AUTHORITATIVE rebuild and 2025 execution (2026-09-17)

The v1 study above remains preserved, unmodified, as EXPLORATORY /
NON-CONFORMING (per Directive #9's own classification — wrong dataset IDs,
no FRED integration, GBM-simulated hedging, no standardized nonlinear
portfolio, single-method/single-confidence VaR). A new AUTHORITATIVE v2
study was built from Directive #9's own D9-C spec text: real
historical-path hedge replay, point-in-time DGS3MO/VIXCLS, the standardized
nonlinear portfolio, three-method/two-confidence VaR/ES (including a
50,000-sim Monte Carlo full revaluation), and Kupiec/Christoffersen
backtesting. See `research/historical-volatility-and-tail-risk.md` for the
full report and `configs/experiments/options_historical_risk_study_v2.yaml`
for the frozen (on creation, per §4 of that report) configuration.

Because SPY 2025 was already inspected once under v1
(`options_hist_risk_v1_holdout_2025`), the v2 2025 result is labeled
**`HISTORICAL EVALUATION`**, per Addendum 13 — **not** `UNTOUCHED FINAL
HOLDOUT`, and the study was not shifted to 2026 (reserved program-wide) to
manufacture an untouched window. All three periods (DEV 2015-2023, VAL
2024, HISTORICAL EVALUATION 2025) were executed in this session under the
already-frozen v2 config; results are committed at
`results/historical_risk/options_hist_risk_v2_{dev_formation,val_2024,historical_evaluation_2025}.json`.

## v2 post-execution defect found and corrected (2026-09-17) — Kupiec/Christoffersen backtest realized-return alignment

Independent review of `src/options_risk/historical_risk_study_v2.py`'s
`run_nonlinear_portfolio_study` (after the v2 execution above had already
run) found that the Kupiec/Christoffersen backtest compared each monthly
roll's 95% VaR forecast against the realized return **ending on the roll
date itself** — already fully realized before the roll, not a next-session
outcome — instead of the return from the roll date to the next trading
session. The bug was purely positional-index arithmetic
(`returns.iloc[ret_pos_val]` landed one session too early once
`log_returns`'s leading-NaN drop shifts its index); the VaR forecast inputs
themselves were always computed strictly from history before the roll, so
this was a backtest-alignment defect, not a future-leak in the risk model.
This is a mechanical implementation defect found by reading the code
against its own stated intent ("Next-session realized P&L vs this roll's
95% VaR forecast"), not by reacting to the 2025 numbers themselves — the
same standard applied to the v1 look-ahead defect above.

Fixed with a date-keyed lookup (`full_prices.index[idx_pos + 1]` →
`returns.loc[that date]`, with a strict existence check and no silent
fallback) plus 5 new regression tests in
`tests/test_historical_risk_study_v2.py::TestNextSessionBacktestAlignment`
proving the fix (a deterministic case where the two definitions produce
different breach classifications; the next-session mapping correctly skips
weekends; a roll with no next session is excluded from the backtest count,
not fabricated; the VaR forecast itself is provably unaffected by the
next-session outcome). All three v2 artifacts (DEV, VAL 2024, 2025
HISTORICAL EVALUATION) were regenerated under the fix; every field except
the Kupiec/Christoffersen backtest section is byte-identical to the
pre-fix artifacts (verified by full field-level diff, not just spot-check).
Pre-fix artifacts preserved at
`results/historical_risk/superseded_next_session_backtest_fix/`, not
deleted. Full before/after numbers in
`research/historical-volatility-and-tail-risk.md` §6.3. No parameter,
threshold, or methodology was changed in response to the corrected
numbers, and 2025 remains labeled `HISTORICAL EVALUATION` throughout.
