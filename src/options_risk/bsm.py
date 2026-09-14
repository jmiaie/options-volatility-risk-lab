from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from scipy.optimize import brentq
from scipy.stats import norm

OptionType = Literal["call", "put"]


@dataclass(frozen=True)
class OptionGreeks:
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float


@dataclass(frozen=True)
class ImpliedVolatilityResult:
    implied_volatility: float | None
    status: str
    message: str
    iterations: int = 0

    @property
    def success(self) -> bool:
        return self.implied_volatility is not None and self.status == "ok"


def _validate_option_type(option_type: OptionType) -> None:
    if option_type not in {"call", "put"}:
        raise ValueError("option_type must be 'call' or 'put'")


def _validate_inputs(
    spot: float,
    strike: float,
    time_to_expiry: float,
    volatility: float,
) -> None:
    values = {
        "spot": spot,
        "strike": strike,
        "time_to_expiry": time_to_expiry,
        "volatility": volatility,
    }
    for name, value in values.items():
        if not math.isfinite(value):
            raise ValueError(f"{name} must be finite")
    if spot <= 0.0:
        raise ValueError("spot must be positive")
    if strike <= 0.0:
        raise ValueError("strike must be positive")
    if time_to_expiry < 0.0:
        raise ValueError("time_to_expiry must be non-negative")
    if volatility < 0.0:
        raise ValueError("volatility must be non-negative")


def _discounted_forward(
    spot: float, rate: float, dividend_yield: float, time_to_expiry: float
) -> float:
    return spot * math.exp((rate - dividend_yield) * time_to_expiry)


def _intrinsic_from_forward(
    option_type: OptionType,
    spot: float,
    strike: float,
    rate: float,
    dividend_yield: float,
    time_to_expiry: float,
) -> float:
    discounted_spot = spot * math.exp(-dividend_yield * time_to_expiry)
    discounted_strike = strike * math.exp(-rate * time_to_expiry)
    if option_type == "call":
        return max(discounted_spot - discounted_strike, 0.0)
    return max(discounted_strike - discounted_spot, 0.0)


def price_bounds(
    option_type: OptionType,
    spot: float,
    strike: float,
    time_to_expiry: float,
    rate: float = 0.0,
    dividend_yield: float = 0.0,
) -> tuple[float, float]:
    _validate_option_type(option_type)
    _validate_inputs(spot, strike, time_to_expiry, 0.0)
    discounted_spot = spot * math.exp(-dividend_yield * time_to_expiry)
    discounted_strike = strike * math.exp(-rate * time_to_expiry)
    if option_type == "call":
        return max(discounted_spot - discounted_strike, 0.0), discounted_spot
    return max(discounted_strike - discounted_spot, 0.0), discounted_strike


def _d1_d2(
    spot: float,
    strike: float,
    time_to_expiry: float,
    rate: float,
    dividend_yield: float,
    volatility: float,
) -> tuple[float, float]:
    sqrt_t = math.sqrt(time_to_expiry)
    variance_term = volatility * sqrt_t
    d1 = (
        math.log(spot / strike)
        + (rate - dividend_yield + 0.5 * volatility * volatility) * time_to_expiry
    ) / variance_term
    d2 = d1 - variance_term
    return d1, d2


def black_scholes_price(
    option_type: OptionType,
    spot: float,
    strike: float,
    time_to_expiry: float,
    volatility: float,
    rate: float = 0.0,
    dividend_yield: float = 0.0,
) -> float:
    _validate_option_type(option_type)
    _validate_inputs(spot, strike, time_to_expiry, volatility)
    if time_to_expiry == 0.0:
        return max(spot - strike, 0.0) if option_type == "call" else max(strike - spot, 0.0)
    if volatility == 0.0:
        return _intrinsic_from_forward(
            option_type, spot, strike, rate, dividend_yield, time_to_expiry
        )

    discounted_spot = spot * math.exp(-dividend_yield * time_to_expiry)
    discounted_strike = strike * math.exp(-rate * time_to_expiry)
    d1, d2 = _d1_d2(spot, strike, time_to_expiry, rate, dividend_yield, volatility)
    if option_type == "call":
        return discounted_spot * float(norm.cdf(d1)) - discounted_strike * float(norm.cdf(d2))
    return discounted_strike * float(norm.cdf(-d2)) - discounted_spot * float(norm.cdf(-d1))


def greeks(
    option_type: OptionType,
    spot: float,
    strike: float,
    time_to_expiry: float,
    volatility: float,
    rate: float = 0.0,
    dividend_yield: float = 0.0,
) -> OptionGreeks:
    _validate_option_type(option_type)
    _validate_inputs(spot, strike, time_to_expiry, volatility)

    if time_to_expiry == 0.0:
        if option_type == "call":
            delta = 1.0 if spot > strike else 0.0 if spot < strike else 0.5
        else:
            delta = -1.0 if spot < strike else 0.0 if spot > strike else -0.5
        return OptionGreeks(delta=delta, gamma=0.0, vega=0.0, theta=0.0, rho=0.0)

    if volatility == 0.0:
        discounted_delta = math.exp(-dividend_yield * time_to_expiry)
        forward = _discounted_forward(spot, rate, dividend_yield, time_to_expiry)
        if option_type == "call":
            delta = (
                discounted_delta
                if forward > strike
                else 0.0
                if forward < strike
                else 0.5 * discounted_delta
            )
        else:
            delta = (
                -discounted_delta
                if forward < strike
                else 0.0
                if forward > strike
                else -0.5 * discounted_delta
            )
        return OptionGreeks(delta=delta, gamma=0.0, vega=0.0, theta=0.0, rho=0.0)

    d1, d2 = _d1_d2(spot, strike, time_to_expiry, rate, dividend_yield, volatility)
    pdf_d1 = norm.pdf(d1)
    discounted_spot = spot * math.exp(-dividend_yield * time_to_expiry)
    discounted_strike = strike * math.exp(-rate * time_to_expiry)
    sqrt_t = math.sqrt(time_to_expiry)
    delta_call = math.exp(-dividend_yield * time_to_expiry) * norm.cdf(d1)
    gamma = math.exp(-dividend_yield * time_to_expiry) * pdf_d1 / (spot * volatility * sqrt_t)
    vega = discounted_spot * pdf_d1 * sqrt_t

    if option_type == "call":
        theta = (
            -discounted_spot * pdf_d1 * volatility / (2.0 * sqrt_t)
            - rate * discounted_strike * norm.cdf(d2)
            + dividend_yield * discounted_spot * norm.cdf(d1)
        )
        rho = strike * time_to_expiry * math.exp(-rate * time_to_expiry) * norm.cdf(d2)
        return OptionGreeks(delta=delta_call, gamma=gamma, vega=vega, theta=theta, rho=rho)

    theta = (
        -discounted_spot * pdf_d1 * volatility / (2.0 * sqrt_t)
        + rate * discounted_strike * norm.cdf(-d2)
        - dividend_yield * discounted_spot * norm.cdf(-d1)
    )
    rho = -strike * time_to_expiry * math.exp(-rate * time_to_expiry) * norm.cdf(-d2)
    return OptionGreeks(
        delta=delta_call - math.exp(-dividend_yield * time_to_expiry),
        gamma=gamma,
        vega=vega,
        theta=theta,
        rho=rho,
    )


def finite_difference_greeks(
    option_type: OptionType,
    spot: float,
    strike: float,
    time_to_expiry: float,
    volatility: float,
    rate: float = 0.0,
    dividend_yield: float = 0.0,
    *,
    spot_step: float | None = None,
    volatility_step: float = 1e-4,
    time_step: float = 1 / 365.0,
    rate_step: float = 1e-4,
) -> OptionGreeks:
    _validate_option_type(option_type)
    _validate_inputs(spot, strike, time_to_expiry, volatility)
    h_s = spot_step if spot_step is not None else max(1e-4, spot * 1e-4)
    h_v = max(volatility_step, 1e-8)
    h_r = max(rate_step, 1e-8)

    price_up = black_scholes_price(
        option_type, spot + h_s, strike, time_to_expiry, volatility, rate, dividend_yield
    )
    price_down = black_scholes_price(
        option_type,
        max(spot - h_s, 1e-12),
        strike,
        time_to_expiry,
        volatility,
        rate,
        dividend_yield,
    )
    price_mid = black_scholes_price(
        option_type, spot, strike, time_to_expiry, volatility, rate, dividend_yield
    )
    delta = (price_up - price_down) / (2.0 * h_s)
    gamma = (price_up - 2.0 * price_mid + price_down) / (h_s * h_s)

    vega_up = black_scholes_price(
        option_type, spot, strike, time_to_expiry, volatility + h_v, rate, dividend_yield
    )
    vega_down = black_scholes_price(
        option_type, spot, strike, time_to_expiry, max(volatility - h_v, 0.0), rate, dividend_yield
    )
    vega = (vega_up - vega_down) / (2.0 * h_v)

    if time_to_expiry == 0.0:
        theta = 0.0
    elif time_to_expiry > time_step:
        earlier = black_scholes_price(
            option_type, spot, strike, time_to_expiry - time_step, volatility, rate, dividend_yield
        )
        later = black_scholes_price(
            option_type, spot, strike, time_to_expiry + time_step, volatility, rate, dividend_yield
        )
        theta = (earlier - later) / (2.0 * time_step)
    else:
        earlier = black_scholes_price(
            option_type, spot, strike, 0.0, volatility, rate, dividend_yield
        )
        theta = (earlier - price_mid) / time_to_expiry

    rho_up = black_scholes_price(
        option_type, spot, strike, time_to_expiry, volatility, rate + h_r, dividend_yield
    )
    rho_down = black_scholes_price(
        option_type, spot, strike, time_to_expiry, volatility, rate - h_r, dividend_yield
    )
    rho = (rho_up - rho_down) / (2.0 * h_r)
    return OptionGreeks(delta=delta, gamma=gamma, vega=vega, theta=theta, rho=rho)


def implied_volatility(
    option_type: OptionType,
    price: float,
    spot: float,
    strike: float,
    time_to_expiry: float,
    rate: float = 0.0,
    dividend_yield: float = 0.0,
    *,
    lower_vol: float = 1e-8,
    upper_vol: float = 5.0,
    tolerance: float = 1e-8,
    max_upper_vol: float = 10.0,
) -> ImpliedVolatilityResult:
    _validate_option_type(option_type)
    _validate_inputs(spot, strike, time_to_expiry, 0.0)
    if not math.isfinite(price):
        raise ValueError("price must be finite")
    if price < 0.0:
        return ImpliedVolatilityResult(None, "out_of_bounds", "Option price must be non-negative")
    if time_to_expiry == 0.0:
        return ImpliedVolatilityResult(
            None, "degenerate", "Implied volatility is undefined at expiry"
        )

    lower_bound, upper_bound = price_bounds(
        option_type, spot, strike, time_to_expiry, rate, dividend_yield
    )
    if price < lower_bound - tolerance or price > upper_bound + tolerance:
        return ImpliedVolatilityResult(
            None,
            "out_of_bounds",
            f"Price must lie within no-arbitrage bounds [{lower_bound:.10f}, {upper_bound:.10f}]",
        )
    if abs(price - lower_bound) <= tolerance or abs(price - upper_bound) <= tolerance:
        return ImpliedVolatilityResult(
            None,
            "degenerate",
            "Price is on a no-arbitrage boundary; implied volatility is not unique",
        )

    def objective(vol: float) -> float:
        return (
            black_scholes_price(
                option_type, spot, strike, time_to_expiry, vol, rate, dividend_yield
            )
            - price
        )

    lo = lower_vol
    hi = upper_vol
    f_lo = objective(lo)
    f_hi = objective(hi)
    expansions = 0
    while f_lo * f_hi > 0.0 and hi < max_upper_vol:
        hi = min(max_upper_vol, hi * 2.0)
        f_hi = objective(hi)
        expansions += 1

    if f_lo * f_hi > 0.0:
        return ImpliedVolatilityResult(
            None, "no_bracket", "Could not bracket a valid implied volatility"
        )

    root, solver = brentq(objective, lo, hi, xtol=tolerance, rtol=tolerance, full_output=True)
    return ImpliedVolatilityResult(
        float(root), "ok", "Solved with Brent root finding", solver.iterations + expansions
    )
