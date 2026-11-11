import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import script_hook


def test_missing_key_error_names_the_shot():
    shots = [{"id": "s7", "seconds": 1.0, "action": "x", "events": [], "lines": []}]
    del shots[0]["seconds"]
    with pytest.raises(ValueError, match="s7"):
        script_hook._validate_shots(shots)


def test_missing_key_error_names_index_when_no_id():
    shots = [{"seconds": 1.0, "action": "x", "events": [], "lines": []}]
    with pytest.raises(ValueError, match="#0"):
        script_hook._validate_shots(shots)
