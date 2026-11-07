"""Build portable CSV/Parquet star-schema tables for the P5 gauge-only pilot."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/bi_handoff"
DESIGNS = [
    "chronological_fit_through_2004",
    "retrospective_1988_2007",
    "avonmouth_transfer_2010_fit_1990_2009",
]


def _write_table(name: str, frame: pd.DataFrame) -> None:
    frame.to_csv(OUT / f"{name}.csv", index=False)
    frame.to_parquet(OUT / f"{name}.parquet", index=False)


def build() -> dict[str, object]:
    OUT.mkdir(parents=True, exist_ok=True)
    score_root = ROOT / "data/clean/p5_gauge_only_evaluation"
    forecast_wide = pd.concat(
        [pd.read_parquet(score_root / d / "scored_high_water.parquet") for d in DESIGNS],
        ignore_index=True,
    )
    forecast_rows = []
    for _, row in forecast_wide.iterrows():
        common = {
            "station_key": "avonmouth", "cycle_id": row.cycle_id,
            "design_id": row.design_id, "split": row.split,
            "target_date": pd.Timestamp(row.H_peak_time_utc).date().isoformat() if pd.notna(row.H_peak_time_utc) else "",
            "target_time_utc": row.H_peak_time_utc,
            "forecast_origin_utc": row.forecast_origin_utc,
            "issue_lead_hours": row.issue_lead_hours,
            "target_type": row.target_type,
            "forecast_inputs_available": bool(row.forecast_inputs_available),
            "target_present": bool(row.target_present),
            "target_eligible": bool(row.high_water_eligible) if pd.notna(row.high_water_eligible) else False,
            "paired_eligible": bool(row.paired_eligible),
            "paired_sample_id": row.paired_sample_id,
            "observed_H_m": row.H_peak_m,
            "surge_m": row.surge_N_m,
            "surge_status": row.surge_status,
            "A_N_m": row.A_N_m,
            "lag_n_minus_2_cycle_id": row.lag_n_minus_2_cycle_id,
            "lag_n_minus_2_e_m": row.lag_n_minus_2_e_m,
            "lag_n_minus_4_cycle_id": row.lag_n_minus_4_cycle_id,
            "lag_n_minus_4_e_m": row.lag_n_minus_4_e_m,
            "lag_n_minus_6_cycle_id": row.lag_n_minus_6_cycle_id,
            "lag_n_minus_6_e_m": row.lag_n_minus_6_e_m,
            "ECM_correction_m": row.ECM_correction_m,
            "model_sha256": row.model_sha256,
            "exclusion_reason": row.exclusion_reason or row.prediction_exclusion_reason,
        }
        for model_id, prediction, error in (
            ("harmonic_baseline", row.P_base_m, row.error_base_cm),
            ("gauge_only_ecm", row.P_ecm_m, row.error_ecm_cm),
        ):
            forecast_rows.append({**common, "model_key": model_id, "prediction_m": prediction, "error_cm": error})
    fact_forecast = pd.DataFrame(forecast_rows)
    fact_forecast["date_key"] = pd.to_datetime(fact_forecast.target_date, errors="coerce").dt.strftime("%Y%m%d")
    fact_forecast["fact_forecast_key"] = fact_forecast.apply(
        lambda r: hashlib.sha256(f"{r.design_id}|{r.cycle_id}|{r.model_key}".encode()).hexdigest()[:20], axis=1
    )

    hourly_path = ROOT / "data/clean/avonmouth_2007_gesla_gauge_only/hourly.parquet"
    hourly = pd.read_parquet(hourly_path)
    harmonic = pd.read_parquet(ROOT / "data/clean/p2_gauge_only/chronological_fit_through_2004/harmonic_hourly.parquet")
    quality = hourly.merge(harmonic[["time_utc", "A_m", "residual_m", "model_id", "design_id"]], on="time_utc", how="left", validate="one_to_one")
    fact_quality = quality.rename(columns={
        "time_utc": "time_utc", "level_m_raw": "H_raw_m", "level_m": "H_hourly_m",
        "analysis_valid": "hourly_valid", "source_qc_flag": "source_qc_flag",
        "source_qc_label": "source_qc_label", "source_use_flag": "source_use_flag",
        "timestamp_present": "timestamp_present", "qc_reason": "qc_reason",
    })[["time_utc", "station_id", "year", "H_raw_m", "H_hourly_m", "A_m", "residual_m",
       "hourly_valid", "source_qc_flag", "source_qc_label", "source_use_flag", "timestamp_present",
       "qc_reason", "datum", "unit", "model_id", "design_id"]].copy()
    fact_quality["station_key"] = "avonmouth"
    fact_quality["date_key"] = pd.to_datetime(fact_quality.time_utc, utc=True).dt.strftime("%Y%m%d")
    fact_quality["fact_quality_key"] = pd.to_datetime(fact_quality.time_utc, utc=True).dt.strftime("%Y%m%d%H%M")

    spectrum_parts = []
    for design in DESIGNS[:2]:
        p = ROOT / f"data/clean/p2_gauge_only/{design}/residual_welch_spectrum.csv"
        part = pd.read_csv(p)
        part["station_key"] = "avonmouth"
        part["model_key"] = "harmonic_baseline"
        part["spectrum_key"] = part.apply(lambda r: f"{design}|{r.frequency_cycles_per_hour:.12g}", axis=1)
        spectrum_parts.append(part)
    fact_spectrum = pd.concat(spectrum_parts, ignore_index=True)

    date_values = pd.concat([
        pd.to_datetime(fact_quality.time_utc, utc=True).dt.floor("D").dt.tz_localize(None),
        pd.to_datetime(fact_forecast.target_date, errors="coerce").dropna().dt.tz_localize(None),
    ]).dropna().drop_duplicates().sort_values()
    dim_date = pd.DataFrame({"date": date_values.dt.date.astype(str)})
    dim_date["date_key"] = pd.to_datetime(dim_date.date).dt.strftime("%Y%m%d")
    dt = pd.to_datetime(dim_date.date)
    dim_date["year"] = dt.dt.year
    dim_date["quarter"] = dt.dt.quarter
    dim_date["month"] = dt.dt.month
    dim_date["month_name"] = dt.dt.month_name()
    dim_date["day"] = dt.dt.day

    dim_station = pd.DataFrame([{
        "station_key": "avonmouth", "station_name": "Avonmouth", "country": "GBR",
        "latitude": 51.50775, "longitude": -2.71275,
        "source": "GESLA S3, BODC lineage", "datum": "unknown", "channel": "unresolved",
        "surge_available": False,
    }])
    dim_model = pd.DataFrame([
        {"model_key": "harmonic_baseline", "model_name": "UTide harmonic baseline", "model_class": "harmonic", "unit": "m", "branch": "gauge_only"},
        {"model_key": "gauge_only_ecm", "model_name": "OLS gauge-only ECM", "model_class": "empirical correction", "unit": "m", "branch": "gauge_only"},
    ])
    dim_run = pd.DataFrame([
        {"design_id": d, "run_key": d, "station_key": "avonmouth",
         "fit_period": {DESIGNS[0]: "harmonic through 2004; ECM fit 2005", DESIGNS[1]: "retrospective harmonic/ECM 1988–2007 in-sample", DESIGNS[2]: "harmonic fit 1990–2009; ECM fit 2009"}[d],
         "evaluation_period": {DESIGNS[0]: "validation 2006 and test 2007", DESIGNS[1]: "in-sample 2007", DESIGNS[2]: "transfer test 2010"}[d],
         "branch": "gauge_only", "issue_lead_hours": 24,
         "surge_status": "unavailable; no surge inferred from H-A",
         "availability_assumption": "QC high-water value available at recorded peak time; provider latency unknown"}
        for d in DESIGNS
    ])

    for name, frame in (("DimStation", dim_station), ("DimDate", dim_date), ("DimModel", dim_model),
                        ("DimRun", dim_run), ("FactForecast", fact_forecast),
                        ("FactQuality", fact_quality), ("FactSpectrum", fact_spectrum)):
        _write_table(name, frame)

    # Filtered expected metrics for the documented overall, month and single-cycle slices.
    checks = []
    paired = fact_forecast[fact_forecast.paired_eligible & fact_forecast.error_cm.notna()]
    slices = [("all_paired", paired)]
    jan = paired[(paired.design_id == DESIGNS[0]) & (paired.split == "test_2007") & (pd.to_datetime(paired.target_time_utc, utc=True).dt.month == 1)]
    slices.append(("chronological_test_2007_january", jan))
    first_cycle = jan.cycle_id.iloc[0]
    slices.append(("single_cycle_" + first_cycle, jan[jan.cycle_id == first_cycle]))
    for slice_name, subset in slices:
        for (design, split, model), group in subset.groupby(["design_id", "split", "model_key"], dropna=False):
            err = group.error_cm.astype(float)
            checks.append({"slice": slice_name, "design_id": design, "split": split, "model_key": model,
                           "paired_cycle_count": group.cycle_id.nunique(), "fact_rows": len(group),
                           "MAE_cm": float(err.abs().mean()), "RMSE_cm": float(np.sqrt(np.square(err).mean()))})
    validation = pd.DataFrame(checks)
    validation.to_csv(OUT / "expected_slice_metrics.csv", index=False)
    validation.to_parquet(OUT / "expected_slice_metrics.parquet", index=False)
    summary = {"tables": {}, "ui_status": "UI_PENDING; no Power BI Desktop available in this Linux environment",
               "validation_slices": ["all pilot by run/model", "chronological test January 2007", f"single cycle {first_cycle}"],
               "paired_policy": "Both model rows share the same cycle eligibility; each measure filters paired_eligible and report page must select one run/target.",
               "source_sha256": hashlib.sha256(hourly_path.read_bytes()).hexdigest()}
    for name, frame in (("DimStation", dim_station), ("DimDate", dim_date), ("DimModel", dim_model),
                        ("DimRun", dim_run), ("FactForecast", fact_forecast),
                        ("FactQuality", fact_quality), ("FactSpectrum", fact_spectrum),
                        ("expected_slice_metrics", validation)):
        summary["tables"][name] = {"rows": len(frame), "columns": frame.columns.tolist()}
    descriptions = {
        "station_key": "Stable station identifier.", "cycle_id": "Immutable high-water cycle identifier.",
        "design_id": "Locked model design and run identifier.", "split": "Chronological validation/test or retrospective split.",
        "target_date": "UTC date of observed high water.", "target_time_utc": "Observed target high-water timestamp in UTC.",
        "forecast_origin_utc": "Forecast issue origin in UTC.", "issue_lead_hours": "Configured lead time from origin to target.",
        "target_type": "Forecast target; this project is gauge-only total observed water level.",
        "forecast_inputs_available": "All required forecast-side inputs were available.",
        "target_present": "Observed target row is present.", "target_eligible": "Target passed P3 peak QC and coverage rules.",
        "paired_eligible": "Common cycle is eligible and has both model predictions.",
        "paired_sample_id": "SHA-256 digest identifying the common cycle set for this run/split.",
        "observed_H_m": "Observed high-water elevation in source metres; datum is unresolved.",
        "surge_m": "Matching surge input; null because no validated product is available.",
        "surge_status": "Explicit availability status; H−A is never treated as surge.",
        "A_N_m": "UTide harmonic prediction at the target event.", "prediction_m": "Model high-water prediction in metres.",
        "error_cm": "Observed total H minus prediction, in centimetres.",
        "model_key": "Stable forecast model key.", "model_sha256": "Hash of persisted fitted model.",
        "lag_n_minus_2_cycle_id": "Cycle ID for lag two high waters earlier.",
        "lag_n_minus_2_e_m": "Gauge-only H−A residual at lag N−2, metres.",
        "lag_n_minus_4_cycle_id": "Cycle ID for lag four high waters earlier.",
        "lag_n_minus_4_e_m": "Gauge-only H−A residual at lag N−4, metres.",
        "lag_n_minus_6_cycle_id": "Cycle ID for lag six high waters earlier.",
        "lag_n_minus_6_e_m": "Gauge-only H−A residual at lag N−6, metres.",
        "ECM_correction_m": "OLS correction in metres.", "exclusion_reason": "Reason target/forecast is excluded, if any.",
        "date_key": "UTC date foreign key formatted YYYYMMDD.",
        "fact_forecast_key": "Stable hash key for design, cycle, and model row.",
        "time_utc": "UTC hourly observation timestamp.", "year": "UTC calendar year.",
        "H_raw_m": "Source level at the exact hourly sample, in metres.",
        "H_hourly_m": "QC-valid hourly observed level in metres; invalid values remain null.",
        "A_m": "UTide harmonic prediction in metres.", "residual_m": "H−A diagnostic residual, not validated surge.",
        "hourly_valid": "P1 analysis-valid flag for the hourly observation.",
        "source_qc_flag": "Original GESLA QC flag.", "source_qc_label": "Readable label for original QC flag.",
        "source_use_flag": "Original source use flag.", "timestamp_present": "Expected timestamp exists in source.",
        "qc_reason": "P1 decision/reason for hourly observation.", "datum": "Vertical datum metadata; source datum unknown.",
        "unit": "Source unit; metres, no datum conversion.", "model_id": "Harmonic model identifier.",
        "fact_quality_key": "Unique station-hour fact key in UTC.",
        "frequency_cycles_per_hour": "Welch frequency axis in cycles per hour.",
        "psd_m2_per_cycle_per_hour": "Welch power spectral density in m²/(cycles/hour).",
        "fs_samples_per_hour": "Sampling frequency used by Welch.", "window": "Welch window function.",
        "nperseg_hours": "Welch segment duration in hours.", "noverlap_hours": "Welch segment overlap in hours.",
        "detrend": "Welch detrending method.", "spectrum_key": "Run/frequency key for spectrum row.",
        "date": "Calendar date in UTC.", "quarter": "Calendar quarter.", "month": "Calendar month number.",
        "month_name": "Calendar month name.", "day": "Day of month.", "station_name": "Readable station name.",
        "country": "ISO country code.", "latitude": "Station latitude in decimal degrees.",
        "longitude": "Station longitude in decimal degrees.", "source": "Source lineage label.",
        "channel": "Original measurement channel; unresolved.", "surge_available": "Whether matched surge is available.",
        "model_name": "Readable model name.", "model_class": "Model family.", "branch": "Experiment target branch.",
        "fit_period": "Training period represented by run.", "evaluation_period": "Evaluation period represented by run.",
        "run_key": "Unique run dimension key.", "availability_assumption": "Forecast-side observation latency assumption.",
        "slice": "Validation slice name.", "paired_cycle_count": "Distinct common cycles in this slice.",
        "fact_rows": "Number of model-specific fact rows in this slice.", "MAE_cm": "Python expected mean absolute error in centimetres.",
        "RMSE_cm": "Python expected root mean square error in centimetres.",
    }
    dictionary_rows = []
    for table, frame in (("DimStation", dim_station), ("DimDate", dim_date), ("DimModel", dim_model),
                         ("DimRun", dim_run), ("FactForecast", fact_forecast),
                         ("FactQuality", fact_quality), ("FactSpectrum", fact_spectrum),
                         ("expected_slice_metrics", validation)):
        for column in frame.columns:
            primary = {"DimStation": {"station_key"}, "DimDate": {"date_key"}, "DimModel": {"model_key"},
                       "DimRun": {"run_key"}, "FactForecast": {"fact_forecast_key"},
                       "FactQuality": {"fact_quality_key"}, "FactSpectrum": {"spectrum_key"},
                       "expected_slice_metrics": set()}
            foreign = {"DimStation": set(), "DimDate": set(), "DimModel": set(), "DimRun": {"station_key"},
                       "FactForecast": {"station_key", "model_key", "design_id", "date_key"},
                       "FactQuality": {"station_key", "date_key"},
                       "FactSpectrum": {"station_key", "model_key", "design_id"},
                       "expected_slice_metrics": set()}
            key_role = "PK" if column in primary[table] else "FK" if column in foreign[table] else ""
            unit = "cm" if column.endswith("_cm") else "m" if column.endswith("_m") or column.endswith("_m2_per_cycle_per_hour") else "UTC" if "utc" in column.lower() or column == "time_utc" else "none"
            dictionary_rows.append({"table": table, "column": column, "dtype": str(frame[column].dtype), "unit": unit,
                                   "key_role": key_role, "description": descriptions.get(column, f"Exported {column} field from {table}.")})
    pd.DataFrame(dictionary_rows).to_csv(ROOT / "reports/powerbi/data_dictionary.csv", index=False)
    (OUT / "manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
