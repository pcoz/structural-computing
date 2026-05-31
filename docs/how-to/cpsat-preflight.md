# How to: pre-flight a CP-SAT model

You have a CP-SAT model and you want to know: *is there a
structural shortcut here that lets me solve it faster?*

## The one-liner

```python
from ortools.sat.python import cp_model
from structural_computing import StructuralComputer

sc = StructuralComputer()

model = cp_model.CpModel()
xs = [model.NewBoolVar(f"x{i}") for i in range(10)]
model.Add(sum(xs) == 5)
# ... add more constraints ...

result = sc.rewrite_cpsat_model(model)

if result.helped:
    # The rewritten model is structurally cheaper.
    solver = cp_model.CpSolver()
    status = solver.Solve(result.rewritten_model)
else:
    # No matchgate shortcut. Solve the original.
    solver = cp_model.CpSolver()
    status = solver.Solve(model)
```

## What the `helped: bool` signal means

- `helped = True`: at least one constraint was rewritten to a
  rank-1 time-slot form. Look at `result.help_reason_text` for
  the specifics:
  ```
  "Rewrote 1 constraint(s) to time-slot rank-1 form;
   added 8 auxiliary boolean(s)."
  ```
- `helped = False`: no constraint matched a known rewrite
  pattern. The `result.rewritten_model` is the original model
  unchanged; you can safely run CP-SAT on it. `help_reason_text`
  explains why no rewrite applied.

## What kinds of constraints get rewritten

The diagnostic targets **rank-explosive** constraints — those
that would force a dense matchgate signature on the underlying
Holant network. Examples:

- Cardinality: `sum(xs) == k`
- All-different over a small range (when expressed via Boolean
  encodings).
- Some at-most-k / at-least-k constraints.

The rewrite replaces each such constraint with a rank-1 time-slot
encoding that uses auxiliary boolean variables but admits a
polynomial-time matchgate-Holant evaluation.

## Verifying the rewrite (small instances)

For models small enough to enumerate, you can confirm the
rewrite preserves the feasible set on the original variables:

```python
verify = sc.verify_cpsat_rewrite(
    model, result,
    enumeration_limit=10000,    # default
    check_objective=True,        # also check optimal objective
    max_witnesses=5,             # how many counterexamples to report
)

if verify.equivalent:
    print(f"OK: {verify.n_original_solutions} solutions, both agree")
else:
    print(f"BUG: rewrite changed the feasible set!")
    print(f"  Missing witnesses: {verify.missing_witnesses}")
    print(f"  Spurious witnesses: {verify.spurious_witnesses}")
```

Use this on your test instances (small enough to enumerate) to
build confidence before relying on the rewrite in production.

## Abstract constraint diagnostic (without a full CpModel)

If you have a list of `holant_tools.ConstraintSpec` objects (e.g.,
from your own model-building layer), you can run the diagnostic
without building a `cp_model.CpModel`:

```python
import holant_tools

constraints = [
    holant_tools.ConstraintSpec(kind="cardinality", arity=10, k=5),
    # ...
]

diag = sc.diagnose_constraints(constraints)
# diag.recommended_encoding, diag.aggregate_complexity_class, ...

blueprint = sc.rewrite_constraints(constraints)
# blueprint.total_rewritten_constraint_count
# blueprint.total_aux_variable_count
```

This is useful at model-design time before committing to a
specific CP-SAT formulation.

## What the framework is doing (one paragraph)

The structural diagnostic checks each constraint against a
catalogue of "rank-explosive" patterns. For each match, it
emits a time-slot rank-1 rewrite that introduces auxiliary
booleans to bind the original variables to time-slot indicator
variables. The rewritten model has the same feasible set on the
original variables but a cheaper matchgate-Holant signature.
CP-SAT itself doesn't know about this — but downstream
holant-tools machinery (if you reach for it directly) can
exploit it.

## When the rewrite doesn't help

`helped = False` is a HONEST stop, not a bug. Many CP-SAT models
don't have rank-explosive constraints, in which case the
diagnostic correctly reports it can't help. Run your original
model normally.

## Related capabilities

- [`sc.diagnose_constraints`](../reference/api.md#diagnose_constraints)
  — encoding-selection diagnostic.
- [`sc.rewrite_constraints`](../reference/api.md#rewrite_constraints)
  — abstract rewrite-blueprint generation.
- [`sc.verify_cpsat_rewrite`](../reference/api.md#verify_cpsat_rewrite)
  — equivalence verification.
