Real defects found:

1. **`ffconcat_text` emits an invalid list when `entries` is empty.**  
   `tools/animatic.py:63` — `entries[-1][0]` raises `IndexError` for an empty list, which is a crash path. The card requires A/B stills → one MP4; zero shots is an input that crashes instead of being rejected.  
   Fix: raise a clear error early, e.g.:
   ```python
   if not entries:
       raise ValueError("at least one shot entry is required")
   ```

2. **`shots_to_entries` does not validate that `a` is present.**  
   `tools/animatic.py:27` — `s["a"]` raises `KeyError` (crash) if a shot dict omits the `"a"` key. The card implies every shot has an A still.  
   Fix: add a check before use, e.g.:
   ```python
   if not s.get("a"):
       raise ValueError("%s: 'a' still is required" % s.get("shot_id"))
   ```

3. **`test_concat_list_repeats_last_still_and_escapes_quotes` is tautological.**  
   `tools/test_animatic.py:31` — it calls `a.ffconcat_text(...)` and asserts the result equals the exact string that `ffconcat_text` itself produces. The test cannot fail if the implementation changes its own formatting.  
   Fix: assert semantic properties instead (e.g. every `file` line appears, the last path is repeated, single quotes are escaped) or compare against a hand-written expected literal.

4. **`test_command_is_24fps_h264_and_takes_guide_audio` does not cover `-map` / `-c:a` / `-shortest` behavior.**  
   The test name claims coverage of guide audio, but it only checks `-shortest` is present and `-i` count; it never verifies `-map 0:v -map 1:a -c:a aac` are actually in the command.  
   Fix: add assertions for those flags, e.g. `assert "-map" in cmd and cmd[cmd.index("-map")+1] == "0:v"` etc.

5. **`test_one_mp4_per_language` does not cover the card’s “per language” requirement for different guides.**  
   The test passes `None` for both languages; it never checks that a provided `guide` is forwarded to `build_command`. The card explicitly says “a guide track → MP4 per language”.  
   Fix: add a test that supplies distinct guides and asserts each language’s command includes the correct guide path (e.g. via `_fake_run.calls` inspection).

VERDICT: FIX-FIRST