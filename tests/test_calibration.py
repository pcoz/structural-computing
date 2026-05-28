"""Tests for the optional calibration loader."""
import math

import pytest

from structural_computing import (
    apply_calibration,
    clear_calibration,
    get_calibration,
    has_calibration_for,
    predict_seconds,
)


@pytest.fixture(autouse=True)
def _reset_calibration():
    """Each test starts with an empty calibration registry."""
    clear_calibration()
    yield
    clear_calibration()


def test_empty_registry_predict_returns_none():
    assert predict_seconds("T0", "count_solutions", n=8) is None
    assert get_calibration() == {}
    assert not has_calibration_for("T0", "count_solutions")


def test_apply_calibration_loads_data():
    data = {
        ("T0", "count_solutions"): {
            "model": "power_law",
            "params": (1e-6, 3.0),
            "rms": 0.05,
        },
    }
    apply_calibration(data)
    assert has_calibration_for("T0", "count_solutions")
    # time = 1e-6 * 8^3 = 5.12e-4
    pred = predict_seconds("T0", "count_solutions", n=8)
    assert abs(pred - 1e-6 * 512) < 1e-12


def test_predict_seconds_exponential():
    apply_calibration({
        ("T4", "matching_count"): {
            "model": "exponential",
            "params": (1e-6, math.log(2)),
            "rms": 0.1,
        },
    })
    # time = 1e-6 * 2^n. n=10 -> 1.024e-3
    pred = predict_seconds("T4", "matching_count", n=10)
    assert abs(pred - 1e-6 * 1024) < 1e-9


def test_apply_calibration_validates_shape():
    with pytest.raises(TypeError):
        apply_calibration("not a dict")
    with pytest.raises(ValueError):
        apply_calibration({("T0", "x"): "not a dict"})
    with pytest.raises(ValueError):
        apply_calibration({("T0", "x"): {"model": "nope", "params": (1, 2)}})
    with pytest.raises(ValueError):
        apply_calibration({("T0", "x"): {"model": "power_law"}})       # missing params


def test_apply_calibration_overwrites_existing_keys():
    apply_calibration({
        ("T2", "matching_count"): {
            "model": "power_law", "params": (1e-9, 2.0), "rms": 0.01,
        },
    })
    apply_calibration({
        ("T2", "matching_count"): {
            "model": "power_law", "params": (5e-7, 3.0), "rms": 0.05,
        },
    })
    a, b = get_calibration()[("T2", "matching_count")]["params"]
    assert a == 5e-7
    assert b == 3.0


def test_predict_seconds_returns_non_negative():
    """Even with weird inputs, predict_seconds never returns a negative."""
    apply_calibration({
        ("T0", "x"): {"model": "power_law", "params": (1e-6, 2.0), "rms": 0.0},
    })
    assert predict_seconds("T0", "x", n=0) >= 0
    assert predict_seconds("T0", "x", n=1) >= 0
