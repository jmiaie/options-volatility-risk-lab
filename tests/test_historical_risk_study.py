"""Offline tests for Directive #9 historical risk study helpers (no network)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from options_risk.historical_risk_study import (
    PeriodSpec,
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
