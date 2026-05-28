r"""Tier -> member + cost map for the pipeline-router.

Given a `Classification` from `classify.py`, emit a `pipeline_router.Route`
(member, cost, meters, tier). The cost models mirror the constants used in
`hybrid_dispatcher.py` where applicable (FKT poly for planar Pfaffian, 4^g
scaling for bounded-genus Galluccio-Loebl). For advised tiers (T5+), the cost
is reported as +infinity -- the runner is expected to fall back to an
external solver named in the meters.

The map at a glance:

    Tier   Member                            Notes
    ----   ------------------------------    ----------------------------------
    T0     ch-form                           support directions of G are the
                                             affine variety of solutions
    T1     ch-form + post-selecting Z        quadratic-phase + measurement
    T2     free-fermion (planar Pfaffian)    holant-tools FKT
    T3     free-fermion + basis-aware rank   exact when rank in {0, 1, 2}
           (rank-2 parity-split)             (true for every symmetric sig)
    T4     free-fermion (genus-g Kasteleyn)  Klein arc; 4^g scaling
    T5     ADVISED                           Stembridge degree-3+ (pending)
    T6     ADVISED  /  tropical-pfaffian     tropical Klein (pending)
    T7     ADVISED                           out of family, external solver
"""
import math
from typing import Any, Dict, Optional

from .calibration import has_calibration_for, predict_seconds
from .classify import Classification
from .pipeline_router import Route


# ---------------------------------------------------------------------------
# Cost model -- per-tier asymptotic complexity, in log2(ops) units
# ---------------------------------------------------------------------------
#
# Each tier's runtime is dominated by a specific algorithmic operation:
#
#   T0 / T1   Gaussian elimination on the affine variety: O(n^3) in the
#             number of variables n. The CH-form data carries O(n*k) where
#             k <= n is the support dimension; per-amplitude readout is one
#             GF(2) solve which is O(n^2).
#   T2        FKT planar Pfaffian: O(n^3) in the number of vertices n.
#             Constant overhead for Kasteleyn orientation construction.
#   T3        Basis-aware rank-2 decomposition: O(n^3) per parity branch;
#             at most 2 branches for symmetric signatures. So O(2 * n^3),
#             which in log2-space is T2_cost + log2(rank).
#   T4        Galluccio-Loebl genus-g Kasteleyn: O(4^g * n^3). In log2,
#             that's T2_cost + g * log2(4) = T2_cost + 2g.
#   T5 / T6   advised tiers (pending native implementation); cost +inf.
#   T7        out-of-family advised; cost +inf.
#
# The constants below capture these complexities at the log2-of-ops level
# of granularity. They are NOT benchmark-calibrated -- they are
# asymptotic-complexity estimates. Benchmark-driven calibration (with
# measured constants per tier per platform) is a v0.2 deliverable; until
# then this model gives reasonable RELATIVE cost ordering between tiers,
# which is what the router needs for member selection.

_GENUS_FACTOR = math.log2(4)              # log2(4^g) per unit of genus

# Per-tier polynomial degree (the exponent in n^d).
_POLY_DEGREE_T0_T1 = 3.0                  # GF(2) Gaussian elimination
_POLY_DEGREE_T2_T3_T4 = 3.0               # Pfaffian / Kasteleyn

# Per-tier constant overhead (log2 of the multiplicative constant).
# These approximate the relative cost of setup work between tiers; tuned
# to the level "T2 should look a bit more expensive than T0 for a given n
# because the Pfaffian setup is more involved than the affine-variety
# read-off."
_OVERHEAD_T0 = 0.5
_OVERHEAD_T1 = 1.0
_OVERHEAD_T2 = 1.5
_OVERHEAD_T3 = 1.5
_OVERHEAD_T4 = 1.5


def _poly_cost(n: int, degree: float = 3.0, overhead: float = 0.0) -> float:
    """Asymptotic cost in log2(ops): `degree * log2(n) + overhead`.

    `degree` is the polynomial degree (3 for cubic algorithms like Pfaffian
    or Gaussian elimination; 2 for quadratic; etc.). `overhead` is a
    constant added in log2-space to capture per-tier setup work.

    Returns log2(2) = 1.0 as a floor for n < 2 to avoid log2(0) = -inf
    swallowing legitimately-small problems.
    """
    return degree * math.log2(max(n, 2)) + overhead


def _poly(n: int) -> float:
    """Backward-compatible alias for the legacy `2 log2 n` surrogate.
    Kept for callers that depend on the old shape; new code should call
    `_poly_cost` with explicit degree and overhead."""
    return 2.0 * math.log2(max(n, 2))


def _size_hint_for(tier: str, m: Dict[str, Any]) -> int:
    """Pick the natural "problem size" for this tier from the meters --
    used to query the calibration's predict_seconds(). The choices
    match the per-tier dispatch logic below: T0/T1 use n_variables,
    T2/T4 use n_vertices, T3 uses arity."""
    if tier in ("T0", "T1"):
        nl = int(m.get("n_linear", m.get("n_variables", 1)))
        nq = int(m.get("n_quadratic", 0))
        return max(nl + nq, 1)
    if tier in ("T2", "T4", "T6"):
        return int(m.get("n_vertices", m.get("arity", 2)))
    if tier == "T3":
        return int(m.get("arity", 3))
    return int(m.get("n_vertices", 1))


def _maybe_calibrated(tier: str, question: Optional[str],
                       m: Dict[str, Any]) -> Optional[float]:
    """If a calibration entry exists for ``(tier, question)``, return the
    predicted seconds for a problem of the natural size. Else return
    None. The ``question`` argument is what makes calibration lookup
    possible; without it we don't know which leaf evaluator will run."""
    if question is None or not has_calibration_for(tier, question):
        return None
    n = _size_hint_for(tier, m)
    return predict_seconds(tier, question, n=n)


def route(classification: Classification,
           question: Optional[str] = None) -> Route:
    """Map a `Classification` to a `Route`. Cost is reported in log2(ops)
    units (so a value of 8.6 means ~2^8.6 = ~388 operations). Advised tiers
    return cost = +inf with the reason in the meters.

    Optional ``question`` argument: when supplied AND a calibration
    entry has been loaded (via
    :func:`structural_computing.apply_calibration`) for the
    ``(tier, question)`` pair, the returned Route's meters also carry
    ``predicted_seconds`` (a wall-clock estimate on the calibrated
    machine) plus ``cost_source = "calibrated"``. The ``cost`` field
    itself stays in log2(ops) for backward-compatibility; the
    calibrated number is informational, surfaced in workflow traces
    and available to callers via ``route.meters["predicted_seconds"]``.

    When ``question`` is omitted OR no calibration is loaded, the
    meters carry ``cost_source = "heuristic"`` and ``predicted_seconds``
    is absent.
    """
    tier = classification.tier
    m: Dict[str, Any] = dict(classification.meters)
    cal_seconds = _maybe_calibrated(tier, question, m)
    cost_meta = (
        {"cost_source": "calibrated", "predicted_seconds": cal_seconds,
         "calibration_question": question}
        if cal_seconds is not None
        else {"cost_source": "heuristic"}
    )

    if tier == "T0":
        nv = int(m.get("n_variables", 1))
        # GF(2) Gaussian elimination is O(n^3) on n variables; in log2 ops:
        # 3 * log2(n) + small overhead. The +1 in nv+1 avoids log2(0) for
        # zero-variable degenerate cases.
        return Route(
            member="ch-form",
            cost=_poly_cost(nv + 1, degree=_POLY_DEGREE_T0_T1, overhead=_OVERHEAD_T0),
            meters={**m, "model": "affine-quadratic support directions",
                    "cost_model": "3*log2(n) + 0.5 (CH-form, Gauss-elim)",
                    **cost_meta},
            tier=tier,
        )

    if tier == "T1":
        nl = int(m.get("n_linear", 0))
        nq = int(m.get("n_quadratic", 0))
        # T1 = T0 + post-selecting Z measurements; same asymptotic but
        # slightly higher constant overhead.
        return Route(
            member="ch-form",
            cost=_poly_cost(nl + nq + 1, degree=_POLY_DEGREE_T0_T1, overhead=_OVERHEAD_T1),
            meters={**m, "model": "affine-quadratic with post-selecting Z measurements",
                    "cost_model": "3*log2(n) + 1.0 (CH-form + post-selection)",
                    **cost_meta},
            tier=tier,
        )

    if tier == "T2":
        nv = int(m.get("n_vertices", m.get("arity", 2)))
        # FKT planar Pfaffian is O(n^3) in the number of vertices. We pass
        # `2 * nv` to capture the matrix-size factor that the Kasteleyn
        # orientation introduces (the antisymmetric matrix has 2*|V| rows
        # after the orientation step).
        return Route(
            member="free-fermion",
            cost=_poly_cost(2 * nv, degree=_POLY_DEGREE_T2_T3_T4, overhead=_OVERHEAD_T2),
            meters={**m, "model": "FKT planar Pfaffian",
                    "cost_model": "3*log2(2|V|) + 1.5 (Pfaffian)",
                    **cost_meta},
            tier=tier,
        )

    if tier == "T3":
        ar = int(m.get("arity", 3))
        rank = int(m.get("basis_aware_rank", 2))
        if rank <= 2:
            # Basis-aware rank-2 decomposition runs the Pfaffian once per
            # parity branch (up to 2 branches), so cost adds log2(max(1, rank)).
            return Route(
                member="free-fermion",
                cost=(_poly_cost(2 * ar, degree=_POLY_DEGREE_T2_T3_T4, overhead=_OVERHEAD_T3)
                       + math.log2(max(1, rank))),
                meters={**m, "model": f"FKT + basis-aware rank-{rank} parity-split decomposition",
                        "cost_model": f"3*log2(2*arity) + 1.5 + log2({rank}) (parity-split)",
                        **cost_meta},
                tier=tier,
            )
        return Route(
            member="advised:nonsymmetric-matchgate-rank",
            cost=float("inf"),
            meters={**m, "reason": "rank > 2 (non-symmetric path); advise nonsymmetric_matchgate_rank"},
            tier=tier,
        )

    if tier == "T4":
        nv = int(m.get("n_vertices", 4))
        g = int(m.get("genus", 1))
        # Galluccio-Loebl genus-g formula: O(4^g * Pfaffian) per spin
        # structure. In log2 that's g * log2(4) added to the planar
        # Pfaffian cost.
        return Route(
            member="free-fermion",
            cost=(g * _GENUS_FACTOR
                   + _poly_cost(2 * nv, degree=_POLY_DEGREE_T2_T3_T4, overhead=_OVERHEAD_T4)),
            meters={**m, "model": f"genus-{g} Kasteleyn (Klein arc, 4^g scaling)",
                    "cost_model": f"{g}*log2(4) + 3*log2(2|V|) + 1.5 (genus-{g} Kasteleyn)",
                    **cost_meta},
            tier=tier,
        )

    if tier == "T5":
        return Route(
            member="advised:stembridge-degree3-plus",
            cost=float("inf"),
            meters={**m, "reason": "cardinality / threshold / modular-counting not yet runnable in family (Stembridge degree-3+ Plucker pending in holant-tools)"},
            tier=tier,
        )

    if tier == "T6":
        nv = int(m.get("n_vertices", 4))
        if classification.in_family and m.get("planar", False):
            return Route(
                member="tropical-pfaffian",
                cost=_poly_cost(2 * nv, degree=_POLY_DEGREE_T2_T3_T4, overhead=_OVERHEAD_T2),
                meters={**m, "model": "planar tropical Pfaffian",
                        "cost_model": "3*log2(2|V|) + 1.5 (tropical Pfaffian)"},
                tier=tier,
            )
        return Route(
            member="advised:tropical-klein",
            cost=float("inf"),
            meters={**m, "reason": "weighted optimisation outside planar tropical regime; native tropical Klein pending in holant-tools"},
            tier=tier,
        )

    # T7 and anything unrecognised.
    return Route(
        member="advised:external-solver",
        cost=float("inf"),
        meters={**m, "reason": classification.reasoning},
        tier=tier,
    )


# ---------------------------------------------------------------------------
# Self-test: feed canned Classifications and verify Route shape and cost
# ordering. (The classifier itself is exercised by classify.self_test.)
# ---------------------------------------------------------------------------

def _C(tier, **meters):
    """Tiny constructor for canned Classifications in the self-test."""
    return Classification(tier=tier, meters=meters, in_family=(tier in {"T0","T1","T2","T3","T4"}), reasoning=f"canned {tier}")


def self_test():
    # In-family tiers all yield a runnable member with finite cost.
    r_t0 = route(_C("T0", n_variables=8, n_constraints=4, modulus=2))
    assert r_t0.member == "ch-form" and math.isfinite(r_t0.cost), r_t0
    r_t1 = route(_C("T1", n_linear=4, n_quadratic=2, modulus=2))
    assert r_t1.member == "ch-form" and math.isfinite(r_t1.cost), r_t1
    r_t2 = route(_C("T2", n_vertices=16, genus=0))
    assert r_t2.member == "free-fermion" and math.isfinite(r_t2.cost), r_t2
    r_t3 = route(_C("T3", arity=4, basis_aware_rank=2))
    assert r_t3.member == "free-fermion" and math.isfinite(r_t3.cost), r_t3
    r_t4 = route(_C("T4", n_vertices=16, genus=1))
    assert r_t4.member == "free-fermion" and math.isfinite(r_t4.cost), r_t4
    print("  [tiers T0..T4 -> in-family members with finite cost]")

    # Genus growth: T4 cost strictly increases with g (4^g scaling shows up).
    g1 = route(_C("T4", n_vertices=16, genus=1)).cost
    g2 = route(_C("T4", n_vertices=16, genus=2)).cost
    g4 = route(_C("T4", n_vertices=16, genus=4)).cost
    assert g1 < g2 < g4, (g1, g2, g4)
    # Each genus step adds exactly log2(4) = 2 to the cost.
    assert abs((g2 - g1) - _GENUS_FACTOR) < 1e-9
    assert abs((g4 - g2) - 2 * _GENUS_FACTOR) < 1e-9
    print(f"  [T4 cost growth matches the 4^g scaling: g=1 {g1:.2f}, g=2 {g2:.2f}, g=4 {g4:.2f}]")

    # T3 with hypothetical rank > 2 (non-symmetric path) -> advised, cost = +inf.
    r_t3_high = route(_C("T3", arity=4, basis_aware_rank=3))
    assert r_t3_high.member.startswith("advised:") and math.isinf(r_t3_high.cost)
    print("  [T3 rank>2 -> advised:nonsymmetric-matchgate-rank, cost = +inf]")

    # Advised tiers all return +inf cost with a reason.
    for tier in ("T5", "T6", "T7"):
        r = route(_C(tier))
        assert r.member.startswith("advised:") and math.isinf(r.cost), (tier, r)
        assert "reason" in r.meters
    print("  [tiers T5/T6/T7 -> advised:* with +inf cost and a reason]")

    # T6 planar special-case: in-family planar tropical -> runs.
    r_t6_planar = route(_C("T6", n_vertices=16, planar=True))
    # in_family is False for T6 by default in our test helper, so this hits advised.
    # Re-check with an explicitly in-family canned instance:
    cls = Classification(tier="T6", meters={"n_vertices": 16, "planar": True},
                          in_family=True, reasoning="planar tropical")
    r_t6_runnable = route(cls)
    assert r_t6_runnable.member == "tropical-pfaffian" and math.isfinite(r_t6_runnable.cost)
    print("  [T6 planar + in-family -> tropical-pfaffian, finite cost]")


if __name__ == "__main__":
    self_test()
