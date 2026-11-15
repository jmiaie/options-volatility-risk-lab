#!/usr/bin/env python3
"""Run the daily VaR/ES backtest of the standardised options book.

Refuses to run unless research/daily_var_backtest/PROTOCOL.md (the frozen protocol) exists. Reads a
raw-data directory that is not in this repository, holding SPY.csv, VIXCLS.csv and DGS3MO.csv in
the formats of the published study, plus its manifest. Writes
results/daily_var_backtest/daily_var_backtest.json and changes no existing artifact.

    python research/daily_var_backtest/run_daily_var_backtest.py \\
        --raw-dir /path/to/raw --manifest /path/to/manifest.json
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import daily_var_backtest as dvb  # noqa: E402
from options_risk.historical_risk_study_v2 import (  # noqa: E402
    load_fred_series_decimal,
    load_spy_close,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PROTOCOL = HERE / "PROTOCOL.md"
OUT = ROOT / "results/daily_var_backtest/daily_var_backtest.json"
SPAN = ("2015-01-01", "2025-12-31")
DEV_END = "2023-12-31"
PUBLISHED_RESULTS_GLOB = "results/historical_risk/options_hist_risk_v2_*.json"
PUBLISHED_SPY_SHA256 = "0c83ab20bf76ec39b97855ac393b7bc74363bd4ff373381f0a92842a2c7c6a63"
PUBLISHED_REL_TOL = 1e-6
VINTAGE_NOTE = (
    "Differences from the published values reflect data vintage (the supplied SPY series is not "
    "the published snapshot) and are informational only; P3 here tests code equivalence."
)


def clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, (float, np.floating)):
        return None if not math.isfinite(float(value)) else float(f"{float(value):.10g}")
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    return value


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_published_hs_var(results_dir: Path) -> dict[pd.Timestamp, float]:
    """roll_date -> hs_var_95_primary_every_roll from the committed v2 result snapshots."""
    out: dict[pd.Timestamp, float] = {}
    files = sorted(glob.glob(str(results_dir / Path(PUBLISHED_RESULTS_GLOB).name)))
    if not files:
        raise FileNotFoundError(f"no published snapshots in {results_dir}")
    for f in files:
        study = json.loads(Path(f).read_text(encoding="utf-8"))["nonlinear_portfolio_study"]
        for snap in study["snapshots"]:
            out[pd.Timestamp(snap["roll_date"])] = float(snap["hs_var_95_primary_every_roll"])
    return out


def run_p3(
    spy_path: Path, spy: pd.Series, rate: pd.Series, published: dict[pd.Timestamp, float]
) -> dict[str, Any]:
    """P3 code equivalence plus the sha256-gated exact-replication check.

    Code equivalence must pass in every case. If the SPY file is the published snapshot (sha256
    equal to PUBLISHED_SPY_SHA256), production's VaR must also match the published value to 1e-6
    relative at every roll; otherwise the published differences are recorded as informational.
    """
    res = dvb.p3_code_equivalence(spy, rate, sorted(published), published)
    exact = sha256_file(spy_path) == PUBLISHED_SPY_SHA256
    res["spy_sha256"] = sha256_file(spy_path)
    res["published_snapshot_supplied"] = exact
    res["code_equivalence_passed"] = res["passed"]
    diffs = [r["rel_diff_vs_published"] for r in res["rolls"] if "rel_diff_vs_published" in r]
    res["max_rel_diff_vs_published"] = max(diffs) if diffs else None
    if exact:
        res["published_match_passed"] = bool(
            len(diffs) == len(res["rolls"]) and all(d <= PUBLISHED_REL_TOL for d in diffs)
        )
        res["passed"] = bool(res["passed"] and res["published_match_passed"])
    else:
        res["note"] = VINTAGE_NOTE
    return res


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--published-dir", type=Path, default=ROOT / "results/historical_risk")
    parser.add_argument("--p4-paths", type=int, default=2000)
    args = parser.parse_args(argv)

    if not PROTOCOL.exists():
        print(
            f"REFUSING TO RUN: {PROTOCOL} does not exist. The frozen protocol must be committed "
            "and pushed before any result is computed.",
            file=sys.stderr,
        )
        return 2

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    spy = load_spy_close(str(args.raw_dir / "SPY.csv"))
    vix = load_fred_series_decimal(str(args.raw_dir / "VIXCLS.csv"), "VIXCLS") * 100.0
    rate = load_fred_series_decimal(str(args.raw_dir / "DGS3MO.csv"), "DGS3MO")

    # P3 runs first, on the data as provided, before any result is computed.
    p3 = run_p3(args.raw_dir / "SPY.csv", spy, rate, load_published_hs_var(args.published_dir))
    if not p3["passed"]:
        stop = {
            "study": "daily VaR and ES backtest of the standardised options book",
            "protocol": "research/daily_var_backtest/PROTOCOL.md",
            "dataset_manifest": manifest,
            "result": {"preconditions": {"P3": p3}, "stopped": "P3 failed; no tests computed"},
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(clean(stop), indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"P3 FAILED; wrote {args.out}", file=sys.stderr)
        return 1

    lo, hi = pd.Timestamp(SPAN[0]), pd.Timestamp(SPAN[1])
    spy = spy[(spy.index >= lo) & (spy.index <= hi)]
    frame, quality = dvb.prepare_frame(spy, vix, rate)

    # Scale for P4: fitted to DEV pairs only (zero-mean synthetic pairs).
    dev = frame[frame.index <= pd.Timestamp(DEV_END)]
    r = np.log(dev["spot"]).diff().dropna().to_numpy()
    dv = np.log(dev["vix"]).diff().dropna().to_numpy()
    scale = dvb.fit_t4_scale(r, dv)

    result = dvb.run_study(frame, p4_paths=args.p4_paths, p4_scale=scale)
    result["preconditions"] = {"P3": p3, **result["preconditions"]}
    payload = {
        "study": "daily VaR and ES backtest of the standardised options book",
        "protocol": "research/daily_var_backtest/PROTOCOL.md",
        "classification": "PREVIOUSLY INSPECTED / HISTORICAL EVALUATION",
        "dataset_manifest": manifest,
        "data_quality": quality,
        "p4_scale_fitted_to_dev": scale,
        "result": result,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(clean(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {args.out}")
    print(f"stopped: {result.get('stopped')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
