"""GESLA Parquet ingestion and exact-minute hourly preparation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd
import pyarrow.parquet as pq


GESLA_COLUMNS = {
    "date_time",
    "year",
    "country",
    "site_name",
    "lat",
    "lon",
    "sea_level",
    "qc_flag",
    "use_flag",
    "file_name",
}
GESLA_MISSING_VALUE = -99.9999
GESLA_QC_LABELS = {
    0: "not_quality_controlled",
    1: "correct",
    2: "interpolated",
    3: "doubtful",
    4: "isolated_spike_or_wrong",
    5: "missing",
}


class IngestError(ValueError):
    """Raised when a source file does not satisfy its declared contract."""


class DuplicateTimestampError(IngestError):
    """Raised rather than collapsing multiple source rows at one timestamp."""


@dataclass(frozen=True)
class SourceIdentity:
    station: str
    country: str
    latitude: float
    longitude: float
    source_ids: tuple[str, ...]
    source_rows: int
    first_time_utc: pd.Timestamp
    last_time_utc: pd.Timestamp


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_gesla_station_parquet(
    path: Path,
    *,
    expected_station: str,
    expected_country: str = "GBR",
    expected_source_ids: tuple[str, ...] | None = None,
) -> tuple[pd.DataFrame, SourceIdentity]:
    """Read an unmodified GESLA file and verify its declared station lineage."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    schema = pq.read_schema(path)
    missing = GESLA_COLUMNS.difference(schema.names)
    if missing:
        raise IngestError(f"Missing GESLA columns: {', '.join(sorted(missing))}")

    frame = pd.read_parquet(path)
    if frame.empty:
        raise IngestError(f"No records in {path}")
    if set(frame["site_name"].dropna().unique()) != {expected_station}:
        raise IngestError(f"Source must contain only the exact site_name {expected_station!r}")
    if set(frame["country"].dropna().unique()) != {expected_country}:
        raise IngestError(f"Source must contain only country code {expected_country}")
    source_ids = tuple(sorted(frame["file_name"].dropna().unique()))
    if expected_source_ids is not None and source_ids != tuple(sorted(expected_source_ids)):
        raise IngestError(f"Source lineage mismatch: expected {expected_source_ids}, got {source_ids}")
    if frame["date_time"].isna().any():
        raise IngestError("Source contains null timestamps")

    times = pd.to_datetime(frame["date_time"], utc=True)
    frame["time_utc"] = times
    identity = SourceIdentity(
        station=expected_station,
        country=expected_country,
        latitude=float(frame["lat"].median()),
        longitude=float(frame["lon"].median()),
        source_ids=source_ids,
        source_rows=len(frame),
        first_time_utc=times.min(),
        last_time_utc=times.max(),
    )
    return frame, identity


def read_gesla_parquet(path: Path) -> tuple[pd.DataFrame, SourceIdentity]:
    """Read and validate the project's original Avonmouth GESLA input."""
    return read_gesla_station_parquet(
        path,
        expected_station="Avonmouth",
        expected_country="GBR",
        expected_source_ids=("avonmouth-avo-gbr-bodc",),
    )


def normalize_gesla(frame: pd.DataFrame) -> pd.DataFrame:
    """Add normalized UTC, metre, and source-QC fields without changing raw fields."""
    normalized = frame.copy()
    normalized["time_utc"] = pd.to_datetime(normalized["date_time"], utc=True)
    normalized["level_m_raw"] = pd.to_numeric(normalized["sea_level"], errors="coerce")
    normalized["source_qc_label"] = normalized["qc_flag"].map(GESLA_QC_LABELS).fillna("unknown")
    finite = np.isfinite(normalized["level_m_raw"].to_numpy(dtype=float))
    not_sentinel = ~np.isclose(
        normalized["level_m_raw"].to_numpy(dtype=float), GESLA_MISSING_VALUE
    )
    source_recommends_use = normalized["use_flag"].eq(1).to_numpy()
    qc_is_correct = normalized["qc_flag"].eq(1).to_numpy()
    normalized["analysis_valid"] = finite & not_sentinel & source_recommends_use & qc_is_correct
    normalized["level_m"] = normalized["level_m_raw"].where(normalized["analysis_valid"])

    reasons = np.full(len(normalized), "valid", dtype=object)
    reasons[~finite | ~not_sentinel] = "missing_or_sentinel"
    reasons[finite & not_sentinel & ~source_recommends_use] = "gesla_use_flag_not_recommended"
    other_qc = finite & not_sentinel & source_recommends_use & ~qc_is_correct
    reasons[other_qc] = np.char.add(
        "gesla_qc_", normalized.loc[other_qc, "source_qc_label"].astype(str).to_numpy()
    )
    normalized["qc_reason"] = reasons
    normalized["datum"] = "unknown_in_GESLA_record; no datum conversion applied"
    normalized["unit"] = "m"
    return normalized


def _check_unique_timestamps(frame: pd.DataFrame) -> None:
    duplicated = frame["time_utc"].duplicated(keep=False)
    if duplicated.any():
        examples = frame.loc[duplicated, "time_utc"].drop_duplicates().head(5).astype(str).tolist()
        raise DuplicateTimestampError(
            f"Found {int(duplicated.sum())} rows with duplicate timestamps; examples: {examples}"
        )


def prepare_hourly(
    frame: pd.DataFrame, year: int, *, station_id: str = "avonmouth"
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Sample exact minute-00 records onto a complete hourly UTC grid.

    No averaging, interpolation, channel combination, or duplicate collapse is done.
    """
    normalized = normalize_gesla(frame)
    source_year = normalized.loc[normalized["time_utc"].dt.year.eq(year)].copy()
    if source_year.empty:
        raise IngestError(f"No source rows for {year}")
    _check_unique_timestamps(source_year)

    expected = pd.date_range(
        start=pd.Timestamp(f"{year}-01-01", tz="UTC"),
        end=pd.Timestamp(f"{year + 1}-01-01", tz="UTC"),
        inclusive="left",
        freq="h",
        name="time_utc",
    )
    exact = source_year.loc[
        source_year["time_utc"].dt.minute.eq(0)
        & source_year["time_utc"].dt.second.eq(0)
        & source_year["time_utc"].dt.microsecond.eq(0)
    ].copy()
    exact = exact.set_index("time_utc").reindex(expected)
    hourly = pd.DataFrame(index=expected)
    hourly.index.name = "time_utc"
    hourly["station_id"] = station_id
    hourly["year"] = year
    hourly["level_m_raw"] = exact["level_m_raw"]
    hourly["level_m"] = exact["level_m"]
    hourly["analysis_valid"] = exact["analysis_valid"].fillna(False).astype(bool)
    hourly["source_qc_flag"] = exact["qc_flag"].astype("Int64")
    hourly["source_qc_label"] = exact["source_qc_label"].fillna("no_exact_minute_00_record")
    hourly["source_use_flag"] = exact["use_flag"].astype("Int64")
    hourly["source_file_name"] = exact["file_name"].fillna("")
    hourly["source_lat"] = exact["lat"]
    hourly["source_lon"] = exact["lon"]
    hourly["channel_id"] = pd.NA
    hourly["datum"] = "unknown_in_GESLA_record; no datum conversion applied"
    hourly["unit"] = "m"

    present = exact["date_time"].notna()
    has_any_source_row = pd.Series(expected.floor("h").isin(source_year["time_utc"].dt.floor("h")), index=expected)
    hourly["timestamp_present"] = present.to_numpy()
    hourly["qc_reason"] = exact["qc_reason"].fillna(
        pd.Series(
            np.where(has_any_source_row, "no_exact_minute_00_record", "no_source_record_for_hour"),
            index=expected,
        )
    ).to_numpy()

    counts = {
        "expected_hourly_timestamps": len(expected),
        "minute_00_timestamps_present": int(present.sum()),
        "valid_hourly_observations": int(hourly["analysis_valid"].sum()),
        "excluded_or_missing_hourly_slots": int((~hourly["analysis_valid"]).sum()),
        "source_rows_for_year": int(len(source_year)),
        "source_valid_rows_for_year": int(source_year["analysis_valid"].sum()),
        "source_interpolated_rows_for_year": int(source_year["qc_flag"].eq(2).sum()),
    }
    return hourly.reset_index(), counts


def monthly_quality(frame: pd.DataFrame, hourly: pd.DataFrame, year: int) -> pd.DataFrame:
    """Count actual source and exact-minute hourly coverage by calendar month."""
    normalized = normalize_gesla(frame)
    normalized = normalized.loc[normalized["time_utc"].dt.year.eq(year)].copy()
    normalized["month"] = normalized["time_utc"].dt.month
    hourly = hourly.copy()
    hourly["month"] = pd.to_datetime(hourly["time_utc"], utc=True).dt.month
    cadence_seconds = normalized["time_utc"].sort_values().diff().dt.total_seconds().mode()
    cadence_minutes = int(cadence_seconds.iloc[0] / 60) if not cadence_seconds.empty else 0

    records = []
    for month in range(1, 13):
        period = pd.Period(f"{year}-{month:02d}", freq="M")
        expected_hours = period.days_in_month * 24
        source = normalized.loc[normalized["month"].eq(month)]
        hour_rows = hourly.loc[hourly["month"].eq(month)]
        row: dict[str, object] = {
            "station_id": "avonmouth",
            "year": year,
            "month": month,
            "source_channel": "GESLA BODC record; original channel ID unresolved",
            "source_cadence_minutes_observed": cadence_minutes,
            "expected_source_timestamps": expected_hours * (60 // cadence_minutes) if cadence_minutes else pd.NA,
            "source_timestamps_present": len(source),
            "source_valid_qc1_rows": int(source["analysis_valid"].sum()),
            "source_qc_flag_2_interpolated_rows": int(source["qc_flag"].eq(2).sum()),
            "source_qc_flag_3_doubtful_rows": int(source["qc_flag"].eq(3).sum()),
            "source_qc_flag_4_spike_rows": int(source["qc_flag"].eq(4).sum()),
            "source_qc_flag_5_missing_rows": int(source["qc_flag"].eq(5).sum()),
            "source_use_flag_0_rows": int(source["use_flag"].eq(0).sum()),
            "expected_hourly_timestamps": expected_hours,
            "minute_00_timestamps_present": int(hour_rows["timestamp_present"].sum()),
            "valid_hourly_observations": int(hour_rows["analysis_valid"].sum()),
            "excluded_or_missing_hourly_slots": int((~hour_rows["analysis_valid"]).sum()),
        }
        records.append(row)
    return pd.DataFrame.from_records(records)


def raw_manifest(path: Path, frame: pd.DataFrame, identity: SourceIdentity) -> dict[str, object]:
    stat = path.stat()
    return {
        "source_product": "GESLA public S3 Parquet; BODC-provided Avonmouth record",
        "source_url": "https://gesla-dataset.s3.eu-west-1.amazonaws.com/parquet_files/avonmouth-avo-gbr-bodc.parquet",
        "query_route": "Full public S3 source object fetched; analysis subset verified with geslaR query_gesla equivalent: country=GBR, site_name=Avonmouth, year=2007, use_flag=1",
        "geslaR_version_reviewed": "1.0-3",
        "dataset_release": "S3 object does not declare a GESLA dataset release; do not label it as GESLA-4.1",
        "source_last_modified": "2023-02-16T19:11:39Z",
        "local_file": str(path),
        "size_bytes": stat.st_size,
        "sha256": sha256_file(path),
        "source_rows": identity.source_rows,
        "source_columns": json.dumps(pq.read_schema(path).names, separators=(",", ":")),
        "source_first_time_utc": identity.first_time_utc.isoformat(),
        "source_last_time_utc": identity.last_time_utc.isoformat(),
        "source_site_name": identity.station,
        "source_country": identity.country,
        "source_latitude": identity.latitude,
        "source_longitude": identity.longitude,
        "source_ids": ";".join(identity.source_ids),
        "source_units": "m (GESLA variable metadata)",
        "source_datum": "unspecified in GESLA file; BODC station metadata says 1986+ TGZ/Chart Datum is 6.50 m below ODN; no conversion applied",
        "channel_id": "not present; primary/secondary BODC channel unresolved",
        "qc_policy": "Preserve qc_flag and use_flag; analysis-valid requires use_flag=1, qc_flag=1, finite non-sentinel level",
        "access_terms": "Public research data; GESLA says provider-specific terms apply. BODC original offers free scientific use but requires registration. Keep local; no redistribution.",
    }
