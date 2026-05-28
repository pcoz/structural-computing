r"""Small-n brute-force verifier for pipeline-router pipelines.

Verifies that a routed pipeline produces the same per-stage outputs as a
brute-force reference -- the foundation of every worked example's
self_test. The verifier itself owns the three brute-force primitives needed
across the examples:

  * `brute_force_count_matchings` -- perfect-matching count on a small graph,
    via holant-tools' own exhaustive enumerator (the reference Stages 2 and 4
    check themselves against in the flagship example).
  * `enumerate_satisfying_assignments` / `satisfies_gf2_affine` -- exhaustive
    GF(2)-affine constraint enumeration; the reference Stage 3 (WITNESS) is
    verified against.
  * `gibbs_expectation_brute` -- exact expectation over an enumerated state
    space (Stage 4 STRESS) reference.

Plus the comparison utility `verify_pipeline(stages, reference_outputs)`,
which runs the routed pipeline once and asserts each stage's output matches.

These are intentionally O(2^n) and thus n-bounded; the verifier is a
small-instance correctness check, not a production tool. Real pipelines
verify at small n once and then run at large n in faith of the verified
construction.
"""
import math
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

import holant_tools

from .pipeline_router import Stage, run_pipeline_streaming


# ---------------------------------------------------------------------------
# Brute-force primitives
# ---------------------------------------------------------------------------

def brute_force_count_matchings(vertices: Iterable, edges: Iterable) -> int:
    """Exact count of perfect matchings. Delegates to holant-tools' own
    brute-force enumerator (used in its tests, so we share a reference)."""
    return holant_tools.perfect_matching_count_brute_force(list(vertices), list(edges))


def brute_force_weighted_matching_sum(vertices: Iterable,
                                       edges: Iterable,
                                       weights: Dict[Tuple[Any, Any], float]) -> float:
    """Exact weighted perfect-matching sum:
    sum over perfect matchings M of (product of weights of edges in M).

    Both endpoint orderings are checked when looking up an edge's weight,
    so (u, v) and (v, u) are treated as the same edge. Missing edges
    default to weight 1.0 (so the function reduces to a plain matching
    count when all weights are 1).

    O(|V|!! * |E|) brute force -- small n only. The honest companion
    to the exact-but-large matchgate-Pfaffian computation.

    Args:
      vertices: iterable of vertex labels.
      edges: iterable of (u, v) edge tuples.
      weights: dict mapping edge (u, v) -> real or integer weight.

    Returns:
      The weighted matching sum. Returns 0 if |V| is odd.
    """
    vertices = list(vertices)
    edges = list(edges)
    n = len(vertices)
    if n % 2 != 0:
        return 0
    # Build an undirected weight lookup.
    w_lookup: Dict[Tuple[Any, Any], float] = {}
    for (u, v), w in weights.items():
        w_lookup[(u, v)] = w
        w_lookup[(v, u)] = w
    # Adjacency: for each vertex, list of neighbours via known edges.
    adj: Dict[Any, List[Any]] = {v: [] for v in vertices}
    for (u, v) in edges:
        if v not in adj[u]:
            adj[u].append(v)
        if u not in adj[v]:
            adj[v].append(u)
    # Enumerate matchings recursively, accumulating weight products.
    total = 0.0
    vertex_set = list(vertices)

    def recurse(unmatched: List[Any], partial_weight: float) -> None:
        nonlocal total
        if not unmatched:
            total += partial_weight
            return
        v = unmatched[0]
        rest = unmatched[1:]
        for u in adj[v]:
            if u in rest:
                w = w_lookup.get((v, u), 1.0)
                recurse([x for x in rest if x != u], partial_weight * w)

    recurse(vertex_set, 1.0)
    return total


def satisfies_gf2_affine(x: int, A: np.ndarray, b: np.ndarray) -> bool:
    """Does integer `x` (interpreted as an n-bit bitstring with bit 0 = MSB)
    satisfy A x = b (mod 2)?"""
    n = int(A.shape[1])
    bits = np.array([(x >> (n - 1 - i)) & 1 for i in range(n)], dtype=int)
    return bool(np.array_equal((A @ bits) % 2, b % 2))


def enumerate_satisfying_assignments(A: np.ndarray, b: np.ndarray) -> List[int]:
    """All n-bit integers x with A x = b (mod 2). 2^n enumeration -- small n only."""
    n = int(A.shape[1])
    return [x for x in range(2 ** n) if satisfies_gf2_affine(x, A, b)]


def gibbs_expectation_brute(states: Sequence[int],
                            weight_fn: Callable[[int], float],
                            observable_fn: Callable[[int], float]) -> float:
    """Exact <observable> = sum_x weight(x) * observable(x) / sum_x weight(x)
    over the enumerated `states`. Useful for checking small-n Stress
    expectations against brute force."""
    if not states:
        return 0.0
    Z = 0.0
    num = 0.0
    for x in states:
        w = weight_fn(x)
        Z += w
        num += w * observable_fn(x)
    return num / Z if Z > 0 else 0.0


# ---------------------------------------------------------------------------
# Pipeline-level verification
# ---------------------------------------------------------------------------

def _close(actual: Any, expected: Any, atol: float) -> Tuple[bool, str]:
    """Compare two values: numerical (with atol), arrays (allclose), else =="""
    if actual is None and expected is None:
        return True, "both None"
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        if math.isnan(actual) and math.isnan(expected):
            return True, "both NaN"
        if abs(float(actual) - float(expected)) > atol:
            return False, f"actual {actual} != expected {expected} (atol {atol})"
        return True, f"actual {actual} matches expected {expected}"
    if isinstance(actual, np.ndarray) or isinstance(expected, np.ndarray):
        a = np.asarray(actual); e = np.asarray(expected)
        if a.shape != e.shape:
            return False, f"shape mismatch {a.shape} vs {e.shape}"
        if not np.allclose(a, e, atol=atol):
            return False, "arrays differ beyond atol"
        return True, "arrays match"
    return (actual == expected), f"{'ok' if actual == expected else 'mismatch'}: {actual!r} vs {expected!r}"


def verify_pipeline(stages: List[Stage],
                    reference_outputs: List[Any],
                    seed: Any = None,
                    *, atol: float = 1e-10) -> Tuple[bool, str]:
    """Run the pipeline once and compare each stage's output to
    `reference_outputs[i]`. Returns (all_ok, multiline_report).

    `reference_outputs` should be precomputed by a brute-force / textbook
    reference -- the verifier's job is to confirm the routed run reproduces
    those numbers exactly (within `atol` for floats)."""
    lines: List[str] = []
    all_ok = True
    streamed = list(run_pipeline_streaming(stages, seed=seed))
    if len(streamed) != len(reference_outputs):
        return False, (f"stage count mismatch: pipeline emitted {len(streamed)}, "
                       f"reference has {len(reference_outputs)}")
    for i, (stage, _route, actual) in enumerate(streamed):
        ok, msg = _close(actual, reference_outputs[i], atol=atol)
        marker = "ok " if ok else "FAIL"
        lines.append(f"  [{marker}] stage {i} ({stage.name}): {msg}")
        all_ok = all_ok and ok
    return all_ok, "\n".join(lines)


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def self_test():
    from .pipeline_router import Route

    # 1. Brute-force matching count on a few known small graphs.
    # K_4 -> 3 perfect matchings
    assert brute_force_count_matchings([0, 1, 2, 3],
                                        [(0,1),(0,2),(0,3),(1,2),(1,3),(2,3)]) == 3
    # C_4 (4-cycle) -> 2 perfect matchings
    assert brute_force_count_matchings([0, 1, 2, 3],
                                        [(0,1),(1,2),(2,3),(3,0)]) == 2
    # Triangle (odd order) -> 0
    assert brute_force_count_matchings([0, 1, 2], [(0,1),(1,2),(2,0)]) == 0
    print("  [brute-force matching count: K_4 -> 3, C_4 -> 2, K_3 -> 0]")

    # 2. GF(2)-affine satisfaction enumeration.
    A = np.array([[1, 1, 0], [0, 1, 1]], dtype=int)
    b = np.array([1, 0], dtype=int)
    sols = enumerate_satisfying_assignments(A, b)
    # x = (x_0, x_1, x_2): x_0 + x_1 = 1, x_1 + x_2 = 0  =>  x_1 = x_2 and x_0 != x_1.
    # MSB convention (bit 0 = MSB): x_0 is bit-of-2, x_1 is bit-of-1...
    # Hmm depends on convention. Just sanity-check via the satisfies fn.
    for x in sols:
        assert satisfies_gf2_affine(x, A, b)
    for x in range(2 ** 3):
        if x not in sols:
            assert not satisfies_gf2_affine(x, A, b)
    # 3 binary variables, 2 independent constraints -> 2^(3-2) = 2 solutions
    assert len(sols) == 2, f"expected 2 solutions, got {len(sols)}: {sols}"
    print(f"  [GF(2)-affine enumeration: 3 vars, 2 constraints -> {len(sols)} solutions, all verified]")

    # 3. Gibbs expectation: uniform weighting, observable = first bit.
    # 4 states {0,1,2,3}; observable(x) = x & 1. Uniform weight -> <obs> = 0.5.
    val = gibbs_expectation_brute([0, 1, 2, 3], lambda x: 1.0, lambda x: x & 1)
    assert abs(val - 0.5) < 1e-12, val
    # Non-uniform weighting: weight = 2^x; favours larger x. <obs> = (1*0 + 2*1 + 4*0 + 8*1)/(1+2+4+8) = 10/15
    val2 = gibbs_expectation_brute([0, 1, 2, 3], lambda x: 2.0 ** x, lambda x: x & 1)
    assert abs(val2 - 10.0 / 15.0) < 1e-12, val2
    print(f"  [Gibbs expectation: uniform=0.5, exponential weighting={val2:.4f} = 10/15]")

    # 4. verify_pipeline: a 3-stage arithmetic pipeline against known outputs.
    def r(_d, _p): return Route(member="m", cost=1.0)
    stages = [
        Stage("add", "arith", 3,    r, lambda d, p, _: (p or 0) + d),     # 0+3 = 3
        Stage("mul", "arith", 2,    r, lambda d, p, _: (p or 0) * d),     # 3*2 = 6
        Stage("sq",  "arith", None, r, lambda d, p, _: (p or 0) ** 2),    # 6^2 = 36
    ]
    ok, report = verify_pipeline(stages, [3, 6, 36], seed=0)
    assert ok, report
    print(f"  [verify_pipeline 3-stage: 3 -> 6 -> 36 against reference, all match]")

    # 5. verify_pipeline catches a mismatch.
    ok, report = verify_pipeline(stages, [3, 6, 35], seed=0)
    assert not ok
    assert "FAIL" in report
    print("  [verify_pipeline catches a deliberate mismatch in the last stage]")


if __name__ == "__main__":
    self_test()
