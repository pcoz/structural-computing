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

def test_planar_separator_is_a_v02_sketch():
    p = PlanarSeparator()
    with pytest.raises(NotImplementedError):
        p.decompose({})


def test_recursive_circuit_cut_is_a_v02_sketch():
    r = RecursiveCircuitCut()
    with pytest.raises(NotImplementedError):
        r.decompose({})


# ---------------------------------------------------------------------------
# Honest scope: invalid tree decompositions
# ---------------------------------------------------------------------------

def test_multibag_dp_empty_bags_raises():
    """Empty bag list raises ValueError."""
    td = {"bags": [], "tree_edges": [], "root_bag_index": 0}
    decomp = TreewidthBoundedDP(tree_decomposition=td)
    with pytest.raises(ValueError):
        decomp.decompose({"vertices": [0], "edges": []})
