"""Option-chain schema and cleaning rules.

Schema (one row per contract quote):

``timestamp, underlying, spot, expiration, strike, option_type, bid, ask,
mid, last, volume, open_interest, r, q, T, iv``

* ``timestamp``: observation time (tz-aware `pandas.Timestamp`).
* ``expiration``: contract expiration time (tz-aware `pandas.Timestamp`).
* ``T``: year-fraction to expiration, computed as
  ``(expiration - timestamp) / 365.25 days`` — a data-layer convention,
  independent of the day-count choice a desk might use for discounting.
* ``mid``: recomputed by this module as ``(bid + ask) / 2`` whenever both
  are present and ``ask >= bid``; never taken from an upstream ``mid``
  field, so the convention is always consistent across sources.
* ``iv``: left as NaN by this module — filled in downstream by
  :mod:`options_risk.pricing.implied_vol` after cleaning, never assumed to
  arrive pre-computed from a data source.

This module intentionally never calls out to the network: real market data
loaders (e.g. a `yfinance`-backed one, in the optional ``data`` extra) live
elsewhere and are not exercised in CI. Tests in this repository use only the
synthetic fixture chains built by :func:`synthetic_chain`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

CHAIN_COLUMNS = [
    "timestamp",
    "underlying",
    "spot",
    "expiration",
    "strike",
    "option_type",
    "bid",
    "ask",
    "mid",
    "last",
    "volume",
    "open_interest",
    "r",
    "q",
    "T",
    "iv",
]


@dataclass(frozen=True)
class CleaningReport:
    """Row-level accounting of what the cleaner did, for auditability."""

    n_input: int
    n_output: int
    n_dropped_expired: int = 0
    n_dropped_negative_bid: int = 0
    n_dropped_crossed: int = 0  # bid > ask
    n_dropped_nonpositive_ask: int = 0
    n_dropped_arbitrage_violation: int = 0
    n_flagged_zero_bid: int = 0
    dropped_reasons: dict[str, int] = field(default_factory=dict)


def _year_fraction(timestamp: pd.Series, expiration: pd.Series) -> pd.Series:
    return (expiration - timestamp).dt.total_seconds() / (365.25 * 24 * 3600)


def clean_chain(raw: pd.DataFrame) -> tuple[pd.DataFrame, CleaningReport]:
    """Apply explicit, documented cleaning rules to a raw option-chain frame.

    Rules applied, in order (a row failing any rule is dropped, not
    silently kept):

    1. ``expiration > timestamp`` (T > 0) — expired/same-instant contracts
       are dropped; this library only prices/solves-IV for T > 0 contracts.
    2. ``bid >= 0`` — a negative bid is a data error, dropped.
    3. ``ask >= bid`` — a crossed quote is a data error (or a stale/illiquid
       snapshot), dropped rather than silently reordered.
    4. ``ask > 0`` — a zero/negative ask is not a tradeable quote, dropped.
    5. Static no-arbitrage bounds on the recomputed mid — a mid outside
       ``[max(S e^{-qT} - K e^{-rT}, 0), S e^{-qT}]`` (call) or the put
       equivalent is dropped; solving IV on such a row is unsolvable anyway
       (see :mod:`options_risk.pricing.implied_vol`).

    Zero-bid quotes are **not** dropped, only flagged (a zero bid is common
    for deep OTM/illiquid contracts and is not itself an arbitrage
    violation) — the caller should treat their IV/pricing as low-confidence
    since the true clearing price could be anywhere in ``[0, ask]``.
    Stale quotes (based on ``timestamp`` age or zero volume/open interest)
    are the caller's responsibility to filter by ``timestamp``/``volume``
    directly; this module does not assume a "freshness" threshold since
    that depends on the trading session and asset.
    """
    from options_risk.pricing.black_scholes import is_within_arbitrage_bounds

    n_input = len(raw)
    df = raw.copy()

    df["T"] = _year_fraction(df["timestamp"], df["expiration"])
    not_expired = df["T"] > 0
    n_dropped_expired = int((~not_expired).sum())
    df = df[not_expired]

    non_negative_bid = df["bid"] >= 0
    n_dropped_negative_bid = int((~non_negative_bid).sum())
    df = df[non_negative_bid]

    positive_ask = df["ask"] > 0
    n_dropped_nonpositive_ask = int((~positive_ask).sum())
    df = df[positive_ask]

    not_crossed = df["ask"] >= df["bid"]
    n_dropped_crossed = int((~not_crossed).sum())
    df = df[not_crossed]

    df["mid"] = (df["bid"] + df["ask"]) / 2.0
    n_flagged_zero_bid = int((df["bid"] == 0).sum())

    if len(df) > 0:
        within_bounds = df.apply(
            lambda row: is_within_arbitrage_bounds(
                row["mid"],
                row["spot"],
                row["strike"],
                row["T"],
                row["r"],
                row["option_type"],
                row["q"],
            ),
            axis=1,
        )
        n_dropped_arbitrage_violation = int((~within_bounds).sum())
        df = df[within_bounds]
    else:
        n_dropped_arbitrage_violation = 0

    df["zero_bid_flag"] = df["bid"] == 0
    df["iv"] = np.nan

    report = CleaningReport(
        n_input=n_input,
        n_output=len(df),
        n_dropped_expired=n_dropped_expired,
        n_dropped_negative_bid=n_dropped_negative_bid,
        n_dropped_crossed=n_dropped_crossed,
        n_dropped_nonpositive_ask=n_dropped_nonpositive_ask,
        n_dropped_arbitrage_violation=n_dropped_arbitrage_violation,
        n_flagged_zero_bid=n_flagged_zero_bid,
        dropped_reasons={
            "expired": n_dropped_expired,
            "negative_bid": n_dropped_negative_bid,
            "crossed": n_dropped_crossed,
            "nonpositive_ask": n_dropped_nonpositive_ask,
            "arbitrage_violation": n_dropped_arbitrage_violation,
        },
    )
    return df.reset_index(drop=True), report


def synthetic_chain(
    *,
    as_of: pd.Timestamp | None = None,
    underlying: str = "SYN",
    spot: float = 100.0,
    r: float = 0.03,
    q: float = 0.0,
    expirations_days: tuple[int, ...] = (7, 30, 90, 180),
    strikes: tuple[float, ...] = (80, 90, 95, 100, 105, 110, 120),
    true_vol_by_expiry: dict[int, float] | None = None,
    spread_frac: float = 0.02,
    seed: int = 0,
    include_bad_rows: bool = False,
) -> pd.DataFrame:
    """Build a deterministic, seeded synthetic option chain for tests/examples.

    Prices are generated from Black-Scholes at a specified "true" vol per
    expiry (a simple smile: shorter-dated / further-OTM strikes get a vol
    bump), then a bid/ask spread is applied around that fair value. This is
    clearly synthetic data for testing purposes, not a real market snapshot
    — every example/report that consumes it says so explicitly.

    When ``include_bad_rows=True``, a handful of deliberately malformed rows
    (crossed quote, negative bid, expired contract) are appended so
    :func:`clean_chain` has something real to remove, exercised in tests.
    """
    from options_risk.pricing.black_scholes import bsm_price

    if as_of is None:
        as_of = pd.Timestamp("2026-01-02T14:30:00Z")
    rng = np.random.default_rng(seed)

    if true_vol_by_expiry is None:
        true_vol_by_expiry = {d: 0.18 + 0.05 * (30 / max(d, 1)) ** 0.5 for d in expirations_days}

    rows = []
    for days in expirations_days:
        expiration = as_of + pd.Timedelta(days=days)
        T = days / 365.25
        base_vol = true_vol_by_expiry[days]
        for K in strikes:
            moneyness = np.log(K / spot)
            smile_vol = base_vol + 0.15 * moneyness**2  # simple symmetric smile bump
            for option_type in ("call", "put"):
                fair = bsm_price(spot, K, T, r, smile_vol, option_type, q)
                spread = max(fair * spread_frac, 0.01)
                noise = rng.normal(0, spread * 0.1)
                mid = max(fair + noise, 0.0)
                bid = max(mid - spread / 2, 0.0)
                ask = mid + spread / 2
                rows.append(
                    {
                        "timestamp": as_of,
                        "underlying": underlying,
                        "spot": spot,
                        "expiration": expiration,
                        "strike": float(K),
                        "option_type": option_type,
                        "bid": round(bid, 4),
                        "ask": round(ask, 4),
                        "last": round(mid, 4),
                        "volume": int(rng.integers(0, 500)),
                        "open_interest": int(rng.integers(0, 5000)),
                        "r": r,
                        "q": q,
                    }
                )

    if include_bad_rows:
        rows.append(
            {  # crossed quote
                "timestamp": as_of,
                "underlying": underlying,
                "spot": spot,
                "expiration": as_of + pd.Timedelta(days=30),
                "strike": 100.0,
                "option_type": "call",
                "bid": 10.0,
                "ask": 5.0,
                "last": 7.0,
                "volume": 1,
                "open_interest": 1,
                "r": r,
                "q": q,
            }
        )
        rows.append(
            {  # negative bid
                "timestamp": as_of,
                "underlying": underlying,
                "spot": spot,
                "expiration": as_of + pd.Timedelta(days=30),
                "strike": 100.0,
                "option_type": "put",
                "bid": -1.0,
                "ask": 5.0,
                "last": 2.0,
                "volume": 1,
                "open_interest": 1,
                "r": r,
                "q": q,
            }
        )
        rows.append(
            {  # already expired
                "timestamp": as_of,
                "underlying": underlying,
                "spot": spot,
                "expiration": as_of - pd.Timedelta(days=1),
                "strike": 100.0,
                "option_type": "call",
                "bid": 1.0,
                "ask": 2.0,
                "last": 1.5,
                "volume": 1,
                "open_interest": 1,
                "r": r,
                "q": q,
            }
        )

    df = pd.DataFrame(rows)
    df["mid"] = (df["bid"] + df["ask"]) / 2.0
    df["T"] = np.nan
    df["iv"] = np.nan
    return df[CHAIN_COLUMNS]
