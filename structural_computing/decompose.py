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
import math
from typing import Any, Callable, Dict, List, Optional, Protocol, Sequence, Set, Tuple


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
    """A node of the decomposition tree.

    Three modes:
      - Leaf with a problem: `is_leaf=True` and `evaluate()` calls
        `leaf_evaluator(self.problem)`.
      - Internal node: has `children`; `evaluate()` recurses on children
        and combines their answers via `combine(child_values)`.
      - Precomputed: `has_precomputed_value=True` and `evaluate()` returns
        `precomputed_value` directly without calling leaf_evaluator. Used
        when the decomposition itself computed the answer (e.g.,
        Bodlaender-style DP that doesn't need a separate leaf evaluator).
    """
    problem: Any
    children: List["DecompositionPlan"] = dataclasses.field(default_factory=list)
    combine: Callable[[List[Any]], Any] = lambda values: values[0] if values else None
    label: str = ""
    notes: str = ""
    has_precomputed_value: bool = False
    precomputed_value: Any = None

    @property
    def is_leaf(self) -> bool:
        return not self.children

    def evaluate(self, leaf_evaluator: Callable[[Any], Any]) -> Any:
        """Walk the tree, evaluate each leaf via `leaf_evaluator`, then
        combine the children's answers at each internal node up to the
        root. If the plan has a precomputed value, return it directly
        without traversing."""
        if self.has_precomputed_value:
            return self.precomputed_value
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
        """Run the Bodlaender-style multi-bag DP over the supplied
        tree decomposition.

        Returns a :class:`DecompositionPlan` carrying a precomputed
        value (the matching count). The plan's ``evaluate(leaf)`` is
        a no-op that returns the precomputed result; the leaf
        evaluator is unused. This is intentional: the multi-bag DP
        already does the work internally, so there's nothing for a
        leaf evaluator to add.

        Single-bag mode (no tree decomposition supplied) still emits
        a leaf-style plan for the v0.1 compatibility path.
        """
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

        # Multi-bag tree decomposition: run the Bodlaender-style DP.
        # We return a special "decomposition plan" whose evaluate()
        # function performs the full DP and returns the matching count.
        return _build_multibag_plan(problem, td)


def _build_multibag_plan(problem: Any, td: dict) -> "DecompositionPlan":
    r"""Build a DecompositionPlan whose evaluator runs the multi-bag DP.

    The Bodlaender DP for perfect-matching count: at each bag B, the
    DP state is a SUBSET `S` of B representing "vertices in B that are
    already matched (via edges in the sub-tree rooted at this bag)."
    The DP value `dp[B][S]` is the number of (partial) matchings of the
    sub-graph induced by the bags in B's subtree such that B's "matched
    boundary" is exactly S.

    The DP transitions:

      Leaf bag (single child or none): enumerate internal matchings on
        B; for each, S is the matched-vertex set.

      Internal bag B with children C_1, ..., C_k:
        - For each combination of child states (S_1, ..., S_k):
            - For each vertex v in C_i \ B (forgotten): S_i MUST contain v
              (otherwise v ends up never matched, violating perfect matching).
            - For each shared vertex v in B ∩ C_i: v's matched status in
              S agrees with S_i.
        - Then within B we can match pairs of vertices in B that are
          not yet matched by any child; enumerate those internal matchings.

    At the ROOT bag, the answer is `dp[root][V(root)]` -- every vertex
    in the root bag is matched. For the global matching count we want
    `sum over S where S = V(root)` of dp[root][S].

    Implementation note: this is a STRAIGHTFORWARD-not-optimised
    implementation. Cost is `O(2^{2w} * n)` where `w = max bag size`;
    for w=O(log n) it's polynomial. Production-quality implementations
    use nice tree decompositions with introduce/forget/join nodes
    explicitly; we just iterate over the user's tree directly.
    """
    bags: List[Set[Any]] = [set(b) for b in td["bags"]]
    tree_edges: List[Tuple[int, int]] = list(td.get("tree_edges", []))
    root_idx: int = int(td.get("root_bag_index", 0))
    n_bags = len(bags)
    # Build adjacency: child relation parented at root_idx.
    adj: Dict[int, List[int]] = {i: [] for i in range(n_bags)}
    for (i, j) in tree_edges:
        adj[i].append(j)
        adj[j].append(i)
    # Root the tree at root_idx via BFS/DFS.
    parent: Dict[int, Optional[int]] = {root_idx: None}
    children: Dict[int, List[int]] = {i: [] for i in range(n_bags)}
    stack = [root_idx]
    visited = {root_idx}
    while stack:
        u = stack.pop()
        for v in adj[u]:
            if v not in visited:
                visited.add(v)
                parent[v] = u
                children[u].append(v)
                stack.append(v)
    # Post-order traversal for bottom-up DP.
    post_order: List[int] = []
    seen = set()
    stack = [(root_idx, False)]
    while stack:
        node, processed = stack.pop()
        if processed:
            post_order.append(node)
        else:
            if node in seen:
                continue
            seen.add(node)
            stack.append((node, True))
            for child in children[node]:
                stack.append((child, False))

    # All edges of G as a set for quick lookup.
    g_edges: Set[Tuple[Any, Any]] = set()
    for (u, v) in problem["edges"]:
        g_edges.add(tuple(sorted([u, v], key=str)))

    def _bag_internal_matchings(bag: Set[Any]) -> List[Set[Any]]:
        """All possible partial matchings using edges strictly inside `bag`.
        Returns a list of sets of matched vertices, one per matching.

        Each matching is enumerated exactly once via a recursion that at
        each step either (a) pairs `remaining[0]` with some `w` in
        `remaining[1:]` via an edge of G, or (b) leaves `remaining[0]`
        unmatched and recurses on `remaining[1:]`."""
        bag_list = list(bag)
        results: List[Set[Any]] = []
        def recurse(remaining: List[Any], matched: Set[Any]) -> None:
            if not remaining:
                results.append(set(matched))
                return
            v = remaining[0]
            # (a) Pair v with each compatible w.
            for i, w in enumerate(remaining[1:], start=1):
                edge = tuple(sorted([v, w], key=str))
                if edge in g_edges:
                    new_remaining = remaining[1:i] + remaining[i + 1:]
                    recurse(new_remaining, matched | {v, w})
            # (b) Leave v unmatched.
            recurse(remaining[1:], matched)
        recurse(bag_list, set())
        return results

    # DP: dp[bag_idx][frozenset(matched_vertices_in_bag)] -> count
    dp: Dict[int, Dict[frozenset, int]] = {}

    for bag_idx in post_order:
        bag = bags[bag_idx]
        if not children[bag_idx]:
            # Leaf bag.
            states: Dict[frozenset, int] = {}
            for matching in _bag_internal_matchings(bag):
                key = frozenset(matching)
                states[key] = states.get(key, 0) + 1
            dp[bag_idx] = states
            continue
        # Internal bag: combine children's states.
        # Start with a single state where nothing is matched yet, count 1.
        combined: Dict[frozenset, int] = {frozenset(): 1}
        for child in children[bag_idx]:
            child_states = dp[child]
            child_bag = bags[child]
            forgotten = child_bag - bag                  # vertices in child but not B
            shared = child_bag & bag
            new_combined: Dict[frozenset, int] = {}
            for (current_set, current_count) in combined.items():
                for (child_set, child_count) in child_states.items():
                    # Forgotten vertices MUST be matched.
                    if not forgotten.issubset(child_set):
                        continue
                    # On shared vertices, the child's matched status must agree
                    # with what we know about B's matched status so far. If a
                    # shared vertex is in current_set, the child must also have
                    # it matched -- else we'd double-count its matching status.
                    # If a shared vertex is in child_set but NOT in current_set,
                    # we incorporate it (the child's subtree matched it).
                    # Disagreement (vertex in current_set but NOT in child_set,
                    # for vertices in shared) is invalid.
                    conflict = False
                    for v in shared:
                        if v in current_set and v not in child_set:
                            conflict = True; break
                    if conflict:
                        continue
                    # Merge: union of current_set (excluding forgotten -- they're
                    # no longer in B) with the new matched-in-bag info from child.
                    merged = (current_set | (child_set & bag))
                    new_combined[merged] = (
                        new_combined.get(merged, 0)
                        + current_count * child_count
                    )
            combined = new_combined
        # Now for each state in `combined`, we can ADDITIONALLY match
        # pairs of vertices in `bag` that aren't yet matched -- using
        # edges of G inside the bag.
        states_with_internal: Dict[frozenset, int] = {}
        for (matched_so_far, count) in combined.items():
            available = bag - matched_so_far
            for additional_matching in _bag_internal_matchings(available):
                # additional_matching is the new set of matched vertices
                # added by within-bag pairing.
                final_set = matched_so_far | additional_matching
                states_with_internal[final_set] = (
                    states_with_internal.get(final_set, 0) + count
                )
        dp[bag_idx] = states_with_internal

    # The answer at the root: sum of counts for states where the FULL set
    # of root-bag vertices is matched (all root vertices are in a matching).
    root_bag = bags[root_idx]
    # For PERFECT matching: every vertex of G must be matched. The root's
    # bag may not be all of V(G); we need to check the matched set IS the
    # full root bag (which then propagates to having matched everything,
    # since forgotten vertices were required to be matched at each step).
    total = dp[root_idx].get(frozenset(root_bag), 0)

    # Wrap the precomputed total in a DecompositionPlan that returns it
    # directly when evaluate() is called -- no leaf-evaluator dispatch.
    return DecompositionPlan(
        problem=None,
        has_precomputed_value=True,
        precomputed_value=total,
        label=f"multi-bag DP ({n_bags} bags, max width {max(len(b) for b in bags) - 1})",
        notes=f"matching count = {total}",
    )


# ---------------------------------------------------------------------------
# Lipton-Tarjan planar separator (v0.4)
# ---------------------------------------------------------------------------
#
# The mathematical content
# ------------------------
# Lipton & Tarjan, *A Separator Theorem for Planar Graphs*, SIAM J.
# Appl. Math. 36(2), 1979: for any connected planar graph G on n
# vertices there is a separator S ⊆ V(G) of size |S| ≤ 2*sqrt(2*n)
# such that V(G) \ S partitions into two sets A and B with no direct
# A-B edge and |A|, |B| ≤ 2n/3. The algorithm is O(n).
#
# What this implementation ships
# ------------------------------
# The SIMPLE CASE of Lipton-Tarjan: BFS-layer from any root, find a
# level L_t such that the levels above and below it each carry at
# most 2n/3 vertices and L_t itself has at most 2*sqrt(2*n) vertices.
# When such a t exists, return (S = L_t, A = above-levels,
# B = below-levels). This case suffices for many practical planar
# graphs (grids, trees-of-grids, "wide-and-short" planar graphs).
#
# When the simple case doesn't apply (some middle level is too fat),
# the full Lipton-Tarjan algorithm falls back to a SPANNING-TREE
# FUNDAMENTAL-CYCLE argument: it picks a non-tree edge whose
# fundamental cycle in the BFS spanning tree separates the graph
# well. That argument has corner cases (degenerate spanning trees,
# non-cellular embeddings on disconnected components) that aren't
# yet implemented; in those cases the function honestly raises
# ValueError and the caller falls back to user-supplied separator.
#
# Why the simple case alone is useful
# -----------------------------------
# For any planar graph with bounded face-degree (most workflow
# graphs, dependency graphs, geometric meshes), the BFS-layer
# distribution is roughly uniform and the simple case fires. The
# fancier cases are needed mainly for adversarially-constructed
# planar graphs.
# ---------------------------------------------------------------------------


def _lipton_tarjan_separator(problem: Any
                              ) -> Tuple[Set[Any], Set[Any], Set[Any]]:
    r"""Find a planar separator ``(S, A, B)`` via the simple-case
    Lipton-Tarjan BFS-layer algorithm.

    Algorithm
    ---------
    1. BFS-layer the graph from an arbitrary root, producing levels
       ``L_0, L_1, ..., L_max``.
    2. For each candidate level ``t``, compute:
         - ``above_count`` = total vertices in ``L_0..L_{t-1}``,
         - ``below_count`` = total vertices in ``L_{t+1}..L_max``,
         - ``level_size`` = ``|L_t|``.
       Return the first ``t`` such that
         - ``above_count <= 2n/3``,
         - ``below_count <= 2n/3``,
         - ``level_size <= 2*sqrt(2*n)``
       all hold.
    3. The partition ``(S = L_t, A = above, B = below)`` is a valid
       Lipton-Tarjan separator: every edge has both endpoints in
       adjacent BFS levels (by the BFS distance property), so no
       edge bypasses ``L_t`` directly from ``A`` to ``B``.

    Parameters
    ----------
    problem : dict
        Graph dict with keys ``"vertices"`` and ``"edges"``. A
        ``"rotation"`` field is accepted but not required (the
        algorithm only consults adjacency). The graph must be
        connected; ValueError is raised on disconnected input.

    Returns
    -------
    (S, A, B) : tuple of three sets
        ``S`` is the discovered separator; ``A`` is the "above"
        side; ``B`` is the "below" side. They partition V(G).

    Raises
    ------
    ValueError
        If the simple case fails -- specifically: (a) the graph is
        disconnected (some vertex unreachable from the BFS root);
        (b) no level satisfies all three Lipton-Tarjan inequalities
        (which can happen on adversarial planar graphs and on
        non-planar graphs). The caller should fall back to a
        user-supplied separator in either case.

    Honest scope (v0.4)
    -------------------
    The full Lipton-Tarjan algorithm includes a spanning-tree
    fundamental-cycle backup case that handles "fat middle level"
    graphs. That case requires the planar embedding (rotation system)
    and has subtle corner cases (non-cellular embeddings, degenerate
    fundamental cycles); it is not yet implemented. For graphs where
    the simple case fails, the framework honestly stops and asks for
    a user-supplied separator.
    """
    if not isinstance(problem, dict) or "vertices" not in problem:
        raise ValueError(
            "_lipton_tarjan_separator expects a graph dict with "
            "'vertices' and 'edges'"
        )

    vertices = list(problem["vertices"])
    edges = list(problem["edges"])
    n = len(vertices)

    # Trivial cases: tiny graphs have no useful Lipton-Tarjan
    # partition (the separator-size bound 2*sqrt(2*n) exceeds the
    # graph size for n < 8). Return everything-in-separator.
    if n < 3:
        return set(vertices), set(), set()

    # Build adjacency. The rotation system, if present, agrees with
    # the edge list on adjacency (it just adds cyclic ordering); we
    # only need adjacency here.
    adj: Dict[Any, List[Any]] = {v: [] for v in vertices}
    for (u, w) in edges:
        # Skip self-loops -- they don't affect BFS distances.
        if u == w:
            continue
        # Avoid duplicate-edge double counting in adjacency lists.
        if w not in adj[u]:
            adj[u].append(w)
        if u not in adj[w]:
            adj[w].append(u)

    # BFS-layer from the first vertex. Any root works; the algorithm's
    # guarantees are independent of root choice (though different
    # roots may yield different valid separators).
    root = vertices[0]
    levels: List[List[Any]] = [[root]]
    seen = {root}
    while True:
        next_level: List[Any] = []
        for v in levels[-1]:
            for w in adj[v]:
                if w not in seen:
                    seen.add(w)
                    next_level.append(w)
        if not next_level:
            break
        levels.append(next_level)

    # Connectivity check: BFS reaches every vertex iff the graph is
    # connected. Lipton-Tarjan requires connectivity; if not, raise.
    if len(seen) != n:
        raise ValueError(
            f"_lipton_tarjan_separator: graph appears disconnected "
            f"({len(seen)} of {n} vertices reachable from BFS root); "
            f"Lipton-Tarjan requires a connected graph"
        )

    # Cumulative size of levels 0..t-1 (= "above" level t).
    # cum_above[0] = 0; cum_above[len(levels)] = n.
    cum_above = [0]
    for L in levels:
        cum_above.append(cum_above[-1] + len(L))

    # Lipton-Tarjan threshold values. The 2n/3 bound is the
    # theorem's "balanced partition" guarantee; the 2*sqrt(2n) bound
    # is the separator-size guarantee.
    bound_AB = 2.0 * n / 3.0
    bound_S = 2.0 * math.sqrt(2.0 * n)

    # Scan levels in order; the FIRST t satisfying all three bounds
    # is a valid separator. (Any t works; the search is deterministic
    # rather than optimal -- a future polishing pass could pick the
    # t that minimises |L_t| for tighter separators.)
    candidate: Optional[int] = None
    for t in range(len(levels)):
        above = cum_above[t]
        below = n - cum_above[t] - len(levels[t])
        level_size = len(levels[t])
        if (above <= bound_AB
                and below <= bound_AB
                and level_size <= bound_S):
            candidate = t
            break

    if candidate is None:
        # Simple case doesn't apply -- the graph has a "fat middle
        # level" where every BFS level violates either the size bound
        # or one of the partition bounds. Fall through to the v0.5
        # spanning-tree backup; if THAT also fails, the v0.6 D2 level-
        # based + articulation-augmentation backup is invoked.
        try:
            return _lipton_tarjan_tree_backup(
                vertices, adj, levels, n, bound_AB, bound_S,
            )
        except ValueError as v05_err:
            # v0.5 backup failed too. Try the v0.6 D2 level-based
            # backup. This handles star-like and K_{2,n}-like graphs
            # where the optimal separator is a small "connector" vertex
            # set in a fat BFS level.
            try:
                return _lipton_tarjan_level_backup(
                    vertices, adj, levels, n, bound_AB, bound_S,
                )
            except ValueError as v06_err:
                # All three approaches failed.
                max_level_size = max(len(L) for L in levels)
                raise ValueError(
                    f"_lipton_tarjan_separator: simple BFS-layer "
                    f"case + v0.5 tree-edge backup + v0.6 level-based "
                    f"backup ALL failed (n={n}, "
                    f"max_level_size={max_level_size}, "
                    f"2*sqrt(2n) bound={bound_S:.2f}). v0.5 said: "
                    f"{v05_err!s}. v0.6 said: {v06_err!s}. This can "
                    f"happen on adversarial planar graphs where none "
                    f"of the BFS-based approaches reach a valid "
                    f"separator, or on non-planar graphs (where the "
                    f"bound doesn't apply). Provide a user-supplied "
                    f"separator via PlanarSeparator(separator=..., "
                    f"side_a=..., side_b=...) instead."
                )

    # Build the three sets.
    S = set(levels[candidate])
    A: Set[Any] = set()
    B: Set[Any] = set()
    for i, L in enumerate(levels):
        if i < candidate:
            A.update(L)
        elif i > candidate:
            B.update(L)
    return S, A, B


# ---------------------------------------------------------------------------
# v0.5 Deliverable 2: spanning-tree fundamental-cycle backup
# ---------------------------------------------------------------------------
#
# The backup catches planar graphs where the BFS-layer simple case
# fails because every level violates either the size bound or one of
# the partition bounds. Canonical example: a "double-star" graph
# (two centers connected by an edge, each with many leaves) -- the
# obvious separator is the two centers, but the BFS-layer search
# can't find it because L_1 (containing both leaves of the first
# center and the second center) is too fat.
#
# The algorithm (a simpler form of Lipton-Tarjan 1979):
#
#   1. Build the BFS spanning tree T_BFS rooted at the BFS root.
#   2. For each tree edge e = (parent, child), compute the size of
#      the subtree rooted at `child`. The edge SPLITS the tree into
#      two parts: the subtree (size s) and the rest (size n - s).
#   3. Find a tree edge whose split is "balanced": both s and n - s
#      are at most 2n/3.
#   4. The initial separator is {parent, child} of that edge.
#      Partition: A = subtree-vertices \ {child}, B = rest \ {parent}.
#   5. Validate: walk through all NON-TREE edges. Any edge (u, v)
#      with u in A and v in B (or vice versa) is "offending" -- a
#      direct A-B crossing not through S. Add ALL non-tree-edge
#      endpoints crossing A and B to S, re-partition A and B
#      (removing the new S vertices), and re-validate. Iterate to
#      fixpoint.
#   6. Check the resulting |S| size: if |S| <= 2*sqrt(2n) (the LT
#      theorem bound), return (S, A, B). Otherwise, the backup
#      gives up.
#
# This is a SIMPLER version of LT than the original 1979 paper's
# fundamental-cycle-via-planar-dual argument. It works for many
# practical planar graphs (notably the double-star and other graphs
# with tree-like separator structure) but may not always find the
# tightest separator. The full Lipton-Tarjan 1979 algorithm using
# the planar embedding is a v0.6 deliverable.
# ---------------------------------------------------------------------------


def _lipton_tarjan_tree_backup(vertices: List[Any],
                                 adj: Dict[Any, List[Any]],
                                 levels: List[List[Any]],
                                 n: int,
                                 bound_AB: float,
                                 bound_S: float,
                                 ) -> Tuple[Set[Any], Set[Any], Set[Any]]:
    r"""Tree-edge balanced-cut backup for the Lipton-Tarjan separator
    when the BFS-layer simple case fails.

    See the section comment above for the algorithm sketch. This
    function is invoked from :func:`_lipton_tarjan_separator` when its
    simple case finds no valid level partition.

    Parameters
    ----------
    vertices : list
        The graph's vertex set.
    adj : dict
        Adjacency lists: ``adj[v]`` is the list of neighbours of v.
    levels : list of lists
        BFS levels from a single root, already computed by the caller.
    n : int
        Total vertex count.
    bound_AB : float
        ``2 * n / 3`` (Lipton-Tarjan balanced-partition bound).
    bound_S : float
        ``2 * sqrt(2 * n)`` (Lipton-Tarjan separator-size bound).

    Returns
    -------
    (S, A, B) : tuple of three sets
        A valid Lipton-Tarjan-style partition.

    Raises
    ------
    ValueError
        If no balanced tree edge exists, or if the augmentation step
        produces a separator larger than ``bound_S``. The caller
        treats this as an honest-stop signal.
    """
    # Step 1: build the BFS spanning tree from the already-computed
    # levels. The parent of each vertex (at level k > 0) is any vertex
    # in level k-1 that's adjacent to it -- BFS guarantees at least one
    # such adjacency exists. We pick the first one found, giving a
    # deterministic spanning tree.
    parent: Dict[Any, Optional[Any]] = {}
    root = levels[0][0]
    parent[root] = None
    vertex_level: Dict[Any, int] = {v: 0 for v in levels[0]}
    for lvl_idx, L in enumerate(levels[1:], start=1):
        for v in L:
            vertex_level[v] = lvl_idx
            # Find the parent: any neighbour of v in the previous level.
            for u in adj[v]:
                if vertex_level.get(u, -1) == lvl_idx - 1:
                    parent[v] = u
                    break

    # Children-map for the spanning tree.
    children: Dict[Any, List[Any]] = {v: [] for v in vertices}
    for v, p in parent.items():
        if p is not None:
            children[p].append(v)

    # Step 2: compute subtree sizes via post-order traversal.
    # ``subtree_size[v]`` = number of vertices in the sub-tree rooted
    # at v, INCLUDING v itself.
    subtree_size: Dict[Any, int] = {}
    # Post-order: iteratively process leaves first.
    order: List[Any] = []
    stack = [(root, False)]
    seen_post = set()
    while stack:
        node, processed = stack.pop()
        if processed:
            order.append(node)
        else:
            if node in seen_post:
                continue
            seen_post.add(node)
            stack.append((node, True))
            for c in children[node]:
                stack.append((c, False))
    for v in order:
        subtree_size[v] = 1 + sum(subtree_size[c] for c in children[v])

    # Step 3: find a tree edge whose split is balanced. We prefer the
    # MOST balanced cut (minimises max(s, n-s)) since that gives the
    # best chance of satisfying the 2n/3 bound on both sides.
    best_edge: Optional[Tuple[Any, Any]] = None
    best_max_side = n + 1                    # initialised to infeasible
    for v in vertices:
        if v == root:
            continue                          # root has no parent edge
        s = subtree_size[v]
        rest = n - s
        if max(s, rest) > bound_AB:
            continue                          # this cut violates 2n/3
        if max(s, rest) < best_max_side:
            best_max_side = max(s, rest)
            best_edge = (parent[v], v)

    if best_edge is None:
        raise ValueError(
            f"tree-edge backup: no balanced tree edge found "
            f"(every tree edge gives a side > 2n/3 = {bound_AB:.1f})"
        )

    edge_parent, edge_child = best_edge

    # Step 4: collect the subtree rooted at edge_child as candidate-A,
    # everything else as candidate-B. The separator starts as
    # {edge_parent, edge_child}.
    A_candidate: Set[Any] = set()
    # Walk subtree of edge_child iteratively.
    sub_stack = [edge_child]
    sub_seen = {edge_child}
    while sub_stack:
        v = sub_stack.pop()
        A_candidate.add(v)
        for c in children[v]:
            if c not in sub_seen:
                sub_seen.add(c)
                sub_stack.append(c)
    B_candidate = set(vertices) - A_candidate
    S: Set[Any] = {edge_parent, edge_child}
    A_candidate.discard(edge_child)
    B_candidate.discard(edge_parent)

    # Step 5: validate by walking all edges. A non-S edge connecting
    # A_candidate to B_candidate is a "crossing edge"; we augment S
    # with one of its endpoints (the deeper one in the tree, since
    # adding a deeper vertex tends to grow S less). Iterate until no
    # crossings remain.
    #
    # Build the edge list once. We iterate it each round; the loop is
    # O(rounds * |E|) where rounds is at most |S| (each augment-step
    # adds at least one vertex to S). For planar graphs this is
    # bounded.
    edge_list: List[Tuple[Any, Any]] = []
    seen_edges: Set[Tuple[Any, Any]] = set()
    for u in vertices:
        for v in adj[u]:
            key = (u, v) if (str(u), str(v)) <= (str(v), str(u)) else (v, u)
            if key not in seen_edges:
                seen_edges.add(key)
                edge_list.append(key)

    max_rounds = n                            # generous upper bound
    for _ in range(max_rounds):
        crossing: Optional[Tuple[Any, Any]] = None
        for (u, v) in edge_list:
            if u in S or v in S:
                continue                      # already a S-incident edge
            if (u in A_candidate) and (v in B_candidate):
                crossing = (u, v)
                break
            if (u in B_candidate) and (v in A_candidate):
                crossing = (v, u)
                break
        if crossing is None:
            break                              # valid partition reached
        # Augment S with the offending edge's endpoints, prioritising
        # the deeper one (which leaves the larger side intact).
        u_cross, v_cross = crossing
        depth_u = vertex_level.get(u_cross, 0)
        depth_v = vertex_level.get(v_cross, 0)
        if depth_u >= depth_v:
            S.add(u_cross)
            A_candidate.discard(u_cross)
            B_candidate.discard(u_cross)
        else:
            S.add(v_cross)
            A_candidate.discard(v_cross)
            B_candidate.discard(v_cross)
        # Safety: if S grows beyond the LT bound, fail early.
        if len(S) > bound_S:
            raise ValueError(
                f"tree-edge backup: separator grew to |S|={len(S)} > "
                f"2*sqrt(2n)={bound_S:.2f} during augmentation; "
                f"backup gives up"
            )
    else:
        # max_rounds exhausted without converging.
        raise ValueError(
            f"tree-edge backup: augmentation loop exceeded "
            f"max_rounds={max_rounds} without converging"
        )

    # Step 6: final size check.
    if len(S) > bound_S:
        raise ValueError(
            f"tree-edge backup: final |S|={len(S)} > 2*sqrt(2n)="
            f"{bound_S:.2f}; backup found a valid partition but the "
            f"Lipton-Tarjan size bound is violated"
        )

    return S, A_candidate, B_candidate


# ---------------------------------------------------------------------------
# v0.6 Deliverable 2: level-based + articulation augmentation backup
# (the simpler form of Lipton-Tarjan 1979's "fat middle level" case)
# ---------------------------------------------------------------------------
#
# Catches planar graphs where BOTH the v0.4 simple BFS-layer case AND
# the v0.5 tree-edge augmentation backup fail. Canonical adversarial
# examples (verified to defeat v0.5):
#
#   - star(n) = K_{1, n}: BFS gives L_0 = {root}, L_1 = {n leaves}.
#     Optimal separator is {root}, size 1. v0.5's tree-edge backup
#     can't see this because the BFS spanning tree's children of
#     root are all leaves (subtree_size = 1), so no "balanced tree
#     edge" exists.
#
#   - K_{2, n} (complete bipartite): two spine vertices + n pages.
#     BFS from spine_0 gives L_0 = {spine_0}, L_1 = {spine_1, all
#     pages}. Optimal separator is {spine_0, spine_1}, size 2.
#
# Algorithm sketch
# ----------------
# For each BFS level L_t (smallest first):
#   1. Initial S = L_t. Skip if |L_t| > bound_S.
#   2. Compute connected components of the residual graph (V \ S).
#   3. Bin-pack components into A and B with capacity 2n/3 each,
#      largest-first greedy. If feasible: return (S, A, B).
#   4. If one component is too big to fit either bin (>2n/3),
#      identify its "articulation" vertex -- the vertex whose
#      removal best splits it. Heuristic: the highest-degree
#      vertex in the component (in the residual sub-graph).
#      Add it to S; recurse step 2.
#   5. If S grows past bound_S: this level is infeasible; try
#      the next level.
#
# Why this works on the corpus
# ----------------------------
#   star(n):     L_0 = {root}, S = {root}. Residual has n isolated
#                vertices (each a separate component). Bin-pack
#                trivially. |S| = 1.
#   K_{2, n}:    L_0 = {spine_0}, S = {spine_0}. Residual is one
#                big component (spine_1 connects to all pages).
#                Augment with spine_1 (highest residual degree).
#                S = {0, 1}, residual = n isolated pages. |S| = 2.
#
# Honest scope (v0.6 D2)
# ----------------------
# This is a SIMPLIFIED form of LT 1979's fat-middle-level argument.
# The full algorithm uses the planar embedding + fundamental-cycle
# inside/outside counting via the planar dual, which gives tighter
# theoretical bounds on adversarial cases. The simplification works
# on star + K_{2,n} corpus + many practical "high-degree connector"
# planar graphs; cases where the residual has only one giant
# component AND no clear articulation vertex still raise honest-stop.
# Full LT 1979 with planar dual is a v0.7+ deliverable.
# ---------------------------------------------------------------------------


def _lipton_tarjan_level_backup(vertices: List[Any],
                                  adj: Dict[Any, List[Any]],
                                  levels: List[List[Any]],
                                  n: int,
                                  bound_AB: float,
                                  bound_S: float,
                                  ) -> Tuple[Set[Any], Set[Any], Set[Any]]:
    r"""Level-based separator with articulation-augmentation backup.

    See the section comment above for the algorithm sketch. Invoked
    from :func:`_lipton_tarjan_separator` when BOTH the simple
    BFS-layer case AND the v0.5 tree-edge augmentation backup have
    failed.

    Parameters
    ----------
    vertices : list
        The graph's vertex set.
    adj : dict
        Adjacency lists (built by the caller).
    levels : list of lists
        BFS levels from a single root.
    n : int
        Total vertex count.
    bound_AB : float
        ``2 * n / 3`` (Lipton-Tarjan balanced-partition bound).
    bound_S : float
        ``2 * sqrt(2 * n)`` (Lipton-Tarjan separator-size bound).

    Returns
    -------
    (S, A, B) : tuple of three sets
        A valid Lipton-Tarjan-style partition.

    Raises
    ------
    ValueError
        If no level admits a balanced partition within the LT bounds
        even after articulation augmentation.
    """
    # Try each level as a candidate separator, smallest first --
    # smaller levels give a smaller initial S that has more room to
    # grow via augmentation before hitting bound_S.
    levels_by_size = sorted(range(len(levels)), key=lambda t: len(levels[t]))
    last_err: Optional[str] = None
    for t in levels_by_size:
        if len(levels[t]) > bound_S:
            # Even before any augmentation, this level is already
            # too fat -- skip.
            continue
        try:
            return _try_level_separator(
                t, vertices, adj, levels, n, bound_AB, bound_S,
            )
        except ValueError as e:
            last_err = str(e)
            continue

    raise ValueError(
        f"level-based backup found no valid level separator "
        f"(tried {len(levels_by_size)} levels); last error: {last_err}"
    )


def _try_level_separator(t: int,
                          vertices: List[Any],
                          adj: Dict[Any, List[Any]],
                          levels: List[List[Any]],
                          n: int,
                          bound_AB: float,
                          bound_S: float,
                          ) -> Tuple[Set[Any], Set[Any], Set[Any]]:
    r"""Try level t as the separator nucleus, augmenting with
    articulation vertices if needed.

    Algorithm
    ---------
    1. S = level t initially.
    2. Compute connected components of the residual graph V \ S.
    3. Bin-pack components into A (capacity 2n/3) and B (capacity
       2n/3). Largest component first.
    4. If a component is too big for either bin, identify its
       highest-degree vertex (in the residual sub-graph), add to S,
       and retry step 2.
    5. Terminate with success if bin-packing succeeds; with
       ValueError if S exceeds bound_S or no articulation vertex
       can reduce the biggest component.

    Raises
    ------
    ValueError
        On infeasibility (too-big component without splittable
        articulation, or |S| > bound_S).
    """
    S: Set[Any] = set(levels[t])
    # Track the "non-S" vertices to bin-pack.
    rest: Set[Any] = set(vertices) - S

    # Augmentation loop. Bounded by len(rest) iterations (each
    # iteration adds at least one vertex to S).
    for _ in range(len(rest) + 1):
        # 2. Compute connected components of rest in the residual
        # graph (where S vertices are excluded from adjacency).
        components = _connected_components_in_residual(rest, adj, S)

        # 3. Largest-first bin-pack into A (cap bound_AB) + B (same).
        components_sorted = sorted(components, key=len, reverse=True)
        A: Set[Any] = set()
        B: Set[Any] = set()
        too_big_component: Optional[Set[Any]] = None
        for comp in components_sorted:
            sz = len(comp)
            # Check if this single component already exceeds bound_AB.
            if sz > bound_AB:
                too_big_component = comp
                break
            # Otherwise place in the bin with more room.
            if len(A) + sz <= bound_AB and (
                len(B) + sz > bound_AB or len(A) <= len(B)
            ):
                A.update(comp)
            elif len(B) + sz <= bound_AB:
                B.update(comp)
            else:
                # Neither bin has room for this component (despite
                # individual size <= bound_AB). Both bins are full.
                # This means total non-S vertices > 2 * bound_AB,
                # so the level itself is too dense -- give up on this
                # level.
                raise ValueError(
                    f"level t={t}: total rest-vertices "
                    f"({len(rest)}) > 2 * bound_AB ({2 * bound_AB:.1f})"
                )

        if too_big_component is None:
            # Bin-packing succeeded. Final size check.
            if len(S) > bound_S:
                raise ValueError(
                    f"level t={t}: bin-pack succeeded but final |S|="
                    f"{len(S)} > 2*sqrt(2n) = {bound_S:.2f}"
                )
            return S, A, B

        # 4. Augment: find the highest-residual-degree vertex in the
        # too-big component, add it to S, retry. This is a heuristic
        # for "articulation vertex": vertices that touch many others
        # are good candidates for separator membership.
        def residual_degree(v):
            return sum(1 for u in adj[v] if u in too_big_component and u != v)

        articulator = max(too_big_component, key=residual_degree)
        S.add(articulator)
        rest.discard(articulator)

        # Bail early if |S| exceeds bound.
        if len(S) > bound_S:
            raise ValueError(
                f"level t={t}: |S| grew past 2*sqrt(2n) = {bound_S:.2f} "
                f"after augmentation (|S|={len(S)})"
            )

    # Shouldn't reach here -- the loop has a guard. But if we do,
    # something is structurally wrong.
    raise ValueError(
        f"level t={t}: augmentation loop did not converge within "
        f"{len(rest) + 1} rounds"
    )


def _connected_components_in_residual(rest: Set[Any],
                                        adj: Dict[Any, List[Any]],
                                        S: Set[Any],
                                        ) -> List[Set[Any]]:
    r"""Connected components of the sub-graph induced on ``rest``
    (i.e., ``V \ S``) in the residual graph.

    Edges from a vertex u in rest to S are IGNORED (we're computing
    components in the residual graph after removing S). Two vertices
    u, v in rest are in the same component iff there's a path in
    rest connecting them (using only intra-rest edges).
    """
    seen: Set[Any] = set()
    components: List[Set[Any]] = []
    for start in rest:
        if start in seen:
            continue
        comp: Set[Any] = set()
        stack = [start]
        while stack:
            v = stack.pop()
            if v in seen:
                continue
            seen.add(v)
            comp.add(v)
            for u in adj[v]:
                if u in rest and u not in seen and u not in S:
                    stack.append(u)
        components.append(comp)
    return components


class PlanarSeparator:
    r"""Divide-and-conquer decomposition: split the graph into two halves
    along a vertex separator, recurse on each side, combine via a sum
    over separator-vertex match patterns.

    The separator can be either USER-SUPPLIED (the v0.3 mode -- pass
    ``separator``, ``side_a``, ``side_b`` explicitly) or AUTO-DISCOVERED
    via Lipton-Tarjan 1979 (the v0.4 mode -- pass ``auto=True``).

    Mathematics
    -----------
    For PERFECT-MATCHING COUNT, the decomposition is:

        PerfMatch(G) = sum over (S_to_A, S_to_B, S_pairs) of
            (prod over (s,t) in S_pairs of w(s,t))
            * PerfMatch(side_a sub-graph plus S_to_A)
            * PerfMatch(side_b sub-graph plus S_to_B)

    where the sum is over partitions of the separator vertices into:
      - ``S_to_A``: matched to a vertex in ``side_a``,
      - ``S_to_B``: matched to a vertex in ``side_b``,
      - ``S_pairs``: pairs of separator vertices matched to each other.

    For ``|S| = k``, the partition count is roughly ``O(3^k * k!)`` --
    tractable for the small separators that planar graphs admit
    (``|S| = O(sqrt(|V|))`` by Lipton-Tarjan).

    Use (manual / v0.3 mode)
    ------------------------
    ::

        decomp = PlanarSeparator(separator={2, 3},
                                  side_a={0, 1}, side_b={4, 5})
        plan = decomp.decompose(graph)
        answer = plan.evaluate(brute_force_count_matchings_leaf)

    Use (auto / v0.4 mode)
    ----------------------
    ::

        decomp = PlanarSeparator(auto=True)
        plan = decomp.decompose(graph)        # Lipton-Tarjan finds (S, A, B)
        answer = plan.evaluate(brute_force_count_matchings_leaf)

    The auto mode is best-effort: when the simple case of Lipton-
    Tarjan fails (typically: adversarial planar graphs with a fat
    middle BFS level, or non-planar inputs), ``decompose()`` raises
    ``ValueError`` and the caller should fall back to manual mode.
    """
    name = "PlanarSeparator"

    def __init__(self,
                  separator: Optional[Set] = None,
                  side_a: Optional[Set] = None,
                  side_b: Optional[Set] = None,
                  *,
                  auto: bool = False):
        r"""Construct either a manual or auto-discovery separator.

        Parameters
        ----------
        separator, side_a, side_b : set, optional
            The three sets must partition the graph's vertex set
            (disjoint + covering) when ``auto=False``. Ignored when
            ``auto=True``.
        auto : bool
            When True, the separator is discovered via Lipton-Tarjan
            in :meth:`decompose`; ``separator/side_a/side_b`` may be
            omitted. When False (default), all three sets must be
            supplied.

        Raises
        ------
        ValueError
            When ``auto=False`` and any of the three sets is missing.
        """
        self.auto = bool(auto)
        if self.auto:
            # Defer set-population to decompose() time, when the
            # actual graph is available.
            self.separator: Optional[Set] = None
            self.side_a:    Optional[Set] = None
            self.side_b:    Optional[Set] = None
        else:
            # v0.3 manual mode: require all three sets up front.
            if separator is None or side_a is None or side_b is None:
                raise ValueError(
                    f"{self.name}: must provide separator/side_a/"
                    f"side_b (or set auto=True for Lipton-Tarjan "
                    f"auto-discovery)"
                )
            self.separator = set(separator)
            self.side_a    = set(side_a)
            self.side_b    = set(side_b)

    def decompose(self, problem: Any) -> "DecompositionPlan":
        """Build the separator-decomposition tree for ``problem``.

        Returns a :class:`DecompositionPlan` whose top-level combines
        (sums) over all valid ``(S_to_A, S_to_B, S_pairs)`` partitions
        of the separator vertices. Each child has two leaf sub-graphs
        (A-side and B-side) and a per-child combine that multiplies
        their evaluated PerfMatches by the S-pairs weight.

        Raises ``ValueError`` if ``problem`` isn't a graph dict, if the
        three sets don't partition the vertex set, or if any edge
        crosses ``side_a`` -> ``side_b`` directly (proof that the
        supplied set isn't a real separator). See the class docstring
        for the full algorithm.
        """
        if not isinstance(problem, dict) or "vertices" not in problem:
            raise ValueError(
                f"{self.name}: expects a graph dict with 'vertices' and 'edges'"
            )

        # v0.4 auto-discovery: when the constructor received auto=True,
        # invoke Lipton-Tarjan now that the actual graph is available.
        # We always re-discover (rather than caching) so that one
        # auto-instance can be applied to multiple graphs. The helper
        # raises ValueError if the simple case doesn't apply; we let
        # that propagate so the caller knows to fall back to a
        # user-supplied separator.
        if self.auto:
            self.separator, self.side_a, self.side_b = \
                _lipton_tarjan_separator(problem)

        verts   = set(problem["vertices"])
        edges   = list(problem["edges"])
        weights = dict(problem.get("weights", {}))
        # Partition checks.
        if self.side_a | self.side_b | self.separator != verts:
            raise ValueError(
                f"{self.name}: side_a + side_b + separator must cover all vertices"
            )
        if (self.side_a & self.side_b
                or self.side_a & self.separator
                or self.side_b & self.separator):
            raise ValueError(
                f"{self.name}: side_a, side_b, separator must be disjoint"
            )
        # Verify the separator is a real separator: no edge directly
        # connects side_a to side_b without passing through the
        # separator.
        for (u, v) in edges:
            if (u in self.side_a and v in self.side_b) \
                    or (u in self.side_b and v in self.side_a):
                raise ValueError(
                    f"{self.name}: edge {(u, v)} crosses sides without "
                    f"going through the separator -- not a valid separator"
                )

        def _w(u, v):
            return float(weights.get((u, v), weights.get((v, u), 1.0)))

        # Enumerate S vertices' partitions: each s is either in S_to_A,
        # S_to_B, or paired with some other s'. Use a recursive
        # enumeration.
        sep_list = list(self.separator)
        partitions: List[Any] = []                       # (S_to_A, S_to_B, S_pairs)
        s_edges = [(u, v) for (u, v) in edges
                    if u in self.separator and v in self.separator]

        def _enumerate(idx: int, assigned: dict, pairs: list):
            if idx == len(sep_list):
                s_to_a = {v for v, role in assigned.items() if role == "A"}
                s_to_b = {v for v, role in assigned.items() if role == "B"}
                partitions.append((s_to_a, s_to_b, list(pairs)))
                return
            v = sep_list[idx]
            if v in assigned:
                _enumerate(idx + 1, assigned, pairs)
                return
            # Option 1: assign to A.
            assigned[v] = "A"
            _enumerate(idx + 1, assigned, pairs)
            del assigned[v]
            # Option 2: assign to B.
            assigned[v] = "B"
            _enumerate(idx + 1, assigned, pairs)
            del assigned[v]
            # Option 3: pair with a later unassigned vertex via an existing S-S edge.
            for (u, w) in s_edges:
                if u == v and w not in assigned and sep_list.index(w) > idx:
                    other = w
                elif w == v and u not in assigned and sep_list.index(u) > idx:
                    other = u
                else:
                    continue
                assigned[v]     = "P"
                assigned[other] = "P"
                pairs.append((v, other))
                _enumerate(idx + 1, assigned, pairs)
                pairs.pop()
                del assigned[v]
                del assigned[other]

        _enumerate(0, {}, [])

        # Build a plan child per partition. Each child has TWO leaves
        # (A-side sub-graph, B-side sub-graph); the child combine
        # multiplies them by the S-pairs weight.
        plan_children: List["DecompositionPlan"] = []
        for (s_to_a, s_to_b, s_pairs) in partitions:
            pair_weight = 1.0
            for (u, v) in s_pairs:
                pair_weight *= _w(u, v)
            a_verts = self.side_a | s_to_a
            b_verts = self.side_b | s_to_b
            a_edges = [(u, v) for (u, v) in edges
                        if u in a_verts and v in a_verts
                        and not (u in self.separator and v in self.separator)]
            b_edges = [(u, v) for (u, v) in edges
                        if u in b_verts and v in b_verts
                        and not (u in self.separator and v in self.separator)]
            sub_a = {
                "vertices": list(a_verts),
                "edges":    a_edges,
                "weights":  {e: _w(*e) for e in a_edges},
            }
            sub_b = {
                "vertices": list(b_verts),
                "edges":    b_edges,
                "weights":  {e: _w(*e) for e in b_edges},
            }
            def _make_combine(pw):
                def _combine(values):
                    return pw * values[0] * values[1]
                return _combine
            plan_children.append(DecompositionPlan(
                problem=None,
                children=[
                    DecompositionPlan(problem=sub_a, label="A-side"),
                    DecompositionPlan(problem=sub_b, label="B-side"),
                ],
                combine=_make_combine(pair_weight),
                label=(f"pattern[|S_to_A|={len(s_to_a)}, "
                        f"|S_to_B|={len(s_to_b)}, |pairs|={len(s_pairs)}]"),
            ))

        return DecompositionPlan(
            problem=problem,
            children=plan_children,
            combine=lambda vs: sum(vs),
            label=f"PlanarSeparator(|S|={len(self.separator)})",
            notes=f"enumerated {len(partitions)} separator partition patterns",
        )


class RecursiveCircuitCut:
    r"""Cut a circuit / graph along a set of wires (edges) and recurse
    by enumerating each wire's two states.

    For PERFECT-MATCHING COUNT, the "two states" of a cut edge are
    "in the matching" (forced; remove both endpoints) and "out of the
    matching" (forced; remove the edge). The decomposition is the
    standard Tutte / Lovasz-Plummer identity applied independently to
    each cut edge:

        M(G) = sum over T subseteq cut of
                  (prod_{e in T} w(e)) * M(G with T's endpoints removed
                                            and (cut \ T) deleted)

    For ``|cut| = k``, this enumerates ``2^k`` sub-problems -- the same
    branching cost as :class:`structural_computing.HybridDecomposition`,
    but presented as a decomposition tree rather than a reduction
    (so it composes naturally with the rest of the framework's
    decomposition layer: ``DecompositionPlan`` carries the tree,
    ``leaf_evaluator`` evaluates leaves, ``combine`` sums them).

    Recursive cuts: the caller may chain RCC objects on the resulting
    sub-problems if a single cut doesn't fully reduce the graph;
    sequential cuts give ``2^(k_1 + k_2 + ...)`` leaves overall,
    matching the cost of a single ``HybridDecomposition`` with the
    union of all cut edges. The advantage is that intermediate plans
    are inspectable and can be combined / re-evaluated independently.

    Use::

        rcc = RecursiveCircuitCut(cut=[(0, 2), (1, 3)])
        plan = rcc.decompose(K_4_graph)
        # plan has 2^2 = 4 leaves, each a sub-graph with 0/1/2 of the
        # cut edges forced in or out of the matching.
        answer = plan.evaluate(brute_force_count_matchings_leaf)
    """
    name = "RecursiveCircuitCut"

    def __init__(self, cut: Sequence[Tuple]):
        """``cut`` is the iterable of edges to cut. Each is a tuple
        ``(u, v)``."""
        self.cut: List[Tuple] = [tuple(e) for e in cut]

    def decompose(self, problem: Any) -> "DecompositionPlan":
        """Build the circuit-cut decomposition tree for ``problem``.

        Returns a :class:`DecompositionPlan` whose top-level sums over
        the ``2^|cut|`` subsets of the cut edges. Each subset specifies
        which cut edges are forced INTO the matching (their endpoints
        removed) and which are forced OUT (the edges deleted). Each
        child carries a single leaf sub-graph and a combine that
        multiplies the leaf's evaluated PerfMatch by the forced-in
        weight product.

        Subsets where two forced-in edges share a vertex are PRUNED
        (the matching can't contain both); the actual number of
        children is at most ``2^|cut|`` but may be smaller.

        Raises ``ValueError`` if ``problem`` isn't a graph dict, or if
        any cut edge is not present in the graph.
        """
        if not isinstance(problem, dict) or "vertices" not in problem:
            raise ValueError(
                f"{self.name}: expects a graph dict with 'vertices' and 'edges'"
            )
        vertices = list(problem["vertices"])
        edges    = list(problem["edges"])
        weights  = dict(problem.get("weights", {}))

        def _w(u, v):
            return float(weights.get((u, v), weights.get((v, u), 1.0)))

        # Validate the cut edges are in the graph.
        def _key(e):
            (u, v) = e
            return (u, v) if (str(u), str(v)) <= (str(v), str(u)) else (v, u)
        edge_keys = {_key(e) for e in edges}
        cut_keys = [_key(e) for e in self.cut]
        for (orig, key) in zip(self.cut, cut_keys):
            if key not in edge_keys:
                raise ValueError(
                    f"{self.name}: cut edge {orig} is not present in the graph"
                )

        # Enumerate subsets T of the cut.
        plan_children: List["DecompositionPlan"] = []
        n_cut = len(self.cut)
        for mask in range(2 ** n_cut):
            forced_in: List[Tuple] = []
            forced_out: List[Tuple] = []
            for i in range(n_cut):
                if (mask >> i) & 1:
                    forced_in.append(self.cut[i])
                else:
                    forced_out.append(self.cut[i])
            # Check forced-in subset is a valid partial matching
            # (no shared vertex among the forced-in edges).
            seen = set()
            valid = True
            for (u, v) in forced_in:
                if u in seen or v in seen:
                    valid = False
                    break
                seen.update((u, v))
            if not valid:
                continue
            # Build sub-graph: remove forced-in endpoints; delete forced-
            # out edges; keep everything else.
            forced_out_keys = {_key(e) for e in forced_out}
            removed_vertices = seen
            sub_vertices = [v for v in vertices if v not in removed_vertices]
            sub_edges = []
            sub_weights: Dict[Tuple, float] = {}
            for e in edges:
                if _key(e) in forced_out_keys:
                    continue
                if e[0] in removed_vertices or e[1] in removed_vertices:
                    continue
                sub_edges.append(e)
                sub_weights[e] = _w(*e)
            # Pre-multiply the forced-in edges' weights into the leaf
            # combine function so the leaf evaluator just sees a clean
            # sub-graph.
            forced_in_weight = 1.0
            for (u, v) in forced_in:
                forced_in_weight *= _w(u, v)

            sub_problem = {
                "vertices": sub_vertices,
                "edges": sub_edges,
                "weights": sub_weights,
            }
            def _make_combine(w):
                def _combine(values):
                    return w * (values[0] if values else 1)
                return _combine
            plan_children.append(DecompositionPlan(
                problem=None,
                children=[
                    DecompositionPlan(problem=sub_problem, label="sub-graph"),
                ],
                combine=_make_combine(forced_in_weight),
                label=(f"mask=0b{mask:0{n_cut}b}, "
                        f"forced_in={forced_in}, forced_out={forced_out}, "
                        f"weight={forced_in_weight:g}"),
            ))

        return DecompositionPlan(
            problem=problem,
            children=plan_children,
            combine=lambda vs: sum(vs),
            label=f"RecursiveCircuitCut(|cut|={n_cut})",
            notes=(f"enumerated {len(plan_children)} valid sub-problems "
                   f"(of 2^{n_cut} = {2**n_cut} subsets; invalid forced-in "
                   f"patterns -- shared endpoints -- pruned)"),
        )


__all__ = [
    "Decomposition",
    "DecompositionPlan",
    "ShannonExpansion",
    "TreewidthBoundedDP",
    "PlanarSeparator",
    "RecursiveCircuitCut",
]
