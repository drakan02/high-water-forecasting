"""Small command line interface for P1 ingestion and preparation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import yaml

from .ingest import raw_manifest, read_gesla_parquet
from .harmonic import audit_history, run_harmonic
from .prepare import prepare


def ingest(config_path: Path) -> dict[str, object]:
    config = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    source = config["sources"]["gauge"]
    raw_path = Path(source["raw_file"])
    frame, identity = read_gesla_parquet(raw_path)
    manifest_path = Path(source["clean_dir"]) / "raw_manifest.csv"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([raw_manifest(raw_path, frame, identity)]).to_csv(manifest_path, index=False)
    return {
        "station": identity.station,
        "source_rows": identity.source_rows,
        "first_time_utc": identity.first_time_utc.isoformat(),
        "last_time_utc": identity.last_time_utc.isoformat(),
        "manifest_csv": str(manifest_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(prog="tide")
    subparsers = parser.add_subparsers(dest="command", required=True)
    ingest_parser = subparsers.add_parser("ingest", help="verify local raw source and write manifest")
    ingest_parser.add_argument("--config", type=Path, required=True)
    prepare_parser = subparsers.add_parser("prepare", help="prepare exact-minute-00 hourly data")
    prepare_parser.add_argument("--config", type=Path, required=True)
    audit_parser = subparsers.add_parser("audit-history", help="audit full-file yearly coverage and Parquet metadata")
    audit_parser.add_argument("--config", type=Path, required=True)
    audit_parser.add_argument("--out-dir", type=Path, default=Path("reports/p2_data_audit"))
    harmonic_parser = subparsers.add_parser("harmonic", help="fit and reconstruct one configured UTide baseline")
    harmonic_parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "ingest":
        result = ingest(args.config)
    elif args.command == "prepare":
        result = prepare(args.config)
    elif args.command == "audit-history":
        config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
        result = audit_history(Path(config["sources"]["gauge"]["raw_file"]), args.out_dir)
    else:
        result = run_harmonic(args.config)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
