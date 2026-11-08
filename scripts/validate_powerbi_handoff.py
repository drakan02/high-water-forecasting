"""Check Power BI exports against P5 scored outputs for three required slices."""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BI = ROOT / "data/bi_handoff"
P5 = ROOT / "data/clean/p5_gauge_only_evaluation"


def _metric_rows(rows: pd.DataFrame, slice_name: str) -> list[dict[str, object]]:
    output = []
    for (design, split, model), group in rows.groupby(["design_id", "split", "model_key"]):
        errors = group.error_cm.astype(float)
        output.append({
            "slice": slice_name, "design_id": design, "split": split, "model_key": model,
            "paired_cycle_count": group.cycle_id.nunique(), "fact_rows": len(group),
            "MAE_cm": errors.abs().mean(), "RMSE_cm": np.sqrt(np.square(errors).mean()),
        })
    return output


def validate(bi_root: Path = BI, p5_root: Path = P5) -> pd.DataFrame:
    forecast = pd.read_parquet(bi_root / "FactForecast.parquet")
    assert forecast.fact_forecast_key.is_unique
    assert pd.read_parquet(bi_root / "DimStation.parquet").station_key.is_unique
    assert pd.read_parquet(bi_root / "DimDate.parquet").date_key.is_unique
    assert pd.read_parquet(bi_root / "DimModel.parquet").model_key.is_unique
    assert pd.read_parquet(bi_root / "DimRun.parquet").run_key.is_unique
    assert forecast.station_key.eq("avonmouth").all()
    assert forecast.design_id.isin(pd.read_parquet(bi_root / "DimRun.parquet").run_key).all()
    assert forecast.model_key.isin(pd.read_parquet(bi_root / "DimModel.parquet").model_key).all()
    assert forecast.surge_m.isna().all()

    paired = forecast[forecast.paired_eligible & forecast.error_cm.notna()]
    counts = paired.groupby(["design_id", "split", "cycle_id"]).model_key.nunique()
    assert counts.eq(2).all(), "Every eligible cycle must have both model rows"
    sample_counts = paired.groupby(["design_id", "split"]).paired_sample_id.nunique()
    assert sample_counts.eq(1).all()

    actual = _metric_rows(paired, "all_paired")
    january = paired[
        (paired.design_id == "chronological_fit_through_2004")
        & (paired.split == "test_2007")
        & (pd.to_datetime(paired.target_time_utc, utc=True).dt.month == 1)
    ]
    actual.extend(_metric_rows(january, "chronological_test_2007_january"))
    cycle_id = january.cycle_id.iloc[0]
    actual.extend(_metric_rows(january[january.cycle_id == cycle_id], f"single_cycle_{cycle_id}"))
    actual_frame = pd.DataFrame(actual).sort_values(["slice", "design_id", "split", "model_key"]).reset_index(drop=True)
    expected = pd.read_parquet(bi_root / "expected_slice_metrics.parquet").sort_values(
        ["slice", "design_id", "split", "model_key"]
    ).reset_index(drop=True)
    assert actual_frame[["slice", "design_id", "split", "model_key", "paired_cycle_count", "fact_rows"]].equals(
        expected[["slice", "design_id", "split", "model_key", "paired_cycle_count", "fact_rows"]]
    )
    for metric in ("MAE_cm", "RMSE_cm"):
        assert np.allclose(actual_frame[metric], expected[metric], rtol=0, atol=1e-10)

    p5_metrics = pd.read_csv(p5_root / "paired_metrics.csv")
    for _, row in p5_metrics.iterrows():
        model_key = "harmonic_baseline" if row.model == "harmonic_baseline" else "gauge_only_ecm"
        detail = paired[(paired.design_id == row.design_id) & (paired.split == row.split) & (paired.model_key == model_key)]
        assert detail.cycle_id.nunique() == row.paired_n
        assert np.isclose(detail.error_cm.abs().mean(), row.MAE_cm, atol=1e-10)
        assert np.isclose(np.sqrt(np.square(detail.error_cm).mean()), row.RMSE_cm, atol=1e-10)
    return actual_frame


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bi-root", type=Path, default=BI)
    parser.add_argument("--p5-root", type=Path, default=P5)
    parser.add_argument("--report-path", type=Path, default=ROOT / "reports/powerbi/validation_results.csv")
    args = parser.parse_args()
    results = validate(args.bi_root, args.p5_root)
    path = args.report_path
    path.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(path, index=False)
    print(results.to_string(index=False))
    print(f"Validated all-paired, January 2007, and single-cycle slices; wrote {path.relative_to(ROOT)}")
