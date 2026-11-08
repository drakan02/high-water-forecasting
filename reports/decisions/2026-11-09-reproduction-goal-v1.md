# Reproduction goal decision v1 — public sources

**Decision date:** 2026-11-09
**Applies from:** `phase/public-source-trial`
**Basis:** audit commit `aa0d0c7a48b937f211b1c740f503a009b9c2c512`

## Decision

The project goal is now to reproduce the methods in Hibbert et al. (2015) as far as permitted by verifiable public data sources, including clearly labeled substitute-source experiments when direct paper inputs are unavailable. No email or NOC support request will be sent; progress must not depend on receiving a reply.

This decision does not revise the earlier P8 finding: direct reproduction of the paper's Avonmouth Table 1(b) remains unverified because the exact paper EHM baseline and matching hourly CS3X hindcast/grid extraction have not been obtained. Any substitute experiment must be identified by source/model/target and kept separate from published EHM results. Do not infer surge as `H-A` or use a BODC observational residual as surge.

## Evidence labels

- **Direct-method reproduction:** same target definition, source classes and model configuration as the paper, with source lineage and time alignment demonstrated.
- **Public-source substitute:** method implemented with available public data whose source/model differs from the paper; report its actual target, uncertainty and differences.
- **Gauge-only:** target is total observed water level `H` unless independently measured/modelled surge is available; metrics use common high-water IDs.
- **Unverified:** required input, temporal availability, station/grid mapping, or algorithm equivalence is not established. Do not merge these results into direct-paper comparison rows.

## Phase gates

1. Complete the public-source trial and its acceptance record on `phase/public-source-trial`.
2. Create each downstream phase branch only from the verified accepted commit of the preceding phase. Full tests, prior-artifact checks, and `main` SHA comparison are required before each commit.
3. Continue independent experiments (ANN, Newlyn Species Concordance, Newport/network, Power BI) with available data and explicit gauge-only/substitute labels. A low score is not a reason to omit a model/site.
4. Preserve the existing P8 assessment on its isolated worktree. Never revise its conclusion to imply Table 1(b) is reproduced.
5. Do not edit or push `main`; do not send correspondence; do not put access tokens in the repository or chat. The user accepts any portal terms directly in their own account.

## Version history

- **v1 (2026-11-09):** first version, setting the public-source substitute objective while preserving the prior direct Table 1(b) limitation.
