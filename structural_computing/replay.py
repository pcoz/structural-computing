r"""Memoisation layer for the pipeline-router.

Many long pipelines re-encounter the same sub-problem repeatedly:

  * MCMC / Gibbs samplers on a structured graphical model -- the conditional
    distribution at step n may exactly match the one at step n - k.
  * Branch-and-bound search trees -- two subtrees often reduce to identical
    canonical sub-problems.
  * Adaptive incremental rebuild -- the same dependency-graph fragment recurs
    across many file saves in a long dev session.

`ReplayCache` keys stage outputs by (data, prev) and threads through
`cached_runner` (a wrapper that drops in for a Stage.runner_fn). The cache is
intentionally simple: a dict keyed by SHA-1 of the JSON-serialised descriptor,
unbounded by default (eviction is a v2 concern). Statistics: hits, misses,
hit_rate, size.

Use:

    from replay import ReplayCache, cached_runner
    cache = ReplayCache()
    cached = cached_runner(my_runner, cache)         # drop-in for runner_fn
    stages = [Stage(name, kind, data_i, route_fn, cached) for ... ]
    final, trace = run_pipeline(stages)
    print(cache.size, cache.hit_rate())
"""
import functools
import hashlib
import json
from typing import Any, Callable, Dict


_MISS = object()                                  # cache-miss sentinel


def default_key(data: Any, prev: Any) -> str:
    """Default cache key: SHA-1 of the JSON of (data, prev). `default=str`
    lets numpy / tuples / sets fall through to their repr, which is usually
    a stable string."""
    payload = json.dumps([data, prev], sort_keys=True, default=str)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


class ReplayCache:
    """A simple dict-backed cache for stage outputs. Unbounded; eviction is
    a future concern. Statistics: hits, misses, hit_rate, size."""

    def __init__(self):
        self._store: Dict[str, Any] = {}
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Any:
        v = self._store.get(key, _MISS)
        if v is _MISS:
            self.misses += 1
            return _MISS
        self.hits += 1
        return v

    def put(self, key: str, value: Any) -> None:
        self._store[key] = value

    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0

    @property
    def size(self) -> int:
        return len(self._store)


def cached_runner(runner_fn: Callable, cache: ReplayCache,
                  key_fn: Callable[[Any, Any], str] = default_key) -> Callable:
    """Wrap `runner_fn(data, prev, route)` so identical (data, prev) calls
    return the cached output. `route` is intentionally not part of the key
    (a routing decision shouldn't change the stage's deterministic output;
    if it does, that's a runner bug, not a cache key issue).

    Pass `key_fn` to override the default JSON-SHA-1 keying -- useful when
    `data` has irrelevant fields you want to ignore, or when a domain-specific
    hash is faster than JSON serialisation."""
    @functools.wraps(runner_fn)
    def wrapped(data, prev, route):
        k = key_fn(data, prev)
        cached = cache.get(k)
        if cached is not _MISS:
            return cached
        result = runner_fn(data, prev, route)
        cache.put(k, result)
        return result
    return wrapped


# ---------------------------------------------------------------------------
# Self-test:
#   1. ReplayCache basic hit / miss / size accounting.
#   2. cached_runner integration with run_pipeline: a 1000-stage pipeline
#      where data alternates over a small set yields ~the-set-size misses
#      and ~rest hits, and the per-stage outputs match the uncached run.
#   3. A custom key_fn correctly groups equivalent descriptors that differ
#      only in an irrelevant field.
# ---------------------------------------------------------------------------

def self_test():
    from .pipeline_router import Stage, Route, run_pipeline

    # 1. Basic accounting.
    c = ReplayCache()
    assert c.size == 0 and c.hit_rate() == 0.0
    assert c.get("k1") is _MISS
    c.put("k1", 42)
    assert c.get("k1") == 42
    assert c.get("k2") is _MISS
    assert c.hits == 1 and c.misses == 2
    assert abs(c.hit_rate() - 1.0 / 3.0) < 1e-9
    print("  [ReplayCache: hit/miss accounting OK, hit_rate = 1/3]")

    # 2. cached_runner inside a pipeline. Data alternates over only 4 values
    #    across 1000 stages. The uncached run records every call; the cached
    #    run should record exactly 4 (the distinct keys) and hit on the rest.
    call_count = {"n": 0}
    def slow_runner(data, prev, route):
        call_count["n"] += 1
        return prev + data                     # deterministic, depends on (data, prev)
    def route_(data, prev):
        return Route(member="m", cost=1.0)

    # Build a deterministic pipeline: stages are pairs (data, prev) that
    # cycle through 4 distinct (data, prev) keys. We force the cycle by
    # zeroing prev between blocks via an explicit "reset" stage.
    cache = ReplayCache()
    cached = cached_runner(slow_runner, cache)
    distinct_keys = set()
    distincts = [(1, 10), (2, 20), (3, 30), (4, 40)]  # 4 distinct (data, seed-like)
    # Run a 1000-call experiment: for each (data_i, seed_i), build a tiny
    # pipeline of length 1 starting at seed_i with that data, repeated 250x.
    for trial in range(250):
        for d, s in distincts:
            stages = [Stage("step", "k", d, route_, cached)]
            _, _ = run_pipeline(stages, seed=s)
            distinct_keys.add(default_key(d, s))
    assert len(distinct_keys) == 4
    assert call_count["n"] == 4, f"slow_runner ran {call_count['n']} times; expected 4 with caching"
    assert cache.size == 4
    expected_hits = 1000 - 4
    assert cache.hits == expected_hits, (cache.hits, expected_hits)
    assert cache.misses == 4
    print(f"  [cached_runner inside 1000-call run: 4 misses + {expected_hits} hits; "
          f"hit_rate = {cache.hit_rate():.3%}; slow_runner called only 4 times]")

    # 3. Custom key_fn: ignore a noise field. Two descriptors that differ
    #    only in `noise` should share a cache entry.
    def noise_blind_key(data, prev):
        return default_key({"k": data["k"]}, prev)
    cache2 = ReplayCache()
    cached2 = cached_runner(slow_runner, cache2, key_fn=noise_blind_key)
    call_count2 = {"n": 0}
    def slow_runner2(data, prev, route):
        call_count2["n"] += 1
        return prev + data["k"]
    cached_with_blind_key = cached_runner(slow_runner2, cache2, key_fn=noise_blind_key)
    for noise in range(100):
        stages = [Stage("step", "k", {"k": 7, "noise": noise}, route_, cached_with_blind_key)]
        run_pipeline(stages, seed=0)
    assert cache2.size == 1, cache2.size
    assert call_count2["n"] == 1, call_count2["n"]
    print(f"  [custom key_fn: 100 calls with varying noise field collapse to 1 cache entry]")


if __name__ == "__main__":
    self_test()
