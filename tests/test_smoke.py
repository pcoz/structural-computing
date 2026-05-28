"""Smoke tests: the package imports, exports the public API, and the
wrapper works on small instances.

A proper test suite covering each primitive is the next iteration; this
file confirms the package is wired up correctly."""

import pytest

import structural_computing
from structural_computing import (
    StructuralComputer,
    CompareReport,
    NotInFamily,
    Stage,
    Route,
    run_pipeline,
    Classification,
    classify_constraint_set,
    classify_graph,
    classify_signature,
    route,
    RichTrace,
    ReplayCache,
    brute_force_count_matchings,
)


def test_version_present():
    assert structural_computing.__version__ == "0.3.0a1"


def test_public_api_complete():
    """All expected names are exported from the top level. As the public
    API grows, update both this set and structural_computing/__init__.py
    in lockstep."""
    expected = {
        # Wrapper
        "StructuralComputer", "CompareReport", "NotInFamily",
        # Pipeline framework
        "Stage", "Route", "StageRecord", "Trace",
        "run_pipeline", "run_pipeline_streaming",
        # Classifier
        "Classification", "classify", "classify_constraint_set",
        "classify_graph", "classify_signature",
        # Router
        "route",
        # Trace aggregator
        "RichTrace", "RegimeChange",
        # Replay cache
        "ReplayCache", "cached_runner", "default_key",
        # Verifier
        "brute_force_count_matchings", "brute_force_weighted_matching_sum",
        "satisfies_gf2_affine",
        "enumerate_satisfying_assignments", "gibbs_expectation_brute",
        "verify_pipeline",
        # Reductions (v0.1 foundation; concrete reductions in v0.2)
        "Reduction", "ReductionResult", "ReductionPlan", "ReductionNotApplicable",
        "NormaliseGraphFormat", "CrossingElimination", "HighDegreeVertexSplit",
        "HybridDecomposition", "RationaliseWeights",
        # Compositions
        "Composition", "CompositionPlan", "LinearCombination",
        "Projection", "HolographicBasisPair", "HolographicBasisResult", "BranchSum",
        # Recursive decomposition
        "Decomposition", "DecompositionPlan", "ShannonExpansion",
        "TreewidthBoundedDP", "PlanarSeparator", "RecursiveCircuitCut",
        # Orchestrator
        "Orchestrator", "OrchestratorResult", "WorkflowStep", "NoKnownReduction",
        "LeafEvaluator", "DEFAULT_LEAF_REGISTRY",
        # Auto-detection
        "auto_detect_extras",
        # Calibration (optional, data from structural-computing-bench)
        "apply_calibration", "clear_calibration", "get_calibration",
        "has_calibration_for", "predict_seconds",
    }
    actual = set(structural_computing.__all__) - {"__version__"}
    assert actual == expected, f"differences: {actual ^ expected}"


# ---------------------------------------------------------------------------
# StructuralComputer smoke
# ---------------------------------------------------------------------------

@pytest.fixture
def sc():
    return StructuralComputer()


def test_count_matchings_4_cycle(sc):
    assert sc.count_matchings([(0, 1), (1, 2), (2, 3), (3, 0)]) == 2


def test_count_matchings_k4(sc):
    assert sc.count_matchings([(0, 1), (0, 2), (0, 3),
                                 (1, 2), (1, 3), (2, 3)]) == 3


def test_witness_returns_valid_matching(sc):
    graph = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]
    wit = sc.witness(graph)
    # Every vertex appears exactly once across the witness edges.
    seen = set()
    for (u, v) in wit:
        assert u not in seen and v not in seen
        seen.add(u); seen.add(v)
    assert seen == {0, 1, 2, 3}


def test_tail_probability_4_cycle(sc):
    p = sc.tail_probability([(0, 1), (1, 2), (2, 3), (3, 0)], p_fail=0.05)
    # P(no matching) = (sum over edge subsets having no matching) of p^k (1-p)^(n-k)
    # 4-cycle has 2 matchings; both destroyed if any edge in one matching is removed
    # and any edge in the other matching is removed.
    # We just check the value is in a sensible range.
    assert 0.005 < p < 0.015


def test_compare_picks_more_reliable(sc):
    a = [(0, 1), (1, 2), (2, 3), (3, 0)]
    b = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]
    rep = sc.compare(a, b, p_fail=0.05)
    # K_4 is more reliable than 4-cycle at small p
    assert rep.more_reliable == "B"
    # The explain() string should mention "more reliable" and not look broken
    assert "more reliable" in rep.explain()


def test_audit_keys(sc):
    graph = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]
    audit = sc.audit(graph, p_fail=0.05)
    for required in ("classification", "tier", "in_family", "reasoning",
                      "matching_count", "witness", "single_points_of_failure"):
        assert required in audit


def test_explain_returns_string(sc):
    text = sc.explain([(0, 1), (1, 2), (2, 3), (3, 0)])
    assert isinstance(text, str) and len(text) > 0
    # Should mention "tier" and the routing decision
    assert "T" in text or "tier" in text.lower()


# ---------------------------------------------------------------------------
# Framework primitives
# ---------------------------------------------------------------------------

def test_classify_constraint_set_t0():
    import numpy as np
    A = np.array([[1, 1, 0], [0, 1, 1]], dtype=int)
    b = np.array([1, 0], dtype=int)
    cls = classify_constraint_set(A=A, b=b)
    assert cls.tier == "T0"
    assert cls.in_family


def test_route_returns_finite_cost_for_t0():
    import numpy as np
    A = np.array([[1, 1, 0], [0, 1, 1]], dtype=int)
    b = np.array([1, 0], dtype=int)
    cls = classify_constraint_set(A=A, b=b)
    r = route(cls)
    import math
    assert math.isfinite(r.cost)
    assert r.tier == "T0"


def test_run_pipeline_trivial():
    """A 3-stage trivial pipeline that adds, multiplies, squares."""
    def trivial_route(data, prev):
        return Route(member="m", cost=1.0)

    def add(d, p, r):    return (p or 0) + d
    def mul(d, p, r):    return (p or 0) * d
    def sq(d, p, r):     return (p or 0) ** 2

    stages = [
        Stage("add", "arith", 1, trivial_route, add),
        Stage("mul", "arith", 2, trivial_route, mul),
        Stage("sq",  "arith", None, trivial_route, sq),
    ]
    final, trace = run_pipeline(stages, seed=3)
    # ((3 + 1) * 2) ** 2 = 64
    assert final == 64
    assert trace.stages == 3


# ---------------------------------------------------------------------------
# ReplayCache
# ---------------------------------------------------------------------------

def test_replay_cache_basic():
    c = ReplayCache()
    assert c.size == 0
    assert c.hit_rate() == 0.0
    from structural_computing.replay import _MISS
    assert c.get("k") is _MISS
    c.put("k", 42)
    assert c.get("k") == 42


def test_brute_force_matchings():
    # K_4 has 3 perfect matchings
    assert brute_force_count_matchings(
        [0, 1, 2, 3], [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]
    ) == 3
    # 4-cycle has 2
    assert brute_force_count_matchings(
        [0, 1, 2, 3], [(0, 1), (1, 2), (2, 3), (3, 0)]
    ) == 2
    # K_3 (odd vertex count) has 0
    assert brute_force_count_matchings(
        [0, 1, 2], [(0, 1), (1, 2), (2, 0)]
    ) == 0
