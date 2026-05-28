"""Tests for the decomposition layer (`decompose.py`).

Concrete decompositions in v0.2:
  - ShannonExpansion (v0.1 -- branches a Boolean variable)
  - TreewidthBoundedDP (multi-bag DP for perfect-matching count)

Sketches that still raise NotImplementedError:
  - PlanarSeparator, RecursiveCircuitCut
"""

import pytest

from structural_computing import (
    ShannonExpansion,
    TreewidthBoundedDP,
    PlanarSeparator,
    RecursiveCircuitCut,
    brute_force_count_matchings,
    DecompositionPlan,
)


# ---------------------------------------------------------------------------
# TreewidthBoundedDP -- single-bag case (v0.1) still works
# ---------------------------------------------------------------------------

def test_single_bag_decomposition_K4():
    """A trivial single-bag decomp containing all vertices: equivalent to
    brute-forcing on the whole graph."""
    K4_edges = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]
    decomp = TreewidthBoundedDP()                # default: synthesise single bag
    plan = decomp.decompose({"vertices": [0, 1, 2, 3], "edges": K4_edges})
    count = plan.evaluate(
        lambda p: brute_force_count_matchings(p["vertices"], p["edges"])
    )
    assert count == 3                             # K_4 has 3 perfect matchings


# ---------------------------------------------------------------------------
# TreewidthBoundedDP -- multi-bag DP (v0.2)
# ---------------------------------------------------------------------------

def test_multibag_dp_C4():
    """C_4 (4-cycle) has 2 perfect matchings via a 2-bag tree decomp."""
    C4_edges = [(0, 1), (1, 2), (2, 3), (3, 0)]
    td = {
        "bags": [{0, 1, 3}, {1, 2, 3}],
        "tree_edges": [(0, 1)],
        "root_bag_index": 0,
    }
    decomp = TreewidthBoundedDP(tree_decomposition=td)
    plan = decomp.decompose({"vertices": [0, 1, 2, 3], "edges": C4_edges})
    # Plan has a precomputed value -- evaluate returns it directly.
    count = plan.evaluate(lambda _p: 0)
    assert count == 2


def test_multibag_dp_P4():
    """Path P_4 has 1 perfect matching."""
    td = {
        "bags": [{0, 1}, {1, 2}, {2, 3}],
        "tree_edges": [(0, 1), (1, 2)],
        "root_bag_index": 0,
    }
    decomp = TreewidthBoundedDP(tree_decomposition=td)
    plan = decomp.decompose({"vertices": [0, 1, 2, 3],
                               "edges": [(0, 1), (1, 2), (2, 3)]})
    assert plan.evaluate(lambda _p: 0) == 1


def test_multibag_dp_C6():
    """6-cycle has 2 perfect matchings; verifies via a 4-bag path decomp."""
    C6_edges = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 0)]
    td = {
        "bags": [{0, 1, 5}, {1, 2, 5}, {2, 3, 5}, {3, 4, 5}],
        "tree_edges": [(0, 1), (1, 2), (2, 3)],
        "root_bag_index": 0,
    }
    decomp = TreewidthBoundedDP(tree_decomposition=td)
    plan = decomp.decompose({"vertices": list(range(6)), "edges": C6_edges})
    expected = brute_force_count_matchings(list(range(6)), C6_edges)
    assert plan.evaluate(lambda _p: 0) == expected == 2


def test_multibag_dp_path_5_vertices_zero_matching():
    """An odd-vertex path P_5 has 0 perfect matchings."""
    td = {
        "bags": [{0, 1}, {1, 2}, {2, 3}, {3, 4}],
        "tree_edges": [(0, 1), (1, 2), (2, 3)],
        "root_bag_index": 0,
    }
    decomp = TreewidthBoundedDP(tree_decomposition=td)
    plan = decomp.decompose({"vertices": [0, 1, 2, 3, 4],
                               "edges": [(0, 1), (1, 2), (2, 3), (3, 4)]})
    assert plan.evaluate(lambda _p: 0) == 0


# ---------------------------------------------------------------------------
# DecompositionPlan -- precomputed-value mode
# ---------------------------------------------------------------------------

def test_decomposition_plan_precomputed():
    """A plan with has_precomputed_value=True returns the stored value
    directly, ignoring leaf_evaluator entirely."""
    plan = DecompositionPlan(
        problem=None,
        has_precomputed_value=True,
        precomputed_value=42,
    )
    assert plan.evaluate(lambda x: 99) == 42      # leaf evaluator NOT called


# ---------------------------------------------------------------------------
# Sketches that remain NotImplementedError
# ---------------------------------------------------------------------------

def test_planar_separator_recovers_c4_unweighted():
    """C_4 with separator {1, 3} decomposes into 4 partition patterns;
    the sum matches the brute-force matching count (2)."""
    graph = {
        "vertices": [0, 1, 2, 3],
        "edges": [(0, 1), (1, 2), (2, 3), (3, 0)],
    }
    sep = PlanarSeparator(separator={1, 3}, side_a={0}, side_b={2})
    plan = sep.decompose(graph)
    leaf = lambda p: brute_force_count_matchings(p["vertices"], p["edges"])
    assert plan.evaluate(leaf) == 2


def test_planar_separator_recovers_c6_unweighted():
    """C_6 with separator {1, 4}: brute force matches separator decomposition."""
    graph = {
        "vertices": [0, 1, 2, 3, 4, 5],
        "edges": [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 0)],
    }
    sep = PlanarSeparator(separator={1, 4},
                            side_a={0, 5}, side_b={2, 3})
    plan = sep.decompose(graph)
    leaf = lambda p: brute_force_count_matchings(p["vertices"], p["edges"])
    expected = brute_force_count_matchings(graph["vertices"], graph["edges"])
    assert plan.evaluate(leaf) == expected


def test_planar_separator_recovers_c4_weighted():
    """Weighted C_4 with non-unit weights -- separator sum matches the
    weighted matching sum exactly."""
    from structural_computing import brute_force_weighted_matching_sum
    graph = {
        "vertices": [0, 1, 2, 3],
        "edges": [(0, 1), (1, 2), (2, 3), (3, 0)],
        "weights": {(0, 1): 2, (1, 2): 3, (2, 3): 5, (3, 0): 7},
    }
    expected = brute_force_weighted_matching_sum(
        graph["vertices"], graph["edges"], graph["weights"])
    assert expected == 31         # 2*5 + 3*7
    sep = PlanarSeparator(separator={1, 3}, side_a={0}, side_b={2})
    plan = sep.decompose(graph)
    leaf = lambda p: brute_force_weighted_matching_sum(
        p["vertices"], p["edges"], p.get("weights", {}))
    assert abs(plan.evaluate(leaf) - 31) < 1e-9


def test_planar_separator_rejects_non_partition():
    """side_a + side_b + separator must cover all vertices."""
    graph = {"vertices": [0, 1, 2, 3], "edges": []}
    with pytest.raises(ValueError):
        PlanarSeparator(separator={1}, side_a={0}, side_b={2}).decompose(graph)


def test_planar_separator_rejects_overlapping_sides():
    """The three sets must be pairwise disjoint."""
    graph = {"vertices": [0, 1, 2, 3], "edges": []}
    with pytest.raises(ValueError):
        PlanarSeparator(separator={1, 2}, side_a={0, 1}, side_b={3}).decompose(graph)


def test_planar_separator_rejects_edge_crossing_sides():
    """An edge directly connecting side_a to side_b means the separator
    isn't a real separator -- reject."""
    graph = {
        "vertices": [0, 1, 2, 3],
        "edges": [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)],
    }
    with pytest.raises(ValueError):
        PlanarSeparator(separator={1, 3}, side_a={0}, side_b={2}).decompose(graph)


def test_recursive_circuit_cut_recovers_k4_unweighted():
    """K_4 cut along its two diagonals: enumerate 2^2=4 forced-in/out
    masks, sum weighted PerfMatches of the sub-graphs. Should give 3
    (the K_4 unweighted matching count)."""
    K4 = {
        "vertices": [0, 1, 2, 3],
        "edges": [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2), (1, 3)],
    }
    rcc = RecursiveCircuitCut(cut=[(0, 2), (1, 3)])
    plan = rcc.decompose(K4)
    leaf = lambda p: brute_force_count_matchings(p["vertices"], p["edges"])
    assert plan.evaluate(leaf) == 3


def test_recursive_circuit_cut_recovers_weighted_k4():
    """Weighted K_4 cut on the two diagonals: the RCC sum exactly
    matches the brute-force weighted matching sum."""
    from structural_computing import brute_force_weighted_matching_sum
    K4 = {
        "vertices": [0, 1, 2, 3],
        "edges": [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2), (1, 3)],
        "weights": {(0, 1): 2, (1, 2): 3, (2, 3): 5, (3, 0): 7,
                     (0, 2): 11, (1, 3): 13},
    }
    expected = brute_force_weighted_matching_sum(
        K4["vertices"], K4["edges"], K4["weights"])
    rcc = RecursiveCircuitCut(cut=[(0, 2), (1, 3)])
    plan = rcc.decompose(K4)
    leaf = lambda p: brute_force_weighted_matching_sum(
        p["vertices"], p["edges"], p.get("weights", {}))
    assert abs(plan.evaluate(leaf) - expected) < 1e-9


def test_recursive_circuit_cut_rejects_edges_not_in_graph():
    """A cut edge that's not present in the graph raises ValueError."""
    K4 = {"vertices": [0, 1, 2, 3],
           "edges": [(0, 1), (1, 2), (2, 3), (3, 0)]}
    with pytest.raises(ValueError):
        RecursiveCircuitCut(cut=[(99, 100)]).decompose(K4)


def test_recursive_circuit_cut_prunes_shared_endpoint_forced_in_subsets():
    """A cut containing two edges sharing a vertex: the 'both-forced-in'
    subset is invalid (the matching can't contain both); RCC prunes it."""
    K4 = {"vertices": [0, 1, 2, 3],
           "edges": [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2), (1, 3)]}
    rcc = RecursiveCircuitCut(cut=[(0, 1), (0, 2)])           # both touch vertex 0
    plan = rcc.decompose(K4)
    # 4 total masks; mask=11 (both forced-in, sharing vertex 0) is pruned
    # -> 3 sub-problems.
    assert len(plan.children) == 3


# ---------------------------------------------------------------------------
# Honest scope: invalid tree decompositions
# ---------------------------------------------------------------------------

def test_multibag_dp_empty_bags_raises():
    """Empty bag list raises ValueError."""
    td = {"bags": [], "tree_edges": [], "root_bag_index": 0}
    decomp = TreewidthBoundedDP(tree_decomposition=td)
    with pytest.raises(ValueError):
        decomp.decompose({"vertices": [0], "edges": []})
