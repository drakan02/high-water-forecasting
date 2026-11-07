"""Write hourly QC products and a source-versus-hourly diagnostic figure."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import yaml

from .ingest import monthly_quality, prepare_hourly, read_gesla_parquet, raw_manifest


def prepare(config_path: Path) -> dict[str, object]:
    config_path = Path(config_path)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    year = int(config["station"]["primary_period"][0].year)
    raw_path = Path(config["sources"]["gauge"]["raw_file"])
    output = Path(config["sources"]["gauge"]["clean_dir"])
    figure_path = Path(config["sources"]["gauge"]["figure_path"])

    frame, identity = read_gesla_parquet(raw_path)
    hourly, counts = prepare_hourly(frame, year)
    monthly = monthly_quality(frame, hourly, year)

    output.mkdir(parents=True, exist_ok=True)
    figure_path.parent.mkdir(parents=True, exist_ok=True)
    hourly_path = output / "hourly.parquet"
    qc_path = output / "qc_by_station_month.csv"
    manifest_path = output / "raw_manifest.csv"
    hourly.to_parquet(hourly_path, index=False)
    monthly.to_csv(qc_path, index=False)
    pd.DataFrame([raw_manifest(raw_path, frame, identity)]).to_csv(manifest_path, index=False)

    start = pd.Timestamp(year=year, month=1, day=1, tz="UTC")
    end = start + pd.Timedelta(days=14)
    raw_times = pd.to_datetime(frame["date_time"], utc=True)
    raw_mask = raw_times.ge(start) & raw_times.lt(end)
    hourly_times = pd.to_datetime(hourly["time_utc"], utc=True)
    hourly_mask = hourly_times.ge(start) & hourly_times.lt(end)

    fig, ax = plt.subplots(figsize=(14, 5))
    ax.plot(raw_times[raw_mask], frame.loc[raw_mask, "sea_level"], color="#96a3ad", linewidth=0.7, label="GESLA raw 15-minute values")
    ax.plot(hourly_times[hourly_mask], hourly.loc[hourly_mask, "level_m"], color="#087e8b", linewidth=1.2, marker=".", markersize=2, label="Valid exact-minute-00 hourly sample")
    excluded = hourly_mask & ~hourly["analysis_valid"]
    ax.scatter(hourly_times[excluded], hourly.loc[excluded, "level_m_raw"], color="#d1495b", marker="x", s=18, label="Minute-00 value excluded by QC policy")
    ax.set_title(f"Avonmouth {year}: source observations and exact-minute-00 hourly values (first 14 days)")
    ax.set_ylabel("Sea level (m; source datum unspecified)")
    ax.set_xlabel("Timestamp (UTC)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b\n%H:%M", tz=mdates.UTC))
    ax.grid(alpha=0.2)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(figure_path, dpi=160)
    plt.close(fig)

    return {
        **counts,
        "source_rows_for_year_expected": 35040 if year == 2007 else None,
        "source_rows_for_year_present": int(frame["year"].eq(year).sum()),
        "source_year_qc1_count": int(frame.loc[frame["year"].eq(year), "qc_flag"].eq(1).sum()),
        "source_year_qc2_interpolated_count": int(frame.loc[frame["year"].eq(year), "qc_flag"].eq(2).sum()),
        "hourly_parquet": str(hourly_path),
        "monthly_qc_csv": str(qc_path),
        "manifest_csv": str(manifest_path),
        "figure": str(figure_path),
    }
