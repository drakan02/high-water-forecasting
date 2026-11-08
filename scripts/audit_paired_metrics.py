"""Read persisted forecasts/labels and write independent audit metrics."""
from __future__ import annotations

import argparse
from pathlib import Path

from tide.audit_metrics import DEFAULT_OUT, run


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    detail, metrics = run(args.output_dir)
    print(metrics.to_string(index=False))
    print(f"Wrote {len(detail)} forecast/label joined rows to {args.output_dir}")
