# Avonmouth ANN public-source design v3

**Locked before refit v3:** 2026-11-09
**Branch:** `phase/ann-avonmouth-public`
**Parent:** public-source trial commit `e465306b6d4d2336f66fcbbfc4aa3708a7c6d383`

This version keeps the v2 chronological UTide state and paired-cycle rule unchanged. The v2 run reached its 250-iteration cap for all three seeds without the optimizer reporting convergence. This is a solver diagnostic, not a change based on held-out scores. Increase only the optimizer iteration cap to 1,000; keep validation patience at six, L-BFGS-B settings, features, seeds, data splits, scaling, and metrics unchanged. A timeout of 240 seconds and one BLAS thread bound compute. If any seed remains unconverged at the cap, report that fact and preserve its validation-best checkpoint; do not claim exact paper algorithm reproduction.
