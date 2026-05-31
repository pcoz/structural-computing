# Chapter 1 — The 100,000-line problem

Let me tell you about Sara.

Sara is a software engineer at a small company in California
that sells reliability analysis to electricity utilities. Her
company's flagship product helps utilities answer one question:
*if random parts of the grid fail, what's the probability the
whole thing keeps working?*

The product is the result of eight years of engineering by a
team of fifteen people. Sara has worked on it for the last
four. The codebase is about 100,000 lines of C++.

If you opened up the codebase and looked at what each line does,
you'd find something surprising. About 80,000 of those lines —
four-fifths of the entire product — do one of five things:

1. They generate a random failure scenario: pick some grid
   components, decide they've failed, see what happens.
2. They simulate what happens after those failures: which lines
   get overloaded, which substations trip, where the cascade
   stops.
3. They aggregate the results across thousands and thousands
   of these random scenarios.
4. They compute confidence intervals — *we're 95% sure the
   answer is between X and Y*.
5. They manage the bookkeeping of all the above: random number
   seeds, parallel execution across hundreds of cores,
   checkpoints so the program can resume if it crashes
   halfway.

That's 80,000 lines. The other 20,000 lines do everything else:
load the grid description from a file, format the report a
regulator wants to see, handle the command-line interface,
manage user accounts, handle the licensing.

So 80% of Sara's company's product is *one big simulator*. They
call it Monte Carlo simulation, after the casino. The idea is
simple: if you can't compute the exact answer, you simulate the
problem many times with random inputs and average the
outcomes. Run it ten thousand times, you get a pretty good
estimate. Run it ten million times, you get a very good one.

Every line of those 80,000 exists because, somewhere around
the year 2000, the founders of Sara's company decided that the
exact answer to *what's the probability of cascading grid
failure?* was **impossible to compute directly**. The
mathematics was assumed too hard, the combinatorial structure
too tangled. The only path forward, they said, was simulation.

They were good engineers. They built the simulator. They made
it fast — runs in twenty minutes for a small utility, twelve
hours for the largest in the country. They scaled it across
hundreds of cores. They added clever tricks to reduce the
variance, so smaller numbers of samples could give better
estimates. They proved their confidence intervals were
statistically valid. Utilities bought the product. The company
grew.

If you asked Sara today, she would tell you the company had
won. They had taken an intractable problem and made it
practical.

She'd be right about practical. She'd be wrong about
intractable.

## The fact Sara doesn't know

Here is something Sara doesn't know, and her company doesn't
know, and most of her industry doesn't know.

Electrical grids are **planar**. Planar means *you can draw
them on a flat map without any cables crossing over each other*.
This is just a geometric property of grids. The transmission
lines follow the geography; they don't fly across each other in
the sky.

In 1961 — sixty-five years before Sara wrote her first line
of code at this company — three mathematicians (Fisher,
Kasteleyn, and Temperley) discovered something striking. For
planar networks, the question Sara's product answers via
twelve hours of Monte Carlo simulation has an **exact**
mathematical formula. The formula can be computed in a fraction
of a second on a modern laptop. No simulation. No confidence
intervals. No parallelisation. No variance reduction. Just an
exact number, computed directly.

The algorithm is called FKT, after the initials of the three
discoverers. It runs in cubic time, which is a way of saying
that doubling the size of your grid makes it eight times
slower (not a million times slower, like a naive approach
would be).

If you handed FKT a grid with 1,000 nodes — about the size of
a US state's transmission network — it would tell you the
exact probability of cascading failure in about half a second.
No twelve hours. No confidence intervals. Just the answer.

That algorithm has been sitting in the mathematical literature
for sixty-five years. Sara's company never used it. Her
industry never used it. Everyone did Monte Carlo simulation
instead.

## How this kind of thing keeps happening

You might think Sara's company is unusual. They're not. The
same dynamic plays out across many industries:

- **Catastrophe modelling.** RMS, AIR, EQECAT — companies that
  predict insurance losses from earthquakes, hurricanes,
  floods. Their codebases are millions of lines of C++ that
  randomly simulate hazards across maps of insured properties.
  Many of the geographic maps they work with are planar in the
  same sense as power grids. The exact computation is
  available; nobody uses it.
- **Cloud reliability engineering.** When Google or Amazon
  analyse "what's the probability our datacentre network
  survives a cascading failure?", they use simulators that
  look exactly like Sara's. Many of those network topologies
  are planar.
- **Bank stress-testing.** When a bank computes how much
  capital it needs to weather a crisis (under Basel III rules),
  large parts of the calculation involve simulating networks
  of counterparties. Many of those networks have exploitable
  structure.
- **Build systems.** Every major software build tool — Bazel,
  Buck, Make, Ninja — has tens of thousands of lines doing
  intricate calculations about which files need to be rebuilt
  when something changes. Underneath those calculations are
  combinatorial questions that have exact, polynomial-time
  answers.
- **Workflow engines.** Tools like Temporal, Camunda, and
  ServiceNow analyse business workflows for things like
  "can this workflow ever get stuck?", or "what are the rare
  failure modes?". Today they do this with simulators.

Each of these industries built its tooling in the same way: an
army of engineers writing imperative code to simulate the
problem. And in each case, somewhere in a mathematics journal,
there sits an algorithm that would replace most of the
imperative code with a single function call.

## Why this isn't anyone's fault

Nobody in any of these industries is being foolish. Sara's
company isn't lazy or incompetent. The pattern is structurally
rational at each step:

1. **In the year 2000**, exact computation genuinely was
   intractable for the tools and software of the day. Monte
   Carlo was the right answer.
2. **In the year 2005**, somebody published a fast exact
   algorithm. But Sara's company didn't read mathematics
   journals. They were too busy fixing bugs in the simulator.
3. **In the year 2010**, the algorithm got refined and made
   more efficient by academics. But the paper was behind a
   paywall, the notation could only be read by specialists,
   and Sara's company still hadn't heard of it.
4. **In the year 2015**, the simulator was so integrated into
   the company's product, the regulator's expectations, the
   customer's workflows, that nothing else made sense. The
   simulator was no longer just a tool the company used. It
   was part of the *infrastructure of the field*.
5. **By 2020**, every job description in the industry says
   "experience with Monte Carlo simulation required". Every
   conference paper assumes Monte Carlo. Every textbook
   teaches it. The algorithm from 2005 is still there, in the
   journal. Nobody can find a path back to it.

That's how 100,000-line simulators end up doing what a
ten-line function could do. It's not malice or laziness. It's
*path dependence*. Once an industry calcifies around an
imperative solution, the declarative one never makes it back
into the engineering mainstream.

## What you're going to learn to recognise

The single most useful skill this book teaches is
**recognition**. Look at a piece of code. Look at a question.
Ask yourself:

> *Is this Monte Carlo machinery solving a question that has an
> exact answer?*

For a surprising fraction of codebases — not all, but a real
fraction worth knowing — the answer is yes. And when the
answer is yes, you can collapse 100,000 lines of imperative
simulator into a declarative query that's a couple of lines
long, runs faster than the simulator, produces an exact answer
instead of a confidence interval, and gives you the same
answer bit-for-bit on different machines.

That's the promise of the rest of the book.

## What the framework is

The framework — its full name is `structural-computing`, and
it's available on PyPI by typing `pip install structural-
computing` — is the practical embodiment of that argument for
the kinds of problem it applies to.

You give it a question with the right shape. It gives you the
exact answer.

For questions that don't have the right shape, it tells you so
honestly and recommends what tool you should be using
instead. (This honest "no" is — surprisingly — one of the most
valuable things the framework does. Chapter 8 is entirely
about this.)

## A small honest caveat

The collapse from 100,000 lines down to 10 is real for
problems with the right shape. It is real for power-grid
reliability. It is real for catastrophe modelling. It is real
for build-system dependency analysis. It is real for workflow
auditing.

But it is **not** real for every codebase. Some problems
genuinely need Monte Carlo because:

- The underlying question is genuinely continuous (think:
  predicting tomorrow's temperature).
- The combinatorial structure is genuinely too tangled (a
  random social network at scale).
- The problem is genuinely out-of-family for the framework's
  approach.

This book is partly about teaching you to recognise which is
which. The framework will tell you which is which. The 10-line
wins are real where they exist; the honest stops where they
don't apply are equally real, and equally valuable.

That's the paradigm. The next chapter shows you that this isn't
the first time this kind of paradigm shift has happened. There's
a famous precedent that turned 100,000 lines of imperative
data-handling code into a single five-line query — a precedent
you use every day without thinking about it. It's called SQL.
And the story of how SQL won, in the 1970s and 1980s, is
something like a blueprint for what could happen here.
