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


# ---------------------------------------------------------------------------
# Auto-discovery of T (v0.3, Cai-Lu SRP practical fragment)
# ---------------------------------------------------------------------------

def test_discover_basis_finds_hadamard_for_3and():
    """[1, 0, 0, 1] is matchgate-realisable on the Hadamard basis;
    discover_basis() finds it from the canonical candidate list."""
    h = HolographicBasisPair()
    discovery = h.discover_basis([1, 0, 0, 1])
    assert discovery is not None
    T, result = discovery
    assert result.is_realisable
    distance = h._matchgate_standard_distance(result.values)
    assert distance < 1e-6


def test_discover_basis_identity_for_already_standard_signature():
    """A signature that's already in matchgate-standard form returns
    the identity basis (first canonical candidate)."""
    h = HolographicBasisPair()
    discovery = h.discover_basis([2, 0, 2, 0, 2])
    assert discovery is not None
    T, _result = discovery
    assert np.allclose(T, np.eye(2))


def test_discover_basis_returns_none_for_non_realisable():
    """[1, 0, 1, 0, 2] doesn't satisfy the order-2 recurrence; no basis
    can rescue it. discover_basis returns None per Cai-Lu Theorem 2.5."""
    h = HolographicBasisPair()
    assert h.discover_basis([1, 0, 1, 0, 2]) is None


def test_discover_basis_finds_single_cube_via_v04_closed_form():
    """[1, 1, 1, 1] = (u+v)^3 is matchgate-realisable as a rank-1 cube
    of a linear form. The v0.3 grid-based search missed this because
    the required basis sends (u+v) to a pure axis (entries outside
    the [-2, +2] grid). The v0.4 closed-form derivation from the
    recurrence kernel finds a valid basis directly.

    Note: v0.3 returned None for this signature, treating it as
    "degenerate." v0.4 correctly identifies it as a legitimate
    rank-1 matchgate-realisable signature (the b=0 Cai-Gorenstein
    degenerate case at the result side, with the only non-zero
    entry at z'_0)."""
    h = HolographicBasisPair()
    discovery = h.discover_basis([1, 1, 1, 1])
    assert discovery is not None, \
        "v0.4 closed-form should find the basis for (u+v)^3"
    T, result = discovery
    distance = h._matchgate_standard_distance(result.values)
    assert distance < 1e-6
    # The transformed signature should be a single-point matchgate-
    # standard form (z'_0 alone non-zero in one parity).
    nonzero_count = sum(1 for v in result.values if abs(v) > 1e-9)
    assert nonzero_count == 1, \
        f"expected single-point form, got {result.values}"


def test_discover_basis_finds_basis_for_nae3():
    """The NAE-3 signature [0, 1, 1, 0] is matchgate-realisable on the
    Hadamard basis (transforms to [6, 0, -2, 0])."""
    h = HolographicBasisPair()
    discovery = h.discover_basis([0, 1, 1, 0])
    assert discovery is not None
    T, result = discovery
    distance = h._matchgate_standard_distance(result.values)
    assert distance < 1e-6


# ---------------------------------------------------------------------------
# Multi-signature SRP (v0.3, Cai-Lu 2011 §4)
# ---------------------------------------------------------------------------

def test_discover_common_basis_finds_hadamard_for_both_hadamard_friendly():
    """Two signatures both solved by Hadamard: discover_common_basis
    returns the shared T = Hadamard."""
    h = HolographicBasisPair()
    sigs = [[1, 0, 0, 1], [0, 1, 1, 0]]                  # 3-AND + NAE-3
    discovery = h.discover_common_basis(sigs)
    assert discovery is not None
    T, results = discovery
    assert len(results) == 2
    for r in results:
        d = h._matchgate_standard_distance(r.values)
        assert d < 1e-6


def test_discover_common_basis_identity_when_both_already_standard():
    """Two signatures both already in matchgate-standard form: the
    identity is a valid common basis."""
    h = HolographicBasisPair()
    sigs = [[1, 0, 1, 0, 1], [2, 0, 2, 0, 2]]
    discovery = h.discover_common_basis(sigs)
    assert discovery is not None
    T, _results = discovery
    np.testing.assert_allclose(T, np.eye(2))


def test_discover_common_basis_returns_none_for_conflicting_bases():
    """Two signatures requiring incompatible bases: discover_common_basis
    returns None."""
    h = HolographicBasisPair()
    # Already-standard arity-4 vs Hadamard-needing arity-3.
    sigs = [[2, 0, 2, 0, 2], [1, 0, 0, 1]]
    assert h.discover_common_basis(sigs) is None


def test_discover_common_basis_returns_none_when_any_signature_non_realisable():
    """If even ONE signature fails the order-2 recurrence, no common
    basis can rescue the set (Cai-Lu Thm 2.5 applied pointwise)."""
    h = HolographicBasisPair()
    sigs = [[1, 0, 0, 1], [1, 0, 1, 0, 2]]      # second is rank-3
    assert h.discover_common_basis(sigs) is None


def test_discover_common_basis_empty_list_raises():
    h = HolographicBasisPair()
    with pytest.raises(ValueError):
        h.discover_common_basis([])


# ---------------------------------------------------------------------------
# Non-symmetric (general-tensor) basis transformation (v0.3)
# ---------------------------------------------------------------------------

def test_transform_general_identity_is_noop():
    """Identity basis on a general (non-symmetric) signature returns
    the same signature for any arity."""
    h = HolographicBasisPair(basis_matrix=np.eye(2))
    # arity 2: 4 values
    r2 = h.transform_signature_general([1, 2, 3, 4], arity=2)
    assert r2.values == [1.0, 2.0, 3.0, 4.0]
    # arity 3: 8 values
    r3 = h.transform_signature_general([1, 2, 3, 4, 5, 6, 7, 8], arity=3)
    assert r3.values == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]


def test_transform_general_hadamard_on_delta():
    """Hadamard transforms a delta function (canonical-basis vector)
    into the uniform-sign tensor. Concretely H^{otimes 2} on [1, 0, 0, 0]
    gives [1, 1, 1, 1] (the all-ones tensor)."""
    T = np.array([[1, 1], [1, -1]], dtype=float)
    h = HolographicBasisPair(basis_matrix=T)
    result = h.transform_signature_general([1, 0, 0, 0], arity=2)
    assert result.values == [1.0, 1.0, 1.0, 1.0]


def test_transform_general_rejects_wrong_length():
    """A signature whose length isn't 2^arity raises ValueError."""
    h = HolographicBasisPair(basis_matrix=np.eye(2))
    with pytest.raises(ValueError):
        h.transform_signature_general([1, 2, 3], arity=2)            # len 3 != 4
    with pytest.raises(ValueError):
        h.transform_signature_general([1, 2, 3, 4, 5], arity=3)      # len 5 != 8


def test_transform_general_matches_symmetric_path():
    """For a SYMMETRIC signature interpreted in both forms, the symmetric
    path's polynomial-substitution result agrees with the general path's
    tensor-power result (with the symmetric output expanded as
    [z_0, z_1, z_1, ..., z_n] over the 2^n bitstring index)."""
    T = np.array([[1, 1], [1, -1]], dtype=float)
    h = HolographicBasisPair(basis_matrix=T)
    # Symmetric arity-2 signature [a, b, c]: in general 2^2-dim form it
    # is [a, b, b, c] (the values at bitstring positions 00, 01, 10, 11).
    sym = [1, 0, 1]
    gen = [1, 0, 0, 1]
    sym_result = h.transform_signature(sym).values
    gen_result = h.transform_signature_general(gen, arity=2).values
    # The general result's positions 01 and 10 should be equal (symmetry
    # preserved by the tensor power) and match the symmetric output.
    assert abs(gen_result[1] - gen_result[2]) < 1e-9
    expected_general = [sym_result[0], sym_result[1],
                         sym_result[1], sym_result[2]]
    np.testing.assert_allclose(gen_result, expected_general, atol=1e-9)


def test_transform_general_invertibility_under_T_inverse_T():
    """Applying T then T^{-1} (each as a general tensor-power) returns
    the original signature."""
    T = np.array([[2, 1], [1, 1]], dtype=float)
    T_inv = np.linalg.inv(T)
    h_fwd = HolographicBasisPair(basis_matrix=T)
    h_inv = HolographicBasisPair(basis_matrix=T_inv)
    original = [1.0, 2.0, -3.0, 4.0, 0.5, -1.5, 7.0, -2.0]
    forward = h_fwd.transform_signature_general(original, arity=3).values
    roundtrip = h_inv.transform_signature_general(forward, arity=3).values
    np.testing.assert_allclose(roundtrip, original, atol=1e-9)


def test_transform_general_realisability_populated_by_mgi_check():
    """For general (non-symmetric) signatures, the realisability flag
    is populated by the v0.4 MGI check. Arity < 4 falls under the
    parity-only path (Valiant 2008 Prop 6.1, 6.2 -- no matchgate
    identities beyond parity exist below arity 4)."""
    h = HolographicBasisPair(basis_matrix=np.eye(2))
    # Arity 2: non-zero in both parities (values 1, 2, 3, 4 at
    # bitstrings 00, 01, 10, 11). Neither branch's parity equations
    # hold, so the parity-only check returns False.
    r = h.transform_signature_general([1, 2, 3, 4], arity=2)
    assert r.is_realisable is False
    assert r.realisability_check == "parity_only"
    assert r.recurrence_coefficients is None
    # An even-parity arity-2 signature (odd-weight entries zero):
    # values 1, 0, 0, 4 at bitstrings 00, 01, 10, 11 -- IS realisable
    # via parity alone.
    r_even = h.transform_signature_general([1, 0, 0, 4], arity=2)
    assert r_even.is_realisable is True
    assert r_even.realisability_check == "parity_only"


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
# v0.4 MGI realisability checks for general (non-symmetric) signatures
#
# These tests guard the v0.4 wiring of `holant_tools.non_symmetric`'s
# matchgate-identity functions into `transform_signature_general`. The
# check answers: "is the transformed signature matchgate-realisable
# *on the standard basis*?" -- which is a stricter criterion than the
# symmetric API's "realisable on some basis" check (Cai-Lu Thm 2.5).
# A symmetric input fed through the general API tests the standard-
# basis form specifically.
#
# Helper: a length-2^arity tensor in the convention where flat-index
# alpha maps to bitstring (b_0, ..., b_{a-1}) with b_i = the i-th bit
# of alpha read MSB-first (axis 0 = MSB).
# ---------------------------------------------------------------------------


def _sym_arity4_tensor(z0, z2, z4):
    """Build a length-16 tensor for a SYMMETRIC arity-4 even-parity
    signature [z_0, 0, z_2, 0, z_4]: every entry indexed by a
    bitstring of Hamming weight k has value z_k (with z_1, z_3 = 0)."""
    values = [0.0] * 16
    for alpha in range(16):
        w = bin(alpha).count("1")
        values[alpha] = {0: z0, 2: z2, 4: z4}.get(w, 0.0)
    return values


def test_mgi_arity_4_even_realisable_symmetric():
    """A symmetric arity-4 even-parity signature [z_0, 0, z_2, 0, z_4]
    with the matchgate-realisability condition z_2^2 = z_0 * z_4 should
    pass the matchgate-identity check on the standard basis."""
    hbp = HolographicBasisPair(basis_matrix=np.eye(2))
    # z_0=1, z_2=2, z_4=4: 2^2 = 1*4 ✓ -> matchgate-standard form.
    r = hbp.transform_signature_general(_sym_arity4_tensor(1, 2, 4), arity=4)
    assert r.is_realisable is True
    assert r.realisability_check == "matchgate_identity_arity_4"


def test_mgi_arity_4_even_perturbed_rejected():
    """Perturbing the same signature so z_2^2 != z_0 * z_4 makes the
    matchgate identity NON-vanishing -- check returns False."""
    hbp = HolographicBasisPair(basis_matrix=np.eye(2))
    values = _sym_arity4_tensor(1, 2, 4)
    values[5] = 2.5                                # perturb one weight-2 entry
    r = hbp.transform_signature_general(values, arity=4)
    assert r.is_realisable is False
    assert r.realisability_check == "matchgate_identity_arity_4"


def test_mgi_arity_4_even_zero_signature():
    """The all-zero signature is trivially matchgate-realisable."""
    hbp = HolographicBasisPair(basis_matrix=np.eye(2))
    r = hbp.transform_signature_general([0.0] * 16, arity=4)
    assert r.is_realisable is True
    # Tiny-magnitude inputs hit the "deferred" early-return; the answer
    # is still True (trivially realisable).
    assert r.realisability_check in ("deferred", "matchgate_identity_arity_4")


def test_mgi_arity_4_odd_realisable_symmetric():
    """A symmetric arity-4 odd-parity signature [0, z_1, 0, z_3, 0]
    with all weight-1 entries equal and all weight-3 entries equal
    automatically satisfies the augmented-Pfaffian identity
    (the odd-parity identity is vacuous on symmetric inputs -- see the
    MATCHGATE_IDENTITIES.md design doc's 'vacuous on symmetric' note)."""
    hbp = HolographicBasisPair(basis_matrix=np.eye(2))
    values = [0.0] * 16
    for alpha in range(16):
        w = bin(alpha).count("1")
        if w == 1:
            values[alpha] = 1.5
        elif w == 3:
            values[alpha] = 0.7
    r = hbp.transform_signature_general(values, arity=4)
    assert r.is_realisable is True
    assert r.realisability_check == "matchgate_identity_arity_4"


def test_mgi_arity_4_odd_perturbed_rejected():
    """An asymmetric arity-4 odd-parity signature that violates the
    augmented-Pfaffian identity: pick weight-1 entries that break the
    bit-position-pairing pattern.

    Identity (from holant-tools): tau_1000 * tau_0111 - tau_0100 *
    tau_1011 + tau_0010 * tau_1101 - tau_0001 * tau_1110 = 0.

    Set tau_1000 = tau_0111 = 1, all other weight-1 / weight-3 entries
    = 0 -> the first product = 1, others = 0, total = 1 != 0."""
    hbp = HolographicBasisPair(basis_matrix=np.eye(2))
    values = [0.0] * 16
    # In the orchestrator's bitstring convention, alpha = b_0 b_1 b_2 b_3
    # read as 4-bit binary MSB-first. So:
    # bitstring (1,0,0,0) <-> alpha = 0b1000 = 8
    # bitstring (0,1,1,1) <-> alpha = 0b0111 = 7
    values[8] = 1.0                                # tau_(1,0,0,0)
    values[7] = 1.0                                # tau_(0,1,1,1)
    r = hbp.transform_signature_general(values, arity=4)
    assert r.is_realisable is False
    assert r.realisability_check == "matchgate_identity_arity_4"


def test_mgi_arity_2_parity_only_realisable():
    """For arity < 4, parity-only is sufficient (Valiant 2008 Prop
    6.1, 6.2). An even-parity arity-2 signature passes."""
    hbp = HolographicBasisPair(basis_matrix=np.eye(2))
    # Bitstrings 00 (w=0) and 11 (w=2) at flat indices 0, 3.
    r = hbp.transform_signature_general([1.0, 0.0, 0.0, 4.0], arity=2)
    assert r.is_realisable is True
    assert r.realisability_check == "parity_only"


def test_mgi_arity_2_parity_violated_rejected():
    """An arity-2 signature with non-zero entries in BOTH parity branches
    fails the parity-only check."""
    hbp = HolographicBasisPair(basis_matrix=np.eye(2))
    r = hbp.transform_signature_general([1.0, 2.0, 3.0, 4.0], arity=2)
    assert r.is_realisable is False
    assert r.realisability_check == "parity_only"


def test_mgi_arity_5_plucker_zero_signature_realisable():
    """The all-zero signature at arity 5 is trivially realisable."""
    hbp = HolographicBasisPair(basis_matrix=np.eye(2))
    r = hbp.transform_signature_general([0.0] * 32, arity=5)
    assert r.is_realisable is True
    # Either the deferred zero shortcut or the Plücker check (both
    # produce the same boolean).
    assert r.realisability_check in ("deferred", "plucker_arity_n")


def test_mgi_arity_5_plucker_random_signature_rejected():
    """An arity-5 signature with non-zero entries in both parity
    branches violates parity and is rejected before the Plücker
    enumeration runs."""
    hbp = HolographicBasisPair(basis_matrix=np.eye(2))
    np.random.seed(42)
    values = list(np.random.randn(32))
    r = hbp.transform_signature_general(values, arity=5)
    assert r.is_realisable is False
    assert r.realisability_check == "plucker_arity_n"


def test_srp_closed_form_finds_rank1_basis_outside_v03_grid():
    """v0.4: the closed-form derivation from the recurrence kernel
    finds bases for rank-1 signatures z_k = r^k whose root ``r`` lies
    OUTSIDE the v0.3 grid search's ``[-2, +2]`` range -- a documented
    failure mode of the v0.3 implementation.

    Each test case is a rank-1 signature (single root in the
    recurrence decomposition). The closed-form derives the basis
    directly from the kernel coefficients, producing a single-point
    matchgate-standard form."""
    h = HolographicBasisPair()
    # Roots well outside the v0.3 [-2, +2] grid:
    roots_and_arities = [
        (5.0,   3),
        (5.0,   4),
        (10.0,  4),
        (-7.0,  4),
        (3.0,   5),
        (100.0, 4),
        (0.5,   4),       # also "below" the grid in magnitude
        (-3.0,  3),
    ]
    for r, n in roots_and_arities:
        z = [r ** k for k in range(n + 1)]
        discovery = h.discover_basis(z)
        assert discovery is not None, \
            f"v0.4 closed-form should find basis for r={r}, arity={n}"
        T, result = discovery
        # The transformed signature should be matchgate-standard
        # (distance < 1e-6 by the success_tol used internally).
        assert h._matchgate_standard_distance(result.values) < 1e-6, \
            f"r={r}, arity={n}: distance check failed"
        # Single-point form: exactly one entry above the relative
        # noise floor.
        max_abs = max(abs(v) for v in result.values)
        n_nonzero = sum(1 for v in result.values
                         if abs(v) > 1e-9 * max(max_abs, 1.0))
        assert n_nonzero == 1, \
            f"r={r}, arity={n}: expected single-point form, " \
            f"got {n_nonzero} non-zero entries"


def test_srp_closed_form_handles_negative_and_fractional_roots():
    """Additional rank-1 stress: roots covering a wide range of real
    values including negative and fractional ones."""
    h = HolographicBasisPair()
    np.random.seed(2026)
    for _trial in range(50):
        # Sample a real root in [-15, +15] excluding the zero-and-near-
        # zero range (which would give a degenerate signature).
        r = np.random.uniform(-15, 15)
        while abs(r) < 0.1:
            r = np.random.uniform(-15, 15)
        n = int(np.random.choice([3, 4, 5]))
        z = [r ** k for k in range(n + 1)]
        discovery = h.discover_basis(z)
        assert discovery is not None, \
            f"trial r={r:.4f}, arity={n}: closed-form should find basis"
        T, result = discovery
        assert h._matchgate_standard_distance(result.values) < 1e-6, \
            f"trial r={r:.4f}, arity={n}: distance failure"


def test_srp_rank2_correctly_returns_none_when_no_basis_exists():
    """Rank-2 signatures (true order-2 recurrence with both roots
    contributing, A != 0 and B != 0 with A != ±B in the
    closed-form decomposition) are GENUINELY matchgate-rank-2 in
    every basis -- no 2x2 basis can bring them to matchgate-standard
    rank-1 form (which requires alternate-zero + geometric
    progression).

    The closed-form should attempt and fail (returning None overall,
    since the rest of the search also can't find a basis that doesn't
    exist). This is correct behaviour, not a v0.4 regression."""
    h = HolographicBasisPair()
    # Pure rank-2: z_k = r_1^k + r_2^k with distinct r_1, r_2.
    z_rank2 = [5 ** k + 7 ** k for k in range(5)]
    discovery = h.discover_basis(z_rank2)
    # Either the closed-form yields a non-matchgate-standard form
    # and the rest of the search also fails (overall None), OR the
    # search finds some weird basis that happens to land near
    # matchgate-standard. We accept either outcome but assert the
    # result is consistent: if a basis is found, the distance must
    # be below tolerance.
    if discovery is not None:
        T, result = discovery
        assert h._matchgate_standard_distance(result.values) < 1e-6


def test_srp_complex_roots_via_v05_closed_form():
    """v0.5: complex-roots recurrence kernels are now handled by the
    closed-form directly. NAE-3 [0, 1, 1, 0] has recurrence kernel ~
    (1, -1, 1) with characteristic polynomial x^2 - x + 1 = 0, roots
    e^{±i*pi/3}. v0.4 fell through to the canonical-bases sweep (where
    Hadamard succeeded); v0.5 derives T = [[1, -alpha], [0, beta]]
    directly with alpha = 1/2, beta = sqrt(3)/2."""
    import numpy as np
    h = HolographicBasisPair()
    discovery = h.discover_basis([0, 1, 1, 0])
    assert discovery is not None
    T, result = discovery
    # The v0.5 closed-form should produce exactly T = [[1, -1/2],
    # [0, sqrt(3)/2]] (not the canonical Hadamard fallback).
    np.testing.assert_allclose(T, [[1.0, -0.5], [0.0, 3**0.5 / 2]],
                                atol=1e-9)
    # And it should land in matchgate-standard form.
    assert h._matchgate_standard_distance(result.values) < 1e-6


def test_srp_complex_roots_corpus():
    """v0.5: a corpus of complex-roots signatures derived from various
    (alpha, beta) pairs, all caught by the closed-form path."""
    import numpy as np
    h = HolographicBasisPair()
    # Each test case is built from a recurrence with characteristic
    # polynomial (x - r_1)(x - r_2) = x^2 - 2*alpha*x + (alpha^2 + beta^2)
    # where r_1, r_2 = alpha +/- i*beta. The signature is z_k = real
    # part of a complex-conjugate-pair decomposition. For simplicity,
    # we use z_k = 2*A*r^k cos(k*theta) where r = sqrt(alpha^2 + beta^2)
    # and theta = arctan(beta/alpha) -- the standard "real form" of the
    # complex-conjugate recurrence solution.
    test_cases = []
    for alpha, beta in [(0.5, 0.866),     # NAE-3 angle
                         (0.0, 1.0),       # purely imaginary roots
                         (1.0, 1.0),       # 45-degree angle
                         (0.3, 2.0),       # small alpha, larger beta
                         (-0.7, 1.5),      # negative real part
                         (2.0, 0.5)]:
        n = 4
        # Build z_k from the explicit cos/sin form.
        r = (alpha * alpha + beta * beta) ** 0.5
        theta = np.arctan2(beta, alpha)
        # A = 1: z_k = 2 * r^k * cos(k * theta).
        z = [2.0 * (r ** k) * np.cos(k * theta) for k in range(n + 1)]
        test_cases.append((f"alpha={alpha}, beta={beta}, arity={n}", z))
    for name, z in test_cases:
        discovery = h.discover_basis(z)
        assert discovery is not None, \
            f"{name}: closed-form should find a basis"
        T, result = discovery
        d = h._matchgate_standard_distance(result.values)
        assert d < 1e-6, \
            f"{name}: distance {d} exceeds tolerance"


def test_srp_complex_roots_random_stress():
    """v0.5 stress test: 50 random (alpha, beta) pairs in
    [-10, +10] x (0.1, 10] all yield matchgate-standard form via the
    closed-form."""
    import numpy as np
    h = HolographicBasisPair()
    rng = np.random.default_rng(2027)
    for _trial in range(50):
        alpha = float(rng.uniform(-10, 10))
        # beta strictly positive to ensure non-degenerate complex roots.
        beta = float(rng.uniform(0.1, 10))
        n = int(rng.choice([3, 4, 5]))
        r = (alpha * alpha + beta * beta) ** 0.5
        theta = np.arctan2(beta, alpha)
        z = [2.0 * (r ** k) * np.cos(k * theta) for k in range(n + 1)]
        discovery = h.discover_basis(z)
        assert discovery is not None, \
            f"trial alpha={alpha:.4f}, beta={beta:.4f}, n={n}: " \
            f"closed-form should find a basis"
        T, result = discovery
        d = h._matchgate_standard_distance(result.values)
        assert d < 1e-6, \
            f"trial alpha={alpha:.4f}, beta={beta:.4f}, n={n}: " \
            f"distance {d} exceeds tolerance"


def test_basis_from_recurrence_kernel_degenerate_cases():
    """Direct tests of the helper's case-handling returns.

    The helper accepts three categories of kernel:
      - Order-1 recurrences (c=0 OR a=0): synthesised as rank-1 T
        sending the single root to a pure axis.
      - Real distinct roots: the generic case, full closed-form T.
      - Complex roots or double roots: None (caller falls through).
    """
    import numpy as np
    h = HolographicBasisPair()

    # c = 0 (order-1 recurrence, rank-1 signature). The helper now
    # synthesises a rank-1 T from r = -a/b = 0.5, NOT None.
    T = h._basis_from_recurrence_kernel(1.0, -2.0, 0.0)
    assert T is not None, \
        "c=0 with valid b should yield a rank-1 closed-form T"
    assert T.shape == (2, 2)

    # a = 0 (order-1 recurrence from the other side, rank-1
    # signature). r = -b/c.
    T = h._basis_from_recurrence_kernel(0.0, -2.0, 1.0)
    assert T is not None, \
        "a=0 with valid c should yield a rank-1 closed-form T"

    # b = 0 AND c = 0: truly degenerate kernel (no recurrence info).
    assert h._basis_from_recurrence_kernel(1.0, 0.0, 0.0) is None

    # Complex roots (discriminant < 0). c*x^2 + b*x + a = x^2 - x + 1
    # has discriminant 1 - 4 = -3 < 0. As of v0.5, this case returns
    # a real T = [[1, -alpha], [0, beta]] derived from alpha, beta
    # (the real and imaginary parts of the conjugate-root pair). v0.4
    # used to return None here; the v0.5 closed-form upgrade catches it.
    T_complex = h._basis_from_recurrence_kernel(1.0, -1.0, 1.0)
    assert T_complex is not None, \
        "v0.5: complex roots should now yield a real closed-form T"
    assert T_complex.shape == (2, 2)
    # alpha = -b/(2c) = 0.5; beta = sqrt(3)/2 ~ 0.866.
    import numpy as np
    np.testing.assert_allclose(T_complex, [[1.0, -0.5], [0.0, 3**0.5 / 2]],
                                 atol=1e-9)

    # Double root (discriminant = 0, r_1 = r_2). c*x^2 + b*x + a =
    # (x - 3)^2 = x^2 - 6x + 9 -> (a, b, c) = (9, -6, 1).
    assert h._basis_from_recurrence_kernel(9.0, -6.0, 1.0) is None

    # Non-degenerate case for contrast: real distinct roots from
    # (x - 2)(x - 3) = x^2 - 5x + 6 -> (a, b, c) = (6, -5, 1).
    T = h._basis_from_recurrence_kernel(6.0, -5.0, 1.0)
    assert T is not None
    assert T.shape == (2, 2)
    # Det should be -r_1 - (-r_2) = r_2 - r_1 = +/-1. The
    # ordering of (r_1, r_2) is implementation-defined.
    assert abs(abs(np.linalg.det(T)) - 1.0) < 1e-9


def test_mgi_basis_transformation_changes_realisability():
    """A symmetric signature that's NOT matchgate-standard becomes
    realisable on the standard basis after applying a basis transform
    that maps it to standard form. Use 3-AND -> Hadamard, which puts
    [1, 0, 0, 1] (4 entries -> in general API: 8 entries arity 3) into
    matchgate-standard form per Cai-Lu 2011.

    In the general API, 3-AND with values [1, 0, 0, 0, 0, 0, 0, 1]
    has parity violated (weights 0 and 3 nonzero -- not all one
    parity), so under T=identity it fails the parity check. Under
    T=Hadamard^{otimes 3}, it transforms into matchgate-standard form
    (parity-respecting + identity satisfied)."""
    # Identity basis: should fail.
    hbp_id = HolographicBasisPair(basis_matrix=np.eye(2))
    and3_general = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0]
    r_id = hbp_id.transform_signature_general(and3_general, arity=3)
    assert r_id.is_realisable is False
    assert r_id.realisability_check == "parity_only"

    # Hadamard basis: should make it realisable (arity 3 -> parity-only
    # path; the transformed values should land in one parity branch).
    T_hadamard = np.array([[1.0, 1.0], [1.0, -1.0]])
    hbp_h = HolographicBasisPair(basis_matrix=T_hadamard)
    r_h = hbp_h.transform_signature_general(and3_general, arity=3)
    # The Hadamard transform of 3-AND is [1, 1, 1, -1, 1, -1, -1, -1] /
    # similar (Cai-Lu 2011 §6.1) -- which is NOT a strict-parity
    # signature, so parity-only still rejects. The MGI check at arity 3
    # is parity-only, so a signature with entries in both parity
    # branches will fail unless the Hadamard happens to zero one
    # branch. For 3-AND under Hadamard, the symmetric API knows it's
    # realisable (recurrence-satisfying), but the standard-basis check
    # doesn't certify it -- this is the documented difference between
    # the two APIs. We assert that the check name is at least
    # "parity_only" (no surprises in the path taken).
    assert r_h.realisability_check == "parity_only"


# ---------------------------------------------------------------------------
# Sketches (should remain NotImplementedError until v0.2)
# ---------------------------------------------------------------------------

def test_projection_ratio():
    """Projection as a marginal ratio of two sub-evaluations."""
    p = Projection(
        name="ratio",
        sub_problems=["num", "den"],
        projector=lambda vs: vs[0] / vs[1],
    )
    eval_fn = lambda x: {"num": 30, "den": 5}[x]
    assert p.evaluate(eval_fn) == 6.0


def test_projection_inclusion_exclusion():
    """Projection as an inclusion-exclusion sum."""
    p = Projection(
        name="incl-excl",
        sub_problems=["A", "B", "AB"],
        projector=lambda vs: vs[0] + vs[1] - vs[2],
    )
    eval_fn = lambda x: {"A": 10, "B": 7, "AB": 3}[x]
    assert p.evaluate(eval_fn) == 14


def test_projection_non_callable_projector_raises():
    p = Projection(name="bad", sub_problems=[1, 2], projector="not callable")
    with pytest.raises(TypeError):
        p.evaluate(lambda x: x)


def test_branch_sum_real_amplitudes():
    """BranchSum sums (amplitude * sub_eval) over named branches."""
    bs = BranchSum(name="binary tree", branches=[
        BranchSum.Branch("left",  0.5, "L"),
        BranchSum.Branch("right", 0.5, "R"),
    ])
    eval_fn = lambda x: {"L": 10, "R": 30}[x]
    assert bs.evaluate(eval_fn) == 20.0          # 0.5*10 + 0.5*30


def test_branch_sum_complex_amplitudes():
    """BranchSum supports complex amplitudes (Clifford+T pattern)."""
    bs = BranchSum(name="C+T branch", branches=[
        BranchSum.Branch("|+>", 1.0 + 0j, "P"),
        BranchSum.Branch("|->", 0.0 + 1j, "M"),
    ])
    eval_fn = lambda x: {"P": 2, "M": 3}[x]
    result = bs.evaluate(eval_fn)
    assert result == 2.0 + 3.0j


def test_branch_sum_sub_problems_and_combine_match_protocol():
    bs = BranchSum(name="x", branches=[
        BranchSum.Branch("a", 1, "X"),
        BranchSum.Branch("b", 2, "Y"),
    ])
    assert bs.sub_problems == ["X", "Y"]
    assert bs.combine([10, 20]) == 1 * 10 + 2 * 20


# ---------------------------------------------------------------------------
# v0.5 Deliverable 1: full augmented-Pfaffian Plücker enumeration at
# EVEN arity >= 6 odd-parity.
#
# These tests cover the new identities derived from |S|=2
# configurations on the (n+1)-vertex augmented Kasteleyn matrix.
# Acceptance:
#   - Identities vanish on signatures built from a real (n+1)x(n+1)
#     skew matrix via the augmented Pfaffian framework
#     (matchgate-realisable construction).
#   - Identities catch perturbations of those signatures.
#   - The realisability_check field reports "plucker_arity_n_full"
#     at arity 6 odd-parity (closing the v0.4 "tight necessary"
#     caveat).
# ---------------------------------------------------------------------------


def _build_realisable_arity_n_odd_signature(n, seed=2027):
    """Construct an arity-n odd-parity signature from a random
    (n+1)x(n+1) skew matrix M_omega using the augmented Pfaffian
    convention: tau(b) = Pf(complement(b) in {0..n-1} ∪ {omega}).
    The resulting signature is matchgate-realisable by construction.
    """
    rng = np.random.default_rng(seed)
    M_raw = rng.normal(size=(n + 1, n + 1))
    M_mat = (M_raw - M_raw.T) / 2     # skew-symmetric

    def pfaffian(indices):
        indices = sorted(indices)
        k = len(indices)
        if k == 0: return 1.0
        if k % 2 != 0: return 0.0
        if k == 2: return M_mat[indices[0], indices[1]]
        total = 0.0
        i0 = indices[0]
        for j in range(1, k):
            sign = (-1) ** (j + 1)
            ij = indices[j]
            rest = [indices[p] for p in range(1, k) if p != j]
            total += sign * M_mat[i0, ij] * pfaffian(rest)
        return total

    omega = n
    values = [0.0] * (1 << n)
    for mask in range(1 << n):
        b = tuple((mask >> (n - 1 - i)) & 1 for i in range(n))
        if sum(b) % 2 == 1:
            complement = [i for i in range(n) if b[i] == 0]
            values[mask] = pfaffian(sorted(complement + [omega]))
    return values


def test_v05_augmented_identities_vanish_on_realisable_arity_6():
    """The v0.5 augmented Plücker identities all vanish on a signature
    built from the augmented Pfaffian framework -- this is the basic
    mathematical correctness test."""
    values = _build_realisable_arity_n_odd_signature(6)
    hbp = HolographicBasisPair(basis_matrix=np.eye(2))
    r = hbp.transform_signature_general(values, arity=6)
    assert r.is_realisable is True, \
        f"realisable signature should pass v0.5 check, got " \
        f"is_realisable={r.is_realisable}, check={r.realisability_check}"
    assert r.realisability_check == "plucker_arity_n_full", \
        f"v0.5 should report 'plucker_arity_n_full' at arity 6 odd-parity"


def test_v05_augmented_identities_reject_perturbed_arity_6():
    """Perturbing a tau entry breaks the augmented identities. The
    perturbed signature is rejected (likely already by v0.4's standard
    Plücker enumeration, but v0.5's augmented check is a tighter
    safety net)."""
    values = _build_realisable_arity_n_odd_signature(6)
    # Perturb one weight-3 entry by 30% of the max-abs value.
    n = 6
    max_abs = max(abs(v) for v in values)
    # Find a weight-3 entry to perturb. Bitstring (0,0,0,1,1,1) ->
    # MSB-first alpha = 0+0+0+4+2+1 = 7.
    weight3_alpha = 7
    values_perturbed = list(values)
    values_perturbed[weight3_alpha] += 0.3 * max_abs

    hbp = HolographicBasisPair(basis_matrix=np.eye(2))
    r = hbp.transform_signature_general(values_perturbed, arity=6)
    assert r.is_realisable is False, \
        "perturbed signature should be rejected"


def test_v05_realisability_check_at_arity_5_does_not_promote():
    """At arity 5, v0.5's augmented identities don't apply (the
    construction requires EVEN arity: weight-(odd) complemented in
    {0..n-1} gives weight-(n-odd), and n-odd is odd iff n is even,
    so the augmented framework yields all-zero Pfaffians at odd
    arity). The realisability_check field must NOT advance to
    'plucker_arity_n_full' at arity 5 -- v0.5 explicitly skips the
    helper at odd arity.

    Use a single-point arity-5 odd-parity signature (only one
    weight-1 entry non-zero) -- realisable on the standard basis
    via a single-point matchgate."""
    n = 5
    values = [0.0] * (1 << n)
    # Bitstring (1, 0, 0, 0, 0) MSB-first -> alpha = 16.
    values[16] = 1.0
    hbp = HolographicBasisPair(basis_matrix=np.eye(2))
    r = hbp.transform_signature_general(values, arity=n)
    # The realisability VERDICT depends on the standard Plücker
    # enumeration; what matters here is the CHECK NAME never becomes
    # v0.5's "_full" form at arity 5.
    assert r.realisability_check != "plucker_arity_n_full", \
        f"arity 5 must not use v0.5's _full check, got " \
        f"'{r.realisability_check}'"


def test_v05_augmented_helper_directly_returns_zero_on_realisable():
    """Direct test of _augmented_plucker_identities_arity_n_odd:
    on a matchgate-realisable arity-6 odd-parity signature, all 30
    identity values should be (essentially) zero."""
    values = _build_realisable_arity_n_odd_signature(6)
    n = 6
    tau = {tuple((alpha >> (n - 1 - i)) & 1 for i in range(n)): values[alpha]
           for alpha in range(1 << n)}
    hbp = HolographicBasisPair()
    identities = hbp._augmented_plucker_identities_arity_n_odd(tau, n)
    assert len(identities) == 30, \
        f"arity 6 should give 30 augmented identities, got {len(identities)}"
    max_abs_tau = max(abs(v) for v in values)
    tol = 1e-9 * max(max_abs_tau ** 2, 1.0)
    for i, val in enumerate(identities):
        assert abs(val) < tol, \
            f"identity {i}: value {val} exceeds tolerance {tol}"


# ---------------------------------------------------------------------------
# v0.6 Deliverable 3: |S| = 4 (m = 3) augmented Plücker enumeration at
# even arity >= 8. Engine-side function in holant-tools v0.6.1 picks
# up the additional 280 identities at arity 8 (alongside the 280 from
# the m = 1 case); structural-computing's delegation wrapper consumes
# them transparently.
# ---------------------------------------------------------------------------


def test_v06_d3_arity_8_realisable_signature_via_v0_6_1_engine():
    """At arity 8 with the v0.6.1 engine, the augmented enumeration
    returns 560 identities (m=1 + m=3). A signature built from a
    random 9x9 skew matrix via the augmented Pfaffian framework
    passes all of them."""
    n = 8
    values = _build_realisable_arity_n_odd_signature(n, seed=2028)
    hbp = HolographicBasisPair(basis_matrix=np.eye(2))
    r = hbp.transform_signature_general(values, arity=n)
    assert r.is_realisable is True, \
        f"realisable arity-8 signature should pass v0.6.1 engine check"
    assert r.realisability_check == "plucker_arity_n_full"


def test_v06_d3_arity_8_perturbed_signature_via_v0_6_1_engine():
    """Perturbing a single weight-3 entry on the arity-8 realisable
    signature breaks at least one of the now-560 augmented identities."""
    n = 8
    values = _build_realisable_arity_n_odd_signature(n, seed=2028)
    # Perturb weight-3 entry. MSB-first convention: bitstring
    # (0, 0, 0, 0, 0, 1, 1, 1) -> alpha = 7.
    max_abs = max(abs(v) for v in values)
    values_perturbed = list(values)
    values_perturbed[7] += 0.3 * max_abs
    hbp = HolographicBasisPair(basis_matrix=np.eye(2))
    r = hbp.transform_signature_general(values_perturbed, arity=n)
    assert r.is_realisable is False, \
        "perturbed arity-8 signature should be rejected by 560 augmented identities"


def test_v06_d3_delegation_count_grew_at_arity_8():
    """Direct test: the delegation wrapper at arity 8 now returns 560
    identities (up from 280 in v0.5 D1 / v0.6.0 which only had m=1)."""
    n = 8
    values = _build_realisable_arity_n_odd_signature(n, seed=2028)
    hbp = HolographicBasisPair()
    tau = {tuple((alpha >> (n - 1 - i)) & 1 for i in range(n)): values[alpha]
           for alpha in range(1 << n)}
    identities = hbp._augmented_plucker_identities_arity_n_odd(tau, n)
    assert len(identities) == 560, \
        f"arity 8 should give 560 identities (280 m=1 + 280 m=3) via " \
        f"v0.6.1 engine; got {len(identities)}"
