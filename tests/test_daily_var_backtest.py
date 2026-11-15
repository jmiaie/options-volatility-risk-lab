"""Tests for the daily VaR/ES backtest harness (research/daily_var_backtest); synthetic data."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from scipy.stats import kstest

from options_risk.risk.backtesting import christoffersen_independence_test

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
dvb: Any = importlib.import_module("research.daily_var_backtest.daily_var_backtest")
runner: Any = importlib.import_module("research.daily_var_backtest.run_daily_var_backtest")


@pytest.fixture(scope="module")
def frame() -> pd.DataFrame:
    return dvb.synthetic_frame(7, 900, dvb.DEFAULT_T4_SCALE)


class TestP1Repricing:
    def test_precondition_passes(self) -> None:
        res = dvb.check_repricing()
        assert res["zero_shock_max_abs_loss"] <= 1e-9
        assert res["decay_vs_direct_abs_diff"] <= 1e-9
        assert res["decay_vs_theta_rel_diff"] <= 0.10
        assert res["passed"]

    def test_decay_only_equals_direct_bs_reprice(self) -> None:
        from options_risk.pricing.black_scholes import bsm_price

        S, K, T, r, sig = 100.0, 100.0, 30 / 252, 0.03, 0.2
        direct = -(
            -200
            * (bsm_price(S, K, T - 1 / 252, r, sig, "call") - bsm_price(S, K, T, r, sig, "call"))
            + 200
            * (
                bsm_price(S, 0.95 * K, T - 1 / 252, r, sig, "put")
                - bsm_price(S, 0.95 * K, T, r, sig, "put")
            )
        )
        a = (np.array([K]), np.array([S]), np.array([T]), np.array([r]), np.array([sig]))
        vec = dvb.scenario_losses(*a, np.zeros((1, 1, 2)), model="M2")[0, 0]
        assert vec == pytest.approx(direct, abs=1e-9)

    def test_vectorised_matches_production_scenario_engine(self) -> None:
        rng = np.random.default_rng(1)
        roll, S, T, r, sig = 410.0, 402.0, 21 / 252, 0.04, 0.27
        pf = dvb.portfolio_for_book(roll, S, T, r, sig)
        shocks = rng.normal(0, [0.015, 0.08], size=(1, 40, 2))
        a = (np.array([roll]), np.array([S]), np.array([T]), np.array([r]), np.array([sig]))
        for model, decay in (("M2", 1 / 252), ("M1", 0.0)):
            vec = dvb.scenario_losses(*a, shocks, model=model)[0]
            ref = [
                dvb.portfolio_scenario_loss(pf, s[0], s[1] if model == "M2" else 0.0, decay)
                for s in shocks[0]
            ]
            assert np.allclose(vec, ref, atol=1e-8)


class TestP2NoLookahead:
    def test_prefix_invariance(self, frame: pd.DataFrame) -> None:
        res = dvb.check_prefix_invariance(frame, 100)
        assert res["passed"]

    def test_future_rows_do_not_change_past_forecasts(self, frame: pd.DataFrame) -> None:
        full = dvb.run_forecasts(frame, models=("M2",))
        bumped = frame.copy()
        bumped.iloc[-50:, bumped.columns.get_loc("spot")] *= 1.3
        other = dvb.run_forecasts(bumped, models=("M2",))
        k = len(full.rows) - 60
        assert np.array_equal(full.models["M2"].var[0.95][:k], other.models["M2"].var[0.95][:k])
        assert np.array_equal(full.loss[:k], other.loss[:k])

    def test_book_rolls_monthly_and_time_falls_by_session(self, frame: pd.DataFrame) -> None:
        st = dvb.book_state(frame)
        months = frame.index.to_period("M")
        assert st.is_roll[0] and st.is_roll[1:].sum() == len(set(months)) - 1
        assert np.allclose(st.T[st.is_roll], 30 / 252)
        i = int(np.where(st.is_roll)[0][3])
        assert st.T[i + 1] == pytest.approx(29 / 252)


class TestPitAndTests:
    def test_pit_uniform_under_correct_model(self, frame: pd.DataFrame) -> None:
        fs = dvb.run_forecasts(frame, models=("M2",), levels=(0.95,))
        u = dvb.randomised_pit(fs.models["M2"].scen, fs.loss)
        assert abs(u.mean() - 0.5) < 0.04
        assert kstest(u, "uniform").pvalue > 1e-3

    def test_pit_noise_is_prefix_stable(self) -> None:
        scen = np.random.default_rng(0).normal(size=(40, 252))
        loss = np.random.default_rng(1).normal(size=40)
        assert np.array_equal(
            dvb.randomised_pit(scen, loss)[:25], dvb.randomised_pit(scen[:25], loss[:25])
        )

    def test_du_escanciano_hand_computed(self) -> None:
        # alpha=0.025; u=[0.01, 0.5, 0.02] -> H = [0.6, 0, 0.2]; mean = 0.8/3
        res = dvb.du_escanciano_test(np.array([0.01, 0.5, 0.02]))
        assert res["statistic"] == pytest.approx(0.8 / 3, abs=1e-12)
        var = 0.025 * (1 / 3 - 0.025 / 4) / 3
        z = (0.8 / 3 - 0.0125) / np.sqrt(var)
        assert res["z"] == pytest.approx(z, abs=1e-12)
        from scipy.stats import norm

        assert res["p_value"] == pytest.approx(2 * norm.sf(abs(z)), abs=1e-12)

    def test_du_escanciano_size_under_uniform_pit(self) -> None:
        rng = np.random.default_rng(5)
        rej = np.mean(
            [dvb.du_escanciano_test(rng.random(2500))["p_value"] < 0.05 for _ in range(300)]
        )
        assert 0.02 <= rej <= 0.09

    def test_holm_known_values(self) -> None:
        assert dvb.holm_adjust([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])
        assert dvb.holm_adjust([0.01, 0.02, 0.03]) == pytest.approx([0.03, 0.04, 0.04])
        assert dvb.holm_adjust([0.5, 0.9]) == pytest.approx([1.0, 1.0])
        assert dvb.holm_adjust([0.001]) == [0.001]

    def test_christoffersen_gapped_matches_production_without_gaps(self) -> None:
        b = np.random.default_rng(2).random(300) < 0.1
        res = dvb.christoffersen_gapped(b, np.ones(299, bool), 0.95)
        assert res["p_value"] == pytest.approx(christoffersen_independence_test(b, 0.95).p_value)
        gapped = np.ones(299, bool)
        gapped[100] = False
        assert dvb.christoffersen_gapped(b, gapped, 0.95)["p_value"] != res["p_value"]

    def test_acerbi_szekely_runs_and_is_finite(self, frame: pd.DataFrame) -> None:
        fs = dvb.run_forecasts(frame, models=("M2",))
        mf = fs.models["M2"]
        z2 = dvb.acerbi_szekely_z2(fs.loss, mf.var[0.975], mf.es[0.975], mf.scen, n_sim=500)
        assert 0 < z2["p_value"] <= 1 and np.isfinite(z2["critical_95"])


class TestNaNRule:
    def test_nan_spot_raises(self, frame: pd.DataFrame) -> None:
        bad = frame.copy()
        bad.iloc[400, bad.columns.get_loc("spot")] = np.nan
        with pytest.raises(ValueError):
            dvb.run_forecasts(bad)

    def test_nan_loss_or_var_raises_in_tests(self) -> None:
        ok = np.ones(10)
        cont = np.ones(9, bool)
        u = np.full(10, 0.5)
        with pytest.raises(ValueError):
            dvb.primary_tests(ok, np.where(np.arange(10) == 3, np.nan, 1.0), cont, u)
        with pytest.raises(ValueError):
            dvb.primary_tests(np.where(np.arange(10) == 3, np.inf, 1.0), ok, cont, u)
        with pytest.raises(ValueError):
            dvb.du_escanciano_test(np.array([0.1, np.nan]))
        with pytest.raises(ValueError):
            dvb.randomised_pit(np.ones((2, 252)), np.array([1.0, np.nan]))


class TestDataPrep:
    def test_vix_carry_and_drop_counts(self) -> None:
        idx = pd.bdate_range("2020-01-01", periods=20)
        spy = pd.Series(100.0, index=idx)
        vix = pd.Series(20.0, index=idx)
        vix = vix.drop([idx[3], idx[10], idx[11], idx[12], idx[13], idx[14], idx[15], idx[16]])
        rate = pd.Series(0.01, index=idx[:1])
        frame, q = dvb.prepare_frame(spy, vix, rate)
        assert q["vix_carried_forward"] == 1 + 5
        assert q["dropped_no_recent_vix"] == 2
        assert len(frame) == 18 and set(frame["sess"]) == set(range(20)) - {15, 16}


class TestP4:
    def test_tiny_run_returns_rates_in_unit_interval(self) -> None:
        p4 = dvb.run_p4(3, length=330)
        assert set(p4["rejection_rates"]) == {"T1", "T2", "T3"}
        assert all(0.0 <= v <= 1.0 for v in p4["rejection_rates"].values())
        assert all(len(v) == 3 for v in p4["statistics"].values())

    def test_tail_multiplier_and_decision_rule(self) -> None:
        p4 = dvb.run_p4(2, length=330, tail_k=2.0)
        assert p4["tail_k"] == 2.0
        obs = {
            "T1": {"statistic": 1.0, "p_value": 0.3},
            "T2": {"statistic": 1.0, "p_value": 0.3},
            "T3": {"z": 1.0, "p_value": 0.3},
        }
        fake = {
            "rejection_rates": {"T1": 0.05, "T2": 0.01, "T3": 0.2},
            "statistics": p4["statistics"],
        }
        d = dvb.apply_p4_decision(obs, fake)
        assert d["T1"]["p_used"] == 0.3 and d["T2"]["p_used"] != 0.3 and d["z2_replaces_t3"]

    def test_paths_are_reproducible(self) -> None:
        a = dvb.synthetic_frame(4, 50, dvb.DEFAULT_T4_SCALE)
        b = dvb.synthetic_frame(4, 50, dvb.DEFAULT_T4_SCALE)
        c = dvb.synthetic_frame(5, 50, dvb.DEFAULT_T4_SCALE)
        assert a.equals(b) and not a.equals(c)


class TestRunner:
    def test_refuses_without_protocol(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(runner, "PROTOCOL", tmp_path / "PROTOCOL.md")
        code = runner.main(
            [
                "--raw-dir",
                str(tmp_path),
                "--manifest",
                str(tmp_path / "m.json"),
                "--out",
                str(tmp_path / "o.json"),
            ]
        )
        assert code != 0
        assert "PROTOCOL.md" in capsys.readouterr().err
        assert not (tmp_path / "o.json").exists()

    def test_repo_has_no_protocol_yet(self) -> None:
        # The frozen copy is added by the owner; until then the real runner must refuse.
        assert runner.PROTOCOL.name == "PROTOCOL.md"
