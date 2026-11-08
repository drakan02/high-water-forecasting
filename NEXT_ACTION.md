# Next actions

The project implementation is complete through P13 on separate phase branches. P13 provides a self-contained offline network dashboard and Power BI import tables for the 44-port P12 matrix. See `reports/acceptance/P12.md` and `reports/acceptance/P13.md`.

## UI evidence still pending

Power BI Desktop refresh, PBIX rendering, and interactive slicer evidence remain `UI_PENDING` because Power BI Desktop is unavailable on Linux. The data tables, schema, measures, dashboard, and Python-based validation are complete. Open `dashboard/index.html` for the offline dashboard; regenerate it with `PYTHONPATH=src .venv/bin/python scripts/build_network_dashboard.py`.

## Direct paper result still blocked by source availability

P8's conclusion remains unchanged: direct Avonmouth Table 1(b) reproduction is not validated without the matching original BODC channel/datum and a verified 2007 residual-surge source and spatial mapping. No NOC email was sent and no surge was inferred from H−A. If those public files become available, record their lineage and terms first, then create a new versioned design/phase before fitting.

All reported network/ANN/Newlyn/Newport results use public GESLA/BODC-lineage gauge records and are explicitly gauge-only substitutes. They do not claim exact EHM, SHOM MAS, paper ANN, or surge-corrected Table 1/2 reproduction.
