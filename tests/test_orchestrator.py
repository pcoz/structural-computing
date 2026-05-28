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
    assert r.leaf_evaluator_used == "_brute_force_matching_leaf"
    assert r.classification.tier == "T2"


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

def test_orchestrator_handles_constraint_set_dispatch_error():
    """Constraint sets / signatures aren't yet routed through the
    orchestrator; the wrapper handles those directly. Make sure the
    error is clean."""
    orch = Orchestrator()
    with pytest.raises(NotImplementedError):
        orch.evaluate({"constraints": "something"}, question="count_solutions")
