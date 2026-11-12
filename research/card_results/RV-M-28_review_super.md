Defect 1 — post_fetch_qa.py never writes the per-shot QA JSON.
Faulty line: `return out` at the end of `run` (and `run_from_files` returns it without writing anything).
Why wrong: The card requires “write qa result json per shot”. `run` builds `out` in memory and returns it, but no `clip_qa.json` is ever serialized under `plan["root"]`, so the QA record is not persisted and downstream gates cannot read it.
Fix: After every assignment to `out[sid]` (missing entry, missing clip, exception, pass, fail — i.e. before each `continue` and after the pass/fail branch), write:
```python
        out_path = Path(plan["root"]) / sid / "clip_qa.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(out[sid], indent=2), encoding="utf-8")
```

Defect 2 — post_fetch_qa.py lets unexpected QA errors crash the whole run instead of failing the shot.
Faulty line:
```python
        except (clip_qa.ClipQAError, ValueError, OSError) as exc:
```
Why wrong: The card says “A shot fails on … a QA error”. Any exception from `qa` outside that tuple (e.g. `AttributeError` when `doc` is not a mapping, `TypeError`, `KeyError`) propagates out of `run` and crashes the batch instead of recording that shot as failed.
Fix:
```python
        except Exception as exc:
```

Defect 3 — test_post_fetch_qa.py: the “routes required” test does not isolate the routes check.
Faulty line:
```python
    assert _go(tmp_path, monkeypatch, ["--qa-plan", "plan.json"]) == 1
```
Why wrong: `plan.json` is never created in `tmp_path`, so `main` can fail on the missing plan file before it ever evaluates `--routes`. The test cannot distinguish a routes refusal from a missing-plan refusal, so it cannot fail if the routes requirement is removed; it does not cover the named behavior.
Fix: Write a valid plan file first so the only missing piece is `--routes`:
```python
    (tmp_path / "plan.json").write_text(json.dumps({"lock": "l.json", "root": "r", "shots": {}}), encoding="utf-8")
    assert _go(tmp_path, monkeypatch, ["--qa-plan", "plan.json"]) == 1
```

VERDICT: FIX-FIRST