"""Network-reliability example for Chapter 9 of the book.

Compares a from-scratch Monte Carlo simulator with the framework's
exact polynomial-time call on a small planar grid.

Run with no arguments for the basic comparison, or with --scale
for the scaling test.
"""
import argparse
import math
import random
import time

from structural_computing import StructuralComputer
from structural_computing.verifier import brute_force_count_matchings


def build_grid_graph(rows: int, cols: int):
    """Build a planar `rows`x`cols` grid graph + rotation system."""
    vertices = [(r, c) for r in range(rows) for c in range(cols)]
    edges = []
    for r in range(rows):
        for c in range(cols):
            if c + 1 < cols:
                edges.append(((r, c), (r, c + 1)))
            if r + 1 < rows:
                edges.append(((r, c), (r + 1, c)))
    # Build a planar rotation system: at each vertex, neighbours
    # appear in CCW order (right, down, left, up when present).
    rotation = {}
    for (r, c) in vertices:
        ccw = []
        if c + 1 < cols:
            ccw.append((r, c + 1))
        if r + 1 < rows:
            ccw.append((r + 1, c))
        if c - 1 >= 0:
            ccw.append((r, c - 1))
        if r - 1 >= 0:
            ccw.append((r - 1, c))
        rotation[(r, c)] = ccw
    return {"vertices": vertices, "edges": edges, "rotation": rotation}


def monte_carlo_failure_probability(graph, p_fail, n_samples, seed=42):
    """The "Monte Carlo simulator" form of the question.

    For each sample, randomly drop each edge with probability p_fail
    and check whether the remaining graph still has a perfect matching.
    The estimate is the fraction of samples with NO surviving matching.
    """
    rng = random.Random(seed)
    edges = graph["edges"]
    vertices = graph["vertices"]
    failures = 0
    for _ in range(n_samples):
        surviving = [e for e in edges if rng.random() > p_fail]
        if brute_force_count_matchings(vertices, surviving) == 0:
            failures += 1
    return failures / n_samples


def monte_carlo_confidence_interval(estimate, n_samples, confidence=0.95):
    """Standard normal-approximation 95% CI on a binomial estimate."""
    if n_samples <= 0:
        return (estimate, estimate)
    z = 1.96 if confidence == 0.95 else 2.58
    se = math.sqrt(estimate * (1 - estimate) / n_samples)
    return (max(0.0, estimate - z * se), min(1.0, estimate + z * se))


def run_basic_comparison():
    # 2x4 grid: 8 vertices (even), 10 edges. Small enough that the
    # framework's exact computation (which enumerates 2^|E| subsets
    # internally) is fast, and large enough that the MC simulator
    # gives a meaningful approximation. Real applications run on
    # much larger inputs where exact via FKT remains polynomial-
    # time while MC remains exponential.
    rows, cols = 2, 4
    p_fail = 0.10
    n_samples = 10_000

    graph = build_grid_graph(rows, cols)
    sc = StructuralComputer()

    print(f"Network: {rows}x{cols} grid with {len(graph['edges'])} edges, "
          f"p_fail per edge = {p_fail}\n")

    # Monte Carlo
    t0 = time.perf_counter()
    mc_estimate = monte_carlo_failure_probability(graph, p_fail, n_samples)
    mc_seconds = time.perf_counter() - t0
    mc_ci = monte_carlo_confidence_interval(mc_estimate, n_samples)

    print(f"Monte Carlo ({n_samples:,} samples):")
    print(f"  estimate: {mc_estimate:.5f}")
    print(f"  95% CI:   [{mc_ci[0]:.4f}, {mc_ci[1]:.4f}]")
    print(f"  wall-clock: {mc_seconds:.2f} sec\n")

    # Framework. The StructuralComputer wrapper takes an edge list
    # (or rotation dict / adjacency dict) directly; it does its own
    # normalisation.
    t0 = time.perf_counter()
    exact = sc.tail_probability(graph["edges"], p_fail=p_fail)
    fw_seconds = time.perf_counter() - t0

    print(f"Framework (sc.tail_probability):")
    print(f"  exact:      {exact:.5f}")
    print(f"  wall-clock: {fw_seconds:.4f} sec\n")

    speedup = mc_seconds / fw_seconds if fw_seconds > 0 else float("inf")
    in_ci = mc_ci[0] <= exact <= mc_ci[1]
    print(f"Speedup:  {speedup:,.0f}x")
    print(f"MC and exact agree: {in_ci} "
          f"(framework's exact value is "
          f"{'inside' if in_ci else 'outside'} MC's 95% CI)")


def run_scaling_test():
    sc = StructuralComputer()
    print("Framework runtime as a function of grid size (no MC comparison):\n")
    print(f"{'Grid':>10} {'Vertices':>10} {'Edges':>10} {'Wall-clock':>12} {'Tail prob':>12}")
    # Use even-vertex-count grids only (odd ⇒ no PM possible).
    # Both dimensions even, or one even and one odd to keep total even.
    sizes = [(2, 4), (2, 6), (2, 8), (4, 4), (3, 4), (3, 6)]
    for (rows, cols) in sizes:
        graph = build_grid_graph(rows, cols)
        t0 = time.perf_counter()
        try:
            exact = sc.tail_probability(graph["edges"], p_fail=0.10)
            seconds = time.perf_counter() - t0
            print(f"{rows}x{cols:>7} {len(graph['vertices']):>10} "
                  f"{len(graph['edges']):>10} {seconds:>10.3f}s "
                  f"{exact:>12.5f}")
        except Exception as e:
            seconds = time.perf_counter() - t0
            print(f"{rows}x{cols:>7} {len(graph['vertices']):>10} "
                  f"{len(graph['edges']):>10} {seconds:>10.3f}s "
                  f"  (skip: {type(e).__name__})")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scale", action="store_true",
                        help="Run the scaling test instead of the basic comparison")
    args = parser.parse_args()
    if args.scale:
        run_scaling_test()
    else:
        run_basic_comparison()


if __name__ == "__main__":
    main()
