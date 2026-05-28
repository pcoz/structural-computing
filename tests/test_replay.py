"""Tests for the ReplayCache (including LRU eviction) and cached_runner."""

import pytest

from structural_computing import ReplayCache, cached_runner, default_key
from structural_computing.replay import _MISS


# ---------------------------------------------------------------------------
# Basic accounting (unbounded cache)
# ---------------------------------------------------------------------------

def test_initial_state():
    c = ReplayCache()
    assert c.size == 0
    assert c.hits == 0
    assert c.misses == 0
    assert c.evictions == 0
    assert c.hit_rate() == 0.0
    assert c.maxsize is None


def test_miss_then_put_then_hit():
    c = ReplayCache()
    assert c.get("k1") is _MISS
    assert c.misses == 1
    c.put("k1", 42)
    assert c.get("k1") == 42
    assert c.hits == 1


def test_hit_rate():
    c = ReplayCache()
    c.put("a", 1)
    c.get("a"); c.get("a"); c.get("b")          # 2 hits, 1 miss
    assert c.hits == 2 and c.misses == 1
    assert abs(c.hit_rate() - 2.0 / 3.0) < 1e-9


def test_unbounded_keeps_everything():
    c = ReplayCache()
    for i in range(1000):
        c.put(f"k{i}", i)
    assert c.size == 1000
    assert c.evictions == 0


def test_clear_preserves_stats():
    c = ReplayCache()
    c.put("a", 1)
    c.get("a"); c.get("b")
    c.clear()
    assert c.size == 0
    # Statistics describe workload, not cache state.
    assert c.hits == 1 and c.misses == 1


# ---------------------------------------------------------------------------
# LRU eviction
# ---------------------------------------------------------------------------

def test_maxsize_validation():
    ReplayCache(maxsize=None)                    # OK
    ReplayCache(maxsize=1)                        # OK
    with pytest.raises(ValueError):
        ReplayCache(maxsize=0)
    with pytest.raises(ValueError):
        ReplayCache(maxsize=-5)


def test_lru_caps_at_maxsize():
    c = ReplayCache(maxsize=10)
    for i in range(100):
        c.put(f"k{i}", i)
    assert c.size == 10
    assert c.evictions == 90


def test_lru_evicts_oldest():
    """After putting a, b, c into a maxsize=3 cache, then putting d, a should be evicted."""
    c = ReplayCache(maxsize=3)
    c.put("a", 1)
    c.put("b", 2)
    c.put("c", 3)
    c.put("d", 4)
    assert c.get("a") is _MISS
    assert c.get("b") == 2
    assert c.get("c") == 3
    assert c.get("d") == 4


def test_lru_refreshes_on_access():
    """If 'a' has been accessed recently, it shouldn't be the next evicted."""
    c = ReplayCache(maxsize=3)
    c.put("a", 1)
    c.put("b", 2)
    c.put("c", 3)
    c.get("a")                                    # refresh 'a' to most-recent
    c.put("d", 4)                                 # this should evict 'b', NOT 'a'
    assert c.get("a") == 1
    assert c.get("b") is _MISS
    assert c.get("c") == 3
    assert c.get("d") == 4


def test_lru_refreshes_on_update():
    """Putting the same key again refreshes its LRU position."""
    c = ReplayCache(maxsize=3)
    c.put("a", 1)
    c.put("b", 2)
    c.put("c", 3)
    c.put("a", 99)                                # update -- refreshes 'a'
    c.put("d", 4)                                 # should evict 'b'
    assert c.get("a") == 99
    assert c.get("b") is _MISS


def test_update_does_not_evict():
    """Updating an existing key shouldn't trigger eviction."""
    c = ReplayCache(maxsize=3)
    c.put("a", 1)
    c.put("b", 2)
    c.put("c", 3)
    c.put("a", 99)                                # update, no eviction
    assert c.evictions == 0
    assert c.size == 3


# ---------------------------------------------------------------------------
# cached_runner
# ---------------------------------------------------------------------------

def test_cached_runner_caches():
    call_count = {"n": 0}
    def slow(data, prev, route):
        call_count["n"] += 1
        return data * 2

    cache = ReplayCache()
    fast = cached_runner(slow, cache)
    fast(5, None, None)                          # miss
    fast(5, None, None)                          # hit
    fast(5, None, None)                          # hit
    assert call_count["n"] == 1
    assert cache.hits == 2 and cache.misses == 1


def test_cached_runner_custom_key():
    """A custom key_fn can ignore noise fields in `data`."""
    call_count = {"n": 0}
    def slow(data, prev, route):
        call_count["n"] += 1
        return data["k"]

    def k_only(data, prev):
        return f"{data['k']}::{prev}"

    cache = ReplayCache()
    fast = cached_runner(slow, cache, key_fn=k_only)
    for noise in range(50):
        fast({"k": 7, "noise": noise}, "p", None)
    assert call_count["n"] == 1
    assert cache.size == 1


def test_cached_runner_with_lru():
    """cached_runner respects the cache's LRU eviction."""
    call_count = {"n": 0}
    def slow(data, prev, route):
        call_count["n"] += 1
        return data

    cache = ReplayCache(maxsize=3)
    fast = cached_runner(slow, cache)
    for i in range(10):
        fast(i, None, None)
    # 10 calls, 10 unique inputs, maxsize=3 -> 7 evictions
    assert call_count["n"] == 10           # every call was a miss (each new input)
    assert cache.evictions == 7
    assert cache.size == 3


# ---------------------------------------------------------------------------
# default_key
# ---------------------------------------------------------------------------

def test_default_key_deterministic():
    k1 = default_key([1, 2, 3], "x")
    k2 = default_key([1, 2, 3], "x")
    assert k1 == k2


def test_default_key_differs_on_different_inputs():
    assert default_key("a", None) != default_key("b", None)
    assert default_key("a", "p1") != default_key("a", "p2")
