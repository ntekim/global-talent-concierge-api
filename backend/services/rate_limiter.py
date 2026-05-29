import asyncio
import time
from collections import defaultdict


class RateLimiter:
    def __init__(self, max_per_minute: int):
        self._max = max_per_minute
        self._store: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def check(self, client_ip: str) -> bool:
        now = time.time()
        async with self._lock:
            window = self._store[client_ip]
            window[:] = [t for t in window if now - t < 60]
            if len(window) >= self._max:
                return False
            window.append(now)
            return True

    async def sweep(self) -> int:
        now = time.time()
        async with self._lock:
            before = len(self._store)
            cleaned = {
                ip: ts for ip, ts in self._store.items()
                if any(now - t < 60 for t in ts)
            }
            self._store.clear()
            self._store.update(cleaned)
            return before - len(self._store)


rate_limiter = RateLimiter(max_per_minute=60)
