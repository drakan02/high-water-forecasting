# Next actions

P12 network expansion is accepted and committed on `phase/network-expansion-2010`. The 44 Hibbert network ports have public GESLA/BODC-lineage inputs and per-port UTide output; 42 ports also have ECM, while Port Ellen and Bournemouth retain ECM `NOT_APPLICABLE_PER_PAPER` status. See `reports/acceptance/P12.md`.

## P13: Power BI network dashboard

The next phase is a dedicated Power BI/dashboard branch from the accepted P12 commit. Extend the existing dashboard using the P12 model × port × period × target matrix and paired peak forecasts. Include station/model/period filters, source coverage and QC, common peak counts, paired MAE/RMSE, forecast origin and lag trace, and clear gauge-only target labels. Validate dashboard totals against `reports/network_2010/network_metrics_paired.csv`; mark Desktop-only refresh/slicer evidence `UI_PENDING` when Power BI Desktop is unavailable on Linux.

Keep every port and model visible regardless of coverage or skill. Preserve the two paper-specified ECM exclusions. Label 2006–2009 metrics in-sample and show per-port cycle counts because candidate interval counts vary substantially.

## Scientific limits carried forward

- P8's direct Table 1(b) conclusion remains unchanged: matched NOC CS3X residual surge, suitable GTSM grid, and original Avonmouth BODC channel/datum have not been verified.
- P12 is a gauge-only network substitute. UTide is not validated as EHM 2015, and no surge is inferred from H−A.
- BODC/GESLA original measurement channel, datum linkage and exact GESLA release remain unresolved. GESLA raw source files are local and ignored by Git.
- The dashboard must not label total observed water-level forecasts as surge predictions or direct Hibbert Table 2 reproduction.
