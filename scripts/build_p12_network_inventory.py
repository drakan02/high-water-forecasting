"""Verify all 44 Hibbert network station mappings against local GESLA BODC Parquet."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

PAPER_PORTS = {
    "st_marys-stm-gbr-bodc": (1, "St Marys"), "newlyn-new-gbr-bodc": (2, "Newlyn"),
    "ilfracombe-ilf-gbr-bodc": (3, "Ilfracombe"), "hinkley_point-hin-gbr-bodc": (4, "Hinkley Point"),
    "portbury-ptb-gbr-bodc": (5, "Portbury"), "avonmouth-avo-gbr-bodc": (6, "Avonmouth"),
    "newport-npo-gbr-bodc": (7, "Newport"), "mumbles-mum-gbr-bodc": (8, "Mumbles"),
    "milford_haven-mha-gbr-bodc": (9, "Milford Haven"), "fishguard-fis-gbr-bodc": (10, "Fishguard"),
    "barmouth-bar-gbr-bodc": (11, "Barmouth"), "holyhead-hol-gbr-bodc": (12, "Holyhead"),
    "llandudno-lla-gbr-bodc": (13, "Llandudno"), "liverpool_gladstone_dock-liv-gbr-bodc": (14, "Liverpool"),
    "heysham-hey-gbr-bodc": (15, "Heysham"), "port_eri_isle_of_man-iom-gbr-bodc": (16, "Port Erin"),
    "workington-wor-gbr-bodc": (17, "Workington"), "bangor-ban-gbr-bodc": (18, "Bangor"),
    "portpatrick-por-gbr-bodc": (19, "Portpatrick"), "portrush-pru-gbr-bodc": (20, "Portrush"),
    "millport-mil-gbr-bodc": (21, "Millport"), "port_ellen_islay-isl-gbr-bodc": (22, "Port Ellen"),
    "tobermory-tob-gbr-bodc": (23, "Tobermory"), "ullapool-ull-gbr-bodc": (24, "Ullapool"),
    "stornoway-sto-gbr-bodc": (25, "Stornoway"), "kinlochbervie-kin-gbr-bodc": (26, "Kinlochbervie"),
    "lerwick-ler-gbr-bodc": (27, "Lerwick"), "wick-wic-gbr-bodc": (28, "Wick"),
    "aberdeen-abe-gbr-bodc": (29, "Aberdeen"), "leith-lei-gbr-bodc": (30, "Leith"),
    "north_shields-nsh-gbr-bodc": (31, "North Shields"), "whitby-whi-gbr-bodc": (32, "Whitby"),
    "immingham-imm-gbr-bodc": (33, "Immingham"), "cromer-cro-gbr-bodc": (34, "Cromer"),
    "lowestoft-low-gbr-bodc": (35, "Lowestoft"), "harwich-har-gbr-bodc": (36, "Harwich"),
    "sheerness-she-gbr-bodc": (37, "Sheerness"), "dover-dov-gbr-bodc": (38, "Dover"),
    "newhaven-nha-gbr-bodc": (39, "Newhaven"), "portsmouth-ptm-gbr-bodc": (40, "Portsmouth"),
    "bournemouth-bou-gbr-bodc": (41, "Bournemouth"), "weymouth-wey-gbr-bodc": (42, "Weymouth"),
    "st_helier_jersey-jer-gbr-bodc": (43, "Jersey"), "devonport-dev-gbr-bodc": (44, "Plymouth (Devonport)"),
}
PAPER_ECM_NOT_APPLICABLE = {"bournemouth-bou-gbr-bodc", "port_ellen_islay-isl-gbr-bodc"}
YEARS = tuple(range(2006, 2011))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    raw_dir = Path("data/raw/gesla_s3")
    output_dir = Path("reports/network_2010")
    output_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for path in sorted(raw_dir.glob("*-gbr-bodc.parquet")):
        schema = pq.read_schema(path)
        required = {"date_time", "country", "site_name", "lat", "lon", "sea_level", "qc_flag", "use_flag", "file_name"}
        missing = required.difference(schema.names)
        if missing:
            raise ValueError(f"{path} missing GESLA fields: {sorted(missing)}")
        frame = pd.read_parquet(path, columns=sorted(required))
        if frame.empty or set(frame.country.dropna().unique()) != {"GBR"}:
            raise ValueError(f"Unexpected or empty country identity in {path}")
        ids = tuple(sorted(frame.file_name.dropna().unique()))
        sites = tuple(sorted(frame.site_name.dropna().unique()))
        if len(ids) != 1 or path.stem != ids[0] or len(sites) != 1:
            raise ValueError(f"File/key/station identity mismatch in {path}: {ids}, {sites}")
        t = pd.to_datetime(frame.date_time, utc=True)
        if t.isna().any() or t.duplicated().any():
            raise ValueError(f"Null/duplicate timestamps in {path}")
        cadence = t.sort_values().diff().dropna().dt.total_seconds().div(60)
        median_cadence = float(cadence.median()) if not cadence.empty else np.nan
        is_paper = ids[0] in PAPER_PORTS
        port_no, paper_station = PAPER_PORTS.get(ids[0], ("", ""))
        record = {
            "paper_port_number": port_no, "paper_station": paper_station, "source_id": ids[0],
            "site_name": sites[0], "country": "GBR", "latitude": float(frame.lat.median()),
            "longitude": float(frame.lon.median()), "source_start_utc": str(t.min()), "source_end_utc": str(t.max()),
            "source_rows": int(len(frame)), "median_cadence_minutes": median_cadence, "unit": "m",
            "datum": "unknown_in_GESLA_record; no conversion", "channel": "BODC lineage; original channel unresolved",
            "local_file": str(path), "size_bytes": path.stat().st_size, "sha256": sha256(path),
            "paper_match": "matched" if is_paper else "extra_GBR_BODC_object_not_in_Hibbert_44",
            "ECM_scope": "not_applicable_per_paper_complex_multiple_high_low_waters" if ids[0] in PAPER_ECM_NOT_APPLICABLE else ("in_paper_scope" if is_paper else "outside_paper_44"),
        }
        for year in YEARS:
            part = frame.loc[frame.date_time.dt.year.eq(year)]
            expected_qh = 35136 if year % 4 == 0 else 35040
            expected_h = 8784 if year % 4 == 0 else 8760
            exact = part.date_time.dt.minute.eq(0) & part.date_time.dt.second.eq(0)
            finite = np.isfinite(pd.to_numeric(part.sea_level, errors="coerce").to_numpy(dtype=float))
            nonfill = ~np.isclose(pd.to_numeric(part.sea_level, errors="coerce").to_numpy(dtype=float), -99.9999)
            valid = part.qc_flag.eq(1).to_numpy() & part.use_flag.eq(1).to_numpy() & finite & nonfill
            stem = f"y{year}_"
            record[stem+"expected_quarter_hours"] = expected_qh
            record[stem+"rows_present"] = int(len(part))
            record[stem+"expected_hours"] = expected_h
            record[stem+"minute00_present"] = int(exact.sum())
            record[stem+"valid_minute00"] = int((exact.to_numpy() & valid).sum())
            record[stem+"coverage"] = float((exact.to_numpy() & valid).sum() / expected_h)
        records.append(record)
    if sum(row["paper_match"] == "matched" for row in records) != 44:
        raise AssertionError(f"Expected exactly 44 mapped paper stations, got {sum(row['paper_match']=='matched' for row in records)}")
    if sorted(row["paper_port_number"] for row in records if row["paper_match"]=="matched") != list(range(1,45)):
        raise AssertionError("Paper port numbers must map exactly once from 1 to 44")
    out=output_dir/"gesla_bodc_station_inventory.csv"
    pd.DataFrame(records).sort_values(["paper_port_number","source_id"],key=lambda s: s.astype(str)).to_csv(out,index=False)
    manifest={"s3_catalog_prefix":"parquet_files/","catalog_objects_total":5119,"gbr_bodc_objects":len(records),"paper_station_matches":44,"downloaded_bytes":int(sum(x["size_bytes"] for x in records)),"raw_files_redistributed":False,"output_csv":str(out),"output_sha256":sha256(out)}
    (output_dir/"source_inventory_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(json.dumps(manifest,indent=2))


if __name__ == "__main__":
    main()
