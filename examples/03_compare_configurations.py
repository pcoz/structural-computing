"""03 — Compare two configurations below the Monte-Carlo noise floor.

Two candidate network topologies. They both look "about the same" to
sampling-based reliability tools. Are they actually different in the
rare tail? By how much?

This is the question regulators care about. The framework produces a
bit-identical reproducible verdict (no sampling noise).
"""
from structural_computing import StructuralComputer

sc = StructuralComputer()

# Two configurations on the same vertex set.
config_a = [(0, 1), (1, 2), (2, 3), (3, 0)]                       # 4-cycle
config_b = [(0, 1), (0, 2), (0, 3),                                # K_4
            (1, 2), (1, 3), (2, 3)]

# Compare them on rare-tail reliability at p_fail = 0.05.
report = sc.compare(config_a, config_b, p_fail=0.05)

print(report.explain())
print()
print(f"  A tail probability:      {report.quantity_a:.4e}")
print(f"  B tail probability:      {report.quantity_b:.4e}")
print(f"  more reliable:           {report.more_reliable}")
print(f"  relative difference:     {report.relative_difference:+.1%}")
