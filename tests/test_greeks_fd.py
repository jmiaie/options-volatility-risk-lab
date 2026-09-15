"""Cross-check analytic Greeks against an independently implemented finite-difference path.

This is the P0 item 4 validation: greeks_fd.py shares no code with greeks.py
(both call only bsm_price), so agreement here is real evidence the closed-form
derivatives are correct, not a tautology.
"""

from __future__ import annotations

import pytest

from options_risk.pricing.greeks import greeks
from options_risk.pricing.greeks_fd import fd_greeks

CASES = [
    dict(S=100, K=100, T=1.0, r=0.05, sigma=0.2, option_type="call", q=0.0),
    dict(S=100, K=100, T=1.0, r=0.05, sigma=0.2, option_type="put", q=0.0),
    dict(S=120, K=100, T=0.5, r=0.03, sigma=0.35, option_type="call", q=0.02),
    dict(S=80, K=100, T=0.5, r=0.03, sigma=0.35, option_type="put", q=0.02),
    dict(S=100, K=90, T=2.0, r=0.01, sigma=0.15, option_type="call", q=0.0),
    dict(S=100, K=110, T=0.05, r=0.05, sigma=0.6, option_type="put", q=0.0),
]


@pytest.mark.parametrize("case", CASES)
def test_delta_matches_finite_difference(case: dict) -> None:
    analytic = greeks(**case)
    fd = fd_greeks(**case)
    assert analytic.delta == pytest.approx(fd.delta, abs=1e-4)


@pytest.mark.parametrize("case", CASES)
def test_gamma_matches_finite_difference(case: dict) -> None:
    analytic = greeks(**case)
    fd = fd_greeks(**case)
    assert analytic.gamma == pytest.approx(fd.gamma, rel=1e-2, abs=1e-4)


@pytest.mark.parametrize("case", CASES)
def test_vega_matches_finite_difference(case: dict) -> None:
    analytic = greeks(**case)
    fd = fd_greeks(**case)
    assert analytic.vega == pytest.approx(fd.vega, rel=1e-4, abs=1e-3)


@pytest.mark.parametrize("case", CASES)
def test_rho_matches_finite_difference(case: dict) -> None:
    analytic = greeks(**case)
    fd = fd_greeks(**case)
    assert analytic.rho == pytest.approx(fd.rho, rel=1e-4, abs=1e-3)


@pytest.mark.parametrize("case", CASES)
def test_theta_matches_finite_difference(case: dict) -> None:
    analytic = greeks(**case)
    fd = fd_greeks(**case)
    assert analytic.theta == pytest.approx(fd.theta, rel=1e-3, abs=1e-2)


def test_fd_rejects_theta_bump_too_close_to_expiry() -> None:
    with pytest.raises(ValueError):
        fd_greeks(S=100, K=100, T=1e-8, r=0.05, sigma=0.2, option_type="call")
