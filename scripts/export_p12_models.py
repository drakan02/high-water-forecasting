"""Export compact, reviewable per-port fit manifests and model coefficients."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/p12_network_2010.yaml"))
    args = parser.parse_args()
    config = json.loads(args.config.read_text()) if args.config.suffix == ".json" else None
    if config is None:
        import yaml
        config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    clean_root = Path(config["output_dir"])
    inventory = pd.read_csv(config["inventory_csv"])
    sites = inventory.loc[inventory.paper_match.eq("matched")].sort_values("paper_port_number")
    run_status = pd.read_csv(clean_root / "run_status.csv")
    station_rows: list[dict[str, object]] = []
    harmonic_rows: list[pd.DataFrame] = []
    ecm_rows: list[dict[str, object]] = []
    for site in sites.itertuples(index=False):
        run = run_status.loc[run_status.paper_port_number.eq(site.paper_port_number)].iloc[0]
        station_id = str(run.station_id)
        station_dir = clean_root / station_id
        transfer = json.loads((station_dir / "utide" / "transfer_manifest.json").read_text(encoding="utf-8"))
        station_rows.append({
            "paper_port_number": int(site.paper_port_number), "paper_station": site.paper_station,
            "station_id": station_id, "source_id": site.source_id, "source_sha256": site.sha256,
            "source_start_utc": site.source_start_utc, "source_end_utc": site.source_end_utc,
            "unit": site.unit, "datum": transfer["datum"], "channel": transfer["channel"],
            "latitude_deg": transfer["latitude"], "longitude_deg": transfer["longitude"],
            "harmonic_model": transfer["model_id"], "fit_start_utc": transfer["fit_start"],
            "fit_end_utc": transfer["fit_end"], "fit_observations": transfer["fit_observations"],
            "constituent_count": len(transfer["constituents"]), "constituents": ";".join(transfer["constituents"]),
            "trend": transfer["trend"], "nodal_corrections": transfer["nodal_corrections"],
            "confidence_intervals": transfer["confidence_intervals"],
            "context_cycles": transfer["context_cycles"], "candidate_2010_cycles": transfer["target_year_cycles"],
            "eligible_2010_cycles": transfer["target_year_eligible"],
            "surge_status": transfer["surge"],
        })
        coefficients = pd.read_csv(station_dir / "utide" / "harmonic_coefficients.csv")
        coefficients.insert(0, "paper_station", site.paper_station)
        coefficients.insert(0, "paper_port_number", int(site.paper_port_number))
        coefficients.insert(0, "station_id", station_id)
        harmonic_rows.append(coefficients)
        summary_path = station_dir / "ecm" / "p4_run_summary.json"
        if summary_path.exists():
            for model in json.loads(summary_path.read_text(encoding="utf-8")):
                ecm_rows.append({
                    "paper_port_number": int(site.paper_port_number), "paper_station": site.paper_station,
                    "station_id": station_id, "design_id": model["design_id"], "mode": model["mode"],
                    "target": "total_observed_water_level_gauge_only", "fit_years": ";".join(map(str, model["fit_years"])),
                    "fit_rows": model["fit_rows"], "design_matrix_rank": model["design_matrix_rank"],
                    "design_matrix_columns": model["design_matrix_columns"], "issue_lead_hours": model["issue_lead_hours"],
                    "C1_lag_N_minus_2": model["coefficients"]["C1"],
                    "C2_lag_N_minus_4": model["coefficients"]["C2"],
                    "C3_lag_N_minus_6": model["coefficients"]["C3"],
                    "C4_intercept_m": model["coefficients"]["C4_intercept_m"],
                    "model_sha256": model["model_sha256"], "forecastable_rows": model["forecastable_rows"],
                    "excluded_rows": model["excluded_rows"], "surge_status": model["surge_status"],
                })
    report_root = Path("reports/network_2010")
    pd.DataFrame(station_rows).to_csv(report_root / "station_fit_manifest.csv", index=False)
    pd.concat(harmonic_rows, ignore_index=True).to_csv(report_root / "harmonic_coefficients.csv", index=False)
    pd.DataFrame(ecm_rows).to_csv(report_root / "ecm_models.csv", index=False)
    print(f"exported stations={len(station_rows)} harmonic_rows={sum(len(x) for x in harmonic_rows)} ecm_models={len(ecm_rows)}")


if __name__ == "__main__":
    main()
