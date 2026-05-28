"""08 -- Auto-rationalised weighted matching sum via the orchestrator.

Many reliability / risk / probabilistic problems have edge weights that
are FLOATS (failure probabilities, decay coefficients, etc.). The exact
matchgate-Pfaffian machinery wants INTEGER weights so it can compute in
exact arithmetic without float drift.

`RationaliseWeights` is the bridge: it scales every weight by 10^precision
and rounds to integers, then remembers the inverse so the answer can be
divided back at the end. The orchestrator wires this into Phase 1.5 so
the user just supplies `hints['rationalise_precision']` and everything
works end-to-end.

The discretisation error is bounded by O(10^(-precision) * |E|) times the
largest matching contribution -- the user chooses the precision based on
the accuracy they need.
"""
from structural_computing import Orchestrator

# A 4-cycle (C_4) with real-valued edge weights.
# Two perfect matchings:
#   M_1 = {(0,1), (2,3)}  -- weight 0.7 * 0.5 = 0.35
#   M_2 = {(1,2), (3,0)}  -- weight 0.3 * 0.9 = 0.27
# Total weighted matching sum = 0.62
graph = {
    "rotation": {0: [1, 3], 1: [0, 2], 2: [1, 3], 3: [0, 2]},
    "vertices": [0, 1, 2, 3],
    "edges": [(0, 1), (1, 2), (2, 3), (3, 0)],
    "weights": {(0, 1): 0.7, (1, 2): 0.3, (2, 3): 0.5, (3, 0): 0.9},
}

orch = Orchestrator()
result = orch.evaluate(
    graph,
    question="weighted_matching_sum",
    hints={"rationalise_precision": 6},      # 6 decimal places of precision
)

print(f"weighted matching sum: {result.answer}")
print(f"expected:              0.62")
print(f"reductions applied:    {result.reductions_applied}")
print()
print("Workflow trace:")
for step in result.workflow_trace:
    print(f"  [{step.phase}] {step.action}  ->  {step.outcome}")
    if step.detail:
        print(f"      detail: {step.detail}")
