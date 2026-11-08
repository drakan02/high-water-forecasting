"""Build stable semi-diurnal high-water cycles from hourly gauge and harmonic series."""
from __future__ import annotations

from pathlib import Path
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

from .harmonic import reconstruct_from_saved_state
from .ingest import normalize_gesla, prepare_hourly, read_gesla_parquet


def _turning_points(values: np.ndarray, times: pd.DatetimeIndex, *, kind: str) -> list[dict[str, object]]:
    """Find discrete extrema, selecting the earliest center sample of exact plateaus."""
    if kind not in {"min", "max"}:
        raise ValueError("kind must be 'min' or 'max'")
    direction = 1 if kind == "min" else -1
    extrema: list[dict[str, object]] = []
    index = 0
    while index < len(values):
        if not np.isfinite(values[index]):
            index += 1
            continue
        end = index
        while end + 1 < len(values) and np.isfinite(values[end + 1]) and values[end + 1] == values[index]:
            end += 1
        if index > 0 and end + 1 < len(values):
            left = values[index - 1]
            right = values[end + 1]
            value = values[index]
            is_extreme = value < left and value < right if kind == "min" else value > left and value > right
            if is_extreme:
                chosen = index + (end - index) // 2
                extrema.append({
                    "index": chosen,
                    "time_utc": times[chosen],
                    "value_m": float(values[chosen]),
                    "plateau_samples": end - index + 1,
                    "plateau_ambiguous": end > index,
                })
        index = end + 1
    return extrema


def extract_high_water_cycles(
    hourly: pd.DataFrame,
    *,
    design_id: str,
    target_year: int | None,
    minimum_cycle_hours: float = 8.0,
    maximum_cycle_hours: float = 16.0,
    station_id: str = "avonmouth",
) -> pd.DataFrame:
    """Pair consecutive low-water minima, then maximize A and H separately per cycle."""
    required = {"time_utc", "H_m", "A_m", "analysis_valid"}
    missing = required.difference(hourly.columns)
    if missing:
        raise ValueError(f"Missing hourly input columns: {', '.join(sorted(missing))}")
    data = hourly.copy()
    data["time_utc"] = pd.to_datetime(data["time_utc"], utc=True)
    data = data.sort_values("time_utc").reset_index(drop=True)
    if data["time_utc"].duplicated().any():
        raise ValueError("Hourly input must have unique timestamps")
    times = pd.DatetimeIndex(data["time_utc"])
    expected = pd.date_range(times.min(), times.max(), freq="h", tz="UTC")
    if not times.equals(expected):
        raise ValueError("Hourly input must be a complete regular UTC hourly grid")
    a = pd.to_numeric(data["A_m"], errors="coerce").to_numpy(dtype=float)
    h = pd.to_numeric(data["H_m"], errors="coerce").to_numpy(dtype=float)
    valid = data["analysis_valid"].fillna(False).to_numpy(dtype=bool) & np.isfinite(h)
    minima = _turning_points(a, times, kind="min")
    records: list[dict[str, object]] = []
    for number, (left, right) in enumerate(zip(minima, minima[1:], strict=False), start=1):
        start_i, end_i = int(left["index"]), int(right["index"])
        duration = float((times[end_i] - times[start_i]).total_seconds() / 3600)
        indices = np.arange(start_i, end_i)
        if indices.size == 0:
            continue
        local_a = a[indices]
        max_a = float(np.nanmax(local_a))
        a_ties = indices[np.isclose(local_a, max_a, rtol=0, atol=1e-12)]
        a_peak_i = int(a_ties[0])
        observed_indices = indices[valid[indices]]
        expected_n = len(indices)
        valid_n = len(observed_indices)
        fraction = valid_n / expected_n if expected_n else 0.0
        if valid_n:
            local_h = h[observed_indices]
            max_h = float(np.max(local_h))
            h_ties = observed_indices[np.isclose(local_h, max_h, rtol=0, atol=1e-12)]
            h_peak_i = int(h_ties[0])
            h_peak_time = times[h_peak_i]
        else:
            max_h = np.nan
            h_peak_i = -1
            h_peak_time = pd.NaT
        full_gauge_coverage = valid_n == expected_n
        duration_ok = minimum_cycle_hours <= duration <= maximum_cycle_hours
        reason = []
        if not full_gauge_coverage:
            reason.append("gauge_gap_in_cycle")
        if not duration_ok:
            reason.append("cycle_duration_outside_registered_bounds")
        if bool(left["plateau_ambiguous"]) or bool(right["plateau_ambiguous"]):
            reason.append("harmonic_low_water_plateau_earliest_center_used")
        cycle_id = f"{station_id}:{design_id}:{times[start_i].strftime('%Y%m%dT%H%MZ')}"
        records.append({
            "station_id": station_id,
            "branch": "gauge_only",
            "design_id": design_id,
            "cycle_number": number,
            "cycle_id": cycle_id,
            "cycle_start_utc": times[start_i],
            "cycle_end_utc_exclusive": times[end_i],
            "cycle_duration_hours": duration,
            "cycle_duration_valid": duration_ok,
            "cycle_start_low_water_A_m": float(left["value_m"]),
            "cycle_end_low_water_A_m": float(right["value_m"]),
            "low_water_boundary_ambiguous": bool(left["plateau_ambiguous"]) or bool(right["plateau_ambiguous"]),
            "expected_hourly_samples": expected_n,
            "gauge_valid_hourly_samples": valid_n,
            "gauge_coverage_fraction": fraction,
            "gauge_window_complete": full_gauge_coverage,
            "A_peak_time_utc": times[a_peak_i],
            "A_peak_m": max_a,
            "A_peak_plateau_samples": len(a_ties),
            "H_peak_time_utc": h_peak_time,
            "H_peak_m": max_h,
            "H_peak_plateau_samples": int(np.sum(np.isclose(h[observed_indices], max_h, rtol=0, atol=1e-12))) if valid_n else 0,
            "H_minus_A_gauge_only_m": max_h - max_a if full_gauge_coverage else np.nan,
            "surge_m": np.nan,
            "surge_status": "unavailable_not_inferred",
            "target_type": "total_observed_water_level_gauge_only",
            "high_water_eligible": bool(full_gauge_coverage and duration_ok),
            "exclusion_reason": ";".join(reason),
            "source_datum": "unknown_in_GESLA_record; no conversion applied",
            "source_channel": "GESLA/BODC-lineage; original primary/secondary unresolved",
            "peak_rule": "left-closed_right-open interval between consecutive hourly A(t) minima; H and A maxima selected separately",
        })
    output = pd.DataFrame.from_records(records)
    if target_year is not None:
        output = output.loc[pd.to_datetime(output["A_peak_time_utc"], utc=True).dt.year.eq(target_year)]
    return output.reset_index(drop=True)


def run_peak_cycles(config_path: Path) -> dict[str, object]:
    config_path = Path(config_path)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    base = yaml.safe_load(Path(config["base_config"]).read_text(encoding="utf-8"))
    raw_path = Path(base["sources"]["gauge"]["raw_file"])
    frame, identity = read_gesla_parquet(raw_path)
    normalized = normalize_gesla(frame)
    target_year = int(config["target_year"])
    context_start = int(config["context_start_year"])
    context_end = int(config["context_end_year"])
    hourly_parts = [prepare_hourly(frame, year)[0] for year in range(context_start, context_end + 1)]
    gauge = pd.concat(hourly_parts, ignore_index=True)
    times = pd.DatetimeIndex(pd.to_datetime(gauge["time_utc"], utc=True))

    summaries = []
    output_root = Path(config["output_dir"])
    output_root.mkdir(parents=True, exist_ok=True)
    for design_path in config["design_configs"]:
        design_config = yaml.safe_load(Path(design_path).read_text(encoding="utf-8"))
        design = design_config["harmonic_design"]
        design_id = design["design_id"]
        state_path = Path(design["output_dir"]) / "utide_reconstruction_state.json"
        if not state_path.is_file():
            raise FileNotFoundError(f"Missing accepted P2 reconstruction state: {state_path}")
        combined = gauge.copy()
        combined["A_m"] = reconstruct_from_saved_state(times, state_path)
        combined["H_m"] = pd.to_numeric(combined["level_m"], errors="coerce").where(combined["analysis_valid"])
        context_peaks = extract_high_water_cycles(
            combined, design_id=design_id, target_year=None,
            minimum_cycle_hours=float(config["minimum_cycle_hours"]),
            maximum_cycle_hours=float(config["maximum_cycle_hours"]),
        )
        context_parquet_path = output_root / design_id / "high_water_context.parquet"
        context_csv_path = output_root / design_id / "high_water_context.csv"
        context_parquet_path.parent.mkdir(parents=True, exist_ok=True)
        context_peaks.to_parquet(context_parquet_path, index=False)
        context_peaks.to_csv(context_csv_path, index=False)
        peaks = context_peaks.loc[
            pd.to_datetime(context_peaks["A_peak_time_utc"], utc=True).dt.year.eq(target_year)
        ].reset_index(drop=True)
        out_dir = output_root / design_id
        out_dir.mkdir(parents=True, exist_ok=True)
        parquet_path = out_dir / "high_water.parquet"
        csv_path = out_dir / "high_water.csv"
        exclusions_path = out_dir / "exclusions.csv"
        review_path = out_dir / "first_20_cycle_review.csv"
        peaks.to_parquet(parquet_path, index=False)
        peaks.to_csv(csv_path, index=False)
        peaks.loc[~peaks["high_water_eligible"]].to_csv(exclusions_path, index=False)
        review_parts = []
        early = peaks.head(14).copy()
        early["review_sample_reason"] = "clear_cycles_near_start_of_2007"
        review_parts.append(early)
        gap_rows = peaks.loc[peaks["exclusion_reason"].str.contains("gauge_gap_in_cycle")].head(1).copy()
        if not gap_rows.empty:
            gap_rows["review_sample_reason"] = "cycle_contains_missing_or_suspect_gauge_hour"
            review_parts.append(gap_rows)
        unusual = peaks.loc[~peaks["cycle_duration_valid"] | peaks["low_water_boundary_ambiguous"]].head(1).copy()
        if not unusual.empty:
            unusual["review_sample_reason"] = "unusual_duration_or_ambiguous_low_boundary"
            review_parts.append(unusual)
        selected_ids = set(pd.concat(review_parts)["cycle_id"])
        remaining = peaks.loc[~peaks["cycle_id"].isin(selected_ids)].tail(max(0, 20 - len(selected_ids))).copy()
        remaining["review_sample_reason"] = "near_end_of_target_year"
        review_parts.append(remaining)
        pd.concat(review_parts, ignore_index=True).to_csv(review_path, index=False)

        plot_start = pd.Timestamp(f"{target_year}-01-01", tz="UTC")
        plot_end = plot_start + pd.Timedelta(days=14)
        plot_mask = (times >= plot_start) & (times < plot_end)
        ptime = pd.to_datetime(peaks["A_peak_time_utc"], utc=True)
        peak_mask = ptime.ge(plot_start) & ptime.lt(plot_end)
        fig, ax = plt.subplots(figsize=(14, 5))
        ax.plot(times[plot_mask], combined.loc[plot_mask, "H_m"], color="#96a3ad", linewidth=0.8, label="H observed (valid QC)")
        ax.plot(times[plot_mask], combined.loc[plot_mask, "A_m"], color="#087e8b", linewidth=1.1, label="A UTide")
        shown = peaks.loc[peak_mask]
        ax.scatter(pd.to_datetime(shown["A_peak_time_utc"], utc=True), shown["A_peak_m"], marker="^", s=24, color="#087e8b", label="A high water")
        observed = shown.loc[shown["H_peak_m"].notna()]
        ax.scatter(pd.to_datetime(observed["H_peak_time_utc"], utc=True), observed["H_peak_m"], marker="v", s=22, color="#d1495b", label="H high water")
        ax.set_title(f"{design_id}: first 14 days; hourly low-water boundaries define cycles")
        ax.set_ylabel("Level (m; source datum unspecified)")
        ax.set_xlabel("Time (UTC)")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b\n%H:%M", tz=mdates.UTC))
        ax.grid(alpha=0.2)
        ax.legend(loc="best")
        fig.tight_layout()
        figure_path = out_dir / "peak_review_first_14_days.png"
        fig.savefig(figure_path, dpi=160)
        plt.close(fig)

        gap_figure_path = None
        if not gap_rows.empty:
            gap_row = gap_rows.iloc[0]
            gap_start = pd.Timestamp(gap_row["cycle_start_utc"]) - pd.Timedelta(hours=6)
            gap_end = pd.Timestamp(gap_row["cycle_end_utc_exclusive"]) + pd.Timedelta(hours=6)
            gap_mask = (times >= gap_start) & (times <= gap_end)
            fig, ax = plt.subplots(figsize=(12, 4))
            ax.plot(times[gap_mask], combined.loc[gap_mask, "H_m"], color="#96a3ad", marker=".", label="H observed (valid QC)")
            ax.plot(times[gap_mask], combined.loc[gap_mask, "A_m"], color="#087e8b", label="A UTide")
            ax.axvspan(pd.Timestamp(gap_row["cycle_start_utc"]), pd.Timestamp(gap_row["cycle_end_utc_exclusive"]), color="#d1495b", alpha=0.12, label="reviewed cycle (contains gap)")
            ax.set_title(f"QC gap cycle {gap_row['cycle_id']}; no interpolation used")
            ax.set_ylabel("Level (m; source datum unspecified)")
            ax.set_xlabel("Time (UTC)")
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b %H:%M", tz=mdates.UTC))
            ax.grid(alpha=0.2)
            ax.legend(loc="best")
            fig.tight_layout()
            gap_figure_path = out_dir / "peak_review_gap_cycle.png"
            fig.savefig(gap_figure_path, dpi=160)
            plt.close(fig)

        summary = {
            "design_id": design_id,
            "target_year": target_year,
            "context_years": f"{context_start}-{context_end}",
            "cycle_boundary_rule": config["cycle_boundary_rule"],
            "cycle_interval": config["cycle_interval"],
            "minimum_cycle_hours": float(config["minimum_cycle_hours"]),
            "maximum_cycle_hours": float(config["maximum_cycle_hours"]),
            "require_complete_hourly_gauge_window": bool(config["require_complete_hourly_gauge_window"]),
            "context_cycle_rows": len(context_peaks),
            "context_parquet": str(context_parquet_path),
            "context_csv": str(context_csv_path),
            "cycles_in_target_year": len(peaks),
            "eligible_complete_cycles": int(peaks["high_water_eligible"].sum()),
            "excluded_cycles": int((~peaks["high_water_eligible"]).sum()),
            "gauge_gap_cycles": int(peaks["exclusion_reason"].str.contains("gauge_gap_in_cycle").sum()),
            "duration_flagged_cycles": int((~peaks["cycle_duration_valid"]).sum()),
            "ambiguous_low_boundary_cycles": int(peaks["low_water_boundary_ambiguous"].sum()),
            "median_cycle_duration_hours": float(peaks["cycle_duration_hours"].median()),
            "minimum_cycle_duration_hours": float(peaks["cycle_duration_hours"].min()),
            "maximum_cycle_duration_hours": float(peaks["cycle_duration_hours"].max()),
            "source_file_sha256": __import__("hashlib").sha256(raw_path.read_bytes()).hexdigest(),
            "source_station": identity.station,
            "latitude": identity.latitude,
            "longitude": identity.longitude,
            "output_parquet": str(parquet_path),
            "output_csv": str(csv_path),
            "exclusions_csv": str(exclusions_path),
            "review_sample_csv": str(review_path),
            "review_figure": str(figure_path),
            "gap_review_figure": str(gap_figure_path) if gap_figure_path else "none; no gap cycle present",
            "review_sample_rows": int(sum(len(part) for part in review_parts)),
        }
        (out_dir / "peak_manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        summaries.append(summary)
    summary_path = output_root / "peak_summary.csv"
    pd.DataFrame(summaries).to_csv(summary_path, index=False)
    return {"target_year": target_year, "designs": summaries, "summary_csv": str(summary_path)}
