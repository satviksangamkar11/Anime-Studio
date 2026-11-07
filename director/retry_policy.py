"""One retry, backoff, circuit-breaker and fallback policy for FREE model calls (OpenRouter :free, NVIDIA build). Stdlib only.
Nothing here touches the network: a caller passes its own call as a function. Clock and sleep are injected for tests.

Kinds (what went wrong): rate_limited (HTTP 429), server (5xx), timeout, network, pending_budget (the NVIDIA route answers
PENDING_BUDGET), empty (answer with no text), empty_cut_off (no text and finish_reason=length: reasoning used the whole budget),
fatal (anything else, e.g. 400/401/403/404: retrying does not help).
  IN_PLACE kinds: wait (exponential backoff with jitter, server Retry-After honoured, capped) and call the same model again.
  SWITCH kinds: the same model will not answer now: give up on it at once so the caller moves to the next model in the chain.
  fatal: give up at once.

Usage (see tools/README.md for the integration points):
  answer = call_with_retry(lambda: openrouter_call(model), model=model, check=lambda r: answer_kind(*r))
  model, answer = call_chain(FREE_CHAIN, lambda m: openrouter_call(m), catalog=catalog)
"""
from __future__ import annotations

import math
import random
import socket
import time
import urllib.error
from dataclasses import dataclass

RATE_LIMITED, SERVER, TIMEOUT, NETWORK = "rate_limited", "server", "timeout", "network"
PENDING_BUDGET, EMPTY, EMPTY_CUT_OFF, FATAL = "pending_budget", "empty", "empty_cut_off", "fatal"
IN_PLACE = frozenset({RATE_LIMITED, SERVER, TIMEOUT, NETWORK})
SWITCH = frozenset({PENDING_BUDGET, EMPTY, EMPTY_CUT_OFF})
FREE_CHAIN = (                                             # owner order: super-vl -> ultra -> dots (ids as write_pack.py / dots_review.py use them)
    "nvidia/nemotron-3.5-super-vl:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "dots-studio/dots-3-note-preview:free",
)


class ModelError(Exception):
    """A call failed with a known kind. retry_after: seconds the server asked us to wait (optional)."""

    def __init__(self, kind: str, message: str = "", retry_after: float | None = None):
        super().__init__(message or kind)
        self.kind, self.retry_after = kind, retry_after


class ModelGaveUp(Exception):
    """This model will not be called again in this call: `kind` is the last kind, `attempts` how many calls were made."""

    def __init__(self, model: str, kind: str, attempts: int, history: list):
        super().__init__(f"{model}: {kind} after {attempts} attempt(s)")
        self.model, self.kind, self.attempts, self.history = model, kind, attempts, history


class CircuitOpen(ModelGaveUp):
    pass


class PaidModelRefused(ValueError):
    pass


class ChainExhausted(RuntimeError):
    def __init__(self, failures: list[str]):
        super().__init__("every free model failed: " + "; ".join(failures))
        self.failures = failures


def classify_http(status: int, body: str = "") -> str:
    if "PENDING_BUDGET" in (body or ""):
        return PENDING_BUDGET
    if status == 429:
        return RATE_LIMITED
    if status == 408:
        return TIMEOUT
    if status >= 500:
        return SERVER
    return FATAL


def _http_body(exc: urllib.error.HTTPError) -> str:
    try:
        return (exc.read(400) or b"").decode("utf-8", "replace")
    except Exception:          # no body stream (e.g. a constructed error): not an error for us
        return ""


def classify_exception(exc: BaseException) -> str:
    if isinstance(exc, ModelError):
        return exc.kind
    if isinstance(exc, urllib.error.HTTPError):
        return classify_http(exc.code, _http_body(exc))
    if "PENDING_BUDGET" in str(exc):
        return PENDING_BUDGET
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return TIMEOUT
    if isinstance(exc, urllib.error.URLError):
        return TIMEOUT if isinstance(exc.reason, (TimeoutError, socket.timeout)) else NETWORK
    if isinstance(exc, (ConnectionError, OSError)):
        return NETWORK
    return FATAL


def answer_kind(text: str | None, finish_reason: str | None = None) -> str | None:
    """None when the answer has text; otherwise EMPTY, or EMPTY_CUT_OFF when the model stopped on the token limit."""
    if text and text.strip():
        return None
    return EMPTY_CUT_OFF if finish_reason == "length" else EMPTY


@dataclass(frozen=True)
class Policy:
    max_attempts: int = 5           # calls per model for IN_PLACE kinds (owner's reviewer window: 5 tries)
    base_delay: float = 15.0        # first wait in seconds; doubles each time
    max_delay: float = 180.0        # cap of one wait
    total_wait_cap: float = 600.0   # all waits for one model together


DEFAULT_POLICY = Policy()


def backoff_delay(attempt: int, policy: Policy = DEFAULT_POLICY, rng: random.Random | None = None,
                  retry_after: float | None = None) -> float:
    """Wait after failed `attempt` (1-based): base * 2^(attempt-1), at least the server's Retry-After, equal jitter (half fixed,
    half random), never above policy.max_delay."""
    rng = rng or random.Random()
    raw = min(policy.max_delay, policy.base_delay * 2 ** (attempt - 1))
    if retry_after is not None and math.isfinite(retry_after):
        raw = max(raw, float(retry_after))
    raw = min(policy.max_delay, raw)
    return min(policy.max_delay, raw / 2 + rng.uniform(0, raw / 2))


class CircuitBreaker:
    """Opens after `threshold` failures in a row. Once `cooldown` seconds have passed, lets ONE trial call through
    (half-open): a success closes it, a failure opens it again for another cooldown."""

    def __init__(self, threshold: int = 3, cooldown: float = 300.0, clock=time.monotonic):
        self.threshold, self.cooldown, self.clock = threshold, cooldown, clock
        self.failures, self.opened_at, self.trial = 0, None, False

    @property
    def state(self) -> str:
        if self.opened_at is None:
            return "closed"
        return "half_open" if self.clock() - self.opened_at >= self.cooldown else "open"

    def allow(self) -> bool:
        if self.opened_at is None:
            return True
        if self.clock() - self.opened_at < self.cooldown or self.trial:
            return False
        self.trial = True
        return True

    def record_success(self) -> None:
        self.failures, self.opened_at, self.trial = 0, None, False

    def record_failure(self) -> None:
        self.failures += 1
        if self.trial or self.failures >= self.threshold:
            self.opened_at = self.clock()
        self.trial = False


def call_with_retry(fn, *, model: str = "", policy: Policy = DEFAULT_POLICY, breaker: CircuitBreaker | None = None,
                    sleep=time.sleep, clock=time.monotonic, rng: random.Random | None = None, check=None, on_retry=None):
    """Call fn() until it answers. `check(result)` returns a kind (a bad answer) or None (good). Returns the result.
    Raises CircuitOpen (breaker open), or ModelGaveUp (fatal, switch kind, attempts or wait budget spent): the caller then
    moves to the next model. The original error is chained as __cause__."""
    if policy.max_attempts < 1:
        raise ValueError(f"policy.max_attempts must be at least 1, got {policy.max_attempts}")
    breaker = breaker or CircuitBreaker(clock=clock)
    rng = rng or random.Random()
    if not breaker.allow():                       # the breaker decides whether a call may START; attempts inside it follow the policy
        raise CircuitOpen(model, "circuit_open", 0, [])
    history, waited = [], 0.0
    for attempt in range(1, policy.max_attempts + 1):
        retry_after = None
        try:
            result = fn()
            kind = check(result) if check else None
            if kind is None:
                breaker.record_success()
                return result
            cause = None
        except Exception as exc:  # noqa: BLE001 - every failure is classified below
            kind, cause = classify_exception(exc), exc
            retry_after = getattr(exc, "retry_after", None)
        breaker.record_failure()
        history.append(kind)
        if kind not in IN_PLACE or attempt == policy.max_attempts:
            raise ModelGaveUp(model, kind, attempt, history) from cause
        delay = backoff_delay(attempt, policy, rng, retry_after)
        if waited + delay > policy.total_wait_cap:
            raise ModelGaveUp(model, f"{kind} (wait budget {policy.total_wait_cap:g}s spent)", attempt, history) from cause
        if on_retry:
            on_retry(attempt, kind, delay)
        sleep(delay)
        waited += delay
    raise AssertionError("unreachable")  # the loop always returns or raises


def is_free_model(model: str, catalog: list) -> bool:
    """True only when the model is in the catalog and EVERY price field is 0. Unknown or unpriced = not free."""
    entry = next((m for m in catalog if m.get("id") == model), None)
    if not entry or not isinstance(entry.get("pricing"), dict) or not entry["pricing"]:
        return False

    def zero(v) -> bool:
        try:
            return isinstance(v, (str, int, float)) and not isinstance(v, bool) and float(v) == 0
        except ValueError:
            return False
    return all(zero(v) for v in entry["pricing"].values())


def require_free(models, catalog: list) -> tuple:
    refused = [m for m in models if not is_free_model(m, catalog)]
    if refused:
        raise PaidModelRefused("refused (not in the free catalog or price not 0): " + ", ".join(refused))
    return tuple(models)


def call_chain(chain, make_call, *, catalog: list, policy: Policy = DEFAULT_POLICY, breakers: dict | None = None,
               sleep=time.sleep, clock=time.monotonic, rng: random.Random | None = None, check=None, on_switch=None):
    """Try each free model in order with call_with_retry. Returns (model, result). Raises ChainExhausted when all fail.
    `breakers` (model -> CircuitBreaker) can be kept by the caller across calls so an open model is skipped at once."""
    require_free(chain, catalog)
    breakers = {} if breakers is None else breakers
    failures = []
    for model in chain:
        breaker = breakers.setdefault(model, CircuitBreaker(clock=clock))
        try:
            return model, call_with_retry(lambda m=model: make_call(m), model=model, policy=policy, breaker=breaker,
                                          sleep=sleep, clock=clock, rng=rng, check=check)
        except ModelGaveUp as exc:
            failures.append(str(exc))
            if on_switch:
                on_switch(model, exc)
    raise ChainExhausted(failures)
