import threading
import time
from typing import Any, Optional

from utils.constants import CACHE_TTL


class MemoryCache:
    def __init__(self, ttl_seconds: int = CACHE_TTL):
        self.cache: dict = {}
        self.ttl = ttl_seconds
        self.lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self.lock:
            if key in self.cache:
                data, timestamp, entry_ttl = self.cache[key]
                if time.time() - timestamp < entry_ttl:
                    return data
                del self.cache[key]
        return None

    def set(self, key: str, value: Any, ttl: int = None) -> None:
        with self.lock:
            entry_ttl = ttl if ttl is not None else self.ttl
            self.cache[key] = (value, time.time(), entry_ttl)

    def clear(self) -> None:
        with self.lock:
            self.cache.clear()

    def size(self) -> int:
        return len(self.cache)


# Instancia global
response_cache = MemoryCache(ttl_seconds=CACHE_TTL)