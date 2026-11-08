from __future__ import annotations

import numpy as np

from tide.species import _fit_species_factors, _species_map
from utide.utilities import Bunch


def _coef(names: list[str], values: np.ndarray) -> Bunch:
    coef = Bunch()
    coef.name = np.asarray(names)
    coef.A = np.abs(values)
    coef.g = (-np.rad2deg(np.angle(values))) % 360.0
    return coef


def test_utide_doodson_species_mapping_has_expected_major_bands() -> None:
    mapped = _species_map(["SA", "O1", "M2", "M3", "Z0"])
    assert mapped == {"SA": 0, "O1": -1, "M2": 2, "M3": 3, "Z0": None}


def test_species_transfer_recovers_complex_gain_by_group() -> None:
    names = ["O1", "K1", "M2", "S2"]
    species = {"O1": -1, "K1": -1, "M2": 2, "S2": 2}
    ref_values = np.array([1.0 + 0.4j, 0.2 - 0.3j, 3.0 + 1.2j, 0.8 - 0.6j])
    factors_expected = {-1: 0.75 + 0.25j, 2: 1.2 - 0.4j}
    target_values = np.array([factors_expected[species[name]] * value for name, value in zip(names, ref_values)])
    factors, counts = _fit_species_factors(_coef(names, ref_values), _coef(names, target_values), species)
    assert counts == {-1: 2, 2: 2}
    for key in factors_expected:
        assert np.isclose(factors[key], factors_expected[key])
