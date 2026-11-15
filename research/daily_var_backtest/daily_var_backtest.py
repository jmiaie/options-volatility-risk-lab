"""Daily VaR/ES backtest harness for the standardised options book (library of pure functions).

Implements the pre-registered design in research/daily_var_backtest/PROTOCOL.md (a frozen copy is
added separately). The book is the published standardised book, re-marked every session at
sigma = VIX/100. Section references (S4, S5, ...) are to that protocol.

Revaluation inside the harness is vectorised closed-form Black-Scholes (the same formula as
``options_risk.pricing.black_scholes``); ``portfolio_for_book`` and ``portfolio_scenario_loss``
build the same book through ``build_standardized_portfolio`` and ``revalue_portfolio`` so the two
paths can be tied together in tests and in precondition P1.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import numpy as np
import pandas as pd
from scipy.special import ndtr
from scipy.stats import binom, norm

from options_risk.historical_risk_study_v2 import build_standardized_portfolio
from options_risk.portfolio.portfolio import Portfolio
from options_risk.portfolio.positions import EquityPosition, OptionPosition
from options_risk.pricing.black_scholes import bsm_price
from options_risk.risk.backtesting import (
    christoffersen_independence_test,
    kupiec_pof_test,
)
from options_risk.risk.var import compute_var_es
from options_risk.stress.scenario import Scenario, revalue_portfolio

WINDOW = 252
MATURITY_SESSIONS = 30
PUT_MONEYNESS = 0.95
YEAR_SESSIONS = 252.0
LEVELS = (0.95, 0.975, 0.99)
SEED_PIT = [20261114, 1]
SEED_AS = [20261114, 2]
SEED_P4_PREFIX = [20261114, 3]
VIX_MAX_STALENESS = 5
P4_BAND = (0.03, 0.08)
AS_N_SIM = 10_000
ES_TAIL = 0.025  # alpha' for T3 and Z2 (97.5% level)
PERIODS = {"DEV": ("2016-01-01", "2023-12-31"), "VAL2024": ("2024-01-01", "2024-12-31")}
PERIODS["2025"] = ("2025-01-01", "2025-12-31")


# --------------------------------------------------------------------------
# Data frame
# --------------------------------------------------------------------------


def prepare_frame(
    spy: pd.Series, vix: pd.Series, rate: pd.Series
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Align SPY close (price), VIX close (level, e.g. 20.0) and rate (decimal) on SPY sessions.

    Columns: spot, vix, rate, sess (the SPY session number, so gaps left by dropped days stay
    visible). A missing VIX is carried forward from the last observation dated on or before the
    day (counted). A day whose last observation is more than 5 SPY sessions old, or that has none,
    is dropped (counted). The rate is carried forward without limit; days with no rate yet are
    dropped (counted).
    """
    spy = spy.sort_index().astype(float)
    n = len(spy)
    sess = np.arange(n)
    vix_obs = vix.dropna().sort_index()
    rate_obs = rate.dropna().sort_index()

    def _asof(obs: pd.Series) -> tuple[np.ndarray, np.ndarray]:
        pos = obs.index.searchsorted(spy.index, side="right") - 1
        values = np.where(pos >= 0, obs.to_numpy()[np.clip(pos, 0, None)], np.nan)
        # SPY session number of the last SPY session dated on or before the observation date
        obs_sess = spy.index.searchsorted(obs.index, side="right") - 1
        stale = np.where(pos >= 0, sess - obs_sess[np.clip(pos, 0, None)], 10**9)
        return values, stale

    v_vals, v_stale = _asof(vix_obs)
    r_vals, _ = _asof(rate_obs)
    carried = (v_stale >= 1) & (v_stale <= VIX_MAX_STALENESS)
    no_vix = v_stale > VIX_MAX_STALENESS
    no_rate = np.isnan(r_vals) & ~no_vix
    keep = ~no_vix & ~np.isnan(r_vals)
    quality = {
        "spy_sessions": int(n),
        "vix_carried_forward": int((carried & keep).sum()),
        "dropped_no_recent_vix": int(no_vix.sum()),
        "dropped_no_rate": int(no_rate.sum()),
        "kept_sessions": int(keep.sum()),
    }
    frame = pd.DataFrame(
        {"spot": spy.to_numpy(), "vix": v_vals, "rate": r_vals, "sess": sess}, index=spy.index
    )[keep]
    if (frame["spot"] <= 0).any() or (frame["vix"] <= 0).any():
        raise ValueError("non-positive spot or VIX in input")
    return frame, quality


# --------------------------------------------------------------------------
# Pricing and the book
# --------------------------------------------------------------------------


def _bs_price(
    S: np.ndarray, K: np.ndarray, T: np.ndarray, r: np.ndarray, sigma: np.ndarray, is_call: bool
) -> np.ndarray:
    """Vectorised Black-Scholes (q = 0), same formula as options_risk.pricing.bsm_price."""
    sd = sigma * np.sqrt(T)
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / sd
    d2 = d1 - sd
    disc = K * np.exp(-r * T)
    if is_call:
        return S * ndtr(d1) - disc * ndtr(d2)
    return disc * ndtr(-d2) - S * ndtr(-d1)


def book_value(S: Any, roll_spot: Any, T: Any, r: Any, sigma: Any) -> np.ndarray:
    """Value of +100 shares, -2 ATM calls, +2 95% puts (100 multiplier), strikes set at roll."""
    S, K, T, r, sigma = np.broadcast_arrays(
        *(np.asarray(a, dtype=float) for a in (S, roll_spot, T, r, sigma))
    )
    if (T <= 0).any() or (sigma <= 0).any():
        raise ValueError("book_value needs T > 0 and sigma > 0")
    call = _bs_price(S, K, T, r, sigma, True)
    put = _bs_price(S, PUT_MONEYNESS * K, T, r, sigma, False)
    return 100.0 * S - 200.0 * call + 200.0 * put


def portfolio_for_book(roll_spot: float, S: float, T: float, r: float, sigma: float) -> Portfolio:
    """The same book as a Portfolio, via the published build_standardized_portfolio.

    Strikes are fixed at the roll spot; spot, time, rate and sigma are the current mark.
    """
    base = build_standardized_portfolio(roll_spot, T, r, sigma, 0.0, put_moneyness=PUT_MONEYNESS)
    positions: list[Any] = []
    for p in base.positions:
        if isinstance(p, EquityPosition):
            positions.append(dataclasses.replace(p, price=S))
        elif isinstance(p, OptionPosition):
            positions.append(dataclasses.replace(p, S=S))
        else:
            positions.append(p)
    return Portfolio(positions=positions)


def portfolio_scenario_loss(
    portfolio: Portfolio, log_return: float, dlog_vix: float, decay_years: float
) -> float:
    """Loss of one scenario through the production full-revaluation engine."""
    scenario = Scenario(
        name="s",
        spot_shock_pct=float(np.exp(log_return) - 1.0),
        vol_shock_mult=float(np.exp(dlog_vix)),
        time_decay_years=decay_years,
    )
    return -revalue_portfolio(portfolio, scenario).pnl


@dataclasses.dataclass(frozen=True)
class BookState:
    roll_spot: np.ndarray  # strike reference of the book held at each row
    T: np.ndarray  # years to expiry at each row's close
    is_roll: np.ndarray  # row is a roll day (new book built at its close)


def book_state(frame: pd.DataFrame) -> BookState:
    """Monthly roll on the first kept session of each calendar month; T falls one per SPY session.

    Row 0 starts the first book. Uses only rows up to each date (causal).
    """
    n = len(frame)
    months = frame.index.to_period("M")
    is_roll = np.ones(n, dtype=bool)
    is_roll[1:] = months[1:] != months[:-1]
    sess = frame["sess"].to_numpy()
    spot = frame["spot"].to_numpy()
    last_roll = np.maximum.accumulate(np.where(is_roll, np.arange(n), 0))
    T = (MATURITY_SESSIONS - (sess - sess[last_roll])) / YEAR_SESSIONS
    if (T[:-1] - (sess[1:] - sess[:-1]) / YEAR_SESSIONS <= 0).any() or (T <= 0).any():
        raise ValueError("a held book would reach expiry before its roll")
    return BookState(roll_spot=spot[last_roll], T=T, is_roll=is_roll)


# --------------------------------------------------------------------------
# Scenarios, losses, forecasts
# --------------------------------------------------------------------------


def scenario_losses(
    roll_spot: np.ndarray,
    S: np.ndarray,
    T: np.ndarray,
    r: np.ndarray,
    sigma: np.ndarray,
    shocks: np.ndarray,
    *,
    model: str,
) -> np.ndarray:
    """Scenario losses, shape (n, W). ``shocks`` is (n, W, 2): (log spot return, d log VIX).

    M2 applies both shocks plus one session of decay; M1 applies the spot shock only, no decay.
    """
    if model not in ("M1", "M2"):
        raise ValueError(f"model must be M1 or M2, got {model!r}")
    v0 = book_value(S, roll_spot, T, r, sigma)[:, None]
    Ss = S[:, None] * np.exp(shocks[:, :, 0])
    if model == "M2":
        sig = sigma[:, None] * np.exp(shocks[:, :, 1])
        Ts = (T - 1.0 / YEAR_SESSIONS)[:, None] * np.ones_like(Ss)
    else:
        sig = np.broadcast_to(sigma[:, None], Ss.shape)
        Ts = np.broadcast_to(T[:, None], Ss.shape)
    v1 = book_value(Ss, roll_spot[:, None], Ts, r[:, None], sig)
    return -(v1 - v0)


@dataclasses.dataclass
class ModelForecasts:
    scen: np.ndarray  # (n, W) scenario losses
    var: dict[float, np.ndarray]
    es: dict[float, np.ndarray]


@dataclasses.dataclass
class ForecastSet:
    rows: np.ndarray  # frame row index of each forecast date t
    dates: pd.DatetimeIndex
    loss: np.ndarray  # realised loss L_t (NaN only for a final row without a next session)
    contiguous: np.ndarray  # forecast i and i+1 are consecutive kept sessions (length n-1)
    vix: np.ndarray
    models: dict[str, ModelForecasts]


def _require_finite(name: str, a: np.ndarray) -> None:
    if not np.all(np.isfinite(a)):
        raise ValueError(f"non-finite {name}: the run stops (spec S5, NaN rule)")


def run_forecasts(
    frame: pd.DataFrame,
    *,
    models: tuple[str, ...] = ("M2", "M1"),
    levels: tuple[float, ...] = LEVELS,
    require_next: bool = True,
    chunk: int = 256,
) -> ForecastSet:
    """Forecast at every kept session t with a full window of 252 pairs ending at t.

    The window at t holds the pairs (log SPY return, change in log VIX) of rows t-251..t, so it
    uses only rows dated <= t. The realised loss uses row t+1. With ``require_next`` the last row is
    not a forecast date; without it (prefix checks) the last forecast has a NaN loss.
    """
    n_rows = len(frame)
    spot = frame["spot"].to_numpy()
    vix = frame["vix"].to_numpy()
    rate = frame["rate"].to_numpy()
    sess = frame["sess"].to_numpy()
    sigma = vix / 100.0
    state = book_state(frame)

    pairs = np.full((n_rows, 2), np.nan)
    pairs[1:, 0] = np.log(spot[1:] / spot[:-1])
    pairs[1:, 1] = np.log(vix[1:] / vix[:-1])

    last = n_rows - 2 if require_next else n_rows - 1
    rows = np.arange(WINDOW, last + 1)
    if len(rows) == 0:
        raise ValueError("not enough rows for a single forecast")
    windows = np.lib.stride_tricks.sliding_window_view(pairs[1:], (WINDOW, 2))[:, 0]
    # windows[j] covers rows j+1..j+WINDOW; the window ending at row t is j = t - WINDOW
    win = windows[rows - WINDOW]

    has_next = rows + 1 < n_rows
    loss = np.full(len(rows), np.nan)
    nx = rows[has_next]
    v0 = book_value(spot[nx], state.roll_spot[nx], state.T[nx], rate[nx], sigma[nx])
    gap = (sess[nx + 1] - sess[nx]) / YEAR_SESSIONS
    v1 = book_value(spot[nx + 1], state.roll_spot[nx], state.T[nx] - gap, rate[nx], sigma[nx + 1])
    loss[has_next] = -(v1 - v0)

    out: dict[str, ModelForecasts] = {}
    for model in models:
        scen = np.empty((len(rows), WINDOW))
        for a in range(0, len(rows), chunk):
            sl = slice(a, a + chunk)
            r_ = rows[sl]
            scen[sl] = scenario_losses(
                state.roll_spot[r_],
                spot[r_],
                state.T[r_],
                rate[r_],
                sigma[r_],
                win[sl],
                model=model,
            )
        _require_finite(f"{model} scenario loss", scen)
        var = {lv: np.empty(len(rows)) for lv in levels}
        es = {lv: np.empty(len(rows)) for lv in levels}
        for i in range(len(rows)):
            for lv in levels:
                var[lv][i], es[lv][i] = compute_var_es(scen[i], lv)
        for lv in levels:
            _require_finite(f"{model} VaR {lv}", var[lv])
            _require_finite(f"{model} ES {lv}", es[lv])
        out[model] = ModelForecasts(scen=scen, var=var, es=es)
    _require_finite("realised loss", loss[has_next])
    if require_next:
        _require_finite("realised loss", loss)
    contiguous = (rows[1:] == rows[:-1] + 1) & (sess[rows[1:]] - sess[rows[:-1]] == 1)
    return ForecastSet(
        rows=rows,
        dates=frame.index[rows],
        loss=loss,
        contiguous=contiguous,
        vix=vix[rows],
        models=out,
    )


def slice_forecasts(fs: ForecastSet, mask: np.ndarray) -> ForecastSet:
    """Restrict a ForecastSet to a boolean mask over forecasts (contiguity recomputed)."""
    idx = np.where(mask)[0]
    contiguous = (
        (idx[1:] == idx[:-1] + 1) & fs.contiguous[idx[:-1]] if len(idx) > 1 else np.array([], bool)
    )
    models = {
        m: ModelForecasts(
            scen=mf.scen[idx],
            var={k: v[idx] for k, v in mf.var.items()},
            es={k: v[idx] for k, v in mf.es.items()},
        )
        for m, mf in fs.models.items()
    }
    return ForecastSet(fs.rows[idx], fs.dates[idx], fs.loss[idx], contiguous, fs.vix[idx], models)


# --------------------------------------------------------------------------
# PIT, tests
# --------------------------------------------------------------------------


def randomised_pit(scen: np.ndarray, loss: np.ndarray) -> np.ndarray:
    """u_t = (R_t + V_t)/(W+1); R_t = #scenario losses >= L_t; V_t ~ U(0,1), seed [20261114, 1]."""
    _require_finite("realised loss", loss)
    w = scen.shape[1]
    ranks = (scen >= loss[:, None]).sum(axis=1)
    v = np.random.default_rng(np.random.SeedSequence(SEED_PIT)).random(len(loss))
    return (ranks + v) / (w + 1)


def du_escanciano_test(u: np.ndarray, alpha: float = ES_TAIL) -> dict[str, float]:
    """Unconditional ES test: mean of H = (alpha-u)1(u<=alpha)/alpha vs null mean alpha/2.

    Null variance of the mean is alpha(1/3 - alpha/4)/n; z-test, two-sided p.
    """
    u = np.asarray(u, dtype=float)
    _require_finite("PIT", u)
    n = len(u)
    h = np.where(u <= alpha, (alpha - u) / alpha, 0.0)
    stat = float(h.mean())
    var = alpha * (1.0 / 3.0 - alpha / 4.0) / n
    z = (stat - alpha / 2.0) / np.sqrt(var)
    return {"statistic": stat, "z": float(z), "p_value": float(2.0 * norm.sf(abs(z))), "n": n}


def _christoffersen_counts_lr(n00: int, n01: int, n10: int, n11: int) -> float:
    """Same LR as production christoffersen_independence_test, from transition counts."""
    n0, n1 = n00 + n01, n10 + n11
    pi01 = n01 / n0 if n0 else 0.0
    pi11 = n11 / n1 if n1 else 0.0
    pi = (n01 + n11) / (n0 + n1) if (n0 + n1) else 0.0

    def ll(p: float, s: int, t: int) -> float:
        if t == 0:
            return 0.0
        if p <= 0:
            return 0.0 if s == 0 else -np.inf
        if p >= 1:
            return 0.0 if s == t else -np.inf
        return s * np.log(p) + (t - s) * np.log(1 - p)

    lr = -2 * (ll(pi, n01, n0) + ll(pi, n11, n1) - ll(pi01, n01, n0) - ll(pi11, n11, n1))
    return max(lr, 0.0) if np.isfinite(lr) else 0.0


def christoffersen_gapped(
    breaches: np.ndarray, contiguous: np.ndarray, confidence_level: float
) -> dict[str, float]:
    """Christoffersen independence; transitions across a gap (contiguous False) are dropped.

    With no gaps this is the production test. With gaps the same LR is computed from the retained
    transition counts (production takes only a plain array).
    """
    b = np.asarray(breaches, dtype=bool)
    if len(contiguous) != len(b) - 1:
        raise ValueError("contiguous must have length len(breaches)-1")
    if np.all(contiguous):
        res = christoffersen_independence_test(b, confidence_level)
        return {"statistic": res.lr_statistic, "p_value": res.p_value}
    a, c = b[:-1][contiguous].astype(int), b[1:][contiguous].astype(int)
    lr = _christoffersen_counts_lr(
        int(((a == 0) & (c == 0)).sum()), int(((a == 0) & (c == 1)).sum()),
        int(((a == 1) & (c == 0)).sum()), int(((a == 1) & (c == 1)).sum()),
    )  # fmt: skip
    from scipy.stats import chi2

    return {"statistic": float(lr), "p_value": float(chi2.sf(lr, 1))}


def acerbi_szekely_z2(
    loss: np.ndarray,
    var: np.ndarray,
    es: np.ndarray,
    scen: np.ndarray,
    *,
    alpha: float = ES_TAIL,
    n_sim: int = AS_N_SIM,
    chunk: int = 250,
) -> dict[str, float]:
    """Z2 = mean(L_t 1(L_t > VaR_t)/(alpha ES_t)) - 1, upper tail (positive = risk understated).

    Null distribution: each simulated L_t is drawn uniformly from day t's own scenario set
    (seed [20261114, 2]). p = (1 + #{sim >= obs})/(1 + n_sim); also returns the 95% critical value.
    """
    for name, a in (("loss", loss), ("VaR", var), ("ES", es)):
        _require_finite(name, a)
    if (es <= 0).any():
        raise ValueError("Acerbi-Szekely Z2 needs ES > 0 on every day")
    n, w = scen.shape
    stat = float((loss * (loss > var) / (alpha * es)).mean() - 1.0)
    rng = np.random.default_rng(np.random.SeedSequence(SEED_AS))
    sims = np.empty(n_sim)
    rows = np.arange(n)
    for a in range(0, n_sim, chunk):
        m = min(chunk, n_sim - a)
        ls = scen[rows, rng.integers(0, w, size=(m, n))]
        sims[a : a + m] = (ls * (ls > var) / (alpha * es)).mean(axis=1) - 1.0
    return {
        "statistic": stat,
        "critical_95": float(np.quantile(sims, 0.95)),
        "p_value": float((1 + (sims >= stat).sum()) / (1 + n_sim)),
        "n_sim": n_sim,
    }


def holm_adjust(p_values: list[float] | np.ndarray) -> list[float]:
    """Holm step-down adjusted p-values (monotone, capped at 1), in the input order."""
    p = np.asarray(p_values, dtype=float)
    m = len(p)
    order = np.argsort(p, kind="stable")
    adj = np.minimum(1.0, (m - np.arange(m)) * p[order])
    adj = np.maximum.accumulate(adj)
    out = np.empty(m)
    out[order] = adj
    return [float(x) for x in out]


def primary_tests(
    var95: np.ndarray, loss: np.ndarray, contiguous: np.ndarray, u: np.ndarray
) -> dict[str, Any]:
    """T1 (Kupiec 95%), T2 (Christoffersen 95%), T3 (Du-Escanciano 97.5%) for one forecast set."""
    _require_finite("VaR", var95)
    _require_finite("realised loss", loss)
    breaches = loss > var95
    t1 = kupiec_pof_test(breaches, 0.95)
    t2 = christoffersen_gapped(breaches, contiguous, 0.95)
    t3 = du_escanciano_test(u)
    return {
        "n": int(len(loss)),
        "n_breaches_95": int(breaches.sum()),
        "T1": {"statistic": t1.lr_statistic, "p_value": t1.p_value},
        "T2": t2,
        "T3": t3,
    }


def evaluate_model(fs: ForecastSet, model: str) -> dict[str, Any]:
    """Tests T1-T3 for one model, plus Acerbi-Szekely Z2 at 97.5%."""
    mf = fs.models[model]
    u = randomised_pit(mf.scen, fs.loss)
    res = primary_tests(mf.var[0.95], fs.loss, fs.contiguous, u)
    es975 = mf.es[0.975]
    if (es975 <= 0).any():
        # Z2 divides by ES; report it as undefined (not silently skipped) and let a caller that
        # needs it in the primary family fail loudly.
        res["Z2"] = {"undefined": f"ES<=0 on {int((es975 <= 0).sum())} forecast days"}
    else:
        res["Z2"] = acerbi_szekely_z2(fs.loss, mf.var[0.975], es975, mf.scen)
    res["holm_T1_T2_T3"] = holm_adjust(
        [res["T1"]["p_value"], res["T2"]["p_value"], res["T3"]["p_value"]]
    )
    return res


def evaluate_by_period(fs: ForecastSet, model: str) -> dict[str, Any]:
    """Each test within DEV / VAL2024 / 2025, Holm-adjusted across the three periods."""
    per: dict[str, Any] = {}
    for name, (lo, hi) in PERIODS.items():
        mask = (fs.dates >= pd.Timestamp(lo)) & (fs.dates <= pd.Timestamp(hi))
        if mask.sum() < 3:
            continue
        sub = slice_forecasts(fs, mask)
        mf = sub.models[model]
        per[name] = primary_tests(
            mf.var[0.95], sub.loss, sub.contiguous, randomised_pit(mf.scen, sub.loss)
        )
    for test in ("T1", "T2", "T3"):
        names = list(per)
        adj = holm_adjust([per[k][test]["p_value"] for k in names])
        for k, a in zip(names, adj, strict=True):
            per[k][test]["p_value_holm_across_periods"] = a
    return per


def vix_regime_breaches(fs: ForecastSet, frame: pd.DataFrame, model: str) -> dict[str, Any]:
    """Descriptive: 95% breach rate with VIX below / above its trailing 252-row median."""
    med = frame["vix"].rolling(WINDOW).median().to_numpy()[fs.rows]
    breaches = fs.loss > fs.models[model].var[0.95]
    low = fs.vix < med
    out = {}
    for name, m in (("below_median", low), ("above_median", ~low)):
        out[name] = {"n": int(m.sum()), "breaches": int(breaches[m].sum())}
    return out


def basel_zones_99(fs: ForecastSet, model: str, block: int = 250) -> list[dict[str, Any]]:
    """Breach counts and Basel zone (green <=4, yellow 5-9, red >=10) of each 250-day block."""
    breaches = fs.loss > fs.models[model].var[0.99]
    rows = []
    for a in range(0, len(breaches) - block + 1, block):
        k = int(breaches[a : a + block].sum())
        rows.append(
            {
                "start": str(fs.dates[a].date()),
                "breaches": k,
                "zone": "green" if k <= 4 else "yellow" if k <= 9 else "red",
            }
        )
    return rows


def kupiec_mde(
    n: int, alpha_level: float = 0.05 / 3, power: float = 0.8, p0: float = 0.05
) -> float:
    """Smallest breach-rate multiple m with exact binomial Kupiec power >= 0.8 at the Holm level."""
    xs = np.arange(n + 1)
    reject = np.array(
        [
            kupiec_pof_test(np.arange(n) < x, 1 - p0, significance_level=alpha_level).reject_null
            for x in xs
        ]
    )
    for m in np.arange(1.0, 10.0, 0.01):
        if binom.pmf(xs, n, min(1.0, m * p0))[reject].sum() >= power:
            return float(m)
    return float("nan")


# --------------------------------------------------------------------------
# P4: synthetic calibration
# --------------------------------------------------------------------------


def fit_t4_scale(returns: np.ndarray, dlog_vix: np.ndarray) -> dict[str, float]:
    """Sample sd of each factor and their correlation (the pair is mean-zero in P4)."""
    c = np.corrcoef(returns, dlog_vix)[0, 1]
    return {
        "sd_ret": float(np.std(returns, ddof=1)),
        "sd_dvix": float(np.std(dlog_vix, ddof=1)),
        "corr": float(c),
    }


DEFAULT_T4_SCALE = {"sd_ret": 0.011, "sd_dvix": 0.075, "corr": -0.7}


def synthetic_frame(
    path_index: int,
    length: int,
    scale: dict[str, float],
    *,
    nu: float = 4.0,
    s0: float = 100.0,
    vix0: float = 20.0,
    rate: float = 0.02,
) -> pd.DataFrame:
    """One iid bivariate Student-t path (covariance matched to ``scale``), seed [20261114, 3, i].

    ``length`` is the number of pairs; the frame has length+1 weekday rows. Spot and VIX are the
    cumulated pairs (VIX is therefore a driftless log random walk, not clipped).
    """
    rng = np.random.default_rng(np.random.SeedSequence([*SEED_P4_PREFIX, path_index]))
    sd = np.array([scale["sd_ret"], scale["sd_dvix"]])
    cov = np.array([[1.0, scale["corr"]], [scale["corr"], 1.0]]) * np.outer(sd, sd)
    chol = np.linalg.cholesky(cov * (nu - 2.0) / nu)
    z = rng.standard_normal((length, 2)) @ chol.T
    z /= np.sqrt(rng.chisquare(nu, size=length) / nu)[:, None]
    idx = pd.bdate_range("2015-01-02", periods=length + 1)
    spot = s0 * np.exp(np.concatenate([[0.0], np.cumsum(z[:, 0])]))
    vix = vix0 * np.exp(np.concatenate([[0.0], np.cumsum(z[:, 1])]))
    return pd.DataFrame(
        {"spot": spot, "vix": vix, "rate": rate, "sess": np.arange(length + 1)}, index=idx
    )


def run_p4(
    n_paths: int,
    *,
    length: int = 2760,
    scale: dict[str, float] | None = None,
    tail_k: float = 1.0,
) -> dict[str, Any]:
    """Run the full harness (book, daily mark, M2 forecasts, T1-T3) on synthetic paths.

    ``tail_k`` > 1 multiplies realised losses above that day's 97.5% VaR by k (D2 power runs).
    Returns rejection rates at 0.05 and the per-path statistics (for simulated p-values).
    """
    scale = scale or DEFAULT_T4_SCALE
    stats: dict[str, list[float]] = {"T1": [], "T2": [], "T3": []}
    pvals: dict[str, list[float]] = {"T1": [], "T2": [], "T3": []}
    for i in range(n_paths):
        fr = synthetic_frame(i, length, scale)
        fs = run_forecasts(fr, models=("M2",), levels=(0.95, 0.975))
        mf = fs.models["M2"]
        loss = fs.loss.copy()
        if tail_k != 1.0:
            hit = loss > mf.var[0.975]
            loss[hit] = loss[hit] * tail_k
        res = primary_tests(mf.var[0.95], loss, fs.contiguous, randomised_pit(mf.scen, loss))
        for t, key in (("T1", "statistic"), ("T2", "statistic"), ("T3", "z")):
            stats[t].append(float(res[t][key]))
            pvals[t].append(float(res[t]["p_value"]))
    rates = {t: float(np.mean(np.array(v) < 0.05)) for t, v in pvals.items()}
    return {
        "n_paths": n_paths,
        "length": length,
        "tail_k": tail_k,
        "rejection_rates": rates,
        "statistics": stats,
    }


def simulated_p_value(
    observed: float, null_stats: list[float], *, two_sided: bool = False
) -> float:
    """Share of P4 statistics at least as extreme as observed, (1+k)/(1+N)."""
    s = np.asarray(null_stats, dtype=float)
    k = (np.abs(s) >= abs(observed)).sum() if two_sided else (s >= observed).sum()
    return float((1 + k) / (1 + len(s)))


def apply_p4_decision(observed: dict[str, Any], p4: dict[str, Any]) -> dict[str, Any]:
    """Section 7 P4 rule: a test with a P4 rate outside [0.03, 0.08] gets its P4 simulated p-value.

    ``observed`` holds the primary tests (T1/T2/T3 dicts with statistic/z and p_value). Returns the
    p-value used per test, the switches, and whether Z2 replaces T3 in the primary family.
    """
    used: dict[str, Any] = {}
    for t, key, two in (("T1", "statistic", False), ("T2", "statistic", False), ("T3", "z", True)):
        rate = p4["rejection_rates"][t]
        in_band = P4_BAND[0] <= rate <= P4_BAND[1]
        sim_p = simulated_p_value(observed[t][key], p4["statistics"][t], two_sided=two)
        used[t] = {
            "p4_rate": rate,
            "in_band": in_band,
            "analytic_p": observed[t]["p_value"],
            "simulated_p": sim_p,
            "p_used": observed[t]["p_value"] if in_band else sim_p,
        }
    used["z2_replaces_t3"] = not used["T3"]["in_band"]
    return used


# --------------------------------------------------------------------------
# Preconditions P1, P2 and the full study
# --------------------------------------------------------------------------


def check_repricing(
    roll_spot: float = 100.0,
    S: float = 100.0,
    T: float = 30 / 252,
    r: float = 0.03,
    sigma: float = 0.2,
) -> dict[str, Any]:
    """P1: zero shocks give zero loss; decay-only loss equals a direct BS reprice; theta check."""
    pf = portfolio_for_book(roll_spot, S, T, r, sigma)
    zero = np.zeros((1, 3, 2))
    args = (np.array([roll_spot]), np.array([S]), np.array([T]), np.array([r]), np.array([sigma]))
    zero_m1 = float(np.abs(scenario_losses(*args, zero, model="M1")).max())
    zero_pf = abs(portfolio_scenario_loss(pf, 0.0, 0.0, 0.0))
    dt = 1.0 / YEAR_SESSIONS
    direct = 0.0
    for p in pf.positions:
        if isinstance(p, OptionPosition):
            direct += (
                p.quantity
                * p.multiplier
                * (
                    bsm_price(p.S, p.strike, p.T - dt, p.r, p.sigma, p.option_type, p.q)
                    - bsm_price(p.S, p.strike, p.T, p.r, p.sigma, p.option_type, p.q)
                )
            )
    direct_loss = -direct
    decay_pf = portfolio_scenario_loss(pf, 0.0, 0.0, dt)
    decay_vec = float(scenario_losses(*args, zero[:, :1], model="M2")[0, 0])
    theta_loss = -pf.greeks().theta / YEAR_SESSIONS
    rel = abs(decay_pf - theta_loss) / abs(theta_loss)
    return {
        "zero_shock_max_abs_loss": max(zero_m1, zero_pf),
        "decay_loss_portfolio": decay_pf,
        "decay_loss_vectorised": decay_vec,
        "decay_loss_direct_bs": direct_loss,
        "decay_vs_direct_abs_diff": max(abs(decay_pf - direct_loss), abs(decay_vec - direct_loss)),
        "decay_vs_theta_rel_diff": float(rel),
        "passed": bool(
            max(zero_m1, zero_pf) <= 1e-9
            and max(abs(decay_pf - direct_loss), abs(decay_vec - direct_loss)) <= 1e-9
            and rel <= 0.10
        ),
    }


def check_prefix_invariance(frame: pd.DataFrame, n_forecast: int = 1500) -> dict[str, Any]:
    """P2: forecasts from data truncated at forecast number ``n_forecast`` equal the full run's.

    The truncated frame ends on that forecast date itself (no later row), so any use of data after
    t shows up as a mismatch. The loss of the final forecast is not defined there and is skipped.
    """
    full = run_forecasts(frame, models=("M2", "M1"))
    if n_forecast > len(full.rows):
        raise ValueError("fewer forecasts than the prefix length")
    cut_row = int(full.rows[n_forecast - 1])
    short = run_forecasts(frame.iloc[: cut_row + 1], models=("M2", "M1"), require_next=False)
    ok = len(short.rows) == n_forecast and np.array_equal(short.rows, full.rows[:n_forecast])
    ok = ok and np.array_equal(short.loss[:-1], full.loss[: n_forecast - 1])
    for m in full.models:
        a, b = short.models[m], full.models[m]
        ok = ok and np.array_equal(a.scen, b.scen[:n_forecast])
        for lv in LEVELS:
            ok = ok and np.array_equal(a.var[lv], b.var[lv][:n_forecast])
            ok = ok and np.array_equal(a.es[lv], b.es[lv][:n_forecast])
    return {
        "forecast_number": n_forecast,
        "forecast_date": str(full.dates[n_forecast - 1].date()),
        "passed": bool(ok),
    }


def run_study(
    frame: pd.DataFrame,
    *,
    p4_paths: int = 2000,
    p4_scale: dict[str, float] | None = None,
    prefix_forecasts: int = 1500,
) -> dict[str, Any]:
    """Preconditions P1, P2, P4, then the tests of sections 6 and 8. P3 is not implemented here."""
    out: dict[str, Any] = {"preconditions": {}}
    pre = out["preconditions"]
    pre["P1"] = check_repricing()
    pre["P2"] = check_prefix_invariance(frame, prefix_forecasts)
    if not (pre["P1"]["passed"] and pre["P2"]["passed"]):
        out["stopped"] = "a precondition failed; no results computed"
        return out
    scale = p4_scale or DEFAULT_T4_SCALE
    p4 = run_p4(p4_paths, scale=scale)
    pre["P4"] = {k: v for k, v in p4.items() if k != "statistics"}
    fs = run_forecasts(frame)
    primary = evaluate_model(fs, "M2")
    decision = apply_p4_decision(primary, p4)
    pre["P4"]["decision"] = decision
    p_used = [decision[t]["p_used"] for t in ("T1", "T2", "T3")]
    family = {"T1": p_used[0], "T2": p_used[1], "T3": p_used[2]}
    if decision["z2_replaces_t3"]:
        if "p_value" not in primary["Z2"]:
            raise ValueError("T3 is outside the P4 band and Z2 is undefined: " + str(primary["Z2"]))
        family["T3"] = primary["Z2"]["p_value"]  # Z2 takes T3's place, with its simulated p
    holm = holm_adjust(list(family.values()))
    out["primary_M2"] = {
        "tests": primary,
        "p_used": family,
        "holm_adjusted": dict(zip(family, holm, strict=True)),
        "D1_rejected": any(h < 0.05 for h in holm),
    }
    out["n_forecasts"] = int(len(fs.rows))
    out["M2_by_period"] = evaluate_by_period(fs, "M2")
    out["M1"] = evaluate_model(fs, "M1")
    out["M1_by_period"] = evaluate_by_period(fs, "M1")
    mf = fs.models["M2"]
    out["secondary_M2"] = {
        "kupiec_99": kupiec_pof_test(fs.loss > mf.var[0.99], 0.99).p_value,
        "basel_zones_99": basel_zones_99(fs, "M2"),
        "vix_regime_breaches_95": vix_regime_breaches(fs, frame, "M2"),
    }
    out["mde"] = {
        "T1_kupiec_multiple_at_holm_level": kupiec_mde(len(fs.rows)),
        "T3_p4_tail_multiplied": {
            str(k): run_p4(p4_paths, scale=scale, tail_k=k)["rejection_rates"]["T3"]
            for k in (1.5, 2.0)
        },
    }
    return out
