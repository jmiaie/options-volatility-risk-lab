# CITATION-REDTEAM — source-citation accuracy self-review

**Scope**: every citation in this pack to (a) the external program sign-off,
(b) `research/historical-volatility-and-tail-risk.md`, (c)
`research/holdout-audit.md`, (d) source code (file:line references), (e)
commit SHAs, and (f) dataset manifests — checked for exact accuracy, not
just plausibility. Severity: P0 = a citation that misattributes, misquotes,
or fabricates a source; P1 = a citation that is materially imprecise or
could mislead about what the source actually says; P2 = minor/stylistic.

## Findings

### CIT-1 (P2) — §3.1 item 3's ratio phrasing vs. the source document's prose

**What was found**: `research/historical-volatility-and-tail-risk.md` §6.2
item 3 states "Historical Simulation's ES (1,789.1) is nearly 2.5x Monte
Carlo's (909.4) and over 2x Delta-Normal's (737.5)." Recomputing these
exact three numbers independently in this session:

```
1789.1 / 909.4 = 1.9673...   (Monte Carlo)
1789.1 / 737.5 = 2.4259...   (Delta-Normal)
```

"Nearly 2.5x" describes the Delta-Normal ratio (2.426) more precisely than
the Monte Carlo ratio (1.967, which is "nearly 2x," not "nearly 2.5x"), and
"over 2x" is imprecise for the Monte Carlo ratio (1.967 is *under* 2, not
over) though it is a defensible loose description of the Delta-Normal ratio
region. In short: the source document's descriptive labels for these two
ratios appear to be swapped or imprecisely paired relative to the numbers
it itself cites. **The three underlying VaR/ES values (1,789.1 / 909.4 /
737.5) are correct in both the source document and this pack — this is a
precision issue in qualitative ratio language, not a numeric error, and not
a claim that the source document's core finding (HS's tail exceeding both
parametric methods in this one row) is wrong.**

**Why it matters**: this pack was instructed to "draw from and cite" the
existing authoritative report, "not contradict it." Silently repeating an
imprecise ratio description would propagate a small inaccuracy; silently
"fixing" it without disclosure would look like an unexplained deviation
from the cited source. Neither is acceptable on its own.

**Resolution — not fixed by editing the source document** (prohibited: this
pack may not modify `research/historical-volatility-and-tail-risk.md`,
`research/holdout-audit.md`, or any other existing D9-C artifact). **Fixed
within this pack's own scope**: `TECHNICAL-PAPER.md` §3.1 item 3 states the
ratios computed directly from the cited numbers in this pack's own voice
(≈1.97x for Monte Carlo, ≈2.43x for Delta-Normal) and includes an explicit
parenthetical: "Note on precision: `research/historical-volatility-and-tail-risk.md`
§6.2 item 3 describes these same three numbers with the qualitative phrases
'nearly 2.5x Monte Carlo's' and 'over 2x Delta-Normal's'; recomputing the
ratios directly from the cited figures in this session gives ≈1.97x for
Monte Carlo and ≈2.43x for Delta-Normal... The underlying VaR/ES values
themselves... are unchanged and correctly cited in both places; this is a
restatement of the ratio language, not a correction to any number." This
discloses the discrepancy rather than hiding it, without asserting the
source document is "wrong" (it is not — the underlying figures it reports
are correct; only the ratio-language pairing is imprecise), and without
editing the prohibited file. Also cross-referenced in `CLAIM-REDTEAM.md`
CL-2.

## Checks performed that found no issue

- **Program sign-off citation (`SOURCE-GATE.md` field 11)**: byte-compared
  the reproduced quotation against the exact text supplied for this task —
  "Directive #9 Final Four-Stream Independent Program Audit — SIGN-OFF YES;
  P0=0; P1=0; HISTORICAL EMPIRICAL VALIDATION COMPLETE / ACCEPTED." —
  confirmed an exact character-for-character match once the markdown
  blockquote's soft line-wrap and surrounding quotation marks are accounted
  for (verified programmatically in this session, not just by eye). The
  citation is explicitly labeled "external, reproduced verbatim — not
  independently re-verified by this document," per the task's explicit
  instruction to treat this as a citation to reproduce, not a claim to
  self-verify.
- **Commit SHAs**: `db9cf44a04f1282f81ed11c7d145b5afe2db8d95` (branch base)
  and `53277193f29a613d39d7e67983298eb832cf03d8` (its parent) were both
  independently confirmed via `git rev-parse` and `git log` in this
  session, not copied from the task brief without checking — the parent SHA
  in particular was not supplied in full by the task (only a 7-character
  abbreviation, `5327719`) and was resolved to its full 40-character form
  independently.
- **Source function file:line citations** (`RESULT-SOURCE-MAP.md`'s code
  citation table): every `file:line` reference (`trailing_realized_vol()`
  at `historical_risk_study_v2.py:144`, `delta_normal_var()` at
  `var.py:146`, `full_revaluation_mc_var_es()` at
  `historical_risk_study_v2.py:472`, `kupiec_pof_test()` at
  `backtesting.py:74`, etc.) was located via direct `grep -n` against the
  actual source files in this session, not guessed or copied from the
  narrative report's prose (which does not itself give line numbers).
- **`research/historical-volatility-and-tail-risk.md` section citations**
  (§2, §3, §4, §5.2, §6.1, §6.2, §6.3, §7, §8, §9): each section number
  cited in this pack was checked against the actual document's own heading
  numbering by reading the full file in this session; no section number is
  cited from memory or inferred.
- **`research/holdout-audit.md` citations**: the "HISTORICAL EVALUATION,
  never untouched holdout" classification and the Addendum 13 reference
  were checked against the actual document's "CURRENT D9-C 2025
  CLASSIFICATION" section and its "v2 AUTHORITATIVE rebuild" section,
  read in full in this session.
- **Dataset manifest citations**: the SPY `acquisition_provenance` field
  quoted/paraphrased in `SOURCE-GATE.md` field 4 was checked against the
  actual field content in `data/manifests/yf_spy_daily_2015_2025_v1.json`,
  read directly in this session — the sibling-repository path
  (`jmiaie/Advanced_Algorithmic_Trading_Simulator_public`,
  `data/raw/yf_stat_arb_etfs_daily_2015_2025_v1/SPY.csv`) and the specific
  acquisition parameters (`yfinance 1.7.0`, date range, `auto_adjust=True`)
  are quoted from that field, not paraphrased from the task brief's
  shorter summary of it.
- **Task-supplied hash values**: the two sha256 values supplied directly by
  the task (`options_historical_risk_study_v2.yaml` config hash and the
  2025 historical-evaluation artifact hash) were independently recomputed
  via `sha256sum` in this session and confirmed to match exactly before
  being cited anywhere in this pack — they are not simply trusted and
  repeated.
- **No citation to an unread source**: confirmed every file this pack cites
  by path (`research/historical-volatility-and-tail-risk.md`,
  `research/holdout-audit.md`, `data/manifests/*.json`,
  `configs/experiments/options_historical_risk_study_v2.yaml`,
  `src/options_risk/historical_risk_study_v2.py`,
  `src/options_risk/risk/var.py`, `src/options_risk/risk/backtesting.py`,
  `tests/test_historical_risk_study_v2.py`) was actually opened and read in
  this session before being cited, not cited from the task brief's
  description of it alone.
- **PR base-branch citation** (this pack's own git workflow, not a
  narrative claim): confirmed `research/historical-risk-validation` is the
  correct PR base per the task's explicit instruction (not `main`), and
  that this repository's remote/branch state matches what the task brief
  described (branch `publication/options-risk-study` created from
  `db9cf44a04f1282f81ed11c7d145b5afe2db8d95`, not from `main`) — verified
  via `git log`/`git branch --show-current` in this session, not assumed.

## Summary

| Severity | Count | Fixed | Not fixed (rationale) |
|---|---:|---:|---|
| P0 | 0 | — | — |
| P1 | 0 | — | — |
| P2 | 1 (CIT-1) | Addressed within this pack's own text (cannot edit the cited source document) | — |

No P0 or P1 citation findings. The one P2 finding (a ratio-language
imprecision in an existing, protected source document) was disclosed and
corrected in this pack's own voice without modifying the prohibited file.
