# options-volatility-risk-lab

A lean Python research lab for derivatives pricing, volatility analysis, discrete delta hedging, portfolio revaluation, and tail-risk analytics.

## Scope

This repository implements synthetic-data research tooling for Directive #4 priorities:

- Dividend-adjusted Black-Scholes-Merton European call/put pricing with continuous `r`/`q` conventions.
- Analytic Delta, Gamma, Vega, Theta, and Rho with finite-difference cross-check utilities.
- Brent-bracketed implied volatility with explicit no-arbitrage bounds and failure statuses.
- Risk-neutral GBM Monte Carlo pricing with deterministic seeds, antithetic variates, and confidence intervals.
- Option-chain validation with an explicit log-moneyness convention `log(K / F)` where `F = S * exp((r-q)T)`.
- Discrete delta hedging with a self-financing ledger, funding, transaction costs, and long/short option handling.
- Compact portfolio aggregation with Greeks, spot/vol/rate/time revaluation, stress testing, and VaR / Expected Shortfall.
- Kupiec proportion-of-failures validation for VaR exceedances.

Everything in `examples/`, `research/`, and `research/results/` uses deterministic synthetic inputs only. No live market data, API calls, or recruiter-style performance claims are included.

## Greek conventions

- `delta`: price change per 1.0 unit move in spot.
- `gamma`: delta change per 1.0 unit move in spot.
- `vega`: price change per 1.0 absolute volatility move (divide by 100 for “per 1 vol point”).
- `theta`: annualized calendar-time decay (`dV/dt`, where positive `t` means time passes and time-to-expiry falls).
- `rho`: price change per 1.0 absolute rate move.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
pip install pytest ruff mypy
pytest
ruff check .
mypy src
python examples/pricing_demo.py
python examples/portfolio_risk_demo.py
```

## Repository layout

- `/src/options_risk`: package source.
- `/tests`: focused numerical and risk-invariant tests.
- `/docs/model-risk.md`: model limitations and assumptions.
- `/research/*.md`: concise research notes based on synthetic scenarios.
- `/research/results/*.json`: deterministic example outputs generated from the example scripts.

## Current limitations / unfinished work

- Only European vanilla options are implemented.
- Smile/term analysis validates exact or tolerance-based slices only; there is intentionally no interpolation or extrapolation layer.
- VaR factor modeling is intentionally compact: delta-normal uses linear `[log spot return, vol shift, rate shift]` factors and Monte Carlo VaR reuses the same factorization.
- Historical scenarios are provided by the caller; the repository does not ship real market histories.
- Kupiec POF is implemented; Christoffersen independence is intentionally omitted rather than shipped partially tested.

## Suggested future central-hub page update

`options-volatility-risk-lab — Build derivatives pricing, volatility, hedging, and portfolio risk research lab with tested Black-Scholes, Monte Carlo, delta hedging, portfolio stress/VaR analytics, and explicitly synthetic example data.`
