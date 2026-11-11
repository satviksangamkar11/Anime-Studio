# Nemotron Super plan review, per slice

## branch file list part 1/1
DEFECTS:
- director/timeline_lock.py missing from both branches (not listed as A/M/D); plan 1a requires it as the contract writer.
- core/core.json (D, merge-only) is the sole loudness source per plan 1e but absent from v4 branch; dropping merge-only files loses it and the -14 exclusion guarantee.
- director/build_vo_tracks.py (D), director/voice_cast.py (D), director/build_final_reel.py (D) are required by plan 1b/1c but absent from v4 branch; v4-only code referencing them breaks after merge.
- director/editorial_by_lang.py (D) remains in merge branch although plan 1a says it is replaced; no deletion shown.
- h3/render_controller.py (M) vs director/build_final_reel.py (D): plan 1b's single-verdict requirement cannot be verified because build_final_reel is not in v4 and the slice shows no shared timeline contract.
- director/run_colab_batch.py (A) may issue Colab/paid calls; plan header bars these without owner, but the slice shows no owner gate.

CHANGES:
- Create director/timeline_lock.py: read vo_tracks_report.json (en/hi/mr); per shot edit_frames = max over languages of ceil(sec*24) + margin; snap edit + head handle + tail handle to H3 lattice 17n+5; music acts at BPM 60/128/176 with BPM changes only at act changes; Candidate A whole-bar (128 BPM: 4 beats = 45 frames; 176 BPM: 11 beats = 90 frames) or Candidate B cut at round(beat_idx*(60/bpm)*24) from act start; choose fewer spare frames; write sha256 of text/voice/clips inputs into timeline_lock.json.
- Delete director/editorial_by_lang.py from merge branch/main.
- Keep core/core.json, director/build_vo_tracks.py, director/voice_cast.py, director/build_final_reel.py in main (merge-only files); port them into v4 branch if v4 is used as a source tree.
- Edit h3/render_controller.py _gate_d_result: read timeline_lock.json, refuse stale hash, and use the same timeline source as build_final_reel so Gate D returns one verdict.
- Edit director/voice_cast.export_wavs: emit `<id>.<lang>.wav` only, check RIFF/WAVE header, remove any in-place speed rewrite of the wav.
- Edit director/build_vo_tracks: read `<id>.<lang>.wav` only.
- Add h3/tests/test_loudness_single_source.py to v4 branch (port from merge): fail if core/core.json or any code contains a loudness target other than -16 LUFS / -1 dBTP (specifically -14).

TESTS:
- test_timeline_lock_contract: asserts timeline_lock.json exists, input sha256 matches, every shot length is 17n+5, edit_frames >= max_lang(ceil(sec*24)) + margin.
- test_loudness_single_source: asserts core/core.json has only -16 LUFS / -1 dBTP and no -14 target appears anywhere.
- test_voice_naming: asserts export_wavs writes `<id>.<lang>.wav`, build_vo_tracks reads `<id>.<lang>.wav`, file starts with RIFF/WAVE, and no speed-rewrite call is present.
- test_gate_d_single_verdict: asserts render_controller._gate_d_result and build_final_reel load the same timeline_lock.json hash and return identical duration verdict (not 70.0 vs 72.833).
- test_caption_diff_approved: asserts hi SHOT-003-D1 and SHOT-010-D1 carry spoken_text, caption_text, and caption_diff_approved: true.

PLAN-WRONG:
- Plan 1a requires new director/timeline_lock.py but the slice shows no such file in either branch.
- Plan 1e assumes core/core.json is a single available source, but slice shows it is D (merge-only) and missing from v4.
- Plan 1b requires build_final_reel and render_controller to share one timeline, but build_final_reel.py is D (merge-only) while render_controller.py is M; plan ignores that build_final_reel is absent from v4.
- Plan 1c requires voice_cast and build_vo_tracks everywhere, but both are D (merge-only) and absent from v4.

NEED:
director/build_h3_batch.py
director/run_colab_batch.py
h3/render_controller.py
h3/gate_d_audio.py
director/build_final_reel.py
director/voice_cast.py
director/build_vo_tracks.py
core/core.json
h3/tests/test_loudness_single_source.py

## diff merge->v4 h3/v4_to_h3.py part 1/2
DEFECTS:
- `_source` (h3/v4_to_h3.py, near line 100): `stage` may be unbound at `return shots, bible, stage, ...` when no file matches the stage condition; the `story.json` fallback that populated it was removed.
- `_stages` (h3/v4_to_h3.py): `ti` head-handle offset removed; `a, b` are pure editorial frames, contradicting plan 1a (clip = editorial + head handle) and the removed comment "the head handle comes first".
- `_mouth` (h3/v4_to_h3.py): `ed`/`ti` removed; clip seconds index `mouth_state` directly by `str(s)` with no editorial bounds or handle-only `"closed"` handling, so handle frames and editorial/clip misalignment are mishandled.
- `fit_lattice` deleted (h3/v4_to_h3.py): no row is re-picked to a legal H3 lattice with head/tail handles and matching seam class; contradicts plan 1a (17n+5 with handles, CN-04/05).
- `MOTION_WORDS` (h3/v4_to_h3.py): silent removal of `("pull back","Pull Out")`, `("crane down","Pedestal Down")`, `("crane up","Pedestal Up")`, `("arc ","Arc Shot")` may leave those directives unclassified.

CHANGES:
- `_source`: initialize `stage = None` before the file loop so the return never raises UnboundLocalError.
- `_stages`: restore signature `(directives, pf, sid, problems, ti=0)` and `a, b = round(float(d["t0"]) * FPS) + ti, round(float(d["t1"]) * FPS) + ti`.
- `_mouth`: restore signature `(track, pf, sid, problems, ed=None, ti=0)` and the midpoint mapping: `mid = (s * FPS + min(s * FPS + FPS, pf)) / 2 - ti`; if `ed is not None and not 0 <= mid < ed`: `states[str(s)] = "closed"; continue`; else `e = int(mid // FPS) if mid >= 0 else 0; v = ms.get(str(e))`.
- `_shot`: restore `ti` argument to the `_stages(...)` call and restore `ed_sec = row.get("editorial_duration_sec")` plus `round(ed_sec * FPS) if _is_num(ed_sec) else None, ti` arguments to the `_mouth(...)` call.
- Restore `fit_lattice(shots)` (original body) and call it on the shot list before per-shot `_shot` processing so each row's `lattice_n`/`pixel_frames`/`latent_slots` satisfy legal head/tail handles and seam-class continuity.

TESTS:
- `test_source_no_stage_returns_tuple`: `_source` on a dir with no matching stage file returns a 5-tuple without UnboundLocalError.
- `test_stages_head_handle_offset`: `_stages` with `t0=1.0, t1=2.0, ti=8, FPS=24` yields `a==32, b==56`.
- `test_mouth_handle_seconds_closed`: `_mouth` with `pf=72, ed=48, ti=20, mouth_state={"0":"open"}` yields `states["0"]=="closed"` and `states["1"]=="open"`.
- `test_fit_lattice_bumps_too_small_n`: `fit_lattice` on a shot with `editorial_duration_sec=10.0` and `lattice_n=7` returns non-empty `changes` and resulting `pixel_frames >= 240`.

PLAN-WRONG:
- Plan 1a requires H3 lattice = edit + head handle + tail handle -> 17n+5 with legal cuts; this slice deletes `fit_lattice` and strips `ti` from `_stages`/`_mouth`, so clip frames ignore the head handle and no lattice re-pick occurs.

NEED:
- `h3/shot_table_spec.py` (lattice, LATTICE_N_MIN/MAX, STATIC_SEAMS, INTER, FPS)
- `h3/build_h3_batch.py` or wherever `_shot`/`fit_lattice` is invoked, to place restored lattice fitting

## diff merge->v4 h3/v4_to_h3.py part 2/2
DEFECTS:
- h3/v4_to_h3.py: removal of `**({"metadata": {"look": ..., "purpose": ..., "captions": []}})` deletes `metadata.look`; the inline comment states post.py and assemble_reel read `metadata.look` (palette, act, hook, impacts), so this breaks those consumers with no replacement in the slice.
- Plan 1f (keep merge branch as main, port only missing/newer): deleting an existing merge-branch field that consumers depend on contradicts that instruction.

CHANGES:
Restore the removed metadata spread in h3/v4_to_h3.py exactly as in the merge branch, before the closing `}` of the shot dict:
```
+        **({"metadata": {"look": copy.deepcopy(row["look"]), "purpose": _text(row.get("purpose")), "captions": []}}
+           if isinstance(row.get("look"), dict) else {}),   # audit C 11-08: post.py and assemble_reel read metadata.look (palette, act, hook, impacts)
```

TESTS:
- test_v4_to_h3_metadata_look_present: row with dict `look`; assert result["metadata"]["look"] == copy.deepcopy(row["look"]), result["metadata"]["purpose"] == _text(row.get("purpose")), result["metadata"]["captions"] == [].
- test_v4_to_h3_metadata_look_absent: row without dict `look`; assert "metadata" not in result.

PLAN-WRONG:
- Plan 1f: this slice removes merge-branch functionality (`metadata.look` used by post.py and assemble_reel) instead of porting only missing/newer code and keeping the merge branch as main.

NEED:
post.py
assemble_reel

## diff merge->v4 h3/render_controller.py part 1/1
DEFECTS:
- `_write_assembly` calls `build_ffmpeg_assembly_plan(shots_sel, f"{ep['episode_id']}.mp4")` without `loudness=loud`; the merge branch passed it, so if the parameter is required the plan build fails (cite: `_write_assembly`, v4 side).
- `_write_assembly` drops `attach_colour_seams(plan, [os.path.join(ep_dir, c) for c in clips], shots_sel)` and the `out["colour_seams"]` emission; consumers expecting seam data or that key break (cite: removed block in `_write_assembly`).
- `prepare` no longer calls `load_loudness_plan(os.path.join(str(ep_dir), "loudness.json"))` before `compile_episode` writes shot files, removing the early corrupt-config guard (cite: removed guarded call in `prepare`).
- `render_controller` reads no `timeline_lock.json` and checks no input sha256, so it cannot refuse a stale contract or share one timeline with `build_final_reel` as plan 1b requires (cite: `_write_assembly` and `prepare`).
- Module docstring says "no ffmpeg" but the module still imports `build_ffmpeg_assembly_plan` and `write_assembly_script` and returns ffmpeg filter/cmd artifacts (cite: module docstring and `_write_assembly` return).

CHANGES:
```
--- a/h3/render_controller.py
+++ b/h3/render_controller.py
@@ -18,7 +18,8 @@
 from h3.asset_manifest import H3_MODEL_ID, blocking_problems, hash_bible, hash_frame_file, hash_shot_row, load_manifest
 from h3.compile_h3_sing8 import compile_comfyui_workflow, compile_episode, compile_fl2va_prompt
 from h3.fallback_policy import attempts_for, load_history
+from h3.assemble_reel import attach_colour_seams, build_ffmpeg_assembly_plan, load_loudness_plan, write_assembly_script
-from h3.assemble_reel import build_ffmpeg_assembly_plan, write_assembly_script
@@ -_write_assembly
 def _write_assembly(ep, shots_sel, ep_dir):
+    loud = load_loudness_plan(os.path.join(os.path.dirname(__file__), "..", "core", "core.json"))
+    plan = build_ffmpeg_assembly_plan(shots_sel, f"{ep['episode_id']}.mp4", loudness=loud)
+    clips = [f"{s['shot_id']}/clip.mp4" for s in shots_sel]
+    attach_colour_seams(plan, [os.path.join(ep_dir, c) for c in clips], shots_sel)
     paths = write_assembly_script(plan, clips, ep_dir)
-    return {"filter": paths["filter"], "cmd": paths["cmd"], "total_frames": plan["total_frames"],
-            "total_duration_sec": plan["total_duration_sec"], "seams": len(plan["seam_transitions"])}
+    out = {"filter": paths["filter"], "cmd": paths["cmd"], "total_frames": plan["total_frames"],
+           "total_duration_sec": plan["total_duration_sec"], "seams": len(plan["seam_transitions"])}
+    if "colour_seams_note" not in plan:
+        out["colour_seams"] = len(plan["colour_seams"])
+    return out
@@ -prepare
+                    load_loudness_plan(os.path.join(str(ep_dir), "loudness.json"))   # a corrupt file raises ValueError before any shot file is written
                     written = compile_episode(story, ep_id, str(ep_dir), shot_ids=sel, second_pass=second_pass)
```
- In `prepare`, before `compile_episode`, read `ep_dir/timeline_lock.json`, verify its `sha256` against the sha256 of its inputs (text, voice files, clips), and raise `ValueError` on mismatch so `render_controller` uses the same timeline as `build_final_reel` (plan 1b).

TESTS:
- `test_render_controller_write_assembly_forwards_loudness_and_seams`: monkeypatch `build_ffmpeg_assembly_plan` and `attach_colour_seams`; assert `loudness=` kwarg is forwarded, `attach_colour_seams` is called with the plan and clip paths, and the returned dict contains `colour_seams` when `colour_seams_note` is absent.
- `test_render_controller_prepare_rejects_corrupt_loudness_before_write`: plant invalid `loudness.json` in `ep_dir`; assert `prepare` raises `ValueError` and `compile_episode` is not invoked.
- `test_render_controller_prepare_refuses_stale_timeline_lock`: plant `timeline_lock.json` with an input sha256 mismatch; assert `prepare` raises before `compile_episode`.
- `test_loudness_single_source_core_json`: assert no file outside `core/core.json` defines a loudness target other than -16 LUFS / -1 dBTP (e.g., -14 LUFS).

PLAN-WRONG:
- Plan 1b requires `render_controller._gate_d_result` to use the same timeline as `build_final_reel`; this slice removes contract/loudness reading from `render_controller` and does not modify `_gate_d_result`, contradicting the single-timeline requirement.
- Plan 1e requires one loudness source in `core/core.json`; the slice deletes loudness loading from `render_controller` without routing it to `core/core.json`, leaving this consumer with no loudness enforcement.
- Plan header says ffmpeg runs only for the G3 colour-seam check; the v4 docstring says "no ffmpeg" while the code still builds ffmpeg filter/cmd assembly artifacts, contradicting the documented behaviour.

NEED:
- `h3/assemble_reel.py` — confirm `build_ffmpeg_assembly_plan` signature (is `loudness` required?) and that `load_loudness_plan` / `attach_colour_seams` still exist.
- `director/timeline_lock.py` (or the `timeline_lock.json` reader) — confirm the sha256/refusal API for exact implementation.
- `core/core.json` — confirm loudness field path and that no -14 target remains.

## diff merge->v4 h3/h3_author.py part 1/1
DEFECTS:
- `scheduler_caller()` references `e2e_sample` but the `from h3 import e2e_sample` import was deleted; `e2e_sample` is undefined in this scope (NameError) unless imported elsewhere. Cite: `scheduler_caller` body.
- `_lint_candidate` removed the temp-dir keyframe staging and `_placeholder_png` writes; it now passes `asset_root: root` directly (possibly `None`). If real boundary frames are not on disk (authoring precedes Gate B), the converter/linter lacks the two profile-sized pictures needed for KF-06/route/PR-00 prompt compile, so lint can fail or be wrong. Cite: deleted `_placeholder_png`, removed `tempfile` block in `_lint_candidate`.
- `_lint_candidate` docstring lost the boundary-frame/placeholder explanation; remaining text describes behavior no longer implemented.
- `scheduler_caller(model=None)` lost the `model` parameter; `main` lost `--model` and `--opus`; `claude_caller` deleted. This removes the free-model model override and the owner-gated Claude Opus path (`--opus` bypassed `LIVE_FLAG_ENV`), contradicting owner-gated step 5 and the comment "owner: use the Super model".
- `main` now unconditionally requires `LIVE_FLAG_ENV=1` for `--live`; no Opus bypass remains, so an owner cannot run the Claude author path without setting the free-model flag.

CHANGES:
Restore merge-branch behavior in `h3/h3_author.py`:
1. Re-add `from h3 import e2e_sample` inside `scheduler_caller`; restore `def scheduler_caller(model=None):` with `sch = e2e_sample.live_scheduler()`, `if model: sch.model = model`, and `return e2e_sample._ask(sch)`.
2. Re-add `claude_caller(model="opus", effort="low")` using `director/write_pack.call_claude`.
3. Re-add `_placeholder_png(width, height)` stdlib PNG generator before `_lint_candidate`.
4. Re-add temp-dir keyframe staging in `_lint_candidate`: `w, h = conv.load_default_profile("sing8_864x1536")["base_resolution"]`; `with tempfile.TemporaryDirectory() as tmp:`; create `tmp/keyframes`; for each shot and letter AB, copy `root/keyframes/<id>-<letter>.png` if present else write `_placeholder_png(w, h)`; call `conv.convert_pack({"shots": shots, "bible": bible, "stage": {}, "asset_root": tmp}, languages=["en"])`; restore full docstring including boundary-frame/placeholder text.
5. Re-add `main` arguments `--model` and `--opus`; restore caller selection `caller = (claude_caller() if args.opus else scheduler_caller(args.model)) if args.live else None`; restore `if args.live and args.opus: pass` bypass before the `LIVE_FLAG_ENV` check.

TESTS:
- `test_scheduler_caller_imports_and_sets_model`: monkeypatch `h3.e2e_sample.live_scheduler` to return a fake scheduler; call `scheduler_caller("nvidia/nemotron-3.5-super-vl-120b-a12b")`; assert `fake.model == "nvidia/nemotron-3.5-super-vl-120b-a12b"` and `_ask` is invoked.
- `test_placeholder_png_valid`: assert `_placeholder_png(864, 1536)` starts with `\x89PNG\r\n\x1a\n` and IHDR width/height are 864/1536.
- `test_lint_candidate_missing_keyframes_no_crash`: call `_lint_candidate` with `root` lacking `keyframes/`; assert it returns a list and does not raise `FileNotFoundError`.
- `test_claude_caller_returns_text`: monkeypatch `write_pack.call_claude` to return `{"result": "ok"}`; assert `claude_caller()("p") == "ok"`.
- `test_main_opus_bypasses_live_flag`: run `main(["--live", "--opus", "--pack-dir", d])` with `LIVE_FLAG_ENV` unset and Claude monkeypatched; assert exit code 0 and no "refused" message on stderr.

PLAN-WRONG:
- Plan 1f says keep merge branch as main and port only what is missing/newer; this slice deletes merge functions (`_placeholder_png`, `claude_caller`, `--model`, `--opus`, placeholder keyframe staging, `e2e_sample` import) instead of preserving them, so applying it regresses main.

NEED:
h3/e2e_sample.py
director/write_pack.py
module defining `conv` (imported in h3_author.py)

## diff merge->v4 h3/schema_and_linter.py part 1/1
DEFECTS:
- h3/schema_and_linter.py SFX_CUE_RE: v4 branch drops alternation tokens bird|song|stream|breeze|murmur|whisper|crackle|rumble|echo|tone|chant|drone|gust|sigh|flutter|patter|ripple|trickle|clang|rush|swell|twang|clasp|conch|thunk, keeping only thump|buzz|chime|bell; the adjacent comment fixes SX_MIN_STAGE_CUES = 7 and requires a sound cue on each of the 7 action sentences, so the narrowed regex causes false negatives and can fail SX-01 lint.
- Taking this v4 subset over the merge branch contradicts the plan rule to keep the merge branch as main and port only what is missing/newer; the change is unrelated to the timeline contract (1a-1f).

CHANGES:
- h3/schema_and_linter.py: restore SFX_CUE_RE to the merge-branch alternation so v4 matches merge.
```
diff --git a/h3/schema_and_linter.py b/h3/schema_and_linter.py
@@ -107,8 +107,7 @@ TAG_RES = (CHIP_RE, BRACKET_TAG_RE, PANEL_RE, ARROW_RE, TIMING_LABEL_RE)
 QUOTE_RE = re.compile(r'"[^"\n]*"|“[^”\n]*”')                   # TX-01 on-screen text
 SFX_CUE_RE = re.compile(r"\b(?:sound|hiss|rustle|splash|wind|water|step|breath|hum|whoosh|roar|crack|thud|drip|flow|"
                         r"ring|voice|pop|click|tick|knock|snap|slam|scrape|tap|clink|creak|crunch|rain|spray|swish|"
-                        r"thump|buzz|chime|bell)\w*", re.I)                    # SX-01 synchronized physical sound
+                        r"thump|buzz|chime|bell|bird|song|stream|breeze|murmur|whisper|crackle|rumble|echo|tone|chant|drone|gust|sigh|flutter|patter|ripple|trickle|clang|rush|swell|twang|clasp|conch|thunk)\w*", re.I)                    # SX-01 synchronized physical sound
```

TESTS:
- test_sfx_cue_re_matches_restored_tokens: assert SFX_CUE_RE.search() matches each restored token (bird, song, stream, breeze, murmur, whisper, crackle, rumble, echo, tone, chant, drone, gust, sigh, flutter, patter, ripple, trickle, clang, rush, swell, twang, clasp, conch, thunk) plus thump/buzz/chime/bell.
- test_sx_min_stage_cues_met: assert len(SFX_CUE_RE.findall(seven_action_sentence_fixture)) >= SX_MIN_STAGE_CUES (7).

PLAN-WRONG:
- The slice contradicts plan instruction "keep the merge branch as main" by substituting a v4 subset for the merge-branch SFX_CUE_RE; plan text otherwise does not address SFX_CUE_RE/SX-01.

NEED:
- none

## merge-tree director/editorial_by_lang.py part 1/1
DEFECTS:
- `director/editorial_by_lang.py` is the legacy workflow plan 1a replaces: `main()` writes `editorial_by_lang.json` with `by_lang: {en: shared, hi: shared, mr: shared}` and hardcodes `MAX_SPEEDUP = 1.03` plus beat rounding (`60.0 / bpm`); plan 1a removes this file, the three tempo limits (1.03/1.15/1.15), and per-language duplication in favor of `timeline_lock.json` carrying a sha256 of inputs.
- No H3 lattice `17n+5` enforcement: `apply_shots()` only does `t["trim_out_frame"] += n` / `t["trim_in_frame"] -= n` and never snaps `edit + head handle + tail handle` to `17n+5` (plan 1a).
- `plan()` violates the last-shot start-only rule: `spare = tail if not last or tail else 0` and `at = "start" if last and not tail else "end"` extends the last shot at its END using tail spare whenever `tail` is non-zero, and never uses head spare `t["trim_in_frame"]` for the last shot (plan 1a: last shot may only grow at its START).
- `load()` returns `{}` when the contract is missing ("Missing file = the v3 build, unchanged"); plan 1b requires consumers to refuse a stale/missing contract, not silently fall back.
- `apply_rows()` changes only `r["editorial_duration_sec"]`, leaving `editorial_frames`, `trim_out_frame`, and `master_reel_*` windows stale/inconsistent.
- No RIFF/WAVE or ID3 header validation on voice files (plan 1c); it passes `Path(raw_root) / lg / f"{k}.{lg}.wav"` straight to `wav_seconds`.

CHANGES:
- Delete `director/editorial_by_lang.py` (remove `FILE`, `MAX_SPEEDUP`, `load`, `apply_rows`, `apply_shots`, `needed_sec`, `plan_shot`, `plan`, `main`).
- Add `director/timeline_lock.py` with CLI `--pack --story --vo-report --langs --write`: read measured natural durations from `vo_tracks_report.json`; per shot `edit_frames = max over langs of ceil(sec*24) + margin`; snap `edit + head_handle + tail_handle` to H3 lattice `17n+5`; compute `sha256` over inputs (text, voice files, clips); write `timeline_lock.json` carrying one shared timeline (identical entries for en/hi/mr), the input sha256, and no tempo-limit/beat fields.
- Update consumers (H3 lattice, `build_vo_tracks`, `build_final_reel`/Gate D, captions, music cue sheet) to read `timeline_lock.json` and reject when the stored input sha256 does not match; make `render_controller._gate_d_result` use the same timeline object as `build_final_reel`.

TESTS:
- `test_timeline_lock_shared_contract`: `vo_tracks_report.json` with en/hi/mr durations that differ per shot; assert written `timeline_lock.json` entries are identical across `en`/`hi`/`mr`, `edit_frames == max_lg(ceil(sec*24)+margin)`, and shot total frames fit `17n+5`.
- `test_timeline_lock_input_hash_rejected`: flip one byte in an input voice file; assert contract `sha256` changes and a consumer stub raises on stale hash.
- `test_last_shot_start_only`: last shot with `trim_in_frame` head spare and zero tail; assert extension reduces `trim_in_frame` (start) and never increases `trim_out_frame`.

PLAN-WRONG:
- Plan 1a replaces `editorial_by_lang.json` with `timeline_lock.json` and drops the three tempo limits (1.03/1.15/1.15); this slice writes `editorial_by_lang.json` and hardcodes `MAX_SPEEDUP = 1.03` with beat rounding.
- Plan 1a last-shot start-only rule contradicted by `at = "start" if last and not tail else "end"` (end extension when tail exists).
- Plan 1a requires contract sha256 of inputs and H3 lattice `17n+5`; this slice has neither.

NEED:
- `director/build_vo_tracks.py`
- `vo_tracks_report.json`

## merge-tree director/build_vo_tracks.py part 1/1
DEFECTS:
- `build_vo_tracks.py` imports `editorial_by_lang` and calls `apply_rows(...)` / `load(pack)` in `build`; `scripted_lines` reads `n["time_range"][0]` and `d["time_range"][0]`. Plan 1a retires `editorial_by_lang.json` and writer `time_range` in favor of `timeline_lock.json`.
- `MAX_TEMPO = 1.15` is a module constant. Plan 1a removes the three tempo limits, so the limit must come from the contract, not hardcoded here.
- `pack_shot` scans `t += 0.01` and returns `round(t, 2)`, so it does not return the true smallest fitting tempo; it returns the smallest 0.01 increment.
- `render_shot` sets `end = math.floor((editorial - TAIL) * 1000) / 1000` and pads/trims to `end`, so the output is `editorial - TAIL` seconds, contradicting the docstring ("exactly `editorial` seconds") and the contract edit length.
- `render_shot` `atrim=0:{end:.3f}` can cut up to 1 ms of speech because `pack_shot` only guarantees `cur <= editorial - TAIL`, not `cur <= end` (floored); the comment itself cites Gate D `VO_OVERFLOW_ERROR`.
- `wav_seconds` uses `wave.open` only; the docstring accepts mp3/wav but there is no RIFF/WAVE or ID3 header check required by plan 1c.
- `build` writes `dst = ... / f"{row['id']}.wav"`; plan 1c requires `<id>.<lang>.wav` everywhere.
- `build`/`pack_shot` compute no sha256 of inputs (text, voice files, clips) and `build` reads no `timeline_lock.json`, violating plan 1a/1b (contract hash and stale-hash refusal).
- `render_shot` uses `adelay={ms}|{ms}` on mono audio; the second delay value is invalid/meaningless for one channel.

CHANGES:
- `pack_shot`: replace the `while t <= max_tempo + 1e-9: ... t += 0.01` loop with a binary search over `t in [1.0, max_tempo]` returning the minimal `t` (rounded to 3 decimals) for which the last `cur <= limit`; raise `ValueError` if none fits.
- `render_shot`: set `end = editorial` (remove `TAIL` subtraction and ms floor); keep `apad=whole_dur={end:.3f},atrim=0:{end:.3f}` so the file is exactly `editorial` seconds.
- `render_shot`: change `adelay={ms}|{ms}` to `adelay={ms}`.
- `build`: remove `from editorial_by_lang import apply_rows, load` and the `apply_rows(...)` call; load `timeline_lock.json` from `pack`; use `edit_frames / 24` as `editorial`; read per-shot/lang start times from the lock file instead of `time_range[0]`; pass lock `max_tempo` (and `gap`/`tail` if present) to `pack_shot`.
- `build`: write output as `Path(out_dir) / lang / f"{row['id']}.{lang}.wav"`.
- Add header validation before `wav_seconds`: reject files that do not start with `RIFF....WAVE` or `ID3`.
- `build`: add `sha256` of `shots.json`, the source voice file, and the clip to each report entry.

TESTS:
- `test_pack_shot_minimal_tempo`: one line natural 2.0 s at start 0, editorial 2.5 s, tail 0.1, max_tempo 1.15; assert returned tempo is the true minimum (~1.053) and last `end <= 2.4` s.
- `test_render_shot_exact_duration`: one line; assert output wav `getnframes()/getframerate() == editorial` (not `editorial - TAIL`).
- `test_output_name_lang_suffix`: assert `dst` name equals `<id>.<lang>.wav`.
- `test_rejects_invalid_header`: pass a file with neither RIFF/WAVE nor ID3 header; assert `build` rejects it.
- `test_refuses_stale_lock`: after change, `timeline_lock.json` sha256 mismatch; assert `build` raises/refuses.

PLAN-WRONG:
- Plan 1a says `timeline_lock.json` replaces `editorial_by_lang.json` and `time_range`; this code still imports `editorial_by_lang` and reads `time_range[0]`.
- Plan 1a says edit length comes from frame-based `ceil(sec*24)` + H3 lattice; this code uses `editorial_duration_sec` directly.
- Plan 1a says the three tempo limits are replaced; this code hardcodes `MAX_TEMPO = 1.15`.
- Plan 1b says every consumer reads the contract and refuses a stale hash; this code reads no contract and checks no hash.
- Plan 1c says `<id>.<lang>.wav` everywhere and RIFF/WAVE or ID3 header check; this code writes `<id>.wav` and has no header check.
- Docstring promises exactly `editorial` seconds; code writes `editorial - TAIL` seconds.

NEED:
- `director/timeline_lock.py` or `timeline_lock.json` schema (field names for `edit_frames`, `max_tempo`, sha256 inputs, per-shot start times).
- `editorial_by_lang.py` (to confirm what `apply_rows`/`load` provide and what is being removed).
- `build_final_reel.py` or `render_controller.py` (to confirm Gate D expects VO files exactly `editorial` seconds, not `editorial - TAIL`).

## merge-tree director/voice_cast.py part 1/3
DEFECTS:
- `Ledger.reserve()` (visible through trailing `finally:`): acquires `(fd, lock)` via `_lock()` but the shown code never executes `os.close(fd)` or `lock.unlink()`; the ledger lock is never released, so every run after the first dies with "the credit ledger is locked by another run".
- `load_plan()`: `a["narration_by_lang"]` and `a["dialogue_by_lang"]["en"]` use direct subscript; a missing track or missing `en` raises `KeyError` instead of the documented clear "language missing is an error".
- `load_plan()`: `a["dialogue_by_lang"][lg][k - 1]["text"]` assumes hi/mr dialogue lists are at least as long as en; a shorter list raises `IndexError`.
- `build_jobs()`: `l[lang]` raises `KeyError` when a line lacks a language; no explicit validation error.
- `Ledger.rows()`: `json.loads(ln)` crashes on blank or corrupt ledger lines.

CHANGES:
- `Ledger.reserve()`: in the `finally:` block add `os.close(fd)` and `lock.unlink(missing_ok=True)` so the lock is released after `reserve` returns.
- `load_plan()`: replace direct subscripts `a["narration_by_lang"]` and `a["dialogue_by_lang"]["en"]` with explicit existence checks; after building `lines`, verify every `lg in LANGS` has non-empty `text` for each narration/dialogue line and that all dialogue lists have equal length; raise `SystemExit` naming the missing language/line on failure.
- `build_jobs()`: before `text = voices.prep_text(l[lang])`, add `if lang not in l: raise SystemExit(f"line {i} missing {lang} text")`.
- `Ledger.rows()`: `continue` on `not ln.strip()` and wrap `json.loads(ln)` in `try/except json.JSONDecodeError` raising `SystemExit("corrupt ledger line")`.
- `voice_cast.export_wavs` (not in this slice): write `<id>.<lang>.wav`, never rewrite an accepted wav in place for speed, and check RIFF/WAVE or ID3 header on read.

TESTS:
- `test_load_plan_missing_hi_narration`: shots.json with narration missing `hi` text asserts `SystemExit` is raised with a clear message.
- `test_load_plan_dialogue_count_mismatch`: en has 2 dialogue entries, hi has 1 asserts `SystemExit` is raised.
- `test_build_jobs_missing_lang`: plan line missing `mr` asserts `SystemExit` is raised.
- `test_ledger_reserve_releases_lock`: call `Ledger.reserve` twice in one process asserts the second call succeeds (lock released).
- `test_ledger_rows_blank_line`: ledger file with a trailing blank line asserts `rows()` returns a dict without crashing.

PLAN-WRONG:
- Plan 1c says `voice_cast.export_wavs writes <id>.wav` but `build_vo_tracks reads <id>.<lang>.wav`; export and read names disagree, and this slice's docstring names clips by job-key sha256, contradicting `<id>.<lang>.wav`.
- Plan 1c forbids in-place speed rewrite of the wav, but `build_jobs()` puts `speed` into `settings`/`job_key`; if speed is applied by rewriting the wav rather than at generation, it violates the plan.

NEED:
- director/voice_cast.py parts 2/3 (export_wavs, run, measured)
- director/build_vo_tracks.py (reads `<id>.<lang>.wav`)

## merge-tree director/voice_cast.py part 2/3
DEFECTS:
- `export_wavs`: `dst = wav_dir / "wav" / r["lang"] / f"{r['id']}.wav"` writes `<id>.wav`; plan 1c requires `<id>.<lang>.wav` everywhere and `build_vo_tracks` reads `<id>.<lang>.wav`, so the written file is never found.
- `export_wavs`: the `if slots:` block computes `tempo = max(1.0, secs / slot)` and (per the cut-off text) applies atempo up to `MAX_TEMPO = 1.15` to the wav copy — an in-place speed rewrite of the wav, which plan 1c forbids ("no in-place speed rewrite of the wav") and plan 1a removes (tempo limits replaced by the timeline contract).
- No RIFF/WAVE or ID3 header check: `run` writes raw POST bytes to an mp3 and only `probe_seconds` decodes it; `export_wavs` never validates the wav header (plan 1c requires header check).
- `load_slots` only reads `"en"` (`a["narration_by_lang"]["en"]`, `a["dialogue_by_lang"]["en"]`), ignoring hi/mr, so plan 1a's `max over languages` cannot be computed.
- `latest_ok` picks the newest clip by dict overwrite order (`d[r["id"]] = r`) with no timestamp sort, so a re-take is not provably the newest despite the docstring.
- `fit_report`: `verdict: "fits" if tempo == 1.0` uses float equality on `r["seconds"] / slot`.
- `run` reuses a cached clip when `sha256_file(out / r["file"]) == r["mp3_sha256"]` without comparing `text_sha256`/job text, so changed text under the same key silently reuses a stale clip.
- `run`/`measured` carry `script_sha256` but there is no `timeline_lock.json` contract hash and no stale-input refusal (plan 1a/1b); the slice has no contract consumer.

CHANGES:
- `export_wavs`: change destination to `wav_dir / "wav" / r["lang"] / f"{r['id']}.{r['lang']}.wav"`.
- `export_wavs`: delete the `if slots:` tempo/atempo block; decode+trim only, no in-place speed rewrite of the wav.
- `run`: after `f.write_bytes(data)`, raise `RuntimeError` unless `data[:3] == b"ID3"`. `export_wavs`: after ffmpeg, raise unless dst header bytes 0:4 == `b"RIFF"` and 8:12 == `b"WAVE"`.
- `load_slots`: iterate `a["narration_by_lang"].values()` and `a["dialogue_by_lang"].values()` for every language and store `out[line_id] = max(out.get(line_id, 0), window_s)`.
- `run`: add `"t": time.time()` to `row`. `latest_ok`: keep the row with the greatest `r.get("t", 0)` per id instead of blind overwrite.
- `fit_report`: replace `tempo == 1.0` with `tempo <= 1.0 + 1e-6`.
- `measured`: require `script_sha256` to equal the timeline contract's script input hash and append a problem/refuse on mismatch (plan 1a/1b contract consumer).

TESTS:
- `test_export_wavs_names_id_lang_wav`: run `export_wavs` with one accepted clip; asserts `wav/<lang>/<id>.<lang>.wav` exists and `wav/<lang>/<id>.wav` does not.
- `test_export_wavs_no_atempo`: monkeypatch `subprocess.run`; asserts ffmpeg args contain no `atempo` and the wav is written.
- `test_export_wavs_riff_wave_header`: asserts produced wav starts with `b"RIFF"` and bytes 8:12 == `b"WAVE"`.
- `test_load_slots_max_over_languages`: shots.json with en window 2.0 s and hi window 3.0 s for the same line; asserts slot == 3.0.
- `test_fit_report_fits_tolerance`: clip with tempo 1.0000002 asserts verdict == "fits".
- `test_run_rejects_non_id3`: monkeypatch `post` to return bytes not starting with `b"ID3"`; asserts `RuntimeError` is raised and no mp3 file is written.

PLAN-WRONG:
- Plan 1a says the three tempo limits (1.03 / 1.15 / 1.15) are replaced by the timeline contract, but this slice still defines `MAX_TEMPO = 1.15` and `fit_report`/`export_wavs` speed-fit clips to it — code and plan disagree on whether local tempo limits remain.

NEED:
- director/build_vo_tracks.py (confirm it reads `<id>.<lang>.wav` and consumes slots)
- director/timeline_lock.py or contract schema (confirm hash inputs and stale-refusal behavior)
- merge-tree shots.json (confirm narration_by_lang/dialogue_by_lang contain en/hi/mr)

## merge-tree director/voice_cast.py part 3/3
DEFECTS:
- director/voice_cast.py (slice): ffmpeg `atempo` followed by `os.replace(tmp, dst)` rewrites the wav in place; plan 1c forbids in-place speed rewrite and plan 1a removes tempo limits.
- Same block: verdicts "fit by atempo" / "TOO LONG: owner decision" and `MAX_TEMPO` contradict plan 1a (tempo limits 1.03/1.15/1.15 removed; H3 lattice decides fit).
- `measured` writes `eleven_measured.json` and hashes only `shots.json`; plan 1a requires measured natural durations feeding `timeline_lock.json` with sha256 over text, voice files, and clips.
- No RIFF/WAVE or ID3 header check on voice files in this slice (plan 1c).
- `export` calls `export_wavs`, which plan 1c identifies as writing `<id>.wav` while consumers read `<id>.<lang>.wav`.

CHANGES:
- director/voice_cast.py: delete the atempo ffmpeg block and `os.replace`; remove `tempo` from the report dict and drop `MAX_TEMPO`; report only `id`, `seconds`, `slot`, and a non-atempo verdict flagged for owner timeline decision.
- export_wavs: write `<id>.<lang>.wav`; validate RIFF/WAVE or ID3 header before accepting a wav; never rewrite in place.
- measured: emit per-shot per-lang natural durations and a sha256 over `shots.json` text, voice files, and clips; write to the timeline_lock input report (vo_tracks_report.json) instead of `eleven_measured.json`.
- Keep `run` requiring `--allow-paid` (no change).

TESTS:
- test_export_wavs_naming_no_atempo: run export with mock manifest/slots; asserts outputs named `<id>.<lang>.wav`, no `.fit.wav`, no ffmpeg atempo call, invalid header rejected.
- test_measured_contract_hash: run measured; asserts output includes per-lang durations and sha256 over text+voice+clips.
- test_run_blocks_without_allow_paid: invoke `run` without `--allow-paid`; asserts non-zero exit before any paid call.

PLAN-WRONG:
- Plan 1a removes the three tempo limits and end-extension, but this slice still applies `MAX_TEMPO` and atempo "fit by atempo".
- Plan 1c describes `voice_cast.export_wavs` writing `<id>.wav` as the current defect; the slice's `export` still invokes it unchanged.

NEED:
director/voice_cast.py parts 1/3 and 2/3 (export_wavs, MAX_TEMPO, measured, paths, load_slots)
director/build_vo_tracks.py (reads `<id>.<lang>.wav`)
director/timeline_lock.py (contract writer target for measured output)
core/core.json (single loudness source)

## merge-tree director/build_final_reel.py part 1/3
DEFECTS:
- `mux_argv` builds VO path as `Path(vo_dir) / lang / f"{r['id']}.wav"`; plan 1c requires `<id>.<lang>.wav` everywhere. (line: `p = Path(vo_dir) / lang / f"{r['id']}.wav"`)
- `mux_argv` creates SFX entries with `input_index: f"h3s{k}"` but never appends SFX audio inputs to `inputs`, so ffmpeg filters reference nonexistent input streams. (lines: `inputs, vo_refs, offsets, t = [str(video)], [], [], 0.0` and `sfx = [...]`)
- `mux_argv` and `spoken_cues_real` compute per-shot offsets from `editorial_duration_sec` in seconds instead of `timeline_lock.json` edit_frames / 24, and never read or refuse a stale contract hash. (lines: `offsets[r["id"]] = t; t += float(r["editorial_duration_sec"])`)
- `CAPTION_FIXES` silent `.replace(old, new)` remains; plan 1d requires explicit `spoken_text`/`caption_text` fields plus `caption_diff_approved: true`. (lines: `CAPTION_FIXES = {...}` and `text[line_id] = text[line_id].replace(old, new)`)
- `PLAY_W, PLAY_H = 1080, 1920` and `CAPTION_POS = (510, 1290)` target a 1080-wide canvas; plan header fixes the reel at 768x1344, so burned caption geometry will be wrong. (lines: `PLAY_W, PLAY_H = 1080, 1920`, `CAPTION_POS = (510, 1290)`)
- `probe_frames` only checks `got < need` where `need = trim_out_frame`; it does not verify the source covers `[trim_in_frame, trim_out_frame]` and crashes on empty ffprobe output. (line: `if got < need:`)
- `mux_argv` silently uses `(None, ed)` when a VO wav is missing, allowing a reel to build with silent shots instead of failing. (line: `else: vo_refs.append((None, ed))`)
- `assemble_video` indexes `clips[s["shot_id"]]` without a key check; missing shot raises KeyError. (line: `paths = [str(clips[s["shot_id"]]) for s in h3_shots]`)
- No guard that core.json delivery loudness is the single -16 LUFS / -1 dBTP target and that no -14 target exists. (line: `d = load_core()["delivery"]`)

CHANGES:
- In `mux_argv`: change `p = Path(vo_dir) / lang / f"{r['id']}.wav"` to `p = Path(vo_dir) / lang / f"{r['id']}.{lang}.wav"`; replace `else: vo_refs.append((None, ed))` with `raise FileNotFoundError(f"missing VO {p}")`.
- In `mux_argv`: append each shot's H3 SFX stem to `inputs` before building `sfx`, use integer input indices (e.g. `1 + len(vo_refs) + k`) instead of `f"h3s{k}"` strings, and pass those indices to `gd.build_sfx_split_filter` and `gd.build_mix_filter`.
- In `mux_argv` and `spoken_cues_real`: load `timeline_lock.json`, verify its sha256 over text/voice/clips inputs, refuse on stale/missing hash, and compute `t` from `edit_frames / 24` per shot rather than `editorial_duration_sec`.
- Remove the `CAPTION_FIXES` dict; in `spoken_cues_real`, for each line entry use `caption_text` when `caption_diff_approved` is true, otherwise `spoken_text`, and build cues from that text.
- Set `PLAY_W, PLAY_H = 768, 1344`; rescale `CAPTION_MAX_W` to `592` and `CAPTION_POS` to `(360, 903)`.
- In `probe_frames`: raise `ValueError` if ffprobe output is empty or non-numeric; change the check to also fail when `trim_in_frame >= got`.
- In `assemble_video`: before building `paths`, verify `s["shot_id"] in clips` for every shot, else raise `KeyError` with the shot id.
- After `d = load_core()["delivery"]` in `assemble_video`: assert `"-14" not in json.dumps(d)` and that the delivery loudness fields equal the core.json -16 LUFS / -1 dBTP values.

TESTS:
- `test_voice_path_uses_lang_suffix`: assert `mux_argv` constructs `<id>.<lang>.wav` and raises `FileNotFoundError` when the file is absent.
- `test_timeline_lock_hash_refusal`: call the build with a `timeline_lock.json` whose sha256 does not match the inputs; assert it raises before ffmpeg.
- `test_caption_text_field_not_CAPTION_FIXES`: assert module has no `CAPTION_FIXES`; feed `spoken_cues_real` a row with `spoken_text`, `caption_text`, and `caption_diff_approved: true`; assert cues use `caption_text`.
- `test_core_loudness_single_target`: import the module, load core delivery, assert `-14` is absent and loudness is -16 LUFS / -1 dBTP.
- `test_reel_caption_resolution`: assert `PLAY_W == 768` and `PLAY_H == 1344`.
- `test_probe_frames_empty_ffprobe`: monkeypatch `subprocess.run` to return empty stdout; assert `probe_frames` raises `ValueError`.

PLAN-WRONG:
- Plan header states reel is 768x1344; code uses `PLAY_W, PLAY_H = 1080, 1920`.
- Plan 1a requires H3 lattice `edit_frames` from `timeline_lock.json`; code uses `editorial_duration_sec` seconds.
- Plan 1b requires every consumer to read the contract and refuse a stale hash; code never reads `timeline_lock.json`.
- Plan 1c requires `<id>.<lang>.wav`; code reads `<id>.wav`.
- Plan 1d requires removing silent `CAPTION_FIXES` in favor of `spoken_text`/`caption_text` + `caption_diff_approved: true`; code retains `CAPTION_FIXES`.

NEED:
director/timeline_lock.py
h3/gate_d_audio.py
h3/assemble_reel.py
core/core.json

## merge-tree director/build_final_reel.py part 2/3
DEFECTS:
- `main` imports `editorial_by_lang` and loads `<pack>/editorial_by_lang.json` (`from editorial_by_lang import apply_rows, apply_shots, load`; `ext = load(a.pack)`), so the build still uses the old end-extension instead of the new `timeline_lock.json` contract required by plan 1a.
- No `timeline_lock.json` is read and no sha256 of text/voice/clips is verified anywhere in this slice, so `build_final_reel` does not refuse a stale contract as plan 1b requires for Gate D/mux.
- `h3_shots = apply_shots(story["episodes"][0]["shots"], ext)` and `assemble_video(h3_shots, ...)` use editorial_by_lang lengths (duplicate totals 70.0/70.8/72.833 s) rather than the 17n+5 H3 lattice from plan 1a.
- `measure` runs `subprocess.run(gd.build_loudness_verify_argv(...), capture_output=True, text=True)` without `check=True`; a failed loudness probe returns empty stderr and `gd.check_post_aac_loudness(text)` may crash or emit invalid stats.
- `spoken_cues_real` indexes `offsets[sh["shot"]]` (`offsets[sh["shot"]] + ln["start"]`) with no guard; a shot missing from `offsets` raises `KeyError` and aborts caption generation.
- `main` silently falls back to `lp["captions"]` when `vo_tracks_report.json` is missing (`if a.title_cards or not report_path.is_file(): cues = lp["captions"]`), hiding missing voice/timeline data instead of refusing (plan 1b).
- `correct_loudness` returns the last measurement even when `loud["ok"]` is still false after `tries`, and `main` records `loudness_ok=false` without blocking the export.
- `loud = correct_loudness(export, measure(export))` measures the export twice before the loop.

CHANGES:
- Create `director/timeline_lock.py` with `load(pack) -> (rows, h3_shots, inputs_sha256)` built from `vo_tracks_report.json` (en/hi/mr) per plan 1a: `edit_frames = max over languages of ceil(sec*24) + margin`, then H3 lattice `17n+5`; `inputs_sha256` over text, voice files, clips.
- In `build_final_reel.main`: replace `from editorial_by_lang import apply_rows, apply_shots, load` with `from timeline_lock import load as load_lock`; replace `ext = load(a.pack)` with `rows, h3_shots, inputs_sha256 = load_lock(a.pack)`; add `if inputs_sha256 != sha256(text, voice files, clips): raise SystemExit("stale timeline lock")`; pass `h3_shots` to `assemble_video` and `shots=rows` to `gd.plan_language_outputs`.
- In `measure`: add `check=True` to the `subprocess.run` call.
- In `spoken_cues_real`: replace `offsets[sh["shot"]]` with `off = offsets.get(sh["shot"]); if off is None: raise KeyError(f"missing offset for shot {sh['shot']}")` and use `off`.
- In `main`: replace `if a.title_cards or not report_path.is_file(): cues = lp["captions"]` with `if a.title_cards: cues = lp["captions"]` and `if not report_path.is_file(): raise SystemExit("missing vo_tracks_report.json")`.
- In `correct_loudness`: after the `for` loop, add `if not loud["ok"]: raise SystemExit("loudness outside -16 LUFS / -1 dBTP")`.
- In `main`: replace `loud = correct_loudness(export, measure(export))` with `loud = measure(export); loud = correct_loudness(export, loud)`.

TESTS:
- `test_timeline_lock_stale_hash_rejected`: write a `timeline_lock.json`, tamper one input file, run `main`, assert `SystemExit` mentioning stale lock.
- `test_measure_ffmpeg_fails`: monkeypatch `subprocess.run` to return nonzero for the loudness probe, call `measure`, assert `subprocess.CalledProcessError` propagates.
- `test_spoken_cues_real_missing_offset`: call `spoken_cues_real` with a report shot absent from `offsets`, assert `KeyError`.
- `test_correct_loudness_blocks_after_tries`: monkeypatch `measure` to always return `ok=False`, call `correct_loudness(..., tries=1)`, assert `SystemExit` / non-ok and build does not continue.
- `test_no_editorial_by_lang`: import `build_final_reel`, assert `editorial_by_lang` is not imported or referenced by `main`.
- `test_loudness_single_target`: parse `core/core.json`, assert exactly one loudness target (-16 LUFS / -1 dBTP) and no -14 target.

PLAN-WRONG:
- Plan 1a says `editorial_by_lang.json` end-extension and duplicate totals (70.0/70.8/72.833 s) are replaced by `timeline_lock.json`; this slice still imports `editorial_by_lang`, loads `editorial_by_lang.json`, and derives `plan["total_duration_sec"]` from those lengths.
- Plan 1b says every consumer reads the contract and refuses a stale hash; this slice reads no `timeline_lock.json` and checks no hash.
- Plan 1c says voice files are `<id>.<lang>.wav` with RIFF/WAVE or ID3 header checks; this slice reads a single `vo_tracks_report.json` and performs no file-naming or header validation.
- Plan 1d says replace silent `CAPTION_FIXES` with explicit `spoken_text`/`caption_text` plus `caption_diff_approved: true`; this slice uses `text[ln["id"]]` and title-card fallback with no `caption_diff_approved` field.
- Plan 1e says add a test that fails if a second loudness target appears; this slice contains no such test and `correct_loudness` reads `audio["lufs"]`/`audio["loudnorm_tp_db"]` without asserting a single target.

NEED:
- `director/timeline_lock.py`
- `core/core.json`
- `gd.py` / `core/gd.py`
- `vo_tracks_report.json` schema

## merge-tree director/build_final_reel.py part 3/3
DEFECTS:
- `stop` is referenced in `return 1 if stop else 0` but is not defined or assigned within this slice; its value depends on omitted preceding code in `director/build_final_reel.py`.
- `e.get("loudness_ok")` is printed, but this slice shows no evidence that loudness is sourced solely from `core/core.json` or that a second target is rejected (plan 1e).
- No `timeline_lock.json` read or stale-hash refusal is visible in `build_final_reel` (plan 1b).
- `b["code"]`, `b["where"]`, `b["message"]` are accessed without evidence these keys exist on every `blocking_errors` entry.

CHANGES:
- `director/build_final_reel.py`, `main()`: before processing entities, load `timeline_lock.json`, recompute the sha256 of its declared inputs (text, voice files, clips), and `return 1` if the contract is missing or the hash mismatches (stale contract refusal).
- `director/build_final_reel.py`, `main()`: ensure `stop` is set true when any entity has `blocking_errors`; keep `return 1 if stop else 0` and `sys.exit(main())`.
- Add a test that fails if any loudness target other than `-16 LUFS / -1 dBTP` from `core/core.json` appears in the codebase (plan 1e).

TESTS:
- `test_build_final_reel_stale_contract_returns_1`: corrupt `timeline_lock.json` sha256; assert `main()` returns 1 before entity processing.
- `test_build_final_reel_ok_returns_0`: valid contract and no `blocking_errors`; assert `main()` returns 0.
- `test_loudness_single_target_in_core_json`: assert only `-16 LUFS` and `-1 dBTP` loudness targets exist and originate from `core/core.json`.

PLAN-WRONG:
none

NEED:
director/build_final_reel.py
core/core.json
render_controller.py

## h3/compile_h3_sing8.py part 1/2
DEFECTS:
- `_mouth_lock(dlg, silent=True)` in h3/compile_h3_sing8.py emits a single mouth-state rule for the whole shot; plan 2b requires per-character mouth state when more than one person is on screen, and no per-character branching exists.
- No auto line `Only [cast] appear in this shot; no extra figures or creatures.` is emitted in `_fl2va`, `_ref2va`, or `compile_fl2va_prompt`; plan 2b requires it.
- `compiled_soundscape(shot, registry)` is emitted in `_fl2va` and `_ref2va` with no filter or refusal for creature/object nouns in audio cues; plan 2b bans them.
- `_fl2va` and `_ref2va` index `shot["dialogue_and_lip_lock"]` directly; a missing key raises KeyError instead of degrading to a silent mouth lock.
- `_fl2va` divides `pf / fps` with no guard for `fps == 0` or missing `timing_and_lattice.pixel_frames` (ZeroDivisionError / KeyError).
- `_ref2va` indexes `chars[cid]` for `cid` in `inv["audio"]` without confirming `cid` exists in `chars`; KeyError on unknown audio-bound character.
- Direct indexing on `shot["motion_7_stage"]`, `shot["timing_and_lattice"]`, `shot["sound_plan"]`, `shot["camera"]`, `shot["anime_timing_cadence"]` can crash the compiler on missing keys.

CHANGES:
- In h3/compile_h3_sing8.py, change `_mouth_lock(dlg, silent=True)` to `_mouth_lock(dlg, registry, on_screen_ids, silent=True)`: when `len(on_screen_ids) > 1`, return `" ".join(f"{clean_text(registry['characters'][cid]['short_disambiguator'])}: {clean_text(dlg.get('mouth_state_rule', ''))}" for cid in on_screen_ids)`; otherwise return the current single-rule string. Update both call sites in `_fl2va` and `_ref2va` to pass `registry` and `shot["continuity_and_seam_lock"]["subjects_present"]`.
- Add `_auto_cast_line(shot, registry)` returning `f"Only {', '.join(clean_text(registry['characters'][cid]['short_disambiguator']) for cid in shot['continuity_and_seam_lock']['subjects_present'])} appear in this shot; no extra figures or creatures."` and append it to the body `san(" ".join([...]))` in both `_fl2va` and `_ref2va`.
- Before emitting `overall_soundscape` in `_fl2va` and `_ref2va`, reject `snd` if it contains any banned creature/object noun (raise `ValueError("creature/object noun in audio cue")`); define or import the ban list in this module.
- Replace direct `shot["dialogue_and_lip_lock"]` indexing with `dlg = shot.get("dialogue_and_lip_lock") or {}` and guard `_mouth_lock` against missing `mouth_state_rule`.
- In `_fl2va`, validate `fps` and `pixel_frames`: `if not fps: raise ValueError("execution_profile.fps is zero")`; `pf = shot["timing_and_lattice"].get("pixel_frames")`; if `pf` is None raise `ValueError("shot missing pixel_frames")`.
- In `_ref2va`, before `chars[cid]`, add `if cid not in chars: raise ValueError(f"audio reference {cid!r} not in registry characters")`.

TESTS:
- `test_mouth_lock_per_character_two_people`: shot with two `subjects_present`; assert compiled prompt contains the mouth rule prefixed by each character's short disambiguator.
- `test_auto_cast_line_emitted`: shot with one subject; assert prompt contains `Only <disambiguator> appear in this shot; no extra figures or creatures.`
- `test_creature_noun_in_soundscape_refused`: `compiled_soundscape` returns text containing a banned creature noun; assert `compile_fl2va_prompt` raises ValueError.
- `test_zero_fps_guarded`: `execution_profile.fps = 0`; assert ValueError, not ZeroDivisionError.
- `test_unknown_audio_character`: ref2va route with `inv["audio"]` cid absent from `registry.characters`; assert ValueError.
- `test_missing_dialogue_and_lip_lock`: shot without `dialogue_and_lip_lock`; assert prompt compiles without KeyError and uses silent mouth lock.

PLAN-WRONG:
- Plan 2b says "no 'with <cue>' glue"; `_speech_sentences` still joins `cue` and `line` via `f"{cue} {line}".strip()`. If the plan forbids all cue glue, this contradicts it; if it only bans the literal word "with", the code is compliant.
- Plan 2c targets `build_h3_batch.py` and `image_prompt_type` "SE"/"S"; this slice is `compile_h3_sing8.py` and contains no batch or image_prompt_type logic, so plan 2c cannot be verified from this code.

NEED:
- h3/schema_and_linter.py (to confirm `compiled_soundscape` shape, `clean_text`, `san`, `MOUTH_LOCK_SENTENCE`, and whether the creature/object ban already exists there)
- build_h3_batch.py (to verify the sing8/pika6 path does not force both frames per plan 2c)

## h3/compile_h3_sing8.py part 2/2
DEFECTS:
- `compile_comfyui_workflow`: `k` is undefined in this scope; line `kf = keyframes or {"picture_1": k.get("picture_1_path"), "picture_2": k.get("picture_2_path")}` raises `NameError` when `keyframes` is falsy.
- `compile_comfyui_workflow`: `t` is referenced at `length=t["pixel_frames"], expected_latent_slots=t["latent_slots"]` but not defined in this slice; potential `NameError` if not defined in part 1/2.
- `compile_comfyui_workflow`: node `5` (`MiniMaxH3ImageToVideo`) unconditionally passes both `first_frame` and `last_frame`; plan 2c requires per-shot `image_prompt_type` "S" to omit `image_end`, and the sing8/pika6 path must not force both frames.
- `compile_episode`: `lint_story(...)` runs before `resolve_keyframes(...)`, so Phase B checks (PNG size, watermark residue, image codes KF-06, PR-00) cannot run after keyframes exist as required by plan 2a; no Phase B invocation appears after keyframe resolution.
- `compile_fl2va_prompt` is called but the slice shows none of the plan 2b compiler fixes: blank-line collapse, no "with <cue>" glue, no duplicate sentence, per-character mouth state for multi-person shots, creature/object noun ban in audio cues, or the auto line `Only [cast] appear in this shot; no extra figures or creatures.`

CHANGES:
- `compile_comfyui_workflow`: replace `k.get("picture_1_path")` / `k.get("picture_2_path")` with `shot.get("picture_1_path")` / `shot.get("picture_2_path")` on the `kf` fallback line.
- `compile_comfyui_workflow`: read `image_prompt_type = shot.get("image_prompt_type", "SE")`; node 5 always sets `first_frame=kf["picture_1"]`; set `last_frame=kf["picture_2"]` only when `image_prompt_type == "SE"`; keep default "SE" and do not activate "S" pending owner approval of the SHOT-008 A/B test.
- `compile_episode`: insert Phase B lint (PNG size, watermark residue, image codes KF-06, PR-00) immediately after `kf = resolve_keyframes(...)` and before `compile_comfyui_workflow`/file writes; raise `ValueError` on errors.
- `compile_fl2va_prompt`: collapse blank lines; strip "with <cue>" glue; drop duplicate sentences; emit per-character mouth state when cast > 1; reject creature/object nouns in audio cues; append `Only [cast] appear in this shot; no extra figures or creatures.`

TESTS:
- `test_workflow_keyframes_fallback_no_name_error`: invoke `compile_comfyui_workflow` with `keyframes=None`; assert no `NameError` and node 5 `first_frame` comes from `shot`.
- `test_image_prompt_type_S_omits_last_frame`: invoke with `shot["image_prompt_type"]="S"`; assert node 5 inputs lack `last_frame`; with default assert `last_frame` is present.
- `test_episode_phase_b_after_keyframes`: run `compile_episode` on a shot with an invalid keyframe PNG size/watermark/image code; assert `ValueError` is raised after keyframe resolution and no `workflow.json` is written.
- `test_fl2va_prompt_plan_2b`: compile a multi-cast shot containing a creature noun, duplicate sentence, and "with <cue>" glue; assert output has no blank lines, no glue, no duplicate, per-character mouth lines, no creature nouns, and ends with the auto cast line.

PLAN-WRONG:
- none

NEED:
- h3/compile_h3_sing8.py part 1/2
- director/h3_director.py
- build_h3_batch.py

## director/build_h3_batch.py part 1/2
DEFECTS:
- `legacy_rows`: every row unconditionally sets `"start": f"keyframes/{sid}-A.png"` and `"end": f"keyframes/{sid}-B.png"` and never emits `image_prompt_type`; plan 2c requires per-shot "SE"/"S" where "S" omits `image_end`.
- `legacy_rows`: `frames = sh["timing_and_lattice"]["pixel_frames"]` is used as `render_frames` with no check that `(frames - 5) % 17 == 0` (H3 length 17n+5 from plan header).
- `jpg_embedder`: docstring says `images` stores base64 JPEG under `.jpg`, but the body populates via `run_kaggle.png_b64(Path(root) / rel)`; PNG bytes under a `.jpg` name may fail VM extension-based decoding.
- `harden`: inserted `helper` calls `time.sleep(30 * n)` and uses `note`/`OUT` without importing `time` or defining `note`/`OUT` in the snippet.
- `split_blobs`: `BLOB_RE = re.compile(r'b64decode\("([A-Za-z0-9+/=]{100000,})"\)')` matches only double-quoted literals; single-quoted `b64decode('...')` blobs remain inline.

CHANGES:
- `legacy_rows`: set `mode = sh.get("image_prompt_type", "SE")`; add `"image_prompt_type": mode` to the row dict; include `"end": f"keyframes/{sid}-B.png"` only when `mode == "SE"`; omit `"end"` when `mode == "S"` (no CLI switch for "S"; stays off pending owner A/B approval on SHOT-008).
- `legacy_rows`: after `frames = sh["timing_and_lattice"]["pixel_frames"]`, insert `if (frames - 5) % 17 != 0: raise ValueError(f"{sid}: render_frames {frames} is not H3 length 17n+5")`.
- `jpg_embedder`: replace `run_kaggle.png_b64(Path(root) / rel)` with `jpeg_b64(Path(root) / rel)`.
- `harden`: prepend `import time\n` to the `helper` string (ensure `note` and `OUT` are globals in the patched script or pass them in).

TESTS:
- `test_legacy_rows_default_se`: one-shot story; assert row has `image_prompt_type == "SE"` and both `start` and `end` keys.
- `test_legacy_rows_s_omits_end`: shot with `"image_prompt_type": "S"`; assert row has `image_prompt_type == "S"` and `"end" not in row`.
- `test_legacy_rows_rejects_bad_frames`: shot with `pixel_frames = 100`; assert `ValueError` raised mentioning 17n+5.
- `test_jpg_embedder_uses_jpeg`: monkeypatch `run_kaggle.png_b64` to raise and `jpeg_b64` to return a sentinel; assert `embed` returns the sentinel path.
- `test_split_blobs_moves_large_literal`: script containing a 150k-char `b64decode("...")`; assert rewritten script uses `b64decode(open("/content/_blob0.txt").read())` and `upload_00.py` is written.

PLAN-WRONG:
- Plan 2c states the sing8/pika6 batch path must not force both frames and must support per-shot "S" (`image_end` absent); `legacy_rows` unconditionally writes both `start` and `end` and lacks `image_prompt_type`, contradicting that requirement.

NEED:
- `director/h3_director.py`
- `run_kaggle.py`
- `h3/compile_h3_sing8.py`

## director/build_h3_batch.py part 2/2
DEFECTS:
- `wheel` and `sha` are used in the wheel-upload function body but their bindings are not visible in this slice (enclosing `def` not shown); `Path(wheel).read_bytes()` and `!= sha` can raise `NameError`.
- `main` contains no per-shot `image_prompt_type` ("SE"/"S") handling; plan 2c requires default "SE", start-only "S", owner-gated "S" for SHOT-008, and verification that sing8/pika6 does not force both frames.
- `run_kaggle.build(..., "colab", ...)` is called unconditionally; plan header bars Colab/paid calls without owner and the slice shows no owner gate before this argument.
- `manifest["embed_mb_total"]` is read in the final print with no guarantee `run_kaggle.build` populated it; risk of `KeyError`.
- `write_wheel_upload(folder)` is called but not defined in this slice; cannot confirm it writes the vendored wheel from `D:/aai work/vendor/chumpy_0.71` with the verified sha256.

CHANGES:
- In the wheel-upload function (enclosing the `upload_wheel.py` docstring), add explicit parameters `wheel: str` and `sha: str`, or bind `sha` to the verified hash of `D:/aai work/vendor/chumpy_0.71`, so `Path(wheel).read_bytes()` and `!= sha` are defined.
- In `main`, after `rows = legacy_rows(...)`, set `row["image_prompt_type"] = "SE"` when both start and end frames are present, otherwise `"S"`; allow `"S"` only when an owner-approved SHOT-008 A/B flag is true; pass `rows` to `run_kaggle.build` so the sing8/pika6 path never requires `image_end` when type is `"S"`.
- Before `run_kaggle.build(..., "colab", ...)`, insert a guard that raises `RuntimeError` if the destination is `"colab"` and owner approval is absent.
- Replace `manifest["embed_mb_total"]` with `manifest.get("embed_mb_total", 0)` in the print, or require `run_kaggle.build` to set `manifest["embed_mb_total"]` before returning.

TESTS:
- `test_wheel_upload_rejects_bad_sha`: call the wheel-upload function with a tampered wheel; asserts `ValueError` raised and message contains "sha256 differs".
- `test_image_prompt_type_default_SE`: run `legacy_rows` on a shot with start+end frames; asserts every row has `image_prompt_type == "SE"`.
- `test_image_prompt_type_S_blocked_without_owner`: run with a start-only shot and no owner approval; asserts `image_prompt_type != "S"` or `main` raises/refuses.
- `test_colab_route_owner_gate`: call `main` targeting `"colab"` without owner approval; asserts `RuntimeError` before `run_kaggle.build` is invoked.
- `test_manifest_embed_mb_total_present`: after `run_kaggle.build`, asserts `"embed_mb_total" in manifest`.

PLAN-WRONG:
- Plan header forbids Colab/paid calls without owner, but `main` unconditionally passes `"colab"` to `run_kaggle.build` with no owner gate; if `build` executes a Colab/paid call, this contradicts the plan.

NEED:
- `director/h3_director.py` (around line 346) to confirm start/end string building and sing8/pika6 frame forcing.
- `run_kaggle.py` (module containing `run_kaggle.build`) to confirm `"colab"` argument is offline-only and the `manifest` contract.
- `director/build_h3_batch.py` part 1/2 for `legacy_rows`, `write_wheel_upload`, and the `wheel`/`sha` bindings.

## director/run_colab_batch.py part 1/2
DEFECTS:
- run_cli: `stdin=None if stdin is not None else subprocess.DEVNULL` with `input=stdin` never delivers stdin (input is ignored unless stdin=PIPE); the HF token one-liner in `batch` is not sent to the VM.
- run_cli: prints `$ colab ` + `" ".join(args)` without quoting paths; plan requires all paths quoted because file names contain spaces.
- batch: `MAX_BATCH_SECONDS = 3 * 3600` is a fixed wall-clock cap; plan requires a dead-man timer sized from the batch estimate x 1.5, not fixed.
- batch: `hardware(name)` is called immediately after `colab new`; if the session is not yet listed it returns None and the code raises "stopping it" but never calls `colab stop`.
- batch: `fetch` raises `RunError` when any file fails; plan requires keeping the session and printing the stop command, not raising.
- fetch_ready: `files` keeps the `ls -s` size prefix, so `dst = results / sid / f` targets a path that includes the block size (e.g. `4096 clip.mp4`).
- batch: no visible try/finally that stops the session only when every clip is verified on disk; `keep = False` is never set or used in this slice.
- Missing from slice: SHOT-001 one-shot proof gate before shots 2..N; chumpy wheel sha256 hash test; runner writing setup log tail into timeline.txt.

CHANGES:
- run_colab_batch.py: add `import shlex`; change run_cli print to `print("$ colab " + " ".join(shlex.quote(a) for a in args), flush=True)`.
- run_colab_batch.py: change run_cli subprocess `stdin` argument to `stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL` so `input=stdin` is delivered.
- run_colab_batch.py `batch`: replace `max_seconds=MAX_BATCH_SECONDS` with `batch_estimate_seconds: int`; compute `deadman_seconds = int(batch_estimate_seconds * 1.5)` and use it as the wall-clock cap; remove fixed `MAX_BATCH_SECONDS` usage.
- run_colab_batch.py `batch`: after `got_hw != gpu`, add `run_cli(["stop", "-s", name], check=False)` before `raise RunError(...)`; retry `hardware(name)` briefly after `new` before treating None as a mismatch.
- run_colab_batch.py `fetch`: replace `if failed: raise RunError(...)` with printing `STOP SESSION: colab stop -s <name>` and returning the failed list (session stays up).
- run_colab_batch.py `fetch_ready`: change `files = [x.strip() for x in listing.splitlines() if x.strip().lower().endswith(".mp4")]` to `files = [line.split()[-1] for line in listing.splitlines() if line.strip().lower().endswith(".mp4")]`.
- run_colab_batch.py `batch`: add `try/finally` around the run; in `finally`, stop the session only when every expected clip is verified under `results`, otherwise print `colab stop -s <name>` and leave the session running.
- run_colab_batch.py: add SHOT-001 preflight gate (require SHOT-001 in `got` before shots 2..N) and a chumpy wheel hash test function comparing `D:/aai work/vendor/chumpy_0.71` sha256 to the value in `build_h3_batch.py`.

TESTS:
- test_run_cli_stdin_delivered: mock subprocess.run; call run_cli(["exec","-s","s"], stdin="x"); assert subprocess.run received stdin=subprocess.PIPE and input="x".
- test_run_cli_log_quotes_spaces: capture print; call run_cli(["download","-s","s","a b.mp4","out"]); assert printed command contains `"a b.mp4"`.
- test_batch_wrong_gpu_stops_session: mock hardware to return "K80"; call batch; assert run_cli called with ["stop","-s",name] and RunError raised.
- test_fetch_failed_keeps_session: mock one download to fail; call fetch; assert no exception, stop command printed, failed list returned.
- test_fetch_ready_strips_ls_size: mock run_cli to return "4096 clip one.mp4"; call fetch_ready; assert download destination is results/sid/clip one.mp4.
- test_deadman_is_estimate_times_1_5: call batch with batch_estimate_seconds=100; assert internal cap == 150.
- test_chumpy_hash_matches: hash D:/aai work/vendor/chumpy_0.71; assert equals sha256 recorded in build_h3_batch.py.
- test_shot001_gate: mock got without SHOT-001; call batch; assert it refuses to start shots 2..N.

PLAN-WRONG:
- Plan says keep session and alert on failed download; code `fetch` raises and has no keep-session path.
- Plan says dead-man timer = batch estimate x 1.5, not fixed; code uses fixed `MAX_BATCH_SECONDS = 3 * 3600`.
- Plan says quote all paths; code prints unquoted CLI commands and `fetch_ready` builds paths from unparsed `ls -s` lines.
- Plan says SHOT-001 proof before shots 2..N; code has no such gate.
- Plan says chumpy wheel hash test; code has no such test.

NEED:
- director/run_colab_batch.py part 2/2
- director/t0_pack/run_t0_colab.py
- build_h3_batch.py

## director/run_colab_batch.py part 2/2
DEFECTS:
- `keep = False` is assigned unconditionally after `fetch(...)`, so `finally` always runs `colab stop` even when `rc != 0` or not every clip is verified on disk; violates "stops the session ... ONLY when every clip is verified on disk (otherwise keep the session, alert)". Cite: `keep = False` and `run_cli(["stop", "-s", name], check=False)`.
- `got` is populated but never compared against an expected clip list or `FILES.txt`; no verification that every clip is on disk before releasing the session. Cite: `got, end = set(), ...` and `fetch_ready(name, Path(results), got)`.
- Dead-man timer uses `max_seconds` (fixed) instead of batch estimate × 1.5; plan forbids a fixed 90 min timer. Cite: `end = clock() + max_seconds`.
- `script_finished(...)` result is compared with `done == 0`; if it returns `True`/`None` the ALL DONE vs FAILED branch misfires. Cite: `done = script_finished(...)` and `{'ALL DONE' if done == 0 else 'FAILED'}`.
- `clock()` is used without import shown in this slice; if it is `time.clock` it is deprecated/removed on Python 3.8+. Cite: `clock() + max_seconds` and `clock() > end`.
- No writes to `anime_studio/PROJECT_LOG.md`; constraint requires logging every step there. Cite: `print(...)` throughout `batch` and `main`.
- `run_cli(["stop", "-s", name], check=False)` silently ignores stop failures; no alert when the session cannot be stopped. Cite: `finally` block.
- `run_cli(["exec", "-s", name], stdin=t0.LIST_CODE)` and `fetch(...)` run before the `rc` check, so on failure the session is still stopped (because `keep` is already False) instead of kept for debugging. Cite: sequence between loop and `if rc: raise`.

CHANGES:
- `batch()`: add parameter `batch_estimate_seconds`; replace `end = clock() + max_seconds` with `end = clock() + batch_estimate_seconds * 1.5`.
- `batch()`: after `fetch(name, Path(results))`, read `results / "FILES.txt"`; require every listed path to exist locally with size > 0. If any missing, leave `keep = True`, print alert with `colab stop -s {name}`, and skip `run_cli(["stop", ...])`.
- `batch()`: move `keep = False` to only after full on-disk verification succeeds; if `rc != 0` or verification fails, keep `keep = True`.
- `batch()`: normalize `script_finished` output: `rc = 0 if done in (0, True) else (done if isinstance(done, int) else 1)`.
- `finally`: call `run_cli(["stop", "-s", name], check=False)` only when `keep` is False; when `keep` is True, print the kept-session alert and do not stop.
- `batch()`/`main()`: add `LOG_PATH = HERE.parent / "anime_studio" / "PROJECT_LOG.md"`; replace `print(..., flush=True)` in `batch` with a helper that appends the message to `LOG_PATH` and prints.

TESTS:
- `test_batch_keeps_session_when_clip_missing`: mock `run_cli`, `fetch`, `fetch_ready`, `script_finished` → 0; make one `FILES.txt` entry missing locally; assert `run_cli(["stop", ...])` is not called and "SESSION KEPT" is printed.
- `test_batch_deadman_is_estimate_times_1_5`: call `batch` with `batch_estimate_seconds=100`; assert wait deadline equals start + 150 s, not a fixed 5400 s.
- `test_batch_script_finished_bool_true_means_done`: mock `script_finished` → `True`; assert loop breaks with `rc == 0` and prints ALL DONE.
- `test_batch_logs_to_project_log`: mock `LOG_PATH`; assert `anime_studio/PROJECT_LOG.md` contains batch start and stop/kept lines.

PLAN-WRONG:
- Plan: "stops the session in try/finally ONLY when every clip is verified on disk (otherwise keep the session, alert)" — code stops unconditionally via `keep = False` + `finally` stop.
- Plan: "VM dead-man timer sized from the batch estimate x 1.5 (not a fixed 90 min)" — code uses `max_seconds` fixed.
- Constraint: "Log every step to anime_studio/PROJECT_LOG.md" — code only prints to stdout.

NEED:
director/run_colab_batch.py part 1/2
anime_studio/PROJECT_LOG.md
