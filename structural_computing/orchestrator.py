r"""The Orchestrator -- the top-level "given a problem, give me an
exact answer" engine.

This is the layer that ties together everything below:

    Orchestrator
        |
        +-- Classifier (classify_constraint_set / _graph / _signature)
        |
        +-- Router (route)
        |
        +-- Leaf evaluators (per-tier exact runners)
        |
        +-- Reduction layer (transform.py)
        +-- Composition layer (compose.py)
        +-- Decomposition layer (decompose.py)

The Orchestrator's job:

  1. Classify the problem.
  2. If in-family AND we have a registered leaf evaluator for the
     emitted (tier, question) pair, dispatch to it and return the
     answer directly.
  3. Else, search the registered reductions / compositions /
     decompositions for one that applies and brings the problem to a
     state where (2) succeeds. Apply it; recurse on the sub-problems;
     combine via the operation's inverse / combine rule.
  4. If no operation reduces the problem to in-family, raise
     `NoKnownReduction` -- the framework's honest-stop verdict.

The design is **registry-driven**: leaf evaluators, reductions,
compositions, decompositions are all stored in pluggable registries.
The default registry is wired up to the v0.1 in-family runners and the
v0.1 concrete reductions; users can register their own.

This v0.1 release ships the API surface plus a minimal default
registry. The full search logic (cost-driven, with backtracking on
failed reductions) is a v0.2 deliverable -- v0.1 tries each registered
reduction once and returns the first successful in-family transformation.
"""
import dataclasses
from typing import Any, Callable, Dict, List, Optional, Tuple

from .classify import Classification, classify_graph
from .route import route as route_classification
from .transform import (
    Reduction,
    ReductionPlan,
    ReductionNotApplicable,
    HybridDecomposition,
    NormaliseGraphFormat,
)
from .compose import Composition, CompositionPlan, LinearCombination
from .decompose import Decomposition, DecompositionPlan, ShannonExpansion
from .verifier import brute_force_count_matchings


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

class NoKnownReduction(RuntimeError):
    """Raised by `Orchestrator.evaluate` when the problem is out-of-family
    AND no registered reduction / composition / decomposition is known
    to bring it in-family for the requested question.

    The `classification` attribute records the framework's verdict at
    the point of giving up; the user can inspect it to understand which
    tier the problem landed in and what was tried."""
    def __init__(self, classification: Classification, attempted: List[str]):
        super().__init__(
            f"no known reduction for {classification.tier}; "
            f"attempted: {', '.join(attempted) if attempted else '(none registered)'}"
        )
        self.classification = classification
        self.attempted = attempted


@dataclasses.dataclass
class OrchestratorResult:
    """The Orchestrator's full answer including provenance.

    Attributes:
      answer: the computed value (the user-facing result).
      classification: the framework's classification of the problem.
      reductions_applied: list of reduction names applied to bring the
        problem in-family. Empty if the problem was in-family directly.
      sub_evaluations: count of how many leaf evaluations were performed.
      leaf_evaluator_used: name of the leaf evaluator used.
    """
    answer: Any
    classification: Classification
    reductions_applied: List[str]
    sub_evaluations: int
    leaf_evaluator_used: str


# ---------------------------------------------------------------------------
# Leaf evaluator registry
# ---------------------------------------------------------------------------
#
# A leaf evaluator is a function `(problem, question) -> answer` that
# handles a specific (tier, question) combination at the in-family level.
# The registry maps (tier, question) -> callable.
#
# v0.1 default registry covers:
#   (T2, "matching_count")  -- planar matching count via brute force at small n
#   (T4, "matching_count")  -- bounded-genus matching count via brute force
#
# v0.2 deliverable: register the full set of (tier, question) combinations
# including the planar / genus-g Pfaffian leaf evaluators for asymptotic
# poly-time on the in-family path.

LeafEvaluator = Callable[[Any, str], Any]


def _brute_force_matching_leaf(problem: Any, question: str) -> int:
    """Default leaf evaluator for the matching_count question on graphs.
    Uses brute force; v0.2 will substitute the planar Pfaffian here."""
    if question != "matching_count":
        raise ValueError(f"_brute_force_matching_leaf can't answer '{question}'")
    if isinstance(problem, dict) and "vertices" in problem:
        return brute_force_count_matchings(problem["vertices"], problem["edges"])
    # Edge-list or rotation-system inputs need normalisation first; the
    # caller is expected to have normalised.
    raise ValueError(f"matching leaf expects a graph dict; got {type(problem).__name__}")


DEFAULT_LEAF_REGISTRY: Dict[Tuple[str, str], LeafEvaluator] = {
    ("T2", "matching_count"): _brute_force_matching_leaf,
    ("T4", "matching_count"): _brute_force_matching_leaf,
}


# ---------------------------------------------------------------------------
# The Orchestrator
# ---------------------------------------------------------------------------

class Orchestrator:
    """The top-level evaluator. Wires together classifier, router,
    leaf-evaluators, and the reductions / compositions / decompositions
    layer into a single `evaluate(problem, question)` interface.

    Usage::

        orch = Orchestrator()
        # In-family graph -- direct dispatch:
        answer = orch.evaluate(my_planar_graph, question="matching_count")
        # K_{3,3} is non-planar but HybridDecomposition applies:
        answer = orch.evaluate(K_3_3_graph, question="matching_count",
                                hints={"extra_edges": [(0, 3)]})

    The orchestrator's search is currently linear: try each registered
    reduction once; first successful in-family transformation wins. v0.2
    will add backtracking and cost-driven search.
    """

    def __init__(self,
                  leaf_registry: Optional[Dict[Tuple[str, str], LeafEvaluator]] = None,
                  reductions: Optional[List[Reduction]] = None):
        """Construct an Orchestrator. Pass `leaf_registry` to override
        the per-(tier, question) leaf evaluators; pass `reductions` to
        override the list of available reductions."""
        self.leaf_registry: Dict[Tuple[str, str], LeafEvaluator] = (
            dict(leaf_registry) if leaf_registry is not None
            else dict(DEFAULT_LEAF_REGISTRY)
        )
        self.reductions: List[Reduction] = (
            list(reductions) if reductions is not None
            else [NormaliseGraphFormat()]
            # HybridDecomposition is parametric (needs extra_edges) so it's
            # not in the default reduction list; the user passes it via
            # `hints` to evaluate().
        )

    def register_leaf_evaluator(self, tier: str, question: str,
                                  evaluator: LeafEvaluator) -> None:
        """Add or replace a leaf evaluator for a (tier, question) pair."""
        self.leaf_registry[(tier, question)] = evaluator

    def register_reduction(self, reduction: Reduction) -> None:
        """Add a reduction to the orchestrator's search list."""
        self.reductions.append(reduction)

    def evaluate(self,
                  problem: Any,
                  question: str,
                  *,
                  hints: Optional[Dict[str, Any]] = None) -> OrchestratorResult:
        """Compute the answer to `question` on `problem`.

        Algorithm:
          1. Normalise the problem if it's a graph in a non-canonical
             format (edge list / adjacency dict -> rotation system).
          2. Classify it.
          3. If (tier, question) is in the leaf registry, dispatch to
             the leaf evaluator and return.
          4. Else, try each registered reduction. The first one that
             applies and produces in-family sub-problems wins; we
             recurse on each sub-problem and combine via the
             reduction's inverse.
          5. If hints are provided (e.g. `extra_edges` for
             HybridDecomposition), try the indicated reduction first.
          6. If no reduction works, raise NoKnownReduction.

        Args:
          problem: the input problem (graph, constraint set, signature).
          question: the question to answer ("matching_count" is the
            main v0.1 question).
          hints: optional parameters for parametric reductions. For
            graph matching with non-planar boundary, pass
            `{"extra_edges": [...]}` to apply HybridDecomposition.

        Returns:
          OrchestratorResult with the answer plus provenance.
        """
        hints = hints or {}

        # 1. Normalise graph inputs.
        normaliser = NormaliseGraphFormat()
        normalised_notes: List[str] = []
        if normaliser.applies_to(problem):
            normalisation = normaliser.apply(problem)
            problem = normalisation.problem
            normalised_notes.append(normaliser.name)

        # 2. Classify (graph case for now; constraint-set / signature
        # would dispatch to other classifiers in v0.2).
        if isinstance(problem, dict) and "rotation" in problem:
            cls = classify_graph(problem["rotation"])
        else:
            # Constraint-set / signature: outside v0.1's orchestrator
            # focus; the StructuralComputer wrapper handles these
            # directly. Future versions of the orchestrator will route
            # those through the classifier dispatcher as well.
            raise NotImplementedError(
                "Orchestrator currently handles graph problems only; "
                "use StructuralComputer.count_solutions / .matchgate_rank "
                "for constraint sets and signatures."
            )

        attempted: List[str] = list(normalised_notes)

        # 3. Direct dispatch to leaf evaluator if in-family.
        leaf = self.leaf_registry.get((cls.tier, question))
        if leaf is not None and cls.in_family:
            answer = leaf(problem, question)
            return OrchestratorResult(
                answer=answer,
                classification=cls,
                reductions_applied=attempted,
                sub_evaluations=1,
                leaf_evaluator_used=leaf.__name__,
            )

        # 4. Try a hint-supplied reduction first (the parametric case).
        if "extra_edges" in hints and question == "matching_count":
            attempted.append("HybridDecomposition(via hints)")
            h = HybridDecomposition(hints["extra_edges"])
            if h.applies_to(problem):
                rresult = h.apply(problem)
                # Each sub-problem is planar (assumption); the leaf
                # evaluator for the matching_count question on planar
                # gives an exact integer.
                leaf = self.leaf_registry.get(("T2", "matching_count"))
                if leaf is None:
                    raise NoKnownReduction(cls, attempted)
                sub_answers = [
                    leaf(sp, question) for sp in rresult.problem["sub_problems"]
                ]
                final = rresult.inverse(sub_answers)
                return OrchestratorResult(
                    answer=final,
                    classification=cls,
                    reductions_applied=attempted,
                    sub_evaluations=len(sub_answers),
                    leaf_evaluator_used=leaf.__name__,
                )

        # 5. Try each registered (non-parametric) reduction.
        for reduction in self.reductions:
            if reduction is normaliser:  # already applied above
                continue
            attempted.append(reduction.name)
            if not reduction.applies_to(problem):
                continue
            # ... apply, recurse, combine. For v0.1, only NormaliseGraphFormat
            # is in the default list (which doesn't change the in-family verdict),
            # so the loop body doesn't actually fire here. v0.2 will add
            # cost-driven search over the auto-applicable reductions
            # (CrossingElimination, HighDegreeVertexSplit, etc.).
            pass

        # 6. Honest stop.
        raise NoKnownReduction(cls, attempted)


__all__ = [
    "Orchestrator",
    "OrchestratorResult",
    "NoKnownReduction",
    "LeafEvaluator",
    "DEFAULT_LEAF_REGISTRY",
]
