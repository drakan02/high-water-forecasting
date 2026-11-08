# Public-source access trial — BODC and Copernicus GTSM

**Trial date:** 2026-11-09
**Branch:** `phase/public-source-trial` from audit `aa0d0c7a48b937f211b1c740f503a009b9c2c512`
**P8 state:** prior report retained in `/tmp/high-water-forecasting-P8`; direct Table 1(b) remains unverified.

## File inventory check

Searched project `data/` for Avonmouth/BODC/surge/GTSM files. The only source record found is the existing ignored GESLA object:

`data/raw/gesla_s3/avonmouth-avo-gbr-bodc.parquet`
SHA-256: `7a796fcb64215becd2fb429b75a48be5afcb392c613a7f54e509c36250e71bb8`

No original BODC annual/all-channel file, BODC residual file, or GTSM/CS3X file was present. No new file was downloaded in this trial.

## BODC processed/all-channels trial

- Public all-channels search page fetched successfully (HTTP 200, 46,394 bytes): https://www.bodc.ac.uk/data/hosted_data_systems/sea_level/uk_tide_gauge_network/processed_all_channels/
- Search listing includes Avonmouth at 51.51089 N, 2.71497 W, 2007-01-01 to 2007-12-31, with data restriction `Unrestricted`.
- The page describes access to all gauge channels. The general UKTGN page says historical processed data are free; the annual/monthly user portal requires a registered account. BODC format documentation confirms observation and residual data are available product classes and defines residual as observed sea level minus predicted tide, so `A_BODC = H_BODC - R_BODC` is valid only when a delivered file contains matched values from the same source/channel/timestamps and compatible datum.
- Tried the public all-channels UI's initial search POST without credentials. BODC returned HTTP 503 (temporary service/capacity response), so no selection, data file or generated query was obtained. The search listing is metadata evidence, not a downloaded/parsed record.
- The archived prediction reconstructed from observed minus BODC residual, if the file supports that, must be named **BODC archived prediction** and compared to locked UTide on common timestamps/peak IDs. It is not presumed equivalent to Hibbert 2015 EHM. BODC residual is not surge.

### One browser route for the user

Open the [BODC processed all-channels page](https://www.bodc.ac.uk/data/hosted_data_systems/sea_level/uk_tide_gauge_network/processed_all_channels/), filter/select the Avonmouth row for 2007-01-01 through 2007-12-31 (the listing marks it `Unrestricted`), add it to the basket, choose an available NTSLF/ASCII output, and download it. Save the delivered archive and metadata unchanged under `data/raw/bodc/avonmouth/` in the main working checkout. If the basket redirects to login, sign in/register with BODC in that browser; do not send credentials here. This output location is reserved for both annual channel data and any delivered metadata. Once present, calculate SHA-256 before parsing and inspect whether the package actually contains observed and residual series, channels, and original QC flags.

## Copernicus CDS GTSM trial

Official dataset page: https://cds.climate.copernicus.eu/datasets/sis-water-level-change-timeseries-cmip6?tab=download. It identifies the dataset as Deltares GTSM v3, ERA5 reanalysis through 2024, storm-surge residual in metres, and reanalysis temporal options including hourly. The data include station/grid coordinates (`station_x_coordinates`, `station_y_coordinates`). The download form currently offers reanalysis v3 and requires the user to accept the CC-BY terms before submitting a request. A documented issue says hourly v2 had a 30-minute shift and that v3 resolves it; use v3 only.

**Attempt/result:** checked local environment without reading or exposing any secret: no CDS API client, `.cdsapirc`, or CDS credential environment variables are present. The portal's mandatory user agreement has not been accepted. Therefore no API job was submitted and no dataset bytes, generated API request, coordinates, or grid points were retrieved. We will not accept terms on the user's behalf.

**Trial request specification (not a portal-generated request):** dataset `sis-water-level-change-timeseries-cmip6`; variable `storm_surge_residual`; experiment `reanalysis`; temporal aggregation `hourly`; year `2007`; month `01`; version `v3`; format `zip`. After portal submission, save its exact “Show API request code” output and returned version/format metadata beside the downloaded data; do not substitute this specification for that generated query.

### User self-service in browser

Open the CDS dataset page, log in or register, select **Storm surge residual**, **Reanalysis**, **Hourly**, **2007**, **January**, **v3**, then accept the dataset's displayed terms in the form and submit. Download the returned ZIP to `data/raw/copernicus_gtsm/avonmouth_trial/`; use the portal's “Show API request code” and save it as `query_generated.py.txt`. Do not paste an API token into chat. This one-month request may return global station time series; only after download can we list actual candidate coordinates and screen coastal connectivity. No GTSM candidate points are yet verified, so no point has been selected based on error.

## Data/method gate from this trial

| Source/input | Period needed now | File retrieved/parsed? | What is confirmed | Remaining condition |
|---|---|---|---|---|
| BODC Avonmouth channels | 2007 first; historical years later | No; page fetched, anonymous query POST returned 503 | Public listing row exists and is marked unrestricted | Obtain actual files and verify variables, channel, QC, units, time/datum; no direct EHM equivalence assumed |
| CDS GTSM v3 ERA5 residual | January 2007 first | No; account/terms gate; no API credentials installed | Product options, units, source model/version, and coordinates fields documented | User must accept terms/download; inspect actual coastal points and connectivity before any error analysis |
| UTide locked baseline | Existing 1988–2007/2004-train designs | Existing accepted pilot artifacts | UTide 0.4.0, 68 constituents, locked source/config recorded in P2 | Substitute baseline only; not EHM 2015 |

**Source-trial conclusion:** no independent residual series or BODC archive file was obtained in this runtime. The most actionable path is now the unrestricted BODC all-channels row, which does not require a NOC email. Copernicus requires an account and user-side terms acceptance before its first-month query. The trial assesses source accessibility and records exact next steps; it does not claim any scientific metric or direct Table 1(b) result. Continue only with experiments supported by locally verified data, keeping target/method labels explicit.
