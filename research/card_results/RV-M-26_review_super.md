Defect 1: `build_final_reel.py` does not implement the master WAV decode + gate_d silence/LRA gate the card requires.
Faulty line: `    errors, warnings = b.audio_gate_from_wav(wav)` in `test_half_second_digital_silence_master_fails_the_build` (same for `b.master_wav_argv`, `b.lra_warnings`, `b.master_audio_check` elsewhere in the test file).
Why wrong: `build_final_reel.py` defines none of `master_wav_argv`, `audio_gate_from_wav`, `lra_warnings`, or `master_audio_check`. The card requires decoding the master to WAV and calling `gate_d` check_no_silence plus LRA warn; every test that calls these raises `AttributeError` before any assertion, so “build fails on a 0.5 s digital-silence master” is not actually tested.
Fix: add to `build_final_reel.py`:
```python
def master_wav_argv(video, wav):
    return ["ffmpeg", "-y", "-v", "error", "-i", str(video), "-vn", "-ar", "48000", "-ac", "2",
            "-c:a", "pcm_s16le", str(wav)]

def audio_gate_from_wav(wav):
    with wave.open(str(wav), "rb") as w:
        rate = w.getframerate()
        pcm = w.readframes(w.getnframes())
    samples = np.frombuffer(pcm, dtype="<i2").astype(np.float64)
    errors, warnings = gd.check_no_silence(samples, rate)
    warnings = warnings + lra_warnings(gd.lra(samples, rate))
    return errors, warnings

def lra_warnings(lra):
    if lra is None or lra <= 11:
        return []
    return [f"LRA {lra} LU exceeds 11 LU limit"]

def master_audio_check(video, work):
    work.mkdir(parents=True, exist_ok=True)
    wav = work / "master.wav"
    subprocess.run(master_wav_argv(video, wav), check=True)
    return audio_gate_from_wav(wav)
```

Defect 2: `build_final_reel.py` never enforces the clip_qa.json gate the card requires.
Faulty line: `import clip_qa  # noqa: E402` (imported but unused; no check anywhere in `assemble_video` or the build flow).
Why wrong: The module docstring states “Each clip's folder must hold a passing clip_qa.json (X-14),” but the code never reads `clip_qa.json`, so a clip with missing or failing QA enters the reel silently.
Fix: in `assemble_video`, after the frame probe, add:
```python
        qa_path = Path(p).parent / "clip_qa.json"
        if not qa_path.is_file():
            raise SystemExit(f"{s['shot_id']}: missing clip_qa.json (X-14)")
        if not json.loads(qa_path.read_text(encoding="utf-8")).get("passed"):
            raise SystemExit(f"{s['shot_id']}: clip_qa.json not passing (X-14)")
```

Defect 3: `run_colab_batch.py` does not implement `qa_inputs`, so the lock route and M-13 chain_prev PNG are not wired.
Faulty line: `    qa = rcb.qa_inputs("SHOT-001", {}, routes, tmp_path)` in `test_qa_route_maps_start_only_to_S_and_skips_the_end_frame` (same for the chain and unknown-route tests).
Why wrong: `run_colab_batch.py` defines no `qa_inputs`. The card requires passing the route from the lock to `qa_shot` and passing the chain_prev PNG from M-13 `chain_step`; the tests cannot run.
Fix: add to `run_colab_batch.py`:
```python
def qa_inputs(shot_id, shot, routes, base_dir):
    route_map = {"S": "S", "REF_S": "S", "SE": "SE", "REF_SE": "SE", "SOFT_SE": "SE"}
    route = routes["routes"][shot_id]["route"]
    if route not in route_map:
        raise ValueError(f"unknown route {route!r} for {shot_id}")
    chain_prev = None
    if "chain_from" in shot:
        png = Path(base_dir) / "chain" / f"{shot['chain_from']}-last.png"
        if not png.is_file():
            raise ValueError(f"{shot_id}: chain_prev {png} not saved by M-13 chain_step")
        chain_prev = png
    return {"route": route_map[route], "chain_prev": chain_prev}
```

Defect 4: `run_colab_batch.py` does not implement `render_gate`, so the render gate (`render_allowed` + `record_drift_step`) is not wired into this module.
Faulty line: `    problems, _ = rcb.render_gate(_history({"SHOT-001": 3}), ["SHOT-001"], drift_step="simplify")` in `test_fourth_render_of_a_shot_is_refused_without_owner_flag` (same for the other render_gate tests).
Why wrong: `run_colab_batch.py` defines no `render_gate`. The card requires the render gate in `run_colab_batch`; all render-gate tests raise `AttributeError` before asserting.
Fix: add to `run_colab_batch.py`:
```python
def render_gate(history, shots, owner_flag=False, drift_step=None, drift_log=None):
    drift_log = dict(drift_log or {})
    problems = []
    log = {}
    for sid in shots:
        n = len((history.get("shots") or {}).get(sid, []))
        if not render_allowed(history, sid, owner_flag=owner_flag):
            problems.append(f"{sid}: escalate - render refused without owner flag")
            continue
        if n >= 1 and drift_step is None:
            problems.append(f"{sid}: drift step required for re-render")
            continue
        if drift_step:
            prev = drift_log.get(sid, [])
            if prev and DRIFT_ORDER.index(drift_step) <= DRIFT_ORDER.index(prev[-1]):
                problems.append(f"{sid}: drift steps out of order")
                continue
            record_drift_step(drift_log, sid, drift_step)
            log.setdefault(sid, []).append(drift_step)
    return problems, log
```

VERDICT: FIX-FIRST