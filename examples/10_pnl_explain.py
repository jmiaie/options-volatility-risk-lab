"""Compare Greek-based (Taylor) P&L explain against full revaluation across shock sizes.

Run: python examples/10_pnl_explain.py
"""

from __future__ import annotations

import json
from pathlib import Path

from options_risk.attribution.pnl_explain import explain_pnl
from options_risk.portfolio import OptionPosition, Portfolio

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results" / "attribution"


def _single_underlying_portfolio() -> Portfolio:
    # explain_pnl requires a single shared base spot across all positions.
    portfolio = Portfolio()
    portfolio.add(OptionPosition("ABC", "call", 10, 100.0, 0.5, 100.0, 0.03, 0.22, multiplier=100))
    portfolio.add(OptionPosition("ABC", "put", -5, 95.0, 0.5, 100.0, 0.03, 0.22, multiplier=100))
    return portfolio


def main() -> None:
    portfolio = _single_underlying_portfolio()

    shocks = [0.5, 1.0, 2.0, 5.0, 10.0, 20.0]
    rows = []
    for dS in shocks:
        a = explain_pnl(portfolio, dS=dS)
        rows.append(
            {
                "dS": dS,
                "delta_pnl": a.delta_pnl,
                "gamma_pnl": a.gamma_pnl,
                "explained_pnl": a.explained_pnl,
                "actual_pnl_full_reval": a.actual_pnl,
                "residual": a.residual,
                "residual_pct_of_actual": a.residual_pct_of_actual,
            }
        )

    result = {
        "portfolio_market_value": portfolio.market_value(),
        "shock_table": rows,
        "note": "residual (unexplained P&L) should grow with |dS| -- the Taylor approximation "
        "is never claimed to equal full-revaluation P&L. See docs/model-risk.md #6.",
    }
    print(json.dumps(result, indent=2))

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "pnl_explain_vs_shock_size.json").write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
