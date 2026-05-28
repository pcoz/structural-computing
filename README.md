# structural-computing

**Declarative structural computation:** exact polynomial-time answers to
combinatorial questions on structured graphs, with automatic routing to
the cheapest correct evaluator.

```bash
pip install structural-computing
```

```python
from structural_computing import StructuralComputer

sc = StructuralComputer()

# A network configuration as edges
config_a = [(0, 1), (1, 2), (2, 3), (3, 0)]
config_b = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]

# Exact rare-tail probability under independent edge failure
print(sc.tail_probability(config_a, p_fail=0.05))   # 9.5063e-03 (exact, ~1.7 ms)
print(sc.tail_probability(config_b, p_fail=0.05))   # 9.2686e-04

# Compare two configurations -- regulator-defensible verdict
report = sc.compare(config_a, config_b, p_fail=0.05)
print(report.explain())
# "Configuration B is 90.2% more reliable (9.5063e-03 vs 9.2686e-04).
#  This distinction is provably real (exact computation),
#  not a sampling artefact."
```

That comparison — sub-statistical-noise-floor, bit-identically
reproducible, regulator-defensible — **no off-the-shelf reliability
tool can produce**, because their internal data models are structurally
Monte-Carlo.

This package is the friendly user-facing entry point to the matchgate-
Holant family of exact polynomial-time computations on structured graphs.

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

See the full API reference at the worked-examples repo:
[`docs/reference/`](https://github.com/pcoz/free-fermion-quantum-simulation/tree/main/docs/reference).

## Documentation

The detailed documentation lives in the companion worked-examples repo
[`free-fermion-quantum-simulation`](https://github.com/pcoz/free-fermion-quantum-simulation):

- **Tutorial:** [`docs/getting-started.md`](https://github.com/pcoz/free-fermion-quantum-simulation/blob/main/docs/getting-started.md) — 10-minute walkthrough.
- **Originality:** [`docs/originality.md`](https://github.com/pcoz/free-fermion-quantum-simulation/blob/main/docs/originality.md) — what's genuinely new here (dart-chain corrected primitive, basis-aware rank ≤ 2, diagnostic-layer triad).
- **Concepts:** [`docs/concepts/`](https://github.com/pcoz/free-fermion-quantum-simulation/tree/main/docs/concepts) — Holant problems, the tier hierarchy, the four coordinates, the paradigm.
- **Cookbook:** [`docs/cookbook/`](https://github.com/pcoz/free-fermion-quantum-simulation/tree/main/docs/cookbook) — domain recipes.
- **Reference:** [`docs/reference/`](https://github.com/pcoz/free-fermion-quantum-simulation/tree/main/docs/reference) — API specs.
- **Glossary + FAQ:** [`docs/glossary.md`](https://github.com/pcoz/free-fermion-quantum-simulation/blob/main/docs/glossary.md), [`docs/faq.md`](https://github.com/pcoz/free-fermion-quantum-simulation/blob/main/docs/faq.md).

## Honest scope

This is **not** a universal computational speedup. The framework's exact
polynomial-time answers apply to combinatorial problems with the right
structural shape: planar, bounded-genus, matchgate-Holant-family,
GF(2)-affine. **Most problems don't have this shape.**

When applicable, the framework produces exact, bit-identical answers
in milliseconds-to-seconds.

When inapplicable, the framework honestly stops and advises the right
external tool. No silent approximation.

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
