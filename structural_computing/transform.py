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
import copy
import dataclasses
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple


# ---------------------------------------------------------------------------
# Auto-detection helper for HybridDecomposition (v0.2)
# ---------------------------------------------------------------------------

def auto_detect_extras(rotation: Dict[Any, List[Any]],
                        *, max_extras: int = 6) -> List[Tuple[Any, Any]]:
    r"""Greedy heuristic: find a small set of edges whose removal makes
    the input graph planar (genus 0).

    For a graph G with genus g, we iteratively remove the edge whose
    removal reduces the genus the most. Stop when genus reaches 0 (the
    remaining graph is planar) or when no removal reduces genus
    (heuristic stuck) or when `max_extras` edges have been removed
    (to prevent the 2^|extras| blowup HybridDecomposition will pay).

    The returned list is the "extra-edge set" suitable for feeding
    to `HybridDecomposition` -- branching on these extras turns the
    non-planar input into a sum of planar sub-problems each evaluable
    via FKT in polynomial time.

    Cost: each genus computation is `O(|V| + |E|)`; the outer loop is
    `O(|extras|)` and each inner sweep over edges is `O(|E|)`, so the
    full heuristic runs in `O(|extras| * |E| * (|V| + |E|))`. For
    practical graphs with a few extras, this is milliseconds.

    Args:
      rotation: the input graph as a rotation-system dict.
      max_extras: hard cap on the number of extra edges to discover.
        The greedy stops here even if the graph is still non-planar.

    Returns:
      A list of edges (as `(u, v)` tuples) suitable for
      `HybridDecomposition(extra_edges=...)`. Empty list if the input
      is already planar OR if the heuristic gets stuck (see "Honest
      scope" below); partial list if the heuristic can't reach
      planarity within `max_extras`.

    Honest scope (v0.2 first cut). The greedy walks the genus surface
    by single-edge removals on the rotation system. For many graphs,
    removing one edge from a cellular embedding produces a NON-cellular
    embedding (a face becomes a non-disk). `holant_tools.genus_from_rotation_system`
    refuses to compute genus on non-cellular embeddings, which the
    heuristic treats as "no improvement available." This means
    auto-detection returns `[]` (the caller should fall back to manual
    `extra_edges` specification) for many simple non-planar graphs
    including the K_{3,3} and 4x4-toroidal canonical cases.

    A v0.3 fix is to RE-EMBED the residual graph after each edge
    removal (find a new cellular rotation), which requires a planarity-
    embedding routine the framework doesn't currently ship. Until then,
    auto-detection is a useful-when-it-works helper, not a general
    solver.

    Raises:
      ImportError: if `holant_tools` is not installed (the heuristic
        delegates to `holant_tools.genus_from_rotation_system`).
    """
    import holant_tools                    # delegated genus computation

    def _genus(rot: Dict[Any, List[Any]]) -> int:
        """Genus of a rotation system. Returns infinity if the rotation
        system isn't a valid cellular embedding (the genus formula
        requires connectedness; an isolated-vertex rotation may fail)."""
        try:
            return holant_tools.genus_from_rotation_system(rot).genus
        except Exception:
            return 10 ** 9                  # treat invalid as "very bad"

    def _enumerate_edges(rot: Dict[Any, List[Any]]) -> List[Tuple[Any, Any]]:
        """Edges (u, v) with u < v in str-order, no duplicates."""
        seen = set()
        edges = []
        for u, neighbours in rot.items():
            for v in neighbours:
                key = tuple(sorted([u, v], key=str))
                if key not in seen and u != v:
                    seen.add(key)
                    edges.append(key)
        return edges

    def _remove_edge_from_rotation(rot: Dict[Any, List[Any]],
                                     edge: Tuple[Any, Any]) -> Dict[Any, List[Any]]:
        """Return a new rotation system with `edge` removed from both
        endpoints' neighbour lists. The original is not mutated."""
        u, v = edge
        out = {k: list(neighbours) for k, neighbours in rot.items()}
        if v in out.get(u, []):
            out[u].remove(v)
        if u in out.get(v, []):
            out[v].remove(u)
        return out

    current_rotation = copy.deepcopy(rotation)
    extras: List[Tuple[Any, Any]] = []
    current_genus = _genus(current_rotation)

    while current_genus > 0 and len(extras) < max_extras:
        best_edge: Optional[Tuple[Any, Any]] = None
        best_genus = current_genus
        for edge in _enumerate_edges(current_rotation):
            test_rotation = _remove_edge_from_rotation(current_rotation, edge)
            test_genus = _genus(test_rotation)
            if test_genus < best_genus:
                best_genus = test_genus
                best_edge = edge
                if test_genus == 0:
                    break                    # found a planarising edge; stop early

        if best_edge is None:
            # Greedy is stuck: no single edge removal reduces genus.
            # This can happen on dense-non-planar graphs where multiple
            # simultaneous removals are needed. The caller gets a partial
            # extras list and can either accept it (HybridDecomposition
            # still gives an exact result if a planar residual emerges
            # in some branch) or fall back to brute force.
            break

        extras.append(best_edge)
        current_rotation = _remove_edge_from_rotation(current_rotation, best_edge)
        current_genus = best_genus

    return extras


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
        # Applies to any of the three accepted graph formats. Crucially,
        # does NOT match constraint-set dicts (key 'A') or signature dicts
        # (key 'values') or anything with a 'kind' field that's not 'graph'.
        if isinstance(problem, list) and problem and isinstance(problem[0], tuple):
            return True
        if isinstance(problem, dict) and problem:
            # Disambiguate dicts: skip if it's a non-graph typed dict.
            if any(k in problem for k in ("A", "values")):
                return False
            kind = problem.get("kind")
            if kind is not None and kind != "graph":
                return False
            # Skip if it's already a normalised graph dict (vertices + edges).
            if "vertices" in problem and "edges" in problem:
                return False
            # The remaining dicts are interpreted as rotation system or
            # adjacency dict; both have list / set values.
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

    def __init__(self, extra_edges: Optional[List[Tuple[Any, Any]]] = None,
                  *, auto: bool = False, max_auto_extras: int = 6):
        """Construct a HybridDecomposition with either an explicit extra-edge
        set or an auto-detected one.

        Args:
          extra_edges: the "make-non-planar" edge set the user identifies.
            Ignored when `auto=True`.
          auto: when True, the reduction's `apply()` calls `auto_detect_extras`
            on the input's rotation system to discover a planarising extra-
            edge set on the fly. Useful when the user doesn't know which
            edges make their graph non-planar.
          max_auto_extras: hard cap on the auto-discovered extras count
            (caps the `2^|extras|` HybridDecomposition cost).
        """
        if auto:
            # Auto-detected: extras will be filled in at apply() time.
            self.extra_edges: List[Tuple[Any, Any]] = []
            self._auto = True
            self._max_auto_extras = max_auto_extras
        else:
            self.extra_edges = [
                tuple(sorted([u, v], key=str)) for (u, v) in (extra_edges or [])
            ]
            self._auto = False
            self._max_auto_extras = max_auto_extras

    def applies_to(self, problem: Any) -> bool:
        """Applies if `problem` is a graph dict with vertices, edges, and
        every declared extra edge is in the graph. Auto-mode requires the
        rotation system too."""
        if not isinstance(problem, dict):
            return False
        if "vertices" not in problem or "edges" not in problem:
            return False
        if self._auto:
            return "rotation" in problem
        edge_set = {tuple(sorted([u, v], key=str)) for (u, v) in problem["edges"]}
        return all(e in edge_set for e in self.extra_edges)

    def apply(self, problem: Any) -> ReductionResult:
        if not self.applies_to(problem):
            raise ReductionNotApplicable(
                f"{self.name}: problem is not a graph dict with the expected "
                f"shape. Provide {{'vertices': ..., 'edges': ..., "
                f"'rotation': ...}} where every extra edge is in 'edges' "
                f"(or set auto=True and provide 'rotation')."
            )
        # Auto-mode: discover the extras from the rotation system now.
        if self._auto:
            self.extra_edges = auto_detect_extras(
                problem["rotation"], max_extras=self._max_auto_extras,
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
    r"""Convert real-valued edge weights into rationalised integer
    weights so the residual problem can be evaluated exactly in integer
    arithmetic (avoiding floating-point drift in the Pfaffian / matching-
    sum computation).

    The construction: pick a precision `p`; replace each edge weight `w`
    with the integer `round(w * 10^p)`. The weighted matching sum on
    the rationalised graph differs from the original by a known
    multiplicative factor:

        sum_M (prod_{e in M} round(w_e * 10^p))
            = 10^(p * matching_size) * sum_M (prod_{e in M} w_e) + O(discretisation_error)

    The inverse function divides by `10^(p * matching_size)` to recover
    an approximation to the original sum. The discretisation error is
    bounded by `O(10^{-p} * |E|)` times the largest matching contribution.

    For RISK and RELIABILITY problems with continuous failure probabilities,
    this lets the framework's exact integer machinery do the work while
    the user explicitly chooses the discretisation precision (and bounds
    the resulting error).

    v0.2 ships the construction for **perfect-matching weighted sum**
    on graphs with edge weights. Generalisation to vertex weights and
    other signature types is straightforward extension; not in this cut.

    Use:

        # Original graph with real-valued weights.
        graph = {
            "vertices": [...],
            "edges": [...],
            "weights": {(u, v): 0.7, (u, w): 0.3, ...},   # real-valued
        }
        reducer = RationaliseWeights(precision=6)        # 6 decimal places
        result = reducer.apply(graph)
        # result.problem now has integer weights = round(w * 10^6).
        # result.inverse(integer_sum) divides out the 10^(6 * matching_size)
        # factor and returns the approximate real-valued sum.
    """
    name = "RationaliseWeights"

    def __init__(self, precision: int = 6, matching_size: Optional[int] = None):
        """Construct with `precision` (number of decimal digits to keep)
        and `matching_size` (number of edges in each matching being summed
        -- for perfect matchings on `n` vertices this is `n // 2`).
        `matching_size` can be `None`; in that case the inverse function
        leaves the integer sum unscaled (the caller does the scaling)."""
        if precision < 0:
            raise ValueError(f"precision must be >= 0, got {precision}")
        self.precision = precision
        self.matching_size = matching_size

    def applies_to(self, problem: Any) -> bool:
        """True iff `problem` is a graph dict with a `weights` field
        mapping edges to floats."""
        if not isinstance(problem, dict):
            return False
        if "weights" not in problem:
            return False
        # Skip if every weight is already integer.
        weights = problem["weights"]
        if not isinstance(weights, dict) or not weights:
            return False
        return any(not isinstance(w, int) for w in weights.values())

    def apply(self, problem: Any) -> ReductionResult:
        if not self.applies_to(problem):
            raise ReductionNotApplicable(
                f"{self.name}: expects a graph dict with float weights in 'weights'"
            )
        scale = 10 ** self.precision
        new_weights = {edge: int(round(w * scale))
                        for edge, w in problem["weights"].items()}
        new_problem = {**problem, "weights": new_weights}
        # Build the inverse function: divide the integer sum by 10^(precision * matching_size).
        if self.matching_size is None:
            divisor = 1.0
        else:
            divisor = float(scale ** self.matching_size)

        def inverse(int_sum: float) -> float:
            return int_sum / divisor

        return ReductionResult(
            problem=new_problem,
            cost_overhead=0.0,
            inverse=inverse,
            notes=(f"weights scaled by 10^{self.precision}; "
                   f"discretisation error bounded by O(10^{-self.precision} * |E|)"),
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
    "auto_detect_extras",
]
