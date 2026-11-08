from __future__ import annotations

import pandas as pd
import pytest

from tide.ingest import (
    DuplicateTimestampError,
    IngestError,
    normalize_gesla,
    prepare_hourly,
    raw_manifest,
    read_gesla_parquet,
    read_gesla_station_parquet,
)


def gesla_rows(records: list[tuple[str, float, int, int]]) -> pd.DataFrame:
    rows = []
    for timestamp, level, qc_flag, use_flag in records:
        time = pd.Timestamp(timestamp)
        rows.append(
            {
                "date_time": time,
                "year": time.year,
                "month": time.month,
                "day": time.day,
                "hour": time.hour,
                "country": "GBR",
                "site_name": "Avonmouth",
                "lat": 51.50775,
                "lon": -2.71275,
                "sea_level": level,
                "qc_flag": qc_flag,
                "use_flag": use_flag,
                "file_name": "avonmouth-avo-gbr-bodc",
            }
        )
    return pd.DataFrame(rows)


def test_missing_sentinel_is_preserved_but_not_valid() -> None:
    source = gesla_rows([("2007-01-01 00:00", -99.9999, 5, 0)])
    normalized = normalize_gesla(source)
    assert normalized.loc[0, "sea_level"] == -99.9999
    assert not normalized.loc[0, "analysis_valid"]
    assert pd.isna(normalized.loc[0, "level_m"])
    assert normalized.loc[0, "qc_reason"] == "missing_or_sentinel"


def test_suspect_and_not_recommended_flags_are_retained_and_excluded() -> None:
    source = gesla_rows(
        [
            ("2007-01-01 00:00", 2.1, 3, 1),
            ("2007-01-01 01:00", 2.2, 1, 0),
        ]
    )
    normalized = normalize_gesla(source)
    assert normalized["qc_flag"].tolist() == [3, 1]
    assert normalized["use_flag"].tolist() == [1, 0]
    assert normalized["level_m"].isna().all()
    assert normalized["qc_reason"].tolist() == ["gesla_qc_doubtful", "gesla_use_flag_not_recommended"]


def test_duplicate_timestamps_are_not_collapsed() -> None:
    source = gesla_rows(
        [
            ("2007-01-01 00:00", 2.1, 1, 1),
            ("2007-01-01 00:00", 2.3, 1, 1),
        ]
    )
    with pytest.raises(DuplicateTimestampError, match="duplicate timestamps"):
        prepare_hourly(source, 2007)


def test_two_channels_at_one_timestamp_raise_instead_of_combining() -> None:
    source = gesla_rows(
        [
            ("2007-01-01 00:00", 2.1, 1, 1),
            ("2007-01-01 00:00", 2.2, 1, 1),
        ]
    )
    source["channel_id"] = ["primary", "secondary"]
    with pytest.raises(DuplicateTimestampError):
        prepare_hourly(source, 2007)


def test_missing_minute_00_is_left_null_even_when_quarter_hours_exist() -> None:
    source = gesla_rows(
        [
            ("2007-01-01 00:15", 2.1, 1, 1),
            ("2007-01-01 00:30", 2.2, 1, 1),
            ("2007-01-01 00:45", 2.3, 1, 1),
        ]
    )
    hourly, counts = prepare_hourly(source, 2007)
    first = hourly.iloc[0]
    assert pd.isna(first["level_m"])
    assert first["qc_reason"] == "no_exact_minute_00_record"
    assert counts["expected_hourly_timestamps"] == 8760
    assert counts["minute_00_timestamps_present"] == 0


def test_manifest_hashes_original_parquet_and_lists_its_columns(tmp_path) -> None:
    source = gesla_rows([("2007-01-01 00:00", 2.1, 1, 1)])
    path = tmp_path / "avonmouth.parquet"
    source.to_parquet(path, index=False)
    frame, identity = read_gesla_parquet(path)

    manifest = raw_manifest(path, frame, identity)

    assert manifest["size_bytes"] == path.stat().st_size
    assert "time_utc" not in manifest["source_columns"]
    assert '"date_time"' in manifest["source_columns"]
    assert manifest["source_rows"] == 1


def test_station_reader_supports_exact_newport_source_without_weakening_avonmouth_default(tmp_path) -> None:
    source = gesla_rows([("2007-01-01 00:00", 4.1, 1, 1)])
    source["site_name"] = "Newport"
    source["lat"] = 51.55
    source["lon"] = -2.987444
    source["file_name"] = "newport-npo-gbr-bodc"
    path = tmp_path / "newport.parquet"
    source.to_parquet(path, index=False)

    frame, identity = read_gesla_station_parquet(
        path,
        expected_station="Newport",
        expected_country="GBR",
        expected_source_ids=("newport-npo-gbr-bodc",),
    )
    hourly, _ = prepare_hourly(frame, 2007, station_id="newport")

    assert identity.station == "Newport"
    assert identity.source_ids == ("newport-npo-gbr-bodc",)
    assert hourly.iloc[0]["station_id"] == "newport"
    with pytest.raises(IngestError, match="exact site_name 'Avonmouth'"):
        read_gesla_parquet(path)
