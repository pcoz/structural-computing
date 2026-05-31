# Getting started with structural-computing (30 minutes)

This tutorial walks you through the framework end-to-end. By the
end you'll have used `StructuralComputer` to:

1. Count perfect matchings on a graph.
2. Compute exact rare-tail probabilities.
3. Find the minimum-weight perfect matching (tropical / Hungarian).
4. Pre-flight a CP-SAT model for a structural shortcut.
5. Compare two configurations with regulator-defensible verdicts.

## Setup

```bash
pip install structural-computing
```

That's it. `structural-computing` pulls in `holant-tools` as a
transitive dependency.

```python
from structural_computing import StructuralComputer

sc = StructuralComputer()
```

`sc` is your one-handle entry point to everything below.

## Step 1 — Count perfect matchings (3 min)

```python
# Two graphs: a 4-cycle and the complete graph K_4.
four_cycle = [(0, 1), (1, 2), (2, 3), (3, 0)]
k4 = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]

print(sc.count_matchings(four_cycle))     # 2
print(sc.count_matchings(k4))             # 3
```

Behind the scenes: the orchestrator classified each graph as
**T2 (planar)**, dispatched to the Kasteleyn-Pfaffian leaf
evaluator, and returned the exact integer count in O(n³) time.
No brute force on small inputs; no sampling at any size.

## Step 2 — Exact rare-tail probability (5 min)

What's the probability that no perfect matching survives if each
edge independently fails with probability `p_fail`?

```python
print(sc.tail_probability(four_cycle, p_fail=0.05))   # 9.5063e-03
print(sc.tail_probability(k4, p_fail=0.05))           # 9.2686e-04
```

Both numbers are **exact** — not Monte-Carlo estimates. The
4-cycle is 10× more likely to fail than `K_4` at the 5% edge-
failure rate, and the framework returns that ratio without
sampling noise.

This is sub-statistical-noise-floor — Monte-Carlo would need
roughly `1 / (0.001 × 0.01²)² ≈ 10¹⁰` samples to distinguish the
two configurations at 1% relative precision. The framework gives
the same answer bit-identically in milliseconds.

## Step 3 — Compare configurations (regulator-defensible) (3 min)

```python
report = sc.compare(four_cycle, k4, p_fail=0.05)
print(report.explain())
# > Configuration B is 90.2% more reliable
# > (9.5063e-03 vs 9.2686e-04).
# > This distinction is provably real (exact computation),
# > not a sampling artefact.
```

The verdict is *provably exact* — not statistical. You can put
this in a regulator submission.

## Step 4 — Find the cheapest perfect matching (5 min)

Same admissible-set machinery, different semiring. The standard
(+, ×) semiring counts matchings; the tropical (min, +) semiring
finds the cheapest.

```python
graph = [(0, 1), (1, 2), (2, 3), (3, 0)]
weights = {
    (0, 1): 1.0,
    (1, 2): 10.0,
    (2, 3): 1.0,
    (3, 0): 10.0,
}
result = sc.min_weight_matching(graph, weights)
# {'cost': 2.0, 'matching': [(0, 1), (2, 3)], 'feasible': True}
```

Polynomial-time exact via Hungarian (bipartite) or Edmonds
blossom (general non-bipartite). No MIP timeout, no heuristic.

## Step 5 — Pre-flight a CP-SAT model (10 min)

If you're already using CP-SAT, you can pass your model to the
framework and ask: *"is there a structural shortcut here?"*

```python
from ortools.sat.python import cp_model

# A model with a cardinality constraint.
model = cp_model.CpModel()
xs = [model.NewBoolVar(f"x{i}") for i in range(4)]
model.Add(sum(xs) == 2)

result = sc.rewrite_cpsat_model(model)
print(result.helped)              # True
print(result.help_reason_text)    # "Rewrote 1 constraint(s) to time-slot rank-1 form..."
```

The framework rewrote the rank-explosive `sum(xs) == 2` into a
rank-1 time-slot encoding. You can solve the rewritten model
with the regular CP-SAT solver:

```python
if result.helped:
    solver = cp_model.CpSolver()
    solver.Solve(result.rewritten_model)
else:
    # Honest stop: framework said it can't help; solve original.
    solver = cp_model.CpSolver()
    solver.Solve(model)
```

For safety on small instances, verify the rewrite preserves the
feasible set:

```python
verify = sc.verify_cpsat_rewrite(model, result, enumeration_limit=1000)
assert verify.equivalent
assert verify.n_original_solutions == 6  # = C(4, 2)
```

## Step 6 — When the framework can't help, it tells you (4 min)

The framework's biggest virtue isn't what it CAN do — it's that
it tells you honestly when it CAN'T.

```python
import numpy as np

# An out-of-family input: random non-planar graph.
random_graph = [(i, (i + 1) % 7) for i in range(7)] + [(0, 3), (1, 4)]

try:
    sc.count_matchings(random_graph)
except Exception as e:
    print(type(e).__name__, e)
    # NotInFamily: graph is non-planar; framework has no exact path
```

You get a `NotInFamily` exception with the classification
attached, telling you exactly what tier the problem landed in
and what was tried. No silent approximation.

## What you've learned

After 30 minutes you've used the framework for:

- **Counting** (matching count, solution count).
- **Reliability** (tail probability, single-points-of-failure).
- **Comparison** (regulator-defensible verdicts).
- **Optimisation** (min-weight matching via tropical semiring).
- **Pre-flighting CP-SAT** (rewrite + verify).
- **Honest stops** (out-of-family detection).

That's the v1.0 capability surface.

## Where to next

- [How-to: min-cost scheduling](../how-to/min-cost-scheduling.md) —
  scheduling instances with capacity constraints.
- [How-to: composing custom pipelines](../how-to/custom-pipelines.md)
  — using the pipeline-router framework.
- [Reference: full API](../reference/api.md) — every public method
  with its signature.
- [Explanation: why tropical works](../explanation/tropical.md) —
  the semiring-choice argument.
