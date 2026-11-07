"""Leakage-aware gauge-only empirical high-water correction forecasts."""
from __future__ import annotations

from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd
import yaml

LAG_STEPS = (2, 4, 6)


def build_forecast_inputs(
    high_water: pd.DataFrame,
    *,
    issue_lead_hours: float = 24.0,
    lag_steps: tuple[int, ...] = LAG_STEPS,
) -> pd.DataFrame:
    """Join lag predictors by immutable cycle number and enforce issue-time availability."""
    required = {
        "cycle_number", "cycle_id", "design_id", "A_peak_time_utc", "A_peak_m",
        "H_peak_time_utc", "H_peak_m", "H_minus_A_gauge_only_m", "high_water_eligible",
    }
    missing = required.difference(high_water.columns)
    if missing:
        raise ValueError(f"Missing high-water fields: {', '.join(sorted(missing))}")
    data = high_water.copy().sort_values("cycle_number").reset_index(drop=True)
    if data["cycle_number"].duplicated().any() or data["cycle_id"].duplicated().any():
        raise ValueError("High-water context must have unique cycle numbers and IDs")
    data["A_peak_time_utc"] = pd.to_datetime(data["A_peak_time_utc"], utc=True)
    data["H_peak_time_utc"] = pd.to_datetime(data["H_peak_time_utc"], utc=True)
    lookup = data.set_index("cycle_number", drop=False)
    records = []
    for target in data.itertuples(index=False):
        origin = target.A_peak_time_utc - pd.Timedelta(hours=issue_lead_hours)
        row = {
            "station_id": "avonmouth",
            "branch": "gauge_only",
            "design_id": target.design_id,
            "cycle_number": int(target.cycle_number),
            "cycle_id": target.cycle_id,
            "forecast_target_time_utc": target.A_peak_time_utc,
            "forecast_origin_utc": origin,
            "issue_lead_hours": float(issue_lead_hours),
            "A_N_m": float(target.A_peak_m),
            "target_type": "total_observed_water_level_gauge_only",
            "surge_N_m": np.nan,
            "surge_status": "unavailable_not_inferred",
            "availability_assumed": True,
            "availability_assumption": "QC high-water observation is available at its recorded H_peak_time_utc; no provider latency metadata exists",
        }
        all_lags_available = True
        for lag in lag_steps:
            source_number = int(target.cycle_number) - int(lag)
            prefix = f"lag_n_minus_{lag}"
            row[f"{prefix}_cycle_number"] = source_number
            if source_number not in lookup.index:
                row[f"{prefix}_cycle_id"] = ""
                row[f"{prefix}_e_m"] = np.nan
                row[f"{prefix}_H_peak_time_utc"] = pd.NaT
                row[f"{prefix}_available_at_origin"] = False
                all_lags_available = False
                continue
            source = lookup.loc[source_number]
            if isinstance(source, pd.DataFrame):
                raise ValueError(f"Non-unique source cycle number {source_number}")
            source_time = source["H_peak_time_utc"]
            source_valid = bool(source["high_water_eligible"]) and pd.notna(source_time) and np.isfinite(source["H_minus_A_gauge_only_m"])
            available = bool(source_valid and source_time <= origin)
            row[f"{prefix}_cycle_id"] = source["cycle_id"]
            row[f"{prefix}_e_m"] = float(source["H_minus_A_gauge_only_m"]) if source_valid else np.nan
            row[f"{prefix}_H_peak_time_utc"] = source_time
            row[f"{prefix}_available_at_origin"] = available
            all_lags_available = all_lags_available and available
        row["forecast_inputs_available"] = bool(all_lags_available and np.isfinite(row["A_N_m"]))
        row["prediction_exclusion_reason"] = "" if row["forecast_inputs_available"] else "one_or_more_lag_residuals_missing_or_not_available_at_origin"
        records.append(row)
    return pd.DataFrame.from_records(records)


def fit_ecm_ols(
    design: pd.DataFrame,
    *,
    fit_year: int,
    minimum_samples: int = 20,
) -> tuple[dict[str, object], pd.DataFrame]:
    """Fit delta H_N = H_N - A_N against e_(N-2/-4/-6), with intercept."""
    fit = design.loc[
        design["A_peak_time_utc"].dt.year.eq(fit_year)
        & design["high_water_eligible"].astype(bool)
        & design["forecast_inputs_available"].astype(bool)
    ].copy()
    feature_names = [f"lag_n_minus_{lag}_e_m" for lag in LAG_STEPS]
    fit["target_delta_m"] = pd.to_numeric(fit["H_peak_m"], errors="coerce") - pd.to_numeric(fit["A_peak_m"], errors="coerce")
    fit = fit.dropna(subset=feature_names + ["target_delta_m"])
    if len(fit) < minimum_samples:
        raise ValueError(f"Insufficient forecastable ECM training rows for {fit_year}: {len(fit)} < {minimum_samples}")
    x = fit[feature_names].to_numpy(dtype=float)
    matrix = np.column_stack([x, np.ones(len(x), dtype=float)])
    y = fit["target_delta_m"].to_numpy(dtype=float)
    rank = int(np.linalg.matrix_rank(matrix))
    if rank != matrix.shape[1]:
        raise ValueError(f"ECM training design matrix is rank deficient: rank={rank}, columns={matrix.shape[1]}")
    coef, _, _, _ = np.linalg.lstsq(matrix, y, rcond=None)
    model = {
        "model_id": f"gauge_only_ecm_ols_fit_{fit_year}",
        "fit_year": int(fit_year),
        "fit_rows": int(len(fit)),
        "feature_order": feature_names,
        "C1": float(coef[0]),
        "C2": float(coef[1]),
        "C3": float(coef[2]),
        "C4_intercept_m": float(coef[3]),
        "design_matrix_rank": rank,
        "design_matrix_columns": int(matrix.shape[1]),
        "fit_method": "ordinary least squares with intercept; numpy.linalg.lstsq; no regularization",
        "response": "H_N - A_N (gauge-only total observed level; not surge-corrected)",
        "predictors": "H_(N-2/-4/-6) - A_(N-2/-4/-6), only if QC-valid and available at 24-hour issue origin",
    }
    return model, fit


def apply_ecm_forecasts(inputs: pd.DataFrame, model: dict[str, object]) -> pd.DataFrame:
    """Create pre-label forecasts; this function never consumes target H_N."""
    output = inputs.copy()
    output["model_id"] = str(model["model_id"])
    output["C1"] = float(model["C1"])
    output["C2"] = float(model["C2"])
    output["C3"] = float(model["C3"])
    output["C4_intercept_m"] = float(model["C4_intercept_m"])
    available = output["forecast_inputs_available"].astype(bool)
    output["P_base_m"] = pd.to_numeric(output["A_N_m"], errors="coerce").where(available)
    correction = (
        output["C1"] * output["lag_n_minus_2_e_m"]
        + output["C2"] * output["lag_n_minus_4_e_m"]
        + output["C3"] * output["lag_n_minus_6_e_m"]
        + output["C4_intercept_m"]
    )
    output["ECM_correction_m"] = correction.where(available)
    output["P_ecm_m"] = (output["P_base_m"] + output["ECM_correction_m"]).where(available)
    output["forecast_status"] = np.where(available, "issued_at_configured_origin", output["prediction_exclusion_reason"])
    # Target observations are intentionally absent; evaluation joins them in P5.
    return output


def run_empirical(config_path: Path) -> dict[str, object]:
    config = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    output_root = Path(config["output_dir"])
    output_root.mkdir(parents=True, exist_ok=True)
    summaries = []
    for design_cfg in config["designs"]:
        context_path = Path(design_cfg["high_water_context"])
        peaks = pd.read_parquet(context_path)
        peaks["A_peak_time_utc"] = pd.to_datetime(peaks["A_peak_time_utc"], utc=True)
        features = build_forecast_inputs(
            peaks,
            issue_lead_hours=float(config["issue_lead_hours"]),
            lag_steps=tuple(int(value) for value in config["lag_steps"]),
        )
        design_id = str(design_cfg["design_id"])
        mode = str(design_cfg["mode"])
        fit_year = int(design_cfg["fit_year"])
        fit_data = features.merge(
            peaks[["cycle_number", "H_peak_m", "A_peak_m", "high_water_eligible", "exclusion_reason"]],
            on="cycle_number", how="left", validate="one_to_one",
        )
        fit_data["A_peak_time_utc"] = fit_data["forecast_target_time_utc"]
        model, fit_rows = fit_ecm_ols(
            fit_data, fit_year=fit_year, minimum_samples=int(config["minimum_fit_rows"]),
        )
        # The fit uses joined training labels; forecast inputs remain a separate pre-label table.
        design_dir = output_root / design_id
        design_dir.mkdir(parents=True, exist_ok=True)
        model_path = design_dir / "ecm_model.json"
        model_path.write_text(json.dumps(model, indent=2), encoding="utf-8")
        model_hash = hashlib.sha256(model_path.read_bytes()).hexdigest()
        fit_rows_path = design_dir / "ecm_fit_rows.csv"
        fit_rows.to_csv(fit_rows_path, index=False)

        if mode == "chronological":
            # Training labels are saved separately; never publish in-sample training predictions as issued forecasts.
            forecast_years = [int(design_cfg["validation_year"]), int(design_cfg["score_year"])]
            split_map = {forecast_years[0]: f"validation_{forecast_years[0]}", forecast_years[1]: f"test_{forecast_years[1]}"}
        elif mode == "retrospective":
            forecast_years = [int(design_cfg["score_year"])]
            split_map = {forecast_years[0]: "retrospective_in_sample_2007"}
        else:
            raise ValueError(f"Unknown design mode {mode!r}")
        forecast_parts = []
        exclusions = []
        for year in forecast_years:
            selected = features.loc[features["forecast_target_time_utc"].dt.year.eq(year)].copy()
            selected["split"] = split_map[year]
            predictions = apply_ecm_forecasts(selected, model)
            predictions["model_sha256"] = model_hash
            forecast_parts.append(predictions)
            exclusions.append(predictions.loc[~predictions["forecast_inputs_available"]].copy())
        forecast = pd.concat(forecast_parts, ignore_index=True)
        # Prevent accidental target leakage in the forecast artifact.
        forbidden = {"H_peak_m", "H_minus_A_gauge_only_m", "target_delta_m"}
        if forbidden.intersection(forecast.columns):
            raise AssertionError(f"Forecast artifact contains target/response columns: {forbidden.intersection(forecast.columns)}")
        forecast_path = design_dir / "forecasts_unscored.parquet"
        forecast_csv_path = design_dir / "forecasts_unscored.csv"
        exclusions_path = design_dir / "prediction_exclusions.csv"
        forecast.to_parquet(forecast_path, index=False)
        forecast.to_csv(forecast_csv_path, index=False)
        pd.concat(exclusions, ignore_index=True).to_csv(exclusions_path, index=False)
        summary = {
            "design_id": design_id,
            "mode": mode,
            "fit_year": fit_year,
            "fit_rows": model["fit_rows"],
            "design_matrix_rank": model["design_matrix_rank"],
            "design_matrix_columns": model["design_matrix_columns"],
            "coefficients": {key: model[key] for key in ("C1", "C2", "C3", "C4_intercept_m")},
            "issue_lead_hours": float(config["issue_lead_hours"]),
            "forecast_rows": len(forecast),
            "forecastable_rows": int(forecast["forecast_inputs_available"].sum()),
            "excluded_rows": int((~forecast["forecast_inputs_available"]).sum()),
            "model_sha256": model_hash,
            "model_path": str(model_path),
            "fit_rows_path": str(fit_rows_path),
            "forecast_path": str(forecast_path),
            "forecast_csv_path": str(forecast_csv_path),
            "prediction_exclusions_path": str(exclusions_path),
            "surge_status": "unavailable; gauge-only correction predicts total H_N and is not Table 1b-comparable",
        }
        (design_dir / "run_manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        summaries.append(summary)
    summary_path = output_root / "p4_run_summary.json"
    summary_path.write_text(json.dumps(summaries, indent=2), encoding="utf-8")
    return {"designs": summaries, "summary": str(summary_path)}
