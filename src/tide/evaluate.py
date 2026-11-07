"""Paired peak scoring and guarded paper-versus-gauge-only comparisons."""
from __future__ import annotations

from pathlib import Path
import hashlib
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

PUBLISHED = {
    ("Avonmouth", "2007", "Table 1b"): {"baseline": {"MAE_cm": 16.30, "RMSE_cm": 19.55}, "ECM": {"MAE_cm": 9.05, "RMSE_cm": 11.59}},
    ("Avonmouth", "2006-2009", "Table 2"): {"baseline": {"MAE_cm": 14.37, "RMSE_cm": 17.80}, "ECM": {"MAE_cm": 8.94, "RMSE_cm": 11.61}},
    ("Newport", "2006-2009", "Table 2"): {"baseline": {"MAE_cm": 15.83, "RMSE_cm": 19.26}, "ECM": {"MAE_cm": 9.71, "RMSE_cm": 12.89}},
}


def _metric_values(error_cm: pd.Series | np.ndarray) -> dict[str, float | int]:
    values = np.asarray(error_cm, dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return {"paired_n": 0, "MAE_cm": np.nan, "RMSE_cm": np.nan, "bias_cm": np.nan}
    return {
        "paired_n": int(values.size),
        "MAE_cm": float(np.mean(np.abs(values))),
        "RMSE_cm": float(np.sqrt(np.mean(np.square(values)))),
        "bias_cm": float(np.mean(values)),
    }


def score_joined_cycles(forecasts: pd.DataFrame, labels: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Join target labels after forecasts, then score only a single common eligible set."""
    if forecasts["cycle_id"].duplicated().any() or labels["cycle_id"].duplicated().any():
        raise ValueError("Forecast and target tables must be unique by cycle_id within a split")
    target_columns = ["cycle_id", "H_peak_m", "H_peak_time_utc", "high_water_eligible", "exclusion_reason"]
    joined = forecasts.merge(labels[target_columns], on="cycle_id", how="left", validate="one_to_one", indicator=True)
    joined["target_present"] = joined["_merge"].eq("both")
    joined = joined.drop(columns="_merge")
    joined["paired_eligible"] = (
        joined["forecast_inputs_available"].fillna(False).astype(bool)
        & joined["target_present"]
        & joined["high_water_eligible"].fillna(False).astype(bool)
        & joined["P_base_m"].notna()
        & joined["P_ecm_m"].notna()
    )
    joined["error_base_cm"] = ((joined["H_peak_m"] - joined["P_base_m"]) * 100).where(joined["paired_eligible"])
    joined["error_ecm_cm"] = ((joined["H_peak_m"] - joined["P_ecm_m"]) * 100).where(joined["paired_eligible"])
    joined["paired_sample_id"] = ""
    for split, group in joined.groupby("split", sort=True):
        ids = group.loc[group["paired_eligible"], "cycle_id"].astype(str)
        sample_id = hashlib.sha256("\n".join(sorted(ids)).encode()).hexdigest()
        joined.loc[group.index, "paired_sample_id"] = sample_id

    metrics: list[dict[str, object]] = []
    gains: list[dict[str, object]] = []
    for split, group in joined.groupby("split", sort=True):
        common = group.loc[group["paired_eligible"]]
        for model, column in (("harmonic_baseline", "error_base_cm"), ("gauge_only_ecm", "error_ecm_cm")):
            metrics.append({"design_id": group["design_id"].iloc[0], "split": split, "model": model, **_metric_values(common[column])})
        base = _metric_values(common["error_base_cm"])
        ecm = _metric_values(common["error_ecm_cm"])
        gain = base["MAE_cm"] - ecm["MAE_cm"] if common.shape[0] else np.nan
        gains.append({
            "design_id": group["design_id"].iloc[0], "split": split,
            "paired_n": int(len(common)), "paired_sample_id": str(group["paired_sample_id"].iloc[0]),
            "MAE_gain_cm": gain,
            "MAE_gain_pct": float(100 * gain / base["MAE_cm"]) if np.isfinite(gain) and base["MAE_cm"] else np.nan,
            "RMSE_gain_cm": base["RMSE_cm"] - ecm["RMSE_cm"] if common.shape[0] else np.nan,
        })
    metrics_frame = pd.DataFrame(metrics)
    gains_frame = pd.DataFrame(gains)

    joined["target_month_utc"] = pd.to_datetime(joined["H_peak_time_utc"], utc=True).dt.month
    monthly: list[dict[str, object]] = []
    for (split, month), group in joined.groupby(["split", "target_month_utc"], dropna=True, sort=True):
        common = group.loc[group["paired_eligible"]]
        for model, column in (("harmonic_baseline", "error_base_cm"), ("gauge_only_ecm", "error_ecm_cm")):
            monthly.append({
                "design_id": group["design_id"].iloc[0], "split": split, "month_utc": int(month),
                "model": model, **_metric_values(common[column]),
            })
    return joined, metrics_frame, gains_frame, pd.DataFrame(monthly)


def paper_comparison(metrics: pd.DataFrame) -> pd.DataFrame:
    """Keep gauge-only values visible but never calculate incomparable paper deltas."""
    rows = []
    lookup = metrics.set_index(["design_id", "split", "model"])
    for (station, period, table), published in PUBLISHED.items():
        relevant = []
        if station == "Avonmouth" and period == "2007":
            relevant = [
                ("chronological_fit_through_2004", "test_2007"),
                ("retrospective_1988_2007", "retrospective_in_sample_2007"),
            ]
        for published_model, model_name in (("baseline", "harmonic_baseline"), ("ECM", "gauge_only_ecm")):
            for metric_name in ("MAE_cm", "RMSE_cm"):
                group_values = []
                for design_id, split in relevant:
                    key = (design_id, split, model_name)
                    value = lookup.loc[key, metric_name] if key in lookup.index else np.nan
                    n = int(lookup.loc[key, "paired_n"]) if key in lookup.index else 0
                    group_values.append((design_id, split, value, n))
                if group_values:
                    for design_id, split, value, n in group_values:
                        rows.append({
                            "station": station, "period": period, "paper_table": table,
                            "model": published_model, "metric": metric_name,
                            "published_value": published[published_model][metric_name],
                            "gauge_only_value": value,
                            "delta_vs_paper": np.nan,
                            "design_id": design_id, "split": split, "paired_n": n,
                            "comparability": "not_comparable_gauge_only_total_H_vs_paper_H_minus_surge; original channel/datum and EHM unresolved; surge absent",
                        })
                else:
                    rows.append({
                        "station": station, "period": period, "paper_table": table,
                        "model": published_model, "metric": metric_name,
                        "published_value": published[published_model][metric_name],
                        "gauge_only_value": np.nan, "delta_vs_paper": np.nan,
                        "design_id": "", "split": "NOT_RUN", "paired_n": 0,
                        "comparability": "not_comparable; matching surge and/or required time period/station data unavailable",
                    })
    return pd.DataFrame(rows)


def run_evaluation(config_path: Path) -> dict[str, object]:
    config = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    output_root = Path(config["output_dir"])
    output_root.mkdir(parents=True, exist_ok=True)
    scored_parts = []
    summaries = []
    monthly_parts = []
    all_metrics = []
    all_gains = []
    for design_cfg in config["designs"]:
        design_id = design_cfg["design_id"]
        forecast_path = Path(design_cfg["forecast_path"])
        labels_path = Path(design_cfg["labels_path"])
        forecast = pd.read_parquet(forecast_path)
        labels = pd.read_parquet(labels_path)
        labels["H_peak_time_utc"] = pd.to_datetime(labels["H_peak_time_utc"], utc=True)
        joined, metrics, gains, monthly = score_joined_cycles(forecast, labels)
        joined["design_id"] = design_id
        metrics["design_id"] = design_id
        gains["design_id"] = design_id
        monthly["design_id"] = design_id
        scored_parts.append(joined)
        all_metrics.append(metrics)
        all_gains.append(gains)
        monthly_parts.append(monthly)
        out_dir = output_root / design_id
        out_dir.mkdir(parents=True, exist_ok=True)
        scored_path = out_dir / "scored_high_water.parquet"
        scored_csv_path = out_dir / "scored_high_water.csv"
        joined.to_parquet(scored_path, index=False)
        joined.to_csv(scored_csv_path, index=False)
        eligible = joined["paired_eligible"]
        for split, split_rows in joined.groupby("split", sort=True):
            split_forecastable = int(split_rows["forecast_inputs_available"].fillna(False).sum())
            split_target_valid = int(split_rows["high_water_eligible"].fillna(False).sum())
            split_paired = int(split_rows["paired_eligible"].sum())
            summaries.append({
                "design_id": design_id,
                "split": split,
                "forecast_source_sha256": hashlib.sha256(forecast_path.read_bytes()).hexdigest(),
                "label_source_sha256": hashlib.sha256(labels_path.read_bytes()).hexdigest(),
                "candidate_forecasts": int(len(split_rows)),
                "forecast_inputs_available": split_forecastable,
                "forecast_input_coverage": split_forecastable / len(split_rows) if len(split_rows) else np.nan,
                "target_label_present": int(split_rows["target_present"].sum()),
                "target_label_eligible": split_target_valid,
                "paired_n": split_paired,
                "paired_coverage_of_candidates": split_paired / len(split_rows) if len(split_rows) else np.nan,
                "paired_sample_id": str(split_rows["paired_sample_id"].iloc[0]) if len(split_rows) else "",
                "scored_parquet": str(scored_path),
                "scored_csv": str(scored_csv_path),
            })
        errors = joined.loc[eligible]
        if len(errors):
            fig, ax = plt.subplots(figsize=(10, 5))
            ax.hist(errors["error_base_cm"], bins=30, alpha=0.55, label="UTide harmonic baseline")
            ax.hist(errors["error_ecm_cm"], bins=30, alpha=0.55, label="Gauge-only ECM")
            ax.axvline(0, color="black", linewidth=0.8)
            ax.set_xlabel("Observed H − prediction (cm)")
            ax.set_ylabel("High-water count")
            ax.set_title(f"{design_id}: paired gauge-only high-water errors; n={len(errors)}")
            ax.legend()
            ax.grid(alpha=0.15)
            fig.tight_layout()
            fig.savefig(out_dir / "paired_error_histogram.png", dpi=160)
            plt.close(fig)
    metrics_all = pd.concat(all_metrics, ignore_index=True)
    gains_all = pd.concat(all_gains, ignore_index=True)
    monthly_all = pd.concat(monthly_parts, ignore_index=True)
    comparison = paper_comparison(metrics_all)
    scored_all = pd.concat(scored_parts, ignore_index=True)
    metrics_all.to_csv(output_root / "paired_metrics.csv", index=False)
    gains_all.to_csv(output_root / "paired_gains.csv", index=False)
    monthly_all.to_csv(output_root / "monthly_metrics.csv", index=False)
    comparison.to_csv(output_root / "paper_vs_replication.csv", index=False)
    pd.DataFrame(summaries).to_csv(output_root / "coverage_summary.csv", index=False)
    transfer_2010 = [
        item for item in summaries
        if item["split"] == "test_2010" and str(item["design_id"]).startswith("avonmouth_transfer_2010")
    ]
    transfer_status = (
        f"RUN_COMPLETE; frozen-through-2009 gauge-only transfer evaluated on {transfer_2010[0]['paired_n']} paired 2010 cycles"
        if transfer_2010 else "NOT_RUN; no frozen-through-2009 transfer design registered"
    )
    summary = {
        "design_summaries": summaries,
        "comparison_path": str(output_root / "paper_vs_replication.csv"),
        "paired_metrics_path": str(output_root / "paired_metrics.csv"),
        "gains_path": str(output_root / "paired_gains.csv"),
        "monthly_metrics_path": str(output_root / "monthly_metrics.csv"),
        "coverage_path": str(output_root / "coverage_summary.csv"),
        "benchmark_delta_policy": "all delta_vs_paper values remain null for gauge_only due target/surge/baseline mismatch",
        "2010_status": transfer_status,
    }
    (output_root / "p5_evaluation_manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
