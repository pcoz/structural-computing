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
from typing import Any, Callable, List, Optional, Protocol, Sequence, Tuple


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

    # -----------------------------------------------------------------
    # Non-symmetric (general-tensor) basis transformation (v0.3)
    # -----------------------------------------------------------------
    #
    # The symmetric `transform_signature` uses the polynomial-substitution
    # shortcut, which only works because a symmetric signature is fully
    # described by its (n+1) Hamming-weight-indexed values. For a
    # GENERAL signature -- an arbitrary 2^a-dim tensor indexed by
    # bitstrings -- the basis transformation is the full tensor power:
    #
    #     sigma'[beta] = sum_{alpha in {0,1}^a} (prod_i T[beta_i, alpha_i]) * sigma[alpha]
    #
    # i.e., apply T to each of the `a` wires independently. Implemented
    # as `a` sequential 2x2 contractions on a length-a tensor of shape
    # (2, 2, ..., 2), so the cost is O(a * 2^a) rather than the naive
    # O(2^{2a}).
    # -----------------------------------------------------------------

    def transform_signature_general(self,
                                      values: Sequence[float],
                                      arity: int) -> "HolographicBasisResult":
        r"""Apply ``T^{otimes a}`` to a general (possibly non-symmetric)
        signature.

        ``values`` is a flat array of length ``2^arity`` indexed by
        bitstrings ``alpha in {0,1}^arity`` (interpreted as integers
        ``0..2^arity - 1`` in standard binary, bit 0 = LSB).

        The transformation rule:

            sigma'[beta] = sum_{alpha} (prod_i T[beta_i, alpha_i]) sigma[alpha]

        is the full tensor-power action of T on each wire. For
        SYMMETRIC signatures, use :meth:`transform_signature` instead
        -- it's much cheaper because it exploits the symmetry to do
        the work in (a+1)-dim coefficient space rather than the full
        2^a-dim tensor.

        Args:
          values: length-``2^arity`` flat array.
          arity: number of wires; ``len(values)`` must equal ``2**arity``.

        Returns:
          :class:`HolographicBasisResult` with the transformed values.
          The ``is_realisable`` field is set to ``None`` for general
          signatures (a v0.4 deliverable will add the Matchgate-
          Identity check; for now the realisability question is
          deferred to the caller).
        """
        import numpy as np
        T = self._validated_T()
        expected = 2 ** arity
        if len(values) != expected:
            raise ValueError(
                f"{self.name}.transform_signature_general: "
                f"expected len(values) = 2^arity = {expected}, got {len(values)}"
            )
        # Reshape into a length-`arity` tensor with shape (2, 2, ..., 2).
        # values[alpha] is indexed by integer alpha in [0, 2^arity); we
        # interpret alpha's bits as the indices along each axis with
        # axis i corresponding to bit i (LSB-first to match numpy's
        # reshape convention from a flat row-major buffer).
        # In numpy reshape((2,)*a) on a flat array, the FIRST axis
        # varies the slowest, so index alpha at flat position
        # `alpha_{a-1} ... alpha_1 alpha_0` (big-endian along the axes).
        # Convention: keep alpha = sum_i (alpha_i * 2^i) (LSB at axis 0)
        # and let numpy choose the axis ordering; what matters is that
        # the final flatten() inverse-matches the reshape.
        tensor = np.asarray(values, dtype=float).reshape((2,) * arity)
        for axis in range(arity):
            # Contract T (shape (2, 2), [beta_axis, alpha_axis]) with
            # the tensor's `axis` (the alpha_axis side).
            tensor = np.tensordot(T, tensor, axes=([1], [axis]))
            # tensordot prepends the new axis; move it back to `axis`.
            tensor = np.moveaxis(tensor, 0, axis)
        new_values = tensor.reshape(-1).tolist()
        return HolographicBasisResult(
            values=new_values,
            is_realisable=None,
            recurrence_coefficients=None,
            basis_matrix=T,
        )

    # -----------------------------------------------------------------
    # Auto-discovery of T (v0.3 -- the practical fragment of Cai-Lu's SRP)
    # -----------------------------------------------------------------
    #
    # Cai-Lu 2011 Theorem 2.5 says a symmetric signature is matchgate-
    # realisable on SOME basis iff it satisfies an order-2 linear
    # recurrence. Their full SRP algorithm decides realisability on a
    # COMMON basis for several signatures simultaneously, via the
    # geometry of subvarieties B_rec(sigma) and B_gen(sigma) in the
    # 2-dim basis manifold M = GL_2(F) / ~.
    #
    # For a SINGLE signature (the case the v0.2 implementation handles)
    # we want a constructive T such that T applied to the signature
    # gives a Cai-Gorenstein Theorem-9 form (alternate-zero with the
    # non-zero entries forming a geometric progression).
    #
    # The v0.3 implementation here ships a PRACTICAL search:
    #   (1) try a list of canonical bases (identity, Hadamard, shears,
    #       coordinate swap);
    #   (2) if none work, parameterise T = [[1, t], [u, v]] and do a
    #       2-D coarse grid search, refining the best candidate with a
    #       few Newton-style polishing iterations.
    #
    # When the signature does not satisfy the order-2 recurrence,
    # discover_basis() returns (None, None) -- no basis can rescue it
    # (Cai-Lu Thm 2.5).
    # -----------------------------------------------------------------

    @staticmethod
    def _matchgate_standard_distance(values, tol: float = 1e-9) -> float:
        r"""Scale-invariant distance of `values` from a Cai-Gorenstein
        Theorem-9 standard-basis matchgate signature: alternate-zero
        with the non-zero entries forming a geometric progression.

        Returns 0 when `values` is exactly in the standard form. Values
        are normalised by their max-absolute entry before scoring, so a
        "collapsed near-zero" signature (which would look trivially
        matchgate under unnormalised scoring) is correctly rejected.
        We score both EVEN and ODD non-zero-position cases and return
        the smaller, since either parity is a valid matchgate form.
        """
        import numpy as np
        v = np.asarray(values, dtype=float)
        n = len(v) - 1
        if n < 1:
            return 0.0
        # Scale-invariant: normalise by max absolute entry. A vector of
        # all-near-zero entries normalises to numerical noise relative
        # to its own (very small) max -- the parity-distance below then
        # surfaces the real structural mismatch rather than the absolute
        # smallness.
        vmax = float(np.max(np.abs(v)))
        if vmax < tol:
            return 0.0                        # the genuinely-zero signature
        vn = v / vmax

        def _parity_distance(zero_positions, nonzero_positions):
            cost = float(sum(vn[i] ** 2 for i in zero_positions))
            nz = [float(vn[i]) for i in nonzero_positions]
            if all(abs(x) < tol for x in nz):
                # All claimed non-zeros are zero; the signature is
                # effectively zero on this parity -- combined with the
                # zero-positions cost gives the right answer.
                return cost
            # Interior-zero on a supposed-nonzero position breaks the
            # geometric progression.
            for x in nz:
                if abs(x) < tol:
                    cost += 1.0
            # Geometric-progression deviation: consecutive log-ratios
            # should agree.
            if len(nz) >= 2:
                ratios = []
                for j in range(len(nz) - 1):
                    if abs(nz[j]) < tol:
                        ratios.append(float("inf"))
                    else:
                        ratios.append(nz[j + 1] / nz[j])
                mean_ratio = float(np.mean(ratios))
                cost += float(sum((r - mean_ratio) ** 2 for r in ratios))
            return cost

        even_positions = list(range(0, n + 1, 2))
        odd_positions  = list(range(1, n + 1, 2))
        d_even = _parity_distance(odd_positions, even_positions)
        d_odd  = _parity_distance(even_positions, odd_positions)
        return min(d_even, d_odd)

    def discover_basis(self,
                        values,
                        *,
                        max_grid_steps: int = 16,
                        success_tol: float = 1e-6,
                        ) -> Optional[Tuple[Any, "HolographicBasisResult"]]:
        r"""Search for a 2x2 invertible basis T such that applying T to
        the symmetric signature `values` produces a Cai-Gorenstein
        Theorem-9 standard-basis matchgate signature.

        Strategy (Cai-Lu 2011 SRP, practical single-signature fragment):

          1. If the signature does NOT satisfy the order-2 recurrence,
             no basis can rescue it (Cai-Lu Theorem 2.5). Return None.
          2. Try a fixed list of canonical candidate bases first
             (identity, Hadamard, coordinate swap, common shears).
          3. If none work, parameterise T = [[1, t], [u, v]] and do a
             coarse grid search over (t, u, v) followed by a polishing
             refinement at the best candidate.

        Args:
          values: symmetric signature [z_0, z_1, ..., z_n].
          max_grid_steps: resolution of each axis in the grid search.
          success_tol: a transformed signature counts as "matchgate-
            standard" if its distance from the form is below this.

        Returns:
          ``(T, result)`` where T is the discovered basis matrix and
          ``result`` is the :class:`HolographicBasisResult` for that T.
          Returns ``None`` if no basis is found (which means either the
          signature is not matchgate-realisable on any basis, or the
          search did not converge within the configured budget).
        """
        import numpy as np
        # Step 1: realisability gate. If the input doesn't satisfy the
        # recurrence, no basis works -- return None immediately.
        backup_T = self.basis_matrix
        self.basis_matrix = np.eye(2)
        try:
            id_result = self.transform_signature(values)
        finally:
            self.basis_matrix = backup_T
        if not id_result.is_realisable:
            return None

        def _try(T):
            saved = self.basis_matrix
            self.basis_matrix = T
            try:
                r = self.transform_signature(values)
            except (ValueError, ZeroDivisionError):
                return None
            finally:
                self.basis_matrix = saved
            return r

        def _matches(result) -> bool:
            return (result is not None
                     and self._matchgate_standard_distance(result.values)
                          < success_tol)

        # Step 2: canonical candidates.
        sqrt2_inv = 1.0 / np.sqrt(2.0)
        canonical: List[Tuple[str, Any]] = [
            ("identity", np.eye(2)),
            ("hadamard", np.array([[1.0, 1.0], [1.0, -1.0]])),
            ("hadamard_normed", np.array([[sqrt2_inv, sqrt2_inv],
                                            [sqrt2_inv, -sqrt2_inv]])),
            ("swap",     np.array([[0.0, 1.0], [1.0, 0.0]])),
            ("shear_+",  np.array([[1.0, 0.0], [1.0, 1.0]])),
            ("shear_-",  np.array([[1.0, 0.0], [-1.0, 1.0]])),
            ("shearT_+", np.array([[1.0, 1.0], [0.0, 1.0]])),
            ("shearT_-", np.array([[1.0, -1.0], [0.0, 1.0]])),
            ("scale_xy",  np.array([[1.0, 0.0], [0.0, 2.0]])),
            ("scale_yx",  np.array([[2.0, 0.0], [0.0, 1.0]])),
            ("rotation_4", np.array([[sqrt2_inv, -sqrt2_inv],
                                       [sqrt2_inv,  sqrt2_inv]])),
        ]
        for _name, T in canonical:
            r = _try(T)
            if _matches(r):
                return T, r

        # Step 3: parameterised grid search.
        best_T, best_r, best_d = None, None, float("inf")
        steps = np.linspace(-2.0, 2.0, max_grid_steps)
        for t in steps:
            for u in steps:
                for v in steps:
                    T = np.array([[1.0, t], [u, v]])
                    if abs(np.linalg.det(T)) < 1e-12:
                        continue
                    r = _try(T)
                    if r is None:
                        continue
                    d = self._matchgate_standard_distance(r.values)
                    if d < best_d:
                        best_d, best_T, best_r = d, T, r
                        if d < success_tol:
                            return T, r

        # Step 4: polish the best grid candidate with a few coordinate
        # descent steps in a shrinking neighbourhood.
        if best_T is not None and best_d > success_tol:
            radius = 0.5
            for _outer in range(4):
                improved = False
                for axis in range(3):
                    for delta in (-radius, +radius):
                        T_try = best_T.copy()
                        # axis 0,1,2 -> t,u,v in [[1, t], [u, v]]
                        if   axis == 0: T_try[0, 1] += delta
                        elif axis == 1: T_try[1, 0] += delta
                        else:           T_try[1, 1] += delta
                        if abs(np.linalg.det(T_try)) < 1e-12:
                            continue
                        r = _try(T_try)
                        if r is None:
                            continue
                        d = self._matchgate_standard_distance(r.values)
                        if d < best_d:
                            best_d, best_T, best_r = d, T_try, r
                            improved = True
                if not improved:
                    radius *= 0.5
                if best_d < success_tol:
                    return best_T, best_r

        if best_T is not None and best_d < success_tol:
            return best_T, best_r
        return None

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
    """Result of a HolographicBasisPair.transform_signature[_general] call.

    Attributes:
      values: the transformed signature values. For symmetric inputs
        this is ``[z'_0, ..., z'_n]`` of length n+1; for general inputs
        this is a flat length-2^arity array indexed by bitstrings.
      is_realisable: For SYMMETRIC results: True iff the transformed
        signature satisfies the Cai-Lu 2011 order-2 recurrence
        (matchgate-realisable). For GENERAL results: None (the MGI
        check on a 2^a-dim tensor is a v0.4 deliverable).
      recurrence_coefficients: when realisable, the (a, b, c) kernel
        vector such that a z'_k + b z'_{k+1} + c z'_{k+2} = 0; None
        otherwise.
      basis_matrix: the 2x2 matrix T applied.
    """
    values: List[float]
    is_realisable: Optional[bool]
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
