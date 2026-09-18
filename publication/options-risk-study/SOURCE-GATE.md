# SOURCE-GATE — D10-C Publication Pack

**Status**: source-of-truth gate for every fact used in this publication
pack, using the program's authoritative 14-field SOURCE-GATE MATRIX schema
(Phase 0). Nothing in `TECHNICAL-PAPER.md`, `CASE-STUDY.md`, or any other
document in `publication/options-risk-study/` may cite a number that is not
traceable to one of the 14 fields below, to one of the unnumbered sections
that follow them, or to `RESULT-SOURCE-MAP.md`, which expands each
paper-level number to an exact JSON key path. This document does not
re-derive or re-verify the Grokbot audit claim in field 11; that claim is
reproduced verbatim as an external citation.

**Note on structure**: fields 1–14 below are the authoritative schema and
contain only what each field name says, kept concise. Everything else this
pack needs from a source gate — full methodology, volatility-units
provenance detail, the complete limitations list, the required-language
statement, the standing prohibitions, and the rest of the artifact
inventory — is preserved in full, in the clearly named unnumbered sections
that follow field 14. Nothing was deleted; content that doesn't belong in
one of the 14 fields was relocated, not removed.

---

## 1. Repository

`jmiaie/options-volatility-risk-lab`

## 2. Source PR / branch

**PR #3**, branch `research/historical-risk-validation` — the D9-C
remediation PR whose accepted HEAD (field 3) this publication pack's
evidence is built from.

**Not to be conflated with**: this publication pack's own branch is
`publication/options-risk-study`, a separate branch created from field 3's
commit. PR #3 / `research/historical-risk-validation` remains open,
unmerged, and untouched by this pack; it is used only as this pack's own
PR's base (read-only reference) — see "Branch and PR provenance" below for
the full detail.

## 3. Accepted HEAD

`db9cf44a04f1282f81ed11c7d145b5afe2db8d95`

## 4. Experiment ID

`options_hist_risk_v2`

## 5. Dataset IDs

`yf_spy_daily_2015_2025_v1`, `fred_dgs3mo_daily_2015_2025_v1`,
`fred_vixcls_daily_2015_2025_v1`

## 6. Dataset SHA / frozen identity

| Dataset ID | `dataset_canonical` sha256 |
|---|---|
| `yf_spy_daily_2015_2025_v1` | `0c83ab20bf76ec39b97855ac393b7bc74363bd4ff373381f0a92842a2c7c6a63` |
| `fred_dgs3mo_daily_2015_2025_v1` | `31ad77f46517b4a51a2313ad86524d3f0f07634e4ca450ba2c387adbddf42a9f` |
| `fred_vixcls_daily_2015_2025_v1` | `b727ab1751d4c9c180159cc1eb3358a2fef6ebf1abe15c74adb46f93019753b1` |

The SPY dataset carries a disclosed reuse-provenance limitation (its bytes
were not freshly acquired in this repository) — preserved in full under
"Additional dataset provenance" below.

## 7. 2025 / holdout status

**HISTORICAL EVALUATION.** Never "untouched holdout," "clean holdout," or
"pristine holdout." SPY's 2025 price history was already inspected once
under this repository's own superseded v1 study
(`options_hist_risk_v1_holdout_2025`), per Directive #9 Addendum 13. See
`research/holdout-audit.md`.

## 8. Final config SHA

`configs/experiments/options_historical_risk_study_v2.yaml`
sha256 = `4bd18561466b5f85b09031868322929c8ad28bd9c2da9358ac3a106fdb725181`

## 9. Primary artifact path

`results/historical_risk/options_hist_risk_v2_historical_evaluation_2025.json`

(The 2025 HISTORICAL EVALUATION artifact is the primary artifact per this
schema's convention. DEV and VAL 2024 artifact paths and hashes, and both
superseded pre-fix artifact sets, are preserved in full under "Additional
artifact inventory" below.)

## 10. Result artifact SHA

`b2c3594445b7f1a726be135cb5cb17f43f69d6a3a938657b3e4faca3dcb62799`

(sha256 of the field 9 artifact, independently computed and confirmed to
match the value supplied for this task.)

## 11. Independent review status

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

## 12. Primary finding

**2025 HISTORICAL EVALUATION, 95% confidence, mean across the period's 12
monthly roll snapshots** (Study 2, "Hypothetical nonlinear portfolio
evaluated on historical risk-factor paths"):

- Historical Simulation VaR ≈ **408.6**, ES ≈ **814.3**
- Delta-Normal VaR ≈ **455.2**
- Monte Carlo (50k) VaR ≈ **513.0**

**Study 1 ("Historical underlying-path hypothetical option hedging
experiment"), 2025 HISTORICAL EVALUATION, mean absolute replication error,
BASE (1bp) cost scenario**:

- Daily rebalancing ≈ **6.65** (exact: 6.6459)
- Weekly rebalancing ≈ **7.45** (exact: 7.454970530990272)

Full tables for all three periods, both confidence levels, and all methods
are in `TECHNICAL-PAPER.md` §2 and `RESULT-SOURCE-MAP.md`.

## 13. Primary null / negative finding

**The previously reported order-of-magnitude divergence between Historical
Simulation and Delta-Normal/Monte Carlo VaR/ES is WITHDRAWN as a genuine
finding.** Most of the apparent divergence was a volatility-units defect,
not a real methodological or vol-regime effect:

- Black-Scholes-Merton option pricing correctly uses **annualized**
  volatility (paired with maturity `T` in years).
- The one-day Delta-Normal and Monte Carlo VaR/ES legs were incorrectly fed
  that same annualized figure directly, instead of the annualized figure
  divided by `sqrt(252)` (the correct daily/per-period conversion).
- Historical Simulation consumes no volatility parameter at all and was
  completely unaffected, as was the Kupiec/Christoffersen backtest.

With the defect corrected, all three methods sit within the same order of
magnitude. The remaining, much smaller Monte-Carlo-vs-Delta-Normal ES
differences are consistent with nonlinear full revaluation / convexity —
**not a proven causal decomposition** (no separate gamma/attribution
analysis was run to isolate convexity as the sole cause). See
`TECHNICAL-PAPER.md` §3 for the full withdrawal statement and
`CLAIM-REDTEAM.md` finding CL-4 for the causal-language precision fix this
framing reflects.

## 14. Primary limitation

At minimum: these are **hypothetical option constructs, not historical
options-tape P&L**; no paid options tape was used; 2025 is **HISTORICAL
EVALUATION**, not an untouched holdout; Kupiec/Christoffersen samples are
small (12–95 observations) with correspondingly weak test power; DGS3MO is
FRED's standard series, not an ALFRED real-time vintage; `q=0` (no discrete
dividend modeling); hedging episodes overlap month-to-month (serially
dependent, not independent, samples). Full list, with detail on each item,
is in "Known limitations and caveats (full list)" below.

---

## Program background

This is **Directive #9 / #10, study D9-C / D10-C** of the multi-repo
quantitative-research remediation program tracked in
`jmiaie/quant-research-portfolio` Issue #3. D9-C was the defect-remediation
phase for this repository's historical volatility / hedging / nonlinear
portfolio VaR study; it produced the AUTHORITATIVE (v2) study documented in
`research/historical-volatility-and-tail-risk.md` and
`research/holdout-audit.md`. D9 (all repos, all streams) has been declared
closed by an external four-stream independent audit (field 11 above).
**D10-C is a PUBLICATION/COMMUNICATION phase**: this pack writes up
already-accepted, already-computed D9-C evidence for external readers.
D10-C performs **no new empirical work** — no retraining, no retuning, no
re-acquiring data, no rerunning any evaluation period (including 2025), and
no alteration of any existing result artifact, config, or source file.
Every file under `publication/options-risk-study/` is new. Nothing outside that directory was
modified to produce it, with one disclosed exception: `.github/workflows/publication-pack.yml`
was added so this pack has its own CI verification gate (`ci.yml` never runs on a PR whose base
is a non-`main` branch); it only checks out the repo, installs dependencies, runs
`scripts/verify_pack.py`, `ruff` and `mypy`, and commits nothing.

## Branch and PR provenance

- **This publication pack's branch**: `publication/options-risk-study`,
  created from field 3's commit (`db9cf44a04f1282f81ed11c7d145b5afe2db8d95`),
  **not** from `main`.
- **Immediate parent SHA** of field 3 (verified via `git rev-parse
  db9cf44a04f1282f81ed11c7d145b5afe2db8d95^` in this session):
  `53277193f29a613d39d7e67983298eb832cf03d8` — commit message: *"D9-C P1:
  fix off-by-one in Kupiec/Christoffersen next-session return"*. Field 3's
  own commit message: *"D9-C P1: fix volatility-units mismatch in
  Delta-Normal/Monte Carlo VaR"* — the commit that fixed the defect
  described in field 13 above.
- `main`'s tip at the time of writing is the still-open, unmerged D9-C
  remediation PR #3 (field 2) on branch `research/historical-risk-validation`;
  this publication pack does not depend on, alter, or merge that PR. This
  pack's own PR targets `research/historical-risk-validation` as its base
  (not `main`) specifically so its diff is isolated to the new publication
  content only.

## Additional dataset provenance

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

## Additional artifact inventory

**Current / authoritative artifact paths and sha256, all three periods**
(all hashed independently this session; field 9/10 above give the primary
2025 artifact only):

| Period | Path | sha256 |
|---|---|---|
| DEV | `results/historical_risk/options_hist_risk_v2_dev_formation.json` | `6e840d4934ead483233aa83bebd232abd94b1652ed410f85408a5a898f5e5f26` |
| VAL 2024 | `results/historical_risk/options_hist_risk_v2_val_2024.json` | `4df81b2d7d6078f9f5bf2cb8526838291d2de249e96fe4cbdd7ed4b2a76ef0b8` |
| 2025 HISTORICAL EVALUATION | `results/historical_risk/options_hist_risk_v2_historical_evaluation_2025.json` | `b2c3594445b7f1a726be135cb5cb17f43f69d6a3a938657b3e4faca3dcb62799` (= field 10) |

The 2025 hash matches the value supplied for this task exactly; the DEV and
VAL 2024 hashes were computed fresh in this session and are recorded here
and in `publication/options-risk-study/tables/dataset_and_artifact_hashes.json`.

**Superseded artifact paths (PRE-FIX, never primary evidence)**. Two
superseded sets, both preserved unmodified in the repository for audit
trail. Neither is used as current evidence anywhere in this pack except
inside explicitly labeled PRE-FIX/SUPERSEDED-vs-CORRECTED comparison
sections.

Set A — `superseded_volatility_units_fix/` (pre the fix at commit
`db9cf44`, the volatility-units defect — central to this pack, see field
13):

| Period | Path | sha256 |
|---|---|---|
| DEV | `results/historical_risk/superseded_volatility_units_fix/options_hist_risk_v2_dev_formation.json` | `7bd4ea0c3a278c86c31e71fc265fda967d8d8a8ffb3481662f995e95576f459a` |
| VAL 2024 | `results/historical_risk/superseded_volatility_units_fix/options_hist_risk_v2_val_2024.json` | `3a8b75fdd52d17727409b99844426b75fc307a8d38df41f9dabeffd2d89e7918` |
| 2025 | `results/historical_risk/superseded_volatility_units_fix/options_hist_risk_v2_historical_evaluation_2025.json` | `8449bf6e20d2095ed564b693ff9567f46490b719de384d593078504710909a2f` |

Set B — `superseded_next_session_backtest_fix/` (pre the earlier
Kupiec/Christoffersen off-by-one fix at commit `5327719`):

| Period | Path | sha256 |
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

## Methodology summary

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

## Volatility-units provenance

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
- `daily_factor_vol_20d` = **0.014835** = 0.235506 / √252 to 6 d.p. (0.01483546539740085)
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

## Known limitations and caveats (full list)

Pulled verbatim in substance from `research/historical-volatility-and-tail-risk.md`
§8 (not softened); field 14 above gives the concise "at minimum" version of
this same list:

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
  pulled here — disclosed in the dataset manifest, see "Additional dataset
  provenance" above.
- The Monte Carlo VaR/ES leg uses a distinct, vectorized code path
  (`full_revaluation_mc_var_es`) from this repository's reference
  `monte_carlo_var`, validated to match it to floating-point tolerance, not
  an approximation.
- **Volatility-units defect disclosure**: Delta-Normal and Monte Carlo
  VaR/ES were previously computed against an annualized (not daily/per-
  period) volatility input, overstating both by ~16–43x, while BSM option
  pricing and Historical Simulation were unaffected throughout — see field
  13 above and `TECHNICAL-PAPER.md`'s corrected VaR/ES section.

## Period classification table

| Period | Date range | Classification | Notes |
|---|---|---|---|
| DEV (formation) | 2015-01-01 – 2023-12-31 | Formation / development | 108 hedging episodes initiated, 95 eligible VaR/ES roll snapshots |
| VAL 2024 | 2024-01-01 – 2024-12-31 | Validation | 12 hedging episodes, 12 roll snapshots |
| 2025 | 2025-01-01 – 2025-12-31 | **HISTORICAL EVALUATION** (= field 7) | 12 hedging episodes initiated (11 completed within data), 12 roll snapshots. **Never** described as "untouched holdout" or "clean holdout" — SPY's 2025 price history was already inspected once under this repository's own superseded v1 study (`options_hist_risk_v1_holdout_2025`), per Directive #9 Addendum 13. See `research/holdout-audit.md`. |

## Required-language statement

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

## Standing prohibitions

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
- **No existing workflow file was modified.** One new, explicitly
  authorized, publication-only verification workflow was added:
  `.github/workflows/publication-pack.yml`. It lints, type-checks, and
  validates this pack's own scripts and artifacts (hash checks against
  `SOURCE-GATE.md`, citation-resolution checks against
  `RESULT-SOURCE-MAP.md`, byte-identity checks on the regenerated
  tables/figure); it does **not** run the empirical study
  (`scripts/run_historical_risk_study_v2.py`), does not fetch data over the
  network, and does not publish this content externally in any way. It
  triggers only on pushes to this pack's own branch and on pull requests
  touching `publication/options-risk-study/**` or the workflow file itself.
  `ci.yml` (the repository's pre-existing test workflow) is untouched.
- This pack's PR is not to be merged by this session; `main` is not touched;
  PR #3 / branch `research/historical-risk-validation` is used only as this
  PR's base (read-only reference).
- `jmiaie/quant-research-portfolio` Issue #3 and all other repositories are
  out of scope and untouched.
- No D11 work is started here.
- Pre-fix/superseded values appear only inside clearly labeled
  PRE-FIX/SUPERSEDED-vs-CORRECTED/AUTHORITATIVE comparison sections, never
  as standalone current evidence.

## Reviewer instructions

This document is the source-of-truth gate: any number appearing in
`TECHNICAL-PAPER.md`, `CASE-STUDY.md`, or any other document in this pack
must trace to one of the 14 fields above, to one of the unnumbered sections
above, or to a row in `RESULT-SOURCE-MAP.md` (which gives the exact source
file, JSON key path, and sha256 for every table/number in the technical
paper). If a reviewer finds a number in this pack that does not trace to
one of those three places, that is a defect in this pack, not a judgment
call — please flag it. `D10-STATUS.md` gives the full deliverables
checklist, red-team resolution summary, and CI status for this pack as a
whole.
