# Nemotron super review of the X-07 write_pack diff

BUGS:

1. `write_pack_glue.py` — `writer_gate` swallows the gate-file write error:
```python
    try:
        gate_path = Path(out) / 'writer_gate.json'
        gate_path.parent.mkdir(parents=True, exist_ok=True)
        with open(gate_path, 'w', encoding='utf-8') as f:
            json.dump(result_dict, f, indent=1, ensure_ascii=False)
    except Exception:
        pass
```
If the write fails, `writer_gate.json` is not created while `result_dict["ok"]` may still be `true`, so the caller sees a passing gate with no gate file on disk (silent pass / missing guard artifact).  
Fix: do not swallow; let the write error propagate (fail-closed) — delete the `try:` / `except Exception: pass` and write the file directly. If you prefer to keep collecting problems, append to `problems` and recompute `ok` after the attempt instead of swallowing.

2. `director/write_pack.py` — repaired answer is never persisted back to `raw_path`:
```python
        data = write_pack_glue.merge_repair(data, write_pack_glue.parse_repair(rep_path.read_text(encoding="utf-8")))
```
`merge_repair` updates only the in-memory `data`; `raw_path` on disk still holds the pre-repair faulty answer, so a successful repair is lost and downstream readers see stale/broken data.  
Fix: write the merged result back immediately after the merge:
```python
        data = write_pack_glue.merge_repair(data, write_pack_glue.parse_repair(rep_path.read_text(encoding="utf-8")))
        raw_path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
```

3. `director/write_pack.py` — gate blocking precondition is too weak, causing an uncaught crash:
```python
        if any(isinstance(s.get("blocking"), dict) for s in shots):
            write_pack_glue.write_blocking_files(out, shots)
```
`write_blocking_files` raises `ValueError` for *any* row whose `blocking` is not a dict, but `any` only requires one shot to have blocking. A mixed list crashes with an uncaught `ValueError`.  
Fix:
```python
        if shots and all(isinstance(s.get("blocking"), dict) for s in shots):
            write_pack_glue.write_blocking_files(out, shots)
```

BYPASS: No real run bypasses the guard through the shown call sites. In a real claude run `main()` sets `GUARD = True`, and all stage calls go through `call_claude` → `write_pack_glue.guarded_claude_call`. `call_claude_raw` is unguarded, but it is only invoked inside `call_claude`; no direct caller is shown in this diff. (Latent: any future direct caller of `call_claude_raw` would bypass the guard.)

VERDICT: FIX-FIRST
