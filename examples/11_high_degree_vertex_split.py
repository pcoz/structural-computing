"""11 -- High-arity symmetric-signature realisation via the
Cai-Gorenstein 2k-node triangle-cycle matchgate.

A symmetric matchgate-realisable signature [z_0, z_1, ..., z_k]
(alternate-zero with geometric progression on the non-zero entries,
per Cai-Gorenstein Theorem 9) gets realised by a planar matchgate
with 2k vertices: k triangles {a_i, b_i, c_i} linked in a cycle with
c_i = b_{i+1}, edge weights x on the a-b and a-c edges and y on the
b-c edge.

The signature value Γ^α = 2 · x^{k-|α|} · y^{|α|/2} for even |α|
(and 0 for odd |α|).

This example takes a non-trivial geometric-progression signature
[2, 0, 6, 0, 18] (ratio 3) and verifies that the Cai-Gorenstein
construction reproduces it exactly via brute-force PerfMatch on the
2k=8 vertices.
"""
from itertools import product as iproduct

from structural_computing import HighDegreeVertexSplit, brute_force_weighted_matching_sum

sig = [2, 0, 6, 0, 18]
print(f"Input signature: {sig}  (arity 4, geometric ratio 3 on the non-zero entries)")
print()

h = HighDegreeVertexSplit(signature=sig)
result = h.apply({"values": sig})
mg = result.problem

print(f"Construction: {mg['construction']}")
print(f"Vertices ({len(mg['vertices'])}): {mg['vertices']}")
print(f"Externals: {mg['externals']}")
print(f"Edges ({len(mg['edges'])}):")
for e in mg["edges"]:
    print(f"  {e}  weight={mg['weights'][e]}")
print()

print("Brute-force verification of all 16 signature entries:")
all_ok = True
for alpha in iproduct([0, 1], repeat=4):
    drop = [mg["externals"][i] for i, b in enumerate(alpha) if b == 1]
    vert = [v for v in mg["vertices"] if v not in drop]
    eds  = [e for e in mg["edges"] if e[0] not in drop and e[1] not in drop]
    pm = brute_force_weighted_matching_sum(
        vert, eds, {e: mg["weights"][e] for e in eds},
    )
    hw = sum(alpha)
    expected = sig[hw]
    ok = abs(pm - expected) < 1e-9
    if not ok:
        all_ok = False
    marker = "OK" if ok else "FAIL"
    print(f"  alpha={alpha}, hw={hw}: brute Pm={pm}, expected={expected}  [{marker}]")

print()
print(f"All 16 entries match: {all_ok}")
