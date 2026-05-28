"""04 — The Orchestrator: just give me an exact answer.

The Orchestrator wraps the classifier + leaf evaluators + reductions
into a single `evaluate(problem, question)` interface. It either:

  - dispatches directly to the right in-family evaluator, or
  - applies a registered reduction to bring the problem in-family, or
  - honestly stops with a NoKnownReduction verdict and the classification
    attached so you can inspect what was tried.
"""
from structural_computing import Orchestrator, NoKnownReduction

orch = Orchestrator()


# 1. K_4 -- planar, T2. Direct dispatch via the leaf-evaluator registry.
K4 = {
    "rotation": {0: [1, 2, 3], 1: [0, 3, 2], 2: [0, 1, 3], 3: [0, 2, 1]},
    "vertices": [0, 1, 2, 3],
    "edges": [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)],
}
result = orch.evaluate(K4, question="matching_count")
print(f"K_4:  answer={result.answer}, tier={result.classification.tier}, "
      f"evaluator={result.leaf_evaluator_used}")


# 2. K_{3,3} -- non-planar. The default registry handles T4 too via brute
#    force at small n, so direct dispatch still works.
K33 = {
    "rotation": {0: [3, 4, 5], 1: [3, 4, 5], 2: [3, 4, 5],
                 3: [0, 1, 2], 4: [0, 1, 2], 5: [0, 1, 2]},
    "vertices": [0, 1, 2, 3, 4, 5],
    "edges": [(0, 3), (0, 4), (0, 5),
              (1, 3), (1, 4), (1, 5),
              (2, 3), (2, 4), (2, 5)],
}
result = orch.evaluate(K33, question="matching_count")
print(f"K_3,3: answer={result.answer}, tier={result.classification.tier}, "
      f"reductions_applied={result.reductions_applied}")


# 3. An unsupported question -> NoKnownReduction with classification attached.
try:
    orch.evaluate(K4, question="compute_widget_count")
except NoKnownReduction as e:
    print()
    print(f"Unsupported question: {e}")
    print(f"  classification tier: {e.classification.tier}")
    print(f"  attempted: {e.attempted}")
