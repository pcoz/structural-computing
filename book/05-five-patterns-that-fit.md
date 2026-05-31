# Chapter 5 — Five patterns that fit, five that don't

In the previous chapter we walked through how to think about
whether the framework applies to a problem in general. This
chapter gets concrete. I'll show you ten patterns — five that
fit the framework cleanly, five that don't — drawn from real
software you've probably encountered.

For each pattern I'll describe:

- What the existing code typically looks like.
- Whether it fits the framework's shape.
- Approximately what the collapse looks like — for the patterns
  that fit, what the 10-line form might be; for the ones that
  don't, what tool is the right one instead.

The aim is *pattern recognition*. After this chapter, when you
see one of these patterns in your own work, you'll know almost
instantly whether the framework is the right tool.

## Patterns that fit

### Pattern 1 — Reliability under random component failures

**The shape.** You have some kind of physical or logical
network. Each piece of the network — each wire, each pipe,
each server, each road — can fail independently with some
probability. The question is: *what's the probability the
network as a whole keeps working?* Or, equivalently: *what's
the probability the system doesn't deliver its function?*

**Where this shows up in real code.**

- Power-grid reliability: nodes are substations, edges are
  transmission lines, the question is *can we still deliver
  power to every load if some lines trip?*
- Telecommunications: nodes are switching centres, edges are
  trunk lines, the question is *can we still route every
  call?*
- Water distribution: nodes are pumping stations, edges are
  pipe segments.
- Computer networks: nodes are routers, edges are network
  links, the question is *what's the probability we drop
  packets?*

**Existing implementation.** Almost universally, this is done
with a Monte Carlo simulator. The simulator generates random
failure scenarios (each edge fails with probability `p`),
checks whether the system still works in each scenario,
averages the result over millions of scenarios. The code is
typically 5,000 to 100,000 lines depending on the industry.

**Does it fit the framework?** Yes, almost always, *if* the
underlying network is planar (and most physical-infrastructure
networks are).

**What the collapse looks like.**

```python
from structural_computing import StructuralComputer
sc = StructuralComputer()

p = sc.tail_probability(my_network, p_fail=0.05)
# exact probability the network fails, computed in seconds
```

Two lines (well, three if you count the import). Replaces the
simulator.

### Pattern 2 — Assignment / scheduling / matching

**The shape.** You have a set of *things* (jobs, employees,
tasks, packages, customers) and a set of *slots* (machines,
shifts, time windows, vehicles, advertising spaces). You want
to assign each thing to a slot, subject to some constraints,
minimising or maximising some objective.

**Where this shows up in real code.**

- Hospital nurse rostering: assigning nurses to shifts subject
  to certifications, time-off requests, headcount minimums.
- Factory job scheduling: assigning manufacturing jobs to
  machines and time slots subject to setup times, due dates,
  machine capabilities.
- Cell tower channel allocation: assigning frequency channels
  to towers subject to interference constraints.
- Ad slot allocation: assigning display ads to webpage slots
  subject to budget caps, frequency caps, contractual
  obligations.
- Truck-to-route assignment: which truck delivers which
  packages, minimising total miles driven.

**Existing implementation.** Usually a Mixed Integer Program
(MIP) solved with a commercial solver — Gurobi, CPLEX, or the
open-source CBC. The MIP has tens of thousands of variables
and constraints. Solving it can take seconds (for small
instances) to many hours (for large ones, and sometimes the
solver just times out and you don't get an answer).

**Does it fit the framework?** Often yes, when the assignment
structure has a particular shape called "tropical rank ≤ 2".
That's a technical condition, but in practice it covers a
*lot* of real assignment problems — most ones where the cost
function is some product or sum of per-job and per-slot
attributes.

**What the collapse looks like.**

```python
result = sc.min_cost_schedule(instance, cost_fn)
# {'cost': 4372.50, 'schedule': {'J1': ('M1', 0), ...},
#  'feasible': True}
```

One line replaces a MIP that might have taken six hours to
converge. The answer is exact and polynomial-time (cubic in the
size of the problem) — no timeout possible.

### Pattern 3 — "Will my CP-SAT model solve faster?"

**The shape.** You're already using CP-SAT (Google's OR-Tools
constraint programming solver) or a similar solver. Your model
works, but it's slow. You suspect there might be a structural
shortcut, but you don't have the math background to find it
yourself.

**Where this shows up in real code.**

- A scheduling system built on CP-SAT that times out on
  realistic-size inputs.
- A combinatorial optimisation pipeline that works at small
  scale but doesn't scale.
- A research codebase that solves the same shape of problem
  hundreds of times but takes minutes per solve.

**Existing implementation.** A CP-SAT or MIP model with
*cardinality constraints* (`sum(xs) == k`), or *all-different*
constraints over small ranges, or other patterns that cause
the solver's internal data structures to explode.

**Does it fit the framework?** Often yes, *as a pre-flight
diagnostic*. The framework reads your CP-SAT model, identifies
constraints that have a known structural rewrite, and produces
an equivalent (but structurally cheaper) model.

**What the collapse looks like.**

```python
result = sc.rewrite_cpsat_model(model)
if result.helped:
    print(result.help_reason_text)
    # "Rewrote 1 constraint(s) to time-slot rank-1 form;
    #  added N auxiliary boolean(s)."   (N depends on the
    #  constraint shape — see the runnable example for the
    #  actual numbers)
    solver = cp_model.CpSolver()
    solver.Solve(result.rewritten_model)
else:
    # honest stop: solve the original
    solver = cp_model.CpSolver()
    solver.Solve(model)
```

Notice this is a *pre-flight* layer, not a replacement. You
keep using CP-SAT. The framework just makes your model
structurally cheaper before CP-SAT sees it. When it can't help,
it tells you so honestly. Three to five lines of code added to
an existing CP-SAT pipeline.

### Pattern 4 — Configuration comparison with audit trails

**The shape.** You have two (or more) designs — Configuration
A, Configuration B — and need to compare them on some
reliability metric. The metric is exact in principle, but the
existing comparison uses Monte Carlo and produces ranges,
which means *the verdict can vary across runs of the same
analysis*. That's a problem when the result has to be defended
to a regulator, an auditor, or a board.

**Where this shows up in real code.**

- Reinsurance treaty comparison: which treaty has the lower
  catastrophe exposure?
- Network topology comparison: which datacentre layout has
  fewer single points of failure?
- Insurance product comparison: which underwriting model has
  lower tail risk?
- Engineering trade studies: which of two bridge designs is
  more reliable?

**Existing implementation.** Two Monte Carlo simulators, one
per configuration. The verdict is: *Configuration A's failure
probability is 0.0031, Configuration B's is 0.0028, the 95%
confidence intervals overlap, conclusion uncertain.* Often the
analysis is rerun with more samples, then again, until either
the difference exceeds the confidence interval or someone runs
out of patience.

**Does it fit the framework?** Yes when both configurations are
planar.

**What the collapse looks like.**

```python
report = sc.compare(config_a, config_b, p_fail=0.05)
print(report.explain())
# "Configuration B is 90.2% more reliable (failure probability
#  9.5063e-03 vs 9.2686e-04). This distinction is provably
#  exact (computed via FKT, not sampled); the verdict is
#  reproducible bit-for-bit across machines."
```

One line. The verdict is bit-identically reproducible.
Regulator-defensible. No "confidence intervals overlap, run
more samples" trap.

### Pattern 5 — Workflow analysis (BPMN, Temporal, Camunda)

**The shape.** Your company runs workflows on a workflow engine
(Camunda, Temporal, BPMN, ServiceNow, Workato, etc.). The
workflow is a graph of steps connected by transitions. You
want to know structural properties: *which terminal states are
reachable from which entries? Are there dead states? Where are
the guard conflicts? Which steps are rare-path-only?*

**Where this shows up in real code.**

- Anywhere your company has automated business processes:
  claims processing, customer onboarding, returns handling,
  loan approval pipelines.
- Compliance auditing: *can this workflow ever produce an
  outcome that violates the rule book?*
- Reliability engineering: *what's the probability this
  workflow stalls at a particular step?*
- Rare-event analysis: *what's the worst-case completion time
  for this workflow under realistic load?*

**Existing implementation.** Today, mostly hand-written graph
traversal code. The workflow vendor ships a basic visual
analyser ("here's your flow chart"); deeper structural
questions either don't get asked or get answered by writing
custom analysis scripts.

**Does it fit the framework?** Yes — workflows almost always
have planar structure (the visual flow chart you can draw on
paper IS the planar embedding). The framework's matching-count
and reachability questions apply directly.

**What the collapse looks like.** The framework's
domain-specific DSL for workflow analysis is a year-10
deliverable (not yet shipped), but the underlying primitives
are there. With a small adapter:

```python
graph = parse_bpmn("claims_processing.bpmn")
audit = sc.audit(graph, p_fail=0.01)
# returns {'reachable_terminals': [...],
#          'dead_states': [],
#          'tail_probability': 0.0023, ...}
```

A few lines replace what would otherwise be a custom workflow-
analysis library.

## Patterns that don't fit

### Anti-pattern 1 — Continuous optimisation

**The shape.** Your variables are real numbers (not just yes/no
or assignments). Your constraints are inequalities like `x +
2y ≤ 5`. Your objective is something like `min x² + y²`. You're
optimising over a continuous landscape, not a discrete one.

**Where this shows up.** Portfolio optimisation. Aerodynamic
design. Chemical process control. Anywhere a CFO is comparing
different mixes of stocks. Anywhere an engineer is shaping a
curve.

**Why the framework doesn't help.** The framework's algorithms
are fundamentally discrete-combinatorial. They count, choose,
match, route. Continuous optimisation needs convexity
arguments, gradient methods, or specialised solvers — different
mathematics, different tools.

**Right tool instead.** `scipy.optimize` for small problems,
CVXPY for convex problems, Gurobi/CPLEX/IPOPT for large
mathematical-programming problems, JAX/PyTorch for
gradient-based optimisation of differentiable functions.

### Anti-pattern 2 — Random expander graphs

**The shape.** You have a network where each node has many
connections, the connections are largely random, and the
network is impossible to draw on paper without crossings —
*non-planar by design*.

**Where this shows up.** Social network analysis at scale
(Facebook, Twitter, LinkedIn). Web graph analysis. Citation
network analysis. Most random networks generated by stochastic
processes.

**Why the framework doesn't help.** The framework's
polynomial-time exact algorithms require the graph to have
specific structure (planar or close to it). Random expander
graphs explicitly have *no* such structure. The framework will
honest-stop on these immediately.

**Right tool instead.** NetworkX for moderate-size network
analysis. Graph databases (Neo4j, Amazon Neptune) for storage
and traversal at scale. Spectral methods for centrality and
community detection. Sampling-based estimators if you need
properties of the whole graph but can tolerate ranges.

### Anti-pattern 3 — High-dimensional continuous Bayesian inference

**The shape.** You have a probabilistic model with many real-
valued parameters. You have data. You want the posterior
distribution over the parameters given the data. The model is
non-trivial — it has hierarchical structure, latent variables,
non-conjugate priors — and you can't write down the posterior
in closed form.

**Where this shows up.** Pharmaceutical clinical trial
analysis. Astronomy (cosmological parameter inference).
Marketing-mix modelling. Anywhere statisticians reach for Stan
or Pyro.

**Why the framework doesn't help.** The variables are
continuous. The integrals don't have combinatorial structure.
The whole problem shape is different — MCMC and variational
inference are the right approaches, and they're fundamentally
different from FKT or matchgate evaluation.

**Right tool instead.** Stan, PyMC, Pyro, NumPyro, TensorFlow
Probability. These are the right tools and they're excellent.

### Anti-pattern 4 — Symbolic theorem proving

**The shape.** You have a logical formula. You want to know
whether it's satisfiable, valid, or implies some other formula.
You're working with first-order logic, type theory, or some
specialised logic.

**Where this shows up.** Formal verification of software.
Mathematical theorem proving (Coq, Lean, Isabelle). SMT
solving for program analysis. Hardware verification.

**Why the framework doesn't help.** The framework counts
solutions to specific algebraic problems; it doesn't reason
about formulas. The mathematical machinery has no overlap.

**Right tool instead.** Z3 and CVC5 for SMT. Lean, Coq, and
Isabelle for theorem proving. Vampire and E for first-order
provers.

### Anti-pattern 5 — Streaming / real-time / online algorithms

**The shape.** Your data arrives one event at a time. You need
answers in microseconds, with bounded memory. You can't see
all the data at once.

**Where this shows up.** High-frequency trading. Network
intrusion detection. Sensor analytics. Anywhere you're
running an algorithm against a firehose of events.

**Why the framework doesn't help.** The framework operates on
*whole problems at rest*. You hand it your entire graph, your
entire constraint set, your entire model, and it computes the
answer. There's no streaming layer.

**Right tool instead.** Streaming algorithms libraries (Apache
Flink, Apache Beam, Kafka Streams). Sketching algorithms
(Count-Min Sketch, HyperLogLog) for approximate counts under
streaming. Reservoir sampling for random samples of streams.

## How to use this list

This list isn't exhaustive. It's a starting set of patterns.
The more you work with the framework, the better you'll get at
recognising the underlying *shape* — which is what really
matters.

The two things to look at, every time:

1. **What is the answer-shape my problem demands?** Count?
   Probability? Cost? Witness? If yes, candidate for the
   framework.
2. **Does my problem have a graph or constraint structure that
   I could draw on paper without too many crossings?** If yes,
   strong candidate.

Past those two, it's worth knowing the patterns above as
shortcuts. But if you skip them and just run `sc.classify` on
the input, the framework will tell you the answer in seconds.

## Where this fits in the book

You're now at the end of Part I — *the paradigm*. The four
chapters so far have given you:

- A sense of *why* this kind of declarative collapse matters
  (the 100,000-line problem, Chapter 1).
- *Historical confidence* that paradigm shifts like this
  actually happen (the SQL story, Chapter 2).
- The *paradigm in one paragraph* with the five core concepts
  spelled out (Chapter 3).
- A *practical diagnostic* for telling whether the framework
  will help your particular problem (Chapter 4, this chapter).

Part II — the mental model — goes deeper. You'll learn what an
"admissible set" really is (Chapter 6), how the classifier
figures out the structural shape (Chapter 7), and what
"honest stops" look like in practice (Chapter 8).

If you're impatient and want to see code, you can skip ahead
to Part III (Chapters 9–11), which contains the worked
examples. The mental-model chapters of Part II are useful
background but not strictly necessary for using the framework.

I'd recommend reading them — they make everything else click
into place — but the book is structured so you can take
either path.
