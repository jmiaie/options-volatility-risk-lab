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

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

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


def build_figure() -> str | None:
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

    rows = build_var_es_table()
    periods = ["dev_formation", "val_2024", "historical_evaluation_2025"]
    conf = "primary"  # 95% confidence, per the requested figure

    # rows_by[(period_key, method_key)] -> row dict, for the 95%-confidence rows only
    rows_by = {(r["period_key"], r["method_key"]): r for r in rows if r["confidence_key"] == conf}

    fig, ax = plt.subplots(figsize=(11, 6.5), facecolor=SURFACE)
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
    ax.set_ylim(50, 60000)
    ax.set_xticks(group_centers)
    ax.set_xticklabels([PERIOD_DISPLAY[p] for p in periods], fontsize=10.5, color=INK_PRIMARY)
    ax.set_ylabel(
        "Mean 95% 1-day VaR, $ per 1-lot-equivalent standardized book (log scale)",
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
        f"Mean {CONF_DISPLAY[conf]} 1-day VaR by method: corrected (authoritative) vs. "
        "pre-fix (superseded)\nHistorical Simulation is unaffected by the volatility-units "
        "fix and is byte-identical in both bars",
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
        "Source: results/historical_risk/options_hist_risk_v2_{dev_formation,val_2024,\n"
        "historical_evaluation_2025}.json (corrected) and results/historical_risk/\n"
        "superseded_volatility_units_fix/*.json (pre-fix). See RESULT-SOURCE-MAP.md. "
        "No experiment was rerun to produce this figure.",
        fontsize=6.6,
        color=INK_MUTED,
        linespacing=1.5,
    )

    fig.tight_layout(rect=(0, 0.075, 1, 1))

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = FIGURES_DIR / "var_es_corrected_vs_superseded_95_all_periods.png"
    fig.savefig(
        out_path,
        dpi=150,
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
