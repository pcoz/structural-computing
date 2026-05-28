# structural-computing

**Exact polynomial-time answers to combinatorial questions that today's
tools can only sample, estimate, or give up on** — for the subset of
problems with the right structural shape (planar, bounded-genus,
near-matchgate, GF(2)-affine). When applicable, the framework returns
bit-identical reproducible numbers in milliseconds-to-seconds. When
inapplicable, it stops honestly with a clear pointer to the right
external tool. No silent approximation.

## What this lets you do

- **Compare two configurations exactly** even when the difference is
  below Monte-Carlo's noise floor. Two network topologies, two
  reinsurance treaty structures, two CI pipeline designs that look
  equivalent to sampling — the framework returns *"Configuration B is
  90.2% more reliable, provably real, not a sampling artefact"* in
  milliseconds.

- **Compute exact rare-tail probabilities** for failure modes you'd
  otherwise have to estimate by long-running Monte-Carlo. Risk reports
  for regulators, capacity-planning analyses that need defensible
  numbers, reliability claims that have to be bit-reproducible across
  runs.

- **Count solutions to combinatorial problems exactly** rather than
  finding just one. How many valid task-resource assignments exist?
  How many distinct ways can these components be paired? Which edges
  are structural single points of failure? Standard solvers find one
  answer; this framework counts and audits the whole solution space.

- **Route different kinds of problems automatically.** The framework's
  classifier figures out which structural shape your problem has, picks
  the right exact-evaluation kernel (FKT for planar graphs, bounded-
  genus Kasteleyn for higher-genus, CH-form for stabilizer arithmetic,
  tropical Pfaffian for max-weight optimisation), and produces an
  answer with a recorded provenance you can audit.

- **Beat out-of-family problems into shape.** A graph that isn't
  natively planar can often be made tractable via reductions (gadget
  substitution, basis changes, parity-split, hybrid decomposition),
  compositions (linear combinations of in-family evaluations,
  holographic basis pairs), or recursive decomposition (treewidth-
  bounded DP, Shannon expansion, circuit cutting). The framework's
  reduction layer makes this routine.

## A taste

```bash
pip install structural-computing
```

```python
from structural_computing import StructuralComputer

sc = StructuralComputer()

# Two candidate network topologies.
config_a = [(0, 1), (1, 2), (2, 3), (3, 0)]                  # 4-cycle
config_b = [(0, 1), (0, 2), (0, 3),                           # K_4
            (1, 2), (1, 3), (2, 3)]

# Exact rare-tail probability under independent edge failure.
print(sc.tail_probability(config_a, p_fail=0.05))    # 9.5063e-03 (exact, ~1.7 ms)
print(sc.tail_probability(config_b, p_fail=0.05))    # 9.2686e-04

# Compare them -- regulator-defensible verdict, no sampling noise.
report = sc.compare(config_a, config_b, p_fail=0.05)
print(report.explain())
# "Configuration B is 90.2% more reliable (9.5063e-03 vs 9.2686e-04).
#  This distinction is provably real (exact computation),
#  not a sampling artefact."
```

That comparison — sub-statistical-noise-floor, bit-identically
reproducible, regulator-defensible — **no off-the-shelf reliability
tool can produce**, because their internal data models are structurally
Monte-Carlo and the question's signal lives below the sampling floor.

## The underlying claim

Many problems people actually care about — counting valid configurations,
exact rare-tail probabilities, single-point-of-failure analysis,
regulator-grade configuration comparison, partition functions of planar
Ising models, free-fermion-equivalent quantum simulation, structural
audit of workflow graphs — sit in a mathematically structured family
called **matchgate-Holant**. For problems IN this family, exact
polynomial-time computation is possible via Kasteleyn's FKT theorem
(1961) and its bounded-genus extensions (Galluccio-Loebl). For many
problems NOT directly in this family, transformations bring them in.

The framework is the runnable form of that claim: a Python package that
takes your problem, classifies its structure, applies whatever
transformation it needs, and produces an exact answer with provenance —
or stops honestly and tells you what external tool to reach for.

The friendly entry point is `StructuralComputer` (one-liners hide every
framework internal). The underlying `Orchestrator` exposes the routing
decisions for users who want to compose custom pipelines or plug in
their own evaluators. The `transform.py` / `compose.py` / `decompose.py`
modules expose the reductions / compositions / recursive-decomposition
layer for users widening the in-family boundary.

## Status

**Alpha** (v0.1.0a1). API may change before v1.0. Foundational components
(test suite, calibrated cost models, ReplayCache eviction) are still
being built out. See [CHANGELOG.md](CHANGELOG.md) for what's in this
release and what's coming.

## What this is for

When you have a **combinatorially structured question** with a graph-like
shape — perfect matching count, rare-tail failure probability,
single-point-of-failure detection, regulator-grade configuration
comparison, satisfying-assignment count — and the underlying graph is
**planar / bounded-genus / GF(2)-affine** in structure, this package
gives you exact polynomial-time answers via the FKT theorem, Kasteleyn
orientations, and the matchgate-Holant family.

When your problem is **outside** the structural family, the package
honest-stops with `advised:external-solver` rather than producing a
false answer.

## What's inside

### The friendly entry point

```python
from structural_computing import StructuralComputer

sc = StructuralComputer()
sc.count_matchings(graph)              # how many perfect matchings?
sc.witness(graph)                       # find one specific matching
sc.tail_probability(graph, p_fail)      # exact P(no matching survives)
sc.single_points_of_failure(graph)      # critical edges
sc.compare(a, b, p_fail)                # which is more reliable?
sc.audit(graph)                         # everything in one call
sc.explain(graph)                       # human-readable plan, no jargon
```

### Framework primitives (for composing custom pipelines)

```python
from structural_computing import (
    Stage, Route, run_pipeline,        # the pipeline-router driver
    classify_graph, classify_constraint_set, classify_signature,  # the classifier
    route,                              # tier -> member + cost
    RichTrace,                          # aggregated routing trace
    ReplayCache, cached_runner,         # memoisation
    verify_pipeline,                    # small-n brute-force harness
)
```

### Orchestrator (the "give me an answer" top-level engine)

For when you don't want to think about tiers, evaluators, or reductions —
just hand the framework a problem and a question:

```python
from structural_computing import Orchestrator

orch = Orchestrator()

# A planar dependency graph -- direct dispatch via T2 free-fermion.
K4 = {
    "rotation": {0: [1, 2, 3], 1: [0, 3, 2], 2: [0, 1, 3], 3: [0, 2, 1]},
    "vertices": [0, 1, 2, 3],
    "edges": [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)],
}
result = orch.evaluate(K4, question="matching_count")
print(result.answer)                  # -> 3
print(result.classification.tier)     # -> "T2"
print(result.leaf_evaluator_used)     # -> "_brute_force_matching_leaf"

# Non-planar K_{3,3}: out-of-family by default, but HybridDecomposition
# reduces it to a sum of planar sub-problems. Supply the "extras" as hints.
K33 = {...}                            # see tests/test_orchestrator.py
result = orch.evaluate(K33, question="matching_count",
                        hints={"extra_edges": [(0, 3)]})
print(result.answer)                  # -> 6  (= 3!)
print(result.reductions_applied)      # -> ["HybridDecomposition(via hints)"]
print(result.sub_evaluations)         # -> 2  (forced-in branch + forced-out branch)
```

If the problem is out-of-family AND no registered reduction applies,
the orchestrator raises `NoKnownReduction` with the classification
attached so the caller can inspect what was tried.

### Reductions / compositions / recursive decomposition

For users who want to compose their own transformations directly:

```python
from structural_computing import (
    HybridDecomposition, ReductionPlan, NormaliseGraphFormat,    # transform.py
    LinearCombination,                                            # compose.py
    ShannonExpansion, TreewidthBoundedDP,                         # decompose.py
)
```

The reductions / compositions / decompositions layer is the framework's
**in-family-boundary widener**. v0.1 ships:

- `NormaliseGraphFormat` — coerce edge-list / adjacency-dict / rotation-
  system inputs into a canonical form.
- `HybridDecomposition` — branch on a small set of "extra" edges that
  make a graph non-planar; pay 2^|extras| × O(|V|^3) for the exact
  matching count.
- `LinearCombination` — combine two or more in-family signature
  evaluations as `sum(coeff_i * value_i)`.
- `ShannonExpansion` — branch on a binary variable; recurse on each
  branch; base case in-family.
- `TreewidthBoundedDP` — single-bag tree-decomposition (DP framework
  in place; multi-bag is the v0.2 deliverable via Bodlaender / Korhonen).

Sketches with detailed v0.2 docstrings (raised as `NotImplementedError`
today): `CrossingElimination`, `HighDegreeVertexSplit`,
`RationaliseWeights`, `Projection`, `HolographicBasisPair`, `BranchSum`,
`PlanarSeparator`, `RecursiveCircuitCut`.

See the full API reference at the worked-examples repo:
[`docs/reference/`](https://github.com/pcoz/free-fermion-quantum-simulation/tree/main/docs/reference).

## Runnable examples

The [`examples/`](examples/) folder contains six self-contained scripts
runnable after `pip install`:

| | |
|---|---|
| `01_count_matchings.py`         | exact perfect-matching count |
| `02_rare_tail_probability.py`   | exact rare-tail probability |
| `03_compare_configurations.py`  | sub-MC-noise-floor comparison |
| `04_orchestrator_dispatch.py`   | the Orchestrator's direct-dispatch + honest-stop |
| `05_hybrid_decomposition.py`    | exact matching count on non-planar K_{3,3} |
| `06_signature_classification.py`| basis-aware rank ≤ 2 across 11 classical symmetric signatures |

Each example produces a bit-identically reproducible number. See
[`examples/README.md`](examples/README.md) for the index.

## Documentation

The detailed documentation lives in the companion worked-examples repo
[`free-fermion-quantum-simulation`](https://github.com/pcoz/free-fermion-quantum-simulation)
— the **development-trail** form of the framework, where the original
worked examples and brute-force verification live. This package is the
**simplified PyPI form**; together they form the full picture (origin
+ polished form):

- **Tutorial:** [`docs/getting-started.md`](https://github.com/pcoz/free-fermion-quantum-simulation/blob/main/docs/getting-started.md) — 10-minute walkthrough.
- **Originality:** [`docs/originality.md`](https://github.com/pcoz/free-fermion-quantum-simulation/blob/main/docs/originality.md) — what's genuinely new here (dart-chain corrected primitive, basis-aware rank ≤ 2, diagnostic-layer triad).
- **Concepts:** [`docs/concepts/`](https://github.com/pcoz/free-fermion-quantum-simulation/tree/main/docs/concepts) — Holant problems, the tier hierarchy, the four coordinates, the paradigm.
- **Cookbook:** [`docs/cookbook/`](https://github.com/pcoz/free-fermion-quantum-simulation/tree/main/docs/cookbook) — domain recipes.
- **Reference:** [`docs/reference/`](https://github.com/pcoz/free-fermion-quantum-simulation/tree/main/docs/reference) — API specs.
- **Glossary + FAQ:** [`docs/glossary.md`](https://github.com/pcoz/free-fermion-quantum-simulation/blob/main/docs/glossary.md), [`docs/faq.md`](https://github.com/pcoz/free-fermion-quantum-simulation/blob/main/docs/faq.md).

## Scope

The framework's exact polynomial-time answers apply natively to problems
with the right structural shape: planar, bounded-genus, matchgate-Holant-
family, GF(2)-affine. The active development direction is the
**reduction / composition / recursive-decomposition layer** that brings
problems that don't *look* like this shape into it:

- **Reductions** — one-shot transformations: crossing-elimination gadgets,
  basis changes, hybrid planar/non-planar decompositions, parity-split,
  high-degree-vertex splitting, semiring choice, and the rest of the
  holographic-algorithm transformation arsenal.
- **Compositions** — combining two or more in-family evaluations to
  compute an out-of-family quantity: linear combinations, projections of
  joint distributions, conditional compositions, tensor/Cartesian
  products, polynomials in matchgate values, holographic-basis pairs
  (Valiant 2004's central technique), branch-sum recombinations.
- **Recursive decomposition** — recursively split a problem into
  sub-problems, base case in-family: tree-decomposition / treewidth-
  bounded dynamic programming, planar-separator divide-and-conquer,
  tensor-network contraction in the right order, Shannon expansion
  (branch on a variable, recurse on each branch), circuit-cutting
  followed by per-block recursive routing.

When the problem is in-shape (or reducible / composable / recursively-
decomposable to in-shape), the framework produces exact, bit-identical
answers in milliseconds-to-seconds.

When a problem is genuinely beyond reach (continuous mathematics with no
discretisation, unbounded matchgate rank with no decomposition, etc.) and
no known reduction or composition fits, the framework honestly stops and
advises the right external tool. No silent approximation.

## Built on holant-tools

This package depends on
[`holant-tools`](https://github.com/pcoz/holant-tools) — the mathematical
engine providing Pfaffian / FKT computation, Kasteleyn orientations,
the corrected dart-chain passage-arc formula, basis-aware matchgate
rank, the CH-form stabilizer representation, and the full set of
matchgate-Holant tractability primitives.

```python
import holant_tools  # automatically installed as a dependency
```

## License

MIT-with-attribution. See [LICENSE](LICENSE). Visible attribution to
**Edward Chalk (sapientronic.ai)** is required for publications,
presentations, derivative works, and products.

## Citation

If you use this package in published work, please cite:

```
Edward Chalk (sapientronic.ai). "structural-computing: declarative
structural computation in Python." Version 0.1.0a1, 2026.
https://github.com/pcoz/structural-computing
```

## Roadmap

- **v0.1.0** (target): test suite + CI matrix + calibrated cost models +
  expanded wrapper API (constraint sets, signatures as first-class).
- **v0.2.0**: ReplayCache eviction policy, matching-polynomial form for
  `tail_probability` on larger graphs.
- **v1.0.0**: API stability contract; production-ready for downstream
  packages.

See the long-horizon roadmap in the research repo's [`FUTURE_DIRECTIONS.md`](https://github.com/pcoz/admissibility-geometry/blob/main/FUTURE_DIRECTIONS.md)
for context on the paradigm-level direction this package serves.
