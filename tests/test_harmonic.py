from __future__ import annotations

import numpy as np
import pandas as pd

from tide.harmonic import fit_utide


def _synthetic_tide(times: pd.DatetimeIndex) -> tuple[np.ndarray, dict[str, float]]:
    frequencies_cycles_per_hour = {
        "M2": 0.0805114007,
        "S2": 0.0833333333,
        "K1": 0.0417807462,
        "O1": 0.0387306544,
    }
    amplitudes = {"M2": 1.2, "S2": 0.4, "K1": 0.3, "O1": 0.2}
    phases_degrees = {"M2": 22.0, "S2": 135.0, "K1": -45.0, "O1": 97.0}
    elapsed_hours = (times.tz_convert("UTC") - times[0]).total_seconds().to_numpy() / 3600
    signal = np.zeros(len(times), dtype=float)
    for constituent, amplitude in amplitudes.items():
        phase = np.deg2rad(phases_degrees[constituent])
        signal += amplitude * np.cos(2 * np.pi * frequencies_cycles_per_hour[constituent] * elapsed_hours + phase)
    return signal, amplitudes


def test_utide_recovers_known_synthetic_constituents() -> None:
    times = pd.date_range("2020-01-01", periods=24 * 180, freq="h", tz="UTC")
    levels, known_amplitudes = _synthetic_tide(times)

    coef, used = fit_utide(
        times,
        levels,
        latitude=51.5,
        fit_start="2020-01-01",
        fit_end="2020-06-28",
        constit=list(known_amplitudes),
        trend=False,
        nodal=False,
        phase="raw",
    )

    recovered = dict(zip(coef.name.astype(str), coef.A))
    assert used.sum() == len(times)
    for name, expected in known_amplitudes.items():
        assert abs(recovered[name] - expected) < 1e-5


def test_chronological_fit_is_invariant_to_changed_post_cutoff_observations() -> None:
    times = pd.date_range("2000-01-01", periods=24 * 800, freq="h", tz="UTC")
    levels, _ = _synthetic_tide(times)
    cutoff = pd.Timestamp("2001-12-31 23:00", tz="UTC")
    changed = levels.copy()
    future = times > cutoff
    changed[future] += np.linspace(50, 500, int(future.sum()))
    options = dict(
        latitude=51.5,
        fit_start="2000-01-01",
        fit_end="2001-12-31",
        constit=["M2", "S2", "K1", "O1"],
        trend=False,
        nodal=False,
        phase="raw",
    )

    original_coef, original_mask = fit_utide(times, levels, **options)
    changed_coef, changed_mask = fit_utide(times, changed, **options)

    np.testing.assert_array_equal(original_mask, changed_mask)
    np.testing.assert_allclose(original_coef.A, changed_coef.A, rtol=0, atol=1e-12)
    np.testing.assert_allclose(original_coef.g, changed_coef.g, rtol=0, atol=1e-10)


def test_confidence_interval_setting_does_not_change_harmonic_coefficients() -> None:
    times = pd.date_range("2020-01-01", periods=24 * 120, freq="h", tz="UTC")
    levels, known_amplitudes = _synthetic_tide(times)
    options = dict(
        latitude=51.5,
        fit_start="2020-01-01",
        fit_end="2020-04-29",
        constit=list(known_amplitudes),
        trend=False,
        nodal=False,
        phase="raw",
    )
    with_ci, _ = fit_utide(times, levels, conf_int="linear", **options)
    without_ci, _ = fit_utide(times, levels, conf_int="none", **options)

    np.testing.assert_allclose(without_ci.A, with_ci.A, rtol=0, atol=1e-12)
    np.testing.assert_allclose(without_ci.g, with_ci.g, rtol=0, atol=1e-10)


def test_saved_utide_state_reconstructs_the_fitted_hourly_series(tmp_path) -> None:
    from utide import reconstruct

    from tide.harmonic import _utc_naive, reconstruct_from_saved_state, save_reconstruction_state

    times = pd.date_range("2020-01-01", periods=24 * 120, freq="h", tz="UTC")
    levels, known_amplitudes = _synthetic_tide(times)
    coef, used = fit_utide(
        times,
        levels,
        latitude=51.5,
        fit_start="2020-01-01",
        fit_end="2020-04-29",
        constit=list(known_amplitudes),
        trend=True,
        nodal=True,
        phase="Greenwich",
        conf_int="none",
    )
    assert used.all()
    path = save_reconstruction_state(coef, tmp_path / "utide_reconstruction_state.json", design_id="test", model_id="UTide-0.4.0")
    direct = reconstruct(_utc_naive(times), coef, verbose=False).h
    replayed = reconstruct_from_saved_state(times, path)

    np.testing.assert_allclose(replayed, direct, rtol=0, atol=1e-12)
