import asyncio
import threading
from typing import Dict

class FileLocker:
    """
    Manages in-memory locks for atomic and concurrency-safe access to files across threads and async tasks.
    """
    def __init__(self):
        self._async_locks: Dict[str, asyncio.Lock] = {}
        self._thread_locks: Dict[str, threading.Lock] = {}
        self._meta_lock = threading.Lock()

    def get_thread_lock(self, file_key: str) -> threading.Lock:
        with self._meta_lock:
            if file_key not in self._thread_locks:
                self._thread_locks[file_key] = threading.Lock()
            return self._thread_locks[file_key]

    def get_async_lock(self, file_key: str) -> asyncio.Lock:
        with self._meta_lock:
            if file_key not in self._async_locks:
                self._async_locks[file_key] = asyncio.Lock()
            return self._async_locks[file_key]

locker = FileLocker()
