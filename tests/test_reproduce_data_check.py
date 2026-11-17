"""Offline tests for scripts/reproduce_data_check.py (no network, tiny synthetic CSVs)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "reproduce_data_check.py"

HEADER = "Date,Capital Gains,Close,Dividends,High,Low,Open,Stock Splits,Volume\n"
ROW1 = "2020-01-02,0.0,10.0,0.0,11.0,9.0,10.0,0.0,100\n"
ROW2 = "2020-01-03,0.0,10.5,0.2,11.0,9.0,10.0,0.0,120\n"
GOOD = HEADER + ROW1 + ROW2
DRIFTED = HEADER + ROW1.replace(",10.0,", ",9.9,", 1) + ROW2.replace(",10.5,", ",10.4,", 1)


@pytest.fixture(scope="module")
def chk():
    spec = importlib.util.spec_from_file_location("reproduce_data_check", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _sha(chk, text: str, tmp_path: Path) -> str:
    p = tmp_path / "_h.csv"
    p.write_bytes(text.encode())
    return chk.sha256_file(p)


def _repo(chk, tmp_path: Path, frozen: dict[str, str]):
    """A fake repo with one frozen manifest whose hashes are those of ``frozen``."""
    root = tmp_path / "repo"
    manifests = root / "data" / "manifests"
    manifests.mkdir(parents=True)
    hashes = {f"{s}.csv": _sha(chk, text, tmp_path) for s, text in frozen.items()}
    manifest = {
        "dataset_id": "fake_v1",
        "source": "yfinance",
        "source_version": "1.7.0",
        "symbols": list(frozen),
        "interval": "1d",
        "requested_start": "2020-01-01",
        "requested_end_exclusive": "2020-02-01",
        "actual_start": {s: "2020-01-02" for s in frozen},
        "actual_end": {s: "2020-01-03" for s in frozen},
        "row_counts": {s: 2 for s in frozen},
        "missing_counts": {s: 0 for s in frozen},
        "actions": {
            s: {
                "dividends": {"present": True, "nonzero_count": 1},
                "stock_splits": {"present": True, "nonzero_count": 0},
                "capital_gains": {"present": True, "nonzero_count": 0},
            }
            for s in frozen
        },
        "retrieval_timestamp_utc": "2026-01-01T00:00:00Z",
        "sha256": {**hashes, "dataset_canonical": chk.canonical_dataset_hash(hashes)},
        "parameters": {"start": "2020-01-01", "end": "2020-02-01", "interval": "1d"},
    }
    path = manifests / "fake_v1.json"
    path.write_text(json.dumps(manifest, indent=2))
    return root, path


def _fetcher(files: dict[str, str]):
    def fetch(spec, out_dir: Path):
        for sym, text in files.items():
            (out_dir / f"{sym}.csv").write_bytes(text.encode())
        return {"retrieval_timestamp_utc": "2026-11-17T00:00:00Z", "excluded": []}

    return fetch


CONFIGS = ({"manifest": "fake_v1.json", "kind": "yfinance_script", "script": "x.py"},)


def _run(chk, root: Path, fetch, tmp_path: Path, extra=()):
    json_out = tmp_path / "out" / "report.json"
    json_out.parent.mkdir(exist_ok=True)
    md_out = tmp_path / "out" / "report.md"
    code = chk.main(
        ["--json-out", str(json_out), "--md-out", str(md_out), *extra],
        fetch=fetch,
        repo_root=root,
        configs=CONFIGS,
    )
    return code, json.loads(json_out.read_text()), md_out.read_text()


def test_match(chk, tmp_path):
    root, _ = _repo(chk, tmp_path, {"AAA": GOOD, "BBB": GOOD})
    code, report, md = _run(chk, root, _fetcher({"AAA": GOOD, "BBB": GOOD}), tmp_path)
    ds = report["datasets"][0]
    assert code == 0
    assert ds["classification"] == "MATCH"
    assert ds["files_matched"] == 2
    assert all(f["match"] is True for f in ds["files"])
    assert ds["dataset_canonical"]["match"] is True
    assert "| fake_v1 |" in md and "MATCH" in md


def test_drift_is_described_and_exit_zero(chk, tmp_path):
    root, _ = _repo(chk, tmp_path, {"AAA": GOOD, "BBB": GOOD})
    code, report, md = _run(chk, root, _fetcher({"AAA": GOOD, "BBB": DRIFTED}), tmp_path)
    ds = report["datasets"][0]
    assert code == 0
    assert ds["classification"] == "DATA DRIFT (not a reproduction failure of the analysis)"
    assert [f["match"] for f in ds["files"]] == [True, False]
    assert ds["dataset_canonical"]["match"] is False
    assert ds["files"][1]["rows"]["match"] is True  # metadata unchanged, values drifted
    assert any("bytes differ in values only" in s for s in ds["drift_summary"])
    assert "DATA DRIFT" in md


def test_metadata_drift_is_reported(chk, tmp_path):
    root, _ = _repo(chk, tmp_path, {"AAA": GOOD})
    longer = GOOD + "2020-01-06,0.0,10.6,0.0,11.0,9.0,10.0,0.0,90\n"
    _, report, _ = _run(chk, root, _fetcher({"AAA": longer}), tmp_path)
    f = report["datasets"][0]["files"][0]
    assert f["rows"] == {"expected": 2, "fresh": 3, "match": False}
    assert f["last_date"]["fresh"] == "2020-01-06"


def test_missing_values_counted(chk, tmp_path):
    text = HEADER + ROW1.replace("0.0,10.0,", "0.0,,", 1) + ROW2
    p = tmp_path / "m.csv"
    p.write_text(text)
    s = chk.summarize_csv(p)
    assert s["missing_values"] == 1
    assert s["actions"]["dividends"]["nonzero_count"] == 1


def test_missing_fresh_file_is_a_drift_not_a_crash(chk, tmp_path):
    root, _ = _repo(chk, tmp_path, {"AAA": GOOD, "BBB": GOOD})
    code, report, _ = _run(chk, root, _fetcher({"AAA": GOOD}), tmp_path)
    ds = report["datasets"][0]
    assert code == 0
    assert ds["files"][1]["fresh_file_present"] is False
    assert ds["files"][1]["match"] is False
    assert ds["classification"].startswith("DATA DRIFT")


def test_fetch_failure_exits_two(chk, tmp_path):
    root, _ = _repo(chk, tmp_path, {"AAA": GOOD})

    def boom(spec, out_dir):
        raise chk.FetchError("network down")

    code, report, md = _run(chk, root, boom, tmp_path)
    assert code == 2
    assert report["datasets"][0]["classification"] == "FETCH FAILED"
    assert "network down" in report["datasets"][0]["error"]
    assert report["exit_code"] == 2 and "FETCH FAILED" in md


def test_refuses_to_write_report_into_manifest_dir(chk, tmp_path):
    root, path = _repo(chk, tmp_path, {"AAA": GOOD})
    before = path.read_text()
    code = chk.main(
        ["--json-out", str(path)], fetch=_fetcher({"AAA": GOOD}), repo_root=root, configs=CONFIGS
    )
    assert code == 2
    assert path.read_text() == before


def test_frozen_manifest_untouched_after_run(chk, tmp_path):
    root, path = _repo(chk, tmp_path, {"AAA": GOOD})
    before = path.read_bytes()
    _run(chk, root, _fetcher({"AAA": DRIFTED}), tmp_path)
    assert path.read_bytes() == before


def test_fetch_script_removes_throwaway_manifest_and_flags_changes(chk, tmp_path, monkeypatch):
    root, path = _repo(chk, tmp_path, {"AAA": GOOD})
    (root / "scripts").mkdir()
    (root / "scripts" / "x.py").write_text("")
    spec = {
        "dataset_id": "fake_v1",
        "script": "x.py",
        "symbols": ["AAA"],
        "start": "2020-01-01",
        "end": "2020-02-01",
        "interval": "1d",
        "extra_args": [],
    }
    throwaway = root / "data" / "manifests" / "fake_v1_reprocheck.json"
    out = tmp_path / "raw"
    out.mkdir()

    def fake_run(cmd, **kwargs):
        assert cmd[cmd.index("--dataset-id") + 1] == "fake_v1_reprocheck"
        assert "--no-freeze" in cmd and "--raw-dir" in cmd
        throwaway.write_text("{}")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(chk, "_run", fake_run)
    chk.fetch_yfinance_script(spec, out, root)
    assert not throwaway.exists()
    assert path.exists()

    def tamper(cmd, **kwargs):
        path.write_text("{}")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(chk, "_run", tamper)
    with pytest.raises(chk.FetchError, match="changed"):
        chk.fetch_yfinance_script(spec, out, root)


def test_fetch_script_refuses_raw_dir_inside_repo(chk, tmp_path):
    root, _ = _repo(chk, tmp_path, {"AAA": GOOD})
    spec = {"dataset_id": "fake_v1", "script": "x.py", "symbols": ["AAA"]}
    with pytest.raises(chk.FetchError, match="inside the repository"):
        chk.fetch_yfinance_script(spec, root / "data" / "raw", root)


FRED_BODY = (
    "observation_date,VIXCLS\n2014-12-31,19.2\n2015-01-01,.\n2015-01-02,17.79\n2026-01-01,15\n"
)


def test_parse_fred_keeps_missing_as_empty_and_filters_dates(chk):
    rows = chk.parse_fred_csv(FRED_BODY, "VIXCLS", "2015-01-01", "2026-01-01")
    assert rows == [["2015-01-01", ""], ["2015-01-02", "17.79"]]


def test_fetch_fred_retries_then_writes_published_shape(chk, tmp_path):
    calls = []

    def runner(cmd, timeout):
        calls.append(cmd)
        if len(calls) < 3:
            return subprocess.CompletedProcess(cmd, 22, "", "curl: (22) 403")
        return subprocess.CompletedProcess(cmd, 0, FRED_BODY, "")

    spec = {"series": "VIXCLS", "start": "2015-01-01", "end": "2026-01-01"}
    meta = chk.fetch_fred(spec, tmp_path, runner=runner, sleep=lambda _s: None)
    assert len(calls) == 3
    assert calls[0][:6] == ["curl", "-sS", "--fail", "-L", "--max-time", "120"]
    assert calls[0][-1] == "https://fred.stlouisfed.org/graph/fredgraph.csv?id=VIXCLS"
    assert meta["retrieval_timestamp_utc"].endswith("Z")
    data = (tmp_path / "VIXCLS.csv").read_bytes()
    assert data == b"observation_date,VIXCLS\r\n2015-01-01,\r\n2015-01-02,17.79\r\n"


def test_fetch_fred_gives_up_after_three_attempts(chk, tmp_path):
    attempts = []

    def runner(cmd, timeout):
        attempts.append(1)
        return subprocess.CompletedProcess(cmd, 22, "", "curl: (22) 403")

    spec = {"series": "VIXCLS", "start": "2015-01-01", "end": "2026-01-01"}
    with pytest.raises(chk.FetchError, match="3 attempts"):
        chk.fetch_fred(spec, tmp_path, runner=runner, sleep=lambda _s: None)
    assert len(attempts) == 3


def test_fred_manifest_layout_match_and_drift(chk, tmp_path):
    csv_text = "observation_date,VIXCLS\r\n2015-01-01,\r\n2015-01-02,17.79\r\n"
    sha = _sha(chk, csv_text, tmp_path)
    root = tmp_path / "repo"
    manifests = root / "data" / "manifests"
    manifests.mkdir(parents=True)
    manifest = {
        "dataset_id": "fred_vixcls_test",
        "source": "fred",
        "source_series_id": "VIXCLS",
        "requested_start": "2015-01-01",
        "requested_end_exclusive": "2026-01-01",
        "actual_start": "2015-01-01",
        "actual_end": "2015-01-02",
        "row_count": 2,
        "missing_value_count": 1,
        "retrieval_timestamp_utc": "2026-09-17T02:30:12Z",
        "sha256": {"VIXCLS.csv": sha, "dataset_canonical": sha},
        "parameters": {"start": "2015-01-01", "end": "2026-01-01", "interval": "1d"},
    }
    (manifests / "fred_vixcls_test.json").write_text(json.dumps(manifest))
    configs = ({"manifest": "fred_vixcls_test.json", "kind": "fred", "script": None},)

    def make_fetch(text):
        def fetch(spec, out_dir):
            assert spec["series"] == "VIXCLS"
            (out_dir / "VIXCLS.csv").write_bytes(text.encode())
            return {"retrieval_timestamp_utc": "2026-11-17T00:00:00Z", "excluded": []}

        return fetch

    out = tmp_path / "r.json"
    code = chk.main(
        ["--json-out", str(out)], fetch=make_fetch(csv_text), repo_root=root, configs=configs
    )
    ds = json.loads(out.read_text())["datasets"][0]
    assert code == 0 and ds["classification"] == "MATCH"
    assert ds["files"][0]["missing_values"] == {"expected": 1, "fresh": 1, "match": True}

    revised = csv_text.replace("17.79", "17.80") + "2015-01-05,18.0\r\n"
    chk.main(["--json-out", str(out)], fetch=make_fetch(revised), repo_root=root, configs=configs)
    ds = json.loads(out.read_text())["datasets"][0]
    assert ds["classification"].startswith("DATA DRIFT")
    assert ds["files"][0]["rows"]["fresh"] == 3
