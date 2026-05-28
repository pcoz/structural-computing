"""Tests for the Orchestrator -- the top-level evaluate(problem, question)
engine."""

import pytest

from structural_computing import (
    Orchestrator,
    OrchestratorResult,
    NoKnownReduction,
    DEFAULT_LEAF_REGISTRY,
)


# ---------------------------------------------------------------------------
# Fixtures: known graphs
# ---------------------------------------------------------------------------

K4_TETRAHEDRON = {
    "rotation": {0: [1, 2, 3], 1: [0, 3, 2], 2: [0, 1, 3], 3: [0, 2, 1]},
    "vertices": [0, 1, 2, 3],
    "edges": [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)],
}

K33 = {
    "rotation": {0: [3, 4, 5], 1: [3, 4, 5], 2: [3, 4, 5],
                  3: [0, 1, 2], 4: [0, 1, 2], 5: [0, 1, 2]},
    "vertices": [0, 1, 2, 3, 4, 5],
    "edges": [(0, 3), (0, 4), (0, 5),
              (1, 3), (1, 4), (1, 5),
              (2, 3), (2, 4), (2, 5)],
}


# ---------------------------------------------------------------------------
# Direct dispatch (in-family + registered leaf evaluator)
# ---------------------------------------------------------------------------

def test_k4_direct_dispatch():
    """K_4 is T2; matching_count is in the leaf registry; direct dispatch."""
    orch = Orchestrator()
    r = orch.evaluate(K4_TETRAHEDRON, question="matching_count")
    assert r.answer == 3
    assert r.classification.tier == "T2"
    assert r.sub_evaluations == 1


def test_k33_direct_dispatch_via_default_t4_registry():
    """K_{3,3} classifies as T4 with the test rotation; T4 matching_count
    is in the default registry (via brute force). Direct dispatch works."""
    orch = Orchestrator()
    r = orch.evaluate(K33, question="matching_count")
    assert r.answer == 6
    assert r.classification.tier == "T4"


def test_result_carries_provenance():
    """OrchestratorResult records provenance: tier, evaluator, reductions applied."""
    orch = Orchestrator()
    r = orch.evaluate(K4_TETRAHEDRON, question="matching_count")
    assert isinstance(r, OrchestratorResult)
    assert r.leaf_evaluator_used == "_matching_count_leaf"
    assert r.classification.tier == "T2"
    # And the workflow_trace records every step.
    assert len(r.workflow_trace) >= 2          # at least classify + dispatch
    phases = [s.phase for s in r.workflow_trace]
    assert "classify" in phases
    assert "direct-dispatch" in phases


# ---------------------------------------------------------------------------
# Reduction-driven (hints supply HybridDecomposition)
# ---------------------------------------------------------------------------

def test_hybrid_decomposition_via_hints_when_t4_not_registered():
    """If we remove ('T4', 'matching_count') from the registry, the
    orchestrator falls through to the hint-driven HybridDecomposition
    path, which still produces the correct answer."""
    custom_registry = dict(DEFAULT_LEAF_REGISTRY)
    custom_registry.pop(("T4", "matching_count"))
    orch = Orchestrator(leaf_registry=custom_registry)
    r = orch.evaluate(K33, question="matching_count",
                       hints={"extra_edges": [(0, 3)]})
    assert r.answer == 6
    assert "HybridDecomposition(via hints)" in r.reductions_applied
    assert r.sub_evaluations == 2                # forced-in + forced-out branches


def test_hybrid_with_multiple_extras():
    """Hybrid with multiple extras still gives the exact answer."""
    custom_registry = dict(DEFAULT_LEAF_REGISTRY)
    custom_registry.pop(("T4", "matching_count"))
    orch = Orchestrator(leaf_registry=custom_registry)
    r = orch.evaluate(K33, question="matching_count",
                       hints={"extra_edges": [(0, 3), (1, 4), (2, 5)]})
    assert r.answer == 6


# ---------------------------------------------------------------------------
# Honest stops
# ---------------------------------------------------------------------------

def test_unsupported_question_raises():
    """A question not registered for the problem's tier -> NoKnownReduction."""
    orch = Orchestrator()
    with pytest.raises(NoKnownReduction) as exc_info:
        orch.evaluate(K4_TETRAHEDRON, question="compute_widget_count")
    # The exception carries the classification so the caller can inspect.
    assert exc_info.value.classification.tier == "T2"


def test_out_of_family_without_reduction_raises():
    """K_{3,3} with no T4 leaf and no hints -> NoKnownReduction."""
    custom_registry = dict(DEFAULT_LEAF_REGISTRY)
    custom_registry.pop(("T4", "matching_count"))
    orch = Orchestrator(leaf_registry=custom_registry)
    with pytest.raises(NoKnownReduction):
        orch.evaluate(K33, question="matching_count")


# ---------------------------------------------------------------------------
# Registry management
# ---------------------------------------------------------------------------

def test_register_custom_leaf_evaluator():
    """A user can add their own leaf evaluator."""
    def custom_leaf(problem, question):
        return 42

    orch = Orchestrator()
    orch.register_leaf_evaluator("T2", "magic_number", custom_leaf)
    r = orch.evaluate(K4_TETRAHEDRON, question="magic_number")
    assert r.answer == 42
    assert r.leaf_evaluator_used == "custom_leaf"


# ---------------------------------------------------------------------------
# Format normalisation
# ---------------------------------------------------------------------------

def test_orchestrator_handles_constraint_set():
    """The orchestrator routes constraint sets through the right classifier
    and leaf evaluator (added in v0.2)."""
    import numpy as np
    constraints = {"A": np.array([[1, 1, 0], [0, 1, 1]], dtype=int),
                    "b": np.array([1, 0], dtype=int)}
    orch = Orchestrator()
    r = orch.evaluate(constraints, question="count_solutions")
    assert r.answer == 2
    assert r.classification.tier == "T0"


def test_orchestrator_handles_signature():
    """The orchestrator routes signatures through classify_signature and
    the matchgate_rank leaf evaluator."""
    orch = Orchestrator()
    r = orch.evaluate({"values": [0, 1, 1]}, question="matchgate_rank")
    assert r.answer in (0, 1, 2)        # basis-aware rank invariant
    assert r.classification.tier == "T2"


def test_orchestrator_unknown_problem_type():
    """A problem object that doesn't match any known dispatch raises
    NoKnownReduction (not NotImplementedError)."""
    orch = Orchestrator()
    with pytest.raises(NoKnownReduction):
        orch.evaluate({"unknown_kind": "weirdness"}, question="anything")


def test_orchestrator_rationalise_weighted_matching_sum():
    """A weighted graph with float weights, asked for weighted_matching_sum,
    is auto-rationalised when `hints['rationalise_precision']` is supplied.
    The orchestrator scales the weights to integers, computes the integer
    matching sum, and divides back by 10^(precision * matching_size) so the
    final answer matches the true real-valued sum."""
    orch = Orchestrator()
    graph = {
        "rotation": {0: [1, 3], 1: [0, 2], 2: [1, 3], 3: [0, 2]},
        "vertices": [0, 1, 2, 3],
        "edges": [(0, 1), (1, 2), (2, 3), (3, 0)],
        # Two perfect matchings:
        #   (0,1) * (2,3) = 0.7 * 0.5 = 0.35
        #   (1,2) * (3,0) = 0.3 * 0.9 = 0.27
        # Total = 0.62
        "weights": {(0, 1): 0.7, (1, 2): 0.3, (2, 3): 0.5, (3, 0): 0.9},
    }
    r = orch.evaluate(graph, question="weighted_matching_sum",
                       hints={"rationalise_precision": 6})
    assert abs(r.answer - 0.62) < 1e-9
    # The rationalise phase fired with outcome ok.
    phases_and_outcomes = [(s.phase, s.outcome) for s in r.workflow_trace]
    assert ("rationalise", "ok") in phases_and_outcomes
    # And RationaliseWeights is in the reductions_applied list.
    assert "RationaliseWeights" in r.reductions_applied


def test_orchestrator_skips_rationalise_when_weights_already_integer():
    """If weights are already integer, the rationalise phase is skipped
    even when the hint is supplied."""
    orch = Orchestrator()
    graph = {
        "rotation": {0: [1, 3], 1: [0, 2], 2: [1, 3], 3: [0, 2]},
        "vertices": [0, 1, 2, 3],
        "edges": [(0, 1), (1, 2), (2, 3), (3, 0)],
        "weights": {(0, 1): 2, (1, 2): 3, (2, 3): 5, (3, 0): 7},
    }
    r = orch.evaluate(graph, question="weighted_matching_sum",
                       hints={"rationalise_precision": 6})
    # Matching 1: 2*5 = 10. Matching 2: 3*7 = 21. Total = 31.
    assert r.answer == 31
    phases_and_outcomes = [(s.phase, s.outcome) for s in r.workflow_trace]
    assert ("rationalise", "skipped") in phases_and_outcomes


def test_orchestrator_treewidth_dp_hint():
    """When a tree_decomposition hint is supplied and direct dispatch is
    NOT available for the (tier, question), the orchestrator falls back
    to TreewidthBoundedDP."""
    from structural_computing import DEFAULT_LEAF_REGISTRY
    # Force the fallback by removing matching_count leaf evaluators.
    reg = {k: v for k, v in DEFAULT_LEAF_REGISTRY.items() if k[1] != "matching_count"}
    orch = Orchestrator(leaf_registry=reg)
    C4 = {
        "rotation": {0: [1, 3], 1: [0, 2], 2: [1, 3], 3: [0, 2]},
        "vertices": [0, 1, 2, 3],
        "edges": [(0, 1), (1, 2), (2, 3), (3, 0)],
    }
    td = {"bags": [{0, 1, 3}, {1, 2, 3}], "tree_edges": [(0, 1)],
          "root_bag_index": 0}
    r = orch.evaluate(C4, "matching_count", hints={"tree_decomposition": td})
    assert r.answer == 2
    # The reductions_applied list records that TreewidthBoundedDP fired.
    assert any("TreewidthBoundedDP" in s for s in r.reductions_applied)
    # The workflow trace's treewidth-dp phase fired with outcome ok.
    phases_and_outcomes = [(s.phase, s.outcome) for s in r.workflow_trace]
    assert ("treewidth-dp", "ok") in phases_and_outcomes
