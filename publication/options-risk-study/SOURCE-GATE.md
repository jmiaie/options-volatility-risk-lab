# SOURCE-GATE — D10-C Publication Pack

**Status**: source-of-truth gate for every fact used in this publication pack.
Nothing in `TECHNICAL-PAPER.md`, `CASE-STUDY.md`, or any other document in
`publication/options-risk-study/` may cite a number that is not traceable to
one of the 14 fields below (or to `RESULT-SOURCE-MAP.md`, which expands each
paper-level number to an exact JSON key path). This document does not
re-derive or re-verify the Grokbot audit claim in field 11; that claim is
reproduced verbatim as an external citation.

---

## 1. Program / directive citation and this study's place in it

This is **Directive #9 / #10, study D9-C / D10-C** of the multi-repo
quantitative-research remediation program tracked in
`jmiaie/quant-research-portfolio` Issue #3. D9-C was the defect-remediation
phase for this repository's historical volatility / hedging / nonlinear
portfolio VaR study; it produced the AUTHORITATIVE (v2) study documented in
`research/historical-volatility-and-tail-risk.md` and `research/holdout-audit.md`.
D9 (all repos, all streams) has been declared closed by an external
four-stream independent audit (field 11). **D10-C is a
PUBLICATION/COMMUNICATION phase**: this pack writes up already-accepted,
already-computed D9-C evidence for external readers. D10-C performs **no new
empirical work** — no retraining, no retuning, no re-acquiring data, no
rerunning any evaluation period (including 2025), and no alteration of any
existing result artifact, config, or source file. Every file under
`publication/options-risk-study/` is new; nothing outside that directory was
modified to produce it.

## 2. Repository and accepted HEAD

- **Repository**: `jmiaie/options-volatility-risk-lab`
- **This publication pack's branch**: `publication/options-risk-study`
- **Branch point / accepted HEAD SHA**: `db9cf44a04f1282f81ed11c7d145b5afe2db8d95`
  — commit message: *"D9-C P1: fix volatility-units mismatch in
  Delta-Normal/Monte Carlo VaR"* — this is the commit that fixed the defect
  described in field 9 below.
- **Immediate parent SHA** (verified via `git rev-parse
  db9cf44a04f1282f81ed11c7d145b5afe2db8d95^` in this session):
  `53277193f29a613d39d7e67983298eb832cf03d8` — commit message: *"D9-C P1: fix
  off-by-one in Kupiec/Christoffersen next-session return"*.
- This branch was created from `db9cf44...`, **not** from `main`. `main`'s
  tip at the time of writing is the still-open, unmerged D9-C remediation PR
  #3 on branch `research/historical-risk-validation`; this publication pack
  does not depend on, alter, or merge that PR. This pack's own PR targets
  `research/historical-risk-validation` as its base (not `main`) specifically
  so its diff is isolated to the new publication content only.

## 3. Experiment ID

`options_hist_risk_v2` — three periods: `dev_formation` (DEV, 2015-01-01 to
2023-12-31), `val_2024` (VAL 2024, 2024-01-01 to 2024-12-31), and
`historical_evaluation_2025` (2025-01-01 to 2025-12-31, classified
**HISTORICAL EVALUATION**, see field 12). Two studies per period: the
hedging experiment and the standardized nonlinear-portfolio VaR/ES study.

## 4. Dataset IDs and `dataset_canonical` sha256

All three verified independently in this session by reading
`data/manifests/*.json`'s own `sha256.dataset_canonical` field (not copied
from the task brief without checking):

| Dataset ID | Role | `dataset_canonical` sha256 |
|---|---|---|
| `yf_spy_daily_2015_2025_v1` | Underlying (SPY daily OHLCV) | `0c83ab20bf76ec39b97855ac393b7bc74363bd4ff373381f0a92842a2c7c6a63` |
| `fred_dgs3mo_daily_2015_2025_v1` | Short-rate proxy (3-Month T-Bill) | `31ad77f46517b4a51a2313ad86524d3f0f07634e4ca450ba2c387adbddf42a9f` |
| `fred_vixcls_daily_2015_2025_v1` | Vol context only (CBOE VIX Close) | `b727ab1751d4c9c180159cc1eb3358a2fef6ebf1abe15c74adb46f93019753b1` |

**SPY reuse-provenance disclosure (reproduced from
`data/manifests/yf_spy_daily_2015_2025_v1.json`'s own `acquisition_provenance`
field, verbatim in substance)**: these SPY bytes were **not freshly acquired
in this repository**. This session's own egress proxy returns an
organization-policy 403 for Yahoo Finance, so no fresh pull could be run
here. The exact bytes (sha256-verified to match) were already legitimately
acquired, hash-verified against its own frozen manifest, and are present in a
sibling Directive #9 repository — `jmiaie/Advanced_Algorithmic_Trading_Simulator_public`,
`data/raw/yf_stat_arb_etfs_daily_2015_2025_v1/SPY.csv` — using the identical
acquisition parameters this repo's own `scripts/acquire_yf_options_risk_underlyings_daily.py`
would use (`yfinance 1.7.0`, `start=2015-01-01`, `end=2026-01-01` exclusive,
`interval=1d`, `auto_adjust=True`). This is disclosed reuse, not a fresh
acquisition presented as new, and not fabrication. The two FRED series were
repackaged from a provisional combined snapshot
(`fred_macro_daily_2015_2025_v1`) into these two authoritative per-series
dataset IDs; the underlying bytes are unchanged from that prior acquisition —
only documentation was corrected (see
`research/historical-volatility-and-tail-risk.md` §2).

## 5. Config path and sha256

`configs/experiments/options_historical_risk_study_v2.yaml`
sha256 = `4bd18561466b5f85b09031868322929c8ad28bd9c2da9358ac3a106fdb725181`
(computed independently in this session via `sha256sum`, matches the value
supplied for this task).

## 6. Current / authoritative artifact paths and sha256 (all three, hashed independently)

| Period | Path | sha256 (computed this session) |
|---|---|---|
| DEV | `results/historical_risk/options_hist_risk_v2_dev_formation.json` | `6e840d4934ead483233aa83bebd232abd94b1652ed410f85408a5a898f5e5f26` |
| VAL 2024 | `results/historical_risk/options_hist_risk_v2_val_2024.json` | `4df81b2d7d6078f9f5bf2cb8526838291d2de249e96fe4cbdd7ed4b2a76ef0b8` |
| 2025 HISTORICAL EVALUATION | `results/historical_risk/options_hist_risk_v2_historical_evaluation_2025.json` | `b2c3594445b7f1a726be135cb5cb17f43f69d6a3a938657b3e4faca3dcb62799` |

The 2025 hash matches the value supplied for this task exactly; the DEV and
VAL 2024 hashes were computed fresh in this session (not supplied) and are
recorded here and in `publication/options-risk-study/tables/dataset_and_artifact_hashes.json`.

## 7. Superseded artifact paths (PRE-FIX, never primary evidence)

Two superseded sets, both preserved unmodified in the repository for audit
trail. **Neither is used as current evidence anywhere in this pack except
inside explicitly labeled PRE-FIX/SUPERSEDED-vs-CORRECTED comparison
sections.**

**Set A — `superseded_volatility_units_fix/`** (pre the fix at commit
`db9cf44`, the volatility-units defect — central to this pack):

| Period | Path | sha256 (computed this session) |
|---|---|---|
| DEV | `results/historical_risk/superseded_volatility_units_fix/options_hist_risk_v2_dev_formation.json` | `7bd4ea0c3a278c86c31e71fc265fda967d8d8a8ffb3481662f995e95576f459a` |
| VAL 2024 | `results/historical_risk/superseded_volatility_units_fix/options_hist_risk_v2_val_2024.json` | `3a8b75fdd52d17727409b99844426b75fc307a8d38df41f9dabeffd2d89e7918` |
| 2025 | `results/historical_risk/superseded_volatility_units_fix/options_hist_risk_v2_historical_evaluation_2025.json` | `8449bf6e20d2095ed564b693ff9567f46490b719de384d593078504710909a2f` |

**Set B — `superseded_next_session_backtest_fix/`** (pre the earlier
Kupiec/Christoffersen off-by-one fix at commit `5327719`):

| Period | Path | sha256 (computed this session) |
|---|---|---|
| DEV | `results/historical_risk/superseded_next_session_backtest_fix/options_hist_risk_v2_dev_formation.json` | `977b65a5c5ca2c9530e2f5f5759e44189740b9f09c7d2b8a10a33a7acdc64895` |
| VAL 2024 | `results/historical_risk/superseded_next_session_backtest_fix/options_hist_risk_v2_val_2024.json` | `3a8b75fdd52d17727409b99844426b75fc307a8d38df41f9dabeffd2d89e7918` |
| 2025 | `results/historical_risk/superseded_next_session_backtest_fix/options_hist_risk_v2_historical_evaluation_2025.json` | `cb44ec98d871e553209a25c14d0cbd776382a0c16990c2a2c01bb2463348ca9a` |

(Set B's VAL 2024 file is byte-identical to Set A's VAL 2024 file — both
hash to `3a8b75fdd5...` — because the volatility-units fix and the
backtest-alignment fix are sequential corrections to the same lineage of
artifacts and VAL 2024's Kupiec/Christoffersen breach sequence happened not
to change between the two fixes; see
`research/historical-volatility-and-tail-risk.md` §6.3 for the documented
explanation of why VAL 2024 is unaffected while DEV and 2025 are not.)

## 8. Methodology summary

**Study 1 — hedging experiment** (`simulate_delta_hedge_on_price_path`,
`src/options_risk/historical_risk_study_v2.py:178`): a standardized, short,
one-lot, ATM 30-trading-day European call delta-hedged by replaying the
*actual* historical subsequent 30 SPY daily closes (not a GBM simulation).
Initiated on the first eligible session of each calendar month; each episode
run at daily and weekly rebalancing crossed with GROSS/BASE/STRESS (0/1/5bp)
transaction-cost scenarios. Required label: **"Historical underlying-path
hypothetical option hedging experiment."**

**Study 2 — standardized nonlinear portfolio VaR/ES**
(`build_standardized_portfolio`, `historical_risk_study_v2.py:419`; rolled
monthly by `run_nonlinear_portfolio_study`, `historical_risk_study_v2.py:628`):
+100 SPY-equivalent shares, −2 ATM 30-session calls, +2 95%-moneyness
30-session puts. At every eligible monthly roll, three independent VaR/ES
methods at two confidence levels (95% primary, 99% secondary), 1-day
horizon:
- **Historical Simulation** — `historical_simulation_var`,
  `src/options_risk/risk/var.py:104` — full revaluation under the trailing
  252-session (primary) / 504-session (sensitivity) actual return
  distribution.
- **Delta-Normal** — `delta_normal_var`, `src/options_risk/risk/var.py:146` —
  linear (dollar-delta × per-period factor vol) parametric approximation.
- **Monte Carlo full revaluation** — `full_revaluation_mc_var_es`,
  `historical_risk_study_v2.py:472` — 50,000 iid-normal single-factor draws
  (seed 0), every draw fully repriced via Black-Scholes (vectorized
  reimplementation of the reference `options_risk.risk.var.monte_carlo_var`,
  `src/options_risk/risk/var.py:190`, validated to `1e-9` relative tolerance
  on a matched seed — see `tests/test_historical_risk_study_v2.py::TestFullRevaluationMcVarEs`).
- **Kupiec / Christoffersen backtest** — `kupiec_pof_test` and
  `christoffersen_independence_test`, `src/options_risk/risk/backtesting.py:74`
  and `:134` — one forecast per monthly roll's own next trading session
  (HS-primary 95% VaR vs. realized full-revaluation P&L).
Required label: **"Hypothetical nonlinear portfolio evaluated on historical
risk-factor paths."**

## 9. Volatility-units provenance

`trailing_realized_vol()` (`historical_risk_study_v2.py:144`) returns
**annualized** volatility (`std(daily log returns, ddof=1) * sqrt(252)`) —
correct as-is for Black-Scholes option pricing (paired with maturity `T`
already expressed in years). `annualized_vol20 = trailing_realized_vol(...)`
feeds BSM pricing in `build_standardized_portfolio`.
`daily_factor_vol20 = annualized_vol20 / sqrt(252)` feeds the one-day
Delta-Normal and Monte Carlo VaR/ES legs, both of which document their vol
parameter as **per one period** (one trading day) in their own docstrings
(`delta_normal_var`'s and `full_revaluation_mc_var_es`'s docstrings — see
`src/options_risk/risk/var.py:146` and `historical_risk_study_v2.py:472`).
Historical Simulation consumes no vol parameter at all (it resamples real
daily log returns directly) and is completely unaffected by this
distinction, as is the Kupiec/Christoffersen backtest (which draws its
forecast from Historical Simulation).

**Concrete verified example** — DEV, first eligible roll, roll date
**2016-02-01** (from
`results/historical_risk/options_hist_risk_v2_dev_formation.json`,
`nonlinear_portfolio_study.snapshots[0]`, independently re-read and
re-verified in this session — see `CASE-STUDY.md` for the full trace):

- `realized_vol_20d` (annualized) = **0.235506**
- `daily_factor_vol_20d` = **0.014836** = 0.235506 / √252 exactly
  (verified to 14 significant figures in
  `tables/case_study_dev_first_roll.json`'s
  `check_daily_equals_annualized_over_sqrt252` field)
- Same roll, 95% confidence, **corrected**: Delta-Normal VaR/ES =
  **213.10 / 267.23**; Monte Carlo VaR/ES = **226.61 / 292.31**; Historical
  Simulation VaR/ES = **137.71 / 192.51** (independently confirmed
  byte-identical pre- and post-fix — see `tables/case_study_dev_first_roll.json`'s
  `historical_simulation_unchanged: true` field).
- Kupiec/Christoffersen backtest results are confirmed byte-identical
  pre/post this fix in all three periods except for the fields the *other*
  (backtest-alignment) fix touched — the volatility-units fix never touches
  the backtest's inputs at all, since it draws its forecast from Historical
  Simulation, never from the vol-units-affected legs.

## 10. Known limitations and caveats

Pulled verbatim in substance from `research/historical-volatility-and-tail-risk.md`
§8 (not softened):

- No paid options tapes; no invented option panels — every option price
  comes from Black-Scholes-Merton off realized volatility.
- DGS3MO is a short-term Treasury constant-maturity yield proxy, never a
  full option discount curve; point-in-time, carry-forward only, never
  future-backfilled.
- **DGS3MO vintage disclosure**: this study uses FRED's standard `DGS3MO`
  series (not an ALFRED real-time vintage/release-calendar series); no
  future observation is ever backfilled, but publication/revision lag
  between an observation's dated value and its actual public availability
  is not separately modeled.
- VIXCLS is market-volatility context/reference only — never a pricing
  input, never described as this study's option's implied volatility.
- No discrete dividend modeling (`q=0.0` throughout, disclosed).
- No antithetic sampling in the Monte Carlo leg — disclosed, not silently
  omitted.
- Hedging episodes' 30-session windows overlap month-to-month; reported
  cross-episode means are over serially dependent, not independent, samples.
- The Kupiec/Christoffersen backtest's monthly cadence yields small samples
  (12–95 observations) well below the ~250-observation rule of thumb for
  reasonable test power, especially in the two one-year periods —
  "fail to reject" there is weak evidence, not proof of correct VaR
  coverage. DEV's post-fix Kupiec p-value (0.073) is materially closer to
  the 5% rejection boundary than the pre-fix number (0.717) suggested.
- `yf_spy_daily_2015_2025_v1`'s raw bytes were reused from a sibling
  Directive #9 repository's already-verified acquisition, not freshly
  pulled here — disclosed in the dataset manifest (field 4 above).
- The Monte Carlo VaR/ES leg uses a distinct, vectorized code path
  (`full_revaluation_mc_var_es`) from this repository's reference
  `monte_carlo_var`, validated to match it to floating-point tolerance, not
  an approximation.
- **Volatility-units defect disclosure**: Delta-Normal and Monte Carlo
  VaR/ES were previously computed against an annualized (not daily/per-
  period) volatility input, overstating both by ~16–45x, while BSM option
  pricing and Historical Simulation were unaffected throughout — see field 9
  and `TECHNICAL-PAPER.md`'s corrected VaR/ES section.

## 11. Program sign-off citation (external, reproduced verbatim — not independently re-verified by this document)

> "Directive #9 Final Four-Stream Independent Program Audit — SIGN-OFF YES;
> P0=0; P1=0; HISTORICAL EMPIRICAL VALIDATION COMPLETE / ACCEPTED."

This is an **external citation**, reproduced exactly as supplied to this
publication task. This document, and this publication pack as a whole,
**does not independently re-verify** the "Grokbot four-stream independent
audit" itself — this repository's local evidence (test suite, artifact
hashes, code review commits) supports the *specific defect fixes and
artifacts* cited elsewhere in this gate, but the program-level sign-off
claim above is reproduced as a citation to that external audit process, not
re-derived here.

## 12. Period classification table

| Period | Date range | Classification | Notes |
|---|---|---|---|
| DEV (formation) | 2015-01-01 – 2023-12-31 | Formation / development | 108 hedging episodes initiated, 95 eligible VaR/ES roll snapshots |
| VAL 2024 | 2024-01-01 – 2024-12-31 | Validation | 12 hedging episodes, 12 roll snapshots |
| 2025 | 2025-01-01 – 2025-12-31 | **HISTORICAL EVALUATION** | 12 hedging episodes initiated (11 completed within data), 12 roll snapshots. **Never** described as "untouched holdout" or "clean holdout" — SPY's 2025 price history was already inspected once under this repository's own superseded v1 study (`options_hist_risk_v1_holdout_2025`), per Directive #9 Addendum 13. See `research/holdout-audit.md`. |

## 13. Required-language statement

Every description of this study's constructs in this publication pack uses,
verbatim, the two labels required by Directive #9's D9-C spec:

- **"Historical underlying-path hypothetical option hedging experiment"**
  (Study 1)
- **"Hypothetical nonlinear portfolio evaluated on historical risk-factor
  paths"** (Study 2)

**Explicit disclaimer**: neither construct is, or is presented as, a
deployed options trading strategy, an observed historical trading position,
real historical options P&L, or an executable trading strategy. No paid
options tapes were used and no option panel is invented — every option price
in both studies is a Black-Scholes-Merton price computed from real
historical underlying (SPY) prices and realized volatility. This is a
standardized hypothetical construct evaluated on real historical
underlying/rate/vol paths, nothing more.

## 14. Standing prohibitions in force for this publication pack

- No modification, retuning, or regeneration of anything under `results/`,
  `configs/`, `src/`, `data/`, `research/historical-volatility-and-tail-risk.md`,
  or `research/holdout-audit.md`. Every file this pack adds is new, under
  `publication/options-risk-study/` only.
- No modification of `research/experiment-ledger.csv`.
- No re-running of any experiment script, no re-acquisition of any dataset,
  no network data calls. No 2025 rerun of any kind, mechanical or otherwise.
- No change to portfolio definition, option contracts, rolling schedule,
  historical underlying paths, DGS3MO/VIX handling, confidence levels, HS
  windows, MC path count/seed, transaction-cost assumptions, hedging
  methodology, or the 2025 classification.
- No invented metric, table value, or claim not traceable to a committed
  artifact.
- No modification of any `.github/workflows/*` file; nothing in this pack
  externally publishes this content.
- This pack's PR is not to be merged by this session; `main` is not touched;
  PR #3 / branch `research/historical-risk-validation` is used only as this
  PR's base (read-only reference).
- `jmiaie/quant-research-portfolio` Issue #3 and all other repositories are
  out of scope and untouched.
- No D11 work is started here.
- Pre-fix/superseded values appear only inside clearly labeled
  PRE-FIX/SUPERSEDED-vs-CORRECTED/AUTHORITATIVE comparison sections, never
  as standalone current evidence.
