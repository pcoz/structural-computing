r"""Aggregated routing trace for the pipeline-router.

Extends the minimal `Trace` in `pipeline_router.py` with:

  * cost breakdowns by member and by tier (both log-budget and log-of-total-ops);
  * detailed regime-change records (which member flipped to which, and the
    cost delta) rather than just the indices;
  * window slicing -- aggregate over `records[start:end]`;
  * a structured `summary()` text suitable for printing.

Use as a drop-in replacement for `Trace` when calling `run_pipeline`:

    from trace import RichTrace
    rt = RichTrace()
    final, _ = run_pipeline(stages, trace=rt)
    print(rt.summary())
    rt.regime_changes_detailed()
    rt.cost_by_member(), rt.ops_by_member()
    rt.window(100, 200).summary()         # diagnose a 100-stage window
"""
import dataclasses
import io
import math
from typing import Dict, List, Optional

from .pipeline_router import Trace, StageRecord


@dataclasses.dataclass
class RegimeChange:
    """One detected regime change: the stage index where the route member
    changed, plus what changed (previous member, new member, log-cost delta)."""
    index: int
    prev_member: str
    new_member: str
    delta_cost: float


def _log2_sum_of_2pow(values):
    """log2(sum 2^v_i), numerically stable. Empty -> -inf (= log of 0 ops)."""
    finite = [v for v in values if not math.isinf(v)]
    if not finite:
        return math.inf if any(math.isinf(v) for v in values) else float("-inf")
    has_inf = any(math.isinf(v) for v in values)
    if has_inf:
        return math.inf
    cmax = max(finite)
    return cmax + math.log2(sum(2.0 ** (v - cmax) for v in finite))


class RichTrace(Trace):
    """A `Trace` with aggregation utilities. Stores the same `records` list as
    its parent; all methods are pure queries over that list."""

    # -- per-member / per-tier breakdowns ------------------------------------

    def cost_by_member(self) -> Dict[str, float]:
        """Member -> sum of per-stage log2-costs (a budget-like score)."""
        out: Dict[str, float] = {}
        for r in self.records:
            out[r.route.member] = out.get(r.route.member, 0.0) + r.route.cost
        return out

    def ops_by_member(self) -> Dict[str, float]:
        """Member -> log2(total ops) actually attributable to that member,
        i.e. log2 of the SUM of 2^cost across stages routed to that member."""
        groups: Dict[str, List[float]] = {}
        for r in self.records:
            groups.setdefault(r.route.member, []).append(r.route.cost)
        return {m: _log2_sum_of_2pow(cs) for m, cs in groups.items()}

    def cost_by_tier(self) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for r in self.records:
            key = r.route.tier or "-"
            out[key] = out.get(key, 0.0) + r.route.cost
        return out

    def ops_by_tier(self) -> Dict[str, float]:
        groups: Dict[str, List[float]] = {}
        for r in self.records:
            key = r.route.tier or "-"
            groups.setdefault(key, []).append(r.route.cost)
        return {k: _log2_sum_of_2pow(cs) for k, cs in groups.items()}

    # -- detailed regime changes ---------------------------------------------

    def regime_changes_detailed(self) -> List[RegimeChange]:
        """Like `regime_changes` but returns full records: the index, previous
        and new member, and the cost delta (new - prev) in log2 ops."""
        out: List[RegimeChange] = []
        for i in range(1, len(self.records)):
            a, b = self.records[i - 1].route, self.records[i].route
            if a.member != b.member:
                out.append(RegimeChange(
                    index=i,
                    prev_member=a.member,
                    new_member=b.member,
                    delta_cost=(b.cost - a.cost) if not (math.isinf(a.cost) or math.isinf(b.cost)) else float("nan"),
                ))
        return out

    # -- windowing ------------------------------------------------------------

    def window(self, start: int, end: Optional[int] = None) -> "RichTrace":
        """A new RichTrace containing only records[start:end]."""
        sub = RichTrace()
        sub.records = list(self.records[start:end])
        return sub

    # -- structured summary --------------------------------------------------

    def summary(self) -> str:
        """A multiline tabular summary suitable for printing at the end of a
        run. Tries to fit a long-pipeline output in O(20) lines: per-member
        table, per-tier table, top regime changes, totals."""
        n = self.stages
        regimes = self.regime_changes_detailed()
        cbm = self.cost_by_member()
        obm = self.ops_by_member()
        cbt = self.cost_by_tier()
        obt = self.ops_by_tier()
        total_budget = self.total_log_budget()
        total_ops = self.total_ops_cost()

        f = io.StringIO()
        print(f"Pipeline trace -- {n} stages, {len(regimes)} regime changes", file=f)
        print(f"  total log-budget   = {total_budget:.2f}    (sum of per-stage log2-costs)", file=f)
        print(f"  total log-ops      = {_fmt_inf(total_ops)}    (log2 of total operations)", file=f)
        print(file=f)

        # by-member
        print("  by member                              stages   log_ops    log_budget", file=f)
        print("  ------------------------------------   ------   --------   ----------", file=f)
        m_counts = self.member_histogram()
        for m in sorted(m_counts, key=lambda m: -m_counts[m]):
            print(f"  {m:<36}   {m_counts[m]:>6}   {_fmt_inf(obm.get(m, float('-inf'))):>8}   "
                  f"{cbm.get(m, 0.0):>10.2f}", file=f)
        print(file=f)

        # by-tier
        print("  by tier   stages   log_ops    log_budget", file=f)
        print("  -------   ------   --------   ----------", file=f)
        t_counts = self.tier_histogram()
        for t in sorted(t_counts):
            print(f"  {t:<7}   {t_counts[t]:>6}   {_fmt_inf(obt.get(t, float('-inf'))):>8}   "
                  f"{cbt.get(t, 0.0):>10.2f}", file=f)
        print(file=f)

        # top regime changes (truncate; full list available via the method)
        if regimes:
            shown = regimes[: min(6, len(regimes))]
            print(f"  regime changes (showing {len(shown)} of {len(regimes)}):", file=f)
            for rc in shown:
                delta = "n/a" if math.isnan(rc.delta_cost) else f"{rc.delta_cost:+.2f}"
                print(f"    stage {rc.index:>4}: {rc.prev_member} -> {rc.new_member}  "
                      f"(delta_cost log2 ops = {delta})", file=f)
        else:
            print("  regime changes: none (single dominant member across the run)", file=f)
        return f.getvalue()


def _fmt_inf(v: float) -> str:
    if math.isinf(v):
        return "inf" if v > 0 else "-inf"
    return f"{v:.2f}"


# ---------------------------------------------------------------------------
# Self-test:
#   1. cost_by_member / ops_by_member give the right log vs log-of-sum split.
#   2. regime_changes_detailed records prev/new members + a cost delta.
#   3. window(start, end) yields a sub-trace whose aggregates are recomputed.
#   4. summary() prints something parseable for a small pipeline.
# ---------------------------------------------------------------------------

def self_test():
    from .pipeline_router import Stage, Route, run_pipeline

    def route_ff(data, prev):
        return Route(member="free-fermion", cost=3.0, tier="T2")
    def route_ch(data, prev):
        return Route(member="ch-form", cost=5.0, tier="T0")
    def runner(data, prev, route):
        return prev

    # 1000 stages, alternating in blocks of 100 between FF and CH-form.
    stages = []
    for i in range(1000):
        rfn = route_ff if (i // 100) % 2 == 0 else route_ch
        stages.append(Stage(f"s_{i}", "k", None, rfn, runner))
    rt = RichTrace()
    _, _ = run_pipeline(stages, trace=rt)

    # 1. by-member: 500 ff + 500 ch.
    cbm = rt.cost_by_member()
    obm = rt.ops_by_member()
    assert cbm["free-fermion"] == 500 * 3.0
    assert cbm["ch-form"] == 500 * 5.0
    # ops_by_member: log2(500 * 2^3) = 3 + log2(500); log2(500 * 2^5) = 5 + log2(500)
    assert abs(obm["free-fermion"] - (3.0 + math.log2(500))) < 1e-9
    assert abs(obm["ch-form"] - (5.0 + math.log2(500))) < 1e-9
    print("  [cost/ops by-member: 500 FF + 500 CH-form, exact log-budget and log-ops]")

    # 2. regime_changes_detailed: 9 transitions, alternating FF<->CH.
    rcs = rt.regime_changes_detailed()
    assert len(rcs) == 9, len(rcs)
    assert rcs[0].prev_member == "free-fermion" and rcs[0].new_member == "ch-form"
    assert rcs[1].prev_member == "ch-form" and rcs[1].new_member == "free-fermion"
    # delta_cost = +2.0 going FF -> CH, -2.0 going CH -> FF
    assert abs(rcs[0].delta_cost - 2.0) < 1e-9
    assert abs(rcs[1].delta_cost - (-2.0)) < 1e-9
    print(f"  [regime_changes_detailed: {len(rcs)} transitions; FF->CH delta=+2.0, CH->FF delta=-2.0]")

    # 3. window(): a 100-stage all-FF window has no regime changes, 100 stages, FF only.
    win = rt.window(0, 100)
    assert win.stages == 100
    assert win.member_histogram() == {"free-fermion": 100}
    assert win.regime_changes_detailed() == []
    print("  [window(0,100): 100 FF stages, 0 regime changes]")

    # 4. summary() emits a structured report with the right shape.
    text = rt.summary()
    for needle in ("Pipeline trace", "by member", "by tier", "regime changes",
                   "free-fermion", "ch-form", "T0", "T2"):
        assert needle in text, f"summary() missing '{needle}'"
    # And the totals match: log_budget = 500*3 + 500*5 = 4000; log_ops = log2(500*8 + 500*32) = log2(20000)
    assert f"{4000.0:.2f}" in text
    expected_log_ops = math.log2(500 * 2 ** 3 + 500 * 2 ** 5)
    assert f"{expected_log_ops:.2f}" in text
    print(f"  [summary() shape OK; total log-budget=4000.00, total log-ops={expected_log_ops:.2f}]")


if __name__ == "__main__":
    self_test()
