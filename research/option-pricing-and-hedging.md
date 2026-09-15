# Option Valuation and Discrete Hedging Error — Black-Scholes, Monte Carlo, Implied Volatility, and Transaction Costs

**Status**: all figures below are reproduced by `examples/01`–`05` and
`examples/10`, writing to `results/pricing/`, `results/monte_carlo/`, and
`results/hedging/`. Run `python examples/0N_*.py` to regenerate them
exactly (all runs are seeded). Every number quoted here comes from one of
those result files — none are invented.

## 1. Purpose and scope

This report asks a narrow question: **given the same Black-Scholes model
used to price an option, how well does a real (discrete, costly) hedging
strategy actually replicate that option's payoff?** It is not a claim that
Black-Scholes is the right model of markets — see `docs/model-risk.md` for
the assumptions being made throughout.

## 2. Black-Scholes-Merton pricing and Greeks

`options_risk.pricing` implements the standard BSM formula for European
calls/puts with continuous dividend yield `q`, plus analytic Greeks with
explicit unit conventions (Vega per 1.00 vol, Theta per year elapsed, Rho
per 1.00 change in `r` — see `options_risk/pricing/greeks.py`).

**Validation**: every analytic Greek is cross-checked against an
independently implemented finite-difference version
(`options_risk.pricing.greeks_fd`, sharing no code with the analytic
formulas) — see `tests/test_greeks_fd.py`, 30 passing cases across
call/put, ITM/OTM, short/long maturity, with/without dividends. Put-call
parity, arbitrage bounds, monotonicity in spot/strike, and positive Gamma
are all directly tested in `tests/test_black_scholes.py`.

## 3. Implied volatility: round-trip recovery

`options_risk.pricing.implied_vol.solve_iv` uses Brent's method (bracketed,
guaranteed convergence) as the primary solver, with Newton-Raphson exposed
only as a secondary cross-check. A representative round trip
(`examples/02_solve_implied_vol.py`, `results/pricing/implied_vol_round_trip.json`):

| Quantity | Value |
|---|---|
| True sigma | 0.27 |
| BSM price at true sigma | 7.766894 |
| Brent-recovered IV | 0.269999998 (9 iterations) |
| Newton-recovered IV (cross-check) | 0.270000000 (3 iterations) |

Both solvers recover the true volatility to better than 1e-6. Separately,
an out-of-bounds price (5x spot) is **refused** rather than solved:
`converged=False`, reason *"observed price violates static no-arbitrage
bounds; no Black-Scholes volatility is consistent with this price."* This
refusal is deliberate — see `docs/model-risk.md` §1.

`tests/test_implied_vol.py` extends this to 9 round-trip cases spanning
ITM/ATM/OTM, 1-week to 5-year maturities, and 5%–150% vol, all recovering
the true sigma to `1e-6` absolute tolerance.

## 4. Monte Carlo vs. analytic Black-Scholes

`options_risk.simulation.monte_carlo` prices the same European call
(`S=100, K=100, T=1, r=3%, sigma=25%`) via risk-neutral GBM simulation with
antithetic variates and a control variate (the discounted terminal stock
price, whose risk-neutral mean is known analytically). Analytic price:
**11.348477**. From `results/monte_carlo/bs_vs_mc_convergence.json`
(seed=42, fixed across path counts):

| Paths | MC price | Std. error | 95% CI | Analytic in CI? |
|---|---|---|---|---|
| 1,000 | 11.34125 | 0.10247 | [11.140, 11.542] | yes |
| 10,000 | 11.29860 | 0.03565 | [11.229, 11.368] | yes |
| 100,000 | 11.33320 | 0.01158 | [11.310, 11.356] | yes |
| 1,000,000 | 11.34553 | 0.00363 | [11.338, 11.353] | yes |

Standard error shrinks roughly as `1/sqrt(N)` (a ~28x reduction from 1,000
to 1,000,000 paths against a ~31.6x = sqrt(1000) theoretical scaling — the
gap is variance-reduction-dependent, not a bug). **No single point estimate
here is presented without its standard error and CI** — see
`tests/test_monte_carlo.py` for the broader validation, including a
20-seed empirical CI-coverage check (>=80% hit rate required) and a direct
comparison showing antithetic and control-variate variance is never worse
than naive Monte Carlo, averaged over 10 seeds.

## 5. Discrete delta hedging: the size of the replication gap

`options_risk.hedging.simulate_delta_hedge` writes one 6-month ATM call
(`S0=100, K=100, T=0.5, r=3%, sigma=25%`), delta-hedges it at discrete
intervals, and reports terminal hedging P&L (0 = perfect replication net of
the option premium). From `results/hedging/delta_hedge_experiments.json`
(200–300 seeds per configuration; all reproducible via the seeds recorded
in the artifact):

### 5a. Rebalancing frequency (zero transaction costs)

| Rebalances | Mean hedging P&L | Std. dev. of hedging P&L |
|---|---|---|
| 12 (~monthly) | 0.076 | 1.685 |
| 52 (weekly) | -0.013 | 0.861 |
| 252 (daily) | 0.002 | 0.389 |

The mean stays close to zero at every frequency (consistent with the
classical result that a correctly-specified discrete hedge is unbiased in
expectation), but its **standard deviation falls by roughly half each time
rebalancing frequency roughly quadruples** — continuous-time replication is
a limit this simulator approaches, never reaches, at any finite frequency.

### 5b. Transaction costs (weekly rebalancing, 52 steps)

| Cost rate | Mean hedging P&L | Mean total costs |
|---|---|---|
| 0 bps | -0.013 | 0.000 |
| 5 bps | -0.189 | 0.175 |
| 20 bps | -0.717 | 0.700 |
| 100 bps | -3.536 | 3.498 |

Costs are a pure drag: mean hedging P&L moves monotonically negative as the
cost rate rises, by almost exactly the accumulated transaction cost —
frequent rebalancing that reduces variance (§5a) is not free, and the
optimal frequency depends on the cost environment.

### 5c. Realized vs. pricing (implied) volatility mismatch

Hedging with `sigma_pricing = 25%` while the underlying actually realizes a
different vol (`sigma_realized`):

| Realized vol | Realized / pricing ratio | Mean hedging P&L |
|---|---|---|
| 12.5% | 0.5x | +3.537 |
| 20.0% | 0.8x | +1.420 |
| 25.0% | 1.0x (matched) | -0.013 |
| 31.25% | 1.25x | -1.816 |
| 50.0% | 2.0x | -7.334 |

A short-gamma writer who hedges at a vol *below* what the market
subsequently realizes loses on average (and vice versa) — the sign and
near-monotonic scale of the bias is exactly what a Gamma/Vega story
predicts, and it is **not small**: at 2x vol mismatch, mean hedging error
is ~29x the matched-vol case (in absolute terms, though on a small base).

## 6. Bottom line

Discrete delta hedging genuinely tracks the option's payoff on average
under correctly-specified, cost-free assumptions, but:

1. **discreteness alone** produces hedging P&L with real dispersion at any
   practical rebalancing frequency (§5a);
2. **transaction costs** turn more-frequent rebalancing into a real
   trade-off, not a free variance reduction (§5b); and
3. **vol misspecification** biases the mean outcome, not just its spread
   (§5c).

None of this is a criticism of Black-Scholes as a pricing convention — it
is exactly what the model, taken honestly, predicts once its continuous-
frictionless-trading assumption is relaxed. See `docs/model-risk.md` §1 and
§4 for the full assumption list.
