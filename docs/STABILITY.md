# API Stability — structural-computing v1.0.0

**Status:** v1.0.0 stability contract (filed during the v0.14 →
v1.0.0 milestone arc, 2026-05-31).

This document declares which parts of the public API are stable
under semantic versioning starting at v1.0.0.

## Stability tiers

The package has three tiers:

| Tier | Meaning | Breaks in |
|---|---|---|
| **Stable** | Public, semver-protected. Backwards-incompatible changes require a major-version bump (v2.0.0). | major releases only |
| **Experimental** | Public but signatures may shift between minor versions. Document carefully if depending on these. | minor releases |
| **Internal** | Underscore-prefixed or otherwise non-imported. No stability promise. | any release |

## Stable API (semver-protected at v1.0.0)

### `StructuralComputer` — the friendly entry point

Every method listed here has its signature frozen at v1.0.0:

**Construction**
- `StructuralComputer()` — no arguments.

**Structural inspection**
- `sc.classify(graph) -> Classification`
- `sc.explain(graph) -> str`

**Counting + reliability (v0.1 era)**
- `sc.count_matchings(graph) -> int`
- `sc.witness(graph) -> List[Tuple[Any, Any]]`
- `sc.tail_probability(graph, p_fail: float) -> float`
- `sc.single_points_of_failure(graph) -> List[Tuple[Any, Any]]`
- `sc.compare(graph_a, graph_b, p_fail: float, metric: str = "tail_probability") -> CompareReport`
- `sc.audit(graph, *, p_fail: float = 0.01) -> Dict[str, Any]`

**Constraint solving**
- `sc.classify_constraints(A=None, b=None, Q=None, c=None, modulus: int = 2) -> Classification`
- `sc.count_solutions(A=None, b=None, Q=None, c=None, modulus: int = 2) -> int`
- `sc.find_witness_solution(A=None, b=None, Q=None, c=None, modulus: int = 2) -> Optional[int]`
- `sc.list_solutions(A=None, b=None, Q=None, c=None, modulus: int = 2) -> List[int]`

**Signature inspection**
- `sc.classify_function(values: Sequence) -> Classification`
- `sc.matchgate_rank(values: Sequence) -> int`
- `sc.is_matchgate_realisable(values: Sequence) -> bool`

**Tropical / min-cost optimisation (v0.10–v0.11)**
- `sc.min_weight_matching(graph, weights: Optional[Dict] = None) -> Dict[str, Any]`
- `sc.min_cost_schedule(instance, cost_fn, *, allowed_machines=None, time_windows=None, forbidden_edges=None) -> Dict[str, Any]`
- `sc.min_cost_flow(instance) -> Dict[str, Any]`
- `sc.min_cost_roster(instance, preference_fn) -> Dict[str, Any]`
- `sc.min_cost_dedup(instance, similarity_fn) -> Dict[str, Any]`
- `sc.tropical_instance_coordinates(instance, cost_fn, *, compute_field_distance: bool = False) -> TropicalInstanceCoordinates`

**CP-SAT pre-flight (v0.13)**
- `sc.diagnose_constraints(constraints) -> EncodingDiagnostic`
- `sc.rewrite_constraints(constraints) -> RewriteSetBlueprint`
- `sc.rewrite_cpsat_model(model, *, rewrite_kinds=None) -> CPSATRewriteResult`
- `sc.verify_cpsat_rewrite(original_model, rewrite_result, *, enumeration_limit: int = 10000, check_objective: bool = True, max_witnesses: int = 5) -> CPSATVerificationResult`

**Hybrid decomposition (matching count on non-planar)**
- `sc.count_matchings_hybrid(graph, extra_edges: Sequence) -> int`

### Classification + routing

Stable dataclasses + helpers:
- `Classification` (dataclass with `tier`, `meters`, `in_family`, `reasoning`)
- `classify(problem)`
- `classify_graph(rotation)`
- `classify_constraint_set(A=None, b=None, Q=None, c=None, modulus=2)`
- `classify_signature(values)`
- `route(classification) -> Route` (returns a `Route` with `.member` and `.cost`)

### Orchestrator

Stable API:
- `Orchestrator()` constructor (no required arguments)
- `Orchestrator.evaluate(problem, question, *, hints=None, verbose=False, log=None) -> OrchestratorResult`
- `OrchestratorResult` dataclass (with `answer`, `classification`, `reductions_applied`, `sub_evaluations`, `leaf_evaluator_used`, `workflow_trace`)
- `WorkflowStep` dataclass
- `NoKnownReduction` exception
- `DEFAULT_LEAF_REGISTRY` dict — the (tier, question) → callable map. Adding new entries is supported via the `leaf_registry` constructor argument or by mutating in-place; replacing existing entries is a stable extension point.

### Exceptions

- `NotInFamily` (from `easy.py`) — raised when an exact computation is requested on an out-of-family problem.
- `NoKnownReduction` (from `orchestrator.py`) — raised when the orchestrator can't reach an in-family answer.
- `ReductionNotApplicable` (from `transform.py`) — raised by reduction classes when their input pre-conditions aren't met.

### Calibration helpers

Stable:
- `apply_calibration(calibration_data)` — load wall-clock cost models produced by `structural-computing-bench`.
- `clear_calibration()`
- `get_calibration(tier, question)`
- `has_calibration_for(tier, question)`
- `predict_seconds(tier, question, *, n)`

### Reduction / composition / decomposition base interfaces

Stable since **v1.1.0** (promoted from Experimental):

- **Base interfaces**: `Reduction`, `ReductionResult`,
  `ReductionPlan`, `ReductionNotApplicable`, `Composition`,
  `CompositionPlan`, `Decomposition`, `DecompositionPlan`.

These are the abstract / dataclass interfaces that downstream code
implements against to register custom reductions / compositions /
decompositions with the orchestrator. Their public method signatures
and dataclass fields are now semver-protected.

### Pipeline-router framework

Stable since **v1.1.0** (promoted from Experimental):

- `Stage`, `Route`, `StageRecord`, `Trace`, `run_pipeline`,
  `run_pipeline_streaming`.

Workflow-level routing primitives. Used heavily by
`free-fermion-quantum-simulation`'s `pipeline-router/` examples.

### Verifier helpers

Stable since **v1.1.0** (promoted from Experimental):

- `brute_force_count_matchings`, `brute_force_weighted_matching_sum`,
  `satisfies_gf2_affine`, `enumerate_satisfying_assignments`,
  `gibbs_expectation_brute`, `verify_pipeline`.

Small-n verification utilities. Used by both the wrapper and the
test suite; signatures have been stable for the entire v0.x cycle.

### Trace + replay

Stable since **v1.1.0** (promoted from Experimental):

- `RichTrace`, `RegimeChange` (the aggregated trace + regime-change
  detection).
- `ReplayCache`, `cached_runner`, `default_key` (memoisation).

## Experimental API (may shift between minor releases)

These are public (importable from `structural_computing`) but
their internal layout / signatures may change before they harden:

- **Reduction implementations** (the concrete classes, not the
  base interfaces): `NormaliseGraphFormat`, `CrossingElimination`,
  `HighDegreeVertexSplit`, `HybridDecomposition`,
  `RationaliseWeights`, `auto_detect_extras`.
- **Composition implementations**: `LinearCombination`, `Projection`,
  `HolographicBasisPair`, `HolographicBasisResult`, `BranchSum`.
- **Decomposition implementations**: `ShannonExpansion`,
  `TreewidthBoundedDP`, `PlanarSeparator`, `RecursiveCircuitCut`.

Note the asymmetry: the abstract base interfaces (`Reduction`,
`Composition`, `Decomposition`, etc.) are Stable as of v1.1.0;
the specific implementation classes are still Experimental, since
their internal layout (which sub-problems they emit, what
combine-rules they use, etc.) may evolve. Downstream code that
implements ITS OWN reduction/composition/decomposition by
subclassing the base interface gets a Stable contract; code that
depends on the EXACT internals of `HybridDecomposition` (etc.) does
not.

Code that uses Experimental-tier symbols should pin a minor-version
range like `structural-computing>=1.1,<1.2` if depending on exact
internal behaviour.

## Internal (no stability promise)

Anything starting with `_` (private functions, helpers). Anything
in `structural_computing.*` modules not re-exported at the
package root. Test code (`tests/`). Documentation source (`docs/`).

The leaf-evaluator functions in `orchestrator.py` (e.g.,
`_matching_count_leaf`, `_min_weight_matching_leaf`,
`_diagnose_constraints_leaf`) are internal; depend on them through
the `DEFAULT_LEAF_REGISTRY` dict and the `Orchestrator.evaluate()`
entry point, not by importing them directly.

## What's NOT in v1.0.0

Carried forward to future releases (no stability promise):

- Domain DSLs (workflow-systems, catastrophe-modelling, build-system
  audit) — sketched in the research roadmap; not yet code.
- Calibration data files for the new tropical + CP-SAT leaves —
  per-machine; the framework runs without them but the router's
  cost-comparison uses heuristic `log2(ops)` until calibration runs.

## Version policy after v1.0.0

- **Major** (v2.0.0, ...): backwards-incompatible changes to any
  Stable-tier symbol. Migration guide required.
- **Minor** (v1.1.0, v1.2.0, ...): backwards-compatible additions
  to Stable-tier; may include breaking changes to Experimental.
- **Patch** (v1.0.1, ...): bug fixes only.

Pre-1.0 alpha releases (v0.4.0a1 ... v0.13.0a1) did NOT honour
this policy — the v0.x line was a moving target. v1.0.0 is the
first release where downstream packages can safely pin
`structural-computing>=1.0,<2.0`.
