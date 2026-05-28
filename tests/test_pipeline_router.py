"""Tests for the pipeline-router driver: Stage, Route, Trace, run_pipeline
and run_pipeline_streaming."""

import math
import pytest

from structural_computing import (
    Stage, Route, Trace, run_pipeline, run_pipeline_streaming,
)


# ---------------------------------------------------------------------------
# Stage / Route / Trace dataclasses
# ---------------------------------------------------------------------------

def test_route_construction():
    """Route has the expected fields and defaults."""
    r = Route(member="m", cost=1.0)
    assert r.member == "m"
    assert r.cost == 1.0
    assert r.meters == {}                         # default empty dict
    assert r.tier is None                          # default None


def test_route_with_meters_and_tier():
    r = Route(member="free-fermion", cost=8.0, meters={"genus": 0}, tier="T2")
    assert r.tier == "T2"
    assert r.meters["genus"] == 0


def test_stage_construction():
    def route_fn(data, prev): return Route(member="m", cost=1.0)
    def runner_fn(data, prev, route): return prev
    s = Stage("a", "k", 42, route_fn, runner_fn)
    assert s.name == "a"
    assert s.kind == "k"
    assert s.data == 42


# ---------------------------------------------------------------------------
# run_pipeline -- eager mode
# ---------------------------------------------------------------------------

def _trivial_route(data, prev):
    return Route(member="arithmetic", cost=1.0)


def test_run_pipeline_single_stage():
    """A 1-stage pipeline just runs the stage."""
    def runner(d, p, r): return d + 10
    stages = [Stage("only", "k", 5, _trivial_route, runner)]
    final, trace = run_pipeline(stages, seed=0)
    assert final == 15
    assert trace.stages == 1


def test_run_pipeline_threads_output():
    """Each stage's output threads into the next stage's prev arg."""
    def add(d, p, r): return (p or 0) + d
    def mul(d, p, r): return (p or 0) * d
    stages = [
        Stage("add", "k", 3, _trivial_route, add),
        Stage("mul", "k", 4, _trivial_route, mul),
    ]
    final, _ = run_pipeline(stages, seed=0)
    assert final == (0 + 3) * 4 == 12


def test_run_pipeline_empty():
    """An empty pipeline returns the seed."""
    final, trace = run_pipeline([], seed=42)
    assert final == 42
    assert trace.stages == 0


def test_run_pipeline_trace_recorded():
    """Every stage gets recorded in the trace."""
    def r(d, p, r): return d
    stages = [Stage(f"s{i}", "k", i, _trivial_route, r) for i in range(5)]
    _, trace = run_pipeline(stages, seed=0)
    assert trace.stages == 5
    names = [rec.name for rec in trace.records]
    assert names == ["s0", "s1", "s2", "s3", "s4"]


# ---------------------------------------------------------------------------
# run_pipeline_streaming -- generator mode
# ---------------------------------------------------------------------------

def test_streaming_yields_each_stage():
    """Streaming yields (stage, route, output) per completed stage."""
    def r(d, p, r): return d
    stages = [Stage(f"s{i}", "k", i, _trivial_route, r) for i in range(3)]
    outs = list(run_pipeline_streaming(stages, seed=0))
    assert len(outs) == 3
    for k, (stage, route, output) in enumerate(outs):
        assert stage.name == f"s{k}"
        assert output == k


def test_streaming_with_generator_input():
    """Stages can be a generator -- never materialised as a list."""
    def stage_gen(n):
        def r(d, p, r): return (p or 0) + 1
        for i in range(n):
            yield Stage(f"s{i}", "k", None, _trivial_route, r)

    final = None
    n = 100
    for _, _, output in run_pipeline_streaming(stage_gen(n), seed=0):
        final = output
    assert final == n


# ---------------------------------------------------------------------------
# Trace queries
# ---------------------------------------------------------------------------

def test_trace_member_histogram():
    """member_histogram counts stages per member."""
    def route_a(d, p): return Route(member="A", cost=1.0)
    def route_b(d, p): return Route(member="B", cost=1.0)
    def r(d, p, r): return d

    stages = ([Stage(f"a{i}", "k", i, route_a, r) for i in range(3)] +
              [Stage(f"b{i}", "k", i, route_b, r) for i in range(2)])
    _, trace = run_pipeline(stages, seed=0)
    assert trace.member_histogram() == {"A": 3, "B": 2}


def test_trace_tier_histogram():
    """tier_histogram counts stages per tier; None -> '-'."""
    def route_t0(d, p): return Route(member="m", cost=1.0, tier="T0")
    def route_t2(d, p): return Route(member="m", cost=1.0, tier="T2")
    def route_none(d, p): return Route(member="m", cost=1.0)            # no tier
    def r(d, p, r): return d

    stages = [
        Stage("a", "k", None, route_t0, r),
        Stage("b", "k", None, route_t2, r),
        Stage("c", "k", None, route_t2, r),
        Stage("d", "k", None, route_none, r),
    ]
    _, trace = run_pipeline(stages, seed=0)
    assert trace.tier_histogram() == {"T0": 1, "T2": 2, "-": 1}


def test_trace_regime_changes():
    """regime_changes() returns indices where the member flipped."""
    members = ["A", "A", "B", "B", "A"]
    def make_route(mem):
        def route(d, p): return Route(member=mem, cost=1.0)
        return route
    def r(d, p, r): return d
    stages = [Stage(f"s{i}", "k", None, make_route(m), r) for i, m in enumerate(members)]
    _, trace = run_pipeline(stages, seed=0)
    # transitions: index 2 (A->B), index 4 (B->A)
    assert trace.regime_changes() == [2, 4]


def test_trace_total_log_budget_and_ops_cost():
    """total_log_budget = sum of per-stage log2-costs; total_ops_cost =
    log2(sum 2^cost) numerically stable."""
    def route_cost_3(d, p): return Route(member="m", cost=3.0)
    def r(d, p, r): return d
    stages = [Stage(f"s{i}", "k", None, route_cost_3, r) for i in range(2)]
    _, trace = run_pipeline(stages, seed=0)
    # Two stages at cost 3 each
    assert abs(trace.total_log_budget() - 6.0) < 1e-9       # 3 + 3
    assert abs(trace.total_ops_cost() - 4.0) < 1e-9          # log2(2^3 + 2^3) = log2(16)


def test_trace_total_ops_cost_with_inf():
    """If any stage has +inf cost, total_ops_cost is +inf."""
    def route_finite(d, p): return Route(member="m", cost=1.0)
    def route_inf(d, p): return Route(member="m", cost=math.inf)
    def r(d, p, r): return d
    stages = [
        Stage("a", "k", None, route_finite, r),
        Stage("b", "k", None, route_inf, r),
    ]
    _, trace = run_pipeline(stages, seed=0)
    assert math.isinf(trace.total_ops_cost())


def test_trace_empty():
    """An empty trace has zero stages, zero cost."""
    t = Trace()
    assert t.stages == 0
    assert t.member_histogram() == {}
    assert t.regime_changes() == []
    assert t.total_log_budget() == 0.0
