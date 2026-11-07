"""P2 gauge-only harmonic fits and diagnostics using UTide."""

from __future__ import annotations

from pathlib import Path
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy
from scipy.signal import welch
import utide
from utide import reconstruct, solve
from utide.utilities import Bunch
import yaml

from .ingest import normalize_gesla, prepare_hourly, read_gesla_parquet


SPECTRUM_NPERSEG = 336
SPECTRUM_NOVERLAP = 168


def _longest_true_run(values: np.ndarray) -> int:
    longest = current = 0
    for value in values:
        current = current + 1 if value else 0
        longest = max(longest, current)
    return longest


def audit_history(raw_path: Path, out_dir: Path) -> dict[str, object]:
    """Write full-file metadata and calendar-year exact-hour coverage."""
    import pyarrow.parquet as pq

    raw_path = Path(raw_path)
    table_metadata = pq.read_metadata(raw_path)
    frame, identity = read_gesla_parquet(raw_path)
    data = normalize_gesla(frame)
    data["year"] = data["time_utc"].dt.year
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    yearly: list[dict[str, object]] = []
    for year in range(identity.first_time_utc.year, identity.last_time_utc.year + 1):
        group = data.loc[data["year"].eq(year)].sort_values("time_utc")
        expected = pd.date_range(f"{year}-01-01", f"{year + 1}-01-01", freq="h", inclusive="left", tz="UTC")
        if group.empty:
            yearly.append({
                "year": year, "first_time_utc": "", "last_time_utc": "", "cadence_mode_minutes": pd.NA,
                "source_rows": 0, "valid_source_rows_all_cadences": 0, "hourly_timestamps_expected": len(expected),
                "hourly_minute00_present": 0, "hourly_valid": 0, "hourly_coverage": 0.0,
                "longest_invalid_or_missing_hour_run": len(expected), "qc_flag_2_rows": 0,
                "qc_flag_3_rows": 0, "qc_flag_4_rows": 0, "qc_flag_5_rows": 0,
                "use_flag_0_rows": 0, "source_file_names": "", "coordinates": "",
                "datum": "unknown_in_GESLA_record", "channel": "unresolved",
            })
            continue

        times = group["time_utc"]
        cadence = times.diff().dt.total_seconds().div(60).mode()
        cadence_mode = int(cadence.iloc[0]) if not cadence.empty else pd.NA
        minute00 = group.loc[
            times.dt.minute.eq(0) & times.dt.second.eq(0) & times.dt.microsecond.eq(0)
        ].copy()
        valid_by_hour = pd.Series(
            minute00["analysis_valid"].to_numpy(),
            index=pd.DatetimeIndex(minute00["time_utc"]),
        ).reindex(expected, fill_value=False)
        yearly.append({
            "year": year,
            "first_time_utc": times.min().isoformat(),
            "last_time_utc": times.max().isoformat(),
            "cadence_mode_minutes": cadence_mode,
            "source_rows": len(group),
            "valid_source_rows_all_cadences": int(group["analysis_valid"].sum()),
            "hourly_timestamps_expected": len(expected),
            "hourly_minute00_present": int(minute00["time_utc"].nunique()),
            "hourly_valid": int(valid_by_hour.sum()),
            "hourly_coverage": float(valid_by_hour.mean()),
            "longest_invalid_or_missing_hour_run": _longest_true_run(~valid_by_hour.to_numpy()),
            "qc_flag_2_rows": int(group["qc_flag"].eq(2).sum()),
            "qc_flag_3_rows": int(group["qc_flag"].eq(3).sum()),
            "qc_flag_4_rows": int(group["qc_flag"].eq(4).sum()),
            "qc_flag_5_rows": int(group["qc_flag"].eq(5).sum()),
            "use_flag_0_rows": int(group["use_flag"].eq(0).sum()),
            "source_file_names": ";".join(sorted(group["file_name"].dropna().unique())),
            "coordinates": f"{group['lat'].median():.5f},{group['lon'].median():.5f}",
            "datum": "unknown_in_GESLA_record; no conversion applied",
            "channel": "GESLA/BODC lineage; primary/secondary unresolved",
        })

    yearly_path = out_dir / "yearly_coverage.csv"
    pd.DataFrame(yearly).to_csv(yearly_path, index=False)
    metadata_path = out_dir / "parquet_metadata.json"
    schema = pq.read_schema(raw_path)
    metadata = {
        "path": str(raw_path),
        "size_bytes": raw_path.stat().st_size,
        "sha256": __import__("hashlib").sha256(raw_path.read_bytes()).hexdigest(),
        "manifest_sha256": str(pd.read_csv("data/clean/avonmouth_2007_gesla_gauge_only/raw_manifest.csv").iloc[0]["sha256"]),
        "sha_matches_manifest": __import__("hashlib").sha256(raw_path.read_bytes()).hexdigest()
        == str(pd.read_csv("data/clean/avonmouth_2007_gesla_gauge_only/raw_manifest.csv").iloc[0]["sha256"]),
        "schema": str(schema),
        "schema_metadata": {k.decode("utf-8"): v.decode("utf-8", errors="replace") for k, v in (schema.metadata or {}).items()},
        "row_groups": table_metadata.num_row_groups,
        "rows": table_metadata.num_rows,
        "created_by": table_metadata.created_by,
        "first_time_utc": identity.first_time_utc.isoformat(),
        "last_time_utc": identity.last_time_utc.isoformat(),
        "timestamp_physical_type": str(schema.field("date_time").type),
        "timestamp_timezone_in_schema": getattr(schema.field("date_time").type, "tz", None),
        "station": identity.station,
        "country": identity.country,
        "latitude": identity.latitude,
        "longitude": identity.longitude,
        "source_ids": list(identity.source_ids),
        "unit": "m per GESLA field documentation; no datum in Parquet metadata",
        "channel": "one GESLA/BODC-lineage record; original channel ID absent",
        "yearly_coverage_csv": str(yearly_path),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return {"yearly_coverage_csv": str(yearly_path), "parquet_metadata_json": str(metadata_path), "rows": table_metadata.num_rows}


def _utc_naive(values: pd.Series | pd.DatetimeIndex) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(pd.to_datetime(values, utc=True)).tz_localize(None)


def fit_utide(
    times: pd.Series | pd.DatetimeIndex,
    levels: np.ndarray | pd.Series,
    *,
    latitude: float,
    fit_start: str,
    fit_end: str,
    constit: str | list[str] = "auto",
    trend: bool = True,
    nodal: bool = True,
    phase: str = "Greenwich",
    conf_int: str = "none",
):
    """Fit only valid data inside the closed UTC fit interval."""
    utc_times = pd.DatetimeIndex(pd.to_datetime(times, utc=True))
    values = np.asarray(levels, dtype=float)
    start = pd.Timestamp(fit_start, tz="UTC")
    end_exclusive = pd.Timestamp(fit_end, tz="UTC") + pd.Timedelta(days=1)
    mask = (utc_times >= start) & (utc_times < end_exclusive) & np.isfinite(values)
    if int(mask.sum()) < 100:
        raise ValueError(f"Too few valid observations in {fit_start}..{fit_end}: {int(mask.sum())}")
    coef = solve(
        _utc_naive(utc_times[mask]), values[mask], lat=latitude, constit=constit,
        method="ols", conf_int=conf_int, order_constit="frequency", trend=trend,
        nodal=nodal, phase=phase, verbose=False,
    )
    return coef, mask


def save_reconstruction_state(coef, path: Path, *, design_id: str, model_id: str) -> Path:
    """Persist the minimum UTide state needed to reproduce harmonic predictions."""
    opt_keys = (
        "twodim", "nodsatlint", "nodsatnone", "gwchlint", "gwchnone",
        "prefilt", "notrend",
    )
    state = {
        "schema_version": 1,
        "design_id": design_id,
        "model_id": model_id,
        "constituent_names": np.asarray(coef.name).astype(str).tolist(),
        "amplitude_m": np.asarray(coef.A, dtype=float).tolist(),
        "phase_greenwich_deg": np.asarray(coef.g, dtype=float).tolist(),
        "mean_m": float(coef.mean),
        "trend_m_per_day": float(coef.slope) if hasattr(coef, "slope") else 0.0,
        "aux": {
            "reftime_utide_mpl_days": float(coef.aux.reftime),
            "frequency_cycles_per_day": np.asarray(coef.aux.frq, dtype=float).tolist(),
            "lind": np.asarray(coef.aux.lind).tolist(),
            "latitude_deg": float(coef.aux.lat),
            "opt": {key: coef.aux.opt[key] for key in opt_keys},
        },
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return path


def reconstruct_from_saved_state(times: pd.Series | pd.DatetimeIndex, path: Path) -> np.ndarray:
    """Rebuild A(t) from a saved coefficient and astronomical-argument state file."""
    state = json.loads(Path(path).read_text(encoding="utf-8"))
    if state.get("schema_version") != 1:
        raise ValueError(f"Unsupported UTide reconstruction state version: {state.get('schema_version')}")
    aux_data = state["aux"]
    opt = Bunch()
    opt.update(aux_data["opt"])
    aux = Bunch(
        reftime=aux_data["reftime_utide_mpl_days"],
        frq=np.asarray(aux_data["frequency_cycles_per_day"], dtype=float),
        lind=np.asarray(aux_data["lind"], dtype=int),
        lat=aux_data["latitude_deg"],
        opt=opt,
    )
    coef = Bunch(
        name=np.asarray(state["constituent_names"]),
        A=np.asarray(state["amplitude_m"], dtype=float),
        g=np.asarray(state["phase_greenwich_deg"], dtype=float),
        mean=state["mean_m"],
        slope=state["trend_m_per_day"],
        aux=aux,
    )
    values = reconstruct(
        _utc_naive(pd.DatetimeIndex(pd.to_datetime(times, utc=True))),
        coef, verbose=False, constit=state["constituent_names"],
    ).h
    return np.asarray(values, dtype=float)


def _coefficient_rows(coef, *, design_id: str, model_id: str, latitude: float, fit_start: str, fit_end: str) -> pd.DataFrame:
    names = np.asarray(coef.name).astype(str)
    amplitude = np.asarray(coef.A, dtype=float)
    phase = np.asarray(coef.g, dtype=float)
    mean = float(coef.mean)
    slope = float(coef.slope) if hasattr(coef, "slope") else 0.0
    return pd.DataFrame({
        "design_id": design_id,
        "model_id": model_id,
        "constituent": names,
        "amplitude_m": amplitude,
        "phase_greenwich_deg": phase,
        "mean_m": mean,
        "trend_m_per_day": slope,
        "latitude_deg": latitude,
        "fit_start_utc": fit_start,
        "fit_end_utc": fit_end,
        "datum": "unknown_in_GESLA_record; no conversion applied",
        "channel": "GESLA/BODC-lineage; original primary/secondary unresolved",
    })


def _welch_segments(hourly: pd.DataFrame, design_id: str, out_dir: Path) -> tuple[pd.DataFrame, dict[str, object]]:
    residual = hourly["residual_m"].to_numpy(dtype=float)
    valid = np.isfinite(residual)
    segment_ranges: list[tuple[int, int]] = []
    start = None
    for index, is_valid in enumerate(valid):
        if is_valid and start is None:
            start = index
        elif not is_valid and start is not None:
            segment_ranges.append((start, index))
            start = None
    if start is not None:
        segment_ranges.append((start, len(valid)))

    accepted = [(a, b) for a, b in segment_ranges if b - a >= SPECTRUM_NPERSEG]
    spectrum_sum = None
    total_windows = 0
    sample_count = 0
    for begin, finish in accepted:
        segment = residual[begin:finish]
        f, psd = welch(
            segment, fs=1.0, window="hann", nperseg=SPECTRUM_NPERSEG,
            noverlap=SPECTRUM_NOVERLAP, detrend="constant", return_onesided=True,
            scaling="density", average="mean",
        )
        windows = 1 + (len(segment) - SPECTRUM_NPERSEG) // (SPECTRUM_NPERSEG - SPECTRUM_NOVERLAP)
        spectrum_sum = psd * windows if spectrum_sum is None else spectrum_sum + psd * windows
        total_windows += windows
        sample_count += len(segment)
    if spectrum_sum is None:
        raise ValueError(f"No continuous valid residual segment of at least {SPECTRUM_NPERSEG} hours for {design_id}")
    spectrum = spectrum_sum / total_windows
    spectrum_frame = pd.DataFrame({
        "design_id": design_id,
        "frequency_cycles_per_hour": f,
        "psd_m2_per_cycle_per_hour": spectrum,
        "fs_samples_per_hour": 1.0,
        "window": "hann",
        "nperseg_hours": SPECTRUM_NPERSEG,
        "noverlap_hours": SPECTRUM_NOVERLAP,
        "detrend": "constant",
    })
    spectrum_frame.to_csv(out_dir / "residual_welch_spectrum.csv", index=False)
    return spectrum_frame, {
        "continuous_valid_segments": len(segment_ranges),
        "segments_used": len(accepted),
        "hours_contributing": sample_count,
        "welch_windows_contributing": total_windows,
        "minimum_segment_hours": SPECTRUM_NPERSEG,
        "longest_valid_segment_hours": max((b - a for a, b in segment_ranges), default=0),
        "fs_samples_per_hour": 1.0,
        "window": "hann",
        "nperseg_hours": SPECTRUM_NPERSEG,
        "noverlap_hours": SPECTRUM_NOVERLAP,
        "detrend": "constant",
        "scaling": "density",
        "psd_units": "m^2 per (cycle/hour)",
    }


def run_harmonic(config_path: Path) -> dict[str, object]:
    config = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    if "base_config" in config:
        base_path = Path(config["base_config"])
        base = yaml.safe_load(base_path.read_text(encoding="utf-8"))
        config = {**base, **config}
    source = config["sources"]["gauge"]
    design = config["harmonic_design"]
    design_id = design["design_id"]
    model_id = "UTide-0.4.0"
    raw_path = Path(source["raw_file"])
    frame, identity = read_gesla_parquet(raw_path)
    normalized = normalize_gesla(frame)
    exact = normalized.loc[
        normalized["time_utc"].dt.minute.eq(0)
        & normalized["time_utc"].dt.second.eq(0)
        & normalized["time_utc"].dt.microsecond.eq(0)
        & normalized["analysis_valid"]
    ].sort_values("time_utc").copy()
    output_dir = Path(design["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    coef, fit_mask = fit_utide(
        exact["time_utc"], exact["level_m"].to_numpy(), latitude=identity.latitude,
        fit_start=design["fit_start"], fit_end=design["fit_end"],
        constit=design["constituents"], trend=bool(design["trend"]),
        nodal=bool(design["nodal_corrections"]), phase=design["phase_convention"],
        conf_int=design.get("confidence_intervals", "none"),
    )
    fitted = exact.loc[fit_mask]
    fit_last = fitted["time_utc"].max()
    fit_year_counts = fitted.assign(year=fitted["time_utc"].dt.year).groupby("year").size().rename("fit_valid_observations").reset_index()
    fit_year_counts.to_csv(output_dir / "fit_year_counts.csv", index=False)

    hourly, hourly_counts = prepare_hourly(frame, year=2007)
    output_times = pd.DatetimeIndex(pd.to_datetime(hourly["time_utc"], utc=True))
    reconstruction_state_path = save_reconstruction_state(
        coef, output_dir / "utide_reconstruction_state.json",
        design_id=design_id, model_id=model_id,
    )
    a_values = reconstruct_from_saved_state(output_times, reconstruction_state_path)
    hourly["H_m"] = hourly["level_m"].astype(float)
    hourly["A_m"] = np.asarray(a_values, dtype=float)
    hourly["residual_m"] = hourly["H_m"] - hourly["A_m"]
    hourly["residual_m"] = hourly["residual_m"].where(hourly["analysis_valid"])
    hourly["qc_status"] = hourly["qc_reason"]
    hourly["model_id"] = model_id
    hourly["design_id"] = design_id
    hourly["source_datum"] = "unknown_in_GESLA_record; no conversion applied"
    hourly["source_channel"] = "GESLA/BODC-lineage; original primary/secondary unresolved"
    hourly_path = output_dir / "harmonic_hourly.parquet"
    hourly[["time_utc", "H_m", "A_m", "residual_m", "qc_status", "model_id", "design_id", "source_datum", "source_channel"]].to_parquet(hourly_path, index=False)

    coefficients_path = output_dir / "harmonic_coefficients.csv"
    coefficient_frame = _coefficient_rows(
        coef, design_id=design_id, model_id=model_id, latitude=identity.latitude,
        fit_start=design["fit_start"], fit_end=design["fit_end"],
    )
    coefficient_frame.to_csv(coefficients_path, index=False)

    residual = hourly.loc[hourly["analysis_valid"], "residual_m"].dropna()
    descriptive = pd.DataFrame([{
        "design_id": design_id,
        "model_id": model_id,
        "metric_scope": "descriptive hourly residual H-A; not peak MAE and not surge",
        "n_valid_hours": len(residual),
        "mean_residual_m": residual.mean(),
        "std_residual_m": residual.std(ddof=1),
        "rms_residual_m": float(np.sqrt(np.mean(np.square(residual)))),
        "min_residual_m": residual.min(),
        "max_residual_m": residual.max(),
        "source_datum": "unknown_in_GESLA_record",
        "channel": "unresolved",
    }])
    descriptive.to_csv(output_dir / "residual_descriptive_metrics.csv", index=False)
    spectrum, spectrum_meta = _welch_segments(hourly, design_id, output_dir)

    dates = output_times
    window = (dates >= pd.Timestamp("2007-01-01", tz="UTC")) & (dates < pd.Timestamp("2007-01-15", tz="UTC"))
    fig, (ax_top, ax_bottom) = plt.subplots(2, 1, figsize=(14, 8), sharex=True, height_ratios=[2, 1])
    ax_top.plot(dates[window], hourly.loc[window, "H_m"], color="#96a3ad", linewidth=0.8, label="H observed (valid QC only)")
    ax_top.plot(dates[window], hourly.loc[window, "A_m"], color="#087e8b", linewidth=1.2, label=f"A harmonic ({model_id}; {design_id})")
    ax_top.set_ylabel("Level (m; datum unspecified)")
    ax_top.legend(loc="best")
    ax_top.set_title("Avonmouth gauge-only: GESLA/BODC lineage; source channel and datum unresolved")
    ax_bottom.plot(dates[window], hourly.loc[window, "residual_m"], color="#d1495b", linewidth=0.8)
    ax_bottom.axhline(0, color="black", linewidth=0.6)
    ax_bottom.set_ylabel("H − A (m)")
    ax_bottom.set_xlabel("Time (UTC)")
    ax_bottom.xaxis.set_major_formatter(mdates.DateFormatter("%d %b\n%H:%M", tz=mdates.UTC))
    for axis in (ax_top, ax_bottom):
        axis.grid(alpha=0.2)
    fig.tight_layout()
    figure_path = output_dir / "harmonic_14day.png"
    fig.savefig(figure_path, dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.semilogx(spectrum["frequency_cycles_per_hour"].replace(0, np.nan), spectrum["psd_m2_per_cycle_per_hour"], color="#087e8b")
    ax.set_xlabel("Frequency (cycles/hour)")
    ax.set_ylabel("PSD (m² per (cycle/hour))")
    ax.set_title(f"Welch spectrum of hourly H−A; {spectrum_meta['hours_contributing']} valid hours")
    ax.grid(alpha=0.2, which="both")
    fig.tight_layout()
    spectrum_figure_path = output_dir / "residual_welch.png"
    fig.savefig(spectrum_figure_path, dpi=160)
    plt.close(fig)

    fit_manifest = {
        "design_id": design_id,
        "model_id": model_id,
        "model_library": "UTide",
        "model_library_version": utide.__version__,
        "scipy_version": scipy.__version__,
        "latitude_deg": identity.latitude,
        "longitude_deg": identity.longitude,
        "datum": "unknown_in_GESLA_record; no conversion applied",
        "source_channel": "GESLA/BODC-lineage; primary/secondary unresolved",
        "source_coordinate_differs_from_BODC_series_metadata": True,
        "fit_start_configured_utc": design["fit_start"],
        "fit_end_configured_utc": design["fit_end"],
        "fit_first_valid_observation_utc": fitted["time_utc"].min().isoformat(),
        "fit_last_valid_observation_utc": fit_last.isoformat(),
        "fit_valid_observations": len(fitted),
        "fit_year_counts_csv": str(output_dir / "fit_year_counts.csv"),
        "constituent_selection": design["constituents"],
        "constituents_fit": [str(name) for name in coef.name],
        "method": "ols",
        "mean_included": True,
        "mean_m": float(coef.mean),
        "trend_included": bool(design["trend"]),
        "trend_m_per_day": float(coef.slope) if hasattr(coef, "slope") else 0.0,
        "phase_convention": design["phase_convention"],
        "nodal_corrections": bool(design["nodal_corrections"]),
        "confidence_intervals": design.get("confidence_intervals", "none"),
        "confidence_interval_rationale": "disabled for the fit; confidence intervals are not consumed by this gauge-only baseline and are not used to reconstruct A(t)",
        "gauge_source": "GESLA S3 BODC-lineage object; release undeclared",
        "fit_observation_rule": "exact UTC minute-00 records with use_flag=1 and qc_flag=1; finite non-fill values",
        "hourly_output": str(hourly_path),
        "reconstruction_state": str(reconstruction_state_path),
        "hourly_output_rows": len(hourly),
        "hourly_expected_2007": 8760,
        "hourly_H_valid": int(hourly["H_m"].notna().sum()),
        "hourly_A_valid": int(hourly["A_m"].notna().sum()),
        "hourly_residual_valid": int(hourly["residual_m"].notna().sum()),
        "welch": spectrum_meta,
        "warning": "UTide is not verified equivalent to the paper's EHM; H-A residual may contain meteorological effects and harmonic-model error, not just surge.",
    }
    manifest_path = output_dir / "fit_manifest.json"
    manifest_path.write_text(json.dumps(fit_manifest, indent=2), encoding="utf-8")
    return {
        "design_id": design_id,
        "model_id": model_id,
        "fit_valid_observations": len(fitted),
        "fit_constituents": len(coef.name),
        "hourly_rows": len(hourly),
        "hourly_H_valid": int(hourly["H_m"].notna().sum()),
        "hourly_A_valid": int(hourly["A_m"].notna().sum()),
        "hourly_residual_valid": int(hourly["residual_m"].notna().sum()),
        "spectrum_hours": spectrum_meta["hours_contributing"],
        "outputs": str(output_dir),
    }
