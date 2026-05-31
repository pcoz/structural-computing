# Preface — Why this book exists

There is a software pattern, present in tens of millions of lines
of code across the world, that goes roughly like this:

> A question about a combinatorial system — *how many ways can
> this fail?*, *which configuration is more reliable?*, *what's
> the cheapest schedule?*, *given these constraints, how many
> assignments satisfy all of them?* — gets answered by a Monte
> Carlo simulator. The simulator samples, the samples are
> aggregated, confidence intervals are computed, the answer is
> reported as a range.

Sometimes that's the right thing to do. The question is
genuinely continuous. The system is genuinely too complicated to
analyse exactly. The Monte Carlo simulator is the best we have.

But often — much more often than the industry realises — the
question has an **exact** answer, computable in **polynomial
time**, and the Monte Carlo machinery isn't needed at all.

That gap is what this book is about.

## The 100,000-to-10 claim

The catastrophe modelling industry (RMS, AIR, EQECAT) maintains
millions of lines of C++ to estimate insurance losses by
sampling. The exact answer, for the planar portions of the
geographic hazard, is computable in polynomial time. The whole
sampling apparatus exists because the field decided, a long time
ago, that exact computation was intractable.

It isn't. Not for this shape of problem. And once you delete
the sampling machinery, the question itself fits in just a few
lines using today's framework:

```python
from structural_computing import StructuralComputer
sc = StructuralComputer()

# `hazard_edges` is the list of (component_a, component_b) tuples
# describing which hazard components are connected on the
# geographic map; per-edge failure probabilities live in `weights`.
loss_dist = sc.tail_probability(hazard_edges, p_fail=0.005)
print(loss_dist)
```

That's the form. Once you've got that, *everything else* is
gone — the sampling loops, the variance-reduction tricks, the
seed management, the confidence-interval computation, the
parallelisation infrastructure. All vanishes. Only the question
remains.

The aspiration — that this is *literally* one line per business
question via a catastrophe-modelling-specific DSL on top of the
framework — is the **year-10 vision** discussed in Chapter 16.
Today you'd write a few extra lines to parse the input and
shape it into the framework's edge list, but the **simulator
itself is gone**. The collapse is real now, not in fifteen
years.

> **Roadmap tracking.** The catastrophe-modelling DSL is tracked
> as a v1.2.0+ item in the project's roadmap; see
> `admissibility-geometry/NEXT.md` § "Open follow-ons" → item 1a
> ("Catastrophe-modelling DSL"). When that DSL ships to PyPI,
> this preface paragraph will be updated to use the real
> one-liner form and drop the "year-10 vision" framing.

## What this book is

A practitioner's guide to the framework — `structural-computing`
on PyPI — that delivers the underlying paradigm. The book
covers:

- **Why the 100,000-to-10 collapse is real** (not hyperbole) for
  the classes of problem it applies to.
- **When it applies** — concrete tests you can apply to your own
  codebase to know if the paradigm helps you.
- **How to write the 10 lines** — three worked examples in
  reliability, optimisation, and CP-SAT integration.
- **When the framework honestly stops** — and why that's a
  feature, not a limitation.

## What this book is not

- It is not a textbook on matchgate theory. The book reaches for
  the underlying math only when explaining why an algorithm
  works; it never makes you do the math yourself.
- It is not a survey of every algorithm in the package. The
  reference docs at [`docs/reference/api.md`](../docs/reference/api.md)
  have that.
- It is not a sales pitch. The framework's honest stops are a
  major feature; if your problem doesn't fit the structural
  shape, the framework will tell you so, and this book will
  show you when that's likely.

## Who you are

The book has been written with **three audiences** in mind, and
each gets a slightly different reading path:

1. **Software engineers** who've run into the same Monte Carlo
   / MIP / CP-SAT pattern enough times that you suspect there
   must be a better way. You've maintained a Monte Carlo
   simulator that takes twelve hours to converge on an answer
   your boss needed yesterday. You've timed-out a MIP solver
   on a scheduling problem that "felt" easy. You've watched a
   CP-SAT pipeline inflate a model with auxiliary variables
   until the solver gave up. The book is the answer to those
   experiences. **Read the whole thing.**

2. **Business analysts** who don't write production code but
   need to understand what your engineering team would buy
   from this framework, and how much it could save. The book
   has a one-page business case (Chapter 1a) and three later
   chapters that quantify the industry-level economics
   (Chapter 15). The paradigm itself (Chapter 3) is presented
   without math notation, in five plain-English words.
   **Read the preface, Chapters 1, 1a, 3, 4, 5, and 15.** Skip
   the code blocks; you don't need them. The reading takes
   about two hours and gives you the full business picture.

3. **CTOs and VPs Engineering** who want to know whether the
   framework is a *strategic build-versus-buy reframing*
   candidate for your stack. Read Chapter 1 (Sara's company),
   Chapter 1a (the business case), Chapter 4 (will the
   framework help my problem?), and Chapter 15 (three
   industries that change). About 45 minutes; gives you enough
   to make a five-minute decision about whether to commission
   a pilot.

For all three audiences, the key honest message is the same:
the framework gives exact answers when it can, refuses
honestly when it can't, and the "refuses honestly" case is a
feature, not a limitation. Half the book is about the value
it adds; the other half is about how to recognise when it
isn't relevant.

## What you'll have at the end

By the end of the book you'll be able to:

1. Look at a problem you'd otherwise solve with Monte Carlo and
   recognise, in seconds, whether the framework applies.
2. Write the 10-line form of a problem you'd previously have
   written 1,000 lines of imperative code for.
3. Wire `structural-computing` into an existing pipeline as a
   diagnostic or pre-flight layer alongside MIP / CP-SAT.
4. Read the audit trail the framework emits — every dispatch
   decision, every reduction, every honest stop — and explain
   it to a regulator, an auditor, or your team.

## The version this book covers

Everything in this book is current to **`structural-computing
v1.1.0`** (and `holant-tools >= 0.7.0`). The API is semver-
protected — see [`docs/STABILITY.md`](../docs/STABILITY.md).
Code in this book that uses Stable-tier symbols will work
unchanged through any v1.x release.

Let's begin.
