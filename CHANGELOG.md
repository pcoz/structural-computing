# Changelog

All notable changes to `structural-computing` will be documented here.

This project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
once it reaches v1.0.0; until then, the v0.x API may shift between minor
versions.

## [0.12.0a1] — 2026-05-31 (v0.12 arc: wrapper consolidation)

**Architectural cleanup.** `StructuralComputer` now holds an
internal `Orchestrator` instance and delegates most evaluation
methods through it. Previously the wrapper and the orchestrator
duplicated evaluation logic for the same questions (matching
count, witness, single points of failure, the tropical family,
constraint solutions). v0.12 establishes a single source of
truth.

### Added

- **`StructuralComputer._orchestrator`** — internal `Orchestrator`
  instance shared by every method that resolves a single (tier,
  question) pair.
- **`StructuralComputer._delegate(problem, question) -> Any`** —
  private helper that runs the orchestrator on a problem dict
  and returns the bare answer. Also keeps
  `_last_classification` in sync with the orchestrator's
  dispatch tier.

### Changed (refactored to delegate)

- `count_matchings` — now goes through
  `(T2/T4, matching_count)`. The leaf evaluator was upgraded to
  use Kasteleyn-Pfaffian (FKT, O(n³)) when a rotation system is
  present and the graph is planar; brute force otherwise.
  Behaviour-preserving on existing call sites.
- `tail_probability` — delegates to `(T2/T4, tail_probability)`.
  The `p_fail` argument now travels inside the problem dict.
- `witness` — delegates to `(T2/T4, witness)`.
- `single_points_of_failure` — delegates to
  `(T2/T4, single_points_of_failure)`.
- `min_weight_matching` — delegates to
  `(T2/T4, min_weight_matching)`.
- `min_cost_schedule` — delegates to `(T2/T4, min_cost_schedule)`.
- `min_cost_flow` — delegates to `(T2/T4, min_cost_flow)`.
- `min_cost_roster` — delegates to `(T2/T4, min_cost_roster)`.
- `min_cost_dedup` — delegates to `(T2/T4, min_cost_dedup)`.
- `tropical_instance_coordinates` — delegates to
  `(T2/T4, tropical_instance_coordinates)`.
- `count_solutions` — delegates to `(T0/T1, count_solutions)`
  (with pre-coercion of A/b/Q/c to numpy arrays).
- `find_witness_solution` — delegates to
  `(T0/T1, find_witness)`.
- `list_solutions` — delegates to `(T0/T1, list_solutions)`.

### Orchestrator-side classifier extension

`Orchestrator._classify_problem` now handles two additional
problem-dict shapes that the wrapper produces:

- Tropical instance-based dicts (`{"instance": ...}`) — routed
  to T2 with `problem_kind = "tropical_instance"` so the
  registered tropical leaf evaluators fire.
- Graph dicts without a rotation system (`{"vertices": ...,
  "edges": ...}`) — routed to T2 with `problem_kind =
  "graph_no_rotation"` for direct leaf dispatch.

### Methods NOT refactored (intentionally)

- `classify`, `explain` — structural inspection, not single-leaf
  evaluation.
- `compare` — meta-method that calls `tail_probability` twice.
- `audit` — meta-method that calls multiple wrapper methods.
- `count_matchings_hybrid` — multi-step reduction
  (HybridDecomposition).
- `classify_constraints`, `classify_function`, `matchgate_rank`,
  `is_matchgate_realisable` — direct classification calls; the
  orchestrator round-trip would add no value.

### Test count

- All 23 smoke tests + 45 constraint tests pass after the
  refactor. No behaviour change visible to callers.

### Architectural benefit

Going forward, any new question registered in
`DEFAULT_LEAF_REGISTRY` is automatically reachable through the
wrapper by writing a thin `sc.foo(...)` that builds a problem
dict and calls `self._delegate(...)`. The orchestrator becomes
the single dispatch surface; the wrapper becomes the thin
ergonomic layer.

---

## [0.11.0a1] — 2026-05-31 (v0.11 arc: finish tropical wiring)

**Closes the tropical-wiring gap left open by v0.10.** v0.10 wired
the two highest-impact tropical questions (`min_weight_matching`
and `min_cost_schedule`); v0.11 finishes the job for the remaining
domain-specific tropical primitives.

### Added

- **`_min_cost_flow_leaf`** — leaf evaluator for
  `holant_tools.MinCostFlowInstance`. Delegates to
  `holant_tools.min_cost_flow`. Returns
  `{"cost", "flow", "feasible"}`.
- **`_min_cost_roster_leaf`** — leaf evaluator for
  `holant_tools.RosteringInstance` + a `preference_fn`. Delegates
  to `holant_tools.min_cost_roster`. Returns
  `{"cost", "roster", "feasible"}`.
- **`_min_cost_dedup_leaf`** — leaf evaluator for
  `holant_tools.MDMInstance` + a `similarity_fn`. Delegates to
  `holant_tools.min_cost_dedup`. Returns
  `{"cost", "assignment", "entity_groups", "feasible"}`.
- **`_tropical_instance_coordinates_leaf`** — the one-call
  diagnostic on `SchedulingInstance` + `cost_fn`. Returns the
  `TropicalInstanceCoordinates` dataclass directly (it's not a
  min-cost question; its fields ARE the diagnostic output).
- **Registry entries** in DEFAULT_LEAF_REGISTRY for all four
  under (T2, ...) and (T4, ...).
- **Wrapper methods** on `StructuralComputer`:
  - `sc.min_cost_flow(instance) -> dict`
  - `sc.min_cost_roster(instance, preference_fn) -> dict`
  - `sc.min_cost_dedup(instance, similarity_fn) -> dict`
  - `sc.tropical_instance_coordinates(instance, cost_fn, *, compute_field_distance=False) -> TropicalInstanceCoordinates`

### Test count

- 299 passing (295 v0.10 + 4 new v0.11 tests).

### What's still carried forward

The polymorphic lower-level Pfaffian / multilinear evaluators
(`pfaffian(M, semiring=...)`, `holant_sum_of_pfaffians`,
`holant_genus_g`, `holant_planar`) remain accessible via direct
import from `holant_tools`; they don't need orchestrator wiring
because they're matrix/tensor-level operations rather than
problem-level questions. Users who need them can `import
holant_tools; holant_tools.pfaffian(M, semiring=...)`.

After v0.11 the tropical-Holant capability is fully reachable
through the orchestrator + wrapper for every domain-specific
primitive in `holant_tools`'s tropical surface.

---

## [0.10.0a1] — 2026-05-31 (v0.10 arc: tropical optimisation in orchestrator)

**New user-facing capability: min-cost queries on the same admissible-
set machinery.** The orchestrator can now answer MIN-WEIGHT
perfect-matching and MIN-COST scheduling questions, dispatching
to holant-tools' polynomial-time tropical Pfaffian kernel.

The same Holant network that counts admissible configurations under
the standard (+, ×) semiring computes the **cheapest** admissible
configuration under the tropical (min, +) semiring. v0.10 wires
this second-semiring capability into the orchestrator + the
`StructuralComputer` one-liner wrapper.

### Added

- **`_min_weight_matching_leaf`** in `orchestrator.py` — leaf
  evaluator for min-weight perfect matching on graphs (T2 / T4).
  Delegates to `holant_tools.min_weight_perfect_matching`, which
  dispatches between Hungarian (bipartite K_{n,n}, O(n³)) and
  Edmonds blossom via NetworkX (general non-bipartite, O(n³)).
  Returns `{"cost": float, "matching": [(u, v), ...], "feasible": bool}`.
- **`_min_cost_schedule_leaf`** in `orchestrator.py` — leaf
  evaluator for `SchedulingInstance` inputs. Delegates to
  `holant_tools.min_cost_schedule`. Returns
  `{"cost": float, "schedule": dict, "feasible": bool}`.
- **Registry entries** in DEFAULT_LEAF_REGISTRY:
  - `(T2, "min_weight_matching")` and `(T4, "min_weight_matching")`
  - `(T2, "min_cost_schedule")` and `(T4, "min_cost_schedule")`
- **Wrapper methods** on `StructuralComputer` (in `easy.py`):
  - `sc.min_weight_matching(graph, weights=None) -> dict`
  - `sc.min_cost_schedule(instance, cost_fn, **kwargs) -> dict`

### Test count

- 295 passing (290 v0.9 baseline + 5 new v0.10 tests).

### Honest scope

The leaf evaluators implemented in v0.10 are `min_weight_matching`
and `min_cost_schedule`. Other tropical primitives already shipped
in `holant-tools` since v0.2.0a* but not yet wired into the
orchestrator: `min_cost_flow`, `min_cost_roster`, `min_cost_dedup`,
`tropical_instance_coordinates`. These will follow as v0.11+
deliverables; the engine is already production-ready, only the
orchestrator-side dispatch wiring is missing.

### Worked example

```python
from structural_computing import StructuralComputer
sc = StructuralComputer()

# 4-cycle 0-1-2-3-0 with weighted edges
graph = [(0, 1), (1, 2), (2, 3), (3, 0)]
weights = {(0, 1): 1.0, (1, 2): 10.0, (2, 3): 1.0, (3, 0): 10.0}

result = sc.min_weight_matching(graph, weights)
# {'cost': 2.0, 'matching': [(0, 1), (2, 3)], 'feasible': True}
```

---

## [0.9.0a2] — 2026-05-31 (documentation-only patch — PyPI public/private boundary)

**Documentation-only release.** Same code as v0.9.0a1; only the
README on PyPI changes.

### Changed

- README.md: removed a line referencing "the private research
  repo" that violated the public/private boundary rule. The
  public packages must not reference the private research
  parent (`admissibility-geometry`) on their PyPI pages.

No code changes. No API changes. No version-floor bumps.

---

## [0.9.0a1] — 2026-05-31 (v0.9 arc: full LT 1979 with explicit planar-dual)

**Closes the last math-completeness gap in the Lipton-Tarjan
cascade.** v0.8 D2 added the fundamental-cycle backup as the 4th
tier using the Jordan-curve property IMPLICITLY (residual
connected-components count). v0.9 D1 implements the ORIGINAL
Lipton-Tarjan 1979 algorithm's planar-dual argument EXPLICITLY
as the 5th tier of the cascade.

### Added

- `_lipton_tarjan_planar_dual_backup` in `decompose.py` — 5th
  tier of the LT cascade. Requires a rotation system (planar
  embedding) as input. Algorithm:
  - Trace faces from the rotation via holant-tools'
    `genus_from_rotation_system`. Verify genus 0.
  - Build edge-to-faces and vertex-to-faces maps.
  - Construct the primal BFS spanning tree T from BFS levels.
  - The cotree primal edges form (their duals form) a spanning
    tree T* of the planar dual G*.
  - For each cotree primal edge e (= dual edge e* in T*),
    removing e* from T* splits T* into two components → F_inside
    and F_outside face sets.
  - Classify each primal vertex via its incident faces: all-inside
    → A, all-outside → B, mixed → on cycle (S).
  - Score the resulting (S, A, B); pick the best.
- `_lipton_tarjan_separator` now reads `problem["rotation"]` when
  present and invokes the 5th tier after the 4th tier (v0.7 D2
  fundamental-cycle backup) fails. Without rotation, the cascade
  ends at the 4th tier (same as v0.8 behaviour).

### Why this catches what v0.8 D2 doesn't

v0.8 D2 uses Jordan-curve implicitly (residual connected
components after removing cycle vertices). On adversarial planar
graphs where the residual heuristic mis-bins ambiguous vertices,
v0.8 D2 may fail. v0.9 D1 uses the planar embedding directly to
GUARANTEE the inside/outside classification is the dual-correct
split.

### Behaviour change for upgraders

If `PlanarSeparator(auto=True)` previously failed on a planar
input where the v0.4-v0.7 cascade gave up, providing a rotation
system in the problem dict now extends the cascade to the
theoretically-grounded 5th tier. Existing call sites without
rotation are unaffected.

### Test count

- 290 passing (285 v0.8 + 5 new v0.9 D1 tests).

### Honest scope (final tier)

Per LT 1979, this fifth tier WILL find a valid separator on
every planar input — modulo bounded-effort enumeration over the
cotree edges. The five-tier cascade now closes the
math-completeness gap on the LT side. Adversarial cases where
all five tiers fail indicate a non-planar input (where the LT
bound doesn't apply) or a non-cellular rotation system.

---

## [0.8.0a1] — 2026-05-31 (v0.8 arc: math completeness, cont.)

**Math completeness arc continuing from v0.6.** Closes the two
remaining v0.6-era honest-scope gaps:

1. **Higher-m augmented Plücker enumeration** — via
   `holant-tools v0.7.0`, the augmented-Pfaffian Plücker
   identities now span every viable m configuration (m ∈ {1, 3,
   5, 7, ...}) at every even arity ≥ 6 odd-parity, not just
   m ∈ {1, 3} as in v0.6.x. This is the engine-side D1.
2. **Fundamental-cycle backup as the 4th tier of the Lipton-
   Tarjan cascade** — closest practical equivalent of the
   original LT 1979 planar-dual fundamental-cycle argument. Adds
   to the v0.4 simple BFS-layer + v0.5 tree-edge + v0.6 D2
   level-based + articulation-augmentation cascade.

### D1: higher-m augmented Plücker (delegated to holant-tools v0.7.0)

- `HolographicBasisPair._augmented_plucker_identities_arity_n_odd`
  continues as a one-line delegation. holant-tools v0.7.0
  shipped the math; structural-computing inherits the
  strengthened check automatically.
- The realisability_check field still reports
  "plucker_arity_n_full" — but the "full" is now actually full
  (modulo the standard non-augmented enumeration that was
  always complete on the underlying n-vertex matrix).
- holant-tools dep floor: `>=0.6.1` → `>=0.7.0`.

### D2: fundamental-cycle backup (4th tier)

- New private function `_lipton_tarjan_fundamental_cycle_backup`
  in `decompose.py`. Invoked after the v0.4 / v0.5 / v0.6 D2
  tiers all fail. Algorithm:
  - Reconstruct the BFS spanning tree T from the BFS levels.
  - Enumerate non-tree edges.
  - For each non-tree edge e = (u, v), the fundamental cycle
    C_e = path_T(u → v) ∪ {e} (always SIMPLE since T is a
    tree).
  - Remove C_e vertices; compute residual connected components
    (Jordan-curve theorem on planar inputs guarantees at most
    TWO main components — "inside" and "outside" the cycle).
  - Pick the non-tree edge whose cycle satisfies both
    |C_e| ≤ 2·sqrt(2n) AND max(component) ≤ 2n/3, scoring by
    a balance heuristic.
- Helper `_fundamental_cycle(tree_parent, u, v)` does the
  path-via-LCA construction.
- Honest scope: works WITHOUT requiring rotation system input
  (the Jordan-curve property is invoked implicitly). The full
  LT 1979 paper's planar-dual argument additionally PROVES
  that an acceptable non-tree edge always exists when the
  simple case fails; our search is bounded-effort and may
  honest-stop on adversarial graphs.

### Test count

- 285 passing (281 v0.7 baseline + 4 new v0.7 D2 tests).

### Notes

- The v0.7 arc (no-version-bump PyPI publication unblock) is
  what brought existing versions to PyPI on 2026-05-31. The
  v0.8 arc is the next functional release continuing the math
  completeness chain.

---

## 2026-05-31 — v0.7 arc (PyPI publication unblock; no version bump)

**Shipped 2026-05-31.** No version bump. This arc landed existing
versions on PyPI for the first time:

- `holant-tools 0.6.1` → PyPI (PyPI was previously at 0.5.0 from
  2026-05-27).
- `structural-computing 0.6.0a1` → PyPI (first-ever upload of this
  package).
- `structural-computing-bench 0.1.0a1` → PyPI (first-ever upload;
  dep floor bumped to `structural-computing>=0.6.0a1`).

### Added (this repo)

- `.github/workflows/publish.yml` already in place from v0.5
  dist-prep — used as-is for the v0.6.0a1 upload.
- `docs/v0.7-plan.md` documenting the arc.

### Verified

- Dist artefacts rebuilt at `dist/structural_computing-0.6.0a1*`;
  `twine check` PASSED.
- Wheel METADATA correctly carries `Requires-Dist:
  holant-tools>=0.6.1`.

### Upload ordering (verified)

- `holant-tools 0.6.1` uploaded first (required for the
  `structural-computing` dep floor to resolve).
- `structural-computing 0.6.0a1` uploaded second (initial attempt
  failed with 400 Bad Request because the
  `Mathematical engine (holant-tools)` Project-URL label was 34
  chars; PyPI core-metadata limits Project-URL keys to 32; fixed
  by shortening to `Math engine (holant-tools)`).
- `structural-computing-bench 0.1.0a1` uploaded third.
- End-to-end clean-venv smoke check: `pip install
  structural-computing-bench` pulls in
  structural-computing 0.6.0a1 + holant-tools 0.6.1 transparently.

---

## [0.6.0a1] — 2026-05-31 (v0.6 alpha — architectural cleanup: D1 promotion)

**v0.6 starts the cleanup-and-math-completeness arc.** Deliverable 1
(of three planned for v0.6) is now complete: the augmented-Pfaffian
Plücker helper prototype-in-place'd in v0.5 has been promoted to
`holant-tools.non_symmetric`, restoring the architectural principle
that math primitives live in the mathematical engine.

### D1: helper promoted to holant-tools (engine side)

- `holant-tools v0.6.0` (released 2026-05-31) ships
  `matchgate_identities_arity_n_odd_augmented(tau, n)` in
  `holant_tools.non_symmetric`, exported at the top level. Same
  type signature and convention as the existing v0.4 MGI siblings
  (sympy-friendly). Wired into
  `realizability_subvariety_non_symmetric` at even arity ≥ 6
  odd-parity.

### D1: structural-computing side (this repo)

- `HolographicBasisPair._augmented_plucker_identities_arity_n_odd`
  is now a one-line delegation to the engine function (`import
  holant_tools as _ht; ... _ht.matchgate_identities_arity_n_odd_augmented(tau, arity)`),
  with a float cast on the returned sympy expressions to preserve
  the orchestrator's tolerance-based check contract.
- The `TODO(v0.6)` marker filed in v0.5 has been removed; the
  helper's surrounding comment now documents the v0.6 promotion.
- `pyproject.toml`: `holant-tools` dep floor bumped from `>=0.5.0`
  to `>=0.6.0`.
- All 272 v0.5 tests still pass (delegation is semantically
  equivalent to the v0.5 prototype).

### Deliverable 2: level-based + articulation-augmentation backup (decompose.py)

**v0.6 D2 catches planar graphs that defeat BOTH v0.4 simple BFS-layer
AND v0.5 tree-edge augmentation.** Canonical adversarial corpus:
star graphs K_{1, n} (BFS spanning tree's children are all leaves; no
balanced tree edge exists) and complete-bipartite K_{2, n} (the optimal
separator is the 2-vertex spine; v0.5's tree-edge backup picks one
spine vertex and tries to augment, but augmentation grows past the
bound).

New private functions in `decompose.py`:

- `_lipton_tarjan_level_backup(vertices, adj, levels, n, bound_AB, bound_S)`
  — invoked from `_lipton_tarjan_separator` when both the simple
  case and the v0.5 tree-edge backup raise. Iterates BFS levels
  smallest-first; for each, runs `_try_level_separator`.
- `_try_level_separator(t, ...)` — starts with S = L_t; computes
  connected components of the residual graph (V \ S); bin-packs
  components into A (capacity 2n/3) and B (same), largest-first
  greedy. If a component exceeds bound_AB, identifies its highest-
  residual-degree vertex (heuristic for articulation) and adds to S,
  then retries. Raises if |S| exceeds 2*sqrt(2n).
- `_connected_components_in_residual(rest, adj, S)` — sub-graph
  connected components on V \ S via iterative DFS.

`_lipton_tarjan_separator` now has a three-step backup chain:
simple BFS-layer → v0.5 tree-edge → v0.6 level-based. ValueError is
raised only when ALL three approaches fail.

### Tests
- 6 new tests in `test_decompose.py`:
  * `test_v06_d2_level_backup_catches_star`: K_{1, 20} (n=21) →
    optimal |S|=1 separator {root} found.
  * `test_v06_d2_level_backup_catches_K_2_n`: K_{2, 20} (n=22) →
    optimal |S|=2 separator {spine_0, spine_1} found.
  * `test_v06_d2_level_backup_handles_various_star_sizes`:
    K_{1, n} for n ∈ {10, 20, 30, 50}.
  * `test_v06_d2_level_backup_handles_various_K_2_n_sizes`:
    K_{2, n} for n ∈ {10, 20, 30, 50}.
  * `test_v06_d2_planar_separator_auto_works_on_star`: end-to-end
    PlanarSeparator(auto=True) matching-count agrees with brute force.
  * `test_v06_d2_disconnected_still_raises`: disconnected graphs
    honest-stop before reaching D2.
- 278 tests passing (272 baseline + 6 new D2; 272 + 6 = 278).

### Honest scope (v0.6 D2)
- This is a SIMPLIFIED form of LT 1979's "fat middle level" case
  using BFS-level + articulation heuristic, not the original 1979
  proof's planar-dual fundamental-cycle argument with rotation-
  system-aware face counting.
- The simplification works on the verified corpus (star and
  K_{2,n} graphs at all tested sizes) plus practical "high-degree
  connector" planar graphs. Cases where the residual has one giant
  component AND no clear high-degree articulation vertex still
  raise honest-stop with combined diagnostics.
- The full Lipton-Tarjan 1979 algorithm with planar dual remains
  a v0.7+ deliverable for adversarial cases.

### Deliverable 3: |S| = 4 (m = 3) augmented Plücker at arity ≥ 8

**v0.6 D3 closes the third v0.6 honest-scope gap** by extending the
augmented-Pfaffian Plücker enumeration to the m = 3 configuration
in `holant_tools v0.6.1`. The structural-computing delegation
wrapper picks up the new identities transparently.

### holant-tools v0.6.1 (sister-repo release)

- `matchgate_identities_arity_n_odd_augmented` now enumerates BOTH
  the m = 1 case (`S = {p, ω}`, v0.6.0) AND the m = 3 case
  (`S = {p, q, r, ω}`, v0.6.1). Configuration analysis: the
  parameter m := |S \ {ω}| must be ODD and satisfy `m + 5 ≤ n` for
  the Plücker identity to give pure-τ relations via the augmented
  convention. Viable m ∈ {1, 3, 5, ...} at arity n ≥ 6, 8, 10, ...
  respectively.
- New count at arity 8: 560 identities (280 m=1 + 280 m=3).
  At arity 10: 5460 identities (1260 + 4200).
- Verified symbolically on a generic 9x9 skew matrix; numerically
  on signatures from random 9x9 skew matrices (all 560 identities
  vanish to machine precision).
- 5 new tests in holant-tools' `tests/test_holant_tools.py`
  (`test_v061_*`); total 348 passing (343 v0.6.0 baseline +5).
- Released as `pcoz/holant-tools v0.6.1` (commit `16d48f6`).

### structural-computing side (this repo)

- `pyproject.toml`: holant-tools dep floor bumped from `>=0.6.0`
  to `>=0.6.1` so the v0.6.1 m=3 identities are guaranteed.
- The delegation wrapper at
  `HolographicBasisPair._augmented_plucker_identities_arity_n_odd`
  consumes the extended engine function transparently — no
  structural-computing code changes needed beyond the floor bump.
- 3 new tests in `test_compose.py`:
  * `test_v06_d3_arity_8_realisable_signature_via_v0_6_1_engine`:
    a random arity-8 odd-parity signature from a 9x9 skew matrix
    passes the now-560 augmented identities.
  * `test_v06_d3_arity_8_perturbed_signature_via_v0_6_1_engine`:
    perturbing a weight-3 entry is detected.
  * `test_v06_d3_delegation_count_grew_at_arity_8`: direct test
    that the delegation wrapper returns 560 identities at arity 8.
- 281 tests passing (278 D2 baseline + 3 new D3).

### Honest scope (v0.6 D3)

- Ships m ∈ {1, 3}. Higher-m configurations (m = 5 at arity ≥ 10,
  m = 7 at arity ≥ 12, ...) remain a follow-on per the same
  configuration analysis.
- Per Cai-Lu 2011 §4, the full augmented Plücker enumeration
  across all m + the standard Plücker enumeration together
  characterises the d-admissibility variety completely. v0.6 D3
  closes a substantial fraction of that program at the arities
  practical implementations care about.

### Cumulative state at v0.6.0a1 release

- 281 tests passing in structural-computing.
- 348 tests passing in holant-tools.
- Three v0.6 deliverables complete:
  - D1: augmented Plücker helper promoted from
    structural-computing v0.5 prototype to
    `holant-tools.non_symmetric` v0.6.0.
  - D2: Lipton-Tarjan level-based + articulation-augmentation
    backup catching star + K_{2,n} adversarial graphs that v0.5's
    tree-edge backup couldn't.
  - D3: augmented Plücker enumeration extended with m = 3
    configuration, doubling identity count at arity 8 (280 → 560)
    and adding 4200 new identities at arity 10.

### Deferred to v0.7+

- Higher-m augmented Plücker configurations (m = 5 at arity ≥ 10,
  m = 7 at arity ≥ 12, ...).
- Full Lipton-Tarjan 1979 backup with planar-dual fundamental-cycle
  counting (for adversarial cases the v0.6 simplification can't
  bound).
- Tropical optimisation (per NEXT.md §δ).
- Diagnostic layer for CP-SAT / Gurobi / SLURM (per §ε).
- Wrapper consolidation: `StructuralComputer` →
  `Orchestrator` delegation.
- PyPI publication.


## [0.5.0a1] — 2026-05-31 (v0.5 alpha — math completeness)

**v0.5 closes the three honest-scope gaps documented in v0.4:**
complex-roots SRP, full Cai-Lu §4 d-admissibility at even arity ≥ 6
odd-parity, and a spanning-tree fundamental-cycle backup for the
Lipton-Tarjan auto-separator. **272 tests pass** (up from 262 v0.4
baseline; +10 net new tests across the three deliverables).

**Deliverable 3 (closed-form SRP for complex-roots rank-2 signatures) — complete.**
The order-2 recurrence kernel's complex-roots case is now caught by
the closed-form path in `HolographicBasisPair._basis_from_recurrence_kernel`,
rather than falling through to the canonical-bases sweep.

### Complex-roots SRP closed-form (compose.py)
- When the recurrence kernel has discriminant `b^2 - 4ac < -tol`, the
  roots are a complex conjugate pair `r = alpha ± i*beta` with
  `alpha = -b/(2c)` and `beta = sqrt(-disc)/(2c)`. The new closed-form
  returns the real basis matrix
  `T = [[1, -alpha], [0, beta]]`, which transforms the signature's
  polynomial encoding `2*Re[A*((alpha*u + v) + i*beta*u)^n]` to
  `2*beta^n * Re[A*(v + i*u)^n]`. The transformed signature
  alternates zero at one parity branch with geometric ratio
  `i^2 = -1` between consecutive non-zero entries.
- Verified empirically on NAE-3 `[0, 1, 1, 0]`: `T = [[1, -0.5],
  [0, sqrt(3)/2]]` produces `[0, 0.75, 0, -0.75]` — alternate-zero
  odd-parity, geometric-progression with ratio -1, distance 0.

### Tests
- 2 new tests in `test_compose.py`:
  * `test_srp_complex_roots_via_v05_closed_form`: NAE-3 hits the
    closed-form path (not the canonical Hadamard fallback); the
    discovered T matches `[[1, -1/2], [0, sqrt(3)/2]]` exactly.
  * `test_srp_complex_roots_corpus`: 6 hand-picked (alpha, beta) pairs
    spanning `(0, 1.0)` (purely imaginary), `(0.5, 0.866)` (NAE-3),
    `(1, 1)` (45°), `(0.3, 2.0)`, `(-0.7, 1.5)`, `(2, 0.5)` -- all
    caught.
  * `test_srp_complex_roots_random_stress`: 50 random `(alpha, beta)`
    pairs in `[-10, 10] x (0.1, 10]`, arities 3-5 -- all caught.
- Renamed and updated 1 v0.4 contract test
  (`test_srp_closed_form_skipped_for_complex_roots` ->
  `test_srp_complex_roots_via_v05_closed_form`) to reflect the
  v0.5 behaviour change.
- Updated 1 v0.4 helper test
  (`test_basis_from_recurrence_kernel_degenerate_cases`): the
  complex-roots case `(1, -1, 1)` now returns a real T instead of None.
- 264/264 tests pass (v0.4 baseline was 262; net +2).

**Deliverable 1 (full Cai-Lu §4 d-admissibility at even arity ≥ 6 odd-parity) — complete.**
The augmented-Pfaffian Plücker enumeration on the (n+1)-vertex Kasteleyn
matrix is now applied at even arity ≥ 6 odd-parity, closing the v0.4
"tight necessary but not provably sufficient" gap. The
`realisability_check` field now reports `"plucker_arity_n_full"` at
arity 6 (and even arity 8, 10, ...) when these identities pass.

### Augmented Plücker enumeration (compose.py)
- New static helper
  `HolographicBasisPair._augmented_plucker_identities_arity_n_odd(tau, n)`
  returning the list of polynomial values for the v0.5 augmented
  identities. Configuration: ``S = {p, omega}`` for each ``p`` in
  ``{0..n-1}``, with 4-subset ``{a, b, c, d}`` ranging over
  ``C(n-1, 4)`` choices in ``{0..n-1} \ {p}``. Each identity maps
  to a Plücker quadratic in tau values via the augmented Pfaffian
  correspondence ``tau(b) = Pf(complement(b) ∪ {omega})``.
- Count: ``n × C(n-1, 4)`` identities. At arity 6: 30. Arity 8: 280.
  Arity 10: 1260. (Growth is O(n^5).)
- Derivation verified symbolically on a generic 7x7 skew matrix
  during development (Plücker identity vanishes identically on
  symbolic Pfaffians).
- Wired into `_check_general_realisability`: at even arity ≥ 6
  odd-parity, after the standard Plücker enumeration and augmented
  weight-1 identity pass, run the new helper. If all pass, the
  result's `realisability_check` is `"plucker_arity_n_full"` --
  signalling a proven-sufficient check rather than the v0.4
  tight-necessary one.

### Honest scope (v0.5 D1)
- The v0.5 helper ships the ``|S|=2`` Plücker configuration only.
  At arity ≥ 8, additional configurations with
  ``|S \ {omega}| ∈ {3, 5, ...}`` also give valid Plücker identities;
  these are deferred to v0.6.
- At ODD arity (5, 7, 9, ...) the augmented identities derived here
  are vacuous on the strict odd-parity branch (weight-(n-1) is even,
  not odd) -- the helper is explicitly skipped, and
  `realisability_check` remains the v0.4 `"plucker_arity_n"`.
- In random testing at arity 6, none of 200 random odd-parity
  signatures pass v0.4's standard Plücker enumeration alone. The
  v0.5 contribution is therefore primarily MATHEMATICAL COMPLETENESS
  (proven-sufficient check), not new rejections in practice.

### Tests
- 4 new tests in `test_compose.py`:
  * `test_v05_augmented_identities_vanish_on_realisable_arity_6`:
    a signature built from a random 7x7 skew matrix via the
    augmented Pfaffian framework passes v0.5's check and reports
    `"plucker_arity_n_full"`.
  * `test_v05_augmented_identities_reject_perturbed_arity_6`:
    perturbing a weight-3 tau entry by 30% of max-abs is rejected.
  * `test_v05_realisability_check_at_arity_5_does_not_promote`:
    at arity 5, the `realisability_check` never becomes
    `"plucker_arity_n_full"` (v0.5 explicitly skips odd-arity).
  * `test_v05_augmented_helper_directly_returns_zero_on_realisable`:
    direct test that the helper returns 30 values for arity 6, all
    of which are below scale-invariant tolerance on a realisable
    input.
- 268/268 tests pass (v0.5 D3 baseline was 264; net +4).

**Deliverable 2 (Lipton-Tarjan spanning-tree fundamental-cycle backup) — complete.**
The `_lipton_tarjan_separator` function now falls back to a tree-edge
balanced-cut backup when the BFS-layer simple case fails, catching
adversarial planar graphs (e.g., double-stars) where every BFS level
violates either the size bound or one of the partition bounds.

### Tree-edge backup (decompose.py)
- New private function `_lipton_tarjan_tree_backup(vertices, adj,
  levels, n, bound_AB, bound_S)` implementing a simpler form of
  the Lipton-Tarjan 1979 backup argument:
    1. Build the BFS spanning tree from the BFS levels already
       computed.
    2. Compute subtree sizes via post-order traversal.
    3. Find the tree edge whose removal gives the most balanced
       partition (closest to 50/50, both sides ≤ 2n/3).
    4. Initial separator = endpoints of the balanced tree edge.
    5. Iteratively augment with offending non-tree-edge endpoints
       until no A-B direct edge remains.
    6. Validate final |S| ≤ 2*sqrt(2n); otherwise honest-stop.
- `_lipton_tarjan_separator` modified: on simple-case failure,
  invoke the backup instead of raising immediately. Only raise if
  the backup ALSO fails (with combined diagnostics).
- Found optimal separator on a corpus of double-stars (k=m=15
  through k=m=50): `S = {center_0, center_1}` of size 2 in every
  case, well within the LT bound.

### Tests
- 4 new tests in `test_decompose.py`:
  * `test_v05_tree_backup_catches_double_star`: the n=42 symmetric
    double-star case where v0.4 raises. v0.5 finds the optimal
    |S|=2 separator.
  * `test_v05_tree_backup_handles_various_double_stars`: 5 sizes
    of symmetric double-stars (n=32, 42, 52, 62, 102), all valid
    partitions within LT bounds.
  * `test_v05_planar_separator_auto_works_on_double_star`: end-to-end
    `PlanarSeparator(auto=True)` matching count via the backup
    equals brute force.
  * `test_v05_tree_backup_disconnected_still_raises`: the backup
    doesn't change disconnected-graph handling (still raises before
    backup invocation).
- 272/272 tests pass (v0.5 D1 baseline was 268; net +4).

### Honest scope (v0.5 D2)
- Implements the SIMPLER form of LT 1979's backup (tree-edge
  balanced-cut + augmentation), not the original paper's
  fundamental-cycle-via-planar-dual argument. Sufficient for many
  practical planar graphs (notably tree-like separator structures).
- For graphs where the tree-edge cut's augmentation grows |S|
  beyond `2*sqrt(2n)`, the backup honestly raises and the caller
  falls back to user-supplied. This can happen on densely-connected
  planar graphs where the spanning-tree backup is suboptimal.
- The full Lipton-Tarjan 1979 algorithm with the planar embedding
  and dual graph is a v0.6 deliverable.

### Package metadata (v0.5 release)
- Version bumped to `0.5.0a1` in `pyproject.toml`,
  `structural_computing/__init__.py`, and the smoke test.
- `holant-tools` dependency floor stays at `>=0.5.0`.

### Cumulative state
- 272 tests passing (229 v0.3 baseline + 33 v0.4 + 10 v0.5).
- Public API surface unchanged at the export level. Additions:
  closed-form complex-roots branch in
  `_basis_from_recurrence_kernel` (D3); new helper
  `_augmented_plucker_identities_arity_n_odd` (D1); new function
  `_lipton_tarjan_tree_backup` (D2).
- New `realisability_check` value `"plucker_arity_n_full"`
  available on `HolographicBasisResult`.

### Deferred to v0.6+
- Full Lipton-Tarjan 1979 backup with the planar embedding /
  dual-graph argument (for adversarial cases the v0.5 tree-edge
  backup can't handle).
- `|S|≥3` augmented Plücker configurations at arity ≥ 8
  (the `|S|=2` case ships in v0.5 D1).
- Odd-arity-specific augmented identities (v0.5's augmented helper
  only applies at even arity ≥ 6).
- Tropical optimisation (per NEXT.md §(δ)).
- Diagnostic layer for CP-SAT / Gurobi / SLURM (per §(ε)).
- Wrapper consolidation: `StructuralComputer` → `Orchestrator`
  delegation.
- PyPI publication of v0.5.0a1.



## [0.4.0a1] — 2026-05-31 (v0.4 alpha — MGI + Lipton-Tarjan + SRP closed-form)

**v0.4 closes the three open items from the v0.3 "out of scope" list:
matchgate-identity (MGI) realisability checking for general
(non-symmetric) signatures, Lipton-Tarjan auto-discovery of planar
separators, and a closed-form fragment of the Cai-Lu SRP search that
catches signatures whose recurrence roots lie outside the v0.3 grid
range.** 262 tests pass (up from 229 in v0.3; +33 new tests across
the three deliverables). Honest-scope limitations are documented per
deliverable below.

### Deliverable 1: MGI for general (non-symmetric) signatures

The matchgate-identity (MGI) realisability check on general
(non-symmetric) signatures is now wired through
`transform_signature_general`, populating
`HolographicBasisResult.is_realisable` (no longer `None` for general
inputs) and the new `realisability_check` field that names which
identity was applied.

### Matchgate-identity wiring (compose.py)
- `HolographicBasisResult` gained a `realisability_check: Optional[str]`
  field naming the check that produced `is_realisable`. Values:
  `"order_2_recurrence"` (symmetric path via Cai-Lu Thm 2.5),
  `"parity_only"` (general arity < 4 -- Valiant 2008 Prop 6.1, 6.2),
  `"matchgate_identity_arity_4"` (general arity 4 via the
  Grassmann-Pluecker even-parity identity and the augmented-Pfaffian
  odd-parity identity), `"plucker_arity_n"` (general arity >= 5 via
  the Plücker enumeration plus, for even arities, the augmented
  weight-1 identity), `"deferred"` (the genuinely-zero signature
  shortcut).
- `HolographicBasisPair.transform_signature_general` now calls a new
  private `_check_general_realisability` method after the tensor
  contraction. The check delegates to `holant_tools.non_symmetric`'s
  identity functions:
    * `matchgate_identity_arity_4_even` / `matchgate_identity_arity_4_odd`
      for arity 4;
    * `matchgate_identities_arity_n_even` /
      `matchgate_identities_arity_n_odd` plus, for even arities,
      `matchgate_identity_augmented_weight_1_arity_n_odd` for arity >= 5.
- New helpers `_flat_index_to_bitstring` and `_build_tau_dict`
  bridge the bitstring-convention mismatch between structural-computing
  (axis 0 = MSB of flat index after `tensor.reshape((2,)*a)`) and
  holant-tools (LSB-first via `(mask >> i) & 1`).
- Scale-invariant tolerance: identities are compared against
  `self.tol * max(max_abs^2, 1.0)` since each identity term is
  quadratic in tau values.

### Orchestrator (orchestrator.py)
- `_holographic_transform_general_leaf` returns the new
  `is_realisable` and `realisability_check` fields alongside the
  transformed `values`, `arity`, and `basis_matrix`.

### Tests (tests/test_compose.py, tests/test_orchestrator.py)
- 10 new tests in `test_compose.py` covering: symmetric arity-4 even-
  parity matchgate-realisable case (z_2^2 = z_0*z_4); perturbation
  rejection; zero signature; symmetric arity-4 odd-parity (vacuous-on-
  symmetric noted); asymmetric arity-4 odd-parity rejection via the
  augmented-Pfaffian identity; arity-2 parity-only positive + negative;
  arity-5 Plücker zero signature; arity-5 random rejection; basis
  transformation changing realisability (3-AND under Hadamard
  illustrating the standard-vs-some-basis distinction).
- 1 new test in `test_orchestrator.py` verifying the leaf surfaces
  the new fields end-to-end on a symmetric matchgate-realisable
  arity-4 even-parity signature.
- Updated 1 existing v0.3 contract test
  (`test_transform_general_is_realisable_is_none_for_general` ->
  `test_transform_general_realisability_populated_by_mgi_check`)
  to assert the new behaviour.
- All 233 existing tests still pass; total now ~244.

### Honest scope (v0.4)
- The check answers "is the TRANSFORMED signature matchgate-realisable
  on the STANDARD basis?" -- a stricter criterion than the symmetric
  API's "realisable on SOME basis" check via Cai-Lu Thm 2.5.
- For arity >= 6 ODD-parity, the Plücker enumeration plus the
  augmented weight-1 identity is a TIGHT NECESSARY check but not
  provably sufficient. Further augmented-Pfaffian Plücker relations
  (weight-3 x weight-3 pairings, etc.) are research-grade and
  deferred. For arity 4 (both parities) and arity 5 (even parity is
  Plücker-complete; odd parity is covered by the standard
  enumeration), the check is sufficient.

**Deliverable 3 (SRP search polish) — complete.** A closed-form
derivation of the basis matrix from the order-2 recurrence kernel
is now tried BEFORE the canonical-bases sweep in `discover_basis`,
catching rank-1 signatures whose root lies outside the v0.3 grid
search's `[-2, +2]` range -- a documented failure mode.

### SRP search closed-form (compose.py)
- New static method `HolographicBasisPair._basis_from_recurrence_kernel(a, b, c)`
  returning T = [[1, -r_2], [1, -r_1]] for distinct real roots of
  c*x^2 + b*x + a = 0, or a rank-1 form T = [[1, 0], [1, -r]] when
  the kernel is degenerate (c=0 or a=0, indicating an order-1
  recurrence from a rank-1 signature). Returns None for complex
  roots, double roots, and truly trivial kernels -- the caller then
  falls through to the v0.3 canonical-bases-and-grid search.
- `discover_basis` now tries the closed-form T immediately after
  the realisability gate, before the canonical-bases sweep. When
  the closed-form lands within the matchgate-standard tolerance, it
  returns the basis directly -- no search required.
- `_matchgate_standard_distance` was fixed to correctly handle the
  Cai-Gorenstein degenerate cases a=0 (only z_n non-zero) and b=0
  (only z_0 non-zero): leading / trailing zeros in the non-zero-
  position subsequence are now allowed, while TRUE interior zeros
  (strictly between the first and last non-zero) still break the
  geometric progression. Without this fix, single-point matchgate-
  standard signatures produced by the closed-form would be
  incorrectly rejected.

### Tests
- 5 new tests in `test_compose.py`:
  * `test_srp_closed_form_finds_rank1_basis_outside_v03_grid`: 8
    rank-1 signatures with roots in `{5, 10, -7, 3, 100, 0.5, -3}`
    spanning arities 3-5, all discovered via the closed-form.
  * `test_srp_closed_form_handles_negative_and_fractional_roots`:
    50 random rank-1 signatures with roots in `[-15, +15]`,
    arities 3-5 -- all discovered.
  * `test_srp_rank2_correctly_returns_none_when_no_basis_exists`:
    a genuinely rank-2 signature (z_k = 5^k + 7^k) correctly fails
    to find a matchgate-standard basis (no such basis exists in
    any 2x2 GL_2).
  * `test_srp_closed_form_skipped_for_complex_roots`: NAE-3 [0, 1,
    1, 0] (complex roots) falls through correctly to the existing
    Hadamard candidate.
  * `test_basis_from_recurrence_kernel_degenerate_cases`: direct
    tests of the helper's case-by-case returns.
- Updated 1 existing v0.3 test
  (`test_discover_basis_returns_none_for_degenerate_single_cube` ->
  `test_discover_basis_finds_single_cube_via_v04_closed_form`) to
  reflect that the v0.3 limitation has been fixed.

### Honest scope (v0.4)
- The closed-form catches RANK-1 signatures whose root lies anywhere
  in the real line, AND rank-2 signatures whose roots are real and
  distinct. The v0.3 search's `[-2, +2]` grid no longer constrains
  reach.
- Rank-2 signatures with COMPLEX roots fall through to the v0.3
  canonical-bases search (Hadamard typically suffices for the
  common cases like NAE-3).
- Genuinely matchgate-rank-2 signatures (A != 0 AND B != 0 in the
  z_k = A*r_1^k + B*r_2^k decomposition, with A != ±B) have no
  basis that produces matchgate-standard form -- the search
  correctly returns None for these.

**Deliverable 2 (Lipton-Tarjan auto-separator) — complete.** The
`PlanarSeparator` class gained an `auto=True` mode that discovers
the partition `(S, A, B)` via the simple case of Lipton-Tarjan 1979
when `decompose()` is called. No user-supplied separator is needed
for planar graphs that the simple case handles.

### Lipton-Tarjan implementation (decompose.py)
- New private function `_lipton_tarjan_separator(problem)` implementing
  the simple case of Lipton-Tarjan 1979: BFS-layer from any root,
  find a level `L_t` whose size is at most `2*sqrt(2*|V|)` and where
  the levels above and below each carry at most `2|V|/3` vertices.
  Returns `(S, A, B)` partitioning the vertex set with no direct
  A-B edge. The guarantees `|S| <= 2*sqrt(2*|V|)` and `|A|, |B| <=
  2|V|/3` follow from the theorem.
- Disconnected inputs and graphs where the simple case fails (fat
  middle level) honestly raise `ValueError`. The full spanning-tree-
  fundamental-cycle backup is deferred to v0.5.
- `PlanarSeparator.__init__` now accepts `auto: bool = False`. When
  True, the `separator/side_a/side_b` arguments may be omitted; they
  are computed by `_lipton_tarjan_separator` in `decompose()`. The
  v0.3 manual-mode API is preserved unchanged.
- `decompose()` re-discovers the separator on every call when in
  auto mode, so a single instance can be reused across multiple
  graphs.

### Orchestrator (orchestrator.py)
- Phase 4.8 now accepts `hints["planar_separator"] = "auto"` as
  shorthand for `PlanarSeparator(auto=True)`. The existing dict
  form `{"separator": ..., "side_a": ..., "side_b": ...}` continues
  to work. The auto-discovered separator size is recorded in the
  `reductions_applied` list (e.g.
  `"PlanarSeparator(auto, |S|=3)"`).
- The `evaluate()` docstring's Phase 4.8 description updated to
  document both hint forms.

### Tests
- 11 new tests in `test_decompose.py`:
  * `test_lipton_tarjan_partition_is_valid_on_grids`: partition
    properties (cover, disjoint, no direct A-B edge) on grids
    3x3 through 6x6.
  * `test_lipton_tarjan_size_bound_holds_on_grids`: `|S| <= 2*sqrt(2|V|)`
    on grids up to 8x8.
  * `test_lipton_tarjan_balanced_sides_on_grids`: `|A|, |B| <= 2|V|/3`
    on grids 4x4 through 8x8.
  * `test_lipton_tarjan_handles_k4`: K_4 (small planar graph).
  * `test_lipton_tarjan_handles_cycles`: C_4 through C_10.
  * `test_lipton_tarjan_disconnected_raises`: honest-stop on
    disconnected graphs.
  * `test_lipton_tarjan_trivial_small_graph`: n < 3 trivial case.
  * `test_planar_separator_auto_mode_round_trip_on_grids`: end-to-end
    matching count matches brute force on a 4x4 grid.
  * `test_planar_separator_auto_round_trip_on_cycles`: C_4, C_6.
  * `test_planar_separator_auto_re_discovers_per_call`: single
    auto-instance reused on multiple graphs.
  * `test_planar_separator_auto_mode_constructor_validation`:
    auto=False without sets raises; auto=True without sets is fine.
- 2 new tests in `test_orchestrator.py` covering the
  `hints["planar_separator"] = "auto"` shorthand.
- All 249 prior tests still pass; total now ~262.

### Honest scope (v0.4)
- The simple case of Lipton-Tarjan handles MOST practical planar
  graphs (grids, geometric meshes, dependency graphs).
- Adversarial planar graphs with a "fat middle level" require the
  spanning-tree fundamental-cycle backup case, which has corner
  cases (non-cellular embeddings on disconnected residuals,
  degenerate fundamental cycles) that aren't yet implemented. The
  function honestly raises `ValueError` for these inputs; the
  caller should fall back to manual-mode `PlanarSeparator(separator=
  ..., side_a=..., side_b=...)`.
- Disconnected inputs are explicitly rejected -- Lipton-Tarjan
  requires connectivity.

### Package metadata
- Version bumped to `0.4.0a1` in `pyproject.toml`,
  `structural_computing/__init__.py`, and the smoke test.
- `holant-tools` dependency floor remains `>=0.5.0` (the MGI engine
  functions are available from holant-tools v0.4.0 stable, but
  v0.5.0 is the currently-tested target).

### Cumulative state
- 262 tests passing (229 v0.3 baseline + 33 new across the three
  deliverables).
- Public API surface unchanged at the export level -- additions are
  internal helpers + new fields on existing dataclasses
  (`HolographicBasisResult.realisability_check`) + new keyword
  argument on `PlanarSeparator.__init__` (`auto=False`).

### Deferred to v0.5+
- Full Cai-Lu §4 d-admissibility for general signatures
  (d-dimensional solution subvarieties at arity >= 6 odd-parity).
- Lipton-Tarjan spanning-tree fundamental-cycle backup for
  "fat middle level" planar graphs.
- Closed-form SRP for rank-2 signatures with complex roots (NAE-3-
  like cases that currently rely on the Hadamard canonical
  candidate).
- Wrapper consolidation: `StructuralComputer` delegating fully
  through `Orchestrator.evaluate(...)`.
- PyPI publication of v0.4.0a1 (gating step for
  `structural-computing-bench`'s release).

## [0.3.0a1] — 2026-05-28 (v0.3 alpha — calibration + holographic + closure)

**v0.3 closes the calibration loop, ships the holographic toolkit, and
fills in every open Composition / Decomposition sketch from v0.2.**

### Calibration loop
- `structural_computing/calibration.py`: optional module for loading
  cost-model calibration data produced by the companion repo
  `structural-computing-bench`. Exposes `apply_calibration`,
  `clear_calibration`, `get_calibration`, `has_calibration_for`,
  `predict_seconds`.
- Router wiring: `route(classification, question=...)` now consults the
  calibration registry. When a calibration entry exists for
  `(tier, question)`:
    * the cost field switches to `log2(predicted_seconds)`,
    * the meter `cost_unit` is set to `"log2_seconds"`,
    * `predicted_seconds` and `cost_source="calibrated"` are surfaced.
  Without calibration, cost stays `log2(ops)` with
  `cost_unit="log2_ops"` and `cost_source="heuristic"`.
- Orchestrator wiring: when calibration is loaded for the about-to-fire
  `(tier, question)`, the orchestrator emits a `[predict]` step in the
  workflow trace before dispatch, recording the predicted seconds and
  the size-hint used.
- Companion repo `structural-computing-bench` (new, separate):
  timing primitives, curve fitters (power-law / exponential), problem
  generators per leaf evaluator, calibration runner CLI, orchestrator-
  trace analytics. Lives at github.com/pcoz/structural-computing-bench.

### Holographic toolkit (compose.py)
- `HolographicBasisPair.transform_signature_general(values, arity)`:
  applies `T^{otimes a}` to a general (non-symmetric) length-2^arity
  signature tensor via `a` sequential 2x2 contractions — O(a * 2^a)
  per call instead of the naive O(2^{2a}). End-to-end verified:
  Hadamard maps `[1, 0, 0, 1]` (general view of 3-AND) to `[0, 2, 0, 2]`;
  T then T^{-1} round-trips a random arity-3 signature.
- `HolographicBasisPair.discover_basis(values)`: practical fragment of
  Cai-Lu's SRP. Realisability gate (Cai-Lu Thm 2.5 order-2 recurrence)
  + canonical-bases sweep (identity, Hadamard, swap, common shears,
  rotation_4) + parameterised grid + coordinate-descent polish.
  Scale-invariant matchgate-standard distance scoring rejects spurious
  near-zero collapses. Finds Hadamard for `[1, 0, 0, 1]` and `[0, 1,
  1, 0]`; honest stop on non-realisable signatures and degenerate
  single-cube polynomials.
- `HolographicBasisPair.discover_common_basis(signatures)`: multi-
  signature SRP via Cai-Lu §4. Finds a single T that puts every input
  signature into matchgate-standard form. Returns None when no common
  basis exists (e.g., conflicting basis requirements or any signature
  is non-realisable).

### Compositions and decompositions (close every v0.2 sketch)
- `Projection` (compose.py): user-supplied projector callable mapping a
  list of sub-evaluations to a single composed value. Generalises
  `LinearCombination` to any combiner (ratio, inclusion-exclusion,
  max/min, etc).
- `BranchSum` (compose.py): named `(name, amplitude, sub_problem)`
  branches with `sum(amp_i * sub_eval(branch_i))` combine. Amplitudes
  may be complex (Clifford+T pattern).
- `PlanarSeparator` (decompose.py): divide-and-conquer along a user-
  supplied vertex separator; enumerates `(S_to_A, S_to_B, S_pairs)`
  partitions of the separator vertices; sums weighted products of
  restricted-graph PerfMatches. Verified on C_4 / C_6 / weighted C_4
  against brute force.
- `RecursiveCircuitCut` (decompose.py): cut along a user-supplied edge
  set; enumerate `2^|cut|` forced-in/forced-out assignments with
  shared-endpoint pruning. The Tutte / Lovasz-Plummer identity
  presented as a decomposition tree.

### Orchestrator (new questions and routes)
- New leaf evaluator `_holographic_transform_general_leaf` registered
  for `('T3', 'holographic_transform_general')`. The orchestrator's
  `_classify_problem` detects general-signature problem dicts (by the
  simultaneous presence of `values` + `arity` + `basis_matrix`) and
  routes them to a new T3 `classify_signature_general` branch.

### Tests / examples
- 229/229 in the main suite (excluding the originality directory).
- Examples 12 (auto-discovery) and 13 (general transform) added.

### Out of scope for v0.3 (deferred to v0.4)
- Matchgate-Identity (MGI) realisability check for general (non-
  symmetric) signatures on the 2^a-dim tensor.
- Auto-detection of Lipton-Tarjan separators for `PlanarSeparator`.

## [0.2.0a1] — 2026-05-28 (v0.2 alpha — reductions layer)

**v0.2 closes the v0.1 NotImplementedError gaps** with real
constructions from the matchgate-Holant literature, plus a richer
orchestrator surface.

### Reductions (transform.py)
- `HybridDecomposition` — full Tutte/Lovasz-Plummer DP on extra edges
  (`M(G) = M(G-e) + M(G/uv)` recursion); auto-discovery via
  `auto_detect_extras` greedy genus heuristic.
- `RationaliseWeights` — real-valued edge weights scaled to integers
  at user-chosen precision, with inverse to descale the final answer.
- `CrossingElimination` — Cai-Gorenstein 6-vertex/7-edge crossover
  gadget at each declared crossing (arXiv:1303.6729 Fig. 6). Preserves
  matchgate signature (signed Pfaffian), not unsigned PerfMatch in
  general; docstring is explicit about this.
- `HighDegreeVertexSplit` — Cai-Gorenstein 2k-node triangle-cycle
  realisation of matchgate-realisable symmetric signatures (Theorem 9
  + Fig. 10); odd-arity case via Fig. 11. All 16 entries of `[2, 0, 6,
  0, 18]` match brute-force PerfMatch exactly.

### Compositions (compose.py)
- `HolographicBasisPair` — Cai-Lu 2011 polynomial-substitution basis
  change on symmetric signatures + matchgate-realisability check via
  the order-2 recurrence rank test (Theorem 2.5). Hadamard basis
  transforms 3-AND [1,0,0,1] into matchgate-standard [0,2,0,2].
  Result type `HolographicBasisResult` carries the transformed values,
  realisability flag, and (when realisable) the (a, b, c) kernel vector.

### Decompositions (decompose.py)
- `TreewidthBoundedDP` — full Bodlaender-style multi-bag DP for
  matching count on bounded-treewidth graphs (single-bag was v0.1).

### Orchestrator
- 7-phase workflow with new phases:
  - Phase 1.5 `rationalise` — hint-driven `RationaliseWeights`.
  - Phase 4.5 `treewidth-dp` — hint-driven `TreewidthBoundedDP`.
  - Phase 4.7 `crossing-elimination` — hint-driven `CrossingElimination`.
- New leaf evaluators:
  - `weighted_matching_sum` for T2/T4 graphs.
  - `matchgate_realisation` for T2/T3 signatures (via
    `HighDegreeVertexSplit`).
- `verbose=True` + custom `log=...` parameters stream each step + reason
  as the orchestrator runs.
- `OrchestratorResult.workflow_trace` carries the full audit trail of
  phases attempted, with outcome + detail per step.

### Verifier
- `brute_force_weighted_matching_sum` — exact weighted
  perfect-matching reference for testing weighted reductions.

### Examples
- 7 self-contained examples (numbered 05-11) covering: hybrid
  decomposition, signature classification, treewidth DP, rationalise
  weights, holographic basis unlock, crossing elimination, high-degree
  vertex split.

### Research artefacts (private repo)
- `admissibility-geometry/research/{crossing_elimination_cai_gorenstein,
  high_degree_vertex_split_symmetric_matchgate,
  holographic_basis_pair_cai_lu}.md` carry the full literature
  extractions used to ship the constructions.

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
