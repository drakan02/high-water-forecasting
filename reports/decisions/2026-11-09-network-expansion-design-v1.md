# 44-station network expansion design v1

**Locked before model fitting:** 2026-11-09
**Branch:** `phase/network-expansion-2010`
**Parent:** accepted P11 commit `45310f46ceb3564470b5ea43413b6bae4ac47db2`

## Source mapping and scope

- Query the complete public GESLA S3 `parquet_files/` listing (5,119 objects). It returned 46 GBR BODC-lineage Parquet objects; all 46 (291,688,461 bytes total) were downloaded sequentially with recorded file size and SHA-256 to ignored `data/raw/gesla_s3/`.
- File identity, station name, country, coordinates, full timestamp span, unique timestamps, cadence, 2006–2010 timestamp counts and minute-00 `qc=1/use=1` counts are read from each actual Parquet. `reports/network_2010/gesla_bodc_station_inventory.csv` maps all 44 Hibbert Table 2 stations exactly once. Felixstowe is an extra non-paper station. Moray Firth is extra and ends in 2004.
- Paper port 44 is listed as Plymouth. NTSLF's official network page labels it Plymouth (Devonport); BODC's Devonport history/report names the same tide-gauge station and location, so the `devonport-dev-gbr-bodc` source is the supported match. Liverpool is matched to its Gladstone Dock object, Jersey to St Helier, and Port Erin/Port Ellen to their exact BODC-lineage objects.
- GESLA objects preserve unit metres and QC/use flags, but do not encode exact GESLA release, original BODC channel or datum. No vertical conversion, QC relaxation, channel joining or interpolation is allowed. Raw objects remain local and uncommitted.

## Registered analysis

For every one of the 44 paper ports, run UTide 0.4.0 OLS as a gauge-only harmonic substitute, fit from `max(1990-01-01, actual source first timestamp)` through 2009-12-31, using all exact-minute-00 finite/non-fill observations with GESLA `qc_flag=1` and `use_flag=1`. Use automatic constituents, Greenwich phase, trend and nodal corrections. Reconstruct hourly peaks with prior context from 2006 (or the later source start) through 2011 and score 2010. Record actual valid fit hours and all excluded rows.

For the 42 locations where the paper applies ECM, fit OLS using eligible 2006–2009 peak errors (use the available subset where a source starts later), forecast 2010 with a 24-hour issue lead and N−2/N−4/N−6 lag IDs. Also produce an explicitly retrospective 2006–2009 score using the coefficients fit on that same interval, to describe the paper's validation-period comparison; do not call that score out-of-sample. Compare UTide and ECM on the identical eligible, forecastable peak IDs. Target is total observed H; no surge is inferred, so these scores are gauge-only and cannot be compared directly with paper Table 2.

Keep Bournemouth (port 41) and Port Ellen (port 22) in inventory and harmonic outputs, and record ECM `not_applicable_per_paper` because Hibbert reports multiple highs/lows each day there. Do not drop a site because of poor QC coverage or poor scores. If a site's required model cannot be fit due to its actual source values, retain the source/site and report the exact blocker and outputs.

## Resource limits and acceptance

Fit stations sequentially in separate guarded processes, one BLAS thread, 3 GiB maximum process-tree RSS, 2.44 GiB minimum available-memory floor and a 60-minute per-station watchdog. No concurrent station fits. Preserve each station's generated config, logs, harmonic state, peaks, ECM model/forecasts/exclusions and hashes. Full project test suite, prior P0–P11 source/output checks, schema/hash/row-count verification, matrix counts and main SHA check are required before commit.
