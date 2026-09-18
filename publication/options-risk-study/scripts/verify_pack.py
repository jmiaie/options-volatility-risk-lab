#!/usr/bin/env python3
"""D10-C publication pack -- CI verification script.

Fails closed if:
  1. Any sha256 that SOURCE-GATE.md cites for a D9-C artifact/config/dataset
     does not match the real, currently-committed file it claims to
     describe (dataset manifests' own `dataset_canonical` field, the frozen
     config, all current + superseded result artifacts).
  2. Any RESULT-SOURCE-MAP.md section reference in CLAIM-REGISTER.md's
     evidentiary-basis column does not resolve to an actual heading in
     RESULT-SOURCE-MAP.md.
  3. Regenerating the tables (via build_tables.py's own functions) or the
     figure (via build_figures.py) from the same committed source artifacts
     produces output that differs from what is currently committed --
     byte-for-byte for the CSV/JSON tables (no tolerance: these are pure
     textual, deterministic outputs), and byte-for-byte for the PNG figure
     with a disclosed content-level (pixel-difference) fallback check for
     the case where a genuine, benign cross-environment rendering
     difference (not a real data change) is the cause.

This script performs NO network calls and NEVER re-runs
scripts/run_historical_risk_study_v2.py or touches results/historical_risk/,
data/, configs/, or src/ -- it only reads already-committed files and
writes table output to a private temporary directory for comparison. The figure is
different: `build_figures.build_figure()` writes to the committed `figures/` path, so the check
snapshots the committed bytes first and writes them back afterwards.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_figures  # noqa: E402
import build_tables  # noqa: E402

REPO_ROOT = build_tables.REPO_ROOT
PUB_DIR = build_tables.PUB_DIR
SOURCE_GATE = PUB_DIR / "SOURCE-GATE.md"
CLAIM_REGISTER = PUB_DIR / "CLAIM-REGISTER.md"
RESULT_SOURCE_MAP = PUB_DIR / "RESULT-SOURCE-MAP.md"
FIGURE_NAME = "var_es_corrected_vs_superseded_95_all_periods.png"

FAILURES: list[str] = []


def fail(msg: str) -> None:
    FAILURES.append(msg)
    print(f"FAIL: {msg}")


def ok(msg: str) -> None:
    print(f"OK:   {msg}")


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_source_gate_hashes() -> None:
    gate_text = SOURCE_GATE.read_text(encoding="utf-8")
    checks: dict[str, str] = {
        "config": sha256_of(
            REPO_ROOT / "configs" / "experiments" / "options_historical_risk_study_v2.yaml"
        )
    }

    for dataset_id in (
        "yf_spy_daily_2015_2025_v1",
        "fred_dgs3mo_daily_2015_2025_v1",
        "fred_vixcls_daily_2015_2025_v1",
    ):
        manifest = build_tables.load_json(REPO_ROOT / "data" / "manifests" / f"{dataset_id}.json")
        checks[f"dataset:{dataset_id}"] = manifest["sha256"]["dataset_canonical"]

    for label, path in build_tables.CURRENT_ARTIFACTS.items():
        checks[f"current:{label}"] = sha256_of(path)
    for label, path in build_tables.SUPERSEDED_VOL_UNITS.items():
        checks[f"superseded_vol_units:{label}"] = sha256_of(path)
    for label, path in build_tables.SUPERSEDED_BACKTEST.items():
        checks[f"superseded_backtest:{label}"] = sha256_of(path)

    for name, digest in checks.items():
        if digest in gate_text:
            ok(f"SOURCE-GATE.md cites the correct, currently-true sha256 for {name}")
        else:
            fail(
                f"SOURCE-GATE.md does NOT contain the freshly-recomputed sha256 for "
                f"{name} ({digest}) -- the cited hash is stale, or the source file "
                f"changed since SOURCE-GATE.md was written"
            )


SECTION_RE = re.compile(r"§(\d+(?:\.\d+)*)")
# Matches "RESULT-SOURCE-MAP.md" followed immediately by a chain of one or
# more "§N[.M]" tokens, optionally joined by "/" (e.g. "§2.2/§3"). Anchoring
# the chain right after the filename -- rather than scanning the whole
# line -- avoids false positives from an unrelated "§N" reference to a
# DIFFERENT document appearing later on the same line (e.g. a citation to
# "research/historical-volatility-and-tail-risk.md §7" on the same table
# row as a "RESULT-SOURCE-MAP.md §2.1" citation must not be misread as a
# RESULT-SOURCE-MAP.md §7 citation).
CITE_CHAIN_RE = re.compile(
    r"RESULT-SOURCE-MAP\.md((?:\s*§\d+(?:\.\d+)*\s*/)*(?:\s*§\d+(?:\.\d+)*)?)"
)


def check_claim_citations_resolve() -> None:
    claim_text = CLAIM_REGISTER.read_text(encoding="utf-8")
    map_text = RESULT_SOURCE_MAP.read_text(encoding="utf-8")

    map_headings = "\n".join(line for line in map_text.splitlines() if line.startswith("#"))
    map_sections = set(SECTION_RE.findall(map_headings))

    cited_sections: set[str] = set()
    for match in CITE_CHAIN_RE.finditer(claim_text):
        cited_sections.update(SECTION_RE.findall(match.group(1)))

    if not cited_sections:
        fail("No RESULT-SOURCE-MAP.md section citations found anywhere in CLAIM-REGISTER.md")
        return

    missing = sorted(cited_sections - map_sections, key=lambda s: [int(p) for p in s.split(".")])
    if missing:
        fail(
            f"CLAIM-REGISTER.md cites RESULT-SOURCE-MAP.md section(s) {missing} that do "
            f"not appear in any RESULT-SOURCE-MAP.md heading (headings found for: "
            f"{sorted(map_sections, key=lambda s: [int(p) for p in s.split('.')])})"
        )
    else:
        ok(
            f"Every RESULT-SOURCE-MAP.md section CLAIM-REGISTER.md cites "
            f"({sorted(cited_sections, key=lambda s: [int(p) for p in s.split('.')])}) "
            f"resolves to an actual heading there"
        )


def check_tables_reproducible(tmp_dir: Path) -> None:
    var_es_rows = build_tables.build_var_es_table()
    hedging_rows = build_tables.build_hedging_table()
    kc_rows = build_tables.build_kupiec_christoffersen_table()
    case_study = build_tables.build_case_study()
    hashes = build_tables.build_hash_manifest()

    build_tables.write_csv(var_es_rows, tmp_dir / "var_es_corrected_vs_prefix.csv")
    build_tables.write_csv(hedging_rows, tmp_dir / "hedging_experiment_summary.csv")
    build_tables.write_csv(kc_rows, tmp_dir / "kupiec_christoffersen.csv")
    (tmp_dir / "case_study_dev_first_roll.json").write_text(
        json.dumps(case_study, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (tmp_dir / "dataset_and_artifact_hashes.json").write_text(
        json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    for name in (
        "var_es_corrected_vs_prefix.csv",
        "hedging_experiment_summary.csv",
        "kupiec_christoffersen.csv",
        "case_study_dev_first_roll.json",
        "dataset_and_artifact_hashes.json",
    ):
        committed_path = build_tables.TABLES_DIR / name
        fresh_path = tmp_dir / name
        if not committed_path.exists():
            fail(f"tables/{name} is missing from the committed pack")
            continue
        committed = committed_path.read_bytes()
        fresh = fresh_path.read_bytes()
        if committed == fresh:
            ok(f"tables/{name} matches freshly recomputed content byte-for-byte")
        else:
            fail(
                f"tables/{name} does NOT match freshly recomputed content -- the "
                f"committed table is stale relative to the source artifacts"
            )


def check_figure_reproducible(tmp_dir: Path) -> None:
    committed_path = build_tables.FIGURES_DIR / FIGURE_NAME
    if not committed_path.exists():
        fail(f"figures/{FIGURE_NAME} is missing from the committed pack")
        return
    committed_bytes = committed_path.read_bytes()
    committed_sha = hashlib.sha256(committed_bytes).hexdigest()

    # Regenerate into the real FIGURES_DIR (build_figures.py's path is not
    # parameterized), then move the result aside into tmp_dir before any
    # later step could re-read it, so the committed file on disk ends the
    # job exactly as it started (this job never intends to change it).
    result = build_figures.build_figure()
    if result is None:
        fail(
            "matplotlib is not importable in this CI job -- the figure could not be "
            "regenerated to verify it; check the dependency-install step's log."
        )
        return

    fresh_bytes = Path(result).read_bytes()
    fresh_sha = hashlib.sha256(fresh_bytes).hexdigest()
    # Restore the committed bytes immediately (this script's job is to
    # verify, not to modify the working tree).
    committed_path.write_bytes(committed_bytes)

    if fresh_sha == committed_sha:
        ok(f"figures/{FIGURE_NAME} regenerates byte-identical (sha256 {fresh_sha[:12]}...)")
        return

    print(
        "NOTE: the regenerated figure is not byte-identical to the committed one. "
        "This can be a genuine data drift OR a benign cross-environment rendering "
        "difference (font hinting / freetype / libpng build differences across OS "
        "or matplotlib patch versions) even with a pinned matplotlib version. "
        "Falling back to a disclosed content-level check (dimensions + normalized "
        "pixel difference) rather than failing closed on byte identity alone."
    )
    try:
        import io

        import numpy as np
        from PIL import Image, ImageChops

        committed_img = Image.open(io.BytesIO(committed_bytes)).convert("RGB")
        fresh_img = Image.open(io.BytesIO(fresh_bytes)).convert("RGB")
        if committed_img.size != fresh_img.size:
            fail(
                f"figures/{FIGURE_NAME} content-level check FAILED: dimensions differ "
                f"(committed {committed_img.size} vs. regenerated {fresh_img.size})"
            )
            return
        diff = ImageChops.difference(committed_img, fresh_img)
        arr = np.asarray(diff)
        frac_differing = float((arr.max(axis=-1) > 8).mean())
        print(
            f"DISCLOSED: byte-identity check failed but the content-level check ran -- "
            f"{frac_differing:.4%} of pixels differ by more than a small tolerance "
            f"(committed sha256 {committed_sha[:12]}..., regenerated {fresh_sha[:12]}...)."
        )
        if frac_differing > 0.02:
            fail(
                f"figures/{FIGURE_NAME} content-level check FAILED: {frac_differing:.4%} "
                f"of pixels differ (2% threshold) -- this looks like a real data change, "
                f"not just font/rendering drift"
            )
        else:
            ok(
                f"figures/{FIGURE_NAME} content-level check PASSED with disclosure: not "
                f"byte-identical, but only {frac_differing:.4%} of pixels differ (within "
                f"the 2% cross-environment-rendering tolerance)"
            )
    except ImportError:
        fail(
            f"figures/{FIGURE_NAME} is not byte-identical and Pillow/numpy are "
            f"unavailable for the content-level fallback check -- cannot confirm "
            f"whether this is a real data change or a benign rendering difference. "
            f"Failing closed."
        )


def main() -> int:
    print("=== D10-C publication pack verification ===")
    check_source_gate_hashes()
    check_claim_citations_resolve()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        check_tables_reproducible(tmp_dir)
        check_figure_reproducible(tmp_dir)

    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) FAILED:")
        for msg in FAILURES:
            print(f"  - {msg}")
        return 1
    print("All publication-pack verification checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
