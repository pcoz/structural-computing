"""10 -- Eliminating a crossing with the Cai-Gorenstein gadget.

K_4 drawn as a square with the two diagonals (0,2) and (1,3) crossing
at the centre. The CrossingElimination reduction inserts the
6-vertex/7-edge Cai-Gorenstein gadget at the crossing, producing a
genuinely planar graph.

What the gadget preserves:
  * The matchgate SIGNATURE (signed Pfaffian sum) of the original
    non-planar graph -- equal to the matching SUM with overlapping-
    chord-pairs contributing a -1 sign.

What it does NOT preserve in general:
  * The unsigned PerfMatch of the original. For K_4 with unit weights
    the two values happen to coincide (both equal 3), but for
    weighted edges they diverge: e.g. K_4 with diagonal weights 11
    and 13 has true PerfMatch = 174 but the planarised graph has
    signed sum = 12 (where the {02, 13} matching's contribution gets
    flipped from +143 to -143 by the gadget's -1 spine).

For unsigned weighted PerfMatch on non-planar graphs, the framework's
recommended tool is HybridDecomposition (exact, no sign artefacts).
"""
from structural_computing import (
    CrossingElimination, brute_force_count_matchings,
    brute_force_weighted_matching_sum,
)

# K_4 vertex labelling: 0 top, 1 right, 2 bottom, 3 left (on the convex
# hull). The two diagonals (0, 2) and (1, 3) cross at the centre.
graph = {
    "vertices": [0, 1, 2, 3],
    "edges": [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2), (1, 3)],
    "weights": {e: 1 for e in [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2), (1, 3)]},
}

print("Original K_4 (non-planar drawing, 1 crossing):")
print(f"  vertices: {len(graph['vertices'])}")
print(f"  edges:    {len(graph['edges'])}")
print(f"  PerfMatch (unit weights): "
       f"{brute_force_count_matchings(graph['vertices'], graph['edges'])}")
print()

# Apply the Cai-Gorenstein gadget at the (0,2)x(1,3) crossing.
ce = CrossingElimination(crossings=[((0, 2), (1, 3))])
result = ce.apply(graph)

print(f"After CrossingElimination ({result.notes}):")
print(f"  vertices: {len(result.problem['vertices'])}  "
       f"(added 6: 4 fresh pins + 2 fresh internals)")
print(f"  edges:    {len(result.problem['edges'])}  "
       f"(removed 2 crossings + added 4 segments + 7 gadget = +9 net)")

# Count the -1 spine edge (there should be exactly one per crossing).
spines = [(e, w) for e, w in result.problem["weights"].items() if w == -1]
print(f"  spine(s): {spines}")
print()

planarised_sum = brute_force_weighted_matching_sum(
    result.problem["vertices"],
    result.problem["edges"],
    result.problem["weights"],
)
print(f"Planarised PerfMatch (= matchgate signature value):")
print(f"  {planarised_sum}")
print(f"  matches original K_4 PerfMatch (unit weights, coincidence): {planarised_sum == 3}")
