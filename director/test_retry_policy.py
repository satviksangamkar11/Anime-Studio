"""Offline tests for director/retry_policy.py: fake calls, fake clock, fake sleep. No network, no model call."""
import io
import random
import socket
import urllib.error

import pytest

import retry_policy as rp

FREE = {"id": "a/free:free", "pricing": {"prompt": "0", "completion": "0"}}
PAID = {"id": "a/paid", "pricing": {"prompt": "0.000002", "completion": "0"}}
UNPRICED = {"id": "a/blank", "pricing": {}}
CATALOG = [FREE, PAID, UNPRICED, {"id": "b/free2:free", "pricing": {"prompt": 0, "completion": 0}}]


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def http(code, body=b""):
    return urllib.error.HTTPError("https://x", code, "err", {}, io.BytesIO(body))


def scripted(*items):
    """Each call pops the next item: an exception instance is raised, anything else is returned."""
    seq = list(items)
    calls = []

    def fn():
        calls.append(1)
        item = seq.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item
    fn.calls = calls
    return fn


def no_wait(delays):
    return lambda d: delays.append(d)


def test_classify_http_and_exceptions():
    assert rp.classify_exception(http(429)) == rp.RATE_LIMITED
    assert rp.classify_exception(http(503)) == rp.SERVER
    assert rp.classify_exception(http(408)) == rp.TIMEOUT
    assert rp.classify_exception(http(400, b'{"error":"PENDING_BUDGET"}')) == rp.PENDING_BUDGET
    assert rp.classify_exception(http(401)) == rp.FATAL
    assert rp.classify_exception(urllib.error.HTTPError("u", 429, "x", {}, None)) == rp.RATE_LIMITED   # no body stream
    assert rp.classify_exception(socket.timeout()) == rp.TIMEOUT
    assert rp.classify_exception(urllib.error.URLError(socket.timeout())) == rp.TIMEOUT
    assert rp.classify_exception(urllib.error.URLError("dns down")) == rp.NETWORK
    assert rp.classify_exception(ConnectionResetError()) == rp.NETWORK
    assert rp.classify_exception(RuntimeError("OpenRouter refused: PENDING_BUDGET")) == rp.PENDING_BUDGET
    assert rp.classify_exception(ValueError("bad json")) == rp.FATAL
    assert rp.classify_exception(rp.ModelError(rp.SERVER, "x")) == rp.SERVER


def test_answer_kind():
    assert rp.answer_kind("hello") is None
    assert rp.answer_kind("   ", "length") == rp.EMPTY_CUT_OFF
    assert rp.answer_kind(None, "stop") == rp.EMPTY


def test_backoff_grows_caps_jitters_and_honours_retry_after():
    pol = rp.Policy(base_delay=15, max_delay=180)
    low = random.Random(); low.uniform = lambda a, b: a     # jitter at its minimum: half of raw
    high = random.Random(); high.uniform = lambda a, b: b   # jitter at its maximum: all of raw
    assert rp.backoff_delay(1, pol, low) == 7.5 and rp.backoff_delay(1, pol, high) == 15
    assert rp.backoff_delay(3, pol, high) == 60
    assert rp.backoff_delay(9, pol, high) == 180                           # capped
    assert rp.backoff_delay(1, pol, high, retry_after=100) == 100          # server asked for more
    assert rp.backoff_delay(1, pol, high, retry_after=9999) == 180         # but never above the cap


def test_retries_rate_limit_then_answers_with_sleeps_recorded():
    fn, delays = scripted(http(429), http(429), "ok"), []
    out = rp.call_with_retry(fn, sleep=no_wait(delays), rng=random.Random(1))
    assert out == "ok" and len(fn.calls) == 3 and len(delays) == 2
    assert delays[1] > delays[0] or delays[1] >= 7.5                    # growing wait


def test_fatal_gives_up_at_once_without_sleeping():
    fn, delays = scripted(http(401), "never"), []
    with pytest.raises(rp.ModelGaveUp) as info:
        rp.call_with_retry(fn, model="m", sleep=no_wait(delays))
    assert info.value.kind == rp.FATAL and delays == [] and len(fn.calls) == 1
    assert isinstance(info.value.__cause__, urllib.error.HTTPError)


def test_switch_kinds_do_not_retry_in_place():
    fn, delays = scripted(http(400, b"PENDING_BUDGET"), "never"), []
    with pytest.raises(rp.ModelGaveUp) as info:
        rp.call_with_retry(fn, sleep=no_wait(delays))
    assert info.value.kind == rp.PENDING_BUDGET and delays == []


def test_empty_cut_off_answer_is_a_switch_kind_via_check():
    fn, delays = scripted(("", "length")), []
    with pytest.raises(rp.ModelGaveUp) as info:
        rp.call_with_retry(fn, sleep=no_wait(delays), check=lambda r: rp.answer_kind(*r))
    assert info.value.kind == rp.EMPTY_CUT_OFF and delays == []


def test_gives_up_after_max_attempts_and_after_wait_budget():
    delays = []
    fn = scripted(*[http(503)] * 5)
    with pytest.raises(rp.ModelGaveUp) as info:
        rp.call_with_retry(fn, policy=rp.Policy(max_attempts=5), sleep=no_wait(delays))
    assert info.value.attempts == 5 and len(delays) == 4

    delays = []
    fn = scripted(*[http(429)] * 10)
    pol = rp.Policy(max_attempts=10, base_delay=100, max_delay=100, total_wait_cap=250)
    with pytest.raises(rp.ModelGaveUp) as info:
        rp.call_with_retry(fn, policy=pol, sleep=no_wait(delays), rng=random.Random(0))
    assert "wait budget" in info.value.kind and sum(delays) <= 250


def test_breaker_opens_after_threshold_and_half_open_trial_recovers():
    clock = Clock()
    br = rp.CircuitBreaker(threshold=3, cooldown=300, clock=clock)
    for _ in range(3):
        assert br.allow()
        br.record_failure()
    assert br.state == "open" and not br.allow()
    clock.now += 299
    assert not br.allow()
    clock.now += 1
    assert br.state == "half_open" and br.allow()
    assert not br.allow()                                  # only one trial at a time
    br.record_success()
    assert br.state == "closed" and br.allow()


def test_failed_trial_reopens_for_another_cooldown():
    clock = Clock()
    br = rp.CircuitBreaker(threshold=1, cooldown=60, clock=clock)
    br.allow(); br.record_failure()
    clock.now += 60
    assert br.allow()
    br.record_failure()
    assert br.state == "open" and not br.allow()
    clock.now += 60
    assert br.allow()


def test_call_with_retry_raises_circuit_open_when_breaker_is_open():
    clock = Clock()
    br = rp.CircuitBreaker(threshold=1, cooldown=600, clock=clock)
    br.allow(); br.record_failure()
    fn = scripted("never")
    with pytest.raises(rp.CircuitOpen):
        rp.call_with_retry(fn, breaker=br, sleep=lambda d: None, clock=clock)
    assert fn.calls == []


def test_require_free_refuses_paid_unpriced_and_unknown():
    assert rp.is_free_model("a/free:free", CATALOG)
    assert rp.is_free_model("b/free2:free", CATALOG)               # numeric zero prices count
    assert not rp.is_free_model("a/paid", CATALOG)
    assert not rp.is_free_model("a/blank", CATALOG)                # no price fields: not proven free
    assert not rp.is_free_model("nobody/none", CATALOG)
    with pytest.raises(rp.PaidModelRefused) as info:
        rp.require_free(["a/free:free", "a/paid"], CATALOG)
    assert "a/paid" in str(info.value)


def test_call_chain_moves_on_and_returns_first_good_model():
    seen = []

    def make_call(model):
        seen.append(model)
        if model == "first":
            raise rp.ModelError(rp.PENDING_BUDGET, "budget")
        return f"answer from {model}"

    catalog = [{"id": m, "pricing": {"prompt": "0"}} for m in ("first", "second")]
    model, out = rp.call_chain(["first", "second"], make_call, catalog=catalog, sleep=lambda d: None)
    assert (model, out) == ("second", "answer from second") and seen == ["first", "second"]


def test_call_chain_exhausted_and_refuses_paid_before_any_call():
    catalog = [{"id": "x", "pricing": {"prompt": "0"}}, {"id": "y", "pricing": {"prompt": "0.5"}}]
    calls = []
    with pytest.raises(rp.PaidModelRefused):
        rp.call_chain(["x", "y"], lambda m: calls.append(m), catalog=catalog)
    assert calls == []

    catalog = [{"id": "x", "pricing": {"prompt": "0"}}]

    def always_bad(model):
        raise http(401)

    with pytest.raises(rp.ChainExhausted) as info:
        rp.call_chain(["x"], always_bad, catalog=catalog, sleep=lambda d: None)
    assert len(info.value.failures) == 1 and "x: fatal" in info.value.failures[0]


def test_call_chain_skips_model_whose_breaker_is_open():
    clock = Clock()
    breakers = {"x": rp.CircuitBreaker(threshold=1, cooldown=900, clock=clock)}
    breakers["x"].allow(); breakers["x"].record_failure()
    catalog = [{"id": "x", "pricing": {"prompt": "0"}}, {"id": "y", "pricing": {"prompt": "0"}}]
    called = []
    model, out = rp.call_chain(["x", "y"], lambda m: called.append(m) or "ok", catalog=catalog, breakers=breakers,
                               clock=clock, sleep=lambda d: None)
    assert called == ["y"] and model == "y" and out == "ok"


def test_free_chain_ids_are_the_owner_order():
    assert rp.FREE_CHAIN[0].startswith("nvidia/nemotron-3.5-super-vl") and rp.FREE_CHAIN[-1].startswith("dots-studio/")
