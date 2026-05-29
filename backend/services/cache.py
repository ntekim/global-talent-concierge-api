import asyncio
import time
from collections import OrderedDict


class LRUCache:
    def __init__(self, maxsize: int, ttl: int):
        self._maxsize = maxsize
        self._ttl = ttl
        self._store: OrderedDict[str, tuple[float, dict]] = OrderedDict()
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> dict | None:
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if time.time() - entry[0] >= self._ttl:
                del self._store[key]
                return None
            self._store.move_to_end(key)
            return entry[1]

    async def set(self, key: str, value: dict):
        async with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = (time.time(), value)
            while len(self._store) > self._maxsize:
                self._store.popitem(last=False)

    async def size(self) -> int:
        async with self._lock:
            return len(self._store)

    async def sweep(self):
        now = time.time()
        async with self._lock:
            stale = [k for k, (t, _) in self._store.items() if now - t >= self._ttl]
            for k in stale:
                del self._store[k]
            return len(stale)


compliance_cache = LRUCache(maxsize=200, ttl=3600)
