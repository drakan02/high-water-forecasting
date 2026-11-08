# Network dashboard design v1

**Date:** 2026-11-09
**Branch:** `phase/powerbi-network`
**Parent:** `911fcee77a626b0f82b0fcdbdc4530b69679b6c6`

## Purpose and input contract

Build a local offline dashboard and Power BI import model from accepted P12 artifacts. The input is the 44-port QC/source inventory, 176-row model × port × period × target metric table, 119,220 paired peak-level rows, and local per-port ECM forecast files for lag trace detail. The dashboard must identify missing source datum/channel metadata, preserve all paper ports, retain the paper-specified ECM exclusions, and label retrospective 2006–2009 results in-sample.

## Interactions

- Filters: port, evaluation period, and display mode (paired, UTide, ECM).
- Network overview: 2010 exact-hour QC coverage by port and MAE by port.
- Peak events: observed H, UTide A, ECM total-H, issue origin, cycle ID, and N−2/N−4/N−6 residuals.
- Matrix: status, paired count, MAE/RMSE, and comparison scope for every model × port × period combination.
- Target label is fixed to `total_observed_water_level_gauge_only`; the interface must not imply surge or direct Hibbert Table 2 equivalence.

## Delivery and validation

Keep the local dashboard self-contained, with no external scripts, fonts, or API calls. Compress the embedded JSON payload for practical file size. Export Power BI dimension/fact CSVs under an ignored local folder, with a tracked table dictionary, relationships, DAX measures, and input/output manifest. Compare dashboard pooled values, Power BI tables, IDs, and row counts to P12. Power BI Desktop refresh/render remains `UI_PENDING` in the Linux environment. Do not publish or push.
