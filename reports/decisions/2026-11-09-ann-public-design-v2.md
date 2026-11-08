# Avonmouth ANN public-source design v2

**Locked before corrected refit:** 2026-11-09
**Branch:** `phase/ann-avonmouth-public`
**Parent:** public-source trial commit `e465306b6d4d2336f66fcbbfc4aa3708a7c6d383`

## Reason for revision

An initial exploratory run used the retrospective UTide state fitted through 2007, so the harmonic input included held-out-year observations. Its metrics are superseded and are not accepted or reported as the experiment result. Review also found that the first peak-metric export used different forecastable cycle sets for UTide and ANN. Version 2 closes both issues before the accepted refit: use the P2 chronological UTide state fit only through 2004, and calculate peak metrics on the intersection of eligible cycle IDs for which both methods have predictions.

## Locked design

- Training targets: 2005; validation: 2006; held-out score: 2007.
- Source: GESLA S3 Avonmouth/BODC-lineage Parquet, SHA-256 `7a796fcb64215becd2fb429b75a48be5afcb392c613a7f54e509c36250e71bb8`; original BODC channel and datum remain unresolved.
- Hourly samples: exact UTC minute-00 only, finite/non-sentinel, `use_flag=1`, `qc_flag=1`; no averaging, interpolation, or filling.
- Harmonic predictor: saved UTide 0.4.0 chronological fit through 2004; state SHA-256 `445e3f857e8c5b89e2d1ba449c0747a95f5e693f33c965cde80280ae5dff76d9`. It contains 68 automatically selected constituents, OLS mean/trend, Greenwich phase and nodal corrections. This is not verified equivalent to the paper EHM.
- Predictors: 168 hourly observed H values through forecast issue time; matching 168 chronological UTide A values; and known UTide A at target time. Forecast lead is fixed at 24 hours. Any invalid historical H in the window makes the forecast unavailable; no imputation.
- Target: total observed hourly water level H. No surge is available or inferred.
- Feed-forward network: 24 and 6 tanh hidden units, linear scalar output; fixed initial seeds 42, 43 and 44; report each and their arithmetic-mean ensemble.
- Train-only feature and target standardization; L2 alpha 0.001. SciPy L-BFGS-B with analytic gradients, maximum 250 iterations, validation early stopping after six consecutive iterations without validation-MSE improvement. Store convergence status; a run hitting the cap without optimizer convergence is reported as not converged and cannot be described as an exact algorithm reproduction.
- Hourly metrics use identical valid target timestamps for UTide and ANN. High-water peak metrics use only the shared eligible P3 cycle IDs forecastable by both methods; the exact shared-ID hash is stored.
- Paper ambiguity remains: exact feature alignment/history, scaling, random seeds and weights are unspecified. MATLAB R2008b Bayesian regularization/Levenberg–Marquardt is not reproduced by this SciPy fixed-L2 optimizer. This is a public-source method substitute, not direct Table 1(a)/(b) reproduction.
