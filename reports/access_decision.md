# P0 source access decision — Avonmouth

Audit date: 2026-11-08 (Asia/Ho_Chi_Minh)
Branch: `phase/P0-avonmouth-source-audit`
Target: Hibbert et al. (2015), Avonmouth 2007.

## Decision: gauge-only path selected

P0 has completed the source verification and selected a feasible **gauge_only** path. An actual public GESLA S3 Parquet object with BODC Avonmouth lineage was downloaded and inspected. The exact chosen object is `parquet_files/avonmouth-avo-gbr-bodc.parquet`; the CMEMS object was not used. GESLA/geslaR offers filtered retrieval by country, site name and year; the local object is the full record object, and the 2007 subset was verified with the equivalent filters `country=GBR`, `site_name=Avonmouth`, `year=2007`, `use_flag=1`. The object last-modified date is 2023-02-16; its GESLA release is undeclared, so it is not labeled GESLA 4.1.

The local file has 853,104 rows, one row group, physical schema `date_time: timestamp[us]` plus `year, month, day, hour, country, site_name, lat, lon, sea_level, qc_flag, use_flag, file_name`; Parquet/pandas writer metadata says PyArrow 9.0.0 and pandas 1.5.0. Full-file span is 1961-01-01 00:00 through 2012-04-30 23:45. SHA-256 is `7a796fcb64215becd2fb429b75a48be5afcb392c613a7f54e509c36250e71bb8` (5,180,521 bytes).

The 2007 record is Avonmouth, GBR, 51.50775 N / 2.71275 W, and spans 2007-01-01 00:00 to 2007-12-31 23:45 UTC. It has 35,040 rows on the expected 15-minute grid. Flag counts: 35,030 `qc_flag=1` and `use_flag=1`; 10 `qc_flag=2` interpolated; none with `qc_flag=3/4/5`, use-flag 0, nulls, fill sentinels or duplicate timestamps. GESLA documents UTC and metres. Parquet has no datum or primary/secondary channel metadata. Coordinates differ slightly from BODC's series page. These limitations remain explicit; P0 does not call this the original BODC primary-channel file.

The GESLA license page lists BODC as permitting research and consultancy, and requests compliance with provider-specific conditions. Since the object release is undeclared, its raw data stays local, is not redistributed, and publications must acknowledge GESLA and cite the papers listed by the GESLA downloads page. [GESLA license](https://gesla787883612.wordpress.com/license/) · [GESLA downloads](https://gesla787883612.wordpress.com/downloads/) · [geslaR query API](https://eireextremes.github.io/geslaR/reference/query_gesla.html) · [BODC series 303295](https://www.bodc.ac.uk/data/documents/series/303295/).

## Independent question: direct Table 1b reproduction

**Not ready.** No 2007 hourly NOC CS3X residual-surge file or verified Avonmouth grid-cell/extraction coordinate is available. NOC format documentation describes hourly residual surge from 1992 and CS3X from 2007, but is not the data series. The NTSLF top skew-surge events summary is not a substitute. The request draft in `reports/data_request_draft.md` has not been sent. No `H-A` or `H-S-A` proxy is used. [NOC CS3/CS3X format](https://noc.ac.uk/files/documents/business/CS3-92on-format-info.pdf).

## P0 disposition

- Gauge-only P0 source verification and branch selection: **DONE**.
- Paper-aligned Table 1b input readiness: **BLOCKED** pending matching 2007 residual surge and location mapping.
- Original BODC channel identity / datum: unresolved limitation, not a gauge-only processing blocker because no conversion or channel assertion is made.
- Portbury: rejected as a substitute.
