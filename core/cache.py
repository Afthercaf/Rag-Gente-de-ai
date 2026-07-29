import threading
import time
from collections import OrderedDict
from sys import getsizeof
from typing import Any, Optional

from utils.constants import CACHE_TTL


class MemoryCache:
    def __init__(self, ttl_seconds: int = CACHE_TTL, max_entries: int = 500,
                 max_entry_bytes: int = 256_000):
        self.cache: OrderedDict = OrderedDict()
        self.ttl = ttl_seconds
        self.max_entries = max(1, max_entries)
        self.max_entry_bytes = max(1, max_entry_bytes)
        self.lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self.lock:
            if key in self.cache:
                data, timestamp, entry_ttl = self.cache[key]
                if time.time() - timestamp < entry_ttl:
                    self.cache.move_to_end(key)
                    return data
                del self.cache[key]
        return None

    def set(self, key: str, value: Any, ttl: int = None) -> None:
        if getsizeof(value) > self.max_entry_bytes:
            return
        with self.lock:
            entry_ttl = ttl if ttl is not None else self.ttl
            self.cache[key] = (value, time.time(), entry_ttl)
            self.cache.move_to_end(key)
            while len(self.cache) > self.max_entries:
                self.cache.popitem(last=False)

    def clear(self) -> None:
        with self.lock:
            self.cache.clear()

    def size(self) -> int:
        with self.lock:
            return len(self.cache)


# Instancia global
response_cache = MemoryCache(ttl_seconds=CACHE_TTL)
