# QUANT-REDTEAM — quantitative accuracy self-review

**Scope**: every number, ratio, and statistical claim in this publication
pack, checked against the exact JSON field it is supposed to trace to
(`RESULT-SOURCE-MAP.md`), independently recomputed where the pack asserts a
mean, ratio, or derived quantity. **Severity**: P0 = blocking fabrication,
incorrect number, or contradiction of a source artifact; P1 = material
overreach or a quantitative imprecision serious enough to mislead a reader
about the size of an effect; P2 = minor/stylistic.

This is a genuine pass, not a formality: the process below re-derived every
mean, ratio, and percentage in `TECHNICAL-PAPER.md` and `CASE-STUDY.md` from
the raw JSON artifacts using `scripts/build_tables.py`, then diffed the
paper's prose against the script's output line by line. Three real
discrepancies were found and are recorded below (all fixed before
finalizing). This document also records the checks that passed clean, so a
reviewer can see what was actually checked, not just what failed.

## Findings

### QT-1 (P1) — Abstract's Monte Carlo overstatement range was imprecise

**What was found**: the abstract's first draft stated the volatility-units
defect "inflated... Monte Carlo VaR by a comparable ~35–50x." The actual
computed range across all 3 periods × 2 confidence levels (from
`tables/var_es_corrected_vs_prefix.csv`'s `var_ratio_prefix_over_corrected`
column, `monte_carlo` rows only) is **35.248 to 40.463**, i.e., ~35–41x, not
~35–50x. A second instance in §5's limitations-adjacent text used "~16–45x"
for the combined Delta-Normal+Monte Carlo range (VaR and ES together);
recomputing the combined range (VaR ratios 15.875–40.463, ES ratios
15.875–42.791) gives ~16–43x, not ~16–45x.

**Why it matters**: this pack's central claim is that the pre-fix narrative
overstated a magnitude, and precision about magnitudes is exactly what this
paper is asking readers to trust it on. An imprecise range in the very
sentence stating the correction undermines that trust, even though the
original commit-message language ("~40–50x") is what motivated the loose
phrasing — the commit message is a rough qualitative note, not a value this
pack should repeat without checking it against the actual artifact-level
range.

**Fixed before finalizing**: yes. `TECHNICAL-PAPER.md` abstract now reads
"~35–41x" and the limitations-adjacent sentence in §3.1 item 3 area now
reads "~16–43x", both matching the ranges independently recomputed from
`tables/var_es_corrected_vs_prefix.csv` in this session.

### QT-2 (P2) — §4's convexity-range example mislabeled which row was the minimum

**What was found**: §4's bullet on the convexity effect originally read
"ranging from roughly +18% (DEV 95%: 298.5 vs. 252.3) to roughly +42%..."
DEV 95%'s actual ratio is +18.3%, which rounds to "roughly +18%," but it is
not the true minimum across all 6 rows — 2025 95% (671.2 vs. 570.8) is
lower, at +17.6%. Both round to the same headline figure, so the +18%/+42%
range itself was correct, but citing DEV 95% as if it were the boundary
example was imprecise.

**Why it matters**: low severity — the range bound stated (+18%) was
numerically correct, and the example given still fell within a rounding
distance of the true minimum. But a reader citing "DEV 95%: 298.5 vs. 252.3"
as *the* minimum-convexity-effect row would be citing the wrong row.

**Fixed before finalizing**: yes. §4 now cites the 2025 95% row (671.2 vs.
570.8, the actual smallest gap in the table) as the +18% example and VAL
2024 99% (unchanged, actual largest gap) as the +42% example, with an
explicit "(the smallest gap in the table)" / "(the largest)" annotation to
prevent this ambiguity from recurring.

### QT-3 (P2) — Abstract's required-language capitalization

**What was found**: the abstract introduced both required verbatim labels
mid-sentence with "a historical..." / "a hypothetical..." (lowercase),
rather than preserving the exact capitalization specified in the task
("Historical underlying-path hypothetical option hedging experiment" /
"Hypothetical nonlinear portfolio evaluated on historical risk-factor
paths"). The labels were already correctly capitalized elsewhere in the
same document (§1.1's Study 1/Study 2 headers) and in `SOURCE-GATE.md`.

**Why it matters**: minor — the substance was never in doubt, only the
literal verbatim-capitalization instruction for these two specific labels.

**Fixed before finalizing**: yes. The abstract now reads "the 'Historical
underlying-path hypothetical option hedging experiment'" and "the
'Hypothetical nonlinear portfolio evaluated on historical risk-factor
paths'", preserving exact capitalization. Verified afterward: both exact
strings (whitespace-normalized to account for markdown line wraps) are
present verbatim in both `TECHNICAL-PAPER.md` and `SOURCE-GATE.md`.

## Checks performed that found no issue (recorded for completeness)

- **Delta-Normal sqrt(252) determinism**: independently recomputed
  `var_ratio_prefix_over_corrected` for all 6 `delta_normal` rows in
  `tables/var_es_corrected_vs_prefix.csv` — all read `15.875`, matching
  `sqrt(252) = 15.8745...` to 3 decimal places, and cross-checked against
  the single-roll case study's 14-significant-figure match
  (`3382.8001955401633 / 213.09638220047478 = 15.874507866387543` vs.
  `sqrt(252) = 15.874507866387544`). No discrepancy.
- **Historical Simulation byte-identity claim**: independently diffed
  `snapshots[0].var_es.primary.historical_simulation_primary` between the
  current and `superseded_volatility_units_fix` DEV artifacts field by
  field (not just VaR/ES) — confirmed identical
  (`historical_simulation_unchanged: true` in
  `tables/case_study_dev_first_roll.json`).
- **All 18 corrected VaR/ES table rows** (§2.2) — independently recomputed
  from raw `snapshots[*]` arrays via `scripts/build_tables.py`, cross-checked
  against `research/historical-volatility-and-tail-risk.md` §6.2's own
  table: every value matches to the stated 1-decimal precision.
- **All 3 Kupiec/Christoffersen rows** (§2.3) — independently read from
  `nonlinear_portfolio_study.kupiec_christoffersen_backtest`, cross-checked
  against `research/historical-volatility-and-tail-risk.md` §6.3: exact
  match on n_forecasts, breach counts, and p-values in all three periods.
- **Mean realized-vol figures (16.33% / 15.15% / 11.84%)** — independently
  computed from `snapshots[*].realized_vol_20d` rather than copied from the
  narrative doc's prose; matches to 2 decimal places.
- **Hedging-experiment summary table** (§2.1) — all 18 rows (3 periods × 2
  frequencies × 3 cost scenarios) cross-checked against
  `hedging_experiment.summary_by_frequency_and_cost_scenario` in each
  current artifact; matches `research/historical-volatility-and-tail-risk.md`
  §5.2's table exactly, including the "mean max cash requirement" figures
  ($246.71 / $477.99 / $546.56).
- **Convexity direction claim** ("MC ES > DN ES in every row") — checked
  all 6 rows individually rather than trusting the aggregate claim; true in
  every row without exception.
- **2025 99% ES cross-method ranking flip** — checked that Historical
  Simulation's 99% ES (1,789.1) genuinely exceeds both Monte Carlo's (909.4)
  and Delta-Normal's (737.5) at 2025-99% only, and that this ranking does
  not occur in any of the other 5 rows — confirmed by inspecting all 6 rows.
- **No fabricated metric**: every number in `TECHNICAL-PAPER.md` was traced
  to an entry in `RESULT-SOURCE-MAP.md` before this document was finalized;
  no number was found that lacked a source-map entry.
- **Pre-fix numbers never presented as primary evidence**: grepped the
  entire pack for every occurrence of a `*_prefix_superseded` /
  `superseded_volatility_units_fix` / `superseded_next_session_backtest_fix`
  value and confirmed each occurs only inside an explicitly labeled
  comparison context, never as a standalone current claim.
- **Config/artifact hash values**: every sha256 cited in `SOURCE-GATE.md`,
  `RESULT-SOURCE-MAP.md`, and `reproducibility.json` was computed
  independently in this session via `sha256sum`/`hashlib.sha256` against
  the actual committed files, not copied from the task brief without
  verification (the two values the task brief supplied — config and 2025
  artifact — matched the independently computed values exactly; the DEV,
  VAL 2024, and all four superseded-set hashes were not supplied and were
  computed fresh).

## Round-2 addition — figure data-integrity check

`figures/var_es_corrected_vs_superseded_95_all_periods.png` (added in the
round-2 remediation pass, see `D10-STATUS.md` §0) was checked for the same
class of issue this document exists to catch: does the figure show numbers
that agree with the already-verified table? `scripts/build_figures.py`
imports `build_var_es_table()` directly from `scripts/build_tables.py`
rather than recomputing anything independently, so by construction the
figure's 18 bar heights are the identical `mean_var_corrected` /
`mean_var_prefix_superseded` values already checked row-by-row earlier in
this document — confirmed by reading `build_figures.py`'s source (it never
opens a JSON artifact itself) and by regenerating the figure and diffing
its sha256 against the committed file (byte-identical). No new numeric
claim was introduced by the figure; it is a visualization of the existing,
already-verified table.

## Summary

| Severity | Count | Fixed | Not fixed (rationale) |
|---|---:|---:|---|
| P0 | 0 | — | — |
| P1 | 1 (QT-1) | 1 | — |
| P2 | 2 (QT-2, QT-3) | 2 | — |

No P0 findings. All P1/P2 findings were fixed before finalizing this pack.
The round-2 figure addition introduced no new quantitative claims requiring
a fresh finding.
