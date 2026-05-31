"""CP-SAT pre-flight rewrite for Chapter 11 of the book.

Shows the framework operating as a pre-flight layer on a small
CP-SAT model: it identifies a rank-explosive cardinality constraint,
rewrites it into a rank-1 time-slot form, verifies equivalence,
and the resulting rewritten model is then solved by the regular
CP-SAT solver.
"""
from ortools.sat.python import cp_model

from structural_computing import StructuralComputer


def build_model(n: int = 8, k: int = 4):
    """Build a tiny CP-SAT model: n booleans, one cardinality
    constraint sum(xs) == k. Feasible set has size C(n, k)."""
    model = cp_model.CpModel()
    xs = [model.NewBoolVar(f"x{i}") for i in range(n)]
    model.Add(sum(xs) == k)
    return model, xs


def show_solution(solver, xs):
    return " ".join(f"x{i}={solver.Value(x)}" for i, x in enumerate(xs))


def main():
    print("CP-SAT pre-flight rewrite on cardinality constraint\n")

    model, xs = build_model(n=8, k=4)
    print(f"Original model: {len(xs)} boolean variables, "
          f"constraint sum(xs) == 4")

    sc = StructuralComputer()
    result = sc.rewrite_cpsat_model(model)

    print(f"Rewritten model:")
    print(f"  helped: {result.helped}")
    print(f"  reason: {result.help_reason_text}")
    print(f"  num_original_variables: {result.num_original_variables}")
    print(f"  num_aux_variables: {result.aux_variable_count}")
    print(f"  num_total_variables: "
          f"{result.num_original_variables + result.aux_variable_count}\n")

    if not result.helped:
        print("Framework couldn't help. Falling back to original CP-SAT solve.\n")
        # Solve the original model.
        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        print(f"  status: {solver.StatusName(status)}")
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            print(f"  one solution: {show_solution(solver, xs)}")
        return

    # Verify
    verify = sc.verify_cpsat_rewrite(model, result, enumeration_limit=1000)
    print(f"Verification:")
    print(f"  equivalent: {verify.equivalent}")
    print(f"  n_original_solutions: {verify.n_original_solutions} "
          f"(= C(8, 4) = 70, as expected)\n")

    if not verify.equivalent:
        print("WARNING: rewrite changed the feasible set!")
        print(f"  Missing witnesses: {verify.missing_witnesses}")
        print(f"  Spurious witnesses: {verify.spurious_witnesses}")
        return

    # Solve rewritten
    print("Solving rewritten model with CP-SAT...")
    solver = cp_model.CpSolver()
    status = solver.Solve(result.rewritten_model)
    print(f"  status: {solver.StatusName(status)}")
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        print(f"  one solution: {show_solution(solver, xs)}")


if __name__ == "__main__":
    main()
