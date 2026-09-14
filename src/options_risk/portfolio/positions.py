"""Position-level representations: equities, European options, and cash.

Sign convention: ``quantity`` is signed — positive is long, negative is
short — for both equities and options, consistent with the hedging
simulator's convention.

An option position's ``quantity`` is the number of **contracts**; each
contract controls ``multiplier`` shares of the underlying (the US-equity
standard is 100 shares/contract, used here as the default). All Greeks and
market values below are contract-and-multiplier-scaled totals, i.e. the
actual dollar/share exposure of the position — not "per contract" or
"per share" unit Greeks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from options_risk.pricing.black_scholes import OptionType, bsm_price
from options_risk.pricing.greeks import Greeks, greeks


class Position(Protocol):
    def market_value(self) -> float: ...
    def position_greeks(self) -> Greeks: ...


@dataclass(frozen=True)
class EquityPosition:
    symbol: str
    quantity: float  # shares, positive = long
    price: float

    def market_value(self) -> float:
        return self.quantity * self.price

    def position_greeks(self) -> Greeks:
        # A share of stock has delta 1 (w.r.t. its own price) and no convexity/time/rate risk.
        return Greeks(delta=self.quantity, gamma=0.0, vega=0.0, theta=0.0, rho=0.0)


@dataclass(frozen=True)
class OptionPosition:
    symbol: str  # underlying ticker
    option_type: OptionType
    quantity: float  # contracts, positive = long
    strike: float
    T: float
    S: float  # current underlying spot, for mark-to-market
    r: float
    sigma: float
    q: float = 0.0
    multiplier: float = 100.0

    def _scale(self) -> float:
        return self.quantity * self.multiplier

    def unit_price(self) -> float:
        return bsm_price(self.S, self.strike, self.T, self.r, self.sigma, self.option_type, self.q)

    def market_value(self) -> float:
        return self._scale() * self.unit_price()

    def unit_greeks(self) -> Greeks:
        return greeks(self.S, self.strike, self.T, self.r, self.sigma, self.option_type, self.q)

    def position_greeks(self) -> Greeks:
        g = self.unit_greeks()
        scale = self._scale()
        return Greeks(
            delta=scale * g.delta,
            gamma=scale * g.gamma,
            vega=scale * g.vega,
            theta=scale * g.theta,
            rho=scale * g.rho,
        )


@dataclass(frozen=True)
class CashPosition:
    amount: float

    def market_value(self) -> float:
        return self.amount

    def position_greeks(self) -> Greeks:
        return Greeks(delta=0.0, gamma=0.0, vega=0.0, theta=0.0, rho=0.0)
