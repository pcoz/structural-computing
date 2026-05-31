"""OR-scheduling worked example for Chapter 10 of the book.

Compares brute-force enumeration with the framework's
sc.min_cost_schedule on a small operating-room scheduling
instance.
"""
import itertools
import time

import holant_tools
from structural_computing import StructuralComputer


def build_or_instance(n: int = 5, seed: int = 42):
    """Build a small OR scheduling instance: n surgeries, n rooms,
    cost matrix encoding surgeon preferences.

    Each surgery has a "preferred room"; assigning it to its preferred
    room costs 1, every other room costs 5. (A rank-1 cost matrix:
    polynomial-time exact via the framework.)
    """
    surgeries = [f"S{i+1}" for i in range(n)]
    rooms = [f"R{i+1}" for i in range(n)]
    # Each surgery prefers a specific room.
    import random
    rng = random.Random(seed)
    preferred = {s: rng.choice(rooms) for s in surgeries}
    costs = {}
    for s in surgeries:
        for r in rooms:
            costs[(s, r)] = 1.0 if r == preferred[s] else 5.0
    return surgeries, rooms, costs


def brute_force_optimal(surgeries, rooms, costs):
    """Try every assignment of surgeries to rooms, return the cheapest."""
    n = len(surgeries)
    best_cost = float("inf")
    best_schedule = None
    for perm in itertools.permutations(rooms):
        # Assignment: surgery i → perm[i]
        total = sum(costs[(s, r)] for s, r in zip(surgeries, perm))
        if total < best_cost:
            best_cost = total
            best_schedule = dict(zip(surgeries, perm))
    return best_cost, best_schedule


def framework_optimal(surgeries, rooms, costs):
    """Use sc.min_cost_schedule for the same question."""
    sc = StructuralComputer()
    jobs = [holant_tools.Job(name=s) for s in surgeries]
    machines = [holant_tools.Machine(name=r) for r in rooms]
    instance = holant_tools.SchedulingInstance(jobs=jobs, machines=machines)

    def cost_fn(job, machine, slot):
        return costs[(job.name, machine.name)]

    result = sc.min_cost_schedule(instance, cost_fn)
    return result


def main():
    n = 5
    surgeries, rooms, costs = build_or_instance(n)

    print(f"OR scheduling: {n} surgeries to {n} rooms\n")

    # Brute force
    t0 = time.perf_counter()
    bf_cost, bf_schedule = brute_force_optimal(surgeries, rooms, costs)
    bf_seconds = time.perf_counter() - t0
    print(f"Brute force (try all {n}! = "
          f"{1 if n == 0 else __import__('math').factorial(n)} assignments):")
    print(f"  optimal cost: {bf_cost}")
    print(f"  schedule:     {bf_schedule}")
    print(f"  wall-clock:   {bf_seconds:.4f} sec\n")

    # Framework
    t0 = time.perf_counter()
    fw_result = framework_optimal(surgeries, rooms, costs)
    fw_seconds = time.perf_counter() - t0
    print(f"Framework (sc.min_cost_schedule):")
    print(f"  optimal cost: {fw_result['cost']}")
    print(f"  schedule:     {fw_result['schedule']}")
    print(f"  wall-clock:   {fw_seconds:.4f} sec\n")

    if abs(fw_result['cost'] - bf_cost) < 1e-9:
        print("Both agree on optimum.\n")
    else:
        print(f"DISAGREEMENT: brute force {bf_cost} vs framework {fw_result['cost']}\n")

    # Structural diagnostic
    sc = StructuralComputer()
    jobs = [holant_tools.Job(name=s) for s in surgeries]
    machines = [holant_tools.Machine(name=r) for r in rooms]
    instance = holant_tools.SchedulingInstance(jobs=jobs, machines=machines)

    def cost_fn(job, machine, slot):
        return costs[(job.name, machine.name)]

    coords = sc.tropical_instance_coordinates(instance, cost_fn)
    print(f"Structural diagnostic (sc.tropical_instance_coordinates):")
    print(f"  admissibility_rank_1:         {coords.admissibility_rank_1}")
    print(f"  polynomial_time_optimisation: {coords.polynomial_time_optimisation}")
    print(f"  -> framework will solve every instance of this shape")
    print(f"     in polynomial time, no matter how big it gets.")


if __name__ == "__main__":
    main()
