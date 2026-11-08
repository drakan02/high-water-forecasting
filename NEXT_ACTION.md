# Next actions

Current branch: `phase/ann-avonmouth-public` (P9). The accepted P9 experiment is a gauge-only public-source substitute; P8's direct Table 1(b) limitation is unchanged.

## Next phase after P9 commit

Create a separate phase branch from the accepted P9 commit for Species Concordance with Newlyn. First inspect existing Newlyn source objects and the paper/repository definition of Species Concordance; freeze its target and comparison set before fitting. Keep the result labeled as a method substitute if the original source or exact implementation is unavailable.

Then assess Newport and network transfer on separate phase branches, retaining every port/model result regardless of score. Keep source coverage, station metadata and target definitions explicit. Only add Power BI views after the validated prediction tables and paired metrics exist.

## User-side source access

- BODC: open the official processed all-channels listing, select the Avonmouth 2007 row, add it to the basket, choose the NTSLF/ASCII download and save the returned file unchanged under `data/raw/bodc/avonmouth/`. The catalog marks the row unrestricted. If the browser requests an account, register/sign in on BODC there; do not share credentials in chat.
- Copernicus CDS: sign in or register on the CDS website, open `sis-water-level-change-timeseries-cmip6`, choose GTSM 3.0 ERA5 reanalysis, storm surge residual, hourly, year 2007, month January, version v3, ZIP, accept the displayed terms and submit. Save the portal-generated API request and downloaded ZIP under `data/raw/copernicus_gtsm/avonmouth_trial/`. Keep the token on the user's machine.

No GTSM candidate point has yet been verified. Do not interpret the UTide residual as surge. Direct Table 1(b) reproduction remains unverified until the surge location and source/channel/datum compatibility are established.
