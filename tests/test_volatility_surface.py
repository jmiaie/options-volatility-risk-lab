"""Volatility surface tests (P1 item 9): moneyness, interpolation, extrapolation flags."""

from __future__ import annotations

import numpy as np
import pytest

from options_risk.data.chain import clean_chain, synthetic_chain
from options_risk.volatility.surface import (
    VolSurface,
    build_surface_from_chain,
    check_surface_sanity,
    log_forward_moneyness,
)


def test_log_forward_moneyness_zero_at_the_forward() -> None:
    S, T, r, q = 100.0, 1.0, 0.05, 0.0
    forward = S * np.exp((r - q) * T)
    k = log_forward_moneyness(forward, S, T, r, q)
    assert k == pytest.approx(0.0, abs=1e-12)


def test_log_forward_moneyness_sign() -> None:
    S, T, r, q = 100.0, 1.0, 0.05, 0.0
    forward = S * np.exp((r - q) * T)
    assert log_forward_moneyness(forward * 1.1, S, T, r, q) > 0
    assert log_forward_moneyness(forward * 0.9, S, T, r, q) < 0


def test_surface_exact_node_returns_that_iv() -> None:
    T = np.array([0.5, 0.5, 0.5])
    k = np.array([-0.1, 0.0, 0.1])
    iv = np.array([0.25, 0.20, 0.22])
    surface = VolSurface(T, k, iv)
    result = surface.query(0.5, 0.0)
    assert result.iv == pytest.approx(0.20)
    assert not result.extrapolated


def test_surface_interpolates_within_smile() -> None:
    T = np.array([0.5, 0.5])
    k = np.array([-0.1, 0.1])
    iv = np.array([0.24, 0.20])
    surface = VolSurface(T, k, iv)
    result = surface.query(0.5, 0.0)
    assert 0.20 < result.iv < 0.24
    assert not result.extrapolated_in_moneyness


def test_surface_flags_extrapolation_in_moneyness() -> None:
    T = np.array([0.5, 0.5])
    k = np.array([-0.1, 0.1])
    iv = np.array([0.24, 0.20])
    surface = VolSurface(T, k, iv)
    result = surface.query(0.5, 5.0)  # way outside observed strikes
    assert result.extrapolated_in_moneyness
    assert result.extrapolated


def test_surface_flags_extrapolation_in_maturity() -> None:
    T = np.array([0.25, 0.25, 1.0, 1.0])
    k = np.array([-0.1, 0.1, -0.1, 0.1])
    iv = np.array([0.22, 0.20, 0.24, 0.22])
    surface = VolSurface(T, k, iv)
    result = surface.query(5.0, 0.0)  # far beyond observed maturities
    assert result.extrapolated_in_maturity


def test_surface_interpolates_across_maturities_via_total_variance() -> None:
    T = np.array([0.25, 0.25, 1.0, 1.0])
    k = np.array([0.0, 0.0, 0.0, 0.0])
    iv = np.array([0.20, 0.20, 0.30, 0.30])
    surface = VolSurface(T, k, iv)
    result = surface.query(0.5, 0.0)
    assert not result.extrapolated_in_maturity
    # total variance interpolation is monotonic in T for monotonic iv nodes
    assert 0.20 < result.iv < 0.30


def test_surface_rejects_non_positive_T() -> None:
    surface = VolSurface(np.array([0.5]), np.array([0.0]), np.array([0.2]))
    with pytest.raises(ValueError):
        surface.query(0.0, 0.0)


def test_surface_requires_matching_lengths() -> None:
    with pytest.raises(ValueError):
        VolSurface(np.array([0.5, 1.0]), np.array([0.0]), np.array([0.2]))


def test_build_surface_from_synthetic_chain() -> None:
    raw = synthetic_chain(seed=11)
    cleaned, _ = clean_chain(raw)
    surface = build_surface_from_chain(cleaned)
    assert len(surface.expiries) > 0
    result = surface.query(float(surface.expiries[0]), 0.0)
    assert result.iv > 0


def test_check_surface_sanity_flags_duplicates() -> None:
    raw = synthetic_chain(seed=12)
    dup = raw.iloc[[0, 0]].reset_index(drop=True)
    report = check_surface_sanity(dup)
    assert report.n_duplicate_contracts == 2


def test_check_surface_sanity_flags_extreme_spread() -> None:
    raw = synthetic_chain(seed=13)
    raw.loc[0, "bid"] = 0.01
    raw.loc[0, "ask"] = 10.0
    raw.loc[0, "mid"] = (raw.loc[0, "bid"] + raw.loc[0, "ask"]) / 2
    report = check_surface_sanity(raw)
    assert report.n_extreme_spread >= 1
