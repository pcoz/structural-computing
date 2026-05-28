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

import numpy as np

from .classify import (
    Classification,
    classify_graph,
    classify_constraint_set,
    classify_signature,
)
from .route import route as route_classification
from .transform import (
    Reduction,
    ReductionPlan,
    ReductionNotApplicable,
    HybridDecomposition,
    NormaliseGraphFormat,
    RationaliseWeights,
    CrossingElimination,
    HighDegreeVertexSplit,
)
from .compose import Composition, CompositionPlan, LinearCombination
from .decompose import (
    Decomposition,
    DecompositionPlan,
    ShannonExpansion,
    TreewidthBoundedDP,
)
from .verifier import (
    brute_force_count_matchings,
    brute_force_weighted_matching_sum,
    enumerate_satisfying_assignments,
    satisfies_gf2_affine,
)


# ===========================================================================
# IMPORTANT: keeping the Orchestrator up to date
# ===========================================================================
#
# The Orchestrator is the framework's TOP-LEVEL DISPATCHER. Every new
# capability added to the package must be exposed through the Orchestrator
# as well, otherwise the user of `Orchestrator.evaluate()` won't be able
# to reach it.
#
# The places that have to be kept in lock-step with the rest of the
# package:
#
#   1. **Classifier dispatcher** -- `_classify_problem` below. If a new
#      problem type is added (a new `classify_*` function in classify.py),
#      add a branch here.
#
#   2. **DEFAULT_LEAF_REGISTRY** -- the (tier, question) -> evaluator map
#      below. Every new (tier, question) pair the framework can answer
#      needs an entry. Wrapper methods on StructuralComputer are
#      effectively shorthand for `Orchestrator.evaluate(problem,
#      question=<the method name>)` -- so every wrapper method should be
#      reachable via a leaf evaluator.
#
#   3. **The Orchestrator's `_default_reductions` list** -- every
#      currently-runnable reduction that can apply auto-detectably should
#      be in this list, so the Phase-6 search reaches it.
#
# If you add new functionality and DON'T touch this file, the orchestrator
# will silently NOT reach the new functionality and the user will get
# `NoKnownReduction` even though the framework CAN do it. So: touch this
# file every time.
#
# When adding a new phase, use the `emit(phase, action, outcome, detail)`
# helper defined inside `evaluate()` -- it appends a WorkflowStep to the
# trace AND (if verbose=True) streams the step to the log so the user
# sees decisions and reasoning as the orchestrator runs. Don't append to
# `workflow_trace` directly; that bypasses verbose mode.
# ===========================================================================


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
# v0.2 default registry covers:
#
#   Graphs (T2/T4):
#     matching_count, witness, single_points_of_failure,
#     tail_probability
#
#   Constraint sets (T0/T1):
#     count_solutions, find_witness, list_solutions
#
#   Signatures (T2/T3):
#     matchgate_rank, is_matchgate_realisable, classify_function
#
# To add a new (tier, question), write a small leaf-evaluator function
# below and register it. To add a question for a new tier, same -- just
# add an entry.

LeafEvaluator = Callable[[Any, str], Any]


# ---------- Graph leaf evaluators ------------------------------------------

def _matching_count_leaf(problem: Any, question: str) -> int:
    """matching_count on a graph (T2 or T4): brute force at small n."""
    if isinstance(problem, dict) and "vertices" in problem:
        return brute_force_count_matchings(problem["vertices"], problem["edges"])
    raise ValueError(f"matching_count_leaf expects a graph dict; got {type(problem).__name__}")


def _weighted_matching_sum_leaf(problem: Any, question: str) -> float:
    """weighted_matching_sum on a graph (T2 or T4): the sum over perfect
    matchings M of (product of weight(e) for e in M). Brute force at
    small n. Requires a `weights` field on the problem dict mapping
    edges -> real (or integer) weights; missing edges default to 1.0."""
    if not isinstance(problem, dict) or "vertices" not in problem:
        raise ValueError(
            f"weighted_matching_sum_leaf expects a graph dict; got {type(problem).__name__}"
        )
    if "weights" not in problem:
        raise ValueError(
            "weighted_matching_sum_leaf requires a 'weights' field on the problem"
        )
    return brute_force_weighted_matching_sum(
        problem["vertices"], problem["edges"], problem["weights"],
    )


def _witness_leaf(problem: Any, question: str) -> List[Tuple[Any, Any]]:
    """witness on a graph (T2 or T4): one perfect matching via min-weight."""
    import math
    import holant_tools
    if not isinstance(problem, dict) or "vertices" not in problem:
        raise ValueError(f"witness_leaf expects a graph dict")
    vertices = problem["vertices"]
    edges = problem["edges"]
    n = len(vertices)
    idx = {v: i for i, v in enumerate(vertices)}
    W = [[math.inf] * n for _ in range(n)]
    for (u, w) in edges:
        i, j = idx[u], idx[w]
        W[i][j] = W[j][i] = 1.0
    _, matching = holant_tools.min_weight_perfect_matching(W)
    if matching is None:
        return []
    return [(vertices[i], vertices[j]) for (i, j) in matching]


def _spofs_leaf(problem: Any, question: str) -> List[Tuple[Any, Any]]:
    """single_points_of_failure on a graph: edges whose removal drops
    the matching count to 0."""
    if not isinstance(problem, dict) or "vertices" not in problem:
        raise ValueError(f"spofs_leaf expects a graph dict")
    vertices = problem["vertices"]
    edges = problem["edges"]
    spofs = []
    for e in edges:
        sub = [x for x in edges if x != e]
        if brute_force_count_matchings(vertices, sub) == 0:
            spofs.append(e)
    return spofs


def _tail_probability_leaf(problem: Any, question: str) -> float:
    """tail_probability on a graph: exact P(no perfect matching survives)
    under independent edge failure. Caller passes `p_fail` via problem
    metadata. Brute-force 2^|E| enumeration; capped at |E| <= 24."""
    if not isinstance(problem, dict) or "vertices" not in problem:
        raise ValueError(f"tail_probability_leaf expects a graph dict")
    p_fail = problem.get("p_fail")
    if p_fail is None:
        raise ValueError("tail_probability requires 'p_fail' in the problem dict")
    vertices = problem["vertices"]
    edges = problem["edges"]
    n_edges = len(edges)
    if n_edges > 24:
        raise ValueError(f"tail_probability_leaf: |E|={n_edges} > 24 (cap)")
    total = 0.0
    for mask in range(2 ** n_edges):
        surviving = [edges[i] for i in range(n_edges) if (mask >> i) & 1]
        k_failed = n_edges - len(surviving)
        weight = (p_fail ** k_failed) * ((1 - p_fail) ** (n_edges - k_failed))
        if brute_force_count_matchings(vertices, surviving) == 0:
            total += weight
    return total


# ---------- Constraint-set leaf evaluators ---------------------------------

def _count_solutions_leaf(problem: Any, question: str) -> int:
    """count_solutions on a constraint set (T0/T1): exact count of x with
    A x = b (mod 2) and optionally quadratic constraints."""
    from .easy import _gf2_rank
    if not isinstance(problem, dict) or "A" not in problem:
        raise ValueError("count_solutions_leaf expects {A, b, Q?, c?}")
    A = np.asarray(problem["A"], dtype=int)
    b = np.asarray(problem.get("b", np.zeros(A.shape[0], dtype=int)), dtype=int)
    Q = problem.get("Q") or []
    c = problem.get("c")
    n = A.shape[1] if A.size else 0
    if n == 0:
        return 1 if not Q else 0
    if not Q:
        # T0: count = 2^(n - rank(A)) if consistent, else 0.
        rank = _gf2_rank(A)
        Aug = np.hstack([A, b.reshape(-1, 1)])
        if _gf2_rank(Aug) != rank:
            return 0
        return 2 ** (n - rank)
    # T1: brute force at small n
    if n > 24:
        raise ValueError(f"count_solutions_leaf T1: n={n} > 24 (cap)")
    Q_list = [np.asarray(Qi, dtype=int) for Qi in Q]
    c_arr = np.asarray(c if c is not None else [0] * len(Q_list), dtype=int)
    count = 0
    for x in range(2 ** n):
        bits = np.array([(x >> (n - 1 - i)) & 1 for i in range(n)], dtype=int)
        if not np.array_equal((A @ bits) % 2, b % 2):
            continue
        if all((bits @ Qi @ bits) % 2 == ci % 2 for Qi, ci in zip(Q_list, c_arr)):
            count += 1
    return count


def _find_witness_constraint_leaf(problem: Any, question: str) -> Optional[int]:
    """find_witness on a constraint set: one satisfying assignment as int,
    or None if infeasible. T0 uses Gauss-Jordan; T1 uses brute force."""
    from .easy import _gf2_solve_one, _bits_to_int
    A = np.asarray(problem["A"], dtype=int)
    b = np.asarray(problem.get("b", np.zeros(A.shape[0], dtype=int)), dtype=int)
    Q = problem.get("Q") or []
    if not Q:
        x = _gf2_solve_one(A, b)
        return _bits_to_int(x) if x is not None else None
    n = A.shape[1]
    if n > 24:
        raise ValueError(f"find_witness_constraint_leaf T1: n={n} > 24")
    Q_list = [np.asarray(Qi, dtype=int) for Qi in Q]
    c_arr = np.asarray(problem.get("c", [0] * len(Q_list)), dtype=int)
    for x in range(2 ** n):
        bits = np.array([(x >> (n - 1 - i)) & 1 for i in range(n)], dtype=int)
        if not np.array_equal((A @ bits) % 2, b % 2):
            continue
        if all((bits @ Qi @ bits) % 2 == ci % 2 for Qi, ci in zip(Q_list, c_arr)):
            return x
    return None


def _list_solutions_leaf(problem: Any, question: str) -> List[int]:
    """list_solutions on a constraint set: brute-force enumeration of all
    satisfying assignments. Capped at n <= 20."""
    A = np.asarray(problem["A"], dtype=int)
    b = np.asarray(problem.get("b", np.zeros(A.shape[0], dtype=int)), dtype=int)
    Q_raw = problem.get("Q") or []
    n = A.shape[1]
    if n > 20:
        raise ValueError(f"list_solutions_leaf: n={n} > 20 (cap)")
    if not Q_raw:
        return enumerate_satisfying_assignments(A, b)
    Q_list = [np.asarray(Qi, dtype=int) for Qi in Q_raw]
    c_arr = np.asarray(problem.get("c", [0] * len(Q_list)), dtype=int)
    out = []
    for x in range(2 ** n):
        bits = np.array([(x >> (n - 1 - i)) & 1 for i in range(n)], dtype=int)
        if not np.array_equal((A @ bits) % 2, b % 2):
            continue
        if all((bits @ Qi @ bits) % 2 == ci % 2 for Qi, ci in zip(Q_list, c_arr)):
            out.append(x)
    return out


# ---------- Signature leaf evaluators --------------------------------------

def _matchgate_rank_leaf(problem: Any, question: str) -> int:
    """matchgate_rank on a symmetric signature (T2 or T3): read the
    basis-aware rank from the Classification meters. The publicly-
    original result is that this is always in {0, 1, 2} for symmetric
    signatures."""
    if not isinstance(problem, dict) or "values" not in problem:
        raise ValueError("matchgate_rank_leaf expects {values: [v_0, ..., v_n]}")
    cls = classify_signature(problem["values"])
    return int(cls.meters.get("basis_aware_rank", -1))


def _is_matchgate_realisable_leaf(problem: Any, question: str) -> bool:
    return _matchgate_rank_leaf(problem, "matchgate_rank") >= 1


def _classify_function_leaf(problem: Any, question: str) -> Classification:
    if not isinstance(problem, dict) or "values" not in problem:
        raise ValueError("classify_function_leaf expects {values: ...}")
    return classify_signature(problem["values"])


def _matchgate_realisation_leaf(problem: Any, question: str) -> Dict[str, Any]:
    """matchgate_realisation on a symmetric signature: build the Cai-
    Gorenstein 2k-node triangle-cycle planar matchgate (Fig. 10/11)
    realising the signature. Returns the matchgate dict {vertices,
    edges, weights, externals, ...}. Raises if the signature is not
    matchgate-realisable (geometric-progression invariant fails)."""
    if not isinstance(problem, dict) or "values" not in problem:
        raise ValueError("matchgate_realisation_leaf expects {values: [...]}")
    h = HighDegreeVertexSplit(signature=list(problem["values"]))
    return h.apply(problem).problem


# ---------- The default registry (covers everything reachable in v0.2) -----

DEFAULT_LEAF_REGISTRY: Dict[Tuple[str, str], LeafEvaluator] = {
    # Graph questions
    ("T2", "matching_count"):            _matching_count_leaf,
    ("T4", "matching_count"):            _matching_count_leaf,
    ("T2", "weighted_matching_sum"):     _weighted_matching_sum_leaf,
    ("T4", "weighted_matching_sum"):     _weighted_matching_sum_leaf,
    ("T2", "witness"):                   _witness_leaf,
    ("T4", "witness"):                   _witness_leaf,
    ("T2", "single_points_of_failure"):  _spofs_leaf,
    ("T4", "single_points_of_failure"):  _spofs_leaf,
    ("T2", "tail_probability"):          _tail_probability_leaf,
    ("T4", "tail_probability"):          _tail_probability_leaf,
    # Constraint-set questions
    ("T0", "count_solutions"):           _count_solutions_leaf,
    ("T1", "count_solutions"):           _count_solutions_leaf,
    ("T0", "find_witness"):              _find_witness_constraint_leaf,
    ("T1", "find_witness"):              _find_witness_constraint_leaf,
    ("T0", "list_solutions"):            _list_solutions_leaf,
    ("T1", "list_solutions"):            _list_solutions_leaf,
    # Signature questions
    ("T2", "matchgate_rank"):            _matchgate_rank_leaf,
    ("T3", "matchgate_rank"):            _matchgate_rank_leaf,
    ("T2", "is_matchgate_realisable"):   _is_matchgate_realisable_leaf,
    ("T3", "is_matchgate_realisable"):   _is_matchgate_realisable_leaf,
    ("T2", "classify_function"):         _classify_function_leaf,
    ("T3", "classify_function"):         _classify_function_leaf,
    ("T2", "matchgate_realisation"):     _matchgate_realisation_leaf,
    ("T3", "matchgate_realisation"):     _matchgate_realisation_leaf,
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
                  hints: Optional[Dict[str, Any]] = None,
                  verbose: bool = False,
                  log: Optional[Callable[[str], None]] = None) -> OrchestratorResult:
        """Compute the answer to `question` on `problem`.

        The Orchestrator's evaluation is organised as a SEQUENCE OF PHASES.
        Each phase tries to make progress; if it succeeds, the orchestrator
        terminates with the answer. If it fails, control passes to the next
        phase. The phases are:

          1. **Normalise** -- coerce edge-list / adjacency-dict inputs into
             a canonical rotation-system graph dict.
          1.5. **Rationalise weights** -- if `hints["rationalise_precision"]`
             is supplied and the problem has real-valued `weights`, scale
             them to integers and remember the inverse so the final answer
             is divided by `10^(precision * matching_size)`.
          2. **Classify** -- emit the structural Classification (tier,
             in_family flag, meters, reasoning).
          3. **Direct dispatch** -- if a leaf evaluator for (tier, question)
             is registered AND the problem is in-family, call it directly.
          4. **Hint-driven** -- if the user supplied `hints["extra_edges"]`,
             try `HybridDecomposition` with those extras.
          4.5. **Treewidth DP** -- if `hints["tree_decomposition"]` is
             supplied and the question is `matching_count`, run the
             Bodlaender-style multi-bag DP.
          4.7. **Crossing elimination** -- if `hints["crossings"]` is
             supplied, insert the Cai-Gorenstein gadget at each declared
             crossing; the resulting planar graph is dispatched to the
             T2 leaf evaluator. The gadget preserves the SIGNED matchgate
             signature, not unsigned PerfMatch in general.
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

        VERBOSE MODE
        ------------
        Pass `verbose=True` to stream each step to stdout (or a custom `log`
        callable) AS IT HAPPENS. The output explains which phase fired, what
        action was taken, what the outcome was, and the reasoning behind
        each decision. This is the easiest way to see what the orchestrator
        is doing inside a long-running pipeline, debug an unexpected honest
        stop, or learn the framework by following an evaluate() call.

        Example::

            orch = Orchestrator()
            r = orch.evaluate(problem, "matching_count", verbose=True)
            # >> [normalise] NormaliseGraphFormat -> skipped
            # >>     reason: input already in canonical form
            # >> [classify] classify_graph -> ok
            # >>     reason: tier=T2, planar (genus 0) on 4 vertices
            # >> [direct-dispatch] leaf_evaluator(T2, matching_count) -> ok
            # >>     reason: answer=3, evaluator=_matching_count_leaf

        Pass a custom `log=my_logger` to redirect output (defaults to
        `print` to stdout). The caller's log function receives one string
        per line.

        Args:
          problem: the input problem (graph, constraint set, signature).
          question: the question to answer ("matching_count" is the
            main v0.1 question).
          hints: optional parameters for parametric reductions. For
            graph matching with non-planar boundary, pass
            `{"extra_edges": [...]}` to apply HybridDecomposition.
          verbose: if True, stream the workflow trace to stdout (or `log`)
            as the orchestrator runs.
          log: custom logger; a callable taking one string. Defaults to
            `print`. Only used when `verbose=True`.

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
        # post_inverse: callable to apply to the final answer (used by
        # RationaliseWeights to undo the 10^(precision * matching_size)
        # scaling). None when no post-processing is needed.
        post_inverse: Optional[Callable[[Any], Any]] = None
        # Verbose-mode logger and emitter.
        log_fn: Callable[[str], None] = log if log is not None else print

        def emit(phase: str, action: str, outcome: str, detail: str = "") -> None:
            """Append a WorkflowStep to the trace AND (if verbose) print it
            so the caller sees decisions and reasoning as the orchestrator
            runs."""
            step = WorkflowStep(phase=phase, action=action,
                                  outcome=outcome, detail=detail)
            workflow_trace.append(step)
            if verbose:
                log_fn(f"[{phase}] {action} -> {outcome}")
                if detail:
                    log_fn(f"    reason: {detail}")

        if verbose:
            log_fn(f"Orchestrator.evaluate(question={question!r}, "
                   f"hints={list(hints.keys()) or '(none)'})")

        # ----- Phase 1: Normalise --------------------------------------
        normaliser = NormaliseGraphFormat()
        if normaliser.applies_to(problem):
            problem = normaliser.apply(problem).problem
            reductions_applied.append(normaliser.name)
            emit("normalise", "NormaliseGraphFormat", "ok",
                 f"vertices={len(problem.get('vertices', []))}, "
                 f"edges={len(problem.get('edges', []))}")
        else:
            emit("normalise", "NormaliseGraphFormat", "skipped",
                 "input already in canonical form (or unsupported type)")

        # ----- Phase 1.5: Rationalise weights (hint-driven) -----------
        # If the user supplied `rationalise_precision` AND the problem is
        # a weighted graph with at least one float weight, scale weights
        # to integers and remember the inverse so we can divide the final
        # answer by 10^(precision * matching_size) at the end. Without an
        # explicit `rationalise_matching_size`, infer it from |V|//2 (the
        # number of edges in a perfect matching). The inverse is a no-op
        # for non-weighted-sum questions, so this phase is safe to fire
        # whenever the hint is present.
        if "rationalise_precision" in hints and isinstance(problem, dict) \
                and "weights" in problem:
            precision = hints["rationalise_precision"]
            matching_size = hints.get(
                "rationalise_matching_size",
                len(problem.get("vertices", [])) // 2,
            )
            rw = RationaliseWeights(precision=precision, matching_size=matching_size)
            if rw.applies_to(problem):
                rresult = rw.apply(problem)
                problem = rresult.problem
                post_inverse = rresult.inverse
                reductions_applied.append(rw.name)
                emit("rationalise",
                     f"RationaliseWeights(precision={precision}, "
                     f"matching_size={matching_size})",
                     "ok",
                     f"scaled {len(problem['weights'])} weights to integers; "
                     f"final-answer divisor = 10^{precision * matching_size}")
            else:
                emit("rationalise",
                     f"RationaliseWeights(precision={precision})",
                     "skipped",
                     "weights already integer-valued (or absent)")

        # ----- Phase 2: Classify --------------------------------------
        cls, classifier_name = self._classify_problem(problem)
        if cls is None:
            emit("classify", "auto-dispatch", "failed",
                 f"could not infer classifier for problem type {type(problem).__name__}")
            raise NoKnownReduction(
                Classification(tier="T7", meters={"problem_type": type(problem).__name__},
                                in_family=False, reasoning="unknown problem type"),
                reductions_applied,
            )
        emit("classify", classifier_name, "ok",
             f"tier={cls.tier}, in_family={cls.in_family}, "
             f"reasoning='{cls.reasoning}'")

        # If calibration data has been loaded for (tier, question), emit
        # a separate "predict" step that records the expected wall-clock
        # cost. This is informational; the dispatch decision is unaffected.
        from .calibration import has_calibration_for as _has_cal, predict_seconds as _predict
        from .route import _size_hint_for as _size_hint
        if _has_cal(cls.tier, question):
            n = _size_hint(cls.tier, cls.meters)
            pred = _predict(cls.tier, question, n=n)
            if pred is not None:
                emit("predict", f"calibrated_predict({cls.tier}, {question})", "ok",
                     f"predicted_seconds={pred:.6g}, size={n}")

        # ----- Phase 3: Direct dispatch -------------------------------
        leaf = self.leaf_registry.get((cls.tier, question))
        if leaf is not None and cls.in_family:
            answer = leaf(problem, question)
            if post_inverse is not None:
                answer = post_inverse(answer)
            emit("direct-dispatch",
                 f"leaf_evaluator({cls.tier}, {question})", "ok",
                 f"answer={answer!r}, evaluator={leaf.__name__}")
            return OrchestratorResult(
                answer=answer,
                classification=cls,
                reductions_applied=reductions_applied,
                sub_evaluations=1,
                leaf_evaluator_used=leaf.__name__,
                workflow_trace=workflow_trace,
            )
        emit("direct-dispatch",
             f"leaf_evaluator({cls.tier}, {question})", "skipped",
             (f"no leaf evaluator registered for ({cls.tier}, {question})"
              if leaf is None else "problem out-of-family"))

        # ----- Phase 4: Hint-driven HybridDecomposition ---------------
        if "extra_edges" in hints and question == "matching_count":
            try:
                result = self._try_hybrid_decomposition(
                    problem, hints["extra_edges"], origin="hints",
                )
                emit("hint-driven", "HybridDecomposition(via hints)", "ok",
                     f"answer={result['answer']!r}, "
                     f"sub_evaluations={result['sub_evaluations']}")
                reductions_applied.append("HybridDecomposition(via hints)")
                answer = result["answer"]
                if post_inverse is not None:
                    answer = post_inverse(answer)
                return OrchestratorResult(
                    answer=answer,
                    classification=cls,
                    reductions_applied=reductions_applied,
                    sub_evaluations=result["sub_evaluations"],
                    leaf_evaluator_used=result["leaf_evaluator_used"],
                    workflow_trace=workflow_trace,
                )
            except (ReductionNotApplicable, NoKnownReduction) as e:
                emit("hint-driven", "HybridDecomposition(via hints)",
                     "failed", str(e))

        # ----- Phase 4.5: Tree-decomposition DP (hint-driven) ---------
        # If the user supplied a tree decomposition AND the question is
        # matching_count, run TreewidthBoundedDP. This is exact poly-time
        # for bounded-treewidth graphs even if non-planar.
        if "tree_decomposition" in hints and question == "matching_count":
            try:
                td = hints["tree_decomposition"]
                decomp = TreewidthBoundedDP(tree_decomposition=td)
                plan = decomp.decompose(problem)
                # Plan is precomputed-value -- evaluate just returns it.
                answer = plan.evaluate(lambda _p: 0)
                emit("treewidth-dp",
                     "TreewidthBoundedDP(tree_decomposition=...)", "ok",
                     f"answer={answer}, bags={len(td.get('bags', []))}")
                reductions_applied.append(
                    f"TreewidthBoundedDP(bags={len(td.get('bags', []))})")
                if post_inverse is not None:
                    answer = post_inverse(answer)
                return OrchestratorResult(
                    answer=answer,
                    classification=cls,
                    reductions_applied=reductions_applied,
                    sub_evaluations=1,                    # the DP is one batched eval
                    leaf_evaluator_used="TreewidthBoundedDP(internal-DP)",
                    workflow_trace=workflow_trace,
                )
            except (NotImplementedError, ValueError) as e:
                emit("treewidth-dp",
                     "TreewidthBoundedDP(tree_decomposition=...)",
                     "failed", str(e))

        # ----- Phase 4.7: Crossing elimination (hint-driven) ----------
        # If the user supplied a list of declared crossings AND the
        # question is matching_count or weighted_matching_sum, insert
        # the Cai-Gorenstein gadget at each crossing to produce a
        # planar graph; then dispatch to the planar (T2) leaf
        # evaluator. NOTE: the gadget preserves the SIGNED matchgate
        # signature, not unsigned PerfMatch in general. For unit-weight
        # graphs the two may coincide; for weighted graphs they don't.
        # Callers should know which semantic they want.
        if "crossings" in hints and question in ("matching_count",
                                                   "weighted_matching_sum"):
            try:
                crossings = hints["crossings"]
                ce = CrossingElimination(crossings=crossings)
                if ce.applies_to(problem):
                    cresult = ce.apply(problem)
                    planar_problem = cresult.problem
                    leaf_t2 = self.leaf_registry.get(("T2", question))
                    if leaf_t2 is None:
                        raise NoKnownReduction(
                            cls,
                            [f"no T2 leaf for ({question}) after planarisation"],
                        )
                    answer = leaf_t2(planar_problem, question)
                    emit("crossing-elimination",
                         f"CrossingElimination(crossings={len(crossings)})",
                         "ok",
                         f"planarised: {len(planar_problem['vertices'])}V, "
                         f"{len(planar_problem['edges'])}E; "
                         f"signed answer={answer!r}")
                    reductions_applied.append(
                        f"CrossingElimination({len(crossings)})")
                    if post_inverse is not None:
                        answer = post_inverse(answer)
                    return OrchestratorResult(
                        answer=answer,
                        classification=cls,
                        reductions_applied=reductions_applied,
                        sub_evaluations=1,
                        leaf_evaluator_used=leaf_t2.__name__,
                        workflow_trace=workflow_trace,
                    )
            except (ReductionNotApplicable, NoKnownReduction, ValueError) as e:
                emit("crossing-elimination",
                     f"CrossingElimination(crossings={len(hints['crossings'])})",
                     "failed", str(e))

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
                        emit("auto-hybrid", "HybridDecomposition(auto=True)", "ok",
                             f"discovered {len(h.extra_edges)} extras; "
                             f"answer={result['answer']!r}; "
                             f"sub_evaluations={result['sub_evaluations']}")
                        reductions_applied.append(
                            f"HybridDecomposition(auto={len(h.extra_edges)})")
                        answer = result["answer"]
                        if post_inverse is not None:
                            answer = post_inverse(answer)
                        return OrchestratorResult(
                            answer=answer,
                            classification=cls,
                            reductions_applied=reductions_applied,
                            sub_evaluations=result["sub_evaluations"],
                            leaf_evaluator_used=result["leaf_evaluator_used"],
                            workflow_trace=workflow_trace,
                        )
                    else:
                        emit("auto-hybrid", "HybridDecomposition(auto=True)",
                             "failed",
                             "auto-detection found no planarising extras "
                             "(see auto_detect_extras docstring's 'Honest scope')")
            except Exception as e:
                emit("auto-hybrid", "HybridDecomposition(auto=True)",
                     "failed", str(e))

        # ----- Phase 6: Registered reductions -------------------------
        for reduction in self.reductions:
            if reduction is normaliser:
                continue                                # already applied
            if not reduction.applies_to(problem):
                emit("reduction", reduction.name, "skipped",
                     "not applicable to current problem")
                continue
            try:
                rresult = reduction.apply(problem)
                result = self._evaluate_sub_problems(
                    rresult.problem.get("sub_problems", []), rresult, question,
                )
                emit("reduction", reduction.name, "ok",
                     f"answer={result['answer']!r}")
                reductions_applied.append(reduction.name)
                answer = result["answer"]
                if post_inverse is not None:
                    answer = post_inverse(answer)
                return OrchestratorResult(
                    answer=answer,
                    classification=cls,
                    reductions_applied=reductions_applied,
                    sub_evaluations=result["sub_evaluations"],
                    leaf_evaluator_used=result["leaf_evaluator_used"],
                    workflow_trace=workflow_trace,
                )
            except (ReductionNotApplicable, NoKnownReduction, NotImplementedError) as e:
                emit("reduction", reduction.name, "failed", str(e))

        # ----- Phase 7: Honest stop -----------------------------------
        emit("honest-stop", "NoKnownReduction", "honest-stop",
             f"tier={cls.tier}, attempted={reductions_applied}")
        raise NoKnownReduction(cls, reductions_applied)

    # -- Helpers ------------------------------------------------------------

    def _classify_problem(self, problem: Any) -> Tuple[Optional[Classification], str]:
        """Auto-detect the problem type and dispatch to the right classifier.

        Recognises:
          - GRAPH dict with 'rotation' key (after normalisation, this is
            the canonical form) -> classify_graph
          - CONSTRAINT-SET dict with 'A' key (and optionally 'b', 'Q', 'c',
            'modulus') -> classify_constraint_set
          - SIGNATURE dict with 'values' key (sequence of Hamming-weight-
            indexed values) -> classify_signature
          - Problem dict with explicit 'kind' field:
              'graph', 'constraint_set', 'signature'

        Returns (Classification, classifier_name) on success; (None, "")
        if the problem doesn't match any known type.

        When you add a new problem type, add a branch here AND a leaf
        evaluator entry in DEFAULT_LEAF_REGISTRY for the relevant
        (tier, question) pairs.
        """
        if not isinstance(problem, dict):
            return None, ""
        # Explicit kind dispatch first (most reliable).
        kind = problem.get("kind")
        if kind == "graph":
            return (classify_graph(problem["data"]["rotation"]
                                     if "data" in problem
                                     else problem.get("rotation", {})),
                    "classify_graph")
        if kind == "constraint_set":
            data = problem.get("data", problem)
            return (classify_constraint_set(**{
                k: data.get(k) for k in ("A", "b", "Q", "c", "modulus")
                if data.get(k) is not None
            }), "classify_constraint_set")
        if kind == "signature":
            data = problem.get("data", problem)
            return (classify_signature(data["values"]), "classify_signature")
        # Heuristic dispatch based on dict keys.
        if "rotation" in problem:
            return classify_graph(problem["rotation"]), "classify_graph"
        if "A" in problem:
            return (classify_constraint_set(
                A=problem["A"],
                b=problem.get("b"),
                Q=problem.get("Q"),
                c=problem.get("c"),
                modulus=problem.get("modulus", 2),
            ), "classify_constraint_set")
        if "values" in problem:
            return classify_signature(problem["values"]), "classify_signature"
        return None, ""

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
