"""Tests for StructuralComputer's constraint-set and signature methods:
classify_constraints, count_solutions, find_witness_solution,
list_solutions, classify_function, matchgate_rank, is_matchgate_realisable.

These tests exercise the wrapper's "first-class constraint sets and
signatures" surface that was added on top of the original graph-only API.
"""

import numpy as np
import pytest

from structural_computing import StructuralComputer, NotInFamily


@pytest.fixture
def sc():
    return StructuralComputer()


# ---------------------------------------------------------------------------
# classify_constraints
# ---------------------------------------------------------------------------

def test_classify_constraints_t0(sc):
    """A pure GF(2)-affine constraint set is T0."""
    A = [[1, 1, 0], [0, 1, 1]]
    b = [1, 0]
    cls = sc.classify_constraints(A=A, b=b)
    assert cls.tier == "T0"
    assert cls.in_family


def test_classify_constraints_t1(sc):
    """Linear + quadratic constraints over GF(2) are T1."""
    A = [[1, 1, 1, 1]]
    b = [0]
    Q = [[[0, 1, 0, 0], [0, 0, 0, 0], [0, 0, 0, 1], [0, 0, 0, 0]]]
    c = [0]
    cls = sc.classify_constraints(A=A, b=b, Q=Q, c=c)
    assert cls.tier == "T1"
    assert cls.in_family


def test_classify_constraints_t7_mod_p(sc):
    """mod-p arithmetic for p != 2 is T7 (out-of-family)."""
    A = [[1, 1]]; b = [0]
    cls = sc.classify_constraints(A=A, b=b, modulus=7)
    assert cls.tier == "T7"
    assert not cls.in_family


# ---------------------------------------------------------------------------
# count_solutions (T0 path -- poly-time via Gaussian elimination)
# ---------------------------------------------------------------------------

def test_count_solutions_t0_basic(sc):
    """A 3-variable system with 2 independent constraints has 2^(3-2) = 2 solutions."""
    A = [[1, 1, 0], [0, 1, 1]]; b = [1, 0]
    assert sc.count_solutions(A=A, b=b) == 2


def test_count_solutions_t0_full_rank(sc):
    """A system with as many independent constraints as variables has 1 solution."""
    A = [[1, 0], [0, 1]]; b = [1, 0]
    assert sc.count_solutions(A=A, b=b) == 1


def test_count_solutions_t0_unconstrained(sc):
    """Zero constraints means all 2^n solutions."""
    A = [[0, 0, 0, 0]]; b = [0]
    assert sc.count_solutions(A=A, b=b) == 16


def test_count_solutions_t0_infeasible(sc):
    """An inconsistent system (rank(A) != rank([A|b])) has 0 solutions."""
    A = [[1, 1], [1, 1]]; b = [0, 1]
    assert sc.count_solutions(A=A, b=b) == 0


def test_count_solutions_t0_large_n_still_fast(sc):
    """Pure GF(2)-affine count is poly-time -- 100 vars should be instant."""
    n = 100
    A = np.zeros((1, n), dtype=int)
    A[0, 0] = 1                        # one constraint: x_0 = 0
    b = np.array([0], dtype=int)
    # 2^99 solutions; we get the exact integer back.
    result = sc.count_solutions(A=A, b=b)
    assert result == 2 ** 99


# ---------------------------------------------------------------------------
# count_solutions (T1 path -- brute-force at small n)
# ---------------------------------------------------------------------------

def test_count_solutions_t1_brute(sc):
    """T1 (linear + quadratic) is brute-forced at small n."""
    A = [[1, 1, 1, 1]]; b = [0]
    Q = [[[0, 1, 0, 0], [0, 0, 0, 0], [0, 0, 0, 1], [0, 0, 0, 0]]]
    c = [0]
    # Count should match brute force.
    n = sc.count_solutions(A=A, b=b, Q=Q, c=c)
    # Brute force here for cross-check.
    expected = 0
    for x in range(16):
        bits = [(x >> (3 - i)) & 1 for i in range(4)]
        if (bits[0] + bits[1] + bits[2] + bits[3]) % 2 != 0:
            continue
        if (bits[0] * bits[1] + bits[2] * bits[3]) % 2 != 0:
            continue
        expected += 1
    assert n == expected


def test_count_solutions_t1_too_large_raises(sc):
    """T1 above the brute-force cap raises ValueError."""
    n = 30
    A = [[1] + [0] * (n - 1)]; b = [0]
    Q = [[[0] * n] * n]
    c = [0]
    with pytest.raises(ValueError):
        sc.count_solutions(A=A, b=b, Q=Q, c=c)


# ---------------------------------------------------------------------------
# find_witness_solution
# ---------------------------------------------------------------------------

def test_find_witness_t0(sc):
    """Witness must satisfy the constraints."""
    A = np.array([[1, 1, 0], [0, 1, 1]], dtype=int)
    b = np.array([1, 0], dtype=int)
    wit = sc.find_witness_solution(A=A, b=b)
    assert wit is not None
    bits = np.array([(wit >> (2 - i)) & 1 for i in range(3)], dtype=int)
    assert np.array_equal((A @ bits) % 2, b % 2)


def test_find_witness_t0_infeasible(sc):
    """Infeasible system returns None."""
    A = [[1, 1], [1, 1]]; b = [0, 1]
    assert sc.find_witness_solution(A=A, b=b) is None


def test_find_witness_t1(sc):
    """T1 witness via brute force."""
    A = [[1, 1, 1, 1]]; b = [0]
    Q = [[[0, 1, 0, 0], [0, 0, 0, 0], [0, 0, 0, 1], [0, 0, 0, 0]]]
    c = [0]
    wit = sc.find_witness_solution(A=A, b=b, Q=Q, c=c)
    assert wit is not None
    # Verify it satisfies.
    bits = np.array([(wit >> (3 - i)) & 1 for i in range(4)], dtype=int)
    A_arr = np.array(A); b_arr = np.array(b)
    Q_arr = np.array(Q[0])
    assert np.array_equal((A_arr @ bits) % 2, b_arr % 2)
    assert (bits @ Q_arr @ bits) % 2 == 0


# ---------------------------------------------------------------------------
# list_solutions
# ---------------------------------------------------------------------------

def test_list_solutions(sc):
    """list_solutions returns every assignment satisfying the constraints."""
    A = [[1, 1, 0], [0, 1, 1]]; b = [1, 0]
    sols = sc.list_solutions(A=A, b=b)
    A_arr = np.array(A); b_arr = np.array(b)
    for x in sols:
        bits = np.array([(x >> (2 - i)) & 1 for i in range(3)], dtype=int)
        assert np.array_equal((A_arr @ bits) % 2, b_arr % 2)
    # Conversely, every other assignment doesn't satisfy.
    for x in range(8):
        bits = np.array([(x >> (2 - i)) & 1 for i in range(3)], dtype=int)
        ok = np.array_equal((A_arr @ bits) % 2, b_arr % 2)
        assert (x in sols) == ok


def test_list_solutions_too_large_raises(sc):
    """list_solutions above the cap raises."""
    A = np.zeros((1, 25), dtype=int); b = np.array([0], dtype=int)
    with pytest.raises(ValueError):
        sc.list_solutions(A=A, b=b)


# ---------------------------------------------------------------------------
# Honest stops for out-of-family
# ---------------------------------------------------------------------------

def test_count_solutions_mod_p_honest_stop(sc):
    """mod-p arithmetic for p != 2 honestly stops via NotInFamily."""
    A = [[1, 1]]; b = [0]
    with pytest.raises(NotInFamily):
        sc.count_solutions(A=A, b=b, modulus=7)


def test_find_witness_mod_p_honest_stop(sc):
    """Same honest stop for find_witness_solution."""
    A = [[1, 1]]; b = [0]
    with pytest.raises(NotInFamily):
        sc.find_witness_solution(A=A, b=b, modulus=5)


# ---------------------------------------------------------------------------
# Signature methods
# ---------------------------------------------------------------------------

def test_classify_function_arity_2(sc):
    """Arity-2 symmetric signatures are T2."""
    cls = sc.classify_function([0, 1, 1])           # OR
    assert cls.tier == "T2"
    assert cls.in_family


def test_classify_function_arity_3(sc):
    """Arity >= 3 symmetric signatures are T3."""
    cls = sc.classify_function([0, 1, 0, 1])        # XOR_arity_3
    assert cls.tier == "T3"
    assert cls.in_family


def test_matchgate_rank_in_0_1_2(sc):
    """Every symmetric signature has basis-aware rank in {0, 1, 2}."""
    for values in ([0, 1, 1],                          # OR
                    [0, 0, 1],                          # AND
                    [0, 1, 0],                          # XOR
                    [1, 0, 1],                          # EQUAL
                    [0, 1, 0, 1],                       # XOR_3
                    [0, 0, 1, 0, 0],                    # EXACTLY_2_of_4
                    [0, 0, 0, 1, 1, 1]):                # MAJORITY_5
        rank = sc.matchgate_rank(values)
        assert rank in (0, 1, 2)


def test_is_matchgate_realisable_or(sc):
    """OR (rank 1) is matchgate-realisable."""
    assert sc.is_matchgate_realisable([0, 1, 1])


def test_is_matchgate_realisable_xor(sc):
    """XOR (rank 1) is matchgate-realisable."""
    assert sc.is_matchgate_realisable([0, 1, 0])
