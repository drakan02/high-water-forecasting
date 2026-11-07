# Report page specification

1. **Station and data quality** — map from `DimStation`; coverage cards and a month/day-by-hour heatmap from `FactQuality` (`timestamp_present`, `hourly_valid`, `qc_reason`). Make the 2007-only quality scope visible.
2. **Hourly tide and peak drill-through** — `FactQuality` line chart for observed hourly H and UTide A (m), plus a residual panel. Drill through by `cycle_id` to its two separate H/A peak values and source QC fields. Do not interpolate missing H.
3. **Residual spectrum and peak errors** — Welch PSD from `FactSpectrum`, frequency in cycles/hour and PSD in m²/(cycles/hour), plus paired error distribution from `FactForecast` in cm. Display design, sampling rate, Hann window, 336-hour segment and 168-hour overlap from the spectrum fact.
4. **Forecast score and explanation** — baseline/ECM paired MAE and RMSE, distinct paired peak count, common sample ID, error by cycle, and a detail table with forecast origin, all three lag residuals, coefficients/correction, prediction, observation and exclusion reason. Filter to one station, run/design, split and target type. Plot forecasts only at high-water events; no continuous hourly ECM line.

Every page must show a visible gauge-only label and an annotation that surge is unavailable, datum/channel are unresolved, and results are not a direct Table 1b replication.
