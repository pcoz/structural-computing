# Why tropical optimisation works on matchgate signatures

## The shape

The framework exposes both `sc.count_matchings(graph)` and
`sc.min_weight_matching(graph, weights)`. They look like
different operations, but they're the SAME operation under
different semirings:

| Operation | Semiring | Identity | What it computes |
|---|---|---|---|
| `count_matchings` | (+, ×) | (0, 1) | sum over matchings of 1 = count |
| `min_weight_matching` | (min, +) | (∞, 0) | min over matchings of weight-sum |

The Holant network and the Pfaffian-Kasteleyn machinery don't
change. Only the addition / multiplication operators change.

## Why this matters operationally

`sc.count_matchings(graph)` and `sc.min_weight_matching(graph,
weights)` share:

- The same admissibility check (is this graph matchgate-tractable?).
- The same orchestrator dispatch logic (which leaf evaluator?).
- The same provenance / audit trail.

The classifier doesn't care which semiring you'll use. The leaf
evaluator picks the right algorithm for the semiring:

- Standard (+, ×): Kasteleyn-Pfaffian, FKT, polynomial-time exact
  counting.
- Tropical (min, +): Hungarian (bipartite) or Edmonds blossom
  (general non-bipartite), polynomial-time exact min-cost.

Both paths are `O(n^3)`. No exponential blow-up.

## Why this is the right framing (not a category extension)

A naive framing would say "Holant counts; for optimisation, use
a different framework." That's wrong — the natural framing is:

> Holant evaluates a tensor contraction. The semiring choice
> determines what the contraction COMPUTES.

Tropical (min, +) is a perfectly good semiring. The same
contraction algorithm evaluates the tensor under either
operator. What changes is what the leaf-level Pfaffian computes:

- Standard Pfaffian (`Pf(M)`): the signed sum of perfect-matching
  products. Equals the matching count when M is the Kasteleyn-
  orientation matrix with all weights 1.
- Tropical Pfaffian (`Pf_trop(M)`): the min over perfect matchings
  of the sum of edge weights. Equals the min-weight perfect
  matching.

Both are `O(n^3)` polynomial-time. The framework calls them
through a single `pfaffian(M, semiring=...)` interface
(at the engine layer in holant-tools).

## Where this comes from

The admissibility-geometry research programme observed that the
matchgate-Holant tractability condition is **semiring-agnostic**.
The four structural coordinates that characterise tractability
(matchgate rank, sum-of-Pfaffians evaluator, field-extension
distance, sub-signature coverage) transfer to the tropical
semiring with minimal modification:

- Matchgate rank: Hankel rank ≤ 2 under either semiring.
- Sum-of-Pfaffians evaluator: polymorphic over semiring.
- Field-extension distance: replaced by the tropical equivalent
  (max-plus vs min-plus).
- Sub-signature coverage: unchanged.

So the same combinatorial structure that lets a graph admit
polynomial-time counting also lets it admit polynomial-time
min-cost optimisation. The user just picks which question.

## What you actually use

```python
from structural_computing import StructuralComputer
sc = StructuralComputer()

# Count: standard (+, ×) semiring.
n_matchings = sc.count_matchings(graph)

# Min-cost: tropical (min, +) semiring.
result = sc.min_weight_matching(graph, weights)
# {'cost': float, 'matching': [...], 'feasible': bool}
```

You don't pass a `semiring=` argument to `StructuralComputer` —
the choice is implicit in the question. Want a count? Use
`count_matchings`. Want a min-cost? Use `min_weight_matching`.
Same graph; framework picks the right algorithm.

## The broader pattern

The framework provides six min-cost methods, all sharing this
structure:

- `sc.min_weight_matching(graph, weights)` — graphs.
- `sc.min_cost_schedule(instance, cost_fn)` —
  `SchedulingInstance`.
- `sc.min_cost_flow(instance)` — `MinCostFlowInstance`.
- `sc.min_cost_roster(instance, preference_fn)` —
  `RosteringInstance`.
- `sc.min_cost_dedup(instance, similarity_fn)` — `MDMInstance`.
- `sc.tropical_instance_coordinates(instance, cost_fn)` —
  one-call structural diagnostic.

Each accepts a domain-specific instance + a callable that
defines the cost. Each returns `{cost, ..., feasible}`. Each
dispatches through the same admissibility check + tropical
Pfaffian dispatch underneath.

## When this DOESN'T apply

The tropical path requires the **admissible set** to fit the
matchgate-Holant shape. Specifically:

- The cost matrix must have **tropical rank** ≤ 2 (the
  tropical analogue of Hankel rank ≤ 2).
- Each constraint must be expressible as a matchgate signature.

For instances that don't fit, the leaf evaluator either
honest-stops (`feasible=False`) or falls back to enumeration.
Run `sc.tropical_instance_coordinates(instance, cost_fn)` first
if you want to check structural fit before committing.

## See also

- [Tutorial step 4](../tutorial/getting-started.md#step-4--find-the-cheapest-perfect-matching-5-min)
  — the min-weight matching tutorial example.
- [How-to: min-cost scheduling](../how-to/min-cost-scheduling.md)
  — scheduling-instance examples.
- [Reference: tropical family](../reference/api.md#tropical--min-cost-optimisation)
  — full signatures.
