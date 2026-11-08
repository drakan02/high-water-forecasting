from __future__ import annotations

import pandas as pd

from scripts.score_p12_network_2010 import _metrics, _sample_hash


def test_paired_metrics_and_hash_use_the_same_cycle_rows() -> None:
    actual = pd.Series([2.0, 4.0, None])
    forecast = pd.Series([2.1, 3.8, 5.0])
    n, mae, rmse = _metrics(actual, forecast)
    assert n == 2
    assert abs(mae - 0.15) < 1e-12
    assert round(rmse, 12) == round((0.025) ** 0.5, 12)


def test_cycle_hash_is_order_independent() -> None:
    assert _sample_hash(pd.Series(["cycle-b", "cycle-a"])) == _sample_hash(pd.Series(["cycle-a", "cycle-b"]))
