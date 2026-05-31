# Chapter 1a — The business case, in one page

(A short interlude between Chapter 1 and Chapter 2. If you read
only one page of this book, read this one.)

Sara's reliability-analysis company from Chapter 1 has the
following annual costs:

| Cost line | Roughly per year |
|---|---|
| Salaries for the 15-person engineering team that maintains the simulator | **$2.4–3.6 million** |
| Compute: the simulator runs on a 200-core cluster, mostly used by the reliability team | **$400k–$600k** |
| Commercial-solver licences (occasional Gurobi runs for fallback) | **$50k–$150k** |
| Customer support: roughly two engineers full-time fielding "the simulator gave a weird answer" tickets | **$300k–$500k** |
| **Total annual cost of the imperative-Monte-Carlo approach** | **$3.2–4.9 million** |

Most of that cost exists because somebody, two decades ago,
decided the exact answer was intractable. It isn't, for the
shape of problem Sara's company sells. If the company adopted
the framework's declarative form for the 80% of their codebase
that's currently simulator, most of the cost lines above would
shrink dramatically:

| Cost line | After adopting the framework |
|---|---|
| Engineering team (smaller, focused on the 20% input/output/integration work) | **$800k–$1.2 million** |
| Compute (cubic-time exact runs need ~1% of the simulator's compute) | **$10k–$50k** |
| Commercial-solver licences (replaced by free framework + free CP-SAT pre-flight) | **$0–$10k** |
| Customer support (fewer "weird answer" tickets because no Monte Carlo bias) | **$150k–$300k** |
| **Total annual cost after the collapse** | **$960k–$1.56 million** |

**Annual saving: roughly $2.3–3.5 million** for a single small
software company. The 100,000-line codebase becomes ~10,000
lines and the team supporting it goes from 15 people to about 4.

Multiply this across an industry. There are roughly 200
software companies and internal teams in the United States
alone whose core product is a Monte Carlo simulator for some
combinatorial reliability question. If half of them have problems
that fit the framework — a conservative estimate — the
aggregate annual saving sits in the range of **$200–400 million
across the industry**, with the savings flowing to whichever
players move first.

## The benefits aren't only cost

Sara's customers — the electricity utilities themselves — also
gain something they couldn't get before:

- **Defensible regulatory filings.** Today's MC-based reliability
  reports come with confidence intervals. A utility filing a
  number like "0.0023 ± 0.0008" is essentially saying *"the
  failure probability is somewhere in this range; we're 95%
  sure it's not far outside"*. With exact methods, the number
  is just **0.0023**. No interval. Regulators prefer exact
  numbers. Pivoting to exact methods can unlock favourable
  regulatory treatment that wasn't available before.
- **Better capital allocation.** When you compute exact failure
  probabilities, you can compare configurations that the MC
  simulator literally couldn't tell apart. The utility's
  capital-investment decisions get sharper. For a typical
  state-level utility with a $1B/year capex budget,
  reallocating even 5% from "obviously-safe-build-more-anyway"
  to "actually-rare-tail-heavy" is **$50M/year of better-
  targeted capex**.
- **Faster turn-around.** Today's MC pipelines run nightly,
  with a few-hour latency. With exact methods, the same
  question answers in seconds, on a laptop, in a meeting,
  while a decision is being made.

## The benefits aren't only for Sara's industry

Sara's company is one example. The same pattern — Monte Carlo
machinery that doesn't need to exist — sits inside:

- **Catastrophe modelling** (RMS, AIR, EQECAT). Annual industry
  revenue ~$1B; reinsurance underpinning it ~$400B. Even a
  20-40% pricing dispersion in reinsurance treaties due to
  model noise represents tens of billions in capital allocation
  uncertainty that exact methods can dissolve.
- **Cloud SRE reliability analysis**. Internal engineering at
  Google, Amazon, Microsoft. The reliability teams are 10-50
  engineers per company; cost figures track Sara's example
  per company.
- **Build systems and CI pipelines**. Bazel, Buck, Make, Ninja
  — tens of thousands of lines of cache-invalidation logic.
  The major tech companies each spend $5-20M/year on build-
  infrastructure engineering. Some fraction of that has the
  same shape.
- **Workflow engines** (Temporal, Camunda, ServiceNow). The
  workflow-analysis layers are 20-50k lines per product;
  rewriting them to use exact methods would consolidate the
  industry around a much smaller stack.

A conservative estimate of the *aggregate* annual addressable
saving from this paradigm shift, across all the industries
where it applies, sits in the **single-digit billions of
dollars per year, growing as adoption spreads**. That's the
business case at full strength.

## What you, personally, get

If you're reading this as a software engineer, the framework is
*on PyPI today*. It's free. You can `pip install` it this
afternoon and start collapsing your team's Monte Carlo code
this week. The early-adopter advantage isn't a fifteen-year
bet on industry transformation — it's a *this-quarter* win on
the specific problems you already have.

If you're reading this as a business analyst, the value is
clearer still: you can ask your engineering team whether *any*
of their reliability / scheduling / CP-SAT pipelines fit the
framework's shape (the four-question diagnostic in Chapter 4
gives them a five-minute answer), and if yes, you've found a
high-leverage cost reduction that's not on anyone's current
roadmap.

If you're reading this as a CTO or VP Engineering, the value
is structural: the framework is a candidate for *strategic
build-versus-buy reframing*. Many of the simulators your teams
maintain in-house may not need to exist. The exit isn't to
"buy" anything; it's to *delete* the parts of the codebase
that the framework's free, open-source declarative form makes
unnecessary.

The rest of the book is the **how**. This one page was the
**why**.
