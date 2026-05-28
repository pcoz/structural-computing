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
from typing import Any, Dict

from .classify import Classification
from .pipeline_router import Route


# Established cost constants (mirror hybrid_dispatcher.py's conventions).
_GENUS_FACTOR = math.log2(4)                 # 4^g for genus-g cost growth


def _poly(n: int) -> float:
    """A 2 log2 n surrogate for "polynomial". Same convention as
    hybrid_dispatcher.route_block's `_poly` helper."""
    return 2.0 * math.log2(max(n, 2))


def route(classification: Classification) -> Route:
    """Map a `Classification` to a `Route`. Cost is reported in log2(ops)
    units (so a value of 8.6 means ~2^8.6 = ~388 operations). Advised tiers
    return cost = +inf with the reason in the meters."""
    tier = classification.tier
    m: Dict[str, Any] = dict(classification.meters)

    if tier == "T0":
        nv = int(m.get("n_variables", 1))
        return Route(
            member="ch-form",
            cost=_poly(nv + 1),
            meters={**m, "model": "affine-quadratic support directions"},
            tier=tier,
        )

    if tier == "T1":
        nl = int(m.get("n_linear", 0))
        nq = int(m.get("n_quadratic", 0))
        return Route(
            member="ch-form",
            cost=_poly(nl + nq + 1),
            meters={**m, "model": "affine-quadratic with post-selecting Z measurements"},
            tier=tier,
        )

    if tier == "T2":
        nv = int(m.get("n_vertices", m.get("arity", 2)))
        return Route(
            member="free-fermion",
            cost=_poly(2 * nv),
            meters={**m, "model": "FKT planar Pfaffian"},
            tier=tier,
        )

    if tier == "T3":
        ar = int(m.get("arity", 3))
        rank = int(m.get("basis_aware_rank", 2))
        if rank <= 2:
            return Route(
                member="free-fermion",
                cost=_poly(2 * ar),
                meters={**m, "model": f"FKT + basis-aware rank-{rank} parity-split decomposition"},
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
        return Route(
            member="free-fermion",
            cost=g * _GENUS_FACTOR + _poly(2 * nv),
            meters={**m, "model": f"genus-{g} Kasteleyn (Klein arc, 4^g scaling)"},
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
                cost=_poly(2 * nv),
                meters={**m, "model": "planar tropical Pfaffian"},
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
