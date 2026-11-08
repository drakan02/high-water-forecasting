"""Resource-bounded Avonmouth public-source ANN substitute experiment."""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import platform

import numpy as np
import pandas as pd
import scipy
from scipy.optimize import minimize
import yaml

from .harmonic import reconstruct_from_saved_state
from .ingest import normalize_gesla, read_gesla_parquet, sha256_file


def _unpack(params: np.ndarray, input_size: int) -> tuple[np.ndarray, ...]:
    i = 0
    w1 = params[i:i + input_size * 24].reshape(input_size, 24); i += input_size * 24
    b1 = params[i:i + 24]; i += 24
    w2 = params[i:i + 24 * 6].reshape(24, 6); i += 24 * 6
    b2 = params[i:i + 6]; i += 6
    w3 = params[i:i + 6]; i += 6
    b3 = params[i]
    return w1, b1, w2, b2, w3, b3


def _forward(params: np.ndarray, x: np.ndarray) -> np.ndarray:
    w1, b1, w2, b2, w3, b3 = _unpack(params, x.shape[1])
    h1 = np.tanh(x @ w1 + b1)
    h2 = np.tanh(h1 @ w2 + b2)
    return h2 @ w3 + b3


def _objective_and_gradient(params: np.ndarray, x: np.ndarray, y: np.ndarray, alpha: float):
    w1, b1, w2, b2, w3, b3 = _unpack(params, x.shape[1])
    h1 = np.tanh(x @ w1 + b1)
    h2 = np.tanh(h1 @ w2 + b2)
    predicted = h2 @ w3 + b3
    residual = predicted - y
    n = len(y)
    loss = float(np.mean(residual * residual) + alpha * (
        np.sum(w1 * w1) + np.sum(w2 * w2) + np.sum(w3 * w3)
    ) / n)
    dy = 2.0 * residual / n
    gw3 = h2.T @ dy + (2.0 * alpha / n) * w3
    gb3 = float(dy.sum())
    dh2 = dy[:, None] * w3[None, :]
    dz2 = dh2 * (1.0 - h2 * h2)
    gw2 = h1.T @ dz2 + (2.0 * alpha / n) * w2
    gb2 = dz2.sum(axis=0)
    dh1 = dz2 @ w2.T
    dz1 = dh1 * (1.0 - h1 * h1)
    gw1 = x.T @ dz1 + (2.0 * alpha / n) * w1
    gb1 = dz1.sum(axis=0)
    grad = np.concatenate([gw1.ravel(), gb1, gw2.ravel(), gb2, gw3, [gb3]])
    return loss, grad


def _initial_params(input_size: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    w1 = rng.uniform(-np.sqrt(6.0 / (input_size + 24)), np.sqrt(6.0 / (input_size + 24)), (input_size, 24))
    b1 = np.zeros(24)
    w2 = rng.uniform(-np.sqrt(6.0 / 30), np.sqrt(6.0 / 30), (24, 6))
    b2 = np.zeros(6)
    w3 = rng.uniform(-np.sqrt(6.0 / 7), np.sqrt(6.0 / 7), 6)
    return np.concatenate([w1.ravel(), b1, w2.ravel(), b2, w3, [0.0]])


def _examples(index: pd.DatetimeIndex, h: np.ndarray, a: np.ndarray, valid: np.ndarray,
              target_year: int, history_hours: int, lead_hours: int) -> pd.DataFrame:
    position = {time: i for i, time in enumerate(index)}
    targets = pd.date_range(f"{target_year}-01-01", f"{target_year + 1}-01-01", freq="h", inclusive="left", tz="UTC")
    records: list[dict[str, object]] = []
    features: list[np.ndarray] = []
    for target in targets:
        j = position[target]
        issue = j - lead_hours
        start = issue - history_hours + 1
        available = start >= 0 and bool(valid[start:issue + 1].all())
        if available:
            x = np.concatenate([h[start:issue + 1], a[start:issue + 1], [a[j]]]).astype(float)
            available = bool(np.isfinite(x).all())
        else:
            x = np.full(history_hours * 2 + 1, np.nan)
        features.append(x)
        records.append({
            "target_time_utc": target,
            "forecast_origin_time_utc": target - pd.Timedelta(hours=lead_hours),
            "forecast_lead_hours": lead_hours,
            "H_target_m": float(h[j]) if valid[j] else np.nan,
            "A_target_m": float(a[j]),
            "target_qc_valid": bool(valid[j]),
            "forecast_inputs_available": available,
            "input_valid_hour_count": history_hours if available else int(valid[max(start, 0):issue + 1].sum()) if issue >= 0 else 0,
        })
    frame = pd.DataFrame(records)
    frame["_x"] = features
    return frame


def _metric_rows(frame: pd.DataFrame, prediction_column: str, model_id: str, split: str) -> dict[str, object]:
    ok = frame["H_target_m"].notna() & frame[prediction_column].notna()
    errors = frame.loc[ok, "H_target_m"].to_numpy(float) - frame.loc[ok, prediction_column].to_numpy(float)
    return {
        "model_id": model_id, "split": split, "target": "total_observed_water_level_gauge_only",
        "paired_n": int(len(errors)),
        "MAE_cm": float(np.mean(np.abs(errors)) * 100) if len(errors) else np.nan,
        "RMSE_cm": float(np.sqrt(np.mean(errors * errors)) * 100) if len(errors) else np.nan,
        "bias_cm": float(np.mean(errors) * 100) if len(errors) else np.nan,
    }


def _common_cycle_ids(peak_detail: pd.DataFrame) -> pd.Index:
    paired = peak_detail.loc[peak_detail["high_water_eligible"] & peak_detail["error_total_H_m"].notna()]
    counts = paired.groupby("cycle_id")["model_id"].nunique()
    return counts.loc[counts.eq(2)].index


def run_ann(config_path: Path) -> dict[str, object]:
    config = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    output = Path(config["output_dir"])
    output.mkdir(parents=True, exist_ok=True)
    raw_path = Path(config["source_file"])
    raw, identity = read_gesla_parquet(raw_path)
    raw = normalize_gesla(raw)
    minute00 = raw.loc[
        raw["time_utc"].dt.minute.eq(0) & raw["time_utc"].dt.second.eq(0)
        & raw["time_utc"].dt.microsecond.eq(0)
    ].copy()
    if minute00["time_utc"].duplicated().any():
        raise ValueError("GESLA minute-00 timestamps must be unique; refusing to collapse duplicates")

    history = int(config["history_hours"])
    lead = int(config["forecast_lead_hours"])
    train_year = int(config["train_year"])
    validation_year = int(config["validation_year"])
    score_year = int(config["score_year"])
    seeds = [int(value) for value in config["seeds"]]
    if history != 168 or lead != 24 or list(config["hidden_layers"]) != [24, 6]:
        raise ValueError("This registered design is fixed to a 168h history, 24h lead, and 24/6 hidden layers")

    start = pd.Timestamp(f"{train_year}-01-01", tz="UTC") - pd.Timedelta(days=8)
    end = pd.Timestamp(f"{score_year + 1}-01-02", tz="UTC")
    index = pd.date_range(start, end, freq="h", inclusive="left", tz="UTC", name="time_utc")
    expected_index = pd.DatetimeIndex(index)
    source_hour = minute00.set_index("time_utc").reindex(expected_index)
    h = pd.to_numeric(source_hour["level_m"], errors="coerce").to_numpy(float)
    valid = source_hour["analysis_valid"].fillna(False).to_numpy(bool) & np.isfinite(h)
    a = reconstruct_from_saved_state(expected_index, Path(config["utide_state_file"]))
    if len(a) != len(expected_index) or not np.isfinite(a).all():
        raise AssertionError("UTide saved state failed to reconstruct the required continuous UTC grid")

    year_frames = {
        year: _examples(expected_index, h, a, valid, year, history, lead)
        for year in (train_year, validation_year, score_year)
    }
    train = year_frames[train_year]
    validation = year_frames[validation_year]
    scored = year_frames[score_year]
    train_mask = train["forecast_inputs_available"].to_numpy(bool) & train["H_target_m"].notna().to_numpy()
    val_mask = validation["forecast_inputs_available"].to_numpy(bool) & validation["H_target_m"].notna().to_numpy()
    if not train_mask.any() or not val_mask.any():
        raise ValueError("Insufficient paired training/validation windows after strict QC filtering")

    def matrix(frame: pd.DataFrame, mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        x = np.vstack(frame.loc[mask, "_x"].to_numpy())
        y = frame.loc[mask, "H_target_m"].to_numpy(float)
        return x, y

    x_train_raw, y_train_raw = matrix(train, train_mask)
    x_val_raw, y_val_raw = matrix(validation, val_mask)
    input_size = 2 * history + 1
    means = np.array([x_train_raw[:, :history].mean(), x_train_raw[:, history:2 * history].mean(), x_train_raw[:, -1].mean()])
    scales = np.array([x_train_raw[:, :history].std(), x_train_raw[:, history:2 * history].std(), x_train_raw[:, -1].std()])
    scales[scales < 1e-12] = 1.0
    y_mean, y_scale = float(y_train_raw.mean()), float(y_train_raw.std())
    if y_scale < 1e-12:
        y_scale = 1.0

    def scale_x(x: np.ndarray) -> np.ndarray:
        out = x.copy()
        out[:, :history] = (out[:, :history] - means[0]) / scales[0]
        out[:, history:2 * history] = (out[:, history:2 * history] - means[1]) / scales[1]
        out[:, -1] = (out[:, -1] - means[2]) / scales[2]
        return out

    x_train = scale_x(x_train_raw)
    y_train = (y_train_raw - y_mean) / y_scale
    x_val = scale_x(x_val_raw)
    y_val = (y_val_raw - y_mean) / y_scale
    score_mask = scored["forecast_inputs_available"].to_numpy(bool)
    x_score_raw = np.vstack(scored.loc[score_mask, "_x"].to_numpy()) if score_mask.any() else np.empty((0, input_size))
    x_score = scale_x(x_score_raw) if len(x_score_raw) else x_score_raw

    alpha = float(config["l2_alpha"])
    maxiter = int(config["max_iterations"])
    patience = int(config["validation_patience"])
    rows = []
    model_meta = []
    for seed in seeds:
        initial = _initial_params(input_size, seed)
        best_params = initial.copy()
        best_val = float("inf")
        stale = 0
        iteration = 0
        result = None

        def callback(candidate: np.ndarray) -> None:
            nonlocal best_params, best_val, stale, iteration
            iteration += 1
            validation_loss = float(np.mean((_forward(candidate, x_val) - y_val) ** 2))
            if validation_loss < best_val - 1e-10:
                best_val = validation_loss
                best_params = candidate.copy()
                stale = 0
            else:
                stale += 1
                if stale >= patience:
                    raise StopIteration

        stopped_early = False
        try:
            result = minimize(
                _objective_and_gradient, initial, args=(x_train, y_train, alpha), jac=True,
                method="L-BFGS-B", callback=callback,
                options={"maxiter": maxiter, "ftol": 1e-8, "maxcor": 8, "maxls": 12},
            )
            stopped_early = stale >= patience
            if not np.isfinite(best_val):
                best_params = result.x.copy()
                best_val = float(np.mean((_forward(best_params, x_val) - y_val) ** 2))
        except StopIteration:
            stopped_early = True

        prediction_scaled = _forward(best_params, x_score) if len(x_score) else np.empty(0)
        predicted = prediction_scaled * y_scale + y_mean
        forecast = scored.drop(columns=["_x"]).copy()
        forecast["ANN_prediction_m"] = np.nan
        forecast.loc[score_mask, "ANN_prediction_m"] = predicted
        forecast["model_id"] = f"ANN_24h_24_6_seed_{seed}"
        forecast["target_type"] = "total_observed_water_level_gauge_only"
        forecast["baseline_UTide_m"] = forecast["A_target_m"]
        path = output / f"forecasts_hourly_seed_{seed}.parquet"
        forecast.to_parquet(path, index=False)
        np.savez_compressed(
            output / f"model_seed_{seed}.npz",
            params=best_params, feature_means=means, feature_scales=scales,
            target_mean=np.array(y_mean), target_scale=np.array(y_scale),
        )
        rows.append(forecast.rename(columns={"ANN_prediction_m": f"ANN_seed_{seed}_m"})[[
            "target_time_utc", "forecast_origin_time_utc", "forecast_lead_hours", "H_target_m",
            "A_target_m", "target_qc_valid", "forecast_inputs_available", f"ANN_seed_{seed}_m",
        ]])
        model_meta.append({
            "seed": seed, "model_id": f"ANN_24h_24_6_seed_{seed}", "optimizer": "SciPy L-BFGS-B with analytic gradients",
            "regularization": "fixed L2 weight penalty; not MATLAB Bayesian regularization",
            "train_rows": int(train_mask.sum()), "validation_rows": int(val_mask.sum()),
            "score_forecastable_rows": int(score_mask.sum()), "best_validation_mse_standardized": best_val,
            "optimizer_iterations_observed": iteration, "stopped_after_validation_patience": stopped_early,
            "optimizer_success": bool(result.success) if result is not None else False,
            "optimizer_termination": "validation_patience" if stopped_early else ("converged" if result is not None and result.success else "iteration_cap_or_line_search"),
            "optimizer_message": str(result.message) if result is not None else "validation patience stop",
            "max_iterations": maxiter, "l2_alpha": alpha,
            "hourly_forecast_file": str(path), "model_file": str(output / f"model_seed_{seed}.npz"),
        })

    ensemble = rows[0].copy()
    for seed in seeds[1:]:
        ensemble = ensemble.merge(rows[seeds.index(seed)][["target_time_utc", f"ANN_seed_{seed}_m"]], on="target_time_utc", validate="one_to_one")
    seed_cols = [f"ANN_seed_{seed}_m" for seed in seeds]
    ensemble["ANN_ensemble_mean_m"] = ensemble[seed_cols].mean(axis=1, skipna=False)
    ensemble["baseline_UTide_m"] = ensemble["A_target_m"]
    ensemble.to_parquet(output / "forecasts_hourly_ensemble.parquet", index=False)
    common = ensemble["H_target_m"].notna() & ensemble[seed_cols].notna().all(axis=1)
    hourly_metrics = [
        _metric_rows(ensemble.loc[common], "baseline_UTide_m", "UTide-0.4.0_chronological_through_2004", f"test_{score_year}_hourly_24h_origin"),
        *[_metric_rows(ensemble.loc[common], f"ANN_seed_{seed}_m", f"ANN_seed_{seed}", f"test_{score_year}_hourly_24h_origin") for seed in seeds],
        _metric_rows(ensemble.loc[common], "ANN_ensemble_mean_m", "ANN_three_seed_mean", f"test_{score_year}_hourly_24h_origin"),
    ]
    pd.DataFrame(hourly_metrics).to_csv(output / "hourly_metrics.csv", index=False)

    peaks_path = Path(config["p3_peak_file"])
    peaks = pd.read_parquet(peaks_path)
    peaks["H_peak_time_utc"] = pd.to_datetime(peaks["H_peak_time_utc"], utc=True)
    peaks["cycle_start_utc"] = pd.to_datetime(peaks["cycle_start_utc"], utc=True)
    peaks["cycle_end_utc_exclusive"] = pd.to_datetime(peaks["cycle_end_utc_exclusive"], utc=True)
    peaks = peaks.loc[peaks["H_peak_time_utc"].dt.year.eq(score_year)].copy()
    peak_records: list[dict[str, object]] = []
    for _, peak in peaks.iterrows():
        hourly_cycle = ensemble.loc[
            ensemble["target_time_utc"].ge(peak["cycle_start_utc"])
            & ensemble["target_time_utc"].lt(peak["cycle_end_utc_exclusive"])
        ]
        base = {
            "station_id": peak["station_id"], "branch": "public_source_substitute_gauge_only",
            "design_id": "ANN_24h_lead_168h_history_UTide_inputs", "cycle_id": peak["cycle_id"],
            "cycle_number": int(peak["cycle_number"]), "cycle_start_utc": peak["cycle_start_utc"],
            "cycle_end_utc_exclusive": peak["cycle_end_utc_exclusive"],
            "H_peak_time_utc": peak["H_peak_time_utc"], "H_peak_m": peak["H_peak_m"],
            "A_peak_time_utc": peak["A_peak_time_utc"], "A_peak_m": peak["A_peak_m"],
            "high_water_eligible": bool(peak["high_water_eligible"]),
            "target_type": "total_observed_water_level_gauge_only",
            "surge_m": np.nan, "surge_status": "unavailable_not_inferred",
        }
        for model_col, model_id in [("baseline_UTide_m", "UTide-0.4.0_baseline"), ("ANN_ensemble_mean_m", "ANN_three_seed_mean")]:
            valid_cycle = hourly_cycle.loc[hourly_cycle[model_col].notna()]
            if valid_cycle.empty:
                pred_time, pred_m = pd.NaT, np.nan
            else:
                idx = valid_cycle[model_col].idxmax()
                pred_time, pred_m = valid_cycle.loc[idx, "target_time_utc"], float(valid_cycle.loc[idx, model_col])
            peak_records.append({**base, "model_id": model_id, "P_peak_time_utc": pred_time, "P_peak_m": pred_m,
                                 "error_total_H_m": float(peak["H_peak_m"] - pred_m) if np.isfinite(pred_m) and np.isfinite(peak["H_peak_m"]) else np.nan,
                                 "issue_time_utc": pred_time - pd.Timedelta(hours=lead) if pd.notna(pred_time) else pd.NaT})
    peak_detail = pd.DataFrame(peak_records)
    peak_detail.to_parquet(output / "high_water_detail.parquet", index=False)
    peak_detail.to_csv(output / "high_water_detail.csv", index=False)
    peak_metrics = []
    common_cycle_ids = _common_cycle_ids(peak_detail)
    for model_id, group in peak_detail.groupby("model_id"):
        eligible = group.loc[group["high_water_eligible"] & group["error_total_H_m"].notna()
                             & group["cycle_id"].isin(common_cycle_ids)]
        errors = eligible["error_total_H_m"].to_numpy(float)
        peak_metrics.append({
            "station_id": "avonmouth", "model_id": model_id, "period": f"test_{score_year}",
            "target": "total_observed_water_level_gauge_only", "paired_n": len(errors),
            "MAE_cm": float(np.mean(np.abs(errors)) * 100) if len(errors) else np.nan,
            "RMSE_cm": float(np.sqrt(np.mean(errors * errors)) * 100) if len(errors) else np.nan,
            "bias_cm": float(np.mean(errors) * 100) if len(errors) else np.nan,
            "sample_id_sha256": hashlib.sha256("\n".join(sorted(eligible["cycle_id"].astype(str))).encode()).hexdigest(),
        })
    pd.DataFrame(peak_metrics).to_csv(output / "high_water_metrics.csv", index=False)

    state_path = Path(config["utide_state_file"])
    manifest = {
        "design_id": "ANN_24h_lead_168h_history_UTide_chronological_inputs",
        "source_file": str(raw_path), "source_sha256": sha256_file(raw_path),
        "source_station": identity.station, "source_latitude": identity.latitude, "source_longitude": identity.longitude,
        "source_datum": "unknown_in_GESLA_record; no conversion applied",
        "source_channel": "GESLA/BODC-lineage; original channel unresolved",
        "source_qc_rule": "exact UTC minute-00 records, finite and non-sentinel, use_flag=1, qc_flag=1; no interpolation",
        "utide_state_file": str(state_path), "utide_state_sha256": sha256_file(state_path),
        "utide_model": "UTide 0.4.0 chronological fit through 2004; 68 auto constituents; mean+trend; nodal correction; Greenwich phase; not verified EHM",
        "p3_peak_file": str(peaks_path), "p3_peak_sha256": sha256_file(peaks_path),
        "feature_definition": "168 hourly H observations ending at issue time; 168 UTide A values over same history; UTide A at target time",
        "history_hours": history, "forecast_lead_hours": lead, "train_year": train_year,
        "validation_year": validation_year, "score_year": score_year,
        "hidden_layers": [24, 6], "hidden_activation": "tanh", "output_activation": "linear",
        "starts": seeds, "optimizer": "SciPy L-BFGS-B with analytic gradients",
        "regularization": "fixed L2 penalty; not MATLAB R2008b Neural Network Toolbox Bayesian regularization",
        "validation_early_stopping_patience": patience, "alpha": alpha, "scipy_version": scipy.__version__,
        "python_version": platform.python_version(), "input_scaling": "train-year means/stds by H-history, A-history, and target-A groups; target H standardized on train only",
        "target": "total observed water level H; surge unavailable and not inferred",
        "metric_comparison": "UTide and ANN scored on common exact-minute QC-valid hourly targets and common P3 eligible cycle IDs; high-water metric cycle IDs are the shared forecastable intersection",
        "ann_runs": model_meta,
    }
    (output / "run_manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    return {
        "design_id": manifest["design_id"], "output_dir": str(output),
        "train_rows": int(train_mask.sum()), "validation_rows": int(val_mask.sum()),
        "score_target_hours": int(len(scored)), "score_forecastable_hours": int(score_mask.sum()),
        "models": len(seeds), "hourly_metrics_csv": str(output / "hourly_metrics.csv"),
        "high_water_metrics_csv": str(output / "high_water_metrics.csv"),
        "run_manifest": str(output / "run_manifest.json"),
    }
