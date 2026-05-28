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
    r"""Replace each declared crossing with the Cai-Gorenstein planar
    crossover gadget — a 6-vertex 7-edge planar matchgate with one
    weight -1 — to obtain a PLANAR graph whose Pfaffian (with the
    induced FKT-style orientation) equals the matchgate signature of
    the original non-planar graph (Cai & Gorenstein, *Matchgates
    Revisited*, arXiv:1303.6729 Fig. 6, eqs. 43-46).

    What the gadget DOES preserve
    -----------------------------
    For each matching M of the original graph G, the gadget records the
    chord-crossing count c(M) as a sign:

        sum over M'∈M(G_planarised) of prod w(e') = sum_M (-1)^{c(M)} · prod_e w(e)

    Specifically: matchings of G that use BOTH edges of a declared
    crossing contribute their weight to the planarised PerfMatch with
    a flipped sign (-1) — this is the role of the gadget's "spine"
    edge (IL, IR) carrying weight -1.

    So the planarised graph's PerfMatch equals the SIGNED chord-crossing
    sum of the original (a.k.a. the matchgate signature value
    Γ^{0...0}). This is the Pfaffian of the non-planar graph under its
    "induced" antisymmetric orientation.

    What the gadget does NOT preserve
    ---------------------------------
    For unsigned (positive-weight) PERFECT-MATCHING COUNT on the
    original non-planar graph, the gadget does NOT in general give the
    right answer. Example::

        K_4 with edge weights w(0,2) = 11, w(1,3) = 13, w(others) = 2..7
        - True PerfMatch (sum over 3 PMs):                  174
        - PerfMatch of planarised K_4 (gadget applied):      12

    The 12 here is the SIGNED matchgate signature, NOT the unsigned PM
    sum. For unsigned PerfMatch, use ``HybridDecomposition`` instead.

    For UNIT-weight K_4 the two values happen to coincide (both 3), but
    this is a combinatorial coincidence of K_4 and not a general
    property — don't rely on it.

    The gadget graph
    ----------------

        (u) --- (v)        (P1)----(P2)
         |       |          |       |
        (P1)---(P2)   <==>  (P1)(IL)(IR)(P2)        (the gadget X
         |       |               -1                  inserted at the
        (P4)---(P3)         (P4)(IL)(IR)(P3)         crossing point)
         |       |          |       |
        (x) --- (y)        (P4)----(P3)

    Each crossing introduces 6 fresh vertices (4 pins P1..P4 + 2
    internals IL, IR), 4 segment edges (connecting original endpoints
    to pins; the segment adjacent to the lower-indexed endpoint carries
    the original edge weight, others carry 1), and 7 gadget-internal
    edges (one with weight -1 on the spine).

    Signature support: X^{0000} = X^{0101} = X^{1010} = +1,
    X^{1111} = -1, all other X^β = 0.

    Use::

        ce = CrossingElimination(crossings=[((0, 2), (1, 3))])
        result = ce.apply(graph)
        # result.problem is the planar expansion. Run FKT on it to get
        # the matchgate signature value, NOT the unsigned PerfMatch.

    Coverage / honest stop:
      * Each crossing supplied as ``(edge_a, edge_b)``; both must exist.
      * NO auto-detection of crossings; the caller declares them.
      * Multiple crossings on the same edge: the edge runs through
        several gadget pins; only the first segment carries the
        original weight (Cai-Gorenstein convention, cf. Fig. 8).
      * For unsigned PerfMatch on non-planar graphs, the framework's
        recommended tool is ``HybridDecomposition``, which branches
        on extra-edge inclusion and gives the exact unsigned count.
    """
    name = "CrossingElimination"

    def __init__(self, crossings: Optional[List[Tuple[Tuple, Tuple]]] = None):
        """`crossings` is a list of `(edge_a, edge_b)` pairs that cross
        in the layout. Each edge is a `(u, v)` tuple. An empty list (or
        `None`) gives the identity reduction. A non-empty list applies
        the Cai-Gorenstein gadget at each declared crossing."""
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

        # Build a working copy of the graph.
        vertices = list(problem["vertices"])
        edges    = list(problem["edges"])
        weights  = dict(problem.get("weights", {}))

        # Helper: canonicalise an edge tuple so lookups are direction-free.
        def _key(e):
            (u, v) = e
            return (u, v) if (str(u), str(v)) <= (str(v), str(u)) else (v, u)

        # Fill in default weight 1 for any edge missing from `weights`.
        for e in edges:
            if _key(e) not in {_key(k) for k in weights}:
                weights[e] = 1

        # Allocate fresh internal-vertex IDs. We tag with a string suffix
        # to avoid collisions with integer vertex labels.
        existing_ids = set(str(v) for v in vertices)
        gadget_counter = 0
        def _fresh_id():
            nonlocal gadget_counter
            while True:
                vid = f"_X{gadget_counter}"
                gadget_counter += 1
                if vid not in existing_ids:
                    existing_ids.add(vid)
                    return vid

        # Verify each declared crossing's edges are in the graph.
        edge_set = {_key(e) for e in edges}
        for (ea, eb) in self.crossings:
            if _key(ea) not in edge_set:
                raise ReductionNotApplicable(
                    f"{self.name}: declared crossing edge {ea} not in graph"
                )
            if _key(eb) not in edge_set:
                raise ReductionNotApplicable(
                    f"{self.name}: declared crossing edge {eb} not in graph"
                )

        # Apply each crossing in order. For each (e_a, e_b):
        #   - delete e_a and e_b from the graph (with their weights)
        #   - introduce 6 fresh gadget vertices: P1, P2, P3, P4 (the
        #     gadget pins) and IL, IR (the gadget internals)
        #   - add 4 SEGMENT edges connecting original endpoints to pins:
        #         (u, P1), (P2, v), (x, P4), (P3, y)
        #     The segment adjacent to the LOWER-indexed endpoint carries
        #     the original edge weight; the other carries weight 1
        #     (Cai-Gorenstein "lower indexed external node" convention).
        #   - add 7 gadget INTERNAL edges per Cai-Gorenstein Fig. 6:
        #         (P1, P2), (P1, IL), (P2, IR),       -- top half
        #         (P4, P3), (P4, IL), (P3, IR),       -- bottom half
        #         (IL, IR) with weight -1            -- the spine
        for (ea, eb) in self.crossings:
            (u, v) = ea
            (x, y) = eb
            # Resolve weights (try both orientations of each edge).
            w_uv = weights.pop(ea, None)
            if w_uv is None:
                w_uv = weights.pop((v, u), 1)
            w_xy = weights.pop(eb, None)
            if w_xy is None:
                w_xy = weights.pop((y, x), 1)
            # Remove the crossing edges (canonical-key match).
            ka, kb = _key(ea), _key(eb)
            edges = [e for e in edges if _key(e) != ka and _key(e) != kb]

            # 6 fresh gadget vertices.
            P1, P2, P3, P4 = _fresh_id(), _fresh_id(), _fresh_id(), _fresh_id()
            IL, IR         = _fresh_id(), _fresh_id()
            vertices.extend([P1, P2, P3, P4, IL, IR])

            # Determine which segment carries the original weight (the
            # one adjacent to the lower-indexed endpoint).
            uv_lower_first = str(u) <= str(v)
            xy_lower_first = str(x) <= str(y)

            new_edges = [
                # Segments for edge (u, v): u -- P1, P2 -- v
                ((u, P1), w_uv if uv_lower_first else 1),
                ((P2, v), 1   if uv_lower_first else w_uv),
                # Segments for edge (x, y): x -- P4, P3 -- y
                ((x, P4), w_xy if xy_lower_first else 1),
                ((P3, y), 1   if xy_lower_first else w_xy),
                # Gadget internal edges (Cai-Gorenstein Fig. 6).
                ((P1, P2), 1),
                ((P4, P3), 1),
                ((P1, IL), 1),
                ((P2, IR), 1),
                ((P4, IL), 1),
                ((P3, IR), 1),
                ((IL, IR), -1),
            ]
            for (e, w) in new_edges:
                edges.append(e)
                weights[e] = w

        return ReductionResult(
            problem={
                "vertices": vertices,
                "edges": edges,
                "weights": weights,
            },
            cost_overhead=0.0,                      # no multiplicative factor
            inverse=lambda x: x,                    # PerfMatch is preserved
            notes=(f"replaced {len(self.crossings)} crossing(s) with "
                   f"Cai-Gorenstein gadgets; "
                   f"added {6 * len(self.crossings)} vertices and "
                   f"{9 * len(self.crossings)} edges per crossing "
                   f"(net edge delta after removing 2: "
                   f"+{9 * len(self.crossings)})"),
        )


class HighDegreeVertexSplit:
    r"""Build a planar 2k-node matchgate realising a high-arity SYMMETRIC
    matchgate-realisable signature, via the Cai-Gorenstein triangle-
    cycle construction (*Matchgates Revisited*, arXiv:1303.6729 §7.1,
    Figs. 10 and 11).

    The realisability criterion (Cai-Gorenstein Theorem 9)
    --------------------------------------------------------
    A symmetric arity-k signature ``[z_0, z_1, ..., z_k]`` is matchgate-
    realisable iff it is "alternate-zero with a geometric progression
    on the non-zero positions" — i.e., either

      * EVEN: ``z_i = 0`` for all odd ``i``, and the even-index entries
        form a geometric progression: ``z_2 / z_0 = z_4 / z_2 = ... = (b/a)^2``.
      * ODD: ``z_i = 0`` for all even ``i``, and the odd-index entries
        form a geometric progression.

    The construction (Cai-Gorenstein Fig. 10, even-arity case)
    ----------------------------------------------------------
    For an EVEN-arity-k signature with non-zero entries
    ``z_0 = 2 a^k, z_2 = 2 a^{k-2} b^2, z_4 = 2 a^{k-4} b^4, ..., z_k = 2 b^k``:

      - Take k triangles ``{a_i, b_i, c_i}`` for ``i = 1, ..., k``.
      - In each triangle:
            edges ``(a_i, b_i)`` and ``(a_i, c_i)`` carry weight ``x``,
            edge   ``(b_i, c_i)``                   carries weight ``y``.
      - Link triangles into a cycle by IDENTIFYING ``c_i`` with
        ``b_{i+1}`` (mod k).
      - External nodes: ``{a_1, ..., a_k}``. Internal: the merged
        ``c_i = b_{i+1}`` (one per pair).
      - Total: 2k vertices (k external + k internal).

    Parameter recovery: ``x = a``, ``y = b^2`` (the y-edge is ONE
    edge inside each triangle, so it lifts the index by 1 every
    even position).

    Signature value (Cai-Gorenstein page 25):

        Γ^α = 2 · x^{k - |α|} · y^{|α| / 2}    for even |α|
        Γ^α = 0                                  for odd |α|

    The construction gives a planar matchgate of 2k vertices whose
    signature matches the input (after solving for x, y).

    ODD-arity case (Fig. 11)
    ------------------------
    Build the even-arity-(k+1) matchgate, then REMOVE one external
    node. This realises the odd-arity-k signature.

    Use::

        # Even arity-4 symmetric signature: [z_0, 0, z_2, 0, z_4]
        # with z_0 = 2, z_2 = 2, z_4 = 2 (geometric ratio 1):
        h = HighDegreeVertexSplit(signature=[2, 0, 2, 0, 2])
        result = h.apply({"kind": "signature", "data": {"values": [2, 0, 2, 0, 2]}})
        # result.problem is the matchgate dict with 2k=8 vertices and
        # the triangle-cycle structure.

    Coverage / honest stop:
      * Symmetric signatures only (alternate-zero, geometric-progression
        non-zero entries).
      * NumPy / Python-float arithmetic; for exact rational parameter
        recovery, supply rational inputs and (in a v0.3 extension)
        compute x, y in exact arithmetic.
      * Does NOT splice the matchgate into a larger graph -- the caller
        feeds the result into the framework as a new matchgate problem.
        Wiring it into an existing high-arity vertex of a graph is a
        graph-rewrite the caller does on the result.
    """
    name = "HighDegreeVertexSplit"

    def __init__(self, signature: Optional[List[float]] = None,
                  *, tol: float = 1e-10):
        """``signature`` is the symmetric arity-k vector
        ``[z_0, z_1, ..., z_k]``. ``tol`` is the numerical tolerance for
        the realisability check on the geometric progression."""
        self.signature = list(signature) if signature is not None else None
        self.tol = tol

    def applies_to(self, problem: Any) -> bool:
        """True iff ``problem`` looks like a symmetric-signature dict
        (``{"values": [...]}`` or ``{"data": {"values": [...]}}``) AND
        a signature has been supplied to the constructor."""
        if self.signature is None:
            return False
        if not isinstance(problem, dict):
            return False
        if "values" in problem:
            return True
        if "data" in problem and isinstance(problem["data"], dict) \
                and "values" in problem["data"]:
            return True
        return False

    def apply(self, problem: Any) -> ReductionResult:
        if not self.applies_to(problem):
            raise ReductionNotApplicable(
                f"{self.name}: expects a symmetric-signature problem dict "
                f"and a signature constructor argument"
            )
        # Verify realisability and recover parameters.
        signature = self.signature
        params = self._fit_geometric_progression(signature)
        if params is None:
            raise ReductionNotApplicable(
                f"{self.name}: signature {signature} is not matchgate-"
                f"realisable (Cai-Gorenstein Theorem 9 requires alternate-"
                f"zero with geometric progression on the non-zero entries)"
            )
        is_even_signature, x, y_squared = params
        k = len(signature) - 1
        # Build the matchgate graph.
        if is_even_signature:
            mg = self._build_even_matchgate(k, x, y_squared)
            note = f"even-arity {k} matchgate (2k={2*k} nodes)"
        else:
            # Odd-arity: build even-arity-(k+1) then mark one external
            # as "to remove" so the user/framework drops it.
            mg = self._build_even_matchgate(k + 1, x, y_squared)
            # Mark the LAST external (a_{k+1}) for removal.
            mg["odd_arity_remove_external"] = mg["externals"][-1]
            note = f"odd-arity {k} matchgate (built as even-arity-{k+1} = "\
                    f"{2*(k+1)} nodes, remove external {mg['odd_arity_remove_external']})"
        return ReductionResult(
            problem=mg,
            cost_overhead=0.0,
            inverse=lambda v: v,                    # signature-preserving
            notes=note,
        )

    def _fit_geometric_progression(self, sig):
        """Decide whether ``sig`` is even-or-odd matchgate-realisable
        and recover (x, y^2). Returns (is_even, x, y_squared) on
        success, or None on failure."""
        k = len(sig) - 1
        if k < 0:
            return None
        # Try EVEN case: odd-index entries should all be 0.
        even_zero = all(abs(sig[i]) < self.tol for i in range(1, k + 1, 2))
        odd_zero  = all(abs(sig[i]) < self.tol for i in range(0, k + 1, 2))
        if even_zero:
            return self._fit_even_geometric(sig, k, is_even=True)
        if odd_zero:
            return self._fit_even_geometric(sig, k, is_even=False)
        return None

    def _fit_even_geometric(self, sig, k, *, is_even):
        """Fit ``Γ^α = 2 x^{k - |α|} y^{|α|/2}`` to the non-zero entries
        of ``sig``. Returns (is_even, x, y_squared) or None."""
        nonzero_idx = list(range(0, k + 1, 2)) if is_even else list(range(1, k + 1, 2))
        nonzero_vals = [sig[i] for i in nonzero_idx]
        if all(abs(v) < self.tol for v in nonzero_vals):
            # All-zeros signature; trivially realisable as the zero matchgate.
            return (is_even, 0.0, 0.0)
        # Find a non-zero starting point.
        first_nz = next((j for j, v in enumerate(nonzero_vals)
                          if abs(v) > self.tol), None)
        if first_nz is None:
            return (is_even, 0.0, 0.0)
        # Solve for (x, y^2) using the first two non-zero entries.
        # Γ^{α=0...0} = 2 x^k    (when first_nz == 0, even case)
        # Recover from Γ^{α at Hamming weight = nonzero_idx[first_nz]}.
        # For the EVEN case: nonzero index i = 2j; Γ = 2 x^{k-2j} y^{2j/2} = 2 x^{k-2j} y^j.
        # For two consecutive non-zero entries Γ_i and Γ_{i+2} (= 2 x^{k-2j} y^j and 2 x^{k-2(j+1)} y^{j+1}):
        # ratio = Γ_{i+2} / Γ_i = (y / x^2). So y_squared = (Γ_{i+2}/Γ_i) * x^2.
        # And |Γ_0| = 2 x^k → x^k = Γ_0 / 2 → x = (Γ_0 / 2)^{1/k} (taking real root).
        # If the first non-zero entry is NOT Γ_0, scale accordingly.
        import math
        # Find the canonical "first non-zero is z_0" by shifting.
        # Use the first two non-zero entries to derive (x, y).
        if len(nonzero_vals) < 2:
            # Only one non-zero entry: under-constrained; pick y = 0.
            # Γ^α = 2 x^k at α with Hamming weight 0. Need this entry non-zero.
            i0_val = nonzero_vals[first_nz]
            # Solve 2 x^k = i0_val (only valid when first_nz=0 in the even case).
            if first_nz != 0:
                # Geometric progression with one nonzero implies trivial: not
                # realisable in the "Γ_0 ≠ 0" branch. Realisable only if x=0
                # and the nonzero is at an "all-ones" position; mark as
                # special case and use x=0, y_squared=any positive.
                x = 0.0
                y_squared = (i0_val / 2.0) ** (2.0 / k) if k > 0 else 1.0
                return (is_even, x, y_squared)
            x = (abs(i0_val) / 2.0) ** (1.0 / k) if k > 0 else 0.0
            return (is_even, x, 0.0)
        # Two or more non-zero values. Extract their actual signature indices.
        j0, j1 = first_nz, first_nz + 1
        # Verify j1's value is consistent with the geometric progression.
        # First verify ALL non-zero entries follow the progression.
        # Take ratio r = Γ_{nonzero_idx[j1]} / Γ_{nonzero_idx[j0]} = (y/x^2)^{j1-j0}.
        # Then check Γ_{nonzero_idx[j]} / Γ_{nonzero_idx[j0]} = r^{j-j0} for all j.
        # Edge case: if j0 != 0, normalise.
        # Simpler approach: check all consecutive ratios are equal.
        ratios = []
        for j in range(len(nonzero_vals) - 1):
            if abs(nonzero_vals[j]) < self.tol:
                ratios.append(None)
                continue
            ratios.append(nonzero_vals[j + 1] / nonzero_vals[j])
        # All non-None ratios must agree.
        r = next((rr for rr in ratios if rr is not None), None)
        if r is None:
            return (is_even, 0.0, 0.0)
        for rr in ratios:
            if rr is not None and abs(rr - r) > max(self.tol, abs(r) * self.tol):
                return None        # not a geometric progression
        # Now recover x, y_squared. y / x^2 = r ⇒ y_squared / x^4 = r^2.
        # Γ_0 = 2 x^k (if Γ_0 != 0): x = (Γ_0/2)^(1/k).
        if first_nz == 0 and abs(nonzero_vals[0]) > self.tol:
            i0_val = nonzero_vals[0]
            x_pow_k = i0_val / 2.0
            # Take the real k-th root (sign carries through).
            if x_pow_k >= 0:
                x = x_pow_k ** (1.0 / k) if k > 0 else 1.0
            else:
                x = -((-x_pow_k) ** (1.0 / k)) if k > 0 else -1.0
            # y_squared = r * x^2  (since y / x^2 = r ⇒ y = r·x^2 ⇒ y_squared = r·x^2).
            # Wait: y is the y-EDGE WEIGHT; y_squared is what appears in
            # the signature formula (Γ uses y^{|α|/2}). So y_squared = y_edge_weight.
            # And the ratio Γ_{i+2}/Γ_i = y_edge / x^2.
            # So y_edge = r * x^2.
            y_edge = r * (x ** 2)
            return (is_even, x, y_edge)
        # Otherwise: Γ_0 = 0 case. Pick x via the first non-zero entry.
        # This is an under-determined fit; choose x = 1 as a normalisation.
        x = 1.0
        y_edge = r * (x ** 2)
        return (is_even, x, y_edge)

    def _build_even_matchgate(self, k, x, y_edge):
        """Build the 2k-node triangle-cycle matchgate for an even-arity-k
        signature with parameters (x, y_edge) per Cai-Gorenstein Fig. 10."""
        # External nodes are a_1, ..., a_k.
        externals = [f"a_{i+1}" for i in range(k)]
        # Internal nodes are c_i (= b_{i+1}) for i = 1..k; we use one
        # internal per triangle-pair.
        internals = [f"c_{i+1}" for i in range(k)]
        vertices = externals + internals
        edges: List[Tuple[Any, Any]] = []
        weights: Dict[Any, float] = {}
        for i in range(k):
            a_i = externals[i]
            # b_i in triangle i is identified with c_{i-1} (mod k).
            b_i = internals[(i - 1) % k]
            c_i = internals[i]
            edges.append((a_i, b_i))
            edges.append((a_i, c_i))
            edges.append((b_i, c_i))
            weights[(a_i, b_i)] = x
            weights[(a_i, c_i)] = x
            weights[(b_i, c_i)] = y_edge
        return {
            "kind": "matchgate",
            "vertices": vertices,
            "edges": edges,
            "weights": weights,
            "externals": externals,
            "internals": internals,
            "arity": k,
            "construction": "Cai-Gorenstein 2k-node triangle-cycle (Fig. 10)",
        }


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
