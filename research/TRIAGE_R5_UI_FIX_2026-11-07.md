# TRIAGE R5 UI FIX (R5U) - 2026-11-07

Branch v4-architecture-2026-11-07. Files edited: ui/server.py, ui/pipeline.py, ui/test_r5u_fixes.py (new).

| # | Verdict | File:line (after fix) | Test |
|---|---------|-----------------------|------|
| 1 | REAL and fixed: `scope_ids` built a set of raw shot ids, so an unhashable id (list/dict) raised TypeError. Now the set holds `str(id)` and the membership test uses `str(i)`. | ui/server.py:414-415 | test_scope_ids_unhashable_shot_id_does_not_raise |
| 2 | REAL and fixed: `export` keyed `order` on raw shot ids, so an unhashable id raised TypeError. Now key, membership and sort use `str(...)`. | ui/server.py:1556-1558 | test_export_unhashable_shot_id_does_not_raise |
| 3 | REAL and fixed: `facts` keyed `dq_entries` and `fl_set` on `version`, so a list/dict version raised TypeError. Queue side and flow side now coerce list/dict `version` to `str`, the same as `image_id`. | ui/pipeline.py:388-391 (queue), 409-411 (flow), 417 (lookup) | test_facts_unhashable_version_does_not_raise |
| 4 | REAL and fixed: `gd["reasons"]` raised KeyError when a gate_d step had no `reasons`. Both reads now use `.get("reasons")`. Line 321 keeps its existing `or ["Gate D not ready"]` fallback, so the output is the same. | ui/pipeline.py:321, 858 | test_gate_d_plan_without_reasons_does_not_raise |
| 5 | REAL and fixed: `read_pack` row `seconds` returned a raw string. Non-number values (string, bool, None) now give 0. Int and float behaviour is unchanged. Strings are not parsed. | ui/server.py:737-738 | test_read_pack_string_seconds_row_is_zero |

Open on purpose (not changed): stat() race in server.py image and video listing; scope_ids duplicate handling beyond item 1; anything under ui/static/.

Suite: ui `246 passed in 17.98s` (baseline 241 + 5 new tests, all green).
