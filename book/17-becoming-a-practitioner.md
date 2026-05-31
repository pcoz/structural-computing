# Chapter 17 — Becoming a practitioner

You're at the end of the book. The first sixteen chapters
gave you the conceptual model, the worked examples, the
patterns. This chapter is about what comes next — concretely.
If you want to become someone whose default reach is the
framework's declarative form rather than a Monte Carlo
simulator, here's how.

The chapter is in five parts:

1. **The first week.** What to do in your first seven days.
2. **The first project.** Picking a problem to actually solve.
3. **The first failure.** When the framework honest-stops on
   you, what to do.
4. **Bringing it to your team.** How to share what you've
   learned without sounding like an evangelist.
5. **Staying current.** Where the community lives, how to
   keep up.

## 1. The first week

You don't need a week. You need an afternoon. But for the sake
of structure, here's what to do across seven days.

### Day 1 — install and run the tutorial

```bash
pip install structural-computing
```

Then open the tutorial at
[`docs/tutorial/getting-started.md`](../docs/tutorial/getting-started.md)
and work through the six steps. The whole thing takes 30
minutes. Don't just read it — *type the code* and run it.
Type-don't-paste matters; your fingers learn faster than your
eyes.

### Day 2 — run the worked examples

The three book examples at
[`book/examples/`](examples/) are runnable. Spend an hour
running them, modifying the inputs, changing parameters,
seeing what happens. The point isn't to memorise specific
function signatures. The point is to develop *intuition*
for how the framework behaves.

If you make an example crash, *good*. The crash teaches you
something. Read the exception. Try the four-question
diagnostic from Chapter 4 on the input that caused the crash.
Almost always, the diagnostic will tell you why.

### Day 3 — read the stability contract

The framework's API is large. Knowing which parts are *stable*
saves you from the trap of building on something that might
change.

Read [`docs/STABILITY.md`](../docs/STABILITY.md). It tells you
which symbols are semver-protected (the Stable tier), which
are evolving (Experimental), and which you should never touch
(Internal).

For day-to-day code, you'll use mostly the Stable tier. For
custom extensions, you might touch the Experimental tier.
Knowing the distinction up front saves you future pain.

### Day 4 — run the classifier on your own data

Take some real data from your job. A graph you work with. A
constraint set. A workflow definition. Run
`sc.classify(...)` on it. Read the classification.

Most readers, doing this, get one of two reactions:

- *"Oh — my data is T2! I had no idea the framework would
  apply."* Great. You've found your first candidate.
- *"My data classifies as T5. The framework can't help here
  directly."* Also great. You now know precisely where the
  framework's boundary is for your work.

Either reaction is useful. Don't skip this step.

### Day 5 — pick a candidate problem

If you found T2 (or T0, T1, T3, T4) data on Day 4, you have a
candidate. Pick the smallest, lowest-risk problem at your job
that involves that data. *Smallest, lowest-risk.* Not the
most important. Not the most visible. The smallest.

The smallness matters. Your first framework integration will
have surprises. You want them to surprise you on a small
contained problem, not a public-facing one.

### Day 6 — write the integration

Spend a few hours writing the integration. Follow the
patterns in Chapter 13. Adapter to convert your data;
framework call; handler to convert the result.

If you get stuck — the framework's error message is unclear,
the result doesn't match what you expected, you can't figure
out the right input shape — go back to the tutorial and
re-read the relevant step. Most issues at this stage are
input-shape issues; the framework wants graphs in a specific
form.

### Day 7 — compare against your existing system

Run your new framework integration in parallel with whatever
you used to use. Compare the results. Investigate any
disagreements.

If the framework and the existing system agree (within the
existing system's confidence interval, if it's Monte Carlo),
great — you've shown the framework works on real data.

If they disagree, *don't assume the framework is wrong*. The
framework is exact; the disagreement is more often a bug in
the existing system or in your input translation. Track down
the root cause before deciding.

By end of Day 7 you've done the early-adopter cycle:
installed, tutorialed, exampled, classified, candidated,
integrated, compared. You're ready to start using the
framework in earnest.

## 2. The first project

Your first real project isn't a tutorial. It's a real piece
of work where the framework either delivers a concrete win
or honestly tells you it can't.

The best first projects share four properties:

- **Small scope.** A specific question on a specific dataset.
  Not "rewrite the reliability pipeline" — "answer one
  specific question with the framework, the same way the
  existing pipeline answers it".
- **Honest fallback.** If the framework honest-stops, you
  have a working alternative (the existing system you didn't
  ditch).
- **Real stakes.** Not a toy. A question your team actually
  cares about. Toys don't generate intuition.
- **Visible result.** The result is something you'll
  actually look at and judge. A dashboard number, a report
  field, a decision input.

The intersection of these four criteria is your first
project. It might be a single function in your codebase —
maybe one helper function that computes a reliability
estimate — being rewritten to use the framework while
everything around it stays.

When you've done that and it works, do the second project.
This time pick something slightly bigger. Keep the same
four properties.

After three or four projects you'll have built up real
intuition. You'll be able to glance at a problem and have a
strong sense of "framework will help here" or "framework
won't help here" without running through Chapter 4's
diagnostic explicitly. The diagnostic becomes intuition.

## 3. The first failure

Sooner or later, the framework will honest-stop on a problem
you wanted it to handle. What now?

A few things.

### First: read the classification carefully

The honest-stop exception carries the full classification.
The `tier` tells you the framework's category for your
problem. The `reasoning` field, in plain English, explains
why. The `meters` field has detailed measurements.

Many "the framework honest-stopped on me" reactions turn out
to be input-shape issues — the data is *almost* in the
expected shape but not quite. The classification reveals the
specific structural property that failed. Often you can fix
the input.

### Second: look at the suggested alternatives

The honest-stop exception suggests alternative tools. They're
not arbitrary suggestions. They're the tools the framework's
maintainers think would handle your specific case well.

If the suggestion is "NetworkX brute force at small n", and
your problem is small, follow it. If the suggestion is
"CP-SAT", read Chapter 11 about how to integrate CP-SAT with
the framework as a pre-flight.

### Third: file a clear bug report if you think the framework should have helped

If you genuinely believe the framework should have handled
your case — if the structural shape *looks* like one the
framework supports, but it honest-stopped — file a bug
report. Include the classification output, the input that
triggered it, and what you expected.

The maintainers care about these reports. The framework
grows by users encountering edge cases and surfacing them.
The honest-stop pattern is robust precisely because the
maintainers want to know when it fires incorrectly.

### Fourth: don't fight the honest stop

The temptation, at first, is to find a way to make the
framework give *some* answer. Resist. The honest stop is
information. Your problem doesn't fit the framework's shape.
The right move is to use a tool that does fit (Chapter 14),
not to coerce the framework.

If you make a habit of overriding honest stops, you'll start
introducing the silent-approximation failure mode the
framework was designed to prevent.

## 4. Bringing it to your team

This is the political part. You've used the framework on a
few personal projects. You see it working. You want your team
to use it too. How do you do that without sounding like
someone who reads too much science fiction?

### Talk in their language

Don't lead with "matchgate-Holant tractability" or
"semiring-generic dispatch". Lead with:

- "Our reliability simulator takes 4 hours; this gives the
  same answer in 3 seconds."
- "Our CP-SAT pipeline times out on these specific cases;
  this rewrites them to a form CP-SAT handles fast."
- "Our MIP solver's Gurobi licence costs $10k/year; for
  these specific problems, this is free and faster."

Concrete numbers. Concrete savings. Concrete pain points
your team already feels.

### Show, don't sell

Don't write a slide deck. Run your existing integration in
front of them. Side by side with the current tool. Let them
see the framework return the same answer (within the
existing tool's confidence interval) in a fraction of the
time.

A short demo with real data does more than a long
presentation. People believe what they see.

### Let the team find their own use cases

After your demo, don't push assignments. Just say "if anyone
has a problem they'd like to try this on, I'm happy to help
wire it up". Wait. Some people will come to you. Those people
are your early-internal-adopters. Help them succeed. Their
wins become advocacy without your having to advocate.

### Embrace the honest stops in team conversations

When the framework honest-stops on someone's problem, *say
so explicitly*. "This doesn't fit the framework — the
classification says T5 — we should stick with the existing
approach for this one." That kind of honest no-this-doesn't-
apply statement builds enormous credibility. It tells the
team you're using the framework where it helps, not
worshipping it.

The teams that adopt the framework most quickly are the ones
where the early advocate is *also* publicly honest about
where it doesn't apply. The framework's worst enemy is an
over-zealous advocate.

## 5. Staying current

The framework is being developed in public. Here's where to
follow it.

### The GitHub repos

- [`pcoz/structural-computing`](https://github.com/pcoz/structural-computing)
  — the main user-facing library.
- [`pcoz/holant-tools`](https://github.com/pcoz/holant-tools)
  — the mathematical engine.
- [`pcoz/structural-computing-bench`](https://github.com/pcoz/structural-computing-bench)
  — the calibration companion.

Star them, watch them, subscribe to releases. Changes ship
on PyPI; release notes live in each repo's `CHANGELOG.md`.

### The docs

The [`docs/`](../docs/) folder evolves as the package does.
New how-to recipes, new explanation pages, new reference
material get added over time. The book itself
(this thing you're reading) is in [`book/`](.).

### Reading mathematical foundations

If you find yourself curious about why specific algorithms
work, the references in
[`docs/architecture.md`](../docs/architecture.md) point at
the underlying mathematics. The original papers are accessible:

- **FKT** (Fisher-Kasteleyn-Temperley, 1961) for planar perfect
  matching counting.
- **Cai-Lu 2011** for the holographic-algorithm framework
  underlying matchgate identities.
- **Galluccio-Loebl 1999** for the bounded-genus extension.

You don't need to read these to use the framework. They're
there if you want to understand *why* the algorithms work
beyond what the docs explain.

## A final note

The framework is built by people who think the paradigm has
legs. The book is built by the same people who think the
paradigm has legs. We could be wrong. Paradigm shifts that
look obvious in retrospect were uncertain at the time. SQL
was obviously going to win — *in retrospect*. In 1979 it was
a niche tool from a small company.

We don't know yet whether this framework will be the SQL of
declarative structural computation, or one of the prior
attempts that didn't reach industry default.

What we do know:

- The mathematics is real. The algorithms are exact and
  polynomial-time on the problems they handle.
- The codebase is small enough to read end-to-end. There are
  no hidden assumptions, no proprietary parts, no walled
  gardens.
- The early-adopter wins are available today, regardless of
  what happens in the next decade. You don't have to bet on
  the long curve to capture short-term value.

If you've read this far, you're in a position to be one of
the early adopters. Whether you take that position is up to
you.

Welcome to the paradigm. Use it well, refuse it honestly when
it doesn't fit, and let us know what you build.

— The end of the book.
