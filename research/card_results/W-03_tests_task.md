Write ONLY the test file director/test_write_timeline_lock.py (plain pytest, standard library, tmp_path, no network, no model call; start with sys.path.insert of its own folder and the project root so the modules import by bare name or package as the neighbouring tests do). It is the frozen test gate for this gap card; the module change is made later by someone else, so the tests must FAIL on the current code and pass on a correct implementation. Use the hand-computed values written in the card; do not copy code from the module under test. Cover every test name the card lists.

CARD:
### W-03: lock writer CLI (versioned)
- **Files:** director/write_timeline_lock.py NEW; director/test_write_timeline_lock.py NEW.
- **Change:**
  1. **Pure `plan_lock(rows, wav_seconds_fn, langs, acts, min_seconds) -> list`**, plus a CLI: `--pack --wav-root <.../wav_export/wav> --manifest --out-dir --langs [--acts acts.json] [--blocking-dir]`. Add `sys.path.insert(0, HERE); sys.path.insert(0, HERE.parent)`.
  2. **Seconds per shot and language:** `needed_sec([{id, start, natural: wav_seconds(wav_root/lang/wav_name(id, lang))}], 1.0)`, using `build_vo_tracks.scripted_lines` and `editorial_by_lang.needed_sec` (this already includes TAIL 0.10). `voice_seconds[sid] = {lang: need}`. If the blocking `min_seconds` is present, add `"min": min_seconds`. A shot with no lines and no `min_seconds` raises SystemExit(`"<sid>: silent shot needs blocking min_seconds"`). This fixes Opus bug 4 at the caller.
  3. **Beat grid:** `plan_shots([{id, bpm: bpm if snap else None}], voice_seconds, margin_frames=0)`. A shot with snap False and bpm not in {None, 60} that is not the last shot of its act (act = run of shots with the same cue, or the same bpm when there is no cue) raises SystemExit. The non-snap shot at the end of an act also resets the act start inside plan_shots, so two acts with the same BPM do not merge.
  4. **Handles:**
     - `v4_to_h3.fit_lattice([{id, episode:1, editorial_duration_sec: ed/24}])`. Its problems raise SystemExit; a reel of one shot raises SystemExit (`"one-shot reel unsupported"`).
     - Then `_seam_defaults(first, last, ed, pf)` and `_plan_handles(...)` must return problems `[]`.
     - Assert `trim_out - trim_in == edit_frames`.
     - `end_frame_position = trim_out_frame - 1`: the last frame shown, 0-based with trim_out exclusive. Opus wrote trim_out_frame, which is one frame past the cut.
     - The `head_handle`/`tail_handle` keys from plan_shots are made up (core.py:195): drop them.
  5. **Lock row:** `id, edit_frames, start_frame, method, beats, error_ms, spare, lattice_n, pixel_frames, trim_in_frame, trim_out_frame, head_handle_frames, tail_handle_frames, incoming_seam_type, outgoing_seam_type, end_frame_position, bpm, snap, cue, act_start_frame`. bpm is kept even when snap is False, because the cue sheet needs it.
  6. **Params:** first write `timeline_lock_vN.params.json` `{margin_frames:0, tail:TAIL, gap:GAP, tempo:1.0, fps:24, langs, lattice:"v4_to_h3.fit_lattice"}`. Inputs = shots.json, the manifest, the params file, every wav used, acts.json, and the blocking files used. So any change to a param or an input makes the lock stale without a P1 io change.
  7. **Versioning:** N = max existing + 1. If the target exists, raise SystemExit. Write `timeline_lock_vN.json` with `write_lock`, and `timeline_lock_vN.diff.json` listing the `[{id, old, new}]` edit_frames changes against vN-1 (rule 47: tell the music session what changed).
- **Tests (synthetic WAVs written with the `wave` module at 24 kHz):**
  - `test_needed_seconds_drive_edit_frames`: narration start 0.5, en 2.40 s, hi 2.00 s. needed = max(0.5+2.4+0.1, 0.5+2.0+0.1) = 3.0 s, so **72** frames, method `"free"`.
  - `test_snap_only_groove_shots`: S1 128 BPM snap, need 72. One beat = 11.25 frames; beat k=7 gives round(78.75) = **79** (spare 7). The bar candidate gives 90 (spare 18), so 79 wins. S2 128 BPM snap False (last of its act), need 72, gives 72. S3 60 BPM snap False gives 72. bpm column [128, 128, 60].
  - `test_non_snap_mid_act_refused`: SystemExit.
  - `test_handles_legal`: every row has 107 ≤ pf ≤ 345, (pf-5) % 17 == 0, `trim_out - trim_in == edit_frames`, `_plan_handles` problems `[]`, `end_frame_position == trim_out_frame - 1`.
  - `test_silent_shot_needs_min_seconds`: SystemExit without it; min 4.0 gives **96** frames.
  - `test_wav_byte_change_is_stale`: `verify_lock(p, lock["inputs"])` raises StaleLockError.
  - `test_params_change_is_stale`: same check after editing the params file.
  - `test_versioned_never_replaced`: two runs give v1 and v2; v1 bytes unchanged; the diff lists the changed shot.
- **Closes:** 2, 4, 5 (stored; owner accepts ±½ frame), 7, 8; 3 and 39 in part (one lattice picker; bpm, snap, cue stored). Bugs: Opus §2 items 2, 4, 5, 6, 8; reverse-engineering B12.
- **Depends on:** W-02 (exported WAVs with edges).
- **Collisions:** imports `needed_sec` from editorial_by_lang; W-12 moves that import. Uses the private v4_to_h3 functions read-only.
- **Acceptance:** `python -m pytest director/test_write_timeline_lock.py director/test_timeline_lock_core.py director/test_timeline_lock_io.py -q`.
- **Owner decision:** D3 (acts.json, ±20.83 ms). **Risk:** med.



EXTRA HINT: 