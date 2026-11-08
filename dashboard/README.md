# UK high-water network dashboard

Open `index.html` in a modern browser after building it to browse the P12 public-source, gauge-only evaluation. The page has no external fonts, CDN, server, or network calls; it embeds the validated P12 metric and peak-level records as gzip-compressed JSON in one offline HTML file.

From the repository root, after the P12 local outputs and report artifacts are present:

```bash
PYTHONPATH=src .venv/bin/python scripts/build_network_dashboard.py
```

Select a station, evaluation period, and model view. The page shows 2010 QC coverage, model MAE by port, event-level forecasts, and the ECM issue origin plus N−2/N−4/N−6 lag values. The metric table retains all 44 ports, the two paper-specified ECM exclusions, and low-coverage ports. `NOT_APPLICABLE_PER_PAPER` is visible for Port Ellen and Bournemouth.

The target is total observed water level H. This is not surge, and the metrics are not direct Hibbert Table 2 results. P8's direct Table 1(b) conclusion remains unchanged. The 2006–2009 retrospective period is in-sample. Forecast-origin availability assumes historical observation timestamps; provider publication latency is unknown.

`manifest.json` contains dashboard/source hashes, row counts, and missing-lag counts. The same build command also writes CSV tables for Power BI to ignored `data/bi_handoff_network/`. Power BI Desktop refresh and slicer interaction are `UI_PENDING` on this Linux environment.
