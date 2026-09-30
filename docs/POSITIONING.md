# Positioning: Options Volatility Risk Lab in the quant research cluster

This note places this repository in the Micap / Jeffrey Milam quantitative
research portfolio so viewers know where the **hub narrative** lives and what
claims this lab does and does not make.

## One-line roles

| Repo | Visibility | Role |
|------|------------|------|
| [`jmiaie/options-volatility-risk-lab`](https://github.com/jmiaie/options-volatility-risk-lab) | public | **This lab** — BSM pricing, Greeks, IV, Monte Carlo, discrete hedging, VaR/ES, stress, and one historical evaluation on frozen SPY/FRED paths. Research library, not a trading system. |
| [`jmiaie/quant-research-portfolio-public`](https://github.com/jmiaie/quant-research-portfolio-public) | public | **Portfolio hub (public)** — findings-led index, portfolio pages, publications list, and VERIFYING entrypoints across flagship projects. Prefer linking here for recruiter / external narrative. |
| [`jmiaie/quant-research-portfolio`](https://github.com/jmiaie/quant-research-portfolio) | private | **Portfolio hub (private)** — same cluster narrative plus internal export / interview tooling. Not required to run or understand this lab. |

Sibling flagships on the public hub (separate repos): Financial Dynamics Model,
Statistical Arbitrage Engine, ML Sentiment Augmented Price Predictor.

## What belongs where

| Change type | Land in |
|-------------|---------|
| Pricing / risk library code, synthetic examples, this repo's historical study pack | **options-volatility-risk-lab** |
| Cross-project headline findings, VERIFYING SHAs, recruiter index copy | **quant-research-portfolio-public** (and private hub when syncing) |
| Live trading, brokerage, invented performance, fabricated Greeks/PnL | **Nowhere** — out of scope for the cluster honesty standard |

## Explicit non-goals for this repository

- Do **not** present model outputs (prices, Greeks, VaR/ES, hedging P&L) as
  live-trading signals, backtested alpha, or investment advice.
- Do **not** invent options-tape P&L; the historical study prices options with
  BSM off realized vol on a **hypothetical** book (see README historical
  evaluation and `publication/options-risk-study/`).
- Do **not** treat the private hub as a runtime dependency — clone this repo
  alone for library + study reproduction.
- Dashboard / interactive viz remains **deferred** (stated on the hub portfolio
  page); do not imply a shipped product UI here.

## Honesty alignment

The public hub reports null and negative results as found. This lab's
withdrawn order-of-magnitude VaR divergence (volatility-units defect) is part
of that standard — cite the corrected publication pack, not the withdrawn
narrative. See [`docs/model-risk.md`](model-risk.md) for model assumptions.
