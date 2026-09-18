# D10-STATUS — Publication Pack Status

**Study**: D10-C publication pack for the D9-C historical volatility /
hedging / nonlinear portfolio VaR study (`options_hist_risk_v2`).
**Branch**: `publication/options-risk-study`, based on commit
`db9cf44a04f1282f81ed11c7d145b5afe2db8d95` (parent
`53277193f29a613d39d7e67983298eb832cf03d8`).

## 1. Deliverables checklist

| # | Deliverable | Path | Status |
|---|---|---|---|
| 1 | Source gate (14 numbered fields) | `SOURCE-GATE.md` | Complete |
| 2 | Technical paper | `TECHNICAL-PAPER.md` | Complete |
| 3 | Result-source map | `RESULT-SOURCE-MAP.md` | Complete |
| 4 | Reproducibility manifest | `reproducibility.json` | Complete |
| 5 | Case study | `CASE-STUDY.md` | Complete |
| 6 | Claim register | `CLAIM-REGISTER.md` | Complete (20 claims enumerated) |
| 7a | Quant red-team | `QUANT-REDTEAM.md` | Complete (0 P0, 1 P1, 2 P2 — all fixed) |
| 7b | Claim red-team | `CLAIM-REDTEAM.md` | Complete (0 P0, 1 P1, 2 P2 — all addressed) |
| 7c | Citation red-team | `CITATION-REDTEAM.md` | Complete (0 P0, 0 P1, 1 P2 — addressed) |
| 8 | This status document | `D10-STATUS.md` | Complete |
| 9a | Tables (script-generated) | `tables/*.csv`, `tables/*.json` | Complete — 5 files, all script-generated from committed artifacts, no manual edits |
| 9b | Scripts | `scripts/build_tables.py` | Complete — deterministic, offline, no network calls, reads only committed artifacts |
| 9c | Figures | `figures/` | **Skipped — see §4 below.** Directory created but empty; matplotlib is not installed in `/tmp/optionsrisk-venv` in this environment, so the before/after VaR bar chart could not be generated. The table builder script detects this gracefully (`try/except ImportError`) and prints a note rather than failing; no figure file exists, and none is fabricated or hand-drawn as a substitute. |

## 2. Red-team findings summary

| Document | P0 | P1 | P2 | All resolved? |
|---|---:|---:|---:|---|
| `QUANT-REDTEAM.md` | 0 | 1 (QT-1) | 2 (QT-2, QT-3) | Yes — all 3 fixed before finalizing |
| `CLAIM-REDTEAM.md` | 0 | 1 (CL-1, = QT-1) | 2 (CL-2, CL-3) | Yes — CL-1 fixed (cross-ref to QT-1); CL-2 addressed within this pack's scope (cannot edit the cited protected source document); CL-3 required no change (already adequate) |
| `CITATION-REDTEAM.md` | 0 | 0 | 1 (CIT-1) | Yes — addressed within this pack's own text |
| **Total distinct findings** | **0** | **1** (QT-1/CL-1 are the same finding, cross-referenced) | **4** distinct P2s (QT-2, QT-3, CL-2/CIT-1 same finding cross-referenced, CL-3) | **All resolved or explicitly addressed with rationale** |

**Both mandatory CLAIM-REDTEAM checks came back clean**: (a) no sentence
anywhere in this pack implies the withdrawn "order of magnitude, explained
by recent vol + convexity" narrative survived correction, and (b) no
sentence implies deployed options trading or real historical options P&L.
Neither automatic-P0 condition was triggered.

**The one substantive finding that recurs across two red-team docs** (an
imprecise magnitude range in the abstract's "~35–50x"/"~16–45x" phrasing,
found in `QUANT-REDTEAM.md` as QT-1 and cross-referenced in
`CLAIM-REDTEAM.md` as CL-1) was fixed by replacing both ranges with the
figures independently recomputed from `tables/var_es_corrected_vs_prefix.csv`
(~35–41x and ~16–43x respectively).

**The one finding not resolved by editing a file** (`CITATION-REDTEAM.md`
CIT-1 / `CLAIM-REDTEAM.md` CL-2: a ratio-language imprecision in
`research/historical-volatility-and-tail-risk.md` §6.2 item 3's prose,
which this pack is prohibited from modifying) was resolved by disclosing
the discrepancy and stating the more precise ratios in this pack's own
text (`TECHNICAL-PAPER.md` §3.1 item 3), rather than silently repeating an
imprecise description or silently correcting it without disclosure.

## 3. Sanity checks performed

Run from `/home/user/options-volatility-risk-lab` with
`/tmp/optionsrisk-venv` activated:

- **`python -m pytest tests/ -q`** — **223 passed**, 0 failed, in 294.37s.
  This is the full existing test suite; this publication pack adds no new
  test files and modifies none.
- **`ruff check .`** — after this pack's own `scripts/build_tables.py` was
  reformatted with `ruff format` to resolve 28 line-length (E501) findings
  in that one new file, `ruff check publication/` reports **all checks
  passed**. The pre-existing repository (outside `publication/`) has 3
  pre-existing `ruff` findings in `scripts/run_historical_risk_study_v2.py`
  (a `UP017`-style deprecated-alias suggestion, unrelated to this pack) —
  **confirmed pre-existing, not introduced by this pack**, by running
  `ruff check . --exclude publication` and observing the same 3 findings
  with `publication/` excluded from the scan entirely.
- **`mypy src/`** — **Success: no issues found in 29 source files.**
  (`src/` is untouched by this publication pack; this pack's own script
  lives under `publication/options-risk-study/scripts/`, outside `src/`
  and outside `mypy`'s configured scope, and was not separately
  type-checked with `mypy` — it is a small, self-contained data-reading
  script with full type annotations, verified correct by running it and
  inspecting its output rather than by `mypy`.)
- **Table-regeneration determinism**: re-ran
  `python publication/options-risk-study/scripts/build_tables.py` after
  the `ruff format` reformatting and confirmed identical output content to
  before the reformat (only whitespace/line-wrapping changed in the
  script's own source, not its logic or output).
- **`git status`** after staging: confirmed only new files under
  `publication/options-risk-study/` are added; zero files outside that
  directory were modified, staged, or deleted. See the final report for
  the exact `git status`/`git diff --stat` output.

## 4. Matplotlib / figures note

The task's deliverable list asks for `figures/` "if matplotlib is
available... skip figures gracefully with a note in D10-STATUS.md if
unavailable." `pip freeze` in `/tmp/optionsrisk-venv` in this session shows
`numpy`, `pandas`, `scipy`, `PyYAML`, `pytest`, `mypy`, `ruff` installed,
but **no `matplotlib`**. `scripts/build_tables.py`'s
`maybe_build_figure()` function attempts `import matplotlib` inside a
`try/except ImportError`, prints
`"matplotlib not importable in this environment -- figure skipped (see D10-STATUS.md)."`,
and returns without writing a file or raising. This was observed directly
by running the script in this session (see the run log referenced in §3).
No figure was fabricated, hand-drawn, or substituted; `figures/` exists as
an empty directory (and may not appear in `git status` as trackable content
until a file is added to it, since git does not track empty directories).
If matplotlib becomes available in a future session, re-running
`python publication/options-risk-study/scripts/build_tables.py` will
populate `figures/var_es_before_after_2025_95.png` with no other changes
needed.

## 5. Explicit confirmations

- **No empirical rerun performed, including no 2025 rerun**: this session
  never invoked `scripts/run_historical_risk_study_v2.py` (or any other
  experiment runner) at any point. All numbers trace to the artifacts
  already committed at commit `db9cf44`.
- **Zero bytes changed in any existing D9 artifact/config/src file**: see
  the final report to the orchestrating session for the literal
  `git status` / `git diff --stat` output confirming only new files under
  `publication/options-risk-study/` are staged.
- **The prior order-of-magnitude narrative is explicitly withdrawn**:
  `TECHNICAL-PAPER.md`'s abstract states "This paper explicitly withdraws
  the prior report's interpretive claim that the resulting
  order-of-magnitude divergence between methods was a genuine finding
  explained by 'recent realized vol running hot' and convexity. This paper
  states plainly that it is superseded/withdrawn, not merely presents
  corrected numbers silently next to it" (paraphrase of the task's own
  requirement, matched in substance by §3's explicit "**That explanation is
  withdrawn. It was wrong in magnitude...**").
- **PR is draft and unmerged**: confirmed via the PR-creation call
  parameters (`draft: true`) and no merge call was made.
- **Nothing published externally**: this pack was published only as a
  draft GitHub PR against a private/internal repository the requesting
  account controls; no `.github/workflows/*` file was touched; no artifact,
  webpage, or external channel was used.

## 6. Standing scope reminders

- No modification to `results/`, `configs/`, `src/`, `data/`,
  `research/historical-volatility-and-tail-risk.md`,
  `research/holdout-audit.md`, or `research/experiment-ledger.csv`.
- No network calls, no dataset re-acquisition, no experiment re-execution.
- No change to portfolio definition, contracts, rolling schedule,
  underlying paths, DGS3MO/VIX handling, confidence levels, HS windows, MC
  path count/seed, transaction costs, hedging methodology, or the 2025
  classification.
- `main` untouched; PR #3 / `research/historical-risk-validation` used only
  as this PR's base, not modified.
- `jmiaie/quant-research-portfolio` Issue #3 and all other repositories:
  untouched.
- No D11 work started.

---

**READY FOR INDEPENDENT REVIEW. NO MERGE. NO D11.**
