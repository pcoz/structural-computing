# Chapter 3 — Declarative structural computing in one paragraph

I'll show you the paragraph at the end of this chapter, not the
start. Before the paragraph makes any sense, we have to build up
some words. Five of them, specifically. None require any
mathematical background, and all of them refer to things you've
already met in everyday life — we just need names for them.

Picture a scenario: you work at an insurance company, and your
job is to figure out the probability that a small business
loses its building to a fire. You have a building, you have a
list of things that can go wrong (an electrical fault, an arson
attempt, a lightning strike), and you have a list of safety
mechanisms (sprinklers, fire doors, the building's location
relative to a fire station). The question is straightforward:
*what's the probability the building burns down this year?*

This is the kind of question the framework answers. To explain
*how* it answers it, we need five words. Let me give them to
you, one at a time, with concrete pictures.

## Word 1: "Structured system"

A **structured system** is a problem you can draw on a
whiteboard. Not literally — you don't have to draw it — but
*in principle* you could. The fire example has structure: there
are rooms, there are connections between rooms (doors,
corridors, ventilation shafts), there are safety devices
attached to specific rooms, and there are exit paths leading
to the outside.

If you described the fire scenario to a colleague, you'd draw a
diagram. Boxes for rooms, lines for connections, little
sprinkler icons in some boxes, a fire-station symbol in the
corner. That diagram is the system's structure. It's the thing
the framework can read.

Two real-world examples of structured systems:

- An **electrical grid**. Nodes are substations, lines are
  transmission cables. Some cables are highly reliable
  (underground, well-maintained); some are less reliable
  (overhead, in a stormy region). The structure is the
  network topology.
- A **workflow** in an HR system. Nodes are steps (submit form,
  manager approves, finance approves, payment sent); lines are
  the transitions between steps. Some transitions have
  conditions (the form must have a manager's signature; the
  amount must be under a threshold).

If your problem looks like one of these — *things connected to
other things* — it's a structured system.

A **non-example**: trying to predict tomorrow's stock price. No
discrete structure. Just a continuous price curve. The
framework doesn't help here.

## Word 2: "Declarative question"

A **declarative question** is a question you can ask by *naming
it*, without explaining how to answer it.

Compare these two ways of phrasing the same thing:

> **(How-to phrasing.)** Start with the room where the fire
> begins. Look at each adjacent room. Check if the connecting
> door is fire-rated. If so, the fire is blocked. If not,
> propagate the fire to the adjacent room. Repeat. Now check
> for sprinklers in each affected room. For each sprinkler,
> roll a random number to see if it activates. If it activates,
> the fire stops. If not, the fire continues. Repeat ten
> thousand times and average the outcomes.

> **(Declarative phrasing.)** What's the probability the fire
> reaches the loading dock?

Both ask the same thing. The first is a recipe for *how to
compute* the answer. The second just *names the question*.

The whole point of the framework is that you write the
declarative version, and the framework figures out the how-to
version. You say *what you want* — "the probability the fire
reaches the loading dock" — and the framework, *which has read
your building's structure*, picks the right exact polynomial-
time algorithm to compute it.

Two more declarative questions:

- *How many ways can we schedule these surgeries across these
  operating rooms?* (named: `count_schedules`)
- *Which of these two factory layouts has the lower probability
  of a production-line stop?* (named: `compare`)

You don't write the algorithm. You ask the question. The
framework answers.

## Word 3: "Structural shape"

Your system has *some* structure, but the framework only handles
*certain kinds* of structure. The kind matters.

The biggest distinction is whether your system is **planar**.
Planar means you can draw it on a flat piece of paper with no
two lines crossing each other. An electrical grid, drawn on a
map, is planar (the transmission cables follow the geography;
they don't fly over each other). A road network is planar
(roads don't usually pass through one another). A river
drainage system is planar. A typical factory floor plan is
planar.

A social network is *not* planar. If you tried to draw all the
"friend" connections between a hundred people on a flat sheet,
the lines would have to cross. You can't avoid it. Most
random-looking networks (citation graphs, Twitter follows, the
web) are non-planar.

The framework's natural domain is planar systems — and a few
extensions that we'll get to (bounded-genus, GF(2)-affine —
unfamiliar words, but they describe geographic networks with
"a few crossings" and certain kinds of constraint systems
respectively).

The framework's biggest hidden feature is: *given your system,
it figures out for you whether it's in one of its handled
shapes*. You don't have to know in advance. You hand it the
data, and it tells you yes-this-is-planar or no-this-isn't.
We'll come back to this in Chapter 6.

## Word 4: "Semiring choice" (the surprising word)

This is the most interesting concept in the framework, and the
least obvious. It's also the one that explains why so many
different questions get answered by the same machinery.

Consider two questions about the fire scenario:

- **Question A.** *How many distinct fire-spread paths exist
  from the kitchen to the loading dock?* Answer is a count: a
  whole number like 7 or 132.
- **Question B.** *What's the cheapest fire-suppression upgrade
  that breaks all of them?* Answer is a cost: a real number
  like $42,000.

These look like completely different questions. They have
different units (count vs. dollars), different solution shapes
(integer vs. real), different intuitions about how you'd
compute them.

But here's the thing: the *algorithm* you'd use to answer them
is the *same algorithm*. The only difference is the **operation
you do at each step**.

For Question A, at each step you ADD the number of paths and
MULTIPLY when paths combine. That's regular arithmetic.

For Question B, at each step you TAKE THE MINIMUM of the costs
and ADD when paths combine. That's a different pair of
operations. Mathematicians call the pair `(min, +)` a
**tropical semiring**. The word "tropical" has nothing to do
with weather; it's a historical accident. The word "semiring"
just means *a pair of operations that play nicely together
(like + and × do)*.

The framework lets you pick the semiring by picking the
question:

| Question name | What semiring you implicitly chose | What you get |
|---|---|---|
| `count_matchings(g)` | standard `(+, ×)` | a count (integer) |
| `min_weight_matching(g, w)` | tropical `(min, +)` | a min cost (real) |
| `tail_probability(g, p)` | probability `(+, ×ₚ)` | a probability (real in [0,1]) |
| `witness(g)` | boolean `(or, and)` | does one exist (yes/no, plus an example) |

You don't write `semiring=...` anywhere in your code. You just
pick the question name. The framework reads your question name
and picks the right semiring underneath.

This is *why* the same package answers counting questions AND
optimisation questions AND reliability questions. They're the
same underlying algorithm under different semirings. That's the
unifying fact.

For the rest of the book, you can mostly forget this word
exists. You'll write `sc.tail_probability(...)` or
`sc.min_weight_matching(...)` and the semiring choice will be
implicit. But it's worth knowing the fact: the reason the
framework is so broad isn't because it has dozens of unrelated
algorithms. It has *one* family of algorithms that compute
different things under different operations.

## Word 5: "Honest stop"

The framework doesn't always have an answer. When it doesn't,
it tells you so — explicitly, with a structured explanation —
rather than guessing.

That's an **honest stop**.

If you hand the framework a problem whose structural shape
doesn't fit (a random expander graph, say), it raises an
exception:

```python
sc.count_matchings(some_non_planar_graph)
# raises NotInFamily:
#   "graph is non-planar (tier T5); no exact path in the framework"
```

That's not a bug. It's the framework's most valuable property.

A Monte Carlo simulator will *always* give you an answer. It'll
give you an answer when the inputs are corrupted, when the
question doesn't make sense, when the sampler hasn't converged.
The answer will look real — it'll have decimal points and
confidence intervals and everything. You won't know it's wrong
until something downstream catches it, possibly months later,
possibly never.

The framework refuses to do that. If it can't answer, it says
so. No silent approximation. No vague-looking number that's
actually unreliable. Just *"I can't help with this; here's the
classification of why."*

This is incredibly useful for regulator-facing analyses.
Imagine showing a regulator a reliability number. Two
possibilities:

1. *"Our Monte Carlo simulator says the failure probability is
   0.003 with a 95% confidence interval of [0.0028, 0.0031]."*
2. *"Our framework says the failure probability is exactly
   2.94 × 10⁻³, with the matchgate-Holant audit trail attached
   to this report."*

The second answer is regulator-defensible in a way the first
isn't. The first answer depends on whether the simulator ran
long enough. The second one doesn't.

## Putting the five words together

You now have the words. Here's the paragraph:

> You have a *structured system* (a graph, a workflow, a grid).
> You ask the framework a *declarative question* about it (how
> many paths? cheapest schedule? probability of failure?). The
> framework reads your system's *structural shape* and the
> *semiring* implied by your question, picks the right exact
> polynomial-time algorithm underneath, and gives you the
> answer in one call. If the structural shape doesn't fit, the
> framework gives you an *honest stop* — a structured "I can't
> help with this and here's why" — rather than a guess.

That's the paradigm. Five words: structured system, declarative
question, structural shape, semiring choice, honest stop.

You'll meet all five again in the worked examples (Chapters
9–11), where we'll do them concretely on real problems. Before
we get there, the next chapter — Chapter 4 — answers the most
practical question this book can: *given a problem, how do you
tell, in under a minute, whether the framework will help?*

## A small parting note on jargon

This book deliberately avoids math notation. Some chapters
later will mention specific algorithms by name — FKT,
Kasteleyn, Hungarian, Edmonds — but only in passing, and only
when knowing the name helps you talk to a specialist or look up
the math.

You don't need to know any of those names to use the framework.
You'll be writing code like:

```python
sc.tail_probability(my_grid, p_fail=0.05)
```

and the framework will pick FKT for you, run it, and return a
number. The names are there so you can explain to a colleague
what the framework did — not so you have to memorise them.

The same is true for "semiring" and "matchgate" and
"GF(2)-affine". They're labels for ideas you mostly don't have
to think about, but might want to mention to a maths-fluent
teammate. The framework hides them under the floor. The book
tries to do the same.
