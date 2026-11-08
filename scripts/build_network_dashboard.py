"""Build the offline P12 network dashboard and Power BI import tables."""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "dashboard" / "index.template.html"
REPORTS = ROOT / "reports" / "network_2010"
P12_CLEAN = ROOT / "data" / "clean" / "p12_network_2010"
PERIODS = ["retrospective_2006_2009", "heldout_2010"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _clean(value):
    if pd.isna(value):
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def build(output: Path = ROOT / "dashboard" / "index.html") -> Path:
    metrics_path = REPORTS / "network_metrics_paired.csv"
    inventory_path = REPORTS / "gesla_bodc_station_inventory.csv"
    fit_path = REPORTS / "station_fit_manifest.csv"
    forecast_path = REPORTS / "network_forecasts_paired.parquet"
    run_status_path = REPORTS / "run_status.csv"
    for path in (metrics_path, inventory_path, fit_path, forecast_path, run_status_path):
        if not path.exists():
            raise FileNotFoundError(f"Missing P12 artifact: {path}")
    if not TEMPLATE.exists():
        raise FileNotFoundError(f"Missing dashboard template: {TEMPLATE}")

    metrics = pd.read_csv(metrics_path).replace({np.nan: None})
    inventory = pd.read_csv(inventory_path)
    inventory = inventory.loc[inventory.paper_match.eq("matched")].sort_values("paper_port_number")
    fit = pd.read_csv(fit_path)
    status = pd.read_csv(run_status_path)
    if len(inventory) != 44 or len(metrics) != 176 or len(fit) != 44:
        raise ValueError("Expected the accepted 44-station P12 inventory, metric matrix, and fit manifest")
    coverage = []
    station_index: dict[str, int] = {}
    for idx, station in enumerate(inventory.itertuples(index=False)):
        run = status.loc[status.station_id.eq(fit.iloc[idx].station_id)].iloc[0]
        fit_row = fit.loc[fit.station_id.eq(run.station_id)].iloc[0]
        station_index[str(run.station_id)] = idx
        expected = int(station.y2010_expected_hours)
        present = int(station.y2010_minute00_present)
        valid = int(station.y2010_valid_minute00)
        coverage.append({
            "station_id": str(run.station_id), "port": int(station.paper_port_number),
            "station": str(station.paper_station), "latitude": float(station.latitude),
            "longitude": float(station.longitude), "unit": str(station.unit),
            "datum": str(station.datum), "channel": str(station.channel),
            "source_start": str(station.source_start_utc), "source_end": str(station.source_end_utc),
            "valid_2010": valid, "present_2010": present, "expected_2010": expected,
            "coverage_pct_2010": 100.0 * valid / expected if expected else None,
            "ecm_status": str(run.ecm_status), "harmonic_status": str(run.harmonic_status),
            "candidate_cycles_2010": int(fit_row.candidate_2010_cycles),
            "eligible_cycles_2010": int(fit_row.eligible_2010_cycles),
            "fit_observations": int(fit_row.fit_observations),
            "fit_start": str(fit_row.fit_start_utc), "fit_end": str(fit_row.fit_end_utc),
            "source_sha256": str(station.sha256),
        })
    period_index = {name: i for i, name in enumerate(PERIODS)}
    forecast = pd.read_parquet(forecast_path)
    forecast_rows: list[list[object]] = []
    lag_rows = 0
    missing_lag_rows = 0
    for station_id, group in forecast.groupby("station_id", sort=False):
        station_dir = P12_CLEAN / str(station_id)
        context_path = station_dir / "utide" / "high_water_context.parquet"
        if not context_path.exists():
            raise FileNotFoundError(f"Replay P12 before building dashboard; missing {context_path}")
        context = pd.read_parquet(context_path, columns=["cycle_id", "A_peak_time_utc", "H_peak_time_utc"])
        context["cycle_id"] = context.cycle_id.astype(str)
        group = group.copy()
        group["cycle_id"] = group.cycle_id.astype(str)
        group = group.merge(context, on="cycle_id", how="left", validate="one_to_one")
        lag_parts = []
        summary_path = station_dir / "ecm" / "p4_run_summary.json"
        if summary_path.exists():
            for model in json.loads(summary_path.read_text(encoding="utf-8")):
                period = "heldout_2010" if model["mode"] == "frozen_transfer" else "retrospective_2006_2009"
                frame = pd.read_parquet(ROOT / model["forecast_path"], columns=[
                    "cycle_id", "forecast_origin_utc", "forecast_target_time_utc", "forecast_status",
                    "P_ecm_m", "lag_n_minus_2_e_m", "lag_n_minus_4_e_m", "lag_n_minus_6_e_m",
                ])
                frame = frame.loc[frame.forecast_status.eq("issued_at_configured_origin") & frame.P_ecm_m.notna()].copy()
                frame["cycle_id"] = frame.cycle_id.astype(str)
                frame["period"] = period
                lag_parts.append(frame.drop(columns=["forecast_status", "P_ecm_m"]))
        lags = pd.concat(lag_parts, ignore_index=True) if lag_parts else pd.DataFrame(columns=[
            "cycle_id", "period", "forecast_origin_utc", "forecast_target_time_utc",
            "lag_n_minus_2_e_m", "lag_n_minus_4_e_m", "lag_n_minus_6_e_m",
        ])
        if not lags.empty:
            group = group.merge(lags, on=["cycle_id", "period"], how="left", validate="one_to_one", suffixes=("", "_ecm"))
        for row in group.itertuples(index=False):
            target_time = getattr(row, "forecast_target_time_utc", None)
            if target_time is None or pd.isna(target_time):
                target_time = row.A_peak_time_utc
            origin = getattr(row, "forecast_origin_utc", None)
            if origin is None or pd.isna(origin):
                origin = getattr(row, "forecast_origin_utc_ecm", None)
            vals = [
                station_index[str(station_id)], period_index[str(row.period)], str(row.cycle_id),
                None if pd.isna(target_time) else pd.Timestamp(target_time).isoformat(),
                None if origin is None or pd.isna(origin) else pd.Timestamp(origin).isoformat(),
                _clean(row.H_peak_m), _clean(row.A_peak_m), _clean(row.P_ecm_m),
                _clean(getattr(row, "lag_n_minus_2_e_m", None)),
                _clean(getattr(row, "lag_n_minus_4_e_m", None)),
                _clean(getattr(row, "lag_n_minus_6_e_m", None)),
                str(row.target),
            ]
            forecast_rows.append(vals)
            if vals[7] is not None and vals[8] is not None and vals[9] is not None and vals[10] is not None:
                lag_rows += 1
            elif vals[7] is not None:
                missing_lag_rows += 1

    metric_records = []
    for row in metrics.to_dict(orient="records"):
        metric_records.append({key: _clean(value) for key, value in row.items()})
    payload = {
        "stations": coverage,
        "periods": PERIODS,
        "metrics": metric_records,
        "forecast_columns": ["station_index", "period_index", "cycle_id", "target_time_utc", "origin_utc", "H_m", "A_m", "ECM_m", "lag_n2_m", "lag_n4_m", "lag_n6_m", "target"],
        "forecasts": forecast_rows,
        "target": "total_observed_water_level_gauge_only",
        "source_note": "GESLA S3; BODC lineage; channel and datum unresolved; no surge inferred",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    compressed = base64.b64encode(gzip.compress(encoded.encode("utf-8"), compresslevel=9, mtime=0)).decode("ascii")
    output.write_text(TEMPLATE.read_text(encoding="utf-8").replace("__NETWORK_DATA_GZIP_BASE64__", compressed), encoding="utf-8")
    manifest = {
        "dashboard": "dashboard/index.html", "dashboard_sha256": sha256(output), "dashboard_bytes": output.stat().st_size,
        "sources": {str(p.relative_to(ROOT)): sha256(p) for p in (metrics_path, inventory_path, fit_path, forecast_path, run_status_path)},
        "station_count": len(coverage), "metric_rows": len(metric_records), "forecast_rows": len(forecast_rows),
        "payload_json_bytes": len(encoded.encode("utf-8")), "payload_gzip_base64_bytes": len(compressed),
        "forecast_rows_with_all_three_lags": lag_rows, "forecast_rows_missing_lag_trace": missing_lag_rows,
        "models": ["UTide-0.4.0", "ECM-OLS-3lag"], "periods": PERIODS,
        "target": "total_observed_water_level_gauge_only", "external_assets": 0,
        "limitations": ["not direct Hibbert Table 2 reproduction", "surge unavailable", "source datum/channel unresolved", "Power BI Desktop UI refresh remains pending"],
    }
    manifest_path = output.with_name("manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _write_powerbi_tables(payload, ROOT / "data" / "bi_handoff_network")
    print(json.dumps(manifest, indent=2))
    return output


def _write_powerbi_tables(payload: dict[str, object], destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(payload["stations"]).to_csv(destination / "DimStation.csv", index=False)
    pd.DataFrame(payload["metrics"]).to_csv(destination / "FactPeakMetrics.csv", index=False)
    columns = payload["forecast_columns"]
    records = [dict(zip(columns, row)) for row in payload["forecasts"]]
    frame = pd.DataFrame(records)
    frame["station_id"] = frame.station_index.map({i: x["station_id"] for i, x in enumerate(payload["stations"])})
    frame["period"] = frame.period_index.map(dict(enumerate(payload["periods"])))
    frame["paired_sample"] = frame.ECM_m.notna()
    long_rows = []
    for model, prediction in (("UTide-0.4.0", "A_m"), ("ECM-OLS-3lag", "ECM_m")):
        part = frame.loc[frame[prediction].notna()].copy()
        part["model"] = model
        part["prediction_m"] = part[prediction]
        part["error_m"] = part.prediction_m - part.H_m
        if model.startswith("UTide"):
            part[["lag_n2_m", "lag_n4_m", "lag_n6_m"]] = None
        long_rows.append(part[[
            "station_id", "period", "cycle_id", "target_time_utc", "origin_utc", "target",
            "model", "H_m", "prediction_m", "error_m", "paired_sample", "lag_n2_m", "lag_n4_m", "lag_n6_m",
        ]])
    forecast_long = pd.concat(long_rows, ignore_index=True)
    station_path = destination / "DimStation.csv"
    period_path = destination / "DimPeriod.csv"
    model_path = destination / "DimModel.csv"
    metrics_path = destination / "FactPeakMetrics.csv"
    forecast_out = destination / "FactPeakForecast.csv"
    pd.DataFrame([
        {"period": "retrospective_2006_2009", "label": "2006–2009 retrospective (in-sample)", "is_in_sample": True},
        {"period": "heldout_2010", "label": "2010 held-out", "is_in_sample": False},
    ]).to_csv(period_path, index=False)
    pd.DataFrame([
        {"model": "UTide-0.4.0", "family": "harmonic baseline", "target": "total_observed_water_level_gauge_only"},
        {"model": "ECM-OLS-3lag", "family": "empirical correction", "target": "total_observed_water_level_gauge_only"},
    ]).to_csv(model_path, index=False)
    forecast_long.to_csv(forecast_out, index=False)
    manifest = {
        "tables": {p.name: {"sha256": sha256(p), "bytes": p.stat().st_size} for p in (station_path, period_path, model_path, metrics_path, forecast_out)},
        "rows": {"DimStation": len(payload["stations"]), "DimPeriod": 2, "DimModel": 2, "FactPeakMetrics": len(payload["metrics"]), "FactPeakForecast": len(forecast_long)},
        "target": "total_observed_water_level_gauge_only", "paired_sample_rule": "cycle ID must have an ECM issued prediction and QC-valid H",
    }
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dashboard" / "index.html")
    args = parser.parse_args()
    print(f"Built {build(args.output)}")
