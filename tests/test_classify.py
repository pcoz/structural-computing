"""Tests for the classifier primitives: classify_constraint_set,
classify_graph, classify_signature, and the top-level dispatcher."""

import numpy as np
import pytest

from structural_computing import (
    Classification,
    classify,
    classify_constraint_set,
    classify_graph,
    classify_signature,
)


# ---------------------------------------------------------------------------
# classify_constraint_set
# ---------------------------------------------------------------------------

def test_constraint_t0_linear_only():
    A = np.array([[1, 1, 0], [0, 1, 1]], dtype=int)
    b = np.array([1, 0], dtype=int)
    cls = classify_constraint_set(A=A, b=b)
    assert cls.tier == "T0"
    assert cls.in_family
    assert "n_variables" in cls.meters


def test_constraint_t1_with_quadratic():
    A = np.array([[1, 1, 1, 1]], dtype=int)
    b = np.array([0], dtype=int)
    Q = [np.array([[0, 1, 0, 0], [0, 0, 0, 0],
                    [0, 0, 0, 1], [0, 0, 0, 0]], dtype=int)]
    c = np.array([0], dtype=int)
    cls = classify_constraint_set(A=A, b=b, Q=Q, c=c)
    assert cls.tier == "T1"
    assert cls.in_family


def test_constraint_t7_mod_p_neq_2():
    A = np.array([[1, 1]], dtype=int)
    b = np.array([0], dtype=int)
    cls = classify_constraint_set(A=A, b=b, modulus=7)
    assert cls.tier == "T7"
    assert not cls.in_family


def test_constraint_t0_empty():
    """Edge case: zero-quadratic = T0 even when Q is provided but empty."""
    A = np.array([[1, 0]], dtype=int)
    b = np.array([0], dtype=int)
    # No quadratic constraints -> still T0
    cls = classify_constraint_set(A=A, b=b)
    assert cls.tier == "T0"


# ---------------------------------------------------------------------------
# classify_graph
# ---------------------------------------------------------------------------

def test_graph_t2_planar():
    """K_4 tetrahedron: planar, T2."""
    rotation = {0: [1, 2, 3], 1: [0, 3, 2], 2: [0, 1, 3], 3: [0, 2, 1]}
    cls = classify_graph(rotation)
    assert cls.tier == "T2"
    assert cls.meters["genus"] == 0
    assert cls.in_family


def test_graph_t4_genus_1():
    """4x4 toroidal grid: genus 1, T4."""
    n = 4
    rotation = {}
    for i in range(n):
        for j in range(n):
            v = (i, j)
            rotation[v] = [(i, (j + 1) % n), ((i + 1) % n, j),
                            (i, (j - 1) % n), ((i - 1) % n, j)]
    cls = classify_graph(rotation)
    assert cls.tier == "T4"
    assert cls.meters["genus"] == 1
    assert cls.in_family


def test_graph_dart_chain_used_for_t4():
    """The classifier records that dart-chain was the intersection-number primitive."""
    n = 4
    rotation = {}
    for i in range(n):
        for j in range(n):
            v = (i, j)
            rotation[v] = [(i, (j + 1) % n), ((i + 1) % n, j),
                            (i, (j - 1) % n), ((i - 1) % n, j)]
    cls = classify_graph(rotation)
    assert cls.meters["intersection_via"] == "dart_chain_intersection"


# ---------------------------------------------------------------------------
# classify_signature
# ---------------------------------------------------------------------------

def test_signature_arity_2_t2():
    cls = classify_signature([0, 1, 1])           # OR
    assert cls.tier == "T2"
    assert cls.meters["arity"] == 2
    assert cls.meters["basis_aware_rank"] in (0, 1, 2)


def test_signature_arity_3_t3():
    cls = classify_signature([0, 1, 0, 1])        # XOR_arity_3
    assert cls.tier == "T3"
    assert cls.meters["arity"] == 3


def test_signature_rank_always_at_most_2():
    """The publicly-original symmetric-signature-rank-<=2 result."""
    for values in ([0, 1, 1], [0, 0, 1], [0, 1, 0], [1, 0, 1],
                    [0, 1, 0, 1], [0, 0, 1, 0, 0], [0, 0, 0, 1, 1, 1]):
        cls = classify_signature(values)
        assert cls.meters["basis_aware_rank"] in (0, 1, 2)


# ---------------------------------------------------------------------------
# Top-level classify() dispatcher
# ---------------------------------------------------------------------------

def test_classify_dispatch_constraint_set():
    A = np.array([[1, 0]], dtype=int); b = np.array([0], dtype=int)
    cls = classify({"kind": "constraint_set", "data": {"A": A, "b": b}})
    assert cls.tier == "T0"


def test_classify_dispatch_graph():
    rotation = {0: [1, 2, 3], 1: [0, 3, 2], 2: [0, 1, 3], 3: [0, 2, 1]}
    cls = classify({"kind": "graph", "data": {"rotation": rotation}})
    assert cls.tier == "T2"


def test_classify_dispatch_signature():
    cls = classify({"kind": "signature", "data": {"values": [0, 1, 1]}})
    assert cls.tier == "T2"


def test_classify_unknown_kind():
    """Unknown problem kinds fall to T7 (advised)."""
    cls = classify({"kind": "mysterious-soup"})
    assert cls.tier == "T7"
    assert not cls.in_family


# ---------------------------------------------------------------------------
# Classification dataclass surface
# ---------------------------------------------------------------------------

def test_classification_fields():
    cls = Classification(tier="T0", meters={"x": 1}, in_family=True, reasoning="test")
    assert cls.tier == "T0"
    assert cls.meters == {"x": 1}
    assert cls.in_family
    assert cls.reasoning == "test"
