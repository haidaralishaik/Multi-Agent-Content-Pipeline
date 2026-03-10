"""Tests for pipeline caching"""

import time
import shutil
from pathlib import Path
from src.cache import PipelineCache


TEST_CACHE_DIR = ".cache_test"


def _clean():
    shutil.rmtree(TEST_CACHE_DIR, ignore_errors=True)


def test_cache_miss():
    """Returns None on cache miss"""
    _clean()
    cache = PipelineCache(cache_dir=TEST_CACHE_DIR)
    result = cache.get("some topic", "research")
    assert result is None
    assert cache.stats["misses"] == 1
    _clean()


def test_cache_put_and_get():
    """Can store and retrieve cached data"""
    _clean()
    cache = PipelineCache(cache_dir=TEST_CACHE_DIR)
    cache.put("AI topic", "research", "Research notes here", cost=0.005)
    result = cache.get("AI topic", "research")
    assert result == "Research notes here"
    assert cache.stats["hits"] == 1
    _clean()


def test_research_cache_reusable_across_formats():
    """Research cache key only depends on topic + notes, not format/tone"""
    _clean()
    cache = PipelineCache(cache_dir=TEST_CACHE_DIR)
    cache.put("AI topic", "research", "Research data", cost=0.005, notes="")
    # Same topic, different format/tone should still hit
    result = cache.get("AI topic", "research", content_format="linkedin_post",
                       tone="casual", notes="")
    assert result == "Research data"
    _clean()


def test_write_cache_varies_by_format():
    """Write cache key depends on format and tone"""
    _clean()
    cache = PipelineCache(cache_dir=TEST_CACHE_DIR)
    cache.put("AI topic", "write", "Blog draft", cost=0.003,
              content_format="blog_post", tone="professional", notes="")
    # Different format should miss
    result = cache.get("AI topic", "write", content_format="linkedin_post",
                       tone="professional", notes="")
    assert result is None
    # Same format should hit
    result = cache.get("AI topic", "write", content_format="blog_post",
                       tone="professional", notes="")
    assert result == "Blog draft"
    _clean()


def test_cache_expiry():
    """Expired entries return None"""
    _clean()
    cache = PipelineCache(cache_dir=TEST_CACHE_DIR)
    cache.DEFAULT_TTL = 0.01  # 10ms TTL
    cache.put("AI topic", "research", "Old data", cost=0.001)
    time.sleep(0.02)
    result = cache.get("AI topic", "research")
    assert result is None
    _clean()


def test_cache_clear():
    """Clear removes all entries"""
    _clean()
    cache = PipelineCache(cache_dir=TEST_CACHE_DIR)
    cache.put("topic1", "research", "data1", cost=0.001)
    cache.put("topic2", "research", "data2", cost=0.002)
    count = cache.clear()
    assert count == 2
    assert cache.get("topic1", "research") is None
    _clean()


def test_cache_clear_expired():
    """clear_expired only removes expired entries"""
    _clean()
    cache = PipelineCache(cache_dir=TEST_CACHE_DIR)
    cache.put("old", "research", "old data", cost=0.001)
    # Manually set very short TTL for the old entry
    import json
    path = cache._entry_path(cache._make_key("old", "research"))
    with open(path, 'r') as f:
        entry = json.load(f)
    entry['ttl'] = 0.001
    entry['created_at'] = time.time() - 1  # 1 second ago
    with open(path, 'w') as f:
        json.dump(entry, f)

    cache.put("new", "research", "new data", cost=0.002)
    count = cache.clear_expired()
    assert count == 1
    assert cache.get("new", "research") == "new data"
    _clean()


def test_cache_stats():
    """Stats track hits, misses, and cost saved"""
    _clean()
    cache = PipelineCache(cache_dir=TEST_CACHE_DIR)
    cache.put("topic", "research", "data", cost=0.005)
    cache.get("topic", "research")  # hit
    cache.get("other", "research")  # miss

    stats = cache.get_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["hit_rate"] == 0.5
    assert stats["cost_saved"] == 0.005
    _clean()
