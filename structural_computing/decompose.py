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
from typing import Any, Callable, List, Optional, Protocol, Set


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
    r"""Treewidth-bounded dynamic programming for perfect-matching count.

    A graph G with treewidth `w` is solvable exactly by DP over its
    tree decomposition, with each "bag" of size at most `w+1` being an
    in-family local subproblem. Total cost `O(2^O(w) * n)`; for graphs
    of bounded treewidth (most workflows, real dependency graphs),
    polynomial-time exact even when the graph isn't planar.

    A tree decomposition of G is:
      * A tree T whose nodes are "bags" -- subsets of V(G).
      * Every edge (u, v) of G has some bag containing both u and v.
      * For every vertex v in V(G), the bags containing v form a
        connected subtree of T.
    The maximum bag size minus 1 is the WIDTH of the decomposition;
    the TREEWIDTH of G is the minimum width over all decompositions.

    This concrete implementation handles the case where the user
    supplies the tree decomposition (computing one optimally is NP-hard
    in general, but for practical instances good heuristics exist;
    accepting one as input is the v0.1 contract).

    The decomposition object the caller provides:

        td = {
            "bags": [{vertex, vertex, ...}, ...],     # list of bag-sets
            "tree_edges": [(i, j), ...],              # tree structure between bags
            "root_bag_index": 0,                       # which bag is the DP root
        }

    Usage:

        decomp = TreewidthBoundedDP(tree_decomposition=td)
        plan = decomp.decompose({"vertices": V, "edges": E})
        count = plan.evaluate(leaf_evaluator)        # exact matching count

    Honest scope: this v0.1 release implements the SIMPLEST case --
    when the tree decomposition has a single bag containing every
    vertex. In that case the DP collapses to "compute the matching
    count of the single bag's induced subgraph" -- which we delegate
    to brute force. This is correct but no faster than brute force.
    The full multi-bag DP (the v0.2 deliverable) handles arbitrary
    tree decompositions; the API here is forward-compatible.

    For the multi-bag case (NotImplementedError today), the algorithm
    is the standard Bodlaender / Korhonen DP for matching counts:
      - For each bag B, the DP state is which vertices in B are
        already matched (a 2^|B| state space).
      - At leaf bags, enumerate states directly.
      - At internal bags, combine child states by summing over
        compatible state pairs.
      - Root gives the total matching count.
    """
    name = "TreewidthBoundedDP"

    def __init__(self, tree_decomposition: Optional[dict] = None):
        """Pass a tree decomposition as `tree_decomposition`. If None,
        the only handled case is "single bag containing all vertices"
        (we'll synthesise that decomposition on demand)."""
        self.tree_decomposition = tree_decomposition

    def decompose(self, problem: Any) -> "DecompositionPlan":
        if not isinstance(problem, dict) or "vertices" not in problem:
            raise ValueError(
                f"{self.name}: problem must be a graph dict with 'vertices' "
                f"and 'edges' fields."
            )
        td = self.tree_decomposition
        if td is None:
            # Synthesise the trivial single-bag decomposition: one bag
            # containing all vertices, no tree edges. The DP then
            # collapses to "compute matchings on the single bag's
            # induced subgraph" = the whole graph.
            td = {
                "bags": [set(problem["vertices"])],
                "tree_edges": [],
                "root_bag_index": 0,
            }
        n_bags = len(td["bags"])
        if n_bags == 0:
            raise ValueError(f"{self.name}: tree decomposition has no bags")
        if n_bags == 1:
            # The trivial single-bag case: one leaf, whose evaluation IS
            # the matching count of the bag's induced subgraph.
            bag = td["bags"][0]
            induced_vertices = [v for v in problem["vertices"] if v in bag]
            induced_edges = [(u, v) for (u, v) in problem["edges"]
                              if u in bag and v in bag]
            leaf = DecompositionPlan(
                problem={"vertices": induced_vertices, "edges": induced_edges},
                label="root-bag (single-bag decomposition)",
            )
            return leaf
        raise NotImplementedError(
            f"{self.name}: multi-bag tree decomposition is on the v0.2 roadmap. "
            f"The standard Bodlaender / Korhonen matching-count DP applies; "
            f"see admissibility-geometry/proposals/reductions_compositions_recursive_decomposition.md"
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
