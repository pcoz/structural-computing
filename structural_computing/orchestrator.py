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
class WorkflowStep:
    """One step in the Orchestrator's evaluation workflow.

    Attributes:
      phase: which orchestrator phase this step belongs to (normalise,
        classify, direct-dispatch, hint-driven, auto-hybrid, reduction,
        recurse, honest-stop).
      action: short description of what the orchestrator did at this step.
      outcome: "ok" / "skipped" / "failed" / "honest-stop" or similar.
      detail: optional free-form text (e.g., the reduction name applied,
        the count of sub-problems, the exception message).
    """
    phase: str
    action: str
    outcome: str
    detail: str = ""


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
      workflow_trace: list of WorkflowStep, one per orchestrator phase
        that ran -- the audit trail of what the orchestrator tried.
    """
    answer: Any
    classification: Classification
    reductions_applied: List[str]
    sub_evaluations: int
    leaf_evaluator_used: str
    workflow_trace: List[WorkflowStep] = dataclasses.field(default_factory=list)


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

        The Orchestrator's evaluation is organised as a SEQUENCE OF PHASES.
        Each phase tries to make progress; if it succeeds, the orchestrator
        terminates with the answer. If it fails, control passes to the next
        phase. The phases are:

          1. **Normalise** -- coerce edge-list / adjacency-dict inputs into
             a canonical rotation-system graph dict.
          2. **Classify** -- emit the structural Classification (tier,
             in_family flag, meters, reasoning).
          3. **Direct dispatch** -- if a leaf evaluator for (tier, question)
             is registered AND the problem is in-family, call it directly.
          4. **Hint-driven** -- if the user supplied `hints["extra_edges"]`,
             try `HybridDecomposition` with those extras.
          5. **Auto-Hybrid** -- if the question is "matching_count" and the
             graph is non-planar but has a rotation system, try
             `HybridDecomposition(auto=True)` (greedy extras discovery).
          6. **Registered reductions** -- iterate the user-supplied
             reductions in registration order; first applicable + successful
             wins. Each sub-problem produced is re-classified and dispatched.
          7. **Honest stop** -- raise NoKnownReduction with the full
             workflow_trace attached.

        Every step is recorded in `result.workflow_trace` as a `WorkflowStep`
        with phase, action, outcome, and detail. The caller can inspect the
        trace to understand exactly what the orchestrator tried.

        Args:
          problem: the input problem (graph, constraint set, signature).
          question: the question to answer ("matching_count" is the
            main v0.1 question).
          hints: optional parameters for parametric reductions. For
            graph matching with non-planar boundary, pass
            `{"extra_edges": [...]}` to apply HybridDecomposition.

        Returns:
          OrchestratorResult with the answer + classification + provenance.

        Raises:
          NoKnownReduction: when no phase produces an answer. The
            exception carries the classification (so the caller can
            inspect which tier the problem landed in) and the list of
            attempted reductions.
        """
        hints = hints or {}
        workflow_trace: List[WorkflowStep] = []
        reductions_applied: List[str] = []

        # ----- Phase 1: Normalise --------------------------------------
        normaliser = NormaliseGraphFormat()
        if normaliser.applies_to(problem):
            problem = normaliser.apply(problem).problem
            reductions_applied.append(normaliser.name)
            workflow_trace.append(WorkflowStep(
                phase="normalise", action="NormaliseGraphFormat",
                outcome="ok",
                detail=f"vertices={len(problem.get('vertices', []))}, "
                        f"edges={len(problem.get('edges', []))}",
            ))
        else:
            workflow_trace.append(WorkflowStep(
                phase="normalise", action="NormaliseGraphFormat",
                outcome="skipped",
                detail="input already in canonical form (or unsupported type)",
            ))

        # ----- Phase 2: Classify --------------------------------------
        if isinstance(problem, dict) and "rotation" in problem:
            cls = classify_graph(problem["rotation"])
            workflow_trace.append(WorkflowStep(
                phase="classify", action="classify_graph",
                outcome="ok",
                detail=f"tier={cls.tier}, in_family={cls.in_family}, "
                        f"reasoning='{cls.reasoning}'",
            ))
        else:
            workflow_trace.append(WorkflowStep(
                phase="classify", action="classify_graph",
                outcome="failed",
                detail="problem is not a graph dict with a rotation system",
            ))
            raise NotImplementedError(
                "Orchestrator currently handles graph problems only; "
                "use StructuralComputer.count_solutions / .matchgate_rank "
                "for constraint sets and signatures."
            )

        # ----- Phase 3: Direct dispatch -------------------------------
        leaf = self.leaf_registry.get((cls.tier, question))
        if leaf is not None and cls.in_family:
            answer = leaf(problem, question)
            workflow_trace.append(WorkflowStep(
                phase="direct-dispatch", action=f"leaf_evaluator({cls.tier}, {question})",
                outcome="ok",
                detail=f"answer={answer!r}, evaluator={leaf.__name__}",
            ))
            return OrchestratorResult(
                answer=answer,
                classification=cls,
                reductions_applied=reductions_applied,
                sub_evaluations=1,
                leaf_evaluator_used=leaf.__name__,
                workflow_trace=workflow_trace,
            )
        workflow_trace.append(WorkflowStep(
            phase="direct-dispatch", action=f"leaf_evaluator({cls.tier}, {question})",
            outcome="skipped",
            detail=(f"no leaf evaluator registered for ({cls.tier}, {question})"
                    if leaf is None else "problem out-of-family"),
        ))

        # ----- Phase 4: Hint-driven HybridDecomposition ---------------
        if "extra_edges" in hints and question == "matching_count":
            try:
                result = self._try_hybrid_decomposition(
                    problem, hints["extra_edges"], origin="hints",
                )
                workflow_trace.append(WorkflowStep(
                    phase="hint-driven", action="HybridDecomposition(via hints)",
                    outcome="ok",
                    detail=f"answer={result['answer']!r}, "
                            f"sub_evaluations={result['sub_evaluations']}",
                ))
                reductions_applied.append("HybridDecomposition(via hints)")
                return OrchestratorResult(
                    answer=result["answer"],
                    classification=cls,
                    reductions_applied=reductions_applied,
                    sub_evaluations=result["sub_evaluations"],
                    leaf_evaluator_used=result["leaf_evaluator_used"],
                    workflow_trace=workflow_trace,
                )
            except (ReductionNotApplicable, NoKnownReduction) as e:
                workflow_trace.append(WorkflowStep(
                    phase="hint-driven", action="HybridDecomposition(via hints)",
                    outcome="failed", detail=str(e),
                ))

        # ----- Phase 5: Auto-Hybrid (greedy extras discovery) ---------
        if question == "matching_count" and not cls.in_family and "rotation" in problem:
            try:
                h = HybridDecomposition(auto=True)
                if h.applies_to(problem):
                    rresult = h.apply(problem)
                    if h.extra_edges:
                        # Successful auto-discovery; evaluate sub-problems.
                        result = self._evaluate_sub_problems(
                            rresult.problem["sub_problems"], rresult, question,
                        )
                        workflow_trace.append(WorkflowStep(
                            phase="auto-hybrid",
                            action="HybridDecomposition(auto=True)",
                            outcome="ok",
                            detail=f"discovered {len(h.extra_edges)} extras; "
                                    f"answer={result['answer']!r}; "
                                    f"sub_evaluations={result['sub_evaluations']}",
                        ))
                        reductions_applied.append(
                            f"HybridDecomposition(auto={len(h.extra_edges)})")
                        return OrchestratorResult(
                            answer=result["answer"],
                            classification=cls,
                            reductions_applied=reductions_applied,
                            sub_evaluations=result["sub_evaluations"],
                            leaf_evaluator_used=result["leaf_evaluator_used"],
                            workflow_trace=workflow_trace,
                        )
                    else:
                        workflow_trace.append(WorkflowStep(
                            phase="auto-hybrid",
                            action="HybridDecomposition(auto=True)",
                            outcome="failed",
                            detail="auto-detection found no planarising extras "
                                    "(see auto_detect_extras docstring's 'Honest scope')",
                        ))
            except Exception as e:
                workflow_trace.append(WorkflowStep(
                    phase="auto-hybrid",
                    action="HybridDecomposition(auto=True)",
                    outcome="failed", detail=str(e),
                ))

        # ----- Phase 6: Registered reductions -------------------------
        for reduction in self.reductions:
            if reduction is normaliser:
                continue                                # already applied
            if not reduction.applies_to(problem):
                workflow_trace.append(WorkflowStep(
                    phase="reduction", action=reduction.name,
                    outcome="skipped", detail="not applicable to current problem",
                ))
                continue
            try:
                rresult = reduction.apply(problem)
                result = self._evaluate_sub_problems(
                    rresult.problem.get("sub_problems", []), rresult, question,
                )
                workflow_trace.append(WorkflowStep(
                    phase="reduction", action=reduction.name, outcome="ok",
                    detail=f"answer={result['answer']!r}",
                ))
                reductions_applied.append(reduction.name)
                return OrchestratorResult(
                    answer=result["answer"],
                    classification=cls,
                    reductions_applied=reductions_applied,
                    sub_evaluations=result["sub_evaluations"],
                    leaf_evaluator_used=result["leaf_evaluator_used"],
                    workflow_trace=workflow_trace,
                )
            except (ReductionNotApplicable, NoKnownReduction, NotImplementedError) as e:
                workflow_trace.append(WorkflowStep(
                    phase="reduction", action=reduction.name,
                    outcome="failed", detail=str(e),
                ))

        # ----- Phase 7: Honest stop -----------------------------------
        workflow_trace.append(WorkflowStep(
            phase="honest-stop", action="NoKnownReduction",
            outcome="honest-stop",
            detail=f"tier={cls.tier}, attempted={reductions_applied}",
        ))
        raise NoKnownReduction(cls, reductions_applied)

    # -- Helpers ------------------------------------------------------------

    def _try_hybrid_decomposition(self, problem, extra_edges, *, origin):
        """Apply HybridDecomposition with the given extras; evaluate the
        resulting sub-problems via the T2 leaf evaluator (planar). Returns
        a dict with answer, sub_evaluations, leaf_evaluator_used."""
        h = HybridDecomposition(extra_edges)
        if not h.applies_to(problem):
            raise ReductionNotApplicable(
                f"HybridDecomposition({origin}) not applicable"
            )
        rresult = h.apply(problem)
        return self._evaluate_sub_problems(
            rresult.problem["sub_problems"], rresult, "matching_count",
        )

    def _evaluate_sub_problems(self, sub_problems, rresult, question):
        """Evaluate each sub-problem produced by a reduction, then combine
        via the reduction's inverse. Used by both hint-driven and
        auto-Hybrid phases. Returns dict with answer, sub_evaluations,
        leaf_evaluator_used."""
        # The sub-problems should be in-family (T2 planar typically).
        # Use the T2 leaf evaluator on each.
        leaf = self.leaf_registry.get(("T2", question))
        if leaf is None:
            raise NoKnownReduction(
                Classification(tier="T2", meters={}, in_family=True,
                                 reasoning="reduction sub-problem"),
                [f"no leaf evaluator for (T2, {question})"],
            )
        sub_answers = [leaf(sp, question) for sp in sub_problems]
        return {
            "answer": rresult.inverse(sub_answers),
            "sub_evaluations": len(sub_answers),
            "leaf_evaluator_used": leaf.__name__,
        }


__all__ = [
    "Orchestrator",
    "OrchestratorResult",
    "WorkflowStep",
    "NoKnownReduction",
    "LeafEvaluator",
    "DEFAULT_LEAF_REGISTRY",
]
