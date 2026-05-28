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
    """Two matchgates with coordinated bases that, together, compute a
    quantity neither could alone.

    This is Valiant 2004's central technique and the engine behind most
    known holographic algorithms (Cai-Lu-Xia). The framework's classifier
    extension to recognise when a basis-pair composition is available
    is the v0.2 deliverable.

    Status: not implemented in v0.1.
    """
    name = "HolographicBasisPair"

    def evaluate(self, sub_evaluator):
        raise NotImplementedError(
            f"{self.name} is on the v0.2 roadmap."
        )


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
