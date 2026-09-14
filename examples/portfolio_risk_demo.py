from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from options_risk import (
    CashPosition,
    EquityPosition,
    EuropeanOptionPosition,
    MarketState,
    Portfolio,
)
from options_risk.risk import (
    StressScenario,
    delta_normal_var,
    historical_var_es,
    monte_carlo_var_es,
    portfolio_historical_pnl,
    stress_test,
)


def build_summary() -> dict[str, float | dict[str, float] | list[dict[str, float | str]] | str]:
    market = MarketState(spot=100.0, rate=0.02, dividend_yield=0.01, volatility=0.2)
    portfolio = Portfolio(
        positions=(
            CashPosition(25.0),
            EquityPosition(3.0),
            EuropeanOptionPosition("call", 100.0, 1.0, 2.0),
            EuropeanOptionPosition("put", 95.0, 0.5, -1.0),
        )
    )
    greeks_map = portfolio.greeks(market)
    covariance = np.array(
        [
            [0.04 / 252.0, 0.0, 0.0],
            [0.0, 0.02**2 / 252.0, 0.0],
            [0.0, 0.0, 0.005**2 / 252.0],
        ]
    )
    scenarios = pd.DataFrame(
        {
            "spot_return": [np.log(0.95), np.log(1.02), np.log(0.9), np.log(1.05)],
            "vol_shift": [0.01, -0.005, 0.03, -0.01],
            "rate_shift": [0.0, 0.001, -0.001, 0.0],
        }
    )
    pnl = portfolio_historical_pnl(portfolio, market, scenarios)
    hist = historical_var_es(pnl, 0.95)
    dn = delta_normal_var(portfolio, market, covariance, 0.95)
    mc = monte_carlo_var_es(
        portfolio, market, covariance, confidence_level=0.95, n_sims=5000, seed=24
    )
    stresses = stress_test(
        portfolio,
        market,
        [
            StressScenario(
                "spot_down_10pct_vol_up_3pts", spot_return=float(np.log(0.9)), vol_shift=0.03
            ),
            StressScenario(
                "spot_up_5pct_vol_down_1pt", spot_return=float(np.log(1.05)), vol_shift=-0.01
            ),
        ],
    )
    return {
        "note": "Synthetic deterministic example only",
        "portfolio_value": round(portfolio.value(market), 6),
        "delta": round(greeks_map["delta"], 6),
        "gamma": round(greeks_map["gamma"], 6),
        "vega": round(greeks_map["vega"], 6),
        "theta": round(greeks_map["theta"], 6),
        "rho": round(greeks_map["rho"], 6),
        "historical_var_95": round(hist.var, 6),
        "historical_es_95": round(hist.expected_shortfall, 6),
        "delta_normal_var_95": round(dn.var, 6),
        "delta_normal_es_95": round(dn.expected_shortfall, 6),
        "monte_carlo_var_95": round(mc.var, 6),
        "monte_carlo_es_95": round(mc.expected_shortfall, 6),
        "stress_scenarios": stresses.round(6).to_dict(orient="records"),
    }


def main() -> None:
    summary = build_summary()
    output_path = Path("research/results/portfolio_risk_demo.json")
    output_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
