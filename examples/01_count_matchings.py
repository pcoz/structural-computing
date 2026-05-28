"""01 — Count perfect matchings exactly on small graphs.

`sc.count_matchings(graph)` returns the exact integer count of perfect
matchings, via FKT (planar) or genus-g Kasteleyn (bounded genus).

For graphs that fit the matchgate-Holant family, the answer is
polynomial-time exact -- not sampled, not estimated.
"""
from structural_computing import StructuralComputer

sc = StructuralComputer()


# Each "graph" is just an edge list. Vertices are inferred.
# Note: the wrapper synthesises a rotation system for edge-list inputs;
# the framework's classifier requires CONNECTED graphs (Euler's formula
# only defines genus for connected cellular embeddings), so disconnected
# inputs raise. Provide a rotation system explicitly if you need them.
examples = [
    ("4-cycle (C_4)",        [(0, 1), (1, 2), (2, 3), (3, 0)]),
    ("K_4 (complete graph)", [(0, 1), (0, 2), (0, 3),
                              (1, 2), (1, 3), (2, 3)]),
    ("path P_4",             [(0, 1), (1, 2), (2, 3)]),
    ("triangle (K_3)",       [(0, 1), (1, 2), (2, 0)]),
]

print(f"  {'graph':<25}  {'matchings':>10}")
print(f"  {'-' * 25}  {'-' * 10}")
for name, edges in examples:
    count = sc.count_matchings(edges)
    print(f"  {name:<25}  {count:>10}")
