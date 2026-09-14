# Portfolio tail-risk research note

This note summarizes compact full-revaluation and local-risk analytics for synthetic portfolios.

## Implemented methods

- Aggregate portfolio value and Greeks across cash, equity, and European option positions.
- Full revaluation under spot, volatility, rate, and time scenarios.
- Historical VaR, delta-normal VaR, Monte Carlo VaR, and Expected Shortfall with a positive-loss convention.
- Kupiec proportion-of-failures backtest for exceedance frequency.
- Deterministic stress scenarios and a spot/vol scenario matrix.

## Interpretation guidance

- Delta-normal VaR is best interpreted as a local approximation.
- Full-revaluation scenario matrices are more informative for nonlinear portfolios than Greek P&L alone.
- Kupiec only checks unconditional exceedance frequency; it does not test clustering.

## Synthetic-data warning

All scenarios and outputs in this repository are synthetic and deterministic. The repository does not claim historical calibration, production controls, or real trading performance.
