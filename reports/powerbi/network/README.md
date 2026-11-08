# Power BI handoff — 44-port network

Run `PYTHONPATH=src .venv/bin/python scripts/build_network_dashboard.py` after P12 outputs exist. The command rebuilds `dashboard/index.html` and writes CSV imports under the ignored `data/bi_handoff_network/` folder:

- `DimStation.csv`: 44 paper ports with coordinates, source period, QC coverage, fit count, datum/channel caveats, and candidate/eligible cycle counts.
- `DimPeriod.csv`: retrospective 2006–2009 (in-sample) and held-out 2010.
- `DimModel.csv`: UTide 0.4.0 and ECM OLS 3-lag; both target total observed H.
- `FactPeakMetrics.csv`: one row per model × port × period, including status, paired count, paired hash, MAE/RMSE and scope.
- `FactPeakForecast.csv`: long form, one model row per event cycle; ECM rows include forecast origin and all three lag residuals. `paired_sample` is true only when the cycle has an issued ECM prediction and QC-valid H.
- `manifest.json`: input/output hashes and row counts.

Create one-to-many, single-direction relationships from `DimStation[station_id]`, `DimPeriod[period]`, and `DimModel[model]` to both fact tables. Use `FactPeakForecast` for recalculating metrics; do not average the aggregated RMSE rows. The target dimension is intentionally a single explicit label, `total_observed_water_level_gauge_only`.

The data model and import tables are prepared. **UI_PENDING:** Power BI Desktop is unavailable on Linux, so PBIX refresh, visual rendering, and interactive slicer evidence have not been checked. Keep P8's Table 1(b) conclusion unchanged.
