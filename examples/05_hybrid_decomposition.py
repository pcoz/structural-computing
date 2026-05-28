"""05 — Hybrid decomposition: exact matching count on a NON-planar graph.

K_{3,3} (the smallest non-planar bipartite graph) doesn't fit the
framework's native T2 path. But K_{3,3} minus any one edge IS planar.

Branching on a small set of "extra" edges (each is either in the
matching or not) gives `2^|extras|` planar sub-problems, each solved
exactly via FKT. The total count is the sum of contributions.

This is the Tutte / Lovasz-Plummer decomposition identity:

    M(G) = M(G - e) + M(G / uv)

where M(X) is the perfect-matching count of X, G - e deletes edge e
(forbidden from the matching), and G / uv contracts e (e is forced into
the matching, consuming both endpoints).
"""
from structural_computing import StructuralComputer, brute_force_count_matchings

sc = StructuralComputer()

# K_{3,3}: bipartite halves {0, 1, 2} and {3, 4, 5}, every cross-edge present.
K33 = [(0, 3), (0, 4), (0, 5),
        (1, 3), (1, 4), (1, 5),
        (2, 3), (2, 4), (2, 5)]
vertices = [0, 1, 2, 3, 4, 5]

# Brute-force matching count (= 3! = 6).
truth = brute_force_count_matchings(vertices, K33)
print(f"K_3,3 has {truth} perfect matchings (brute force)")
print()

# Hybrid decomposition with various numbers of extra edges.
# More extras = more sub-problems but each is smaller. All give the same
# exact answer.
for n_extras in (1, 2, 3):
    extras = K33[:n_extras]
    count = sc.count_matchings_hybrid(K33, extra_edges=extras)
    print(f"  hybrid with {n_extras} extra edge(s): {count}  "
          f"(2^{n_extras} = {2 ** n_extras} sub-problems)")
    assert count == truth, "hybrid decomposition must give the exact count"

print()
print("All hybrid decompositions give the exact count -- the framework's")
print("matching-count primitive scales beyond the strict planar boundary.")
