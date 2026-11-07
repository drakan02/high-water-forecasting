# Power BI handoff — Avonmouth gauge-only pilot

## Refresh

The portable model tables are generated under `data/bi_handoff/` in CSV and Parquet. CSV is the Power BI import path. In Power Query, create a text parameter named `pDataFolder` pointing to the absolute `data/bi_handoff` folder, then use the helper in `PowerQuery.m` for each table. Refresh command:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/build_powerbi_handoff.py
```

Do not add raw data or credentials to the report. The `DimStation` metadata deliberately leaves source channel unresolved and datum unknown. `surge_m` is blank; no H−A surrogate is present.

## Model relationships

Create the one-way, one-to-many relationships listed in `relationships.csv`. Dimension tables filter facts. Keep `DimRun` and `DimModel` slicers single-select. The date relationship is from target date to `FactForecast` and event/hour date to `FactQuality`; keep it inactive or use a separate date role when mixing the two facts on one visual.

`FactForecast` is long form: one row per design/cycle/model. Each model row carries the same `paired_eligible` value from the P5 common sample. The KPI measures in `measures.dax` use this flag and `DISTINCTCOUNT(cycle_id)`, so two model rows do not double the peak count. Compare models only within the same `design_id`, split, station, target type and date filter. Do not average monthly RMSE to make an annual RMSE.

## Validation slices

`data/bi_handoff/expected_slice_metrics.csv` contains Python-computed MAE/RMSE and distinct paired-cycle counts for each run/model, January 2007 chronological test, and a single paired cycle. These form the expected values for all-pilot, one-month and one-peak refresh checks. Rebuild and compare against the P5 source scoring table after changing any query or measure.

## Pages

See `visual_catalog.md` for the four requested report pages. The ECM is a high-water prediction only; never draw it as a continuous hourly forecast line.

## UI status

**UI_PENDING.** The data model, measures, parameterized query template, validation values, and visual specification are prepared. Power BI Desktop is unavailable in this Linux environment, so PBIX open/refresh and interactive slicer evidence have not been produced.
