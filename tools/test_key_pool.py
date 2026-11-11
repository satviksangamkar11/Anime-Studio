import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import key_pool


class Clock:
    def __init__(self):
        self.t = 1000.0

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s


def make(tmp_path, nkeys=2, limit=3):
    c = Clock()
    return key_pool.KeyPool(tmp_path / "s.json", nkeys=nkeys, limit=limit, clock=c.now, sleep=c.sleep), c


def test_spreads_calls_over_keys(tmp_path):
    pool, c = make(tmp_path)
    got = [pool.acquire() for _ in range(6)]
    assert sorted(got) == [0, 0, 0, 1, 1, 1]          # limit 3 per key, 2 keys


def test_waits_when_all_keys_are_full(tmp_path):
    pool, c = make(tmp_path)
    for _ in range(6):
        pool.acquire()
    t0 = c.t
    pool.acquire()
    assert c.t - t0 >= 60 - 1e-6 or c.t - t0 > 55        # slept until the window freed a slot


def test_cooldown_and_disable_skip_a_key(tmp_path):
    pool, c = make(tmp_path)
    pool.cooldown(0, 60)
    assert [pool.acquire() for _ in range(3)] == [1, 1, 1]
    c.t += 61
    pool2, _ = make(tmp_path)
    pool.disable(1)
    assert pool.acquire() == 0


def test_two_pool_objects_share_the_file(tmp_path):
    a, c = make(tmp_path, nkeys=1, limit=2)
    b = key_pool.KeyPool(tmp_path / "s.json", nkeys=1, limit=2, clock=c.now, sleep=c.sleep)
    a.acquire()
    b.acquire()
    t0 = c.t
    a.acquire()
    assert c.t - t0 > 55
