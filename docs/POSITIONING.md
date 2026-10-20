# Positioning: Options Volatility Risk Lab in the quant research cluster

This note places this repository in the Micap AI quantitative research
portfolio: where the **hub narrative** lives and what claims this lab does and
does not make.

## One-line roles

| Repo | Visibility | Role |
|------|------------|------|
| [`jmiaie/options-volatility-risk-lab`](https://github.com/jmiaie/options-volatility-risk-lab) | public | **This lab** — BSM pricing, Greeks, IV, Monte Carlo, discrete hedging, VaR/ES, stress, and one historical evaluation on frozen SPY/FRED paths. Research library, not a trading system. |
| [`jmiaie/quant-research-portfolio-public`](https://github.com/jmiaie/quant-research-portfolio-public) | public | **Portfolio hub (public)** — findings-led index, portfolio pages, publications list, and VERIFYING entrypoints across flagship projects. |

Sibling flagships on the public hub (separate repos): Financial Dynamics Model,
Statistical Arbitrage Engine, ML Sentiment Augmented Price Predictor.

## What belongs where

| Content | Lives in |
|-------------|---------|
| Pricing / risk library code, synthetic examples, this repo's historical study pack | **options-volatility-risk-lab** |
| Cross-project headline findings, VERIFYING SHAs, public findings index | **quant-research-portfolio-public** |
| Live trading, brokerage, invented performance, fabricated Greeks/PnL | **Nowhere** — out of scope for the cluster honesty standard |

## Explicit non-goals for this repository

- Do **not** present model outputs (prices, Greeks, VaR/ES, hedging P&L) as
  live-trading signals, backtested alpha, or investment advice.
- Do **not** invent options-tape P&L; the historical study prices options with
  BSM off realized vol on a **hypothetical** book (see README historical
  evaluation and `publication/options-risk-study/`).
- Do **not** treat any portfolio hub as a runtime dependency — clone this repo
  alone for library + study reproduction.
- No dashboard or interactive visualization ships with this repository; it
  remains **deferred** (see the hub portfolio page).

## Honesty alignment

The public hub reports null and negative results as found. This lab's
withdrawn order-of-magnitude VaR divergence (volatility-units defect) is part
of that standard — cite the corrected publication pack, not the withdrawn
narrative. See [`docs/model-risk.md`](model-risk.md) for model assumptions.
