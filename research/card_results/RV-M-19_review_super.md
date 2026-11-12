Defect 1 — `flow/scripts/bible_to_sheet_jobs.py`, `sheet_jobs`
Faulty line:
```python
            prompt = (item.get("sheet_prompt") or item.get("card_prompt")) if isinstance(item, dict) else None   # V4 bible: characters have sheet_prompt, places and props card_prompt
```
Why: Card M-19 requires that only CHAR / ENV / PROP entries with a `sheet_prompt` become jobs. Falling back to `card_prompt` issues jobs for entries that have no `sheet_prompt`, violating the card and letting bad input pass silently.
Fix:
```python
            prompt = item.get("sheet_prompt") if isinstance(item, dict) else None
```

Defect 2 — `flow/scripts/bible_to_sheet_jobs.py`, `extra_sheet_jobs`
Faulty line:
```python
        prompt = (item.get("sheet_prompt") or item.get("card_prompt")) if isinstance(item, dict) else None
```
Why: Same violation as Defect 1 for turnaround / expressions jobs; entries without a `sheet_prompt` still get jobs.
Fix:
```python
        prompt = item.get("sheet_prompt") if isinstance(item, dict) else None
```

Defect 3 — `director/continuity_sheet.py`, `_start` / `_end`
Faulty lines:
```python
def _start(m):
    return m.get("start") or {}


def _end(m):
    return m.get("end") or {}
```
Why: If `start` or `end` is a truthy non-dict (e.g. a string or list), `or {}` returns it, and callers (`direction`, `eyeline_pairs`, `direction_flips`, `end_state`) then call `.get()` on it and crash with `AttributeError`.
Fix:
```python
def _start(m):
    s = m.get("start")
    return s if isinstance(s, dict) else {}


def _end(m):
    e = m.get("end")
    return e if isinstance(e, dict) else {}
```

Defect 4 — `flow/scripts/bible_to_sheet_jobs.py`, `sheet_jobs` (same crash in `extra_sheet_jobs`)
Faulty line:
```python
        items = bible.get(group) if isinstance(bible.get(group), dict) else {}
```
Why: `load_bible` can return a list or scalar from `json.loads`; `bible.get` then raises `AttributeError` instead of refusing cleanly.
Fix: Add `if not isinstance(bible, dict): return []` at the top of both `sheet_jobs` and `extra_sheet_jobs` (or coerce `data` to `{}` in `load_bible` before returning).

Defect 5 — `flow/scripts/bible_to_sheet_jobs.py`, `extra_sheet_jobs`
Faulty lines:
```python
    style = bible.get("style") if isinstance(bible.get("style"), dict) else {}
    style_prompt = style.get("sheet_prompt")
    if isinstance(style_prompt, str) and style_prompt.strip():
        jobs.append(_make_job("STYLE", "STYLE__chip__v01", style_prompt.strip(), [], 0))
```
Why: `--only` is documented as the ids to include, but the STYLE chip is always appended when `--section-4-3` is set, even when `only` excludes it.
Fix:
```python
    if not (only and "STYLE" not in only):
        style = bible.get("style") if isinstance(bible.get("style"), dict) else {}
        style_prompt = style.get("sheet_prompt")
        if isinstance(style_prompt, str) and style_prompt.strip():
            jobs.append(_make_job("STYLE", "STYLE__chip__v01", style_prompt.strip(), [], 0))
```

VERDICT: FIX-FIRST