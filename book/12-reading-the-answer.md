# Chapter 12 — Reading the answer

You've now seen the framework in action across three worked
examples. Each one ended with the framework returning *some*
answer. This chapter goes deeper on what the answers actually
look like — what's in them, what each field means, how to
read them in production code, and how to defend them to an
auditor or regulator.

The chapter is in five parts:

1. **The four answer shapes.** Counts, costs, probabilities,
   witnesses.
2. **The dict-style results.** Why `min_cost_*` returns a
   dictionary, what's in it.
3. **The audit trail.** Every framework call leaves a trail
   showing how the answer was computed.
4. **Verbose mode.** Watching the framework think.
5. **Reading honest stops.** The structure of the failure
   message.

## 1. The four answer shapes

Across all the methods you've seen, the framework returns one
of four kinds of answer:

### Counts (integers)

`sc.count_matchings(graph)` returns an integer.
`sc.count_solutions(A=..., b=...)` returns an integer. Both
are exact whole numbers — `42` is `42`, not `42 ± 0.5`.

These are the simplest results to use. Drop them straight into
a database column, a report, a calculation. No special
handling required.

### Real-valued quantities (floats)

`sc.tail_probability(graph, p_fail=0.05)` returns a float.
`sc.matchgate_rank(values)` returns an integer that happens
to come back as a float in some intermediate computations.
Anything involving probability or weight returns a float.

These are exact in the mathematical sense (no Monte Carlo
sampling error) but limited by floating-point precision (the
last 1-2 digits may not match across architectures). For
regulatory work where bit-identical reproducibility matters,
either pin your Python and library versions, or use the
framework's sympy-based exact path (slower but
rationals-precise).

### Witnesses (lists of edges, dicts, or other concrete objects)

`sc.witness(graph)` returns a list of edges forming a perfect
matching. `sc.find_witness_solution(A=..., b=...)` returns an
integer encoding a satisfying assignment. `sc.min_cost_schedule(...)`'s
result includes a schedule dict mapping jobs to (machine, slot)
pairs.

Witnesses are concrete examples — proof that an admissible
configuration exists. They're useful for two reasons: as
existence proofs, and as starting points for downstream work
(if you've found one matching, you can ask follow-up questions
about it).

### Compound results (dicts)

`sc.min_weight_matching(...)`, `sc.min_cost_schedule(...)`,
`sc.rewrite_cpsat_model(...)` and similar return *dicts* or
*structured dataclasses* with multiple fields. We'll cover the
typical structure in the next section.

## 2. The dict-style results

The framework returns dicts from methods that have multiple
things to say. The standard shape, with minor variations
across methods, is:

```python
{
    "cost": float | None,         # the optimal value, or None
    "matching" / "schedule" / ...: structured | None,
                                    # the witness, or None
    "feasible": bool,             # could a valid configuration be found?
    # plus method-specific extras
}
```

For example:

```python
result = sc.min_weight_matching(graph, weights={...})
# {
#     "cost": 13.0,
#     "matching": [(0, 2), (1, 3)],
#     "feasible": True,
# }
```

The `feasible` key is the most important one. It tells you
*whether the framework found a valid configuration at all*:

- `feasible: True` — the answer is meaningful. Use `cost`,
  `matching`, etc.
- `feasible: False` — no valid configuration exists. `cost` and
  the witness fields will be `None`. The problem is structurally
  infeasible (e.g., odd vertex count for perfect matching), not
  out-of-family. (Out-of-family raises `NotInFamily`, doesn't
  return `feasible: False`.)

In production code, the pattern is:

```python
result = sc.min_weight_matching(graph, weights)
if not result["feasible"]:
    handle_infeasibility(graph, weights)
    return
cost, matching = result["cost"], result["matching"]
```

This handles both the "no solution exists" case and the "got
one" case cleanly. The framework doesn't throw exceptions for
infeasible-but-valid inputs; it returns `feasible: False` and
lets you handle it.

## 3. The audit trail

Every framework call leaves a trail. You can access it through
the orchestrator's `evaluate()` method, which returns an
`OrchestratorResult` with:

- `answer` — the bare result (same as what the wrapper
  methods return).
- `classification` — the `Classification` object showing what
  tier the problem landed in.
- `reductions_applied` — list of reduction-step names that
  ran during evaluation.
- `sub_evaluations` — count of sub-problem evaluations (for
  problems that needed decomposition).
- `leaf_evaluator_used` — name of the actual algorithm that
  produced the answer.
- `workflow_trace` — list of `WorkflowStep` objects, one per
  orchestrator phase, with timestamps and outcomes.

The `StructuralComputer` wrapper hides this from you for
brevity. If you want it, drop a level:

```python
from structural_computing import Orchestrator

orch = Orchestrator()
result = orch.evaluate(problem, "min_cost_schedule")

print(result.answer)              # the actual schedule
print(result.classification.tier) # T2
print(result.leaf_evaluator_used) # '_min_cost_schedule_leaf'
print(len(result.workflow_trace)) # 4 (or however many phases ran)

for step in result.workflow_trace:
    print(f"  {step.phase}: {step.action} -> {step.outcome}")
    if step.detail:
        print(f"     reason: {step.detail}")
```

A typical workflow trace might look like:

```
  normalise: NormaliseGraphFormat -> skipped
     reason: input already in canonical form
  classify: classify_graph -> ok
     reason: tier=T2, planar (genus 0) on 16 vertices
  direct-dispatch: leaf_evaluator(T2, min_cost_schedule) -> ok
     reason: answer=42.0, evaluator=_min_cost_schedule_leaf
```

Three lines (normalise, classify, direct-dispatch) and the
problem is solved. For more complex problems — where the
orchestrator has to apply reductions or decompositions before
reaching a leaf evaluator — the trace can be longer, with
each step recording what the orchestrator tried and what
happened.

### Why this matters for regulatory work

The workflow trace is the framework's audit trail. For a
regulator-facing computation, you can attach the trace to your
report as evidence. The trace shows:

- Which classifier ran (so the regulator can see why the
  problem was deemed in-family).
- Which leaf evaluator computed the answer (so the regulator
  can confirm the algorithm is one approved for the regulation
  in question).
- What reductions were applied (in case the problem required
  any transformations before solving).

A Monte Carlo simulator's audit trail is essentially "we ran
N samples and averaged". The framework's audit trail is "we
classified the problem as T2 (planar) and applied
Kasteleyn-Pfaffian via leaf evaluator
`_tail_probability_leaf`". The second is much more defensible.

## 4. Verbose mode

For development and debugging, the orchestrator has a
`verbose=True` option that prints each step as it happens:

```python
result = orch.evaluate(problem, "min_cost_schedule", verbose=True)
```

Output:

```
[normalise] NormaliseGraphFormat -> skipped
    reason: input already in canonical form
[classify] classify_graph -> ok
    reason: tier=T2, planar (genus 0) on 16 vertices
[direct-dispatch] leaf_evaluator(T2, min_cost_schedule) -> ok
    reason: answer={'cost': 42.0, ...}, evaluator=_min_cost_schedule_leaf
```

The exact same content as the workflow trace, but printed live
so you can watch what's happening. Useful when:

- You're investigating why a problem is honest-stopping.
- You're benchmarking which phase takes the time.
- You're learning the framework and want to see what it does.

For production code, leave verbose off (default). For
debugging, turn it on.

## 5. Reading honest stops

We covered honest stops in Chapter 8. Here's how to read the
specific failure message you'll see in practice.

When the framework can't answer, it raises one of two
exceptions:

### `NotInFamily`

Raised by the `StructuralComputer` wrapper when the problem's
classification puts it out-of-family. The exception carries:

```python
try:
    sc.count_matchings(some_non_planar_graph)
except NotInFamily as e:
    print(e.classification.tier)        # 'T5'
    print(e.classification.reasoning)   # 'non-planar graph...'
    print(e.classification.meters)      # detailed measurements
```

The pattern: catch `NotInFamily`, read the classification,
either fall back to an alternative tool or surface the error
upstream with the classification context. Don't catch and
silently swallow — the whole point of the honest stop is
that the failure is visible.

### `NoKnownReduction`

Raised by the `Orchestrator` when the classification is
in-family but no leaf evaluator exists for the requested
(tier, question) pair. The exception carries:

```python
try:
    orch.evaluate(problem, "some_question_not_registered")
except NoKnownReduction as e:
    print(e.classification)   # the classification at the point of giving up
    print(e.attempted)        # list of reductions tried (if any)
```

This is rarer in practice than `NotInFamily` because most
well-known (tier, question) pairs are registered. You'd see
it if you wrote a custom orchestrator with a partial registry,
or if you ask for a question name that isn't supported on the
tier the problem fell into.

## In summary

Reading the framework's answers is mostly straightforward —
the methods return what their names suggest, plus a `feasible`
flag for the cases where infeasibility is possible.

The deeper layer — the audit trail, verbose mode, exception
structure — is there when you need it. For day-to-day code,
you'll work with the surface layer. For regulator-facing work
or debugging, you'll reach for the deeper layer.

The next chapter covers the practical art of wiring the
framework into existing systems. We'll look at integration
patterns, error handling, and what to do when your existing
codebase has assumptions that don't match the framework's.
