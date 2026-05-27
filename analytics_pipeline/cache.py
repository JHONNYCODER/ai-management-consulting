# ─────────────────────────────────────────────
# PART 5: PERFORMANCE OPTIMIZATION (CACHING)
# ─────────────────────────────────────────────

from typing import Any, Dict, Callable

class PipelineCache:
    def __init__(self):
        self._cache: Dict[str, Any] = {}
    
    def get_or_compute(self, key: str, compute_fn: Callable) -> Any:
        if key not in self._cache:
            self._cache[key] = compute_fn()
        return self._cache[key]
    
    def clear(self):
        self._cache.clear()