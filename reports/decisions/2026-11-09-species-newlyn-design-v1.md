# Newlyn reference species-transfer design v1

**Locked before fitting/scoring:** 2026-11-09
**Branch:** `phase/species-concordance-newlyn`
**Parent:** accepted ANN commit `e142474527c052a6d9e80cd03850c64c1bf15e06`

## Source and objective

- Use the actual Newlyn GESLA S3 object with BODC lineage: `parquet_files/newlyn-new-gbr-bodc.parquet`, downloaded from the public `gesla-dataset` bucket. Object SHA-256 `fce88b666b281f8d2b47c8b91336f7e27df3115956c7f80449cb83d0aa2a8ce9`, 10,404,468 bytes. GESLA release number is not encoded in this Parquet object's metadata; report it as a GESLA S3 Parquet object, release unresolved. Original BODC channel and vertical datum are not present.
- Pair with the unchanged Avonmouth source object, SHA-256 `7a796fcb64215becd2fb429b75a48be5afcb392c613a7f54e509c36250e71bb8`.
- The paper used SHOM's MAS (MArvé Simon) Species Concordance suite, one year of overlapping Newlyn/Avonmouth data, and reports Newlyn as its selected reference. The original MAS implementation is unavailable in this repository. This design is a transparent **species-banded complex harmonic transfer approximation**, not exact MAS or direct reproduction of the paper method.
- Fit/calibrate on 2006 and score the held-out calendar year 2007. In 2006, exact-minute QC-valid samples are 8,402 at Avonmouth and 8,299 at Newlyn (8,077 common). In 2007, there are 8,759 Avonmouth and 6,007 Newlyn valid hours (6,006 common). The 2007 Newlyn file contains 9,013 doubtful and 1,959 missing-QC rows; retain this as a source limitation, and do not use those values.

## Locked calculation

- Normalize timestamps to UTC, retain only exact minute-00 records with finite/non-fill values and `use_flag=1`, `qc_flag=1`; never interpolate, average channels, or fill gaps.
- Fit separate UTide 0.4.0 OLS harmonic models to 2006 QC-valid hourly observations at each port, with automatic constituent selection, Greenwich phases, mean and trend, and nodal corrections. Use the intersection of constituent names in a fixed order.
- For each constituent with a finite UTide Doodson species code (`-1`, `0`, `2`, `3`, etc.), calculate its complex coefficient as `A exp(-i g)`. Estimate one complex multiplier per species by least squares through the origin from Newlyn coefficients to Avonmouth coefficients. Set species-unclassified constituents to zero in the transferred prediction; list them in the manifest. Add the 2006 Avonmouth mean and trend to the transferred astronomical series.
- Reconstruct the transferred series on the full 2007 UTC hourly grid. Keep observed `H` null where Avonmouth QC fails. Produce a parallel direct UTide-through-2006 baseline.
- Compare both predictions on the same valid Avonmouth timestamps and the same eligible P3 high-water cycle IDs. Label all scores as total observed water level H (gauge-only), not surge-corrected. No surge is inferred.
- This transfer omits the MAS time-varying complex-envelope procedure and the paper's detailed Eq. 2–4 handling; interpret it only as a documented computational substitute. Its 2007 predictions are retrospective astronomical hindcasts; no real-time Newlyn availability claim is made.
