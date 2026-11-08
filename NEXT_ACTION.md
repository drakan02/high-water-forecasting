# Next actions

Accepted through P11 on `phase/newport-network-transfer`. P8's direct Table 1(b) result remains unchanged: a matched historical CS3X residual and original BODC channel/datum are still unverified. P11 adds a second-port gauge-only 2010 result and covers two of the article's 44 network locations including Avonmouth.

## Next phase: remaining network stations

Create a separate network expansion phase from the accepted P11 commit. Inventory the remaining paper stations against actual public source objects, validate each station's metadata/cadence/QC and run eligible registered methods without filtering on skill. Extend `reports/results/model_port_period_target.csv`; keep total-H gauge-only scores separate from surge-corrected paper metrics. Newport and Avonmouth are the current two sites, not the full network.

After the network matrix is complete or each remaining station has a documented source-specific blocker, create a dedicated Power BI phase. Start from the existing dashboard and bind it to validated forecast tables and the matrix. Preserve paired peak IDs, QC coverage, forecast origin, lag trace and target labels. Validate dashboard counts against Python paired CSVs; mark Desktop-only refresh/UI checks pending if Power BI Desktop is unavailable.

## Direct paper source access still needed

- BODC: register/sign in on BODC in the browser, download Avonmouth 2007 processed all-channel/NTSLF data unchanged to `data/raw/bodc/avonmouth/`.
- Copernicus CDS: sign in, accept the dataset terms, request GTSM 3.0 ERA5 hourly storm-surge residual for January 2007, and save the generated query and ZIP under `data/raw/copernicus_gtsm/avonmouth_trial/`. Keep credentials/token local.

No NOC email is planned. Never use H−A as storm surge.
