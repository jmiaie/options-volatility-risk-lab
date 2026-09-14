from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TypeAlias

import pandas as pd

from .bsm import OptionType, black_scholes_price, greeks


@dataclass(frozen=True)
class MarketState:
    spot: float
    rate: float
    dividend_yield: float
    volatility: float


@dataclass(frozen=True)
class CashPosition:
    amount: float

    def value(
        self, market: MarketState, *, rate_shift: float = 0.0, time_shift: float = 0.0
    ) -> float:
        effective_rate = market.rate + rate_shift
        if time_shift <= 0.0:
            return self.amount
        return self.amount * math.exp(effective_rate * time_shift)


@dataclass(frozen=True)
class EquityPosition:
    quantity: float

    def value(self, market: MarketState, *, spot: float | None = None) -> float:
        return self.quantity * (market.spot if spot is None else spot)


@dataclass(frozen=True)
class EuropeanOptionPosition:
    option_type: OptionType
    strike: float
    time_to_expiry: float
    quantity: float

    def value(
        self,
        market: MarketState,
        *,
        spot: float | None = None,
        volatility: float | None = None,
        rate: float | None = None,
        time_shift: float = 0.0,
    ) -> float:
        return self.quantity * black_scholes_price(
            self.option_type,
            market.spot if spot is None else spot,
            self.strike,
            max(self.time_to_expiry - time_shift, 0.0),
            market.volatility if volatility is None else volatility,
            market.rate if rate is None else rate,
            market.dividend_yield,
        )

    def greeks(self, market: MarketState) -> dict[str, float]:
        values = greeks(
            self.option_type,
            market.spot,
            self.strike,
            self.time_to_expiry,
            market.volatility,
            market.rate,
            market.dividend_yield,
        )
        return {
            "delta": self.quantity * values.delta,
            "gamma": self.quantity * values.gamma,
            "vega": self.quantity * values.vega,
            "theta": self.quantity * values.theta,
            "rho": self.quantity * values.rho,
        }


Position: TypeAlias = CashPosition | EquityPosition | EuropeanOptionPosition


@dataclass(frozen=True)
class Portfolio:
    positions: tuple[Position, ...]

    def value(
        self,
        market: MarketState,
        *,
        spot_shift: float = 0.0,
        vol_shift: float = 0.0,
        rate_shift: float = 0.0,
        time_shift: float = 0.0,
    ) -> float:
        shocked_spot = market.spot + spot_shift
        shocked_vol = max(market.volatility + vol_shift, 0.0)
        shocked_rate = market.rate + rate_shift
        total = 0.0
        for position in self.positions:
            if isinstance(position, CashPosition):
                total += position.value(market, rate_shift=rate_shift, time_shift=time_shift)
            elif isinstance(position, EquityPosition):
                total += position.value(market, spot=shocked_spot)
            else:
                total += position.value(
                    market,
                    spot=shocked_spot,
                    volatility=shocked_vol,
                    rate=shocked_rate,
                    time_shift=time_shift,
                )
        return total

    def greeks(self, market: MarketState) -> dict[str, float]:
        totals = {"delta": 0.0, "gamma": 0.0, "vega": 0.0, "theta": 0.0, "rho": 0.0}
        for position in self.positions:
            if isinstance(position, CashPosition):
                continue
            if isinstance(position, EquityPosition):
                totals["delta"] += position.quantity
                continue
            for name, value in position.greeks(market).items():
                totals[name] += value
        return totals

    def pnl_explain(
        self,
        market: MarketState,
        *,
        spot_shift: float = 0.0,
        vol_shift: float = 0.0,
        rate_shift: float = 0.0,
        time_shift: float = 0.0,
    ) -> dict[str, float]:
        base_value = self.value(market)
        shocked_value = self.value(
            market,
            spot_shift=spot_shift,
            vol_shift=vol_shift,
            rate_shift=rate_shift,
            time_shift=time_shift,
        )
        greeks_map = self.greeks(market)
        greek_pnl = (
            greeks_map["delta"] * spot_shift
            + 0.5 * greeks_map["gamma"] * spot_shift * spot_shift
            + greeks_map["vega"] * vol_shift
            + greeks_map["rho"] * rate_shift
            + greeks_map["theta"] * time_shift
        )
        repricing_pnl = shocked_value - base_value
        return {
            "base_value": base_value,
            "repriced_value": shocked_value,
            "repricing_pnl": repricing_pnl,
            "greek_pnl": greek_pnl,
            "residual": repricing_pnl - greek_pnl,
        }

    def spot_vol_matrix(
        self,
        market: MarketState,
        *,
        spot_shifts: list[float],
        vol_shifts: list[float],
    ) -> pd.DataFrame:
        rows: list[dict[str, float]] = []
        base = self.value(market)
        for spot_shift in spot_shifts:
            for vol_shift in vol_shifts:
                shocked = self.value(market, spot_shift=spot_shift, vol_shift=vol_shift)
                rows.append(
                    {
                        "spot_shift": spot_shift,
                        "vol_shift": vol_shift,
                        "value": shocked,
                        "pnl": shocked - base,
                    }
                )
        return pd.DataFrame(rows)
