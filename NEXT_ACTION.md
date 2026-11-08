# Next actions

Current accepted phase: P10, Newlyn Species Concordance substitute. P8 remains the separate direct Table 1(b) input audit; its conclusion is unchanged. The accepted experiments target total observed water level H where storm-surge residual is unavailable.

## Next phase

Create the Newport and network-transfer phase from the accepted P10 commit. Before fitting, inventory public Newport and other network-station records, verify station identity, time span, cadence, QC and units from the actual files, and freeze the site/model comparison design. Keep every registered model and port in the output regardless of skill. Where only gauge data exists, label the target total H and do not infer surge from H minus a tide prediction.

After network forecasts and paired peak metrics are validated, make the Power BI handoff/dashboard phase from its own branch. Preserve the model × port × period × target matrix, peak-level paired metrics, source lineage, and replay commands.

## User-side source access

- BODC: use the official processed all-channels portal in a browser. Register/sign in there if prompted, select Avonmouth 2007 and download the original annual processed/NTSLF file unchanged to `data/raw/bodc/avonmouth/`. Do not share credentials in chat.
- Copernicus CDS: sign in/register on the CDS site, open `sis-water-level-change-timeseries-cmip6`, select GTSM 3.0 ERA5 reanalysis, storm-surge residual, hourly, 2007 January, v3, ZIP, accept the displayed terms, and submit. Save the portal-generated API request and ZIP under `data/raw/copernicus_gtsm/avonmouth_trial/`; keep any token local.

Neither a suitable GTSM point nor the required original BODC channel/datum has been validated. Do not use the UTide residual as surge. P8's direct Table 1(b) result remains pending those compatible inputs.
