"""Build an Avonmouth frozen-through-2009 gauge-only transfer baseline for 2010."""
from __future__ import annotations

from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd
import yaml

from .harmonic import fit_utide, reconstruct_from_saved_state, save_reconstruction_state, _coefficient_rows
from .ingest import normalize_gesla, prepare_hourly, read_gesla_station_parquet
from .peaks import extract_high_water_cycles


def run_transfer_2010(config_path: Path) -> dict[str, object]:
    config = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    raw_path = Path(config["raw_file"])
    expected_station = str(config.get("expected_station", "Avonmouth"))
    expected_country = str(config.get("expected_country", "GBR"))
    expected_source_ids = tuple(config.get("expected_source_ids", ("avonmouth-avo-gbr-bodc",)))
    frame, identity = read_gesla_station_parquet(
        raw_path,
        expected_station=expected_station,
        expected_country=expected_country,
        expected_source_ids=expected_source_ids,
    )
    station_id = str(config.get("station_id", "avonmouth"))
    normalized = normalize_gesla(frame)
    fit_start = str(config["fit_start"])
    fit_end = str(config["fit_end"])
    fit_years = (normalized["time_utc"].dt.year >= int(fit_start[:4])) & (normalized["time_utc"].dt.year <= int(fit_end[:4]))
    exact_minute = normalized["time_utc"].dt.minute.eq(0) & normalized["time_utc"].dt.second.eq(0) & normalized["time_utc"].dt.microsecond.eq(0)
    fit_observations = normalized.loc[fit_years & exact_minute & normalized["analysis_valid"]].copy()
    coef, used = fit_utide(
        fit_observations["time_utc"], fit_observations["level_m"].to_numpy(),
        latitude=identity.latitude, fit_start=fit_start, fit_end=fit_end,
        constit=config["constituents"], trend=bool(config["trend"]),
        nodal=bool(config["nodal_corrections"]), phase=str(config["phase_convention"]),
        conf_int=str(config["confidence_intervals"]),
    )
    output = Path(config["output_dir"])
    output.mkdir(parents=True, exist_ok=True)
    design_id = str(config["design_id"])
    state_path = save_reconstruction_state(coef, output / "utide_reconstruction_state.json", design_id=design_id, model_id="UTide-0.4.0")
    state_model = _coefficient_rows(
        coef, design_id=design_id, model_id="UTide-0.4.0", latitude=identity.latitude,
        fit_start=fit_start, fit_end=fit_end,
    )
    state_model.to_csv(output / "harmonic_coefficients.csv", index=False)

    hourly_parts = [prepare_hourly(frame, year, station_id=station_id)[0] for year in range(int(config["context_start_year"]), int(config["context_end_year"]) + 1)]
    hourly = pd.concat(hourly_parts, ignore_index=True)
    times = pd.DatetimeIndex(pd.to_datetime(hourly["time_utc"], utc=True))
    hourly["A_m"] = reconstruct_from_saved_state(times, state_path)
    hourly["H_m"] = pd.to_numeric(hourly["level_m"], errors="coerce").where(hourly["analysis_valid"])
    context = extract_high_water_cycles(
        hourly, design_id=design_id, target_year=None,
        minimum_cycle_hours=float(config["minimum_cycle_hours"]),
        maximum_cycle_hours=float(config["maximum_cycle_hours"]),
        station_id=station_id,
    )
    target_year = int(config["target_year"])
    target = context.loc[pd.to_datetime(context["A_peak_time_utc"], utc=True).dt.year.eq(target_year)].reset_index(drop=True)
    context.to_parquet(output / "high_water_context.parquet", index=False)
    target.to_parquet(output / "high_water_2010.parquet", index=False)
    target.to_csv(output / "high_water_2010.csv", index=False)
    context_summary = {
        "design_id": design_id,
        "model_id": "UTide-0.4.0",
        "station_id": station_id,
        "station": identity.station,
        "source_ids": list(identity.source_ids),
        "source_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
        "fit_start": fit_start,
        "fit_end": fit_end,
        "fit_observations": int(used.sum()),
        "latitude": identity.latitude,
        "longitude": identity.longitude,
        "constituents": [str(name) for name in coef.name],
        "trend": bool(config["trend"]),
        "nodal_corrections": bool(config["nodal_corrections"]),
        "confidence_intervals": str(config["confidence_intervals"]),
        "context_years": f"{config['context_start_year']}-{config['context_end_year']}",
        "context_cycles": int(len(context)),
        "target_year_cycles": int(len(target)),
        "target_year_eligible": int(target["high_water_eligible"].sum()),
        "target_year_excluded": int((~target["high_water_eligible"]).sum()),
        "datum": "unknown_in_GESLA_record; no conversion applied",
        "channel": "GESLA/BODC-lineage; original channel unresolved",
        "surge": "not used; gauge_only",
        "reconstruction_state": str(state_path),
        "context_path": str(output / "high_water_context.parquet"),
        "target_path": str(output / "high_water_2010.parquet"),
    }
    (output / "transfer_manifest.json").write_text(json.dumps(context_summary, indent=2), encoding="utf-8")
    return context_summary
