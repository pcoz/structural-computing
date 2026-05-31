# Chapter 4 — Will the framework help my problem?

This chapter answers the single most useful practical question
about the framework: *given some problem in your existing
codebase, how do you tell — in under a minute, without
expertise — whether the framework will give you a useful
speedup?*

The chapter doesn't give you a hard rule. There isn't one.
What it gives you is a way of thinking about your problem that
reliably produces the right call. We'll walk through it as a
conversation, with examples. By the end you'll have a
diagnostic intuition you can apply to anything that crosses
your desk.

Let me set this up with a scenario. Maya is a data engineer at
a logistics company. She runs a pipeline that simulates package
routing through her company's network of warehouses, trucks,
and final-mile drivers. Her pipeline is about 8,000 lines of
Python. It's slow — runs four hours every night, sometimes
times out and has to be restarted. Her manager has heard about
this "structural-computing thing" and asked her to find out
whether it can help.

Maya doesn't know matchgate theory. Maya doesn't know what a
Pfaffian is. Maya has a four-hour-a-night problem, a manager
breathing down her neck, and one Friday afternoon to figure out
whether this is worth a deeper look.

Here's how Maya should think about it.

## The first thing to look at: what's the actual question?

Before anything else, Maya should write down — in plain
English, one sentence — *what her pipeline is actually
computing*. Not how. What.

If she does this seriously, she'll find that most of her
pipeline is computing several different things, but they're
all variations on one of these:

- *"How many packages can route from origin A to destination B
  given these capacity limits?"*
- *"What's the probability we miss our SLA tomorrow given
  historical reliability of each leg of the network?"*
- *"Which set of routes is cheapest to use this week?"*

These are **declarative questions**. They state what Maya wants
to know without saying how to compute it. That's a good sign.

Now, what makes a question declarative isn't just the phrasing.
It's the *kind of answer* the question demands. The three
examples above each have an answer that's:

- a **count** (a whole number, like 47),
- a **probability** (a number between 0 and 1),
- a **cost** (a real number, like $4,372.50), or
- a **witness** (a specific example, like "use route 3 then
  route 7 then route 12").

These are exactly the answer-shapes the framework specialises
in. If Maya's question has an answer in one of these shapes,
she's looking at a candidate.

**Counter-example for clarity.** A pipeline that predicts
*"what will the demand be in Region 5 next month?"* is asking
for a continuous prediction over an unbounded range. That
doesn't fit the framework's shape. It's a regression problem.
Use whatever statistical tool you're already using.

So question one for Maya: *does my pipeline ultimately produce
a count, a probability, a cost, or a witness?*

If yes, keep going. If no, the framework isn't relevant.

## The second thing to look at: is there a graph anywhere?

The framework lives on **graphs**. It also handles a couple of
other shapes (constraint sets, Holant signatures), but the most
common case by far is: your problem involves a graph somewhere.

A graph is just *things connected to other things*. The things
are usually called nodes (or vertices) and the connections are
usually called edges. That's it. No mathematics.

Maya's logistics network is a graph. Warehouses, trucks, and
drivers are nodes. The routes between them are edges. She
doesn't have to draw it on paper. But she could.

For most readers, if you can identify that your problem has
something graph-like at its core, you're a candidate. Here are
some common things people don't always recognise as graphs:

- A workflow (steps connected by transitions).
- An electrical grid (substations connected by cables).
- A factory floor plan (machines connected by conveyors).
- A schedule (jobs connected to machines and time slots).
- A computer network (servers connected by links).
- A telephone network's call routing (switches and trunks).
- A drug-interaction database (drugs connected by known
  interactions).
- An organisation chart (people connected by reporting lines).

If any of these resemble what your pipeline does, you have a
graph. Even if you've never thought of it that way, even if
your code doesn't have an explicit "graph" data structure
anywhere in it. The graph is *there*, hidden in your data.

So question two: *is there a graph hiding in your problem,
even if you don't currently model it as one?*

If yes, keep going.

## The third thing to look at: does the graph "look planar"?

This one's a little trickier, but there's a quick way to think
about it.

**Planar** just means: you can draw the graph on a flat sheet
of paper with no two connections crossing each other. Roads on
a map are planar. Electrical grids are planar. Most physical
networks that follow geography are planar.

The opposite, **non-planar**, means: no matter how you arrange
the nodes on paper, *some* of the connections will have to
cross. The classic non-planar graphs are highly interconnected
networks: a social media graph where many random people are
each connected to many other random people. Friendship
networks on Facebook. The Web. A list of who-emails-whom
across a large company.

Most physical-infrastructure networks are planar. Most
social/web networks are non-planar. Most workflow networks are
planar. Most random data graphs are non-planar.

Maya's logistics network — physical, geographic — is almost
certainly planar. Good. Her pipeline is a candidate.

For Maya's purposes, she doesn't need to *prove* the graph is
planar. She just needs to suspect it. The framework will
confirm it for her in one function call. We'll see how in
Chapter 7.

So question three: *if you imagine your graph drawn out, does
it feel like a physical network (planar) or a social/random
network (non-planar)?*

If physical/geographic, keep going. If social/random, stop —
the framework probably honestly won't help, and you should
look at network analysis libraries instead.

## The fourth thing to look at: is there sampling in the existing code?

This is the smoking-gun question.

If Maya opens her 8,000-line pipeline and grep'ds for words
like:

- `random`
- `monte carlo` / `monte_carlo`
- `sample`
- `simulation`
- `seed`
- `numpy.random` / `random.choice` / etc.
- `repeat` / `n_runs`
- `confidence_interval`
- `variance_reduction`

...and finds lots of hits, she's almost certainly looking at
the 100,000-to-10 collapse pattern. The reason her pipeline is
8,000 lines instead of 100 is *that it's mostly a simulator*.
The simulator is there because someone, at some point, assumed
the exact answer was intractable.

If the structural shape of her problem turns out to fit the
framework — and so far it does — then most of that 8,000 lines
*isn't needed*. The exact answer is computable directly.

So question four: *does my existing code do a lot of random
sampling because someone decided the exact answer was too
hard?*

If yes, you've got a strong candidate for a dramatic collapse.
The framework is worth a careful look.

## Putting it together for Maya

Let's run the four questions on Maya's pipeline:

1. **Declarative question?** Yes — her pipeline computes
   counts (packages routable), probabilities (SLA-miss
   chance), and costs (cheapest routes). All three fit the
   framework's answer-shape.
2. **Graph hiding in the problem?** Yes — her logistics
   network is literally a graph. Warehouses, trucks, drivers
   as nodes; routes as edges.
3. **Planar-feeling?** Yes — her network is physical and
   geographic. It probably is planar.
4. **Sampling in the existing code?** Yes — her pipeline is
   four hours of Monte Carlo simulation, run nightly.

Four yeses. Maya has an extremely strong candidate for the
framework. Her four-hour nightly pipeline is plausibly a
ten-second one-liner once she gets the framework wired in.

That's the diagnostic. Four questions. Maya can do this
analysis in under five minutes.

## What if Maya gets a mixed answer?

Real life is mixed answers. Maybe Maya has questions 1, 2, and
4 saying yes, but question 3 — is it planar? — is unclear.
What then?

Two options.

**First option: just try it.** The framework provides a
`classify` function whose job is to read your problem and tell
you what shape it has. The cost of running `classify` is a
second or two. The result is a definitive answer to question 3.

```python
from structural_computing import StructuralComputer
sc = StructuralComputer()

cls = sc.classify(my_graph)
print(cls.tier, cls.reasoning)
```

If the tier comes back as `T2` or `T4` (planar or bounded-genus,
both in-family), Maya's good. If it comes back as `T5`,
`T6`, or `T7`, the framework will honest-stop on this
particular shape — but the classifier output explains exactly
why.

**Second option: stop and think harder about the problem.** If
Maya runs `classify` and her network is borderline — partly
planar, partly not — she has interesting options. The
framework can sometimes handle a non-planar graph if you can
identify a small number of *extra edges* that, when removed,
leave a planar core. This is called "hybrid decomposition". We
won't dwell on it here; the docs cover it.

The point is: a mixed answer doesn't mean "stop". It means
"this is interesting, look closer". The framework rewards
attention.

## What if the answer is clearly "no, the framework won't help"?

Equally important: *knowing when to walk away*.

Some pipelines just aren't the right shape. Continuous-
optimisation pipelines (portfolio optimisation, structural
engineering, fluid dynamics) aren't. Pure machine-learning
pipelines aren't. High-dimensional Bayesian inference (Stan,
Pyro) isn't. Symbolic theorem proving (Z3, Lean) isn't.
Streaming-data systems with sub-millisecond requirements aren't.

If you run the four questions and get no's, the framework
honestly cannot help you. That's not a failure of the
framework. It's the framework being clear about its scope.

The reason the framework's honest stops are valuable is the
same reason a doctor's honest "I don't know, see a specialist"
is valuable: it sends you to the right tool faster than a
wrong answer would.

So if your answer is clearly no — go and use the right tool.
Spend an hour reading the next chapter of *this* book anyway,
because the recognition pattern compounds. The next time a
problem crosses your desk, you'll spot the structural shape
faster.

## A small risk-management note

You don't have to commit to anything yet. The smallest
experiment you can run is:

1. Take a 10-minute slice of your existing pipeline.
2. Reshape its input into a graph dict the framework can read.
3. Call `sc.classify(...)` to see what tier you land in.
4. Run a representative method (`sc.count_matchings(...)`, or
   `sc.tail_probability(...)`, or `sc.min_weight_matching(...)`,
   whichever matches your question).
5. Compare the framework's answer to your existing one.

If the answers agree and the framework runs faster, you've
found a candidate for the collapse. If the framework honest-
stops, you've confirmed the existing tool is the right one
and gained a documented reason why for your team. If the
framework returns an answer but it disagrees with yours,
you've found a bug somewhere — possibly in your existing code,
possibly in the framework, possibly in how you reshaped the
input. All three are worth knowing about.

The total cost of this experiment is about ten minutes. The
upside, if it works, is the collapse of a major piece of
infrastructure. The downside is ten minutes spent learning
something useful about your own pipeline.

## What comes next

The next chapter goes deeper on *which kinds of problem fit
the framework* with five concrete patterns. After that we move
into the mental model — what an "admissible set" really is
(Chapter 6), how the classifier figures out the structural
shape (Chapter 7), and the role of honest stops (Chapter 8).
Then in Part III we get to the worked examples where Maya's
kind of pipeline becomes a one-liner.

Through all of it, the recognition skill you just learned —
the four questions — keeps getting more refined. By the end of
the book, looking at a problem and assessing its fit takes
you about ten seconds.
