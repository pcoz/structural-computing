# Example: CP-SAT pre-flight rewrite

This folder accompanies Chapter 11 of the book. It shows the
framework operating as a *pre-flight layer* on a CP-SAT model
— rewriting rank-explosive constraints into a structurally
cheaper form before handing the model back to the regular
CP-SAT solver.

## What's in this folder

- `cardinality_rewrite.py` — a small CP-SAT model with a
  cardinality constraint. Compares solving the original model
  with solving the rewritten model. Verifies that both produce
  the same feasible set.
- `README.md` — this file.

## Prerequisites

You need OR-Tools installed:

```bash
pip install ortools
```

## How to run

```bash
cd book/examples/11_cpsat_preflight
python cardinality_rewrite.py
```

Expected output:

```
CP-SAT pre-flight rewrite on cardinality constraint

Original model: 8 boolean variables, constraint sum(xs) == 4
Rewritten model:
  helped: True
  reason: Rewrote 1 constraint(s) to time-slot rank-1 form;
          added 6 auxiliary boolean(s).
  num_original_variables: 8
  num_total_variables: 14

Verification:
  equivalent: True
  n_original_solutions: 70 (= C(8, 4), as expected)

Solving rewritten model with CP-SAT...
  status: OPTIMAL
  one solution: x0=1 x1=1 x2=1 x3=1 x4=0 x5=0 x6=0 x7=0
  ...
```

## What this demonstrates

The framework reads a CP-SAT model, identifies the cardinality
constraint, rewrites it into a rank-1 time-slot form, and
hands you back a new CP-SAT model. You verify the rewrite
preserves the feasible set (it does — 70 solutions for both,
matching `C(8, 4) = 70`). Then you solve the rewritten model
with the same CP-SAT solver.

On this 8-variable example, the speedup is negligible — both
models solve in milliseconds. The point is the **pattern**:

- The framework lives alongside CP-SAT, not in place of it.
- It rewrites constraints that CP-SAT handles inefficiently
  into forms it handles efficiently.
- The `helped: bool` signal is first-class — you branch on it
  and either run the rewritten or the original model.
- Verification is built in, so you can confirm equivalence on
  small instances before deploying.

For real production CP-SAT models with many rewritable
constraints, the speedup can be substantial. The framework's
internal benchmarks (see `holant-tools` documentation) report
28-orders-of-magnitude reduction in evaluation cost on
specific real-world workloads.

## When to use this pattern

Use the pre-flight pattern when:

- You're already using CP-SAT and don't want to switch.
- Your models have cardinality, all-different, at-most-k, or
  similar rank-explosive constraints.
- Speed is a concern but not so critical that you'd consider
  replacing CP-SAT entirely.

When NOT to use the pattern:

- Your models have no rank-explosive constraints. The
  framework will honest-stop (`helped=False`) and you'll add
  nothing but a few milliseconds of pre-flight time.
- You're already using a non-CP-SAT solver (Gurobi, CPLEX).
  The pre-flight is CP-SAT-specific in this iteration.
- Your problem fits the framework's `min_cost_*` family
  better than CP-SAT. Then replace, don't pre-flight.

## How the framework decides what to rewrite

The framework inspects each constraint in the CP-SAT model.
It looks for known rank-explosive patterns: cardinality
constraints, all-different over small ranges, at-most-k. When
it finds one, it consults its catalogue of known rewrites
and applies the matching rewrite.

You can see what would be rewritten without committing by
calling `sc.diagnose_constraints(constraint_specs)` first,
which returns a structured report of which constraints are
rewritable, which encoding strategy is structurally optimal,
and the aggregate complexity class of the model. The diagnostic
is a "look before you leap" version of the rewrite.
