from __future__ import annotations

import numpy as np
import pandas as pd

from tide.empirical import apply_ecm_forecasts, build_forecast_inputs, fit_ecm_ols


def _cycles(n=14):
    peak_times = pd.date_range("2005-01-01 06:00", periods=n, freq="12h", tz="UTC")
    e = np.linspace(-0.06, 0.07, n)
    return pd.DataFrame({
        "cycle_number": np.arange(1, n + 1),
        "cycle_id": [f"c{i}" for i in range(1, n + 1)],
        "design_id": "test",
        "A_peak_time_utc": peak_times,
        "A_peak_m": 5.0 + np.sin(np.arange(n) / 3),
        "H_peak_time_utc": peak_times,
        "H_peak_m": 5.0 + np.sin(np.arange(n) / 3) + e,
        "H_minus_A_gauge_only_m": e,
        "high_water_eligible": True,
        "exclusion_reason": "",
    })


def test_lag_joins_use_exact_cycle_numbers_not_row_position() -> None:
    cycles = _cycles()
    base = build_forecast_inputs(cycles)
    target = base.loc[base.cycle_number.eq(10)].iloc[0]
    assert target.lag_n_minus_2_cycle_id == "c8"
    assert target.lag_n_minus_4_cycle_id == "c6"
    assert target.lag_n_minus_6_cycle_id == "c4"

    missing = cycles.loc[~cycles.cycle_number.eq(8)]
    after_gap = build_forecast_inputs(missing)
    target_after_gap = after_gap.loc[after_gap.cycle_number.eq(10)].iloc[0]
    assert target_after_gap.lag_n_minus_2_cycle_id == ""
    assert not target_after_gap.forecast_inputs_available


def test_lag_peak_must_be_available_at_registered_issue_time() -> None:
    cycles = _cycles()
    # N=10 issues at N's harmonic peak minus 24 h; N-2 is one hour later.
    cycles.loc[cycles.cycle_number.eq(8), "H_peak_time_utc"] += pd.Timedelta(hours=1)
    inputs = build_forecast_inputs(cycles)
    target = inputs.loc[inputs.cycle_number.eq(10)].iloc[0]
    assert not target.lag_n_minus_2_available_at_origin
    assert not target.forecast_inputs_available


def test_future_target_observation_does_not_change_its_own_forecast() -> None:
    cycles = _cycles()
    first = build_forecast_inputs(cycles)
    model = {"model_id":"test", "C1":0.5, "C2":0.25, "C3":0.1, "C4_intercept_m":0.01}
    before = apply_ecm_forecasts(first.loc[first.cycle_number.eq(10)], model)
    cycles.loc[cycles.cycle_number.eq(10), "H_peak_m"] += 100.0
    cycles.loc[cycles.cycle_number.eq(10), "H_minus_A_gauge_only_m"] += 100.0
    after = apply_ecm_forecasts(build_forecast_inputs(cycles).loc[lambda x: x.cycle_number.eq(10)], model)
    np.testing.assert_allclose(before.P_ecm_m, after.P_ecm_m, rtol=0, atol=0)
    assert "H_peak_m" not in before.columns


def test_ols_recovers_registered_three_lag_model_with_intercept() -> None:
    n = 40
    index = np.arange(n, dtype=float)
    x = np.column_stack([np.sin(index / 2), np.cos(index / 3), (index % 7) / 7])
    truth = np.array([0.5, 0.25, 0.1, 0.01])
    target_delta = np.column_stack([x, np.ones(n)]) @ truth
    fit = pd.DataFrame({
        "A_peak_time_utc": pd.date_range("2005-01-01", periods=n, freq="12h", tz="UTC"),
        "high_water_eligible": True,
        "forecast_inputs_available": True,
        "H_peak_m": 5 + target_delta,
        "A_peak_m": 5.0,
        "lag_n_minus_2_e_m": x[:, 0],
        "lag_n_minus_4_e_m": x[:, 1],
        "lag_n_minus_6_e_m": x[:, 2],
    })
    model, rows = fit_ecm_ols(fit, fit_year=2005)
    np.testing.assert_allclose([model["C1"],model["C2"],model["C3"],model["C4_intercept_m"]], truth, rtol=0, atol=1e-12)
    assert len(rows) == n and model["design_matrix_rank"] == 4


def test_ecm_prediction_matches_registered_hand_calculation() -> None:
    inputs = pd.DataFrame({
        "forecast_inputs_available": [True],
        "prediction_exclusion_reason": [""],
        "A_N_m": [5.0],
        "lag_n_minus_2_e_m": [0.10],
        "lag_n_minus_4_e_m": [-0.04],
        "lag_n_minus_6_e_m": [0.02],
    })
    model = {"model_id":"example", "C1":0.5, "C2":0.25, "C3":0.1, "C4_intercept_m":0.01}
    forecast = apply_ecm_forecasts(inputs, model).iloc[0]
    assert abs(forecast.P_ecm_m - 5.052) < 1e-12
    assert abs((5.20 - 5.052 - 0.10) * 100 - 4.8) < 1e-12
    assert abs((5.20 - 5.0 - 0.10) * 100 - 10.0) < 1e-12
