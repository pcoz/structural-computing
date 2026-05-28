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


def test_crossing_elimination_inserts_cai_gorenstein_gadget():
    """A declared crossing is replaced by the 6-vertex/7-edge
    Cai-Gorenstein gadget: 4 fresh pin vertices + 2 fresh internal
    vertices + 4 segment edges + 7 gadget internal edges (one with
    weight -1 on the spine)."""
    graph = {
        "vertices": [0, 1, 2, 3],
        "edges": [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2), (1, 3)],
        "weights": {e: 1 for e in [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2), (1, 3)]},
    }
    r = CrossingElimination(crossings=[((0, 2), (1, 3))])
    result = r.apply(graph)
    # Vertex count: 4 original + 6 fresh = 10
    assert len(result.problem["vertices"]) == 10
    # Edge count: 6 original - 2 deleted + 4 segments + 7 gadget = 15
    assert len(result.problem["edges"]) == 15
    # Exactly one edge carries the -1 weight (the gadget spine).
    minus_one_weights = [w for w in result.problem["weights"].values() if w == -1]
    assert len(minus_one_weights) == 1


def test_crossing_elimination_preserves_unit_weight_k4_pm_count():
    """K_4 (3 unit-weight perfect matchings) has the property that the
    gadget-inserted -1 signs cancel out across all matchings, so the
    planarised K_4 has PerfMatch = 3 too. This is a useful sanity
    test (NOT a general property -- see the class docstring on what
    the gadget actually preserves)."""
    graph = {
        "vertices": [0, 1, 2, 3],
        "edges": [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2), (1, 3)],
        "weights": {e: 1 for e in [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2), (1, 3)]},
    }
    original = brute_force_count_matchings(graph["vertices"], graph["edges"])
    assert original == 3
    r = CrossingElimination(crossings=[((0, 2), (1, 3))])
    result = r.apply(graph)
    from structural_computing import brute_force_weighted_matching_sum
    planarised = brute_force_weighted_matching_sum(
        result.problem["vertices"],
        result.problem["edges"],
        result.problem["weights"],
    )
    assert planarised == 3


def test_crossing_elimination_rejects_undeclared_edge():
    """A crossing whose edges aren't in the graph raises ReductionNotApplicable."""
    r = CrossingElimination(crossings=[((99, 100), (101, 102))])
    with pytest.raises(ReductionNotApplicable):
        r.apply({"vertices": [0, 1], "edges": [(0, 1)]})


def test_high_degree_vertex_split_realises_geometric_signature():
    """An even-arity-4 symmetric matchgate-realisable signature
    [2, 0, 6, 0, 18] (ratio 3) gets realised by the 2k=8-node
    triangle-cycle matchgate. Every signature entry Γ^α matches the
    brute-force PerfMatch of the matchgate with the α-indicated
    externals removed."""
    from itertools import product as iproduct
    from structural_computing import brute_force_weighted_matching_sum

    sig = [2, 0, 6, 0, 18]
    h = HighDegreeVertexSplit(signature=sig)
    result = h.apply({"values": sig})
    mg = result.problem
    assert mg["arity"] == 4
    assert len(mg["vertices"]) == 8                  # 2k = 2*4 = 8
    assert len(mg["externals"]) == 4
    # Verify each of the 16 entries of the signature.
    for alpha in iproduct([0, 1], repeat=4):
        drop = [mg["externals"][i] for i, b in enumerate(alpha) if b == 1]
        vert = [v for v in mg["vertices"] if v not in drop]
        eds  = [e for e in mg["edges"] if e[0] not in drop and e[1] not in drop]
        pm = brute_force_weighted_matching_sum(
            vert, eds, {e: mg["weights"][e] for e in eds},
        )
        hw = sum(alpha)
        expected = sig[hw]
        assert abs(pm - expected) < 1e-9, (
            f"alpha={alpha} (hw={hw}): brute force {pm} != expected {expected}"
        )


def test_high_degree_vertex_split_rejects_non_geometric_signature():
    """[1, 0, 1, 0, 2] does not satisfy the geometric-progression
    invariant (z_2/z_0=1 but z_4/z_2=2), so it's NOT matchgate-realisable
    and the reduction must refuse."""
    h = HighDegreeVertexSplit(signature=[1, 0, 1, 0, 2])
    with pytest.raises(ReductionNotApplicable):
        h.apply({"values": [1, 0, 1, 0, 2]})


def test_high_degree_vertex_split_rejects_non_alternate_zero():
    """A signature with non-zero entries at both even and odd indices
    is not matchgate-realisable."""
    h = HighDegreeVertexSplit(signature=[1, 1, 1, 0, 0])
    with pytest.raises(ReductionNotApplicable):
        h.apply({"values": [1, 1, 1, 0, 0]})


def test_high_degree_vertex_split_no_signature_supplied_does_not_apply():
    """Without a signature argument, the reduction does not apply."""
    h = HighDegreeVertexSplit()
    assert h.applies_to({"values": [1, 0, 1]}) is False
    with pytest.raises(ReductionNotApplicable):
        h.apply({"values": [1, 0, 1]})


def test_rationalise_weights_real_to_integer():
    """RationaliseWeights converts real-valued edge weights to integer
    weights at the requested decimal precision."""
    r = RationaliseWeights(precision=4, matching_size=2)
    graph = {
        "vertices": [0, 1, 2, 3],
        "edges": [(0, 1), (1, 2), (2, 3), (3, 0)],
        "weights": {(0, 1): 0.7, (1, 2): 0.3, (2, 3): 0.5, (3, 0): 0.9},
    }
    result = r.apply(graph)
    expected = {(0, 1): 7000, (1, 2): 3000, (2, 3): 5000, (3, 0): 9000}
    assert result.problem["weights"] == expected
    # The inverse divides by 10^(precision * matching_size) = 10^8.
    assert abs(result.inverse(12345678) - 0.12345678) < 1e-9


def test_rationalise_weights_honest_stop_on_integer_weights():
    """Already-integer weights mean the reduction has nothing to do."""
    r = RationaliseWeights()
    graph_int = {"weights": {(0, 1): 1, (1, 2): 2}}
    with pytest.raises(ReductionNotApplicable):
        r.apply(graph_int)


def test_rationalise_weights_negative_precision_raises():
    with pytest.raises(ValueError):
        RationaliseWeights(precision=-1)


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
