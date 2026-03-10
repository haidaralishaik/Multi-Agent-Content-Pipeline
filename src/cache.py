"""
Pipeline Cache - Content-addressed caching for pipeline stages

Caches each agent's output independently so repeated runs avoid
redundant API calls. Research is keyed by (topic + notes), writing
by (topic + notes + format + tone), etc.
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Dict, Optional
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """A single cached stage output"""
    key: str
    stage: str
    data: str
    created_at: float
    ttl: float
    cost_saved: float
    hit_count: int = 0

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl


class PipelineCache:
    """
    Content-addressed cache for pipeline stages.

    Key design: different stages use different inputs for cache keys,
    so research can be reused across format/tone changes.

    - research key  = hash(topic + notes)
    - write key     = hash(topic + notes + format + tone)
    - edit key      = hash(topic + notes + format + tone)
    - fact_check key = hash(topic + notes + format + tone)
    """

    DEFAULT_TTL = 3600 * 24  # 24 hours

    def __init__(self, cache_dir: str = ".cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.stats = {"hits": 0, "misses": 0, "cost_saved": 0.0}

    def _make_key(self, topic: str, stage: str,
                  content_format: str = "", tone: str = "",
                  notes: str = "") -> str:
        """Create cache key from inputs relevant to that stage."""
        # Research depends only on topic + notes (reusable across formats)
        if stage == "research":
            key_input = f"{topic}|{notes}"
        else:
            # All other stages depend on format and tone too
            key_input = f"{topic}|{notes}|{content_format}|{tone}|{stage}"

        return hashlib.sha256(key_input.encode()).hexdigest()[:16]

    def _entry_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def get(self, topic: str, stage: str, **kwargs) -> Optional[str]:
        """Retrieve cached stage output. Returns None on miss or expiry."""
        key = self._make_key(topic, stage, **kwargs)
        path = self._entry_path(key)

        if not path.exists():
            self.stats["misses"] += 1
            return None

        try:
            with open(path, 'r', encoding='utf-8') as f:
                raw = json.load(f)
            entry = CacheEntry(**raw)
        except (json.JSONDecodeError, TypeError, KeyError):
            self.stats["misses"] += 1
            path.unlink(missing_ok=True)
            return None

        if entry.is_expired:
            self.stats["misses"] += 1
            path.unlink(missing_ok=True)
            return None

        # Cache hit
        entry.hit_count += 1
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(asdict(entry), f, ensure_ascii=False)

        self.stats["hits"] += 1
        self.stats["cost_saved"] += entry.cost_saved
        logger.info(f"Cache HIT for {stage} [key={key[:8]}]")
        return entry.data

    def put(self, topic: str, stage: str, data: str,
            cost: float, **kwargs) -> None:
        """Store stage output in cache."""
        key = self._make_key(topic, stage, **kwargs)
        entry = CacheEntry(
            key=key,
            stage=stage,
            data=data,
            created_at=time.time(),
            ttl=self.DEFAULT_TTL,
            cost_saved=cost,
        )
        path = self._entry_path(key)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(asdict(entry), f, ensure_ascii=False)
        logger.info(f"Cache PUT for {stage} [key={key[:8]}], cost_saved=${cost:.6f}")

    def get_stats(self) -> Dict:
        """Return cache hit/miss stats and total cost saved."""
        total = self.stats["hits"] + self.stats["misses"]
        return {
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "hit_rate": round(self.stats["hits"] / total, 2) if total > 0 else 0,
            "cost_saved": round(self.stats["cost_saved"], 6),
        }

    def clear(self) -> int:
        """Clear all cached entries. Returns number of entries removed."""
        count = 0
        for f in self.cache_dir.glob("*.json"):
            f.unlink()
            count += 1
        self.stats = {"hits": 0, "misses": 0, "cost_saved": 0.0}
        logger.info(f"Cache cleared: {count} entries removed")
        return count

    def clear_expired(self) -> int:
        """Remove expired entries. Returns number of entries removed."""
        count = 0
        for f in self.cache_dir.glob("*.json"):
            try:
                with open(f, 'r', encoding='utf-8') as fh:
                    raw = json.load(fh)
                entry = CacheEntry(**raw)
                if entry.is_expired:
                    f.unlink()
                    count += 1
            except (json.JSONDecodeError, TypeError, KeyError):
                f.unlink()
                count += 1
        logger.info(f"Expired cache entries cleared: {count}")
        return count
