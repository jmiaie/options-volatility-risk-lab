"""Offline tests for Directive #9 historical risk study helpers (no network)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from options_risk.historical_risk_study import (
    PeriodSpec,
    equity_and_option_var_snapshot,
    load_close_panel,
    period_realized_vol,
    rolling_hs_var_backtest,
    run_period_study,
)


def _synthetic_panel(n: int = 800) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    idx = pd.date_range("2015-01-02", periods=n, freq="B")
    spy = 100 * np.exp(np.cumsum(rng.normal(0.0002, 0.01, n)))
    qqq = 80 * np.exp(np.cumsum(rng.normal(0.00025, 0.012, n)))
    iwm = 60 * np.exp(np.cumsum(rng.normal(0.00015, 0.014, n)))
    return pd.DataFrame({"SPY": spy, "QQQ": qqq, "IWM": iwm}, index=idx)


def test_period_realized_vol_positive():
    panel = _synthetic_panel()
    rets = np.log(panel["SPY"] / panel["SPY"].shift(1)).dropna()
    vol = period_realized_vol(rets)
    assert vol > 0


def test_rolling_hs_var_backtest_runs():
    panel = _synthetic_panel()
    rets = np.log(panel["SPY"] / panel["SPY"].shift(1)).dropna()
    out = rolling_hs_var_backtest(rets, lookback=60, confidence_level=0.95, notional=1.0)
    assert out["n_forecasts"] > 0
    assert "kupiec" in out
    assert out["kupiec"]["n_obs"] == out["n_forecasts"]


def test_holdout_blocked_without_freeze():
    panel = _synthetic_panel()
    formation = PeriodSpec("formation_dev", "2015-01-01", "2018-12-31")
    holdout = PeriodSpec("holdout", "2019-01-01", "2019-12-31")
    config = {
        "status": "not-yet-frozen-for-holdout",
        "risk": {"var_lookback": 60, "confidence_level": 0.95, "equity_notional": 1.0},
        "stylized_book": {
            "equity_shares": 0.0,
            "option_contracts": -1.0,
            "option_T": 30 / 365,
            "rate": 0.02,
            "dividend_yield": 0.01,
            "multiplier": 100.0,
        },
        "hedging": {
            "option_T": 0.5,
            "n_steps": 12,
            "cost_rate": 0.0,
            "n_seeds": 5,
            "option_qty": -1.0,
        },
    }
    with pytest.raises(RuntimeError, match="Holdout evaluation blocked"):
        run_period_study(
            full_panel=panel,
            formation=formation,
            eval_period=holdout,
            config=config,
            primary_symbol="SPY",
            allow_holdout=True,
        )


def test_formation_study_produces_key_metrics():
    panel = _synthetic_panel()
    formation = PeriodSpec("formation_dev", "2015-01-01", "2018-12-31")
    config = {
        "status": "not-yet-frozen-for-holdout",
        "risk": {"var_lookback": 60, "confidence_level": 0.95, "equity_notional": 1.0},
        "stylized_book": {
            "equity_shares": 0.0,
            "option_contracts": -1.0,
            "option_T": 30 / 365,
            "rate": 0.02,
            "dividend_yield": 0.01,
            "multiplier": 100.0,
        },
        "hedging": {
            "option_T": 0.5,
            "n_steps": 12,
            "cost_rate": 0.0,
            "n_seeds": 5,
            "option_qty": -1.0,
        },
    }
    out = run_period_study(
        full_panel=panel,
        formation=formation,
        eval_period=formation,
        config=config,
        primary_symbol="SPY",
        allow_holdout=False,
    )
    km = out["key_metrics"]
    assert km["n_eval_bars"] > 0
    assert km["option_hs_var"] is not None
    assert km["hedge_mean_final_wealth"] is not None


def test_load_close_panel(tmp_path):
    panel = _synthetic_panel(n=20)
    for col in panel.columns:
        df = pd.DataFrame(
            {
                "Open": panel[col],
                "High": panel[col],
                "Low": panel[col],
                "Close": panel[col],
                "Volume": 1_000_000,
            },
            index=panel.index,
        )
        df.to_csv(tmp_path / f"{col}.csv")
    loaded = load_close_panel(tmp_path, list(panel.columns))
    assert list(loaded.columns) == list(panel.columns)
    assert len(loaded) == 20


def _default_test_config(var_lookback: int = 60) -> dict:
    return {
        "status": "not-yet-frozen-for-holdout",
        "risk": {
            "var_lookback": var_lookback,
            "confidence_level": 0.95,
            "equity_notional": 1.0,
        },
        "stylized_book": {
            "equity_shares": 0.0,
            "option_contracts": -1.0,
            "option_T": 30 / 365,
            "rate": 0.02,
            "dividend_yield": 0.01,
            "multiplier": 100.0,
        },
        "hedging": {
            "option_T": 0.5,
            "n_steps": 12,
            "cost_rate": 0.0,
            "n_seeds": 5,
            "option_qty": -1.0,
        },
    }


def test_option_book_snapshot_uses_shocks_not_eval_period_argument_name():
    """Regression test: an earlier version of equity_and_option_var_snapshot
    took an `eval_returns` argument and fed it directly as both the
    historical-simulation shock set and the delta-normal factor vol input --
    using returns from WITHIN the period being evaluated to estimate the
    risk of a position established at that period's start, a look-ahead
    relative to historical_simulation_var's own documented contract ("uses
    only a rolling window of past returns"). The parameter is now named
    `shock_returns` and callers must supply a pre-period window."""
    rng = np.random.default_rng(0)
    spot = 100.0
    shock_returns = rng.normal(0, 0.01, 300)
    out = equity_and_option_var_snapshot(
        spot,
        shock_returns,
        formation_vol=0.2,
        confidence_level=0.95,
        equity_shares=0.0,
        option_contracts=-1.0,
        option_T=30 / 365,
        rate=0.02,
        dividend_yield=0.01,
        multiplier=100.0,
    )
    assert out["n_shock_returns"] == len(shock_returns)


def test_option_book_var_is_unaffected_by_eval_period_returns():
    """The core regression: perturbing ONLY the eval period's own prices
    (after the point the option book is established) must not change the
    option-book VaR/ES snapshot at all, since those shocks must come from
    before the eval period starts. Before the fix, this test would have
    failed -- the snapshot used to be computed directly from the eval
    period's own returns."""
    formation = PeriodSpec("formation_dev", "2015-01-01", "2018-12-31")
    validation = PeriodSpec("validation", "2019-01-01", "2019-06-30")
    config = _default_test_config()

    panel_a = _synthetic_panel(n=1200)
    panel_b = panel_a.copy()
    # Perturb prices strictly AFTER the validation window's first bar --
    # leaving the first bar untouched keeps `spot` (set from eval_prices[0])
    # identical between A and B, isolating whether shocks/factor-vol still
    # depend on the (perturbed) later eval-period returns.
    val_mask = (panel_b.index > "2019-01-02") & (panel_b.index <= "2019-06-30")
    rng = np.random.default_rng(1)
    perturbation = np.exp(rng.normal(0, 0.05, int(val_mask.sum())))
    for col in panel_b.columns:
        panel_b.loc[val_mask, col] = panel_b.loc[val_mask, col].to_numpy() * perturbation

    out_a = run_period_study(
        full_panel=panel_a,
        formation=formation,
        eval_period=validation,
        config=config,
        primary_symbol="SPY",
        allow_holdout=False,
    )
    out_b = run_period_study(
        full_panel=panel_b,
        formation=formation,
        eval_period=validation,
        config=config,
        primary_symbol="SPY",
        allow_holdout=False,
    )

    snap_a = out_a["stylized_option_book_var"]
    snap_b = out_b["stylized_option_book_var"]
    assert snap_a["historical_simulation"]["var"] == pytest.approx(
        snap_b["historical_simulation"]["var"]
    )
    assert snap_a["historical_simulation"]["es"] == pytest.approx(
        snap_b["historical_simulation"]["es"]
    )
    assert snap_a["delta_normal"]["var"] == pytest.approx(snap_b["delta_normal"]["var"])
    # Sanity: the perturbation is large enough that it WOULD have changed
    # eval_vol (proving this isn't a no-op perturbation).
    assert out_a["key_metrics"]["eval_realized_vol_ann"] != pytest.approx(
        out_b["key_metrics"]["eval_realized_vol_ann"]
    )
