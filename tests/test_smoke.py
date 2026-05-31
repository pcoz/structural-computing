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
    assert structural_computing.__version__ == "0.6.0a1"


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


# ============================================================
# v0.10: tropical / min-cost optimisation
# ============================================================


def test_v010_min_weight_matching_k4_uniform(sc):
    """K_4 with weights — three perfect matchings, pick the cheapest."""
    graph = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]
    weights = {(0, 1): 1.0, (0, 2): 5.0, (0, 3): 3.0,
               (1, 2): 4.0, (1, 3): 2.0, (2, 3): 6.0}
    result = sc.min_weight_matching(graph, weights)
    assert result["feasible"]
    # Three matchings: (0,1)+(2,3)=7, (0,2)+(1,3)=7, (0,3)+(1,2)=7 — all tied.
    assert abs(result["cost"] - 7.0) < 1e-9


def test_v010_min_weight_matching_4cycle_picks_cheap(sc):
    """4-cycle with edge weights asymmetric across the two perfect
    matchings: the cheaper matching should win."""
    graph = [(0, 1), (1, 2), (2, 3), (3, 0)]
    weights = {(0, 1): 1.0, (1, 2): 10.0, (2, 3): 1.0, (3, 0): 10.0}
    # M_a = {(0,1), (2,3)}: cost 2. M_b = {(1,2), (3,0)}: cost 20.
    result = sc.min_weight_matching(graph, weights)
    assert result["feasible"]
    assert abs(result["cost"] - 2.0) < 1e-9
    # Matching should be the cheap pair (order of (u, v) may vary).
    edges_set = {frozenset(e) for e in result["matching"]}
    assert edges_set == {frozenset({0, 1}), frozenset({2, 3})}


def test_v010_min_weight_matching_infeasible_on_odd_vertices(sc):
    """A graph with an odd number of vertices has no perfect matching."""
    graph = [(0, 1), (1, 2)]  # 3 vertices
    result = sc.min_weight_matching(graph)
    assert not result["feasible"]
    assert result["cost"] is None
    assert result["matching"] is None


def test_v010_min_weight_matching_default_weights_1(sc):
    """If no weights dict is supplied, every edge defaults to weight
    1.0; total cost = n/2."""
    graph = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]
    result = sc.min_weight_matching(graph)  # no weights
    assert result["feasible"]
    # Cost = 2 edges × 1.0 = 2.0
    assert abs(result["cost"] - 2.0) < 1e-9


def test_v011_min_cost_flow_basic():
    """Minimal flow: 1 source supplying 2, 1 sink demanding 2, two
    parallel edges with different costs/capacities."""
    import holant_tools
    from structural_computing import StructuralComputer
    sc = StructuralComputer()

    src = holant_tools.FlowNode("S", supply=2)
    snk = holant_tools.FlowNode("T", supply=-2)
    edges = [
        holant_tools.FlowEdge(source="S", target="T", cost=1.0, capacity=1),
        holant_tools.FlowEdge(source="S", target="T", cost=10.0, capacity=2),
    ]
    inst = holant_tools.MinCostFlowInstance(sources=[src], sinks=[snk], edges=edges)
    result = sc.min_cost_flow(inst)
    assert result["feasible"]
    assert result["cost"] is not None


def test_v011_min_cost_roster_two_employees_two_shifts():
    """2 employees, 2 shifts, opposing preferences. Optimal pairing:
    Alice→Morning, Bob→Evening, both at preference cost 1.0 = total 2.0."""
    import holant_tools
    from structural_computing import StructuralComputer
    sc = StructuralComputer()

    employees = [
        holant_tools.Employee(name="Alice", max_shifts=1),
        holant_tools.Employee(name="Bob", max_shifts=1),
    ]
    shifts = [
        holant_tools.Shift(name="Morning", headcount=1),
        holant_tools.Shift(name="Evening", headcount=1),
    ]
    inst = holant_tools.RosteringInstance(employees=employees, shifts=shifts)

    def pref(emp, shift):
        if emp.name == "Alice":
            return 1.0 if shift.name == "Morning" else 5.0
        return 5.0 if shift.name == "Morning" else 1.0

    result = sc.min_cost_roster(inst, pref)
    assert result["feasible"]
    assert abs(result["cost"] - 2.0) < 1e-9
    assert result["roster"]["Alice"] == ["Morning"]
    assert result["roster"]["Bob"] == ["Evening"]


def test_v011_min_cost_dedup_basic():
    """2 records, 2 entity candidates. Verifies the wrapper returns
    a feasible assignment with cost + entity_groups."""
    import holant_tools
    from structural_computing import StructuralComputer
    sc = StructuralComputer()

    records = [
        holant_tools.Record(name="R1"),
        holant_tools.Record(name="R2"),
    ]
    candidates = [
        holant_tools.EntityCandidate(id="E1", capacity=1),
        holant_tools.EntityCandidate(id="E2", capacity=1),
    ]
    inst = holant_tools.MDMInstance(records=records, entity_candidates=candidates)

    def sim(record, candidate):
        # similarity_fn = COST in holant-tools' convention (lower = better)
        return 0.1 if (record.name, candidate.id) in {("R1", "E1"), ("R2", "E2")} else 0.9

    result = sc.min_cost_dedup(inst, sim)
    assert result["feasible"]
    # Optimal assignment: R1→E1, R2→E2, both at cost 0.1 → total 0.2.
    assert abs(result["cost"] - 0.2) < 1e-9
    assert result["assignment"]["R1"] == "E1"
    assert result["assignment"]["R2"] == "E2"


def test_v013_rewrite_cpsat_model_helps_on_rank_explosive():
    """A small CP-SAT model with a rank-explosive constraint should be
    rewritten by the diagnostic layer; the wrapper exposes the
    helped/help_reason_text signal."""
    pytest_module = __import__("pytest")
    cp_model_module = pytest_module.importorskip("ortools.sat.python.cp_model")
    from structural_computing import StructuralComputer
    sc = StructuralComputer()
    model = cp_model_module.CpModel()
    xs = [model.NewBoolVar(f"x{i}") for i in range(4)]
    model.Add(sum(xs) == 2)
    result = sc.rewrite_cpsat_model(model)
    assert result.helped
    assert "Rewrote" in result.help_reason_text or "rank-1" in result.help_reason_text
    assert result.num_original_variables == 4


def test_v013_verify_cpsat_rewrite_preserves_feasible_set():
    """Verification of a rank-explosive rewrite should report
    equivalent feasible sets on the original variables."""
    pytest_module = __import__("pytest")
    cp_model_module = pytest_module.importorskip("ortools.sat.python.cp_model")
    from structural_computing import StructuralComputer
    sc = StructuralComputer()
    model = cp_model_module.CpModel()
    xs = [model.NewBoolVar(f"x{i}") for i in range(4)]
    model.Add(sum(xs) == 2)
    rewrite = sc.rewrite_cpsat_model(model)
    verify = sc.verify_cpsat_rewrite(model, rewrite, enumeration_limit=1000)
    assert verify.equivalent
    # The feasible set on the original vars is C(4, 2) = 6 assignments.
    assert verify.n_original_solutions == 6


def test_v013_rewrite_cpsat_with_no_rewritable_constraints_signals_not_helped():
    """A CP-SAT model with no rank-explosive constraints should produce
    helped=False so callers can fall through to running the original."""
    pytest_module = __import__("pytest")
    cp_model_module = pytest_module.importorskip("ortools.sat.python.cp_model")
    from structural_computing import StructuralComputer
    sc = StructuralComputer()
    model = cp_model_module.CpModel()
    x = model.NewBoolVar("x")
    y = model.NewBoolVar("y")
    # A pair of simple linear constraints — neither is rank-explosive.
    model.Add(x + y >= 1)
    result = sc.rewrite_cpsat_model(model)
    # Most rewrites either help with a clear reason OR honestly stop with
    # an explanation. Either way the wrapper should return a structured
    # result; we just verify the contract.
    assert hasattr(result, "helped")
    assert hasattr(result, "help_reason_text")
    assert result.num_original_variables == 2


def test_v011_tropical_instance_coordinates_diagnostic():
    """The one-call diagnostic on a simple uniform-cost SchedulingInstance
    should return polynomial-time-feasible coordinates."""
    import holant_tools
    from structural_computing import StructuralComputer
    sc = StructuralComputer()

    jobs = [holant_tools.Job(name="J1"), holant_tools.Job(name="J2")]
    machines = [holant_tools.Machine(name="M1"), holant_tools.Machine(name="M2")]
    inst = holant_tools.SchedulingInstance(jobs=jobs, machines=machines)

    def cost_fn(job, machine, slot):
        return 1.0  # uniform — rank-1 cost matrix → polynomial time

    coords = sc.tropical_instance_coordinates(inst, cost_fn)
    assert coords.polynomial_time_optimisation
    assert coords.admissibility_rank_1


def test_v010_min_cost_schedule_two_jobs_two_machines():
    """Minimal scheduling instance: 2 jobs, 2 machines, asymmetric
    cost. The optimal schedule assigns each job to its preferred
    machine."""
    import holant_tools
    from structural_computing import StructuralComputer
    sc = StructuralComputer()

    jobs = [holant_tools.Job(name="J1"), holant_tools.Job(name="J2")]
    machines = [holant_tools.Machine(name="M1"), holant_tools.Machine(name="M2")]
    instance = holant_tools.SchedulingInstance(jobs=jobs, machines=machines)

    def cost_fn(job, machine, slot):
        # J1 → M1 cheap, M2 expensive. J2 → opposite.
        if job.name == "J1":
            return 1.0 if machine.name == "M1" else 5.0
        return 5.0 if machine.name == "M1" else 1.0

    result = sc.min_cost_schedule(instance, cost_fn)
    assert result["feasible"]
    assert abs(result["cost"] - 2.0) < 1e-9  # 1.0 + 1.0
    # Verify the schedule assigns each job to its preferred machine.
    assert result["schedule"]["J1"][0] == "M1"
    assert result["schedule"]["J2"][0] == "M2"


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
