"""Cross-process key pool for the 14 NVIDIA keys: every process asks this file for the next free key, so any number of
parallel jobs share one rolling window per key (default 9 calls per 60 s, below the 10/min rule) and one cooldown list.

  idx = KeyPool(state_path).acquire()      # blocks until some key is free; returns the key index 0..13
  pool.cooldown(idx, 60)                   # after an HTTP 429 on that key
  pool.disable(idx)                        # after 401/403
"""
import json
import os
import random
import time

LIMIT = 9
WINDOW = 60.0


class KeyPool:
    def __init__(self, state_path, nkeys=14, limit=LIMIT, window=WINDOW, clock=time.time, sleep=time.sleep):
        self.path = str(state_path)
        self.lock_path = self.path + ".lock"
        self.nkeys = nkeys
        self.limit = limit
        self.window = window
        self.clock = clock
        self.sleep = sleep
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)

    def _lock(self):
        for _ in range(2000):
            try:
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                return
            except FileExistsError:
                try:
                    if time.time() - os.path.getmtime(self.lock_path) > 10:
                        os.remove(self.lock_path)          # stale lock of a dead process
                except OSError:
                    pass
                time.sleep(0.02)
        raise RuntimeError("key pool lock busy")

    def _unlock(self):
        try:
            os.remove(self.lock_path)
        except OSError:
            pass

    def _load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = {}
        data.setdefault("calls", {})
        data.setdefault("cool", {})
        data.setdefault("off", [])
        return data

    def _save(self, data):
        tmp = self.path + ".tmp%d" % os.getpid()
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, self.path)

    def acquire(self, allowed=None):
        """Index of a key that has a free slot now (records the call). allowed = optional list of indexes to choose from."""
        pool = list(allowed) if allowed else list(range(self.nkeys))
        while True:
            self._lock()
            try:
                data = self._load()
                now = self.clock()
                best = []
                for i in pool:
                    if i in data["off"] or data["cool"].get(str(i), 0) > now:
                        continue
                    recent = [t for t in data["calls"].get(str(i), []) if now - t < self.window]
                    data["calls"][str(i)] = recent
                    if len(recent) < self.limit:
                        best.append((len(recent), random.random(), i))
                if best:
                    best.sort()
                    i = best[0][2]
                    data["calls"][str(i)].append(now)
                    self._save(data)
                    return i
                self._save(data)
            finally:
                self._unlock()
            self.sleep(1.0)

    def cooldown(self, idx, seconds=60.0):
        self._lock()
        try:
            data = self._load()
            data["cool"][str(idx)] = self.clock() + seconds
            self._save(data)
        finally:
            self._unlock()

    def disable(self, idx):
        self._lock()
        try:
            data = self._load()
            if idx not in data["off"]:
                data["off"].append(idx)
            self._save(data)
        finally:
            self._unlock()
