import pytest

from options_risk.bsm import black_scholes_price
from options_risk.monte_carlo import monte_carlo_european_price


def test_monte_carlo_matches_bsm_with_confidence_interval() -> None:
    analytic = black_scholes_price("call", 100.0, 100.0, 1.0, 0.2, 0.05, 0.02)
    result = monte_carlo_european_price(
        "call",
        100.0,
        100.0,
        1.0,
        0.2,
        0.05,
        0.02,
        n_paths=200_000,
        seed=7,
        antithetic=True,
    )
    assert result.standard_error > 0.0
    assert result.confidence_interval[0] <= analytic <= result.confidence_interval[1]
    assert result.price == pytest.approx(analytic, abs=0.15)


def test_zero_volatility_monte_carlo_is_exact() -> None:
    result = monte_carlo_european_price("put", 100.0, 105.0, 0.5, 0.0, 0.02, 0.01, seed=1)
    analytic = black_scholes_price("put", 100.0, 105.0, 0.5, 0.0, 0.02, 0.01)
    assert result.price == pytest.approx(analytic)
    assert result.standard_error == 0.0
