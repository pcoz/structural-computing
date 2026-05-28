r"""The recursive-decomposition layer -- split a problem into sub-problems,
base case in-family.

Where `transform.py` ships a problem through one-shot reductions and
`compose.py` combines multiple in-family evaluations, this module
recursively splits a problem into smaller sub-problems, base case being
in-family. Most known FPT (fixed-parameter-tractable) algorithms live
in this layer.

The mental model is divide-and-conquer with structural splitting:

  * The problem doesn't yet match the in-family shape.
  * Recursively decompose by some structural parameter (treewidth, a
    cut vertex, a free variable to branch on, a circuit cut).
  * At each leaf of the recursion, the sub-problem IS in-family.
  * Combine the leaf answers back up through the recursion tree.

This v0.1 release ships:

  * The `Decomposition` protocol that every concrete decomposition
    conforms to.
  * The `DecompositionPlan` dataclass for inspecting a decomposition tree.
  * One concrete decomposition: `ShannonExpansion` -- branch on a single
    binary variable; each branch is a smaller sub-problem.
  * Sketches of upcoming decompositions (`TreewidthBoundedDP`,
    `PlanarSeparator`, `RecursiveCircuitCut`) raised as
    `NotImplementedError` with docstrings.

The full set of planned decompositions lives in
admissibility-geometry/proposals/reductions_compositions_recursive_decomposition.md.
"""
import dataclasses
from typing import Any, Callable, List, Optional, Protocol


# ---------------------------------------------------------------------------
# Base protocol
# ---------------------------------------------------------------------------

class Decomposition(Protocol):
    """A recursive decomposition produces a tree of sub-problems whose
    leaves are in-family. The framework recursively walks the tree,
    evaluating each leaf and combining sub-tree answers.

    The contract:

      1. `decompose(problem)` returns a `DecompositionPlan` -- a
         lazily-evaluated tree.

      2. Each leaf of the tree (`children == []`) carries an in-family
         `problem` that the framework can evaluate directly.

      3. Each internal node carries a `combine` function that takes the
         list of child answers and returns the answer to its own
         sub-problem.

      4. Decomposition is PURE -- it doesn't mutate its inputs.
    """
    name: str

    def decompose(self, problem: Any) -> "DecompositionPlan":
        ...


@dataclasses.dataclass
class DecompositionPlan:
    """A node of the decomposition tree. Leaves have `children = []`;
    internal nodes carry a `combine` that merges child answers."""
    problem: Any
    children: List["DecompositionPlan"] = dataclasses.field(default_factory=list)
    combine: Callable[[List[Any]], Any] = lambda values: values[0] if values else None
    label: str = ""
    notes: str = ""

    @property
    def is_leaf(self) -> bool:
        return not self.children

    def evaluate(self, leaf_evaluator: Callable[[Any], Any]) -> Any:
        """Walk the tree, evaluate each leaf via `leaf_evaluator`, then
        combine the children's answers at each internal node up to the
        root."""
        if self.is_leaf:
            return leaf_evaluator(self.problem)
        child_values = [c.evaluate(leaf_evaluator) for c in self.children]
        return self.combine(child_values)


# ---------------------------------------------------------------------------
# Concrete decomposition: ShannonExpansion
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class ShannonExpansion:
    """Branch on a single binary variable: `f(x_1, ..., x_n) =
    f(0, x_2, ..., x_n) | f(1, x_2, ..., x_n)` where the recombination
    rule depends on what we're computing.

    For counting: `count(f) = count(f|x=0) + count(f|x=1)`.
    For expected value: weighted sum of the two branches.
    For probability: weighted sum with weights from x's prior.

    Recursing all the way down gives Shannon expansion: a 2^n leaf
    decomposition. The framework only goes far enough to make each leaf
    in-family.

    Use case: a boolean function that's not directly matchgate-realisable
    but each restriction (substituting one variable) IS matchgate-
    realisable.
    """
    name: str = "ShannonExpansion"
    variable: str = ""             # which variable to branch on
    combiner: Callable[[List[Any]], Any] = lambda values: sum(values)

    def decompose(self, problem: Any) -> DecompositionPlan:
        """Branch the problem on `self.variable`. Returns a two-child
        DecompositionPlan: child 0 is the problem with `variable = 0`,
        child 1 is the problem with `variable = 1`.

        This relies on `problem` providing a `restrict(variable, value)`
        method that produces the restricted sub-problem. Different
        problem types implement this differently; for the simplest case
        (a Holant problem with explicit binary variables), `restrict`
        substitutes the variable and returns a smaller Holant problem.
        """
        if not hasattr(problem, "restrict"):
            raise ValueError(
                f"ShannonExpansion: `problem` of type {type(problem).__name__} "
                f"must provide a `restrict(variable, value)` method"
            )
        child_0 = DecompositionPlan(
            problem=problem.restrict(self.variable, 0),
            label=f"{self.variable}=0",
        )
        child_1 = DecompositionPlan(
            problem=problem.restrict(self.variable, 1),
            label=f"{self.variable}=1",
        )
        return DecompositionPlan(
            problem=problem,
            children=[child_0, child_1],
            combine=self.combiner,
            label=f"Shannon({self.variable})",
            notes=f"branching on {self.variable}; combiner=count-sum",
        )


# ---------------------------------------------------------------------------
# Sketches of upcoming decompositions
# ---------------------------------------------------------------------------

class TreewidthBoundedDP:
    """Treewidth-bounded dynamic programming. A graph with treewidth `w`
    is solvable exactly by recursing on its tree-decomposition, with
    each bag of size `w+1` being an in-family Holant problem.

    For workflows / dependency graphs with bounded local connectivity
    (most real cases), the treewidth is small even when the graph isn't
    planar. Treewidth-bounded DP gives exact answers in `O(2^w * n)`.

    Status: not implemented in v0.1. The tree-decomposition computation
    itself is NP-hard in general but has good heuristics; the per-bag
    Holant evaluation is the framework's existing in-family path.
    """
    name = "TreewidthBoundedDP"

    def decompose(self, problem):
        raise NotImplementedError(
            f"{self.name} is on the v0.2 roadmap."
        )


class PlanarSeparator:
    """Lipton-Tarjan planar-separator divide-and-conquer. A planar graph
    of n vertices has a `O(sqrt(n))` separator that splits it into two
    halves each of size at most `2n/3`. Recursively decomposing on
    separators gives `O(n^1.5)` algorithms for some structural problems
    on planar graphs that are otherwise cubic.

    Status: not implemented in v0.1. The separator construction is
    well-understood (Lipton-Tarjan 1979); wiring it into the framework
    is the v0.2 deliverable.
    """
    name = "PlanarSeparator"

    def decompose(self, problem):
        raise NotImplementedError(
            f"{self.name} is on the v0.2 roadmap."
        )


class RecursiveCircuitCut:
    """The hybrid-dispatcher's circuit-cutting pattern, lifted to
    arbitrary N-way splits and recursive sub-cuts. At each cut, the
    framework chooses the cut that best separates the structural shape;
    recursive sub-cuts handle pieces that themselves don't yet fit.

    Status: the binary form (cut into two halves) exists for circuits
    in `hybrid-dispatcher/hybrid_dispatcher.py`. Lifting to a recursive
    N-way primitive is the v0.2 deliverable.
    """
    name = "RecursiveCircuitCut"

    def decompose(self, problem):
        raise NotImplementedError(
            f"{self.name} is on the v0.2 roadmap (the binary cut "
            f"specialisation is in hybrid_dispatcher.py)."
        )


__all__ = [
    "Decomposition",
    "DecompositionPlan",
    "ShannonExpansion",
    "TreewidthBoundedDP",
    "PlanarSeparator",
    "RecursiveCircuitCut",
]
