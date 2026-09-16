#!/usr/bin/env python3
"""Run Directive #9 Options historical risk validation on frozen local data only.

Examples:
  python scripts/run_historical_risk_study.py \\
    --config configs/experiments/options_historical_risk_study_v1.yaml

  # Holdout (2025) only after YAML status is frozen-for-holdout
  python scripts/run_historical_risk_study.py --allow-holdout --skip-dev --skip-validation
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from options_risk.historical_risk_study import (
    PeriodSpec,
    load_close_panel,
    run_period_study,
    write_json_artifact,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _append_ledger(path: Path, row: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "experiment_id",
        "repo",
        "branch",
        "dataset_id",
        "config_path",
        "status",
        "period_name",
        "period_start",
        "period_end",
        "horizons",
        "seed",
        "primary_symbol",
        "artifact_path",
        "artifact_sha256",
        "key_metrics_json",
        "notes",
        "created_utc",
    ]
    exists = path.exists() and path.stat().st_size > 0
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in fieldnames})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/experiments/options_historical_risk_study_v1.yaml"),
    )
    parser.add_argument("--raw-dir", type=Path, default=None)
    parser.add_argument("--results-dir", type=Path, default=Path("results/historical_risk"))
    parser.add_argument("--ledger", type=Path, default=Path("research/experiment-ledger.csv"))
    parser.add_argument("--branch", default="research/historical-risk-validation")
    parser.add_argument("--allow-holdout", action="store_true")
    parser.add_argument("--skip-dev", action="store_true")
    parser.add_argument("--skip-validation", action="store_true")
    parser.add_argument("--holdout-only", action="store_true")
    args = parser.parse_args(argv)

    root = _repo_root()
    config_path = args.config if args.config.is_absolute() else root / args.config
    experiment = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    dataset_id = str(experiment["dataset_id"])
    status = str(experiment.get("status", ""))
    manifest_path = root / "data" / "manifests" / f"{dataset_id}.json"
    if not manifest_path.exists():
        print(f"ERROR: missing manifest {manifest_path}", file=sys.stderr)
        return 2
    manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "DATA FROZEN":
        print(f"ERROR: dataset not DATA FROZEN (status={manifest.get('status')})", file=sys.stderr)
        return 2

    symbols = list(manifest["symbols"])
    primary_symbol = str(experiment.get("primary_symbol") or symbols[0])
    raw_dir = args.raw_dir or (root / "data" / "raw" / dataset_id)
    panel = load_close_panel(raw_dir, symbols)

    periods = experiment["periods"]
    formation = PeriodSpec(
        "formation_dev",
        periods["formation_dev"]["start"],
        periods["formation_dev"]["end_inclusive"],
    )
    validation = PeriodSpec(
        "validation",
        periods["validation"]["start"],
        periods["validation"]["end_inclusive"],
    )
    holdout = PeriodSpec(
        "holdout",
        periods["holdout"]["start"],
        periods["holdout"]["end_inclusive"],
    )

    results_dir = args.results_dir if args.results_dir.is_absolute() else root / args.results_dir
    ledger_path = args.ledger if args.ledger.is_absolute() else root / args.ledger
    exp_id = str(experiment["experiment_id"])
    rel_config = str(config_path.relative_to(root))

    jobs: list[tuple[str, PeriodSpec, PeriodSpec]] = []
    if args.holdout_only:
        jobs.append((f"{exp_id}_holdout_2025", formation, holdout))
    else:
        if not args.skip_dev:
            jobs.append((f"{exp_id}_dev_formation", formation, formation))
        if not args.skip_validation:
            jobs.append((f"{exp_id}_val_2024", formation, validation))
        if args.allow_holdout:
            jobs.append((f"{exp_id}_holdout_2025", formation, holdout))

    for experiment_id, form_period, eval_period in jobs:
        print(f"Running {experiment_id} eval={eval_period.name} ...")
        payload = run_period_study(
            full_panel=panel,
            formation=form_period,
            eval_period=eval_period,
            config=experiment,
            primary_symbol=primary_symbol,
            allow_holdout=args.allow_holdout,
        )
        artifact = {
            "experiment_id": experiment_id,
            "dataset_id": dataset_id,
            "dataset_canonical_sha256": (manifest.get("sha256") or {}).get("dataset_canonical"),
            "config_path": rel_config,
            "config_status": status,
            "branch": args.branch,
            "n_symbols": len(symbols),
            "symbols": symbols,
            "result": payload,
        }
        out_path = results_dir / f"{experiment_id}.json"
        digest = write_json_artifact(out_path, artifact)
        key_metrics = payload.get("key_metrics") or {}
        _append_ledger(
            ledger_path,
            {
                "experiment_id": experiment_id,
                "repo": "options-volatility-risk-lab",
                "branch": args.branch,
                "dataset_id": dataset_id,
                "config_path": rel_config,
                "status": status,
                "period_name": eval_period.name,
                "period_start": eval_period.start,
                "period_end": eval_period.end_inclusive,
                "horizons": "",
                "seed": str(experiment.get("seed", "")),
                "primary_symbol": primary_symbol,
                "artifact_path": str(out_path.relative_to(root)),
                "artifact_sha256": digest,
                "key_metrics_json": json.dumps(key_metrics, sort_keys=True),
                "notes": str(payload.get("notes", "")),
                "created_utc": _utc_now(),
            },
        )
        print(
            f"  wrote {out_path} sha256={digest[:16]}... "
            f"eval_vol={key_metrics.get('eval_realized_vol_ann')} "
            f"hs_var={key_metrics.get('option_hs_var')} "
            f"kupiec_p={key_metrics.get('equity_var_kupiec_pvalue')}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
