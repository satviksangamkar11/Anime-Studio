import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import script_hook


def test_question_mark_alone_is_not_stakes():
    assert script_hook._has_stakes("Who is there?", "en") is False


def test_stakes_word_still_counts():
    word = next(entry for entry in script_hook.STAKES_WORDS["en"] if " " not in entry)
    assert script_hook._has_stakes("He said " + word + " now", "en") is True


def test_h3_still_passes_for_a_question_opener():
    shots = [
        {
            "id": "s1",
            "seconds": 6.0,
            "action": "A king stands on a cliff.",
            "events": [{"t": 0.5}],
            "lines": [{"start_s": 0.3, "end_s": 2.0, "text": "Who is there?"}],
        }
    ]
    result = script_hook.inspect_hook(shots, "en")
    # H3 is reported under the "reasons" key (not hard_fails).
    assert "H3" not in "".join(result["reasons"])
