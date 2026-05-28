"""09 -- Holographic basis change unlocking matchgate-realisability.

Valiant's holographic algorithms (2004) work by EXACT BASIS CHANGE: a
signature that is not matchgate-realisable in the standard basis may
BECOME matchgate-realisable under a 2x2 invertible basis transformation
applied to each variable. This example shows the canonical case.

Cai-Lu 2011 Theorem 2.5: a symmetric signature [z_0, z_1, ..., z_n] is
matchgate-realisable on SOME basis iff there exist constants (a, b, c)
(not all zero) such that

    a*z_k + b*z_{k+1} + c*z_{k+2} = 0   for all 0 <= k <= n - 2.

This is a linear-recurrence-of-order-2 condition. For arity 4 (5
values) the rank check on a 3x3 matrix tells us whether the signature
satisfies any such recurrence -- if rank < 3, it does.

For ARITY 3 (4 values), there are 2 equations in 3 unknowns, so the
recurrence always has a non-trivial solution: every arity-3 symmetric
signature is matchgate-realisable on some basis. So the "discovery" is
to find the actual basis. The Hadamard basis transforms many arity-3
signatures into their matchgate-standard form.
"""
import numpy as np

from structural_computing import HolographicBasisPair

# ---------------------------------------------------------------------------
# Example 1: the 3-AND signature [1, 0, 0, 1].
# This signature is the "only-the-all-1s configuration" symmetric
# signature. In the standard basis it's NOT in matchgate-standard form
# (matchgates require alternating-zero with geometric-progression
# non-zeros). The Hadamard basis transforms it into the standard form.
# ---------------------------------------------------------------------------
print("=" * 60)
print("Example 1: Hadamard unlock of 3-AND signature")
print("=" * 60)
T_hadamard = np.array([[1, 1], [1, -1]], dtype=float)
hbp = HolographicBasisPair(basis_matrix=T_hadamard)

original = [1, 0, 0, 1]
result = hbp.transform_signature(original)

print(f"original signature:    {original}")
print(f"transformed signature: {[round(v, 6) for v in result.values]}")
print(f"matchgate-realisable:  {result.is_realisable}")
print(f"recurrence (a, b, c):  {tuple(round(c, 6) for c in result.recurrence_coefficients)}")
print()

# ---------------------------------------------------------------------------
# Example 2: An arity-4 signature that's NOT realisable on any basis.
# The 3x3 recurrence matrix has rank 3, so no non-trivial recurrence
# exists. The framework's honest stop says so.
# ---------------------------------------------------------------------------
print("=" * 60)
print("Example 2: Honest stop on a truly non-realisable signature")
print("=" * 60)
hbp_id = HolographicBasisPair(basis_matrix=np.eye(2))

original = [1, 0, 1, 0, 2]
result = hbp_id.transform_signature(original)
print(f"signature:             {original}")
print(f"matchgate-realisable:  {result.is_realisable}")
print(f"recurrence:            {result.recurrence_coefficients}")
print("(no basis transformation can rescue this signature -- it lives"
      " outside the matchgate quadratic-curve subvariety of Cai-Lu's"
      " basis manifold M.)")
print()

# ---------------------------------------------------------------------------
# Example 3: NAE-3 signature [0, 1, 1, 0] is matchgate-realisable AS-IS
# in the standard basis (Cai-Lu 2011 §6.1).
# ---------------------------------------------------------------------------
print("=" * 60)
print("Example 3: NAE-3 -- realisable in the standard basis already")
print("=" * 60)
result = hbp_id.transform_signature([0, 1, 1, 0])
print(f"signature:             [0, 1, 1, 0]")
print(f"matchgate-realisable:  {result.is_realisable}")
print(f"recurrence (a, b, c):  {tuple(round(c, 6) for c in result.recurrence_coefficients)}")
a, b, c = result.recurrence_coefficients
print(f"check recurrence: a*z_0 + b*z_1 + c*z_2 = "
       f"{a*0 + b*1 + c*1:.6f}, a*z_1 + b*z_2 + c*z_3 = "
       f"{a*1 + b*1 + c*0:.6f}")
