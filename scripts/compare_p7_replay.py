"""Compare the clean P1-P6 replay with accepted outputs and save evidence."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPLAY = ROOT / "data/p7_replay"
RESULTS: list[dict[str, object]] = []


def compare(label: str, accepted: Path, replayed: Path, key: str,
            numeric: tuple[str, ...], categorical: tuple[str, ...] = (),
            tolerance: float = 1e-10) -> None:
    left = pd.read_parquet(accepted) if accepted.suffix == ".parquet" else pd.read_csv(accepted)
    right = pd.read_parquet(replayed) if replayed.suffix == ".parquet" else pd.read_csv(replayed)
    if key not in left or key not in right:
        raise AssertionError(f"{label}: key {key!r} missing")
    if left[key].astype(str).tolist() != right[key].astype(str).tolist():
        left = left.sort_values(key).reset_index(drop=True)
        right = right.sort_values(key).reset_index(drop=True)
        assert left[key].astype(str).tolist() == right[key].astype(str).tolist(), f"{label}: IDs/order differ"
    assert len(left) == len(right), f"{label}: count differs"
    max_diff = 0.0
    for column in numeric:
        a = pd.to_numeric(left[column], errors="coerce").to_numpy(float)
        b = pd.to_numeric(right[column], errors="coerce").to_numpy(float)
        assert np.array_equal(np.isnan(a), np.isnan(b)), f"{label}.{column}: null mask differs"
        valid = np.isfinite(a)
        diff = float(np.max(np.abs(a[valid] - b[valid]))) if valid.any() else 0.0
        max_diff = max(max_diff, diff)
        assert diff <= tolerance, f"{label}.{column}: max diff {diff} > {tolerance}"
    for column in categorical:
        a = left[column].astype("string").fillna("<NA>").tolist()
        b = right[column].astype("string").fillna("<NA>").tolist()
        assert a == b, f"{label}.{column}: categorical values differ"
    RESULTS.append({"artifact": label, "rows": len(left), "key": key, "max_abs_numeric_diff": max_diff,
                    "tolerance": tolerance, "status": "PASS"})


def run() -> pd.DataFrame:
    compare("P1 hourly", ROOT / "data/clean/avonmouth_2007_gesla_gauge_only/hourly.parquet",
            REPLAY / "p1/hourly.parquet", "time_utc", ("level_m_raw", "level_m"),
            ("analysis_valid", "source_qc_flag", "source_use_flag", "qc_reason"))
    for design in ("chronological_fit_through_2004", "retrospective_1988_2007"):
        folder = f"data/clean/p2_gauge_only/{design}"
        replay = REPLAY / "p2" / design
        compare(f"P2 hourly {design}", ROOT / folder / "harmonic_hourly.parquet", replay / "harmonic_hourly.parquet",
                "time_utc", ("H_m", "A_m", "residual_m"), ("qc_status", "model_id", "design_id"))
        compare(f"P2 coefficients {design}", ROOT / folder / "harmonic_coefficients.csv", replay / "harmonic_coefficients.csv",
                "constituent", ("amplitude_m", "phase_greenwich_deg", "mean_m", "trend_m_per_day"),
                ("model_id", "fit_start_utc", "fit_end_utc"), 1e-9)
        compare(f"P3 cycles {design}", ROOT / f"data/clean/p3_gauge_only_peaks/{design}/high_water_context.parquet",
                REPLAY / f"p3/{design}/high_water_context.parquet", "cycle_id",
                ("A_peak_m", "H_peak_m", "gauge_coverage_fraction"),
                ("A_peak_time_utc", "H_peak_time_utc", "high_water_eligible", "exclusion_reason"))
        compare(f"P4 forecasts {design}", ROOT / f"data/clean/p4_gauge_only_ecm/{design}/forecasts_unscored.parquet",
                REPLAY / f"p4/{design}/forecasts_unscored.parquet", "cycle_id",
                ("P_base_m", "P_ecm_m", "C1", "C2", "C3", "C4_intercept_m"),
                ("forecast_inputs_available", "forecast_status", "split"))
    compare("P5 transfer labels", ROOT / "data/clean/p5_transfer_2010/high_water_2010.parquet",
            REPLAY / "p5_transfer/high_water_2010.parquet", "cycle_id", ("A_peak_m", "H_peak_m"),
            ("high_water_eligible", "exclusion_reason", "H_peak_time_utc"))
    transfer_design = "avonmouth_transfer_2010_fit_1990_2009"
    compare("P5 transfer forecasts", ROOT / f"data/clean/p5_transfer_2010/ecm/{transfer_design}/forecasts_unscored.parquet",
            REPLAY / f"p5_transfer/ecm/{transfer_design}/forecasts_unscored.parquet", "cycle_id",
            ("P_base_m", "P_ecm_m", "C1", "C2", "C3", "C4_intercept_m"),
            ("forecast_inputs_available", "forecast_status", "split"))
    compare("P5 paired metrics", ROOT / "data/clean/p5_gauge_only_evaluation/paired_metrics.csv",
            REPLAY / "p5_evaluation/paired_metrics.csv", "design_id", ("paired_n", "MAE_cm", "RMSE_cm", "bias_cm"),
            ("split", "model"), 1e-6)
    for table, key, numeric, categorical in (
        ("FactForecast", "fact_forecast_key", ("observed_H_m", "prediction_m", "error_cm"), ("paired_eligible", "model_key", "cycle_id")),
        ("FactQuality", "fact_quality_key", ("H_hourly_m", "A_m", "residual_m"), ("hourly_valid", "qc_reason")),
        ("FactSpectrum", "spectrum_key", ("frequency_cycles_per_hour", "psd_m2_per_cycle_per_hour"), ("design_id", "model_key")),
    ):
        compare(f"P6 {table}", ROOT / f"data/bi_handoff/{table}.parquet", REPLAY / f"bi_handoff/{table}.parquet",
                key, numeric, categorical, 1e-9)
    result = pd.DataFrame(RESULTS)
    result.to_csv(ROOT / "reports/p7_replay/comparison.csv", index=False)
    return result


if __name__ == "__main__":
    print(run().to_string(index=False))
