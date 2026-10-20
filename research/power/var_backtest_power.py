"""Power / null-calibration of the repo's own VaR backtests (Study B).

Calibrates the PRODUCTION test functions in ``options_risk.risk.backtesting``
(``kupiec_pof_test``, ``christoffersen_independence_test``,
``conditional_coverage_test``) at the published study's VaR level. Every
accept/reject decision in this module is made by one of those functions; this
module only generates breach sequences, enumerates breach counts, and tallies
the decisions. The frozen design is ``research/power/PROTOCOL.md``.

Reproduce the full run (from the repository root)::

    python -m research.power.var_backtest_power --workers 4

Outputs ``results/power/var_backtest_power.json`` and
``results/power/var_backtest_power.png``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import scipy
from scipy.stats import binom

from options_risk.risk.backtesting import (
    christoffersen_independence_test,
    conditional_coverage_test,
    kupiec_pof_test,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

# --------------------------------------------------------------------------
# Frozen parameters (see PROTOCOL.md section 3). Changing any of these after
# the design-freeze commit requires a dated amendment in PROTOCOL.md.
# --------------------------------------------------------------------------
PROTOCOL_VERSION = "1.0"
# The published backtest calls kupiec_pof_test / christoffersen_independence_test
# with CONFIDENCE_LEVELS["primary"] = 0.95 (historical_risk_study_v2.py).
CONFIDENCE_PRIMARY = 0.95
# Config's secondary VaR level; computed but never backtested in the study.
# Supplementary, Kupiec-only (exact).
CONFIDENCE_SECONDARY = 0.99
# The study uses the production default significance_level=0.05.
SIGNIFICANCE = 0.05
N_GRID: tuple[int, ...] = (12, 95, 250, 1000, 2500)
MULTIPLES: tuple[float, ...] = (1.0, 1.5, 2.0, 3.0)
PERSISTENCE: tuple[float, ...] = (0.0, 0.2, 0.5)
N_REPS_FULL = 20_000
MASTER_SEED = 20261020
POWER_TARGET = 0.80
N_SEARCH_MAX = 10_000
N_SEARCH_MULTIPLES: tuple[float, ...] = (1.5, 2.0, 3.0)
MULTIPLE_STEP_HUNDREDTHS = 1  # fine multiple grid step = 0.01
SIZE_BAND = (0.04, 0.06)
BORDERLINE_SE = 2.0
SIM_VS_EXACT_TOL_SE = 4.0
FIGURE_N_MAX = 2500

PUBLISHED_ARTIFACTS: dict[str, str] = {
    "DEV": "results/historical_risk/options_hist_risk_v2_dev_formation.json",
    "VAL 2024": "results/historical_risk/options_hist_risk_v2_val_2024.json",
    "2025 HISTORICAL EVALUATION": (
        "results/historical_risk/options_hist_risk_v2_historical_evaluation_2025.json"
    ),
}
# Daily-cadence backtests of the same SPY history (v1, exploratory); used ONLY
# for their forecast counts, i.e. what n a daily backtest yields per period.
DAILY_COUNT_ARTIFACTS: dict[str, str] = {
    "DEV (daily)": "results/historical_risk/options_hist_risk_v1_dev_formation.json",
    "VAL 2024 (daily)": "results/historical_risk/options_hist_risk_v1_val_2024.json",
    "2025 (daily)": "results/historical_risk/options_hist_risk_v1_holdout_2025.json",
}


@dataclass(frozen=True)
class RunConfig:
    n_grid: tuple[int, ...] = N_GRID
    multiples: tuple[float, ...] = MULTIPLES
    persistence: tuple[float, ...] = PERSISTENCE
    n_reps: int = N_REPS_FULL
    n_search_max: int = N_SEARCH_MAX
    figure_n_max: int = FIGURE_N_MAX
    master_seed: int = MASTER_SEED
    workers: int = 1
    label: str = "full"


SMOKE_CONFIG = RunConfig(
    n_grid=(12, 95),
    n_reps=500,
    n_search_max=300,
    figure_n_max=300,
    label="smoke",
)


# --------------------------------------------------------------------------
# Kupiec: exact binomial enumeration, decisions by the production function
# --------------------------------------------------------------------------
def _breach_array(n: int, x: int) -> np.ndarray:
    arr = np.zeros(n, dtype=bool)
    arr[:x] = True
    return arr


def kupiec_rejects(n: int, x: int, confidence_level: float) -> bool:
    """Production Kupiec decision for x breaches in n forecasts (order is irrelevant)."""
    res = kupiec_pof_test(_breach_array(n, x), confidence_level, significance_level=SIGNIFICANCE)
    return bool(res.reject_null)


def kupiec_enumerate(n: int, confidence_level: float) -> dict[str, Any]:
    """Call the production Kupiec test for every possible breach count 0..n."""
    reject = np.zeros(n + 1, dtype=bool)
    p_values = np.zeros(n + 1)
    inconsistent: list[int] = []
    for x in range(n + 1):
        res = kupiec_pof_test(
            _breach_array(n, x), confidence_level, significance_level=SIGNIFICANCE
        )
        reject[x] = res.reject_null
        p_values[x] = res.p_value
        if bool(res.reject_null) != bool(res.p_value < SIGNIFICANCE) or not np.isfinite(
            res.p_value
        ):
            inconsistent.append(x)
    return {"reject": reject, "p_values": p_values, "inconsistent_x": inconsistent}


def kupiec_thresholds(n: int, confidence_level: float) -> tuple[int, int]:
    """(x_lo, x_hi): production test rejects iff x <= x_lo or x >= x_hi.

    x_lo = -1 means the lower tail is empty; x_hi = n + 1 means the upper tail
    is empty. Found by bisection on each side of floor(n * p0), which relies on
    the Kupiec LR being convex in x (monotone p-value on each side). That
    structural property is verified against full enumeration in the unit tests
    and at every grid n in the run itself.
    """
    p0 = 1.0 - confidence_level
    c = min(int(np.floor(n * p0)), n)

    def rej(x: int) -> bool:
        return kupiec_rejects(n, x, confidence_level)

    # Upper: smallest x in (c, n] that rejects.
    lo, hi = c + 1, n + 1  # answer in [lo, hi]; hi = n + 1 means none
    if lo <= n and rej(n):
        while lo < hi:
            mid = (lo + hi) // 2
            if mid <= n and rej(mid):
                hi = mid
            else:
                lo = mid + 1
        x_hi = lo
    else:
        x_hi = n + 1
    # Lower: largest x in [0, c] that rejects.
    if rej(0):
        a, b = 0, c  # rej(a) is True; find largest rejecting in [a, b]
        if rej(b):
            x_lo = b
        else:
            while b - a > 1:
                mid = (a + b) // 2
                if rej(mid):
                    a = mid
                else:
                    b = mid
            x_lo = a
    else:
        x_lo = -1
    return x_lo, x_hi


def power_from_thresholds(n: int, x_lo: int, x_hi: int, p: float | np.ndarray) -> Any:
    upper = binom.sf(x_hi - 1, n, p) if x_hi <= n else 0.0 * np.asarray(p)
    lower = binom.cdf(x_lo, n, p) if x_lo >= 0 else 0.0 * np.asarray(p)
    return upper + lower


def power_from_enumeration(n: int, reject: np.ndarray, p: float) -> float:
    xs = np.arange(n + 1)
    return float(binom.pmf(xs[reject], n, p).sum())


def fine_multiples(confidence_level: float) -> np.ndarray:
    p0 = 1.0 - confidence_level
    top = int(round(100.0 / p0))  # multiple at which breach rate = 1.0
    return np.arange(100, top + 1, MULTIPLE_STEP_HUNDREDTHS) / 100.0


def sustained_first(values: np.ndarray, grid: np.ndarray, target: float) -> dict[str, Any]:
    """First grid point reaching target, and first point after which it is never lost."""
    ok = values >= target
    first = grid[np.argmax(ok)] if ok.any() else None
    sustained = None
    if ok[-1]:
        bad = np.where(~ok)[0]
        sustained = grid[bad[-1] + 1] if len(bad) else grid[0]
    return {
        "first": None if first is None else float(first),
        "sustained": None if sustained is None else float(sustained),
    }


def kupiec_exact_section(confidence_level: float, cfg: RunConfig) -> dict[str, Any]:
    p0 = 1.0 - confidence_level
    m_fine = fine_multiples(confidence_level)
    per_n: dict[str, Any] = {}
    for n in cfg.n_grid:
        enum = kupiec_enumerate(n, confidence_level)
        x_lo, x_hi = kupiec_thresholds(n, confidence_level)
        xs = np.arange(n + 1)
        thr_set = (xs <= x_lo) | (xs >= x_hi)
        power = {f"{m:g}": power_from_enumeration(n, enum["reject"], m * p0) for m in cfg.multiples}
        fine = power_from_thresholds(n, x_lo, x_hi, m_fine * p0)
        mde = sustained_first(fine, m_fine, POWER_TARGET)
        size = power["1"]
        per_n[str(n)] = {
            "n": n,
            "rejecting_counts": {
                "x_lo": x_lo,
                "x_hi": x_hi,
                "lower_tail_empty": x_lo < 0,
                "upper_tail_empty": x_hi > n,
                "description": (
                    f"reject iff x <= {x_lo} or x >= {x_hi}"
                    if x_lo >= 0
                    else f"reject iff x >= {x_hi} (zero breaches can never reject)"
                ),
            },
            "enumeration_matches_threshold_form": bool(np.array_equal(enum["reject"], thr_set)),
            "reject_flag_inconsistent_x": enum["inconsistent_x"],
            "power": power,
            "size_at_multiple_1": size,
            "size_label": size_label(size),
            "mde_multiple_80": mde["sustained"],
            "mde_multiple_80_first_crossing": mde["first"],
            "mde_breach_rate_80": None if mde["sustained"] is None else mde["sustained"] * p0,
            "expected_breaches_at_mde": (
                None if mde["sustained"] is None else mde["sustained"] * p0 * n
            ),
        }

    # n needed: search n = 1..n_search_max using the threshold form.
    ns = np.arange(1, cfg.n_search_max + 1)
    thresholds = [kupiec_thresholds(int(n), confidence_level) for n in ns]
    n_needed: dict[str, Any] = {}
    for m in N_SEARCH_MULTIPLES:
        pw = np.array(
            [
                power_from_thresholds(int(n), lo, hi, m * p0)
                for n, (lo, hi) in zip(ns, thresholds, strict=True)
            ]
        )
        res = sustained_first(pw, ns, POWER_TARGET)
        n_needed[f"{m:g}"] = {
            "n_sustained": None if res["sustained"] is None else int(res["sustained"]),
            "n_first_crossing": None if res["first"] is None else int(res["first"]),
            "search_range": [1, cfg.n_search_max],
        }
    curve_n = ns[ns <= cfg.figure_n_max]
    curves = {
        f"{m:g}": [
            round(float(power_from_thresholds(int(n), *thresholds[int(n) - 1], m * p0)), 6)
            for n in curve_n
        ]
        for m in cfg.multiples
    }
    lower_tail_first_n = next(
        (int(n) for n, (lo, _) in zip(ns, thresholds, strict=True) if lo >= 0), None
    )
    return {
        "confidence_level": confidence_level,
        "nominal_breach_rate": p0,
        "significance_level": SIGNIFICANCE,
        "method": "exact binomial enumeration; decisions by options_risk kupiec_pof_test",
        "per_n": per_n,
        "n_needed_for_80pct_power": n_needed,
        "smallest_n_where_zero_breaches_can_reject": lower_tail_first_n,
        "power_vs_n_curve": {"n": [int(n) for n in curve_n], "power": curves},
    }


def size_label(size: float) -> str:
    if size < SIZE_BAND[0]:
        return "conservative"
    if size > SIZE_BAND[1]:
        return "liberal"
    return "approximately nominal"


# --------------------------------------------------------------------------
# Christoffersen (independence, conditional coverage): Markov-chain simulation
# --------------------------------------------------------------------------
def markov_params(p: float, rho: float) -> tuple[float, float]:
    """(pi01, pi11) of a two-state chain with stationary rate p and lag-1 autocorrelation rho.

    pi01 = P(breach | no breach) = p (1 - rho); pi11 = P(breach | breach) = p + rho (1 - p).
    """
    if not 0.0 <= p <= 1.0 or not 0.0 <= rho < 1.0:
        raise ValueError("need 0 <= p <= 1 and 0 <= rho < 1")
    return p * (1.0 - rho), p + rho * (1.0 - p)


def simulate_markov_breaches(
    rng: np.random.Generator, n: int, reps: int, p: float, rho: float
) -> np.ndarray:
    """(reps, n) boolean breach matrix; first state drawn from the stationary distribution."""
    pi01, pi11 = markov_params(p, rho)
    out = np.empty((reps, n), dtype=bool)
    out[:, 0] = rng.random(reps) < p
    for t in range(1, n):
        prob = np.where(out[:, t - 1], pi11, pi01)
        out[:, t] = rng.random(reps) < prob
    return out


def cell_seed(master_seed: int, level_idx: int, mult_idx: int, rho_idx: int, n: int) -> int:
    """Deterministic per-cell seed entropy, independent of grid order and worker count."""
    ss = np.random.SeedSequence([master_seed, level_idx, mult_idx, rho_idx, n])
    return int(ss.generate_state(1, dtype=np.uint64)[0])


def run_sim_cell(task: dict[str, Any]) -> dict[str, Any]:
    n, reps, conf = int(task["n"]), int(task["reps"]), float(task["confidence_level"])
    m, rho, seed = float(task["multiple"]), float(task["persistence"]), int(task["seed"])
    p = m * (1.0 - conf)
    rng = np.random.default_rng(seed)
    breaches = simulate_markov_breaches(rng, n, reps, p, rho)
    k_rej = i_rej = c_rej = either = 0
    inconsistent = nonfinite = cc_sum_mismatch = 0
    n_breaches = np.empty(reps)
    n11 = np.empty(reps)
    for r in range(reps):
        b = breaches[r]
        k = kupiec_pof_test(b, conf, significance_level=SIGNIFICANCE)
        ind = christoffersen_independence_test(b, conf, significance_level=SIGNIFICANCE)
        cc = conditional_coverage_test(b, conf, significance_level=SIGNIFICANCE)
        k_rej += k.reject_null
        i_rej += ind.reject_null
        c_rej += cc.reject_null
        either += k.reject_null or ind.reject_null
        for res in (k, ind, cc):
            if not np.isfinite(res.p_value):
                nonfinite += 1
            elif bool(res.reject_null) != bool(res.p_value < SIGNIFICANCE):
                inconsistent += 1
        if abs(cc.lr_statistic - (k.lr_statistic + ind.lr_statistic)) > 1e-9:
            cc_sum_mismatch += 1
        n_breaches[r] = k.n_breaches
        n11[r] = int(np.sum(b[:-1] & b[1:]))

    def est(count: int) -> dict[str, float]:
        ph = count / reps
        return {"rejections": count, "power": ph, "mc_se": float(np.sqrt(ph * (1 - ph) / reps))}

    pi01, pi11 = markov_params(p, rho)
    return {
        "n": n,
        "multiple": m,
        "persistence": rho,
        "true_breach_rate": p,
        "pi01": pi01,
        "pi11": pi11,
        "seed": seed,
        "reps": reps,
        "christoffersen_independence": est(i_rej),
        "conditional_coverage": est(c_rej),
        "kupiec_simulated": est(k_rej),
        "either_kupiec_or_independence": est(either),
        "mean_breaches": float(n_breaches.mean()),
        "share_with_no_consecutive_breach_pair": float(np.mean(n11 == 0)),
        "checks": {
            "reject_flag_inconsistent": inconsistent,
            "nonfinite_p_values": nonfinite,
            "cc_lr_not_sum_of_components": cc_sum_mismatch,
        },
    }


def christoffersen_section(cfg: RunConfig) -> dict[str, Any]:
    conf = CONFIDENCE_PRIMARY
    tasks = []
    for mi, m in enumerate(cfg.multiples):
        for ri, rho in enumerate(cfg.persistence):
            for n in cfg.n_grid:
                tasks.append(
                    {
                        "n": n,
                        "reps": cfg.n_reps,
                        "confidence_level": conf,
                        "multiple": m,
                        "persistence": rho,
                        "seed": cell_seed(cfg.master_seed, 0, mi, ri, n),
                    }
                )
    # Largest cells first for better load balance; results re-sorted below.
    tasks.sort(key=lambda t: -t["n"])
    if cfg.workers > 1:
        with ProcessPoolExecutor(max_workers=cfg.workers) as ex:
            cells = list(ex.map(run_sim_cell, tasks))
    else:
        cells = [run_sim_cell(t) for t in tasks]
    cells.sort(key=lambda c: (c["multiple"], c["persistence"], c["n"]))
    return {
        "confidence_level": conf,
        "significance_level": SIGNIFICANCE,
        "n_reps_per_cell": cfg.n_reps,
        "master_seed": cfg.master_seed,
        "seed_rule": "SeedSequence([master_seed, 0, multiple_idx, persistence_idx, n])",
        "breach_process": (
            "two-state Markov chain, stationary rate p = multiple * 0.05, lag-1 "
            "autocorrelation rho; pi01 = p(1-rho), pi11 = p + rho(1-p); first state ~ Bernoulli(p)"
        ),
        "cells": cells,
    }


def _cell(cells: list[dict[str, Any]], n: int, m: float, rho: float) -> dict[str, Any]:
    for c in cells:
        if c["n"] == n and c["multiple"] == m and c["persistence"] == rho:
            return c
    raise KeyError((n, m, rho))


def sim_mde_section(sim: dict[str, Any], cfg: RunConfig) -> dict[str, Any]:
    cells = sim["cells"]
    out: dict[str, Any] = {}
    for test in ("conditional_coverage", "christoffersen_independence", "kupiec_simulated"):
        per_rho: dict[str, Any] = {}
        for rho in cfg.persistence:
            by_n: dict[str, Any] = {}
            for n in cfg.n_grid:
                mde = None
                borderline = []
                for m in cfg.multiples:
                    if m == 1.0 and rho == 0.0:
                        continue  # the null itself
                    e = _cell(cells, n, m, rho)[test]
                    if abs(e["power"] - POWER_TARGET) < BORDERLINE_SE * e["mc_se"]:
                        borderline.append(m)
                    if mde is None and e["power"] >= POWER_TARGET:
                        mde = m
                by_n[str(n)] = {
                    "mde_multiple_80": mde if mde is not None else f">{max(cfg.multiples):g}",
                    "borderline_multiples": borderline,
                }
            n80 = {}
            for m in cfg.multiples:
                if m == 1.0 and rho == 0.0:
                    continue
                first = next(
                    (n for n in cfg.n_grid if _cell(cells, n, m, rho)[test]["power"] >= 0.8),
                    None,
                )
                n80[f"{m:g}"] = first if first is not None else f">{max(cfg.n_grid)}"
            per_rho[f"{rho:g}"] = {"by_n": by_n, "smallest_grid_n_with_80pct_power": n80}
        out[test] = per_rho
    return out


def sim_vs_exact_check(sim: dict[str, Any], kup: dict[str, Any]) -> dict[str, Any]:
    rows = []
    worst = 0.0
    for c in sim["cells"]:
        if c["persistence"] != 0.0:
            continue
        exact = kup["per_n"][str(c["n"])]["power"][f"{c['multiple']:g}"]
        simv = c["kupiec_simulated"]["power"]
        se = max(np.sqrt(exact * (1 - exact) / c["reps"]), 1e-12)
        z = (simv - exact) / se
        worst = max(worst, abs(z))
        rows.append({"n": c["n"], "multiple": c["multiple"], "exact": exact, "sim": simv, "z": z})
    return {
        "max_abs_z": worst,
        "tolerance_z": SIM_VS_EXACT_TOL_SE,
        "pass": worst <= 4.0,
        "rows": rows,
    }


# --------------------------------------------------------------------------
# Published results: interpretation aids from committed artifacts (read-only)
# --------------------------------------------------------------------------
def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def kupiec_acceptance_multiples(n: int, x: int) -> dict[str, Any]:
    """Test inversion with the production Kupiec function at the published level.

    For each hypothesised breach rate p_h = m * 0.05 (m on a 0.01 grid, p_h < 1),
    call kupiec_pof_test(breaches, confidence_level=1 - p_h); return the range
    of m that the production test does NOT reject given the observed count.
    """
    p0 = 1.0 - CONFIDENCE_PRIMARY
    ms = np.arange(1, int(round(100.0 / p0))) / 100.0
    b = _breach_array(n, x)
    ok = np.array(
        [
            not kupiec_pof_test(b, 1.0 - m * p0, significance_level=SIGNIFICANCE).reject_null
            for m in ms
        ]
    )
    idx = np.where(ok)[0]
    contiguous = bool(len(idx) and np.all(np.diff(idx) == 1))
    return {
        "multiple_grid": [0.01, float(ms[-1])],
        "non_rejected_multiple_min": float(ms[idx[0]]) if len(idx) else None,
        "non_rejected_multiple_max": float(ms[idx[-1]]) if len(idx) else None,
        "non_rejected_set_contiguous": contiguous,
    }


def published_section(kup: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for period, rel in PUBLISHED_ARTIFACTS.items():
        path = REPO_ROOT / rel
        bt = json.loads(path.read_text())["nonlinear_portfolio_study"][
            "kupiec_christoffersen_backtest"
        ]
        n, x = int(bt["n_forecasts"]), int(bt["kupiec"]["n_breaches"])
        recomputed = kupiec_pof_test(
            _breach_array(n, x), CONFIDENCE_PRIMARY, significance_level=SIGNIFICANCE
        ).p_value
        x_lo, x_hi = kupiec_thresholds(n, CONFIDENCE_PRIMARY)
        p0 = 1.0 - CONFIDENCE_PRIMARY
        power = {f"{m:g}": float(power_from_thresholds(n, x_lo, x_hi, m * p0)) for m in MULTIPLES}
        mde = kup["per_n"].get(str(n), {}).get("mde_multiple_80")
        out[period] = {
            "artifact": rel,
            "artifact_sha256": sha256_file(path),
            "n_forecasts": n,
            "n_breaches": x,
            "published_kupiec_p": float(bt["kupiec"]["p_value"]),
            "recomputed_kupiec_p": float(recomputed),
            "published_christoffersen_p": float(bt["christoffersen"]["p_value"]),
            "kupiec_rejecting_counts": {"x_lo": x_lo, "x_hi": x_hi},
            "kupiec_power_at_this_n": power,
            "kupiec_mde_multiple_80": mde,
            "kupiec_acceptance_by_inversion": kupiec_acceptance_multiples(n, x),
        }
    return out


def daily_counterfactual_section() -> dict[str, Any]:
    p0 = 1.0 - CONFIDENCE_PRIMARY
    rows: dict[str, Any] = {}
    total = 0
    for label, rel in DAILY_COUNT_ARTIFACTS.items():
        path = REPO_ROOT / rel
        n = int(
            json.loads(path.read_text())["result"]["equity_rolling_hs_var_backtest"]["n_forecasts"]
        )
        total += n
        rows[label] = {"artifact": rel, "artifact_sha256": sha256_file(path), "n": n}
    rows["all periods (daily)"] = {"artifact": None, "n": total}
    m_fine = fine_multiples(CONFIDENCE_PRIMARY)
    for row in rows.values():
        n = row["n"]
        lo, hi = kupiec_thresholds(n, CONFIDENCE_PRIMARY)
        row["kupiec_power"] = {
            f"{m:g}": float(power_from_thresholds(n, lo, hi, m * p0)) for m in MULTIPLES
        }
        row["kupiec_mde_multiple_80"] = sustained_first(
            power_from_thresholds(n, lo, hi, m_fine * p0), m_fine, POWER_TARGET
        )["sustained"]
    return {
        "note": (
            "Forecast counts of the daily-cadence backtests over the same SPY history "
            "(v1 artifacts, used only for n). Kupiec exact power at 95%."
        ),
        "rows": rows,
    }


# --------------------------------------------------------------------------
# Figure
# --------------------------------------------------------------------------
SERIES_COLORS = ("#2a78d6", "#eb6834", "#1baf7a", "#c98500")
MARKERS = ("o", "s", "^", "D")


def make_figure(result: dict[str, Any], out_png: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    kup = result["kupiec_exact"]["confidence_0.95"]
    sim = result["christoffersen_simulation"]
    cells = sim["cells"]
    n_grid = result["parameters"]["n_grid"]
    multiples = result["parameters"]["multiples"]
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.8), sharey=True)
    ink, muted = "#0b0b0b", "#52514e"

    def style(ax: Any, title: str) -> None:
        ax.set_xscale("log")
        ax.set_ylim(-0.02, 1.02)
        ax.axhline(0.8, color=muted, lw=1, ls="--")
        ax.axhline(0.05, color=muted, lw=1, ls=":")
        for n_pub in (12, 95):
            ax.axvline(n_pub, color="#c3c2b7", lw=1)
            ax.text(n_pub * 1.05, 0.97, f"n={n_pub}", color=muted, fontsize=8, va="top")
        ax.set_title(title, fontsize=10, color=ink, loc="left")
        ax.set_xlabel("number of VaR forecasts n (log scale)", color=muted)
        ax.grid(True, which="major", color="#ecebe8", lw=0.6)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)

    ax = axes[0]
    curve_n = kup["power_vs_n_curve"]["n"]
    for i, m in enumerate(multiples):
        ax.plot(
            curve_n,
            kup["power_vs_n_curve"]["power"][f"{m:g}"],
            color=SERIES_COLORS[i],
            lw=1.2,
            label=f"{m:g}x ({m * 5:g}% true rate)",
        )
    style(ax, "A. Kupiec POF (exact), every n")
    ax.set_ylabel("rejection probability at 5% size", color=muted)
    ax.legend(fontsize=8, frameon=False, loc="center right")

    for ax, test, title in (
        (axes[1], "conditional_coverage", "B. Conditional coverage (simulated)"),
        (axes[2], "christoffersen_independence", "C. Christoffersen independence (simulated)"),
    ):
        for i, m in enumerate(multiples):
            for rho, ls in ((0.0, "-"), (0.5, "--")):
                ys = [_cell(cells, n, m, rho)[test]["power"] for n in n_grid]
                ax.plot(
                    n_grid,
                    ys,
                    color=SERIES_COLORS[i],
                    ls=ls,
                    lw=2,
                    marker=MARKERS[i],
                    ms=6,
                    label=f"{m:g}x, persistence {rho:g}"
                    if test == "conditional_coverage"
                    else None,
                )
        style(ax, title)
    axes[1].legend(fontsize=7, frameon=False, loc="upper left", bbox_to_anchor=(0.0, 0.92))
    fig.text(
        0.01,
        0.01,
        "95% one-day VaR, nominal breach rate 5%. Dashed grey = 80% power; dotted = 5% size. "
        "Panels B-C: solid = independent breaches, dashed = clustered (lag-1 autocorrelation "
        f"0.5); {sim['n_reps_per_cell']:,} replications per point.",
        fontsize=8,
        color=muted,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=150, metadata={"Software": None})
    plt.close(fig)


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------
def _git_head() -> dict[str, Any]:
    def run(args: Sequence[str]) -> str:
        try:
            return subprocess.run(
                list(args), cwd=REPO_ROOT, capture_output=True, text=True, check=True
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return ""

    return {
        "commit": run(["git", "rev-parse", "HEAD"]) or None,
        "dirty_paths": [ln for ln in run(["git", "status", "--porcelain"]).splitlines() if ln],
    }


def run_study(cfg: RunConfig, *, progress: Callable[[str], None] | None = None) -> dict[str, Any]:
    log = progress or (lambda _msg: None)
    t0 = time.time()
    log("kupiec exact (95%)")
    kup95 = kupiec_exact_section(CONFIDENCE_PRIMARY, cfg)
    log("kupiec exact (99%, supplementary)")
    kup99 = kupiec_exact_section(CONFIDENCE_SECONDARY, cfg)
    log("christoffersen simulation")
    sim = christoffersen_section(cfg)
    log("summaries")
    result: dict[str, Any] = {
        "study": "B: power / null-calibration of the VaR backtests",
        "protocol": "research/power/PROTOCOL.md",
        "protocol_version": PROTOCOL_VERSION,
        "run_label": cfg.label,
        "parameters": {
            "confidence_primary": CONFIDENCE_PRIMARY,
            "confidence_secondary_supplementary": CONFIDENCE_SECONDARY,
            "significance_level": SIGNIFICANCE,
            "n_grid": list(cfg.n_grid),
            "multiples": list(cfg.multiples),
            "persistence": list(cfg.persistence),
            "n_reps": cfg.n_reps,
            "master_seed": cfg.master_seed,
            "power_target": POWER_TARGET,
            "n_search_max": cfg.n_search_max,
            "n_search_multiples": list(N_SEARCH_MULTIPLES),
            "fine_multiple_step": MULTIPLE_STEP_HUNDREDTHS / 100.0,
            "size_band": list(SIZE_BAND),
            "production_functions": [
                "options_risk.risk.backtesting.kupiec_pof_test",
                "options_risk.risk.backtesting.christoffersen_independence_test",
                "options_risk.risk.backtesting.conditional_coverage_test",
            ],
        },
        "kupiec_exact": {"confidence_0.95": kup95, "confidence_0.99_supplementary": kup99},
        "christoffersen_simulation": sim,
        "simulated_mde": sim_mde_section(sim, cfg),
        "check_simulated_kupiec_vs_exact": sim_vs_exact_check(sim, kup95),
        "published_results": published_section(kup95),
        "daily_backtest_counterfactual": daily_counterfactual_section(),
    }
    result["run_info"] = {
        "excluded_from_determinism": True,
        "git": _git_head(),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "workers": cfg.workers,
        "wall_seconds": round(time.time() - t0, 1),
    }
    return result


def _json_default(o: Any) -> Any:
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    raise TypeError(f"not JSON serializable: {type(o)}")


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    ap.add_argument("--smoke", action="store_true", help="tiny grid for a fast check")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument(
        "--out-json", type=Path, default=REPO_ROOT / "results/power/var_backtest_power.json"
    )
    ap.add_argument(
        "--out-png", type=Path, default=REPO_ROOT / "results/power/var_backtest_power.png"
    )
    ap.add_argument("--no-figure", action="store_true")
    args = ap.parse_args(argv)
    base = SMOKE_CONFIG if args.smoke else RunConfig()
    cfg = RunConfig(**{**base.__dict__, "workers": args.workers})
    result = run_study(
        cfg, progress=lambda m: print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)
    )
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(result, indent=1, default=_json_default) + "\n")
    if not args.no_figure:
        make_figure(result, args.out_png)
    print(f"wrote {args.out_json}" + ("" if args.no_figure else f" and {args.out_png}"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
