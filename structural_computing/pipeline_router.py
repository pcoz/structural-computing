r"""Pipeline-router driver.

Routes a SEQUENCE of typed problems through the same router primitive that
hybrid-dispatcher/ uses for a single circuit. The driver `run_pipeline(stages)`
walks an iterable of `Stage`s once, calls each stage's router and runner, and
threads the output of one stage as the input to the next.

Generator-driven: the iterable of stages may itself be a generator, so a
1000-stage pipeline streams rather than materialising the whole sequence in
memory before the first stage runs.

Each Stage owns:
  * `data`        -- a typed sub-problem descriptor (a circuit, a constraint
                     set, a graph, an amplitude oracle, ...);
  * `route_fn(data, prev)`   -> Route   -- inspect the problem in context of
                                          the running pipeline and emit
                                          (member, cost, meters, tier);
  * `runner_fn(data, prev, route)` -> output -- run the chosen member and
                                                return whatever the next
                                                stage needs.

Per-stage `route_fn` is free to call `route_block` from hybrid_dispatcher (for
a circuit), `classify` + `route_constraint` (for a constraint set; Phase 1.2),
or anything else that returns a Route. The driver is agnostic to the per-stage
shapes -- they live in the worked examples.

This file is the v0.1 driver. Aggregated traces (Phase 1.4, trace.py) and
memoised replay (Phase 1.5, replay.py) plug in via the Trace and `cache`
parameters; the local Trace here is intentionally minimal and forward-
compatible with the richer trace.py extension.

Run:  python pipeline_router.py     # runs the built-in self_test().
"""
import dataclasses
import math
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional, Tuple


@dataclasses.dataclass
class Route:
    """The route_fn's answer: which member, expected cost, and the meters that
    justified the choice. `tier` is the constraint-hierarchy tier the classifier
    emitted, when applicable (None for non-constraint stages)."""
    member: str
    cost: float
    meters: Dict[str, Any] = dataclasses.field(default_factory=dict)
    tier: Optional[str] = None


@dataclasses.dataclass
class Stage:
    """A single typed sub-problem in the pipeline. `route_fn(data, prev)`
    returns a Route; `runner_fn(data, prev, route)` returns the output that is
    threaded as `prev` into the next stage."""
    name: str
    kind: str
    data: Any
    route_fn: Callable[[Any, Any], Route]
    runner_fn: Callable[[Any, Any, Route], Any]


@dataclasses.dataclass
class StageRecord:
    """One stage's entry in the trace."""
    name: str
    kind: str
    route: Route
    output_summary: Any = None


class Trace:
    """A minimal, forward-compatible trace: an ordered list of StageRecords and
    a handful of queries (member histogram, total cost, regime-change indices).
    Phase 1.4 (trace.py) will extend this with richer aggregation; everything
    here is a stable seam."""

    def __init__(self):
        self.records: List[StageRecord] = []

    def record(self, stage: Stage, route: Route, output_summary: Any = None) -> None:
        self.records.append(StageRecord(stage.name, stage.kind, route, output_summary))

    @property
    def stages(self) -> int:
        return len(self.records)

    def member_histogram(self) -> Dict[str, int]:
        """Member -> count of stages routed to it. Reveals the dominant
        routing regime across long pipelines."""
        out: Dict[str, int] = {}
        for r in self.records:
            out[r.route.member] = out.get(r.route.member, 0) + 1
        return out

    def tier_histogram(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for r in self.records:
            key = r.route.tier or "-"
            out[key] = out.get(key, 0) + 1
        return out

    def total_log_budget(self) -> float:
        """Sum of per-stage log2-costs. A budget-like complexity score (NOT
        the log of total operations -- summing log2(x) gives log2(prod x),
        not log2(sum x)). For the actual total-operations cost across a
        sequential pipeline use `total_ops_cost`."""
        return sum(r.route.cost for r in self.records)

    def total_ops_cost(self) -> float:
        """log2 of the SUM of per-stage operations (the meaningful "how many
        ops total" cost for a sequential pipeline). Returns +inf if any
        stage was advised (cost = +inf)."""
        if any(math.isinf(r.route.cost) for r in self.records):
            return math.inf
        if not self.records:
            return 0.0
        # log2(sum 2^c_i) computed in a numerically stable way.
        cs = [r.route.cost for r in self.records]
        cmax = max(cs)
        return cmax + math.log2(sum(2.0 ** (c - cmax) for c in cs))

    def regime_changes(self) -> List[int]:
        """Indices i where records[i].route.member differs from records[i-1].
        A long pipeline whose dominant member is constant has few entries; one
        whose member shifts (an adaptive-Hamiltonian-style schedule, an MCMC
        whose conditional flips between Pfaffian-tractable and dense) has many."""
        out: List[int] = []
        for i in range(1, len(self.records)):
            if self.records[i].route.member != self.records[i - 1].route.member:
                out.append(i)
        return out


def run_pipeline(stages: Iterable[Stage],
                 seed: Any = None,
                 trace: Optional[Trace] = None,
                 output_summary_fn: Optional[Callable[[Any], Any]] = None
                 ) -> Tuple[Any, Trace]:
    """Walk an iterable of Stages once, routing and running each in order.
    Threads the output of stage i as `prev` for stage i+1. Returns
    (final_output, trace).

    The trace can be inspected after the run for routing decisions, regime
    changes, member histogram, total cost.
    """
    if trace is None:
        trace = Trace()
    prev = seed
    final = seed
    for stage in stages:
        route = stage.route_fn(stage.data, prev)
        output = stage.runner_fn(stage.data, prev, route)
        summary = output_summary_fn(output) if output_summary_fn else None
        trace.record(stage, route, summary)
        prev = output
        final = output
    return final, trace


def run_pipeline_streaming(stages: Iterable[Stage],
                           seed: Any = None,
                           trace: Optional[Trace] = None,
                           output_summary_fn: Optional[Callable[[Any], Any]] = None
                           ) -> Iterator[Tuple[Stage, Route, Any]]:
    """Generator-driven variant: yields (stage, route, output) per completed
    stage. Lets a caller react after each step (the 1000-pass adaptive use
    case) and lets stage iterables themselves be generators (so the whole
    sequence is never materialised).

    The caller can stop iteration at any time; earlier stages are not re-run.
    """
    if trace is None:
        trace = Trace()
    prev = seed
    for stage in stages:
        route = stage.route_fn(stage.data, prev)
        output = stage.runner_fn(stage.data, prev, route)
        summary = output_summary_fn(output) if output_summary_fn else None
        trace.record(stage, route, summary)
        prev = output
        yield stage, route, output


# ---------------------------------------------------------------------------
# Self-test: a small explicit pipeline (3 stages) and a streaming 1000-stage
# verification that the generator-driven driver does not blow up at scale.
# ---------------------------------------------------------------------------

def _trivial_route(data, prev):
    return Route(member="arithmetic", cost=1.0, meters={"size": 1})


def _add_runner(data, prev, route):
    return (prev or 0) + data


def _mul_runner(data, prev, route):
    return (prev or 0) * data


def _sq_runner(data, prev, route):
    return (prev or 0) ** 2


def _build_three_stage():
    return [
        Stage("add", "arith", 1, _trivial_route, _add_runner),
        Stage("mul", "arith", 2, _trivial_route, _mul_runner),
        Stage("sq",  "arith", None, _trivial_route, _sq_runner),
    ]


def _three_stage_brute(start):
    """Brute-force reference for the three-stage pipeline above."""
    return ((start + 1) * 2) ** 2


def self_test():
    """Verify the driver on small explicit pipelines against a brute-force
    composition, and verify streaming at 1000 stages via a generator."""

    # 1) Eager driver on a three-stage pipeline, brute-force reference.
    for start in range(0, 10):
        stages = _build_three_stage()
        final, trace = run_pipeline(stages, seed=start)
        ref = _three_stage_brute(start)
        assert final == ref, f"three-stage mismatch at start={start}: {final} != {ref}"
        assert trace.stages == 3
    print("  [eager driver: 3-stage pipeline correct on starts 0..9]")

    # 2) Streaming yields the same cumulative outputs (4, 8, 64) at seed=3.
    stages = _build_three_stage()
    outputs = [output for _, _, output in run_pipeline_streaming(stages, seed=3)]
    assert outputs == [4, 8, 64], f"streaming output mismatch: {outputs}"
    print("  [streaming driver: per-stage outputs (4, 8, 64) match the eager run]")

    # 3) 1000-stage pipeline via a GENERATOR (never materialised as a list).
    #    The trace must still be complete and queryable after the streaming run.
    def stage_gen(n):
        for i in range(n):
            if i % 3 == 0:
                yield Stage(f"add_{i}", "add", 1, _trivial_route, _add_runner)
            else:
                yield Stage(f"mul_{i}", "mul", 2, _trivial_route, _mul_runner)

    trace = Trace()
    final = None
    for _, _, output in run_pipeline_streaming(stage_gen(1000), seed=0, trace=trace):
        final = output
    assert trace.stages == 1000, f"trace stages: {trace.stages}"
    hist = trace.member_histogram()
    assert hist == {"arithmetic": 1000}, hist
    # single member across the whole run -> no regime changes
    assert trace.regime_changes() == [], "spurious regime changes on constant member"
    print("  [streaming driver: 1000 stages via generator, trace complete, no spurious regime changes]")

    # 4a) Cost semantics. Two stages costing log2 = 3 each (so 8 + 8 = 16 ops).
    #     total_log_budget is 6.0 (sum of logs); total_ops_cost is 4.0 (log2(16)).
    def fixed_route(data, prev):
        return Route(member="m", cost=3.0)
    def identity_runner(data, prev, route):
        return prev
    pair = [Stage("a", "k", None, fixed_route, identity_runner),
            Stage("b", "k", None, fixed_route, identity_runner)]
    _, t = run_pipeline(pair, seed=0)
    assert abs(t.total_log_budget() - 6.0) < 1e-9, t.total_log_budget()
    assert abs(t.total_ops_cost() - 4.0) < 1e-9, t.total_ops_cost()
    print("  [Trace cost semantics: total_log_budget=6.0 sums logs; total_ops_cost=4.0 = log2(8+8)]")

    # 4b) A pipeline whose route MEMBER alternates -- regime_changes must catch it.
    def alternating_route(data, prev):
        return Route(member="free-fermion" if data % 2 == 0 else "stabilizer",
                     cost=1.0, tier=("T0" if data % 2 == 0 else "T2"))
    stages = [Stage(f"s_{i}", "alt", i, alternating_route, _add_runner) for i in range(10)]
    _, trace = run_pipeline(stages, seed=0)
    # i = 0,1,2,..,9 -> ff,st,ff,st,...  9 transitions
    assert trace.regime_changes() == list(range(1, 10)), \
        f"regime_changes: {trace.regime_changes()}"
    assert set(trace.tier_histogram()) == {"T0", "T2"}
    print("  [regime-change detection: 9/9 transitions caught on alternating member]")


if __name__ == "__main__":
    self_test()
