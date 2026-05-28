r"""The compositions layer -- combine 2+ in-family evaluations to produce
an out-of-family answer.

Where `transform.py` ships a problem through a sequence of transformations,
this module ships *multiple* in-family evaluations whose results combine.
Most known holographic-algorithm wins (Cai-Lu-Xia, Valiant 2004 onwards)
live in this layer.

The mental model: the user has a quantity `Q` they want to compute. `Q`
itself may not be matchgate-realisable, but it can be expressed as
`F(Q_1, Q_2, ..., Q_k)` where each `Q_i` IS matchgate-realisable and `F`
is a simple combining function (linear combination, projection, polynomial,
holographic-basis pair, branch sum, etc.). The composition object names
each `Q_i` (an in-family sub-problem) and the combiner `F`.

This v0.1 release ships:

  * The `Composition` protocol that every concrete composition conforms to.
  * The `CompositionPlan` dataclass for inspecting a composition.
  * One concrete composition: `LinearCombination` -- evaluate two
    in-family signatures and combine their evaluations linearly. The
    simplest non-trivial composition, and the gateway to expressing
    many non-matchgate signatures as `alpha * sig_A + beta * sig_B`.
  * Sketches of upcoming compositions (`Projection`, `HolographicBasisPair`,
    `BranchSum`) raised as `NotImplementedError` with docstrings.

The full set of planned compositions lives in
admissibility-geometry/proposals/reductions_compositions_recursive_decomposition.md.
"""
import dataclasses
from typing import Any, Callable, List, Optional, Protocol, Sequence


# ---------------------------------------------------------------------------
# Base protocol -- every composition is a list of in-family sub-problems
# plus a combiner that takes their evaluated values and produces the
# composed answer.
# ---------------------------------------------------------------------------

class Composition(Protocol):
    """A composition is: a list of in-family sub-problems + a rule for
    combining their evaluated values into the composed answer.

    The contract:

      1. Each `sub_problems[i]` must be evaluable by the framework's
         in-family machinery (the runner can call the appropriate
         tier's evaluator on each).

      2. `combine(values)` takes the list `[evaluator(p) for p in sub_problems]`
         and returns the answer to the original composed question.

      3. The composition is PURE -- it does not mutate its inputs.
    """
    name: str
    sub_problems: List[Any]
    combine: Callable[[List[Any]], Any]


@dataclasses.dataclass
class CompositionPlan:
    """A composition expressed as a dataclass for easy inspection. Most
    user-facing code constructs one of these directly rather than going
    through the Composition protocol."""
    name: str
    sub_problems: List[Any]
    combine: Callable[[List[Any]], Any]
    cost_overhead: float = 0.0
    notes: str = ""

    def evaluate(self, sub_evaluator: Callable[[Any], Any]) -> Any:
        """Apply `sub_evaluator` to each sub-problem in order, then combine
        the values. The sub-evaluator is the framework's in-family
        runner (which the caller wires in)."""
        values = [sub_evaluator(p) for p in self.sub_problems]
        return self.combine(values)


# ---------------------------------------------------------------------------
# Concrete composition: LinearCombination
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class LinearCombination:
    """Evaluate two (or more) in-family sub-problems and combine their
    values as `sum(coeff_i * value_i)`.

    Use case: a signature `s` that's not matchgate-realisable as-is might
    decompose as `s = a * s_A + b * s_B` where `s_A` and `s_B` ARE
    matchgate-realisable. The framework evaluates each, then combines.

    Example::

        # Suppose we want to evaluate signature s = 0.7 * OR + 0.3 * AND
        comp = LinearCombination(
            name="0.7 OR + 0.3 AND",
            sub_problems=[
                {"kind": "signature", "data": {"values": [0, 1, 1]}},   # OR
                {"kind": "signature", "data": {"values": [0, 0, 1]}},   # AND
            ],
            coefficients=[0.7, 0.3],
        )
        result = comp.evaluate(framework_evaluator)
    """
    name: str
    sub_problems: List[Any]
    coefficients: Sequence[float]

    def __post_init__(self):
        if len(self.sub_problems) != len(self.coefficients):
            raise ValueError(
                f"LinearCombination: {len(self.sub_problems)} sub-problems but "
                f"{len(self.coefficients)} coefficients (must match)"
            )

    @property
    def combine(self):
        coeffs = list(self.coefficients)
        def _combine(values: List[Any]) -> Any:
            return sum(c * v for c, v in zip(coeffs, values))
        return _combine

    def evaluate(self, sub_evaluator: Callable[[Any], Any]) -> Any:
        values = [sub_evaluator(p) for p in self.sub_problems]
        return self.combine(values)


# ---------------------------------------------------------------------------
# Sketches of upcoming compositions
# ---------------------------------------------------------------------------

class Projection:
    """Two Holant evaluations on different graphs that project into the
    same answer space; the non-conforming quantity is the projection.

    Used in the framework where the answer is a sum or marginal over a
    joint distribution whose factors are matchgate-Holant but the joint
    isn't.

    Status: not implemented in v0.1. The mathematical content is
    Bayesian / message-passing in matchgate-Holant; implementation needs
    to nail down the API for joint vs. marginal problem objects.
    """
    name = "Projection"

    def evaluate(self, sub_evaluator):
        raise NotImplementedError(
            f"{self.name} is on the v0.2 roadmap."
        )


class HolographicBasisPair:
    r"""A 2x2 invertible basis transformation applied to a symmetric
    Holant signature, with a check (per Cai-Lu 2011 Theorem 2.5) that
    the transformed signature is matchgate-realisable.

    This is Valiant 2004's central technique ("Holographic Algorithms"
    DOI 10.1109/FOCS.2004.40) and the engine behind most known
    holographic algorithms (Cai-Lu-Xia 2009 onwards). The mental model:

      Given a 2x2 invertible basis matrix T = ((p, q), (r, s)), the
      same symmetric signature can be "viewed in different bases" via
      the polynomial-substitution rule. Encode the symmetric signature
      [z_0, ..., z_n] as the homogeneous polynomial
        P(u, v) = sum_k C(n, k) z_k u^{n-k} v^k.
      The basis change sends (u, v) -> (p u + r v, q u + s v), so
        P'(u, v) = P(p u + r v, q u + s v),
      and the new signature values are the coefficients of P' in the
      same basis.

      A symmetric signature is matchgate-realisable iff it satisfies a
      LINEAR RECURRENCE OF ORDER 2 (Cai-Lu 2011 Theorem 2.5): there
      exist a, b, c (not all zero) such that a z_k + b z_{k+1} +
      c z_{k+2} = 0 for all valid k. The rank-check below decides this
      in O(n) time.

    Use::

        # Apply a Hadamard-style basis to a non-matchgate symmetric
        # signature and check whether the transformed signature lands
        # in the matchgate family.
        T = np.array([[1, 1], [1, -1]], dtype=float)
        h = HolographicBasisPair(basis_matrix=T)
        result = h.transform_signature([1, 0, 0, 1])     # 3-AND signature
        # -> if the transformed signature satisfies the order-2 recurrence,
        #    `result.is_realisable` is True and the transformed values are
        #    in `result.values`.

    Caveats (honest scope for v0.2):
      * Symmetric signatures only. General (non-symmetric) signatures
        require the full tensor-power T^{⊗a} on a 2^a-dim space; the
        polynomial-substitution shortcut here doesn't apply.
      * Numerical rank check over R/C with tunable tolerance. Modular /
        finite-field exact checks are a v0.3 extension.
      * The user supplies T explicitly. Auto-discovery of a basis on
        which a given signature becomes matchgate-realisable -- the full
        Cai-Lu Simultaneous Realisability Problem -- is also v0.3.
    """
    name = "HolographicBasisPair"

    def __init__(self, basis_matrix=None, *, tol: float = 1e-10):
        """`basis_matrix` is the 2x2 invertible matrix T defining the
        basis change. `tol` is the numerical tolerance for the rank
        check that decides matchgate-realisability."""
        self.basis_matrix = basis_matrix
        self.tol = tol

    def _validated_T(self):
        import numpy as np
        if self.basis_matrix is None:
            raise ValueError(
                f"{self.name}: specify a 2x2 invertible basis_matrix."
            )
        T = np.asarray(self.basis_matrix, dtype=float)
        if T.shape != (2, 2):
            raise ValueError(
                f"{self.name}: basis_matrix must be 2x2; got shape {T.shape}"
            )
        if abs(np.linalg.det(T)) < self.tol:
            raise ValueError(
                f"{self.name}: basis_matrix must be invertible "
                f"(det = {np.linalg.det(T)})"
            )
        return T

    def transform_signature(self, values):
        """Apply this composition's basis matrix to the symmetric
        signature `values` and return a :class:`HolographicBasisResult`
        carrying the transformed values + matchgate-realisability flag.

        For a symmetric signature [z_0, ..., z_n] under T = ((p, q), (r, s)):

            z'_k = sum_{i=0..k, j=0..n-k}
                       C(k, i) C(n-k, j) p^i q^{k-i} r^j s^{n-k-j} z_{i+j}

        This is the polynomial-substitution rule applied to the
        symmetric encoding P(u, v) = sum_k C(n, k) z_k u^{n-k} v^k
        under (u, v) -> (p u + r v, q u + s v).
        """
        import math
        T = self._validated_T()
        n = len(values) - 1
        p, q = T[0, 0], T[0, 1]
        r, s = T[1, 0], T[1, 1]
        # Apply the basis transformation symmetrically.
        new_values = [0.0] * (n + 1)
        for k in range(n + 1):
            for i in range(k + 1):
                for j in range(n - k + 1):
                    src = i + j
                    if src > n:
                        continue
                    coeff = (math.comb(k, i) * math.comb(n - k, j)
                              * (p ** i) * (q ** (k - i))
                              * (r ** j) * (s ** (n - k - j)))
                    new_values[k] += coeff * float(values[src])
        is_real, recurrence = self._matchgate_realisable(new_values)
        return HolographicBasisResult(
            values=new_values,
            is_realisable=is_real,
            recurrence_coefficients=recurrence,
            basis_matrix=T,
        )

    def _matchgate_realisable(self, values):
        """Check whether `values` satisfies a linear recurrence of order
        2 (Cai-Lu 2011 Theorem 2.5). Returns (is_realisable,
        (a, b, c)) where (a, b, c) is one non-trivial kernel vector
        when realisable, else None."""
        import numpy as np
        n = len(values) - 1
        if n < 2:
            return True, None
        # Build the (n-1) x 3 matrix M[k, :] = [z_k, z_{k+1}, z_{k+2}].
        M = np.array(
            [[values[k], values[k + 1], values[k + 2]] for k in range(n - 1)],
            dtype=float,
        )
        rank = int(np.linalg.matrix_rank(M, tol=self.tol))
        if rank < 3:
            # Find a kernel vector via SVD (right singular vector with
            # smallest singular value).
            _, _, Vt = np.linalg.svd(M)
            kernel = Vt[-1]
            return True, tuple(kernel.tolist())
        return False, None

    def evaluate(self, sub_evaluator):
        """Apply the basis transformation to a Holant-style problem
        with a symmetric signature, and dispatch to the sub-evaluator
        on the TRANSFORMED problem.

        The sub-evaluator receives a problem of the form
        ``{"values": <transformed_signature>}`` plus the transformation
        metadata. The composition's Holant value equals the
        sub-evaluator's value on the transformed signature (no
        multiplicative correction needed -- that's the content of
        Valiant's Holant Theorem).
        """
        import numpy as np
        T = self._validated_T()
        if np.allclose(T, np.eye(2), atol=self.tol):
            # Trivial identity case: no transformation, just dispatch.
            return sub_evaluator({"identity_basis": True,
                                  "note": "no transformation -- evaluate signature in the natural basis"})
        raise NotImplementedError(
            f"{self.name}.evaluate() with non-identity basis requires a "
            f"sub_evaluator that takes a transformed-signature problem; "
            f"use transform_signature() directly to get the new values "
            f"and route them through the orchestrator separately."
        )


@dataclasses.dataclass
class HolographicBasisResult:
    """Result of a HolographicBasisPair.transform_signature call.

    Attributes:
      values: the transformed signature values [z'_0, ..., z'_n].
      is_realisable: True iff the transformed signature satisfies the
        Cai-Lu 2011 order-2 recurrence (matchgate-realisable).
      recurrence_coefficients: when realisable, the (a, b, c) kernel
        vector such that a z'_k + b z'_{k+1} + c z'_{k+2} = 0; None
        otherwise.
      basis_matrix: the 2x2 matrix T applied.
    """
    values: List[float]
    is_realisable: bool
    recurrence_coefficients: Optional[Any]
    basis_matrix: Any


class BranchSum:
    """A sum over branches, each branch being an in-family evaluation
    with a coefficient. The hybrid-dispatcher's amplitude-level
    recombination is one instance of this pattern.

    Status: the circuit-specific form exists in
    `free-fermion-quantum-simulation/hybrid-dispatcher/hybrid_dispatcher.py`.
    Lifting to a general framework primitive is the v0.2 deliverable.
    """
    name = "BranchSum"

    def evaluate(self, sub_evaluator):
        raise NotImplementedError(
            f"{self.name} is on the v0.2 roadmap (general form -- the circuit "
            f"specialisation is in hybrid_dispatcher.py)."
        )


__all__ = [
    "Composition",
    "CompositionPlan",
    "LinearCombination",
    "Projection",
    "HolographicBasisPair",
    "BranchSum",
]
