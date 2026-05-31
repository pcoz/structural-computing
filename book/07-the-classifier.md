# Chapter 7 — The classifier: your tool decides what tool it should use

There's a piece of the framework you mostly don't have to think
about — it sits behind every method call, doing its job
invisibly. But understanding it makes everything else click.

It's called the **classifier**. Its job is to look at the
problem you handed in and decide *what kind of algorithm should
handle this*. It's the framework's quiet brain.

This chapter tells you how the classifier thinks. We'll do it
through a small example, so the abstract idea lands on
something concrete.

## Why the classifier exists

Different problems need different algorithms. The framework
has lots of algorithms under the floor. If you (the user)
chose them all by hand, the framework would be exhausting to
use. You'd have to know:

- "This graph is planar so I should use FKT."
- "This bipartite assignment problem so I should use Hungarian."
- "This constraint set is linear so I should use Gaussian
  elimination over GF(2)."
- "This rotation system is for a torus so I should use the
  bounded-genus Kasteleyn evaluator."

A specialist might know all of those off the top of their
head. A normal human doesn't, shouldn't have to, and is the
person the framework was built for.

So the framework picks the algorithm for you. The piece that
picks is the classifier.

## How the classifier thinks

You hand the classifier a problem — a graph, say. It produces
a small report called a **Classification**. The report has
four parts:

1. **Tier** — a one-letter-plus-number label like `T2` or `T4`
   or `T5`. The tier is the classifier's *category* for your
   problem. We'll meet the tiers in a moment.
2. **In-family flag** — `True` or `False`. Is this a problem
   the framework can handle exactly? `True` means yes; `False`
   means the framework will honest-stop.
3. **Meters** — a dictionary of measurements the classifier
   took. Things like *how many vertices?*, *what's the genus
   of the planar embedding?*, *is the rotation system
   cellular?*, *is this a connected graph?*. These are diagnostic
   readings; they help the algorithm picker.
4. **Reasoning** — a short English sentence explaining how
   the classifier reached its verdict. Things like *"planar
   embedding with 16 vertices, genus 0, in-family"*.

You can ask for the classification any time:

```python
from structural_computing import StructuralComputer
sc = StructuralComputer()

cls = sc.classify(my_graph)
print(cls.tier, cls.in_family, cls.reasoning)
```

Most of the time you won't bother — you'll just call
`sc.count_matchings(...)` and let the classifier work
invisibly. But when something surprising happens, the
classification is the first thing to look at.

## The tiers

The framework's tiers describe *categories of problem* that
the classifier recognises. Here's the lay of the land:

| Tier | What it means | In-family? |
|---|---|---|
| **T0** | Linear constraint set over GF(2): `Ax = b mod 2` | Yes |
| **T1** | Quadratic constraint set over GF(2) | Yes |
| **T2** | Planar graph (no edge crossings) | Yes |
| **T3** | Symmetric matchgate signature | Yes |
| **T4** | Bounded-genus graph (planar with a few "handles") | Yes |
| **T5** | Non-planar graph, no exploitable structure | No |
| **T6** | Continuous problem (the framework doesn't do these) | No |
| **T7** | Unknown shape / can't be classified | No |

The tiers from T0 to T4 are all *in-family*. The framework has
polynomial-time exact algorithms for each. The tiers from T5
to T7 are out-of-family — the framework will tell you so
honestly.

Notice the tiers don't perfectly cleave by data type. T2 and
T4 are both about graphs; T0 and T1 are both about constraints;
T3 is about signatures (a more abstract mathematical object
we'll meet later). The framework uses the same orchestrator
to dispatch across all of them.

## A worked example: classifying a 3x3 grid

Let me show you the classifier in action. Suppose I have a 3x3
grid graph — nine nodes arranged in three rows of three,
connected to their horizontal and vertical neighbours. There
are 12 edges total (6 horizontal, 6 vertical).

```python
import structural_computing

# The 3x3 grid graph
vertices = [(r, c) for r in range(3) for c in range(3)]
edges = []
for r in range(3):
    for c in range(3):
        if c < 2: edges.append(((r, c), (r, c+1)))
        if r < 2: edges.append(((r, c), (r+1, c)))

graph = {"vertices": vertices, "edges": edges}

sc = structural_computing.StructuralComputer()
cls = sc.classify(graph)
print(cls.tier, cls.in_family, cls.reasoning)
# Tier T2, in_family=True, reasoning="planar embedding..."
```

The classifier returns Tier T2 (planar), in_family=True. From
here the framework knows that any matching question on this
graph can be answered with the polynomial-time FKT algorithm.
If I now call:

```python
sc.count_matchings(graph)
```

The framework consults the classification, sees T2, looks up
the leaf evaluator registered for `(T2, matching_count)`, and
runs it. The leaf evaluator uses FKT under the hood. The
answer comes back in milliseconds.

You never had to know any of this happens. You wrote
`sc.count_matchings(graph)`. The classifier ran. The leaf
evaluator was picked. The exact integer answer came back. Job
done.

## A worked example where the classifier honest-stops

Now suppose I try a different graph — the complete graph K₅,
where 5 nodes are all connected to every other node.

```python
vertices = [0, 1, 2, 3, 4]
edges = [(u, v) for u in vertices for v in vertices if u < v]
graph = {"vertices": vertices, "edges": edges}

cls = sc.classify(graph)
print(cls.tier, cls.in_family, cls.reasoning)
# Tier T5, in_family=False, reasoning="non-planar graph (K5
# has no planar embedding); no exact path in the framework"
```

K₅ is famously non-planar. The classifier recognises this and
reports Tier T5, in_family=False. The reasoning tells me
*why*: K₅ has no planar embedding.

If I now try:

```python
sc.count_matchings(graph)
# raises: NotInFamily: graph is T5 (non-planar);
#         no exact path in the framework.
```

The framework doesn't try to compute anything. It refuses,
referring back to the classification. The error tells me to
look at the tier and the reasoning. If I want to count
matchings on K₅ anyway, I can fall back to:

- A brute-force enumeration (the framework's `verifier` module
  has `brute_force_count_matchings` for this; works for small
  graphs).
- An external tool (NetworkX for moderate-size graphs; CP-SAT
  if formulated as a constraint problem).

The framework didn't give me a wrong answer dressed up as a
right one. It told me clearly what's possible and what isn't.
That's the honest stop pattern (Chapter 8 is dedicated to it).

## What the meters tell you

The classifier's `meters` field is the most diagnostic part of
the classification. It contains things like:

```python
cls.meters
# {'n_vertices': 9, 'n_edges': 12, 'genus': 0,
#  'rotation_provided': True, 'classifier': 'classify_graph'}
```

Most users don't need to read meters directly. But if something
unexpected happens — say, a problem you thought was planar
classifies as T4 (bounded-genus) — the meters tell you why.

For instance, a "graph that looks planar" might actually have
been drawn with extra crossings due to a sloppy rotation
system in the input. The meters might reveal `genus=1`,
meaning the framework reads your input as if it sits on a
torus rather than a flat plane. That's almost always a hint
that your input is malformed and the planarity check needs
attention.

So while you don't usually look at meters, when something
surprising happens, the meters are your debug surface.

## How leaf evaluators get picked

After classification produces a tier, the framework's
**orchestrator** (we'll meet it in passing in later chapters)
consults a registry:

```python
# Roughly (with a lot of detail elided):
DEFAULT_LEAF_REGISTRY = {
    ("T2", "matching_count"):    _matching_count_leaf,
    ("T2", "min_weight_matching"): _min_weight_matching_leaf,
    ("T2", "tail_probability"):  _tail_probability_leaf,
    ("T0", "count_solutions"):   _count_solutions_leaf,
    ...
}
```

It looks up `(tier, question)` and finds the matching leaf
evaluator. The leaf evaluator is the actual algorithm — the
function that does the polynomial-time computation.

This is the registry pattern. Adding new question types is a
matter of registering a new entry in the dictionary. As of
v1.1.0, the framework has about 20 entries in this registry,
covering counting, witness-finding, min-cost optimisation,
reliability, CP-SAT pre-flight, and a few others.

You can also write your own leaf evaluators and register them
in a private orchestrator instance — useful if you have a
specialised algorithm for some niche problem shape. The
v1.1.0 stability contract (`docs/STABILITY.md`) makes this
extension pattern semver-protected.

## Why this design works

The classifier-and-orchestrator pattern is what makes the
framework feel like a single tool rather than a collection of
unrelated algorithms.

If you compare this to, say, a Python script that has to
choose between scipy.optimize and CVXPY and Gurobi and CPLEX,
each with its own interface, its own input format, its own
quirks — the contrast is stark. The framework hides all of
that. You call `sc.count_matchings(graph)` and the right
algorithm runs. The classifier is what makes that possible.

If you compare it to a database query optimiser — which reads
your SQL, looks at the data's indexes and statistics, picks
hash join vs. merge join vs. nested loop — the parallel is
exact. The classifier is the framework's query optimiser. It's
what lets the user write a declarative call instead of an
imperative recipe.

## In summary

The classifier is the framework's quiet brain. It runs on
every call. It produces a classification with a tier, an
in-family flag, meters, and reasoning. The tier plus the
question determines which leaf evaluator handles the call.
When the tier is in-family, the answer comes back exactly.
When the tier isn't, you get a structured honest stop instead.

You will mostly not think about the classifier. That's a
feature. But when something surprising happens, the very first
thing to do is `print(sc.classify(my_problem))` and read the
tier, the flag, and the reasoning. Almost every weird symptom
the framework can produce is explained by some unexpected
classification.

The next chapter — Chapter 8 — is the final chapter of Part II.
It's about what happens when the classifier says "no" — the
honest stop pattern, and why it's a feature instead of a
limitation.
