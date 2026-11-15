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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=OUT)
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
    lo, hi = pd.Timestamp(SPAN[0]), pd.Timestamp(SPAN[1])
    spy = spy[(spy.index >= lo) & (spy.index <= hi)]
    frame, quality = dvb.prepare_frame(spy, vix, rate)

    # Scale for P4: fitted to DEV pairs only (zero-mean synthetic pairs).
    dev = frame[frame.index <= pd.Timestamp(DEV_END)]
    r = np.log(dev["spot"]).diff().dropna().to_numpy()
    dv = np.log(dev["vix"]).diff().dropna().to_numpy()
    scale = dvb.fit_t4_scale(r, dv)

    result = dvb.run_study(frame, p4_paths=args.p4_paths, p4_scale=scale)
    payload = {
        "study": "daily VaR and ES backtest of the standardised options book",
        "protocol": "research/daily_var_backtest/PROTOCOL.md",
        "classification": "PREVIOUSLY INSPECTED / HISTORICAL EVALUATION",
        "dataset_manifest": manifest,
        "data_quality": quality,
        "p4_scale_fitted_to_dev": scale,
        "result": result,
        "not_implemented_in_this_runner": ["P3 published replication"],
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
