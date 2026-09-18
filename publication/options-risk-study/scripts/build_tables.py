#!/usr/bin/env python3
"""D10-C publication pack — deterministic table builder.

Reads ONLY already-committed, already-frozen result artifacts under
results/historical_risk/ (current AND superseded) and the dataset/config
files under data/manifests/ and configs/experiments/. Performs NO network
calls, NO re-execution of any experiment script, and NO alteration of any
input file. Every number this script emits is either:
  (a) read verbatim from a JSON field in a committed artifact, or
  (b) an arithmetic mean/ratio computed directly from those verbatim fields,
      using the same "mean across roll snapshots" definition already used
      in research/historical-volatility-and-tail-risk.md.

Outputs (all under publication/options-risk-study/):
  tables/hedging_experiment_summary.csv
  tables/var_es_corrected_vs_prefix.csv
  tables/kupiec_christoffersen.csv
  tables/case_study_dev_first_roll.json
  tables/dataset_and_artifact_hashes.json
  figures/var_es_before_after_2025_95.png   (only if matplotlib is importable)

Run from the repository root:
  python publication/options-risk-study/scripts/build_tables.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
RESULTS_DIR = REPO_ROOT / "results" / "historical_risk"
PUB_DIR = REPO_ROOT / "publication" / "options-risk-study"
TABLES_DIR = PUB_DIR / "tables"
FIGURES_DIR = PUB_DIR / "figures"

CURRENT_ARTIFACTS = {
    "dev_formation": RESULTS_DIR / "options_hist_risk_v2_dev_formation.json",
    "val_2024": RESULTS_DIR / "options_hist_risk_v2_val_2024.json",
    "historical_evaluation_2025": RESULTS_DIR
    / "options_hist_risk_v2_historical_evaluation_2025.json",
}

SUPERSEDED_VOL_UNITS = {
    "dev_formation": RESULTS_DIR
    / "superseded_volatility_units_fix"
    / "options_hist_risk_v2_dev_formation.json",
    "val_2024": RESULTS_DIR
    / "superseded_volatility_units_fix"
    / "options_hist_risk_v2_val_2024.json",
    "historical_evaluation_2025": RESULTS_DIR
    / "superseded_volatility_units_fix"
    / "options_hist_risk_v2_historical_evaluation_2025.json",
}

SUPERSEDED_BACKTEST = {
    "dev_formation": RESULTS_DIR
    / "superseded_next_session_backtest_fix"
    / "options_hist_risk_v2_dev_formation.json",
    "val_2024": RESULTS_DIR
    / "superseded_next_session_backtest_fix"
    / "options_hist_risk_v2_val_2024.json",
    "historical_evaluation_2025": RESULTS_DIR
    / "superseded_next_session_backtest_fix"
    / "options_hist_risk_v2_historical_evaluation_2025.json",
}

PERIOD_DISPLAY = {
    "dev_formation": "DEV",
    "val_2024": "VAL 2024",
    "historical_evaluation_2025": "2025 HISTORICAL EVALUATION",
}

METHOD_KEYS = ["historical_simulation_primary", "delta_normal", "monte_carlo"]
METHOD_DISPLAY = {
    "historical_simulation_primary": "Historical Simulation (252d)",
    "delta_normal": "Delta-Normal",
    "monte_carlo": "Monte Carlo (50k)",
}
CONF_KEYS = ["primary", "secondary"]
CONF_DISPLAY = {"primary": "95%", "secondary": "99%"}


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def mean(values: list[float]) -> float:
    return sum(values) / len(values)


def var_es_means(artifact: dict[str, Any]) -> dict[tuple[str, str, str], float]:
    """Returns {(confidence_key, method_key, 'var'|'es'): mean_value} across
    all roll snapshots in this one artifact's nonlinear_portfolio_study."""
    snaps = artifact["nonlinear_portfolio_study"]["snapshots"]
    out: dict[tuple[str, str, str], float] = {}
    for conf in CONF_KEYS:
        for method in METHOD_KEYS:
            for stat in ("var", "es"):
                vals = [s["var_es"][conf][method][stat] for s in snaps]
                out[(conf, method, stat)] = mean(vals)
    return out


def build_var_es_table() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for period_key in ("dev_formation", "val_2024", "historical_evaluation_2025"):
        current = load_json(CURRENT_ARTIFACTS[period_key])
        prefix = load_json(SUPERSEDED_VOL_UNITS[period_key])
        cur_means = var_es_means(current)
        pre_means = var_es_means(prefix)
        for conf in CONF_KEYS:
            for method in METHOD_KEYS:
                cur_var = cur_means[(conf, method, "var")]
                cur_es = cur_means[(conf, method, "es")]
                pre_var = pre_means[(conf, method, "var")]
                pre_es = pre_means[(conf, method, "es")]
                rows.append(
                    {
                        "period": PERIOD_DISPLAY[period_key],
                        "period_key": period_key,
                        "confidence": CONF_DISPLAY[conf],
                        "confidence_key": conf,
                        "method": METHOD_DISPLAY[method],
                        "method_key": method,
                        "mean_var_corrected": round(cur_var, 1),
                        "mean_es_corrected": round(cur_es, 1),
                        "mean_var_prefix_superseded": round(pre_var, 1),
                        "mean_es_prefix_superseded": round(pre_es, 1),
                        "var_ratio_prefix_over_corrected": round(pre_var / cur_var, 3)
                        if cur_var
                        else None,
                        "es_ratio_prefix_over_corrected": round(pre_es / cur_es, 3)
                        if cur_es
                        else None,
                        "source_current_artifact": str(
                            CURRENT_ARTIFACTS[period_key].relative_to(REPO_ROOT)
                        ),
                        "source_current_sha256": sha256_of(CURRENT_ARTIFACTS[period_key]),
                        "source_prefix_artifact": str(
                            SUPERSEDED_VOL_UNITS[period_key].relative_to(REPO_ROOT)
                        ),
                        "source_prefix_sha256": sha256_of(SUPERSEDED_VOL_UNITS[period_key]),
                    }
                )
    return rows


def build_hedging_table() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for period_key in ("dev_formation", "val_2024", "historical_evaluation_2025"):
        artifact_path = CURRENT_ARTIFACTS[period_key]
        artifact = load_json(artifact_path)
        summary = artifact["hedging_experiment"]["summary_by_frequency_and_cost_scenario"]
        for freq_scenario, stats in summary.items():
            freq, scenario = freq_scenario.split("_", 1)
            rows.append(
                {
                    "period": PERIOD_DISPLAY[period_key],
                    "period_key": period_key,
                    "rebalance_frequency": freq,
                    "cost_scenario": scenario,
                    "n_episodes": stats["n_episodes"],
                    "mean_absolute_replication_error": round(
                        stats["mean_absolute_replication_error"], 3
                    ),
                    "mean_transaction_cost": round(stats["mean_transaction_cost"], 3),
                    "mean_n_rebalances": round(stats["mean_n_rebalances"], 1),
                    "mean_realized_minus_assumed_vol": round(
                        stats["mean_realized_minus_assumed_vol"], 4
                    ),
                    "mean_max_cash_requirement": round(stats["mean_max_cash_requirement"], 2),
                    "source_artifact": str(artifact_path.relative_to(REPO_ROOT)),
                    "source_sha256": sha256_of(artifact_path),
                }
            )
    return rows


def build_kupiec_christoffersen_table() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for period_key in ("dev_formation", "val_2024", "historical_evaluation_2025"):
        current_path = CURRENT_ARTIFACTS[period_key]
        prefix_path = SUPERSEDED_BACKTEST[period_key]
        current = load_json(current_path)
        prefix = load_json(prefix_path)
        cur_bt = current["nonlinear_portfolio_study"]["kupiec_christoffersen_backtest"]
        pre_bt = prefix["nonlinear_portfolio_study"]["kupiec_christoffersen_backtest"]
        rows.append(
            {
                "period": PERIOD_DISPLAY[period_key],
                "period_key": period_key,
                "n_forecasts": cur_bt["n_forecasts"],
                "n_breaches_before": pre_bt["kupiec"]["n_breaches"],
                "n_breaches_after": cur_bt["kupiec"]["n_breaches"],
                "kupiec_p_before": pre_bt["kupiec"]["p_value"],
                "kupiec_p_after": cur_bt["kupiec"]["p_value"],
                "kupiec_conclusion_after": cur_bt["kupiec"]["conclusion"],
                "christoffersen_p_before": pre_bt["christoffersen"]["p_value"],
                "christoffersen_p_after": cur_bt["christoffersen"]["p_value"],
                "source_current_artifact": str(current_path.relative_to(REPO_ROOT)),
                "source_current_sha256": sha256_of(current_path),
                "source_prefix_artifact": str(prefix_path.relative_to(REPO_ROOT)),
                "source_prefix_sha256": sha256_of(prefix_path),
            }
        )
    return rows


def build_case_study() -> dict[str, Any]:
    current_path = CURRENT_ARTIFACTS["dev_formation"]
    prefix_path = SUPERSEDED_VOL_UNITS["dev_formation"]
    current = load_json(current_path)
    prefix = load_json(prefix_path)
    cur_snap = current["nonlinear_portfolio_study"]["snapshots"][0]
    pre_snap = prefix["nonlinear_portfolio_study"]["snapshots"][0]
    assert cur_snap["roll_date"] == "2016-02-01", cur_snap["roll_date"]
    assert pre_snap["roll_date"] == "2016-02-01", pre_snap["roll_date"]
    import math

    dn_ratio = (
        pre_snap["var_es"]["primary"]["delta_normal"]["var"]
        / cur_snap["var_es"]["primary"]["delta_normal"]["var"]
    )
    mc_ratio = (
        pre_snap["var_es"]["primary"]["monte_carlo"]["var"]
        / cur_snap["var_es"]["primary"]["monte_carlo"]["var"]
    )
    return {
        "roll_date": cur_snap["roll_date"],
        "S0": cur_snap["S0"],
        "realized_vol_20d_annualized": cur_snap["realized_vol_20d"],
        "daily_factor_vol_20d": cur_snap["daily_factor_vol_20d"],
        "sqrt_252": math.sqrt(252.0),
        "check_daily_equals_annualized_over_sqrt252": cur_snap["realized_vol_20d"]
        / math.sqrt(252.0),
        "portfolio_dollar_delta": cur_snap["var_es"]["primary"]["delta_normal"][
            "portfolio_dollar_delta"
        ],
        "confidence_95_corrected": {
            "delta_normal_var": cur_snap["var_es"]["primary"]["delta_normal"]["var"],
            "delta_normal_es": cur_snap["var_es"]["primary"]["delta_normal"]["es"],
            "monte_carlo_var": cur_snap["var_es"]["primary"]["monte_carlo"]["var"],
            "monte_carlo_es": cur_snap["var_es"]["primary"]["monte_carlo"]["es"],
            "historical_simulation_var": cur_snap["var_es"]["primary"][
                "historical_simulation_primary"
            ]["var"],
            "historical_simulation_es": cur_snap["var_es"]["primary"][
                "historical_simulation_primary"
            ]["es"],
        },
        "confidence_95_prefix_superseded": {
            "delta_normal_var": pre_snap["var_es"]["primary"]["delta_normal"]["var"],
            "delta_normal_es": pre_snap["var_es"]["primary"]["delta_normal"]["es"],
            "monte_carlo_var": pre_snap["var_es"]["primary"]["monte_carlo"]["var"],
            "monte_carlo_es": pre_snap["var_es"]["primary"]["monte_carlo"]["es"],
            "historical_simulation_var": pre_snap["var_es"]["primary"][
                "historical_simulation_primary"
            ]["var"],
            "historical_simulation_es": pre_snap["var_es"]["primary"][
                "historical_simulation_primary"
            ]["es"],
        },
        "delta_normal_prefix_over_corrected_var_ratio": dn_ratio,
        "monte_carlo_prefix_over_corrected_var_ratio": mc_ratio,
        "historical_simulation_unchanged": (
            cur_snap["var_es"]["primary"]["historical_simulation_primary"]
            == pre_snap["var_es"]["primary"]["historical_simulation_primary"]
        ),
        "source_current_artifact": str(current_path.relative_to(REPO_ROOT)),
        "source_current_sha256": sha256_of(current_path),
        "source_prefix_artifact": str(prefix_path.relative_to(REPO_ROOT)),
        "source_prefix_sha256": sha256_of(prefix_path),
    }


def build_hash_manifest() -> dict[str, Any]:
    manifests_dir = REPO_ROOT / "data" / "manifests"
    config_path = REPO_ROOT / "configs" / "experiments" / "options_historical_risk_study_v2.yaml"

    def manifest_canonical_sha(dataset_id: str) -> str:
        m = load_json(manifests_dir / f"{dataset_id}.json")
        return m["sha256"]["dataset_canonical"]

    out = {
        "config": {
            "path": str(config_path.relative_to(REPO_ROOT)),
            "sha256_computed": sha256_of(config_path),
        },
        "datasets": {
            "yf_spy_daily_2015_2025_v1": {
                "manifest_path": str(
                    (manifests_dir / "yf_spy_daily_2015_2025_v1.json").relative_to(REPO_ROOT)
                ),
                "dataset_canonical_sha256": manifest_canonical_sha("yf_spy_daily_2015_2025_v1"),
            },
            "fred_dgs3mo_daily_2015_2025_v1": {
                "manifest_path": str(
                    (manifests_dir / "fred_dgs3mo_daily_2015_2025_v1.json").relative_to(REPO_ROOT)
                ),
                "dataset_canonical_sha256": manifest_canonical_sha(
                    "fred_dgs3mo_daily_2015_2025_v1"
                ),
            },
            "fred_vixcls_daily_2015_2025_v1": {
                "manifest_path": str(
                    (manifests_dir / "fred_vixcls_daily_2015_2025_v1.json").relative_to(REPO_ROOT)
                ),
                "dataset_canonical_sha256": manifest_canonical_sha(
                    "fred_vixcls_daily_2015_2025_v1"
                ),
            },
        },
        "current_artifacts": {
            k: {"path": str(v.relative_to(REPO_ROOT)), "sha256_computed": sha256_of(v)}
            for k, v in CURRENT_ARTIFACTS.items()
        },
        "superseded_volatility_units_fix": {
            k: {"path": str(v.relative_to(REPO_ROOT)), "sha256_computed": sha256_of(v)}
            for k, v in SUPERSEDED_VOL_UNITS.items()
        },
        "superseded_next_session_backtest_fix": {
            k: {"path": str(v.relative_to(REPO_ROOT)), "sha256_computed": sha256_of(v)}
            for k, v in SUPERSEDED_BACKTEST.items()
        },
    }
    return out


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def maybe_build_figure(var_es_rows: list[dict[str, Any]]) -> str:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        note = (
            "matplotlib not importable in this environment -- figure skipped (see D10-STATUS.md)."
        )
        print(note)
        return note

    target = [
        r
        for r in var_es_rows
        if r["period_key"] == "historical_evaluation_2025" and r["confidence_key"] == "primary"
    ]
    methods = [r["method"] for r in target]
    corrected = [r["mean_var_corrected"] for r in target]
    prefix = [r["mean_var_prefix_superseded"] for r in target]

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))

    axes[0].bar(methods, prefix, color="#b3261e")
    axes[0].set_title("PRE-FIX (superseded)\nmean 95% VaR, 2025 HISTORICAL EVALUATION")
    axes[0].set_ylabel("Mean 1-day VaR ($, 1-lot equivalent)")
    axes[0].tick_params(axis="x", rotation=20)

    axes[1].bar(methods, corrected, color="#1e6b3a")
    axes[1].set_title(
        "CORRECTED (current, authoritative)\nmean 95% VaR, 2025 HISTORICAL EVALUATION"
    )
    axes[1].set_ylabel("Mean 1-day VaR ($, 1-lot equivalent)")
    axes[1].tick_params(axis="x", rotation=20)

    fig.suptitle(
        "Volatility-units fix: mean 95% VaR before vs after correction\n"
        "(y-axis scales differ; PRE-FIX values are superseded, shown for comparison only)"
    )
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    out_path = FIGURES_DIR / "var_es_before_after_2025_95.png"
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return f"figure written to {out_path.relative_to(REPO_ROOT)}"


def main() -> int:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    var_es_rows = build_var_es_table()
    write_csv(var_es_rows, TABLES_DIR / "var_es_corrected_vs_prefix.csv")

    hedging_rows = build_hedging_table()
    write_csv(hedging_rows, TABLES_DIR / "hedging_experiment_summary.csv")

    kc_rows = build_kupiec_christoffersen_table()
    write_csv(kc_rows, TABLES_DIR / "kupiec_christoffersen.csv")

    case_study = build_case_study()
    (TABLES_DIR / "case_study_dev_first_roll.json").write_text(
        json.dumps(case_study, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    hashes = build_hash_manifest()
    (TABLES_DIR / "dataset_and_artifact_hashes.json").write_text(
        json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    fig_note = maybe_build_figure(var_es_rows)

    print("Wrote:")
    print(f"  {TABLES_DIR / 'var_es_corrected_vs_prefix.csv'}")
    print(f"  {TABLES_DIR / 'hedging_experiment_summary.csv'}")
    print(f"  {TABLES_DIR / 'kupiec_christoffersen.csv'}")
    print(f"  {TABLES_DIR / 'case_study_dev_first_roll.json'}")
    print(f"  {TABLES_DIR / 'dataset_and_artifact_hashes.json'}")
    print(f"  figure: {fig_note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
