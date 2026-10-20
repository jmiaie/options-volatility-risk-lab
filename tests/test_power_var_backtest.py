"""Tests for the VaR-backtest power study harness (research/power/var_backtest_power.py)."""

from __future__ import annotations

import importlib
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from scipy.stats import binom

from options_risk.risk.backtesting import kupiec_pof_test

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
vbp: Any = importlib.import_module("research.power.var_backtest_power")


class TestKupiecEnumeration:
    def test_n12_rejection_region_hand_derived(self) -> None:
        # Hand-derived: at n=12, p0=5%, LR(x=2)=2.19 (p=0.139), LR(x=3)=5.40 (p=0.020).
        assert vbp.kupiec_thresholds(12, 0.95) == (-1, 3)
        enum = vbp.kupiec_enumerate(12, 0.95)
        assert list(np.where(enum["reject"])[0]) == list(range(3, 13))
        size = vbp.power_from_enumeration(12, enum["reject"], 0.05)
        assert size == pytest.approx(binom.sf(2, 12, 0.05), abs=1e-12)

    @pytest.mark.parametrize("conf", [0.95, 0.99])
    def test_threshold_form_matches_full_enumeration(self, conf: float) -> None:
        for n in list(range(1, 151)) + [251, 499]:
            enum = vbp.kupiec_enumerate(n, conf)
            lo, hi = vbp.kupiec_thresholds(n, conf)
            xs = np.arange(n + 1)
            assert np.array_equal(enum["reject"], (xs <= lo) | (xs >= hi)), n
            assert enum["inconsistent_x"] == []

    def test_enumeration_uses_production_decision(self) -> None:
        n = 95
        enum = vbp.kupiec_enumerate(n, 0.95)
        for x in range(n + 1):
            b = np.zeros(n, dtype=bool)
            b[:x] = True
            assert enum["reject"][x] == kupiec_pof_test(b, 0.95).reject_null

    def test_zero_breaches_first_reject_at_n38(self) -> None:
        # -2 n ln(0.95) > 3.841 first holds at n = 38.
        assert vbp.kupiec_thresholds(37, 0.95)[0] == -1
        assert vbp.kupiec_thresholds(38, 0.95)[0] == 0

    def test_power_at_top_of_fine_grid_is_finite(self) -> None:
        # Regression (Amendment A1): 20 * (1 - 0.95) overshoots 1.0 by one ulp.
        m = vbp.fine_multiples(0.95)
        lo, hi = vbp.kupiec_thresholds(95, 0.95)
        pw = vbp.power_from_thresholds(95, lo, hi, m * (1 - 0.95))
        assert np.all(np.isfinite(pw)) and pw[-1] == pytest.approx(1.0)
        assert vbp.sustained_first(pw, m, 0.8)["sustained"] is not None

    def test_sustained_first(self) -> None:
        grid = np.arange(6.0)
        vals = np.array([0.1, 0.85, 0.7, 0.9, 0.95, 0.99])
        assert vbp.sustained_first(vals, grid, 0.8) == {"first": 1.0, "sustained": 3.0}
        assert vbp.sustained_first(vals * 0, grid, 0.8) == {"first": None, "sustained": None}


class TestMarkovChain:
    def test_params(self) -> None:
        assert vbp.markov_params(0.05, 0.0) == pytest.approx((0.05, 0.05))
        pi01, pi11 = vbp.markov_params(0.1, 0.5)
        assert pi11 - pi01 == pytest.approx(0.5)
        assert pi01 / (1 - pi11 + pi01) == pytest.approx(0.1)
        with pytest.raises(ValueError):
            vbp.markov_params(0.1, 1.0)

    @pytest.mark.parametrize("rho", [0.0, 0.2, 0.5])
    def test_marginal_rate_and_autocorrelation(self, rho: float) -> None:
        rng = np.random.default_rng(123)
        b = vbp.simulate_markov_breaches(rng, 4000, 50, 0.1, rho).astype(float)
        assert b.mean() == pytest.approx(0.1, abs=0.005)
        x0, x1 = b[:, :-1].ravel(), b[:, 1:].ravel()
        assert np.corrcoef(x0, x1)[0, 1] == pytest.approx(rho, abs=0.02)

    def test_cell_seed_deterministic_and_distinct(self) -> None:
        a = vbp.cell_seed(1, 0, 1, 2, 95)
        assert a == vbp.cell_seed(1, 0, 1, 2, 95)
        assert a != vbp.cell_seed(1, 0, 1, 2, 96)
        assert a != vbp.cell_seed(1, 0, 2, 1, 95)

    def test_sim_cell_reproducible(self) -> None:
        task = {
            "n": 95,
            "reps": 50,
            "confidence_level": 0.95,
            "multiple": 2.0,
            "persistence": 0.2,
            "seed": 7,
        }
        r1, r2 = vbp.run_sim_cell(task), vbp.run_sim_cell(task)
        assert r1 == r2
        assert r1["checks"] == {
            "reject_flag_inconsistent": 0,
            "nonfinite_p_values": 0,
            "cc_lr_not_sum_of_components": 0,
        }


def test_smoke_run_under_30s(tmp_path: Path) -> None:
    out = tmp_path / "smoke.json"
    t0 = time.time()
    assert vbp.main(["--smoke", "--no-figure", "--out-json", str(out)]) == 0
    elapsed = time.time() - t0
    assert elapsed < 30.0, f"smoke run took {elapsed:.1f}s"
    res = json.loads(out.read_text())
    kup = res["kupiec_exact"]["confidence_0.95"]["per_n"]
    assert kup["12"]["rejecting_counts"]["x_hi"] == 3
    assert all(v["enumeration_matches_threshold_form"] for v in kup.values())
    assert len(res["christoffersen_simulation"]["cells"]) == 2 * 4 * 3
    pub = res["published_results"]
    assert pub["DEV"]["n_forecasts"] == 95 and pub["DEV"]["n_breaches"] == 9
    for row in pub.values():
        assert row["recomputed_kupiec_p"] == pytest.approx(row["published_kupiec_p"], abs=1e-12)
    assert res["daily_backtest_counterfactual"]["rows"]["all periods (daily)"]["n"] == 2511


def test_smoke_figure(tmp_path: Path) -> None:
    pytest.importorskip("matplotlib")
    out = tmp_path / "smoke.json"
    png = tmp_path / "smoke.png"
    assert vbp.main(["--smoke", "--out-json", str(out), "--out-png", str(png)]) == 0
    assert png.stat().st_size > 10_000
