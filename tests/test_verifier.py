"""Tests for the brute-force verification primitives:
brute_force_count_matchings, satisfies_gf2_affine,
enumerate_satisfying_assignments, gibbs_expectation_brute, verify_pipeline.

These are the small-n correctness contract. Every example in the package
that produces a numerical answer is verified against these at small n;
that verification IS the framework's correctness contract."""

import math
import numpy as np
import pytest

from structural_computing import (
    Stage, Route, run_pipeline,
    brute_force_count_matchings,
    satisfies_gf2_affine,
    enumerate_satisfying_assignments,
    gibbs_expectation_brute,
    verify_pipeline,
)


# ---------------------------------------------------------------------------
# brute_force_count_matchings
# ---------------------------------------------------------------------------

def test_count_matchings_k4():
    """K_4 has 3 perfect matchings."""
    assert brute_force_count_matchings(
        [0, 1, 2, 3],
        [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)],
    ) == 3


def test_count_matchings_c4():
    """The 4-cycle has 2 perfect matchings."""
    assert brute_force_count_matchings(
        [0, 1, 2, 3], [(0, 1), (1, 2), (2, 3), (3, 0)]
    ) == 2


def test_count_matchings_odd_order_is_zero():
    """A graph with an odd number of vertices has 0 perfect matchings."""
    assert brute_force_count_matchings(
        [0, 1, 2], [(0, 1), (1, 2), (2, 0)]
    ) == 0


def test_count_matchings_path():
    """The 4-vertex path 0-1-2-3 has 1 perfect matching: {0-1, 2-3}."""
    assert brute_force_count_matchings(
        [0, 1, 2, 3], [(0, 1), (1, 2), (2, 3)]
    ) == 1


def test_count_matchings_disconnected():
    """Two disjoint edges have 1 perfect matching."""
    assert brute_force_count_matchings(
        [0, 1, 2, 3], [(0, 1), (2, 3)]
    ) == 1


# ---------------------------------------------------------------------------
# satisfies_gf2_affine + enumerate_satisfying_assignments
# ---------------------------------------------------------------------------

def test_satisfies_gf2_affine_basic():
    """Predicate: A x = b (mod 2). bit 0 = MSB convention."""
    A = np.array([[1, 1, 0], [0, 1, 1]], dtype=int)
    b = np.array([1, 0], dtype=int)
    # x = 0b101 = 5: x_0=1, x_1=0, x_2=1
    # A x = (1+0, 0+1) = (1, 1) mod 2; b = (1, 0). Not equal.
    assert not satisfies_gf2_affine(5, A, b)
    # x = 0b110 = 6: x_0=1, x_1=1, x_2=0
    # A x = (1+1, 1+0) = (2, 1) mod 2 = (0, 1). b = (1, 0). Not equal.
    assert not satisfies_gf2_affine(6, A, b)


def test_enumerate_satisfying_returns_correct_count():
    """3 vars, 2 independent constraints -> 2 satisfying assignments."""
    A = np.array([[1, 1, 0], [0, 1, 1]], dtype=int)
    b = np.array([1, 0], dtype=int)
    sols = enumerate_satisfying_assignments(A, b)
    assert len(sols) == 2


def test_enumerate_satisfying_all_pass_predicate():
    """Every solution from enumerate must satisfy the predicate, and
    every non-solution must not."""
    A = np.array([[1, 1, 0], [0, 1, 1]], dtype=int)
    b = np.array([1, 0], dtype=int)
    sols = set(enumerate_satisfying_assignments(A, b))
    for x in range(8):
        ok = satisfies_gf2_affine(x, A, b)
        assert (x in sols) == ok


# ---------------------------------------------------------------------------
# gibbs_expectation_brute
# ---------------------------------------------------------------------------

def test_gibbs_uniform_weighting_first_bit():
    """Uniform weights, observable = first bit: <obs> = 0.5."""
    states = [0, 1, 2, 3]
    val = gibbs_expectation_brute(states, lambda x: 1.0, lambda x: x & 1)
    assert abs(val - 0.5) < 1e-12


def test_gibbs_exponential_weighting():
    """Weights 2^x, observable = first bit: <obs> = (0+2+0+8)/(1+2+4+8) = 10/15."""
    val = gibbs_expectation_brute([0, 1, 2, 3],
                                    lambda x: 2.0 ** x,
                                    lambda x: x & 1)
    assert abs(val - 10.0 / 15.0) < 1e-12


def test_gibbs_empty_states_returns_zero():
    """Empty state space returns 0 (the convention)."""
    val = gibbs_expectation_brute([], lambda x: 1.0, lambda x: 1.0)
    assert val == 0.0


# ---------------------------------------------------------------------------
# verify_pipeline
# ---------------------------------------------------------------------------

def test_verify_pipeline_all_match():
    """verify_pipeline returns (True, report) when every stage matches."""
    def r(d, p, route): return (p or 0) + d
    def route(d, p): return Route(member="m", cost=1.0)
    stages = [
        Stage("s1", "k", 3, route, r),    # 0+3=3
        Stage("s2", "k", 7, route, r),    # 3+7=10
        Stage("s3", "k", 2, route, r),    # 10+2=12
    ]
    ok, report = verify_pipeline(stages, [3, 10, 12], seed=0)
    assert ok
    assert "ok" in report.lower()


def test_verify_pipeline_catches_mismatch():
    """verify_pipeline returns (False, report) on any mismatch."""
    def r(d, p, route): return (p or 0) + d
    def route(d, p): return Route(member="m", cost=1.0)
    stages = [
        Stage("s1", "k", 3, route, r),
        Stage("s2", "k", 7, route, r),
    ]
    ok, report = verify_pipeline(stages, [3, 99], seed=0)     # 99 is wrong
    assert not ok
    assert "FAIL" in report


def test_verify_pipeline_stage_count_mismatch():
    """If reference_outputs has wrong length, the function reports it."""
    def r(d, p, route): return d
    def route(d, p): return Route(member="m", cost=1.0)
    stages = [Stage("only", "k", 5, route, r)]
    ok, report = verify_pipeline(stages, [5, 5, 5], seed=0)
    assert not ok
    assert "count" in report.lower() or "mismatch" in report.lower()


def test_verify_pipeline_with_atol():
    """verify_pipeline tolerates floating-point noise up to atol."""
    def r(d, p, route): return 1.0 + 1e-12
    def route(d, p): return Route(member="m", cost=1.0)
    stages = [Stage("a", "k", None, route, r)]
    ok, _ = verify_pipeline(stages, [1.0], seed=0, atol=1e-9)
    assert ok
