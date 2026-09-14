# Model risk

This repository is a research lab, not a production risk engine.

## Core assumptions

- European options are priced with Black-Scholes-Merton under lognormal diffusion, constant volatility, and continuous compounding.
- Monte Carlo pricing reuses the same GBM assumptions, so it validates implementation consistency rather than market realism.
- Portfolio VaR and stress tests are simplified factor models driven by synthetic log-spot, volatility, and rate shocks.

## Key limitations

- Discrete hedging error can be material when volatility is misspecified, rebalancing is sparse, or transaction costs are non-zero.
- Implied volatility is only reported when the observed price is strictly inside no-arbitrage bounds and a valid Brent bracket exists.
- Smile and term analyses do not extrapolate or interpolate silently; missing slices are surfaced as validation errors.
- Delta-normal VaR is a local linear approximation and can understate nonlinear tail risk for options portfolios.
- Historical VaR quality depends entirely on the supplied scenario history; this repository only demonstrates synthetic scenarios.

## Validation stance

- Unit tests focus on no-arbitrage relationships, monotonicity, positivity of gamma, expiry behavior, analytic-versus-finite-difference agreement, Monte Carlo consistency, self-financing ledger accounting, and positive-loss VaR conventions.
- Deterministic examples are shipped so that users can reproduce the documented outputs exactly.
