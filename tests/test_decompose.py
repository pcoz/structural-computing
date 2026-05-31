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


# ---------------------------------------------------------------------------
# v0.4: Lipton-Tarjan auto-separator for PlanarSeparator
# ---------------------------------------------------------------------------
#
# These tests cover the auto-discovery path: PlanarSeparator(auto=True)
# invokes the BFS-layer simple case of Lipton-Tarjan 1979 in decompose().
# Verify (a) the partition properties, (b) the size bound 2*sqrt(2|V|),
# (c) round-trip with brute-force matching count on canonical planar
# graphs, and (d) the honest-stop on disconnected / failing inputs.


def _make_planar_grid(d: int):
    """Build a d-by-d planar grid as a graph dict."""
    verts = [(i, j) for i in range(d) for j in range(d)]
    edges = []
    for i in range(d):
        for j in range(d):
            if i + 1 < d:
                edges.append(((i, j), (i + 1, j)))
            if j + 1 < d:
                edges.append(((i, j), (i, j + 1)))
    return {"vertices": verts, "edges": edges}


def test_lipton_tarjan_partition_is_valid_on_grids():
    """The discovered (S, A, B) partition the vertex set, and no edge
    connects A and B directly. Verified on planar grids of sizes 3-6."""
    from structural_computing.decompose import _lipton_tarjan_separator
    for d in (3, 4, 5, 6):
        g = _make_planar_grid(d)
        S, A, B = _lipton_tarjan_separator(g)
        # Cover: S ∪ A ∪ B = V.
        assert S | A | B == set(g["vertices"])
        # Disjoint: pairwise disjoint.
        assert not (S & A) and not (S & B) and not (A & B)
        # No direct A-B edge.
        for (u, v) in g["edges"]:
            assert not ((u in A and v in B) or (u in B and v in A)), \
                f"d={d}: edge {(u, v)} crosses A-B directly"


def test_lipton_tarjan_size_bound_holds_on_grids():
    """The Lipton-Tarjan theorem guarantees |S| <= 2*sqrt(2|V|). Verify
    on planar grids."""
    import math
    from structural_computing.decompose import _lipton_tarjan_separator
    for d in (3, 4, 5, 6, 7, 8):
        g = _make_planar_grid(d)
        n = len(g["vertices"])
        S, A, B = _lipton_tarjan_separator(g)
        bound = 2.0 * math.sqrt(2.0 * n)
        assert len(S) <= bound, \
            f"d={d}, n={n}: |S|={len(S)} exceeds bound {bound:.2f}"


def test_lipton_tarjan_balanced_sides_on_grids():
    """The Lipton-Tarjan theorem guarantees |A|, |B| <= 2|V|/3. Verify
    on planar grids."""
    from structural_computing.decompose import _lipton_tarjan_separator
    for d in (4, 5, 6, 7, 8):
        g = _make_planar_grid(d)
        n = len(g["vertices"])
        S, A, B = _lipton_tarjan_separator(g)
        bound = 2.0 * n / 3.0
        assert len(A) <= bound, \
            f"d={d}: |A|={len(A)} exceeds 2|V|/3 = {bound}"
        assert len(B) <= bound, \
            f"d={d}: |B|={len(B)} exceeds 2|V|/3 = {bound}"


def test_lipton_tarjan_handles_k4():
    """K_4 (4-vertex complete graph) is planar; auto-separator should
    return a valid partition (possibly trivial: K_4 is small enough
    that the bound 2*sqrt(8) ~ 5.66 exceeds n=4, so the entire vertex
    set as the separator is OK)."""
    from structural_computing.decompose import _lipton_tarjan_separator
    g = {"vertices": [0, 1, 2, 3],
         "edges": [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]}
    S, A, B = _lipton_tarjan_separator(g)
    assert S | A | B == set(g["vertices"])


def test_lipton_tarjan_handles_cycles():
    """Cycle graphs C_n are planar; the BFS-layer gives clean
    separators (typically size 2)."""
    from structural_computing.decompose import _lipton_tarjan_separator
    for n in (4, 6, 8, 10):
        verts = list(range(n))
        edges = [(i, (i + 1) % n) for i in range(n)]
        g = {"vertices": verts, "edges": edges}
        S, A, B = _lipton_tarjan_separator(g)
        assert S | A | B == set(verts)
        # No A-B direct edge.
        for (u, v) in edges:
            assert not ((u in A and v in B) or (u in B and v in A)), \
                f"C_{n}: edge {(u, v)} crosses A-B"


def test_lipton_tarjan_disconnected_raises():
    """Disconnected graphs aren't handled by the simple case (BFS
    only reaches one component). The function honestly raises
    ValueError so the caller knows to fall back."""
    from structural_computing.decompose import _lipton_tarjan_separator
    g = {"vertices": [0, 1, 2, 3], "edges": [(0, 1), (2, 3)]}
    with pytest.raises(ValueError, match="disconnected"):
        _lipton_tarjan_separator(g)


def test_lipton_tarjan_trivial_small_graph():
    """Graphs with n < 3 trivially return (V, empty, empty)."""
    from structural_computing.decompose import _lipton_tarjan_separator
    S, A, B = _lipton_tarjan_separator({"vertices": [0, 1], "edges": [(0, 1)]})
    assert S == {0, 1}
    assert A == set()
    assert B == set()


def test_planar_separator_auto_mode_round_trip_on_grids():
    """End-to-end: PlanarSeparator(auto=True) on a 4x4 planar grid
    produces a matching count agreeing with brute-force."""
    g = _make_planar_grid(4)
    sep = PlanarSeparator(auto=True)
    plan = sep.decompose(g)
    auto_count = plan.evaluate(
        lambda p: brute_force_count_matchings(p["vertices"], p["edges"])
    )
    brute_count = brute_force_count_matchings(g["vertices"], g["edges"])
    assert int(auto_count) == brute_count, \
        f"auto={auto_count}, brute={brute_count}"


def test_planar_separator_auto_round_trip_on_cycles():
    """Auto-PlanarSeparator on cycle graphs C_4, C_6 -- a clean
    test case where the partition is unambiguous."""
    for n in (4, 6):
        verts = list(range(n))
        edges = [(i, (i + 1) % n) for i in range(n)]
        g = {"vertices": verts, "edges": edges}
        sep = PlanarSeparator(auto=True)
        plan = sep.decompose(g)
        auto_count = plan.evaluate(
            lambda p: brute_force_count_matchings(p["vertices"], p["edges"])
        )
        brute_count = brute_force_count_matchings(verts, edges)
        assert int(auto_count) == brute_count, \
            f"C_{n}: auto={auto_count}, brute={brute_count}"


def test_planar_separator_auto_re_discovers_per_call():
    """A single PlanarSeparator(auto=True) instance should re-discover
    the separator when decompose() is called on a different graph.
    (Important when the same instance is reused, e.g., across a
    pipeline of similar but distinct sub-problems.)"""
    g1 = _make_planar_grid(3)
    g2 = _make_planar_grid(4)
    sep = PlanarSeparator(auto=True)
    sep.decompose(g1)
    sep1 = sep.separator
    sep.decompose(g2)
    sep2 = sep.separator
    # Different graphs should produce different separator vertex sets.
    assert sep1 != sep2, "auto mode should re-discover per decompose call"


def test_planar_separator_auto_mode_constructor_validation():
    """auto=False (default) without explicit sets raises ValueError;
    auto=True without sets is fine."""
    # auto=False, no sets -> error.
    with pytest.raises(ValueError, match="separator"):
        PlanarSeparator()
    # auto=True, no sets -> fine.
    sep = PlanarSeparator(auto=True)
    assert sep.auto is True
    assert sep.separator is None  # populated by decompose()
