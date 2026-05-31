# structural-computing — documentation

This documentation follows the [Diátaxis](https://diataxis.fr/)
quadrant structure: tutorial (learn), how-to (do), reference
(lookup), explanation (understand).

## Tutorial — learn the framework

- [Getting started (30 minutes)](tutorial/getting-started.md) —
  end-to-end walkthrough covering counting, reliability,
  min-cost matching, CP-SAT pre-flight, and honest stops.

## How-to — do specific tasks

- [Min-cost scheduling](how-to/min-cost-scheduling.md) —
  optimal job-to-machine assignment with capacity constraints.
- [CP-SAT pre-flight](how-to/cpsat-preflight.md) — rewrite
  rank-explosive constraints to rank-1 time-slot equivalents.

## Reference — full API

- [API reference](reference/api.md) — every public method on
  `StructuralComputer` with signature + return type + one-line
  description.
- [Stability contract](STABILITY.md) — per-symbol stability
  tiers (Stable / Experimental / Internal).

## Explanation — understand the framework

- [Why tropical works](explanation/tropical.md) — the semiring-
  choice argument for min-cost optimisation on the same
  admissible-set machinery as counting.

## Book — the narrative guide

- [Declarative Structural Computing — a Practitioner's Guide](book.md)
  — a 17-chapter narrative walkthrough of the paradigm: the
  100,000-line problem, the SQL precedent, the five plain-
  English concepts, three runnable worked examples (reliability,
  scheduling, CP-SAT pre-flight), integration patterns, and the
  long-horizon industry view. Includes a one-page business case
  for business-analyst readers. Chapter files live under
  [`../book/`](../book/) with runnable examples at
  [`../book/examples/`](../book/examples/).

## Release history

- [v1.1 plan](v1.1-plan.md) — post-1.0 polish (calibration + Diátaxis docs + stability promotions).
- [v1.0 plan](v1.0-plan.md) — the production-ready milestone.
- [v0.13 plan](v0.13-plan.md) — CP-SAT diagnostic layer.
- [v0.12 plan](v0.12-plan.md) — wrapper consolidation.
- [v0.11 plan](v0.11-plan.md) — finish tropical wiring.
- [v0.10 plan](v0.10-plan.md) — tropical optimisation in orchestrator.
- [v0.9 plan](v0.9-plan.md) — full LT 1979 with explicit planar-dual.
- [v0.8 plan](v0.8-plan.md) — higher-m Plücker + LT 4th tier.
- [v0.7 plan](v0.7-plan.md) — PyPI publication unblock.
- [v0.6 plan](v0.6-plan.md) — cleanup + math completeness.
- [v0.5 plan](v0.5-plan.md) — Cai-Lu §4 d-admissibility.
- [v0.4 plan](v0.4-plan.md) — MGI realisability + LT auto-separator.

## Architecture deep dive

- [`architecture.md`](architecture.md) — comprehensive system
  reference (orchestrator dispatch, classifier, leaf-evaluator
  registry, reductions / compositions / decompositions layer,
  calibration loop, pipeline-router framework).
