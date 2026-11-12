**Defect 1 — Card requirement not met: voice lock missing.**  
Faulty line: `def make_animatic(entries, out, guide=None, runner=subprocess.run):` (same omission in `build_command(list_path, guide, out, fps=FPS)` and `make_all(entries_by_lang, out_dir, guides=None, runner=subprocess.run)`).  
Why: M-18 requires “A/B stills + the voice lock + a guide track” as inputs. The tool accepts only `guide`; there is no voice-lock parameter, no voice-lock input, and no mapping of it into the MP4. The owner cannot gate a voice-locked animatic.  
Fix: Add `voice_lock=None` to `make_animatic`, `build_command`, and `make_all` (as `voice_locks=None`), thread it through, and in `build_command` append `-i <voice_lock>` and map its audio stream when present. Exact `build_command` patch:  
```
def build_command(list_path, guide, out, voice_lock=None, fps=FPS):
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(list_path)]
    if guide:
        cmd += ["-i", str(guide)]
    if voice_lock:
        cmd += ["-i", str(voice_lock)]
    cmd += ["-r", str(fps), "-c:v", "libx264", "-pix_fmt", "yuv420p"]
    if guide or voice_lock:
        cmd += ["-map", "0:v"]
        if guide:
            cmd += ["-map", "1:a"]
        if voice_lock:
            cmd += ["-map", "%d:a" % (2 if guide else 1)]
        cmd += ["-c:a", "aac", "-shortest"]
    cmd.append(str(out))
    return cmd
```

**Defect 2 — Wrong result: delivery loudness not enforced (-14 LUFS).**  
Faulty line: `cmd += ["-map", "0:v", "-map", "1:a", "-c:a", "aac", "-shortest"]` in `build_command`.  
Why: core/core.json owner decision of 2026-11-11 sets delivery loudness to -14 LUFS (superseding -16). The command muxes guide/voice audio with no loudness normalization, so any loudness passes silently into the delivery MP4.  
Fix: Insert an audio loudnorm filter targeting -14 LUFS integrated loudness. Exact fix: replace that line with  
```
cmd += ["-map", "0:v", "-map", "1:a", "-af", "loudnorm=I=-14", "-c:a", "aac", "-shortest"]
```
(Adjust the `-map 1:a` input index if voice_lock is added per Defect 1.)

**Defect 3 — Crash path: empty entries list.**  
Faulty line: `lines.append("file '%s'" % _esc(entries[-1][0]))` in `ffconcat_text`.  
Why: `check_entries` does not reject an empty list, so `make_animatic([], ...)` reaches `entries[-1]` and raises `IndexError` instead of a clear validation error.  
Fix: Guard `check_entries` against empty input. Exact fix: insert at the top of `check_entries`:  
```
if not entries:
    raise ValueError("entries must not be empty")
```

**Defect 4 — Wrong result: ffconcat_text repeats the last still without duration.**  
Faulty line: `lines.append("file '%s'" % _esc(entries[-1][0]))` in `ffconcat_text`.  
Why: The concat demuxer does not need a trailing file without duration. Repeating the last still creates an extra segment whose duration is unset; the image2 demuxer assigns a default frame time (~0.04 s), so the animatic ends with a spurious near-instant duplicate of the last still.  
Fix: Remove the trailing repeated `file` line. Exact fix: delete those two lines from `ffconcat_text` so the function returns `"\n".join(lines) + "\n"` after the loop.

**Defect 5 — Test asserts the bug and cannot catch it.**  
Faulty line: `assert text == "file 'a.png'\nduration 2.000\nfile 'it'\\''s.png'\nduration 1.500\nfile 'it'\\''s.png'\n"` in `test_concat_list_repeats_last_still_and_escapes_quotes`.  
Why: It encodes Defect 4 as expected output, so the test passes while the ffconcat file is wrong. It does not cover correct concat behavior.  
Fix: Change the expected string to omit the repeated last file:  
```
assert text == "file 'a.png'\nduration 2.000\nfile 'it'\\''s.png'\nduration 1.500\n"
```

VERDICT: FIX-FIRST