from __future__ import annotations

import numpy as np

import pandas as pd

from tide.ann import _common_cycle_ids, _forward, _initial_params, _objective_and_gradient


def test_ann_gradient_matches_finite_difference() -> None:
    rng = np.random.default_rng(18)
    x = rng.normal(size=(5, 7))
    y = rng.normal(size=5)
    params = _initial_params(7, 19)
    loss, gradient = _objective_and_gradient(params, x, y, 0.01)
    assert np.isfinite(loss)
    for index in (0, 3, 37, len(params) - 1):
        step = 1e-6
        plus = params.copy(); plus[index] += step
        minus = params.copy(); minus[index] -= step
        numeric = (
            _objective_and_gradient(plus, x, y, 0.01)[0]
            - _objective_and_gradient(minus, x, y, 0.01)[0]
        ) / (2 * step)
        assert np.isclose(gradient[index], numeric, rtol=2e-4, atol=2e-6)


def test_ann_forward_is_finite_and_scalar_per_row() -> None:
    x = np.zeros((4, 9))
    params = _initial_params(9, 5)
    y = _forward(params, x)
    assert y.shape == (4,)
    assert np.isfinite(y).all()


def test_peak_metrics_use_only_shared_forecastable_cycle_ids() -> None:
    detail = pd.DataFrame({
        "cycle_id": ["a", "a", "b", "b", "c"],
        "model_id": ["ANN", "UTide", "ANN", "UTide", "ANN"],
        "high_water_eligible": [True] * 5,
        "error_total_H_m": [0.1, 0.2, 0.3, float("nan"), 0.4],
    })
    assert list(_common_cycle_ids(detail)) == ["a"]
