# Option pricing and hedging research note

This note summarizes deterministic synthetic experiments from `examples/pricing_demo.py` and the delta-hedging tests.

## What is implemented

- Dividend-adjusted Black-Scholes-Merton pricing for European calls and puts.
- Analytic Greeks plus finite-difference cross-checks.
- Implied volatility recovery using bounded Brent bracketing.
- Risk-neutral Monte Carlo pricing with antithetic variates and confidence intervals.
- A discrete delta-hedging simulator with self-financing cash, hedge shares, financing, and transaction costs.

## Synthetic findings

- Analytic and finite-difference Greeks agree closely away from expiry.
- Monte Carlo prices converge to Black-Scholes levels within the reported confidence interval; no stronger precision claim is made.
- Discrete hedge replication error remains path- and frequency-dependent, and transaction costs mechanically worsen replication quality.

## Synthetic-data warning

All results in this repository are generated from fixed synthetic inputs. They are suitable for implementation validation and educational discussion, not for claims about live execution quality.
