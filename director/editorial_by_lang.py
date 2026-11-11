"""DEPRECATED shim (P2 W-12, 2026-11-11). Use the timeline lock: director/write_timeline_lock.py (writer) and
director/timeline_lock_io.py (reader). Shot lengths for new reels come only from the lock.

This module only re-exports the reel-1 code in director/editorial_legacy.py so the historical reel-1 path and its old tests keep
working. Nothing else may import it (director/test_editorial_retired.py scans for that). Importing it warns with DeprecationWarning.
The file itself is kept until the owner gate; deleting it is an owner decision.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

warnings.warn("editorial_by_lang is deprecated: shot lengths come from the timeline lock (write_timeline_lock.py)",
              DeprecationWarning, stacklevel=2)

from editorial_legacy import (FILE, MAX_SPEEDUP, TAIL, apply_rows, apply_shots, load, main, needed_sec,  # noqa: E402,F401
                              pack_shot, plan, plan_shot, scripted_lines, wav_seconds)

if __name__ == "__main__":
    sys.exit(main())
