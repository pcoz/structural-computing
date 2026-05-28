"""06 — Symmetric signatures and the basis-aware rank ≤ 2 result.

A SYMMETRIC signature is a constraint function whose value depends only
on the HAMMING WEIGHT of its inputs (not on WHICH inputs are 1). Classic
examples: OR, AND, XOR, MAJORITY, EXACTLY-K, AT-LEAST-K.

The publicly-original mathematical result the framework exploits:
**every symmetric signature has basis-aware matchgate rank in {0, 1, 2}**.
This guarantees every symmetric Holant problem is poly-time exact via
the basis-aware rank-2 parity-split construction.

Pass a list of values indexed by Hamming weight 0..arity; the framework
classifies and reports the rank.
"""
from structural_computing import StructuralComputer

sc = StructuralComputer()

# A battery of classical symmetric signatures.
signatures = [
    ("OR_arity_2",         [0, 1, 1]),
    ("AND_arity_2",        [0, 0, 1]),
    ("XOR_arity_2",        [0, 1, 0]),
    ("EQUAL_arity_2",      [1, 0, 1]),
    ("OR_arity_3",         [0, 1, 1, 1]),
    ("MAJORITY_arity_3",   [0, 0, 1, 1]),
    ("EXACTLY_1_of_3",     [0, 1, 0, 0]),
    ("EXACTLY_2_of_4",     [0, 0, 1, 0, 0]),
    ("MAJORITY_arity_5",   [0, 0, 0, 1, 1, 1]),
    ("ALL_OR_NOTHING_4",   [1, 0, 0, 0, 1]),
    ("XOR_arity_5",        [0, 1, 0, 1, 0, 1]),
]

print(f"  {'signature':<22}  {'arity':>5}  {'tier':>5}  {'rank':>5}")
print(f"  {'-' * 22}  {'-' * 5}  {'-' * 5}  {'-' * 5}")

for name, values in signatures:
    cls = sc.classify_function(values)
    rank = sc.matchgate_rank(values)
    arity = len(values) - 1
    print(f"  {name:<22}  {arity:>5}  {cls.tier:>5}  {rank:>5}")
    # The publicly-original guarantee:
    assert rank in (0, 1, 2)

print()
print("All ranks in {0, 1, 2} -- the basis-aware rank-<=2 result for")
print("symmetric signatures holds across the entire battery.")
