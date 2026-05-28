"""Tests for the composition layer (`compose.py`).

Concrete compositions in v0.1:
  - LinearCombination (multi-signature linear combiner)
  - HolographicBasisPair (identity-basis no-op only)

Sketches that should raise NotImplementedError:
  - Projection, BranchSum
"""

import numpy as np
import pytest

from structural_computing import (
    LinearCombination,
    HolographicBasisPair,
    Projection,
    BranchSum,
)


# ---------------------------------------------------------------------------
# LinearCombination
# ---------------------------------------------------------------------------

def test_linear_combination_basic():
    """Two sub-problems, weights [0.5, 0.5] -> average."""
    def evaluator(p):
        return {"A": 10, "B": 20}[p]
    comp = LinearCombination(
        name="avg(A, B)",
        sub_problems=["A", "B"],
        coefficients=[0.5, 0.5],
    )
    assert comp.evaluate(evaluator) == 15.0


def test_linear_combination_three_terms():
    """Three sub-problems with non-uniform weights."""
    def evaluator(p):
        return {"x": 1, "y": 2, "z": 3}[p]
    comp = LinearCombination(
        name="custom",
        sub_problems=["x", "y", "z"],
        coefficients=[1.0, 2.0, 3.0],
    )
    # 1*1 + 2*2 + 3*3 = 14
    assert comp.evaluate(evaluator) == 14.0


def test_linear_combination_length_mismatch_raises():
    """Mismatched sub_problems / coefficients lengths raise."""
    with pytest.raises(ValueError):
        LinearCombination(name="bad",
                          sub_problems=["A", "B"],
                          coefficients=[1.0])


# ---------------------------------------------------------------------------
# HolographicBasisPair
# ---------------------------------------------------------------------------

def test_holographic_basis_pair_identity_passes_through():
    """Identity basis = no transformation. The sub_evaluator is called
    with a marker problem and the returned value passes through."""
    hbp = HolographicBasisPair(basis_matrix=np.eye(2))
    called_with = []
    def evaluator(p):
        called_with.append(p)
        return 99
    assert hbp.evaluate(evaluator) == 99
    assert called_with == [{"identity_basis": True,
                              "note": "no transformation -- evaluate signature in the natural basis"}]


def test_holographic_basis_pair_non_identity_is_v02():
    """A non-identity basis raises NotImplementedError pending Valiant 2004."""
    hbp = HolographicBasisPair(basis_matrix=np.array([[1, 1], [0, 1]]))
    with pytest.raises(NotImplementedError):
        hbp.evaluate(lambda p: 0)


def test_holographic_basis_pair_no_basis_raises():
    """No basis_matrix supplied -> ValueError."""
    hbp = HolographicBasisPair(basis_matrix=None)
    with pytest.raises(ValueError):
        hbp.evaluate(lambda p: 0)


def test_holographic_basis_pair_wrong_shape_raises():
    """A non-2x2 basis matrix raises ValueError."""
    hbp = HolographicBasisPair(basis_matrix=np.eye(3))
    with pytest.raises(ValueError):
        hbp.evaluate(lambda p: 0)


# ---------------------------------------------------------------------------
# Sketches (should remain NotImplementedError until v0.2)
# ---------------------------------------------------------------------------

def test_projection_is_a_v02_sketch():
    p = Projection()
    with pytest.raises(NotImplementedError):
        p.evaluate(lambda p: 0)


def test_branch_sum_is_a_v02_sketch():
    b = BranchSum()
    with pytest.raises(NotImplementedError):
        b.evaluate(lambda p: 0)
