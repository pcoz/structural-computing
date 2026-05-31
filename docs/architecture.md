# `structural-computing` — Architecture

**Audience:** contributors and downstream developers who need a complete
mental model of how the package fits together. Reading this end-to-end
takes ~20 minutes and should cover everything you'd otherwise have to
piece together from the source.

**Version covered:** v1.1.0 (released 2026-05-31; current `main`).

---

## 1. Purpose

### 1.1 The problem this codebase exists to solve

Most software that answers combinatorial questions —
"how many valid configurations are there?", "what is the exact
probability of failure?", "are these two designs measurably different?"
— either **samples** (Monte Carlo, with a noise floor that hides small
but real differences), **estimates** (heuristics with no guarantee),
or **gives up** when the problem is too large to brute-force. For a
large subclass of questions that practitioners actually care about,
this is overkill: there is a structural shape underneath the problem
(planar, bounded-genus, matchgate-Holant, GF(2)-affine) that admits an
**exact polynomial-time answer**, and the math for that answer has
existed since Kasteleyn's 1961 FKT theorem and Valiant's 2004
holographic algorithms. What has been missing is a **runnable form**
of those results — a single package that takes your problem in any
common representation, decides whether it fits the shape, applies any
needed transformation if it doesn't, and returns a bit-identically
reproducible answer with provenance. Where it doesn't fit, the
package stops honestly rather than producing a confident-but-wrong
number.

`structural-computing` is that runnable form.

### 1.2 Why this matters

The exact-vs-sampled distinction has practical consequences in several
domains:

- **Regulator-grade comparisons.** Two reinsurance treaty structures,
  two network topologies, two reliability designs that *look*
  equivalent under Monte Carlo (their difference lives below the
  sampling noise floor) can be distinguished provably here. The
  framework returns *"Configuration B is 90.2% more reliable, provably
  real, not a sampling artefact"* in milliseconds — a defensible
  verdict you can put in a filing.
- **Rare-tail probabilities.** The probability of a black-swan
  failure mode is exactly the regime where Monte Carlo is worst —
  variance scales with `1/p`. For the right problem shape this
  package computes the same quantity exactly.
- **Counting whole solution spaces.** Standard solvers find *one*
  satisfying assignment; this package returns the count and surfaces
  structural single-points-of-failure across the whole space.
- **Reproducibility.** Same inputs → same exact bits, every run, every
  machine, every Python version. No RNG seed, no convergence threshold,
  no platform drift. This is the kind of computation that survives
  six months of audit.

### 1.3 Who this codebase serves

There are three concentric audiences:

1. **End users** (a developer with a graph and a question, no
   Holant-Holant-Holant background needed) — they live in
   `StructuralComputer`'s one-liner API.
2. **Power users / framework integrators** (someone composing custom
   pipelines, wiring in their own leaf evaluators, plugging the
   package into a workflow DSL or a catastrophe-modelling system) —
   they live in `Orchestrator`, the leaf-evaluator registry, the
   reductions / compositions / decompositions protocols, and the
   pipeline-router primitives.
3. **Researchers widening the in-family boundary** (someone adding a
   new gadget, a new basis-discovery algorithm, a new matchgate
   identity, a new tier to the hierarchy) — they live in
   `transform.py` / `compose.py` / `decompose.py`, the classifier, and
   the originality tests.

The package is designed so each audience can ignore the layers above
their level and the layers below stay stable as the package grows.

### 1.4 What problem categories the package handles

The natively-in-family slice covers:

- **Perfect-matching count** on planar or bounded-genus graphs.
- **Weighted matching sums** on the same.
- **Rare-tail / reliability probabilities** under independent edge
  failure.
- **Single-points-of-failure** and **witnesses** (one specific
  matching).
- **Regulator-grade comparisons** between two configurations on any of
  the above.
- **Constraint-set counting / witnessing** over GF(2) (linear and
  quadratic).
- **Symmetric-signature classification** — matchgate rank, basis-aware
  realisability, basis discovery via Cai-Lu SRP.
- **General (non-symmetric) signature transformation** via the full
  `T^{⊗a}` tensor-power action.

The reductions / compositions / decompositions layer widens this to
include **near-planar matching** (HybridDecomposition),
**bounded-treewidth matching** (TreewidthBoundedDP), **planar
graphs with declared crossings** (CrossingElimination), **graphs split
by a vertex separator** (PlanarSeparator), and **graphs cut along a
small edge set** (RecursiveCircuitCut). Each transformation is a real
construction from the matchgate-Holant literature, not a placeholder.

### 1.5 What the package deliberately does NOT do

- **No silent approximation.** If your problem is genuinely outside the
  framework's reach (mod-p arithmetic for `p ≠ 2`, unbounded matchgate
  rank with no decomposition, continuous mathematics with no
  discretisation), the framework raises `NotInFamily` or
  `NoKnownReduction` with the classification attached. It will not
  produce a Monte-Carlo estimate as a fallback.
- **No general-purpose SAT / SMT / ILP solving.** Out-of-family problems
  are referred to the right external tool by name — `advised:external-solver`.
- **No timing / benchmarking machinery in the core.** That work lives
  in the sibling repo `structural-computing-bench`, which produces a
  calibration data file this package can opt-in load.
- **No black-box ML / neural inference.** Every answer the framework
  produces is symbolic and reproducible.

### 1.6 What this package is, mechanically

Putting all of the above into a single mechanical paragraph:
`structural-computing` answers combinatorial questions
(perfect-matching count, rare-tail probability, single-point-of-failure
detection, weighted matching sum, signature-realisability) **exactly**
and in **polynomial time** for problems whose underlying structure is
planar / bounded-genus / matchgate-Holant / GF(2)-affine. When the
problem already has that structure, an answer comes back via the FKT
theorem, Kasteleyn orientations, or Gaussian elimination over GF(2).
When it doesn't, a **reductions / compositions / decompositions**
layer tries to transform it into a form that does. When *that* fails
too, the framework **honest-stops** with a `NoKnownReduction` /
`NotInFamily` exception carrying the classification — no silent
approximation. The mathematical engine for the in-family work lives
in the sibling package `holant-tools`; this package is the orchestrator,
classifier, reduction layer, and user-facing API on top of it.

---

## 2. Repository layout

```
structural-computing/
├── structural_computing/      ← the installable Python package (this doc)
│   ├── __init__.py            ← public API surface (49 exports)
│   ├── easy.py                ← StructuralComputer wrapper (the friendly entry point)
│   ├── orchestrator.py        ← top-level evaluate(problem, question) engine
│   ├── classify.py            ← tier classifier (T0..T7)
│   ├── route.py               ← tier → member + cost
│   ├── calibration.py         ← optional log2(seconds) cost-model loader
│   ├── pipeline_router.py     ← Stage / Route / run_pipeline driver
│   ├── trace.py               ← RichTrace aggregator
│   ├── replay.py              ← ReplayCache memoisation
│   ├── verifier.py            ← brute-force references + verify_pipeline
│   ├── transform.py           ← reductions (one-shot transformations)
│   ├── compose.py             ← compositions (combine multiple in-family evals)
│   └── decompose.py           ← decompositions (recursive splitting)
├── tests/                     ← pytest suite (302 tests across 15 modules)
│   ├── test_smoke.py          ← public-API contract + wrapper smoke
│   ├── test_orchestrator.py   ← 26 orchestrator scenarios
│   ├── test_{module}.py       ← per-module coverage
│   └── originality/           ← guards the two publicly-original results
├── examples/                  ← 13 self-contained runnable scripts
├── docs/                      ← this folder (architecture.md is this file)
├── pyproject.toml             ← packaging: name, deps, classifiers
├── README.md                  ← user-facing intro
├── CHANGELOG.md               ← per-release notes
└── LICENSE                    ← MIT-with-attribution
```

The 8164 source lines split roughly: **compose** 22%, **decompose** 16%,
**orchestrator** 15%, **transform** 14%, **easy** 9%, **route** 4%,
**classify** 4%, everything else < 4% each.

---

## 3. The layered architecture

The package is organised into five layers. Each layer depends on the
ones below it; there are no upward dependencies.

```
┌──────────────────────────────────────────────────────────────────┐
│  Layer 5 — USER-FACING ENTRY POINTS                              │
│  • StructuralComputer          (easy.py)         one-liners      │
│  • Orchestrator                (orchestrator.py) evaluate()      │
└──────────────────────────────────────────────────────────────────┘
                              │
┌──────────────────────────────▼───────────────────────────────────┐
│  Layer 4 — TRANSFORMATION LAYER  (widens the in-family boundary) │
│  • Reductions     transform.py    one-shot problem → problem'    │
│  • Compositions   compose.py      combine k in-family evals      │
│  • Decompositions decompose.py    recursive split, leaves in-fam │
└──────────────────────────────────────────────────────────────────┘
                              │
┌──────────────────────────────▼───────────────────────────────────┐
│  Layer 3 — CLASSIFIER + ROUTER  (decide WHAT to run)             │
│  • classify.py    problem  → Classification(tier, meters, in_fam)│
│  • route.py       Classification → Route(member, cost, meters)   │
│  • calibration.py optional: flip cost from log2(ops)→log2(sec)   │
└──────────────────────────────────────────────────────────────────┘
                              │
┌──────────────────────────────▼───────────────────────────────────┐
│  Layer 2 — IN-FAMILY LEAF EVALUATORS  (do the actual work)       │
│  • Leaf evaluators in orchestrator.py (registered by (tier,Q))   │
│  • Wrap brute-force / Pfaffian / FKT / Kasteleyn primitives      │
│  • Brute-force references in verifier.py                         │
└──────────────────────────────────────────────────────────────────┘
                              │
┌──────────────────────────────▼───────────────────────────────────┐
│  Layer 1 — FRAMEWORK PRIMITIVES + EXTERNAL ENGINE                │
│  • pipeline_router.py: Stage / Route / Trace / run_pipeline      │
│  • trace.py:           RichTrace aggregator                      │
│  • replay.py:          ReplayCache (LRU memoisation)             │
│  • holant-tools:       Pfaffian, FKT, Kasteleyn, matchgate rank, │
│                        dart-chain primitive (HARD DEPENDENCY)    │
└──────────────────────────────────────────────────────────────────┘
```

### What each layer is for

| Layer | Mental model | When you touch it |
|---|---|---|
| **5 — Entry points** | "Make it one method call" / "Just give me an answer with provenance" | Adding a new user-facing method or question |
| **4 — Transformation** | "Beat my problem into matchgate-Holant shape" | Adding a new reduction/composition/decomposition primitive |
| **3 — Classifier/router** | "What tier is this? What's it cost?" | Recognising a new problem type or tier |
| **2 — Leaf evaluators** | "Run the right algorithm on an in-family problem" | Adding a new (tier, question) leaf |
| **1 — Primitives** | "Plumbing that supports everything above" | Almost never — these are stable seams |

---

## 4. The two entry points

There are two ways into the package. Both ultimately call the same
machinery; pick the one that matches your level of detail.

### 4.1 `StructuralComputer` — the friendly wrapper (`easy.py`)

For users who want one method call and an answer:

```python
from structural_computing import StructuralComputer
sc = StructuralComputer()

sc.count_matchings(graph)                # exact integer
sc.witness(graph)                        # one specific matching
sc.tail_probability(graph, p_fail)       # exact rare-tail probability
sc.single_points_of_failure(graph)       # critical edges
sc.compare(graph_a, graph_b, p_fail)     # CompareReport (more reliable + Δ)
sc.audit(graph, p_fail=0.01)             # full report as a dict
sc.explain(graph)                        # human-readable plan
sc.classify(graph)                       # Classification

# Constraint sets (T0/T1)
sc.classify_constraints(A=..., b=..., Q=..., c=...)
sc.count_solutions(A=..., b=...)
sc.find_witness_solution(A=..., b=...)
sc.list_solutions(A=..., b=...)

# Signatures (T2/T3)
sc.classify_function(values)
sc.matchgate_rank(values)
sc.is_matchgate_realisable(values)

# Non-planar matching via HybridDecomposition
sc.count_matchings_hybrid(graph, extra_edges=[...])
```

**Out-of-family** problems raise `NotInFamily(classification)` so the
caller can inspect why. Input formats are flexible: edge lists,
adjacency dicts, and rotation systems are all accepted by
`_normalise_graph` in `easy.py`.

The wrapper is intentionally **stateless** apart from
`self._last_classification`, which lets `explain()` print the most
recent routing decision.

### 4.2 `Orchestrator` — the dispatch engine (`orchestrator.py`)

For users who want provenance, hint-driven reductions, or to plug in
their own leaf evaluators:

```python
from structural_computing import Orchestrator
orch = Orchestrator()

result = orch.evaluate(problem, question="matching_count", hints={...},
                        verbose=False, log=None)

result.answer                  # the computed value
result.classification          # tier, in_family, meters, reasoning
result.reductions_applied      # ["NormaliseGraphFormat", "HybridDecomposition(...)"]
result.sub_evaluations         # count of leaf calls performed
result.leaf_evaluator_used     # which leaf fired
result.workflow_trace          # list[WorkflowStep], full audit trail
```

The Orchestrator is **registry-driven** — leaf evaluators and
reductions live in dicts you can mutate:

```python
orch.register_leaf_evaluator(tier="T2", question="my_question", evaluator=my_fn)
orch.register_reduction(MyReduction())
```

Where `StructuralComputer` is the convenience layer,
`Orchestrator` is the layer the wrapper *should* delegate to (and will
in a future cleanup — today the wrapper duplicates some leaf-evaluator
logic for historical reasons).

---

## 5. Canonical problem shapes

Every leaf evaluator, reduction, composition, and decomposition agrees
on **four canonical problem shapes**. Knowing them is most of knowing
the framework.

### 5.1 Graph (after normalisation)

```python
{
    "vertices": [v_0, v_1, ...],         # list of vertex labels
    "edges":    [(u, v), ...],           # list of undirected edge tuples
    "rotation": {v: [neighbour, ...]},   # rotation system (cellular embedding)
    "weights":  {(u, v): w, ...},        # optional; edges missing default to 1.0
}
```

`rotation` is the cellular-embedding-defining structure — for a planar
graph it is a planar rotation; for genus-`g` it is a genus-`g`
rotation. The classifier reads it to compute genus directly via the
Euler formula in `holant_tools.genus_from_rotation_system`.

`NormaliseGraphFormat` is the reduction that turns edge lists / adjacency
dicts into this shape; the Orchestrator runs it in Phase 1.

### 5.2 Constraint set (GF(2))

```python
{
    "A": ndarray(m, n) of {0, 1},        # linear part: A x = b (mod 2)
    "b": ndarray(m) of {0, 1},
    "Q": [ndarray(n, n) of {0, 1}, ...], # optional quadratic part: x^T Q_i x = c_i
    "c": ndarray(k) of {0, 1},
    "modulus": 2,                         # only modulus=2 is in-family
}
```

`modulus != 2` lands in **T7** (out-of-family, advised). The SRP-solver
branch lives in the sibling `admissibility-geometry` repo.

### 5.3 Signature (symmetric)

```python
{"values": [z_0, z_1, ..., z_n]}        # arity = n; one value per Hamming weight
```

The basis-aware matchgate rank is always in `{0, 1, 2}` for symmetric
signatures (one of the two publicly-original results — see §11).

### 5.4 Signature (general, non-symmetric)

```python
{
    "values": [...],                     # flat length-2^arity tensor
    "arity":  a,                          # number of wires
    "basis_matrix": [[p, q], [r, s]],     # 2x2 invertible T
}
```

Detected by `_classify_problem` (in `orchestrator.py`) when all three
keys are present and `len(values) == 2**arity`; routes to T3 with
`general=True` in the meters and dispatches to
`_holographic_transform_general_leaf`.

### 5.5 Multi-signature (for SRP common-basis search)

```python
{"signatures": [[z_0, ..., z_n], [w_0, ..., w_m], ...]}
```

Routes to T3 with `n_signatures` in meters; dispatched to
`_discover_common_basis_leaf` for the Cai-Lu 2011 §4 SRP search.

---

## 6. The tier hierarchy

Defined in `classify.py` (the docstring at the top of the module lays
out the full hierarchy). Every problem lands in one of these:

| Tier | Description | In-family? | Member used (when in-family) |
|------|-------------|------------|------------------------------|
| **T0** | GF(2)-affine: `A x = b (mod 2)` | yes | `ch-form` (Gauss-Jordan) |
| **T1** | GF(2)-quadratic: `x^T Q x = c (mod 2)` | yes | `ch-form` + post-selection |
| **T2** | Planar binary Holant (genus 0, arity-2 sigs) | yes | `free-fermion` (FKT Pfaffian) |
| **T3** | Higher-arity symmetric signatures (arity ≥ 3) | yes (rank ≤ 2) | `free-fermion` + parity-split |
| **T4** | Bounded-genus Holant (genus ≥ 1, finite) | yes | `free-fermion` (Klein arc, 4ᵍ scaling) |
| **T5** | Cardinality / threshold / mod counting | no, advised | pending (Stembridge degree-3+) |
| **T6** | Weighted optimisation / tropical Holant | partial | `tropical-pfaffian` (planar only) |
| **T7** | Out-of-family forever (mod-p ≠ 2, etc.) | no, advised | external solver |

For the in-family tiers, `route()` returns a finite cost. For advised
tiers, `cost = +inf` and the meters carry a reason. Cost is in
`log2(ops)` by default and `log2(seconds)` once
`apply_calibration(...)` is loaded.

### Cost models (in `route.py`)

| Tier | log2(ops) heuristic |
|------|---------------------|
| T0   | `3·log2(n) + 0.5` |
| T1   | `3·log2(n) + 1.0` |
| T2   | `3·log2(2·|V|) + 1.5` |
| T3   | T2 + `log2(rank)` |
| T4   | T2 + `g · log2(4)` |

These are asymptotic-complexity estimates, not benchmark-measured. The
calibration loader (§9) replaces them with measured-coefficient
predictions per-`(tier, question)` when supplied.

---

## 7. The transformation layer

This is the framework's **in-family-boundary widener**. Three sibling
modules, three different mental models, one common Protocol pattern in
each.

### 7.1 Reductions (`transform.py`)

One-shot `problem → problem'` transformations. Each `Reduction`
conforms to:

```python
class Reduction(Protocol):
    name: str
    def applies_to(self, problem: Any) -> bool: ...
    def apply(self, problem: Any) -> ReductionResult: ...
```

`ReductionResult` carries `(problem, cost_overhead, inverse, notes)`
— the `inverse` callable lifts an answer computed on the transformed
problem back to an answer for the original.

| Concrete reduction | What it does | Reference |
|---|---|---|
| `NormaliseGraphFormat` | coerce edge-list/adj-dict to canonical graph dict | — |
| `HybridDecomposition` | branch on `\|extras\|` edges; sum over `2^\|extras\|` planar sub-problems | Tutte / Lovász-Plummer |
| `RationaliseWeights` | scale real weights by `10^p`, invert at end | — |
| `CrossingElimination` | replace each declared crossing with 6-vertex gadget | Cai-Gorenstein 2013 Fig. 6 |
| `HighDegreeVertexSplit` | build 2k-node triangle-cycle matchgate for symmetric sig | Cai-Gorenstein 2013 Fig. 10 |

`HybridDecomposition` and `auto_detect_extras` (greedy genus-reducing
edge picker) are the main paths the Orchestrator uses automatically.
`auto_detect_extras` has an honest scope: removing one edge from a
cellular rotation often produces a *non-cellular* embedding, which the
greedy treats as "no improvement available" — so for K₃,₃ and 4×4-torus
it returns `[]` and the caller must supply extras manually.

### 7.2 Compositions (`compose.py`)

Combine multiple in-family evaluations:

| Concrete composition | Combiner |
|---|---|
| `LinearCombination` | `sum(coeff_i · value_i)` |
| `Projection` | user-supplied callable (ratio, inclusion-exclusion, …) |
| `HolographicBasisPair` | basis change via `T^{⊗a}` (Valiant 2004) |
| `BranchSum` | `sum(amp_i · sub_eval(branch_i))` with complex amps |

`HolographicBasisPair` is the deepest one and the largest single class
in the package. Its public methods:

- `transform_signature(values)` — symmetric signatures, O((n+1)³) via
  polynomial-substitution.
- `transform_signature_general(values, arity)` — general signatures,
  O(a · 2ᵃ) via `a` sequential 2×2 tensor contractions (`numpy.tensordot`).
- `discover_basis(values)` — practical Cai-Lu SRP fragment with a
  four-step search in increasing-cost order:
  1. order-2 recurrence gate (Cai-Lu Thm 2.5 — no basis can rescue a
     signature that fails this);
  2. **v0.4–v0.5 closed-form shortcut**: derive T directly from the
     recurrence kernel's roots in O(1):
     - real distinct roots → `T = [[1, -r_2], [1, -r_1]]` (v0.4);
     - degenerate (c=0 or a=0, rank-1) → `T = [[1, 0], [1, -r]]` (v0.4);
     - complex conjugate roots `α ± iβ` → `T = [[1, -α], [0, β]]` (v0.5).
     Together these catch signatures whose roots lie anywhere on the
     real line OR on a generic complex conjugate pair, without any
     search;
  3. canonical-bases sweep (identity, Hadamard, swap, shears,
     rotation_4) for cases the closed-form doesn't reach (double
     roots, exotic complex conditions);
  4. parameterised grid + coordinate-descent polish as the final
     fallback for exotic cases.
- `discover_common_basis(signatures)` — multi-signature SRP (Cai-Lu
  2011 §4): same search space, total-distance scoring.

The matchgate-realisability check (`is_realisable` field on
`HolographicBasisResult`) is **populated for both symmetric and
general inputs** as of v0.4. The new `realisability_check` field on
the result names which check was applied:

- `"order_2_recurrence"` — symmetric path via Cai-Lu 2011 Theorem 2.5.
  This checks "matchgate-realisable on *some* basis" (the recurrence
  is basis-invariant).
- `"parity_only"` — general arity < 4 (Valiant 2008 Prop 6.1, 6.2 —
  no matchgate identities exist beyond parity below arity 4).
- `"matchgate_identity_arity_4"` — general arity 4 via the
  Grassmann-Plücker even-parity identity and the augmented-Pfaffian
  odd-parity identity. Sufficient check.
- `"plucker_arity_n"` — general arity ≥ 5 via the standard Plücker
  enumeration plus, for even arities, the augmented weight-1 identity.
  Complete for arity-5; reported at odd arities ≥ 7 where v0.5's
  even-arity augmented helper doesn't apply.
- `"plucker_arity_n_full"` — even arity ≥ 6 odd-parity with the
  full augmented Plücker enumeration on the (n+1)-vertex augmented
  Kasteleyn matrix. v0.5 D1 shipped the `|S|=2` configuration
  (`n × C(n-1, 4)` identities — 30 at arity 6, 280 at arity 8,
  1260 at arity 10); **v0.6 D3 added the `|S|=4` configuration**
  (`C(n, 3) × C(n-3, 4)` identities — 0 at arity 6, 280 at arity 8,
  4200 at arity 10). Combined count at arity 8: 560. At arity 10:
  5460. Proven-sufficient check, closing v0.4's "tight necessary"
  caveat. Higher-m configurations (m ∈ {5, 7, …}) remain a v0.7+
  follow-on. The identities live in `holant_tools.non_symmetric`
  (function `matchgate_identities_arity_n_odd_augmented`,
  promoted from a structural-computing prototype to the engine in
  the v0.6 D1 cleanup pass).
- `"deferred"` — the genuinely-zero-signature shortcut (trivially
  realisable; the check was skipped because the regular check would
  do meaningless arithmetic on near-zero numbers).

The **general path checks standard-basis realisability specifically**
— a stricter criterion than the symmetric path's "realisable on some
basis" check. A symmetric signature satisfying the order-2 recurrence
may still fail the general standard-basis MGI check; that signals it
needs a non-identity basis transformation to land in matchgate-standard
form (and the SRP-search side, `discover_basis`, finds that basis).

### 7.3 Decompositions (`decompose.py`)

Recursively split into sub-problems, base case in-family:

| Concrete decomposition | What it splits on |
|---|---|
| `ShannonExpansion` | branch on one binary variable; combine via sum |
| `TreewidthBoundedDP` | Bodlaender-style multi-bag DP on a user-supplied tree decomp |
| `PlanarSeparator` | divide-and-conquer along a vertex separator (user-supplied OR auto-discovered via Lipton-Tarjan 1979 — BFS-layer simple case in v0.4, tree-edge balanced-cut backup in v0.5, level-based + articulation-augmentation backup in v0.6 catching star + K_{2,n} adversarial corpus) |
| `RecursiveCircuitCut` | enumerate `2^\|cut\|` forced-in/forced-out edge assignments |

`DecompositionPlan` is the tree node. Each node is either a leaf (with
a `problem` for the leaf evaluator), an internal node (with `children`
and a `combine` callable), or a **precomputed-value** node (used by
`TreewidthBoundedDP`, which performs the full DP internally and returns
the answer directly with no leaf-evaluator dispatch needed).

---

## 8. The Orchestrator — full reference

`orchestrator.py` is the package's largest module (1180 lines) and the
single most important component to understand. This section is a
complete reference: every public type, the constructor and registry
mutators, the `evaluate()` method's signature and parameters, each
phase of the 7-phase pipeline, the `_classify_problem` auto-detection
table, the private helpers, the error contract, and a worked example.

If you're reading the architecture doc for the first time, skim §8.1–8.4
to get the shape, then come back to the rest as needed.

### 8.1 The class — constructor and registry mutators

```python
class Orchestrator:
    def __init__(self,
                 leaf_registry: Optional[Dict[Tuple[str, str], LeafEvaluator]] = None,
                 reductions:    Optional[List[Reduction]] = None):
        ...
```

The constructor takes two optional overrides:

- `leaf_registry` — a copy of `DEFAULT_LEAF_REGISTRY` is used by default.
  Pass your own dict to replace the entire registry, or pass nothing
  and mutate `self.leaf_registry` after construction.
- `reductions` — defaults to `[NormaliseGraphFormat()]`. The
  parametric reductions (`HybridDecomposition`, `RationaliseWeights`,
  `CrossingElimination`, `TreewidthBoundedDP`, `PlanarSeparator`,
  `RecursiveCircuitCut`) are intentionally NOT in the default list:
  they need parameters the orchestrator can't infer, so they fire only
  via hints (§8.4).

After construction, mutate the registries with:

```python
orch.register_leaf_evaluator(tier="T2", question="my_question",
                              evaluator=my_leaf_fn)
orch.register_reduction(MyReduction())
```

These are simple appenders — `register_leaf_evaluator` overwrites any
existing entry for `(tier, question)`; `register_reduction` appends to
the search list (Phase 6 iterates in registration order).

### 8.2 Public types

```python
LeafEvaluator = Callable[[Any, str], Any]
# (problem, question) -> answer. Pure functions; no state.

@dataclass
class WorkflowStep:
    phase:   str        # "normalise" | "classify" | "direct-dispatch" | …
    action:  str        # "NormaliseGraphFormat" | "leaf_evaluator(T2, matching_count)" | …
    outcome: str        # "ok" | "skipped" | "failed" | "honest-stop"
    detail:  str = ""   # free-form, often the exception message or the answer

@dataclass
class OrchestratorResult:
    answer:               Any
    classification:       Classification
    reductions_applied:   List[str]      # e.g. ["NormaliseGraphFormat",
                                          #       "HybridDecomposition(via hints)"]
    sub_evaluations:      int             # how many leaf calls fired
    leaf_evaluator_used:  str             # name of the leaf that produced the answer
    workflow_trace:       List[WorkflowStep]   # the complete audit trail

class NoKnownReduction(RuntimeError):
    classification: Classification       # framework's verdict at giveup
    attempted:      List[str]            # reductions tried (always includes "NormaliseGraphFormat")
```

`WorkflowStep` is the unit of the audit trail; `OrchestratorResult`
is what you get back on success; `NoKnownReduction` is what's raised
on failure. The `classification` field on the exception is the
single most useful piece of state when debugging a honest-stop —
inspect `e.classification.tier` and `e.classification.reasoning` to
see *why* the framework decided the problem was out-of-family.

### 8.3 `evaluate()` — signature and parameters

```python
def evaluate(self,
              problem: Any,
              question: str,
              *,
              hints:   Optional[Dict[str, Any]] = None,
              verbose: bool = False,
              log:     Optional[Callable[[str], None]] = None,
              ) -> OrchestratorResult:
```

| Param | Purpose |
|-------|---------|
| `problem` | A graph dict / constraint-set dict / signature dict / multi-signature dict / general-signature dict / raw edge list / raw adjacency dict. Phase 1 normalises edge lists and adjacency dicts. |
| `question` | The name of the question. Must match a `(tier, question)` key in `self.leaf_registry` for direct dispatch to succeed. The full v0.3 question set is enumerated in §8.6. |
| `hints` | Optional dict of parametric-reduction parameters. Recognised keys: `rationalise_precision`, `rationalise_matching_size`, `extra_edges`, `tree_decomposition`, `crossings`, `planar_separator`, `circuit_cut`. Unrecognised keys are silently ignored. |
| `verbose` | When `True`, stream each `WorkflowStep` to stdout (or `log`) as it happens. Useful for debugging an unexpected honest-stop or learning the framework by following an `evaluate()` call. Defaults to `False` — silent. |
| `log` | Custom logger; a callable taking one string. Defaults to `print`. Only consulted when `verbose=True`. |

Returns `OrchestratorResult` on success; raises `NoKnownReduction` on
failure (Phase 7).

### 8.4 The seven-phase pipeline — per-phase detail

The pipeline runs phases in order. Each phase either **returns** (with
a built `OrchestratorResult`) or **continues** to the next phase. Phase
7 is the only one that raises. Every phase emits one or more
`WorkflowStep` entries via the local `emit()` helper.

```
Phase 1     normalise              ─┐
Phase 1.5   rationalise             │  installs post_inverse closure
Phase 2     classify                │  always runs; gates everything below
Phase 2.5   predict                 │  informational only
Phase 3     direct-dispatch         │  fastest path; happiest case
Phase 4     hint-driven HybridDec.  ├─ hint-gated; first applicable wins
Phase 4.5   treewidth-dp            │
Phase 4.7   crossing-elimination    │
Phase 4.8   planar-separator        │
Phase 4.9   circuit-cut             │
Phase 5     auto-hybrid             │  greedy fallback for out-of-family
Phase 6     registered reductions   │  iterate self.reductions
Phase 7     honest-stop            ─┘  raise NoKnownReduction
```

#### Phase 1 — Normalise

Always tried. Applies `NormaliseGraphFormat` to the input: coerces edge
lists and adjacency dicts to the canonical
`{"vertices": [...], "edges": [...], "rotation": {...}}` form. If the
input is already in canonical form (or is a constraint-set / signature
dict), the reduction skips itself via `applies_to()` and the phase
emits `"skipped"`.

**Emits:** `("normalise", "NormaliseGraphFormat", "ok"|"skipped", …)`.
**Returns?** No — control always continues to Phase 1.5.

#### Phase 1.5 — Rationalise weights

Fires only when `hints["rationalise_precision"]` is supplied AND the
problem is a weighted graph dict with at least one float weight.
Builds a `RationaliseWeights(precision=p, matching_size=k)`, applies
it, and — critically — installs the reduction's `inverse` callable as
`post_inverse`. The Orchestrator threads `post_inverse` through every
later phase: whatever phase produces the final answer, that answer is
piped through `post_inverse` before being placed in the
`OrchestratorResult`.

`matching_size` defaults to `len(vertices) // 2` (the number of edges
in a perfect matching); override via
`hints["rationalise_matching_size"]`.

**Emits:** `("rationalise", "RationaliseWeights(...)", "ok"|"skipped", …)`.
**Returns?** No — control always continues to Phase 2.

#### Phase 2 — Classify

Calls `self._classify_problem(problem)` which auto-detects the problem
type and dispatches to the right classifier (§8.5). If classification
fails (problem doesn't match any known shape), raises
`NoKnownReduction` immediately with a synthesised T7 classification.

**Emits:** `("classify", classifier_name, "ok"|"failed", …)`.
**Returns?** No on success — continues. **Raises** `NoKnownReduction`
on classification failure (rare; means the input was a Python type the
orchestrator can't pattern-match).

#### Phase 2.5 — Predict

Fires only when `calibration.has_calibration_for(tier, question)` is
true. Emits a `WorkflowStep("predict", …)` recording the predicted
wall-clock cost and the size hint used. **Informational only** — does
not affect dispatch. Useful in `verbose=True` mode to see what the
framework expects each leaf to cost before it fires.

**Emits:** `("predict", "calibrated_predict(T?, question)", "ok",
"predicted_seconds=…, size=…")`.
**Returns?** No.

#### Phase 3 — Direct dispatch

The happy path. Looks up `self.leaf_registry[(cls.tier, question)]`.
If present AND `cls.in_family` is True, calls the leaf with
`(problem, question)`. Applies `post_inverse` to the answer if installed
by Phase 1.5. Builds and returns `OrchestratorResult`.

**Emits:** `("direct-dispatch", "leaf_evaluator(T?, question)",
"ok"|"skipped", …)`. The `"skipped"` reason is either "no leaf
evaluator registered" or "problem out-of-family"; the detail string
distinguishes them.

**Returns?** Yes on success.

#### Phase 4 — Hint-driven `HybridDecomposition`

Fires only when `hints["extra_edges"]` is supplied AND
`question == "matching_count"`. Builds
`HybridDecomposition(extra_edges)`, applies it, evaluates each
resulting sub-problem via the T2 leaf for `matching_count`, and sums
via the reduction's `inverse`. See `_try_hybrid_decomposition` in §8.6.

**Emits:** `("hint-driven", "HybridDecomposition(via hints)", "ok"|"failed", …)`.
**Returns?** Yes on success.

#### Phase 4.5 — TreewidthBoundedDP

Fires only when `hints["tree_decomposition"]` is supplied AND
`question == "matching_count"`. Builds
`TreewidthBoundedDP(tree_decomposition=td)`. The resulting plan is
"precomputed-value" (the DP runs inside `decompose()` and returns the
answer directly), so the leaf evaluator passed to `plan.evaluate()` is
a no-op `lambda _p: 0`.

**Emits:** `("treewidth-dp", …, "ok"|"failed", …)`. **Returns?** Yes.

#### Phase 4.7 — CrossingElimination

Fires only when `hints["crossings"]` is supplied AND `question` is
`"matching_count"` or `"weighted_matching_sum"`. Inserts the
Cai-Gorenstein 6-vertex gadget at each declared crossing, dispatches
the resulting planar graph to the T2 leaf evaluator. **Returns the
SIGNED matchgate signature, not unsigned PerfMatch** in general — for
unit-weight graphs the two may coincide, for weighted graphs they
don't. The docstring of `CrossingElimination` is explicit about this
semantic.

**Emits:** `("crossing-elimination", …, "ok"|"failed", …)`. **Returns?** Yes.

#### Phase 4.8 — PlanarSeparator

Fires only when `hints["planar_separator"]` is supplied AND
`question` is `"matching_count"` or `"weighted_matching_sum"`. Two
hint forms are recognised:

- **Dict form** `{"separator": ..., "side_a": ..., "side_b": ...}` —
  the v0.3 explicit user-supplied path.
- **String `"auto"`** — v0.4 Lipton-Tarjan auto-discovery via
  `PlanarSeparator(auto=True)`. The BFS-layer simple case is tried;
  if it succeeds, the discovered `(S, A, B)` is used and the
  separator size goes into `reductions_applied` as
  `"PlanarSeparator(auto, |S|=k)"`. If the simple case fails
  (disconnected graph, fat middle level, non-planar input),
  `decompose()` raises `ValueError` and the orchestrator emits a
  `"failed"` step then continues to the next phase.

Once the partition is established (either way), the orchestrator
calls `plan.evaluate(...)` with the T2 leaf as the leaf evaluator.
The plan's combine sums over separator-vertex match patterns
weighted by per-pair edge weights.

**Emits:** `("planar-separator", …, "ok"|"failed", …)`. **Returns?** Yes.

#### Phase 4.9 — RecursiveCircuitCut

Fires only when `hints["circuit_cut"]` is supplied (iterable of edges)
AND `question` is `"matching_count"` or `"weighted_matching_sum"`.
Builds a `RecursiveCircuitCut`, calls `decompose()` to enumerate
`2^|cut|` forced-in / forced-out sub-graphs (with shared-endpoint
pruning), then `plan.evaluate(...)` sums them.

**Emits:** `("circuit-cut", …, "ok"|"failed", …)`. **Returns?** Yes.

#### Phase 5 — Auto-Hybrid

Fires when `question == "matching_count"`, the problem is
out-of-family (`not cls.in_family`), and the problem has a `rotation`
field. Builds `HybridDecomposition(auto=True)`, which internally calls
`auto_detect_extras` on the rotation system to discover a planarising
edge set greedily. **Honest scope:** `auto_detect_extras` returns `[]`
on graphs whose single-edge removals produce non-cellular embeddings
(see the "Honest scope" block in `auto_detect_extras`' docstring in
`transform.py`); the Orchestrator emits a `"failed"` step with
that reason and continues.

**Emits:** `("auto-hybrid", "HybridDecomposition(auto=True)",
"ok"|"failed", …)`. **Returns?** Yes on success.

#### Phase 6 — Registered reductions

Iterates `self.reductions` in registration order. For each:

1. Skip if it's the `NormaliseGraphFormat` already applied in Phase 1.
2. Skip if `applies_to(problem)` is False (emit `"skipped"`).
3. Otherwise call `apply()`, evaluate sub-problems via
   `_evaluate_sub_problems`, return the result.
4. If `apply()` raises `ReductionNotApplicable`, `NoKnownReduction`,
   or `NotImplementedError`, emit `"failed"` and continue to the
   next reduction.

The default `self.reductions` is `[NormaliseGraphFormat()]`, so this
phase does nothing useful out of the box; it exists for user-registered
custom reductions.

**Emits:** one `("reduction", reduction.name, …, …)` step per
reduction tried. **Returns?** Yes on first applicable success.

#### Phase 7 — Honest stop

If no phase has returned by this point, emit a final `"honest-stop"`
step and raise `NoKnownReduction(classification, reductions_applied)`.
The exception carries the full classification and the list of
reductions attempted so the caller can inspect what was tried.

**Emits:** `("honest-stop", "NoKnownReduction", "honest-stop",
"tier=…, attempted=…")`. **Raises:** `NoKnownReduction`.

### 8.5 The `_classify_problem` auto-detection table

`_classify_problem` (in `orchestrator.py`) auto-detects the problem
type from the dict shape after Phase 1's normalisation. The dispatch
table:

| Detection rule | Tier route | Classifier called |
|---|---|---|
| `problem["kind"] == "graph"` | T2 or T4 (from genus) | `classify_graph` |
| `problem["kind"] == "constraint_set"` | T0 / T1 / T7 | `classify_constraint_set` |
| `problem["kind"] == "signature"` | T2 or T3 (from arity) | `classify_signature` |
| `"rotation" in problem` (no explicit `kind`) | T2 / T4 | `classify_graph` |
| `"A" in problem` (no explicit `kind`) | T0 / T1 / T7 | `classify_constraint_set` |
| `"values" + "arity" + "basis_matrix" in problem` AND `len(values) == 2^arity` | **T3 with `general=True` meter** | synthesised inline (not a classify_* call) |
| `"values" in problem` (other) | T2 or T3 | `classify_signature` |
| `"signatures" in problem` (list) | **T3 with `n_signatures` meter** | synthesised inline (for SRP common-basis search) |
| anything else | — | returns `(None, "")` → Phase 2 raises |

The two **synthesised classifications** are for general (non-symmetric)
signatures and multi-signature SRP problems — these don't have a
`classify_*` function because they don't fit the symmetric path; the
orchestrator builds the `Classification` directly with `in_family=True`
and the appropriate meters so direct-dispatch can pick up the right
leaf evaluator (`_holographic_transform_general_leaf` or
`_discover_common_basis_leaf`).

**Adding a new problem type** means adding a branch here AND wiring
the relevant `(tier, question)` leaf evaluators into
`DEFAULT_LEAF_REGISTRY`. The "IMPORTANT: keeping the Orchestrator up
to date" comment block at the top of `orchestrator.py` is explicit
about this lock-step requirement.

### 8.6 The leaf-evaluator registry — full enumeration

`DEFAULT_LEAF_REGISTRY` (defined near the top of `orchestrator.py`,
just above the `Orchestrator` class) is the canonical map.
v0.3 ships 28 entries:

| Tier | Question | Leaf evaluator |
|------|----------|----------------|
| T0 | `count_solutions` | `_count_solutions_leaf` |
| T0 | `find_witness` | `_find_witness_constraint_leaf` |
| T0 | `list_solutions` | `_list_solutions_leaf` |
| T1 | `count_solutions` | `_count_solutions_leaf` |
| T1 | `find_witness` | `_find_witness_constraint_leaf` |
| T1 | `list_solutions` | `_list_solutions_leaf` |
| T2 | `matching_count` | `_matching_count_leaf` |
| T2 | `weighted_matching_sum` | `_weighted_matching_sum_leaf` |
| T2 | `witness` | `_witness_leaf` |
| T2 | `single_points_of_failure` | `_spofs_leaf` |
| T2 | `tail_probability` | `_tail_probability_leaf` |
| T2 | `matchgate_rank` | `_matchgate_rank_leaf` |
| T2 | `is_matchgate_realisable` | `_is_matchgate_realisable_leaf` |
| T2 | `classify_function` | `_classify_function_leaf` |
| T2 | `matchgate_realisation` | `_matchgate_realisation_leaf` |
| T2 | `discover_basis` | `_discover_basis_leaf` |
| T3 | `matchgate_rank` | `_matchgate_rank_leaf` |
| T3 | `is_matchgate_realisable` | `_is_matchgate_realisable_leaf` |
| T3 | `classify_function` | `_classify_function_leaf` |
| T3 | `matchgate_realisation` | `_matchgate_realisation_leaf` |
| T3 | `discover_basis` | `_discover_basis_leaf` |
| T3 | `discover_common_basis` | `_discover_common_basis_leaf` |
| T3 | `holographic_transform_general` | `_holographic_transform_general_leaf` |
| T4 | `matching_count` | `_matching_count_leaf` |
| T4 | `weighted_matching_sum` | `_weighted_matching_sum_leaf` |
| T4 | `witness` | `_witness_leaf` |
| T4 | `single_points_of_failure` | `_spofs_leaf` |
| T4 | `tail_probability` | `_tail_probability_leaf` |

Each leaf is `(problem: Any, question: str) -> Any`. The `question`
argument is rarely used inside the leaf — most leafs implement exactly
one question — but it's there so a single leaf function can serve
multiple `(tier, question)` keys when the work is identical (e.g.,
`_matching_count_leaf` is registered for both T2 and T4).

Internal implementation notes:

- `_matching_count_leaf` / `_weighted_matching_sum_leaf` / `_spofs_leaf`
  delegate to brute-force primitives in `verifier.py`. Production
  scaling for large `|V|` is a future deliverable (the planar-Pfaffian
  via `holant_tools.exact_planar_pfaffian` is already used by
  `StructuralComputer.count_matchings` but not yet by the orchestrator
  leaf — a known small duplication).
- `_witness_leaf` uses `holant_tools.min_weight_perfect_matching`.
- `_tail_probability_leaf` is `O(2^|E|)` enumeration capped at `|E| <= 24`.
- `_count_solutions_leaf` for T0 uses `_gf2_rank` (poly-time) from
  `easy.py`; T1 falls back to `O(2^n)` brute force capped at `n <= 24`.
- The signature leafs (`_matchgate_rank_leaf`, `_classify_function_leaf`)
  consult the basis-aware-rank machinery in `holant-tools`.

### 8.7 Private helpers

#### `_classify_problem(problem) -> (Classification | None, classifier_name: str)`

The auto-detection dispatcher described in §8.5. Returns
`(None, "")` only when no rule matches — Phase 2 treats that as fatal.

#### `_try_hybrid_decomposition(problem, extra_edges, *, origin)`

Builds a `HybridDecomposition`, validates applicability, applies it,
and evaluates each sub-problem via the T2 `matching_count` leaf.
Returns `{"answer": ..., "sub_evaluations": ...,
"leaf_evaluator_used": ...}`. Used by Phase 4 (hint-driven). Raises
`ReductionNotApplicable` if the extras don't validate.

#### `_evaluate_sub_problems(sub_problems, rresult, question)`

Walks a list of `sub_problems` (typically planar residuals from a
hybrid decomposition), evaluates each via the T2 leaf for `question`,
then calls `rresult.inverse(sub_answers)` to combine. Used by Phase 4
(via `_try_hybrid_decomposition`), Phase 5 (auto-Hybrid), and Phase 6
(registered reductions). Raises `NoKnownReduction` if no T2 leaf is
registered for `question`.

### 8.8 The `emit()` helper and the workflow_trace contract

```python
def emit(phase: str, action: str, outcome: str, detail: str = "") -> None:
    step = WorkflowStep(phase, action, outcome, detail)
    workflow_trace.append(step)
    if verbose:
        log_fn(f"[{phase}] {action} -> {outcome}")
        if detail:
            log_fn(f"    reason: {detail}")
```

`emit` is a **closure defined inside `evaluate()`**
so it has access to the local `workflow_trace`, `verbose`, and
`log_fn` variables. The contract:

- Every phase that runs **must** emit at least one step (success,
  skipped, or failed). Phases never silently do nothing.
- Phases that loop (Phase 6 iterates `self.reductions`) emit one step
  per inner item.
- The `detail` field is free-form — but conventionally it carries
  either (a) the answer summary on success (`"answer=…"`), (b) the
  exception message on failure, or (c) a short explanation on skip.

The "IMPORTANT: keeping the Orchestrator up to date" comment block at
the top of `orchestrator.py` warns: **do not append to
`workflow_trace` directly**; always go through `emit()`, or
`verbose=True` mode will miss the step.

### 8.9 Verbose mode — streaming the workflow as it runs

`verbose=True` flips the Orchestrator from "build a trace silently
and hand it back at the end" to "stream every step to the caller as
it happens." The trace still gets built either way (see
`OrchestratorResult.workflow_trace`); verbose mode is purely additive
— it just *also* emits each step to a callable as it's appended to the
trace.

#### 8.9.1 When to use it

- **Debugging an unexpected `NoKnownReduction`.** When `evaluate()`
  raises, the exception carries the classification and the
  `attempted` list, but verbose mode shows you the *sequence* of
  attempts in order, including which hint was malformed or which
  reduction's `applies_to()` returned False. This is usually the
  fastest path to the root cause.
- **Learning the framework.** Watching the phase sequence on a
  half-dozen example problems builds intuition for which path each
  kind of problem takes faster than reading the source.
- **Observability in production pipelines.** A long-running pipeline
  (1000+ stages, MCMC trajectory, batch reliability audit) can pipe
  verbose output to a structured log sink to support after-the-fact
  analysis without the caller having to inspect every result's
  `workflow_trace` field.
- **Auditing for regulator-grade reports.** The streamed verbose
  output is a human-readable transcript of the framework's
  decision-making — captured to a file, it becomes part of the
  provenance package alongside the answer itself.

When to **NOT** use it:

- Inside a tight test loop where you only care about the answer —
  the trace overhead is negligible but the printed output is noise.
- When you've already captured the trace via `result.workflow_trace`
  and want to inspect it programmatically — that path doesn't need
  verbose at all.

#### 8.9.2 Output format

`verbose=True` first emits a single header line summarising the
call, then two lines per `WorkflowStep`:

```
Orchestrator.evaluate(question='matching_count', hints=['extra_edges'])
[normalise] NormaliseGraphFormat -> ok
    reason: vertices=6, edges=9
[classify] classify_graph -> ok
    reason: tier=T4, in_family=True, reasoning='genus-1 cellular embedding on 6 vertices; …'
[direct-dispatch] leaf_evaluator(T4, matching_count) -> ok
    reason: answer=6, evaluator=_matching_count_leaf
```

The format is:

```
[<phase>] <action> -> <outcome>
    reason: <detail>
```

Two lines, the second indented with four spaces. The `reason:` line
is omitted when `detail` is empty (rare, but possible for the most
trivial skipped phases).

The header line emits the question and the *names* of the hint keys
the user supplied (not their values — hint values are often large data
structures like full tree decompositions or vertex partitions, and
printing them would dwarf the per-step output). To inspect hint
values, pass a custom `log` callable that records the full
`hints` dict separately before invoking `evaluate()`.

#### 8.9.3 The `log` callable contract

```python
log: Optional[Callable[[str], None]] = None
```

The contract is intentionally minimal: **one string per call, no
trailing newline, no return value**. The Orchestrator emits *each line
separately* (header, phase line, reason line, phase line, reason
line, …), so a single `WorkflowStep` produces 1–2 calls to `log`.

When `log` is `None`, the Orchestrator uses `print` directly. The
default is exactly equivalent to `log=print`.

#### 8.9.4 Common redirection patterns

**Redirect to stderr:**
```python
import sys
orch.evaluate(problem, "matching_count", verbose=True,
               log=lambda msg: print(msg, file=sys.stderr))
```

**Capture to a list** (e.g., for testing or buffering before display):
```python
captured: list[str] = []
orch.evaluate(problem, "matching_count", verbose=True,
               log=captured.append)
# `captured` is now a list of strings, one per line.
```

**Write to a file**:
```python
with open("trace.log", "w") as f:
    orch.evaluate(problem, "matching_count", verbose=True,
                   log=lambda msg: f.write(msg + "\n"))
```

**Route to a structured logger** (e.g., the standard `logging`
module):
```python
import logging
logger = logging.getLogger("structural_computing.orchestrator")
orch.evaluate(problem, "matching_count", verbose=True,
               log=logger.info)
```

**Tag with a request ID** for distributed-tracing-style correlation:
```python
request_id = "req-1234"
def tagged_log(msg):
    print(f"[{request_id}] {msg}")
orch.evaluate(problem, "matching_count", verbose=True,
               log=tagged_log)
```

**Custom formatter** (e.g., to convert to JSON-line output for
downstream tooling):
```python
import json, re
phase_pattern = re.compile(r"\[([\w-]+)\] (.+?) -> (\w+)")
def jsonify(msg):
    m = phase_pattern.match(msg)
    if m:
        print(json.dumps({"phase": m.group(1), "action": m.group(2),
                           "outcome": m.group(3)}))
    else:
        print(json.dumps({"text": msg}))
orch.evaluate(problem, "matching_count", verbose=True, log=jsonify)
```

For production-grade structured logging, prefer to skip `verbose=True`
entirely and walk `result.workflow_trace` after the fact —
`WorkflowStep` is already a structured dataclass and serialises
cleanly. Verbose mode is for human-readable streaming; the trace is
for programmatic inspection.

#### 8.9.5 Performance impact

Verbose mode adds one `if verbose:` check per `emit()` call and (when
True) one or two `log` invocations per step. A typical evaluation
emits 3–8 steps, so the overhead is **microseconds** in absolute
terms — negligible compared to the leaf evaluator's actual work.

The one practical caveat: `print` is line-buffered to a TTY and
block-buffered to a pipe by default; if you're piping a very large
batch through verbose mode, force-flush stdout (`print(..., flush=True)`)
in your custom `log` callable to avoid buffering surprises.

#### 8.9.6 Relationship to the workflow_trace

Verbose mode and `workflow_trace` are **two views of the same
underlying stream of events**:

- The trace is the **persistent typed record** — `list[WorkflowStep]`,
  in-memory, queryable. It's always built, regardless of `verbose`.
- Verbose output is the **transient human-readable stream** — strings,
  emitted in real time, gone once the function returns unless the
  `log` callable captures them.

They never disagree (both come from the same `emit()` helper), so use
whichever fits your use case:

| You want | Use |
|---|---|
| Inspect what happened after the fact | `result.workflow_trace` |
| Watch decisions in real time as evaluation runs | `verbose=True` |
| Both | `verbose=True` AND inspect `result.workflow_trace` afterwards |
| Capture decisions for archival / audit | `verbose=True` with a file-backed `log` |
| Build a UI that shows decisions live | `verbose=True` with a `log` that pushes to your UI's event queue |
| Add programmatic assertions in tests | `result.workflow_trace` (with list comprehensions / `next()` filters) |

### 8.10 Error contract

What the Orchestrator catches and what it lets propagate:

| Exception | Source | Handling |
|---|---|---|
| `ReductionNotApplicable` | A reduction's `apply()` | Caught in Phases 4, 4.7, 4.8, 6. Emits `"failed"` and continues to the next phase. |
| `NoKnownReduction` (nested) | `_evaluate_sub_problems` when no T2 leaf is registered | Caught in Phases 4, 4.5, 4.7, 4.8, 4.9, 6. Emits `"failed"` and continues. |
| `NotImplementedError` | A reduction's `apply()` (sketches) | Caught in Phase 6 only. Emits `"failed"`. |
| `ValueError` | A decomposition with invalid input (e.g., separator with edges crossing it) | Caught in Phases 4.5, 4.7, 4.8, 4.9. Emits `"failed"`. |
| `KeyError` | Malformed hint dict | Caught in Phase 4.8 only (the only phase that pattern-matches hint dict keys). Emits `"failed"`. |
| Any other exception from a leaf evaluator | A leaf's body | **Not caught.** Propagates to the user. Leafs are expected to validate their input and raise `ValueError` with a clear message; any other exception is a bug. |
| `NoKnownReduction` (top-level) | Phase 7 | **Raised** to the user. The exception carries `classification` and `attempted`. |

The asymmetric handling — caught for known reduction/decomposition
errors, uncaught for leaf-internal bugs — is intentional: a leaf
evaluator is supposed to be a clean polynomial-time algorithm on an
in-family problem, so an unexpected exception inside one is a real bug
the user should see, not a fallback opportunity.

### 8.11 Worked example — K₃,₃ with hints

K₃,₃ (the smallest non-planar bipartite graph) is genus 1, so it
classifies as T4. The default registry has a T4 `matching_count` leaf
that brute-forces, so direct dispatch succeeds — but suppose we want
the planar-decomposition path instead.

```python
from structural_computing import Orchestrator

orch = Orchestrator()

K33 = {
    "rotation": {0: [3, 4, 5], 1: [3, 4, 5], 2: [3, 4, 5],
                 3: [0, 1, 2], 4: [0, 1, 2], 5: [0, 1, 2]},
    "vertices": [0, 1, 2, 3, 4, 5],
    "edges": [(0, 3), (0, 4), (0, 5),
              (1, 3), (1, 4), (1, 5),
              (2, 3), (2, 4), (2, 5)],
}

result = orch.evaluate(K33, question="matching_count",
                        hints={"extra_edges": [(0, 3)]},
                        verbose=True)
```

Verbose output (annotated):

```
Orchestrator.evaluate(question='matching_count', hints=['extra_edges'])
[normalise] NormaliseGraphFormat -> skipped         # already canonical
    reason: input already in canonical form (or unsupported type)
[classify] classify_graph -> ok                      # genus 1 -> T4
    reason: tier=T4, in_family=True, reasoning='genus-1 cellular embedding…'
[direct-dispatch] leaf_evaluator(T4, matching_count) -> ok
    reason: answer=6, evaluator=_matching_count_leaf
```

Direct dispatch fired (Phase 3) and returned the answer (6 = 3!).
**Phase 4 was never reached** because Phase 3 succeeded. To force the
hint path you'd remove the T4 leaf from the registry first — a pattern
exercised in `tests/test_orchestrator.py::test_hybrid_decomposition_via_hints_when_t4_not_registered`.

`result.workflow_trace` carries all three steps for after-the-fact
inspection. `result.reductions_applied` is `[]` (Phase 3 doesn't
record `NormaliseGraphFormat` because that one was skipped).
`result.leaf_evaluator_used` is `"_matching_count_leaf"`.
`result.sub_evaluations` is `1`.

### 8.12 Extension recipes (cross-link to §13)

The Orchestrator is the layer you touch when adding new capability.
The patterns:

| To add | What to touch | Where |
|---|---|---|
| A new leaf evaluator | Write `_my_leaf(problem, question)`; add to `DEFAULT_LEAF_REGISTRY` | `orchestrator.py` |
| A new problem-type recognition | Add a branch to `_classify_problem` | `orchestrator.py` |
| A new hint-driven phase | Add a `if "my_hint" in hints` block in `evaluate()`, between the existing Phase 4.5 and Phase 5 blocks | `orchestrator.py` |
| A new auto-applicable reduction | Append it to the constructor's default `reductions` list (be careful: it must be parameterless or use sensible defaults) | `orchestrator.py` |
| A new question without a new tier | Just a leaf evaluator entry — no other change | `DEFAULT_LEAF_REGISTRY` |

The detailed recipes are in §13 (Extension cookbook).

### 8.13 The Orchestrator as a workflow engine

Everything above describes the Orchestrator as a *function* — input
goes in, an `OrchestratorResult` comes out. That's accurate but
incomplete. The Orchestrator is also a **workflow engine** whose
primary artefact is the `workflow_trace` — a typed, structured,
inspectable record of every decision made during evaluation. The
`answer` field on the result is just *one* of the trace's outputs;
the trace itself is what you reach for to audit, debug, replay, or
analyse what happened.

This sub-section explains the workflow type system: what
`WorkflowStep` records carry, what the canonical trace shapes look
like per evaluation kind, how to inspect a trace post-hoc, and the
contract every capability must respect to participate in the trace
correctly.

#### 8.13.1 The `WorkflowStep` type — a per-phase audit record

```python
@dataclass
class WorkflowStep:
    phase:   str        # which orchestrator phase this step belongs to
    action:  str        # short description of what the phase did
    outcome: str        # "ok" | "skipped" | "failed" | "honest-stop"
    detail:  str = ""   # free-form: answer summary, exception, or reason
```

The four fields form a closed typed enumeration over evaluation
events. Read together they encode: *"in phase P, the orchestrator
attempted action A; the result was O; with extra context D."*

**`phase`** is a string drawn from a fixed vocabulary that mirrors the
seven-phase pipeline:

| Phase string | When emitted |
|---|---|
| `"normalise"` | Phase 1 |
| `"rationalise"` | Phase 1.5 (when the hint is present) |
| `"classify"` | Phase 2 |
| `"predict"` | Phase 2.5 (when calibration is loaded) |
| `"direct-dispatch"` | Phase 3 |
| `"hint-driven"` | Phase 4 (HybridDecomposition via `extra_edges`) |
| `"treewidth-dp"` | Phase 4.5 |
| `"crossing-elimination"` | Phase 4.7 |
| `"planar-separator"` | Phase 4.8 |
| `"circuit-cut"` | Phase 4.9 |
| `"auto-hybrid"` | Phase 5 |
| `"reduction"` | Phase 6 (one step per reduction tried) |
| `"honest-stop"` | Phase 7 |

**`outcome`** is a fixed four-way enumeration: `"ok"` (phase
succeeded), `"skipped"` (phase didn't apply), `"failed"` (phase tried
and raised — orchestrator continued), `"honest-stop"` (Phase 7 only).

**`action`** carries the specific operation — for `"normalise"` it's
always `"NormaliseGraphFormat"`; for `"reduction"` it's the reduction
class's `name` attribute; for `"direct-dispatch"` it's
`f"leaf_evaluator({tier}, {question})"`; etc.

**`detail`** is the free-form payload. Conventionally:

- On `"ok"`: the answer summary, e.g.
  `"answer=3, evaluator=_matching_count_leaf"`.
- On `"skipped"`: the reason, e.g.
  `"no leaf evaluator registered for (T4, my_question)"`.
- On `"failed"`: the exception message via `str(e)`.
- On `"honest-stop"`: a recap, e.g.
  `"tier=T7, attempted=['NormaliseGraphFormat']"`.

#### 8.13.2 Canonical trace shapes — recognising an evaluation kind

The trace's shape is diagnostic — looking at the phase sequence tells
you what *kind* of evaluation happened without inspecting the answer.
The canonical shapes:

**Shape A — in-family direct dispatch** (the fastest path):
```
normalise   ok | skipped
classify    ok
direct-dispatch  ok
```
3 steps. The most common shape for happy-path uses of the framework.

**Shape B — in-family with calibration loaded**:
```
normalise   …
classify    ok
predict     ok          ← only when calibration is loaded
direct-dispatch  ok
```
4 steps. Same as Shape A plus the informational `predict` step.

**Shape C — hint-driven reduction**:
```
normalise   …
classify    ok          (typically T4 or out-of-family)
direct-dispatch  skipped (problem out-of-family, or leaf missing on purpose)
hint-driven ok          (or treewidth-dp / crossing-elimination / planar-separator / circuit-cut)
```
4 steps. The user supplied a hint that selected a specific reduction.

**Shape D — auto-hybrid fallback**:
```
normalise   …
classify    ok          (out-of-family, has rotation)
direct-dispatch  skipped
auto-hybrid ok
```
4 steps. The orchestrator discovered the reduction parameters itself.

**Shape E — multiple failed phases then success**:
```
normalise   …
classify    ok
direct-dispatch  skipped (no leaf)
hint-driven failed       (hint malformed)
treewidth-dp failed      (DP raised)
crossing-elimination failed
planar-separator failed
circuit-cut failed
reduction MyReduction ok ← finally found one
```
N steps. Diagnostic for "the orchestrator tried hard before succeeding";
useful in `verbose=True` mode to spot which hint was malformed.

**Shape F — honest stop**:
```
normalise   …
classify    ok          (out-of-family OR unsupported question)
direct-dispatch  skipped
[hint-driven phases all skipped or failed]
auto-hybrid skipped
reduction Normalise skipped
honest-stop honest-stop
```
N+1 steps ending with the `honest-stop` row. The exception that
gets raised carries the same information, but the trace lets you see
*everything tried* in order.

A trace post-mortem can classify the shape with a one-liner:

```python
phases = [s.phase for s in result.workflow_trace]
if phases[-1] == "honest-stop":
    shape = "F (honest stop)"
elif "auto-hybrid" in phases and phases[-1] == "auto-hybrid":
    shape = "D (auto-hybrid fallback)"
elif phases[-1] == "direct-dispatch":
    shape = "A or B (direct dispatch)"
else:
    shape = "C, E, or custom"
```

#### 8.13.3 Inspecting a trace post-hoc

The `workflow_trace` is a plain `list[WorkflowStep]`, so standard
list comprehensions and filters work:

```python
result = orch.evaluate(problem, "matching_count")

# Did any phase fail?
failures = [s for s in result.workflow_trace if s.outcome == "failed"]

# What's the slowest phase to emit (the one that did the most work)?
# Usually `direct-dispatch` for in-family work, `reduction` for transforms.
non_trivial = [s for s in result.workflow_trace
               if s.outcome == "ok" and s.phase != "normalise"]
last_active = non_trivial[-1] if non_trivial else None

# How many reductions were attempted in Phase 6?
phase6 = [s for s in result.workflow_trace if s.phase == "reduction"]

# Get the classification reasoning string out of the trace.
classify_step = next(s for s in result.workflow_trace if s.phase == "classify")
# classify_step.detail starts with "tier=T?, in_family=...,
# reasoning='...'", parse if needed.
```

In tests, asserting on trace contents is the standard way to verify
the orchestrator chose the path you intended:

```python
def test_my_hint_fires():
    result = orch.evaluate(problem, "matching_count",
                            hints={"my_hint": value})
    phases = [s.phase for s in result.workflow_trace]
    assert "my-phase-name" in phases
    my_step = next(s for s in result.workflow_trace
                    if s.phase == "my-phase-name")
    assert my_step.outcome == "ok"
```

`tests/test_orchestrator.py` uses this pattern in 18 of its 26
scenarios — the trace is treated as a first-class testable artefact,
not an implementation detail.

#### 8.13.4 The two trace systems — `workflow_trace` vs `RichTrace`

The package has **two** trace systems and they serve different
purposes — knowing which to reach for matters:

| | `workflow_trace` (Orchestrator) | `RichTrace` (pipeline_router) |
|---|---|---|
| **Unit** | `WorkflowStep` (phase + action + outcome + detail) | `StageRecord` (name + kind + route + output_summary) |
| **Granularity** | one step per orchestrator phase that ran | one record per pipeline `Stage` executed |
| **Where it lives** | `OrchestratorResult.workflow_trace` | The `Trace` argument threaded through `run_pipeline(stages, trace=…)` |
| **Tracks** | decision-making (which phase fired, what was tried, what was skipped) | runtime work (per-stage routing decisions, costs, member histograms) |
| **Aggregation** | flat list; user filters as needed | `RichTrace` adds `cost_by_member()`, `regime_changes_detailed()`, `summary()`, etc. |
| **When to use** | debugging an `evaluate()` call, asserting in tests, building a UI that shows what the framework did | long-running pipelines, MCMC trajectories, cost analytics across many sub-problems |

In short: **`workflow_trace` is the *decision* trace** (what the
framework considered) and **`RichTrace` is the *execution* trace**
(what cost what). The two never see each other directly. An advanced
user wiring the Orchestrator into a `Stage`'s `runner_fn` ends up with
both — a per-stage routing record in the outer pipeline `RichTrace`,
and (if the runner inspects the `OrchestratorResult`) a per-stage
inner `workflow_trace` per stage.

#### 8.13.5 The phase contract — what every capability must respect

For a new capability to participate correctly in the workflow
system, it must:

1. **Emit at least one `WorkflowStep`** via the `emit()` helper. Phases
   that loop (Phase 6 iterates `self.reductions`) emit one step per
   inner item. Silent phases are bugs.
2. **Use a phase name from the fixed vocabulary** (§8.13.1) if the
   capability slots into an existing phase. New capabilities that need
   a new phase name should add it to that vocabulary and document it
   here AND in the `evaluate()` docstring.
3. **Pick an `outcome` from the four-way enumeration**. Avoid inventing
   new outcome strings — tools that filter the trace (analytics, UIs,
   test assertions) rely on the enumeration being closed.
4. **Encode the key info in `detail`** following the conventions in
   §8.13.1 (answer summary on `ok`, exception text on `failed`, etc.).
5. **Append to `reductions_applied`** if the capability is a reduction
   / composition / decomposition that actually fired (not just
   attempted). This list goes into the result and is what callers
   inspect to know *which* transformations were applied.

The closed-vocabulary phase set and four-way outcome enumeration are
deliberate: they make the trace **machine-parseable**. Downstream
tooling (the bench repo's `orchestrator_analytics.py`, future UIs)
can pattern-match on these strings without fragile substring matching.

#### 8.13.6 Replay, audit, and observability

The workflow trace is designed for three downstream use cases:

**Replay** — a saved `workflow_trace` plus the original `problem` and
`question` is enough to *understand* (though not exactly re-execute)
an old evaluation. The trace records every decision; the leaf
evaluators are deterministic; so given the same inputs and the same
registries, the same trace results. If you want bit-exact replay,
pickle the result and compare.

**Audit** — for regulator-facing reliability reports, the trace is the
provenance chain. "Configuration B is 90.2% more reliable" plus a
trace showing
`classify→T2 → direct-dispatch→_tail_probability_leaf→ok` is a
defensible chain of custody: exact computation, no sampling, no
approximation, the framework's verdict and the algorithm that produced
it both named explicitly.

**Observability** — long-running pipelines (1000+ stages, MCMC
trajectories) can stream traces to a log sink via `verbose=True` and
a custom `log` callable. The bench repo's
`orchestrator_analytics.py` consumes these to produce per-phase
profiling — *which phase spent how long, on which size of problem*.
This is how calibration data eventually gets generated.

---

#### Summary: think of the Orchestrator's output as a typed event log

The `answer` field is the *headline* of an evaluation. The
`workflow_trace` is the *transcript*. Treating the transcript as a
first-class typed object — with a closed phase vocabulary, a closed
outcome enumeration, and a stable detail-string convention — is what
makes the Orchestrator a workflow engine rather than just a function
with a return value. Every capability added to the framework
participates in the transcript or it doesn't really participate at
all.

---

## 9. The calibration loop (optional)

`calibration.py` is opt-in. Without it, `route()` returns
`cost = log2(ops)` with `cost_unit = "log2_ops"`.

With it loaded:

```python
from structural_computing import apply_calibration
from my_calibration_data import CALIBRATED_COSTS
apply_calibration(CALIBRATED_COSTS)
```

`route()` switches to `cost = log2(predicted_seconds)` with
`cost_unit = "log2_seconds"` and `cost_source = "calibrated"` in the
meters. The Orchestrator also emits a `[predict]` workflow step
before direct-dispatch (inside `Orchestrator.evaluate`) recording
`predicted_seconds` and the size hint used.

The calibration data is produced by the sibling repo
`structural-computing-bench` (see §11). Models supported:
`power_law` (`time = a · n^b`) and `exponential` (`time = a · exp(b·n)`).
The registry is module-level state in `calibration.py:_REGISTRY`;
`clear_calibration()` resets it.

---

## 10. The framework primitives (Layer 1)

These exist for users who want to compose their own pipelines without
going through the Orchestrator at all.

### `Stage`, `Route`, `run_pipeline` (`pipeline_router.py`)

```python
Stage(name, kind, data, route_fn, runner_fn)
  route_fn(data, prev) -> Route(member, cost, meters, tier)
  runner_fn(data, prev, route) -> output  # threaded as `prev` to next stage

final, trace = run_pipeline(stages, seed=...)
# or, streaming:
for stage, route, output in run_pipeline_streaming(stages, seed=...):
    ...
```

The driver is intentionally **generator-friendly**: a 1000-stage
pipeline can be a Python generator and is never materialised in memory.

### `RichTrace` (`trace.py`)

Aggregator on top of the base `Trace`. Adds:

- `cost_by_member()`, `cost_by_tier()` — sum of per-stage log-costs.
- `ops_by_member()`, `ops_by_tier()` — `log2(sum 2^cost)` (the actual
  total-ops log, not the sum of logs).
- `regime_changes_detailed()` — `RegimeChange(index, prev_member,
  new_member, delta_cost)` records.
- `window(start, end)` — sub-trace for a slice of stages.
- `summary()` — multi-line tabular report.

### `ReplayCache` (`replay.py`)

LRU memoisation of stage outputs keyed by SHA-1 of JSON-serialised
`(data, prev)`. `maxsize=None` is unbounded (default); `maxsize=N`
gives LRU eviction. `cached_runner(runner_fn, cache, key_fn=...)` wraps
a `runner_fn` to make it a drop-in cache-aware replacement.

### `verifier.py` — the brute-force reference

The framework's correctness story rests on `verify_pipeline(stages,
reference_outputs)`: run the routed pipeline, compare each stage's
output to a brute-force / textbook reference (with tolerance for
floats). The brute-force primitives needed across examples live in
this module:

- `brute_force_count_matchings(vertices, edges)` — delegates to
  `holant_tools.perfect_matching_count_brute_force`.
- `brute_force_weighted_matching_sum(vertices, edges, weights)` —
  exact weighted perfect-matching sum.
- `satisfies_gf2_affine(x, A, b)` / `enumerate_satisfying_assignments`.
- `gibbs_expectation_brute(states, weight_fn, observable_fn)`.

Every leaf evaluator is small enough to be reproducible by these
primitives at small `n`. **Real pipelines verify at small `n` once and
then run at large `n` in faith of the verified construction.**

---

## 11. External dependencies and sibling repos

### Hard dependencies

- **`holant-tools >= 0.5.0`** — the mathematical engine. Provides
  Pfaffian / FKT, Kasteleyn orientations, the corrected dart-chain
  passage-arc formula, basis-aware matchgate rank, CH-form stabilizer
  representation, `genus_from_rotation_system`,
  `min_weight_perfect_matching`, `exact_planar_pfaffian`,
  `kasteleyn_orient`, `homology_generators`, plus the matchgate-
  identity functions in `holant_tools.non_symmetric`
  (`matchgate_identity_arity_4_{even,odd}`,
  `matchgate_identities_arity_n_{even,odd}`,
  `matchgate_identity_augmented_weight_1_arity_n_odd`) consumed by
  the v0.4 MGI check on general (non-symmetric) signatures.
- **`numpy >= 1.24`**, **`sympy >= 1.12`**, **Python >= 3.10**.

### Sibling repos in the ecosystem (all under `C:\Temp\`)

| Repo | Role |
|---|---|
| `admissibility-geometry` | Research parent (private). Holds conceptual lineage, literature-extraction notes (`research/*.md`), session notes, the d-admissibility / viewing-frame paradigm work, and the long-horizon roadmap. |
| `holant-tools` | Mathematical engine. Hard dependency above. |
| `free-fermion-quantum-simulation` | Worked-examples sibling — the development-trail form. Full user docs (tutorial / concepts / cookbook / reference / glossary / FAQ). The PyPI form's `Documentation` URL points here. |
| `structural-computing-bench` | Calibration companion. Timing primitives, curve fitters, problem generators per leaf evaluator, calibration runner CLI, orchestrator-trace analytics. Produces the data file consumed by `apply_calibration()`. |

### Two publicly-original mathematical results

Guarded by `tests/originality/`:

1. **Dart-chain passage-arc formula** (in `holant_tools.dart_chain_intersection`).
   Fixes Cimasoni 2012's blindspot at degree-3 vertices. Used
   automatically in `classify_graph` for genus ≥ 1.
   `tests/originality/test_dart_chain.py` asserts the 4×4 torus case
   where it disagrees with the naive walks formula
   (walks gives `[[0,0],[0,0]]`; dart-chain gives `[[0,1],[1,0]]`).

2. **Basis-aware matchgate rank ≤ 2 for symmetric signatures**
   (in `holant_tools.basis_aware_matchgate_rank`). Every symmetric
   signature has basis-aware matchgate rank in `{0, 1, 2}` via
   parity-split common-basis construction. Used by `classify_signature`
   and the T3 cost model. `tests/originality/test_basis_aware_rank.py`
   parametrises this over 17 classical signatures.

---

## 12. Testing strategy

- **302 tests** across ~15 modules. Run with `pytest tests/`.
- Per-module test files cover each primitive in isolation.
- `tests/test_smoke.py` is the public-API contract: every name in
  `structural_computing.__all__` must round-trip through this test;
  every wrapper method must produce a sensible answer on a small
  example.
- `tests/test_orchestrator.py` has 26 scenarios covering direct
  dispatch, every hint-driven phase, honest stops, custom-leaf
  registration, verbose mode, and calibration emission.
- `tests/originality/` contains parametric stress tests that defend
  the two publicly-original results above.
- The brute-force primitives in `verifier.py` are the cross-check that
  keeps every exact evaluator honest at small `n`.

---

## 13. Extension cookbook

### To add a new leaf evaluator

1. Write `_my_leaf(problem, question) -> answer` in `orchestrator.py`.
2. Add `("T?", "my_question"): _my_leaf` to `DEFAULT_LEAF_REGISTRY`.
3. Add a test in `tests/test_orchestrator.py`.
4. Add a wrapper method on `StructuralComputer` if it's user-facing.

### To add a new reduction / composition / decomposition

1. Create the class in `transform.py` / `compose.py` / `decompose.py`
   implementing the relevant Protocol (`Reduction` / `Composition` /
   `Decomposition`) with `applies_to` + `apply` (reductions) or
   `decompose` (decompositions) or `evaluate` (compositions).
2. Export it from the module's `__all__`.
3. Re-export from `structural_computing/__init__.py`.
4. Add it to `tests/test_smoke.py::test_public_api_complete`'s expected
   set.
5. If the operation is auto-applicable (no parameters needed beyond
   the problem), consider adding it to the Orchestrator's
   `_default_reductions` list. Otherwise add a hint-driven phase
   (4.x) in `evaluate()`.

### To recognise a new problem type

1. Add a `classify_{type}(...)` function in `classify.py`.
2. Add a tier (with `in_family` flag and meters) to the documented
   hierarchy.
3. Add a branch to `_classify_problem` in `orchestrator.py`.
4. Add the natural `(tier, question)` leaf evaluators per the recipe
   above.
5. Add a `route()` branch in `route.py` if the cost model needs to
   differ from existing tiers.

### To wire calibration for a new `(tier, question)`

1. Add a problem generator + leaf-evaluator binding in the
   `structural-computing-bench` sibling repo.
2. Run the bench's calibration CLI to fit `(a, b)` for `power_law` or
   `exponential`.
3. Save the rendered `CALIBRATED_COSTS` dict; users
   `apply_calibration(...)` it from their own code.

---

## 14. Pointers into the source

If you only have time to read a few files end-to-end to "get" the
package, this is the order:

1. **`__init__.py`** (180 lines) — the public surface.
2. **`easy.py`** (710 lines) — see how a user-facing method maps
   onto classifier + leaf.
3. **`classify.py`** (336 lines) — see how a problem becomes a tier.
4. **`orchestrator.py`** (1180 lines) — the central control flow, the
   7-phase evaluate(), the leaf registry.
5. **`transform.py` / `compose.py` / `decompose.py`** (3 × ~1000 lines)
   — the transformation layer. Skim the docstrings; only one or two
   classes per file need deep reading the first time.

The README and CHANGELOG cover what each release delivers; this
document is for understanding the *shape* of what's there.

---

## 15. Where this document lives in the ecosystem

This file is `docs/architecture.md` in the structural-computing repo
(the PyPI form). Detailed user-facing documentation (tutorial,
cookbook, glossary, reference) lives in the worked-examples sibling
[`free-fermion-quantum-simulation`](https://github.com/pcoz/free-fermion-quantum-simulation)
under `docs/`. Research-trail material, paradigm-level direction, and
session notes live in the private research parent `admissibility-geometry`
on disk at `C:\Temp\admissibility-geometry`.

Last updated: 2026-05-31 (against v1.1.0).
