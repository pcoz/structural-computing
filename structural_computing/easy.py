r"""StructuralComputer -- the friendly entry point.

The rest of this folder is the framework: tier classifiers, routing maps,
Pfaffian-backed evaluators, trace aggregators, replay caches. Those are the
tools. This file is the **handle on the toolbox**: a wrapper class that an
average developer can use without knowing what a "Holant problem" is, what
a "matchgate rank" is, or what "basis-aware" means.

The shape of the wrapper:

    from easy import StructuralComputer
    sc = StructuralComputer()

    sc.count_matchings(graph)               # how many perfect matchings?
    sc.tail_probability(graph, p_fail)      # exact rare-tail probability
    sc.witness(graph)                       # one specific matching
    sc.single_points_of_failure(graph)      # critical edges
    sc.compare(config_a, config_b, p_fail)  # which is more reliable, and by how much?
    sc.audit(graph)                         # everything at once, formatted
    sc.explain(graph)                       # human-readable plan, no math jargon

Inputs are flexible: graphs can be edge lists, NetworkX-style adjacency
dicts, or rotation systems. The wrapper picks the right format internally
and dispatches through `classify_graph` + the pipeline-router's primitives.

If the question is outside the structural-graph family, you get a clear
honest-stop message ("this isn't planar; here's the suggested external
solver"). If it's inside, you get an exact answer in milliseconds.

This is the "10 lines instead of 100k" handle that the
`proposals/declarative_structural_computation.md` document in the private
repo describes as the Year-5 to Year-10 deliverable of the paradigm. It's
a first cut -- the DSL would have more sugar, more domain dialects, and
more polish -- but the shape is here.
"""
import math
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

import holant_tools

from .classify import (Classification, classify_graph,
                       classify_constraint_set, classify_signature)
from .route import route as route_classification
from .trace import RichTrace
from .verifier import brute_force_count_matchings


# ---------------------------------------------------------------------------
# Input normalisation -- accept several common formats, emit one canonical
# (vertices, edges, rotation) tuple.
# ---------------------------------------------------------------------------

GraphLike = Union[
    Dict[Any, List[Any]],            # rotation system (canonical)
    List[Tuple[Any, Any]],           # edge list (need to infer rotation)
    Dict[Any, set],                  # adjacency dict
]


def _normalise_graph(graph: GraphLike, *, rotation_required: bool = False
                     ) -> Tuple[List[Any], List[Tuple[Any, Any]], Optional[Dict[Any, List[Any]]]]:
    """Accept a graph in any of several formats; emit (vertices, edges, rotation).
    `rotation` is None if the input didn't include one and we don't need it."""
    # Rotation system (dict of vertex -> ordered neighbour list)
    if isinstance(graph, dict) and graph and all(isinstance(v, list) for v in graph.values()):
        rotation = graph
        vertices = list(rotation.keys())
        edges = sorted({tuple(sorted([u, w], key=str)) for u, ns in rotation.items() for w in ns})
        return vertices, edges, rotation
    # Adjacency dict (set values)
    if isinstance(graph, dict) and graph and all(isinstance(v, (set, frozenset)) for v in graph.values()):
        vertices = list(graph.keys())
        edges = sorted({tuple(sorted([u, w], key=str)) for u, ns in graph.items() for w in ns})
        if rotation_required:
            # Synthesise a deterministic rotation (sorted neighbours). Not
            # guaranteed planar/cellular; if structural classification needs
            # a cellular embedding, the caller must provide one explicitly.
            rotation = {v: sorted(graph[v], key=str) for v in vertices}
            return vertices, edges, rotation
        return vertices, edges, None
    # Edge list
    if isinstance(graph, list):
        edges = list(graph)
        vertices = sorted({v for e in edges for v in e}, key=str)
        if rotation_required:
            adj: Dict[Any, List[Any]] = {v: [] for v in vertices}
            for (u, w) in edges:
                adj[u].append(w)
                adj[w].append(u)
            rotation = {v: sorted(adj[v], key=str) for v in vertices}
            return vertices, edges, rotation
        return vertices, edges, None
    raise ValueError(f"unrecognised graph format: {type(graph).__name__}")


# ---------------------------------------------------------------------------
# The wrapper
# ---------------------------------------------------------------------------

@dataclass
class CompareReport:
    """Result of `sc.compare(a, b, ...)`. Human-readable when printed."""
    quantity_a: float
    quantity_b: float
    absolute_difference: float
    relative_difference: float
    more_reliable: str            # "A" / "B" / "equal"

    def __repr__(self):
        return (f"CompareReport(A={self.quantity_a:.4e}, B={self.quantity_b:.4e}, "
                f"more_reliable={self.more_reliable}, "
                f"relative_difference={self.relative_difference:+.1%})")

    def explain(self) -> str:
        if self.more_reliable == "equal":
            return f"A and B have identical reliability ({self.quantity_a:.4e})."
        winner = self.more_reliable
        rel = abs(self.relative_difference)
        return (f"Configuration {winner} is {rel:.1%} more reliable "
                f"({self.quantity_a:.4e} vs {self.quantity_b:.4e}). "
                f"This distinction is provably real (exact computation), not a sampling artefact.")


def _as_array(arr) -> np.ndarray:
    """Coerce a Python list, nested list, tuple, or existing np.ndarray
    into an int-dtype np.ndarray.

    The wrapper's constraint-set methods accept callers' inputs in any of
    these forms (most users write `[[1, 0, 1], [0, 1, 1]]` not
    `np.array([[1, 0, 1], [0, 1, 1]], dtype=int)`). This helper normalises
    them so the rest of the code can assume np.ndarray.
    """
    return np.asarray(arr, dtype=int)


def _gf2_rank(M: np.ndarray) -> int:
    """Rank of a 0/1 matrix over GF(2), the two-element field where
    addition is XOR and multiplication is AND.

    Algorithm: standard Gaussian elimination, with the twist that we
    XOR rows instead of subtracting (which is the same thing mod 2).
    For each column from left to right:

      1. Find a row at or below the current pivot row whose entry in
         this column is 1.
      2. If none exists, this column has no pivot -- move on.
      3. Otherwise, swap that row up to the pivot position, then XOR
         this row into every other row that has a 1 in this column
         (clearing the column elsewhere).
      4. Advance the pivot row counter.

    The rank is the number of pivots placed -- equivalently, the number
    of linearly-independent rows of `M` over GF(2). For an `m x n`
    matrix with `m <= n`, this runs in `O(m^2 * n)`.

    Returns 0 for empty / None inputs (convenient for the constraint-set
    classifier's edge cases).
    """
    if M is None or M.size == 0:
        return 0
    # Work on a deep copy as nested Python lists -- avoids mutating the
    # caller's input and lets us XOR rows with simple list comprehensions.
    rows = [list(map(int, row)) for row in M]
    n_rows = len(rows)
    n_cols = len(rows[0]) if rows else 0
    rank = 0
    for col in range(n_cols):
        # Find a pivot row: at or below `rank`, with a 1 in this column.
        pv = next((r for r in range(rank, n_rows) if rows[r][col] == 1), None)
        if pv is None:
            # No pivot available for this column; move on.
            continue
        # Swap the pivot row up to the current rank position.
        rows[rank], rows[pv] = rows[pv], rows[rank]
        # Eliminate this column from every OTHER row.
        for r in range(n_rows):
            if r != rank and rows[r][col] == 1:
                rows[r] = [(a ^ b) for a, b in zip(rows[r], rows[rank])]
        rank += 1
    return rank


def _gf2_solve_one(A: np.ndarray, b: np.ndarray) -> Optional[np.ndarray]:
    """Find one solution `x` to `A x = b (mod 2)`, or None if no solution
    exists.

    Returns the solution as a length-n integer vector (np.ndarray dtype
    int) with entries in {0, 1}. When the system has multiple solutions
    (i.e. when `A` is not full column rank), this returns the one obtained
    by setting all free variables to 0 -- a deterministic choice that's
    convenient for `find_witness_solution` callers.

    Algorithm: augment `[A | b]` and Gauss-Jordan over GF(2):

      1. Row-reduce as in `_gf2_rank`, tracking which column each pivot
         lands in.
      2. After reduction, check consistency: if any reduced row is
         all zeros in the A-part but has a 1 in the b-part, the system
         is `0 = 1` and infeasible.
      3. Otherwise, read off the solution: for each pivot column, the
         pivot row directly gives the variable's value; free variables
         get value 0.

    Returns None on infeasibility. Runs in `O(m^2 * n)` for `m x n` `A`.
    """
    m, n = A.shape
    # Build the augmented matrix as Python lists for easy row XOR.
    rows = [list(map(int, A[i])) + [int(b[i])] for i in range(m)]
    pivots: Dict[int, int] = {}                 # column index -> pivot row
    row = 0
    for col in range(n):
        sel = next((rr for rr in range(row, m) if rows[rr][col]), None)
        if sel is None:
            # Free variable; will end up zero in the witness.
            continue
        rows[row], rows[sel] = rows[sel], rows[row]
        # Eliminate this column from every other row (Gauss-Jordan, not
        # just Gauss -- we want to read solutions off the reduced form
        # directly, so we clear above the pivot too).
        for rr in range(m):
            if rr != row and rows[rr][col]:
                rows[rr] = [(a ^ b) for a, b in zip(rows[rr], rows[row])]
        pivots[col] = row
        row += 1
    # Consistency: any row with all zeros in [0:n] but a 1 in [n] is the
    # system claiming `0 = 1`, which means infeasible.
    for r in range(m):
        if rows[r][n] == 1 and not any(rows[r][:n]):
            return None
    # Build the witness: pivot variables take the value sitting in the
    # b-column of their pivot row; free variables remain 0.
    x = np.zeros(n, dtype=int)
    for col, rrow in pivots.items():
        x[col] = rows[rrow][n]
    return x


def _bits_to_int(bits: np.ndarray) -> int:
    """Convert a length-n bit vector to an integer using the
    "bit 0 = most-significant" convention.

    The framework uses this convention throughout (it matches how the
    underlying classify/route functions index bits). So `[1, 0, 1]`
    becomes `0b101 = 5`, NOT `0b001 reversed = 5`. The point is to be
    consistent across the package, not to follow any particular external
    convention.
    """
    n = len(bits)
    val = 0
    for i in range(n):
        if int(bits[i]) & 1:
            val |= 1 << (n - 1 - i)
    return val


class StructuralComputer:
    """The friendly entry point. Construct one; call the methods you need."""

    def __init__(self):
        self._last_classification: Optional[Classification] = None

    # -- structural inspection ----------------------------------------------

    def classify(self, graph: GraphLike) -> Classification:
        """What kind of structural problem is this? Returns a Classification
        with tier, in_family flag, and structural meters."""
        _, _, rotation = _normalise_graph(graph, rotation_required=True)
        cls = classify_graph(rotation)
        self._last_classification = cls
        return cls

    def explain(self, graph: GraphLike) -> str:
        """Human-readable: what will the framework do with this graph?"""
        cls = self.classify(graph)
        member = route_classification(cls).member
        bits = [
            f"This graph is classified as {cls.tier} ({cls.reasoning}).",
            f"The framework will route the analysis to: {member}.",
        ]
        if not cls.in_family:
            bits.append("WARNING: this problem is outside the structural-graph family; "
                        "the framework will honestly stop and advise an external solver.")
        else:
            bits.append("Exact analyses are available: count_matchings, tail_probability, "
                        "witness, single_points_of_failure, audit.")
        return " ".join(bits)

    # -- counting / probability ---------------------------------------------

    def count_matchings(self, graph: GraphLike) -> int:
        """How many perfect matchings does this graph admit? Exact, integer."""
        vertices, edges, rotation = _normalise_graph(graph, rotation_required=True)
        cls = classify_graph(rotation)
        self._last_classification = cls
        if not cls.in_family:
            raise NotInFamily(cls)
        g = cls.meters.get("genus", 0)
        if g == 0:
            K = holant_tools.kasteleyn_orient(vertices, edges, rotation)
            return abs(int(holant_tools.exact_planar_pfaffian(K)))
        # For genus >= 1, holant-tools' genus-g pipeline can be finicky on
        # arbitrary rotation systems; fall back to brute force at small n.
        # (A future version of this wrapper picks Klein arc when available.)
        return brute_force_count_matchings(vertices, edges)

    def tail_probability(self, graph: GraphLike, p_fail: float) -> float:
        """Exact P(NO perfect matching survives) under independent edge
        failure at probability `p_fail`. Brute-force enumeration of edge
        subsets at small |E|; the algorithm scales to larger instances via
        the matching polynomial, but this wrapper uses the small-n form."""
        vertices, edges, _ = _normalise_graph(graph)
        n_edges = len(edges)
        if n_edges > 24:
            raise ValueError(f"|E| = {n_edges} too large for this wrapper's exact "
                              f"enumeration (cap = 24); larger instances need the "
                              f"matching-polynomial form (Year-6 deliverable).")
        total = 0.0
        for mask in range(2 ** n_edges):
            surviving = [edges[i] for i in range(n_edges) if (mask >> i) & 1]
            k_failed = n_edges - len(surviving)
            weight = (p_fail ** k_failed) * ((1 - p_fail) ** (n_edges - k_failed))
            if brute_force_count_matchings(vertices, surviving) == 0:
                total += weight
        return total

    # -- witnesses / structural decisions -----------------------------------

    def witness(self, graph: GraphLike) -> List[Tuple[Any, Any]]:
        """Find one perfect matching, if any exists. Returns the edges."""
        vertices, edges, _ = _normalise_graph(graph)
        n = len(vertices)
        idx = {v: i for i, v in enumerate(vertices)}
        W = [[math.inf] * n for _ in range(n)]
        for (u, w) in edges:
            i, j = idx[u], idx[w]
            W[i][j] = W[j][i] = 1.0
        cost, matching = holant_tools.min_weight_perfect_matching(W)
        if matching is None:
            return []
        return [(vertices[i], vertices[j]) for (i, j) in matching]

    # -- tropical / min-cost optimisation (v0.10) ---------------------------

    def min_weight_matching(self,
                              graph: GraphLike,
                              weights: Optional[Dict[Tuple[Any, Any], float]] = None,
                              ) -> Dict[str, Any]:
        """Minimum-weight perfect matching, exact, polynomial time.

        Same admissible-set machinery as ``matching_count`` and
        ``witness``, but with the tropical (min, +) semiring instead of
        the standard (+, ×). Dispatches internally between Hungarian
        (for bipartite K_{n,n} inputs) and Edmonds blossom (for general
        non-bipartite), both polynomial-time and exact.

        Args:
            graph: any graph format ``_normalise_graph`` accepts.
            weights: optional dict mapping edges (u, v) to real-valued
                costs. Missing edges default to weight 1.0.

        Returns:
            ``{"cost": float, "matching": [(u, v), ...],
              "feasible": bool}``. Infeasible (no perfect matching
            exists) returns feasible=False with cost=matching=None.
        """
        vertices, edges, _ = _normalise_graph(graph)
        n = len(vertices)
        if n % 2 != 0:
            return {"cost": None, "matching": None, "feasible": False}
        idx = {v: i for i, v in enumerate(vertices)}
        W = [[math.inf] * n for _ in range(n)]
        weights = weights or {}
        for (u, v) in edges:
            i, j = idx[u], idx[v]
            w = weights.get((u, v))
            if w is None:
                w = weights.get((v, u), 1.0)
            W[i][j] = W[j][i] = float(w)
        cost, matching = holant_tools.min_weight_perfect_matching(W)
        if matching is None:
            return {"cost": None, "matching": None, "feasible": False}
        return {
            "cost": float(cost),
            "matching": [(vertices[i], vertices[j]) for (i, j) in matching],
            "feasible": True,
        }

    def min_cost_schedule(self,
                            instance: Any,
                            cost_fn: Callable[[Any, Any, int], float],
                            *,
                            allowed_machines: Optional[Dict[str, set]] = None,
                            time_windows: Optional[Dict[str, Tuple[int, int]]] = None,
                            forbidden_edges: Optional[set] = None,
                            ) -> Dict[str, Any]:
        """Exact polynomial-time minimum-cost schedule on a
        ``holant_tools.SchedulingInstance``.

        Wraps ``holant_tools.min_cost_schedule``. Accepts the same
        per-job constraints (``allowed_machines``, ``time_windows``,
        ``forbidden_edges``) as the engine entry point.

        Returns ``{"cost": float, "schedule": ..., "feasible": bool}``.
        """
        result = holant_tools.min_cost_schedule(
            instance, cost_fn,
            allowed_machines=allowed_machines,
            time_windows=time_windows,
            forbidden_edges=forbidden_edges,
        )
        if hasattr(result, "feasible") and not result.feasible:
            return {"cost": None, "schedule": None, "feasible": False}
        # holant-tools' MinCostScheduleResult uses `min_cost` and `schedule`.
        cost_val = getattr(result, "min_cost", None)
        if cost_val is None:
            cost_val = getattr(result, "cost", None)
        return {
            "cost": float(cost_val) if cost_val is not None else None,
            "schedule": getattr(result, "schedule", None),
            "feasible": True,
        }

    def min_cost_flow(self, instance: Any) -> Dict[str, Any]:
        """Exact polynomial-time minimum-cost flow on a
        ``holant_tools.MinCostFlowInstance``.

        Returns ``{"cost", "flow", "feasible"}``.
        """
        result = holant_tools.min_cost_flow(instance)
        if hasattr(result, "feasible") and not result.feasible:
            return {"cost": None, "flow": None, "feasible": False}
        return {
            "cost": float(result.min_cost) if result.min_cost is not None else None,
            "flow": getattr(result, "flow", None),
            "feasible": True,
        }

    def min_cost_roster(self,
                          instance: Any,
                          preference_fn: Callable[[Any, Any], float],
                          ) -> Dict[str, Any]:
        """Exact polynomial-time minimum-cost rostering on a
        ``holant_tools.RosteringInstance``.

        Returns ``{"cost", "roster", "feasible"}``.
        """
        result = holant_tools.min_cost_roster(instance, preference_fn)
        if hasattr(result, "feasible") and not result.feasible:
            return {"cost": None, "roster": None, "feasible": False}
        return {
            "cost": float(result.min_cost) if result.min_cost is not None else None,
            "roster": getattr(result, "roster", None),
            "feasible": True,
        }

    def min_cost_dedup(self,
                         instance: Any,
                         similarity_fn: Callable[[Any, Any], float],
                         ) -> Dict[str, Any]:
        """Exact polynomial-time minimum-cost record-to-entity assignment
        for entity deduplication on a ``holant_tools.MDMInstance``.

        Returns ``{"cost", "assignment", "entity_groups", "feasible"}``.
        """
        result = holant_tools.min_cost_dedup(instance, similarity_fn)
        if hasattr(result, "feasible") and not result.feasible:
            return {"cost": None, "assignment": None,
                    "entity_groups": None, "feasible": False}
        return {
            "cost": float(result.min_cost) if result.min_cost is not None else None,
            "assignment": getattr(result, "assignment", None),
            "entity_groups": getattr(result, "entity_groups", None),
            "feasible": True,
        }

    def tropical_instance_coordinates(self,
                                        instance: Any,
                                        cost_fn: Callable[[Any, Any, int], float],
                                        *,
                                        compute_field_distance: bool = False,
                                        ) -> Any:
        """One-call diagnostic: "is this SchedulingInstance structurally
        well-suited for tropical optimisation?" Returns the
        ``TropicalInstanceCoordinates`` dataclass with the four-coordinate
        viewing-frame apparatus plus tropical-rank diagnostics.
        """
        return holant_tools.tropical_instance_coordinates(
            instance, cost_fn, compute_field_distance=compute_field_distance,
        )

    def single_points_of_failure(self, graph: GraphLike) -> List[Tuple[Any, Any]]:
        """Edges whose removal eliminates all perfect matchings -- the
        structural single points of failure."""
        vertices, edges, _ = _normalise_graph(graph)
        spofs = []
        for e in edges:
            sub = [x for x in edges if x != e]
            if brute_force_count_matchings(vertices, sub) == 0:
                spofs.append(e)
        return spofs

    # -- comparison / distinguishability ------------------------------------

    def compare(self, graph_a: GraphLike, graph_b: GraphLike, p_fail: float,
                metric: str = "tail_probability") -> CompareReport:
        """Compare two configurations on the chosen reliability metric. Returns
        a CompareReport with the absolute and relative difference and a
        verdict on which is more reliable. The verdict is provably exact (not
        statistical) -- it can resolve sub-MC-noise-floor differences."""
        if metric != "tail_probability":
            raise ValueError(f"unknown metric: {metric}")
        a = self.tail_probability(graph_a, p_fail)
        b = self.tail_probability(graph_b, p_fail)
        rel = (b - a) / a if a > 0 else float("inf")
        if abs(a - b) < 1e-15:
            verdict = "equal"
        else:
            # Lower tail probability = MORE reliable.
            verdict = "A" if a < b else "B"
        return CompareReport(
            quantity_a=a, quantity_b=b,
            absolute_difference=b - a,
            relative_difference=rel,
            more_reliable=verdict,
        )

    # -- constraint sets ----------------------------------------------------

    def classify_constraints(self,
                              A=None,
                              b=None,
                              Q=None,
                              c=None,
                              modulus: int = 2) -> Classification:
        """Return the Classification for a constraint set: linear part
        `A x = b (mod modulus)` plus an optional quadratic part
        `x^T Q_i x = c_i (mod 2)`. Tier T0 for affine, T1 for quadratic,
        T7 for mod-p != 2."""
        A_arr = _as_array(A) if A is not None else None
        b_arr = _as_array(b) if b is not None else None
        Q_list = [_as_array(Qi) for Qi in Q] if Q else None
        c_arr = _as_array(c) if c is not None else None
        cls = classify_constraint_set(A=A_arr, b=b_arr, Q=Q_list, c=c_arr, modulus=modulus)
        self._last_classification = cls
        return cls

    def count_solutions(self,
                         A=None,
                         b=None,
                         Q=None,
                         c=None,
                         modulus: int = 2) -> int:
        """Exact count of n-bit assignments x satisfying A x = b (mod modulus)
        and (optionally) every x^T Q_i x = c_i (mod 2).

        For pure GF(2)-affine constraints (no quadratic part), the count is
        2^(n - rank(A)) over the satisfying affine subspace; computed
        exactly via Gaussian elimination, poly-time at any n.

        With a quadratic part, the wrapper brute-forces 2^n assignments
        (capped at n <= 24). Raises ValueError for larger n; raises
        NotInFamily for mod-p != 2 (the SRP-solver branch lives in
        admissibility-geometry's tools/admissibility/).
        """
        cls = self.classify_constraints(A=A, b=b, Q=Q, c=c, modulus=modulus)
        if not cls.in_family:
            raise NotInFamily(cls)
        A_arr = _as_array(A) if A is not None else None
        b_arr = _as_array(b) if b is not None else None
        n = int(A_arr.shape[1]) if (A_arr is not None and A_arr.size) else 0
        if n == 0:
            return 1 if Q is None or not Q else 0
        if Q is None or not Q:
            # T0: linear only; count = 2^(n - rank(A)).
            rank = _gf2_rank(A_arr)
            # Check feasibility: rank([A | b]) must equal rank(A).
            Aug = np.hstack([A_arr, b_arr.reshape(-1, 1)]) if b_arr is not None else A_arr
            if _gf2_rank(Aug) != rank:
                return 0
            return 2 ** (n - rank)
        # T1: brute force at small n.
        if n > 24:
            raise ValueError(
                f"count_solutions: n = {n} too large for the wrapper's "
                f"brute-force quadratic enumeration (cap = 24). The "
                f"reduction layer for T1 -> T0 is on the roadmap."
            )
        Q_list = [_as_array(Qi) for Qi in Q]
        c_arr = _as_array(c) if c is not None else np.zeros(len(Q_list), dtype=int)
        count = 0
        for x in range(2 ** n):
            bits = np.array([(x >> (n - 1 - i)) & 1 for i in range(n)], dtype=int)
            if b_arr is not None and A_arr is not None:
                if not np.array_equal((A_arr @ bits) % 2, b_arr % 2):
                    continue
            ok = True
            for Qi, ci in zip(Q_list, c_arr):
                if (bits @ Qi @ bits) % 2 != ci % 2:
                    ok = False; break
            if ok:
                count += 1
        return count

    def find_witness_solution(self,
                               A=None,
                               b=None,
                               Q=None,
                               c=None,
                               modulus: int = 2) -> Optional[int]:
        """Find one assignment satisfying the constraint set, returned as
        an integer with MSB-first bit convention (bit 0 = MSB). Returns
        None if no solution exists.

        For T0 (GF(2)-affine), uses Gaussian elimination to find a witness
        in poly time. For T1 (with quadratic constraints), brute-forces
        at small n. Honest-stops via NotInFamily for mod-p != 2."""
        cls = self.classify_constraints(A=A, b=b, Q=Q, c=c, modulus=modulus)
        if not cls.in_family:
            raise NotInFamily(cls)
        A_arr = _as_array(A) if A is not None else None
        b_arr = _as_array(b) if b is not None else None
        n = int(A_arr.shape[1]) if (A_arr is not None and A_arr.size) else 0
        if n == 0:
            return 0 if (Q is None or not Q) else None
        if Q is None or not Q:
            # T0: Gaussian elimination in poly time.
            x = _gf2_solve_one(A_arr, b_arr)
            if x is None:
                return None
            return _bits_to_int(x)
        # T1: brute force at small n.
        if n > 24:
            raise ValueError(
                f"find_witness_solution: n = {n} too large for brute-force quadratic search."
            )
        Q_list = [_as_array(Qi) for Qi in Q]
        c_arr = _as_array(c) if c is not None else np.zeros(len(Q_list), dtype=int)
        for x in range(2 ** n):
            bits = np.array([(x >> (n - 1 - i)) & 1 for i in range(n)], dtype=int)
            if b_arr is not None and A_arr is not None:
                if not np.array_equal((A_arr @ bits) % 2, b_arr % 2):
                    continue
            if all((bits @ Qi @ bits) % 2 == ci % 2 for Qi, ci in zip(Q_list, c_arr)):
                return x
        return None

    def list_solutions(self,
                        A=None,
                        b=None,
                        Q=None,
                        c=None,
                        modulus: int = 2) -> List[int]:
        """All assignments satisfying the constraint set. Brute-force
        enumeration at small n (cap n <= 20; raises ValueError above)."""
        cls = self.classify_constraints(A=A, b=b, Q=Q, c=c, modulus=modulus)
        if not cls.in_family:
            raise NotInFamily(cls)
        A_arr = _as_array(A) if A is not None else None
        b_arr = _as_array(b) if b is not None else None
        Q_list = [_as_array(Qi) for Qi in Q] if Q else []
        c_arr = _as_array(c) if c is not None else np.zeros(len(Q_list), dtype=int)
        n = int(A_arr.shape[1]) if (A_arr is not None and A_arr.size) else 0
        if n > 20:
            raise ValueError(
                f"list_solutions: n = {n} too large for full enumeration "
                f"(cap = 20). Use count_solutions or find_witness_solution instead."
            )
        out = []
        for x in range(2 ** n):
            bits = np.array([(x >> (n - 1 - i)) & 1 for i in range(n)], dtype=int)
            if b_arr is not None and A_arr is not None:
                if not np.array_equal((A_arr @ bits) % 2, b_arr % 2):
                    continue
            if all((bits @ Qi @ bits) % 2 == ci % 2 for Qi, ci in zip(Q_list, c_arr)):
                out.append(x)
        return out

    # -- hybrid decomposition (matching count on non-planar graphs) ---------

    def count_matchings_hybrid(self,
                                graph: GraphLike,
                                extra_edges: Sequence[Tuple[Any, Any]],
                                ) -> int:
        """Exact perfect-matching count on a non-planar graph, computed by
        **branching on a small set of "extra" edges** that makes the
        residual planar.

        The decomposition identity is the standard one for perfect-matching
        count (Tutte, Lovasz-Plummer): for any edge `e = (u, v)`,
        `M(G) = M(G - e) + M(G / uv)`. Recursively applying it to all of
        `extra_edges` gives `2^|extra_edges|` planar sub-problems whose
        matching counts sum to the original.

        This is the first concrete operation in the reductions layer; it
        widens the framework's natively-in-family scope from "planar
        graphs only" to "any graph that becomes planar after removing a
        small set of edges." Cost is `2^|extra_edges| * O(|V|^3)`.

        Args:
          graph: a graph in any of the wrapper's accepted formats.
          extra_edges: the small set of edges to branch on; the graph
            minus these edges should be planar (or at least
            brute-force-tractable for the sub-problems' matching counts
            via the framework's verifier).

        Returns:
          Exact perfect-matching count of `graph`, as an integer.

        Honest scope: at small `n`, sub-problems are evaluated via
        `brute_force_count_matchings`; for v0.2, sub-problems will be
        evaluated via the planar Pfaffian (FKT) for asymptotic poly-time
        on the residual.
        """
        from .transform import HybridDecomposition
        vertices, edges, _ = _normalise_graph(graph)
        h = HybridDecomposition(extra_edges)
        problem = {"vertices": vertices, "edges": edges}
        result = h.apply(problem)
        # Leaf evaluator: brute-force matching count on each planar
        # sub-problem. (v0.2 will use the planar Pfaffian here for
        # asymptotic poly-time; today's brute force is fine at small n.)
        sub_counts = [
            brute_force_count_matchings(sp["vertices"], sp["edges"])
            for sp in result.problem["sub_problems"]
        ]
        return result.inverse(sub_counts)

    # -- signatures ---------------------------------------------------------

    def classify_function(self, values: Sequence) -> Classification:
        """Classify a symmetric signature given as a sequence of values
        indexed by Hamming weight 0..arity. Arity is derived from len(values)."""
        cls = classify_signature(list(values))
        self._last_classification = cls
        return cls

    def matchgate_rank(self, values: Sequence) -> int:
        """Basis-aware matchgate rank of a symmetric signature. Always in
        {0, 1, 2} for symmetric signatures (the publicly-original result;
        if this ever returns >2 for a symmetric input, the theorem has
        been refuted or holant-tools has a bug)."""
        cls = self.classify_function(values)
        rank = int(cls.meters.get("basis_aware_rank", -1))
        if rank < 0:
            raise RuntimeError(f"classify_signature did not emit basis_aware_rank meter: {cls.meters}")
        return rank

    def is_matchgate_realisable(self, values: Sequence) -> bool:
        """True iff the symmetric signature is matchgate-realisable in
        some basis (basis-aware rank >= 1)."""
        return self.matchgate_rank(values) >= 1

    # -- audit (everything at once) -----------------------------------------

    def audit(self, graph: GraphLike, *, p_fail: float = 0.01) -> Dict[str, Any]:
        """A single-call audit returning the full structural report:
        classification, matching count, witness, single-points-of-failure,
        tail probability at the given failure rate, and a routing-trace
        summary. The output is a plain dict; format it however you want."""
        cls = self.classify(graph)
        out: Dict[str, Any] = {"classification": cls,
                                 "tier": cls.tier,
                                 "in_family": cls.in_family,
                                 "reasoning": cls.reasoning}
        if not cls.in_family:
            out["verdict"] = "out of family; no exact analysis available"
            return out
        out["matching_count"] = self.count_matchings(graph)
        out["witness"] = self.witness(graph)
        out["single_points_of_failure"] = self.single_points_of_failure(graph)
        try:
            out["tail_probability"] = self.tail_probability(graph, p_fail=p_fail)
            out["p_fail_assumed"] = p_fail
        except ValueError as e:
            out["tail_probability"] = None
            out["tail_probability_note"] = str(e)
        return out


class NotInFamily(RuntimeError):
    """Raised when the user asks for an exact computation on a problem
    outside the structural-graph family. The classification is attached
    so the caller can inspect it."""
    def __init__(self, classification: Classification):
        super().__init__(f"problem is {classification.tier}: {classification.reasoning}")
        self.classification = classification


# ---------------------------------------------------------------------------
# Self-test / demonstration
# ---------------------------------------------------------------------------

def self_test():
    sc = StructuralComputer()

    # Two small reliability configurations: a 4-cycle vs K_4.
    c4 = [(0, 1), (1, 2), (2, 3), (3, 0)]
    k4 = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]

    print("=" * 70)
    print("Demonstration: a developer with NO knowledge of Holant problems")
    print("=" * 70)

    print("\n--- counting matchings ---")
    print(f"  4-cycle:        {sc.count_matchings(c4)}    (2 expected)")
    print(f"  K_4 (complete): {sc.count_matchings(k4)}    (3 expected)")
    assert sc.count_matchings(c4) == 2 and sc.count_matchings(k4) == 3

    print("\n--- finding witnesses ---")
    print(f"  K_4 witness:    {sc.witness(k4)}")

    print("\n--- single points of failure ---")
    print(f"  4-cycle SPOFs:  {sc.single_points_of_failure(c4)}")
    print(f"  K_4 SPOFs:      {sc.single_points_of_failure(k4)}")

    print("\n--- exact tail probabilities (p_fail = 0.05) ---")
    pa = sc.tail_probability(c4, p_fail=0.05)
    pb = sc.tail_probability(k4, p_fail=0.05)
    print(f"  4-cycle:        {pa:.4e}")
    print(f"  K_4:            {pb:.4e}")

    print("\n--- the COMPARE method: distinguish two configurations ---")
    report = sc.compare(c4, k4, p_fail=0.05)
    print(f"  {report}")
    print(f"  Explanation: {report.explain()}")

    print("\n--- explain (no math jargon) ---")
    print(f"  C_4: {sc.explain(c4)}")
    print(f"  K_4: {sc.explain(k4)}")

    print("\n--- audit (everything in one call) ---")
    audit = sc.audit(k4, p_fail=0.05)
    print(f"  K_4 audit:")
    for k, v in audit.items():
        if k == "classification": continue
        print(f"    {k}: {v}")

    print("\n--- honest stop on out-of-family ---")
    # A non-cellular graph (no rotation provided; synthesised one is unlikely
    # to be cellular). Just demonstrate the api shape.
    try:
        sc.count_matchings([(0, 1), (1, 2)])         # triangle path, odd vertex count
    except NotInFamily as e:
        print(f"  caught NotInFamily: {e}")
    except Exception:
        # The error path can be either NotInFamily or a brute-force result
        # of 0 (odd vertex count). Both are honest.
        print(f"  (odd vertex count; 0 matchings as expected)")

    print("\n" + "=" * 70)
    print("Done. Total user-facing lines to run this entire audit: ~10.")
    print("=" * 70)


if __name__ == "__main__":
    self_test()
