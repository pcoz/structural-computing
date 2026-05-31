# Declarative Structural Computing — A Practitioner's Guide

**A book on a new computing paradigm.** When the imperative
"how" can be separated from the declarative "what," entire
codebases shrink. SQL did this for tables. JAX did this for
gradients. This book is about the same move for structured
combinatorial computation — counting, reliability, optimisation,
all on the same machinery.

This is the index. The chapters live in
[`../book/`](../book/) (one file each) plus runnable examples in
[`../book/examples/`](../book/examples/).

---

## Who should read this

You should read this if:

- You write Monte Carlo code for combinatorial questions
  (reliability, rare-tail risk, configuration comparison) and
  suspect there must be a better way.
- You maintain a CP-SAT or MIP pipeline that times out on
  problems that "feel" structured.
- You write scheduling, rostering, or assignment code by hand
  and want to know when it can be replaced with one line.
- You're a business analyst trying to understand what your
  engineering team would buy from this.

You DO NOT need to know matchgate theory, Pfaffians, or Holant
algorithms. The book reaches for them only when needed and only
in passing.

## Table of contents

### Preface
- [Preface — Why this book exists](../book/00-preface.md)

### Part I — The paradigm

- [Chapter 1 — The 100,000-line problem](../book/01-the-100k-line-problem.md)
- [Chapter 1a — The business case, in one page](../book/01a-the-business-case-in-one-page.md)
- [Chapter 2 — The SQL story, retold](../book/02-the-sql-story-retold.md)
- [Chapter 3 — Declarative structural computing in one paragraph](../book/03-the-paradigm-in-one-paragraph.md)
- [Chapter 4 — Will the framework help my problem?](../book/04-when-it-applies.md)
- [Chapter 5 — Five patterns that fit, five that don't](../book/05-five-patterns-that-fit.md)

### Part II — The mental model

- [Chapter 6 — Admissible sets and the questions you can ask them](../book/06-admissible-sets.md)
- [Chapter 7 — The classifier — your tool decides what tool it should use](../book/07-the-classifier.md)
- [Chapter 8 — Honest stops — when "no" is the most valuable answer](../book/08-honest-stops.md)

### Part III — First worked examples

- [Chapter 9 — Network reliability: 1,000 lines of Monte Carlo → 5 lines](../book/09-network-reliability.md)
- [Chapter 10 — Schedule optimisation: from MIP timeout to one-liner](../book/10-schedule-optimisation.md)
- [Chapter 11 — CP-SAT pre-flight: making your existing solver faster](../book/11-cpsat-preflight.md)

### Part IV — Patterns and integration

- [Chapter 12 — Reading the answer (cost, witness, feasibility, audit trail)](../book/12-reading-the-answer.md)
- [Chapter 13 — Wiring structural-computing into existing systems](../book/13-wiring-it-in.md)
- [Chapter 14 — When to use this vs MIP vs CP-SAT vs Monte Carlo](../book/14-when-to-use-what.md)

### Part V — The bigger picture

- [Chapter 15 — Three industries that change](../book/15-three-industries.md)
- [Chapter 16 — Where this goes next](../book/16-where-this-goes.md)
- [Chapter 17 — Becoming a practitioner](../book/17-becoming-a-practitioner.md)

### Runnable examples

The `../book/examples/` folder has runnable examples for each
worked-example chapter:

- [`book/examples/09_network_reliability/`](../book/examples/09_network_reliability/)
- [`book/examples/10_schedule_optimisation/`](../book/examples/10_schedule_optimisation/)
- [`book/examples/11_cpsat_preflight/`](../book/examples/11_cpsat_preflight/)

Each example folder has a runnable `.py` script + a `README.md`
explaining what the example demonstrates and how to run it.

---

## How to read this book

**If you're a business analyst (and not a developer):** read
the preface, Chapter 1, Chapter 1a (the business case),
Chapter 3 (the paradigm in five plain-English words),
Chapter 4 (will it help my problem?), Chapter 5 (patterns that
fit), and Chapter 15 (three industries that change). That's
about half the book and gives you the whole business picture
without requiring you to read Python. Skip the code blocks —
they're there for the developers on your team.

**If you have an hour as a developer:** read the preface,
Chapter 1, Chapter 1a, Chapter 3, and Chapter 9. That's the
paradigm, the business case, and one worked example. You'll
have enough to decide whether the framework is relevant.

**If you have an afternoon as a developer:** add Chapters 10
and 11. That covers all three worked examples — the
imperative-to-declarative move will be concrete in three
different domains.

**If you have a weekend:** read the whole thing. Part II makes
you fluent in the mental model. Part IV teaches you the
day-to-day patterns. Part V is the long-horizon view — where
this paradigm could go in the next decade.

---

## Connection to the rest of the docs

This book is the **narrative** version. For the reference and
API material, see the standard Diátaxis docs at
[`docs/README.md`](README.md):

- [Tutorial](tutorial/getting-started.md) — 30-minute hands-on
  walkthrough (the same ground as Chapters 1–11 but compressed).
- [How-to](how-to/) — recipes for specific tasks.
- [API reference](reference/api.md) — every public method.
- [Stability contract](STABILITY.md) — what's
  semver-protected at v1.x.
