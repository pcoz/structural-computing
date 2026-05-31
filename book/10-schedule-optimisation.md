# Chapter 10 — Schedule optimisation: from MIP timeout to one-liner

Chapter 9 dealt with a Monte Carlo simulator that didn't need
to exist. This chapter deals with a different kind of code that
also doesn't need to exist: a Mixed Integer Programming (MIP)
solver pipeline for routine scheduling problems.

The runnable example lives at
[`book/examples/10_schedule_optimisation/`](examples/10_schedule_optimisation/).

## The scenario

Imagine you work at a mid-sized hospital. Your job is to
schedule operating-room (OR) slots: each morning, you have a
list of surgeries that need to happen, and a list of available
operating rooms with their staff schedules. You need to assign
each surgery to a room and a time slot, minimising overall
cost.

The cost function is not trivial. It accounts for:

- Surgeon preference for specific operating rooms.
- Whether a given OR has the right equipment for a given
  procedure.
- Setup and turnover times between procedures in the same OR.
- Overtime pay if a surgery runs late.
- Patient priority (cancer surgeries get earlier slots than
  elective procedures).
- Equipment dependencies (only OR 3 has the robot; only OR 6
  has the C-arm).

You currently use a Mixed Integer Programming solver (Gurobi
or CPLEX commercially, or CBC open-source) to compute the
optimal schedule each morning. The MIP model has about 50,000
binary variables (one for each (surgery, room, slot) triple)
and tens of thousands of constraints. Solving takes anywhere
from a few minutes to several hours depending on the day.

Sometimes — once or twice a month — the solver doesn't
converge in time. Your team has to ship a schedule generated
by a hand-tuned heuristic, which is usually 10-15% worse than
the MIP optimum. On those mornings, your costs go up
noticeably.

## What the existing code looks like

The MIP model your team maintains is about 3,000 lines of
Python that builds a Gurobi model. It looks roughly like
this (heavily abridged):

```python
import gurobipy as gp
from gurobipy import GRB

def build_or_schedule_model(surgeries, rooms, slots, costs):
    m = gp.Model()
    m.params.TimeLimit = 1800  # 30 minutes max

    # Binary variable for each (surgery, room, slot) triple.
    x = {}
    for s in surgeries:
        for r in rooms:
            for t in slots:
                x[s, r, t] = m.addVar(vtype=GRB.BINARY, name=f"x_{s}_{r}_{t}")

    # Each surgery is assigned to exactly one (room, slot).
    for s in surgeries:
        m.addConstr(gp.quicksum(x[s, r, t] for r in rooms for t in slots) == 1)

    # Each (room, slot) has at most one surgery.
    for r in rooms:
        for t in slots:
            m.addConstr(gp.quicksum(x[s, r, t] for s in surgeries) <= 1)

    # Setup/turnover between consecutive surgeries
    # ... about 200 more lines ...

    # Equipment dependencies
    # ... about 100 more lines ...

    # Objective: minimise total cost
    m.setObjective(
        gp.quicksum(x[s, r, t] * costs[(s, r, t)] for s in surgeries for r in rooms for t in slots),
        GRB.MINIMIZE,
    )

    return m

def solve_daily_schedule(surgeries, rooms, slots, costs):
    m = build_or_schedule_model(surgeries, rooms, slots, costs)
    m.optimize()
    if m.status == GRB.OPTIMAL:
        return extract_schedule(m, surgeries, rooms, slots)
    elif m.status == GRB.TIME_LIMIT:
        log_timeout()
        return fallback_heuristic(surgeries, rooms, slots, costs)
    else:
        raise Exception(f"unexpected status: {m.status}")
```

The full code is much larger — about 3,000 lines including
the input data layer (loading from your hospital's electronic
medical records system), the output layer (producing a
schedule in the format the OR coordinators need), the
fallback heuristic for when Gurobi times out, the
post-processing for shift-handoff rules, and so on.

The MIP-solving line, `m.optimize()`, is the bottleneck. Most
mornings it returns in a few minutes. Some mornings it doesn't.

## What's going on under the floor

A MIP solver is a remarkable piece of software. It does
exponential-time enumeration over the space of binary
variables, but with extensive cleverness — branch and bound,
cutting planes, presolve, heuristics — to avoid most of the
exponential. For "easy" MIPs it returns in seconds. For "hard"
MIPs it takes forever.

Your OR scheduling problem is borderline. Most days the
problem is structurally easy and the solver returns quickly.
On the bad mornings, something about the specific surgery mix
puts the problem in a region of the solver's space that's
genuinely hard. The exponential rears up. The solver gives up
at the 30-minute time limit.

The MIP solver is solving the problem in the most general way
possible. It doesn't know that, structurally, your problem is
*a kind of assignment problem with rank-1 cost structure*.
That's a mathematical category that has a much faster
algorithm — the Hungarian algorithm, which runs in `O(n^3)`,
exactly, with no possibility of timeout.

The framework knows.

## The framework form

Here's the entire schedule optimisation, framework form:

```python
import holant_tools
from structural_computing import StructuralComputer

sc = StructuralComputer()

def solve_daily_schedule(surgeries, rooms, costs):
    # Translate surgeries and rooms into framework objects.
    jobs = [holant_tools.Job(name=s.id) for s in surgeries]
    machines = [holant_tools.Machine(name=r.id) for r in rooms]
    instance = holant_tools.SchedulingInstance(
        jobs=jobs, machines=machines,
    )

    # Cost function: (surgery_id, room_id, slot) -> dollars.
    def cost_fn(job, machine, slot):
        return costs[(job.name, machine.name, slot)]

    # The actual question. One line.
    result = sc.min_cost_schedule(instance, cost_fn)

    return result
```

About 15 lines including the translation to framework objects.
The schedule comes back exactly, polynomial-time, no possibility
of timeout. The result is a dict with the cost and the
assignment.

Compare:

| | MIP form | Framework form |
|---|---|---|
| **Lines of optimiser code** | ~500 | ~15 |
| **Total lines** | ~3,000 | ~300 (input/output preserved) |
| **Runtime** | minutes-to-hours, sometimes timeout | sub-second, no timeout possible |
| **Answer quality** | optimal when solver converges, heuristic when not | optimal, always |
| **Reproducibility** | depends on Gurobi version/license/threading | bit-identical across machines |
| **Cost** | Gurobi licence ($10k+/year per developer) | open-source |

The big win isn't just the lines saved. It's that the
**bad-morning case goes away**. The framework doesn't time
out. It always returns the exact optimum.

## When this works and when it doesn't

The framework's `min_cost_schedule` works when the underlying
cost structure has "tropical rank ≤ 2". That's a technical
condition, but in practice it covers a huge fraction of
real-world assignment / scheduling problems — specifically:

- **Bipartite assignment with separable costs.** Each cost is
  of the form `cost(job, machine, slot) = a(job, machine) +
  b(job, slot) + c(machine, slot)`, possibly with additional
  rank-1 structure. Common in scheduling.
- **Pure assignment** (no time slots, just job-to-machine).
  Always tropical rank 1.
- **Min-cost flow with rank-1 cost rates.** Common in
  routing and logistics.

The framework can detect this. You can pre-check before
committing:

```python
coords = sc.tropical_instance_coordinates(instance, cost_fn)
print(coords.admissibility_rank_1, coords.polynomial_time_optimisation)
# True True  -> framework will solve in polynomial time
# False True -> framework solves but slower than rank-1 case
# False False -> framework will honest-stop; use MIP instead
```

If both come back True, you're golden. If
`polynomial_time_optimisation` is False, the framework
honest-stops and your existing MIP pipeline handles it. (The
MIP pipeline is now the *exceptional path* rather than the
default path.)

## Hospital scheduling: the typical answer

For most real hospital OR scheduling problems, the cost
structure passes the rank-1 check. Surgeons have preferences,
equipment has constraints, but the costs are mostly separable
across job, machine, and slot. The framework handles them.

The bad mornings — the ones where the MIP solver would have
timed out — are typically the ones where the cost structure
has *unusually high rank*, often because of an unusual mix of
surgeries with conflicting equipment needs. On those mornings,
the framework's tropical_instance_coordinates check fails, and
the framework honest-stops with a clear message:

```
sc.min_cost_schedule(instance, cost_fn)
# returns: {'cost': None, 'schedule': None, 'feasible': False}
# coords.polynomial_time_optimisation == False
```

You see this *before* committing to a solver run. You fall back
to the MIP solver explicitly, knowing why. The fallback case is
documented in your pipeline rather than emerging from a
mysterious timeout.

## A note on the runnable example

The accompanying runnable code at
[`book/examples/10_schedule_optimisation/`](examples/10_schedule_optimisation/)
demonstrates the framework call on a small but realistic
scheduling instance — 5 surgeries to 5 rooms with a structured
cost function. The framework returns the exact optimum in
milliseconds. The same example with a simple brute-force
"try every assignment" approach has 5! = 120 possibilities and
is essentially a worst-case scenario for naive approaches; at
6×6 it's 720, at 10×10 it's 3.6 million, and the brute-force
runtime explodes.

The framework's runtime stays sub-second across all of these.

Run it to see the contrast. Then look at the framework code
and the brute-force code and compare. The MIP-form code would
be hundreds of lines; the brute-force code is dozens; the
framework code is one line.

## What this chapter taught you

1. **MIP solvers are general-purpose.** They handle a wide
   range of problems but at unbounded worst-case cost. For
   problems with the right structural shape, they're
   overkill.
2. **Assignment problems often have rank-1 cost structure.**
   When they do, the Hungarian algorithm — wrapped by the
   framework as `min_cost_schedule` — solves them exactly in
   polynomial time. No solver timeout possible.
3. **The framework's `tropical_instance_coordinates` is a
   pre-flight check.** Run it before committing; if the
   structure fits, you save the MIP solver's licence cost,
   developer time, and unpredictable runtime; if it doesn't,
   you honest-stop and fall back to MIP explicitly.

Next chapter: the third worked example — CP-SAT pre-flight,
where the framework integrates with an existing CP-SAT
pipeline rather than replacing it.
