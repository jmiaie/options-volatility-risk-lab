"""Build a small mixed equity/option/cash portfolio and aggregate its Greeks.

Run: python examples/06_build_portfolio.py
"""

from __future__ import annotations

import json
from pathlib import Path

from options_risk.portfolio import CashPosition, EquityPosition, OptionPosition, Portfolio

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results" / "attribution"


def build_example_portfolio() -> Portfolio:
    portfolio = Portfolio()
    portfolio.add(EquityPosition(symbol="ABC", quantity=500, price=100.0))
    portfolio.add(
        OptionPosition(
            symbol="ABC",
            option_type="put",
            quantity=-10,
            strike=95.0,
            T=0.25,
            S=100.0,
            r=0.03,
            sigma=0.22,
            q=0.0,
            multiplier=100,
        )
    )
    portfolio.add(
        OptionPosition(
            symbol="ABC",
            option_type="call",
            quantity=5,
            strike=110.0,
            T=0.5,
            S=100.0,
            r=0.03,
            sigma=0.24,
            q=0.0,
            multiplier=100,
        )
    )
    portfolio.add(CashPosition(amount=25_000.0))
    return portfolio


def main() -> None:
    portfolio = build_example_portfolio()
    g = portfolio.greeks()

    result = {
        "positions": [
            {"type": type(p).__name__, **{k: v for k, v in vars(p).items()}}
            for p in portfolio.positions
        ],
        "market_value": portfolio.market_value(),
        "portfolio_greeks": {
            "delta": g.delta,
            "gamma": g.gamma,
            "vega": g.vega,
            "theta": g.theta,
            "rho": g.rho,
        },
        "note": "Delta/Gamma/Vega/Theta/Rho are already scaled by quantity and contract "
        "multiplier (total dollar/share exposure), per options_risk.pricing.greeks conventions.",
    }
    print(json.dumps(result, indent=2))

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "example_portfolio.json").write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
