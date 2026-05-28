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

## [Unreleased]

Coming in v0.1.0:
- `tests/` directory with pytest coverage of all primitives.
- CI matrix (Linux/macOS/Windows × Python 3.10-3.13).
- `tests/originality/` — dart-chain demo, basis-aware rank checks,
  MC comparison as proper pytest fixtures.
- Expanded `StructuralComputer` API: first-class methods for
  constraint sets and signatures.

Coming in v0.2.0:
- ReplayCache eviction policy (LRU or size-bounded).
- Calibrated cost models in `route` (replace the `2 log2 n` surrogate
  with benchmark-measured constants per tier).
- Matching-polynomial form for `tail_probability` on larger graphs.

Coming in v1.0.0:
- API stability contract.
- Production-ready for downstream packages (workflow-system DSLs,
  catastrophe-modelling DSLs, etc.).
