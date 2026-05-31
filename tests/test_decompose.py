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


# ---------------------------------------------------------------------------
# v0.5 Deliverable 2: spanning-tree fundamental-cycle backup
#
# The backup catches planar graphs where the v0.4 BFS-layer simple case
# fails because every BFS level violates either the size bound or one
# of the partition bounds. Canonical adversarial example: the
# "double-star" (two centers connected, each with many leaves). The
# obvious separator is the two centers, but BFS-layer search can't
# see it because the level containing both leaves AND the other
# center is too fat.
# ---------------------------------------------------------------------------


def _make_double_star(k, m):
    """Double-star graph: vertices 0, 1 are centers connected to each
    other; vertices 2..k+1 are leaves of 0; vertices k+2..k+m+1 are
    leaves of 1. n = k + m + 2."""
    verts = [0, 1] + list(range(2, 2 + k + m))
    edges = [(0, 1)]
    for i in range(k):
        edges.append((0, 2 + i))
    for j in range(m):
        edges.append((1, 2 + k + j))
    return {"vertices": verts, "edges": edges}


def test_v05_tree_backup_catches_double_star():
    """The v0.4 simple case fails on a sufficiently large symmetric
    double-star (n=42 with k=m=20: every level fails either the
    2*sqrt(2n) size bound or the 2n/3 partition bounds). v0.5's
    tree-edge backup catches it, finding the optimal |S|=2 separator
    {center_0, center_1}."""
    import math
    from structural_computing.decompose import _lipton_tarjan_separator
    g = _make_double_star(20, 20)
    n = len(g["vertices"])
    bound_S = 2.0 * math.sqrt(2.0 * n)
    S, A, B = _lipton_tarjan_separator(g)
    assert S == {0, 1}, \
        f"expected optimal separator {{0, 1}} on double-star, got {S}"
    assert len(S) <= bound_S
    assert len(A) <= 2 * n / 3
    assert len(B) <= 2 * n / 3
    # No A-B direct edge.
    for (u, v) in g["edges"]:
        assert not ((u in A and v in B) or (u in B and v in A))


def test_v05_tree_backup_handles_various_double_stars():
    """The backup handles a range of double-star sizes correctly,
    always finding a valid partition within the LT bounds."""
    import math
    from structural_computing.decompose import _lipton_tarjan_separator
    for (k, m) in [(15, 15), (20, 20), (25, 25), (30, 30), (50, 50)]:
        g = _make_double_star(k, m)
        n = len(g["vertices"])
        bound_S = 2.0 * math.sqrt(2.0 * n)
        S, A, B = _lipton_tarjan_separator(g)
        # Partition validity.
        assert S | A | B == set(g["vertices"])
        assert not (S & A) and not (S & B) and not (A & B)
        # No A-B direct edge.
        for (u, v) in g["edges"]:
            assert not ((u in A and v in B) or (u in B and v in A)), \
                f"ds({k},{m}): edge {(u,v)} crosses A-B"
        # Size + balance bounds.
        assert len(S) <= bound_S, \
            f"ds({k},{m}): |S|={len(S)} > 2*sqrt(2n)={bound_S:.2f}"
        assert len(A) <= 2 * n / 3
        assert len(B) <= 2 * n / 3


def test_v05_planar_separator_auto_works_on_double_star():
    """End-to-end: PlanarSeparator(auto=True) with the v0.5 backup
    succeeds on a double-star, and the matching-count via the
    decomposition equals brute force."""
    g = _make_double_star(20, 20)
    sep = PlanarSeparator(auto=True)
    plan = sep.decompose(g)
    auto_count = plan.evaluate(
        lambda p: brute_force_count_matchings(p["vertices"], p["edges"])
    )
    brute_count = brute_force_count_matchings(g["vertices"], g["edges"])
    # Double-star with k=m has perfect matchings only if k+m+2 is even
    # AND the structure permits it. For k=m=20: n=42 (even). Each
    # center must match with one of its leaves; the connecting edge
    # (0,1) takes both centers; etc. Just verify auto == brute.
    assert int(auto_count) == brute_count, \
        f"auto={auto_count}, brute={brute_count}"


def test_v05_tree_backup_disconnected_still_raises():
    """The backup does NOT change the disconnected-graph behaviour:
    the connectivity check happens before backup invocation in the
    simple case, so disconnected still raises immediately."""
    import pytest
    from structural_computing.decompose import _lipton_tarjan_separator
    g = {"vertices": [0, 1, 2, 3], "edges": [(0, 1), (2, 3)]}
    with pytest.raises(ValueError, match="disconnected"):
        _lipton_tarjan_separator(g)


# ---------------------------------------------------------------------------
# v0.6 Deliverable 2: level-based + articulation-augmentation backup.
#
# Catches "star-like" planar graphs where BOTH v0.4's simple BFS-layer
# case AND v0.5's tree-edge augmentation backup fail. Canonical
# adversarial examples: K_{1, n} (star) and K_{2, n} (complete
# bipartite "book").
# ---------------------------------------------------------------------------


def _make_star(n):
    """Star K_{1, n}: vertex 0 connected to vertices 1..n. n+1 total."""
    return {"vertices": list(range(n + 1)),
            "edges": [(0, i) for i in range(1, n + 1)]}


def _make_K_2_n(n):
    """K_{2, n}: two spine vertices 0, 1; n page vertices 2..n+1, each
    connected to BOTH spine vertices. n+2 total. Planar."""
    verts = [0, 1] + list(range(2, 2 + n))
    edges = [(0, i) for i in range(1, 2 + n)] + [(1, i) for i in range(2, 2 + n)]
    return {"vertices": verts, "edges": edges}


def test_v06_d2_level_backup_catches_star():
    """v0.4's simple case + v0.5's tree-edge backup BOTH fail on a
    20-leaf star: every BFS level violates either size or partition
    bounds; the BFS spanning tree has no balanced tree edge (every
    leaf has subtree_size = 1). v0.6's level-based backup finds the
    optimal separator S = {0} (the center)."""
    import math
    from structural_computing.decompose import _lipton_tarjan_separator
    g = _make_star(20)
    n = len(g["vertices"])
    S, A, B = _lipton_tarjan_separator(g)
    assert S == {0}, f"expected optimal separator {{0}}, got {S}"
    assert len(S) <= 2.0 * math.sqrt(2.0 * n)
    assert len(A) <= 2 * n / 3
    assert len(B) <= 2 * n / 3
    # Star edges all go from center to leaves; no leaf-leaf edges.
    for (u, v) in g["edges"]:
        assert not ((u in A and v in B) or (u in B and v in A))


def test_v06_d2_level_backup_catches_K_2_n():
    """K_{2, 20} defeats v0.4 + v0.5: both spine vertices live in the
    fat BFS level. v0.6's level-based backup starts with S = {spine_0}
    (the BFS root level), finds the residual has one mega-component
    (spine_1 + all 20 pages, since spine_1 connects to all pages),
    augments S with spine_1 (highest residual degree), bin-packs the
    remaining 20 isolated pages 10/10."""
    import math
    from structural_computing.decompose import _lipton_tarjan_separator
    g = _make_K_2_n(20)
    n = len(g["vertices"])
    S, A, B = _lipton_tarjan_separator(g)
    assert S == {0, 1}, f"expected optimal separator {{0, 1}}, got {S}"
    assert len(S) <= 2.0 * math.sqrt(2.0 * n)
    assert len(A) <= 2 * n / 3
    assert len(B) <= 2 * n / 3
    for (u, v) in g["edges"]:
        assert not ((u in A and v in B) or (u in B and v in A))


def test_v06_d2_level_backup_handles_various_star_sizes():
    """The level-based backup handles star K_{1, n} for a range of n,
    always finding the optimal |S| = 1 separator."""
    import math
    from structural_computing.decompose import _lipton_tarjan_separator
    for n_leaves in (10, 20, 30, 50):
        g = _make_star(n_leaves)
        n = len(g["vertices"])
        S, A, B = _lipton_tarjan_separator(g)
        assert S == {0}, f"star({n_leaves}): expected {{0}}, got {S}"
        # Balanced partition of leaves (within rounding for odd n).
        assert abs(len(A) - len(B)) <= 1, \
            f"star({n_leaves}): expected balanced leaves, " \
            f"got |A|={len(A)}, |B|={len(B)}"


def test_v06_d2_level_backup_handles_various_K_2_n_sizes():
    """The level-based backup handles K_{2, n} for a range of n,
    always finding the optimal |S| = 2 separator."""
    import math
    from structural_computing.decompose import _lipton_tarjan_separator
    for n_pages in (10, 20, 30, 50):
        g = _make_K_2_n(n_pages)
        n = len(g["vertices"])
        S, A, B = _lipton_tarjan_separator(g)
        assert S == {0, 1}, \
            f"K_{{2,{n_pages}}}: expected {{0, 1}}, got {S}"
        # Pages bin-packed balanced.
        assert abs(len(A) - len(B)) <= 1


def test_v06_d2_planar_separator_auto_works_on_star():
    """End-to-end: PlanarSeparator(auto=True) on a star, using the
    v0.6 D2 level-based backup, gives the same matching count as
    brute force (= 0 for odd-cardinality star)."""
    g = _make_star(20)
    sep = PlanarSeparator(auto=True)
    plan = sep.decompose(g)
    auto_count = plan.evaluate(
        lambda p: brute_force_count_matchings(p["vertices"], p["edges"])
    )
    brute_count = brute_force_count_matchings(g["vertices"], g["edges"])
    assert int(auto_count) == brute_count


def test_v06_d2_disconnected_still_raises():
    """The v0.6 backup chain is invoked AFTER the connectivity check;
    disconnected inputs still honest-stop before reaching D2."""
    from structural_computing.decompose import _lipton_tarjan_separator
    g = {"vertices": [0, 1, 2, 3], "edges": [(0, 1), (2, 3)]}
    with pytest.raises(ValueError, match="disconnected"):
        _lipton_tarjan_separator(g)
