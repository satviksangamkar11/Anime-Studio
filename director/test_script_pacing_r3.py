import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import script_pacing


def _line(start_s, end_s, text='hello'):
    return {'speaker': 'narrator', 'text': text, 'start_s': start_s, 'end_s': end_s}


def _shot(shot_id, seconds, events, lines, action='Arjun walks to the temple'):
    return {'id': shot_id, 'seconds': seconds, 'action': action, 'events': events, 'lines': lines}


def _make_shots():
    shots = []
    for i in range(10):
        events = [{'t': 0.5}, {'t': 3.0}]
        lines = [_line(0.4, 2.0)]
        shots.append(_shot('s%d' % i, 7.0, events, lines))
    return shots


def test_event_after_shot_end_still_counts_as_payoff():
    shots = _make_shots()
    shots[9]['events'].append({'t': 8.0})
    result = script_pacing.inspect_pacing(shots, 'en')
    for problem in result['problems']:
        assert 'payoff' not in problem


def test_override_negative_raises():
    shots = _make_shots()
    with pytest.raises(ValueError) as excinfo:
        script_pacing.inspect_pacing(shots, 'en', seconds_override={'s9': -5.0})
    assert 'seconds_override for s9 must be a positive finite number' in str(excinfo.value)


def test_override_nan_raises():
    shots = _make_shots()
    with pytest.raises(ValueError) as excinfo:
        script_pacing.inspect_pacing(shots, 'en', seconds_override={'s9': float('nan')})
    assert 'seconds_override for s9 must be a positive finite number' in str(excinfo.value)


def test_override_bool_raises():
    shots = _make_shots()
    with pytest.raises(ValueError) as excinfo:
        script_pacing.inspect_pacing(shots, 'en', seconds_override={'s9': True})
    assert 'seconds_override for s9 must be a positive finite number' in str(excinfo.value)


def test_override_positive_ok():
    shots = _make_shots()
    result = script_pacing.inspect_pacing(shots, 'en', seconds_override={'s9': 7.0})
    assert result['pass'] is True
