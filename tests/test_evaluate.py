from __future__ import annotations

import numpy as np
import pandas as pd

from tide.evaluate import paper_comparison, score_joined_cycles


def _forecast_and_labels():
    forecast = pd.DataFrame({
        "cycle_id": ["c1", "c2", "c3"],
        "split": ["test_2007"]*3,
        "design_id": ["chronological_fit_through_2004"]*3,
        "forecast_inputs_available": [True, True, False],
        "P_base_m": [5.0, 5.0, np.nan],
        "P_ecm_m": [5.05, 4.95, np.nan],
    })
    labels = pd.DataFrame({
        "cycle_id": ["c1", "c2", "c3"],
        "H_peak_m": [5.1, 4.9, 5.3],
        "H_peak_time_utc": pd.to_datetime(["2007-01-05T03:00Z", "2007-02-05T03:00Z", "2007-03-05T03:00Z"], utc=True),
        "high_water_eligible": [True, False, True],
        "exclusion_reason": ["", "gap", ""],
    })
    return forecast, labels


def test_metrics_use_one_common_paired_sample_and_coverage_is_separate() -> None:
    forecast, labels = _forecast_and_labels()
    joined, metrics, gains, monthly = score_joined_cycles(forecast, labels)

    assert int(joined.paired_eligible.sum()) == 1
    base = metrics.loc[metrics.model.eq("harmonic_baseline")].iloc[0]
    ecm = metrics.loc[metrics.model.eq("gauge_only_ecm")].iloc[0]
    assert base.paired_n == ecm.paired_n == 1
    assert np.isclose(base.MAE_cm, 10.0) and np.isclose(ecm.MAE_cm, 5.0)
    assert np.isclose(gains.iloc[0].MAE_gain_cm, 5.0)
    assert len(monthly) == 6


def test_gauge_only_comparison_never_emits_numeric_paper_delta() -> None:
    forecast, labels = _forecast_and_labels()
    _, metrics, _, _ = score_joined_cycles(forecast, labels)
    comparison = paper_comparison(metrics)
    assert comparison.delta_vs_paper.isna().all()
    row = comparison.loc[comparison.period.eq("2007")]
    assert row.comparability.str.contains("not_comparable").all()
