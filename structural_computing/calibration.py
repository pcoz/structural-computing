r"""Optional per-machine cost-model calibration.

The router's default cost models are HAND-PICKED constants chosen to
give reasonable RELATIVE cost ordering between tiers. For ABSOLUTE
cost predictions on a given machine, callers can load a calibration
data file produced by the ``structural-computing-bench`` companion
repo and apply it here. After ``apply_calibration(data)``, the
function :func:`predict_seconds` returns measured-coefficient
predictions for any registered ``(tier, question)`` pair.

The calibration data structure (matches the bench repo's render output):

    CALIBRATED_COSTS = {
        ("T0", "count_solutions"): {
            "model": "power_law",
            "params": (a, b),                       # time = a * n^b
            "rms": float,
        },
        ("T4", "matching_count"): {
            "model": "exponential",
            "params": (a, b),                       # time = a * exp(b * n)
            "rms": float,
        },
        ...
    }

The router does NOT consume this data directly in v0.2; it remains
available via :func:`predict_seconds` for diagnostic / planning use.
A v0.3 deliverable wires the predictions into route-selection itself.

Usage::

    from structural_computing.calibration import apply_calibration
    from my_calibration_file import CALIBRATED_COSTS
    apply_calibration(CALIBRATED_COSTS)

    # Later:
    from structural_computing.calibration import predict_seconds
    predict_seconds("T2", "matching_count", n=16)         # -> ~0.0017 seconds

Why a separate loader (not bundled with the framework):

  * The framework should install with NO timing / measurement deps.
  * Calibration data is MACHINE-SPECIFIC; bundling a single default
    would mislead users on different hardware.
  * The bench repo can grow heavier deps (plotting, scipy fits,
    hypothesis test cases) without bloating the core.
"""
from __future__ import annotations

import math
from typing import Any, Callable, Dict, Optional, Tuple


# Module-level registry. Empty unless apply_calibration() has been called.
_REGISTRY: Dict[Tuple[str, str], Dict[str, Any]] = {}


def apply_calibration(data: Dict[Tuple[str, str], Dict[str, Any]]) -> None:
    """Load a calibration dict into the module-level registry.

    Overwrites any existing entries for matching ``(tier, question)``
    keys; preserves entries with non-matching keys. Pass an empty dict
    to leave the registry unchanged (use :func:`clear_calibration` to
    reset).

    Args:
      data: mapping ``{(tier, question): {"model": ..., "params": (a, b), ...}}``.
        The shape produced by the bench repo's ``render_calibration_module``.

    Raises:
      TypeError if `data` is not a dict.
      ValueError if any entry is malformed (missing model / params).
    """
    if not isinstance(data, dict):
        raise TypeError(
            f"apply_calibration: expected dict, got {type(data).__name__}"
        )
    for key, value in data.items():
        if not isinstance(value, dict):
            raise ValueError(
                f"apply_calibration: entry {key} is not a dict (got {type(value).__name__})"
            )
        if "model" not in value or "params" not in value:
            raise ValueError(
                f"apply_calibration: entry {key} missing 'model' or 'params'"
            )
        if value["model"] not in ("power_law", "exponential"):
            raise ValueError(
                f"apply_calibration: unsupported model '{value['model']}' for {key}"
            )
        params = value["params"]
        if not (isinstance(params, (tuple, list)) and len(params) == 2):
            raise ValueError(
                f"apply_calibration: entry {key} 'params' must be a length-2 tuple"
            )
        _REGISTRY[tuple(key)] = dict(value)


def clear_calibration() -> None:
    """Reset the calibration registry to empty."""
    _REGISTRY.clear()


def get_calibration() -> Dict[Tuple[str, str], Dict[str, Any]]:
    """Return a shallow copy of the current registry."""
    return dict(_REGISTRY)


def has_calibration_for(tier: str, question: str) -> bool:
    """Whether a calibration entry exists for the given ``(tier, question)``."""
    return (tier, question) in _REGISTRY


def predict_seconds(tier: str, question: str, *, n: int) -> Optional[float]:
    """Predict the wall-clock cost of running the ``(tier, question)``
    leaf evaluator on a problem of size ``n``, using the calibrated
    model. Returns ``None`` if no calibration is loaded for this
    ``(tier, question)``.

    Args:
      tier: e.g. ``"T0"``, ``"T2"``, ``"T4"``.
      question: e.g. ``"matching_count"``, ``"count_solutions"``.
      n: problem size (interpretation depends on the leaf evaluator;
        for graphs it's typically |V|, for constraint sets it's the
        number of variables, for signatures it's the arity).

    Returns:
      Predicted seconds (always >= 0), or None if no calibration is
      registered for this ``(tier, question)``.
    """
    entry = _REGISTRY.get((tier, question))
    if entry is None:
        return None
    a, b = entry["params"]
    model = entry["model"]
    if model == "power_law":
        # time = a * n^b
        return float(max(a * max(n, 1) ** b, 0.0))
    if model == "exponential":
        # time = a * exp(b * n)
        return float(max(a * math.exp(b * n), 0.0))
    return None                                  # pragma: no cover


__all__ = [
    "apply_calibration",
    "clear_calibration",
    "get_calibration",
    "has_calibration_for",
    "predict_seconds",
]
