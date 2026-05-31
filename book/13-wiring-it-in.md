# Chapter 13 — Wiring structural-computing into existing systems

The framework lives well alongside other tools. This chapter is
about the practical art of plugging it into an existing
codebase — what goes where, how to organise the integration,
and what patterns survive contact with production.

The chapter is in four parts:

1. **Where the framework lives in your stack.**
2. **The two big integration patterns** (replacement vs.
   pre-flight).
3. **Error handling at integration boundaries.**
4. **Calibration and the cost model.**

## 1. Where the framework lives in your stack

The framework is a library you import. It runs in the same
process as your code, reads in-memory Python objects, and
returns in-memory Python objects. It doesn't talk to a
database, doesn't spawn subprocesses, doesn't make network
calls (except optionally to PyPI when you `pip install` it).

The natural placement is:

```
your-application/
├── adapters/           # convert your data → framework's format
│   ├── from_postgres.py
│   ├── from_csv.py
│   └── from_existing_objects.py
├── core/
│   └── analysis.py     # uses sc.* methods
├── handlers/           # turn framework results into your output format
│   ├── to_regulator_report.py
│   ├── to_dashboard.py
│   └── to_database.py
└── tests/
    └── ...
```

The framework lives in `core/`. Your adapters and handlers
sit around it. The adapters translate inbound data into the
framework's expected shapes (graph dicts, constraint sets,
scheduling instances). The handlers translate the framework's
outputs into whatever downstream systems need.

This separation is worth taking seriously. If the framework
later supports a new data format, you change the adapters
without touching the analysis core. If your downstream
reporting changes, you change the handlers without touching
the analysis core. The core stays small — typically a few
hundred lines, sometimes less.

## 2. The two big integration patterns

There are two distinct patterns for using the framework, and
the choice of pattern shapes everything else.

### Pattern A — Replacement

The framework replaces an existing component entirely. Your
old code had a Monte Carlo simulator, a brute-force matching
counter, or an MIP solver. The framework's call replaces it.
Everything else in the pipeline — input loading, output
formatting, business logic — stays.

This is the Chapter 9 and Chapter 10 pattern. The structural
move is:

```python
# OLD: 1,200 lines of Monte Carlo
def old_failure_probability(graph, p_fail):
    return run_monte_carlo_sim(graph, p_fail, n_samples=1_000_000)

# NEW: 2 lines
def new_failure_probability(graph, p_fail):
    return sc.tail_probability(graph, p_fail)
```

The old function still lives in the codebase initially.
You point new callers at the new function. You measure both
in parallel for a while. Once the new function has proved
itself, you delete the old.

This "double-write, then cut over" pattern is the safest way
to do the replacement. The framework's answer is exact; the
old simulator's answer should be approximately equal to it.
If they ever disagree by more than the simulator's
confidence interval, you've found a bug somewhere (often in
how the input data is being translated, sometimes in the
framework, sometimes in the simulator). You want to find
that bug while the old code is still around to compare
against.

### Pattern B — Pre-flight

The framework runs *alongside* an existing component, making
it faster but not replacing it. Your existing CP-SAT model
(or MIP, or whatever) still runs; the framework just
pre-processes the input.

This is the Chapter 11 pattern:

```python
def solve_problem(inputs):
    model = build_existing_model(inputs)

    # Pre-flight: try the framework's rewrite.
    result = sc.rewrite_cpsat_model(model)

    solver = cp_model.CpSolver()
    if result.helped:
        return solver.Solve(result.rewritten_model)
    else:
        return solver.Solve(model)
```

The integration is three new lines (`result = ...`,
`if result.helped: ...`, `else: ...`). The existing code is
unchanged. The new code can be removed without breaking
anything.

This pattern is much lower-risk than replacement. The
framework is purely additive — it never produces a *wrong*
answer for the original code path, because the original code
path runs unchanged when the framework can't help. The worst
case is "we paid a few milliseconds of pre-flight time and
got no benefit", which is small.

### Which pattern to use

- If the existing component is **slow, approximate, or
  expensive**, and the framework can produce an *exact*
  answer for the same question — use **replacement**. You'll
  save lines of code, runtime, and money.
- If the existing component is **fine on most cases but
  sometimes slow**, and the framework can speed up the slow
  cases — use **pre-flight**. You don't lose the existing
  component's coverage; you just speed up the cases the
  framework knows how to help.

In practice, most teams adopt the pre-flight pattern first
(low-risk integration), prove the framework on real workloads,
and then promote it to replacement once they're confident.

## 3. Error handling at integration boundaries

Your existing code probably has assumptions about its own
behaviour that don't quite match the framework's. The most
common mismatches:

### Mismatch 1 — Existing code never throws; framework does

Your Monte Carlo simulator might never raise an exception.
Worst case it returns garbage. Your code downstream assumes
the simulator always returns *something*.

The framework's honest stops raise `NotInFamily` exceptions.
If you swap the framework in without handling the exception,
the next layer of code crashes when an out-of-family input
arrives.

The fix is to wrap the framework call in a try/except at the
integration boundary:

```python
from structural_computing import StructuralComputer, NotInFamily

def safe_tail_probability(graph, p_fail):
    try:
        return {
            "p": sc.tail_probability(graph, p_fail),
            "method": "structural-computing exact",
            "auditable": True,
        }
    except NotInFamily as e:
        # Fall back to existing simulator (or honest-stop upstream).
        return {
            "p": old_monte_carlo_sim(graph, p_fail),
            "method": "monte-carlo (fallback)",
            "auditable": False,
            "framework_classification": e.classification.tier,
        }
```

This pattern — try framework, catch honest stop, fall back —
makes the integration robust. It also gives you observability:
you can log how often the fallback fires and what
classification triggered it.

### Mismatch 2 — Existing code expects a single numeric answer; framework returns a dict

For methods like `min_weight_matching` that return dicts, the
existing code might expect a single float. The integration
needs to unpack:

```python
result = sc.min_weight_matching(graph, weights)
if not result["feasible"]:
    raise InfeasibleProblem(graph)
old_consumer.use_cost(result["cost"])
old_consumer.use_assignment(result["matching"])
```

For each dict-returning method, decide upfront how your code
handles infeasibility. The framework returns `feasible: False`
when no valid configuration exists; your code should either
honest-stop, fall back to a heuristic, or surface the
infeasibility to the user. Don't silently substitute
`cost = inf` and continue; that's the silent-failure pattern
the framework is designed to prevent.

### Mismatch 3 — Existing code's results are bit-unstable; framework's are bit-stable

The framework's results are bit-identical across machines
(modulo last-digit floating-point variation). Your existing
code's results may vary depending on RNG seeds, thread
scheduling, library versions.

If your downstream code has tests that pin specific values
(e.g., `assert result == 0.0312`), those tests will start
working differently when you swap in the framework. Some
will become *more* stable (good); some may flap if the test
was tuned to the simulator's specific bias (bad).

The right fix is usually to relax the tests to assert
approximate equality with a tolerance, OR to pin to the
framework's exact value once you've verified it.

## 4. Calibration and the cost model

The framework's orchestrator has an optional cost model. By
default, when deciding which leaf evaluator to dispatch to,
the orchestrator uses a heuristic cost (`log₂(operations)`)
that's good enough for most cases but not specific to your
machine.

If you care about latency-budgeting — "this method needs to
return in under 500 ms on this hardware" — the framework
ships a calibration system that produces wall-clock cost
models specific to your hardware. Wall-clock cost is much
more useful than `log₂(ops)` when you're scheduling work or
deciding which path to take based on time budget.

The calibration is done by a companion package,
`structural-computing-bench`. The flow:

```bash
pip install structural-computing-bench
python -m structural_computing_bench  # ... or scripts/run_calibration.py
```

This runs the framework's default-evaluator menu on your
machine, fits a cost curve per `(tier, question)`, and writes
the result to a Python file. Load it:

```python
from structural_computing import apply_calibration
import my_calibration_data as cdata
apply_calibration(cdata.CALIBRATED_COSTS)
```

After this, the orchestrator's cost predictions use
wall-clock seconds on your hardware. Most downstream code
doesn't care, but if you do (because you're scheduling
real-time work, choosing between framework paths, or
budgeting), this is where to look.

The default cost model is good enough for most cases. If
you're hitting it as a limitation, you'll know.

## A small pattern checklist

Before deploying a framework integration to production:

- [ ] Adapter: translates upstream data to the framework's
  expected shape.
- [ ] Handler: translates framework results to downstream
  expectations.
- [ ] Exception handling: catches `NotInFamily`, decides
  whether to fall back, propagate, or honest-stop upstream.
- [ ] Feasibility handling: handles `feasible: False` for
  methods that can return it.
- [ ] Logging: records framework method, classification tier,
  and outcome for each call. Useful for monitoring.
- [ ] Tests: unit-tested on representative inputs, including
  intentionally out-of-family inputs to verify honest stops.
- [ ] Audit trail: if regulatory, captures the workflow_trace
  per call.
- [ ] Calibration: if latency-sensitive, applies a calibration
  data file for your hardware.

That's the integration pattern. Most of it is one-time work
when you first wire the framework in. After that, the
framework calls themselves are just a few lines.

## What this chapter taught you

1. The framework lives in `core/`. Adapters sit upstream of
   it; handlers sit downstream.
2. Two integration patterns: **replacement** (swap out an
   existing component entirely) and **pre-flight** (run
   alongside, make the existing component faster).
3. Error handling at integration boundaries is mostly about
   catching honest stops and handling infeasibility cleanly.
4. Optional calibration gives you wall-clock cost models for
   latency-sensitive use cases.

The next chapter — Chapter 14 — covers the choice between the
framework and other tools (MIP, CP-SAT, Monte Carlo,
NetworkX) when you're staring at a fresh problem and trying
to pick the right one.
