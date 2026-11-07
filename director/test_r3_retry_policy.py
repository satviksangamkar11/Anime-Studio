"""Round-3 regression (triage R3-DIR): max_attempts < 1 is refused up front, not an 'unreachable' AssertionError."""
import pytest

import retry_policy as rp


def test_zero_attempts_is_refused_before_any_call():
    calls = []
    with pytest.raises(ValueError, match="max_attempts"):
        rp.call_with_retry(lambda: calls.append(1) or 1, policy=rp.Policy(max_attempts=0))
    assert calls == []
