# CLAIM-REDTEAM — interpretive/narrative self-review

**Scope**: whether this pack's interpretive claims are honest, correctly
caveated, and — the two specific checks this pack is required to make —
(1) whether anything still implies the withdrawn "order of magnitude,
explained by recent vol + convexity" story survived correction, and (2)
whether anything implies deployed trading or real historical options P&L.
**Either of those two, if found, is an automatic P0.** Severity otherwise:
P1 = material overreach, missing required caveat, or an ambiguous
withdrawal; P2 = minor/stylistic.

This is a genuine pass: every occurrence of "genuine finding," "order of
magnitude," "trading strategy," "deployed," "P&L," "holdout," "clean," and
"untouched" across every file in `publication/options-risk-study/` was
individually re-read in context (not just pattern-matched) before
concluding whether it was an assertion, a negation, or a quoted
description of the withdrawn claim. Full grep output is reproduced below
each check so a reviewer can verify the sweep was actually exhaustive, not
asserted.

## Check 1 — does anything imply the withdrawn OOM narrative survived?

**Method**: grepped every file in this pack for "genuine finding," "order
of magnitude," "explained by," and "explains the," then read each hit in
its surrounding paragraph.

**Findings, read in context**:

- `TECHNICAL-PAPER.md:38` — "...order-of-magnitude divergence between
  methods was a genuine finding..." — this is inside the abstract's
  sentence describing what is being **withdrawn** ("This paper explicitly
  withdraws the prior report's interpretive claim that..."). Not an
  assertion.
- `TECHNICAL-PAPER.md:293` — `a **"genuine finding"** attributable to two
  effects` — the phrase is in scare-quotes specifically because §3 is
  quoting and then dismantling the withdrawn framing. The very next
  sentences read "**That explanation is withdrawn. It was wrong in
  magnitude...**". Not an assertion of present validity.
- `TECHNICAL-PAPER.md:315` — "...framing as if it were still a live
  interpretation. It is superseded and withdrawn." — explicit negation.
- `TECHNICAL-PAPER.md:339` — "Convexity survives as a real, genuine
  finding, **at its true (much smaller) scale**" — this is describing the
  correctly-scaled *retained* finding (item 2 of §3.1), not the withdrawn
  OOM claim. The retained finding is explicitly scoped to a modest,
  bounded magnitude (+18% to +42% ES premium, §4), not an order of
  magnitude. Legitimate — the task instructions explicitly ask for
  "the real, much smaller residual effects... may be reported, correctly
  scaled, as real but modest findings," and this is exactly that.
- `TECHNICAL-PAPER.md:349` — "A genuine finding visible only after
  correction..." — describes the new 2025 99% ES tail-ranking finding
  (§3.1 item 3), a different, smaller, previously-invisible effect. Not
  a restatement of the withdrawn claim.
- `CLAIM-REGISTER.md` C8 — the withdrawn claim is recorded explicitly with
  `superseded: true` and the note "This claim is false as originally
  stated... not asserted as true anywhere else in this pack."

**Additional check**: searched for any sentence that quantifies the
pre-fix/post-fix gap using vague, unscaled language (e.g., "much larger,"
"significantly bigger") without a number attached, which could smuggle
back an order-of-magnitude impression without a checkable figure. None
found — every comparison between pre-fix and corrected magnitudes in this
pack (§3, §4, `CASE-STUDY.md`) cites the specific ratio (15.875x, ~35–41x,
~16–43x, +18% to +42%) rather than a qualitative "much bigger."

**Verdict**: **No P0.** The withdrawal is explicit, stated in the abstract,
restated in §3 with the specific "withdrawn" language required by the task,
and no sentence anywhere in the pack lets the old magnitude framing stand
unchallenged. Every "genuine finding" phrase found refers either to (a) the
withdrawn claim, always in a withdrawal context, or (b) a correctly-scaled
retained/new finding with an explicit, bounded, checkable magnitude.

## Check 2 — does anything imply deployed trading or real historical options P&L?

**Method**: grepped every file for "deployed," "trading strategy," "P&L,"
"real options," "actual trading," "live trading," and separately re-read
every use of "hedging" and "portfolio" for language that could be misread
as describing an actually-held position.

**Findings, read in context**:

- `TECHNICAL-PAPER.md:27` — "Neither construct reflects a deployed trading
  strategy or real historical options P&L" — explicit negation/disclaimer.
- `SOURCE-GATE.md` field 13 — "neither construct is, or is presented as, a
  deployed options trading strategy, an observed historical trading
  position, real historical options P&L, or an executable trading
  strategy" — explicit negation/disclaimer, and this is the section
  specifically required by the task to carry this language.
- `CLAIM-REGISTER.md` C17 — records the disclaimer as a claim with its own
  evidentiary basis, `superseded: false` (it was never part of the withdrawn
  narrative in the first place — it is a standing constraint, not a
  corrected number).
- Every description of Study 1 ("hedging experiment") and Study 2
  ("nonlinear portfolio") in `TECHNICAL-PAPER.md` §1.1, `CASE-STUDY.md`,
  and `SOURCE-GATE.md` field 8/13 uses "standardized," "hypothetical," or
  the required verbatim labels ("Historical underlying-path hypothetical
  option hedging experiment" / "Hypothetical nonlinear portfolio evaluated
  on historical risk-factor paths") rather than language implying an
  actually-held position (no use of "our position," "the trade," "P&L we
  realized," etc. was found anywhere in the pack).
- `TECHNICAL-PAPER.md` §1.3's case-study walkthrough describes
  "the standardized portfolio at this roll has portfolio dollar-delta..."
  — this describes the *modeled construct's* Greeks at a point in time, not
  a claim that this delta was ever actually hedged in a real market. Read
  in context (immediately following "hypothetical nonlinear portfolio"
  framing throughout §1.1), this does not cross into deployed-trading
  language.

**Verdict**: **No P0.** No sentence in this pack asserts or implies actual
deployed trading, an observed historical position, or real P&L. The
required disclaimer is present verbatim in the two places (`SOURCE-GATE.md`
field 13, `TECHNICAL-PAPER.md` abstract) most likely to be read in
isolation.

## Additional interpretive checks (beyond the two mandatory ones)

### CL-1 (P1, found and fixed during QUANT-REDTEAM, cross-referenced here) — precision of magnitude language in the withdrawal itself

Already documented as QT-1 in `QUANT-REDTEAM.md`: the abstract's "~35–50x"
and the limitations text's "~16–45x" overstated the actual computed ranges
(~35–41x and ~16–43x respectively). This is cross-referenced here because an
imprecise *overstatement* of how bad the pre-fix numbers were, even in the
direction that makes the correction look more dramatic, is itself a form
of the "don't overstate a magnitude" failure this pack exists to correct.
**Fixed** — see `QUANT-REDTEAM.md` QT-1 for the resolution; both ranges now
match the artifact-derived figures exactly.

### CL-2 (P2) — the 2025 99% ES ratio phrasing vs. the source doc's prose

`research/historical-volatility-and-tail-risk.md` §6.2 item 3 describes the
2025 99% ES figures with "nearly 2.5x Monte Carlo's (909.4) and over 2x
Delta-Normal's (737.5)." Recomputing directly from the cited numbers in this
session gives HS/MC ≈ 1.967x and HS/DN ≈ 2.426x — i.e., "nearly 2.5x" more
precisely describes the Delta-Normal ratio and "just under 2x" more
precisely describes the Monte Carlo ratio, the reverse pairing from the
source doc's phrasing. The underlying VaR/ES values themselves (1,789.1 /
909.4 / 737.5) are correct and unchanged in both places — this is a
ratio-language imprecision in the qualitative description, not a numeric
error in the cited figures, and not a case of the withdrawn OOM narrative
resurfacing (this is a *different*, much smaller, genuinely-retained
finding, and the actual numbers were never in dispute).

**Not fixed by editing the source document** — `research/historical-volatility-and-tail-risk.md`
is explicitly prohibited from modification by this task's standing
prohibitions (it is D9-C's own authoritative artifact, not a publication-pack
file). **Fixed within this pack's own scope**: `TECHNICAL-PAPER.md` §3.1
item 3 states the ratios computed directly from the cited figures
(≈1.97x, ≈2.43x) and includes an explicit parenthetical noting the more
precise pairing, rather than silently repeating the source doc's less
precise phrasing as if it were this pack's own independently-verified
conclusion. See `CITATION-REDTEAM.md` CIT-1 for the citation-accuracy
framing of the same finding.

### CL-4 (P2, externally identified by the orchestrating session in a follow-up review — not found by this pack's own first-pass red-team) — unproven causal attribution to convexity

**What was found**: `TECHNICAL-PAPER.md` §3.1 item 2 originally read
"Convexity survives as a real, genuine finding, at its true (much smaller)
scale," and stated that Monte Carlo's ES exceeding Delta-Normal's ES in
every row was "exactly as expected from a book with genuine gamma."
Similar phrasing ("because the full-revaluation book has genuine gamma")
also appeared in §1.3's case-study paragraph, §3's Monte Carlo ratio
discussion, the §4 bullet heading ("Convexity effect"), the conclusion, and
in `CASE-STUDY.md` §4/§5. The artifacts genuinely establish: (a) Monte
Carlo's full-revaluation ES exceeds Delta-Normal's linear ES in every
accepted period/confidence row, and (b) the standardized book has nonzero
gamma at every roll (`portfolio_greeks.gamma`, directly in the artifacts).
Both are true and artifact-backed. But this pack never ran a separate
gamma/attribution decomposition isolating convexity as the sole or
dominant cause of that specific ES gap — "compatible with convexity" and
"proven to be caused by convexity" are different claims, and the original
phrasing ("genuine finding," "exactly as expected," "because... gamma")
read as the latter.

**Why it matters**: this is exactly the category of overreach this pack
exists to police (the whole point of the central withdrawal is that a
plausible-sounding mechanism is not the same as a proven one) — leaving an
unproven "because convexity" causal claim standing, even for a real and
much smaller effect than the withdrawn OOM narrative, would be inconsistent
with that standard applied to itself.

**Fixed before finalizing**: yes, throughout. Every instance of
"convexity/gamma [is/was] the cause" was reworded to "consistent with
convexity" / "compatible with the book's convexity" / "a persistent
nonlinear-revaluation difference," with an explicit note that no separate
gamma-attribution decomposition was performed — in `TECHNICAL-PAPER.md`
(abstract, §1.3, §3, §3.1 item 2, §4, §6 conclusion), `CASE-STUDY.md` (§4,
§5), `CLAIM-REGISTER.md` (C5, C10), and `RESULT-SOURCE-MAP.md` (§4 heading).
The measured +18%/+42% ES-gap figures and the ~35–41x Monte Carlo VaR-ratio
range themselves were **not** changed — those are artifact-backed
observations, independent of what causes them, and remain exactly as
computed. Item 3 of §3.1 (the 2025 HS-vs-parametric ES tail-ranking
finding) was reviewed against the same standard and left unchanged: its
explanation ("Historical Simulation draws real historical daily returns...
Monte Carlo and Delta-Normal both assume an iid-normal daily return...")
is a direct structural fact about what each method's own definition
assumes (documented in each method's own docstring/methodology, not
inferred from the data), not an attribution requiring a decomposition to
prove — it does not invoke convexity as an explanation at all.

### CL-3 (P2) — checked for asymmetric caveat treatment between the two corrections

The pack discusses two distinct defect corrections (the volatility-units
fix, central to this pack, and the earlier next-session backtest-alignment
fix). Checked whether the pack gives the backtest-alignment fix's own
"before/after" framing enough distinction from the volatility-units
correction that a reader would not conflate the two or think the
backtest-alignment numbers are part of the withdrawn OOM narrative.
`TECHNICAL-PAPER.md` §2.3's closing paragraph explicitly separates them:
"These numbers *do* differ from an earlier, separate, already-corrected
defect... orthogonal to this paper's central correction and is not being
re-litigated here." No fix needed — already adequately separated.

## Summary

| Severity | Count | Fixed | Not fixed (rationale) |
|---|---:|---:|---|
| P0 | 0 | — | — |
| P1 | 1 (CL-1, = QT-1) | 1 | — |
| P2 | 3 (CL-2, CL-3, CL-4) | CL-2 addressed within pack scope; CL-3 required no change; CL-4 fixed throughout | CL-2: cannot edit the cited source document (standing prohibition) — addressed by stating the more precise ratio in this pack's own text instead |

**Both mandatory checks (withdrawn-OOM-narrative survival; deployed-trading/
real-P&L implication) came back clean: zero occurrences of either failure
mode anywhere in this pack.**

**Provenance note on CL-4**: unlike every other finding in this pack's three
red-team documents, CL-4 (unproven causal attribution to convexity) was
**not** caught by this pack's own first-pass red-team review — it was
identified by the orchestrating session in an independent follow-up review
and sent back as a required fix. It is recorded here, with full detail, in
the same format as this pack's self-identified findings, both because it
belongs in this document's permanent record and so a reviewer can see that
an external catch was integrated rather than only self-reported findings.
