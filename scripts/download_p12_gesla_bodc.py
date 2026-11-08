"""Fetch all 46 registered GESLA/BODC inventory objects without overwriting verified files."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import urllib.request

import pandas as pd


BASE_URL = "https://gesla-dataset.s3.eu-west-1.amazonaws.com/parquet_files/"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=Path("reports/network_2010/gesla_bodc_station_inventory.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw/gesla_s3"))
    args = parser.parse_args()
    inventory = pd.read_csv(args.inventory)
    sites = inventory
    if len(sites) != 46 or sites.source_id.nunique() != 46:
        raise ValueError("Expected the locked inventory of 46 unique GBR BODC objects (44 paper ports plus two extras)")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for row in sites.itertuples(index=False):
        name = f"{row.source_id}.parquet"
        destination = args.output_dir / name
        expected = str(row.sha256)
        if destination.exists():
            actual = sha256(destination)
            if actual != expected:
                raise ValueError(f"Existing file hash differs; refusing to overwrite: {destination} {actual}")
            print(f"verified existing {name} sha256={actual}", flush=True)
            continue
        temporary = destination.with_suffix(destination.suffix + ".part")
        request = urllib.request.Request(BASE_URL + name, headers={"User-Agent": "high-water-forecasting-replay/1.0"})
        with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as out:
            while block := response.read(1024 * 1024):
                out.write(block)
        actual = sha256(temporary)
        if actual != expected:
            temporary.unlink(missing_ok=True)
            raise ValueError(f"Downloaded SHA-256 mismatch for {name}: expected {expected}, got {actual}")
        temporary.replace(destination)
        print(f"downloaded {name} bytes={destination.stat().st_size} sha256={actual}", flush=True)


if __name__ == "__main__":
    main()
