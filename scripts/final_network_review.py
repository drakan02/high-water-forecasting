"""Audit P12 paired 2010 forecasts and export per-port results and figures."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "reports/network_2010/network_forecasts_paired.parquet"
TARGET = "total_observed_water_level_gauge_only"
PERIOD = "heldout_2010"


def run(source: Path = SOURCE, outdir: Path = ROOT / "reports/final_network_review") -> dict:
    outdir.mkdir(parents=True, exist_ok=True)
    df = pd.read_parquet(source)
    required = {
        "cycle_id", "H_peak_m", "A_peak_m", "P_ecm_m", "forecast_origin_utc",
        "forecast_target_time_utc", "paper_station", "station_id", "period", "target",
    }
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing forecast columns: {sorted(missing)}")
    df = df.loc[(df["period"] == PERIOD) & (df["target"] == TARGET)].copy()
    if df.duplicated(["station_id", "cycle_id"]).any():
        raise AssertionError("Duplicate station/cycle forecast key in selected transfer run")
    # The paired P12 table carries one row per candidate cycle and both model predictions.
    valid = df[["H_peak_m", "A_peak_m", "P_ecm_m"]].notna().all(axis=1)
    pair = df.loc[valid].copy()
    if pair["forecast_origin_utc"].isna().any() or pair["forecast_target_time_utc"].isna().any():
        raise AssertionError("A scored pair lacks forecast origin or target time")
    if pair["target"].nunique() != 1 or pair["target"].iloc[0] != TARGET:
        raise AssertionError("Target is not the registered gauge-only total water level")
    if pair["period"].nunique() != 1 or pair["period"].iloc[0] != PERIOD:
        raise AssertionError("Selected rows include another evaluation period")

    pair["utide_error_cm"] = (pair["H_peak_m"] - pair["A_peak_m"]) * 100.0
    pair["ecm_error_cm"] = (pair["H_peak_m"] - pair["P_ecm_m"]) * 100.0
    pair["event_gain_mae_cm"] = pair["utide_error_cm"].abs() - pair["ecm_error_cm"].abs()
    rows = []
    for (station_id, station_name), g in pair.groupby(["station_id", "paper_station"], sort=True):
        u = g["utide_error_cm"].to_numpy(dtype=np.float64)
        e = g["ecm_error_cm"].to_numpy(dtype=np.float64)
        mae_u, mae_e = float(np.mean(np.abs(u))), float(np.mean(np.abs(e)))
        rmse_u = float(np.sqrt(np.mean(np.square(u))))
        rmse_e = float(np.sqrt(np.mean(np.square(e))))
        gain = mae_u - mae_e
        rows.append({
            "station_id": station_id,
            "station_name": station_name,
            "n_pairs": int(len(g)),
            "mae_utide_cm": mae_u,
            "mae_ecm_cm": mae_e,
            "gain_mae_cm": gain,
            "gain_mae_pct": 100.0 * gain / mae_u if mae_u != 0.0 else np.nan,
            "rmse_utide_cm": rmse_u,
            "rmse_ecm_cm": rmse_e,
            "gain_rmse_cm": rmse_u - rmse_e,
            "mae_result": "improved" if gain > 0.0 else ("worse" if gain < 0.0 else "equal"),
        })
    metrics = pd.DataFrame(rows)
    if len(metrics) != 42 or int(metrics.n_pairs.sum()) != 22267:
        raise AssertionError(f"Expected 42 ports and 22267 pairs, got {len(metrics)} / {metrics.n_pairs.sum()}")
    if pair["cycle_id"].duplicated().any():
        # P12 cycle IDs are station-prefixed; this also guards cross-port collisions.
        raise AssertionError("Cycle IDs unexpectedly collide across ports")

    # Independently verify paired rows against the tracked P12 per-port metric table.
    prior = pd.read_csv(ROOT / "reports/network_2010/network_metrics_paired.csv")
    prior = prior.loc[(prior.period == PERIOD) & (prior.target == TARGET)]
    prior = prior.loc[prior.model.isin(["UTide-0.4.0", "ECM-OLS-3lag"])]
    prior = prior.loc[prior.n_scored_paired > 0]
    observed = {}
    for model, prediction in (("UTide-0.4.0", "A_peak_m"), ("ECM-OLS-3lag", "P_ecm_m")):
        col = "utide" if model.startswith("UTide") else "ecm"
        obs = pair.assign(abs_err=(pair.H_peak_m - pair[prediction]).abs())
        observed[col] = obs.abs_err.agg(["mean", "count"])
    for key, model in (("utide", "UTide-0.4.0"), ("ecm", "ECM-OLS-3lag")):
        expected_rows = prior.loc[prior.model == model]
        if len(expected_rows) != 42:
            raise AssertionError(f"Expected 42 prior metric rows for {model}, got {len(expected_rows)}")
        expected_n = int(expected_rows.n_scored_paired.sum())
        expected_mae = float(np.average(expected_rows.MAE_m, weights=expected_rows.n_scored_paired) * 100)
        got_mae = float(observed[key]["mean"] * 100)
        if expected_n != len(pair) or abs(expected_mae - got_mae) > 1e-8:
            raise AssertionError(f"P12 metric reconciliation failed for {model}: {got_mae} vs {expected_mae}")

    # Direct pooled metrics; do not average the station-level RMSEs.
    ue = pair.utide_error_cm.to_numpy(float)
    ee = pair.ecm_error_cm.to_numpy(float)
    pooled = {
        "n_pairs": int(len(pair)),
        "utide_mae_cm": float(np.mean(np.abs(ue))),
        "ecm_mae_cm": float(np.mean(np.abs(ee))),
        "utide_rmse_cm": float(np.sqrt(np.mean(ue**2))),
        "ecm_rmse_cm": float(np.sqrt(np.mean(ee**2))),
    }
    pooled["gain_mae_cm"] = pooled["utide_mae_cm"] - pooled["ecm_mae_cm"]
    pooled["gain_rmse_cm"] = pooled["utide_rmse_cm"] - pooled["ecm_rmse_cm"]
    if not np.allclose(
        [pooled["utide_mae_cm"], pooled["ecm_mae_cm"], pooled["utide_rmse_cm"], pooled["ecm_rmse_cm"]],
        [12.70690644218559, 9.711735808955016, 16.930379087705187, 13.156395541851316],
        atol=1e-8, rtol=0,
    ):
        raise AssertionError(f"Pooled results differ from P13 validator anchors: {pooled}")

    counts = metrics.mae_result.value_counts().to_dict()
    if sum(counts.values()) != 42:
        raise AssertionError(f"MAE port categories do not sum to 42: {counts}")
    event_counts = {
        "improved": int((pair.event_gain_mae_cm > 0).sum()),
        "equal": int((pair.event_gain_mae_cm == 0).sum()),
        "worse": int((pair.event_gain_mae_cm < 0).sum()),
    }
    summary = {
        "scope": "P12 heldout_2010 transfer; gauge-only total observed water level",
        "source": str(source.relative_to(ROOT)),
        "target": TARGET,
        "period": PERIOD,
        "unit": "cm for errors and gains; source predictions stored in metres",
        "pair_key": ["station_id", "cycle_id"],
        "pair_checks": {
            "selected_candidate_rows": int(len(df)),
            "valid_paired_rows": int(len(pair)),
            "duplicate_station_cycle_keys": 0,
            "same_H_A_ECM_target_and_issue_origin": True,
            "not_applicable_ports": ["p22_port_ellen", "p41_bournemouth"],
            "not_applicable_reason": "Paper excludes ECM at locations with multiple high/low waters per day",
        },
        "ports_scored": int(len(metrics)),
        "port_mae_categories": {k: int(counts.get(k, 0)) for k in ("improved", "equal", "worse")},
        "port_improvement_pct": 100.0 * counts.get("improved", 0) / len(metrics),
        "median_station_gain_mae_cm": float(metrics.gain_mae_cm.median()),
        "event_pair_abs_error_categories": event_counts,
        "event_pair_improvement_pct": 100.0 * event_counts["improved"] / len(pair),
        "pooled_pair_metrics": pooled,
        "classification": "strict comparison of unrounded float64 gain_mae_cm; no tie tolerance",
        "input_p12_paired_metric_sha256": "3a0ff3932607cc2f1f80838eb8f71b8e9c3ed5d9901274fed829725cdc5162b7",
        "input_p12_forecast_parquet_sha256": "01126f1852eaf3961d6d4ce9adb6cdfb5fb41e6f71e8f0ee10b5db8f8a21ba1d",
    }
    metrics = metrics.sort_values("gain_mae_cm", ascending=False, kind="mergesort")
    metrics.to_csv(outdir / "station_metrics_2010.csv", index=False, float_format="%.15g")
    (outdir / "network_summary_2010.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    # Full detail for reproducible per-event diagnostics.
    pair.to_csv(outdir / "paired_event_gains_2010.csv", index=False, float_format="%.15g")
    fig, ax = plt.subplots(figsize=(12, 15), constrained_layout=True)
    colors = ["#238b45" if x > 0 else "#cb181d" if x < 0 else "#636363" for x in metrics.gain_mae_cm]
    ax.barh(metrics.station_name, metrics.gain_mae_cm, color=colors, edgecolor="white", linewidth=0.4)
    ax.axvline(0, color="#222222", linewidth=1.1)
    ax.invert_yaxis()
    ax.set_xlabel("MAE giảm do ECM so với UTide (cm) — dương nghĩa là ECM tốt hơn")
    ax.set_ylabel("Cảng")
    ax.set_title("ECM theo từng cảng — held-out năm 2010\nGauge-only: target là tổng mực nước H; 42 cảng có cặp hợp lệ")
    ax.grid(axis="x", linestyle=":", alpha=0.35)
    ax.tick_params(axis="y", labelsize=8)
    fig.savefig(outdir / "ecm_mae_gain_by_port_2010.png", dpi=220, bbox_inches="tight")
    plt.close(fig)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--outdir", type=Path, default=ROOT / "reports/final_network_review")
    args = parser.parse_args()
    print(json.dumps(run(args.source, args.outdir), indent=2))
