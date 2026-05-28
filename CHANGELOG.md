# Changelog

All notable changes to `structural-computing` will be documented here.

This project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
once it reaches v1.0.0; until then, the v0.x API may shift between minor
versions.

## [0.1.0a1] — 2026-05-28 (initial alpha)

**The first packaged form of the declarative structural computation
framework.** Extracted from the worked-examples repository
[`free-fermion-quantum-simulation`](https://github.com/pcoz/free-fermion-quantum-simulation)'s
`pipeline-router/` folder, with the loose-file structure converted into
a proper installable Python package.

### Added

- `StructuralComputer` — the friendly wrapper class. Methods:
  - `count_matchings(graph)` — exact perfect-matching count
  - `witness(graph)` — one specific matching
  - `tail_probability(graph, p_fail)` — exact P(no matching survives)
  - `single_points_of_failure(graph)` — critical edges
  - `compare(a, b, p_fail)` — regulator-defensible comparison verdict
  - `audit(graph, p_fail)` — everything in one call
  - `classify(graph)` — Classification object for advanced users
  - `explain(graph)` — human-readable plan
- `CompareReport.explain()` — regulator-style verdict string
- `NotInFamily` exception with attached `Classification`
- Framework primitives exposed at the top level:
  - `Stage`, `Route`, `StageRecord`, `Trace`, `run_pipeline`,
    `run_pipeline_streaming`
  - `Classification`, `classify`, `classify_constraint_set`,
    `classify_graph`, `classify_signature`
  - `route` (tier → member + cost)
  - `RichTrace`, `RegimeChange`
  - `ReplayCache`, `cached_runner`, `default_key`
  - `brute_force_count_matchings`, `satisfies_gf2_affine`,
    `enumerate_satisfying_assignments`, `gibbs_expectation_brute`,
    `verify_pipeline`

### Originality artefacts retained from the source repo

The two publicly-original mathematical results that the framework
exercises:

- **The dart-chain passage-arc formula** (in `holant-tools` v0.4.0a5
  as a dependency) — the corrected intersection-number primitive
  that fixes Cimasoni 2012's blindspot at degree-3 vertices. Used
  automatically by `classify_graph` when computing genus-related
  meters.
- **Basis-aware matchgate rank ≤ 2 for symmetric signatures** (in
  `holant-tools` v0.4.0 as a dependency) — every symmetric signature
  has basis-aware matchgate rank in `{0, 1, 2}` via parity-split
  common-basis construction. Used by `classify_signature`.

### Honest scope

What this release **is**:
- A proof-of-concept package extracting the working framework into a
  pip-installable form.
- API surface for graphs and matching-style questions (the
  `StructuralComputer` wrapper handles these in one-liners).
- Brute-force verification harness intact from the source repo.

What this release **is not**:
- A fully API-stable v1.0. The wrapper's API may shift before v1.0.
- A complete test suite. The self-tests from each module are
  retained; a pytest-based test suite is the next iteration.
- Calibrated cost models. The current cost surrogate is
  `2 log2 n`; benchmark-calibrated constants are coming in v0.2.
- Constraint-set and signature support in the wrapper at the same
  fluency as graph support. Currently those require the framework
  primitives directly; the wrapper layer is coming.
- ReplayCache eviction. Unbounded today; an LRU / size-bounded
  eviction policy is coming in v0.2.

### Dependencies

- `holant-tools>=0.5.0`
- `numpy>=1.24`
- `sympy>=1.12`
- Python `>=3.10`

### Provenance

- Extracted from
  [`free-fermion-quantum-simulation/pipeline-router/`](https://github.com/pcoz/free-fermion-quantum-simulation/tree/main/pipeline-router).
- The mathematical engine
  [`holant-tools`](https://github.com/pcoz/holant-tools) is a hard
  dependency.
- Conceptual lineage in the (private) research repo
  [`admissibility-geometry`](https://github.com/pcoz/admissibility-geometry)
  via
  [`ORIENTATION.md`](https://github.com/pcoz/admissibility-geometry/blob/main/ORIENTATION.md).

## [Unreleased] — v0.1.0a4 follow-up

Continuing through the four-reductions + orchestrator priority list:

- **`HybridDecomposition` fully implemented** in `transform.py` (was
  `NotImplementedError`). Implements the standard Tutte / Lovasz-Plummer
  decomposition `M(G) = M(G - e) + M(G / uv)` for perfect-matching
  counts. For a non-planar graph that becomes planar after removing a
  small set of extra edges, gives exact matching count in
  `2^|extras| * O(|V|^3)`.
  - New method `sc.count_matchings_hybrid(graph, extra_edges)` on
    `StructuralComputer` wires it to the leaf evaluator.
  - `tests/test_transform.py` (16 tests): verifies on K_{3,3}
    (non-planar, 6 matchings) via 1 / 2 / 3 extra edges; K_4
    with no extras; direct apply() inspection; invalid forced-in
    subsets skipped; bad inputs raise correctly.

- **`TreewidthBoundedDP` partial implementation** in `decompose.py`.
  The trivial single-bag case is fully implemented (== brute force on
  the whole graph). The multi-bag case raises a clear
  `NotImplementedError` with a pointer to the v0.2 deliverable
  (standard Bodlaender / Korhonen matching-count DP). The API
  accepts a tree-decomposition spec (`{"bags": [...], "tree_edges":
  [...], "root_bag_index": ...}`) so callers can wire in their own
  tree-decomposition algorithms.

- **`Orchestrator` shipped** as a new module `orchestrator.py`. The
  top-level "give me an exact answer" engine. Wires together:
  classifier + router + per-(tier, question) leaf evaluator
  registry + the reductions/compositions/decompositions layer.

  API:
    `orch = Orchestrator()`
    `result = orch.evaluate(problem, question="matching_count", hints=...)`
    `result.answer, result.classification, result.reductions_applied`,
    `result.sub_evaluations, result.leaf_evaluator_used`

  Default registry covers `(T2, matching_count)` and `(T4,
  matching_count)` via brute-force. Pluggable: users can `register_leaf_evaluator(tier, question, callable)`
  or `register_reduction(reduction)`. Out-of-family + no known
  reduction -> `NoKnownReduction` honest stop.

  Hint-driven path: `evaluate(..., hints={"extra_edges": [...]})`
  applies `HybridDecomposition` automatically for matching-count
  questions on graphs that classify out-of-family.

  v0.1 search is linear (try each registered reduction once). v0.2
  will add backtracking + cost-driven search over auto-applicable
  reductions.

- **Public API now 52 symbols** (added Orchestrator, OrchestratorResult,
  NoKnownReduction, LeafEvaluator, DEFAULT_LEAF_REGISTRY).

- **`tests/test_orchestrator.py` (9 tests)** covering direct dispatch
  on T2/T4, HybridDecomposition via hints, honest stops on unsupported
  questions, custom-leaf registration, format-normalisation.

- **`CrossingElimination` and `HolographicBasisPair`** remain
  `NotImplementedError` with v0.2 docstrings. These need the specific
  matching-preserving gadget construction (Cai-Lu-Xia 2009) and the
  Valiant 2004 basis-change machinery respectively; v0.2 deliverables.

## [0.1.0a3] — 2026-05-28 (same session)

Shipped after v0.1.0a2 in the same session:

- **Per-primitive pytest files** added under `tests/`:
  - `test_pipeline_router.py` (15 tests covering Stage/Route/Trace/run_pipeline/run_pipeline_streaming)
  - `test_classify.py` (15 tests covering classify_constraint_set, classify_graph, classify_signature, top-level dispatcher)
  - `test_route.py` (13 tests covering tier → member routing and the 4^g cost scaling)
  - `test_trace.py` (11 tests covering RichTrace aggregation and windowing)
  - `test_verifier.py` (15 tests covering brute_force_count_matchings, GF(2) enumeration, gibbs_expectation_brute, verify_pipeline)
- Combined test surface: ~145+ tests across 9 files; all primitives now have
  pytest-level coverage of their public surface.

- **Calibrated cost models in `route.py`.** Replaced the flat `2 log2 n`
  surrogate with **tier-specific asymptotic complexity estimates**:
  - T0/T1 (CH-form, Gauss-elim): `3 * log2(n) + 0.5` / `+ 1.0`
  - T2 (FKT Pfaffian): `3 * log2(2|V|) + 1.5`
  - T3 (basis-aware rank-2 parity-split): T2 cost + `log2(rank)`
  - T4 (genus-g Kasteleyn): T2 cost + `g * log2(4)` (preserves 4^g scaling)
  - Tropical Pfaffian (T6 planar): same shape as T2
  Each cost model is now explicit in `Route.meters["cost_model"]` so
  downstream tooling can inspect why a given cost was reported. Note: the
  constants are asymptotic-complexity estimates, not benchmark-calibrated.
  Real benchmark-driven calibration with per-platform constants is a v0.2
  deliverable; until then, the relative cost ordering between tiers is
  what the router needs for member selection, which this model provides.

- **Reductions / compositions / recursive-decomposition layer foundation.**
  Three new modules with the API surface in place and one concrete
  operation per module, plus sketches of upcoming operations as
  `NotImplementedError` with clear v0.2 docstrings:
  - `transform.py` — the `Reduction` protocol, `ReductionPlan` for
    sequencing, `ReductionResult` dataclass; `NormaliseGraphFormat`
    concrete reduction; sketches of `CrossingElimination`,
    `HighDegreeVertexSplit`, `HybridDecomposition`, `RationaliseWeights`.
  - `compose.py` — the `Composition` protocol, `CompositionPlan`
    dataclass; `LinearCombination` concrete composition; sketches of
    `Projection`, `HolographicBasisPair`, `BranchSum`.
  - `decompose.py` — the `Decomposition` protocol, `DecompositionPlan`
    dataclass; `ShannonExpansion` concrete decomposition; sketches of
    `TreewidthBoundedDP`, `PlanarSeparator`, `RecursiveCircuitCut`.

  This is the foundation for the v0.2+ work of widening the in-family
  boundary. The full set of planned operations is documented in the
  research-repo proposal `proposals/reductions_compositions_recursive_decomposition.md`.

- **`__all__` and public-API expanded** with the 23 new symbols from the
  reductions / compositions / decomposition layer. Top-level `import
  structural_computing` now exposes 47 public names.

## [0.1.0a2] — 2026-05-28 (later same day)

Shipped after v0.1.0a1 in the same session:

- `.github/workflows/test.yml` — CI matrix
  (Linux/macOS/Windows × Python 3.10–3.13).
- `.github/workflows/publish.yml` — Trusted Publisher to PyPI on release
  (with manual TestPyPI option).
- `tests/test_replay.py` — ~20 tests for `ReplayCache` including the
  new LRU eviction.
- `tests/originality/test_dart_chain.py` — asserts the dart-chain
  corrected primitive's 4×4-torus disagree-case is still resolved
  correctly, plus empirical stress on 30 random K_5 and K_{3,3}
  rotations.
- `tests/originality/test_basis_aware_rank.py` — asserts every classical
  symmetric signature (OR, AND, XOR, MAJORITY, EXACTLY-K, ALL-OR-NOTHING,
  ...) has basis-aware matchgate rank in {0, 1, 2}; parametrised over
  17 signatures plus scaling tests.
- `tests/test_constraints.py` — ~17 tests for the new
  constraint-set and signature methods on `StructuralComputer`.
- `ReplayCache(maxsize=N)` — LRU eviction policy. Backward-compatible:
  default `maxsize=None` is unbounded (the existing v0.1.0a1 behaviour).
  Tracks an `evictions` statistic alongside hits / misses.
- **`StructuralComputer` constraint-set API:**
  - `sc.classify_constraints(A, b, Q=None, c=None, modulus=2)` — emit the
    `Classification` for a constraint set.
  - `sc.count_solutions(A, b, Q=None, c=None, modulus=2)` — exact count.
    Pure GF(2)-affine (T0) is poly-time via Gaussian elimination at any
    n; T1 (with quadratic part) brute-forces at n ≤ 24.
  - `sc.find_witness_solution(A, b, Q=None, c=None, modulus=2)` — one
    specific solution. T0 via Gaussian elimination (poly-time);
    T1 brute force at small n. Returns None if infeasible.
  - `sc.list_solutions(A, b, Q=None, c=None, modulus=2)` — all
    solutions; brute force at n ≤ 20.
- **`StructuralComputer` signature API:**
  - `sc.classify_function(values)` — emit Classification for a symmetric
    signature.
  - `sc.matchgate_rank(values)` — basis-aware rank in {0, 1, 2}.
  - `sc.is_matchgate_realisable(values)` — boolean shortcut.
- **Scope-language reframe** in `README.md` — defensive "most problems
  don't have this shape" replaced with the active "natively-in-family +
  reductions + compositions + recursive decomposition + honest stops
  only when no such structure exists" framing. The
  reduction/composition/recursive-decomposition layer is filed as the
  largest active development direction.
- **Helper-function comment sweep** — `_gf2_rank`, `_gf2_solve_one`,
  `_bits_to_int`, `_as_array` got fully-explained docstrings covering
  algorithm, invariants, edge cases, and the framework's bit-ordering
  conventions.

Coming in v0.2.0:
- Reduction layer (`transform.py`) with crossing-elimination gadgets
  for near-planar graphs as the first reduction.
- Composition layer (`compose.py`) with holographic basis pairs and
  linear-combination composition.
- Recursive-decomposition layer (`decompose.py`) with
  treewidth-bounded DP as the first decomposition.
- Calibrated cost models in `route.py` (replace the `2 log2 n` surrogate
  with benchmark-measured constants per tier).
- Matching-polynomial form for `tail_probability` on larger graphs.

Coming in v1.0.0:
- API stability contract.
- Production-ready for downstream packages (workflow-system DSLs,
  catastrophe-modelling DSLs, etc.).
