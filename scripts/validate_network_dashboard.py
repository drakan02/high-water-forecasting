"""Validate the offline network dashboard payload and Power BI tables against P12."""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path
import re

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dashboard", type=Path, default=Path("dashboard/index.html"))
    args = parser.parse_args()
    dashboard = ROOT / args.dashboard
    manifest_path = dashboard.with_name("manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if sha256(dashboard) != manifest["dashboard_sha256"]:
        raise AssertionError("Dashboard SHA-256 differs from manifest")
    for source, expected in manifest["sources"].items():
        if sha256(ROOT / source) != expected:
            raise AssertionError(f"Dashboard source checksum mismatch: {source}")
    html = dashboard.read_text(encoding="utf-8")
    if re.search(r'<script\s+src=|<link[^>]+href=["\']https?://', html, re.IGNORECASE):
        raise AssertionError("Dashboard must not depend on external scripts or stylesheets")
    match = re.search(r'<script id="payload" type="application/octet-stream">([^<]+)</script>', html)
    if not match:
        raise AssertionError("Missing compressed embedded payload")
    payload = json.loads(gzip.decompress(base64.b64decode(match.group(1))).decode("utf-8"))
    assert len(payload["stations"]) == 44
    assert len(payload["metrics"]) == 176
    assert len(payload["forecasts"]) == 119220
    assert payload["target"] == "total_observed_water_level_gauge_only"
    assert manifest["external_assets"] == 0
    assert manifest["forecast_rows_missing_lag_trace"] == 0

    pbi_root = ROOT / "data" / "bi_handoff_network"
    pbi_manifest = json.loads((pbi_root / "manifest.json").read_text(encoding="utf-8"))
    for name, item in pbi_manifest["tables"].items():
        if sha256(pbi_root / name) != item["sha256"]:
            raise AssertionError(f"Power BI table checksum mismatch: {name}")
    forecast_csv = pd.read_csv(pbi_root / "FactPeakForecast.csv")
    metrics_csv = pd.read_csv(pbi_root / "FactPeakMetrics.csv")
    assert len(forecast_csv) == 232932 and len(metrics_csv) == 176
    assert not forecast_csv.duplicated(["station_id", "period", "cycle_id", "model"]).any()
    assert set(forecast_csv.target.unique()) == {payload["target"]}
    assert forecast_csv.loc[forecast_csv.paired_sample, "cycle_id"].notna().all()

    records = payload["forecasts"]
    pooled = {}
    for period_index, period in enumerate(payload["periods"]):
        rows = [r for r in records if r[1] == period_index and r[7] is not None]
        actual = np.asarray([r[5] for r in rows], dtype=float)
        baseline = np.asarray([r[6] for r in rows], dtype=float)
        ecm = np.asarray([r[7] for r in rows], dtype=float)
        if not rows:
            raise AssertionError(f"No paired forecast rows for {period}")
        pooled[period] = {
            "n": len(rows),
            "UTide_MAE_cm": float(np.abs(baseline - actual).mean() * 100),
            "UTide_RMSE_cm": float(np.sqrt(np.square(baseline - actual).mean()) * 100),
            "ECM_MAE_cm": float(np.abs(ecm - actual).mean() * 100),
            "ECM_RMSE_cm": float(np.sqrt(np.square(ecm - actual).mean()) * 100),
        }
    expected = {
        "heldout_2010": (22267, 12.70690644218559, 16.930379087705187, 9.711735808955016, 13.156395541851316),
        "retrospective_2006_2009": (91445, 14.148087790966887, 18.90835102145086, 11.010919658004317, 15.398405136341248),
    }
    for period, values in expected.items():
        got = pooled[period]
        assert got["n"] == values[0]
        for key, expected_value in zip(("UTide_MAE_cm", "UTide_RMSE_cm", "ECM_MAE_cm", "ECM_RMSE_cm"), values[1:]):
            assert abs(got[key] - expected_value) < 1e-8, (period, key, got[key], expected_value)
    result = {"status": "PASS", "dashboard_sha256": manifest["dashboard_sha256"], "dashboard_bytes": dashboard.stat().st_size, "station_count": 44, "metric_rows": 176, "dashboard_peak_rows": 119220, "powerbi_long_peak_rows": 232932, "paired_metrics_reproduced": pooled}
    out = ROOT / "reports" / "powerbi" / "network" / "validation_results.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
