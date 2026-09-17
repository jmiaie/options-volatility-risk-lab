"""Directive #9 D9-C authoritative historical options/volatility/portfolio-risk
study (v2) -- supersedes historical_risk_study.py (v1), which Directive #9
itself labels EXPLORATORY / NON-CONFORMING TO FINAL D9-C SPEC.

This is NOT a historical options-trading alpha study. Every result here
answers: how do the validated pricing/risk systems behave on real historical
underlying/risk-factor paths?

Required labels, used verbatim wherever these results are reported:
- "Historical underlying-path hypothetical option hedging experiment"
- "Hypothetical nonlinear portfolio evaluated on historical risk-factor paths"

Data-source labeling discipline (per spec):
- DGS3MO is a short-term Treasury constant-maturity yield proxy -- never a
  full option discount curve.
- VIXCLS is market-volatility context/reference -- never the exact implied
  volatility of the modeled SPY option.

No paid options tapes. No invented option panels. Options are priced with
Black-Scholes-Merton using realized volatility, never a fabricated implied
volatility surface.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, cast

import numpy as np
import pandas as pd
from scipy.stats import norm

from options_risk.portfolio.portfolio import Portfolio
from options_risk.portfolio.positions import CashPosition, EquityPosition, OptionPosition
from options_risk.pricing.black_scholes import OptionType, bsm_price, intrinsic_value
from options_risk.pricing.greeks import greeks
from options_risk.risk.backtesting import (
    breaches_from_losses,
    christoffersen_independence_test,
    kupiec_pof_test,
)
from options_risk.risk.var import (
    LossDistributionSummary,
    compute_var_es,
    delta_normal_var,
    historical_simulation_var,
)
from options_risk.stress.scenario import Scenario, revalue_portfolio

REALIZED_VOL_WINDOW_PRIMARY = 20
REALIZED_VOL_WINDOW_SECONDARY = 60
OPTION_MATURITY_SESSIONS = 30
COST_SCENARIOS_BPS: dict[str, float] = {"GROSS": 0.0, "BASE": 1.0, "STRESS": 5.0}
HS_LOOKBACKS = {"primary": 252, "sensitivity": 504}
CONFIDENCE_LEVELS = {"primary": 0.95, "secondary": 0.99}
MC_N_SIMS = 50_000
MC_SEED = 0


@dataclass(frozen=True)
class PeriodSpec:
    name: str
    start: str
    end_inclusive: str

    def mask(self, index: pd.DatetimeIndex) -> np.ndarray:
        start = pd.Timestamp(self.start).normalize()
        end = pd.Timestamp(self.end_inclusive).normalize()
        idx = index.normalize()
        return (idx >= start) & (idx <= end)


def _datetime_index(index: pd.Index) -> pd.DatetimeIndex:
    """load_spy_close()/load_fred_series_decimal() always build a
    DatetimeIndex at runtime; pandas-stubs types generic Index attribute
    access more loosely, so this documents and narrows that known-true fact."""
    return cast(pd.DatetimeIndex, index)


# --------------------------------------------------------------------------
# Data loading: SPY closes, point-in-time DGS3MO, VIXCLS context
# --------------------------------------------------------------------------


def load_spy_close(raw_dir_path: str) -> pd.Series:
    df = pd.read_csv(raw_dir_path, index_col=0, parse_dates=True)
    if "Close" not in df.columns:
        raise ValueError(f"{raw_dir_path} missing Close column")
    close = df["Close"].astype(float).sort_index()
    close = close[~close.index.duplicated(keep="first")]
    return close


def load_fred_series_decimal(csv_path: str, value_col: str) -> pd.Series:
    """Load a FRED daily series, percent -> decimal, indexed by date.

    Per D9-C DGS3MO/VIX rules: missing observations (weekends, holidays,
    FRED publication gaps -- see the manifest's missing_value_representation
    for how they appear in this file) are NOT interpolated or dropped here;
    they are left as NaN so point_in_time_value's carry-forward logic (never
    future-backfill) is the only source of a value on a non-observation day.
    """
    df = pd.read_csv(csv_path)
    date_col = "observation_date" if "observation_date" in df.columns else df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col])
    raw = pd.to_numeric(df[value_col], errors="coerce")
    series = pd.Series(raw.to_numpy() / 100.0, index=df[date_col].to_numpy())
    series = series.sort_index()
    return series[~series.index.duplicated(keep="first")]


@dataclass(frozen=True)
class PointInTimeValue:
    value: float
    as_of_date: pd.Timestamp
    staleness_sessions: int


def point_in_time_value(series: pd.Series, decision_date: pd.Timestamp) -> PointInTimeValue:
    """The latest observation known AT OR BEFORE decision_date -- carry-forward
    only, never future-backfill. Raises if no observation exists on or before
    decision_date at all (nothing to carry forward)."""
    known = series.loc[series.index <= decision_date].dropna()
    if known.empty:
        raise ValueError(f"no {series.name or 'series'} observation on or before {decision_date}")
    as_of = known.index[-1]
    staleness = int((decision_date.normalize() - pd.Timestamp(as_of).normalize()).days)
    return PointInTimeValue(
        value=float(known.iloc[-1]), as_of_date=pd.Timestamp(as_of), staleness_sessions=staleness
    )


# --------------------------------------------------------------------------
# Realized volatility
# --------------------------------------------------------------------------


def log_returns(prices: pd.Series) -> pd.Series:
    ratio = prices / prices.shift(1)
    logged = pd.Series(np.log(ratio.to_numpy()), index=ratio.index)
    return logged.dropna()


def trailing_realized_vol(returns: pd.Series, as_of_index: int, window: int) -> float:
    """Annualized realized vol over the `window` sessions strictly before
    `as_of_index` in `returns` -- never includes the decision day's own
    (not-yet-realized) return."""
    if as_of_index < window:
        return float("nan")
    tail = returns.iloc[as_of_index - window : as_of_index]
    return float(tail.std(ddof=1) * np.sqrt(252))


# --------------------------------------------------------------------------
# D9-C HEDGING EXPERIMENT: historical underlying-path hypothetical hedging
# --------------------------------------------------------------------------


@dataclass
class HedgeEpisodeResult:
    initiation_date: str
    expiry_date: str
    rebalance_frequency: str  # "daily" | "weekly"
    cost_scenario: str
    S0: float
    K: float
    initial_vol_assumption: float
    realized_vol: float
    replication_error: float
    absolute_replication_error: float
    transaction_cost: float
    n_rebalances: int
    max_cash_requirement: float
    rate_used: float
    dividend_yield_used: float


def simulate_delta_hedge_on_price_path(
    prices: pd.Series,
    *,
    K: float,
    r: float,
    sigma_pricing: float,
    option_type: OptionType,
    q: float,
    option_qty: float,
    cost_rate: float,
    rebalance_every_n_sessions: int,
) -> HedgeEpisodeResult:
    """Discrete delta-hedge replayed against a REAL historical daily-close
    path (`prices`, length = maturity sessions + 1, first=initiation,
    last=expiry) -- not a GBM-simulated path. Same self-financing/cost/
    dividend-accrual mechanics as options_risk.hedging.delta_hedge's
    GBM-based simulator, driven by actual market data instead.

    Rebalances only every `rebalance_every_n_sessions` sessions (1=daily,
    5=weekly); between rebalances shares_held is fixed and cash accrues
    interest/dividends daily regardless."""
    n_sessions = len(prices) - 1
    T_total = n_sessions / 252.0
    dt = 1.0 / 252.0

    cash = -option_qty * bsm_price(
        float(prices.iloc[0]), K, T_total, r, sigma_pricing, option_type, q
    )
    shares_held = 0.0
    total_costs = 0.0
    n_rebalances = 0
    cash_path = [cash]

    for i in range(n_sessions + 1):
        S_i = float(prices.iloc[i])
        T_remaining = (n_sessions - i) / 252.0
        is_rebalance_day = (i % rebalance_every_n_sessions == 0) or (i == n_sessions)

        if T_remaining > 1e-12:
            delta = greeks(S_i, K, T_remaining, r, sigma_pricing, option_type, q).delta
        else:
            delta = 0.0

        if is_rebalance_day:
            target_shares = 0.0 if i == n_sessions else -option_qty * delta
            shares_traded = target_shares - shares_held
            trade_notional = abs(shares_traded) * S_i
            trade_cost = cost_rate * trade_notional
            total_costs += trade_cost
            cash -= shares_traded * S_i + trade_cost
            shares_held = target_shares
            if shares_traded != 0.0:
                n_rebalances += 1

        if i < n_sessions:
            cash += shares_held * S_i * (np.exp(q * dt) - 1.0)
            cash *= np.exp(r * dt)
        cash_path.append(cash)

    S_final = float(prices.iloc[-1])
    payoff = intrinsic_value(S_final, K, option_type)
    final_wealth = option_qty * payoff + shares_held * S_final + cash
    realized_returns = log_returns(prices)
    realized_vol = (
        float(realized_returns.std(ddof=1) * np.sqrt(252))
        if len(realized_returns) > 1
        else float("nan")
    )

    return HedgeEpisodeResult(
        initiation_date=str(prices.index[0].date()),
        expiry_date=str(prices.index[-1].date()),
        rebalance_frequency="daily" if rebalance_every_n_sessions == 1 else "weekly",
        cost_scenario="",  # filled in by caller
        S0=float(prices.iloc[0]),
        K=K,
        initial_vol_assumption=sigma_pricing,
        realized_vol=realized_vol,
        replication_error=float(final_wealth),
        absolute_replication_error=float(abs(final_wealth)),
        transaction_cost=float(total_costs),
        n_rebalances=n_rebalances,
        max_cash_requirement=float(-min(cash_path)) if min(cash_path) < 0 else 0.0,
        rate_used=r,
        dividend_yield_used=q,
    )


def _first_eligible_session_of_each_month(
    index: pd.DatetimeIndex, period: PeriodSpec
) -> list[pd.Timestamp]:
    mask = period.mask(index)
    in_period = index[mask]
    if len(in_period) == 0:
        return []
    df = pd.Series(in_period, index=in_period).to_frame("date")
    df["ym"] = df["date"].dt.to_period("M")
    firsts = df.groupby("ym", sort=True)["date"].min()
    return list(firsts.to_numpy())


def run_hedging_experiment(
    full_prices: pd.Series,
    rate_series: pd.Series,
    eval_period: PeriodSpec,
    *,
    dividend_yield: float = 0.0,
    option_qty: float = -1.0,
) -> dict[str, Any]:
    """Required label: "Historical underlying-path hypothetical option
    hedging experiment". One episode per first-eligible-session-of-month in
    eval_period; each episode replays the ACTUAL next
    OPTION_MATURITY_SESSIONS trading sessions (which may extend past
    eval_period's own end -- disclosed, not hidden). Consecutive monthly
    episodes' 30-session windows overlap (a ~30-trading-day option spans
    more than one calendar month); this is disclosed rather than presented
    as independent draws.

    Dividend handling: this engine does not model discrete dividend dates,
    only a continuous yield q -- passed here as 0.0 by default (disclosed,
    not silently assumed to be some nonzero market yield) unless the caller
    supplies an actual validated estimate."""
    returns = log_returns(full_prices)
    initiations = _first_eligible_session_of_each_month(
        _datetime_index(full_prices.index), eval_period
    )

    episodes: list[dict[str, Any]] = []
    skipped_insufficient_data = 0
    for init_date in initiations:
        idx_pos = full_prices.index.get_indexer(pd.DatetimeIndex([init_date]))[0]
        ret_pos = returns.index.get_indexer(pd.DatetimeIndex([init_date]))
        ret_pos_val = int(ret_pos[0]) if len(ret_pos) and ret_pos[0] != -1 else None
        if ret_pos_val is None or ret_pos_val < REALIZED_VOL_WINDOW_PRIMARY:
            skipped_insufficient_data += 1
            continue
        if idx_pos + OPTION_MATURITY_SESSIONS >= len(full_prices):
            skipped_insufficient_data += 1
            continue

        initial_vol = trailing_realized_vol(returns, ret_pos_val, REALIZED_VOL_WINDOW_PRIMARY)
        if not np.isfinite(initial_vol) or initial_vol <= 0:
            skipped_insufficient_data += 1
            continue

        path = full_prices.iloc[idx_pos : idx_pos + OPTION_MATURITY_SESSIONS + 1]
        S0 = float(path.iloc[0])
        pit_rate = point_in_time_value(rate_series, pd.Timestamp(init_date))

        for _freq_name, n_sessions_per_rebalance in (("daily", 1), ("weekly", 5)):
            for scenario_name, bps in COST_SCENARIOS_BPS.items():
                result = simulate_delta_hedge_on_price_path(
                    path,
                    K=S0,
                    r=pit_rate.value,
                    sigma_pricing=initial_vol,
                    option_type="call",
                    q=dividend_yield,
                    option_qty=option_qty,
                    cost_rate=bps / 10_000.0,
                    rebalance_every_n_sessions=n_sessions_per_rebalance,
                )
                result.cost_scenario = scenario_name
                record = asdict(result)
                record["rate_source"] = "fred_dgs3mo_daily_2015_2025_v1 (point-in-time)"
                record["rate_as_of"] = str(pit_rate.as_of_date.date())
                record["rate_staleness_days"] = pit_rate.staleness_sessions
                episodes.append(record)

    def _agg(freq: str, scenario: str, field_name: str) -> float | None:
        vals = [
            e[field_name]
            for e in episodes
            if e["rebalance_frequency"] == freq and e["cost_scenario"] == scenario
        ]
        return float(np.mean(vals)) if vals else None

    summary: dict[str, Any] = {}
    for freq in ("daily", "weekly"):
        for scenario in COST_SCENARIOS_BPS:
            key = f"{freq}_{scenario}"
            mean_realized_vol = _agg(freq, scenario, "realized_vol")
            mean_initial_vol = _agg(freq, scenario, "initial_vol_assumption")
            mean_realized_minus_assumed = (
                None
                if mean_realized_vol is None or mean_initial_vol is None
                else mean_realized_vol - mean_initial_vol
            )
            summary[key] = {
                "n_episodes": sum(
                    1
                    for e in episodes
                    if e["rebalance_frequency"] == freq and e["cost_scenario"] == scenario
                ),
                "mean_replication_error": _agg(freq, scenario, "replication_error"),
                "mean_absolute_replication_error": _agg(
                    freq, scenario, "absolute_replication_error"
                ),
                "mean_transaction_cost": _agg(freq, scenario, "transaction_cost"),
                "mean_n_rebalances": _agg(freq, scenario, "n_rebalances"),
                "mean_realized_vol": mean_realized_vol,
                "mean_initial_vol_assumption": mean_initial_vol,
                "mean_realized_minus_assumed_vol": mean_realized_minus_assumed,
                "mean_max_cash_requirement": _agg(freq, scenario, "max_cash_requirement"),
            }

    return {
        "label": "Historical underlying-path hypothetical option hedging experiment",
        "standardized_option": {
            "type": "European call",
            "moneyness": "ATM at initiation (K = S0)",
            "maturity_sessions": OPTION_MATURITY_SESSIONS,
            "position": "short one option",
        },
        "primary_rebalance_frequency": "daily",
        "secondary_rebalance_frequency": "weekly",
        "cost_scenarios_bps": COST_SCENARIOS_BPS,
        "n_episodes_initiated": len(initiations),
        "n_episodes_skipped_insufficient_data": skipped_insufficient_data,
        "note_on_episode_overlap": (
            "Episodes initiate on the first eligible session of each calendar month, but each "
            "spans OPTION_MATURITY_SESSIONS (=30) trading sessions -- roughly 1.4 calendar "
            "months -- so consecutive episodes' underlying-path windows overlap. Reported "
            "cross-episode statistics are means over overlapping, serially dependent samples, "
            "not independent draws; no independence claim is made."
        ),
        "dividend_handling": (
            f"Continuous dividend yield q={dividend_yield} used uniformly (no discrete "
            "dividend-date modeling in this engine). Disclosed rather than silently assumed: "
            "if q=0.0 here, no dividend carry is modeled for this run."
        ),
        "summary_by_frequency_and_cost_scenario": summary,
        "episodes": episodes,
    }


# --------------------------------------------------------------------------
# D9-C STANDARDIZED NONLINEAR PORTFOLIO
# --------------------------------------------------------------------------


def build_standardized_portfolio(
    S0: float, T: float, r: float, sigma: float, q: float, *, put_moneyness: float = 0.95
) -> Portfolio:
    """+100 SPY-equivalent shares, -2 ATM 30-trading-day calls, +2
    95%-moneyness 30-trading-day puts. Required label: "Hypothetical
    nonlinear portfolio evaluated on historical risk-factor paths" -- this
    is a standardized construct, never presented as an observed historical
    position."""
    equity = EquityPosition(symbol="SPY", quantity=100.0, price=S0)
    call = OptionPosition(
        symbol="SPY", option_type="call", quantity=-2.0, strike=S0, T=T, S=S0, r=r, sigma=sigma, q=q
    )
    put = OptionPosition(
        symbol="SPY",
        option_type="put",
        quantity=2.0,
        strike=S0 * put_moneyness,
        T=T,
        S=S0,
        r=r,
        sigma=sigma,
        q=q,
    )
    return Portfolio(positions=[equity, call, put])


def _historical_log_returns_window(
    returns: pd.Series, end_index: int, lookback: int
) -> np.ndarray | None:
    if end_index < lookback:
        return None
    return returns.iloc[end_index - lookback : end_index].to_numpy()


def _bsm_price_vectorized(
    S: np.ndarray, K: float, T: float, r: float, sigma: float, option_type: OptionType, q: float
) -> np.ndarray:
    """Vectorized BSM price over an array of spot draws `S`, for fixed
    K/T/r/sigma/q -- algebraically identical to
    options_risk.pricing.black_scholes.bsm_price's T>0, sigma>0 branch (the
    only branch reachable here: every call site guards T=OPTION_MATURITY_
    SESSIONS/252 > 0 and sigma=trailing realized vol > 0 upstream). Exists
    solely so full_revaluation_mc_var_es can full-revalue 50,000 draws in
    one array op instead of 50,000 scalar Python calls."""
    d1 = (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    df_r = np.exp(-r * T)
    df_q = np.exp(-q * T)
    if option_type == "call":
        return S * df_q * norm.cdf(d1) - K * df_r * norm.cdf(d2)
    return K * df_r * norm.cdf(-d2) - S * df_q * norm.cdf(-d1)


def full_revaluation_mc_var_es(
    portfolio: Portfolio,
    *,
    mean_return: float,
    vol: float,
    n_sims: int,
    horizon: int,
    confidence_level: float,
    seed: int | None,
) -> LossDistributionSummary:
    """Vectorized reimplementation of options_risk.risk.var.monte_carlo_var's
    exact methodology (iid-normal single-factor shock, fixed seed, full
    revaluation of every position) -- NOT an approximation. The reference
    implementation reprices each of n_sims draws through
    dataclasses.replace()+Portfolio.market_value() one Python object at a
    time; at the D9-C spec's own 50,000-sim cadence, applied at every
    quarterly full-VaR-ES snapshot across a 9-year formation window, that
    scalar loop is computationally impractical for this study (empirically
    ~110s per single 50,000-sim/one-confidence-level call). This function
    draws the SAME rng sequence (np.random.default_rng(seed).normal(...))
    and full-revalues every position under every draw with the SAME
    closed-form BSM formula, then feeds the same options_risk.risk.var.
    compute_var_es(...) used by every other VaR method here -- so results
    match the reference monte_carlo_var to floating-point tolerance (see
    tests/test_historical_risk_study_v2.py). Only spot is shocked (the only
    scenario type this study's Monte Carlo ever applies), matching
    Scenario(spot_shock_pct=...) semantics in options_risk.stress.scenario.
    """
    rng = np.random.default_rng(seed)
    horizon_mean = mean_return * horizon
    horizon_vol = vol * np.sqrt(horizon)
    simulated_returns = rng.normal(horizon_mean, horizon_vol, size=n_sims)
    spot_shocks = np.exp(simulated_returns) - 1.0

    mv_before = portfolio.market_value()
    mv_after = np.zeros(n_sims)
    for position in portfolio.positions:
        if isinstance(position, EquityPosition):
            mv_after += position.quantity * position.price * (1.0 + spot_shocks)
        elif isinstance(position, OptionPosition):
            s_shocked = position.S * (1.0 + spot_shocks)
            prices = _bsm_price_vectorized(
                s_shocked,
                position.strike,
                position.T,
                position.r,
                position.sigma,
                position.option_type,
                position.q,
            )
            mv_after += position.quantity * position.multiplier * prices
        elif isinstance(position, CashPosition):
            mv_after += position.amount
        else:
            raise TypeError(f"unsupported position type for vectorized MC: {type(position)!r}")

    losses = -(mv_after - mv_before)
    var, es = compute_var_es(losses, confidence_level)
    return LossDistributionSummary(
        confidence_level=confidence_level,
        horizon=horizon,
        n_obs=n_sims,
        var=var,
        es=es,
        mean_loss=float(losses.mean()),
        std_loss=float(losses.std(ddof=1)),
        min_loss=float(losses.min()),
        max_loss=float(losses.max()),
        losses=losses,
    )


def var_es_all_methods(
    portfolio: Portfolio,
    hs_returns_primary: np.ndarray,
    hs_returns_sensitivity: np.ndarray | None,
    *,
    mc_vol: float,
    confidence_level: float,
    mc_n_sims: int = MC_N_SIMS,
    mc_seed: int = MC_SEED,
) -> dict[str, Any]:
    """Historical Simulation (252 + 504-session sensitivity), Delta-Normal,
    and Monte Carlo (50,000 sims, fixed seed, full nonlinear revaluation)
    VaR/ES for one confidence level. No antithetic sampling -- not
    implemented in this release, so not claimed."""
    hs_primary = historical_simulation_var(
        portfolio,
        hs_returns_primary,
        confidence_level=confidence_level,
        return_type="log",
        horizon=1,
    )
    hs_sensitivity: LossDistributionSummary | None = None
    if hs_returns_sensitivity is not None:
        hs_sensitivity = historical_simulation_var(
            portfolio,
            hs_returns_sensitivity,
            confidence_level=confidence_level,
            return_type="log",
            horizon=1,
        )
    g = portfolio.greeks()
    S0 = next(p.price for p in portfolio.positions if isinstance(p, EquityPosition))
    # portfolio.greeks().delta is share-equivalent (quantity/quantity*multiplier
    # scaled, per options_risk.portfolio.positions), not dollar-scaled -- must
    # multiply by the underlying's own price to get dollar delta, matching how
    # options_risk.hedging.delta_hedge and the v1 module's own snapshot do it.
    dollar_delta = float(g.delta) * S0
    dn = delta_normal_var(
        dollar_delta=dollar_delta, factor_vol=mc_vol, confidence_level=confidence_level, horizon=1
    )
    mc = full_revaluation_mc_var_es(
        portfolio,
        mean_return=0.0,
        vol=mc_vol,
        n_sims=mc_n_sims,
        horizon=1,
        confidence_level=confidence_level,
        seed=mc_seed,
    )
    return {
        "confidence_level": confidence_level,
        "historical_simulation_primary": {
            "lookback": HS_LOOKBACKS["primary"],
            "var": hs_primary.var,
            "es": hs_primary.es,
            "n_obs": hs_primary.n_obs,
        },
        "historical_simulation_sensitivity": (
            None
            if hs_sensitivity is None
            else {
                "lookback": HS_LOOKBACKS["sensitivity"],
                "var": hs_sensitivity.var,
                "es": hs_sensitivity.es,
                "n_obs": hs_sensitivity.n_obs,
            }
        ),
        "delta_normal": {
            "var": dn.var,
            "es": dn.es,
            "portfolio_dollar_delta": dn.portfolio_dollar_delta,
            "factor_vol": dn.factor_vol,
        },
        "monte_carlo": {
            "var": mc.var,
            "es": mc.es,
            "n_sims": mc_n_sims,
            "seed": mc_seed,
            "n_obs": mc.n_obs,
            "antithetic_sampling": "not included in this release",
        },
    }


def run_nonlinear_portfolio_study(
    full_prices: pd.Series,
    rate_series: pd.Series,
    vix_series: pd.Series,
    eval_period: PeriodSpec,
    *,
    dividend_yield: float = 0.0,
    mc_n_sims: int = MC_N_SIMS,
    mc_seed: int = MC_SEED,
) -> dict[str, Any]:
    """The standardized portfolio rolls monthly (per spec); every eligible
    monthly roll gets the full three-method, two-confidence-level VaR/ES
    snapshot (historical simulation, delta-normal, and a 50,000-simulation
    Monte Carlo full revaluation via full_revaluation_mc_var_es, which is
    vectorized rather than the reference scalar options_risk.risk.var.
    monte_carlo_var -- see that function's docstring). The Kupiec/
    Christoffersen backtest at the bottom draws one HS-primary-95% VaR
    forecast from every roll's own snapshot."""
    returns = log_returns(full_prices)
    roll_dates = _first_eligible_session_of_each_month(
        _datetime_index(full_prices.index), eval_period
    )
    T = OPTION_MATURITY_SESSIONS / 252.0

    snapshots: list[dict[str, Any]] = []
    all_daily_losses: list[float] = []
    all_daily_vars_95: list[float] = []

    for roll_date in roll_dates:
        idx_pos = int(full_prices.index.get_indexer(pd.DatetimeIndex([roll_date]))[0])
        ret_pos = returns.index.get_indexer(pd.DatetimeIndex([roll_date]))
        ret_pos_val = int(ret_pos[0]) if len(ret_pos) and ret_pos[0] != -1 else None
        if ret_pos_val is None or ret_pos_val < HS_LOOKBACKS["primary"]:
            continue
        S0 = float(full_prices.iloc[idx_pos])
        vol20 = trailing_realized_vol(returns, ret_pos_val, REALIZED_VOL_WINDOW_PRIMARY)
        vol60 = trailing_realized_vol(returns, ret_pos_val, REALIZED_VOL_WINDOW_SECONDARY)
        if not np.isfinite(vol20) or vol20 <= 0:
            continue
        pit_rate = point_in_time_value(rate_series, pd.Timestamp(roll_date))
        try:
            pit_vix = point_in_time_value(vix_series, pd.Timestamp(roll_date))
            vix_context = pit_vix.value
        except ValueError:
            vix_context = None

        portfolio = build_standardized_portfolio(S0, T, pit_rate.value, vol20, dividend_yield)
        hs_primary_window = _historical_log_returns_window(
            returns, ret_pos_val, HS_LOOKBACKS["primary"]
        )
        # Guaranteed non-None: the `ret_pos_val < HS_LOOKBACKS["primary"]`
        # guard above already `continue`s otherwise.
        assert hs_primary_window is not None

        hs_sensitivity_window = _historical_log_returns_window(
            returns, ret_pos_val, HS_LOOKBACKS["sensitivity"]
        )
        by_confidence: dict[str, Any] = {}
        for conf_name, conf_level in CONFIDENCE_LEVELS.items():
            by_confidence[conf_name] = var_es_all_methods(
                portfolio,
                hs_primary_window,
                hs_sensitivity_window,
                mc_vol=vol20,
                confidence_level=conf_level,
                mc_n_sims=mc_n_sims,
                mc_seed=mc_seed,
            )
        # The Kupiec/Christoffersen backtest below draws its per-roll VaR
        # forecast from this same snapshot's own 95% historical-simulation
        # leg, rather than a separate call.
        hs_95_only = by_confidence["primary"]["historical_simulation_primary"]

        snapshots.append(
            {
                "roll_date": str(pd.Timestamp(roll_date).date()),
                "S0": S0,
                "realized_vol_20d": vol20,
                "realized_vol_60d_sensitivity": vol60 if np.isfinite(vol60) else None,
                "rate_used": pit_rate.value,
                "rate_as_of": str(pit_rate.as_of_date.date()),
                "vixcls_context": vix_context,
                "portfolio_market_value": portfolio.market_value(),
                "portfolio_greeks": asdict(portfolio.greeks()),
                "hs_var_95_primary_every_roll": hs_95_only["var"],
                "var_es": by_confidence,
            }
        )

        # Next-session realized P&L vs this roll's 95% VaR forecast, for Kupiec/Christoffersen.
        if idx_pos + 1 < len(full_prices):
            next_return = float(returns.iloc[ret_pos_val]) if ret_pos_val < len(returns) else None
            if next_return is not None:
                scenario = Scenario(
                    name="next_day", spot_shock_pct=float(np.exp(next_return) - 1.0)
                )
                pnl = revalue_portfolio(portfolio, scenario).pnl
                all_daily_losses.append(-pnl)
                all_daily_vars_95.append(hs_95_only["var"])

    backtest: dict[str, Any] | None = None
    if len(all_daily_losses) >= 10:
        losses_arr = np.asarray(all_daily_losses)
        vars_arr = np.asarray(all_daily_vars_95)
        breaches = breaches_from_losses(losses_arr, vars_arr)
        kupiec = kupiec_pof_test(breaches, CONFIDENCE_LEVELS["primary"])
        christ = christoffersen_independence_test(breaches, CONFIDENCE_LEVELS["primary"])
        backtest = {
            "n_forecasts": int(len(losses_arr)),
            "confidence_level": CONFIDENCE_LEVELS["primary"],
            "note": (
                "One forecast per monthly roll date's own next trading session "
                "(HS-primary VaR vs realized full-revaluation P&L) -- a small, "
                "monthly-cadence sample, not a daily rolling backtest; interpret "
                "accordingly (see sample_size_caveat on each test result)."
            ),
            "kupiec": {
                "test_name": kupiec.test_name,
                "n_obs": kupiec.n_obs,
                "n_breaches": kupiec.n_breaches,
                "breach_rate": kupiec.breach_rate,
                "expected_breach_rate": kupiec.expected_breach_rate,
                "p_value": kupiec.p_value,
                "reject_null": kupiec.reject_null,
                "conclusion": kupiec.conclusion,
                "sample_size_caveat": kupiec.sample_size_caveat,
            },
            "christoffersen": {
                "test_name": christ.test_name,
                "n_obs": christ.n_obs,
                "n_breaches": christ.n_breaches,
                "p_value": christ.p_value,
                "reject_null": christ.reject_null,
                "conclusion": christ.conclusion,
                "sample_size_caveat": christ.sample_size_caveat,
            },
        }
    else:
        backtest = {
            "note": "insufficient roll dates for a Kupiec/Christoffersen backtest in this period"
        }

    return {
        "label": "Hypothetical nonlinear portfolio evaluated on historical risk-factor paths",
        "standardized_portfolio": {
            "equity_shares": 100.0,
            "calls": {
                "quantity": -2.0,
                "moneyness": "ATM",
                "maturity_sessions": OPTION_MATURITY_SESSIONS,
            },
            "puts": {
                "quantity": 2.0,
                "moneyness": "95%",
                "maturity_sessions": OPTION_MATURITY_SESSIONS,
            },
            "roll_frequency": "monthly (first eligible session of each month)",
        },
        "confidence_levels": CONFIDENCE_LEVELS,
        "hs_lookbacks": HS_LOOKBACKS,
        "monte_carlo_n_sims": mc_n_sims,
        "monte_carlo_seed": mc_seed,
        "monte_carlo_note": (
            "Monte Carlo VaR/ES uses full_revaluation_mc_var_es, a vectorized "
            "reimplementation of options_risk.risk.var.monte_carlo_var's identical "
            "methodology (same rng draws, same closed-form BSM full revaluation, "
            "same compute_var_es) -- validated to match the reference scalar "
            "implementation to floating-point tolerance. Every eligible monthly "
            "roll gets the full three-method, two-confidence-level VaR/ES snapshot; "
            "no cadence reduction was needed."
        ),
        "n_roll_snapshots": len(snapshots),
        "snapshots": snapshots,
        "kupiec_christoffersen_backtest": backtest,
    }
