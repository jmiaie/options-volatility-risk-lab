#!/usr/bin/env python3
"""Reproducibility bundle -- deterministic figure builder.

Reads ONLY already-committed, already-frozen result artifacts under
results/historical_risk/ (current AND superseded), via the exact same
computation as build_tables.py (imported, not reimplemented, so the figure
and the CSV tables can never silently disagree). Performs NO network calls,
NO re-execution of any experiment script, and NO alteration of any input
file.

Output:
  figures/var_es_corrected_vs_superseded_95_all_periods.png

Run from the repository root:
  python publication/options-risk-study/scripts/build_figures.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_tables  # noqa: E402
from build_tables import (  # noqa: E402
    CONF_DISPLAY,
    FIGURES_DIR,
    METHOD_DISPLAY,
    METHOD_KEYS,
    PERIOD_DISPLAY,
    build_var_es_table,
)

# Fixed categorical palette (dataviz skill's validated default, first 3 slots
# -- these three validate all-pairs CVD/normal-vision separation in both
# light and dark surfaces): blue = Historical Simulation, orange =
# Delta-Normal, aqua = Monte Carlo. Hue is assigned to METHOD identity and
# held fixed; corrected vs. pre-fix status is encoded by fill style
# (solid vs. hatched + reduced alpha), not by a second hue, per the
# "color follows the entity, never a second dimension" rule.
METHOD_COLOR = {
    "historical_simulation_primary": "#2a78d6",  # categorical slot 1, blue
    "delta_normal": "#eb6834",  # categorical slot 2, orange
    "monte_carlo": "#1baf7a",  # categorical slot 3, aqua
}
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
SURFACE = "#fcfcfb"
FIGURE_NAME = "var_es_corrected_vs_superseded_95_all_periods.png"
CONTRACT_NAME = "var_es_corrected_vs_superseded_95_all_periods.render-contract.json"
FIGSIZE_INCHES = (11.0, 6.5)
DPI = 150
Y_LIMITS = (50, 60000)
PERIODS = ["dev_formation", "val_2024", "historical_evaluation_2025"]
CONFIDENCE_KEY = "primary"
TITLE = (
    f"Mean {CONF_DISPLAY[CONFIDENCE_KEY]} 1-day VaR by method: corrected (authoritative) "
    "vs. pre-fix (superseded)\nHistorical Simulation is unaffected by the volatility-units "
    "fix and is byte-identical in both bars"
)
Y_LABEL = "Mean 95% 1-day VaR, $ per 1-lot-equivalent standardized book (log scale)"
SOURCE_NOTE = (
    "Source: results/historical_risk/options_hist_risk_v2_{dev_formation,val_2024,\n"
    "historical_evaluation_2025}.json (corrected) and results/historical_risk/\n"
    "superseded_volatility_units_fix/*.json (pre-fix). See RESULT-SOURCE-MAP.md. "
    "No experiment was rerun to produce this figure."
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_render_contract() -> dict[str, object]:
    """Return the portable, deterministic semantic contract for the figure.

    PNG raster bytes are not portable across FreeType/fontconfig/libpng builds.
    This contract is: it fixes every plotted value, label, categorical mapping,
    axis setting, source hash, canvas size, and material visual encoding. The
    publication verifier compares this object byte-for-byte after canonical JSON
    serialization and validates the committed PNG separately by its fixed hash.
    """

    rows = build_var_es_table()
    plotted_rows = [
        {
            "period_key": period_key,
            "period_label": PERIOD_DISPLAY[period_key],
            "method_key": method_key,
            "method_label": METHOD_DISPLAY[method_key],
            "mean_var_corrected": next(
                row["mean_var_corrected"]
                for row in rows
                if row["confidence_key"] == CONFIDENCE_KEY
                and row["period_key"] == period_key
                and row["method_key"] == method_key
            ),
            "mean_var_prefix_superseded": next(
                row["mean_var_prefix_superseded"]
                for row in rows
                if row["confidence_key"] == CONFIDENCE_KEY
                and row["period_key"] == period_key
                and row["method_key"] == method_key
            ),
        }
        for period_key in PERIODS
        for method_key in METHOD_KEYS
    ]

    source_paths = sorted(
        [
            *[path for path in build_tables.CURRENT_ARTIFACTS.values()],
            *[path for path in build_tables.SUPERSEDED_VOL_UNITS.values()],
        ]
    )
    sources = [
        {
            "path": str(path.relative_to(build_tables.REPO_ROOT)),
            "sha256": _sha256(path),
        }
        for path in source_paths
    ]

    return {
        "schema_version": 1,
        "research_classification": "HISTORICAL EVALUATION",
        "figure": {
            "name": FIGURE_NAME,
            "figsize_inches": list(FIGSIZE_INCHES),
            "dpi": DPI,
            "expected_pixel_dimensions": [1650, 975],
            "facecolor": SURFACE,
            "y_scale": "log",
            "y_limits": list(Y_LIMITS),
            "confidence_key": CONFIDENCE_KEY,
            "period_order": PERIODS,
            "method_order": list(METHOD_KEYS),
            "method_colors": METHOD_COLOR,
            "corrected_style": {"alpha": 1.0, "fill": "solid"},
            "superseded_style": {"alpha": 0.35, "hatch": "///"},
            "title": TITLE,
            "y_label": Y_LABEL,
            "source_note": SOURCE_NOTE,
        },
        "plotted_rows": plotted_rows,
        "source_artifacts": sources,
    }


def write_render_contract(contract: dict[str, object], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_figure(
    output_path: Path | None = None,
    contract_path: Path | None = None,
) -> str | None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        note = (
            "matplotlib not importable in this environment -- figure skipped (install matplotlib)."
        )
        print(note)
        return None

    contract = build_render_contract()
    if output_path is None and contract_path is None:
        contract_path = FIGURES_DIR / CONTRACT_NAME
    if contract_path is not None:
        write_render_contract(contract, contract_path)

    rows = build_var_es_table()
    periods = PERIODS
    conf = CONFIDENCE_KEY  # 95% confidence, per the requested figure

    # rows_by[(period_key, method_key)] -> row dict, for the 95%-confidence rows only
    rows_by = {(r["period_key"], r["method_key"]): r for r in rows if r["confidence_key"] == conf}

    fig, ax = plt.subplots(figsize=FIGSIZE_INCHES, facecolor=SURFACE)
    ax.set_facecolor(SURFACE)

    n_periods = len(periods)
    n_methods = len(METHOD_KEYS)
    group_width = 0.78
    bar_width = group_width / (n_methods * 2)
    group_centers = list(range(n_periods))

    for pi, period_key in enumerate(periods):
        for mi, method_key in enumerate(METHOD_KEYS):
            row = rows_by[(period_key, method_key)]
            color = METHOD_COLOR[method_key]
            # Two adjacent bars per method: pre-fix (superseded, left, hatched,
            # reduced alpha) and corrected (authoritative, right, solid).
            cluster_offset = (mi - (n_methods - 1) / 2) * (2 * bar_width) * 1.12
            x_pre = group_centers[pi] + cluster_offset - bar_width * 0.52
            x_cur = group_centers[pi] + cluster_offset + bar_width * 0.52

            ax.bar(
                x_pre,
                row["mean_var_prefix_superseded"],
                width=bar_width,
                color=color,
                alpha=0.35,
                hatch="///",
                edgecolor=color,
                linewidth=0.8,
                zorder=3,
            )
            ax.bar(
                x_cur,
                row["mean_var_corrected"],
                width=bar_width,
                color=color,
                alpha=1.0,
                edgecolor=INK_PRIMARY,
                linewidth=0.6,
                zorder=3,
            )

            # Selective direct labels: corrected value above every corrected
            # bar (18 bars total is small enough that every value is useful
            # here -- this is a reference figure meant to be read closely,
            # not a dashboard tile), pre-fix value above its own bar in a
            # muted, smaller weight.
            ax.text(
                x_cur,
                row["mean_var_corrected"] * 1.15,
                f"{row['mean_var_corrected']:,.0f}",
                ha="center",
                va="bottom",
                fontsize=7.3,
                color=INK_PRIMARY,
                zorder=4,
            )
            ax.text(
                x_pre,
                row["mean_var_prefix_superseded"] * 1.15,
                f"{row['mean_var_prefix_superseded']:,.0f}",
                ha="center",
                va="bottom",
                fontsize=6.6,
                color=INK_SECONDARY,
                zorder=4,
            )

    ax.set_yscale("log")
    ax.set_ylim(*Y_LIMITS)
    ax.set_xticks(group_centers)
    ax.set_xticklabels([PERIOD_DISPLAY[p] for p in periods], fontsize=10.5, color=INK_PRIMARY)
    ax.set_ylabel(
        Y_LABEL,
        fontsize=9.5,
        color=INK_SECONDARY,
    )
    ax.tick_params(axis="y", colors=INK_MUTED, labelsize=8.5)
    ax.grid(axis="y", which="major", color=GRIDLINE, linewidth=0.8, zorder=0)
    ax.grid(axis="y", which="minor", color=GRIDLINE, linewidth=0.4, alpha=0.5, zorder=0)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(INK_MUTED)

    ax.set_title(
        TITLE,
        fontsize=11.5,
        color=INK_PRIMARY,
        pad=14,
        loc="left",
    )

    # Method (hue) legend -- fixed categorical order, matching METHOD_KEYS.
    method_handles = [
        plt.Rectangle(
            (0, 0), 1, 1, facecolor=METHOD_COLOR[mk], edgecolor=INK_PRIMARY, linewidth=0.6
        )
        for mk in METHOD_KEYS
    ]
    method_labels = [METHOD_DISPLAY[mk] for mk in METHOD_KEYS]
    legend1 = ax.legend(
        method_handles,
        method_labels,
        title="Method",
        loc="upper left",
        frameon=False,
        fontsize=8.5,
        title_fontsize=9,
    )
    ax.add_artist(legend1)

    # Status (fill-style) legend -- solid vs. hatched, not a second hue.
    status_handles = [
        plt.Rectangle(
            (0, 0), 1, 1, facecolor=INK_MUTED, alpha=1.0, edgecolor=INK_PRIMARY, linewidth=0.6
        ),
        plt.Rectangle(
            (0, 0),
            1,
            1,
            facecolor=INK_MUTED,
            alpha=0.35,
            hatch="///",
            edgecolor=INK_MUTED,
            linewidth=0.8,
        ),
    ]
    status_labels = ["Corrected (authoritative)", "Pre-fix (superseded) -- comparison only"]
    ax.legend(
        status_handles,
        status_labels,
        loc="upper right",
        frameon=False,
        fontsize=8.5,
    )

    fig.text(
        0.01,
        0.035,
        SOURCE_NOTE,
        fontsize=6.6,
        color=INK_MUTED,
        linespacing=1.5,
    )

    fig.tight_layout(rect=(0, 0.075, 1, 1))

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = output_path or FIGURES_DIR / FIGURE_NAME
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        out_path,
        dpi=DPI,
        facecolor=SURFACE,
        metadata={"Software": "", "Creation Time": "", "Author": "", "Description": ""},
    )
    plt.close(fig)
    return str(out_path)


def main() -> int:
    result = build_figure()
    if result is None:
        return 0
    print(f"Wrote: {result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
