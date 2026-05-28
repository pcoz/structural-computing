"""13 -- Non-symmetric holographic basis transformation (T^otimes a).

For SYMMETRIC signatures, the basis change is computed via polynomial
substitution on the (a+1)-dim coefficient vector
(see example 09_holographic_basis_unlock.py and the
HolographicBasisPair.transform_signature method).

For GENERAL (non-symmetric) signatures, the basis change is the full
tensor power: T applied to each of the `a` wires independently. The
signature is a length-2^a flat array indexed by bitstrings, and the
transformed signature is computed by `a` sequential 2x2 contractions,
each peeling one axis off the length-`a` tensor (giving O(a * 2^a)
total work instead of the naive O(2^{2a})).

Two checks here:
  1. The general path agrees with the symmetric path when the input
     is a symmetric signature interpreted in both forms.
  2. The transform is involutive under T followed by T^{-1}: round-
     tripping a random arity-3 signature recovers it exactly.
"""
import numpy as np

from structural_computing import HolographicBasisPair


# -------------------------------------------------------------------
# Check 1: agreement with the symmetric path
# -------------------------------------------------------------------
T = np.array([[1, 1], [1, -1]], dtype=float)              # Hadamard
h = HolographicBasisPair(basis_matrix=T)

# A SYMMETRIC arity-2 signature [a, b, c] is, in general 2^2-dim form,
# [a, b, b, c] (the values at bitstring positions 00, 01, 10, 11).
sym  = [1, 0, 1]                                          # the AND-3 mod 2 signature
gen  = [1, 0, 0, 1]                                       # same, viewed as general

sym_result = h.transform_signature(sym)
gen_result = h.transform_signature_general(gen, arity=2)

print("=" * 60)
print("Check 1: symmetric and general paths agree on a symmetric input")
print("=" * 60)
print(f"  symmetric input:  {sym}")
print(f"  general view:     {gen}")
print(f"  symmetric output: {sym_result.values}")
print(f"  general   output: {gen_result.values}")
print(f"  general output's symmetric form should be: "
       f"[{sym_result.values[0]}, {sym_result.values[1]}, "
       f"{sym_result.values[1]}, {sym_result.values[2]}]")
print()


# -------------------------------------------------------------------
# Check 2: round-trip invariance under T then T^{-1}
# -------------------------------------------------------------------
T = np.array([[2, 1], [1, 1]], dtype=float)
T_inv = np.linalg.inv(T)

h_fwd = HolographicBasisPair(basis_matrix=T)
h_inv = HolographicBasisPair(basis_matrix=T_inv)

original  = [1.0, 2.0, -3.0, 4.0, 0.5, -1.5, 7.0, -2.0]    # arity 3, 8 values
forward   = h_fwd.transform_signature_general(original, arity=3).values
roundtrip = h_inv.transform_signature_general(forward, arity=3).values

print("=" * 60)
print("Check 2: T then T^{-1} is identity (round-trip)")
print("=" * 60)
print(f"  original:  {original}")
print(f"  forward:   {[round(v, 6) for v in forward]}")
print(f"  roundtrip: {[round(v, 6) for v in roundtrip]}")
print(f"  matches:   {np.allclose(roundtrip, original, atol=1e-9)}")
print()


# -------------------------------------------------------------------
# Check 3: Hadamard maps the canonical-basis delta to the all-ones
# tensor (Walsh-Hadamard transform of a delta function).
# -------------------------------------------------------------------
print("=" * 60)
print("Check 3: H^{otimes 3} on delta_000 is the uniform tensor [1, ..., 1]")
print("=" * 60)
T = np.array([[1, 1], [1, -1]], dtype=float)
h = HolographicBasisPair(basis_matrix=T)
delta = [1, 0, 0, 0, 0, 0, 0, 0]
result = h.transform_signature_general(delta, arity=3).values
print(f"  delta:    {delta}")
print(f"  H * delta: {result}")
