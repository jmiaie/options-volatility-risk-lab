#!/usr/bin/env python3
"""Run Directive #9 D9-C AUTHORITATIVE (v2) historical options/volatility/
portfolio-risk validation on frozen local data only.

Runs the hedging experiment ("Historical underlying-path hypothetical option
hedging experiment") and the standardized nonlinear portfolio VaR/ES study
("Hypothetical nonlinear portfolio evaluated on historical risk-factor
paths") for formation/validation, plus the 2025 HISTORICAL EVALUATION period
(not "untouched holdout" -- see the v2 config's own note).

Examples:
  python scripts/run_historical_risk_study_v2.py

  # Full-cost Monte Carlo (50,000 sims) is compute-heavy; override for a
  # faster local smoke test:
  python scripts/run_historical_risk_study_v2.py --mc-n-sims 2000
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

from options_risk.historical_risk_study_v2 import (
    PeriodSpec,
    load_fred_series_decimal,
    load_spy_close,
    run_hedging_experiment,
    run_nonlinear_portfolio_study,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_json(payload: dict[str, Any]) -> tuple[str, str]:
    import hashlib

    text = json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"
    return text, hashlib.sha256(text.encode("utf-8")).hexdigest()


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


def _load_manifest(root: Path, dataset_id: str) -> dict[str, Any]:
    manifest_path = root / "data" / "manifests" / f"{dataset_id}.json"
    if not manifest_path.exists():
        print(f"ERROR: missing manifest {manifest_path}", file=sys.stderr)
        raise SystemExit(2)
    manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "DATA FROZEN":
        print(
            f"ERROR: {dataset_id} not DATA FROZEN (status={manifest.get('status')})",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/experiments/options_historical_risk_study_v2.yaml"),
    )
    parser.add_argument("--raw-dir", type=Path, default=None)
    parser.add_argument("--results-dir", type=Path, default=Path("results/historical_risk"))
    parser.add_argument("--ledger", type=Path, default=Path("research/experiment-ledger.csv"))
    parser.add_argument("--branch", default="research/historical-risk-validation")
    parser.add_argument(
        "--allow-2025",
        action="store_true",
        help="Include the 2025 HISTORICAL EVALUATION period (requires status frozen-for-holdout)",
    )
    parser.add_argument("--skip-dev", action="store_true")
    parser.add_argument("--skip-validation", action="store_true")
    parser.add_argument(
        "--mc-n-sims",
        type=int,
        default=None,
        help="Override Monte Carlo n_sims (default: spec 50000)",
    )
    args = parser.parse_args(argv)

    root = _repo_root()
    config_path = args.config if args.config.is_absolute() else root / args.config
    experiment = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    status = str(experiment.get("status", ""))
    dataset_ids = experiment["dataset_ids"]

    if args.allow_2025 and status != "frozen-for-holdout":
        print(
            f"ERROR: refuse 2025 evaluation; experiment status is {status!r}, "
            "need frozen-for-holdout",
            file=sys.stderr,
        )
        return 3

    spy_manifest = _load_manifest(root, dataset_ids["underlying"])
    rate_manifest = _load_manifest(root, dataset_ids["short_rate"])
    vix_manifest = _load_manifest(root, dataset_ids["vol_context"])

    raw_root = args.raw_dir or (root / "data" / "raw")
    spy_path = raw_root / dataset_ids["underlying"] / "SPY.csv"
    rate_path = raw_root / dataset_ids["short_rate"] / "DGS3MO.csv"
    vix_path = raw_root / dataset_ids["vol_context"] / "VIXCLS.csv"
    for p in (spy_path, rate_path, vix_path):
        if not p.exists():
            print(f"ERROR: missing frozen raw file {p}", file=sys.stderr)
            return 2

    spy_close = load_spy_close(str(spy_path))
    rate_series = load_fred_series_decimal(str(rate_path), "DGS3MO")
    vix_series = load_fred_series_decimal(str(vix_path), "VIXCLS")

    periods = experiment["periods"]
    formation = PeriodSpec(
        "formation_dev",
        periods["formation_dev"]["start"],
        periods["formation_dev"]["end_inclusive"],
    )
    validation = PeriodSpec(
        "validation", periods["validation"]["start"], periods["validation"]["end_inclusive"]
    )
    historical_eval = PeriodSpec(
        "historical_evaluation",
        periods["historical_evaluation"]["start"],
        periods["historical_evaluation"]["end_inclusive"],
    )

    results_dir = args.results_dir if args.results_dir.is_absolute() else root / args.results_dir
    ledger_path = args.ledger if args.ledger.is_absolute() else root / args.ledger
    exp_id = str(experiment["experiment_id"])
    rel_config = str(config_path.relative_to(root))

    kwargs: dict[str, Any] = {}
    if args.mc_n_sims is not None:
        kwargs["mc_n_sims"] = args.mc_n_sims

    jobs: list[tuple[str, PeriodSpec, str]] = []
    if not args.skip_dev:
        jobs.append(
            (f"{exp_id}_dev_formation", formation, "PRE-SPECIFIED DEVELOPMENT CHARACTERIZATION")
        )
    if not args.skip_validation:
        jobs.append((f"{exp_id}_val_2024", validation, "PRE-SPECIFIED VALIDATION CHARACTERIZATION"))
    if args.allow_2025:
        jobs.append(
            (f"{exp_id}_historical_evaluation_2025", historical_eval, "HISTORICAL EVALUATION")
        )

    if not jobs:
        print("No periods selected.", file=sys.stderr)
        return 1

    for experiment_id, eval_period, period_label in jobs:
        print(f"Running {experiment_id} ({period_label}) on {eval_period.name}...")

        hedging = run_hedging_experiment(spy_close, rate_series, eval_period)
        nonlinear = run_nonlinear_portfolio_study(
            spy_close, rate_series, vix_series, eval_period, **kwargs
        )

        artifact = {
            "experiment_id": experiment_id,
            "period_label": period_label,
            "dataset_ids": dataset_ids,
            "dataset_canonical_sha256": {
                "underlying": (spy_manifest.get("sha256") or {}).get("dataset_canonical"),
                "short_rate": (rate_manifest.get("sha256") or {}).get("dataset_canonical"),
                "vol_context": (vix_manifest.get("sha256") or {}).get("dataset_canonical"),
            },
            "config_path": rel_config,
            "config_status": status,
            "branch": args.branch,
            "eval_period": {"start": eval_period.start, "end_inclusive": eval_period.end_inclusive},
            "hedging_experiment": hedging,
            "nonlinear_portfolio_study": nonlinear,
        }
        text, digest = _sha256_json(artifact)
        results_dir.mkdir(parents=True, exist_ok=True)
        out_path = results_dir / f"{experiment_id}.json"
        out_path.write_text(text, encoding="utf-8")

        key_metrics = {
            "n_hedge_episodes": hedging["n_episodes_initiated"],
            "hedge_daily_base_mean_abs_replication_error": hedging[
                "summary_by_frequency_and_cost_scenario"
            ]["daily_BASE"]["mean_absolute_replication_error"],
            "hedge_daily_base_mean_transaction_cost": hedging[
                "summary_by_frequency_and_cost_scenario"
            ]["daily_BASE"]["mean_transaction_cost"],
            "n_portfolio_roll_snapshots": nonlinear["n_roll_snapshots"],
            "kupiec_p_value": (nonlinear["kupiec_christoffersen_backtest"] or {})
            .get("kupiec", {})
            .get("p_value"),
            "christoffersen_p_value": (nonlinear["kupiec_christoffersen_backtest"] or {})
            .get("christoffersen", {})
            .get("p_value"),
        }
        _append_ledger(
            ledger_path,
            {
                "experiment_id": experiment_id,
                "repo": "options-volatility-risk-lab",
                "branch": args.branch,
                "dataset_id": "|".join(dataset_ids.values()),
                "config_path": rel_config,
                "status": status,
                "period_name": eval_period.name,
                "period_start": eval_period.start,
                "period_end": eval_period.end_inclusive,
                "horizons": "1",
                "seed": str(experiment.get("seed", "")),
                "primary_symbol": "SPY",
                "artifact_path": str(out_path.relative_to(root)),
                "artifact_sha256": digest,
                "key_metrics_json": json.dumps(key_metrics, sort_keys=True, default=str),
                "notes": f"{period_label}. {hedging['label']}. {nonlinear['label']}.",
                "created_utc": _utc_now(),
            },
        )
        print(
            f"  wrote {out_path} sha256={digest[:16]}... "
            f"episodes={key_metrics['n_hedge_episodes']} "
            f"rolls={key_metrics['n_portfolio_roll_snapshots']} "
            f"kupiec_p={key_metrics['kupiec_p_value']}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
