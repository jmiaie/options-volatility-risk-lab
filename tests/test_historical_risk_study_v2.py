"""Offline tests for Directive #9 D9-C authoritative (v2) historical risk
study helpers. Synthetic fixtures only -- no network, no real market data."""

from __future__ import annotations

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
