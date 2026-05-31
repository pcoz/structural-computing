# Chapter 16 — Where this goes next

Chapter 2 told you the SQL story: how a paradigm shift moved
through five stages from academic insight to industry default,
each stage taking about three years, the full transition
taking fifteen.

This chapter tells you where the framework's own journey sits
on that timeline, and what each future stage looks like
concretely. The chapter is intentionally honest — some of the
future is speculative, and I'll mark which parts are which.

## Where the framework is today (v1.x)

As of v1.1.0, the framework is a working, semver-protected
PyPI library:

- The **mathematical foundations** in `holant-tools` are
  complete for the core domains (planar matching counting,
  GF(2)-affine constraint sets, tropical optimisation,
  CP-SAT diagnostic surface).
- The **orchestrator and wrapper** in `structural-computing`
  expose ~30 methods covering counting, reliability, witness-
  finding, min-cost optimisation across six instance types,
  and CP-SAT pre-flight.
- The **calibration system** in `structural-computing-bench`
  produces per-machine wall-clock cost models so the
  orchestrator can make informed scheduling decisions.

In SQL terms, this is approximately **Oracle 1979**: a real
commercial-ish library, early adopters using it, the math
underneath established. The full industry hasn't caught up.

## What the next 2-3 years look like (v1.2 — v2.0)

The most concrete additions in the near-term roadmap:

### Refinements to the existing surface

- **Calibration coverage** for the tropical + CP-SAT leaves
  shipped in v1.1.0. The wall-clock cost models are essential
  for production scheduling.
- **Stability tier promotions** as the specific
  implementation classes (HybridDecomposition, PlanarSeparator,
  HolographicBasisPair, etc.) prove themselves stable in
  downstream use.
- **More how-to recipes** in the Diátaxis documentation as
  the early adopters report their use cases.
- **More worked examples** in the book's example folder.

### Capability extensions

- **Streaming-style problems** — currently the framework
  operates on whole problems at rest. Some applications
  (real-time grid monitoring, online ad-allocation) need
  incremental answers as inputs change. The mathematical
  foundations for incremental matching exist; building them
  out is a year's work.
- **Approximate honest-stops** — for problems just outside
  the structural family, return an *approximation with a
  proven error bound* rather than refusing entirely. This is
  more useful than Monte Carlo (the bound is real) but
  honest about the approximation.
- **More semirings** beyond standard, tropical, and
  probability. The mathematical machinery supports more; the
  open question is which ones have practical demand.

### The first domain DSL

The framework today is library-level. To reach the year-10
"10-line form is literally one line" vision, you need a
*domain-specific language* sitting on top of the framework,
where the user writes things like:

```python
catastrophe_loss = analyse_portfolio(
    portfolio="treaty_2024",
    hazard="california_earthquake",
    return_periods=[10, 100, 500, 1000],
)
```

That's the year-10 form. Most users wouldn't see the
framework at all — they'd see the domain DSL, which is
catastrophe-modelling-specific, and the framework would be a
library the DSL calls underneath.

Building one of these DSLs is a year or two of focused work
on a specific domain. The most likely first target is
**workflow systems** (Temporal, Camunda, BPMN). A
`structural-computing-workflows` package, on top of the
core framework, that parses BPMN files and answers questions
like *reachable_terminals*, *rare_failure_modes*,
*single_points_of_failure*, *guard_conflicts* — all in one
or two lines per question.

This is **year-5 to year-6** work. The framework has the
primitives; what's needed is the DSL design and the parsing
adapters for the various workflow formats.

### Likely v2.0

A v2.0 release becomes appropriate when one of the following
happens:

- A breaking API change is justified by major architectural
  evolution (e.g., the streaming layer requires reshaping
  the orchestrator's interface).
- A new domain DSL is mature enough that its inclusion in
  the core package makes sense.
- The Experimental tier of v1.x classes has stabilised and
  enough churn is needed that a major-version bump is more
  honest than minor-bump promotions.

If none of these triggers, v1.x can run for several years on
minor releases. The SQL standard didn't have a "v2.0"-style
break either; it accumulated additions (SQL-86, SQL-89,
SQL-92, ...) over decades.

## What the long-horizon view looks like (years 5-10)

This part is the most speculative. If the paradigm pans out,
here's what the world looks like.

### Domain DSLs become the user-facing layer

Most users don't write `import structural_computing`. They
write `import structural_computing_workflows` or
`import structural_computing_reinsurance` or
`import structural_computing_grid_reliability`. Each domain
DSL is its own package, maintained by domain experts,
calling the core framework underneath.

The user-facing code becomes:

```python
# Reinsurance underwriter
import structural_computing_reinsurance as scr
loss_distribution = scr.tail_loss(
    portfolio="treaty_2024",
    hazard="california_earthquake",
    return_periods=[10, 100, 500, 1000],
)

# Grid reliability engineer
import structural_computing_grid as scg
report = scg.reliability_audit(
    grid="california_iso_2024",
    p_failure_per_line=0.001,
)

# Workflow architect
import structural_computing_workflows as scw
audit = scw.audit(
    workflow="claims_processing.bpmn",
    questions=["dead_states", "rare_paths"],
)
```

Each of these *is* the 10-line form referenced throughout the
book. Today, you'd write them as 15-line raw-framework calls
(see Chapters 9-11). In the domain-DSL era, they're literally
one line each.

### The core framework becomes infrastructure

Just as `numpy` is infrastructure for scientific Python and
nobody much talks about it any more, the framework would
become infrastructure for declarative structural computation.
You'd see it in stack-overflow answers but not in the public
discourse about "computing paradigms". It just *is*.

The community around it would be similar to the database
community in the 1990s: niche but deep, with strong tooling,
serious documentation, and standardised interfaces.

### Regulatory acceptance shifts

By year 10, exact-method reports could be a regulatory
preference (rather than just an option) in several industries.
NERC reliability filings, Solvency II catastrophe model
output, ISO grid reliability standards — all could prefer
exact methods over Monte Carlo. The discovery dynamic is the
same that drove SQL adoption: once one major institution
mandates the new method, every other institution that
wants the contract has to support it.

### The 100,000-to-10 collapse happens at scale

In year 10, the 100,000-to-10 collapse isn't a theoretical
claim but a measurable industry transformation. The
catastrophe-modelling industry has consolidated. The grid-
reliability software industry has consolidated. The build-
system industry has standardised on a declarative core. Each
of these has 50,000+ lines of bespoke imperative code replaced
by a few hundred lines of declarative queries.

## What this means for you

If you're reading this in **year 0-3** of the trajectory, you
have the early-adopter advantage. You can use the framework
for your problems today and capture wins that the rest of the
industry hasn't noticed yet. The compounding value of being
the first person on your team to know this paradigm is
substantial.

If you're reading this in **year 4-7** of the trajectory, the
framework is becoming more visible. Job descriptions are
starting to mention it. Conference talks reference it. Early
domain DSLs exist. The advantage isn't as enormous, but it's
still real.

If you're reading this in **year 8+** of the trajectory, the
paradigm is becoming infrastructure. You probably learned it
during your training. It's part of the toolkit. The
extraordinary leverage of the early-adopter era is gone, but
the everyday productivity of using the right tool for the
problem remains.

This book exists in year 0. The early-adopter window is
wide open.

## A small word on the open path

The framework today is open-source and free. The mathematics
underneath is open. The development happens in public on
GitHub. There's nothing proprietary, no licensing fees, no
walled gardens. If the paradigm wins, it wins via people
trying it on their own problems and reporting back.

This is by design. The SQL pattern that worked in the 1980s —
"build a commercial product, charge for it, defend the market"
— is less useful in a world where the underlying mathematics
is openly available and the development tooling
(Python, PyPI, git) is universally accessible. The paradigm
spreads by demonstration, not by lock-in.

That has consequences for how the future plays out. If the
paradigm wins, it wins broadly — many companies adopt it
in parallel — not narrowly through a single dominant
vendor. The endgame is more like the spread of `numpy` than
the spread of Oracle.

## What this chapter taught you

1. The framework today is at approximately "Oracle 1979" on
   the SQL trajectory — real, commercial-ish, early adopters
   using it, the math underneath established.
2. The next 2-3 years look like calibration coverage,
   stability tier promotions, and the first domain DSL
   (probably workflow systems).
3. The 5-10 year view, if the paradigm pans out, is domain
   DSLs as the user-facing layer, the core framework as
   infrastructure, regulatory acceptance shifting, and the
   100,000-to-10 collapse happening at scale.
4. Where you sit on this trajectory determines what kind of
   leverage you have. Earlier = more.

The next chapter — the final chapter — is about how to become
a practitioner of this paradigm, in concrete terms. Not just
"read more docs" but "here's how the community works, here's
how to contribute, here's how to bring it back to your own
team".
