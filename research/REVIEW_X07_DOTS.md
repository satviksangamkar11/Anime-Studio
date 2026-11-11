

## Review

I read the diff and both helper files carefully. The guard routing, the per-shot repair (separate `rep_path` instead of overwriting `raw_path`), the ledger/budget plumbing, and the fail-closed `cli_ready()`/`WRITER_CAP_CENTS` checks are all sound. The repair no longer overwrites the original answer — that was the right fix.

Two concrete defects remain:

**severity: medium — crash** — `director/write_pack.py:97`
```python
write_pack_glue.write_blocking_files(out, shots)
```
`write_blocking_files` raises `ValueError('...: missing dict blocking')` for any row whose `blocking` is not a dict (`write_pack_glue.py:117-118`). But the enclosing guard is only `if any(isinstance(s.get("blocking"), dict) for s in shots)` — true as soon as **one** row has a sheet. So a pack where some shots lack a `blocking` dict blows up with an unhandled `ValueError` at this call, even though the *same* call one layer down (`write_pack_glue.py:136`) is wrapped in try/except and turns it into a gate problem. Inconsistent handling; a partial writer output crashes the run instead of failing the gate.
Fix: wrap this call in try/except (or filter `shots` to rows with a dict `blocking`) so a missing sheet becomes a gate problem, matching `writer_gate`'s own behavior.

**severity: low — swallowed exception** — `write_pack_glue.py:186-187`
```python
    try:
        gate_path = Path(out) / 'writer_gate.json'
        ...
            json.dump(result_dict, f, indent=1, ensure_ascii=False)
    except Exception:
        pass
```
A failure writing the gate file is silently ignored. The result dict is still computed/returned correctly, so this doesn't fake a passing gate — but the `StageFailed` message raised at `write_pack.py:100` tells the user to inspect `writer_gate.json`, which may not exist. Fix: don't swallow (let it raise), or write the file before computing `ok`/problems so the diagnostic always exists.

**On guard bypass:** No real run bypasses the guard. In a CLI run `via` defaults to `"claude"`, so `main()` sets `GUARD = True` before any stage executes and every `call_claude` routes through `guarded_claude_call`, which is fail-closed (`WRITER_CAP_CENTS` required, ledger cap checked, `cli_ready()` gates on the binary). The only bypass is an explicit `GUARD = False` (tests / a non-claude `--via`), which is by design.

FINAL:
- medium, director/write_pack.py:97, `write_blocking_files(out, shots)` raises ValueError on any row lacking a dict `blocking` while the guard only checks `any(...)` and the call is unwrapped (unlike the same call inside `writer_gate`), so a partial pack crashes the run instead of becoming a gate problem — wrap in try/except or filter rows.
- low, write_pack_glue.py:186-187, the `except Exception: pass` around the `writer_gate.json` write swallows a real failure and leaves the failure message pointing at a possibly-missing file — don't swallow, or write before computing the result.