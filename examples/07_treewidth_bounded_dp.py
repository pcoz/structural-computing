"""07 -- Multi-bag TreewidthBoundedDP for matching count on bounded-
treewidth graphs.

Many "natural" non-planar graphs have bounded TREEWIDTH -- even when they
fail the planar test, they have a tree-like structural decomposition that
keeps a Bodlaender-style DP cheap. This example shows the orchestrator
falling back to TreewidthBoundedDP when given a tree-decomposition hint.

The tree decomposition is a user-supplied object:

    {
        "bags": [set_of_vertices, ...],         # the bags
        "tree_edges": [(i, j), ...],              # tree structure between bags
        "root_bag_index": 0,                       # which bag is the root
    }

The orchestrator runs the Bodlaender DP and returns the exact matching
count in `O(2^O(w) * n)` time, where w = max bag size.
"""
from structural_computing import (
    Orchestrator, DEFAULT_LEAF_REGISTRY, brute_force_count_matchings,
)

# A 6-cycle (C_6) -- it's planar so direct dispatch would work, but the
# point here is to demonstrate the treewidth-DP path. We construct an
# orchestrator without the matching_count leaf entry so the treewidth-DP
# phase fires.
C6_vertices = [0, 1, 2, 3, 4, 5]
C6_edges = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 0)]

# A valid path decomposition of C_6 -- 4 bags, max size 3 (treewidth 2):
td_C6 = {
    "bags": [{0, 1, 5}, {1, 2, 5}, {2, 3, 5}, {3, 4, 5}],
    "tree_edges": [(0, 1), (1, 2), (2, 3)],
    "root_bag_index": 0,
}

# Build the C_6 problem (rotation is irrelevant for the DP path).
C6 = {
    "rotation": {0: [1, 5], 1: [0, 2], 2: [1, 3],
                  3: [2, 4], 4: [3, 5], 5: [4, 0]},
    "vertices": C6_vertices,
    "edges": C6_edges,
}

# Build an orchestrator without matching_count direct-dispatch so the
# treewidth-DP path fires.
reg = {k: v for k, v in DEFAULT_LEAF_REGISTRY.items() if k[1] != "matching_count"}
orch = Orchestrator(leaf_registry=reg)

result = orch.evaluate(C6, question="matching_count",
                         hints={"tree_decomposition": td_C6})

print(f"C_6 matching count via TreewidthBoundedDP: {result.answer}")
print(f"  brute force says:                          "
       f"{brute_force_count_matchings(C6_vertices, C6_edges)}")
print()
print(f"Reductions applied: {result.reductions_applied}")
print()
print("Workflow trace (each Orchestrator phase that fired):")
for step in result.workflow_trace:
    print(f"  [{step.phase}] {step.action}  ->  {step.outcome}")
    if step.detail:
        print(f"      detail: {step.detail}")
