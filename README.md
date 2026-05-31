# structural-computing

[![PyPI](https://img.shields.io/pypi/v/structural-computing.svg)](https://pypi.org/project/structural-computing/)

**Exact polynomial-time answers to combinatorial questions that today's
tools can only sample, estimate, or give up on** — for the subset of
problems with the right structural shape (planar, bounded-genus,
near-matchgate, GF(2)-affine). When applicable, the framework returns
bit-identical reproducible numbers in milliseconds-to-seconds. When
inapplicable, it stops honestly with a clear pointer to the right
external tool. No silent approximation.

> 📘 **New here?** Read the book first: [**Declarative Structural
> Computing — A Practitioner's Guide**](docs/book.md) (17 chapters,
> ~6 hours end-to-end; a 1-hour skim is enough to decide whether the
> framework helps your work).
>
> The book explains the *paradigm* this package embodies — what
> happens when entire codebases (100,000+ lines of Monte Carlo
> simulators, MIP timeouts, hand-rolled scheduling heuristics)
> collapse to a few lines of declarative query, in the same way
> SQL collapsed 1970s data-iteration code. It's written for
> regular humans — not mathematicians — with concrete characters,
> three runnable worked examples
> ([reliability](book/examples/09_network_reliability/),
> [scheduling](book/examples/10_schedule_optimisation/),
> [CP-SAT pre-flight](book/examples/11_cpsat_preflight/)), and
> a [one-page business case](book/01a-the-business-case-in-one-page.md)
> with concrete dollar figures.

## What this codebase / repo / library lets you do

The framework wraps a handful of polynomial-time exact algorithms
(matchgate-Holant evaluation, FKT, Kasteleyn, Hungarian, CP-SAT
diagnostic) behind a small declarative API. You ask a *question*
about a *combinatorially structured input* — how many? which is
cheapest? what's the failure probability? which configuration is
more reliable? — and the framework picks the right algorithm
and returns the exact answer. If your problem doesn't fit, the
framework refuses to guess and tells you what tool to reach for
instead. In concrete terms, this lets you:

- **Compare two configurations exactly** even when the difference is
  below Monte-Carlo's noise floor. Two network topologies, two
  reinsurance treaty structures, two CI pipeline designs that look
  equivalent to sampling — the framework returns *"Configuration B is
  90.2% more reliable, provably real, not a sampling artefact"* in
  milliseconds.

- **Compute exact rare-tail probabilities** for failure modes you'd
  otherwise have to estimate by long-running Monte-Carlo. Risk reports
  for regulators, capacity-planning analyses that need defensible
  numbers, reliability claims that have to be bit-reproducible across
  runs.

- **Count solutions to combinatorial problems exactly** rather than
  finding just one. How many valid task-resource assignments exist?
  How many distinct ways can these components be paired? Which edges
  are structural single points of failure? Standard solvers find one
  answer; this framework counts and audits the whole solution space.

- **Route different kinds of problems automatically.** The framework's
  classifier figures out which structural shape your problem has, picks
  the right exact-evaluation kernel (FKT for planar graphs, bounded-
  genus Kasteleyn for higher-genus, CH-form for stabilizer arithmetic,
  tropical Pfaffian for max-weight optimisation), and produces an
  answer with a recorded provenance you can audit.

- **Beat out-of-family problems into shape.** A graph that isn't
  natively planar can often be made tractable via reductions (gadget
  substitution, basis changes, parity-split, hybrid decomposition),
  compositions (linear combinations of in-family evaluations,
  holographic basis pairs), or recursive decomposition (treewidth-
  bounded DP, Shannon expansion, circuit cutting). The framework's
  reduction layer makes this routine.

## A taste — your first one-liner

Before the full mental model, here's the simplest possible
end-to-end use. We define two candidate network topologies as
edge lists (the framework accepts plain Python lists of tuples
for graphs), then ask the framework which one is more reliable
under random edge failures. The whole thing — install, import,
two network definitions, the comparison — fits on one screen.

```bash
pip install structural-computing
```

```python
from structural_computing import StructuralComputer

sc = StructuralComputer()

# Two candidate network topologies.
config_a = [(0, 1), (1, 2), (2, 3), (3, 0)]                  # 4-cycle
config_b = [(0, 1), (0, 2), (0, 3),                           # K_4
            (1, 2), (1, 3), (2, 3)]

# Exact rare-tail probability under independent edge failure.
print(sc.tail_probability(config_a, p_fail=0.05))    # 9.5063e-03 (exact, ~1.7 ms)
print(sc.tail_probability(config_b, p_fail=0.05))    # 9.2686e-04

# Compare them -- regulator-defensible verdict, no sampling noise.
report = sc.compare(config_a, config_b, p_fail=0.05)
print(report.explain())
# "Configuration B is 90.2% more reliable (9.5063e-03 vs 9.2686e-04).
#  This distinction is provably real (exact computation),
#  not a sampling artefact."
```

That comparison — sub-statistical-noise-floor, bit-identically
reproducible, regulator-defensible — **no off-the-shelf reliability
tool can produce**, because their internal data models are structurally
Monte-Carlo and the question's signal lives below the sampling floor.

## More worked examples

Three more one-screen examples, each in a different domain.
They use the same `StructuralComputer` object — only the
question changes. If you've read the book ([`docs/book.md`](docs/book.md)),
these are condensed versions of Chapters 9, 10, and 11; if
you haven't, they're the fastest way to see the framework's
range across reliability, optimisation, and pre-flighting an
existing CP-SAT solver.

### Min-cost matching (tropical / Hungarian / Edmonds)

Suppose each edge of a graph has a weight (a cost) and you want
the cheapest set of edges that pairs up every vertex exactly
once. This is the **min-weight perfect matching** problem, and
it shows up in production code under many names — assignment
problems, dispatching, package routing, ad-slot allocation.
The framework solves it exactly in polynomial time. The
underlying algorithm is the same one used for counting
matchings; only the arithmetic changes (replace standard
`(+, ×)` with the tropical `(min, +)` semiring). You don't
mention the semiring anywhere in the call — the question
name `min_weight_matching` selects it for you:

```python
from structural_computing import StructuralComputer
sc = StructuralComputer()

graph = [(0, 1), (1, 2), (2, 3), (3, 0)]
weights = {(0, 1): 1.0, (1, 2): 10.0, (2, 3): 1.0, (3, 0): 10.0}

result = sc.min_weight_matching(graph, weights)
# {'cost': 2.0, 'matching': [(0, 1), (2, 3)], 'feasible': True}
```

Polynomial-time exact via Hungarian (bipartite K_{n,n}) or Edmonds
blossom (general non-bipartite); no MIP timeout, no heuristic.

### CP-SAT pre-flight: faster solve via structural rewrite

If you already use Google's OR-Tools CP-SAT solver and don't
want to migrate away from it, the framework can sit *upstream*
of CP-SAT as a structural pre-processor. It reads your
`cp_model.CpModel`, identifies *rank-explosive* constraints —
cardinality (`sum(xs) == k`), at-most-k, certain all-different
patterns — and rewrites them into a form CP-SAT handles more
efficiently. The rewrite is mathematically equivalent on the
original variables; you verify equivalence on a sample and then
deploy with confidence. If no rewrite applies, the framework
honestly says so via `result.helped == False` and you solve the
original model — nothing has been changed, nothing is at risk.
The total integration is three new lines around your existing
`solver.Solve(model)` call:

```python
from structural_computing import StructuralComputer
from ortools.sat.python import cp_model

sc = StructuralComputer()
model = cp_model.CpModel()
xs = [model.NewBoolVar(f"x{i}") for i in range(4)]
model.Add(sum(xs) == 2)

result = sc.rewrite_cpsat_model(model)
# result.helped == True
# result.help_reason_text:
#   "Rewrote 1 constraint(s) to time-slot rank-1 form;
#    added 8 auxiliary boolean(s)."

if result.helped:
    solver = cp_model.CpSolver()
    solver.Solve(result.rewritten_model)
else:
    # Honest stop: solver the original model with CP-SAT
    solver = cp_model.CpSolver()
    solver.Solve(model)
```

Optionally verify the rewrite preserves the feasible set on the
original variables:

```python
verify = sc.verify_cpsat_rewrite(model, result, enumeration_limit=1000)
# verify.equivalent == True
# verify.n_original_solutions == 6  (= C(4, 2))
```

### Schedule optimisation in one line

Job-to-machine assignment, surgical rooming, nurse rostering,
truck-to-route dispatch — the standard shape is *N things to
assign to M slots subject to constraints, minimising total
cost*. Production teams typically reach for a MIP solver
(Gurobi, CPLEX, CBC) here. For the large fraction of these
problems where the cost structure has the right rank — which
is most of them in practice — the framework solves them
exactly in polynomial time via the Hungarian algorithm (under
the floor), with no commercial licence and no possibility of
solver timeout. The whole thing fits in one
`sc.min_cost_schedule(...)` call:

```python
import holant_tools
from structural_computing import StructuralComputer

sc = StructuralComputer()

jobs = [holant_tools.Job(name="J1"), holant_tools.Job(name="J2")]
machines = [holant_tools.Machine(name="M1"), holant_tools.Machine(name="M2")]
instance = holant_tools.SchedulingInstance(jobs=jobs, machines=machines)

def cost_fn(job, machine, slot):
    # cheap when matched to preferred machine
    if job.name == "J1": return 1.0 if machine.name == "M1" else 5.0
    return 5.0 if machine.name == "M1" else 1.0

result = sc.min_cost_schedule(instance, cost_fn)
# result['cost'] == 2.0
# result['schedule'] == {'J1': ('M1', 0), 'J2': ('M2', 0)}
```

## The underlying claim

Many problems people actually care about — counting valid configurations,
exact rare-tail probabilities, single-point-of-failure analysis,
regulator-grade configuration comparison, partition functions of planar
Ising models, free-fermion-equivalent quantum simulation, structural
audit of workflow graphs — sit in a mathematically structured family
called **matchgate-Holant**. For problems IN this family, exact
polynomial-time computation is possible via Kasteleyn's FKT theorem
(1961) and its bounded-genus extensions (Galluccio-Loebl). For many
problems NOT directly in this family, transformations bring them in.

The framework is the runnable form of that claim: a Python package that
takes your problem, classifies its structure, applies whatever
transformation it needs, and produces an exact answer with provenance —
or stops honestly and tells you what external tool to reach for.

The friendly entry point is `StructuralComputer` (one-liners hide every
framework internal). The underlying `Orchestrator` exposes the routing
decisions for users who want to compose custom pipelines or plug in
their own evaluators. The `transform.py` / `compose.py` / `decompose.py`
modules expose the reductions / compositions / recursive-decomposition
layer for users widening the in-family boundary.

## Where the framework helps — and where it stops

The framework's exact polynomial-time answers apply when your
problem has the right **structural shape** — typically planar
graphs, bounded-genus graphs, GF(2)-affine constraint sets, or
the matchgate-Holant family. In practice this covers a lot of
real-world problems: most physical-infrastructure networks
(grids, pipes, roads), most workflow graphs, many scheduling
and assignment instances, and a sizeable fraction of CP-SAT
models with rank-explosive constraints.

For problems that don't *natively* fit one of these shapes,
there's a second route: the reductions / compositions /
recursive-decomposition layer can sometimes *bring them in*. A
non-planar graph with a small number of "extra" edges can be
hybrid-decomposed back into planar pieces; a constraint set
with the wrong rank structure can sometimes be rewritten; a
bounded-treewidth problem can be solved by recursive DP. The
book ([`docs/book.md`](docs/book.md)) chapter on "Five patterns
that fit, five that don't" walks through this in detail.

When neither route applies — continuous mathematics with no
discretisation, random expander graphs with no exploitable
structure, problems that are genuinely too tangled — the
framework refuses to guess. It raises `NotInFamily` with a
structured explanation (the structural tier, the meters that
failed, suggested alternative tools) so you know exactly why.
**No silent approximation, ever.** That refusal is by design;
the book has a whole chapter on why honest stops are valuable.

## Status

**v1.1.0 — Production / Stable** (released 2026-05-31). `pip
install structural-computing` pulls in `holant-tools >= 0.7.0`
transparently. The public API is semver-protected for
downstream packages — see [docs/STABILITY.md](docs/STABILITY.md)
for the per-method stability contract. 302 tests across ~15 test
modules pass.

**Capability surface:**

- **Counting + reliability** (v0.1–v0.3): perfect matching counts,
  rare-tail failure probabilities, single-points-of-failure,
  regulator-grade configuration comparison.
- **Realisability + holographic toolkit** (v0.4–v0.6): MGI
  realisability check, full Cai-Lu §4 d-admissibility, Lipton-Tarjan
  5-tier auto-separator cascade (v0.4 simple → v0.5 tree-edge →
  v0.6 level-based → v0.8 fundamental-cycle → v0.9 explicit
  planar-dual), closed-form SRP for both real and complex roots.
- **Tropical / min-cost optimisation** (v0.10–v0.11): the same
  admissible-set machinery computes MIN-COST configurations under
  the (min, +) semiring — `sc.min_weight_matching`,
  `sc.min_cost_schedule`, `sc.min_cost_flow`, `sc.min_cost_roster`,
  `sc.min_cost_dedup`, `sc.tropical_instance_coordinates`.
- **CP-SAT pre-flight** (v0.13): pass a `cp_model.CpModel` to
  `sc.rewrite_cpsat_model(...)` and get back either a
  structurally cheaper rewritten model OR an explicit
  "can't help here" signal.
- **Wrapper consolidation** (v0.12): the friendly
  `StructuralComputer` wrapper delegates through the
  `Orchestrator` engine; any new question registered in the
  leaf-evaluator registry is automatically reachable via a thin
  wrapper method.

See [CHANGELOG.md](CHANGELOG.md) for the full release history.
The companion repo
[`structural-computing-bench`](https://github.com/pcoz/structural-computing-bench)
ships a per-machine cost-model calibration runner the router
loads via `apply_calibration()`.

## Runnable examples

The [`examples/`](examples/) folder contains 11 self-contained scripts
runnable after `pip install`:

| | |
|---|---|
| `01_count_matchings.py`              | exact perfect-matching count |
| `02_rare_tail_probability.py`        | exact rare-tail probability |
| `03_compare_configurations.py`       | sub-MC-noise-floor comparison |
| `04_orchestrator_dispatch.py`        | Orchestrator direct-dispatch + honest-stop |
| `05_hybrid_decomposition.py`         | exact matching count on non-planar K_{3,3} |
| `06_signature_classification.py`     | basis-aware rank ≤ 2 across symmetric signatures |
| `07_treewidth_bounded_dp.py`         | multi-bag Bodlaender DP on a tree decomp |
| `08_rationalise_weighted_matching.py`| float weights → integer arithmetic with exact descale |
| `09_holographic_basis_unlock.py`     | Hadamard basis turns 3-AND into matchgate-standard form |
| `10_crossing_elimination_k4.py`      | Cai-Gorenstein gadget at K_4's diagonal crossing |
| `11_high_degree_vertex_split.py`     | 2k-node triangle cycle realising a high-arity symmetric signature |

Each example produces a bit-identically reproducible number. See
[`examples/README.md`](examples/README.md) for the index.

## Documentation

The full documentation lives under [`docs/`](docs/) — index at
[`docs/README.md`](docs/README.md). The most useful entry
points:

- **The book** —
  [`docs/book.md`](docs/book.md). A 17-chapter narrative guide
  covering the paradigm, the business case, three worked
  examples (reliability, scheduling, CP-SAT pre-flight),
  integration patterns, and the long-horizon view. **Start here
  if you're a business analyst or a developer new to the
  framework.**
- **Tutorial** —
  [`docs/tutorial/getting-started.md`](docs/tutorial/getting-started.md).
  A 30-minute hands-on walkthrough.
- **How-to recipes** —
  [`docs/how-to/`](docs/how-to/) (min-cost scheduling, CP-SAT
  pre-flight).
- **API reference** —
  [`docs/reference/api.md`](docs/reference/api.md): every
  public method on `StructuralComputer` with signature, return
  type, and one-line description.
- **Stability contract** —
  [`docs/STABILITY.md`](docs/STABILITY.md). Per-symbol stability
  tiers (Stable / Experimental / Internal) under semver.
- **Architecture deep dive** —
  [`docs/architecture.md`](docs/architecture.md). Comprehensive
  system reference for contributors.

The companion worked-examples repo
[`free-fermion-quantum-simulation`](https://github.com/pcoz/free-fermion-quantum-simulation)
has the original development-trail with brute-force verification
on every routine; this package is the **simplified PyPI form**.

## Built on holant-tools

This package depends on
[`holant-tools`](https://github.com/pcoz/holant-tools) — the mathematical
engine providing Pfaffian / FKT computation, Kasteleyn orientations,
the corrected dart-chain passage-arc formula, basis-aware matchgate
rank, the CH-form stabilizer representation, and the full set of
matchgate-Holant tractability primitives.

```python
import holant_tools  # automatically installed as a dependency
```

## License

MIT-with-attribution. See [LICENSE](LICENSE). Visible attribution to
**Edward Chalk (sapientronic.ai)** is required for publications,
presentations, derivative works, and products.

## Citation

If you use this package in published work, please cite:

```
Edward Chalk (sapientronic.ai). "structural-computing: declarative
structural computation in Python." Version 1.0.0, 2026.
https://github.com/pcoz/structural-computing
```

## Roadmap

- **v0.3.0a1**: closed the calibration loop (route's `cost` field is
  `log2(seconds)` when calibrated, with `cost_unit` meter always
  present), shipped the holographic toolkit
  (`HolographicBasisPair.transform_signature_general` for non-symmetric
  signatures, `discover_basis` + `discover_common_basis` for Cai-Lu
  SRP single- and multi-signature), and filled in every v0.2-era
  `NotImplementedError` sketch (`Projection`, `BranchSum`,
  `PlanarSeparator`, `RecursiveCircuitCut`). 229 tests passing.
- **v0.4.0a1**: matchgate-identity (MGI) realisability check for
  general (non-symmetric) signatures via `holant_tools.non_symmetric`;
  `PlanarSeparator(auto=True)` mode invoking the simple BFS-layer
  case of Lipton-Tarjan 1979; closed-form SRP shortcut catching
  rank-1 signatures whose recurrence roots lie outside the v0.3
  search's `[-2, +2]` grid. 262 tests passing.
- **v0.5.0a1**: full Cai-Lu §4 d-admissibility at even arity ≥ 6
  odd-parity (augmented-Pfaffian Plücker enumeration on the
  (n+1)-vertex Kasteleyn matrix, |S|=2 case, prototype-in-place);
  spanning-tree fundamental-cycle backup for Lipton-Tarjan when
  the BFS-layer simple case fails on fat-middle-level planar
  graphs; closed-form SRP for complex-roots rank-2 signatures via
  `T = [[1, -α], [0, β]]`. 272 tests passing.
- **v0.6.0a1** (shipped): D1 promoted the v0.5 augmented-Plücker
  helper to `holant-tools v0.6.0` (architectural cleanup, math
  primitive now lives in the engine); D2 added a level-based +
  articulation-augmentation backup to `_lipton_tarjan_separator`
  catching star K_{1,n} and K_{2,n} adversarial graphs; D3 extended
  the augmented-Plücker enumeration with the m = 3 (|S|=4)
  configuration via `holant-tools v0.6.1` (count at arity 8: 280 →
  560; at arity 10: 1260 → 5460). 281 tests passing.
- **v0.7 arc (2026-05-31)**: PyPI publication unblock. All three
  packages (holant-tools, structural-computing,
  structural-computing-bench) landed on PyPI for the first time.
  No version bumps; just availability.
- **v0.8.0a1**: D1 — full augmented Plücker enumeration across
  every viable m (m ∈ {1, 3, 5, 7, ...}) via holant-tools
  v0.7.0. D2 — fundamental-cycle backup as the 4th tier of the
  Lipton-Tarjan cascade. 285 tests passing.
- **v0.9.0a1**: full LT 1979 with explicit planar-dual as the
  5th tier of the LT cascade. With rotation system input, the
  cascade is now theoretically complete per LT 1979's existence
  guarantee. 290 tests.
- **v0.10.0a1**: tropical optimisation wired into the
  orchestrator. `min_weight_matching` and `min_cost_schedule`
  reachable via `StructuralComputer`. 295 tests.
- **v0.11.0a1**: finish tropical wiring. `min_cost_flow`,
  `min_cost_roster`, `min_cost_dedup`,
  `tropical_instance_coordinates` all reachable. 299 tests.
- **v0.12.0a1**: wrapper consolidation. `StructuralComputer`
  delegates 13 single-leaf methods through the internal
  `Orchestrator` instance — single source of truth for
  evaluation logic.
- **v0.13.0a1**: CP-SAT diagnostic + rewrite layer.
  `sc.rewrite_cpsat_model(model)` returns a structurally cheaper
  rewritten `cp_model.CpModel` or an explicit "can't help"
  signal. 302 tests.
- **v1.0.0** (2026-05-31): production-ready release. API
  stability contract in `docs/STABILITY.md`. Documentation
  pass + first calibration run + Development-Status classifier
  bumped to Production/Stable.
- **v1.1.0** (current, 2026-05-31): post-1.0 polish. Extended
  bench coverage to 11 calibrated leaves (was 4); Diátaxis-
  style docs restructure (`docs/tutorial/`, `docs/how-to/`,
  `docs/reference/`, `docs/explanation/`); 5 symbol groups
  promoted from Experimental to Stable. Plus a 17-chapter
  narrative ebook under `book/` (index: `docs/book.md`).
  302 tests.
- **v1.2.0+** (next): a domain-specific DSL on top of the
  framework — most likely workflow-systems first, then the
  catastrophe-modelling "literal one-liner" form per the
  research roadmap.
