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
the sampling machinery, the question itself fits in about
ten lines:

```python
hazard = pipeline.load_hazard_graph("california_seismic.geojson")
portfolio = pipeline.load_exposure("treaty_2024.parquet")
loss_dist = pipeline.exact_loss_distribution(
    hazard, portfolio,
    quantiles=[0.99, 0.995, 0.999],
)
print(loss_dist.tail_summary())
```

That's the form. Once you've got that, *everything else* is
gone — the sampling loops, the variance-reduction tricks, the
seed management, the confidence-interval computation, the
parallelisation infrastructure. All vanishes. Only the question
remains.

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

You're a software engineer or analyst who's run into the same
pattern enough times that you suspect there must be a better
way. You've maintained a Monte Carlo simulator that takes
twelve hours to converge on an answer your boss needed
yesterday. You've timed-out a MIP solver on a scheduling
problem that "felt" easy. You've watched a CP-SAT pipeline
inflate a model with auxiliary variables until the solver gave
up.

This book is the answer to those experiences for the subset of
problems where the answer is "yes, there's a better way, and
here it is."

For the problems where the answer is "no, the framework can't
help you" — and there are plenty — the book will help you
recognise those quickly too. That's worth the read on its own.

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
