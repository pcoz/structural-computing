# Chapter 14 — When to use this vs MIP vs CP-SAT vs Monte Carlo

This chapter is a practical decision guide. You have a problem
on your desk. You're trying to decide which tool to reach for.
The chapter walks you through the choice in terms anyone on a
software team can use.

We'll cover:

1. **The tools.** A short profile of each (the framework, MIP,
   CP-SAT, Monte Carlo simulators, NetworkX, scipy).
2. **The choice tree.** Given your problem, which tool fits.
3. **Mixed strategies.** When to combine tools.

By the end you'll be able to look at a new problem and pick the
right tool in under five minutes.

## 1. The tools

### Tool A — `structural-computing` (the framework)

**What it does.** Exact polynomial-time answers to
combinatorial questions on structured graphs / constraint
sets / signatures. Counting, reliability, optimisation,
witnesses.

**When it shines.** Planar graphs. Bipartite or near-bipartite
assignment problems. Workflow-style graphs. Anything where a
Monte Carlo simulator was built because exact computation was
assumed intractable but actually isn't.

**Where it stops.** Continuous problems. Random expander
graphs (non-planar at scale). Anything that's not
combinatorial-structural.

**Performance.** `O(n^3)` for the inner solver (Pfaffian /
Hungarian / etc.). No exponential blow-up. No solver timeout.

### Tool B — MIP solver (Gurobi, CPLEX, CBC)

**What it does.** Solves Mixed Integer Programs. Optimises a
linear objective over linear constraints with some variables
restricted to integers.

**When it shines.** Genuinely hard combinatorial optimisation
where the structure isn't matchgate-friendly. Heavily
constrained scheduling, routing, vehicle routing problems
(VRP), production planning. Industrial problems with
hundreds of constraints.

**Where it stops.** Worst-case time is exponential. Real
instances mostly work, but some don't, and you can't always
predict which. Commercial solvers (Gurobi, CPLEX) require
licences (~$10k/year per developer); CBC is free but slower.

**Performance.** Highly variable. Easy MIPs solve in
milliseconds. Hard ones take hours or time out.

### Tool C — CP-SAT (OR-Tools)

**What it does.** Constraint programming with boolean and
integer variables. Handles a broader range of constraint
types than MIP (all-different, table constraints, scheduling
constraints, etc.).

**When it shines.** Pure constraint-satisfaction problems
(SAT-like). Scheduling problems with rich constraint structure
where MIP modelling is awkward. Free, well-maintained,
production-quality.

**Where it stops.** Like MIP, worst-case exponential. Rank-
explosive constraints (cardinality, all-different over big
domains) slow it down. This is exactly where the framework's
pre-flight rewrite (Chapter 11) helps.

**Performance.** Often very fast on the problems it handles
well. Pathologically slow on rank-explosive cases.

### Tool D — Monte Carlo simulators

**What it does.** Estimates statistical quantities (means,
variances, tail probabilities) by random sampling.

**When it shines.** Problems with genuine continuous
randomness. Bayesian inference where exact computation is
intractable. Risk analyses where the underlying distribution
is genuinely uncertain. Simulation of stochastic processes.

**Where it stops.** Whenever the question has an exact answer
that's computable in reasonable time. Whenever the question
isn't really about sampling but is being framed as such for
historical reasons (this is the Chapter 1 / Chapter 9 case).

**Performance.** Linear in the number of samples. Variance
scales as `1/sqrt(N)`, so to halve the confidence interval
you need 4× the samples.

### Tool E — NetworkX

**What it does.** General-purpose graph analysis library in
Python. Handles graphs of any structure.

**When it shines.** Graph problems where the structure isn't
matchgate-friendly. Social network analysis. Web graph
metrics. Centrality, community detection, path-finding.

**Where it stops.** Many algorithms in NetworkX are
exponential-worst-case (perfect matching counting on
non-bipartite graphs, for example). Slow at scale.

**Performance.** Good for small-to-medium graphs. Slow at
very large scale unless you carefully pick algorithms.

### Tool F — scipy.optimize / CVXPY

**What it does.** Continuous optimisation. Convex problems,
nonlinear programming, least-squares fits.

**When it shines.** Continuous variables. Real-valued
objectives. Convex constraint sets. Anywhere the underlying
math is calculus, not combinatorics.

**Where it stops.** Discrete-combinatorial problems.
Constraint-satisfaction problems where the variables are
fundamentally boolean.

**Performance.** Excellent on the convex problems they're
designed for. Wrong tool entirely for combinatorial problems.

## 2. The choice tree

For a new problem, walk through these questions in order.

**Question 1: are my variables continuous or discrete?**

- *Continuous* (real-valued): tool F (scipy.optimize / CVXPY).
  Skip the rest of this tree.
- *Discrete* (integer / boolean / categorical): continue.

**Question 2: what's the answer shape?**

- *Probability under random failure*: continue. Likely Tool A
  or Tool D.
- *A count of something*: continue. Likely Tool A.
- *An optimal cost or schedule*: continue. Likely Tool A, B,
  or C.
- *A witness (one specific example)*: continue. Likely Tool A
  or NetworkX.
- *Graph metrics (centrality, betweenness, etc.)*: NetworkX
  (Tool E). Skip the rest.

**Question 3: is the underlying graph or structure
matchgate-friendly?**

This is the key question. Run `sc.classify(...)` on the
problem.

- *Returns T0, T1, T2, T3, or T4 (in-family)*: Tool A (the
  framework) is your first choice. It'll give you an exact
  polynomial-time answer.
- *Returns T5 or higher (out-of-family)*: the framework
  honest-stops. Go to question 4.

**Question 4: how big is the problem?**

- *Small (< 50 nodes / variables)*: Tool E (NetworkX brute
  force) might work. Or Tool D for probability questions.
- *Medium (50-10,000)*: Tool B (MIP) or Tool C (CP-SAT).
  Consider running both and picking the one that converges.
- *Large (> 10,000)*: Tool B or C with a time limit; expect
  to need a heuristic fallback for the hard cases. Or Tool D
  if the question is genuinely probabilistic.

**Question 5: do I need exact answers (regulator-facing) or
approximate ones?**

- *Exact*: Tool A is the only one that gives bit-identical
  exact answers. Tools B, C give exact answers when they
  converge but not always. Tool D gives confidence
  intervals, not exact.
- *Approximate is fine*: any tool works; pick on
  performance and ease of use.

## 3. Mixed strategies

In real codebases, you often combine tools:

### Strategy: Framework first, MIP fallback

Try the framework. If it honest-stops, fall back to MIP. This
gives you the best of both worlds — exact polynomial-time on
the cases that fit, MIP on the rest.

```python
try:
    result = sc.min_cost_schedule(instance, cost_fn)
    if result["feasible"]:
        return result
    # In-family but infeasible: structurally impossible.
    raise InfeasibleProblem()
except NotInFamily:
    return solve_with_mip(instance, cost_fn)
```

The framework gets used on the easy structural cases (which
is most of them in practice). MIP gets used on the
exceptional cases. Total runtime drops; MIP licence cost may
drop too (you might be able to use the free CBC for the
exceptional cases since they're now rare).

### Strategy: CP-SAT pre-flight + CP-SAT solve

This is the Chapter 11 pattern. The framework pre-processes
the model, then CP-SAT solves. The framework integrates
without replacing.

### Strategy: Monte Carlo as ground truth in development; framework in production

During development, you keep a Monte Carlo simulator running
alongside the framework's calls. The simulator is your
ground truth (you trust its statistical estimates). The
framework's answers should match the simulator's, within
the confidence interval, on every input.

Once you're confident both agree, you delete the simulator
in production and keep only the framework. The simulator
stays around in a test harness for regression testing.

### Strategy: Framework for the structural answer; NetworkX for visualisation

The framework computes the structural answer (probability,
cost, etc.). NetworkX handles the visualisation — drawing
the graph, highlighting paths, generating layouts for
reports. The two integrate cleanly because NetworkX uses
similar graph representations.

## A real-world decision example

Let's say Maya (from Chapter 4) has her logistics-network
problem. She walks through the tree:

- **Q1**: variables are discrete (which package goes on which
  truck). Continue.
- **Q2**: she needs both a count (how many feasible routes)
  and an optimal cost (cheapest assignment). Continue, likely
  Tool A.
- **Q3**: she runs `sc.classify(...)` on the logistics network.
  Returns T2 (planar). Continue, Tool A is a strong fit.
- **Q4**: doesn't apply (Tool A handled it).
- **Q5**: she needs exact answers for the regulator. Tool A
  it is.

She picks the framework. Her existing MIP solver becomes the
fallback for cases that honest-stop (which she expects to be
rare).

That's the choice in five minutes. The choice tree wasn't
strictly necessary — once she knew the framework existed and
how to think about it, she could have made the choice in 30
seconds. The tree just makes the reasoning explicit.

## What this chapter taught you

1. There are six main families of tools for combinatorial
   computation: the framework, MIP, CP-SAT, Monte Carlo,
   NetworkX, and continuous optimisers.
2. Each has a structural niche. Knowing the niches lets you
   pick the right tool quickly.
3. The framework's niche is **planar / GF(2)-affine /
   matchgate-realisable** structures with **exact** answer
   requirements.
4. Mixed strategies — framework + fallback, framework
   pre-flight + existing solver, framework + MC ground truth
   — are common and effective.

This is the end of Part IV. You now have the practical
toolkit — how to read the framework's answers (Chapter 12),
how to wire it into existing systems (Chapter 13), and how
to choose between the framework and other tools (Chapter 14,
this chapter).

Part V is the long-horizon view: where this paradigm could
go in the next decade, three industries where it could
plausibly transform daily practice, and how to become a
practitioner who's part of that shift.
