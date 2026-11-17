"""Tests for the fail-closed behaviour of the options-risk-study pack verifier.

``verify_pack.py`` has no ``--repo-root`` option: it derives the repository root
from its own location. Each test therefore copies the files the verifier reads
into ``tmp_path`` and runs the copied script there in a subprocess, so the real
repository tree is never written to. Figure regeneration (renderer dependent)
is deliberately not exercised; only the figure check's early "missing file"
exits, which return before any rendering, are covered.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PACK_REL = Path("publication/options-risk-study")
SCRIPT = REPO_ROOT / PACK_REL / "scripts" / "verify_pack.py"
RESULTS_REL = Path("results/historical_risk")
CONFIG_REL = Path("configs/experiments/options_historical_risk_study_v2.yaml")
MANIFESTS_REL = Path("data/manifests")
DATASET_IDS = (
    "yf_spy_daily_2015_2025_v1",
    "fred_dgs3mo_daily_2015_2025_v1",
    "fred_vixcls_daily_2015_2025_v1",
)
FIGURE_NAME = "var_es_corrected_vs_superseded_95_all_periods.png"
CONTRACT_NAME = "var_es_corrected_vs_superseded_95_all_periods.render-contract.json"

pytestmark = pytest.mark.skipif(not SCRIPT.exists(), reason="verify_pack.py not present")

# Runs selected checks of the *copied* verify_pack module and reports via exit code.
_DRIVER = """
import sys, tempfile
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import verify_pack as v
for name in sys.argv[2:]:
    if name == "hashes":
        v.check_recorded_hashes()
    elif name == "docs":
        v.check_doc_references_resolve()
    elif name == "tables":
        with tempfile.TemporaryDirectory() as t:
            v.check_tables_reproducible(Path(t))
    elif name == "figure_missing":
        with tempfile.TemporaryDirectory() as t:
            v.check_figure_reproducible(Path(t))
sys.exit(1 if v.FAILURES else 0)
"""


def _run(root: Path, *checks: str) -> subprocess.CompletedProcess[str]:
    driver = root.parent / "driver.py"
    driver.write_text(_DRIVER, encoding="utf-8")
    scripts = root / PACK_REL / "scripts"
    return subprocess.run(
        [sys.executable, "-I", str(driver), str(scripts), *checks],
        capture_output=True,
        text=True,
        timeout=60,
    )


@pytest.fixture
def pack(tmp_path: Path) -> Path:
    """Copy of everything verify_pack's non-figure checks read (figures/ omitted)."""
    root = tmp_path / "repo"
    ignore = shutil.ignore_patterns("__pycache__")
    shutil.copytree(
        REPO_ROOT / PACK_REL,
        root / PACK_REL,
        ignore=shutil.ignore_patterns("__pycache__", "figures"),
    )
    shutil.copytree(REPO_ROOT / RESULTS_REL, root / RESULTS_REL, ignore=ignore)
    shutil.copytree(REPO_ROOT / MANIFESTS_REL, root / MANIFESTS_REL, ignore=ignore)
    (root / CONFIG_REL).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO_ROOT / CONFIG_REL, root / CONFIG_REL)
    return root


def _load_module():
    spec = importlib.util.spec_from_file_location("options_verify_pack_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pinned_files() -> list[Path]:
    """Relative paths of every file whose sha256 is cited in reproducibility.json."""
    mod = _load_module()
    bt = mod.build_tables
    paths = [REPO_ROOT / CONFIG_REL]
    for group in (bt.CURRENT_ARTIFACTS, bt.SUPERSEDED_VOL_UNITS, bt.SUPERSEDED_BACKTEST):
        paths.extend(group.values())
    return [p.relative_to(REPO_ROOT) for p in paths]


def _flip_last_byte(path: Path) -> None:
    data = bytearray(path.read_bytes())
    data[-1] ^= 0x01
    path.write_bytes(bytes(data))


def test_sha256_of_known_input(tmp_path: Path) -> None:
    f = tmp_path / "x.txt"
    f.write_bytes(b"abc")
    mod = _load_module()
    assert mod.sha256_of(f) == hashlib.sha256(b"abc").hexdigest()
    assert mod.sha256_of(f) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_doc_reference_regex_on_known_input() -> None:
    rx = _load_module().DOC_REF_RE
    text = "see `CASE-STUDY.md`, `notes_v2.md` and `not-md.txt`; plain CASE.md is ignored"
    assert rx.findall(text) == ["CASE-STUDY.md", "notes_v2.md"]
    assert isinstance(rx, re.Pattern)


def test_pinned_file_list_is_complete() -> None:
    # config + 3 current + 3 superseded (units) + 3 superseded (backtest)
    assert len(_pinned_files()) == 10


def test_committed_pack_passes_offline_checks(pack: Path) -> None:
    r = _run(pack, "hashes", "docs", "tables")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "FAIL" not in r.stdout
    assert "OK:" in r.stdout


@pytest.mark.parametrize("rel", _pinned_files(), ids=lambda p: p.name + ":" + p.parent.name)
def test_one_byte_tamper_of_each_pinned_file_fails_hashes(pack: Path, rel: Path) -> None:
    _flip_last_byte(pack / rel)
    r = _run(pack, "hashes")
    assert r.returncode != 0
    assert "FAIL: reproducibility.json does NOT contain the freshly-recomputed sha256" in r.stdout


def test_missing_pinned_file_fails_closed(pack: Path) -> None:
    (pack / _pinned_files()[1]).unlink()
    r = _run(pack, "hashes")
    assert r.returncode != 0
    assert "FileNotFoundError" in r.stderr


def test_wrong_recorded_hash_fails_hashes(pack: Path) -> None:
    repro = pack / PACK_REL / "reproducibility.json"
    digest = hashlib.sha256((pack / CONFIG_REL).read_bytes()).hexdigest()
    text = repro.read_text(encoding="utf-8")
    assert digest in text
    repro.write_text(text.replace(digest, "0" * 64), encoding="utf-8")
    r = _run(pack, "hashes")
    assert r.returncode != 0
    assert f"({digest})" in r.stdout
    assert "config" in r.stdout


def test_tampered_dataset_manifest_hash_fails_hashes(pack: Path) -> None:
    path = pack / MANIFESTS_REL / f"{DATASET_IDS[0]}.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["sha256"]["dataset_canonical"] = "f" * 64
    path.write_text(json.dumps(manifest), encoding="utf-8")
    r = _run(pack, "hashes")
    assert r.returncode != 0
    assert f"dataset:{DATASET_IDS[0]}" in r.stdout


def test_missing_reproducibility_json_fails_closed(pack: Path) -> None:
    (pack / PACK_REL / "reproducibility.json").unlink()
    r = _run(pack, "hashes")
    assert r.returncode != 0


def test_dangling_document_reference_fails(pack: Path) -> None:
    doc = pack / PACK_REL / "CASE-STUDY.md"
    doc.write_text(doc.read_text("utf-8") + "\nSee `NO-SUCH-DOC.md`.\n", encoding="utf-8")
    r = _run(pack, "docs")
    assert r.returncode != 0
    assert "CASE-STUDY.md references `NO-SUCH-DOC.md`" in r.stdout


def test_missing_public_document_fails_closed(pack: Path) -> None:
    (pack / PACK_REL / "TECHNICAL-PAPER.md").unlink()
    r = _run(pack, "docs")
    assert r.returncode != 0


@pytest.mark.parametrize(
    "name",
    [
        "var_es_corrected_vs_prefix.csv",
        "hedging_experiment_summary.csv",
        "kupiec_christoffersen.csv",
        "case_study_dev_first_roll.json",
        "dataset_and_artifact_hashes.json",
    ],
)
def test_tampered_committed_table_fails_tables(pack: Path, name: str) -> None:
    _flip_last_byte(pack / PACK_REL / "tables" / name)
    r = _run(pack, "tables")
    assert r.returncode != 0
    assert f"tables/{name} does NOT match" in r.stdout


def test_missing_committed_table_fails_tables(pack: Path) -> None:
    (pack / PACK_REL / "tables" / "kupiec_christoffersen.csv").unlink()
    r = _run(pack, "tables")
    assert r.returncode != 0
    assert "tables/kupiec_christoffersen.csv is missing" in r.stdout


def test_tampered_source_artifact_fails_tables(pack: Path) -> None:
    # A changed result artifact must not silently agree with the committed tables.
    rel = _pinned_files()[1]
    _flip_last_byte(pack / rel)
    r = _run(pack, "tables")
    assert r.returncode != 0


def test_figure_check_fails_closed_when_figures_absent(pack: Path) -> None:
    # figures/ is not in the copy, so the check exits before any rendering.
    r = _run(pack, "figure_missing")
    assert r.returncode != 0
    assert f"figures/{FIGURE_NAME} is missing from the committed pack" in r.stdout


def test_figure_check_fails_closed_when_contract_absent(pack: Path) -> None:
    figures = pack / PACK_REL / "figures"
    figures.mkdir()
    shutil.copy2(REPO_ROOT / PACK_REL / "figures" / FIGURE_NAME, figures / FIGURE_NAME)
    r = _run(pack, "figure_missing")
    assert r.returncode != 0
    assert f"figures/{CONTRACT_NAME} is missing from the committed pack" in r.stdout
