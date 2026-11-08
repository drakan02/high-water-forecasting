"""Newlyn-reference, species-banded harmonic transfer substitute."""
from __future__ import annotations

from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd
import yaml
from utide import reconstruct, solve
from utide.harmonics import ut_constants
from utide.utilities import Bunch

from .harmonic import _utc_naive
from .ingest import normalize_gesla, sha256_file


def _load_station(path: Path, expected_site: str, expected_file: str) -> tuple[pd.DataFrame, dict[str, object]]:
    raw = pd.read_parquet(path)
    for column in ("date_time", "country", "site_name", "lat", "lon", "sea_level", "qc_flag", "use_flag", "file_name"):
        if column not in raw.columns:
            raise ValueError(f"{path}: missing GESLA field {column}")
    if set(raw["site_name"].dropna().unique()) != {expected_site}:
        raise ValueError(f"{path}: expected only station {expected_site}")
    if set(raw["country"].dropna().unique()) != {"GBR"}:
        raise ValueError(f"{path}: expected country GBR")
    if set(raw["file_name"].dropna().unique()) != {expected_file}:
        raise ValueError(f"{path}: unexpected source lineage")
    data = normalize_gesla(raw)
    identity = {
        "station": expected_site, "country": "GBR", "source_id": expected_file,
        "latitude": float(data["lat"].median()), "longitude": float(data["lon"].median()),
        "rows": len(data), "first_time_utc": data["time_utc"].min().isoformat(),
        "last_time_utc": data["time_utc"].max().isoformat(),
        "datum": "unknown_in_GESLA_record; no conversion applied",
        "channel": "GESLA/BODC lineage; original channel unresolved",
    }
    return data, identity


def _hourly_station(data: pd.DataFrame, year: int) -> pd.DataFrame:
    rows = data.loc[
        data["time_utc"].dt.year.eq(year)
        & data["time_utc"].dt.minute.eq(0)
        & data["time_utc"].dt.second.eq(0)
        & data["time_utc"].dt.microsecond.eq(0)
    ].copy()
    if rows["time_utc"].duplicated().any():
        raise ValueError(f"Duplicate exact-hour timestamps at {data['site_name'].iloc[0]} {year}")
    grid = pd.date_range(f"{year}-01-01", f"{year + 1}-01-01", freq="h", inclusive="left", tz="UTC", name="time_utc")
    hourly = rows.set_index("time_utc").reindex(grid)
    hourly["timestamp_present"] = hourly["site_name"].notna()
    hourly["level_m"] = pd.to_numeric(hourly["level_m_raw"], errors="coerce")
    hourly["analysis_valid"] = hourly["analysis_valid"].fillna(False).astype(bool) & np.isfinite(hourly["level_m"].to_numpy(float))
    hourly.loc[~hourly["analysis_valid"], "level_m"] = np.nan
    hourly.index.name = "time_utc"
    return hourly.reset_index()


def _fit(times: pd.DatetimeIndex, levels: np.ndarray, latitude: float, constituents: str | list[str]):
    valid = np.isfinite(levels)
    if int(valid.sum()) < 100:
        raise ValueError("Not enough valid calibration values for UTide")
    return solve(
        _utc_naive(times[valid]), levels[valid], lat=latitude, constit=constituents,
        method="ols", conf_int="none", order_constit="frequency", trend=True,
        nodal=True, phase="Greenwich", verbose=False,
    )


def _species_map(names: list[str] | np.ndarray) -> dict[str, int | None]:
    catalog_names = np.asarray(ut_constants.const.name).astype(str)
    catalog_species = np.asarray(ut_constants.const.doodsonspecies, dtype=float)
    lookup = {name: value for name, value in zip(catalog_names, catalog_species)}
    result: dict[str, int | None] = {}
    for name in map(str, names):
        code = lookup.get(name, np.nan)
        result[name] = int(code) if np.isfinite(code) else None
    return result


def _complex_coefficients(coef) -> np.ndarray:
    return np.asarray(coef.A, dtype=float) * np.exp(-1j * np.deg2rad(np.asarray(coef.g, dtype=float)))


def _fit_species_factors(reference, target, species_by_name: dict[str, int | None]) -> tuple[dict[int, complex], dict[int, int]]:
    reference_names = list(map(str, reference.name))
    target_names = list(map(str, target.name))
    if reference_names != target_names:
        raise ValueError("Reference and target UTide coefficient order must be identical")
    ref_c = _complex_coefficients(reference)
    target_c = _complex_coefficients(target)
    factors: dict[int, complex] = {}
    counts: dict[int, int] = {}
    for species in sorted({s for s in species_by_name.values() if s is not None}):
        indexes = np.array([i for i, name in enumerate(reference_names) if species_by_name[name] == species], dtype=int)
        x, y = ref_c[indexes], target_c[indexes]
        denominator = float(np.vdot(x, x).real)
        if denominator <= np.finfo(float).eps:
            continue
        factors[int(species)] = complex(np.vdot(x, y) / denominator)
        counts[int(species)] = int(len(indexes))
    if not factors:
        raise ValueError("No UTide constituents have a usable Doodson species code")
    return factors, counts


def _transferred_coefficients(reference, target, species_by_name: dict[str, int | None], factors: dict[int, complex], target_latitude: float):
    names = list(map(str, reference.name))
    result = Bunch()
    result.update(reference)
    result.name = np.asarray(names)
    result.A = np.zeros(len(names), dtype=float)
    result.g = np.asarray(reference.g, dtype=float).copy()
    ref_c = _complex_coefficients(reference)
    target_mean = float(np.asarray(target.mean).squeeze())
    target_slope = float(np.asarray(target.slope).squeeze()) if hasattr(target, "slope") else 0.0
    for i, name in enumerate(names):
        species = species_by_name[name]
        if species is None or species not in factors:
            continue
        transferred = factors[species] * ref_c[i]
        result.A[i] = abs(transferred)
        result.g[i] = float((-np.rad2deg(np.angle(transferred))) % 360.0)
    result.mean = target_mean
    result.slope = target_slope
    aux = Bunch()
    aux.update(reference.aux)
    aux.lat = target_latitude
    result.aux = aux
    return result


def _predict(times: pd.DatetimeIndex, coef, names: list[str]) -> np.ndarray:
    return np.asarray(reconstruct(_utc_naive(times), coef, constit=names, verbose=False).h, dtype=float)


def _metric(target: np.ndarray, prediction: np.ndarray, model_id: str, split: str) -> dict[str, object]:
    valid = np.isfinite(target) & np.isfinite(prediction)
    error = target[valid] - prediction[valid]
    return {
        "model_id": model_id, "split": split, "target": "total_observed_water_level_gauge_only",
        "paired_n": int(valid.sum()), "MAE_cm": float(np.mean(np.abs(error)) * 100),
        "RMSE_cm": float(np.sqrt(np.mean(error * error)) * 100), "bias_cm": float(np.mean(error) * 100),
    }


def run_species(config_path: Path) -> dict[str, object]:
    config = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    output = Path(config["output_dir"])
    output.mkdir(parents=True, exist_ok=True)
    train_year, score_year = int(config["training_year"]), int(config["score_year"])
    avon_path, newlyn_path = Path(config["avonmouth_file"]), Path(config["newlyn_file"])
    avon, avon_identity = _load_station(avon_path, "Avonmouth", "avonmouth-avo-gbr-bodc")
    newlyn, newlyn_identity = _load_station(newlyn_path, "Newlyn", "newlyn-new-gbr-bodc")
    av_train = _hourly_station(avon, train_year)
    ne_train = _hourly_station(newlyn, train_year)
    av_score = _hourly_station(avon, score_year)
    ne_score = _hourly_station(newlyn, score_year)
    if not av_train["time_utc"].equals(ne_train["time_utc"]):
        raise AssertionError("Calibration grids must be aligned hourly UTC")

    av_valid = av_train["analysis_valid"].to_numpy(bool)
    ne_valid = ne_train["analysis_valid"].to_numpy(bool)
    av_lat, ne_lat = avon_identity["latitude"], newlyn_identity["latitude"]
    ref_auto = _fit(pd.DatetimeIndex(ne_train.time_utc), ne_train.level_m.to_numpy(float), ne_lat, "auto")
    target_auto = _fit(pd.DatetimeIndex(av_train.time_utc), av_train.level_m.to_numpy(float), av_lat, "auto")
    target_auto_names = set(map(str, target_auto.name))
    common_names = [str(name) for name in ref_auto.name if str(name) in target_auto_names]
    if len(common_names) < 10:
        raise ValueError(f"Too few common auto constituents: {len(common_names)}")
    reference = _fit(pd.DatetimeIndex(ne_train.time_utc), ne_train.level_m.to_numpy(float), ne_lat, common_names)
    target = _fit(pd.DatetimeIndex(av_train.time_utc), av_train.level_m.to_numpy(float), av_lat, common_names)
    names = list(map(str, reference.name))
    species_by_name = _species_map(names)
    factors, species_counts = _fit_species_factors(reference, target, species_by_name)
    transferred_coef = _transferred_coefficients(reference, target, species_by_name, factors, av_lat)

    times = pd.DatetimeIndex(av_score.time_utc)
    utide_prediction = _predict(times, target, names)
    species_prediction = _predict(times, transferred_coef, names)
    observed = av_score.level_m.to_numpy(dtype=float, copy=True)
    observed[~av_score.analysis_valid.to_numpy(bool)] = np.nan
    forecast = pd.DataFrame({
        "time_utc": times, "H_target_m": observed, "A_utide_train2006_m": utide_prediction,
        "P_species_newlyn_m": species_prediction,
        "qc_status": av_score.qc_flag.astype("Int64"), "qc_use_flag": av_score.use_flag.astype("Int64"),
        "qc_valid": av_score.analysis_valid.to_numpy(bool),
        "design_id": str(config["design_id"]), "target_type": "total_observed_water_level_gauge_only",
    })
    hourly_rows = [
        _metric(observed, utide_prediction, "UTide-0.4.0_Avonmouth_fit_2006", f"test_{score_year}_hourly"),
        _metric(observed, species_prediction, "SC_species_banded_Newlyn_transfer_2006", f"test_{score_year}_hourly"),
    ]
    forecast.to_parquet(output / "forecasts_hourly.parquet", index=False)
    pd.DataFrame(hourly_rows).to_csv(output / "hourly_metrics.csv", index=False)

    peaks_path = Path(config["p3_peak_file"])
    peaks = pd.read_parquet(peaks_path)
    peaks = peaks.loc[pd.to_datetime(peaks["H_peak_time_utc"], utc=True).dt.year.eq(score_year)].copy()
    peaks["cycle_start_utc"] = pd.to_datetime(peaks["cycle_start_utc"], utc=True)
    peaks["cycle_end_utc_exclusive"] = pd.to_datetime(peaks["cycle_end_utc_exclusive"], utc=True)
    peaks["H_peak_time_utc"] = pd.to_datetime(peaks["H_peak_time_utc"], utc=True)
    peak_records = []
    for _, peak in peaks.iterrows():
        in_cycle = forecast.loc[forecast.time_utc.ge(peak.cycle_start_utc) & forecast.time_utc.lt(peak.cycle_end_utc_exclusive)]
        for model_id, column in [
            ("UTide-0.4.0_Avonmouth_fit_2006", "A_utide_train2006_m"),
            ("SC_species_banded_Newlyn_transfer_2006", "P_species_newlyn_m"),
        ]:
            good = in_cycle.loc[in_cycle[column].notna()]
            if good.empty:
                pred_time, pred_m = pd.NaT, np.nan
            else:
                row = good.loc[good[column].idxmax()]
                pred_time, pred_m = row.time_utc, float(row[column])
            peak_records.append({
                "station_id": "avonmouth", "cycle_id": peak.cycle_id, "model_id": model_id,
                "H_peak_time_utc": peak.H_peak_time_utc, "H_peak_m": peak.H_peak_m,
                "P_peak_time_utc": pred_time, "P_peak_m": pred_m,
                "error_total_H_m": float(peak.H_peak_m - pred_m) if np.isfinite(pred_m) else np.nan,
                "high_water_eligible": bool(peak.high_water_eligible),
                "target_type": "total_observed_water_level_gauge_only",
                "surge_m": np.nan, "surge_status": "unavailable_not_inferred",
                "design_id": str(config["design_id"]),
            })
    peak_detail = pd.DataFrame(peak_records)
    peak_detail.to_parquet(output / "high_water_detail.parquet", index=False)
    peak_detail.to_csv(output / "high_water_detail.csv", index=False)
    eligible = peak_detail.loc[peak_detail.high_water_eligible & peak_detail.error_total_H_m.notna()]
    per_model = eligible.groupby("model_id").cycle_id.agg(lambda ids: set(ids.astype(str)))
    common_cycles = set.intersection(*per_model.tolist()) if len(per_model) else set()
    cycle_hash = hashlib.sha256("\n".join(sorted(common_cycles)).encode()).hexdigest()
    peak_metrics = []
    for model_id, group in peak_detail.groupby("model_id"):
        paired = group.loc[group.high_water_eligible & group.error_total_H_m.notna() & group.cycle_id.astype(str).isin(common_cycles)]
        errors = paired.error_total_H_m.to_numpy(float)
        peak_metrics.append({
            "station_id": "avonmouth", "model_id": model_id, "period": f"test_{score_year}",
            "target": "total_observed_water_level_gauge_only", "paired_n": len(errors),
            "MAE_cm": float(np.mean(np.abs(errors)) * 100) if len(errors) else np.nan,
            "RMSE_cm": float(np.sqrt(np.mean(errors * errors)) * 100) if len(errors) else np.nan,
            "bias_cm": float(np.mean(errors) * 100) if len(errors) else np.nan,
            "sample_id_sha256": cycle_hash,
        })
    pd.DataFrame(peak_metrics).to_csv(output / "high_water_metrics.csv", index=False)

    coefficient_rows = []
    ref_c, target_c = _complex_coefficients(reference), _complex_coefficients(target)
    for i, name in enumerate(names):
        species = species_by_name[name]
        factor = factors.get(species) if species is not None else None
        coefficient_rows.append({
            "constituent": name, "doodson_species": species,
            "newlyn_amplitude_m": float(reference.A[i]), "newlyn_phase_greenwich_deg": float(reference.g[i]),
            "avonmouth_amplitude_m": float(target.A[i]), "avonmouth_phase_greenwich_deg": float(target.g[i]),
            "transfer_real": float(factor.real) if factor is not None else np.nan,
            "transfer_imag": float(factor.imag) if factor is not None else np.nan,
            "transfer_abs": float(abs(factor)) if factor is not None else np.nan,
            "transfer_arg_deg": float(np.rad2deg(np.angle(factor))) if factor is not None else np.nan,
            "newlyn_complex_real": float(ref_c[i].real), "newlyn_complex_imag": float(ref_c[i].imag),
            "avonmouth_complex_real": float(target_c[i].real), "avonmouth_complex_imag": float(target_c[i].imag),
        })
    pd.DataFrame(coefficient_rows).to_csv(output / "species_transfer_coefficients.csv", index=False)

    def coverage(hourly: pd.DataFrame) -> dict[str, object]:
        valid = hourly.analysis_valid.to_numpy(bool)
        return {
            "expected_hourly": len(hourly), "minute00_present": int(hourly.timestamp_present.sum()),
            "valid_hourly": int(valid.sum()), "qc_flag_counts": hourly.qc_flag.value_counts(dropna=False).sort_index().to_dict(),
            "use_flag_counts": hourly.use_flag.value_counts(dropna=False).sort_index().to_dict(),
        }

    monthly_rows = []
    for station, yearly in [("Avonmouth", av_train), ("Newlyn", ne_train), ("Avonmouth", av_score), ("Newlyn", ne_score)]:
        period = train_year if yearly is av_train or yearly is ne_train else score_year
        for month, group in yearly.groupby(yearly.time_utc.dt.month):
            monthly_rows.append({
                "station": station, "year": period, "month": int(month),
                "hourly_expected": len(group), "minute00_present": int(group.timestamp_present.sum()),
                "hourly_valid": int(group.analysis_valid.sum()),
                "qc_flag_1": int(group.qc_flag.eq(1).sum()), "qc_flag_2": int(group.qc_flag.eq(2).sum()),
                "qc_flag_3": int(group.qc_flag.eq(3).sum()), "qc_flag_4": int(group.qc_flag.eq(4).sum()),
                "qc_flag_5": int(group.qc_flag.eq(5).sum()), "use_flag_0": int(group.use_flag.eq(0).sum()),
            })
    pd.DataFrame(monthly_rows).to_csv(output / "monthly_source_coverage.csv", index=False)

    artifact_manifest = {}
    for artifact in sorted(output.iterdir()):
        if artifact.is_file() and artifact.name != "run_manifest.json":
            rows = None
            if artifact.suffix == ".parquet":
                rows = len(pd.read_parquet(artifact))
            elif artifact.suffix == ".csv":
                rows = len(pd.read_csv(artifact))
            artifact_manifest[artifact.name] = {
                "size_bytes": artifact.stat().st_size, "sha256": sha256_file(artifact), "rows": rows,
            }

    source_manifest = {
        "design_id": str(config["design_id"]), "training_year": train_year, "score_year": score_year,
        "avonmouth": {**avon_identity, "file": str(avon_path), "sha256": sha256_file(avon_path), "calibration_coverage": coverage(av_train), "score_coverage": coverage(av_score)},
        "newlyn": {**newlyn_identity, "file": str(newlyn_path), "sha256": sha256_file(newlyn_path), "calibration_coverage": coverage(ne_train), "score_coverage": coverage(ne_score)},
        "newlyn_bucket_object_url": "https://gesla-dataset.s3.eu-west-1.amazonaws.com/parquet_files/newlyn-new-gbr-bodc.parquet",
        "newlyn_catalog_url": "https://gesla787883612.wordpress.com/downloads/",
        "bodc_processed_catalog_url": "https://www.bodc.ac.uk/data/hosted_data_systems/sea_level/uk_tide_gauge_network/processed/",
        "newlyn_bucket_object_version": "GESLA release not encoded in Parquet; object contains data through 2021-07-31",
        "unit": "metres per GESLA format; datum unknown; no conversion applied",
        "hourly_rule": "exact UTC minute-00; finite/non-fill; use_flag=1; qc_flag=1; no interpolation",
        "training_valid_pair_hours": int((av_valid & ne_valid).sum()),
        "target": "total observed Avonmouth water level H; gauge-only; surge unavailable and not inferred",
        "method": "species-banded complex harmonic transfer approximation using UTide 0.4.0 Doodson species codes; not SHOM MAS and not exact Eq. 2-4 implementation",
        "constituent_names": names, "species_by_constituent": species_by_name,
        "species_transfer_factors": {str(k): {"real": v.real, "imag": v.imag, "abs": abs(v), "arg_deg": float(np.rad2deg(np.angle(v)))} for k, v in factors.items()},
        "species_constituent_counts": species_counts,
        "unclassified_constituents_zeroed": [name for name, species in species_by_name.items() if species is None],
        "common_eligible_peak_cycle_count": len(common_cycles), "common_peak_cycle_sha256": cycle_hash,
        "monthly_source_coverage_csv": str(output / "monthly_source_coverage.csv"),
        "artifact_manifest": artifact_manifest,
        "utide": {"version": "0.4.0", "method": "OLS", "fit_times": "2006-01-01 through 2006-12-31 UTC", "constituent_selection": "intersection of independent auto-selected lists, refit both stations to the identical list", "phase": "Greenwich", "trend": True, "nodal_corrections": True},
        "metrics": {"hourly_common_n": int(np.isfinite(observed).sum()), "hourly": hourly_rows, "high_water": peak_metrics},
    }
    (output / "run_manifest.json").write_text(json.dumps(source_manifest, indent=2, default=str), encoding="utf-8")
    return {
        "design_id": str(config["design_id"]), "output_dir": str(output),
        "training_pair_hours": int((av_valid & ne_valid).sum()), "score_hourly_valid": int(np.isfinite(observed).sum()),
        "common_peak_cycles": len(common_cycles), "models": 2,
        "hourly_metrics_csv": str(output / "hourly_metrics.csv"),
        "high_water_metrics_csv": str(output / "high_water_metrics.csv"),
        "run_manifest": str(output / "run_manifest.json"),
    }
