#!/usr/bin/env python3
"""Reproducibility bundle -- CI verification script.

Fails closed if:
  1. Any sha256 for a study artifact/config/dataset (dataset manifests' own
     `dataset_canonical` field, the frozen config, all current + superseded
     result artifacts) is not cited in reproducibility.json, i.e. the
     recorded hash is stale relative to the currently-committed file.
  2. Any public document in the bundle references a Markdown file in this
     directory that does not exist (dangling cross-reference).
  3. Regenerating the tables and the figure's canonical render contract from
     the same committed source artifacts differs from what is committed.
     CSV/JSON tables and the semantic render contract are compared
     byte-for-byte with no tolerance. The contract fixes all plotted values,
     labels, visual encodings, source hashes, and dimensions. The committed
     PNG is separately protected by its published SHA-256 and validated as a
     readable image of the contracted dimensions. Regenerated PNG bytes are
     reported and checked with the existing 2% differing-pixel gate. Contract
     agreement alone cannot establish that the rendered image is equivalent.

This script performs NO network calls and NEVER re-runs
scripts/run_historical_risk_study_v2.py or touches results/historical_risk/,
data/, configs/, or src/ -- it only reads already-committed files and
writes every regenerated output to a private temporary directory. It never
overwrites the committed publication figure during verification.
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
REPRODUCIBILITY = PUB_DIR / "reproducibility.json"
PUBLIC_DOCS = ("TECHNICAL-PAPER.md", "CASE-STUDY.md", "RESULT-SOURCE-MAP.md")
RESULT_SOURCE_MAP = PUB_DIR / "RESULT-SOURCE-MAP.md"
FIGURE_NAME = "var_es_corrected_vs_superseded_95_all_periods.png"
CONTRACT_NAME = "var_es_corrected_vs_superseded_95_all_periods.render-contract.json"

FAILURES: list[str] = []


def fail(msg: str) -> None:
    FAILURES.append(msg)
    print(f"FAIL: {msg}")


def ok(msg: str) -> None:
    print(f"OK:   {msg}")


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_recorded_hashes() -> None:
    gate_text = REPRODUCIBILITY.read_text(encoding="utf-8")
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
            ok(f"reproducibility.json records the correct, currently-true sha256 for {name}")
        else:
            fail(
                f"reproducibility.json does NOT contain the freshly-recomputed sha256 for "
                f"{name} ({digest}) -- the cited hash is stale, or the source file "
                f"changed since reproducibility.json was written"
            )


DOC_REF_RE = re.compile(r"`([A-Za-z0-9_-]+\.md)`")


def check_doc_references_resolve() -> None:
    for doc in PUBLIC_DOCS:
        text = (PUB_DIR / doc).read_text(encoding="utf-8")
        for name in sorted(set(DOC_REF_RE.findall(text))):
            # Only bundle-level documents use UPPER-CASE names (e.g. CASE-STUDY.md).
            if not name[:-3].isupper() or (PUB_DIR / name).exists():
                continue
            fail(f"{doc} references `{name}`, which does not exist in {PUB_DIR.name}/")
        ok(f"{doc}: every referenced bundle document exists")


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
    committed_contract_path = build_tables.FIGURES_DIR / CONTRACT_NAME
    if not committed_path.exists():
        fail(f"figures/{FIGURE_NAME} is missing from the committed pack")
        return
    if not committed_contract_path.exists():
        fail(f"figures/{CONTRACT_NAME} is missing from the committed pack")
        return

    committed_bytes = committed_path.read_bytes()
    committed_sha = hashlib.sha256(committed_bytes).hexdigest()
    reproducibility = build_tables.load_json(REPRODUCIBILITY)
    recorded_sha = reproducibility["publication_pack_derived_artifacts"]["figure_output"][
        "sha256_committed_png"
    ]
    recorded_contract_sha = reproducibility["publication_pack_derived_artifacts"]["figure_output"][
        "render_contract_sha256"
    ]
    if committed_sha != recorded_sha:
        fail(
            f"figures/{FIGURE_NAME} sha256 is {committed_sha}, not the published "
            f"committed-PNG hash {recorded_sha}; the presentation artifact changed"
        )
    else:
        ok(f"figures/{FIGURE_NAME} matches its published sha256 ({committed_sha[:12]}...)")

    committed_contract_sha = sha256_of(committed_contract_path)
    if committed_contract_sha != recorded_contract_sha:
        fail(
            f"figures/{CONTRACT_NAME} sha256 is {committed_contract_sha}, not the "
            f"published contract hash {recorded_contract_sha}"
        )
    else:
        ok(
            f"figures/{CONTRACT_NAME} matches its published sha256 "
            f"({committed_contract_sha[:12]}...)"
        )

    fresh_path = tmp_dir / FIGURE_NAME
    fresh_contract_path = tmp_dir / CONTRACT_NAME
    result = build_figures.build_figure(fresh_path, fresh_contract_path)
    if result is None:
        fail(
            "matplotlib is not importable in this CI job -- the figure could not be "
            "regenerated to verify it; check the dependency-install step's log."
        )
        return

    fresh_bytes = fresh_path.read_bytes()
    fresh_sha = hashlib.sha256(fresh_bytes).hexdigest()
    committed_contract = committed_contract_path.read_bytes()
    fresh_contract = fresh_contract_path.read_bytes()
    if committed_contract != fresh_contract:
        fail(
            f"figures/{CONTRACT_NAME} does NOT match the freshly recomputed semantic "
            "contract -- a plotted value, label, source hash, dimension, ordering, or "
            "material visual encoding changed"
        )
    else:
        ok(f"figures/{CONTRACT_NAME} matches freshly recomputed content byte-for-byte")

    try:
        import io

        import numpy as np
        from PIL import Image, ImageChops

        committed_img = Image.open(io.BytesIO(committed_bytes)).convert("RGB")
        fresh_img = Image.open(io.BytesIO(fresh_bytes)).convert("RGB")
        expected_dimensions = tuple(
            json.loads(committed_contract)["figure"]["expected_pixel_dimensions"]
        )
        if committed_img.size != expected_dimensions:
            fail(
                f"figures/{FIGURE_NAME} dimensions {committed_img.size} do not match "
                f"the semantic contract {expected_dimensions}"
            )
        else:
            ok(f"figures/{FIGURE_NAME} committed dimensions match {expected_dimensions}")
        if fresh_img.size != expected_dimensions:
            fail(
                f"regenerated {FIGURE_NAME} dimensions {fresh_img.size} do not match "
                f"the semantic contract {expected_dimensions}"
            )
        else:
            ok(f"regenerated {FIGURE_NAME} dimensions match {expected_dimensions}")
        if committed_img.size == fresh_img.size:
            diff = np.asarray(ImageChops.difference(committed_img, fresh_img))
            fraction = float((diff.max(axis=-1) > 8).mean())
            print(f"DISCLOSED: {fraction:.4%} of pixels differ by more than 8/255.")
            if fraction > 0.02:
                fail(
                    f"figure visual comparison differs at {fraction:.4%} of pixels "
                    "(existing 2% threshold). Semantic contract agreement does not "
                    "resolve this visual mismatch; rendering investigation is required."
                )
            else:
                ok("figure visual comparison is within the existing 2% threshold")
    except ImportError:
        fail(
            "Pillow is unavailable; cannot validate committed and regenerated PNG "
            "dimensions against the semantic render contract"
        )

    if fresh_sha == committed_sha:
        ok(f"figures/{FIGURE_NAME} also regenerates byte-identical in this environment")
    else:
        print(
            "DISCLOSED: regenerated PNG bytes differ from the fixed committed PNG "
            f"(committed {committed_sha[:12]}..., regenerated {fresh_sha[:12]}...). "
            "Semantic contract and visual comparison results are reported separately above. "
            "Contract agreement does not waive a failed visual comparison."
        )


def main() -> int:
    print("=== Reproducibility bundle verification ===")
    check_recorded_hashes()
    check_doc_references_resolve()
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
    print("All reproducibility-bundle verification checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
