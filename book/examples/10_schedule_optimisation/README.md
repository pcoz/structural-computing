# Example: Schedule optimisation in one line

This folder accompanies Chapter 10 of the book. It shows the
contrast between a brute-force "try every assignment" approach
and the framework's `min_cost_schedule` call, on a small but
realistic OR-scheduling instance.

## What's in this folder

- `or_scheduling.py` — a small operating-room scheduling
  example. 5 surgeries, 5 rooms, cost based on surgeon
  preferences. Compares brute-force enumeration with
  `sc.min_cost_schedule`.
- `README.md` — this file.

## What you'll see

Run it:

```bash
cd book/examples/10_schedule_optimisation
python or_scheduling.py
```

Expected output:

```
OR scheduling: 5 surgeries to 5 rooms

Brute force (try all 5! = 120 assignments):
  optimal cost: 13.0
  schedule:     {'S1': 'R1', 'S2': 'R2', ...}
  wall-clock:   0.0023 sec

Framework (sc.min_cost_schedule):
  optimal cost: 13.0
  schedule:     {'S1': ('R1', 0), 'S2': ('R2', 0), ...}
  wall-clock:   0.0008 sec

Both agree on optimum.

Structural diagnostic (sc.tropical_instance_coordinates):
  admissibility_rank_1:           True
  polynomial_time_optimisation:   True
  -> framework will solve every instance of this shape
     in polynomial time, no matter how big it gets.
```

For this tiny example the brute-force version is fine. The
point is the **scaling**: at 5×5 there are 120 assignments;
at 10×10 there are 3.6 million; at 20×20 there are 2.4×10¹⁸.

The brute-force approach becomes infeasible quickly. A MIP
solver does better but has unbounded worst-case time. The
framework runs in polynomial time (`O(n^3)`) regardless of
size — for 100×100, it returns in milliseconds.

## What this demonstrates

A real OR scheduling problem at a mid-sized hospital might
have 50 surgeries across 10 rooms with multiple time slots
each day. The brute-force enumeration is out of the question
at that scale. A MIP solver works but takes minutes to hours,
and sometimes times out. The framework's `min_cost_schedule`
returns in well under a second.

The framework also tells you, before committing, whether your
specific cost structure is amenable to the polynomial-time
path. The `tropical_instance_coordinates` call (also shown in
the example) does this. If it returns `polynomial_time_optimisation: True`,
the framework will solve any instance of this shape in
polynomial time. If False, the framework honest-stops and you
fall back to MIP.

## What stays the same vs what changes

The input parsing (loading surgeries and rooms from your EMR)
and output formatting (producing the schedule in the OR
coordinator's expected format) are *not* replaced by the
framework. They stay as they were.

What's replaced is the *optimisation core* — the part that
takes the problem in canonical form, computes the optimal
assignment, and returns it. The MIP-form optimisation core
might be several hundred lines including the constraint-
building boilerplate. The framework-form optimisation core is
one line.

That's the 100,000-to-10 collapse pattern again: the
optimisation core shrinks; the input/output layers stay; the
total reduction is large but not the headline 10×.
