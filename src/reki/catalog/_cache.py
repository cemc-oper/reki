"""Bounded in-process caches for immutable resource values."""

from collections import OrderedDict
from threading import Lock


class _ResourceCache:
    def __init__(self, maxsize):
        self._maxsize = maxsize
        self._entries = OrderedDict()
        self._lock = Lock()

    def get_or_create(self, key, create):
        with self._lock:
            if key in self._entries:
                self._entries.move_to_end(key)
                return self._entries[key]

        value = create()
        with self._lock:
            value = self._entries.setdefault(key, value)
            self._entries.move_to_end(key)
            if len(self._entries) > self._maxsize:
                self._entries.popitem(last=False)
        return value
