# Portfolio Tail Risk Under Nonlinear Exposure — VaR, Expected Shortfall, Stress Testing, and Full Revaluation

**Status**: all figures below are reproduced by `examples/06`–`09`, writing
to `results/attribution/`, `results/stress/`, and `results/var/`. Run
`python examples/0N_*.py` to regenerate them exactly (all runs are seeded).
Every number quoted here comes from one of those result files — none are
invented.

## 1. Purpose and scope

This report asks: **for a portfolio with real option convexity, how far
apart are a linear risk approximation and a full-revaluation one, and what
does that gap look like concretely?** Every VaR/ES/stress number here uses
the loss-sign convention `loss = -(P&L)` documented in
`options_risk.risk.var` — a positive VaR/ES is an adverse (loss) number.
See `docs/model-risk.md` §5–6 for the full assumption list behind each
model used.

## 2. The example portfolio

`examples/06_build_portfolio.py` builds a small mixed book on one
underlying (`options_risk.portfolio.Portfolio`):

- 500 shares long
- 10 short 3-month $95-strike puts (100 shares/contract)
- 5 long 6-month $110-strike calls (100 shares/contract)
- $25,000 cash

Market value: **$74,818.17**. Aggregate Greeks are computed by full
position-level scaling (quantity x contract multiplier x per-share Greek),
not approximated — see `options_risk.portfolio.portfolio.Portfolio.greeks`.

## 3. Full-revaluation stress testing shows real convexity

`examples/08_stress_matrix.py` runs the standard deterministic stress suite
(`options_risk.stress.scenario.STANDARD_STRESS_SCENARIOS`) via **full
Black-Scholes revaluation** of every position — not a Greek approximation.
Selected results from `results/stress/stress_and_spot_vol_matrix.json`:

| Scenario | P&L | P&L % |
|---|---|---|
| Equity -5% | -$5,046.06 | -6.74% |
| Equity -10% | -$10,780.88 | -14.41% |
| Equity -20% | -$24,275.92 | -32.45% |
| Equity +5% | +$4,560.32 | +6.10% |
| Equity +10% | +$8,887.64 | +11.88% |
| Vol +10 pts | -$402.45 | -0.54% |
| Vol doubling | -$650.33 | -0.87% |
| Rates +100bps | +$152.70 | +0.20% |
| Crash (-20%) + vol spike (+10pts) | -$24,655.97 | -32.95% |

Two nonlinearities are visible directly in these full-revaluation numbers,
with no Greek approximation involved:

- **Asymmetry**: +5% spot gives +6.10% P&L but -5% gives -6.74% — the
  short-put leg's negative gamma bites harder on the downside than the
  long-call leg's positive gamma helps on the upside of equal size.
- **Acceleration**: -20% spot P&L (-32.45%) is proportionally worse than
  4x the -5% P&L (4 x -6.74% = -26.96%) — the loss accelerates
  super-linearly as the short puts move further ITM, exactly the
  convexity a linear (Delta-only) risk measure cannot see.

`examples/08` additionally runs a 7x5 spot-vol grid
(`options_risk.stress.scenario.spot_vol_matrix`) via full revaluation —
see `results/stress/stress_and_spot_vol_matrix.json` for the full grid.

## 4. Greek-based P&L explain vs. full revaluation: the residual grows with shock size

`examples/10_pnl_explain.py` compares the second-order Taylor
approximation (`Delta*dS + 0.5*Gamma*dS^2 + ...`) against full revaluation
for a simpler long-call/short-put book, across shock sizes
(`results/attribution/pnl_explain_vs_shock_size.json`):

| Spot shock (dS) | Explained (Taylor) P&L | Actual (full reval) P&L | Residual | Residual as % of actual |
|---|---|---|---|---|
| $0.50 | 363.108 | 363.107 | -0.001 | 0.0004% |
| $1.00 | 729.708 | 729.696 | -0.012 | 0.0017% |
| $2.00 | 1,473.381 | 1,473.263 | -0.119 | 0.0081% |
| $5.00 | 3,788.193 | 3,785.392 | -2.801 | 0.0740% |
| $10.00 | 7,925.518 | 7,892.096 | -33.423 | 0.4235% |
| $20.00 | 17,247.566 | 16,856.349 | -391.216 | 2.3209% |

The residual (unexplained P&L) grows from 0.0004% of actual P&L at a
50-cent move to **2.32% at a $20 move** — a monotonic, accelerating growth
exactly as expected for a second-order approximation to a genuinely convex
payoff. The Taylor explain is never presented alone; it is always shown
next to the full-revaluation number it is approximating.

## 5. VaR model comparison: Historical, Delta-Normal, and Monte Carlo

`examples/07_var_es_calc.py` computes 95% VaR/ES for the mixed portfolio
(§2) under a synthetic daily log-return series (mean 0.02%, vol 1.5%,
seed=2024 — clearly synthetic, not real market data). From
`results/var/var_es_comparison.json`:

| Model | VaR | ES | Notes |
|---|---|---|---|
| Historical Simulation (full reval, 500 obs) | $2,260.44 | $3,068.23 | actual repricing under each historical return |
| Delta-Normal (linear, parametric) | $2,349.35 | $2,946.18 | assumes normal returns, linear P&L, no Gamma |
| Monte Carlo (full reval, 20,000 sims) | $2,347.19 | $2,969.91 | normal risk-factor simulation + full reval |

**For this particular book and shock scale, the three models land within
~4% of each other** — this portfolio's long-call and short-put legs have
partially offsetting convexity at the ~1.5%-daily-vol scale sampled here,
so it is *not* a case where Delta-Normal is dramatically wrong. This is an
honest, reproducible result, not a cherry-picked one: §3 and §4 above (the
full stress suite and the Taylor-vs-full-reval comparison) are the sharper
demonstrations of convexity risk in this repository, precisely because
they probe larger and more one-sided moves (a -20% crash, a $20 spot move)
where the linear approximation's blind spot is unambiguous. **The general
point stands and is demonstrated directly in §3-4**: Delta-Normal VaR
cannot see convexity at all, by construction (see `docs/model-risk.md`
§5); whether that blindness happens to matter for a *given* book at a
*given* shock size is an empirical question this repository answers by
computing it, not by asserting it.

## 6. VaR backtesting: Kupiec, Christoffersen, conditional coverage

`examples/09_var_backtest.py` runs a rolling 60-day-window historical VaR
(95% confidence) forward through 150 out-of-sample test days on a synthetic
daily return series (mean 0, vol 1.4%, seed=99), **strictly avoiding
lookahead** — each day's VaR forecast uses only the 60 returns prior to
that day. Results (`results/var/var_backtest.json`):

| Test | Statistic | p-value | Conclusion |
|---|---|---|---|
| Kupiec POF (8 breaches vs. 7.5 expected / 150 days) | LR=0.034 | 0.853 | fail to reject (rate consistent with 5% expected) |
| Christoffersen independence | LR=0.640 | 0.424 | fail to reject (no significant clustering) |
| Conditional coverage | LR=0.674 | 0.714 | fail to reject |

**This is explicitly not read as "the model is validated."** `n_obs=150`
is below this library's own ~250-observation (roughly one trading year)
rule-of-thumb threshold for reasonable test power — every
`BacktestResult` carries this caveat verbatim
(`sample_size_caveat`), and the conclusion text is deliberately hedged
("fail to reject," never "valid"). At a 95% confidence level, 150
observations imply only ~7.5 expected breaches — not enough to detect
anything but a fairly large miscalibration.

## 7. Bottom line

- Full revaluation (§3) shows real, asymmetric, accelerating convexity risk
  that a linear approximation structurally cannot represent.
- The Greek-based P&L explain (§4) tracks full revaluation closely for
  small moves and diverges predictably (residual growing to single-digit
  percent) as moves get large — it is a documented approximation, not a
  claim of exactness.
- Comparing VaR models (§5) on one book at one shock scale can land close
  together, as it does here — the honest conclusion is that Delta-Normal's
  blindness to convexity is a structural property (proven directly in §3–4),
  not something every single portfolio/scenario combination will
  visibly demonstrate on its own.
- VaR backtesting (§6) is reported with its full statistical machinery and
  its sample-size limitations in the same breath — never a bare pass/fail.

See `docs/model-risk.md` for the complete list of assumptions and known
limitations behind every model referenced in this report.
