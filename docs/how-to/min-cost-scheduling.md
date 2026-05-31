# How to: min-cost scheduling

You have N jobs to assign to M machines, with a per-(job, machine,
slot) cost. You want the cheapest valid assignment, exactly,
polynomial-time.

## The one-liner

```python
import holant_tools
from structural_computing import StructuralComputer

sc = StructuralComputer()

jobs = [holant_tools.Job(name="J1"), holant_tools.Job(name="J2")]
machines = [holant_tools.Machine(name="M1"), holant_tools.Machine(name="M2")]
instance = holant_tools.SchedulingInstance(jobs=jobs, machines=machines)

def cost_fn(job, machine, slot):
    return abs(int(job.name[1:]) - int(machine.name[1:]))

result = sc.min_cost_schedule(instance, cost_fn)
# result['cost'] == 0.0
# result['schedule'] == {'J1': ('M1', 0), 'J2': ('M2', 0)}
```

## What `cost_fn` is

A callable `(job, machine, slot) -> float` returning the cost of
assigning that job to that machine at that time slot. Higher
cost = worse assignment.

## Constraints

`min_cost_schedule` accepts three optional per-job restrictions:

```python
result = sc.min_cost_schedule(
    instance,
    cost_fn,
    allowed_machines={"J1": {"M1"}, "J2": {"M2"}},
    time_windows={"J1": (0, 1), "J2": (1, 2)},
    forbidden_edges={("J1", "M2", 0), ("J2", "M1", 0)},
)
```

- `allowed_machines`: per-job set of allowed machine names.
- `time_windows`: per-job `(start_slot, end_slot)` inclusive range.
- `forbidden_edges`: set of `(job_name, machine_name, slot)` triples
  to exclude.

## What you get back

```python
{
    "cost": float,          # the optimal total cost
    "schedule": dict,       # {job_name: (machine_name, slot)}
    "feasible": bool,       # False if no valid schedule exists
}
```

## When it works

The tropical Pfaffian dispatch handles:
- **Bipartite** instances via Hungarian (`O(n^3)`).
- **General non-bipartite** via Edmonds blossom (`O(n^3)` with
  the NetworkX optional dependency).
- **Both** are exact polynomial-time — no MIP timeout, no
  heuristic.

If neither path applies (degenerate inputs, missing networkx for
non-bipartite), the leaf evaluator falls back to enumeration.
You'll see this reflected in `feasible: False` for inputs the
fallback can't solve.

## Related capabilities

- [`sc.min_cost_flow(instance)`](../reference/api.md#min_cost_flow)
  — for network-flow problems.
- [`sc.min_cost_roster(instance, preference_fn)`](../reference/api.md#min_cost_roster)
  — for employee-shift assignment.
- [`sc.min_cost_dedup(instance, similarity_fn)`](../reference/api.md#min_cost_dedup)
  — for record-to-entity assignment.
- [`sc.tropical_instance_coordinates(instance, cost_fn)`](../reference/api.md#tropical_instance_coordinates)
  — one-call "is this instance well-suited?" structural
  diagnostic.

## Comparison with MIP / CP-SAT

`min_cost_schedule` gives **exact** answers in polynomial time
**when the problem fits the matchgate-Holant shape**. CP-SAT and
MIP solvers handle a broader problem class but at exponential
worst-case cost; on this specific shape (square assignment),
they're orders of magnitude slower than the Hungarian path.

If you're not sure whether your problem fits, run
`sc.tropical_instance_coordinates(instance, cost_fn)` first — it
tells you in `O(n^3)` whether the polynomial-time path applies.
