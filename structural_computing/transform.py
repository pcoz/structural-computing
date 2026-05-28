r"""The reductions layer -- "beat your problem into matchgate-Holant shape."

The framework's classifier emits a tier label for the problem AS IT WAS HANDED
TO IT. Many out-of-family problems can be REDUCED to in-family ones via
specific transformations. This module exposes those transformations as
first-class objects so they can be composed, inspected, and applied
programmatically.

The mental model is the same as SQL's query optimiser. The user hands the
framework a problem; the classifier examines it; if it's already in-family
the answer is computed directly; if it's out-of-family but reducible, the
classifier emits a `ReductionPlan` saying "apply these transformations
in order and the result is in-family"; the runner applies the plan and
computes the in-family answer; the inverse transformation lifts the answer
back to a result for the original problem.

This v0.1 release ships:

  * The `Reduction` protocol that every concrete reduction conforms to.
  * The `ReductionPlan` dataclass for sequencing multiple reductions.
  * One concrete reduction: `NormaliseGraphFormat` -- coerces edge-list /
    adjacency-dict / rotation-system inputs into a canonical
    `(vertices, edges, rotation)` triple. This is what the wrapper's
    `_normalise_graph` did inline; lifting it into the reduction-layer
    API makes the pattern explicit.
  * Sketches of upcoming reductions (`CrossingElimination`,
    `HighDegreeVertexSplit`, `HybridDecomposition`, `RationaliseWeights`)
    raised as `NotImplementedError` with clear docstrings describing
    what they will do.

The full set of planned reductions lives in
admissibility-geometry/proposals/reductions_compositions_recursive_decomposition.md.
"""
import dataclasses
from typing import Any, Callable, List, Optional, Protocol, Tuple


# ---------------------------------------------------------------------------
# The base protocol -- what every reduction must provide
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class ReductionResult:
    """The output of applying a `Reduction` to a problem.

    Attributes:
        problem: the transformed problem (in-family if the reduction is
            successful, possibly still out-of-family if a single reduction
            was insufficient -- compose multiple reductions in a
            `ReductionPlan` to chain them).
        cost_overhead: the log2 of the multiplicative cost factor this
            reduction introduces. For example, a `HybridDecomposition`
            that pays `2^k` on a boundary of size `k` has
            `cost_overhead = k`.
        inverse: a callable that lifts a result computed on the transformed
            problem back to a result for the original problem. For most
            reductions this is the identity (the answer is preserved
            directly); some reductions multiply by a known factor.
        notes: free-form text suitable for tracing / debugging.
    """
    problem: Any
    cost_overhead: float
    inverse: Callable[[Any], Any] = lambda x: x
    notes: str = ""


class Reduction(Protocol):
    """Every concrete reduction conforms to this protocol.

    A reduction takes a problem (a graph, a constraint set, a signature)
    and returns a `ReductionResult` containing the transformed problem
    plus enough metadata to lift any answer back to the original
    problem. Reductions are PURE -- they do not mutate their input.

    The contract:

      1. If the reduction does NOT apply to this problem
         (`applies_to(problem) == False`), `apply()` may raise
         `ReductionNotApplicable`.

      2. If it applies, the transformed problem `result.problem` must
         be a strictly simpler / more-tractable form (lower tier, or
         a smaller / more structured instance of the same tier).

      3. The `inverse` callable must be its inverse: for any answer `a`
         computed on the transformed problem, `result.inverse(a)` must
         equal the answer that would have been computed on the original.
    """
    name: str

    def applies_to(self, problem: Any) -> bool:
        """True iff this reduction can be applied to `problem`."""
        ...

    def apply(self, problem: Any) -> ReductionResult:
        """Apply the reduction. Raises ReductionNotApplicable if not applicable."""
        ...


class ReductionNotApplicable(RuntimeError):
    """Raised by `Reduction.apply()` when the reduction doesn't apply to
    the given problem (e.g., trying to apply `CrossingElimination` to a
    problem that's already planar)."""


# ---------------------------------------------------------------------------
# ReductionPlan -- a sequence of reductions to apply in order
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class ReductionPlan:
    """A sequence of `Reduction` objects to apply in order. The plan is
    the bridge from "out-of-family problem" to "in-family problem the
    framework can evaluate directly":

        plan = ReductionPlan([
            NormaliseGraphFormat(),
            HighDegreeVertexSplit(),
            HybridDecomposition(),
        ])
        result = plan.apply(my_out_of_family_problem)
        # result.problem is now in-family;
        # result.inverse(in_family_answer) is the answer to the original.
    """
    reductions: List[Reduction] = dataclasses.field(default_factory=list)

    @property
    def total_cost_overhead(self) -> float:
        """Cumulative cost overhead. Reductions compose multiplicatively
        (additively in log2 space)."""
        # Cannot compute statically without running -- this is a placeholder
        # that returns 0; the actual value emerges from applying the plan.
        return 0.0

    def apply(self, problem: Any) -> ReductionResult:
        """Apply every reduction in order. Each step's output becomes the
        next step's input. The composed inverse lifts an answer all the
        way back to the original problem."""
        current = problem
        cumulative_overhead = 0.0
        inverses: List[Callable[[Any], Any]] = []
        notes: List[str] = []
        for reduction in self.reductions:
            if not reduction.applies_to(current):
                # Skip this step rather than erroring -- a plan can include
                # reductions that may or may not apply depending on the
                # intermediate state.
                continue
            step_result = reduction.apply(current)
            current = step_result.problem
            cumulative_overhead += step_result.cost_overhead
            # The inverses must be applied in REVERSE order to lift an
            # answer back to the original problem (the last reduction
            # applied is the first to be undone).
            inverses.append(step_result.inverse)
            if step_result.notes:
                notes.append(f"[{reduction.name}] {step_result.notes}")

        def composed_inverse(answer: Any) -> Any:
            for inv in reversed(inverses):
                answer = inv(answer)
            return answer

        return ReductionResult(
            problem=current,
            cost_overhead=cumulative_overhead,
            inverse=composed_inverse,
            notes=" | ".join(notes) if notes else "",
        )


# ---------------------------------------------------------------------------
# Concrete reduction: NormaliseGraphFormat
# ---------------------------------------------------------------------------

class NormaliseGraphFormat:
    """Coerce a graph input in any common format into a canonical
    `(vertices, edges, rotation)` triple. This is what the wrapper's
    `_normalise_graph` did inline; lifting it into the reductions-layer
    API makes the pattern explicit and reusable.

    Accepts:
      - Edge list: `[(u, v), ...]`
      - Adjacency dict: `{vertex: {neighbour, ...}, ...}`
      - Rotation system: `{vertex: [neighbour, ...], ...}` (with list values)

    Emits the canonical rotation-system form (the framework's preferred
    representation), suitable for `classify_graph` and the
    perfect-matching evaluators.

    Note that the synthesised rotation system for edge-list / adjacency-
    dict inputs is just the sorted neighbour order, which is NOT
    guaranteed to be a planar embedding even on planar graphs. If
    planarity matters, the caller should supply a real rotation system.
    """
    name = "NormaliseGraphFormat"

    def applies_to(self, problem: Any) -> bool:
        # Applies to any of the three accepted graph formats.
        if isinstance(problem, list) and problem and isinstance(problem[0], tuple):
            return True
        if isinstance(problem, dict) and problem:
            sample_value = next(iter(problem.values()))
            return isinstance(sample_value, (set, frozenset, list))
        return False

    def apply(self, problem: Any) -> ReductionResult:
        # Late import to avoid a circular dependency on .easy.
        from .easy import _normalise_graph
        if not self.applies_to(problem):
            raise ReductionNotApplicable(
                f"{self.name} expects an edge list, adjacency dict, or rotation system; "
                f"got {type(problem).__name__}"
            )
        vertices, edges, rotation = _normalise_graph(problem, rotation_required=True)
        return ReductionResult(
            problem={"vertices": vertices, "edges": edges, "rotation": rotation},
            cost_overhead=0.0,                           # pure format change
            inverse=lambda x: x,                          # answer is unchanged
            notes=f"normalised to (V={len(vertices)}, E={len(edges)}, rotation system)",
        )


# ---------------------------------------------------------------------------
# Sketches of upcoming reductions (declared with clear NotImplementedError)
# ---------------------------------------------------------------------------
#
# These are the next concrete deliverables for the reductions layer. Each
# raises NotImplementedError with a docstring describing what it will do,
# so the framework's user-facing surface already shows the planned API.
# When each is implemented, replacing the body is the only change required.

class CrossingElimination:
    r"""Replace each crossing in a near-planar graph layout with a small
    planar gadget that preserves the matching sum.

    For a graph that's planar except for a small number of crossings (real
    workflow / dependency graphs are often "mostly planar" with a few
    crossings that come from layout artefacts rather than fundamental
    non-planarity), this reduction makes the graph genuinely planar via a
    polynomial-size gadget per crossing -- vs `HybridDecomposition`'s
    exponential `2^k` for `k` crossings.

    The construction (Cai-Lu-Xia 2009, "Holographic algorithms with
    matchgates capture precisely tractable planar #CSP"): for each
    crossing of edges (a, b) and (c, d), substitute a 4-port planar
    gadget on 4 fresh internal vertices whose matching contribution at
    its 4 dangling edges equals the contribution of the original
    crossing. The gadget structure is the specific signature-preserving
    construction documented in the paper.

    v0.1 ships only the **trivial no-crossings case**: if you instantiate
    with `crossings=[]` (or None) and apply to a graph, the reduction is
    the identity (the graph is unchanged). This is correct for already-
    planar inputs and provides the API surface for callers; the
    substantive Cai-Lu-Xia gadget construction is the v0.2 deliverable.

    For graphs with actual crossings today, use `HybridDecomposition`
    with the crossing edges as the "extra-edge set" -- you pay the
    exponential `2^k` cost, but you get the exact matching count via
    the v0.1 framework with no missing primitive.
    """
    name = "CrossingElimination"

    def __init__(self, crossings: Optional[List[Tuple[Tuple, Tuple]]] = None):
        """`crossings` is a list of `(edge_a, edge_b)` pairs that cross
        in the layout. Each edge is a `(u, v)` tuple. v0.1 only supports
        the empty list (no crossings -> identity reduction); non-empty
        lists raise NotImplementedError pending the v0.2 Cai-Lu-Xia
        gadget."""
        self.crossings: List[Tuple[Tuple, Tuple]] = list(crossings or [])

    def applies_to(self, problem: Any) -> bool:
        """True iff `problem` looks like a graph dict (vertices + edges)."""
        return isinstance(problem, dict) and "vertices" in problem and "edges" in problem

    def apply(self, problem: Any) -> ReductionResult:
        if not self.applies_to(problem):
            raise ReductionNotApplicable(
                f"{self.name}: expects a graph dict with 'vertices' and 'edges'"
            )
        if not self.crossings:
            # The trivial case: no crossings declared, identity reduction.
            return ReductionResult(
                problem=problem,
                cost_overhead=0.0,
                inverse=lambda x: x,
                notes="no crossings declared; identity reduction",
            )
        raise NotImplementedError(
            f"{self.name} with non-empty crossings is on the v0.2 roadmap. "
            f"For exact matching count on a graph with crossings today, "
            f"use HybridDecomposition with the crossing edges as the "
            f"'extra-edge set'. See "
            f"admissibility-geometry/proposals/reductions_compositions_recursive_decomposition.md"
        )


class HighDegreeVertexSplit:
    """Replace each vertex of degree > 3 with a small planar gadget of
    degree-3 vertices that has the same effective matching signature.

    Many problems naturally produce vertices of high degree (a task
    constrained against many resources; a fork/join in a workflow with
    high fanout). Splitting them into trees of degree-3 vertices makes
    the framework's degree-3-friendly machinery (dart-chain at the
    classifier, the Pfaffian evaluator) directly applicable.

    Status: not implemented in v0.1. The split construction is
    well-known; the wiring is straightforward.
    """
    name = "HighDegreeVertexSplit"

    def applies_to(self, problem: Any) -> bool:
        return False

    def apply(self, problem: Any) -> ReductionResult:
        raise NotImplementedError(
            f"{self.name} is on the v0.2 roadmap. See "
            f"admissibility-geometry/proposals/reductions_compositions_recursive_decomposition.md"
        )


class HybridDecomposition:
    r"""Split a mostly-planar graph into its planar bulk and a small
    "extra-edge" set whose inclusion makes it non-planar. Decompose the
    matching-count question into a sum over **2^|extra|** sub-problems,
    each obtained by either DELETING or CONTRACTING each extra edge --
    and the residual of each sub-problem is planar, so its matching
    count is computable in poly time via FKT.

    The decomposition identity for perfect-matching count is the standard
    one (Tutte / Lovasz-Plummer): for any edge `e = (u, v)` in a graph G,

        M(G) = M(G - e) + M(G / uv)

    where:
      * `M(X)` is the number of perfect matchings of `X`,
      * `G - e` is `G` with edge `e` removed,
      * `G / uv` is `G` with `e` "contracted" -- both endpoints removed
        (and all their other incident edges removed), reflecting that
        `e` is forced INTO the matching, consuming both u and v.

    Recursively applying this identity to all of the extra edges
    produces a binary tree of depth `|extra|`; each leaf is the matching
    count of a planar graph, computable in poly time via FKT. Total
    cost: `2^|extra| * O(|V|^3)`.

    Construction:

        graph = {"vertices": [...], "edges": [...], "rotation": {...}}
        extra_edges = [(u1, v1), (u2, v2), ...]    # the small "non-planar" set

        h = HybridDecomposition(extra_edges)
        result = h.apply({"vertices": [...], "edges": [...], "rotation": {...}})
        # result.problem is a list of (planar sub-graph, sign) pairs;
        # the matching count is the sum of M(planar_part) over the list.
        # result.cost_overhead = len(extra_edges).

    The "inverse" function applied to the sum of sub-problem matching
    counts returns the matching count of the original graph (an exact
    integer, no error).

    Honest scope: this decomposition is for perfect-matching COUNT
    specifically (the unweighted, signature-`PERFECT_MATCHING-at-every-
    vertex` Holant problem). Generalising to other Holant signatures
    follows the same pattern but with signature-specific delete/contract
    rules; not implemented in v0.1.
    """
    name = "HybridDecomposition"

    def __init__(self, extra_edges: List[Tuple[Any, Any]]):
        """`extra_edges` is the set of "make-non-planar" edges. The
        remaining edges of the input graph must form a planar embedding
        (the caller is responsible for choosing the extra set; v0.2 will
        ship an auto-detection helper)."""
        # Store as a list of normalised (u, v) tuples (sorted endpoints
        # for hashability).
        self.extra_edges: List[Tuple[Any, Any]] = [
            tuple(sorted([u, v], key=str)) for (u, v) in extra_edges
        ]

    def applies_to(self, problem: Any) -> bool:
        """Applies if `problem` is a graph dict with vertices, edges, and
        every declared extra edge is in the graph."""
        if not isinstance(problem, dict):
            return False
        if "vertices" not in problem or "edges" not in problem:
            return False
        edge_set = {tuple(sorted([u, v], key=str)) for (u, v) in problem["edges"]}
        return all(e in edge_set for e in self.extra_edges)

    def apply(self, problem: Any) -> ReductionResult:
        if not self.applies_to(problem):
            raise ReductionNotApplicable(
                f"{self.name}: problem is not a graph dict with the expected "
                f"extra edges. Provide {{'vertices': ..., 'edges': ..., "
                f"'rotation': ...}} where every extra edge is in 'edges'."
            )
        # Build the list of (sub-graph, contribution-weight) pairs by
        # enumerating 2^|extra| subsets. Each subset describes which
        # extras are "forced in the matching" (contract them) and which
        # are "forbidden from the matching" (delete them).
        sub_problems: List[Tuple[Any, int]] = []
        vertices = list(problem["vertices"])
        edges = [tuple(sorted([u, v], key=str)) for (u, v) in problem["edges"]]
        extras = self.extra_edges
        non_extras = [e for e in edges if e not in extras]
        n_extras = len(extras)
        for mask in range(2 ** n_extras):
            # bit i of mask = 1 means extra i is FORCED IN the matching (contracted)
            forced_in = [extras[i] for i in range(n_extras) if (mask >> i) & 1]
            forced_out = [extras[i] for i in range(n_extras) if not (mask >> i) & 1]
            # Validate: forced-in edges must be vertex-disjoint (otherwise
            # they can't all be simultaneously in a matching).
            occupied = set()
            valid = True
            for (u, v) in forced_in:
                if u in occupied or v in occupied:
                    valid = False; break
                occupied.add(u); occupied.add(v)
            if not valid:
                continue
            # Build the residual:
            # - Remove every vertex occupied by a forced-in edge.
            # - Remove every edge incident to those vertices.
            # - Remove every forced-out extra edge.
            residual_vertices = [v for v in vertices if v not in occupied]
            forced_out_set = set(forced_out)
            residual_edges = []
            for (u, v) in non_extras + forced_in:
                # forced_in edges themselves are already "consumed" by their
                # endpoints being occupied, so they don't appear in the
                # residual (their endpoints are gone).
                if u in occupied or v in occupied:
                    continue
                if (u, v) in forced_out_set:
                    continue
                residual_edges.append((u, v))
            sub_problems.append(({"vertices": residual_vertices,
                                   "edges": residual_edges}, 1))

        # The matching count of the original is sum of (weight * M(residual))
        # over the sub-problems. The inverse function takes the list of
        # sub-problem matching counts and computes that sum.
        def inverse(sub_counts: List[int]) -> int:
            if len(sub_counts) != len(sub_problems):
                raise ValueError(
                    f"inverse: expected {len(sub_problems)} sub-counts, got {len(sub_counts)}"
                )
            return sum(w * c for (_, w), c in zip(sub_problems, sub_counts))

        return ReductionResult(
            problem={"sub_problems": [sp for (sp, _) in sub_problems],
                     "weights": [w for (_, w) in sub_problems]},
            cost_overhead=float(n_extras),   # log2 of the 2^|extras| factor
            inverse=inverse,
            notes=f"decomposed via {n_extras} extra edges into {len(sub_problems)} valid sub-problems",
        )


class RationaliseWeights:
    """Convert real-valued edge / vertex weights to rational form,
    then to GF(p) for an appropriate prime p, so the resulting
    constraint set is GF(p)-affine and the classifier emits T0 / T1.

    For risk / reliability problems with continuous failure probabilities,
    rationalising at a chosen precision lets the framework evaluate
    exactly while documenting the discretisation error. The alternative
    is the honest-stop on T7 ("real-valued, advised").

    Status: not implemented in v0.1.
    """
    name = "RationaliseWeights"

    def applies_to(self, problem: Any) -> bool:
        return False

    def apply(self, problem: Any) -> ReductionResult:
        raise NotImplementedError(
            f"{self.name} is on the v0.2 roadmap. See "
            f"admissibility-geometry/proposals/reductions_compositions_recursive_decomposition.md"
        )


__all__ = [
    "Reduction",
    "ReductionResult",
    "ReductionPlan",
    "ReductionNotApplicable",
    "NormaliseGraphFormat",
    "CrossingElimination",
    "HighDegreeVertexSplit",
    "HybridDecomposition",
    "RationaliseWeights",
]
