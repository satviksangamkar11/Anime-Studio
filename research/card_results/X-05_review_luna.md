- `h3/v4_to_h3.py`: `problems.append(f"{sid}: cast {_id_set(subjects)} != blocking {_id_set(blk_ids)}")` does not produce the card-required problem `"<sid>: cast differs from blocking sheet"`. Change it to `problems.append(f"{sid}: cast differs from blocking sheet")`.

- `h3/v4_to_h3.py`: `_load_blocking_dir` calls `blk.load_sheet(path)` for each file. The card requires loading sheets with `blocking.load_reel` when `blocking_dir` is given. Load the directory through `blk.load_reel(directory)` and handle its validation errors.

- `h3/tests/test_v4_to_h3_x05.py`: the card requires appending these tests to `h3/tests/test_v4_to_h3.py`, but they are in a separate file. The stated acceptance command, `python -m pytest h3/tests/test_v4_to_h3.py -q`, will not run them. Move the tests into the required file.

- `test_no_blocking_dir_unchanged` only compares implicit `blocking_dir=None` with explicit `blocking_dir=None`. Both use the new implementation, so this cannot establish byte equality with the pre-change round-trip output. Compare against a pre-change golden output or an equivalent fixed expected result.

VERDICT: FIX-FIRST.