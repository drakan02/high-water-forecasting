"""Independently score persisted high-water forecasts against persisted labels."""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
AUDIT_ID = "20261108-p0-p7-paper-comparison"
DEFAULT_OUT = ROOT / "reports/audit" / AUDIT_ID
DESIGNS = [
    {
        "design_id": "chronological_fit_through_2004",
        "forecast": "data/clean/p4_gauge_only_ecm/chronological_fit_through_2004/forecasts_unscored.parquet",
        "labels": "data/clean/p3_gauge_only_peaks/chronological_fit_through_2004/high_water_context.parquet",
    },
    {
        "design_id": "retrospective_1988_2007",
        "forecast": "data/clean/p4_gauge_only_ecm/retrospective_1988_2007/forecasts_unscored.parquet",
        "labels": "data/clean/p3_gauge_only_peaks/retrospective_1988_2007/high_water.parquet",
    },
    {
        "design_id": "avonmouth_transfer_2010_fit_1990_2009",
        "forecast": "data/clean/p5_transfer_2010/ecm/avonmouth_transfer_2010_fit_1990_2009/forecasts_unscored.parquet",
        "labels": "data/clean/p5_transfer_2010/high_water_2010.parquet",
    },
]


def audit_design(forecasts: pd.DataFrame, labels: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return paired per-cycle detail and one wide, independently computed row per split."""
    if forecasts.cycle_id.duplicated().any():
        raise ValueError("Forecast cycle_id must be unique")
    if labels.cycle_id.duplicated().any():
        raise ValueError("Label cycle_id must be unique")
    if forecasts.design_id.nunique() != 1:
        raise ValueError("Each forecast file must contain one design_id")
    if set(forecasts.branch.dropna().unique()) != {"gauge_only"}:
        raise ValueError("Expected gauge_only forecasts")
    forecast_columns = [
        "station_id", "branch", "design_id", "cycle_number", "cycle_id", "forecast_origin_utc",
        "forecast_target_time_utc", "issue_lead_hours", "target_type", "forecast_inputs_available",
        "prediction_exclusion_reason", "P_base_m", "P_ecm_m", "ECM_correction_m", "model_id",
        "model_sha256", "C1", "C2", "C3", "C4_intercept_m", "lag_n_minus_2_cycle_id",
        "lag_n_minus_2_cycle_number",
        "lag_n_minus_2_e_m", "lag_n_minus_2_H_peak_time_utc", "lag_n_minus_2_available_at_origin",
        "lag_n_minus_4_cycle_id", "lag_n_minus_4_e_m", "lag_n_minus_4_H_peak_time_utc",
        "lag_n_minus_4_cycle_number",
        "lag_n_minus_4_available_at_origin", "lag_n_minus_6_cycle_id", "lag_n_minus_6_e_m",
        "lag_n_minus_6_H_peak_time_utc", "lag_n_minus_6_available_at_origin", "split",
        "lag_n_minus_6_cycle_number",
    ]
    label_columns = [
        "cycle_id", "H_peak_m", "H_peak_time_utc", "high_water_eligible", "exclusion_reason",
        "gauge_valid_hourly_samples", "expected_hourly_samples", "gauge_coverage_fraction",
    ]
    missing_forecast = set(forecast_columns).difference(forecasts.columns)
    missing_labels = set(label_columns).difference(labels.columns)
    if missing_forecast or missing_labels:
        raise ValueError(f"Missing columns: forecasts={sorted(missing_forecast)}, labels={sorted(missing_labels)}")
    f = forecasts[forecast_columns].copy()
    l = labels[label_columns].copy()
    for col in ("forecast_origin_utc", "forecast_target_time_utc", "lag_n_minus_2_H_peak_time_utc",
                "lag_n_minus_4_H_peak_time_utc", "lag_n_minus_6_H_peak_time_utc"):
        f[col] = pd.to_datetime(f[col], utc=True)
    l["H_peak_time_utc"] = pd.to_datetime(l["H_peak_time_utc"], utc=True)
    detail = f.merge(l, how="left", on="cycle_id", validate="one_to_one", indicator=True)
    detail["target_present"] = detail.pop("_merge").eq("both")
    detail["target_eligible"] = detail["high_water_eligible"].fillna(False).astype(bool)
    detail["both_predictions_present"] = detail["P_base_m"].notna() & detail["P_ecm_m"].notna()
    detail["paired_eligible"] = (
        detail["forecast_inputs_available"].fillna(False).astype(bool)
        & detail["target_present"] & detail["target_eligible"]
        & detail["H_peak_m"].notna() & detail["both_predictions_present"]
    )
    detail["error_base_cm"] = (detail["H_peak_m"] - detail["P_base_m"]) * 100
    detail["error_ecm_cm"] = (detail["H_peak_m"] - detail["P_ecm_m"]) * 100
    detail.loc[~detail.paired_eligible, ["error_base_cm", "error_ecm_cm"]] = np.nan
    detail["abs_error_gain_cm"] = detail["error_base_cm"].abs() - detail["error_ecm_cm"].abs()
    detail.loc[~detail.paired_eligible, "abs_error_gain_cm"] = np.nan

    for lag in (2, 4, 6):
        ts = detail[f"lag_n_minus_{lag}_H_peak_time_utc"]
        flag = detail[f"lag_n_minus_{lag}_available_at_origin"].fillna(False).astype(bool)
        valid_times = ts.notna()
        if (flag & valid_times & ts.gt(detail.forecast_origin_utc)).any():
            raise AssertionError(f"Lag N-{lag} is later than forecast origin")
        if (detail.forecast_inputs_available & ~flag).any():
            raise AssertionError(f"Forecast marked available despite unavailable N-{lag}")
    for lag in (2, 4, 6):
        lag_numbers = detail.cycle_number - lag
        stored_numbers = detail[f"lag_n_minus_{lag}_cycle_number"]
        valid_rows = detail.forecast_inputs_available.fillna(False).astype(bool)
        if not stored_numbers.loc[valid_rows].astype(int).equals(lag_numbers.loc[valid_rows].astype(int)):
            raise AssertionError(f"N-{lag} cycle number does not match the cycle sequence")
        if not detail.loc[valid_rows, f"lag_n_minus_{lag}_cycle_id"].ne("").all():
            raise AssertionError(f"Forecast available with missing N-{lag} cycle ID")
        if not detail.loc[valid_rows, f"lag_n_minus_{lag}_e_m"].notna().all():
            raise AssertionError(f"Forecast available with missing N-{lag} residual")
    detail["abs_error_outcome"] = np.select(
        [detail.abs_error_gain_cm.gt(1e-12), detail.abs_error_gain_cm.lt(-1e-12)],
        ["ECM_lower_absolute_error", "ECM_higher_absolute_error"], default="equal_within_1e-12_cm",
    )
    detail.loc[~detail.paired_eligible, "abs_error_outcome"] = "not_paired"

    summaries = []
    for split, group in detail.groupby("split", sort=True):
        paired = group[group.paired_eligible]
        eb = paired.error_base_cm.to_numpy(float)
        ee = paired.error_ecm_cm.to_numpy(float)
        n = len(paired)
        base_mae = float(np.mean(np.abs(eb))) if n else np.nan
        ecm_mae = float(np.mean(np.abs(ee))) if n else np.nan
        base_rmse = float(np.sqrt(np.mean(eb**2))) if n else np.nan
        ecm_rmse = float(np.sqrt(np.mean(ee**2))) if n else np.nan
        summaries.append({
            "design_id": str(group.design_id.iloc[0]), "split": str(split),
            "candidate_cycles": int(len(group)),
            "target_labels_present": int(group.target_present.sum()),
            "target_qc_eligible": int(group.target_eligible.sum()),
            "forecast_inputs_available": int(group.forecast_inputs_available.fillna(False).sum()),
            "both_predictions_present": int(group.both_predictions_present.sum()),
            "paired_n": int(n),
            "target_qc_only_not_forecastable": int((group.target_eligible & ~group.forecast_inputs_available.fillna(False)).sum()),
            "forecastable_target_qc_invalid": int((group.forecast_inputs_available.fillna(False) & ~group.target_eligible).sum()),
            "baseline_MAE_cm": base_mae, "ECM_MAE_cm": ecm_mae,
            "gain_MAE_cm": base_mae - ecm_mae,
            "gain_MAE_pct": (base_mae - ecm_mae) / base_mae * 100 if n and base_mae else np.nan,
            "baseline_RMSE_cm": base_rmse, "ECM_RMSE_cm": ecm_rmse,
            "gain_RMSE_cm": base_rmse - ecm_rmse,
            "baseline_bias_cm": float(np.mean(eb)) if n else np.nan,
            "ECM_bias_cm": float(np.mean(ee)) if n else np.nan,
            "ECM_lower_abs_error_n": int(paired.abs_error_gain_cm.gt(1e-12).sum()),
            "ECM_higher_abs_error_n": int(paired.abs_error_gain_cm.lt(-1e-12).sum()),
            "equal_abs_error_n": int(paired.abs_error_gain_cm.abs().le(1e-12).sum()),
            "target_type": str(group.target_type.iloc[0]),
            "issue_lead_hours": float(group.issue_lead_hours.iloc[0]),
            "surge_status": "unavailable_not_inferred",
        })
    return detail, pd.DataFrame(summaries)


def run(output_dir: Path = DEFAULT_OUT) -> tuple[pd.DataFrame, pd.DataFrame]:
    output_dir = output_dir if output_dir.is_absolute() else ROOT / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    all_details, all_summaries = [], []
    for design in DESIGNS:
        forecasts = pd.read_parquet(ROOT / design["forecast"])
        labels = pd.read_parquet(ROOT / design["labels"])
        detail, summary = audit_design(forecasts, labels)
        expected_design = design["design_id"]
        if set(summary.design_id) != {expected_design}:
            raise AssertionError(f"Unexpected design_id for {expected_design}")
        detail_path = output_dir / f"{expected_design}_paired_detail.csv"
        detail.to_csv(detail_path, index=False)
        all_details.append(detail)
        all_summaries.append(summary)
    details = pd.concat(all_details, ignore_index=True)
    summaries = pd.concat(all_summaries, ignore_index=True)
    details.to_csv(output_dir / "paired_detail.csv", index=False)
    summaries.to_csv(output_dir / "paired_metrics.csv", index=False)
    return details, summaries


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    detail, metrics = run(args.output_dir)
    print(metrics.to_string(index=False))
    print(f"Wrote {len(detail)} forecast/label joined rows to {args.output_dir}")
