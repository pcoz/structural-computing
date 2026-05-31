"""12 -- Auto-discovery of a holographic basis (Cai-Lu SRP practical fragment).

Given a symmetric signature, find a 2x2 invertible basis T such that
T applied to the signature produces a Cai-Gorenstein Theorem-9
standard-basis matchgate signature (alternate-zero with the non-zero
entries forming a geometric progression).

This is the practical fragment of Cai-Lu's SRP (Simultaneous
Realisability Problem) algorithm:

  - Cai-Lu 2011 Theorem 2.5 gives the GATE: a signature is matchgate-
    realisable on SOME basis iff it satisfies an order-2 recurrence.
  - Theorem 9 (Cai-Gorenstein) gives the TARGET FORM in the standard
    basis: alternate-zero with geometric progression on the non-zero
    entries.
  - This example uses HolographicBasisPair.discover_basis() to search
    the basis manifold for a T that maps the input into the target
    form. The v0.4 search has four steps in increasing-cost order:
    (1) order-2 recurrence gate; (2) v0.4 closed-form shortcut derived
    from the recurrence kernel (catches rank-1 signatures whose root
    lies anywhere on the real line); (3) canonical-bases sweep
    (identity, Hadamard, swap, common shears) for complex-roots cases;
    (4) parameterised grid + coordinate-descent polish as final
    fallback.

Honest scope: rank-2 signatures (true two-root decomposition with
both amplitudes non-zero) are GENUINELY matchgate-rank-2 in every
basis -- no 2x2 basis can bring them to matchgate-standard form. The
search correctly returns None for these. Adversarial complex-roots
cases that miss the canonical candidates also return None; the full
Cai-Lu §4 algorithm with all four "realizability subvariety" cases
is a v0.5 deliverable.
"""
from structural_computing import HolographicBasisPair

h = HolographicBasisPair()

cases = [
    ("3-AND [1, 0, 0, 1]",            [1, 0, 0, 1]),
    ("NAE-3 [0, 1, 1, 0]",            [0, 1, 1, 0]),
    ("already standard [2, 0, 2, 0, 2]", [2, 0, 2, 0, 2]),
    ("non-realisable [1, 0, 1, 0, 2]", [1, 0, 1, 0, 2]),
    ("degenerate cube [1, 1, 1, 1]",   [1, 1, 1, 1]),
]

for label, sig in cases:
    print(f"signature: {label}")
    discovery = h.discover_basis(sig)
    if discovery is None:
        print(f"  -> no basis found (signature not matchgate-realisable "
               f"on any basis, or rank-2 with complex roots outside "
               f"the canonical candidates)")
    else:
        T, result = discovery
        rounded_T = [[round(float(x), 6) for x in row] for row in T]
        rounded_z = [round(float(v), 6) for v in result.values]
        print(f"  -> T = {rounded_T}")
        print(f"     transformed signature = {rounded_z}")
    print()
