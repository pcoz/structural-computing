# Chapter 8 — Honest stops: when "no" is the most valuable answer

I want to spend a whole chapter on something that, on the
surface, sounds like a limitation. The framework refuses to
answer some questions. When it does, it tells you so explicitly.
It calls this an **honest stop**.

By the end of the chapter you'll understand why this is one of
the framework's most valuable features. Not a workaround for
limitations. A *feature*.

## The pattern, restated

A typical interaction with the framework looks like:

```python
answer = sc.count_matchings(my_graph)
```

If the framework can compute the answer exactly, it returns
an integer. Done.

If it can't, it raises an exception:

```python
NotInFamily: graph is T5 (non-planar); no exact path in the
framework. The classification's `meters` show n_vertices=12,
n_edges=66, planar_check=failed. Consider: NetworkX brute force
at small n; CP-SAT for larger n; Monte Carlo if the question
is genuinely probabilistic.
```

The exception is rich. It has the classification attached. It
explains *why* the framework stopped. It suggests where to go
next.

This is the honest stop. The framework refuses to *guess*.

## Why this is unusual

Most software you use doesn't behave this way. Most software,
when it can't do exactly what you asked, does something
approximate and doesn't tell you. This is so widespread that
we don't even notice it.

Some examples:

**A Monte Carlo simulator.** You hand it a problem. It runs
some samples. It returns an estimate with a confidence
interval. You don't know whether the confidence interval is
trustworthy unless you trust the convergence diagnostics. Many
people don't check them. The answer looks like a real number.
It might or might not be accurate.

**A neural network.** You hand it an input. It produces an
output. The output is *always* a real number — even if the
input is gibberish, even if the network has never seen
anything like it, even if the network is poorly trained. There
is no internal mechanism that says "I'm not sure about this
one; you should look at it manually". You have to build that
on top.

**A linear solver.** You ask it to solve `Ax = b`. If the
matrix is singular, you might get NaN or a hugely inaccurate
answer depending on numerical implementation details. Often
you don't know unless you check after the fact.

**A web service.** You query it. If it can't get an answer in
time, it usually returns *some* answer, possibly stale,
possibly partial, possibly approximate. The "graceful
degradation" pattern is praised by engineering folklore. But
graceful degradation is just *not telling you when you got an
inferior answer*.

In all of these cases, the system produces output even when
it shouldn't. The result is that you, the user, can't tell
the difference between "real answer" and "approximation
that's silently breaking". This is a major source of bugs in
real software systems. The output of an approximate system
flows into a downstream system that treats it as exact, and
something goes wrong months later, often expensively.

The framework refuses to participate in this. If it can't
answer exactly, it refuses to answer at all.

## Why this matters in regulated industries

This honest-stop behaviour is especially valuable when the
answer feeds into a *regulated* downstream process — a
regulator-facing report, an audit, a board-level decision, a
court case.

Compare:

**Without honest stops.** Your Monte Carlo simulator runs.
Maybe it converged; maybe it didn't. Maybe the random seeds
happened to land in a representative region of the space;
maybe they didn't. The simulator outputs a number. A
regulator-facing report quotes that number. Later, someone
questions the report. *Was the simulator's convergence
threshold appropriate? Was the seed used representative?
Were the underlying inputs in the simulator's known-good
range?* Answering these questions costs hundreds of hours of
forensic work.

**With honest stops.** Your framework call ran. Either it
returned an exact number (bit-identically reproducible
across machines, computed by a documented algorithm) or it
raised a `NotInFamily` exception with a structured
explanation. If you have a number, you have a number you can
defend. If you have an exception, you have documentation of
what wasn't possible.

For regulator-facing work, honest stops are not optional —
they're *essential*. A number you can't defend is worse than
no number.

## Why this matters for engineering teams

Honest stops also fundamentally change *how teams use the
framework* in their pipelines.

In a typical Monte Carlo pipeline, you write code that
*always* runs to completion. The pipeline produces results.
The results flow downstream. The pipeline assumes the results
are roughly correct. Validation happens later, in a separate
testing layer that someone might or might not maintain.

With the framework's honest stops, you write code that
*either succeeds exactly or fails loudly*. The pipeline either
produces a defensible answer or it produces an explicit
exception that propagates back to whoever needs to look at
it. There's no silent failure mode. There's no "results are
wrong but the pipeline says they're fine".

This forces a discipline:

- **Either** your inputs are in the framework's structural
  family, in which case you get exact answers, and you don't
  need a testing layer to second-guess them.
- **Or** your inputs aren't, in which case you find out
  immediately — at integration time, not at deployment time —
  and you can choose how to handle the case explicitly.

In real codebases, this difference shows up as: framework-
based pipelines have fewer bugs and the bugs they do have
are easier to find. The honest stop is the loud failure
mode that turns silent corruption into catchable exceptions.

## A real example of an honest stop in action

Let me show you what an honest stop actually looks like in
code, in a slightly more nuanced case.

Suppose you have a graph that *seems* planar but actually
isn't — it has one or two edges that cross. Your graph
might come from a piece of source data that mostly produces
planar graphs but occasionally produces something with extra
edges. Maybe a user pasted in a CSV by accident.

You write:

```python
sc.count_matchings(my_graph)
```

The framework's classifier runs. It probes the graph. It
discovers the extra edges. It reports:

```python
# NotInFamily: graph is T5 (non-planar); no exact path in
# the framework. The classification's meters show:
#   n_vertices=16, n_edges=27, planar_check=failed,
#   non_planar_witness=("kuratowski_K5_minor", [list of nodes])
# Consider:
#   - HybridDecomposition with extra_edges=[...] if you can
#     identify a small set of "extra" edges whose removal
#     makes the graph planar (sc.count_matchings_hybrid).
#   - NetworkX brute force at small n.
#   - CP-SAT for larger n.
```

The exception tells you:

1. *Why* the framework stopped (the graph is non-planar).
2. *Where the non-planarity comes from* (the
   non-planar witness — specific nodes that violate
   planarity).
3. *Three concrete alternatives* (Hybrid decomposition,
   NetworkX, CP-SAT), in approximate order of preference.

You can act on this. You can look at the witness, see if
there are one or two "extra" edges you can remove, and try
`sc.count_matchings_hybrid(graph, extra_edges=[...])`. Or
you can pivot to a different tool.

The point: the honest stop is *actionable*. It doesn't just
say "I can't do this". It says "here's why, and here's where
to look next".

## Two failure modes that honest stops prevent

Two specific kinds of failure the honest-stop pattern
prevents.

### Failure mode 1: silent degradation under input drift

Your pipeline works fine for years. Then someone changes the
upstream data format slightly. The new inputs are *almost*
the same shape as before, but with a small structural
difference — say, an added edge here and there.

In a non-honest-stop system, the pipeline would continue
running. It would produce numbers that *look right* but are
actually computed on the wrong shape. Downstream consumers
would never know. The error would surface, weeks or months
later, as some inexplicable inconsistency in a report.

In the framework, the moment the inputs drift out of the
structural family, the next call raises `NotInFamily`. You
notice immediately. Your CI catches it before deployment.
The pipeline either gets fixed (Hybrid decomposition, perhaps,
to handle the new structure) or gets honest-stopped with a
documented reason.

This is one of the framework's quiet superpowers. It catches
input-drift bugs at runtime instead of letting them poison
your downstream pipelines.

### Failure mode 2: silently wrong cross-team integration

You're building a pipeline that uses someone else's library
underneath. The other library does something approximate but
doesn't document that clearly. You assume it's exact. You
build your pipeline assuming the other library's answers are
trustworthy. Some quarter later, someone notices the
discrepancy. It's traced back to the other library's
approximation. The bug-hunt costs many hundreds of hours.

The framework's API makes this kind of integration mistake
much harder. Either the framework's method returned an exact
answer (and you can trace its computation through the
classification + leaf-evaluator chain to verify), or it
raised `NotInFamily`. There's no "the framework returned a
number but the number might be approximate" middle ground.

## How to use honest stops in your own pipelines

When you build a system on top of the framework, you should
embrace the honest-stop pattern explicitly. Here's a typical
shape:

```python
from structural_computing import StructuralComputer, NotInFamily

sc = StructuralComputer()

def daily_reliability_report(graph):
    try:
        p = sc.tail_probability(graph, p_fail=0.01)
        return {
            "answer": p,
            "method": "structural-computing exact",
            "auditable": True,
        }
    except NotInFamily as e:
        # We didn't get an exact answer.
        # Decide explicitly what to do.
        return {
            "answer": None,
            "method": "honest-stop; structure mismatch",
            "auditable": False,
            "reason": e.classification.reasoning,
            "tier": e.classification.tier,
            "suggested_alternatives": ["NetworkX MC fallback"],
        }
```

This pattern — try the framework, catch the honest stop,
record what happened — is the right way to structure
pipelines. It surfaces the honest-stop case as a
*first-class outcome*, not as a runtime error. Downstream
consumers can branch on `auditable: True/False` and decide
what to do.

You might think "but I just want a number; the honest-stop
case is a hassle". In the short term, yes. In the long term,
the explicit handling of the honest-stop case is what makes
the pipeline robust to input drift, easy to audit, and
defensible to regulators.

## In summary

The framework refuses to answer questions it can't answer
exactly. Instead, it raises a structured exception explaining
why. This is called an honest stop.

Honest stops feel like a limitation when you first encounter
them. They aren't. They're the framework's defence against
the silent-approximation failure mode that bedevils most
real software systems. In regulator-facing work, in
audit-sensitive pipelines, in production systems with input
drift — the honest stop is the framework's most valuable
feature.

This concludes Part II — the mental model. You now know:

- **What an admissible set is** (Chapter 6) — the set of
  configurations satisfying your rules.
- **How the classifier works** (Chapter 7) — the framework's
  brain that picks the right algorithm.
- **Why honest stops matter** (Chapter 8, this chapter) — the
  framework's refusal to silently approximate.

Part III opens with worked examples. We'll take real problems
— problems you might recognise from your own work — and watch
the 100,000-to-10 collapse happen.
