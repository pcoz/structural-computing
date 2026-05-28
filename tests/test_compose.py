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


def test_holographic_basis_pair_transform_identity_signature():
    """Identity basis on a signature returns the same signature."""
    hbp = HolographicBasisPair(basis_matrix=np.eye(2))
    r = hbp.transform_signature([1, 0, 1, 0])
    assert [round(v, 9) for v in r.values] == [1, 0, 1, 0]
    assert r.is_realisable is True


def test_holographic_basis_pair_hadamard_on_3and():
    """The 3-AND signature [1, 0, 0, 1] is matchgate-realisable on some
    basis (Cai-Lu 2011 Theorem 2.5 -- every arity-3 signature is, since
    the order-2 recurrence over 4 values has 2 equations in 3 unknowns).
    The Hadamard basis makes the realising form concrete: it transforms
    the signature to [0, 2, 0, 2], which is the standard-basis matchgate
    form (alternating-zero with geometric progression on the non-zero
    indices)."""
    T = np.array([[1, 1], [1, -1]], dtype=float)
    hbp = HolographicBasisPair(basis_matrix=T)
    r = hbp.transform_signature([1, 0, 0, 1])
    # Transformed values: [0, 2, 0, 2] (matchgate-standard form).
    assert [round(v, 9) for v in r.values] == [0, 2, 0, 2]
    assert r.is_realisable is True


def test_holographic_basis_pair_rejects_truly_non_realisable_signature():
    """At arity 4 the recurrence matrix is 3x3, so signatures with rank-3
    matrices are NOT matchgate-realisable on any basis. Example: the
    arity-4 signature [1, 0, 1, 0, 2] -- the 3x3 recurrence matrix has
    determinant 1, so rank 3, so not realisable."""
    hbp = HolographicBasisPair(basis_matrix=np.eye(2))
    r = hbp.transform_signature([1, 0, 1, 0, 2])
    assert r.is_realisable is False
    assert r.recurrence_coefficients is None


def test_holographic_basis_pair_nae3_realisable_as_is():
    """The NAE-3 signature [0, 1, 1, 0] is matchgate-realisable in the
    standard basis (Cai-Lu 2011 §6.1 example). The recurrence check
    confirms this without any basis transformation."""
    hbp = HolographicBasisPair(basis_matrix=np.eye(2))
    r = hbp.transform_signature([0, 1, 1, 0])
    assert r.is_realisable is True
    # The recurrence is (a, b, c) such that a z_0 + b z_1 + c z_2 = 0,
    # so b = -c (from a*0 + b*1 + c*1 = 0) and similarly. Don't pin the
    # exact coefficients (they come from SVD), just check the recurrence
    # is satisfied.
    a, b, c = r.recurrence_coefficients
    values = [0, 1, 1, 0]
    for k in range(2):
        assert abs(a * values[k] + b * values[k + 1] + c * values[k + 2]) < 1e-9


def test_holographic_basis_pair_rejects_singular_matrix():
    """A singular basis matrix raises ValueError."""
    with pytest.raises(ValueError):
        hbp = HolographicBasisPair(basis_matrix=np.ones((2, 2)))
        hbp.transform_signature([1, 0])


def test_holographic_basis_pair_evaluate_non_identity_directs_to_transform():
    """evaluate() with a non-identity basis tells the user to use
    transform_signature() directly. This keeps the orchestrator's
    contract simple while making the substantive transform reachable."""
    hbp = HolographicBasisPair(basis_matrix=np.array([[1, 1], [1, -1]]))
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
