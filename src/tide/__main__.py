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
from .peaks import run_peak_cycles
from .empirical import run_empirical
from .evaluate import run_evaluation
from .transfer import run_transfer_2010
from .ann import run_ann
from .species import run_species


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
    peaks_parser = subparsers.add_parser("peaks", help="extract stable gauge-only semi-diurnal high-water cycles")
    peaks_parser.add_argument("--config", type=Path, required=True)
    ecm_parser = subparsers.add_parser("ecm", help="fit and issue gauge-only high-water ECM forecasts")
    ecm_parser.add_argument("--config", type=Path, required=True)
    evaluate_parser = subparsers.add_parser("evaluate", help="join frozen forecasts to labels and calculate paired peak metrics")
    evaluate_parser.add_argument("--config", type=Path, required=True)
    transfer_parser = subparsers.add_parser("transfer-2010", help="build frozen-through-2009 gauge-only 2010 transfer forecasts")
    transfer_parser.add_argument("--config", type=Path, required=True)
    ann_parser = subparsers.add_parser("ann", help="fit a registered gauge-only ANN substitute and score hourly/high-water outputs")
    ann_parser.add_argument("--config", type=Path, required=True)
    species_parser = subparsers.add_parser("species", help="fit a Newlyn species-banded harmonic-transfer substitute")
    species_parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "ingest":
        result = ingest(args.config)
    elif args.command == "prepare":
        result = prepare(args.config)
    elif args.command == "audit-history":
        config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
        result = audit_history(Path(config["sources"]["gauge"]["raw_file"]), args.out_dir)
    elif args.command == "harmonic":
        result = run_harmonic(args.config)
    elif args.command == "peaks":
        result = run_peak_cycles(args.config)
    elif args.command == "ecm":
        result = run_empirical(args.config)
    elif args.command == "evaluate":
        result = run_evaluation(args.config)
    elif args.command == "ann":
        result = run_ann(args.config)
    elif args.command == "species":
        result = run_species(args.config)
    else:
        result = run_transfer_2010(args.config)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
