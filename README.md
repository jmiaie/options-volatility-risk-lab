# Options, Volatility & Portfolio Risk Lab

**Derivatives Pricing • Implied Volatility • Monte Carlo • Hedging • VaR/ES • Stress Testing**

A research library, not a trading system: every model here computes a
number under explicitly stated assumptions and is validated against an
independent check (a finite-difference cross-check, put-call parity, a
round-trip solve, a closed-form toy answer, an out-of-sample backtest).
No live trading, no brokerage integration, no invented market data or
performance numbers.

## Historical evaluation (SPY 2015–2025)

Alongside the synthetic library, the repo contains one historical study on
real, frozen SPY / FRED (DGS3MO, VIXCLS) daily snapshots, 2015–2025
(`src/options_risk/historical_risk_study_v2.py`, pre-registered spec v2).
Result summary, quoted from the committed writeup:

- A volatility-units defect (annualized vol fed where a daily figure was required) inflated Delta-Normal VaR by exactly `sqrt(252) ≈ 15.87x` and Monte Carlo VaR by 35.2–40.5x (range across the six period/confidence aggregate cells); after correction, all three VaR/ES methods sit within the same order of magnitude, and the earlier "vol running hot + convexity" explanation is withdrawn.
- Full-revaluation Monte Carlo ES exceeds Delta-Normal ES in every period/confidence row, by roughly +18% to +42%.
- 2025 mean realized vol (16.33%) exceeded DEV's (15.15%) and VAL 2024's (11.84%) modestly, not by an order of magnitude.

**Classification:** historical evaluation (2025 is labeled HISTORICAL
EVALUATION, not an untouched holdout) of a hypothetical, standardized
portfolio and hedging construct. No options tape (options are priced with
BSM off realized vol), no deployed strategy, no live trading.

Links: [technical paper](publication/options-risk-study/TECHNICAL-PAPER.md) ·
[case study](publication/options-risk-study/CASE-STUDY.md) ·
[result source map](publication/options-risk-study/RESULT-SOURCE-MAP.md) ·
[research report](research/historical-volatility-and-tail-risk.md) ·
[results](results/historical_risk/) · [dataset manifests](data/manifests/)

## Why this project

Most "options pricing" portfolio projects stop at a Black-Scholes formula.
This one is built the way a quant research desk would actually validate
one: analytic Greeks checked against an independently-coded finite-
difference version, an implied-vol solver that refuses to answer for an
arbitrage-violating price, a Monte Carlo engine that never reports a price
without its standard error, a delta-hedging simulator that shows discrete
hedging error rather than assuming continuous replication, and a full-
revaluation risk stack (VaR/ES/stress) that is explicitly compared against
— and shown to disagree with — its own linear (Delta-Normal) approximation.

## Research modules

| Module | What it does |
|---|---|
| `options_risk.pricing` | Black-Scholes-Merton European pricing, analytic Greeks, independent finite-difference Greeks, Brent-based implied-vol solver with no-arbitrage bounds checking |
| `options_risk.simulation` | Risk-neutral GBM Monte Carlo pricing with antithetic + control-variate variance reduction, always reporting SE/CI |
| `options_risk.data` | Option-chain schema, cleaning rules (crossed quotes, bounds, stale/zero-bid flags), synthetic fixtures (no network) |
| `options_risk.volatility` | Log-forward-moneyness smile/term-structure/surface interpolation with explicit interpolation-vs-extrapolation flags |
| `options_risk.hedging` | Discrete delta-hedging simulator (financing, transaction costs, rebalance frequency) and batch hedging experiments |
| `options_risk.portfolio` | Equity/option/cash position representation with Greek aggregation |
| `options_risk.stress` | Full-revaluation scenario engine, standard stress suite, spot-vol convexity grid |
| `options_risk.attribution` | Greek-based (Taylor) P&L explain vs. full revaluation, with residual reporting |
| `options_risk.risk` | Historical / Delta-Normal / Monte Carlo VaR, Expected Shortfall, VaR backtesting (Kupiec, Christoffersen, conditional coverage) |

## Validation

Every claim below is a real, passing test in `tests/` (part of the full suite) —
not aspirational:

- **Put-call parity, arbitrage bounds, monotonicity, positive Gamma** —
  `tests/test_black_scholes.py`
- **Analytic Greeks vs. an independently coded finite-difference path** —
  `tests/test_greeks_fd.py` (30 cases, no shared code between the two)
- **Implied-vol round trip** (sigma -> price -> solved IV) across
  ITM/ATM/OTM, short/long maturity, low/high vol — `tests/test_implied_vol.py`
- **Monte Carlo vs. analytic BSM**: convergence, CI coverage, seed
  reproducibility, antithetic/control-variate variance never worse than
  naive — `tests/test_monte_carlo.py`. (Antithetic variates are used in
  the pricing Monte Carlo only, not in the historical study's Monte Carlo VaR.)
- **Portfolio accounting invariants**: position-level Greek scaling, a
  delta-hedged book summing to zero Delta — `tests/test_portfolio.py`
- **Delta-hedge self-financing accounting**: portfolio-value identity holds
  every row, hedge closes out at expiry, matched-vol replication is
  unbiased in expectation — `tests/test_delta_hedge.py`
- **VaR/ES on toy distributions with known closed-form answers** (uniform,
  normal) — `tests/test_var_es.py`
- **VaR backtesting** on synthetic breach series with known statistical
  properties (well-calibrated, miscalibrated, clustered) —
  `tests/test_var_backtesting.py`
- **Full-revaluation stress/P&L attribution**: convexity shows up directly
  in full-reval P&L, and the Greek-based Taylor explain's residual grows
  with shock size — `tests/test_stress_and_attribution.py`

```
pytest --cov=options_risk --cov-report=term-missing
```

## Research reports

- [`research/option-pricing-and-hedging.md`](research/option-pricing-and-hedging.md) —
  Option Valuation and Discrete Hedging Error: BSM, Monte Carlo, implied
  vol round-trips, and quantified transaction-cost/vol-misspecification
  effects on hedging P&L.
- [`research/portfolio-tail-risk.md`](research/portfolio-tail-risk.md) —
  Portfolio Tail Risk Under Nonlinear Exposure: full-revaluation stress
  testing, Greek-explain-vs-full-reval residuals, VaR model comparison,
  and VaR backtesting with sample-size caveats.

Every figure in both reports is reproduced by a script in `examples/` and
written to `results/` — nothing is hand-typed or invented.

## Reproduce

```bash
pip install -e ".[dev,viz]"
pytest                                  # full test suite
ruff check src tests                    # lint
ruff format --check src tests           # format check
mypy                                    # static types

python examples/01_price_option.py           # BSM price + Greeks
python examples/02_solve_implied_vol.py       # IV round-trip + bounds rejection
python examples/03_bs_vs_mc_comparison.py     # MC convergence vs. analytic
python examples/04_vol_smile_from_fixture.py  # vol surface from synthetic chain
python examples/05_delta_hedge_sim.py         # hedging experiments
python examples/06_build_portfolio.py         # mixed portfolio + Greeks
python examples/07_var_es_calc.py             # Historical/Delta-Normal/MC VaR+ES
python examples/08_stress_matrix.py           # stress suite + spot-vol grid
python examples/09_var_backtest.py            # rolling VaR backtest
python examples/10_pnl_explain.py             # Taylor P&L explain vs. full reval
```

Every script is seeded and writes a small JSON artifact to
`results/<category>/` documenting its exact config, seed, and assumptions.

## Model risk & limitations

Every model here is built under explicit, documented assumptions — constant
vol, lognormal diffusion, continuous/frictionless trading for
Black-Scholes; linearized exposure and normal returns for Delta-Normal VaR;
finite sampling for Monte Carlo and historical VaR; no arbitrage
enforcement for the vol surface. **See
[`docs/model-risk.md`](docs/model-risk.md) for the full list.** Nothing in
this repository should be read as investment advice, a live-trading
signal, or a guarantee about real market behavior — every number is a
model output under stated assumptions.

## Scope & data

- Vanilla European options only — no exotics, no American exercise.
- Unit tests, CI, and `examples/` use **synthetic** data only (seeded
  fixtures in `options_risk.data.chain.synthetic_chain`) and make no
  network calls.
- The historical study (above) uses frozen SPY/FRED 2015–2025 snapshots
  recorded in `data/manifests/`; its results are committed under
  `results/historical_risk/`. Acquisition scripts (`yfinance`, optional
  `data` extra) are not run in CI.
- No live trading, no brokerage integration, no deep learning.

## Setup

```bash
git clone https://github.com/jmiaie/options-volatility-risk-lab.git
cd options-volatility-risk-lab
pip install -e ".[dev,viz]"
pytest
```

Requires Python 3.11+. Core dependencies: numpy, scipy, pandas.
`matplotlib` is an optional `viz` extra; `yfinance` is an optional `data`
extra kept out of the core install and out of CI. CI runs on GitHub Actions
against Python 3.11 and 3.12 (`.github/workflows/ci.yml`): ruff lint,
ruff format check, mypy, and the full pytest suite.

## Package layout

```
src/options_risk/
  pricing/       BSM pricing, analytic + finite-difference Greeks, implied vol
  volatility/    smile/term-structure/surface utilities
  simulation/    Monte Carlo GBM pricing
  hedging/       discrete delta-hedging simulator + experiments
  portfolio/     position/portfolio representation
  risk/          VaR, ES, VaR backtesting
  stress/        full-revaluation scenario engine, stress suite
  attribution/   Greek-based P&L explain vs. full revaluation
  data/          option-chain schema, cleaning, synthetic fixtures
tests/           full suite covering the financial invariants above
examples/        10 runnable, seeded example scripts
results/         reproducible small artifacts written by examples/
research/        research reports referenced above
publication/     historical-study writeup + reproducibility bundle
docs/            model-risk.md
```
