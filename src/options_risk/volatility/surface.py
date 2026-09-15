"""Volatility smile, term-structure, and surface utilities.

Moneyness convention: **log-forward-moneyness**, ``k = log(K / F)`` with
forward ``F = S * exp((r - q) * T)``. This is the standard convention
because it is symmetric around ATM (k=0) regardless of interest
rates/dividends, unlike ``K/S``.

Interpolation is deliberately simple (linear), not a parametric vol model
(no SVI, no local vol — explicitly out of scope per the project brief).
Two interpolation choices are made and documented rather than left
implicit:

* **Within an expiry slice (the smile)**: linear interpolation in ``k``.
* **Across expiries (the term structure)**: linear interpolation in total
  variance ``w = iv^2 * T`` as a function of ``T``, then converted back to
  vol via ``iv = sqrt(w / T)``. Interpolating total variance rather than
  vol directly is the standard convention because it is what enters the
  Black-Scholes formula linearly and avoids obviously wrong behavior (like
  variance going negative between two positive-variance nodes).

Every query result carries an explicit ``extrapolated`` flag: a query
outside the observed ``(T, k)`` range is never silently treated the same as
one inside it — this module refuses to claim it "knows" the vol in a region
it has no data for; it will still produce a number (flat extrapolation at
the nearest boundary) but the caller is told so.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

import numpy as np
import pandas as pd


def log_forward_moneyness(
    K: float | np.ndarray, S: float, T: float, r: float, q: float = 0.0
) -> np.ndarray:
    """k = log(K / F), F = S * exp((r - q) * T). Vectorized over K."""
    forward = S * np.exp((r - q) * T)
    return np.log(np.asarray(K) / forward)


@dataclass(frozen=True)
class SurfaceQueryResult:
    iv: float
    extrapolated_in_moneyness: bool
    extrapolated_in_maturity: bool

    @property
    def extrapolated(self) -> bool:
        return self.extrapolated_in_moneyness or self.extrapolated_in_maturity


class VolSurface:
    """A simple, linearly-interpolated implied-volatility surface.

    Built from a "quote table" of already-solved IVs: one row per
    ``(T, log_moneyness, iv)`` observation. Use
    :func:`build_surface_from_chain` to build one directly from a cleaned
    option chain (which solves IV internally).
    """

    def __init__(self, T: np.ndarray, k: np.ndarray, iv: np.ndarray) -> None:
        if not (len(T) == len(k) == len(iv)):
            raise ValueError("T, k, iv must have the same length")
        if len(T) == 0:
            raise ValueError("VolSurface requires at least one observation")
        df = pd.DataFrame({"T": T, "k": k, "iv": iv}).sort_values(["T", "k"])
        self._by_expiry: dict[float, pd.DataFrame] = {
            float(cast(Any, t)): grp.sort_values("k").reset_index(drop=True)
            for t, grp in df.groupby("T")
        }
        self._expiries = np.array(sorted(self._by_expiry.keys()))

    @property
    def expiries(self) -> np.ndarray:
        return self._expiries

    def _smile_iv(self, T_node: float, k_query: float) -> tuple[float, bool]:
        smile = self._by_expiry[T_node]
        k_arr = smile["k"].to_numpy()
        iv_arr = smile["iv"].to_numpy()
        extrapolated = bool(k_query < k_arr.min() or k_query > k_arr.max())
        iv = float(np.interp(k_query, k_arr, iv_arr))  # np.interp flat-extrapolates at the ends
        return iv, extrapolated

    def query(self, T: float, k: float) -> SurfaceQueryResult:
        """Interpolate implied vol at maturity ``T`` (years) and log-moneyness ``k``."""
        if T <= 0:
            raise ValueError(f"T must be > 0, got {T}")

        extrap_T = bool(T < self._expiries.min() or T > self._expiries.max())

        if T in self._by_expiry:
            iv, extrap_k = self._smile_iv(T, k)
            return SurfaceQueryResult(iv, extrap_k, False)

        lower_candidates = self._expiries[self._expiries <= T]
        upper_candidates = self._expiries[self._expiries >= T]
        T_lo = lower_candidates.max() if len(lower_candidates) else self._expiries.min()
        T_hi = upper_candidates.min() if len(upper_candidates) else self._expiries.max()

        if T_lo == T_hi:
            iv, extrap_k = self._smile_iv(T_lo, k)
            return SurfaceQueryResult(iv, extrap_k, extrap_T)

        iv_lo, extrap_k_lo = self._smile_iv(T_lo, k)
        iv_hi, extrap_k_hi = self._smile_iv(T_hi, k)
        w_lo, w_hi = iv_lo**2 * T_lo, iv_hi**2 * T_hi
        weight_hi = (T - T_lo) / (T_hi - T_lo)
        w = w_lo + weight_hi * (w_hi - w_lo)
        iv = float(np.sqrt(max(w, 0.0) / T))
        return SurfaceQueryResult(iv, extrap_k_lo or extrap_k_hi, extrap_T)


@dataclass(frozen=True)
class SurfaceSanityReport:
    n_rows: int
    n_duplicate_contracts: int
    n_negative_iv: int
    n_extreme_spread: int
    flagged_indices: list[int]


def check_surface_sanity(
    df: pd.DataFrame, *, extreme_spread_frac: float = 0.5
) -> SurfaceSanityReport:
    """Arbitrage-aware sanity checks on a quote table before building a surface.

    This does **not** certify the surface is arbitrage-free (no calendar-
    spread or butterfly-arbitrage enforcement is implemented) — it only
    flags the cheap, unambiguous problems: duplicate contracts, a negative
    solved IV (should be impossible given :func:`solve_iv`'s bounds check,
    but checked defensively), and quotes with an extreme relative spread
    (``(ask-bid)/mid`` above ``extreme_spread_frac``) that make the mid an
    unreliable estimate of fair value.
    """
    flagged: set[int] = set()

    dup_cols = [c for c in ("strike", "expiration", "option_type") if c in df.columns]
    n_duplicates = 0
    if dup_cols:
        dup_mask = df.duplicated(subset=dup_cols, keep=False)
        n_duplicates = int(dup_mask.sum())
        flagged.update(df.index[dup_mask].tolist())

    n_negative_iv = 0
    if "iv" in df.columns:
        neg_mask = df["iv"] < 0
        n_negative_iv = int(neg_mask.sum())
        flagged.update(df.index[neg_mask].tolist())

    n_extreme_spread = 0
    if {"bid", "ask", "mid"}.issubset(df.columns):
        with np.errstate(divide="ignore", invalid="ignore"):
            rel_spread = (df["ask"] - df["bid"]) / df["mid"].replace(0, np.nan)
        extreme_mask = rel_spread > extreme_spread_frac
        n_extreme_spread = int(extreme_mask.fillna(False).sum())
        flagged.update(df.index[extreme_mask.fillna(False)].tolist())

    return SurfaceSanityReport(
        n_rows=len(df),
        n_duplicate_contracts=n_duplicates,
        n_negative_iv=n_negative_iv,
        n_extreme_spread=n_extreme_spread,
        flagged_indices=sorted(flagged),
    )


def build_surface_from_chain(df: pd.DataFrame) -> VolSurface:
    """Solve IV for each row of a cleaned chain and build a :class:`VolSurface`.

    Rows for which :func:`solve_iv` fails to converge (see
    :mod:`options_risk.pricing.implied_vol`) are dropped from the surface
    rather than included with a placeholder value.
    """
    from options_risk.pricing.black_scholes import OptionType
    from options_risk.pricing.implied_vol import solve_iv

    Ts, ks, ivs = [], [], []
    for row in df.itertuples():
        # itertuples() loses per-column dtypes (each attribute types as a
        # broad Union at the type-checker level), so cast explicitly even
        # though the cleaned chain guarantees these are numeric/str at runtime.
        mid = float(cast(Any, row.mid))
        spot = float(cast(Any, row.spot))
        strike = float(cast(Any, row.strike))
        T = float(cast(Any, row.T))
        r = float(cast(Any, row.r))
        q = float(cast(Any, row.q))
        option_type = cast(OptionType, row.option_type)
        result = solve_iv(mid, spot, strike, T, r, option_type, q)
        if not result.converged or result.iv is None:
            continue
        k = float(log_forward_moneyness(strike, spot, T, r, q))
        Ts.append(T)
        ks.append(k)
        ivs.append(result.iv)

    if not Ts:
        raise ValueError("no rows produced a convergent implied volatility")

    return VolSurface(np.array(Ts), np.array(ks), np.array(ivs))
