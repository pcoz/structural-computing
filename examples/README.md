# Examples

Self-contained worked examples demonstrating the `structural-computing`
package. Each script is runnable with `python <script>.py` once the
package is installed:

```bash
pip install structural-computing      # once published to PyPI
# OR for the development source:
pip install -e .                        # from the repo root
```

## The examples

| file | what it shows |
|---|---|
| [`01_count_matchings.py`](01_count_matchings.py) | Exact perfect-matching count on small graphs via `sc.count_matchings(graph)` |
| [`02_rare_tail_probability.py`](02_rare_tail_probability.py) | Exact rare-tail probability under independent edge failure (`sc.tail_probability`) |
| [`03_compare_configurations.py`](03_compare_configurations.py) | Sub-statistical-noise-floor configuration comparison (`sc.compare`); regulator-defensible verdict |
| [`04_orchestrator_dispatch.py`](04_orchestrator_dispatch.py) | The `Orchestrator` -- direct dispatch + honest stop |
| [`05_hybrid_decomposition.py`](05_hybrid_decomposition.py) | Exact matching count on a non-planar graph (`sc.count_matchings_hybrid` on K_{3,3}) |
| [`06_signature_classification.py`](06_signature_classification.py) | Symmetric signature classification + basis-aware rank ≤ 2 across 11 classical signatures |
| [`07_treewidth_bounded_dp.py`](07_treewidth_bounded_dp.py) | Multi-bag Bodlaender-style DP for matching count on a supplied tree decomposition |
| [`08_rationalise_weighted_matching.py`](08_rationalise_weighted_matching.py) | Float-weighted graphs scaled to integer arithmetic via `RationaliseWeights`, exact descale at the end |
| [`09_holographic_basis_unlock.py`](09_holographic_basis_unlock.py) | Hadamard basis maps 3-AND `[1, 0, 0, 1]` into matchgate-standard `[0, 2, 0, 2]` -- the canonical Valiant-style holographic unlock |
| [`10_crossing_elimination_k4.py`](10_crossing_elimination_k4.py) | Cai-Gorenstein 6-vertex crossover gadget inserted at K_4's diagonal crossing |
| [`11_high_degree_vertex_split.py`](11_high_degree_vertex_split.py) | Cai-Gorenstein 2k-node triangle-cycle matchgate realising an arity-4 symmetric signature; brute-force-verifies all 16 entries |
| [`12_discover_holographic_basis.py`](12_discover_holographic_basis.py) | Auto-discovery of a holographic basis (`discover_basis`) -- the practical fragment of Cai-Lu's SRP algorithm |
| [`13_general_holographic_transform.py`](13_general_holographic_transform.py) | Non-symmetric `T^⊗a` transformation on a length-`2^a` tensor; agreement with the symmetric path, T then T^{-1} round-trip, Walsh-Hadamard of a delta |

## What you'll see

These are not demos. They're the runnable form of the cookbook recipes
documented at
[`free-fermion-quantum-simulation/docs/cookbook/`](https://github.com/pcoz/free-fermion-quantum-simulation/tree/main/docs/cookbook).
Each one produces a number (or a verdict, or a table) that's bit-
identically reproducible across runs.

## How these relate to the worked-examples repo

[`free-fermion-quantum-simulation`](https://github.com/pcoz/free-fermion-quantum-simulation)
is the **development-trail repo** -- it contains the original worked
examples with brute-force verification, the originality demonstrations,
and the conceptual documentation. The examples there are written
against the loose-file form of the framework
(`pipeline-router/easy.py`, `pipeline-router/pipeline_router.py`, etc.).

The examples here in `structural-computing/examples/` are the
**simplified PyPI-package form** -- written against the
`structural_computing` package. Same capabilities, much less code.

Both forms are preserved on purpose: the development trail stays visible
in `free-fermion-quantum-simulation`; the polished form lives here.

## See also

- [`../README.md`](../README.md) -- package overview.
- [`../CHANGELOG.md`](../CHANGELOG.md) -- what shipped when.
- Full documentation: [`free-fermion-quantum-simulation/docs/`](https://github.com/pcoz/free-fermion-quantum-simulation/tree/main/docs)
  (tutorial / how-to / reference / explanation / glossary / FAQ).
