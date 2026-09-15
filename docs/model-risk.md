# Model Risk & Limitations

Every number this library produces — a price, a Greek, an implied vol, a
Monte Carlo estimate, a hedging P&L, a VaR, an Expected Shortfall, a stress
scenario's P&L — is **a model output, computed under stated assumptions,
not a guarantee, a prediction, or a bound on what can actually happen.**
This document collects the assumptions and known failure modes behind each
model in the library, organized by module. It exists so that anyone using
this code (including a recruiter skimming it) can see exactly what is and
is not being claimed.

## 1. Black-Scholes-Merton (pricing, Greeks, implied vol)

Implemented in `options_risk.pricing`. The BSM model assumes:

- **Constant volatility** over the life of the option. Real implied
  volatility varies by strike and maturity (the "smile"/"skew") — see
  §2. Pricing a single option off a single `sigma` is a simplification
  every practitioner making a "single number" vol assumption is making
  explicitly, not accidentally.
- **Lognormal, continuous diffusion** of the underlying (geometric
  Brownian motion with no jumps). Real markets gap — overnight, at
  earnings, around macro releases — in ways a diffusion process
  structurally cannot produce. Jump risk is not modeled anywhere in this
  library.
- **Continuous, frictionless trading** with no transaction costs or
  liquidity constraints, enabling the theoretical continuous replication
  argument the model is built on. The hedging simulator (§4) exists
  specifically to quantify how this assumption breaks down once trading is
  discrete and costly.
- **Constant, known interest rates and dividend yield** over the option's
  life. Real rates and dividend policy change; this library takes `r` and
  `q` as fixed inputs per pricing call, not as stochastic processes.
- **No arbitrage / frictionless markets** (no bid-ask spread, shorting is
  unrestricted and costless, borrowing/lending at the same rate `r`).

**Implied volatility** (`options_risk.pricing.implied_vol`) inherits all of
the above: an IV is only the volatility that makes BSM match an observed
price under these assumptions — it is a model-implied quantity, not a
directly observed one, and a different pricing model (e.g. one with jumps
or stochastic vol) would back out a different number from the same price.
The solver refuses to return an IV for a price outside static no-arbitrage
bounds (see `is_within_arbitrage_bounds`), but that check is necessary, not
sufficient — a price inside the bounds is not necessarily "correct."

## 2. Volatility surface (`options_risk.volatility`)

- **Stale/illiquid quotes**: a quoted mid can lag the true clearing price,
  especially for low-volume/low-open-interest contracts; `synthetic_chain`
  /`clean_chain` flag (not drop) zero-bid quotes for exactly this reason —
  see `options_risk.data.chain`.
- **Bid/ask noise**: solving IV from the midpoint assumes the mid is an
  unbiased estimate of fair value; for wide markets it is a noisy one.
  `check_surface_sanity` flags (but does not correct) extreme relative
  spreads.
- **Interpolation choice**: the surface uses linear interpolation in
  log-moneyness within an expiry and linear interpolation in total
  variance across expiries (see `options_risk.volatility.surface` module
  docstring for the exact convention). This is a simple, transparent
  choice — not a parametric arbitrage-free model (no SVI, no local vol).
  A different interpolation scheme will produce different vols at
  untraded strikes/maturities.
- **Sparse strikes/maturities**: interpolation between widely-spaced nodes
  is a bigger extrapolation of market information than it looks like
  numerically.
- **Extrapolation**: every surface query reports whether it fell outside
  the observed `(T, k)` range (`SurfaceQueryResult.extrapolated`). This
  library never claims to "know" the vol outside its data — it flat-
  extrapolates and says so.
- **No arbitrage enforcement**: `check_surface_sanity` catches cheap,
  unambiguous problems (duplicate contracts, negative IV, extreme
  spreads) — it does **not** enforce or verify the absence of calendar-
  spread or butterfly arbitrage in the constructed surface. A surface
  built by this module should not be described as "arbitrage-free."

## 3. Monte Carlo (`options_risk.simulation`)

- **Simulation error**: every MC price is a point estimate with sampling
  error; this library always reports a standard error and confidence
  interval (never a bare number) for exactly this reason. A single run,
  even with variance reduction, can still miss — see the CI-coverage test
  in `tests/test_monte_carlo.py`, which explicitly allows and measures a
  non-zero miss rate.
- **Model specification**: the simulator draws from the same risk-neutral
  GBM as the analytic BSM pricer; it will converge to the BSM price by
  construction (this is a validation of the simulator's correctness, not
  independent confirmation that GBM is a good description of markets).
- **Insufficient paths**: variance reduction (antithetic variates, control
  variates) narrows the CI for a given path count, but does not eliminate
  sampling error; users must still choose `n_paths` appropriate to the
  precision they need, and the reported SE tells them what precision they
  got.
- **Extending to multi-factor / path-dependent products**: this simulator
  prices vanilla European payoffs off terminal price only; a covariance
  matrix among multiple correlated risk factors, or path-dependent payoffs
  (barriers, Asians, American exercise), are not implemented and would
  introduce their own model risk (covariance estimation error, discretization
  bias for path-dependent payoffs) not covered by anything here.

## 4. Discrete delta hedging (`options_risk.hedging`)

- **Discrete rebalancing**: the simulator hedges at discrete intervals (a
  parameter, not a limit going to zero), and the whole point of
  `options_risk.hedging.experiments` is to show that hedging error does
  not vanish at any finite rebalancing frequency — see
  `research/option-pricing-and-hedging.md` for the quantified results.
- **Transaction costs**: modeled as a simple proportional rate on traded
  notional. Real transaction costs also include bid-ask spread crossing,
  market impact for large trades, and financing-rate spreads (borrow vs.
  lend) — none of which are modeled here.
- **Vol misspecification**: the hedge ratio (Delta) is computed from
  `sigma_pricing`, while the underlying can be simulated under a different
  `sigma_realized` — a deliberate lever to show that hedging error is
  systematically biased (not just noisier) when the hedger's vol view is
  wrong, as `vol_misspecification_experiment` demonstrates.
  **Real markets add a further layer this simulator does not touch:
  implied vol itself moves over the life of the trade in response to
  supply/demand and realized-vol surprises** — a genuinely stochastic-vol
  effect (Vega/Vanna P&L), not represented by a single fixed
  `sigma_realized` draw here.
- **Jump / gap risk**: the underlying is simulated as continuous GBM; a
  real overnight gap can move the underlying past where the hedge was set,
  producing hedging error this simulator's continuous-diffusion path
  structurally cannot reproduce.
- **Liquidity**: the simulator assumes every hedge trade executes at the
  simulated price with no market impact and no execution delay.

## 5. Value-at-Risk / Expected Shortfall (`options_risk.risk`)

- **Confidence level and window dependence**: VaR/ES estimates are
  sensitive to the chosen confidence level and (for historical simulation)
  the lookback window — a short window under-samples tail events, a long
  one may include stale/irrelevant regimes. This library exposes the
  window/confidence level as explicit parameters; it does not pick one for
  the user.
- **Normality assumptions**: `delta_normal_var` assumes normally
  distributed returns and a linear P&L — both are simplifications
  deliberately included to be shown as inadequate for convex, option-heavy
  books (`research/portfolio-tail-risk.md` quantifies the disagreement with
  full-revaluation VaR). Real return distributions have fatter tails and
  volatility clustering that a single-period normal does not capture.
- **Covariance/vol instability**: both `delta_normal_var` and
  `monte_carlo_var` take a volatility (or covariance) as a fixed input;
  estimation error and regime shifts in that input are not modeled.
- **Limited tail information**: even full-revaluation historical/Monte
  Carlo VaR only characterizes the distribution implied by the sampled/
  simulated scenarios — a truly unprecedented event (outside the
  historical sample, or outside the assumed return distribution) is by
  definition not represented.
- **Procyclicality**: historical-simulation VaR calculated on a rolling
  window will understate risk in a calm period right before a regime
  shift, and overstate it for a while after a crisis rolls out of the
  window — a structural property of any backward-looking risk measure.
- **Nonlinear exposure**: this is the central point of the whole risk
  module — a linear (Delta-Normal) VaR cannot see Gamma/convexity risk.
  Full-revaluation historical and Monte Carlo VaR are provided specifically
  because they reprice the actual (nonlinear) option positions under each
  scenario rather than linearizing them.
- **VaR is not a maximum loss.** By construction, VaR at confidence level
  `alpha` is expected to be exceeded `(1 - alpha)` of the time — that is
  what the number means. **Expected Shortfall is reported alongside VaR
  specifically because VaR alone says nothing about how bad the tail
  beyond it is** — but ES too is a modeled conditional mean under the same
  sampled/simulated distribution, not an empirical guarantee.
- **Backtest sample-size limitations**: `options_risk.risk.backtesting`
  attaches an explicit sample-size caveat to every result and never
  concludes a model is "valid" from a single test — see
  `BacktestResult.sample_size_caveat` and `conclusion`. With realistic
  sample sizes (a year or two of daily observations), these tests have
  limited statistical power to detect miscalibration, especially at high
  confidence levels (99% VaR implies only ~2-5 expected breaches per year).

## 6. Full-revaluation stress testing & P&L attribution

- **Single-underlying scope**: `options_risk.stress.scenario` and
  `options_risk.attribution.pnl_explain` both assume every position in the
  portfolio shares one underlying spot (the Scenario applies one uniform
  shock to every position). A book spanning multiple names would need a
  per-symbol shock mapping, which is not implemented.
- **Deterministic scenarios are illustrative, not exhaustive.** The
  standard stress suite (`STANDARD_STRESS_SCENARIOS`) covers a fixed set of
  equity/vol/rate shocks chosen for recognizability, not because they
  bound all plausible outcomes.
- **The Greek-based P&L explain is a second-order Taylor approximation**
  and is only ever presented alongside, and compared against, full
  revaluation. `research/portfolio-tail-risk.md` and the tests in
  `tests/test_stress_and_attribution.py` show explicitly that its residual
  (unexplained P&L) grows with shock size — it is never claimed to *be*
  the P&L.

## Bottom line

Every model here is useful for what it is built to show — the shape of
option payoffs, the cost of discrete hedging, the gap between linear and
full-revaluation risk measures — and none of it should be read as a
promise about real markets. Treat every number this library prints as
"here is what this model, under these stated assumptions, computes" and
not as "here is what will happen."
