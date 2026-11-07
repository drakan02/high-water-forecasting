# High Water Forecasting — P0 source decision

P0 audit for the Avonmouth 2007 pilot in Hibbert et al. (2015). Current branch: `phase/P0-avonmouth-source-audit`. This phase selects the feasible gauge-only path; it does not claim a direct Table 1b replication.

## P0 decision

A real 2007 Avonmouth gauge record is available in the public GESLA S3 Parquet mirror with BODC provider lineage. The selected object is `parquet_files/avonmouth-avo-gbr-bodc.parquet`; the separate CMEMS object and Avonmouth Portbury station were not substituted. The underlying GESLA release is not declared by the object.

The exact station record is `site_name=Avonmouth`, `country=GBR`, coordinates 51.50775 N, 2.71275 W. The BODC original series coordinates are slightly different (51.51089 N, 2.71497 W). GESLA has one BODC-lineage record but no original primary/secondary channel ID. Its Parquet timestamp is timezone-naive physically; GESLA documents UTC. `sea_level` is in metres; datum is unspecified in the object. Do not convert datum or assert primary/secondary identity without provider confirmation.

For 2007 the actual record runs 2007-01-01 00:00 through 2007-12-31 23:45 UTC, with 35,040 15-minute rows; 35,030 are `qc_flag=1` and `use_flag=1`, while 10 have `qc_flag=2` (interpolated). The GESLA object size is 5,180,521 bytes and SHA-256 is `7a796fcb64215becd2fb429b75a48be5afcb392c613a7f54e509c36250e71bb8`. This was checked from the actual file, not inferred from catalog coverage.

GESLA's current license page lists BODC records as permitted for research and consultancy and asks users to observe provider-specific conditions. Because this S3 object's release is undeclared, use it for local research, cite GESLA and its required papers, and do not redistribute the raw object. [GESLA license](https://gesla787883612.wordpress.com/license/) · [GESLA downloads and citations](https://gesla787883612.wordpress.com/downloads/) · [BODC series metadata](https://www.bodc.ac.uk/data/documents/series/303295/).

**Selected experimental branch: `gauge_only`.** This satisfies the P0 source decision for a real gauge-only analysis. The direct Table 1b branch remains blocked: the 2007 hourly CS3X residual surge and its Avonmouth grid-cell mapping have not been obtained. NTSLF's skew-surge top-events page is not the missing residual time series. Do not derive surge as H−A. The NOC request remains a draft at `reports/data_request_draft.md`. [NOC CS3/CS3X format](https://noc.ac.uk/files/documents/business/CS3-92on-format-info.pdf).

## Recheck the selected source

Run from the repository root after installing `pyarrow` and `pandas` into a Python environment:

```bash
python3 - <<'PY'
from pathlib import Path
import hashlib
import pandas as pd
import pyarrow.parquet as pq
p = Path("data/raw/gesla_s3/avonmouth-avo-gbr-bodc.parquet")
expected = "7a796fcb64215becd2fb429b75a48be5afcb392c613a7f54e509c36250e71bb8"
assert hashlib.sha256(p.read_bytes()).hexdigest() == expected
d = pd.read_parquet(p)
y = d[(d.site_name == "Avonmouth") & (d.country == "GBR") & (d.year == 2007)]
assert len(y) == 35040
assert str(pq.read_schema(p).field("date_time").type) == "timestamp[us]"
print(len(d), y.date_time.min(), y.date_time.max(), y.qc_flag.value_counts().sort_index().to_dict())
PY
```

The P0 inventory and explicit distinction between the gauge-only decision and the blocked Table 1b route are in `data/source_inventory.csv`, `reports/access_decision.md`, `docs/paper_map.csv`, and `reports/status.csv`.
