"""Tests for RichTrace and its aggregation queries."""

import math
import pytest

from structural_computing import (
    Stage, Route, RichTrace, RegimeChange, run_pipeline,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _route(member, cost, tier=None):
    def route_fn(data, prev):
        return Route(member=member, cost=cost, tier=tier)
    return route_fn


def _identity(data, prev, route):
    return prev


# ---------------------------------------------------------------------------
# Basic RichTrace mechanics
# ---------------------------------------------------------------------------

def test_richtrace_inherits_from_trace():
    """RichTrace is a Trace -- all the minimal-trace queries work."""
    rt = RichTrace()
    assert rt.stages == 0
    assert rt.member_histogram() == {}
    assert rt.regime_changes() == []


def test_richtrace_used_by_run_pipeline():
    """run_pipeline accepts a RichTrace via its trace= argument."""
    stages = [Stage(f"s{i}", "k", None,
                     _route(f"m{i % 2}", 1.0, f"T{i % 2}"),
                     _identity) for i in range(4)]
    rt = RichTrace()
    run_pipeline(stages, trace=rt)
    assert rt.stages == 4


# ---------------------------------------------------------------------------
# Cost / ops by member and by tier
# ---------------------------------------------------------------------------

def test_cost_by_member():
    """Per-member log-budget breakdown."""
    stages = [
        Stage("a", "k", None, _route("X", 2.0), _identity),
        Stage("b", "k", None, _route("X", 3.0), _identity),
        Stage("c", "k", None, _route("Y", 4.0), _identity),
    ]
    rt = RichTrace()
    run_pipeline(stages, trace=rt)
    cbm = rt.cost_by_member()
    assert cbm == {"X": 5.0, "Y": 4.0}             # 2+3 and 4


def test_ops_by_member_numerically_stable():
    """ops_by_member returns log2(sum 2^cost) per bucket."""
    stages = [
        Stage("a", "k", None, _route("X", 3.0), _identity),
        Stage("b", "k", None, _route("X", 3.0), _identity),       # 2^3 + 2^3 = 16; log2 = 4
        Stage("c", "k", None, _route("Y", 5.0), _identity),       # log2(2^5) = 5
    ]
    rt = RichTrace()
    run_pipeline(stages, trace=rt)
    obm = rt.ops_by_member()
    assert abs(obm["X"] - 4.0) < 1e-9
    assert abs(obm["Y"] - 5.0) < 1e-9


def test_cost_by_tier():
    """Per-tier log-budget breakdown."""
    stages = [
        Stage("a", "k", None, _route("m", 2.0, tier="T0"), _identity),
        Stage("b", "k", None, _route("m", 3.0, tier="T2"), _identity),
        Stage("c", "k", None, _route("m", 4.0, tier="T2"), _identity),
    ]
    rt = RichTrace()
    run_pipeline(stages, trace=rt)
    cbt = rt.cost_by_tier()
    assert cbt == {"T0": 2.0, "T2": 7.0}


def test_inf_costs_propagate_correctly():
    """ops_by_member of a member with any +inf cost is +inf."""
    stages = [
        Stage("a", "k", None, _route("X", 2.0), _identity),
        Stage("b", "k", None, _route("X", math.inf), _identity),
    ]
    rt = RichTrace()
    run_pipeline(stages, trace=rt)
    assert math.isinf(rt.ops_by_member()["X"])


# ---------------------------------------------------------------------------
# Detailed regime changes
# ---------------------------------------------------------------------------

def test_regime_changes_detailed_records_prev_new():
    """regime_changes_detailed returns RegimeChange records with prev/new member."""
    stages = [
        Stage("a", "k", None, _route("A", 1.0), _identity),
        Stage("b", "k", None, _route("A", 1.0), _identity),
        Stage("c", "k", None, _route("B", 3.0), _identity),
        Stage("d", "k", None, _route("A", 1.0), _identity),
    ]
    rt = RichTrace()
    run_pipeline(stages, trace=rt)
    rcs = rt.regime_changes_detailed()
    assert len(rcs) == 2                          # transitions at index 2 and 3
    assert isinstance(rcs[0], RegimeChange)
    assert rcs[0].prev_member == "A" and rcs[0].new_member == "B"
    # Cost delta: stage 2 (B, cost 3) - stage 1 (A, cost 1) = +2
    assert abs(rcs[0].delta_cost - 2.0) < 1e-9
    assert rcs[1].prev_member == "B" and rcs[1].new_member == "A"


def test_regime_changes_detailed_with_inf():
    """delta_cost is NaN when either endpoint is +inf."""
    stages = [
        Stage("a", "k", None, _route("A", 1.0), _identity),
        Stage("b", "k", None, _route("B", math.inf), _identity),
    ]
    rt = RichTrace()
    run_pipeline(stages, trace=rt)
    rcs = rt.regime_changes_detailed()
    assert len(rcs) == 1
    assert math.isnan(rcs[0].delta_cost)


# ---------------------------------------------------------------------------
# Windowing
# ---------------------------------------------------------------------------

def test_window_returns_sub_trace():
    """window(start, end) returns a RichTrace with only records[start:end]."""
    stages = [Stage(f"s{i}", "k", None,
                     _route(f"m{i % 2}", 1.0), _identity) for i in range(10)]
    rt = RichTrace()
    run_pipeline(stages, trace=rt)
    win = rt.window(2, 7)
    assert win.stages == 5
    assert isinstance(win, RichTrace)


def test_window_preserves_aggregation():
    """window().cost_by_member etc work correctly on the sub-trace."""
    stages = [Stage(f"s{i}", "k", None,
                     _route("X", float(i + 1)), _identity) for i in range(5)]
    rt = RichTrace()
    run_pipeline(stages, trace=rt)
    win = rt.window(2, 4)                          # records 2 and 3 -> costs 3.0, 4.0
    assert win.cost_by_member() == {"X": 7.0}


# ---------------------------------------------------------------------------
# summary() text
# ---------------------------------------------------------------------------

def test_summary_returns_string_with_key_sections():
    """summary() emits a structured report with the expected section labels."""
    stages = [Stage(f"s{i}", "k", None,
                     _route("X", 1.0, tier="T0"), _identity) for i in range(3)]
    rt = RichTrace()
    run_pipeline(stages, trace=rt)
    text = rt.summary()
    assert "Pipeline trace" in text
    assert "by member" in text
    assert "by tier" in text
    assert "X" in text
    assert "T0" in text
