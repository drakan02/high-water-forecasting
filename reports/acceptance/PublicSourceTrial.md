# Public-source trial acceptance

- Branch: `phase/public-source-trial`
- Parent: `aa0d0c7a48b937f211b1c740f503a009b9c2c512` (audit)
- `main` at start: `e6deb2b04ef28b1d5e42258b128f2f53d8f78882`
- Scope: evaluate public-source access for BODC Avonmouth all-channel 2007 and Copernicus CDS GTSM v3 ERA5 residual, and version the revised project objective.
- Result: **accepted for source-access assessment only**. No water-level/surge file was downloaded or parsed; this is not scientific-method acceptance and does not alter P8's direct Table 1(b) limitation.

## Checklist

- [x] Verified audit SHA, P7 working branch/HEAD, `main` SHA, and P8 worktree. P7 uncommitted dashboard/log work was left untouched; P8 in `/tmp/high-water-forecasting-P8` was preserved.
- [x] Created this phase branch from the audit SHA in persistent worktree `/home/khang/Code/data-pipeline/worktrees/high-water-forecasting-public-source-trial`.
- [x] Searched repository `data/`; only the existing GESLA/BODC-lineage file was present. Its SHA matches the P1 manifest; no original BODC data, BODC residual, or GTSM/CS3X file was available.
- [x] Fetched the official BODC processed-all-channels page (HTTP 200); confirmed the Avonmouth 2007 row and `Unrestricted` status. An anonymous query POST returned HTTP 503. No data file was produced.
- [x] Checked the official CDS form/documentation for GTSM v3, ERA5, hourly storm-surge residual, metre units, coordinate fields, and user-side terms acceptance. Local CDS client/config is absent; no job was submitted, and no terms were accepted by the agent.
- [x] Added `reports/decisions/2026-11-09-reproduction-goal-v1.md`, preserving the old P8 boundary and forbidding correspondence/token sharing.
- [x] Added a self-service browser route and exact one-month CDS request selection to `reports/public_source_trial/source_access.md`. No candidate GTSM point or error-based selection is claimed.
- [x] Full existing test suite passed: 22 tests. Python syntax, CSV/YAML/JSON checks and `git diff --check` passed.
- [x] No source/model outputs were overwritten. No main checkout, merge, push, or token access occurred.

## Scope and limits

This phase answers whether the public acquisition routes are identified and records the real access results. BODC's unrestricted listing is actionable without a NOC request, but the anonymous query failed transiently and actual values/QC fields remain to be checked. CDS selection is blocked until the user logs in and accepts terms; its dataset metadata do not provide point coordinates in the search result, so no GTSM point can yet be judged for coastal connectivity. The existing UTide baseline remains a labeled substitute. Direct paper EHM comparison and Table 1(b) remain unverified.

Next phase may start only from this commit and must use a separately labeled gauge-only/public-source method while the user-side data downloads remain outstanding. Keep the prior P8 worktree unchanged.
