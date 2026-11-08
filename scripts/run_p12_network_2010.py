"""Run sequential, resource-guarded UTide and 2006–09 ECM fits for the 44 paper ports."""
from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path
import re
import subprocess
import sys

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _run(command: list[str], *, env: dict[str, str], log: Path, timeout: int) -> tuple[int, str]:
    log.parent.mkdir(parents=True, exist_ok=True)
    try:
        with log.open("w", encoding="utf-8") as stream:
            result = subprocess.run(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout, check=False)
        return result.returncode, "" if result.returncode == 0 else f"exit_{result.returncode}; see {log}"
    except subprocess.TimeoutExpired:
        return 124, f"timeout_after_{timeout}s; see {log}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/p12_network_2010.yaml"))
    args = parser.parse_args()
    cfg = yaml.safe_load((ROOT / args.config).read_text(encoding="utf-8"))
    inventory = pd.read_csv(ROOT / cfg["inventory_csv"])
    sites = inventory.loc[inventory["paper_match"].eq("matched")].sort_values("paper_port_number")
    if len(sites) != 44 or sites["paper_port_number"].astype(int).nunique() != 44:
        raise ValueError(f"Expected 44 unique matched paper ports, got {len(sites)}")
    output = ROOT / cfg["output_dir"]
    output.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
        env[name] = "1"
    env.setdefault("MPLCONFIGDIR", "/tmp/mpl-cache")
    results=[]
    for row in sites.itertuples(index=False):
        port=int(row.paper_port_number)
        station_key=f"p{port:02d}_{slug(row.paper_station)}"
        station_dir=output/station_key
        first=pd.Timestamp(row.source_start_utc).tz_localize("UTC") if pd.Timestamp(row.source_start_utc).tzinfo is None else pd.Timestamp(row.source_start_utc).tz_convert("UTC")
        fit_start=max(first.normalize(),pd.Timestamp(cfg["fit_start_floor"],tz="UTC"))
        fit_start_text=fit_start.strftime("%Y-%m-%d")
        context_start=max(int(cfg["context_start_floor_year"]),int(first.year))
        available_fit_years=[year for year in cfg["ecm_fit_years"] if int(getattr(row,f"y{year}_rows_present"))>0]
        design_id=f"{station_key}_network_2010_fit_{fit_start.year}_2009"
        utide_out=Path(cfg["output_dir"])/station_key/"utide"
        transfer={
            "raw_file":str(row.local_file),"expected_station":str(row.site_name),"expected_country":"GBR",
            "expected_source_ids":[str(row.source_id)],"station_id":station_key,"design_id":design_id,
            "target_year":int(cfg["score_year"]),"fit_start":fit_start_text,"fit_end":cfg["fit_end"],
            "constituents":"auto","trend":True,"nodal_corrections":True,"phase_convention":"Greenwich",
            "confidence_intervals":"none","context_start_year":context_start,"context_end_year":int(cfg["context_end_year"]),
            "minimum_cycle_hours":8,"maximum_cycle_hours":16,"output_dir":str(utide_out),
        }
        transfer_config=station_dir/"transfer_2010.yaml"
        transfer_config.parent.mkdir(parents=True,exist_ok=True)
        transfer_config.write_text(yaml.safe_dump(transfer,sort_keys=False),encoding="utf-8")
        utide_log=station_dir/"utide_guarded.log"
        utide_command=[sys.executable,"scripts/run_harmonic_guarded.py","--tide-command","transfer-2010","--config",str(transfer_config.relative_to(ROOT)),"--max-rss-gib",str(cfg["max_rss_gib"]),"--min-available-gib",str(cfg["min_available_gib"]),"--timeout-minutes",str(cfg["timeout_minutes"]),"--log",str(utide_log)]
        utide_rc,utide_error=_run(utide_command,env=env,log=utide_log,timeout=int(float(cfg["timeout_minutes"])*60+120))
        result={"paper_port_number":port,"paper_station":row.paper_station,"station_id":station_key,"source_id":row.source_id,"source_sha256":row.sha256,"fit_start":fit_start_text,"fit_end":cfg["fit_end"],"context_start_year":context_start,"harmonic_status":"DONE" if utide_rc==0 else "FAILED","harmonic_exit_code":utide_rc,"harmonic_error":utide_error,"ecm_fit_years":";".join(map(str,available_fit_years)),"ecm_status":"NOT_RUN","ecm_error":""}
        if utide_rc==0:
            if port in (22,41):
                result["ecm_status"]="NOT_APPLICABLE_PER_PAPER"
                result["ecm_error"]="paper reports multiple high/low waters per day; ECM not applied"
            elif not available_fit_years:
                result["ecm_status"]="BLOCKED_NO_TRAINING_YEARS"
                result["ecm_error"]="No source rows in configured 2006-2009 ECM fit years"
            else:
                design_base=f"{station_key}_ecm_fit_{available_fit_years[0]}_{available_fit_years[-1]}"
                context=str(utide_out/"high_water_context.parquet")
                score_years=[y for y in available_fit_years if y <= 2009]
                ecm={"output_dir":str(Path(cfg["output_dir"])/station_key/"ecm"),"issue_lead_hours":float(cfg["issue_lead_hours"]),"lag_steps":[int(x) for x in cfg["lag_steps"]],"minimum_fit_rows":int(cfg["minimum_fit_rows"]),"designs":[
                    {"design_id":f"{station_key}_network_2010_fit_{available_fit_years[0]}_{available_fit_years[-1]}","mode":"frozen_transfer","high_water_context":context,"fit_years":available_fit_years,"score_year":int(cfg["score_year"])},
                    {"design_id":f"{station_key}_retrospective_2006_2009_fit_{available_fit_years[0]}_{available_fit_years[-1]}","mode":"retrospective","high_water_context":context,"fit_years":available_fit_years,"score_years":score_years},
                ]}
                ecm_config=station_dir/"ecm.yaml"
                ecm_config.write_text(yaml.safe_dump(ecm,sort_keys=False),encoding="utf-8")
                ecm_log=station_dir/"ecm.log"
                ecm_rc,ecm_error=_run([sys.executable,"-m","tide","ecm","--config",str(ecm_config.relative_to(ROOT))],env=env,log=ecm_log,timeout=900)
                result["ecm_status"]="DONE" if ecm_rc==0 else "FAILED"
                result["ecm_error"]=ecm_error
                if ecm_rc==0:
                    result["ecm_model_count"]=2
                    result["ecm_fit_design_id"]=design_base
        results.append(result)
        print(f"P{port:02d} {row.paper_station}: UTide={result['harmonic_status']} ECM={result['ecm_status']}",flush=True)
        pd.DataFrame(results).to_csv(output/"run_status.csv",index=False)
    pd.DataFrame(results).to_csv(output/"run_status.csv",index=False)
    print(f"Completed {len(results)} paper ports; failures={(pd.DataFrame(results).harmonic_status!='DONE').sum()} harmonic / {(pd.DataFrame(results).ecm_status=='FAILED').sum()} ECM")


if __name__ == "__main__":
    main()
