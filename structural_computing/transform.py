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
    """Replace each crossing in a near-planar graph layout with a small
    planar gadget that preserves the matching sum.

    For a graph that's planar EXCEPT for a small number of crossings (real
    workflow / dependency graphs are often "mostly planar" with a few
    crossings that come from layout artefacts rather than fundamental
    non-planarity), this reduction makes the graph genuinely planar at
    the cost of a few extra vertices per crossing.

    Status: not implemented in v0.1. Standard technique from the
    holographic-algorithm tradition (Cai-Lu-Xia, Valiant 2004). The
    gadget construction is well-defined; implementation is a matter
    of plumbing.
    """
    name = "CrossingElimination"

    def applies_to(self, problem: Any) -> bool:
        # Will be: True iff `problem` is a near-planar graph with bounded crossings.
        return False

    def apply(self, problem: Any) -> ReductionResult:
        raise NotImplementedError(
            f"{self.name} is on the v0.2 roadmap. See "
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
    """Split a mostly-planar graph into its planar bulk and a small
    non-planar boundary. Compute the planar part exactly via FKT; pay
    exponential cost only on the small boundary; combine.

    For a graph G with |E_extra| << |E| extra (non-planar-causing) edges,
    this gives an answer in time `2^|E_extra| · poly(|E|)`. The
    hybrid-dispatcher already does this for circuits; generalising it
    to general Holant graphs is the natural next step.

    Status: not implemented in v0.1. The decomposition logic exists in
    `hybrid-dispatcher/hybrid_dispatcher.py` for the circuit case; lifting
    it to a general framework primitive is the v0.2 deliverable.
    """
    name = "HybridDecomposition"

    def applies_to(self, problem: Any) -> bool:
        return False

    def apply(self, problem: Any) -> ReductionResult:
        raise NotImplementedError(
            f"{self.name} is on the v0.2 roadmap. See "
            f"admissibility-geometry/proposals/reductions_compositions_recursive_decomposition.md"
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
