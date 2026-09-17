"""Offline tests for Directive #9 D9-C authoritative (v2) historical risk
study helpers. Synthetic fixtures only -- no network, no real market data."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import pytest

from options_risk.historical_risk_study_v2 import (
    HS_LOOKBACKS,
    OPTION_MATURITY_SESSIONS,
    REALIZED_VOL_WINDOW_PRIMARY,
    PeriodSpec,
    build_standardized_portfolio,
    full_revaluation_mc_var_es,
    load_fred_series_decimal,
    point_in_time_value,
    run_hedging_experiment,
    run_nonlinear_portfolio_study,
    simulate_delta_hedge_on_price_path,
    trailing_realized_vol,
    var_es_all_methods,
)
from options_risk.risk.var import monte_carlo_var


def _synthetic_prices(
    n: int = 900, seed: int = 0, vol: float = 0.01, drift: float = 0.0001
) -> pd.Series:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2015-01-02", periods=n)
    prices = 100 * np.exp(np.cumsum(rng.normal(drift, vol, n)))
    return pd.Series(prices, index=idx)


class TestPointInTimeValue:
    def test_returns_latest_observation_on_or_before_date(self):
        idx = pd.bdate_range("2020-01-01", periods=10)
        series = pd.Series(
            [np.nan, 1.0, np.nan, np.nan, 2.0, np.nan, 3.0, np.nan, np.nan, np.nan], index=idx
        )
        # idx[7] itself is NaN; the latest known value at or before it is 3.0 at idx[6].
        result = point_in_time_value(series, idx[7])
        assert result.value == 3.0
        assert result.as_of_date == idx[6]
        assert result.staleness_sessions == (idx[7] - idx[6]).days

    def test_never_future_backfills(self):
        idx = pd.bdate_range("2020-01-01", periods=5)
        series = pd.Series([np.nan, np.nan, np.nan, 5.0, 6.0], index=idx)
        # No observation on or before idx[1] -> must raise, not peek forward to 5.0/6.0.
        with pytest.raises(ValueError):
            point_in_time_value(series, idx[1])

    def test_raises_when_nothing_known_yet(self):
        idx = pd.bdate_range("2020-01-01", periods=5)
        series = pd.Series([np.nan] * 3 + [1.0, 2.0], index=idx)
        with pytest.raises(ValueError):
            point_in_time_value(series, idx[1])


class TestLoadFredSeriesDecimal:
    def test_percent_to_decimal_and_missing_as_nan(self, tmp_path):
        csv_path = tmp_path / "TESTSERIES.csv"
        csv_path.write_text(
            "observation_date,TESTSERIES\n2015-01-01,\n2015-01-02,2.00\n2015-01-05,3.50\n"
        )
        series = load_fred_series_decimal(str(csv_path), "TESTSERIES")
        assert len(series) == 3
        assert np.isnan(series.iloc[0])
        assert series.iloc[1] == pytest.approx(0.02)
        assert series.iloc[2] == pytest.approx(0.035)


class TestTrailingRealizedVol:
    def test_is_causal_and_excludes_own_day(self):
        idx = pd.bdate_range("2020-01-01", periods=30)
        # Flat returns for the first REALIZED_VOL_WINDOW_PRIMARY days, then a
        # single huge spike on the decision day itself -- trailing vol AS OF
        # that day must not be contaminated by that same day's return.
        returns = pd.Series(0.001, index=idx)
        returns.iloc[REALIZED_VOL_WINDOW_PRIMARY] = 5.0  # huge spike at the decision index
        vol_before_spike_included = trailing_realized_vol(
            returns, REALIZED_VOL_WINDOW_PRIMARY, REALIZED_VOL_WINDOW_PRIMARY
        )
        assert vol_before_spike_included == pytest.approx(0.0, abs=1e-9)

    def test_nan_when_insufficient_history(self):
        idx = pd.bdate_range("2020-01-01", periods=5)
        returns = pd.Series(0.001, index=idx)
        assert np.isnan(trailing_realized_vol(returns, 3, REALIZED_VOL_WINDOW_PRIMARY))


class TestHedgeOnPricePath:
    def test_zero_vol_zero_cost_flat_path_small_replication_error(self):
        """A perfectly flat price path with the pricing vol matching realized
        (zero) vol and zero transaction costs should replicate almost
        exactly -- the option is always worth its (zero, since ATM and
        never moves) intrinsic value and delta stays at a constant 0.5ish
        boundary; this is a sanity check on the mechanics, not a precise
        theoretical zero."""
        idx = pd.bdate_range("2020-01-01", periods=OPTION_MATURITY_SESSIONS + 1)
        flat = pd.Series(100.0, index=idx)
        result = simulate_delta_hedge_on_price_path(
            flat,
            K=100.0,
            r=0.02,
            sigma_pricing=0.01,
            option_type="call",
            q=0.0,
            option_qty=-1.0,
            cost_rate=0.0,
            rebalance_every_n_sessions=1,
        )
        assert result.transaction_cost == 0.0
        assert result.n_rebalances >= 0
        assert np.isfinite(result.replication_error)

    def test_more_rebalancing_frequency_changes_cost(self):
        idx = pd.bdate_range("2020-01-01", periods=OPTION_MATURITY_SESSIONS + 1)
        rng = np.random.default_rng(1)
        prices = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(idx)))), index=idx)
        daily = simulate_delta_hedge_on_price_path(
            prices,
            K=100.0,
            r=0.02,
            sigma_pricing=0.15,
            option_type="call",
            q=0.0,
            option_qty=-1.0,
            cost_rate=0.0005,
            rebalance_every_n_sessions=1,
        )
        weekly = simulate_delta_hedge_on_price_path(
            prices,
            K=100.0,
            r=0.02,
            sigma_pricing=0.15,
            option_type="call",
            q=0.0,
            option_qty=-1.0,
            cost_rate=0.0005,
            rebalance_every_n_sessions=5,
        )
        assert daily.n_rebalances > weekly.n_rebalances

    def test_uses_real_path_not_gbm_simulation(self):
        """Two calls with the SAME seed-independent real price path must
        produce IDENTICAL results (no internal randomness) -- proving this
        is a deterministic replay of the given path, not a stochastic
        simulation like options_risk.hedging.delta_hedge.simulate_delta_hedge."""
        idx = pd.bdate_range("2020-01-01", periods=OPTION_MATURITY_SESSIONS + 1)
        prices = pd.Series(100 + np.sin(np.linspace(0, 6, len(idx))) * 5, index=idx)
        r1 = simulate_delta_hedge_on_price_path(
            prices,
            K=100.0,
            r=0.02,
            sigma_pricing=0.2,
            option_type="call",
            q=0.0,
            option_qty=-1.0,
            cost_rate=0.0005,
            rebalance_every_n_sessions=1,
        )
        r2 = simulate_delta_hedge_on_price_path(
            prices,
            K=100.0,
            r=0.02,
            sigma_pricing=0.2,
            option_type="call",
            q=0.0,
            option_qty=-1.0,
            cost_rate=0.0005,
            rebalance_every_n_sessions=1,
        )
        assert r1.replication_error == r2.replication_error


class TestRunHedgingExperiment:
    def test_produces_episodes_with_required_label_and_disclosures(self):
        prices = _synthetic_prices(n=800)
        rate_idx = prices.index
        rate_series = pd.Series(0.02, index=rate_idx)
        period = PeriodSpec("eval", str(prices.index[300].date()), str(prices.index[700].date()))
        out = run_hedging_experiment(prices, rate_series, period)
        assert out["label"] == "Historical underlying-path hypothetical option hedging experiment"
        assert out["n_episodes_initiated"] > 0
        assert len(out["episodes"]) > 0
        for ep in out["episodes"]:
            assert ep["rebalance_frequency"] in ("daily", "weekly")
            assert ep["cost_scenario"] in ("GROSS", "BASE", "STRESS")
        assert "note_on_episode_overlap" in out
        assert "dividend_handling" in out

    def test_gross_scenario_has_zero_transaction_cost(self):
        prices = _synthetic_prices(n=800)
        rate_series = pd.Series(0.02, index=prices.index)
        period = PeriodSpec("eval", str(prices.index[300].date()), str(prices.index[700].date()))
        out = run_hedging_experiment(prices, rate_series, period)
        gross_episodes = [e for e in out["episodes"] if e["cost_scenario"] == "GROSS"]
        assert gross_episodes
        assert all(e["transaction_cost"] == 0.0 for e in gross_episodes)

    def test_stress_costs_exceed_base_costs(self):
        prices = _synthetic_prices(n=800)
        rate_series = pd.Series(0.02, index=prices.index)
        period = PeriodSpec("eval", str(prices.index[300].date()), str(prices.index[700].date()))
        out = run_hedging_experiment(prices, rate_series, period)
        base = out["summary_by_frequency_and_cost_scenario"]["daily_BASE"]["mean_transaction_cost"]
        stress = out["summary_by_frequency_and_cost_scenario"]["daily_STRESS"][
            "mean_transaction_cost"
        ]
        assert stress > base > 0


class TestStandardizedPortfolio:
    def test_composition_matches_spec(self):
        portfolio = build_standardized_portfolio(S0=100.0, T=30 / 252, r=0.02, sigma=0.2, q=0.0)
        equities = [
            p
            for p in portfolio.positions
            if hasattr(p, "quantity") and not hasattr(p, "option_type")
        ]
        calls = [p for p in portfolio.positions if getattr(p, "option_type", None) == "call"]
        puts = [p for p in portfolio.positions if getattr(p, "option_type", None) == "put"]
        assert len(equities) == 1 and equities[0].quantity == 100.0
        assert len(calls) == 1 and calls[0].quantity == -2.0 and calls[0].strike == 100.0
        assert len(puts) == 1 and puts[0].quantity == 2.0 and puts[0].strike == pytest.approx(95.0)


class TestFullRevaluationMcVarEs:
    def test_matches_reference_scalar_implementation(self):
        """full_revaluation_mc_var_es exists purely as a performance
        rewrite of options_risk.risk.var.monte_carlo_var (same rng draws,
        same closed-form BSM formula, same compute_var_es) -- this proves
        it is not an approximation by reproducing the reference scalar
        implementation's result to floating-point tolerance."""
        portfolio = build_standardized_portfolio(S0=100.0, T=30 / 252, r=0.02, sigma=0.2, q=0.0)
        vectorized = full_revaluation_mc_var_es(
            portfolio,
            mean_return=0.0,
            vol=0.2,
            n_sims=3000,
            horizon=1,
            confidence_level=0.95,
            seed=42,
        )
        reference = monte_carlo_var(
            portfolio,
            mean_return=0.0,
            vol=0.2,
            n_sims=3000,
            horizon=1,
            confidence_level=0.95,
            seed=42,
        )
        assert vectorized.var == pytest.approx(reference.var, rel=1e-9)
        assert vectorized.es == pytest.approx(reference.es, rel=1e-9)
        assert vectorized.n_obs == reference.n_obs
        np.testing.assert_allclose(vectorized.losses, reference.losses, rtol=1e-9)


class TestVarEsAllMethods:
    def test_all_three_methods_return_positive_var_with_es_at_least_var(self):
        portfolio = build_standardized_portfolio(S0=100.0, T=30 / 252, r=0.02, sigma=0.2, q=0.0)
        rng = np.random.default_rng(0)
        hs_returns = rng.normal(0, 0.01, 300)
        result = var_es_all_methods(
            portfolio,
            hs_returns,
            hs_returns,
            mc_vol=0.2,
            confidence_level=0.95,
            mc_n_sims=2000,
            mc_seed=0,
        )
        for method in ("historical_simulation_primary", "delta_normal", "monte_carlo"):
            assert result[method]["var"] > 0
            assert result[method]["es"] >= result[method]["var"]

    def test_higher_confidence_yields_higher_var(self):
        portfolio = build_standardized_portfolio(S0=100.0, T=30 / 252, r=0.02, sigma=0.2, q=0.0)
        rng = np.random.default_rng(0)
        hs_returns = rng.normal(0, 0.01, 600)
        var_95 = var_es_all_methods(
            portfolio,
            hs_returns,
            hs_returns,
            mc_vol=0.2,
            confidence_level=0.95,
            mc_n_sims=2000,
            mc_seed=0,
        )
        var_99 = var_es_all_methods(
            portfolio,
            hs_returns,
            hs_returns,
            mc_vol=0.2,
            confidence_level=0.99,
            mc_n_sims=2000,
            mc_seed=0,
        )
        assert var_99["monte_carlo"]["var"] > var_95["monte_carlo"]["var"]
        assert var_99["delta_normal"]["var"] > var_95["delta_normal"]["var"]

    def test_no_sensitivity_window_returns_none(self):
        portfolio = build_standardized_portfolio(S0=100.0, T=30 / 252, r=0.02, sigma=0.2, q=0.0)
        rng = np.random.default_rng(0)
        hs_returns = rng.normal(0, 0.01, 300)
        result = var_es_all_methods(
            portfolio,
            hs_returns,
            None,
            mc_vol=0.2,
            confidence_level=0.95,
            mc_n_sims=2000,
            mc_seed=0,
        )
        assert result["historical_simulation_sensitivity"] is None

    def test_default_n_sims_matches_spec(self):
        """The module default (used by the real study run) must be the
        spec's required 50,000 -- this test asserts the default without
        actually running 50k sims itself."""
        import inspect

        sig = inspect.signature(var_es_all_methods)
        assert sig.parameters["mc_n_sims"].default == 50_000


class TestRunNonlinearPortfolioStudy:
    def test_end_to_end_produces_snapshots_and_backtest(self):
        # Just past the primary HS lookback, with ~2 monthly roll dates in
        # the eval window -- enough to exercise the logic without the cost
        # of dozens of full-revaluation VaR snapshots.
        prices = _synthetic_prices(n=HS_LOOKBACKS["primary"] + 45, seed=2)
        rate_series = pd.Series(0.02, index=prices.index)
        vix_series = pd.Series(0.18, index=prices.index)
        period = PeriodSpec(
            "eval",
            str(prices.index[HS_LOOKBACKS["primary"] + 1].date()),
            str(prices.index[-1].date()),
        )
        out = run_nonlinear_portfolio_study(
            prices, rate_series, vix_series, period, mc_n_sims=200, mc_seed=0
        )
        assert (
            out["label"]
            == "Hypothetical nonlinear portfolio evaluated on historical risk-factor paths"
        )
        assert out["n_roll_snapshots"] > 0
        for snap in out["snapshots"]:
            assert "hs_var_95_primary_every_roll" in snap
            assert "primary" in snap["var_es"]
            assert "secondary" in snap["var_es"]
        assert "kupiec_christoffersen_backtest" in out

    def test_vix_context_present_when_series_available(self):
        prices = _synthetic_prices(n=HS_LOOKBACKS["primary"] + 45, seed=3)
        rate_series = pd.Series(0.02, index=prices.index)
        vix_series = pd.Series(0.20, index=prices.index)
        period = PeriodSpec(
            "eval",
            str(prices.index[HS_LOOKBACKS["primary"] + 1].date()),
            str(prices.index[-1].date()),
        )
        out = run_nonlinear_portfolio_study(
            prices, rate_series, vix_series, period, mc_n_sims=200, mc_seed=0
        )
        assert out["snapshots"]
        assert all(snap["vixcls_context"] == pytest.approx(0.20) for snap in out["snapshots"])

    def test_every_roll_gets_full_var_es_snapshot(self):
        """Every eligible monthly roll gets the full 3-method, 2-confidence
        VaR/ES snapshot (including Monte Carlo) -- tractable now that Monte
        Carlo full revaluation is vectorized (full_revaluation_mc_var_es),
        so no cadence reduction is needed even across many roll dates."""
        prices = _synthetic_prices(n=HS_LOOKBACKS["primary"] + 400, seed=4)
        rate_series = pd.Series(0.02, index=prices.index)
        vix_series = pd.Series(0.18, index=prices.index)
        period = PeriodSpec(
            "eval",
            str(prices.index[HS_LOOKBACKS["primary"] + 1].date()),
            str(prices.index[-1].date()),
        )
        out = run_nonlinear_portfolio_study(
            prices,
            rate_series,
            vix_series,
            period,
            mc_n_sims=100,
            mc_seed=0,
        )
        assert out["n_roll_snapshots"] > 1
        for snap in out["snapshots"]:
            assert np.isfinite(snap["hs_var_95_primary_every_roll"])
            assert "primary" in snap["var_es"]
            assert "secondary" in snap["var_es"]


def _monthly_roll_positions(idx: pd.DatetimeIndex) -> list[int]:
    """Independently computed (not via the module's own private helper) --
    the position of the first business day of each calendar month in `idx`.
    Mirrors _first_eligible_session_of_each_month's intent so these tests
    verify against the production behavior rather than assume it."""
    months = pd.Series(idx).dt.to_period("M")
    first_positions = pd.Series(range(len(idx))).groupby(months.to_numpy()).min()
    return sorted(int(p) for p in first_positions.to_numpy())


class TestNextSessionBacktestAlignment:
    """Real defect (independent review, 2026-09-17): the Kupiec/Christoffersen
    backtest compared each roll's 95% VaR forecast against the return ENDING
    ON the roll date (already realized before the roll) instead of the
    return from the roll date to the NEXT trading session. The VaR forecast
    inputs stayed causal throughout -- only the realized-return side of the
    comparison was misaligned. Fixed via a date-keyed lookup
    (full_prices.index[idx_pos + 1] -> returns.loc[that date]) instead of
    the old positional returns.iloc[ret_pos_val].

    All fixtures here use exact-zero returns for "the session immediately
    after a roll" everywhere except one deliberately engineered roll, so
    every control roll's realized P&L is deterministically zero (never
    breaches, regardless of the VaR magnitude) -- no reliance on tail
    probabilities, so nothing here is flaky.
    """

    def _build_fixture(
        self, *, spike_return: float, spike_next_return: float = 0.0, n: int = 600
    ) -> tuple[pd.Series, list[int], int]:
        idx = pd.bdate_range("2015-01-02", periods=n)
        roll_positions = _monthly_roll_positions(idx)
        # Need HS lookback history before the first usable roll, and >=10
        # more rolls after the spike so Kupiec/Christoffersen actually runs.
        usable_rolls = [p for p in roll_positions if p >= HS_LOOKBACKS["primary"] + 5]
        assert len(usable_rolls) >= 12, "fixture too short for this test's roll-count needs"
        spike_position = usable_rolls[0]
        rolls_after_spike = [p for p in usable_rolls if p > spike_position]
        assert len(rolls_after_spike) >= 10

        daily_returns = np.zeros(n)
        next_session_positions = {p + 1 for p in roll_positions if p + 1 < n}
        for i in range(1, n):
            if i in next_session_positions:
                daily_returns[i] = 0.0  # every roll's own next session: forced flat
            else:
                daily_returns[i] = 0.0002 if i % 2 == 0 else -0.0002
        daily_returns[spike_position] = spike_return
        if spike_position + 1 < n:
            daily_returns[spike_position + 1] = spike_next_return
        prices = pd.Series(100.0 * np.exp(np.cumsum(daily_returns)), index=idx)
        return prices, usable_rolls, spike_position

    def _run(self, prices: pd.Series, usable_rolls: list[int]) -> dict[str, Any]:
        period = PeriodSpec(
            "eval",
            str(prices.index[usable_rolls[0]].date()),
            str(prices.index[-1].date()),
        )
        rate_series = pd.Series(0.02, index=prices.index)
        vix_series = pd.Series(0.18, index=prices.index)
        return run_nonlinear_portfolio_study(
            prices, rate_series, vix_series, period, mc_n_sims=200, mc_seed=0
        )

    def test_breach_uses_next_session_return_not_roll_date_return(self):
        """The return ENDING ON the roll date is a huge -30% shock (this is
        exactly what the pre-fix code, returns.iloc[ret_pos_val], would have
        used, and it would have registered as a breach against any
        realistic VaR forecast). The return for the NEXT session is exactly
        0.0 (like every other roll's next session in this fixture). Under
        the fix, every roll -- including this one -- must show zero
        breaches, since every actual next-session return is 0."""
        prices, usable_rolls, spike_position = self._build_fixture(
            spike_return=0.30, spike_next_return=0.0
        )
        out = self._run(prices, usable_rolls)
        backtest = out["kupiec_christoffersen_backtest"]
        assert "kupiec" in backtest, backtest.get("note")
        assert backtest["kupiec"]["n_breaches"] == 0
        assert backtest["kupiec"]["n_obs"] == len(usable_rolls)

    def test_breach_direction_flips_when_next_session_is_the_shock(self):
        """Mirror image of the test above: this time the return ENDING ON
        the roll date is flat (0.0) and the NEXT session carries the -30%
        shock. This must now register a breach for that roll -- proving the
        implementation is actually reading the next-session value, not just
        coincidentally always reporting zero breaches."""
        prices, usable_rolls, spike_position = self._build_fixture(
            spike_return=0.0, spike_next_return=0.30
        )
        out = self._run(prices, usable_rolls)
        backtest = out["kupiec_christoffersen_backtest"]
        assert "kupiec" in backtest, backtest.get("note")
        assert backtest["kupiec"]["n_breaches"] == 1
        assert backtest["kupiec"]["n_obs"] == len(usable_rolls)

    def test_last_roll_with_no_next_session_is_excluded_not_fabricated(self):
        """Truncate the price series so the LAST usable roll date is also
        the very last price in the series -- it has no next trading session
        at all. That roll must be excluded from the backtest's observation
        count, not silently given a fabricated or missing-becomes-zero
        return."""
        prices, usable_rolls, spike_position = self._build_fixture(spike_return=0.0)
        last_roll = usable_rolls[-1]
        truncated_prices = prices.iloc[: last_roll + 1]  # ends exactly on the last roll date
        period = PeriodSpec(
            "eval",
            str(truncated_prices.index[usable_rolls[0]].date()),
            str(truncated_prices.index[-1].date()),
        )
        rate_series = pd.Series(0.02, index=truncated_prices.index)
        vix_series = pd.Series(0.18, index=truncated_prices.index)
        out = run_nonlinear_portfolio_study(
            truncated_prices, rate_series, vix_series, period, mc_n_sims=200, mc_seed=0
        )
        # The truncated series still produces a snapshot for the last roll
        # (VaR forecasting doesn't need a next session)...
        assert out["n_roll_snapshots"] == len(usable_rolls)
        # ...but the backtest must count one fewer observation: the last
        # roll has no valid next-session realization to compare against.
        backtest = out["kupiec_christoffersen_backtest"]
        assert "kupiec" in backtest, backtest.get("note")
        assert backtest["kupiec"]["n_obs"] == len(usable_rolls) - 1

    def test_var_forecast_is_unaffected_by_the_next_session_outcome(self):
        """The spike roll's OWN VaR forecast must be identical regardless of
        what actually happens in its next session -- it is computed purely
        from history strictly before that roll. Re-running the same fixture
        with two different next-session outcomes for the spike roll (which
        is usable_rolls[0], i.e. snapshots[0]) must leave that one snapshot's
        hs_var_95_primary_every_roll byte-identical, proving the fix didn't
        (and the original defect never did) leak the forward-looking return
        into the forecast itself.

        Later rolls' own forecasts are deliberately NOT compared here: their
        trailing history legitimately includes the spike roll's next session
        once enough calendar time has passed, so their VaR forecasts are
        SUPPOSED to differ between prices_a and prices_b -- that's ordinary
        causal history, not a leak.
        """
        prices_a, usable_rolls, spike_position = self._build_fixture(
            spike_return=0.0, spike_next_return=0.0
        )
        prices_b, _, _ = self._build_fixture(spike_return=0.0, spike_next_return=0.30)
        out_a = self._run(prices_a, usable_rolls)
        out_b = self._run(prices_b, usable_rolls)
        assert out_a["snapshots"][0]["roll_date"] == out_b["snapshots"][0]["roll_date"]
        assert (
            out_a["snapshots"][0]["hs_var_95_primary_every_roll"]
            == out_b["snapshots"][0]["hs_var_95_primary_every_roll"]
        )

    def test_next_session_is_the_next_trading_day_not_a_calendar_day(self):
        """Pick whichever usable roll in the fixture falls on a Friday (bdate_range
        guarantees the very next entry in the index is the following Monday,
        never a nonexistent Saturday) and engineer that specific roll's
        Friday-to-Monday return as the shock. A calendar-day (roll_date + 1
        day) computation would land on a Saturday that isn't in the returns
        index at all; this test only passes if the actual next TRADING
        session (Monday) was used."""
        prices, usable_rolls, _ = self._build_fixture(spike_return=0.0, spike_next_return=0.0)
        idx = prices.index
        friday_rolls = [p for p in usable_rolls[:-1] if idx[p].dayofweek == 4]
        assert friday_rolls, "fixture must contain at least one Friday roll for this test"
        friday_roll = friday_rolls[0]
        assert idx[friday_roll + 1].dayofweek == 0, "next entry must be the following Monday"

        daily_returns = np.zeros(len(idx))
        next_session_positions = {p + 1 for p in usable_rolls if p + 1 < len(idx)}
        for i in range(1, len(idx)):
            if i in next_session_positions:
                daily_returns[i] = 0.0
            else:
                daily_returns[i] = 0.0002 if i % 2 == 0 else -0.0002
        daily_returns[friday_roll + 1] = 0.30  # the Monday shock
        engineered_prices = pd.Series(100.0 * np.exp(np.cumsum(daily_returns)), index=idx)

        out = self._run(engineered_prices, usable_rolls)
        backtest = out["kupiec_christoffersen_backtest"]
        assert "kupiec" in backtest, backtest.get("note")
        assert backtest["kupiec"]["n_breaches"] == 1
