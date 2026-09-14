"""Build a volatility surface from a synthetic (fixture) option chain.

No network access: uses options_risk.data.chain.synthetic_chain, which is
clearly synthetic data, not a real market snapshot.

Run: python examples/04_vol_smile_from_fixture.py
"""

from __future__ import annotations

import json
from pathlib import Path

from options_risk.data.chain import clean_chain, synthetic_chain
from options_risk.volatility.surface import build_surface_from_chain, check_surface_sanity

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results" / "volatility"


def main() -> None:
    raw = synthetic_chain(seed=7, include_bad_rows=True)
    cleaned, cleaning_report = clean_chain(raw)
    sanity_report = check_surface_sanity(cleaned)
    surface = build_surface_from_chain(cleaned)

    smile_rows = []
    T0 = float(surface.expiries[0])
    for k in (-0.15, -0.05, 0.0, 0.05, 0.15):
        q = surface.query(T0, k)
        smile_rows.append(
            {"k": k, "iv": q.iv, "extrapolated_in_moneyness": q.extrapolated_in_moneyness}
        )

    result = {
        "data_source": "SYNTHETIC fixture (options_risk.data.chain.synthetic_chain, seed=7) "
        "-- not real market data",
        "cleaning_report": {
            "n_input": cleaning_report.n_input,
            "n_output": cleaning_report.n_output,
            "dropped_reasons": cleaning_report.dropped_reasons,
        },
        "sanity_report": {
            "n_rows": sanity_report.n_rows,
            "n_duplicate_contracts": sanity_report.n_duplicate_contracts,
            "n_negative_iv": sanity_report.n_negative_iv,
            "n_extreme_spread": sanity_report.n_extreme_spread,
        },
        "expiries_years": surface.expiries.tolist(),
        "smile_at_shortest_expiry": smile_rows,
    }
    print(json.dumps(result, indent=2))

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "vol_smile_from_synthetic_chain.json").write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
