from __future__ import annotations

import numpy as np
import pandas as pd

from tide.peaks import _turning_points, extract_high_water_cycles


def _two_cycles(*, gap_at: int | None = None, plateau: bool = False) -> pd.DataFrame:
    times = pd.date_range("2020-12-31 18:00", "2021-01-02 00:00", freq="h", tz="UTC")
    a = np.interp(np.arange(len(times)), [0, 3, 9, 15, 21, 27, 30], [3, 0, 10, 0, 10, 0, 3])
    if plateau:
        a[3:5] = 0.0
    h = a.copy()
    h[10] = 12.0
    h[22] = 13.0
    valid = np.ones(len(times), dtype=bool)
    if gap_at is not None:
        valid[gap_at] = False
        h[gap_at] = np.nan
    return pd.DataFrame({"time_utc": times, "H_m": h, "A_m": a, "analysis_valid": valid})


def test_cycle_extraction_selects_observed_and_harmonic_high_waters_separately() -> None:
    peaks = extract_high_water_cycles(_two_cycles(), design_id="test", target_year=2021)

    assert len(peaks) == 2
    assert peaks["cycle_number"].tolist() == [1, 2]
    assert peaks["high_water_eligible"].all()
    assert peaks.loc[0, "A_peak_time_utc"] != peaks.loc[0, "H_peak_time_utc"]
    assert peaks.loc[0, "H_minus_A_gauge_only_m"] == 2.0
    assert peaks.loc[1, "surge_status"] == "unavailable_not_inferred"


def test_cycle_with_a_missing_gauge_sample_is_excluded_not_interpolated() -> None:
    peaks = extract_high_water_cycles(_two_cycles(gap_at=7), design_id="test", target_year=2021)

    first = peaks.iloc[0]
    assert not first["high_water_eligible"]
    assert first["gauge_valid_hourly_samples"] == first["expected_hourly_samples"] - 1
    assert np.isnan(first["H_minus_A_gauge_only_m"])
    assert first["exclusion_reason"] == "gauge_gap_in_cycle"
    assert peaks["cycle_number"].tolist() == [1, 2]


def test_low_water_plateau_uses_registered_center_and_flags_ambiguity() -> None:
    data = _two_cycles(plateau=True)
    extrema = _turning_points(data.A_m.to_numpy(), pd.DatetimeIndex(data.time_utc), kind="min")
    plateau_min = next(item for item in extrema if item["plateau_samples"] == 2)
    assert plateau_min["index"] == 3
    peaks = extract_high_water_cycles(data, design_id="test", target_year=2021)
    assert peaks["low_water_boundary_ambiguous"].any()
    assert peaks["exclusion_reason"].str.contains("plateau_earliest_center_used").any()


def test_duplicate_or_irregular_hourly_grid_is_rejected() -> None:
    data = _two_cycles()
    data.loc[1, "time_utc"] = data.loc[0, "time_utc"]
    try:
        extract_high_water_cycles(data, design_id="test", target_year=2021)
    except ValueError as error:
        assert "unique timestamps" in str(error)
    else:
        raise AssertionError("duplicate hourly timestamps must be rejected")
