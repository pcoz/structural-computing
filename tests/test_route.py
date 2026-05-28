"""Tests for the tier-to-member router (route_constraint -> Route)."""

import math
import pytest

from structural_computing import Classification, route


def _cls(tier, **meters):
    """Tiny constructor for canned Classifications."""
    in_family = tier in {"T0", "T1", "T2", "T3", "T4"}
    return Classification(tier=tier, meters=meters, in_family=in_family,
                          reasoning=f"canned {tier}")


# ---------------------------------------------------------------------------
# In-family tiers -> runnable members with finite cost
# ---------------------------------------------------------------------------

def test_t0_to_ch_form():
    r = route(_cls("T0", n_variables=8, n_constraints=4, modulus=2))
    assert r.member == "ch-form"
    assert r.tier == "T0"
    assert math.isfinite(r.cost)


def test_t1_to_ch_form():
    r = route(_cls("T1", n_linear=4, n_quadratic=2, modulus=2))
    assert r.member == "ch-form"
    assert r.tier == "T1"
    assert math.isfinite(r.cost)


def test_t2_to_free_fermion():
    r = route(_cls("T2", n_vertices=16, genus=0))
    assert r.member == "free-fermion"
    assert math.isfinite(r.cost)


def test_t3_to_free_fermion_rank_2():
    r = route(_cls("T3", arity=4, basis_aware_rank=2))
    assert r.member == "free-fermion"
    assert math.isfinite(r.cost)


def test_t4_to_free_fermion():
    r = route(_cls("T4", n_vertices=16, genus=1))
    assert r.member == "free-fermion"
    assert math.isfinite(r.cost)


# ---------------------------------------------------------------------------
# T4 4^g cost scaling: each unit of genus adds log2(4) = 2 to the cost
# ---------------------------------------------------------------------------

def test_t4_cost_growth_matches_4_to_the_g():
    g1 = route(_cls("T4", n_vertices=16, genus=1)).cost
    g2 = route(_cls("T4", n_vertices=16, genus=2)).cost
    g4 = route(_cls("T4", n_vertices=16, genus=4)).cost
    assert g1 < g2 < g4
    # Each +1 in genus -> +log2(4) = +2 in cost
    assert abs((g2 - g1) - math.log2(4)) < 1e-9
    assert abs((g4 - g2) - 2 * math.log2(4)) < 1e-9


# ---------------------------------------------------------------------------
# Advised tiers -> infinite cost with reason in meters
# ---------------------------------------------------------------------------

def test_t5_advised():
    r = route(_cls("T5"))
    assert r.member.startswith("advised:")
    assert math.isinf(r.cost)
    assert "reason" in r.meters


def test_t6_advised_when_non_planar():
    r = route(_cls("T6"))                       # in_family=False (T6 not in our in-family set)
    # The T6 path checks in_family + planar. The canned cls is not in_family,
    # so this hits the advised path.
    assert r.member.startswith("advised:")
    assert math.isinf(r.cost)


def test_t6_planar_in_family_runnable():
    """T6 planar in-family -> tropical-pfaffian (NOT advised)."""
    cls = Classification(tier="T6", meters={"n_vertices": 16, "planar": True},
                         in_family=True, reasoning="planar tropical")
    r = route(cls)
    assert r.member == "tropical-pfaffian"
    assert math.isfinite(r.cost)


def test_t7_advised():
    r = route(_cls("T7"))
    assert r.member.startswith("advised:")
    assert math.isinf(r.cost)
    assert "reason" in r.meters


def test_t3_high_rank_advised():
    """T3 with rank > 2 (hypothetical non-symmetric) routes to advised."""
    r = route(_cls("T3", arity=4, basis_aware_rank=3))
    assert r.member.startswith("advised:")
    assert math.isinf(r.cost)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_unknown_tier_falls_to_advised():
    """A tier not in {T0..T7} routes to advised."""
    r = route(_cls("T99"))
    assert r.member.startswith("advised:")
    assert math.isinf(r.cost)


def test_route_preserves_meters():
    """The original meters from the Classification carry into the Route."""
    cls = _cls("T0", n_variables=10, custom_field="hello")
    r = route(cls)
    assert "custom_field" in r.meters


# ---------------------------------------------------------------------------
# Calibration wiring (v0.3)
# ---------------------------------------------------------------------------

def test_route_without_question_marks_heuristic():
    """Calling route() with no question argument always tags the cost
    source as 'heuristic' and omits predicted_seconds."""
    from structural_computing import clear_calibration
    clear_calibration()
    r = route(_cls("T2", n_vertices=8))
    assert r.meters.get("cost_source") == "heuristic"
    assert "predicted_seconds" not in r.meters


def test_route_with_question_and_no_calibration_still_heuristic():
    """An empty calibration registry means even a supplied question
    returns heuristic-only meters."""
    from structural_computing import clear_calibration
    clear_calibration()
    r = route(_cls("T2", n_vertices=8), question="matching_count")
    assert r.meters.get("cost_source") == "heuristic"


def test_route_with_calibration_adds_predicted_seconds():
    """When calibration is loaded for (tier, question), route() surfaces
    predicted_seconds and tags cost_source='calibrated'."""
    from structural_computing import apply_calibration, clear_calibration
    clear_calibration()
    apply_calibration({
        ("T2", "matching_count"): {
            "model": "power_law", "params": (1e-7, 3.0), "rms": 0.05,
        },
    })
    try:
        r = route(_cls("T2", n_vertices=10), question="matching_count")
        assert r.meters["cost_source"] == "calibrated"
        # Power law: 1e-7 * 10^3 = 1e-4 seconds (problem size = 10 for T2)
        assert abs(r.meters["predicted_seconds"] - 1e-4) < 1e-9
        # Cost is now log2(predicted_seconds), not log2(ops).
        assert r.meters["cost_unit"] == "log2_seconds"
        assert abs(r.cost - math.log2(1e-4)) < 1e-9
    finally:
        clear_calibration()


def test_route_heuristic_cost_unit_is_log2_ops():
    """Without calibration, the cost field is the log2(ops) heuristic
    and cost_unit is tagged as 'log2_ops' so downstream consumers can
    tell the units."""
    from structural_computing import clear_calibration
    clear_calibration()
    r = route(_cls("T2", n_vertices=8))
    assert r.meters["cost_unit"] == "log2_ops"
    assert r.meters["cost_source"] == "heuristic"
    # Heuristic for T2 with n_vertices=8: 3*log2(16) + 1.5 = 13.5.
    assert abs(r.cost - (3 * math.log2(16) + 1.5)) < 1e-9


def test_route_calibrated_cost_is_log2_seconds_t4():
    """The same unit-switch happens for T4 (and all in-family tiers)."""
    from structural_computing import apply_calibration, clear_calibration
    clear_calibration()
    apply_calibration({
        ("T4", "matching_count"): {
            "model": "exponential", "params": (1e-6, math.log(2)), "rms": 0.1,
        },
    })
    try:
        r = route(_cls("T4", n_vertices=10, genus=1),
                   question="matching_count")
        # time = 1e-6 * 2^10 = 1.024e-3
        expected_seconds = 1e-6 * (2 ** 10)
        assert abs(r.meters["predicted_seconds"] - expected_seconds) < 1e-9
        assert r.meters["cost_unit"] == "log2_seconds"
        assert abs(r.cost - math.log2(expected_seconds)) < 1e-9
    finally:
        clear_calibration()
