from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.stats import norm

from .bsm import OptionType, black_scholes_price


@dataclass(frozen=True)
class MonteCarloResult:
    price: float
    standard_error: float
    confidence_level: float
    confidence_interval: tuple[float, float]
    sample_size: int


def monte_carlo_european_price(
    option_type: OptionType,
    spot: float,
    strike: float,
    time_to_expiry: float,
    volatility: float,
    rate: float = 0.0,
    dividend_yield: float = 0.0,
    *,
    n_paths: int = 100_000,
    seed: int | None = None,
    antithetic: bool = True,
    confidence_level: float = 0.95,
) -> MonteCarloResult:
    if n_paths <= 1:
        raise ValueError("n_paths must be greater than 1")
    exact = black_scholes_price(
        option_type, spot, strike, time_to_expiry, volatility, rate, dividend_yield
    )
    if time_to_expiry == 0.0 or volatility == 0.0:
        return MonteCarloResult(
            price=exact,
            standard_error=0.0,
            confidence_level=confidence_level,
            confidence_interval=(exact, exact),
            sample_size=n_paths,
        )

    rng = np.random.default_rng(seed)
    if antithetic:
        half = n_paths // 2
        draws = rng.standard_normal(half)
        normals = np.concatenate([draws, -draws])
        if n_paths % 2 == 1:
            normals = np.concatenate([normals, rng.standard_normal(1)])
    else:
        normals = rng.standard_normal(n_paths)

    drift = (rate - dividend_yield - 0.5 * volatility * volatility) * time_to_expiry
    diffusion = volatility * math.sqrt(time_to_expiry) * normals
    terminal_spots = spot * np.exp(drift + diffusion)
    if option_type == "call":
        payoffs = np.maximum(terminal_spots - strike, 0.0)
    else:
        payoffs = np.maximum(strike - terminal_spots, 0.0)
    discounted = math.exp(-rate * time_to_expiry) * payoffs
    price = float(np.mean(discounted))
    standard_error = float(np.std(discounted, ddof=1) / math.sqrt(discounted.size))
    z_value = float(norm.ppf(0.5 + confidence_level / 2.0))
    interval = (price - z_value * standard_error, price + z_value * standard_error)
    return MonteCarloResult(
        price=price,
        standard_error=standard_error,
        confidence_level=confidence_level,
        confidence_interval=interval,
        sample_size=int(discounted.size),
    )
