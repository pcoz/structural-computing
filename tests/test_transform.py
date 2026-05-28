"""Tests for the reductions layer (`transform.py`).

The concrete reductions in v0.1:
  - NormaliseGraphFormat (the format-coercion reduction)
  - HybridDecomposition (matching-count on non-planar graphs)

Sketches that should raise NotImplementedError until v0.2:
  - CrossingElimination, HighDegreeVertexSplit, RationaliseWeights
"""

import pytest

from structural_computing import (
    NormaliseGraphFormat,
    HybridDecomposition,
    CrossingElimination,
    HighDegreeVertexSplit,
    RationaliseWeights,
    ReductionNotApplicable,
    ReductionPlan,
    StructuralComputer,
    brute_force_count_matchings,
)


# ---------------------------------------------------------------------------
# NormaliseGraphFormat
# ---------------------------------------------------------------------------

def test_normalise_edge_list():
    """Edge-list input gets normalised to a (V, E, rotation) dict."""
    r = NormaliseGraphFormat()
    result = r.apply([(0, 1), (1, 2), (2, 3), (3, 0)])
    assert "vertices" in result.problem
    assert "edges" in result.problem
    assert "rotation" in result.problem
    assert sorted(result.problem["vertices"]) == [0, 1, 2, 3]
    assert result.cost_overhead == 0.0          # pure format change


def test_normalise_adjacency_dict():
    """Adjacency-dict input also normalises."""
    r = NormaliseGraphFormat()
    result = r.apply({0: {1, 3}, 1: {0, 2}, 2: {1, 3}, 3: {0, 2}})
    assert len(result.problem["vertices"]) == 4


def test_normalise_rotation_system_passthrough():
    """A rotation-system input passes through largely unchanged."""
    rotation = {0: [1, 2, 3], 1: [0, 3, 2], 2: [0, 1, 3], 3: [0, 2, 1]}
    r = NormaliseGraphFormat()
    result = r.apply(rotation)
    assert result.problem["rotation"] == rotation


def test_normalise_rejects_garbage():
    """Garbage input raises ReductionNotApplicable."""
    r = NormaliseGraphFormat()
    with pytest.raises(ReductionNotApplicable):
        r.apply(42)
    with pytest.raises(ReductionNotApplicable):
        r.apply("hello")


# ---------------------------------------------------------------------------
# HybridDecomposition -- the v0.1 concrete reduction for matching counts
# ---------------------------------------------------------------------------

K33_VERTICES = [0, 1, 2, 3, 4, 5]
K33_EDGES = [(0, 3), (0, 4), (0, 5),
              (1, 3), (1, 4), (1, 5),
              (2, 3), (2, 4), (2, 5)]


def test_hybrid_k33_1_extra_edge_matches_brute_force():
    """K_{3,3} has 6 perfect matchings; hybrid with 1 extra edge matches."""
    sc = StructuralComputer()
    expected = brute_force_count_matchings(K33_VERTICES, K33_EDGES)
    assert expected == 6
    got = sc.count_matchings_hybrid(K33_EDGES, extra_edges=[(0, 3)])
    assert got == expected


def test_hybrid_k33_2_extra_edges_matches_brute_force():
    """Same answer with 2 extra edges."""
    sc = StructuralComputer()
    got = sc.count_matchings_hybrid(K33_EDGES, extra_edges=[(0, 3), (1, 4)])
    assert got == 6


def test_hybrid_k33_3_extra_edges_matches_brute_force():
    """Same answer with 3 extra edges."""
    sc = StructuralComputer()
    got = sc.count_matchings_hybrid(K33_EDGES, extra_edges=[(0, 3), (1, 4), (2, 5)])
    assert got == 6


def test_hybrid_k4_no_extra_edges_passthrough():
    """With no extra edges, hybrid decomp degenerates to the planar case."""
    sc = StructuralComputer()
    k4_edges = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]
    got = sc.count_matchings_hybrid(k4_edges, extra_edges=[])
    assert got == 3                              # K_4 has 3 perfect matchings


def test_hybrid_apply_directly():
    """Apply HybridDecomposition directly to inspect the sub-problems."""
    h = HybridDecomposition(extra_edges=[(0, 3)])
    problem = {
        "vertices": K33_VERTICES,
        "edges": [tuple(sorted([u, v], key=str)) for (u, v) in K33_EDGES],
    }
    result = h.apply(problem)
    # 2^1 = 2 valid sub-problems (forced-in is valid; forced-out is valid).
    assert len(result.problem["sub_problems"]) == 2
    assert result.cost_overhead == 1.0           # log2(2^1)


def test_hybrid_invalid_edges_skipped():
    """Sub-problems with vertex-sharing forced-in edges are skipped."""
    # extra_edges = [(0,3), (0,4)] -- both incident to vertex 0; can't both
    # be simultaneously forced in. The mask=3 case (both forced in) is invalid.
    h = HybridDecomposition(extra_edges=[(0, 3), (0, 4)])
    problem = {
        "vertices": K33_VERTICES,
        "edges": [tuple(sorted([u, v], key=str)) for (u, v) in K33_EDGES],
    }
    result = h.apply(problem)
    # mask=0 (both out), mask=1 (only (0,3) in), mask=2 (only (0,4) in) are valid.
    # mask=3 (both in, share vertex 0) is INVALID and skipped.
    assert len(result.problem["sub_problems"]) == 3


def test_hybrid_rejects_non_graph_input():
    """HybridDecomposition raises when the input isn't a graph dict."""
    h = HybridDecomposition(extra_edges=[(0, 1)])
    with pytest.raises(ReductionNotApplicable):
        h.apply([(0, 1)])               # not a dict


def test_hybrid_rejects_missing_extra_edges():
    """If `extra_edges` lists an edge not in the graph, apply raises."""
    h = HybridDecomposition(extra_edges=[(99, 100)])
    problem = {
        "vertices": K33_VERTICES,
        "edges": [tuple(sorted([u, v], key=str)) for (u, v) in K33_EDGES],
    }
    with pytest.raises(ReductionNotApplicable):
        h.apply(problem)


# ---------------------------------------------------------------------------
# Sketches that should raise NotImplementedError (v0.2 deliverables)
# ---------------------------------------------------------------------------

def test_crossing_elimination_trivial_no_crossings():
    """CrossingElimination with no declared crossings is identity."""
    r = CrossingElimination(crossings=[])
    result = r.apply({"vertices": [0, 1], "edges": [(0, 1)]})
    assert result.cost_overhead == 0.0
    # Identity inverse: answer passes through unchanged.
    assert result.inverse(42) == 42


def test_crossing_elimination_with_crossings_is_v02():
    """CrossingElimination with non-empty crossings raises NotImplementedError
    pending the v0.2 Cai-Lu-Xia gadget construction."""
    r = CrossingElimination(crossings=[((0, 1), (2, 3))])
    with pytest.raises(NotImplementedError):
        r.apply({"vertices": [0, 1, 2, 3], "edges": [(0, 1), (2, 3)]})


def test_high_degree_vertex_split_is_a_v02_sketch():
    r = HighDegreeVertexSplit()
    with pytest.raises(NotImplementedError):
        r.apply({"vertices": [], "edges": []})


def test_rationalise_weights_is_a_v02_sketch():
    r = RationaliseWeights()
    with pytest.raises(NotImplementedError):
        r.apply({})


# ---------------------------------------------------------------------------
# ReductionPlan composition
# ---------------------------------------------------------------------------

def test_reduction_plan_chains_steps():
    """A ReductionPlan applies its constituent reductions in order."""
    plan = ReductionPlan(reductions=[NormaliseGraphFormat()])
    result = plan.apply([(0, 1), (1, 2)])
    assert "vertices" in result.problem
    # cost_overhead is 0 here (one cost-free reduction).
    assert result.cost_overhead == 0.0
