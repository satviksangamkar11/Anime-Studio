**Defect found:**

In `test_three_consumers_same_offsets`, the assertion is tautological and does not actually test that the cue sheet's `start_s` values equal the lock-derived offsets. The code builds `gate_d_offsets` by iterating over `seen["shots"]` (which were passed to the mocked `plan_language_outputs`) and accumulating `editorial_duration_sec`. Then it builds `cue_starts` from `cs.build_locked_cue_sheet`. However, the assertion:

```python
assert final_offsets == gate_d_offsets == cue_starts == [0.0, 7.0, 12.0], lang
```

is evaluated **inside** a loop over `LANGS`, but `final_offsets`, `gate_d_offsets`, and `cue_starts` are computed **once** before the loop and are not language-specific. More critically, the `lang` variable in the error message is misleading — it implies per-language variation where there is none. But the real issue is that `gate_d_offsets` is derived from `seen["shots"]`, which is populated by the spy function that is called inside `rc._gate_d_result`. That call happens **before** the loop, so `seen["shots"]` is fixed. The problem is that `gate_d_offsets` is constructed by manually summing `editorial_duration_sec` from the shots — but these shots are the same objects that were passed to the spy, which in turn were derived from the story, which was derived from the lock. So this is not a tautology per se, but it is **not independent**: it does not verify that `rc._gate_d_result` *uses* the lock to compute offsets; it only verifies that the shots it received have certain durations. The test does not check that `rc._gate_d_result` *computed* the offsets from the lock — it just assumes that the shots it passed in had the right durations.

But the **real defect** is elsewhere.

Look at this line in `test_three_consumers_same_offsets`:

```python
report, _problems = bvt.build(str(reel.pack), str(reel.raw), str(tmp_path / "vo3"), list(LANGS),
                              lock=str(reel.lock_path))
```

This is called **after** `rc._gate_d_result` is invoked. But `rc._gate_d_result` is supposed to be the Gate D consumer of the lock. However, the test does not verify that `rc._gate_d_result` actually *read* the lock. It monkeypatches `rc.plan_language_outputs` with a spy, but `rc._gate_d_result` may not even call `plan_language_outputs` — or it may call it with shots that are not derived from the lock. The test assumes that `seen["shots"]` are the shots from the story, but it does not verify that `rc._gate_d_result` *used the lock* to construct them. In fact, the story is built via `_story(reel)`, which does use the lock, so the shots *are* lock-derived. But the test does not assert that `rc._gate_d_result` *itself* reads the lock — it only asserts that the shots it received had certain durations. This is weak but not a failure.

**The actual defect is in `test_same_gate_d_verdict`:**

```python
direct = gd.plan_language_outputs(ep["episode_id"], list(LANGS), str(tmp_path / "out" / ep["episode_id"] / "audio"
                                                                    / "vo"),
                                  None, shots=shots, video_path=str(tmp_path / "v.mp4"), video_has_audio=True,
                                  captions_dir=str(tmp_path / "c"), export_dir=str(tmp_path / "e"),
                                  story_gate_checks=story["registry"]["story_gate_checks"],
                                  voice_engines=story["registry"].get("voice_engine"))
```

Here, `shots` is constructed as:

```python
shots = [dict(s, editorial_duration_sec=lock_sec[s["shot_id"]]) for s in ep["shots"]]
```

But `ep["shots"]` are the shots from the story, which already have `editorial_duration_sec` set (from the lock). This line **overwrites** it with the same value from `lock_sec`, which is derived from `tli.lock_rows(reel.lock)`. So it's redundant but not wrong.

However, the critical issue is that `gd.plan_language_outputs` is called with `video_path=str(tmp_path / "v.mp4")` and `video_has_audio=True`, but **no actual video file exists at that path**. The function `gd.plan_language_outputs` likely tries to probe the video (e.g., with ffprobe) to get duration, audio streams, etc. If it does, it will crash or return errors because the file doesn't exist. The test does not create `tmp_path / "v.mp4"`. This is a **crash path** or a **silent failure** if the function handles missing files gracefully.

But the test expects `direct["reports"][lg]["errors"]` to be empty or to match `via_controller["reasons"]`. If `plan_language_outputs` fails because the video file is missing, it will return errors like "video file not found" or similar, which will not match `via_controller["reasons"]` (which may be empty or have different errors). This will cause the test to fail **intermittently** or **always** if the function is strict.

**This is a real defect: the test does not provide a valid video file for `gd.plan_language_outputs`, which may require it.**

Fix: create a minimal valid video file at `tmp_path / "v.mp4"` before calling `gd.plan_language_outputs`.

Example fix:

```python
video_path = tmp_path / "v.mp4"
_make_clip(video_path, seconds=20.0)  # or whatever duration is needed
direct = gd.plan_language_outputs(..., video_path=str(video_path), ...)
```

Alternatively, if `plan_language_outputs` can accept `None` or a dummy, ensure it does not require a real file. But since the test is end-to-end, it should provide a real file.

VERDICT: FIX-FIRST