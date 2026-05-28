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
