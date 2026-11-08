"""Score paired Newport 2010 gauge-only high-water forecasts."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", type=Path, default=Path("data/clean/p11_newport_transfer_2010/high_water_2010.parquet"))
    parser.add_argument("--forecasts", type=Path, default=Path("data/clean/p11_newport_transfer_2010/ecm/newport_transfer_2010_fit_1993_2009/forecasts_unscored.parquet"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/clean/p11_newport_transfer_2010/scored"))
    args = parser.parse_args()
    labels = pd.read_parquet(args.labels)
    forecasts = pd.read_parquet(args.forecasts)
    joined = labels.merge(forecasts, on=["station_id", "cycle_id"], suffixes=("_label", "_forecast"), validate="one_to_one")
    common = (
        joined["high_water_eligible"].fillna(False)
        & joined["forecast_inputs_available"].fillna(False)
        & joined["P_base_m"].notna()
        & joined["P_ecm_m"].notna()
    )
    paired = joined.loc[common].copy()
    if paired.empty:
        raise ValueError("No common QC-eligible high-water cycles for baseline and ECM")
    paired["baseline_error_m"] = paired["H_peak_m"] - paired["P_base_m"]
    paired["ecm_error_m"] = paired["H_peak_m"] - paired["P_ecm_m"]
    cycle_hash = hashlib.sha256("\n".join(sorted(paired["cycle_id"].astype(str))).encode()).hexdigest()
    rows = []
    for model_id, column in (("UTide-0.4.0_fit_1993_2009", "baseline_error_m"), ("ECM_OLS_fit_2009", "ecm_error_m")):
        error_cm = paired[column].to_numpy(float) * 100.0
        rows.append({
            "station_id": "newport",
            "model_id": model_id,
            "period": "test_2010_high_water",
            "target": "total_observed_water_level_gauge_only",
            "paired_n": len(paired),
            "MAE_cm": float(np.mean(np.abs(error_cm))),
            "RMSE_cm": float(np.sqrt(np.mean(error_cm ** 2))),
            "bias_cm": float(np.mean(error_cm)),
            "paired_cycle_id_sha256": cycle_hash,
        })
    args.output_dir.mkdir(parents=True, exist_ok=True)
    paired[["station_id", "cycle_number_label", "cycle_id", "A_peak_time_utc", "H_peak_time_utc", "A_peak_m", "H_peak_m", "P_base_m", "P_ecm_m", "ECM_correction_m", "high_water_eligible", "forecast_inputs_available", "lag_n_minus_2_cycle_id", "lag_n_minus_4_cycle_id", "lag_n_minus_6_cycle_id"]].rename(columns={"cycle_number_label": "cycle_number"}).to_parquet(args.output_dir / "paired_high_water_forecasts.parquet", index=False)
    pd.DataFrame(rows).to_csv(args.output_dir / "high_water_metrics.csv", index=False)
    print(pd.DataFrame(rows).to_string(index=False))
    print(f"common_eligible_cycles={len(paired)}; cycle_id_sha256={cycle_hash}")


if __name__ == "__main__":
    main()
