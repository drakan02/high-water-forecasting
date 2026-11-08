# Avonmouth ANN public-source design v1

**Locked before model fitting:** 2026-11-09
**Branch:** `phase/ann-avonmouth-public`
**Parent:** public-source trial commit `e465306b6d4d2336f66fcbbfc4aa3708a7c6d383`

## Input periods and target

- Training targets: calendar 2005; validation: 2006; held-out score: 2007.
- Source: verified GESLA S3 Avonmouth/BODC-lineage Parquet; original BODC channel and datum remain unresolved.
- Hourly samples: exact UTC minute-00 only, finite/non-sentinel, `use_flag=1`, `qc_flag=1`; do not average, interpolate, or fill gaps.
- Harmonic input: accepted UTide 0.4.0 retrospective 1988–2007 saved state, not author EHM. It includes 68 automatically selected constituents, OLS mean/trend, Greenwich phase, and nodal corrections.
- Predictors: the 168 hourly observed H values through forecast issue time; the matching 168 UTide A values over that historical window; and the known UTide A at target time. Forecast lead is fixed at 24 hours. Any invalid historical H in the window makes the forecast unavailable; no imputation.
- Target: total observed hourly water level H. No surge is available, so do not subtract a residual or claim the paper's surge-corrected error.

## Network and fit

- Feed-forward network: 24 and 6 tanh hidden units, linear scalar output.
- Three fixed initialization seeds: 42, 43, 44. Report all three and their arithmetic-mean ensemble; do not choose the best seed by test score.
- Train-only feature and target standardization; L2 alpha 0.001.
- Validation early stopping after six consecutive iterations without validation-MSE improvement; max 60 L-BFGS-B iterations per seed.
- Implementation uses SciPy L-BFGS-B with analytic gradients. This differs from MATLAB R2008b Neural Network Toolbox Bayesian regularization/Levenberg–Marquardt in the paper; this is a public-source method substitute, not exact algorithm replication.
- Score hourly held-out target levels and separately score P3 high-water cycle peaks. Compare UTide and ANN on identical timestamp/cycle IDs; report the target as total H and keep surge null.

## Known paper ambiguities

The paper reports 2005 training data, 2006 validation data, 2007 pilot evaluation, two predictors (observed level and EHM tide) over input windows from 7 days to 24 hours, and a 24/6 hidden-layer model. It does not fully specify the exact selected history length/feature alignment, scaling, split treatment at window boundaries, random seeds, or the learned weights. This registered design chooses a seven-day history and a 24-hour issue lead before examining test metrics. Results must not be reported as direct reproduction of Table 1(a) or 1(b).
