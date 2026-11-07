# High Water Forecasting

Reproducible Avonmouth pilot based on Hibbert et al. (2015). Phase branches are separate. Active branch: `phase/P1-gauge-ingestion-qc`; P0 source decision is committed and `main` remains unchanged.

## Current status

- **P0 gauge-only source decision: DONE.** A real GESLA S3 Parquet object with BODC Avonmouth lineage is verified. The object release is undeclared; its primary/secondary channel and datum remain unknown. See `reports/acceptance/P0.md` and `reports/access_decision.md`.
- **P1 gauge ingestion/QC: DONE for the available gauge-only record.** The raw object has 853,104 rows, 1961-01-01 00:00 through 2012-04-30 23:45 UTC per GESLA convention. For 2007: 35,040/35,040 expected 15-minute rows, 35,030 `qc_flag=1`/`use_flag=1`, and 10 `qc_flag=2`. The hourly grid has 8,760/8,760 minute-00 timestamps and 8,759 valid observations.
- **Direct Table 1b reproduction: BLOCKED separately.** No matching 2007 NOC CS3X residual-surge file or Avonmouth grid mapping. Do not calculate surge as `H-A`; the P1 pipeline has no surge input.

The source is not the original BODC file. Do not claim the GESLA record is a specific original BODC channel or convert its unspecified datum. The record is suitable for a labeled gauge-only experiment, not direct equivalence to paper EHM or Table 1b.

## Source and P1 artifacts

Raw file (kept byte-identical and ignored by Git): `data/raw/gesla_s3/avonmouth-avo-gbr-bodc.parquet`

SHA-256: `7a796fcb64215becd2fb429b75a48be5afcb392c613a7f54e509c36250e71bb8`

P1 outputs: `data/clean/avonmouth_2007_gesla_gauge_only/hourly.parquet`, `data/clean/avonmouth_2007_gesla_gauge_only/qc_by_station_month.csv`, `data/clean/avonmouth_2007_gesla_gauge_only/raw_manifest.csv`, and `reports/figures/avonmouth_2007_first_14_days_raw_vs_hourly.png`. The manifest stores source URL/query route, object timestamp, SHA-256, schema, site, coordinates, UTC/unit/datum/channel caveats, QC and use terms. Monthly coverage is computed from file values, not catalog coverage.

## Re-run

Run at repository root. In this workspace use writable uv and Matplotlib cache paths:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv sync --locked
UV_CACHE_DIR=/tmp/uv-cache MPLCONFIGDIR=/tmp/mpl-cache uv run python -m tide ingest --config configs/avonmouth.yaml
UV_CACHE_DIR=/tmp/uv-cache MPLCONFIGDIR=/tmp/mpl-cache uv run python -m tide prepare --config configs/avonmouth.yaml
UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q
```

`ingest` validates the configured local source and writes the raw manifest. `prepare` writes the exact-minute-00 hourly Parquet, monthly QC/coverage, manifest and first-14-days plot. The source is not automatically fetched.

## Phase gate

P1 prepares real gauge observations and preserves source QC. It is not a tide forecast or peak forecast. Continue to P2 on its own branch after the P1 acceptance checks pass. Keep P0 gauge-only provenance separate from the still-blocked paper-aligned Table 1b path.
