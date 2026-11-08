from __future__ import annotations

import pandas as pd
import numpy as np

from tide.audit_metrics import audit_design


def test_audit_pairing_and_metrics_known_example() -> None:
    origins = pd.to_datetime(["2007-01-01T00:00Z"] * 3, utc=True)
    forecasts = pd.DataFrame({
        "station_id": ["avonmouth"] * 3,
        "branch": ["gauge_only"] * 3,
        "design_id": ["test_design"] * 3,
        "cycle_number": [20, 21, 22],
        "cycle_id": ["c20", "c21", "c22"],
        "forecast_origin_utc": origins,
        "forecast_target_time_utc": pd.to_datetime(["2007-01-02T00:00Z", "2007-01-02T12:00Z", "2007-01-03T00:00Z"], utc=True),
        "issue_lead_hours": [24.0] * 3,
        "target_type": ["total_observed_water_level_gauge_only"] * 3,
        "forecast_inputs_available": [True, True, False],
        "prediction_exclusion_reason": ["", "", "missing_lag"],
        "P_base_m": [10.0, 10.0, float("nan")],
        "P_ecm_m": [10.1, 9.9, float("nan")],
        "ECM_correction_m": [0.1, -0.1, float("nan")],
        "model_id": ["test"] * 3,
        "model_sha256": ["abc"] * 3,
        "C1": [0.1] * 3, "C2": [0.0] * 3, "C3": [0.0] * 3, "C4_intercept_m": [0.0] * 3,
        "split": ["test_2007"] * 3,
    })
    for lag in (2, 4, 6):
        forecasts[f"lag_n_minus_{lag}_cycle_number"] = forecasts.cycle_number - lag
        forecasts[f"lag_n_minus_{lag}_cycle_id"] = [f"lag-{lag}-{n}" for n in forecasts.cycle_number]
        forecasts[f"lag_n_minus_{lag}_e_m"] = [0.01] * 3
        forecasts[f"lag_n_minus_{lag}_H_peak_time_utc"] = pd.to_datetime(["2006-12-31T00:00Z"] * 3, utc=True)
        forecasts[f"lag_n_minus_{lag}_available_at_origin"] = [True, True, False]
    labels = pd.DataFrame({
        "cycle_id": ["c20", "c21", "c22"],
        "H_peak_m": [10.2, 9.8, 11.0],
        "H_peak_time_utc": pd.to_datetime(["2007-01-02T00:00Z", "2007-01-02T12:00Z", "2007-01-03T00:00Z"], utc=True),
        "high_water_eligible": [True, True, False],
        "exclusion_reason": ["", "", "gap"],
        "gauge_valid_hourly_samples": [12, 12, 11],
        "expected_hourly_samples": [12, 12, 12],
        "gauge_coverage_fraction": [1.0, 1.0, 11 / 12],
    })

    detail, summary = audit_design(forecasts, labels)
    result = summary.iloc[0]
    assert result.candidate_cycles == 3
    assert result.target_qc_eligible == 2
    assert result.forecast_inputs_available == 2
    assert result.paired_n == 2
    assert np.isclose(result.baseline_MAE_cm, 20.0)
    assert np.isclose(result.ECM_MAE_cm, 10.0)
    assert np.isclose(result.gain_MAE_cm, 10.0)
    assert np.isclose(result.gain_MAE_pct, 50.0)
    assert result.ECM_lower_abs_error_n == 2
    assert detail.loc[~detail.paired_eligible, "error_base_cm"].isna().all()
