import threading
import time
from typing import Any, Hashable, Optional


class TTLCache:
    """Caché en memoria, segura entre hilos, con vencimiento por entrada."""

    def __init__(self, ttl_seconds: float, maxsize: int = 256):
        self.ttl = ttl_seconds
        self.maxsize = maxsize
        self._data: dict = {}
        self._lock = threading.Lock()

    def get(self, key: Hashable) -> Optional[Any]:
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            stored_at, value = item
            if time.monotonic() - stored_at >= self.ttl:
                del self._data[key]
                return None
            return value

    def set(self, key: Hashable, value: Any) -> None:
        with self._lock:
            if key not in self._data and len(self._data) >= self.maxsize:
                oldest = min(self._data, key=lambda k: self._data[k][0])
                del self._data[oldest]
            self._data[key] = (time.monotonic(), value)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
