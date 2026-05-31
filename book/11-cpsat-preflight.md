# Chapter 11 — CP-SAT pre-flight: making your existing solver faster

The previous two chapters showed the framework replacing
existing systems — Monte Carlo simulators in Chapter 9, MIP
solvers in Chapter 10. This chapter shows something different:
the framework working *alongside* an existing system, making
it faster without replacing it.

The runnable example lives at
[`book/examples/11_cpsat_preflight/`](examples/11_cpsat_preflight/).

## The scenario

Imagine you work at a small but successful constraint-
satisfaction shop. Your team builds applications on top of
CP-SAT — Google's open-source constraint programming solver
that's part of OR-Tools. You like CP-SAT. It's free, it's well
maintained, it handles a broad range of problems. You write
your models, you call `solver.Solve(model)`, you get answers
back, usually quickly.

But CP-SAT has a known weakness: certain kinds of constraint —
particularly **cardinality constraints** like `sum(x_i) == k`
— cause the solver's internal data structures to explode. The
solver has to track every subset of variables that could
contribute to satisfying the constraint, and there are
combinatorial-many such subsets. On problems heavy with these
constraints, CP-SAT can take minutes to hours, or just give up
entirely.

You'd like a way to make these specific cases faster *without*
ditching CP-SAT for a different solver. You've invested time
in modelling against CP-SAT; the rest of your codebase
integrates with it; you don't want to rewrite everything.

The framework offers exactly this pattern.

## What the framework does for CP-SAT

The framework reads your CP-SAT model — the actual
`cp_model.CpModel` object that you'd otherwise pass to
`solver.Solve(...)` — and looks for constraints it knows how
to rewrite into a structurally cheaper form. Specifically, it
recognises *rank-explosive* constraints (cardinality, certain
all-different patterns) and rewrites them using auxiliary
boolean variables in a way that's mathematically equivalent
but structurally rank-1.

After the rewrite, the new model is still a `cp_model.CpModel`.
You hand it to the same CP-SAT solver you were going to use.
The solver runs faster, because the rank-explosive constraints
are gone — replaced by a structurally simpler form that
CP-SAT's internals can handle in linear time.

The framework provides two methods:

```python
result = sc.rewrite_cpsat_model(model)
# result.rewritten_model    — the new, structurally cheaper model
# result.helped             — True if any constraint was rewritten
# result.help_reason_text   — human-readable explanation
```

And, for safety:

```python
verify = sc.verify_cpsat_rewrite(model, result, enumeration_limit=10000)
# verify.equivalent          — True if the rewrite preserved the feasible set
# verify.n_original_solutions — number of solutions in the original model
```

The verification step is brute-force and works only on small
models, but it's an excellent safety check on test instances
before you commit to the rewrite in production.

## A worked example

Consider a small constraint problem: you have 10 boolean
variables and a single constraint `sum(xs) == 5`. (This is
artificially small; real problems have many constraints, of
which only some are rewritten.)

The naive CP-SAT formulation looks like:

```python
from ortools.sat.python import cp_model

model = cp_model.CpModel()
xs = [model.NewBoolVar(f"x{i}") for i in range(10)]
model.Add(sum(xs) == 5)
```

CP-SAT will solve this. For 10 variables it'll be fast. For
50 variables, slower. For 500 variables, slow enough to notice.

Now run the rewrite:

```python
from structural_computing import StructuralComputer

sc = StructuralComputer()
result = sc.rewrite_cpsat_model(model)

print(result.helped)
# True

print(result.help_reason_text)
# "Rewrote 1 constraint(s) to time-slot rank-1 form; added 40
#  auxiliary boolean(s)."
```

The framework has identified the cardinality constraint,
recognised that it's rewritable, and produced a new model with
the constraint replaced by a rank-1 form. The new model has
the original 10 variables plus 40 auxiliary variables.

If 40 auxiliary variables sounds like a lot for a 10-variable
constraint, remember the *point* of the rewrite: the original
constraint was rank-explosive — its rank scaled badly with the
problem size. The rewritten form has rank 1, which scales
linearly. As your problem grows, the auxiliary-variable
overhead grows as `O(n · k)` (where `k` is the cardinality
bound), but the solver's effort to handle the constraint
**drops**, often by orders of magnitude. The trade is "a few
more variables now, much faster solve later". On the small
example here that trade is invisible; on production models
with hundreds of variables it can be transformative.

You verify the rewrite preserves the feasible set:

```python
verify = sc.verify_cpsat_rewrite(model, result, enumeration_limit=1000)
print(verify.equivalent)             # True
print(verify.n_original_solutions)   # 252
```

The verification confirms both models have the same 252
satisfying assignments on the original variables.

Now solve the rewritten model with the regular CP-SAT solver:

```python
solver = cp_model.CpSolver()
status = solver.Solve(result.rewritten_model)
```

The solver handles the rewritten model more efficiently. On
small examples the difference is tiny. On real problems with
many variables and multiple rewritable constraints, the
speedup can be substantial.

## The "helped: bool" pattern

The framework reports an explicit boolean `helped`. This is
the user-facing pattern for integrating the framework as a
pre-flight layer:

```python
result = sc.rewrite_cpsat_model(model)

solver = cp_model.CpSolver()
if result.helped:
    print(f"Solver getting rewritten model: {result.help_reason_text}")
    status = solver.Solve(result.rewritten_model)
else:
    # Honest stop: framework couldn't help. Solve the original.
    print(f"No rewrite available: {result.help_reason_text}")
    status = solver.Solve(model)
```

The `helped: False` case is just as important as the `helped:
True` case. The framework tells you when it can't help; you
run the original solver. No silent failure. No "the framework
returned something but it was useless".

In a production pipeline, you'd typically log both branches
so you can see how often the framework helps on your specific
workload. Over time, this lets you make data-driven decisions
— "60% of our daily jobs benefit from the rewrite, average
2× speedup on those" — that justify (or don't justify)
keeping the pre-flight layer in.

## What kinds of constraints get rewritten

As of v1.1.0, the framework recognises:

- **Cardinality** constraints (`sum(x_i) == k`,
  `sum(x_i) <= k`, etc.).
- Some **all-different** patterns over small domains.
- Boolean **at-most-k** and **at-least-k** patterns.

The catalogue is expanding as more rank-explosive patterns are
characterised and added to the rewrite engine. Future versions
will recognise more constraint types.

You can run the diagnostic without doing the rewrite, if you
just want to know what would be rewritten:

```python
diagnostic = sc.diagnose_constraints(my_constraint_specs)
print(diagnostic.recommended_encoding)
print(diagnostic.aggregate_complexity_class)
print(diagnostic.reasoning)
```

The diagnostic reports, in plain language, which encoding
strategy is structurally optimal for your specific constraint
set.

## Why this is interesting

Most "make my CP-SAT faster" advice is one of three flavours:

1. **Hardware**: more CPU, more memory.
2. **Constraint reformulation by hand**: read papers, learn
   modelling tricks, hand-tune your model.
3. **Buy Gurobi**: commercial MIP solvers are sometimes faster.

The framework's pre-flight pattern offers a fourth option: a
*structural rewriter* that hand-tunes specific constraint
types automatically, while leaving you on CP-SAT. The total
cost is the time it takes to integrate the pre-flight layer
(a few hours), and the rewriter itself is free.

For pipelines where most of the runtime is in CP-SAT, the
pre-flight layer is a free speedup on the rewritable cases.
For pipelines where CP-SAT is fine, the layer honest-stops
and you lose nothing.

## A note on integration patterns

There are two main patterns for integrating the framework as
a CP-SAT pre-flight layer.

**Pattern 1 — Eager rewrite.** Every time you build a model,
you immediately pre-flight it before solving:

```python
def solve_my_problem(inputs):
    model = build_cpsat_model(inputs)
    result = sc.rewrite_cpsat_model(model)
    solver = cp_model.CpSolver()
    if result.helped:
        return solver.Solve(result.rewritten_model)
    return solver.Solve(model)
```

This is the simplest integration. You add three lines
(`result = ...`, `if result.helped: ...`, `else: ...`) and the
pre-flight is on. It costs a small amount of pre-flight time
even on problems that don't benefit, but the cost is tiny
compared to the average solver run.

**Pattern 2 — Conditional rewrite.** If you suspect only some
of your model classes benefit, you pre-flight only those:

```python
def solve_my_problem(inputs):
    model = build_cpsat_model(inputs)
    if has_cardinality_constraints(inputs):
        result = sc.rewrite_cpsat_model(model)
        if result.helped:
            return cp_model.CpSolver().Solve(result.rewritten_model)
    return cp_model.CpSolver().Solve(model)
```

The wrapper `has_cardinality_constraints` is application-
specific; you decide when to pre-flight based on what you
know about your model class.

In practice, Pattern 1 is fine for most use cases. The
pre-flight is cheap; honest stops are fast; the wins on
rewritable constraints are large.

> **A note on the example's scale.** The runnable example
> in [`book/examples/11_cpsat_preflight/`](examples/11_cpsat_preflight/)
> uses 8 boolean variables with a single cardinality constraint
> (`sum(xs) == 4`). At that size, both the original and the
> rewritten CP-SAT models solve in milliseconds, so the example
> doesn't *demonstrate* a speedup — it demonstrates the
> *mechanism*: the framework reads your model, identifies a
> rewritable constraint, produces an equivalent model, and you
> can verify equivalence by enumeration. The chapter's
> argument about CP-SAT speedups applies at production scale
> (hundreds of variables, multiple rewritable constraints),
> where the rank-explosive cost CP-SAT pays on the original
> formulation becomes the bottleneck. On the example's tiny
> 8-variable model, the framework adds 40 auxiliary booleans
> for a model that wasn't bottlenecked in the first place; on
> a production 1,000-variable model, the same rewrite pattern
> shifts the solver's work from exponential-in-the-cardinality-
> bound to linear. The example proves the framework works; the
> chapter's economics describe where it matters.

## What this chapter taught you

1. **The framework can integrate with existing solvers** as a
   pre-flight layer, not just replace them. The
   `rewrite_cpsat_model` method takes a CP-SAT model and
   returns a structurally cheaper equivalent.
2. **The `helped: bool` pattern is first-class.** You branch
   on it explicitly. The honest stop is part of the API.
3. **Verification is built in.** On small instances you can
   confirm the rewrite preserves the feasible set; on
   production instances you can deploy with confidence.

We've now seen all three worked-example patterns:

- **Replacement** (Chapter 9: Monte Carlo simulator → exact
  framework call).
- **Optimisation** (Chapter 10: MIP timeout → polynomial-time
  framework call).
- **Pre-flight** (Chapter 11, this chapter: existing solver
  gets faster via framework rewrite).

Part IV is about everyday patterns — how to read the answers
the framework returns, how to wire the framework into existing
pipelines, and how to choose between the framework and other
tools (MIP, CP-SAT, Monte Carlo) when you have a new problem
in front of you.
