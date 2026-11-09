# Review: score/gate_d_bridge.py (agent GBR, 2026-11-09)

Scope: score/gate_d_bridge.py, score/tests/test_gate_d_bridge.py against checklist section B1-B7
(research/SCORE_BUILD_CHECKLIST_STRICT_2026-11-09.md), score-reel SKILL.md rules 2 and 11, and
h3/gate_d_audio.py (validate_bgm_manifest, check_music_presence, _bgm_track, BGM_DUCK, BGM_PRESENCE).
Read only. Probes ran from throwaway snippets with stdin (no files saved in the repo); float WAVs written to the scratchpad.

Test run: `python -m pytest score/tests/test_gate_d_bridge.py -q` gave `35 passed in 8.68s`.

## Summary

| id | severity | title |
|----|----------|-------|
| GBR-1 | HIGH | NaN or inf samples in a float stem pass every check and the manifest is written |
| GBR-2 | MED | Anti-phase bass with an exactly zero mid skips the bass check (test passes for the wrong reason) |
| GBR-3 | LOW | Single-channel stem with no bass is labelled STEM_BASS_NOT_MONO |
| GBR-4 | LOW | presence_levels raises on NaN or inf win_s (contract says never raise) |
| GBR-5 | LOW | Length tolerance boundary (2001 samples) not tested |

Counts: HIGH 1, MED 1, LOW 3.

Checklist items B1-B7 are implemented. Stdlib and numpy checks: no third-party imports in the bridge; the project
modules that gate_d_audio imports use stdlib only. Subprocess calls use argument lists (no shell, no -I issue), and
paths are passed through str(), so no backslash breakage was found. Length tolerance (exactly 2000 passes, 2001 fails),
mono fold maths (10 log10 of power ratio, phase-cancelled = inf), LUFS parsing (last match wins), and NaN cue sheets
(STEM_CUE_INVALID) were checked and are correct.

---

## GBR-1 (HIGH): NaN or inf samples in a float stem pass every check

- File: score/gate_d_bridge.py:161 (`np.any(stereo)` is True for NaN), 113-117 (`_bass_side_db`: NaN compares False
  against the -20 dB limit), 125-129 (`_mono_loss_db`: NaN compares False against the 3 dB limit).
- What is wrong: NaN makes every comparison false, so the bass and mono checks never fire. `write_bgm_manifest` then
  writes the manifest, which is the one thing the bridge must never do for a bad stem (the module docstring says a
  bad stem can never reach Gate D). No finite check exists anywhere in check_score_stem.
- Reproduction (stdin snippet, scratchpad path):
  ```
  python - <<'EOF'
  import sys, os
  sys.path.insert(0, ".")
  from score.tests.test_gate_d_bridge import _write, _stereo, _tone, _cue
  from score import gate_d_bridge as gb
  S = r"C:\Users\Satvik\AppData\Local\Temp\claude\34bc6e8cd9f62db3\f5adc626-6aab-44f4-8ef5-3a984a22d83e\scratchpad"
  z = _tone(16, 440, 0.3); z[1000] = float("nan")
  p = _write(os.path.join(S, "C.wav"), _stereo(z), codec="pcm_f32le")
  rep = gb.write_bgm_manifest(p, _cue(), os.path.join(S, "nan_manifest", "bgm.json"), bpm=128, lufs=-18.5)
  print("ok=", rep["ok"], "errors=", rep["errors"], "manifest_exists=", os.path.exists(os.path.join(S, "nan_manifest", "bgm.json")))
  EOF
  ```
  Output: `ok= True errors= [] manifest_exists= True`. A check_score_stem call on the same file (and on an inf
  sample) gives `codes=[]`, with `side=nan loss=nan`. The RuntimeWarning from numpy is printed and ignored.
- Fix: after decoding, add `if not np.all(np.isfinite(stereo))` and return an error (for example STEM_UNREADABLE or a
  new STEM_NONFINITE) before the silence and bass checks. Add a test with a pcm_f32le stem holding one NaN and one
  inf; it must fail and must not write a manifest.

## GBR-2 (MED): anti-phase bass with an exactly zero mid skips the bass check

- File: score/gate_d_bridge.py:113-114 (`if mid_p <= 0.0: return None`). The caller at line 166 then skips the check.
- What is wrong: when the stem is exactly out of phase (R = -L), the mid is exactly zero, so the function returns None
  ("no bass") even though side bass is loud. A 24-bit WAV hides this because rounding leaves a tiny mid residue; a
  float WAV does not. The check then reports nothing for STEM_BASS_NOT_MONO. The stem still fails, but only with
  STEM_MONO_LOSS, so the B2 code never fires for the exact case the checklist names.
- Test weakness: test_bass_out_of_phase_fails (score/tests/test_gate_d_bridge.py:131-134) passes only because the
  24-bit residue gives side 130 dB over mid (the test passes for the wrong reason). No float-WAV version exists.
- Reproduction:
  ```
  python - <<'EOF'
  import sys, os
  sys.path.insert(0, ".")
  from score.tests.test_gate_d_bridge import _write, _stereo, _tone, _cue, _codes
  from score import gate_d_bridge as gb
  S = r"C:\Users\Satvik\AppData\Local\Temp\claude\34bc6e8cd9f62db3\f5adc626-6aab-44f4-8ef5-3a984a22d83e\scratchpad"
  x = _tone(16, 100.0, 0.3)
  r = gb.check_score_stem(_write(os.path.join(S, "A.wav"), _stereo(x, -x), codec="pcm_f32le"), _cue())
  print("f32 codes=", _codes(r), "side=", r["stats"].get("bass_side_db"))
  r = gb.check_score_stem(_write(os.path.join(S, "A24.wav"), _stereo(x, -x)), _cue())
  print("s24 codes=", _codes(r), "side=", r["stats"].get("bass_side_db"))
  EOF
  ```
  Output: `f32 codes= ['STEM_MONO_LOSS'] side= None` (no STEM_BASS_NOT_MONO); `s24 codes= ['STEM_BASS_NOT_MONO', 'STEM_MONO_LOSS'] side= 130.0`.
- Fix: when mid_p is zero and side_p is positive, return +inf (side is infinitely louder than mid), and treat None
  only when both are zero. Add the float-WAV anti-phase test and assert STEM_BASS_NOT_MONO in its codes.

## GBR-3 (LOW): single-channel stem with no bass is labelled STEM_BASS_NOT_MONO

- File: score/gate_d_bridge.py:107-117. For a stem with only the left channel, side equals mid exactly at every
  frequency, so the low-band ratio is always 0 dB, whatever the content.
- What is wrong: the stem fails anyway (STEM_MONO_LOSS at 3.01 dB), so the result is right, but a stem with no bass
  at all is reported as a bass failure. This contradicts the module decision "A stem with no bass at all passes"
  (line 21) and misleads whoever reads the code.
- Reproduction output (1 kHz tone on the left only, 24-bit and float):
  `B_f32_Lonly_1k_nobass codes= ['STEM_BASS_NOT_MONO', 'STEM_MONO_LOSS'] side= 0.0 loss= 3.01`
  `B_s24_Lonly_1k_nobass codes= ['STEM_BASS_NOT_MONO', 'STEM_MONO_LOSS'] side= 0.0 loss= 3.01`
- Fix: optional. Either report only the mono-loss code for one-channel content, or measure the low band only when its
  mid energy is above a small floor (for example -120 dB, matching DB_FLOOR). Add a test that documents the choice.

## GBR-4 (LOW): presence_levels raises on NaN or inf win_s

- File: score/gate_d_bridge.py:198-200. The guard `not win_s or win_s <= 0` does not catch NaN or inf, and
  `int(round(win_s * rate_v))` raises outside the try block (`_FAILS` only wraps decoding).
- Module docstring line 4 says bad input is reported, never raised; presence_levels docstring says it returns ([], [])
  on bad input.
- Reproduction output: `F raised nan ValueError cannot convert float NaN to integer`;
  `F raised inf OverflowError cannot convert float infinity to integer`.
  The CLI always passes the default 0.5, so this only affects Python callers.
- Fix: change the guard to `if rate_v != rate_s or not math.isfinite(win_s) or win_s <= 0: return [], []`. Add a
  one-line test with win_s=float("nan").

## GBR-5 (LOW): length tolerance boundary not tested on the long side at +2001

- File: score/tests/test_gate_d_bridge.py:88-97. The only near-boundary test checks +2000 (passes) and -2400 (fails).
  Nothing checks +2001 or -2000.
- Behaviour is correct, verified by probe: a 770001-sample stem gives `['STEM_LENGTH']`; a 766000-sample stem
  (exactly 2000 short) gives `[]`.
- Fix: add parametrised cases for 2000 long, 2001 long, 2000 short, 2001 short. This is a test gap, not a code defect.

---

Not findings (checked and correct): 16-bit WAV, mp3, 44.1 kHz and mono rejection; silence; the empty file (STEM_LENGTH
and STEM_SILENT); unreadable and missing files; NaN and bool cue totals (STEM_CUE_INVALID); validate_bgm_manifest
rejecting NaN LUFS; _bgm_track accepting the written manifest; presence math (0.5 s windows, -120 dB floor, speech gate
-40 dB, p95 floor from the 5th percentile); manifest path absolute; CLI exit codes 0, 1, 2 (tests exist).
