"""Originality test: every SYMMETRIC signature has basis-aware matchgate
rank in {0, 1, 2}, via a common-basis parity-split construction.

This is the publicly-original mathematical result the framework's
classifier wires in via `holant_tools.basis_aware_matchgate_rank`
(shipped in holant-tools v0.4.0, originally observed 2026-05-26).

These tests assert the rank-<=2 property holds across the standard
classical symmetric signatures. If any of them ever produces rank > 2,
either the theorem has been refuted (newsworthy) or the framework has
a bug.
"""

import pytest

from structural_computing import classify_signature


# ---------------------------------------------------------------------------
# Classical symmetric signatures (values indexed by Hamming weight 0..arity)
# ---------------------------------------------------------------------------

CLASSICAL_SIGNATURES = [
    # name, values
    ("OR_arity_2",                [0, 1, 1]),
    ("AND_arity_2",               [0, 0, 1]),
    ("XOR_arity_2",               [0, 1, 0]),
    ("EQUAL_arity_2",             [1, 0, 1]),
    ("OR_arity_3",                [0, 1, 1, 1]),
    ("XOR_arity_3",               [0, 1, 0, 1]),
    ("MAJORITY_arity_3",          [0, 0, 1, 1]),
    ("EXACTLY_1_of_3",            [0, 1, 0, 0]),
    ("EXACTLY_2_of_4",            [0, 0, 1, 0, 0]),
    ("AT_LEAST_2_of_4",           [0, 0, 1, 1, 1]),
    ("AT_MOST_1_of_4",            [1, 1, 0, 0, 0]),
    ("MAJORITY_arity_5",          [0, 0, 0, 1, 1, 1]),
    ("AT_LEAST_3_of_5",           [0, 0, 0, 1, 1, 1]),
    ("ALL_OR_NOTHING_arity_4",    [1, 0, 0, 0, 1]),
    ("EXACTLY_3_of_5",            [0, 0, 0, 1, 0, 0]),
    ("XOR_arity_4",               [0, 1, 0, 1, 0]),
    ("XOR_arity_5",               [0, 1, 0, 1, 0, 1]),
]


@pytest.mark.parametrize("name,values", CLASSICAL_SIGNATURES)
def test_symmetric_signature_rank_at_most_2(name, values):
    """Every symmetric signature MUST have basis-aware matchgate rank
    in {0, 1, 2}. This is the publicly-original result. If this test
    fails, either the theorem has been refuted or the framework has a bug."""
    cls = classify_signature(values)
    rank = cls.meters["basis_aware_rank"]
    assert rank in (0, 1, 2), (
        f"{name}: signature {values} has basis-aware rank {rank} -- not in {{0, 1, 2}}. "
        f"Either the publicly-original symmetric-signature-rank-<=2 result has been "
        f"refuted (file a paper!), or holant_tools.basis_aware_matchgate_rank has a bug."
    )


def test_all_classical_signatures_in_family():
    """Every classical symmetric signature classifies as in-family
    (T2 for arity <= 2, T3 for arity >= 3)."""
    for name, values in CLASSICAL_SIGNATURES:
        cls = classify_signature(values)
        arity = len(values) - 1
        if arity <= 2:
            assert cls.tier == "T2", f"{name}: tier {cls.tier}, expected T2"
        else:
            assert cls.tier == "T3", f"{name}: tier {cls.tier}, expected T3"
        assert cls.in_family, f"{name}: in_family is False, but every symmetric signature should be in-family"


def test_xor_arity_higher_still_rank_le_2():
    """Even high-arity XOR-like signatures should have rank <= 2."""
    # XOR generalised: value 1 iff Hamming weight is odd
    for arity in (3, 5, 7, 9):
        values = [w % 2 for w in range(arity + 1)]
        cls = classify_signature(values)
        rank = cls.meters["basis_aware_rank"]
        assert rank in (0, 1, 2), f"arity-{arity} XOR-like has rank {rank}"


def test_cardinality_signatures_rank_le_2():
    """EXACTLY-K signatures for various (n, k) should all have rank <= 2."""
    for n in (3, 4, 5, 6, 7):
        for k in range(n + 1):
            values = [1 if w == k else 0 for w in range(n + 1)]
            cls = classify_signature(values)
            rank = cls.meters["basis_aware_rank"]
            assert rank in (0, 1, 2), (
                f"EXACTLY-{k}-of-{n}: signature {values} has rank {rank}"
            )
