"""Offline tests for Directive #9 acquisition helpers (no network)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1] / "scripts" / "acquire_yf_options_risk_underlyings_daily.py"
)


def _load_acquire_module():
    spec = importlib.util.spec_from_file_location(
        "acquire_yf_options_risk_underlyings_daily", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def acq():
    return _load_acquire_module()


def _sample_frame(n: int = 10) -> pd.DataFrame:
    dates = pd.date_range("2015-01-02", periods=n, freq="B")
    rng = np.random.default_rng(0)
    prices = 100 + np.cumsum(rng.normal(0, 0.5, n))
    return pd.DataFrame(
        {
            "Open": prices - 0.1,
            "High": prices + 0.2,
            "Low": prices - 0.2,
            "Close": prices,
            "Volume": rng.integers(1_000_000, 2_000_000, n),
            "Dividends": 0.0,
            "Stock Splits": 0.0,
        },
        index=dates,
    )


def test_validate_frame_ok(acq):
    stats = acq.validate_frame("SPY", _sample_frame())
    assert stats["row_count"] == 10
    assert stats["missing_ohlcv_cells"] == 0


def test_canonical_hash_stable(acq):
    h1 = acq.canonical_dataset_hash({"A.csv": "aaa", "B.csv": "bbb"})
    h2 = acq.canonical_dataset_hash({"B.csv": "bbb", "A.csv": "aaa"})
    assert h1 == h2
    assert len(h1) == 64


def test_default_symbols(acq):
    assert acq.DEFAULT_SYMBOLS == ["SPY", "QQQ", "IWM"]
