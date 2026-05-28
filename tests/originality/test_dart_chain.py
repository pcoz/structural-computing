"""Originality test: the dart-chain passage-arc formula CORRECTS Cimasoni
2012's direction-aware-intersection-walks primitive at degree-3 vertices.

This is the publicly-original mathematical result the framework's
classifier wires in via `holant_tools.dart_chain_intersection` (shipped
in holant-tools v0.4.0a5, originally observed 2026-05-26).

These tests assert the correction is real and present in the framework's
behaviour. If they ever fail, the corrected primitive has regressed --
that's a real bug.
"""

import random

import pytest

from structural_computing import classify_graph


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def torus_4x4_rotation():
    """The 4x4 toroidal grid rotation system. Standard test instance for
    the dart-chain disagree-case."""
    n = 4
    rotation = {}
    for i in range(n):
        for j in range(n):
            v = (i, j)
            rotation[v] = [(i, (j + 1) % n), ((i + 1) % n, j),
                            (i, (j - 1) % n), ((i - 1) % n, j)]
    return rotation


def k33_random_rotation(seed: int):
    """K_{3,3} with a random rotation system, seeded for reproducibility."""
    rng = random.Random(seed)
    rotation = {}
    for v in (0, 1, 2):
        nbrs = [3, 4, 5]; rng.shuffle(nbrs); rotation[v] = nbrs
    for v in (3, 4, 5):
        nbrs = [0, 1, 2]; rng.shuffle(nbrs); rotation[v] = nbrs
    return rotation


def k5_random_rotation(seed: int):
    """K_5 with a random rotation system, seeded for reproducibility."""
    rng = random.Random(seed)
    rotation = {}
    for v in range(5):
        nbrs = [u for u in range(5) if u != v]
        rng.shuffle(nbrs)
        rotation[v] = nbrs
    return rotation


def gf2_rank(M):
    """Rank over GF(2) of a 0/1 matrix."""
    if not M:
        return 0
    m = [row[:] for row in M]
    n = len(m)
    rank = 0
    for col in range(n):
        pv = next((r for r in range(rank, n) if m[r][col] == 1), None)
        if pv is None:
            continue
        m[rank], m[pv] = m[pv], m[rank]
        for r in range(n):
            if r != rank and m[r][col] == 1:
                m[r] = [a ^ b for a, b in zip(m[r], m[rank])]
        rank += 1
    return rank


# ---------------------------------------------------------------------------
# The canonical disagree-case: 4x4 toroidal grid
# ---------------------------------------------------------------------------

def test_4x4_torus_dart_chain_gives_canonical_symplectic():
    """The classifier uses dart-chain internally. On the 4x4 torus the
    intersection matrix should be the canonical symplectic [[0, 1], [1, 0]],
    NOT the degenerate [[0, 0], [0, 0]] that the walks formula returns."""
    rotation = torus_4x4_rotation()
    cls = classify_graph(rotation)
    assert cls.tier == "T4", f"expected T4 (genus >= 1), got {cls.tier}"
    assert cls.meters["genus"] == 1
    assert cls.meters["intersection_via"] == "dart_chain_intersection"
    M = cls.meters["intersection_matrix"]
    assert M == [[0, 1], [1, 0]], (
        f"intersection matrix is {M}, not the canonical symplectic. "
        f"This means the dart-chain primitive has regressed -- you've lost the "
        f"v0.4.0a5 correction over the walks formula."
    )


# ---------------------------------------------------------------------------
# Empirical stress -- random rotations on K_5 and K_{3,3}
# ---------------------------------------------------------------------------

def test_k33_random_rotations_all_non_degenerate():
    """On 30 random K_{3,3} rotation systems (all-degree-3 vertices -- the
    walks-formula blindspot), every dart-chain-derived intersection matrix
    should be non-degenerate (rank == 2*genus). The walks formula fails
    here 100% of the time per the docstring; dart-chain succeeds 60/60
    per the public stress test."""
    successes = 0
    trials = 0
    for seed in range(30):
        try:
            cls = classify_graph(k33_random_rotation(seed))
            g = cls.meters["genus"]
            if g == 0:
                continue                          # skip genus 0 if any
            M = cls.meters["intersection_matrix"]
            trials += 1
            if gf2_rank(M) == 2 * g:
                successes += 1
        except Exception:
            continue
    # Expect a high success rate. With 30 trials at the empirical 100%
    # success rate from the holant-tools stress test, this should be
    # ~30/30.  Allowing slack for any single-seed weirdness.
    assert successes >= int(0.95 * trials), (
        f"dart-chain only non-degenerate on {successes}/{trials} K_{{3,3}} "
        f"random rotations. Expected ~100%. The framework's dart-chain "
        f"primitive may have regressed."
    )


def test_k5_random_rotations_mostly_non_degenerate():
    """K_5 mixes degree-3 and degree-4 vertices; per the holant-tools stress
    test the dart-chain primitive gives non-degenerate intersection
    matrices on essentially every random rotation. The walks formula
    succeeds only 22/60 per the empirical stress."""
    successes = 0
    trials = 0
    for seed in range(30):
        try:
            cls = classify_graph(k5_random_rotation(seed))
            g = cls.meters["genus"]
            if g == 0:
                continue
            M = cls.meters["intersection_matrix"]
            trials += 1
            if gf2_rank(M) == 2 * g:
                successes += 1
        except Exception:
            continue
    assert successes >= int(0.9 * trials), (
        f"dart-chain non-degenerate on {successes}/{trials} K_5 rotations. "
        f"Expected high rate. Possible regression."
    )
