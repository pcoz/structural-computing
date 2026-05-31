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
import math
from typing import Any, Callable, Dict, List, Optional, Protocol, Sequence, Tuple


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

@dataclasses.dataclass
class Projection:
    r"""Evaluate two or more in-family sub-problems and project their
    values through a user-supplied projector callable to obtain the
    composed quantity.

    Use case: the answer Q is a sum, marginal, or other functional of
    several matchgate-Holant evaluations. For example:

      * Marginal probability: Q = Z_in / Z_total, where Z_in is the
        partition function restricted to "in-set" configurations and
        Z_total is the full partition function. Each Z is matchgate-
        Holant; Q is their projector.
      * Inclusion-exclusion expansion: Q = sum_{S subseteq T} (-1)^|S|
        * matchgate-eval(graph_S). Each evaluation is in-family; the
        projector applies the signs and sums.
      * Conditional expectations: Q = E[X | event] where the joint is
        matchgate-Holant; evaluate two related Holant problems and
        divide.

    Where :class:`LinearCombination` fixes the combiner to ``sum(coeff *
    value)``, :class:`Projection` accepts ANY callable mapping a list of
    sub-values to a single composed value -- ratios, products,
    inclusion-exclusion signs, max/min, etc.

    Example::

        # Marginal as ratio of two matchgate-Holant evaluations.
        proj = Projection(
            name="P(matching uses edge e) = M(G with e forced) / M(G)",
            sub_problems=[{"...": "G with e forced"}, {"...": "G"}],
            projector=lambda values: values[0] / values[1],
        )
        result = proj.evaluate(framework_evaluator)
    """
    name: str
    sub_problems: List[Any]
    projector: Callable[[List[Any]], Any]

    @property
    def combine(self):
        """Projection.combine == projector. Provided for Composition
        protocol conformance so a Projection can be passed where any
        Composition is expected."""
        return self.projector

    def evaluate(self, sub_evaluator: Callable[[Any], Any]) -> Any:
        """Apply ``sub_evaluator`` to each sub-problem in order; pass
        the resulting list of values to ``self.projector`` to produce
        the composed answer."""
        if not callable(self.projector):
            raise TypeError(
                f"{self.name}: projector must be callable, got "
                f"{type(self.projector).__name__}"
            )
        values = [sub_evaluator(p) for p in self.sub_problems]
        return self.projector(values)


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
            realisability_check="order_2_recurrence",
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
          :class:`HolographicBasisResult` with the transformed values
          and the ``is_realisable`` + ``realisability_check`` fields
          populated by the v0.4 Matchgate-Identity check (extended in
          v0.5 with the augmented-Pfaffian Plücker enumeration at
          even arity ≥ 6 odd-parity).
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
        is_realisable, check_name = self._check_general_realisability(
            new_values, arity,
        )
        return HolographicBasisResult(
            values=new_values,
            is_realisable=is_realisable,
            recurrence_coefficients=None,
            basis_matrix=T,
            realisability_check=check_name,
        )

    # -----------------------------------------------------------------
    # MGI (Matchgate-Identity) check for general (non-symmetric)
    # signatures (v0.4 deliverable)
    # -----------------------------------------------------------------
    #
    # The math, in one paragraph:
    #
    #     A matchgate is a planar weighted graph with a designated set
    #     of "external" vertices. Its STANDARD SIGNATURE on a bitstring
    #     `b = (b_0, ..., b_{a-1})` of length `a` is the signed
    #     perfect-matching count of the graph with the externals at
    #     positions `i` where `b_i = 0` left in place and the externals
    #     at positions where `b_i = 1` removed. By Valiant 2008 +
    #     Cai-Lu 2011, these signatures (viewed as a 2^a-dim tensor)
    #     are exactly the simultaneous-zero locus of a specific set of
    #     polynomial identities -- the MATCHGATE IDENTITIES, derived
    #     from the Grassmann-Plücker identities for Pfaffians of skew-
    #     symmetric matrices via Valiant's framework.
    #
    # What this method checks: given a transformed signature tensor
    # (length 2^arity), decide whether it lies in the standard-basis
    # matchgate locus. The check has three arity-dependent paths,
    # corresponding to three regimes in the matchgate-identity theory:
    #
    #   arity < 4 -- PARITY ONLY.
    #     Below arity 4, the only identities are the parity-vanishing
    #     equations (Valiant 2008 Propositions 6.1, 6.2). A signature
    #     is matchgate-realisable on the standard basis iff either:
    #       * all odd-Hamming-weight entries are zero (EVEN parity
    #         branch -- the matchgate has an even number of unmatched
    #         externals), OR
    #       * all even-Hamming-weight entries are zero (ODD parity
    #         branch -- this requires the AUGMENTED-PFAFFIAN framework
    #         with a virtual omega vertex; see Cai-Lu 2011 §4).
    #     No identities beyond parity exist at this arity; parity is
    #     necessary AND sufficient.
    #
    #   arity = 4 -- PARITY PLUS ONE IDENTITY PER BRANCH.
    #     At arity 4, the smallest Pfaffian identity kicks in. For the
    #     EVEN-parity branch this is the classical 4-pair identity
    #
    #         tau_0000 * tau_1111
    #             - tau_1100 * tau_0011
    #             + tau_1010 * tau_0101
    #             - tau_1001 * tau_0110  =  0
    #
    #     (the three ways of pairing {0,1,2,3} into two-element subsets,
    #     each giving a Pfaffian product, plus the full and empty
    #     Pfaffians). For the ODD-parity branch, the analogous identity
    #     is derived via the augmented (n+1)x(n+1) Kasteleyn matrix
    #     with a virtual omega vertex (Cai-Lu 2011 §4 augmented-Pfaffian
    #     framework). Both identities are SUFFICIENT (in conjunction
    #     with parity) for standard-basis matchgate realisability at
    #     arity 4.
    #
    #   arity >= 5 -- PLÜCKER ENUMERATION (+ AUGMENTED WEIGHT-1 AT
    #                 EVEN ARITIES).
    #     At arity n >= 5, the general Plücker quadratic identities
    #     give one identity per choice of 4-subset {a,b,c,d} of
    #     positions and each (even, resp. odd) cardinality subset S
    #     of the remaining n-4 positions. By Plücker's classical
    #     result this enumeration is COMPLETE for the even-parity
    #     branch. For the odd-parity branch, the augmented weight-1
    #     identity Sigma_i (-1)^i tau(e_i) tau(complement(e_i))
    #     gives an additional necessary equation; this is meaningful
    #     ONLY at EVEN arities (at odd arity it reduces to 0=0
    #     because weight n-1 has the wrong parity -- see the
    #     same-parity-pair condition in the engine docstring).
    #     The check is a tight necessary check at arity >= 6 odd-
    #     parity (a strict over-approximation of the true realisable
    #     locus); arity 5 odd-parity is fully covered by the Plücker
    #     enumeration since |remaining| = 1 gives one identity per
    #     4-subset with S = {the remaining position}.
    #
    # Bridge to the engine: the matchgate-identity functions live in
    # `holant-tools.non_symmetric` (shipped in holant-tools v0.4.0).
    # They accept a `tau` dict mapping bitstrings (`Tuple[int, ...]`)
    # to numeric or symbolic values, and return a polynomial expression
    # in those values. For numeric tau (our case), the expression
    # evaluates to a numeric (sympy Float or Python float); we test
    # whether |expression| falls below a scale-invariant tolerance.
    #
    # Why standard-basis-specific: this check answers the question
    # "is the TRANSFORMED signature (after T^⊗a is applied) realisable
    # on the STANDARD basis?" -- which is the question Valiant's
    # holographic-algorithm framework cares about. A different
    # question, "is the signature realisable on SOME basis?", is
    # handled by the symmetric path's order-2-recurrence check
    # (`_matchgate_realisable`) for symmetric inputs, or by
    # `discover_basis` for general inputs.
    # -----------------------------------------------------------------

    @staticmethod
    def _flat_index_to_bitstring(flat_index: int, arity: int) -> Tuple[int, ...]:
        """Convert a flat-array index into the bitstring convention used
        by ``holant_tools.non_symmetric``.

        Why this bridge exists
        ----------------------
        The two packages use different bitstring conventions internally,
        and the matchgate-identity functions in ``holant-tools`` look up
        tau values by bitstring tuple. We MUST get the convention right
        or the identities will be evaluated on the wrong entries.

        ``structural-computing`` convention (after the
        ``tensor.reshape(-1)`` in :meth:`transform_signature_general`):
          The 1D length-2^arity values array is interpreted as a tensor
          of shape ``(2,)*arity`` in numpy's C-order (row-major). This
          means ``tensor[i_0, i_1, ..., i_{a-1}]`` sits at flat index
          ``alpha = i_0 * 2^{a-1} + i_1 * 2^{a-2} + ... + i_{a-1}``,
          i.e. axis 0 corresponds to the MSB of the flat index.

        ``holant-tools.non_symmetric`` convention:
          Bitstrings are tuples ``(b_0, b_1, ..., b_{a-1})`` where
          ``b_i`` is interpreted as the value at WIRE ``i`` of the
          matchgate. The internal pullback code iterates with
          ``b = tuple((mask >> i) & 1 for i in range(arity))``, which
          puts the LSB of ``mask`` at position 0.

        The bridge: we identify tensor axis ``i`` with matchgate wire
        ``i``. The bitstring for flat index ``alpha`` (interpreting
        ``alpha`` MSB-first into the tensor's axis labels) is then the
        natural tuple ``(b_0, ..., b_{a-1})`` to use with the holant-
        tools identity functions. So we read the bits of ``alpha`` MSB-
        first into the bitstring tuple.

        Worked example, arity 4
        -----------------------
          flat_index = 0  (binary 0000) -> bitstring (0, 0, 0, 0)
          flat_index = 5  (binary 0101) -> bitstring (0, 1, 0, 1)
          flat_index = 13 (binary 1101) -> bitstring (1, 1, 0, 1)
        """
        return tuple((flat_index >> (arity - 1 - i)) & 1 for i in range(arity))

    @classmethod
    def _build_tau_dict(cls,
                         values: Sequence[float],
                         arity: int,
                         ) -> Dict[Tuple[int, ...], float]:
        """Build a ``{bitstring: value}`` dict in the convention expected
        by the matchgate-identity functions in ``holant_tools.non_symmetric``.

        ``values`` is the flat length-2^arity array produced by
        :meth:`transform_signature_general`. Each entry corresponds to
        one bitstring; the convention bridge between the two packages
        is handled by :meth:`_flat_index_to_bitstring` (see that
        method's docstring for the rationale).

        Returns
        -------
        Dict[Tuple[int, ...], float]
            Keys are length-``arity`` tuples of 0s and 1s; values are
            the corresponding signature entries cast to Python float.
            The dict has exactly ``2**arity`` entries (one per
            bitstring; we always build the full tensor here even when
            some entries are zero, because the matchgate-identity
            functions expect every key to be present).
        """
        return {
            cls._flat_index_to_bitstring(idx, arity): float(values[idx])
            for idx in range(2 ** arity)
        }

    def _check_general_realisability(self,
                                       values: Sequence[float],
                                       arity: int,
                                       ) -> Tuple[Optional[bool], Optional[str]]:
        r"""Decide whether a general (non-symmetric) length-``2^arity``
        signature is matchgate-realisable on the STANDARD basis. Returns
        ``(is_realisable, realisability_check)``.

        See the module-level comment block above this method for the
        underlying mathematics (parity, Pfaffian identities, augmented-
        Pfaffian framework, Plücker enumeration); see
        :class:`HolographicBasisResult`'s ``realisability_check`` field
        for what each returned name means semantically.

        Tolerance strategy
        ------------------
        The matchgate identities are QUADRATIC in the tau values (every
        term is a product of two tau entries). So the natural absolute
        magnitude of an identity expression scales as ``max_abs^2``
        where ``max_abs = max |z'|`` over the signature. A
        signature-relative tolerance is therefore
        ``self.tol * max(max_abs^2, 1.0)`` -- the ``max(..., 1.0)``
        floor keeps the tolerance sane when ``max_abs`` is small (the
        identity polynomial inherits the same scale).

        Special case: the all-zero signature
        ------------------------------------
        A signature whose max-absolute entry falls below ``self.tol``
        is treated as the GENUINELY-ZERO signature -- it is trivially
        matchgate-realisable (the empty matchgate produces the zero
        signature). We short-circuit with ``(True, "deferred")``
        because the regular check would do meaningless arithmetic on
        near-zero numbers.

        Parity branches
        ---------------
        Standard-basis matchgate signatures vanish on one Hamming-
        weight parity:
          - EVEN-parity branch: all entries at odd Hamming weight are
            zero.
          - ODD-parity branch: all entries at even Hamming weight are
            zero (this branch requires the augmented-Pfaffian framework
            -- the bare Pfaffian on an odd-cardinality subset of a
            skew-symmetric matrix vanishes, so the odd-parity values
            need an augmented (n+1)-vertex Kasteleyn matrix to be
            represented as Pfaffians).

        The check first detects which (if any) parity branch holds for
        the input, then applies the arity-appropriate identities.
        Returns ``False`` immediately if neither branch holds (a
        signature with non-zero entries in BOTH parities cannot be a
        standard-basis matchgate signature).
        """
        # Pre-flight: scale and the special-case zero signature.
        max_abs = max((abs(v) for v in values), default=0.0)
        if max_abs < self.tol:
            # Trivially matchgate-realisable (the empty matchgate
            # produces the zero signature on any basis). The
            # "deferred" label signals that we shortcut rather than
            # running an identity check on near-zero arithmetic.
            return True, "deferred"

        # Tolerance for the (quadratic) identity expressions. Each
        # identity term is tau * tau, so absolute magnitude scales as
        # max_abs^2; we multiply by self.tol to get a relative
        # threshold. The max(..., 1.0) floor avoids over-tightening for
        # signatures with small max_abs (where max_abs^2 << max_abs).
        eff_tol = self.tol * max(max_abs * max_abs, 1.0)

        # Build the {bitstring: value} dict in the convention the
        # holant-tools identity functions expect.
        tau = self._build_tau_dict(values, arity)

        def _parity_zero(parity: int) -> bool:
            """True iff every tau entry whose Hamming-weight parity is
            ``parity`` (0 = even, 1 = odd) is effectively zero
            (below ``self.tol * max_abs``).

            For the EVEN-parity branch we require all ODD-weight
            entries to be zero (so we pass ``parity=1``); for the ODD-
            parity branch we require all EVEN-weight entries to be
            zero (``parity=0``).
            """
            return all(
                abs(v) < self.tol * max_abs
                for b, v in tau.items() if sum(b) % 2 == parity
            )

        even_branch = _parity_zero(parity=1)       # odd-weight entries zero
        odd_branch  = _parity_zero(parity=0)       # even-weight entries zero

        # ============================================================
        # ARITY < 4 : PARITY ONLY (Valiant 2008 Prop 6.1, 6.2)
        # ============================================================
        # At arities 1, 2, 3 there are NO matchgate identities beyond
        # the parity-vanishing condition. So if either parity branch
        # holds, the signature is matchgate-realisable on the standard
        # basis. (For arity 0 the only signature is a scalar; both
        # parity checks trivially hold.)
        if arity < 4:
            return (even_branch or odd_branch), "parity_only"

        # ============================================================
        # ARITY 4 : PARITY + ONE PFAFFIAN IDENTITY PER BRANCH
        # ============================================================
        # The matchgate-identity engine ships hand-coded identities
        # for both parities at arity 4. Even-parity is the classical
        # 4-pair Pfaffian identity; odd-parity is derived via the
        # augmented (5x5) Kasteleyn matrix.
        if arity == 4:
            import holant_tools as _ht

            # Try the EVEN-parity branch first. We only attempt the
            # even-parity identity if all odd-weight entries vanish
            # (otherwise the parity violation alone disqualifies the
            # signature; running the identity would just confirm the
            # rejection but with a less-clear meaning).
            if even_branch:
                # The identity returns a sympy expression; with numeric
                # tau values it's a sympy Float (or Python float for
                # trivial cases). Cast to float for the magnitude test.
                value = float(_ht.matchgate_identity_arity_4_even(tau))
                if abs(value) < eff_tol:
                    return True, "matchgate_identity_arity_4"
                # Identity violated -> not realisable on this branch.

            # Try the ODD-parity branch (using the augmented-Pfaffian
            # identity). Both branches can be tried in sequence because
            # a signature might be all-zero on either parity (in which
            # case only the OTHER branch is non-trivially testable).
            if odd_branch:
                value = float(_ht.matchgate_identity_arity_4_odd(tau))
                if abs(value) < eff_tol:
                    return True, "matchgate_identity_arity_4"

            # Neither branch produced a valid match. This covers:
            #   - parity violated on both branches (the most common
            #     "obviously not realisable" case)
            #   - parity holds on one branch but the identity fails
            #     (a more subtle obstruction the parity check alone
            #     wouldn't catch)
            return False, "matchgate_identity_arity_4"

        # ============================================================
        # ARITY >= 5 : PLÜCKER ENUMERATION + AUGMENTED (EVEN ARITIES)
        # ============================================================
        # For arity n >= 5 the matchgate-identity engine provides:
        #
        #   matchgate_identities_arity_n_even(tau, n)
        #       Returns a LIST of polynomials, one per (4-subset of
        #       positions, even-cardinality remaining-subset) pair. By
        #       Plücker's classical result this enumeration is COMPLETE
        #       for the even-parity matchgate variety.
        #
        #   matchgate_identities_arity_n_odd(tau, n)
        #       Same shape but with odd-cardinality remaining-subset.
        #       This catches one piece of the odd-parity story; the
        #       augmented weight-1 identity below catches another.
        #
        #   matchgate_identity_augmented_weight_1_arity_n_odd(tau, n)
        #       Single polynomial: Sigma_i (-1)^i tau(e_i) tau(bar e_i)
        #       where e_i is the i-th unit bitstring. Meaningful only
        #       at EVEN arities (see same-parity-pair note below).
        #
        # We evaluate each identity polynomial at the numeric tau
        # values and short-circuit on the first one that exceeds
        # ``eff_tol`` -- if any identity is non-zero, the signature is
        # not in the matchgate locus.
        import holant_tools as _ht

        if even_branch:
            # Plücker enumeration for the even-parity branch. This is
            # COMPLETE (Plücker's classical Grassmannian result), so a
            # signature that passes every identity here is genuinely
            # matchgate-realisable on the standard basis at this arity.
            for expr in _ht.matchgate_identities_arity_n_even(tau, arity):
                if abs(float(expr)) > eff_tol:
                    return False, "plucker_arity_n"
            return True, "plucker_arity_n"

        if odd_branch:
            # Standard Plücker enumeration for odd-parity. Catches part
            # of the odd-parity constraint set.
            for expr in _ht.matchgate_identities_arity_n_odd(tau, arity):
                if abs(float(expr)) > eff_tol:
                    return False, "plucker_arity_n"

            # The augmented weight-1 identity adds further constraint,
            # but only at EVEN arities. The reason (per the engine's
            # "same-parity-pair condition" note): the identity pairs
            # weight-1 entries with weight-(n-1) entries, and both
            # factors must lie in the same parity branch for the
            # identity to bite. Weight-1 is always odd; weight-(n-1)
            # is odd iff (n-1) is odd iff n is even. At odd n, the
            # second factor has even parity and is identically zero on
            # the strict odd-parity branch -- making the whole formula
            # collapse to 0 = 0 (a vacuous identity). We therefore
            # only apply this identity at even arities.
            if arity % 2 == 0:
                expr = _ht.matchgate_identity_augmented_weight_1_arity_n_odd(
                    tau, arity,
                )
                if abs(float(expr)) > eff_tol:
                    return False, "plucker_arity_n"

            # v0.5 Deliverable 1: full augmented-Pfaffian Plücker
            # enumeration at even arity >= 6, on the (n+1)-vertex
            # augmented Kasteleyn matrix M_omega. The v0.4 check ships
            # only the augmented weight-1 identity; the full set
            # includes weight-3 x weight-3 x weight-5 x weight-1
            # mixings derived from 4-subsets that pass through the
            # virtual omega vertex (see _augmented_plucker_identities
            # _arity_n_odd for the derivation).
            #
            # Closes the v0.4 "tight necessary but not provably
            # sufficient" gap at even arity >= 6 odd-parity: the
            # realisability_check field becomes "plucker_arity_n_full"
            # when these additional identities are applied. At arity 5
            # odd-parity, the standard Plücker enumeration is already
            # complete (|S|=1 odd-cardinality subsets of |remaining|=1)
            # so v0.5's contribution kicks in at n=6, 8, 10, ...
            if arity >= 6 and arity % 2 == 0:
                for expr in self._augmented_plucker_identities_arity_n_odd(
                        tau, arity):
                    if abs(float(expr)) > eff_tol:
                        return False, "plucker_arity_n_full"
                return True, "plucker_arity_n_full"

            # Arity 5 odd-parity: the standard enumeration is already
            # complete by Plücker (|S|=1 odd-cardinality identities).
            # Arity >= 7 odd-parity (odd n): the augmented identities
            # described above are vacuous (same-parity-pair condition);
            # higher augmented relations exist but are v0.6+ research-
            # grade work.
            return True, "plucker_arity_n"

        # Neither parity branch holds: the signature has non-zero
        # entries at both even AND odd Hamming weights. No matchgate
        # signature on the standard basis can have this shape (parity
        # vanishing is necessary at every arity), so we reject.
        return False, "plucker_arity_n"

    # -----------------------------------------------------------------
    # Full augmented-Pfaffian Plücker enumeration at EVEN arity >= 6
    # odd-parity (closes Cai-Lu §4 d-admissibility, |S|=2 configuration).
    # -----------------------------------------------------------------
    #
    # Prototyped in `structural-computing v0.5.0a1` (2026-05-31);
    # **promoted to `holant_tools.non_symmetric` in v0.6.0** (mirroring
    # how v0.4's MGI check consumes `matchgate_identity_arity_4_{even,odd}`
    # etc. from the engine repo). The helper below is now a thin
    # delegation wrapper that calls the engine function and casts the
    # returned sympy expressions to floats for the orchestrator's
    # tolerance-based check.
    #
    # The math primitives now live in their architecturally-correct
    # home (the mathematical engine). Per the v0.5 → v0.6 cleanup
    # commitment filed in admissibility-geometry's decision_log.md.
    # -----------------------------------------------------------------
    #
    # The math, in one paragraph
    # ---------------------------
    # Per the augmented-Pfaffian framework (Valiant 2008, Cai-Lu 2011
    # §4): odd-parity tau values at arity n are identified with
    # Pfaffians on the (n+1)-vertex Kasteleyn matrix M_omega, where
    # omega is a virtual augmenting vertex. The correspondence is
    #
    #     tau(b) = Pf( complement(b) in {0..n-1} ∪ {omega} )    (1)
    #
    # for each odd-weight bit string b. Plücker quadratic identities
    # on M_omega translate to polynomial constraints on tau values.
    # The v0.4 implementation ships the augmented weight-1 identity
    # (which is the single specific Plücker identity giving
    # Sigma_i (-1)^i tau(e_i) tau(complement(e_i)) = 0). Larger Plücker
    # 4-subsets in {0..n-1, omega} that INCLUDE omega give further
    # identities -- this method enumerates them.
    #
    # Configuration analysis (why |S|=2 works at arity 6)
    # ---------------------------------------------------
    # The Plücker identity has the form
    #     Pf(S) Pf(S∪{a,b,c,d}) - Pf(S∪{a,b}) Pf(S∪{c,d})
    #         + Pf(S∪{a,c}) Pf(S∪{b,d}) - Pf(S∪{a,d}) Pf(S∪{b,c}) = 0
    # for any choice of S ⊆ {0..n-1, omega} \ {a,b,c,d}. For all 8
    # Pfaffians to be expressible as tau values via the correspondence
    # (1), each subset T = S∪X (with X ⊆ {a,b,c,d}) must include omega
    # AND have even cardinality. The simplest configuration that
    # satisfies this for ALL 8 subsets is:
    #
    #     omega ∈ S, |S \ {omega}| = 1
    #
    # i.e. S = {p, omega} for some p ∈ {0..n-1}. Then |T| takes values
    # |S|, |S|+2, |S|+4 = 2, 4, 6 -- mapping to weight-(n-1),
    # weight-(n-3), weight-(n-5) tau values via (1). For the weights
    # to all be odd (so the tau values are non-zero on the odd-parity
    # branch), we need n-1, n-3, n-5 all odd, which requires n EVEN.
    #
    # The 4-subset {a,b,c,d} must avoid omega and p, so {a,b,c,d}
    # ⊆ {0..n-1} \ {p}. For arity n=6, this gives
    #     6 choices of p  ×  C(5, 4) = 5 choices of {a,b,c,d}  =  30 identities.
    # For arity 8: 8 × C(7,4) = 8 × 35 = 280 identities.
    # For arity 10: 10 × C(9,4) = 10 × 126 = 1260 identities.
    # (The count grows as O(n × C(n-1, 4)) = O(n^5).)
    #
    # Honest scope (post-v0.6.1)
    # --------------------------
    # The configuration parameter is ``m := |S \ {omega}|`` which
    # must be ODD and satisfy ``m + 5 <= n``. The viable
    # configurations are therefore ``m ∈ {1, 3, 5, ...}`` with arity
    # requirements ``n >= 6, 8, 10, ...`` respectively. v0.5 D1
    # shipped m=1; v0.6 D3 shipped m=3. Counts:
    #   - arity 6: 30 (m=1 only).
    #   - arity 8: 560 = 280 (m=1) + 280 (m=3).
    #   - arity 10: 5460 = 1260 (m=1) + 4200 (m=3).
    # The full Cai-Lu §4 enumeration would also include m ∈ {5, 7,
    # ...}; those higher configurations remain v0.7+ work.
    #
    # Practical note
    # --------------
    # In random testing at arity 6, v0.4's standard Plücker
    # enumeration plus augmented weight-1 identity already rejects
    # essentially every non-realisable signature -- the "tight
    # necessary but not provably sufficient" v0.4 caveat is more
    # theoretical than empirical at this arity. The v0.5/v0.6
    # contribution is therefore primarily MATHEMATICAL
    # COMPLETENESS: the realisability_check field reports
    # "plucker_arity_n_full" rather than the v0.4
    # "plucker_arity_n", signalling that the check now spans the
    # full m ∈ {1, 3} augmented enumeration shipped to date.
    # -----------------------------------------------------------------

    @staticmethod
    def _augmented_plucker_identities_arity_n_odd(tau, arity):
        r"""Enumerate the augmented-Pfaffian Plücker identities at
        EVEN arity >= 6, odd-parity branch.

        Enumerates all ``m ∈ {1, 3}`` configurations (with the
        configuration parameter ``m := |S \ {omega}|`` required to
        be odd with ``m + 5 <= n``):

          - ``m = 1``: ``S = {p, omega}``; 4-subset ranges over
            ``{0..n-1} \ {p}``. Count: ``n × C(n-1, 4)``.
          - ``m = 3``: ``S = {p, q, r, omega}``; 4-subset ranges
            over ``{0..n-1} \ {p, q, r}``. Count:
            ``C(n, 3) × C(n-3, 4)``. Requires ``n >= 8``.

        Total identity count: arity 6 = 30, arity 8 = 560
        (280 + 280), arity 10 = 5460 (1260 + 4200).

        Implementation note (v0.6.1)
        ----------------------------
        Delegates to
        ``holant_tools.matchgate_identities_arity_n_odd_augmented``
        and casts the returned sympy expressions to float for the
        orchestrator's tolerance-based check. v0.6.0 shipped the
        m=1 case; v0.6.1 added the m=3 case in the engine. This
        wrapper preserves the float-typed return contract for
        in-package callers.

        Returns
        -------
        list of float
            One value per identity; a matchgate-realisable signature
            has all values equal to 0.
        """
        import holant_tools as _ht
        exprs = _ht.matchgate_identities_arity_n_odd_augmented(tau, arity)
        return [float(expr) for expr in exprs]

    # -----------------------------------------------------------------
    # Auto-discovery of T (v0.3 + v0.4 -- practical fragment of Cai-Lu's SRP)
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
    # The v0.3 + v0.4 implementation ships a PRACTICAL search in
    # increasing-cost order:
    #   (0) v0.4 closed-form shortcut: when the recurrence has real
    #       roots and the arity is even, derive T directly from the
    #       roots via T = [[r_2, -1], [-r_1, 1]]. This sends the
    #       polynomial encoding A*(u+r_1*v)^n + B*(u+r_2*v)^n to
    #       (r_2-r_1)^n * (A*u^n + B*v^n), which is matchgate-standard
    #       even-parity form for even n. See
    #       :meth:`_basis_from_recurrence_kernel`.
    #   (1) v0.3 canonical bases: try a list (identity, Hadamard, swap,
    #       shears, rotation_4). Cheap and catches the most common
    #       "well-conditioned" cases.
    #   (2) v0.3 parameterised grid: parameterise T = [[1, t], [u, v]]
    #       and do a 3-D coarse grid search over (t, u, v) in the
    #       [-2, +2] range, refining the best candidate via coordinate-
    #       descent polish.
    #
    # The closed-form shortcut (step 0, new in v0.4) catches signatures
    # whose recurrence roots lie OUTSIDE the [-2, +2] grid the v0.3
    # search explores -- a documented failure mode of the v0.3
    # implementation. Even-arity signatures with two distinct real
    # roots are now handled in O(1) without any search.
    #
    # When the signature does not satisfy the order-2 recurrence,
    # discover_basis() returns (None, None) -- no basis can rescue it
    # (Cai-Lu Thm 2.5).
    # -----------------------------------------------------------------

    @staticmethod
    def _basis_from_recurrence_kernel(a: float,
                                        b: float,
                                        c: float,
                                        *,
                                        tol: float = 1e-12,
                                        ):
        r"""Derive a closed-form basis matrix T from the order-2
        recurrence kernel ``(a, b, c)`` of a symmetric signature
        satisfying ``a*z_k + b*z_{k+1} + c*z_{k+2} = 0``. Returns a
        ``(2, 2)`` numpy array, or ``None`` if no real closed-form
        derivation applies.

        The mathematics
        ---------------
        A signature satisfying the recurrence has the closed form

            z_k = A * r_1^k + B * r_2^k

        where ``r_1, r_2`` are the roots of the characteristic
        polynomial ``c*x^2 + b*x + a = 0`` and ``A, B`` are determined
        by the initial conditions.

        In ``transform_signature``'s polynomial encoding (the
        convention this module's substitution rule produces in
        practice -- ``z_k`` is the coefficient at ``u^k * v^{n-k}``
        divided by ``C(n, k)``), this corresponds to

            P(u, v) = A * (r_1*u + v)^n + B * (r_2*u + v)^n.

        Applying the basis substitution induced by

            T = [[1, -r_2], [1, -r_1]]

        (i.e. ``u_orig -> u + v``, ``v_orig -> -r_2*u - r_1*v``) sends:

            (r_1*u_orig + v_orig) -> (r_1 - r_2)*u_new      (pure u)
            (r_2*u_orig + v_orig) -> (r_2 - r_1)*v_new      (pure v)

        So the transformed polynomial is

            P_new(u, v) = A*(r_1-r_2)^n * u^n
                        + B*(-(r_1-r_2))^n * v^n.

        The transformed signature (in this module's encoding) is
        therefore ``[K*B*(-1)^n, 0, 0, ..., 0, K*A]`` with
        ``K = (r_1 - r_2)^n`` -- only ``z'_0`` and ``z'_n`` are
        non-zero.

        For EVEN arity ``n``, this is matchgate-standard EVEN-parity
        form (positions 0 and n are both even Hamming-weight). For
        ODD arity, position n is odd Hamming-weight so the result has
        entries at mixed parities and is NOT matchgate-standard. The
        caller falls through to the search.

        When this method returns None
        -----------------------------
        Three degenerate cases yield ``None`` (the caller should fall
        through to the existing search):

          1. ``|c| < tol``: the recurrence is effectively order-1 or
             trivial; the characteristic polynomial isn't quadratic.
          2. Discriminant ``b^2 - 4ac < -tol``: complex roots. The
             closed-form T would have complex entries; matchgate
             theory is defined over the reals here, so we don't try.
          3. ``|r_1 - r_2| < tol``: a double root means the two linear
             forms in the polynomial encoding coincide, the
             decomposition ``z_k = A*r_1^k + B*r_2^k`` degenerates,
             and the basis T would be singular
             (``det T = -r_1 + r_2 = r_2 - r_1``, vanishing iff
             ``r_1 = r_2``).

        Parameters
        ----------
        a, b, c : float
            Coefficients of the order-2 recurrence (typically
            obtained from ``_matchgate_realisable``'s SVD kernel
            vector).
        tol : float
            Numerical tolerance for the three degeneracy checks. Use
            the class's ``self.tol`` when calling from inside a
            method; the default here is conservative.

        Returns
        -------
        np.ndarray of shape (2, 2) or None
            The closed-form basis matrix, or None if the kernel is
            degenerate / has complex roots.
        """
        import numpy as np
        a_f, b_f, c_f = float(a), float(b), float(c)

        # Special case: degenerate quadratic from a RANK-1 signature.
        # When SVD operates on the recurrence-Hankel matrix of a
        # genuinely rank-1 signature (z_k = K*r^k), the kernel space
        # is 2-dimensional within R^3 and SVD may pick any kernel
        # direction. The most common picks are:
        #   - (a, b, 0)   -- the order-1 recurrence a*z_k + b*z_{k+1} = 0
        #                    (with r = -a/b), or
        #   - (0, b, c)   -- z_{k+1} + (c/b)*z_{k+2} = 0 (a-free).
        # Both correspond to rank-1 with single root. We derive T
        # directly:
        #
        #     P_orig = K * (r*u + v)^n
        #
        # is sent to a pure-u^n form by T = [[1, 0], [1, -r]] (using
        # this module's substitution convention). The transformed
        # signature is [0, 0, ..., 0, K*r^n] -- single non-zero at
        # position n, matchgate-standard for both even and odd arity.
        #
        # We extract the single root r from whichever degenerate
        # direction SVD returned: c=0 gives r = -a/b; a=0 gives
        # r = -b/c. The two formulas agree when both a*c and the
        # signature are consistent with rank-1.
        if abs(c_f) < tol:
            # (a, b, 0)-style kernel -- order-1 recurrence z_{k+1}
            # = r*z_k with r = -a/b.
            if abs(b_f) < tol:
                return None                   # truly trivial kernel
            r_single = -a_f / b_f
            return np.array([[1.0, 0.0], [1.0, -r_single]], dtype=float)
        if abs(a_f) < tol:
            # (0, b, c)-style kernel -- the recurrence is z_{k+1}
            # + (c/b)*z_{k+2} = 0 i.e. z_{k+2} = -(b/c)*z_{k+1}, an
            # order-1 relation on z_1..z_n with root r = -b/c.
            r_single = -b_f / c_f
            return np.array([[1.0, 0.0], [1.0, -r_single]], dtype=float)

        # Compute the characteristic-polynomial discriminant.
        # c*x^2 + b*x + a has discriminant b^2 - 4*a*c.
        disc = b_f * b_f - 4.0 * a_f * c_f

        # Case 2 (v0.5): complex roots. When disc < 0, the roots are
        # a conjugate pair r = alpha +/- i*beta with
        #   alpha = -b / (2c),   beta = sqrt(-disc) / (2c).
        # The signature in compose.py's polynomial encoding has the
        # form
        #     P(u, v) = A * ((alpha + i*beta)*u + v)^n
        #             + conj(A) * ((alpha - i*beta)*u + v)^n
        # (with B = conj(A) so the signature is real). Equivalently,
        # P(u, v) = 2 * Re[A * ((alpha*u + v) + i*beta*u)^n].
        #
        # The real basis T = [[1, -alpha], [0, beta]] (in compose.py's
        # substitution convention u_orig -> u + 0*v = u,
        # v_orig -> -alpha*u + beta*v) sends:
        #   (alpha+i*beta)*u + v
        #     = (alpha+i*beta)*u + (-alpha*u + beta*v)
        #     = i*beta*u + beta*v
        #     = beta * (v + i*u)
        # and similarly (alpha-i*beta)*u + v = beta * (v - i*u).
        # The transformed polynomial becomes
        #   P_new = beta^n * [A*(v + i*u)^n + conj(A)*(v - i*u)^n]
        #         = 2*beta^n * Re[A*(v + i*u)^n].
        # Expanding (v + i*u)^n = sum_k C(n,k) * i^k * u^k * v^{n-k},
        # the coefficient of u^k v^{n-k} carries i^k * (A + conj(A))
        # for even k and i^k * (A - conj(A)) for odd k. So the
        # transformed signature is ALTERNATE-ZERO at one parity:
        #   - k even: 2*beta^n * Re(A) * i^k    (zero when Re(A)=0)
        #   - k odd:  2*beta^n * i*Im(A) * i^k  (zero when Im(A)=0)
        # In particular, for a "balanced" real signature derived from
        # a complex-conjugate-pair decomposition with Re(A) != 0 and
        # Im(A) != 0 simultaneously, the transformed values land on
        # ONE parity branch with geometric ratio coming from i^2 = -1.
        # The result is matchgate-standard even-parity or odd-parity
        # depending on the (A_r, A_i) balance -- verified empirically
        # on NAE-3 (which has A = -conj(A) so Re(A) = 0 and the result
        # is odd-parity, matching Hadamard's [0, -2, 0, 6] up to scale).
        if disc < -tol:
            alpha = -b_f / (2.0 * c_f)
            beta = math.sqrt(-disc) / (2.0 * c_f)
            # beta must be non-zero (we already gated on disc < -tol,
            # so beta != 0 strictly).
            return np.array([[1.0, -alpha], [0.0, beta]], dtype=float)

        # Real (possibly equal) roots via the standard formula.
        # max(disc, 0) protects against tiny negative numerical
        # discriminants near zero.
        sqrt_disc = np.sqrt(max(disc, 0.0))
        r_1 = (-b_f + sqrt_disc) / (2.0 * c_f)
        r_2 = (-b_f - sqrt_disc) / (2.0 * c_f)

        # Case 3: double root. r_1 == r_2 means the two linear forms
        # in the polynomial encoding coincide and T becomes singular.
        if abs(r_1 - r_2) < tol:
            return None

        return np.array([[1.0, -r_2], [1.0, -r_1]], dtype=float)

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
            r"""Distance of the sub-sequence at ``nonzero_positions`` from
            a Cai-Gorenstein-form geometric progression, plus the cost
            of the supposedly-zero entries at ``zero_positions``.

            The Cai-Gorenstein matchgate-standard form for the EVEN
            arity case is z_{2j} = 2 * a^{n-2j} * b^{2j}. This admits
            three regimes:

              (i)  generic (both a, b non-zero): every position in
                   ``nonzero_positions`` has a non-zero value AND
                   consecutive ratios agree (the geometric
                   progression);
              (ii) ``b = 0`` degenerate: only the first position
                   (z_0) is non-zero, all the rest are zero -- this
                   is the "leading non-zero with trailing zeros"
                   pattern;
              (iii) ``a = 0`` degenerate: only the LAST position
                   (z_n) is non-zero, all the rest are zero -- the
                   "trailing non-zero with leading zeros" pattern.

            All three are LEGITIMATE matchgate-standard forms. The
            old implementation conflated regimes (ii) and (iii) with
            "interior zero breaks the geometric progression" and
            penalised them incorrectly. v0.4 fix: distinguish TRUE
            interior zeros (strictly between the first and last
            non-zero entry) from LEADING / TRAILING zeros (before the
            first or after the last non-zero entry) -- the former
            break the GP, the latter are fine.

            Why interior zeros are bad
            --------------------------
            For a GP with non-zero a and b: ALL even-indexed entries
            are non-zero (z_{2j} = 2*a^{n-2j}*b^{2j} != 0 for all j
            when a, b != 0). An interior zero (say z_2 = 0 with
            z_0 != 0 and z_4 != 0) means the progression has a hole,
            which Cai-Gorenstein form forbids. This also matches the
            matchgate-identity story: a signature like [16, 0, 0, 0, 16]
            (arity 4) fails the matchgate identity (16*16 - 0 + 0 - 0
            = 256 != 0), so it's genuinely not matchgate-realisable.
            """
            cost = float(sum(vn[i] ** 2 for i in zero_positions))
            nz = [float(vn[i]) for i in nonzero_positions]
            if all(abs(x) < tol for x in nz):
                # All claimed non-zeros are zero; the signature is
                # effectively zero on this parity -- combined with the
                # zero-positions cost gives the right answer.
                return cost

            # Find the first and last non-zero indices within `nz`.
            # Leading entries (before `first`) and trailing entries
            # (after `last`) are allowed to be zero -- those are the
            # b=0 / a=0 Cai-Gorenstein degenerate cases. ONLY entries
            # strictly between `first` and `last` count as interior
            # zeros that break the geometric progression.
            present = [j for j, x in enumerate(nz) if abs(x) >= tol]
            first, last = present[0], present[-1]

            # Penalise TRUE interior zeros (strictly between first
            # and last non-zero).
            for j in range(first + 1, last):
                if abs(nz[j]) < tol:
                    cost += 1.0

            # Geometric-progression check on the consecutive non-zero
            # range [first, last]. If only one non-zero entry
            # (first == last), the GP is trivial and cost is just the
            # zero-positions contribution (plus any interior-zero
            # penalty -- which would be zero since there's no
            # interior to check).
            if last > first:
                active = nz[first:last + 1]
                # If interior zeros remain in `active` (which means
                # we already counted them above), the ratios below
                # would explode. Bail with the already-accumulated
                # cost; the interior-zero penalty already conveys
                # the obstruction.
                if all(abs(x) >= tol for x in active):
                    ratios = [active[i + 1] / active[i]
                              for i in range(len(active) - 1)]
                    mean_ratio = float(np.mean(ratios))
                    cost += float(sum((r - mean_ratio) ** 2
                                       for r in ratios))
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

        # Step 1.5 (v0.4): closed-form shortcut via the recurrence
        # kernel. The realisability gate above already gave us the
        # kernel (a, b, c) such that a*z_k + b*z_{k+1} + c*z_{k+2} = 0.
        # When that kernel has real, distinct roots AND the arity is
        # even, T = [[r_2, -1], [-r_1, 1]] sends the signature directly
        # to matchgate-standard EVEN-parity form (see
        # :meth:`_basis_from_recurrence_kernel`). This catches the
        # signatures whose roots lie OUTSIDE the [-2, +2] grid the
        # subsequent search explores -- a documented failure mode of
        # the v0.3 implementation.
        #
        # We try the closed-form here, BEFORE the canonical-bases
        # sweep, because:
        #   (a) when it applies, it's exact (no numerical search),
        #   (b) it's free -- a single 2x2 matrix construction,
        #   (c) it has no failure mode on the cases it handles, so
        #       it never wastes work via a near-miss.
        # If the closed-form returns None (complex roots, double
        # root, odd arity that doesn't simplify), or if the resulting
        # T doesn't actually land in matchgate-standard form (which
        # can happen for the unbalanced-amplitudes case A != B), we
        # fall through to the canonical-bases search.
        kernel = id_result.recurrence_coefficients
        if kernel is not None and len(kernel) >= 3:
            T_closed = self._basis_from_recurrence_kernel(
                kernel[0], kernel[1], kernel[2], tol=self.tol,
            )
            if T_closed is not None:
                r = _try(T_closed)
                if _matches(r):
                    return T_closed, r

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

    def discover_common_basis(self,
                                signatures: List[Sequence[float]],
                                *,
                                max_grid_steps: int = 16,
                                success_tol: float = 1e-6,
                                ) -> Optional[Tuple[Any, List["HolographicBasisResult"]]]:
        r"""Find a SINGLE basis T that simultaneously puts every signature
        in ``signatures`` into a Cai-Gorenstein Theorem-9 standard-basis
        matchgate form. This is the multi-signature fragment of Cai-Lu's
        SRP (Simultaneous Realisability Problem, Cai-Lu 2011 §4).

        Strategy:

          1. Realisability gate for each signature: if ANY signature
             fails the order-2 recurrence in the standard basis, no
             common basis can rescue it (Cai-Lu Theorem 2.5 applied
             pointwise). Return ``None``.
          2. Search the same canonical-bases-plus-parameterised-grid
             space as :meth:`discover_basis`, but score each candidate
             T as the SUM of matchgate-standard distances over all
             signatures. The first T whose total distance falls below
             ``success_tol`` wins.

        Args:
          signatures: list of symmetric signatures, each a sequence
            ``[z_0, z_1, ..., z_n]``. Signatures may have different
            arities (each has its own ``len(values) - 1``).
          max_grid_steps: resolution of each axis in the grid search.
          success_tol: a candidate basis T succeeds when the SUM of
            matchgate-standard distances of T applied to each
            signature is below this. Stricter than the single-
            signature case because the failure modes compound.

        Returns:
          ``(T, results)`` where ``results`` is the list of
          :class:`HolographicBasisResult` for each input signature
          under the discovered T (in input order). Returns ``None`` if
          no common basis is found within the configured budget.
        """
        import numpy as np
        if not signatures:
            raise ValueError("discover_common_basis: empty signature list")

        # Step 1: per-signature realisability gate.
        backup_T = self.basis_matrix
        self.basis_matrix = np.eye(2)
        try:
            for sig in signatures:
                check = self.transform_signature(sig)
                if not check.is_realisable:
                    return None
        finally:
            self.basis_matrix = backup_T

        def _try(T):
            """Apply T to every signature. Returns the list of results
            (or None if any application raised)."""
            saved = self.basis_matrix
            self.basis_matrix = T
            try:
                results = []
                for sig in signatures:
                    results.append(self.transform_signature(sig))
            except (ValueError, ZeroDivisionError):
                return None
            finally:
                self.basis_matrix = saved
            return results

        def _total_distance(results) -> float:
            return float(sum(self._matchgate_standard_distance(r.values)
                              for r in results))

        # Step 2: canonical candidates.
        sqrt2_inv = 1.0 / np.sqrt(2.0)
        canonical: List[Tuple[str, Any]] = [
            ("identity", np.eye(2)),
            ("hadamard", np.array([[1.0, 1.0], [1.0, -1.0]])),
            ("swap",     np.array([[0.0, 1.0], [1.0, 0.0]])),
            ("shear_+",  np.array([[1.0, 0.0], [1.0, 1.0]])),
            ("shear_-",  np.array([[1.0, 0.0], [-1.0, 1.0]])),
            ("shearT_+", np.array([[1.0, 1.0], [0.0, 1.0]])),
            ("shearT_-", np.array([[1.0, -1.0], [0.0, 1.0]])),
            ("rotation_4", np.array([[sqrt2_inv, -sqrt2_inv],
                                       [sqrt2_inv,  sqrt2_inv]])),
        ]
        for _name, T in canonical:
            results = _try(T)
            if results is not None and _total_distance(results) < success_tol:
                return T, results

        # Step 3: parameterised grid + polish.
        best_T, best_results, best_d = None, None, float("inf")
        steps = np.linspace(-2.0, 2.0, max_grid_steps)
        for t in steps:
            for u in steps:
                for v in steps:
                    T = np.array([[1.0, t], [u, v]])
                    if abs(np.linalg.det(T)) < 1e-12:
                        continue
                    results = _try(T)
                    if results is None:
                        continue
                    d = _total_distance(results)
                    if d < best_d:
                        best_d, best_T, best_results = d, T, results
                        if d < success_tol:
                            return T, results

        if best_T is not None and best_d > success_tol:
            # Polish.
            radius = 0.5
            for _outer in range(4):
                improved = False
                for axis in range(3):
                    for delta in (-radius, +radius):
                        T_try = best_T.copy()
                        if   axis == 0: T_try[0, 1] += delta
                        elif axis == 1: T_try[1, 0] += delta
                        else:           T_try[1, 1] += delta
                        if abs(np.linalg.det(T_try)) < 1e-12:
                            continue
                        results = _try(T_try)
                        if results is None:
                            continue
                        d = _total_distance(results)
                        if d < best_d:
                            best_d, best_T, best_results = d, T_try, results
                            improved = True
                if not improved:
                    radius *= 0.5
                if best_d < success_tol:
                    return best_T, best_results

        if best_T is not None and best_d < success_tol:
            return best_T, best_results
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
      is_realisable: True iff the transformed signature is matchgate-
        realisable on the standard basis. For SYMMETRIC results: based
        on the Cai-Lu 2011 order-2 recurrence (Theorem 2.5). For
        GENERAL results: based on parity plus the matchgate identities
        from ``holant_tools.non_symmetric`` (v0.4). ``None`` only when
        the check is deferred (e.g., an unsupported arity).
      recurrence_coefficients: when realisable (symmetric only), the
        (a, b, c) kernel vector such that a z'_k + b z'_{k+1} +
        c z'_{k+2} = 0; None otherwise.
      basis_matrix: the 2x2 matrix T applied.
      realisability_check: name of the check that produced
        ``is_realisable``. One of:
          - ``"order_2_recurrence"`` — symmetric path via Cai-Lu Thm 2.5.
          - ``"parity_only"`` — general arity < 4 (Valiant 2008
            Propositions 6.1, 6.2 — no matchgate identities exist
            beyond parity below arity 4).
          - ``"matchgate_identity_arity_4"`` — general arity 4 via the
            Grassmann-Pluecker (even parity) and augmented-Pfaffian
            (odd parity) identities. Sufficient check.
          - ``"plucker_arity_n"`` — general arity >= 5 via the standard
            Plücker enumeration plus, for even arities, the augmented
            weight-1 identity. Complete for even-parity arity-5; a
            tight necessary check (but not provably sufficient) at
            arity >= 6 odd-parity.
          - ``"deferred"`` — the check was skipped (e.g., the values
            are all near-zero so the question is degenerate).
          - ``None`` — no check applicable (e.g., bare construction).
    """
    values: List[float]
    is_realisable: Optional[bool]
    recurrence_coefficients: Optional[Any]
    basis_matrix: Any
    realisability_check: Optional[str] = None


@dataclasses.dataclass
class BranchSum:
    r"""A sum over named branches, each branch being an in-family
    sub-problem with a (possibly complex) amplitude coefficient. The
    combined result is ``sum(amplitude_i * sub_evaluator(branch_i))``.

    Where :class:`LinearCombination` treats coefficients as opaque
    floats with no per-branch metadata, ``BranchSum`` keeps each branch
    as a named ``Branch(name, amplitude, sub_problem)`` triple so the
    trace records which physical branch contributed how much. This is
    the abstract form of the amplitude-level recombination used in
    ``free-fermion-quantum-simulation/hybrid-dispatcher`` -- there, the
    branches are the two outcomes of a Clifford+T extraction at each
    T-gate, with amplitudes (cos(pi/8), -i sin(pi/8)).

    Use case: a quantity Q decomposes as
        Q = sum_i amp_i * sub_eval(branch_i)
    where each branch is matchgate-Holant in-family and ``amp_i`` is a
    branch-specific amplitude (possibly complex). The framework runs
    each branch, multiplies by its amplitude, and sums.

    Example::

        bs = BranchSum(
            name="Clifford+T recombination",
            branches=[
                BranchSum.Branch("|+>", 0.9239, problem_plus),
                BranchSum.Branch("|->", 0.3827j, problem_minus),
            ],
        )
        Q = bs.evaluate(framework_evaluator)
    """

    @dataclasses.dataclass
    class Branch:
        """A single named branch with its amplitude and sub-problem."""
        name: str
        amplitude: Any
        sub_problem: Any

    name: str
    branches: List["BranchSum.Branch"]

    @property
    def sub_problems(self) -> List[Any]:
        """The in-family sub-problems, one per branch, in branch order.
        Provided for Composition-protocol conformance."""
        return [b.sub_problem for b in self.branches]

    @property
    def combine(self):
        amps = [b.amplitude for b in self.branches]
        def _combine(values: List[Any]) -> Any:
            total = 0
            for amp, val in zip(amps, values):
                total = total + amp * val
            return total
        return _combine

    def evaluate(self, sub_evaluator: Callable[[Any], Any]) -> Any:
        """Evaluate each branch via ``sub_evaluator``, multiply by the
        branch's amplitude, and sum. The amplitudes may be complex
        (e.g., Clifford+T amplitudes); the sum's type follows."""
        total = 0
        for branch in self.branches:
            val = sub_evaluator(branch.sub_problem)
            total = total + branch.amplitude * val
        return total


__all__ = [
    "Composition",
    "CompositionPlan",
    "LinearCombination",
    "Projection",
    "HolographicBasisPair",
    "BranchSum",
]
