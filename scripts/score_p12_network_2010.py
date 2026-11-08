"""Score gauge-only forecasts for the 44 Hibbert ports on paired peak cycles."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


def _metrics(actual: pd.Series, prediction: pd.Series) -> tuple[int, float, float]:
    pair = pd.DataFrame({"actual": pd.to_numeric(actual, errors="coerce"), "prediction": pd.to_numeric(prediction, errors="coerce")}).dropna()
    if pair.empty:
        return 0, float("nan"), float("nan")
    error = pair.prediction.to_numpy() - pair.actual.to_numpy()
    return len(pair), float(np.abs(error).mean()), float(np.sqrt(np.square(error).mean()))


def _sample_hash(cycle_ids: pd.Series) -> str:
    payload = "\n".join(sorted(cycle_ids.astype(str))).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/p12_network_2010.yaml"))
    args = parser.parse_args()
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    root = Path(config["output_dir"])
    inventory = pd.read_csv(config["inventory_csv"])
    sites = inventory.loc[inventory.paper_match.eq("matched")].sort_values("paper_port_number")
    metric_rows: list[dict[str, object]] = []
    forecast_rows: list[pd.DataFrame] = []
    for site in sites.itertuples(index=False):
        port = int(site.paper_port_number)
        station_id = f"p{port:02d}_" + "_".join(str(site.paper_station).lower().replace("(", " ").replace(")", " ").split())
        station_dir = root / station_id
        status_file = root / "run_status.csv"
        status_df = pd.read_csv(status_file) if status_file.exists() else pd.DataFrame()
        status_match = status_df.loc[status_df.station_id.eq(station_id)] if not status_df.empty else pd.DataFrame()
        status = status_match.iloc[0].to_dict() if not status_match.empty else {}
        context_path = station_dir / "utide" / "high_water_context.parquet"
        if not context_path.exists():
            for period in ("retrospective_2006_2009", "heldout_2010"):
                for model in ("UTide-0.4.0", "ECM-OLS-3lag"):
                    metric_rows.append({"paper_port_number": port, "paper_station": site.paper_station, "station_id": station_id, "period": period, "model": model, "target": "total_observed_water_level_gauge_only", "status": status.get("harmonic_status", "MISSING_ARTIFACT") if model.startswith("UTide") else status.get("ecm_status", "MISSING_ARTIFACT"), "comparison_scope": "no_scored_artifact", "n_scored_paired": 0, "MAE_m": np.nan, "RMSE_m": np.nan, "MAE_cm": np.nan, "RMSE_cm": np.nan, "paired_cycle_sha256": ""})
            continue
        context = pd.read_parquet(context_path)
        context["A_peak_time_utc"] = pd.to_datetime(context.A_peak_time_utc, utc=True)
        forecasts_by_period: dict[str, pd.DataFrame] = {}
        for period, years in (("retrospective_2006_2009", range(2006, 2010)), ("heldout_2010", [2010])):
            actual = context.loc[context.A_peak_time_utc.dt.year.isin(years) & context.high_water_eligible.astype(bool)].copy()
            actual = actual.dropna(subset=["H_peak_m", "A_peak_m"])
            ecm = pd.DataFrame()
            fit_years = str(status.get("ecm_fit_years", "2006;2007;2008;2009")).split(";")
            fit_years = [int(x) for x in fit_years if x]
            suffix = f"{fit_years[0]}_{fit_years[-1]}" if fit_years else ""
            if period == "heldout_2010":
                design = f"{station_id}_network_2010_fit_{suffix}"
            else:
                design = f"{station_id}_retrospective_2006_2009_fit_{suffix}"
            ecm_path = station_dir / "ecm" / design / "forecasts_unscored.parquet"
            ecm_status = str(status.get("ecm_status", "MISSING_ARTIFACT"))
            if ecm_path.exists():
                ecm = pd.read_parquet(ecm_path)
                ecm = ecm.loc[ecm.forecast_status.eq("issued_at_configured_origin") & ecm.P_ecm_m.notna()].copy()
                ecm["cycle_id"] = ecm.cycle_id.astype(str)
            model_rows = actual[["cycle_id", "H_peak_m", "A_peak_m"]].copy()
            if not ecm.empty:
                model_rows = model_rows.merge(ecm[["cycle_id", "P_ecm_m", "forecast_origin_utc", "forecast_target_time_utc", "model_id"]], on="cycle_id", how="inner", validate="one_to_one")
            else:
                model_rows["P_ecm_m"] = np.nan
            n, mae, rmse = _metrics(model_rows.H_peak_m, model_rows.A_peak_m)
            digest = _sample_hash(model_rows.cycle_id) if n else ""
            ecm_not_applicable = str(ecm_status) == "NOT_APPLICABLE_PER_PAPER"
            metric_rows.append({"paper_port_number": port, "paper_station": site.paper_station, "station_id": station_id, "period": period, "model": "UTide-0.4.0", "target": "total_observed_water_level_gauge_only", "status": status.get("harmonic_status", "DONE"), "comparison_scope": "harmonic_only_ecm_not_applicable" if ecm_not_applicable else "paired_with_ecm", "eligible_peaks": len(actual), "ecm_forecastable_peaks": 0 if ecm_not_applicable else len(model_rows), "n_scored_paired": 0 if ecm_not_applicable else n, "n_scored_model": len(actual) if ecm_not_applicable else n, "MAE_m": _metrics(actual.H_peak_m, actual.A_peak_m)[1] if ecm_not_applicable else mae, "RMSE_m": _metrics(actual.H_peak_m, actual.A_peak_m)[2] if ecm_not_applicable else rmse, "MAE_cm": _metrics(actual.H_peak_m, actual.A_peak_m)[1] * 100 if ecm_not_applicable else (mae * 100 if np.isfinite(mae) else np.nan), "RMSE_cm": _metrics(actual.H_peak_m, actual.A_peak_m)[2] * 100 if ecm_not_applicable else (rmse * 100 if np.isfinite(rmse) else np.nan), "paired_cycle_sha256": "" if ecm_not_applicable else digest})
            if str(ecm_status) == "NOT_APPLICABLE_PER_PAPER":
                ecm_metric_status = ecm_status
            elif not ecm_path.exists():
                ecm_metric_status = ecm_status if ecm_status != "DONE" else "MISSING_ARTIFACT"
            else:
                ecm_metric_status = "DONE" if len(model_rows) else "NO_PAIRED_FORECASTS"
            e_n, e_mae, e_rmse = _metrics(model_rows.H_peak_m, model_rows.P_ecm_m)
            metric_rows.append({"paper_port_number": port, "paper_station": site.paper_station, "station_id": station_id, "period": period, "model": "ECM-OLS-3lag", "target": "total_observed_water_level_gauge_only", "status": ecm_metric_status, "comparison_scope": "not_applicable_per_paper" if ecm_not_applicable else "paired_with_utide", "eligible_peaks": len(actual), "ecm_forecastable_peaks": e_n, "n_scored_paired": e_n, "MAE_m": e_mae, "RMSE_m": e_rmse, "MAE_cm": e_mae * 100 if np.isfinite(e_mae) else np.nan, "RMSE_cm": e_rmse * 100 if np.isfinite(e_rmse) else np.nan, "paired_cycle_sha256": _sample_hash(model_rows.loc[model_rows.P_ecm_m.notna(), "cycle_id"]) if e_n else ""})
            scored = model_rows.copy()
            scored["paper_port_number"] = port
            scored["paper_station"] = site.paper_station
            scored["station_id"] = station_id
            scored["period"] = period
            scored["target"] = "total_observed_water_level_gauge_only"
            forecast_rows.append(scored)
    metrics = pd.DataFrame(metric_rows)
    forecasts = pd.concat(forecast_rows, ignore_index=True) if forecast_rows else pd.DataFrame()
    root.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(root / "network_metrics_paired.csv", index=False)
    forecasts.to_parquet(root / "network_forecasts_paired.parquet", index=False)
    forecasts.to_csv(root / "network_forecasts_paired.csv", index=False)
    summary = {"metric_rows": len(metrics), "ports": int(metrics.paper_port_number.nunique()), "forecast_rows": len(forecasts), "status_counts": metrics.groupby(["model", "status"]).size().reset_index(name="rows").to_dict(orient="records"), "target": "total_observed_water_level_gauge_only", "metric_scope": "paired high-water cycles only; UTide and ECM on identical forecastable cycle IDs", "metrics_csv_sha256": hashlib.sha256((root / "network_metrics_paired.csv").read_bytes()).hexdigest()}
    (root / "network_scoring_manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
