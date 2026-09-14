"""Portfolio aggregation: market value and Greeks across mixed positions.

Portfolio-level sign convention follows the position-level one: aggregate
Delta is the total first-order dollar-equivalent sensitivity to a $1 move
in each position's own underlying (summed across possibly-different
underlyings — this package does not net Greeks across different
underlyings into a single "market delta" unless the caller explicitly
means them to be the same name). Gamma/Vega/Theta/Rho follow the unit
conventions documented in :mod:`options_risk.pricing.greeks`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from options_risk.portfolio.positions import CashPosition, EquityPosition, OptionPosition
from options_risk.pricing.greeks import Greeks

AnyPosition = EquityPosition | OptionPosition | CashPosition


@dataclass(frozen=True)
class PortfolioGreeks:
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float


@dataclass
class Portfolio:
    positions: list[AnyPosition] = field(default_factory=list)

    def add(self, position: AnyPosition) -> None:
        self.positions.append(position)

    def market_value(self) -> float:
        return sum(p.market_value() for p in self.positions)

    def greeks(self) -> PortfolioGreeks:
        totals = {"delta": 0.0, "gamma": 0.0, "vega": 0.0, "theta": 0.0, "rho": 0.0}
        for p in self.positions:
            g: Greeks = p.position_greeks()
            totals["delta"] += g.delta
            totals["gamma"] += g.gamma
            totals["vega"] += g.vega
            totals["theta"] += g.theta
            totals["rho"] += g.rho
        return PortfolioGreeks(**totals)

    def equities(self) -> list[EquityPosition]:
        return [p for p in self.positions if isinstance(p, EquityPosition)]

    def options(self) -> list[OptionPosition]:
        return [p for p in self.positions if isinstance(p, OptionPosition)]

    def cash_positions(self) -> list[CashPosition]:
        return [p for p in self.positions if isinstance(p, CashPosition)]

    def total_cash(self) -> float:
        return sum(p.amount for p in self.cash_positions())
