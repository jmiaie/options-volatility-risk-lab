# Holdout audit — Options Directive #9 (2025 calendar year)

**Repository:** `jmiaie/options-volatility-risk-lab`  
**Branch:** `research/historical-risk-validation`  
**Audit date (PT):** 2026-09-15  
**Holdout window under D9:** calendar **2025-01-01 ≤ t < 2026-01-01**  
**Dataset ID (planned):** `yf_options_risk_underlyings_daily_2015_2025_v1`

## Verdict

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
