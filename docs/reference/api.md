# API reference — `StructuralComputer`

This page lists every public method on `StructuralComputer` with
its signature, return type, and a one-line description. For the
formal stability contract see
[STABILITY.md](../STABILITY.md).

For runnable examples see:
- [Tutorial](../tutorial/getting-started.md)
- [How-to: min-cost scheduling](../how-to/min-cost-scheduling.md)
- [How-to: CP-SAT pre-flight](../how-to/cpsat-preflight.md)

## Construction

### `StructuralComputer()`

No arguments. Returns an instance with an internal `Orchestrator`
that all method calls dispatch through.

## Counting + reliability (v0.1–v0.3 era)

### `count_matchings(graph) -> int`

Exact perfect-matching count. Smart-path: Kasteleyn-Pfaffian
(O(n³)) for planar inputs with a rotation system; brute force
otherwise.

### `witness(graph) -> List[Tuple[Any, Any]]`

One specific perfect matching, if any exists. Empty list if none.

### `tail_probability(graph, p_fail: float) -> float`

Exact P(no perfect matching survives) under independent edge
failure. Brute-force enumeration of edge subsets at small |E|
(cap |E| ≤ 24).

### `single_points_of_failure(graph) -> List[Tuple[Any, Any]]`

Edges whose removal eliminates all perfect matchings.

### `compare(graph_a, graph_b, p_fail: float, metric: str = "tail_probability") -> CompareReport`

Compare two configurations on the chosen reliability metric.
Returns a `CompareReport` with absolute / relative difference
plus a verdict on which is more reliable.

### `audit(graph, *, p_fail: float = 0.01) -> Dict[str, Any]`

Single-call audit returning classification, matching count,
witness, single-points-of-failure, tail probability.

## Constraint solving

### `classify_constraints(A=None, b=None, Q=None, c=None, modulus: int = 2) -> Classification`

Classify a constraint set: linear `A x = b (mod modulus)` plus
optional quadratic constraints `x^T Q_i x = c_i (mod 2)`.

### `count_solutions(A=None, b=None, Q=None, c=None, modulus: int = 2) -> int`

Exact count of x satisfying the constraint set. T0 (linear only):
2^(n - rank(A)). T1 (with quadratic): brute force at small n.

### `find_witness_solution(A=None, b=None, Q=None, c=None, modulus: int = 2) -> Optional[int]`

One satisfying assignment as MSB-first integer. T0: Gauss-Jordan
in polynomial time. T1: brute force at small n. Returns `None`
if no solution exists.

### `list_solutions(A=None, b=None, Q=None, c=None, modulus: int = 2) -> List[int]`

All satisfying assignments. Brute-force enumeration capped at
n ≤ 20.

## Signature inspection

### `classify_function(values: Sequence) -> Classification`

Classify a symmetric signature given as a sequence indexed by
Hamming weight 0..arity.

### `matchgate_rank(values: Sequence) -> int`

Basis-aware matchgate rank. Always in {0, 1, 2} for symmetric
signatures.

### `is_matchgate_realisable(values: Sequence) -> bool`

`True` iff the signature is matchgate-realisable in some basis.

## Tropical / min-cost optimisation (v0.10–v0.11)

### `min_weight_matching(graph, weights: Optional[Dict] = None) -> Dict[str, Any]`

Minimum-weight perfect matching. Polynomial-time exact via
Hungarian (bipartite) or Edmonds (general). Returns
`{"cost", "matching", "feasible"}`.

### `min_cost_schedule(instance, cost_fn, *, allowed_machines=None, time_windows=None, forbidden_edges=None) -> Dict[str, Any]`

Min-cost schedule on a `holant_tools.SchedulingInstance`. The
`cost_fn` is `(job, machine, slot) -> float`. Returns
`{"cost", "schedule", "feasible"}`.

### `min_cost_flow(instance) -> Dict[str, Any]`

Min-cost flow on a `holant_tools.MinCostFlowInstance`. Returns
`{"cost", "flow", "feasible"}`.

### `min_cost_roster(instance, preference_fn) -> Dict[str, Any]`

Min-cost rostering on a `holant_tools.RosteringInstance`. The
`preference_fn` is `(employee, shift) -> float`. Returns
`{"cost", "roster", "feasible"}`.

### `min_cost_dedup(instance, similarity_fn) -> Dict[str, Any]`

Min-cost record-to-entity assignment for entity deduplication.
The `similarity_fn` is `(record, candidate) -> float`
(LOWER = more similar). Returns
`{"cost", "assignment", "entity_groups", "feasible"}`.

### `tropical_instance_coordinates(instance, cost_fn, *, compute_field_distance: bool = False) -> TropicalInstanceCoordinates`

One-call diagnostic: "is this `SchedulingInstance` structurally
well-suited for tropical optimisation?" Returns the
`TropicalInstanceCoordinates` dataclass with the four-coordinate
viewing-frame apparatus plus tropical-rank diagnostics.

## CP-SAT pre-flight (v0.13)

### `diagnose_constraints(constraints) -> EncodingDiagnostic`

Encoding-selection diagnostic on a list of
`holant_tools.ConstraintSpec`.

### `rewrite_constraints(constraints) -> RewriteSetBlueprint`

Produce a `RewriteSetBlueprint` describing how rewritable
constraints would be transformed into rank-1 time-slot
equivalents.

### `rewrite_cpsat_model(model, *, rewrite_kinds=None) -> CPSATRewriteResult`

Rewrite rank-explosive CP-SAT constraints in a `cp_model.CpModel`.
Returns a `CPSATRewriteResult` with `helped: bool` and
`help_reason_text`.

### `verify_cpsat_rewrite(original_model, rewrite_result, *, enumeration_limit: int = 10000, check_objective: bool = True, max_witnesses: int = 5) -> CPSATVerificationResult`

Verify that a CP-SAT rewrite preserves the feasible set + optional
objective on the original variables.

## Hybrid decomposition

### `count_matchings_hybrid(graph, extra_edges: Sequence) -> int`

Exact perfect-matching count on a non-planar graph, computed by
branching on a small set of "extra" edges that makes the residual
planar. Cost is `2^|extra_edges| * O(|V|^3)`.

## Inspection + explanation

### `classify(graph) -> Classification`

Return the structural classification of a graph (tier, in-family
flag, structural meters, reasoning).

### `explain(graph) -> str`

Human-readable: what will the framework do with this graph?

## Stability

Every method on this page is in the **Stable tier** at v1.0.0.
Signatures are semver-protected; breaking changes require a
major-version bump. See [STABILITY.md](../STABILITY.md) for the
full contract.
