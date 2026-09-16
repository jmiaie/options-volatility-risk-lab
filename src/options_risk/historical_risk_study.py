"""Directive #9 historical options/risk validation helpers.

Uses existing lab capabilities only:
- realized volatility from underlying closes
- VaR/ES via ``options_risk.risk.var`` (HS + delta-normal)
- Kupiec / Christoffersen / conditional coverage via ``options_risk.risk.backtesting``
- discrete delta-hedging error via ``options_risk.hedging.delta_hedge``

Honest limitations:
- No paid options tapes / no invented option panels.
- Option-book HS VaR uses a *stylized* short ATM European call marked with
  formation-period realized vol (BSM), shocked by historical underlying returns.
- Hedging paths are GBM calibrated to empirical vols — not listed-option paths.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd

from options_risk.hedging.delta_hedge import simulate_delta_hedge
from options_risk.portfolio.portfolio import Portfolio
from options_risk.portfolio.positions import EquityPosition, OptionPosition
from options_risk.risk.backtesting import (
    breaches_from_losses,
    christoffersen_independence_test,
    conditional_coverage_test,
    kupiec_pof_test,
)
from options_risk.risk.var import (
    compute_var_es,
    delta_normal_var,
    historical_simulation_var,
)


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
    """load_close_panel() always parses dates (parse_dates=True), so every
    price Series' index genuinely is a DatetimeIndex at runtime; pandas-stubs
    types DataFrame column access as returning the generic Index, so this
    documents and narrows that known-true fact for PeriodSpec.mask()."""
    return cast(pd.DatetimeIndex, index)


def load_close_panel(raw_dir: Path, symbols: list[str]) -> pd.DataFrame:
    frames: dict[str, pd.Series] = {}
    for symbol in symbols:
        path = raw_dir / f"{symbol}.csv"
        if not path.exists():
            raise FileNotFoundError(f"missing raw file: {path}")
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        if "Close" not in df.columns:
            raise ValueError(f"{path} missing Close column")
        frames[symbol] = df["Close"].astype(float)
    panel = pd.DataFrame(frames).sort_index()
    panel = panel.dropna(how="any")
    return panel


def log_returns(prices: pd.Series) -> pd.Series:
    ratio = prices / prices.shift(1)
    # np.log() on a Series is typed by numpy's stubs as returning an ndarray
    # (it actually returns a Series at runtime via __array_ufunc__); rebuild
    # the Series explicitly so downstream .dropna() has a correct static type.
    logged = pd.Series(np.log(ratio.to_numpy()), index=ratio.index)
    return logged.dropna()


def realized_vol_annualized(returns: pd.Series, window: int = 21) -> float:
    if len(returns) < window:
        return float("nan")
    return float(returns.tail(window).std(ddof=1) * np.sqrt(252))


def period_realized_vol(returns: pd.Series) -> float:
    if len(returns) < 2:
        return float("nan")
    return float(returns.std(ddof=1) * np.sqrt(252))


def write_json_artifact(path: Path, payload: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True, default=_json_default) + "\n"
    path.write_text(text, encoding="utf-8")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _json_default(obj: Any) -> Any:
    if isinstance(obj, (np.floating, np.integer)):
        return obj.item()
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (pd.Timestamp,)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)!r} is not JSON serializable")


def _backtest_result_dict(result: Any) -> dict[str, Any]:
    return {
        "test_name": result.test_name,
        "n_obs": result.n_obs,
        "n_breaches": result.n_breaches,
        "expected_breaches": result.expected_breaches,
        "breach_rate": result.breach_rate,
        "expected_breach_rate": result.expected_breach_rate,
        "lr_statistic": result.lr_statistic,
        "degrees_of_freedom": result.degrees_of_freedom,
        "p_value": result.p_value,
        "significance_level": result.significance_level,
        "reject_null": result.reject_null,
        "conclusion": result.conclusion,
        "sample_size_caveat": result.sample_size_caveat,
    }


def rolling_hs_var_backtest(
    returns: pd.Series,
    *,
    lookback: int,
    confidence_level: float,
    notional: float,
) -> dict[str, Any]:
    """Point-in-time rolling historical-simulation VaR backtest on equity P&L.

    Loss_t = -r_t * notional (log-return approx for unit equity book).
    VaR_t uses only returns in [t-lookback, t) — no peeking.
    """
    r = returns.dropna().astype(float)
    if len(r) <= lookback + 1:
        return {
            "n_forecasts": 0,
            "kupiec": None,
            "christoffersen": None,
            "conditional_coverage": None,
            "notes": "insufficient observations for rolling VaR backtest",
        }

    losses_list: list[float] = []
    vars_list: list[float] = []
    for i in range(lookback, len(r)):
        hist = r.iloc[i - lookback : i].to_numpy()
        hist_losses = -hist * notional
        var_i, _es_i = compute_var_es(hist_losses, confidence_level)
        realized_loss = float(-r.iloc[i] * notional)
        losses_list.append(realized_loss)
        vars_list.append(float(var_i))

    losses_arr = np.asarray(losses_list, dtype=float)
    vars_arr = np.asarray(vars_list, dtype=float)
    breaches = breaches_from_losses(losses_arr, vars_arr)
    kupiec = kupiec_pof_test(breaches, confidence_level)
    christ = christoffersen_independence_test(breaches, confidence_level)
    cond = conditional_coverage_test(breaches, confidence_level)
    return {
        "n_forecasts": int(len(losses_arr)),
        "lookback": lookback,
        "confidence_level": confidence_level,
        "notional": notional,
        "mean_realized_loss": float(losses_arr.mean()),
        "mean_var": float(vars_arr.mean()),
        "kupiec": _backtest_result_dict(kupiec),
        "christoffersen": _backtest_result_dict(christ),
        "conditional_coverage": _backtest_result_dict(cond),
    }


def equity_and_option_var_snapshot(
    spot: float,
    shock_returns: np.ndarray,
    *,
    formation_vol: float,
    confidence_level: float,
    equity_shares: float,
    option_contracts: float,
    option_T: float,
    rate: float,
    dividend_yield: float,
    multiplier: float,
) -> dict[str, Any]:
    """One-shot HS + delta-normal VaR, as of the eval period's first bar, on a
    stylized equity + short ATM call book.

    ``shock_returns`` must be a trailing window of returns dated BEFORE the
    eval period starts (e.g. the tail of the formation period) -- this is
    what makes the estimate a genuine as-of-that-date VaR forecast rather
    than a retrospective characterization built from information the
    position holder would not yet have had. historical_simulation_var's own
    docstring states this same requirement ("uses only a rolling window of
    past returns"); an earlier version of this function violated it for
    both the historical-simulation shocks and the delta-normal factor vol by
    passing the eval period's own returns.
    """
    equity = EquityPosition(symbol="UNDERLYING", quantity=equity_shares, price=spot)
    opt = OptionPosition(
        symbol="UNDERLYING",
        option_type="call",
        quantity=option_contracts,
        strike=float(spot),
        T=option_T,
        S=float(spot),
        r=rate,
        sigma=float(formation_vol),
        q=dividend_yield,
        multiplier=multiplier,
    )
    portfolio = Portfolio(positions=[equity, opt])
    hs = historical_simulation_var(
        portfolio,
        shock_returns,
        confidence_level=confidence_level,
        return_type="log",
        horizon=1,
    )
    g = portfolio.greeks()
    dollar_delta = float(g.delta) * float(spot)
    dn = delta_normal_var(
        dollar_delta=dollar_delta,
        factor_vol=float(np.std(shock_returns, ddof=1)),
        confidence_level=confidence_level,
        horizon=1,
    )
    return {
        "spot": float(spot),
        "formation_vol_used_for_option_mark": float(formation_vol),
        "n_shock_returns": int(len(shock_returns)),
        "portfolio_share_delta": float(g.delta),
        "portfolio_dollar_delta": float(dollar_delta),
        "portfolio_gamma": float(g.gamma),
        "portfolio_vega": float(g.vega),
        "historical_simulation": {
            "var": hs.var,
            "es": hs.es,
            "mean_loss": hs.mean_loss,
            "std_loss": hs.std_loss,
            "min_loss": hs.min_loss,
            "max_loss": hs.max_loss,
            "confidence_level": hs.confidence_level,
            "n_obs": hs.n_obs,
        },
        "delta_normal": {
            "var": dn.var,
            "es": dn.es,
            "portfolio_dollar_delta": dn.portfolio_dollar_delta,
            "factor_vol": dn.factor_vol,
            "pnl_std": dn.pnl_std,
            "confidence_level": dn.confidence_level,
        },
        "notes": (
            "Option mark uses formation-period realized vol as BSM sigma — "
            "not market implied vol. No options tape used. Historical-"
            "simulation shocks and delta-normal factor vol are drawn from a "
            "trailing pre-eval-period window (the formation tail), not the "
            "eval period's own returns, so this is a genuine as-of-start-of-"
            "period VaR estimate, not a retrospective one."
        ),
    }


def hedging_error_study(
    *,
    spot: float,
    formation_vol: float,
    realized_vol: float,
    rate: float,
    dividend_yield: float,
    option_T: float,
    n_steps: int,
    cost_rate: float,
    n_seeds: int,
    option_qty: float,
) -> dict[str, Any]:
    """GBM discrete-hedge error under empirically calibrated vols."""
    wealths: list[float] = []
    costs: list[float] = []
    for seed in range(n_seeds):
        result = simulate_delta_hedge(
            S0=spot,
            K=spot,
            T=option_T,
            r=rate,
            sigma_pricing=formation_vol,
            option_type="call",
            q=dividend_yield,
            sigma_realized=realized_vol,
            option_qty=option_qty,
            n_steps=n_steps,
            cost_rate=cost_rate,
            seed=seed,
        )
        wealths.append(float(result.final_wealth))
        costs.append(float(result.total_transaction_costs))
    w = np.asarray(wealths, dtype=float)
    c = np.asarray(costs, dtype=float)
    return {
        "n_seeds": n_seeds,
        "n_steps": n_steps,
        "cost_rate": cost_rate,
        "option_qty": option_qty,
        "sigma_pricing_formation": float(formation_vol),
        "sigma_realized_eval": float(realized_vol),
        "mean_final_wealth": float(w.mean()),
        "std_final_wealth": float(w.std(ddof=1)) if len(w) > 1 else 0.0,
        "mean_total_costs": float(c.mean()),
        "notes": (
            "Paths are risk-neutral GBM with empirically estimated vols — "
            "not historical listed-option paths."
        ),
    }


def run_period_study(
    *,
    full_panel: pd.DataFrame,
    formation: PeriodSpec,
    eval_period: PeriodSpec,
    config: dict[str, Any],
    primary_symbol: str,
    allow_holdout: bool = False,
) -> dict[str, Any]:
    status = str(config.get("status", ""))
    if eval_period.name == "holdout":
        if status != "frozen-for-holdout" or not allow_holdout:
            raise RuntimeError(
                "Holdout evaluation blocked until config status is "
                "frozen-for-holdout and --allow-holdout is set "
                f"(status={status!r}, allow_holdout={allow_holdout})"
            )

    if primary_symbol not in full_panel.columns:
        raise KeyError(f"primary_symbol {primary_symbol!r} not in panel")

    prices = full_panel[primary_symbol].dropna()

    form_mask = formation.mask(_datetime_index(prices.index))
    eval_mask = eval_period.mask(_datetime_index(prices.index))
    form_prices = prices.loc[form_mask]
    eval_prices = prices.loc[eval_mask]
    form_rets = log_returns(form_prices)
    eval_rets = log_returns(eval_prices)

    risk_cfg = config.get("risk", {})
    hedge_cfg = config.get("hedging", {})
    book_cfg = config.get("stylized_book", {})

    lookback = int(risk_cfg.get("var_lookback", 252))
    confidence_level = float(risk_cfg.get("confidence_level", 0.95))
    notional = float(risk_cfg.get("equity_notional", 1.0))
    vol_window = int(risk_cfg.get("realized_vol_window", 21))

    formation_vol = period_realized_vol(form_rets)
    eval_vol = period_realized_vol(eval_rets)
    formation_vol_w = realized_vol_annualized(form_rets, window=vol_window)
    eval_vol_w = realized_vol_annualized(eval_rets, window=vol_window)

    seed_rets = form_rets.tail(lookback)
    backtest_series = pd.concat([seed_rets, eval_rets])
    backtest_series = backtest_series[~backtest_series.index.duplicated(keep="last")]
    bt_full = rolling_hs_var_backtest(
        backtest_series,
        lookback=lookback,
        confidence_level=confidence_level,
        notional=notional,
    )
    r = backtest_series.dropna().astype(float)
    eval_start = eval_rets.index.min() if len(eval_rets) else None
    losses_list: list[float] = []
    vars_list: list[float] = []
    if eval_start is not None and len(r) > lookback:
        for i in range(lookback, len(r)):
            if r.index[i] < eval_start:
                continue
            hist = r.iloc[i - lookback : i].to_numpy()
            hist_losses = -hist * notional
            var_i, _ = compute_var_es(hist_losses, confidence_level)
            losses_list.append(float(-r.iloc[i] * notional))
            vars_list.append(float(var_i))
    equity_var_backtest: dict[str, Any]
    if losses_list:
        losses_arr = np.asarray(losses_list, dtype=float)
        vars_arr = np.asarray(vars_list, dtype=float)
        breaches = breaches_from_losses(losses_arr, vars_arr)
        equity_var_backtest = {
            "n_forecasts": int(len(losses_arr)),
            "lookback": lookback,
            "confidence_level": confidence_level,
            "notional": notional,
            "mean_realized_loss": float(losses_arr.mean()),
            "mean_var": float(vars_arr.mean()),
            "kupiec": _backtest_result_dict(kupiec_pof_test(breaches, confidence_level)),
            "christoffersen": _backtest_result_dict(
                christoffersen_independence_test(breaches, confidence_level)
            ),
            "conditional_coverage": _backtest_result_dict(
                conditional_coverage_test(breaches, confidence_level)
            ),
        }
    else:
        equity_var_backtest = bt_full

    spot = float(eval_prices.iloc[0]) if len(eval_prices) else float(form_prices.iloc[-1])
    option_snapshot = equity_and_option_var_snapshot(
        spot,
        seed_rets.to_numpy(),
        formation_vol=formation_vol if np.isfinite(formation_vol) else 0.2,
        confidence_level=confidence_level,
        equity_shares=float(book_cfg.get("equity_shares", 0.0)),
        option_contracts=float(book_cfg.get("option_contracts", -1.0)),
        option_T=float(book_cfg.get("option_T", 30 / 365)),
        rate=float(book_cfg.get("rate", 0.02)),
        dividend_yield=float(book_cfg.get("dividend_yield", 0.01)),
        multiplier=float(book_cfg.get("multiplier", 100.0)),
    )

    hedge = hedging_error_study(
        spot=spot,
        formation_vol=formation_vol if np.isfinite(formation_vol) else 0.2,
        realized_vol=eval_vol if np.isfinite(eval_vol) else formation_vol,
        rate=float(book_cfg.get("rate", 0.02)),
        dividend_yield=float(book_cfg.get("dividend_yield", 0.01)),
        option_T=float(hedge_cfg.get("option_T", 1.0)),
        n_steps=int(hedge_cfg.get("n_steps", 52)),
        cost_rate=float(hedge_cfg.get("cost_rate", 0.0005)),
        n_seeds=int(hedge_cfg.get("n_seeds", 50)),
        option_qty=float(hedge_cfg.get("option_qty", -1.0)),
    )

    per_symbol_vol: dict[str, Any] = {}
    for symbol in full_panel.columns:
        s_prices = full_panel[symbol].dropna()
        s_form = log_returns(s_prices.loc[formation.mask(_datetime_index(s_prices.index))])
        s_eval = log_returns(s_prices.loc[eval_period.mask(_datetime_index(s_prices.index))])
        per_symbol_vol[symbol] = {
            "formation_realized_vol_ann": period_realized_vol(s_form),
            "eval_realized_vol_ann": period_realized_vol(s_eval),
            "n_formation_returns": int(len(s_form)),
            "n_eval_returns": int(len(s_eval)),
        }

    key_metrics = {
        "primary_symbol": primary_symbol,
        "n_formation_bars": int(form_mask.sum()),
        "n_eval_bars": int(eval_mask.sum()),
        "formation_realized_vol_ann": formation_vol,
        "eval_realized_vol_ann": eval_vol,
        "formation_realized_vol_ann_trailing_window": formation_vol_w,
        "eval_realized_vol_ann_trailing_window": eval_vol_w,
        "equity_var_n_forecasts": equity_var_backtest.get("n_forecasts"),
        "equity_var_breach_rate": (equity_var_backtest.get("kupiec") or {}).get("breach_rate"),
        "equity_var_kupiec_pvalue": (equity_var_backtest.get("kupiec") or {}).get("p_value"),
        "equity_var_kupiec_reject": (equity_var_backtest.get("kupiec") or {}).get("reject_null"),
        "equity_var_christoffersen_pvalue": (equity_var_backtest.get("christoffersen") or {}).get(
            "p_value"
        ),
        "equity_var_christoffersen_reject": (equity_var_backtest.get("christoffersen") or {}).get(
            "reject_null"
        ),
        "option_hs_var": option_snapshot["historical_simulation"]["var"],
        "option_hs_es": option_snapshot["historical_simulation"]["es"],
        "option_dn_var": option_snapshot["delta_normal"]["var"],
        "hedge_mean_final_wealth": hedge["mean_final_wealth"],
        "hedge_std_final_wealth": hedge["std_final_wealth"],
        "hedge_mean_total_costs": hedge["mean_total_costs"],
    }

    return {
        "formation": asdict(formation),
        "eval_period": asdict(eval_period),
        "primary_symbol": primary_symbol,
        "realized_vol": {
            "window": vol_window,
            "primary": {
                "formation_full_sample_ann": formation_vol,
                "eval_full_sample_ann": eval_vol,
                "formation_trailing_window_ann": formation_vol_w,
                "eval_trailing_window_ann": eval_vol_w,
            },
            "per_symbol": per_symbol_vol,
        },
        "equity_rolling_hs_var_backtest": equity_var_backtest,
        "stylized_option_book_var": option_snapshot,
        "discrete_hedging_error": hedge,
        "key_metrics": key_metrics,
        "notes": (
            "Underlyings-only historical validation. Stylized option book uses "
            "formation realized vol as BSM mark (not market IV). Hedging uses "
            "GBM paths calibrated to empirical vols. No options tape."
        ),
    }
