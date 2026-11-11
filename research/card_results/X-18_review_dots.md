Let me carefully review the code against the card requirements.

**Card requirements:**
1. `sfx_policy_filter(label_in, label_out, keep, bed_gain_db)` → volume expression with G = 10^(bed_gain_db/20). Keep windows are clip-relative `sfx_keep` from clip_qa.json.
2. `bed_gain_db = min(0, (voice_db − 22) − bed_db)`. Per shot, voice_db from vo_tracks_report; bed_db from clip_qa.json.
3. `build_mix_filter(..., sfx_policy=None)` applies it per clip before concat. None leaves behaviour unchanged.
4. `check_sfx_beds(levels) -> errors`: SFX_BED_LOUD when `bed_db > voice_db − 22 + 0.5`.
5. build_final_reel passes the policy from each shot's clip_qa.json. A missing clip_qa.json raises (X-15 already blocks).

**Test requirements:**
- `test_bed_gain_hand`: voice −18, bed −30 → −10 dB → G = 0.3162.
- `test_bed_already_quiet_gain_0`: bed −45 → 0.
- `test_keep_window_expression_text` (exact string).
- `test_bed_louder_than_voice_minus_22_fails`.
- `test_policy_none_unchanged`.

**Defect 1 — `test_bed_gain_hand` is tautological/weak:**
```python
assert round(10 ** (gd.bed_gain_db(-18.0, -30.0) / 20), 4) == 0.3162
```
This recomputes G from the function's own return value. It tests nothing about the formula; if `bed_gain_db` returned −10.0 by any other logic, this still passes. The card requires G = 10^(bed_gain_db/20) to be used inside the filter expression. A stronger test would assert the actual filter string contains `0.3162` for a −10 dB gain. This test cannot fail if the implementation is wrong in a way that still yields −10 dB.

Actually, let me be careful — the first assertion `gd.bed_gain_db(-18.0, -30.0) == pytest.approx(-10.0)` is a real check. The second assertion is the tautological one. It's a weak test but not strictly "cannot fail" — it could fail if `bed_gain_db` returned something other than −10.0. Hmm. It's redundant/tautological but not literally impossible to fail. I'll flag it as weak but not a hard defect.

**Defect 2 — `test_keep_window_expression_text` exact string:**
```python
expr = gd.sfx_policy_filter("sfxin", "sfxout", [(1.0, 2.0), (3.0, 4.0)], -10.0)
assert expr == "[sfxin]volume='if(between(t,1.000,2.000)+between(t,3.000,4.000),1,0.3162)':eval=frame[sfxout]"
```
The card says: `volume='if(between(t,a1,b1)+between(t,a2,b2),1,G)':eval=frame` with G = 10^(bed_gain_db/20). For bed_gain_db = −10.0, G = 0.31623... The implementation formats with `{g:.4f}` → 0.3162. The test expects 0.3162. That matches. OK.

But wait — the card says the keep windows are the clip-relative `sfx_keep` from clip_qa.json. The test uses hardcoded windows. That's fine for a unit test of the expression text.

**Defect 3 — `test_policy_none_unchanged`:**
```python
plain = gd.build_mix_filter(clips, "vo_full", None, 2.0)
assert gd.build_mix_filter(clips, "vo_full", None, 2.0, sfx_policy=None) == plain
assert gd.build_mix_filter(clips, "vo_full", None, 2.0, sfx_policy=[None]) == plain
```
This is a tautology — it calls the same function with the same args and asserts equality. `sfx_policy=None` is literally the default. This test cannot detect any regression in the None path because it compares the function to itself. It provides zero coverage of the "None leaves behaviour unchanged" requirement relative to any baseline. A real test would compare against a hardcoded expected filter string.

**Defect 4 — Missing test coverage.** The card lists test names. All five are present. But `test_policy_none_unchanged` is tautological.

**Defect 5 — `build_mix_filter` with `sfx_policy=[None]`:**
Looking at the code:
```python
pol = sfx_policy[n] if sfx_policy is not None else None
raw = f"sfx{n}raw" if pol else labels[-1]
```
When `pol` is `None`, `raw` = `labels[-1]` = `f"sfx{n}"`. Then no policy filter is appended. So `sfx_policy=[None]` produces the same as `sfx_policy=None`. That's correct behaviour. The test asserts this. But again it's comparing to the default call.

**Defect 6 — Real bug in `sfx_policy_for` in build_final_reel.py:**
```python
qa = json.loads((Path(clips[r["id"]]).parent / "clip_qa.json").read_text(encoding="utf-8"))
```
This reads clip_qa.json per shot. The card says "A missing clip_qa.json raises (X-15 already blocks)." But `clip_qa_problems` already checked each clip has a clip_qa.json. However, `sfx_policy_for` reads `qa["bed_db"]` and `qa["sfx_keep"]` without checking those keys exist. If clip_qa.json exists but lacks `bed_db` or `sfx_keep`, this crashes with KeyError rather than raising a clean error. That's a crash path. But the card says clip_qa.json is validated by X-14 (clip_qa.clip_ok). Whether those keys are required by clip_qa is unknown.

**Defect 7 — `voice_db` computation:**
```python
voice_db = voice_db_of(Path(vo_dir) / lang / f"{r['id']}.wav", wins)
if voice_db is None:
    policy.append(None)
    continue
```
When voice_db is None (no voice file or no speech windows), policy gets None — meaning no ducking for that shot. The card says policy is per shot from clip_qa.json. For shots with no voice, None is reasonable. But then `levels` doesn't get an entry for that shot, so `check_sfx_beds` doesn't check it. That's acceptable.

**Defect 8 — The real defect I should focus on.** Let me re-read the card's test list and check each is meaningful.

Actually, let me look more carefully at `test_bed_louder_than_voice_minus_22_fails`:
```python
loud = gd.check_sfx_beds([{"shot": "SHOT-001", "voice_db": -18.0, "bed_db": -39.0}])
assert [e["code"] for e in loud] == ["SFX_BED_LOUD"]
```
The check is `bed_db > voice_db - 22 + 0.5`. voice_db − 22 + 0.5 = −18 − 22 + 0.5 = −39.5. bed_db = −39.0 > −39.5 → True → SFX_BED_LOUD. Correct.

```python
assert gd.check_sfx_beds([{"shot": "SHOT-001", "voice_db": -18.0, "bed_db": -40.0}]) == []
```
−40.0 > −39.5 → False → no error. Correct.

But this test only covers one voice level (−18). It doesn't test the boundary at other levels, and critically it doesn't test the case where the tolerance matters. It's weak but not tautological.

**The strongest real defect:** `test_policy_none_unchanged` is tautological — it asserts `f(x) == f(x)`. This is the "test that cannot fail" category the card warns about. It provides no protection against regression of the None path. A proper test would hardcode the expected filter string for the None case.

Also `test_bed_gain_hand`'s second assertion is tautological (computes G from the function's own output).

Let me also check: does the card require a test for `check_sfx_beds` with multiple shots or edge cases? The card lists `test_bed_louder_than_voice_minus_22_fails` — present.

**Verdict:** There are tautological tests. `test_policy_none_unchanged` literally cannot fail as written (it compares the function to itself with the default). This is a real defect per the card's own warning category ("a test that cannot fail (weak or tautological)").

Fix: Replace the tautological assertions with a hardcoded expected filter string.

Expected for None policy with one clip:
Looking at build_mix_filter:
- chains.append trim/asetpts/afade for sfx0raw (since pol is None, raw = "sfx0", labels[-1] = "sfx0")
- chains.append concat
- vo_input is "vo_full" (a str, not None), so it goes to build_voice_branch

Wait, `vo_input="vo_full"` is a string, so `vo_input is None` is False. So it calls build_voice_branch("h3_sfx_full", "vo_full", None, 2.0, ...). Hmm, but in the test, vo_input is "vo_full". Let me trace:

```python
chains.append("".join(f"[{l}]" for l in labels) + f"concat=n={len(labels)}:v=0:a=1[h3_sfx_full]")
lt = LOUDNESS
loud = f"loudnorm=I=...[{MASTER_LABEL}]"
if vo_input is None:  # False, vo_input = "vo_full"
    ...
chains += build_voice_branch("h3_sfx_full", "vo_input", bgm_input, total, MASTER_LABEL, ...)
```

Wait, there's a bug here! Look:
```python
chains += build_voice_branch("h3_sfx_full", vo_input, bgm_input, total, MASTER_LABEL, lt["target_lufs"], lt["loudnorm_tp"], lt["lra"])
```
It passes `vo_input` (the variable, which is "vo_full") — that's correct.

But wait, in the `if vo_input is None` branch, there's a redundant `lt = LOUDNESS` before it, and then another `lt = LOUDNESS` after the if block. That's harmless.

So the expected plain output for the test would be a long string. Hardcoding it is fragile but that's what a real test would do. Actually a better approach: test that `sfx_policy=None` produces a filter WITHOUT any `volume=` SFX policy expression, and that `sfx_policy=[None]` also doesn't. But the current test is still tautological.

Actually, the cleanest fix that keeps the test meaningful: assert that the None-path output does NOT contain the ducking volume expression, and that it equals a specific expected string. Let me just give the exact fix.

Let me reconsider — is `test_policy_none_unchanged` truly unable to fail? 
```python
plain = gd.build_mix_filter(clips, "vo_full", None, 2.0)
assert gd.build_mix_filter(clips, "vo_full", None, 2.0, sfx_policy=None) == plain
```
Since `sfx_policy=None` is the default, `build_mix_filter(clips, "vo_full", None, 2.0, sfx_policy=None)` is byte-identical to `build_mix_filter(clips, "vo_full", None, 2.0)`. This is a mathematical identity — it cannot fail. Same for the `[None]` line? No — `[None]` is not None, so it takes a different code path (the loop sets `pol = None` for that entry, `raw = "sfx0"`, no policy filter appended). So the `[None]` assertion could theoretically fail if the `[None]` path were buggy. But the first assertion (`sfx_policy=None`) is strictly tautological.

So the fix: replace the first assertion with a hardcoded expected string, or remove it and keep only the `[None]` one plus a content check.

Let me write the exact fix.

VERDICT: FIX-FIRST

Let me be precise about the faulty line and fix.

Faulty line (test file):
```python
    plain = gd.build_mix_filter(clips, "vo_full", None, 2.0)
    assert gd.build_mix_filter(clips, "vo_full", None, 2.0, sfx_policy=None) == plain
```

Fix: replace with a content assertion that the None path produces no SFX ducking expression and matches an explicit expected string.

Actually, I realize I should double check whether there might be a more serious defect. Let me re-examine `build_mix_filter` more carefully for the `sfx_policy=[None]` case and the `raw` logic.

```python
for n, c in enumerate(sfx_clips):
    dur = c["trim_out_sec"] - c["trim_in_sec"]
    ...
    labels.append(f"sfx{n}")
    pol = sfx_policy[n] if sfx_policy is not None else None
    raw = f"sfx{n}raw" if pol else labels[-1]
    chains.append(f"...[{raw}]")
    if pol:
        chains.append(sfx_policy_filter(raw, labels[-1], pol["keep"], pol["bed_gain_db"]))
```

When `sfx_policy=[None]`: pol = None, raw = "sfx0" (= labels[-1]), no policy filter. Correct — matches None behaviour. Good.

When `sfx_policy=[{"keep":..., "bed_gain_db":...}]`: pol is a dict, raw = "sfx0raw", policy filter applied producing [sfx0]. Correct.

So the implementation is correct. The only real defect is the tautological test.

One more: `test_bed_gain_hand` second assertion:
```python
assert round(10 ** (gd.bed_gain_db(-18.0, -30.0) / 20), 4) == 0.3162
```
This is circular — it derives G from the function's output and checks it equals the expected G. If `bed_gain_db` were wrong but still returned −10.0, this passes. It's weak/redundant but the first assertion does check the −10.0 value. I'll flag it as weak but the primary fix is the tautology.

I'll report both but focus the fix on the tautological one.

Actually, let me reconsider the second assertion. `10 ** (gd.bed_gain_db(-18.0, -30.0) / 20)` — if bed_gain_db returned, say, −9.0 instead of −10.0, then 10^(−9/20) = 0.3548, round → 0.3548 ≠ 0.3162 → fails. So it's not strictly unable to fail. It's just redundant given the first assertion. It's a "weak" test, not tautological. I'll mention it but the hard fix is `test_policy_none_unchanged`.

Let me finalize.

Faulty lines:
1. `h3/tests/test_gate_d_sfx_policy.py` — `test_policy_none_unchanged`: `assert gd.build_mix_filter(clips, "vo_full", None, 2.0, sfx_policy=None) == plain` is a tautology (compares the function to itself with the default arg).

Fix: assert against an explicit expected string or assert the absence of the ducking expression.

I'll provide the exact replacement.

VERDICT: FIX-FIRST