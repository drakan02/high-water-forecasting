# Newport network gauge-only design v1

**Locked before model fitting:** 2026-11-09
**Branch:** `phase/newport-network-transfer`
**Parent:** P10 accepted commit `bdf19428d52429602ca936ada37bbb64fb7c7e6c`

## Source

Use the public GESLA S3 Parquet object `parquet_files/newport-npo-gbr-bodc.parquet`, exact source ID `newport-npo-gbr-bodc`, country GBR and site Newport. It is a BODC-lineage source mirror; the object does not encode the GESLA release number, original BODC channel, or vertical datum. Retain the source unit as metres and make no vertical conversion. Keep the raw object unchanged.

The file contains 1,002,144 rows from 1993-01-01 through 2021-07-31 23:45 UTC at 15-minute cadence, coordinates 51.55 N, 2.987444 W. Exact-hour analysis uses only minute-00, finite, non-fill observations with `use_flag=1` and `qc_flag=1`; no interpolation, averaging, channel blending, or QC relaxation.

## Locked models and split

1. UTide 0.4.0 OLS harmonic baseline, fit 1993-01-01 through 2009-12-31 on all exact-hour QC-valid observations, auto constituent selection, Greenwich phase, mean/trend and nodal corrections. This is Newport's own long-history baseline, not a transferred Avonmouth EHM.
2. Frozen gauge-only ECM: reconstruct Newport A(t) from the same UTide state; form high-water cycle errors from Newport H−A; fit OLS with intercept using 2009 eligible peaks only; issue time is A-peak minus 24 hours; predictors are N−2/N−4/N−6 by immutable cycle number; score calendar 2010.
3. Report baseline A_N and ECM A_N + correction on the same QC-eligible 2010 cycle IDs. The target is total observed Newport H. No residual is labeled as surge and no Table 1 or Table 2 metric is inferred.

Use exact hourly grids for 2008–2011 to retain the prior-cycle context. Preserve excluded peaks and lag-availability flags. Report the 2010 counts from file values, not catalog coverage.

## Scope limits

This phase adds a second-port gauge-only network evaluation. It does not implement the paper's SHOM MAS at Newport, ANN (the paper's ANN pilot is Avonmouth), the 44-station network, or paper-aligned surge-corrected metrics. All methods remain registered in the project's model/port matrix with explicit not-applicable or unavailable reasons; poor scores are not a reason to remove a model or port.
