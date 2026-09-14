"""Option-chain cleaning tests (P1 item 8), all against synthetic fixtures — no network."""

from __future__ import annotations

from options_risk.data.chain import CHAIN_COLUMNS, clean_chain, synthetic_chain


def test_synthetic_chain_has_documented_schema() -> None:
    df = synthetic_chain(seed=1)
    assert list(df.columns) == CHAIN_COLUMNS
    assert len(df) > 0


def test_clean_chain_drops_all_bad_rows() -> None:
    raw = synthetic_chain(seed=1, include_bad_rows=True)
    cleaned, report = clean_chain(raw)

    assert report.n_dropped_crossed >= 1
    assert report.n_dropped_negative_bid >= 1
    assert report.n_dropped_expired >= 1
    assert report.n_output == len(cleaned)
    assert report.n_output < report.n_input


def test_clean_chain_recomputes_mid_consistently() -> None:
    raw = synthetic_chain(seed=2)
    cleaned, _ = clean_chain(raw)
    assert (cleaned["mid"] == (cleaned["bid"] + cleaned["ask"]) / 2.0).all()


def test_clean_chain_no_crossed_quotes_remain() -> None:
    raw = synthetic_chain(seed=3, include_bad_rows=True)
    cleaned, _ = clean_chain(raw)
    assert (cleaned["ask"] >= cleaned["bid"]).all()


def test_clean_chain_no_negative_bids_remain() -> None:
    raw = synthetic_chain(seed=4, include_bad_rows=True)
    cleaned, _ = clean_chain(raw)
    assert (cleaned["bid"] >= 0).all()


def test_clean_chain_all_rows_have_positive_time_to_expiry() -> None:
    raw = synthetic_chain(seed=5, include_bad_rows=True)
    cleaned, _ = clean_chain(raw)
    assert (cleaned["T"] > 0).all()


def test_clean_chain_flags_zero_bid_without_dropping() -> None:
    raw = synthetic_chain(seed=6)
    raw.loc[0, "bid"] = 0.0
    cleaned, report = clean_chain(raw)
    assert report.n_flagged_zero_bid >= 1
    assert "zero_bid_flag" in cleaned.columns
    assert cleaned["zero_bid_flag"].any()


def test_clean_chain_enforces_arbitrage_bounds() -> None:
    raw = synthetic_chain(seed=7)
    # Force one row's mid to violate the call upper bound (price above spot).
    call_mask = raw["option_type"] == "call"
    idx = raw[call_mask].index[0]
    raw.loc[idx, "bid"] = raw.loc[idx, "spot"] * 2
    raw.loc[idx, "ask"] = raw.loc[idx, "spot"] * 2.1
    cleaned, report = clean_chain(raw)
    assert report.n_dropped_arbitrage_violation >= 1
    assert idx not in cleaned.index or len(cleaned) < len(raw)


def test_clean_chain_deterministic_given_same_seed() -> None:
    raw1 = synthetic_chain(seed=42)
    raw2 = synthetic_chain(seed=42)
    cleaned1, _ = clean_chain(raw1)
    cleaned2, _ = clean_chain(raw2)
    assert cleaned1.equals(cleaned2)
