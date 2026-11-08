"""Replay P1-P6 into a fresh output root with the accepted raw source and configs."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import yaml

ROOT = Path(__file__).resolve().parents[1]
REPLAY = ROOT / "data/p7_replay"
CONFIGS = REPLAY / "configs"
LOGS = ROOT / "reports/p7_replay/logs"


def _save(name: str, config: dict) -> Path:
    CONFIGS.mkdir(parents=True, exist_ok=True)
    path = CONFIGS / name
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return path


def _run(name: str, args: list[str], env: dict[str, str], records: list[dict]) -> None:
    start = time.time()
    result = subprocess.run(args, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    log_path = LOGS / f"{name}.log"
    log_path.write_text(result.stdout, encoding="utf-8")
    records.append({"step": name, "command": args, "return_code": result.returncode,
                    "elapsed_seconds": round(time.time() - start, 3), "log": str(log_path.relative_to(ROOT)),
                    "log_sha256": hashlib.sha256(log_path.read_bytes()).hexdigest()})
    if result.returncode:
        raise RuntimeError(f"Replay step {name} failed ({result.returncode}); see {log_path}")


def run(replay_root: Path = REPLAY, logs_dir: Path = LOGS,
        manifest_path: Path = ROOT / "reports/p7_replay/run_manifest.json") -> dict:
    global REPLAY, CONFIGS, LOGS
    REPLAY = replay_root if replay_root.is_absolute() else ROOT / replay_root
    LOGS = logs_dir if logs_dir.is_absolute() else ROOT / logs_dir
    manifest_path = manifest_path if manifest_path.is_absolute() else ROOT / manifest_path
    CONFIGS = REPLAY / "configs"
    REPLAY.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.setdefault("UV_CACHE_DIR", "/tmp/uv-cache")
    env.setdefault("MPLCONFIGDIR", "/tmp/mpl-cache")
    env["OPENBLAS_NUM_THREADS"] = "1"
    env["OMP_NUM_THREADS"] = "1"
    env["MKL_NUM_THREADS"] = "1"
    records: list[dict] = []

    base = yaml.safe_load((ROOT / "configs/avonmouth.yaml").read_text(encoding="utf-8"))
    base["sources"]["gauge"]["clean_dir"] = str(REPLAY / "p1")
    base["sources"]["gauge"]["figure_path"] = str(REPLAY / "p1/first_14_days.png")
    base_path = _save("avonmouth.yaml", base)
    _run("P1_ingest", [sys.executable, "-u", "-m", "tide", "ingest", "--config", str(base_path)], env, records)
    _run("P1_prepare", [sys.executable, "-u", "-m", "tide", "prepare", "--config", str(base_path)], env, records)

    p2_paths = {}
    for design, original in (
        ("chronological_fit_through_2004", "p2_gauge_only_chronological.yaml"),
        ("retrospective_1988_2007", "p2_gauge_only_retrospective.yaml"),
    ):
        config = yaml.safe_load((ROOT / "configs" / original).read_text(encoding="utf-8"))
        config["base_config"] = str(base_path)
        config["harmonic_design"]["output_dir"] = str(REPLAY / "p2" / design)
        path = _save(f"{design}.yaml", config)
        p2_paths[design] = path
        _run(f"P2_{design}", [sys.executable, "-u", "scripts/run_harmonic_guarded.py", "--config", str(path)], env, records)

    p3 = yaml.safe_load((ROOT / "configs/p3_peaks.yaml").read_text(encoding="utf-8"))
    p3["base_config"] = str(base_path)
    p3["design_configs"] = [str(p2_paths[k]) for k in p2_paths]
    p3["output_dir"] = str(REPLAY / "p3")
    p3_path = _save("p3_peaks.yaml", p3)
    _run("P3_peaks", [sys.executable, "-u", "-m", "tide", "peaks", "--config", str(p3_path)], env, records)

    p4 = yaml.safe_load((ROOT / "configs/p4_ecm_gauge_only.yaml").read_text(encoding="utf-8"))
    p4["output_dir"] = str(REPLAY / "p4")
    for design in p4["designs"]:
        design["high_water_context"] = str(REPLAY / "p3" / design["design_id"] / "high_water_context.parquet")
    p4_path = _save("p4_ecm.yaml", p4)
    _run("P4_ecm", [sys.executable, "-u", "-m", "tide", "ecm", "--config", str(p4_path)], env, records)

    transfer = yaml.safe_load((ROOT / "configs/p5_transfer_2010.yaml").read_text(encoding="utf-8"))
    transfer["output_dir"] = str(REPLAY / "p5_transfer")
    transfer_path = _save("p5_transfer_2010.yaml", transfer)
    _run("P5_transfer_2010", [sys.executable, "-u", "scripts/run_harmonic_guarded.py", "--tide-command", "transfer-2010", "--config", str(transfer_path)], env, records)

    ecm = yaml.safe_load((ROOT / "configs/p5_transfer_2010_ecm.yaml").read_text(encoding="utf-8"))
    ecm["output_dir"] = str(REPLAY / "p5_transfer/ecm")
    ecm["designs"][0]["high_water_context"] = str(REPLAY / "p5_transfer/high_water_context.parquet")
    ecm_path = _save("p5_transfer_2010_ecm.yaml", ecm)
    _run("P5_transfer_ecm", [sys.executable, "-u", "-m", "tide", "ecm", "--config", str(ecm_path)], env, records)

    evaluation = yaml.safe_load((ROOT / "configs/p5_evaluation.yaml").read_text(encoding="utf-8"))
    evaluation["output_dir"] = str(REPLAY / "p5_evaluation")
    for design in evaluation["designs"]:
        design_id = design["design_id"]
        if design_id == "chronological_fit_through_2004":
            design["forecast_path"] = str(REPLAY / "p4" / design_id / "forecasts_unscored.parquet")
            design["labels_path"] = str(REPLAY / "p3" / design_id / "high_water_context.parquet")
        elif design_id == "retrospective_1988_2007":
            design["forecast_path"] = str(REPLAY / "p4" / design_id / "forecasts_unscored.parquet")
            design["labels_path"] = str(REPLAY / "p3" / design_id / "high_water.parquet")
        else:
            design["forecast_path"] = str(REPLAY / "p5_transfer/ecm" / design_id / "forecasts_unscored.parquet")
            design["labels_path"] = str(REPLAY / "p5_transfer/high_water_2010.parquet")
    evaluation_path = _save("p5_evaluation.yaml", evaluation)
    _run("P5_evaluate", [sys.executable, "-u", "-m", "tide", "evaluate", "--config", str(evaluation_path)], env, records)

    _run("P6_build", [sys.executable, "-u", "scripts/build_powerbi_handoff.py", "--output-dir", str(REPLAY / "bi_handoff"),
                       "--p5-root", str(REPLAY / "p5_evaluation"), "--p1-hourly", str(REPLAY / "p1/hourly.parquet"),
                       "--p2-root", str(REPLAY / "p2")], env, records)
    _run("P6_validate", [sys.executable, "-u", "scripts/validate_powerbi_handoff.py", "--bi-root", str(REPLAY / "bi_handoff"),
                         "--p5-root", str(REPLAY / "p5_evaluation"), "--report-path", str(LOGS.parent / "bi_validation.csv")], env, records)
    _run("P7_tests", [sys.executable, "-u", "-m", "pytest", "-q"], env, records)

    raw_path = ROOT / "data/raw/gesla_s3/avonmouth-avo-gbr-bodc.parquet"
    source_hash = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    version_names = ("numpy", "pandas", "scipy", "UTide", "pyarrow", "matplotlib", "pytest")
    versions = {name: importlib.metadata.version(name) for name in version_names}
    config_hashes = {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((ROOT / "configs").glob("*.yaml"))
    }
    lock_path = ROOT / "uv.lock"
    summary = {"raw_source": str(raw_path.relative_to(ROOT)), "raw_sha256": source_hash,
               "python": sys.version, "package_versions": versions, "config_sha256": config_hashes,
               "uv_lock_sha256": hashlib.sha256(lock_path.read_bytes()).hexdigest(),
               "steps": records, "replay_root": str(REPLAY.relative_to(ROOT))}
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay-root", type=Path, default=REPLAY)
    parser.add_argument("--logs-dir", type=Path, default=LOGS)
    parser.add_argument("--manifest-path", type=Path, default=ROOT / "reports/p7_replay/run_manifest.json")
    args = parser.parse_args()
    print(json.dumps(run(args.replay_root, args.logs_dir, args.manifest_path), indent=2))
