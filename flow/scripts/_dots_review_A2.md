` blocks (non-greedy, re.S). Then if "</think>" in text, take after last. Then split on first <think> and take before. Hmm — if the model outputs `<think> reasoning </think> answer`, first sub removes the think block → " answer". Then "</think>" not in text → skip. Then split on "<think>" → ["", " answer"]? Wait after removing think block, text = " answer" (with leading space). Then `.split("<think>", 1)[0]` → "" since no <think>. strip → "". Hmm! That's a bug: if the model output is exactly `<think>...</think> answer`, after removing the think block, the remaining text is " answer", and there's no <think> left, so split returns the whole string [0] = " answer", strip → "answer". Wait `text.split("<think>", 1)` on " answer" returns [" answer"], [0] = " answer". strip → "answer". OK fine.

But consider output: `answer <think> more` (think at end, unclosed) — hmm. The logic: remove all `<think>...</think>` pairs. Then if "</think>" present, take after last. Then take before first <think>. So if text = "answer <think> reasoning" (no closing), after no pairs removed, "</think>" not in text, split on first  → "answer". Good.

Edge: text = "<think> a </think> b <think> c </think> d" → sub removes both pairs → " b  d"? Actually non-greedy: first match `<think> a </think>`, second ` b <think> c </think>`? Let's see: `re.sub(r"</think>.*?</think>", "", text, flags=re.S)` — pattern is `</think>.*?</think>`. It matches from first <think> to first <think> after it... wait pattern starts with <think>. In " a  b  c  d" (with tags), first match: ` a ` (from first <think> to second <think>). Then continues from "b  c  d": next match ` c ` (third <think> to fourth <think>). Result: "b d"? Actually remaining: after removing first match, string is "b c d" with tags: "b  c  d" → removing ` c ` leaves "b d". Hmm, so result "b d". Then no <think>, split → "b d".strip(). OK, it keeps both. Fine-ish.

The real concern: what if model outputs answer inside think block? Then empty. That's caught by empty reply → error. Fine.

11. Line 138-151 _Params: wraps post, adds temperature/top_p/seed/chat_template_kwargs. Note: `kwargs["json"] = dict(kwargs["json"], ...)` — assumes kwargs has "json". The scheduler's call presumably passes json. Also note `enable_thinking: True` — but strip_think handles <think>. OK.

Potential bug: if the scheduler passes json as something else... not our concern.

12. Line 159-172 call_review: `res = sched.call(parts, max_tokens=MAX_TOKENS)`. Then checks `res["status"] == "CLIENT_ERROR" and params.model_missing and sched.model == MODEL`. Then fallback. Then `info = {"model": sched.model, "key_used": f"key {res['key_index']}" if "key_index" in res else None, "tries": sched.snapshot()["http_attempts"]}`. Note: after fallback, `res` is the new result, and info uses the new res's key_index. Fine.

But: if first call fails with model_missing and status CLIENT_ERROR, we switch model and retry. But what if the retry also fails? Then res["status"] != "OK" → returns error. OK.

Hmm, but there's a subtle issue: `params.model_missing` is set only when response status in (400,404) and text contains "not found"/"does not exist". But `res["status"] == "CLIENT_ERROR"` — does the scheduler map 404 to CLIENT_ERROR? Presumably. OK.

13. Line 175-199 review(): 
- `cands = [Path(candidates)] if isinstance(candidates, (str, Path)) else [Path(c) for c in candidates]` — fine.
- `labels = list("AB"[:len(cands)])` — for 1 candidate → ["A"], for 2 → ["A","B"]. OK.
- `sheet = base.with_name(base.stem + "__neighbours.jpg")` — base is first candidate path. So the sheet is written next to candidate A. Fine.
- `build_sheet(job, [str(c) for c in cands], sheet)` — builds continuity sheet.
- `report = base.with_name(base.stem + "__review.md")` — report file.
- `parts = [{"type": "text", "text": review_prompt(job, labels)}] + [image_part(p) for p in [sheet, *cands]]` — includes sheet + candidates as images. Good.
- reply = call_review. text = reply.get("text") or "".
- `report.write_text(text, encoding="utf-8")` — writes even if error. Fine.
- For each candidate, parse. If text empty → UNSURE with missing all questions. Good — fail closed.
- out dict includes key_used, tries, model. Hmm — `key_used` is "key {index}" not the actual key. Good, no key leak.
- `out["prompt_sha256"] = job["prompt_sha256"]` — fine.
- Writes review.json. Returns out.

Potential bug: `reply.get("error")` — when call_review returns error dict, it has "error" key. In review(), `text = reply.get("text") or ""` → "". Then results all UNSURE. out["error"] = reply["error"]. Good.

But wait: in call_review, when status != OK, returns {"error": ..., **info}. info includes "model", "key_used", "tries". So reply has no "text". Good.

14. main(): 
- Line 208: `job = next((j for j in json.loads(a.jobs.read_text(...)) if j["shot_id"] == a.shot), None)`. If jobs file is huge, fine.
- Line 209: `if job is None or not all(c.is_file() for c in a.candidate) or len(a.candidate) > 2: return 2`. Good.
- Line 213: `keys = load_env_keys(ENV_FILE)`. On ValueError → return 2 (refused). Good.
- Line 217: `out = review(job, a.candidate, keys)`. Note: a.candidate is a list of Path. review accepts list. OK.
- Line 219-223: prints results.
- Line 224-225: prints error.
- Line 226: prints model/key_used/tries.
- Line 229: `return {"PASS": 0, "BLOCK": 1}.get(out["choice"]["decision"], 3)`. So PASS→0, BLOCK→1, else (UNSURE)→3. Good, matches docstring.

But: if `out["choice"]["decision"]` is "BLOCK", exit 1. Docstring says exit 1 BLOCK (fix). Good.

Hmm — but what if review() itself raised an exception? Not handled. E.g., build_sheet failing, or network error in sched.call. The scheduler probably catches. But `requests.post` could raise ConnectionError — uncaught → traceback, exit 1. Not great but not a logic bug per se.

15. Key leak check: The output JSON contains "key_used": "key N" — index only, not the key. Good. The report markdown contains the model's text only. The prompt contains job['prompt'] — that's the prompt, not a key. Good.

Wait — line 194: `"key_used": reply["key_used"]` — but if reply has no "key_used" (error path where... no, call_review always includes info). Actually in review(), `reply = call_review(...)`; if call_review returns error dict, it includes info with key_used. OK.

Hmm, but line 194 references `reply["key_used"]` and `reply["tries"]` and `reply["model"]` — if reply is error dict, these exist. Good.

16. One bug: line 165 `info = {... "key_used": f"key {res['key_index']}" if "key_index" in res else None ...}`. But on the fallback path, `res` is reassigned to the second call result. Fine.

17. Potential bug: In `review()`, `out` uses `reply["model"]` — after fallback, sched.model is FALLBACK_MODEL, so model reflects fallback. Good.

18. Now the big one: `choose()` line 112: `return {"decision": "PASS", "chosen": best["candidate"], "label": best.get("label")}`. But `best` is a result dict from `results`, which has keys: verdict, stated_verdict, answers, missing, fix, edit_instruction, regen_sentence, label, candidate. So best["candidate"] is the path string. OK.

Line 114-115: fixes list for BLOCK results. OK.

19. Bug? In `parse`, line 91: `derived = "BLOCK" if "BLOCK" in results else ...`. `results` is a list of strings from answers. If any answer is BLOCK → derived BLOCK. Good.

But what about ADVISORY answers? They don't affect derived. Good.

Line 93: `verdict = derived if stated == derived else ("BLOCK" if derived == "BLOCK" else "UNSURE")`. Consider derived = "PASS", stated = None (no VERDICT line). Then stated != derived → else branch → derived != BLOCK → UNSURE. So missing VERDICT line → UNSURE. Fail-closed. Good.

Consider derived = "BLOCK", stated = "PASS" → verdict BLOCK. Hmm, that means if the model says PASS in VERDICT but answers contain BLOCK, we go BLOCK. Fail-closed. Good.

Consider derived = "UNSURE", stated = "BLOCK" → stated != derived → else → derived != BLOCK → UNSURE. OK.

Consider derived = "PASS", stated = "BLOCK" → UNSURE. Hmm, model says BLOCK in verdict but all answers PASS → we say UNSURE rather than BLOCK. Slightly odd but fail-closed (not fail-open). Acceptable.

20. Now — is there a fail-open path? The requirement: "missing answer or empty reply must be UNSURE never PASS". 
- Empty reply → text = "" → parse not called; r = UNSURE. Good.
- Missing answers → missing list non-empty → derived UNSURE (unless BLOCK present). Good.
- But: what if text is non-empty but contains no parseable lines at all? Then answers = {}, missing = all 6, results = [], derived: "BLOCK" in [] → False; missing non-empty → UNSURE. stated = None. verdict = UNSURE. Good.

21. Now consider a subtle bug: line 87 regex uses `\b` after the verdict token. For "UNSURE" the `\b` requires a word boundary after. If the model writes "UNSURE" at end of line with no trailing char... `\b` matches between S and end-of-string? Yes, \b matches at end of word. Fine.

But the regex `^\s*{pre}(Q[1-6])\s*[:\-]\s*(PASS|BLOCK|ADVISORY|UNSURE)\b\s*[-:]?\s*(.*)$` — the `\s*[-:]?` allows an optional dash/colon after the verdict. So "A Q1: PASS - reason" matches with reason="reason". And "A Q1: PASS reason" (no dash) → after `\b` we have `\s*` matching space, `[-:]?` optional none, `\s*` none, `(.*)` = "reason". OK.

But "A Q1: PASS" with no reason → reason = "". Fine.

22. Now `fields` regex line 88: `^\s*{pre}({'|'.join(FIELDS)})\s*:\s*(.*)$`. FIELDS = ("VERDICT","FIX","EDIT_INSTRUCTION","REGEN_SENTENCE"). Note "EDIT_INSTRUCTION" contains underscore; fine. But order in alternation: VERDICT|FIX|EDIT_INSTRUCTION|REGEN_SENTENCE. Regex alternation is ordered; "FIX" vs... no overlaps. Fine.

But note: the answers regex also would match "VERDICT" lines? No, answers requires Q[1-6]. Fine.

23. Potential issue: The `parse` function's answers regex would also match lines like "A Q1: PASS" inside the FIX line? No.

24. Now, one real bug: line 89 `missing = [q for q, _ in QUESTIONS if q not in answers]`. answers keys are "Q1".."Q6". Good.

25. Let me check `review_prompt` line 63: `full = ", ".join(f"image {k + 2} = CANDIDATE {l} at full size" for k, l in enumerate(labels))`. Image 1 is the sheet, so candidates are images 2,3. Good.

26. Now bridge_flow_to_h3.py:

Line 32-55 plan(): 
- `tw % 32 or th % 32` → raise. Good.
- src_aspect = Fraction(sw, sh), target = Fraction(tw, th).
- `off_pct = abs(src_aspect - target) / target * 100` — this is a Fraction arithmetic. abs of Fraction, divided by target (Fraction), times 100 → Fraction. Then `if off_pct > Fraction(str(tol_pct))`. tol_pct is a float 3.0; str(3.0) = "3.0"; Fraction("3.0") = 3. OK. Comparison of Fractions — fine.
- Then compute win_h, win_w as Fractions.
- `left = (sw - win_w) / 2` — Fraction. `box = tuple(float(v) for v in (left, top, left + win_w, top + win_h))` — floats.
- `box_aspect = (box[2] - box[0]) / (box[3] - box[1])` — float division.
- aspect_error_pct computed.

Bug? `crop_px_removed = round(float((sw - win_w) + (sh - win_h)), 3)`. Fine.

Line 66: `src.resize(size, Image.LANCZOS, box=box).save(dst_path, format="PNG")`. Here `src` is the converted RGB image. `box` is a float tuple. Pillow's resize with box accepts floats since Pillow 8? Actually the `box` parameter for resize was added in Pillow 8.0 and accepts floats. Hmm, but there's a subtlety: Pillow's resize box must be a 4-tuple of floats within the source. Fine.

But wait — a real bug: `src.resize(size, Image.LANCZOS, box=box)` — the box defines the source region. But the box computed has floats like (left, top, left+win_w, top+win_h) where win_w may be a non-integer Fraction. Pillow handles float boxes by... it should work. OK.

Hmm, but actually there's a known issue: when box is given, Pillow resamples from that region. The box coordinates are in source pixel coordinates. Fine.

Line 67-69: verify output size. Good.

Line 78-103 _convert():
- `label = os.path.basename(src).split("__")[0]` — for "LEAP-001__candidate_v01__final.png" → "LEAP-001". Good.
- Check if dst exists: open and check size. If matches → SKIP. If exists with different size → raise ValueError "not overwriting". Good — no overwrite.
- But: there's a TOCTOU-ish thing, minor.
- `with Image.open(src) as im: src_size = im.size` — opens again just for size. Then plan. Then if dry_run print DRY. Then `os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)` — good.
- `r = bridge(src, dst, size, tol_pct)` — bridge opens src again, converts, resizes, saves, verifies.

Bug: In `_convert`, when dst exists with wrong size, it raises ValueError → caught → REFUSED. Good.

But: in `bridge()`, line 60: `if os.path.abspath(src_path) == os.path.abspath(dst_path): raise ValueError`. Good.

Line 96: `os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)` — if dst has no directory part, os.path.dirname returns "" → os.path.abspath("") = cwd → makedirs(cwd) exist_ok=True. Fine.

Line 124: `files = sorted(glob.glob(...))`. Good.

Line 134: `return 1 if "REFUSED" in statuses else 0`. So exit 1 if any refused, else 0. SKIP/DRY/OK → 0. Hmm, is that right? DRY-RUN returns 0 even though nothing written. Probably fine.

Now let me think about the actual bugs more carefully.

review_shot.py potential bugs:

A. Line 180: `build_sheet(job, [str(c) for c in cands], sheet)` — we don't check the return / whether sheet was created. If build_sheet fails, exception propagates. Not a logic bug per se.

B. Line 182: `parts = [{"type": "text", "text": review_prompt(job, labels)}] + [image_part(p) for p in [sheet, *cands]]`. Note image_part opens each path. If a candidate is a browser screenshot that's fine.

C. The `choose()` function: line 112 `best = min(passed, key=lambda r: sum(a["result"] == "ADVISORY" for a in r["answers"].values()))`. If answers is empty (shouldn't happen for PASS), sum = 0. Fine.

D. Real bug candidate: In `parse`, the `fields` dict could contain "VERDICT" with value "PASS - something". `stated = fields["VERDICT"].split()[0].upper()` → "PASS". Good.

E. Real bug: line 98: `if fix == "edit" and not (ins.startswith("Change only") and "Keep everything else exactly the same" in ins): fix = "regenerate"`. ins = fields.get("EDIT_INSTRUCTION", "") → "" if missing. "".startswith("Change only") → False → fix = regenerate. Good.

F. Now think about the key scheduler interaction. `sched.call(parts, max_tokens=MAX_TOKENS)`. What does the scheduler expect for `parts`? It presumably builds chat messages with images. The `_Params` wrapper modifies kwargs["json"]. We assume the scheduler passes json kwarg. If the scheduler's call signature is `call(self, parts, max_tokens, ...)` and internally builds `json={...}` and calls `post(url, json=..., headers=...)`, then our wrapper adds temperature etc. Fine.

G. Potential key leak: `out` JSON includes "sheet" and "report" paths, "model", "key_used" (index), "tries". No actual keys. The .env file keys are loaded but never printed. Good.

Wait — line 226 in main: `print(f"model: {out['model']}  {out['key_used']}  tries: {out['tries']}  advisory_only: True")`. key_used is "key N". Good.

H. Now: is there a fail-open path where a missing answer yields PASS? Let's trace: derived = "BLOCK" if "BLOCK" in results else ("UNSURE" if missing or "UNSURE" in results else "PASS"). For derived to be PASS: no BLOCK in results, no missing, no UNSURE in results. So all 6 answers present and all PASS/ADVISORY. Then stated must == "PASS" for verdict PASS. If the model didn't output a VERDICT line, stated = None → verdict = UNSURE. Good, fail closed.

I. What about `choose()` — it only looks at verdict == "PASS". So UNSURE results never chosen. Good.

J. Hmm — one thing: line 189-190 when text.strip() is falsy, r = {"verdict": "UNSURE", ...}. But then `r.update(label=lab, candidate=str(c))`. And `r.get("answers", {})` in main print loop → {} → no questions printed. Fine. And `r.get("error")` → reply.get("error") or "empty reply". Good.

K. Consider: text is non-empty but model returned only thinking (no answer). strip_think returns "" → reply has "text": "" → call_review returns {"text": "", **info}? Wait line 169-171: `text = strip_think(res["text"])`; `if not text: return {"error": "empty reply ...", **info}`. So reply is error dict, no "text". Then in review: `text = reply.get("text") or ""` → "". Good → UNSURE.

L. Now, an actual logic bug: line 162: `if res["status"] == "CLIENT_ERROR" and params.model_missing and sched.model == MODEL:`. But `params.model_missing` is set in `_Params.__call__` based on the *response text*. But `sched.call` may itself retry on 429 etc. and may ultimately return CLIENT_ERROR. The model_missing flag is set on the last post call. OK.

But there's a subtle issue: `params.model_missing` stays True forever after first detection. If the fallback model also returns 404, then `sched.model == MODEL` is False so we don't loop. Good — no infinite retry.

M. Now let me look for "retries that loop or spend extra". In call_review, only one fallback retry. Good. The scheduler itself handles 429 retries — that's in the existing scheduler, not our code.

N. Exit codes: 0 PASS, 1 BLOCK, 2 refused, 3 UNSURE. Docstring says "2 refused". main returns 2 for refused (line 210, 216). And line 229 returns 3 for UNSURE. Good. But wait — docstring says "Exit 0 PASS (keep), 1 BLOCK (fix), 3 UNSURE (stop, report), 2 refused." Consistent.

Hmm, but line 209: `if job is None or not all(c.is_file() for c in a.candidate) or len(a.candidate) > 2: return 2`. Docstring says "a candidate file is missing, or more than two candidates" → REFUSED → 2. Good.

O. Pillow box misuse in review_shot: `im.thumbnail((IMG_SIDE, IMG_SIDE))` — correct usage. `Image.open(path)` context manager — fine.

P. Overwriting files: review_shot writes `sheet` (base.stem + "__neighbours.jpg"), `report` (base.stem + "__review.md"), `base.stem + "__review.json"`. These are new files with distinct names; no overwrite of candidates. But if run twice on same candidates, it overwrites the review.json/report/sheet — that's expected (idempotent re-review). Not a bug.

Hmm, but wait: the sheet path is `base.with_name(base.stem + "__neighbours.jpg")`. base is candidate A path. If candidate A is "LEAP-001__candidate_v01__final.png", stem = "LEAP-001__candidate_v01__final", sheet = "LEAP-001__candidate_v01__final__neighbours.jpg". Fine.

Q. Now let me think about a real logic bug in `parse` regarding the `pre` prefix and the answers regex. `pre = rf"{re.escape(label)}\s+"`. For label "A", pre = "A\\s+". The regex: `^\s*A\s+(Q[1-6])\s*[:\-]\s*(PASS|...)...`. Good.

But the FIELDS regex line 88: `^\s*{pre}({'|'.join(FIELDS)})\s*:\s*(.*)$` → `^\s*A\s+(VERDICT|FIX|...)\s*:\s*(.*)$`. Good.

R. Bug: In `parse`, `fields` is built with re.finditer over the whole text with the pre prefix. But what if the model writes "A VERDICT: PASS" — matches. Good. What if model writes "VERDICT: PASS" without label (because the prompt says "for each candidate exactly these lines: <candidate> FIX: ...")? The prompt explicitly says `<candidate> VERDICT: ...`. So labelled. Good.

But the answers regex also requires label. Prompt says `<candidate> Q<n>: ...`. Good.

S. Now, an important one: the prompt line 72 says answer format `<candidate> Q<n>: PASS|BLOCK|ADVISORY|UNSURE - <short reason>`. And line 80: `<candidate> VERDICT: PASS | BLOCK | UNSURE`. Good.

T. Now, is there any path where `out["choice"]["decision"]` key missing? choose() always returns a dict with "decision". Good. Unless results empty — results always has len >= 1 (one per candidate). choose handles.

U. Let me reconsider line 93 more carefully:
```
verdict = derived if stated == derived else ("BLOCK" if derived == "BLOCK" else "UNSURE")
```
Case: derived=PASS, stated=PASS → PASS. 
Case: derived=BLOCK, stated=BLOCK → BLOCK.
Case: derived=UNSURE, stated=UNSURE → UNSURE.
Case: derived=BLOCK, stated=PASS → BLOCK (fail closed, good).
Case: derived=BLOCK, stated=UNSURE → BLOCK.
Case: derived=PASS, stated=BLOCK → UNSURE.
Case: derived=PASS, stated=UNSURE → UNSURE.
Case: derived=PASS, stated=None → UNSURE.
Case: derived=UNSURE, stated=PASS → UNSURE.
Case: derived=UNSURE, stated=BLOCK → UNSURE.
Case: derived=UNSURE, stated=None → UNSURE.
All fail-closed. Good.

V. Now `choose`: if all results UNSURE → decision UNSURE → exit 3. Good.

W. One more: line 113 `if any(r["verdict"] == "BLOCK" for r in results)`. Good.

X. Now let me check for "key leaks into output or logs". The review.json contains the full prompt? No — it contains shot_id, flow_title, results, choice, sheet, report, model, key_used, tries, advisory_only, backend, prompt_sha256, time. The prompt itself is only in the report.md? No — report.md contains the model's reply text, not the prompt. The prompt is sent to the model but not written anywhere. Good. Actually wait, is the prompt written? Line 186: `report.write_text(text, ...)` — text is the model reply. Good. No prompt leak.

Hmm, but the prompt contains job['prompt'] which is the generation prompt — that's not a secret key. Fine.

Y. Now bridge_flow_to_h3.py bugs:

1. Line 41: `if off_pct > Fraction(str(tol_pct))`. tol_pct default 3.0. But `off_pct` is a Fraction; comparison works. But note: `Fraction(str(tol_pct))` — if tol_pct is passed as an int 3, str(3) = "3", Fraction("3") = 3. Fine. If tol_pct = 3.333, str → "3.333", Fraction("3.333") = 3333/1000. Fine.

2. Line 51: `box = tuple(float(v) for v in (left, top, left + win_w, top + win_h))`. floats. Then line 52: `box_aspect = (box[2] - box[0]) / (box[3] - box[1])`. Fine.

3. Line 66: `src.resize(size, Image.LANCZOS, box=box)`. Hmm — Pillow's `Image.resize(size, resample, box=box, reducing_gap=...)`. The box parameter: "The box argument specifies the source region. ... It must be a 4-tuple of floats." Actually, when box is given, the resize is done from that region. But there's a documented gotcha: the box coordinates are in the source image's coordinate system, and the output size is `size`. So this crops the box region and resizes to `size` in one pass. Good, that matches the docstring "resamples only that window to the target size in one Lanczos pass".

But — is the box exactly the target aspect? win_w = win_h * target where win_h = sh (Fraction). So win_w = sh * tw/th. box width = win_w, box height = sh. Aspect = win_w/sh = tw/th = target. Exact. Good. And for tall: win_w = sw, win_h = sw/th*tw... wait: `win_h = win_w / target` = sw / (tw/th) = sw*th/tw. box aspect = sw / (sw*th/tw) = tw/th. Good.

4. Line 66-69: after save, re-open and check size. Good.

5. Potential bug: `src.resize(...)` with box of floats — Pillow may raise "Invalid box" if box values are out of range or NaN. left = (sw - win_w)/2. Since off_pct within tolerance, win_w <= sw, so left >= 0. Fine.

6. Line 90: `with Image.open(src) as im: src_size = im.size` — then later `bridge(src, dst, ...)` opens again. Double open, minor inefficiency, not a bug.

7. Real bug? Line 89: `raise ValueError(f"{dst} exists as {existing[0]}x{existing[1]}; not overwriting")`. Good — no overwrite.

8. Line 132: `dst = os.path.join(args.out_dir, f"{leap}_{w}x{h}.png")`. Fine.

9. Exit code: `return 1 if "REFUSED" in statuses else 0`. Hmm — if a file is SKIP or DRY, returns 0. Reasonable.

But wait: if `--final-dir` has files but all are REFUSED, returns 1. If no files, prints "NO FILES" and returns 1. Good.

10. One bug: line 124 `files = sorted(glob.glob(os.path.join(args.final_dir, PATTERN)))`. PATTERN = "LEAP-*__candidate_v01__final.png". Fine.

11. Hmm — `parse_size` uses `text.lower().split("x")`. If text = "864x1536" → ["864","1536"]. Good. If "864X1536" → lower handles. Good. If "864 x 1536" with spaces → int(" 864") works? int(" 864") → 864 (strips). int("1536 ") → 1536. Actually int() strips whitespace. So "864 x 1536".split("x") → ["864 ", " 1536"] → int ok. Fine.

12. Now — the `bridge` function: line 62-63 `with Image.open(src_path) as im: src = im.convert("RGB")`. Then line 64 `plan(src.size, size, tol_pct)`. Then line 66 `src.resize(size, Image.LANCZOS, box=box).save(dst_path, format="PNG")`. 

Wait — a subtle bug: `src.resize` returns a new image; we call `.save` on it. Fine.

But: the `box` from plan() uses floats. Pillow's resize with box requires the box to be within [0, w] x [0, h]. Since left >= 0 and left+win_w <= sw (approximately; floating point). win_w = win_h * target where win_h = Fraction(sh). Actually for the wide case: win_w = sh * tw/th. Is sh*tw/th <= sw? Since src_aspect > target means sw/sh > tw/th → sw > sh*tw/th. So yes, win_w < sw, left > 0. Good. For tall case: win_h = sw*th/tw < sh since sw/sh < tw/th → sw < sh*tw/th → sw*th/tw < sh. Good.

13. Hmm, one thing: `box_aspect` computed but never used except in the return dict. Fine.

14. Now let me think about whether `plan`'s `crop_px_removed` is meaningful: `(sw - win_w) + (sh - win_h)` — for wide case, sh - win_h = 0 (win_h = sh), so it's sw - win_w. Good.

15. Now, is there a bug where `bridge` writes to dst even when... no.

16. Actually, let me reconsider: in `_convert`, the dry-run path computes `box, _, removed = plan(src_size, size, tol_pct)` — fine, no write.

17. Potential issue: `os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)` is called in _convert before bridge(), but bridge() also doesn't create dirs. Fine.

18. Now, one thing about `Image.LANCZOS` — in newer Pillow, `Image.LANCZOS` is deprecated alias for `Image.Resampling.LANCZOS`. It still works (with deprecation warning) in Pillow 9-10, and removed in Pillow 11? Actually `Image.LANCZOS` was removed in Pillow 10? Let me think: Pillow 9.1.0 deprecated `Image.LANCZOS` in favor of `Image.Resampling.LANCZOS`. The old constants were removed in Pillow 11.0.0 (May 2024). Hmm, so if the environment has Pillow >= 11, `Image.LANCZOS` raises AttributeError. That's a real potential bug but environment-dependent. Similarly in review_shot.py there's no LANCZOS use. I'll note it as medium/low severity depending. Actually since I can't verify the environment, I'll flag it as a medium compatibility risk. Hmm, but the instruction says "Report concrete bugs only". I'll flag it as low/medium.

Actually let me be careful: the task says check "Pillow box misuse". Let me check box usage more.

In bridge(), `src.resize(size, Image.LANCZOS, box=box)` — box is a tuple of 4 floats. Pillow expects box as (left, top, right, bottom). Our box is (left, top, left+win_w, top+win_h). Correct order. Good.

One thing: Pillow's resize box semantics — when box is given, the output image is `size` and the box is the source region. But there's a subtlety: the box coordinates may need to be within the image bounds; floating point coordinates like 0.5 are fine. OK.

Hmm, actually there IS a known Pillow gotcha: when using `box` with `resize`, the resampling uses the box as the exact source area, and the output maps 1:1 to size. That's what we want. Good.

19. Let me reconsider review_shot for a real logic bug: line 178-180:
```
base = cands[0]
sheet = base.with_name(base.stem + "__neighbours.jpg")
build_sheet(job, [str(c) for c in cands], sheet)
```
What if cands[0] is a screenshot named e.g. "shot.png"? base.stem = "shot", sheet = "shot__neighbours.jpg". Fine.

20. Now — a potentially significant bug: In `review()`, the `parts` list sends the sheet + candidates. But `image_part` is called for `sheet` which was just written by build_sheet. If build_sheet wrote a JPEG, fine.

21. Now let me reconsider the `choose` "fewest ADVISORY answers wins" — line 111. `min(passed, key=...)`. If tie, first. Fine.

22. Hmm, one thing: line 112 returns `{"decision": "PASS", "chosen": best["candidate"], "label": best.get("label")}`. But `best` is a result dict which also contains "fix", "edit_instruction", etc. — but those would be "none" for a PASS. Fine.

23. Now, main() line 219: `print(f"{r['label']} {r['verdict']}  fix={r['fix']}  regen={r['regen_sentence']}  edit={r['edit_instruction']}")`. For PASS results, fix = "none", edit_instruction = None, regen_sentence = None. Fine.

24. Let me now think about whether there's a bug where `parse` could produce derived=PASS with missing answers. No — missing non-empty → UNSURE.

25. Now — an important one. Line 91: `results = [a["result"] for a in answers.values()]`. But `answers` is a dict built from regex finditer; if the same Q appears twice, the later overwrites. Fine.

26. Let me check: does the answers regex accidentally match "Q1" inside "EDIT_INSTRUCTION" or other lines? E.g., a line "A EDIT_INSTRUCTION: Change only the Q1..." — the answers regex requires `A\s+Q[1-6]\s*[:\-]`. In "A EDIT_INSTRUCTION: Change only the Q1 ..." there's no "A Q1:" pattern. But what about "A Q1" appearing in the edit instruction text? The regex is anchored `^\s*A\s+Q[1-6]\s*[:\-]` — so the line must start with "A Q1:" etc. An edit instruction line starts with "A EDIT_INSTRUCTION:". So no. Good.

But hmm — what about the REGEN_SENTENCE containing "A Q1: PASS"? Unlikely. Fine.

27. Now, let me look at a subtle issue in `parse`: line 87 the regex `^\s*{pre}(Q[1-6])\s*[:\-]\s*(PASS|BLOCK|ADVISORY|UNSURE)\b\s*[-:]?\s*(.*)$`. Consider a line "A Q1: PASS - one person". pre = "A\s+". So full: `^\s*A\s+Q[1-6]\s*[:\-]\s*(PASS|...)\b\s*[-:]?\s*(.*)$`. "A Q1: PASS - one person": `\s*` matches "", `A\s+` matches "A ", `Q[1-6]` matches "Q1", `\s*` matches "", `[:\-]` matches ":", `\s*` matches " ", `(PASS|...)` matches "PASS", `\b` ok, `\s*` matches " ", `[-:]?` matches "-", `\s*` matches " ", `(.*)` = "one person". Good.

28. Now — what about a genuine bug: line 92 `stated = fields["VERDICT"].split()[0].upper() if fields.get("VERDICT") else None`. If VERDICT line is "A VERDICT: PASS" → fields["VERDICT"] = "PASS". Good. If "A VERDICT: PASS because ..." → "PASS". Good.

29. Let me now consider the interaction: `out` in review() line 193-195 includes `"prompt_sha256": job["prompt_sha256"]`. If job lacks that key → KeyError. But job comes from the jobs file; presumably has it. Minor.

Also line 193: `"shot_id": job["shot_id"], "flow_title": job["flow_title"]` — if job lacks flow_title → KeyError. The jobs file should have it. Minor robustness.

30. Now let me reconsider the prompt's image numbering and the `full` string line 63: `full = ", ".join(f"image {k + 2} = CANDIDATE {l} at full size" for k, l in enumerate(labels))`. For 2 candidates: "image 2 = CANDIDATE A at full size, image 3 = CANDIDATE B at full size". And parts = [text, sheet, candA, candB]. So image 1 = sheet, image 2 = A, image 3 = B. Consistent. Good.

31. Now — the prompt line 66: "Image 1 is a continuity sheet, top row: ...; bottom row: the reference sheets". And build_sheet presumably constructs that. Fine, that's in neighbour_sheet.

32. Let me now think about "fail-open paths" once more specifically for the case where the model returns a valid-looking but wrong verdict. E.g., model returns "A VERDICT: PASS" and all Q answers PASS → derived PASS, stated PASS → verdict PASS → chosen. That's the model's call; advisory-only. Fine.

33. Now, one more real bug: In `call_review`, line 165: `info = {"model": sched.model, "key_used": f"key {res['key_index']}" if "key_index" in res else None, "tries": sched.snapshot()["http_attempts"]}`. If the scheduler's result dict uses a different key name for the key index... we assume "key_index". If it's absent, key_used = None. Not a bug, just informational.

But `sched.snapshot()` — does that method exist? We assume the existing scheduler has it. If not, AttributeError. Can't verify; it's the existing scheduler's API. Not our bug.

34. Hmm, let me reconsider `_Params.__call__`: `kwargs["json"] = dict(kwargs["json"], temperature=..., top_p=..., seed=..., chat_template_kwargs={"enable_thinking": True})`. If the scheduler calls post without a "json" kwarg (e.g., it builds the payload differently), this KeyErrors. But we're told the scheduler's post is used. Risk: medium? Actually the comment says "adds the fields its call() does not set (it hardcodes temperature 0.2)". So the scheduler does pass json. OK.

But there's a subtle bug: `chat_template_kwargs={"enable_thinking": True}` — for a model that doesn't support thinking, this might cause issues. But MODEL is a reasoning model. Fine.

35. Now, `strip_think`: line 132 `text = re.sub(r"</think>.*?</think>", "", text or "", flags=re.S)`. Wait — the pattern is `</think>.*?</think>` — it starts with <think>, not <think>. So it removes `<think>...</think>` blocks. But what if the model outputs `<think>reasoning</think>answer`? Pattern matches `<think>reasoning</think>` → removed → "answer". Good.

But what if the model outputs just `answer` with no tags? No match, no <think>, split → "answer". Good.

What if the model outputs `<think>a</think> b <think>c</think> d`? sub removes both → " b d"? Let's recompute: text = "a b c d" with tags: `a b c d`. Pattern `answer.*?answer` non-greedy: first match starts at first : `a ` (up to second ). Remove → " b c d". Continue scanning from after the removed portion: remaining string " b c d" → next match ` c ` (third 8 to fourth 8) → remove → " b d". Result " b d". Then no 8, split on first 8 → " b d". strip → "b d". Hmm, that keeps "b" and "d" concatenated with space. That's a weird case but unlikely. Not a bug per se.

36. Actually wait, there's a real bug in strip_think: line 133-134:
```
if "</think>" in text:
    text = text.rsplit("</think>", 1)[1]
```
After removing all `<think>...</think>` pairs, if there's still a stray 8 (unclosed think block at the end), we take everything after the last 8. But consider: model outputs `reasoning without close` (just an 8 at start, no closing). After sub (no complete pair), text = "reasoning without close". "8" not in text? Wait there IS an 8 at the start. Hmm, text = "reasoning without close" — the 8 is there. So `"8" in text` True → `text.rsplit("8", 1)[1]` = "" (nothing after the 8). So text = "". Then `text.split("8", 1)[0]` = "". strip → "". So an unclosed think block with no answer → empty → "empty reply" error → UNSURE. Good, fail-closed.

But consider: model outputs `8 reasoning 8 answer` — sub removes the pair → " answer". "8" not in " answer" → skip. split on first 8 → [" answer"]... wait " answer".split("8", 1) = [" answer"] (no 8), [0] = " answer", strip → "answer". Good.

Consider: `8a8b8c8d` (two pairs) → sub removes `8a8` and `8c8` → "b d"? Actually as computed above → "b d". Hmm wait let me redo: text = "8a8b8c8d". finditer for `8.*?8`: first match "8a8" (positions 0-3). Next search starts at position 4: "b8c8d" → match "8c8" at positions 1-4 of remaining... in original positions 5-8. So removed both → "b" + "d" = "bd"? Let me carefully: original = 8 a 8 b 8 c 8 d (chars 0..7). Match1 = chars 0..3 ("8a8"). Match2 starts searching from char 4: "b8c8d" → first "8" at char 5, non-greedy up to next "8" at char 7 → "8c8" (chars 5-7). Remove both → remaining chars: char 4 ("b"), char 8 ("d") → "bd". So result "bd". Then no 8 → split → "bd". Hmm, that merges. But this is a pathological case (model outputting multiple think blocks with no separators). Unlikely. Not worth flagging.

37. Let me now think about whether review_shot has a bug where it could output PASS when the model gave no VERDICT but all answers PASS — covered: UNSURE. Good.

38. Now, one more: `choose()` line 109-116. If `passed` non-empty → PASS. But what if a result has verdict "PASS" but the model's stated VERDICT was actually BLOCK? No — parse() ensures verdict == PASS only if derived == PASS and stated == PASS. So a result with verdict PASS genuinely has all answers PASS/ADVISORY and stated PASS. Good.

39. Now let me check bridge for a subtle aspect error bug: line 52-53:
```
box_aspect = (box[2] - box[0]) / (box[3] - box[1])
aspect_error_pct = abs(box_aspect / float(target) - 1) * 100
```
box_aspect should equal tw/th exactly (in exact arithmetic). With floats, tiny error. Reported but not used for decisions. Fine.

40. Hmm — actually, here's a potential real bug in bridge: line 66 `src.resize(size, Image.LANCZOS, box=box)`. The `box` is computed as floats, but the actual crop region in the source should be integer-aligned for a clean crop? No — Pillow handles float boxes by resampling. But the resulting image may not be *exactly* the target aspect if Pillow rounds. Actually Pillow with box resamples the box region to exactly `size`, so aspect is exact. Fine.

But wait — there's a known issue: Pillow's `resize` with `box` requires that the box be within the image. With floats like left = 0.4999..., fine.

41. Let me reconsider: is there a bug where `plan` computes `win_w` as a Fraction that, when converted to float and used as box right edge, exceeds `sw`? left = (sw - win_w)/2; right = left + win_w = (sw + win_w)/2. Since win_w < sw, right < sw. Fine. Float rounding could make right = sw + epsilon? Possibly if win_w is very close to sw. Then Pillow might complain "box out of bounds"? Actually Pillow clips or raises? I recall Pillow raises `ValueError: box out of bounds`? Hmm, not sure. It's a low-probability edge. I might mention as low.

Actually, let me check: for the wide case, win_w = sh * tw/th. off_pct <= tol means sw/sh vs tw/th within 3%. So win_w = sh*tw/th ≈ sw*(1 ± 0.03). Since src_aspect > target (wide case), sw/sh > tw/th, so win_w < sw. Margin up to 3% → left ≈ 0.015*sw. Float error tiny. Fine.

42. Now let me look for "wrong exit codes" in bridge: main returns 1 if REFUSED else 0. The docstring doesn't specify exit codes. Fine.

43. Hmm, one thing in bridge `_convert`: line 83-89 — if dst exists and size matches → SKIP. But it doesn't check whether the source has changed. Fine (idempotent).

44. Now — a real bug in bridge: line 90-91 opens src to get size, then line 97 calls bridge() which opens src again and converts. But between the size check and bridge, the file could change (TOCTOU). Minor, ignore.

45. Let me reconsider review_shot for file overwrite issues: line 180 `build_sheet(job, [str(c) for c in cands], sheet)` — sheet is a new path. But what if `base.stem + "__neighbours.jpg"` collides with a candidate file? base is a candidate, so base.stem + "__neighbours.jpg" ≠ base name. Fine.

46. Now, an important one I should double check: line 178 `base = cands[0]`. If only one candidate is passed, labels = ["A"], and the sheet includes just that one candidate. Fine.

47. Let me reconsider the `--candidate` nargs="+". In main, `a.candidate` is a list of Path. `len(a.candidate) > 2` → refused. So 1 or 2. Good.

48. Now — potential bug: `review()` accepts `candidates` as list; main passes `a.candidate` (list of Path). `cands = [Path(c) for c in candidates]` since not str/Path. Good.

49. Let me now think about whether the output JSON leaks the API key. `load_env_keys(ENV_FILE)` returns keys list, passed to make_scheduler → NvidiaScheduler. The keys are not stored in `out`. Good.

50. Hmm — but wait: line 194 `"key_used": reply["key_used"]`. And in main line 226 prints it. It's "key N". Good.

51. Now let me reconsider: is there any path where `out["choice"]` is missing? No.

52. Let me reconsider the `parse` function's handling when `fields` has VERDICT but the model wrote "VERDICT: UNSURE" while derived = BLOCK. stated = "UNSURE", derived = "BLOCK" → stated != derived → else → derived == "BLOCK" → verdict = BLOCK. Good, fail closed.

53. Now, one more consideration — the prompt says "ADVISORY ONLY: the reviewer advises, Claude and the owner decide." But the script exits 0/1/3 based on the review. That's by design.

54. Let me now look for a genuine logic bug I might have missed in `parse`: line 94 `fix = (fields.get("FIX") or "none").split()[0].lower() if fields.get("FIX") else "none"`. If fields["FIX"] = "edit" → "edit". If "regenerate" → "regenerate". If "none" → "none". If "edit something" → "edit". Good. If "EDIT" → lower → "edit". Good.

Line 95-96: if fix not in ("none","edit","regenerate") → "regenerate". Good.

55. Now, the `choose` fixes list line 114-115 includes `r["fix"]`, `r["edit_instruction"]`, `r["regen_sentence"]` for BLOCK results. Good.

56. Hmm — one thing: in `choose`, for BLOCK decision, it doesn't include a "chosen". Fine.

57. Let me now think about whether `review()` writes the report before or after parsing — line 186 writes text, then parses. Fine.

58. Now, an actual bug: line 198 `base.with_name(base.stem + "__review.json").write_text(json.dumps(out, ...))`. `out` contains `results` which include `candidate` paths, `sheet`, `report` paths — all strings. JSON-serializable. But `out["choice"]` for BLOCK contains "fixes" list of dicts with strings. Fine. `out["time"]` is ISO string. Fine.

But `out["results"][r]["answers"]` is a dict of dicts — fine.

59. Hmm — what about `out` containing `datetime`? No, converted to isoformat string. Good.

60. Let me now double-check bridge's `plan` for the case `src_aspect == target` exactly: off_pct = 0. Then src_aspect > target is False → else branch: win_w = sw, win_h = sw/target = sw*th/tw. Since src_aspect == target → sw/sh = tw/th → sh = sw*th/tw → win_h = sh. So box = (0, 0, sw, sh) — full image, just resize. Good.

61. Now, one more bridge consideration: line 66 `.save(dst_path, format="PNG")`. PNG default. Fine.

62. Let me reconsider whether bridge has a bug with `Image.LANCZOS` and `box` together: In Pillow, when both `box` and `size` are given to resize, it's equivalent to cropping the box then resizing. Actually the docs: "If box is given, the source region is first cropped to the box, then resampled to the target size." Hmm, actually I think it's: the box specifies the region of the source to sample, and the output is size. So it's a single resample from the box region to size. Correct.

But there's a documented constraint: "The box argument ... must be a 4-tuple of floats ... The box is in the source image's coordinate system." And: "When box is given, reducing_gap is ignored." Fine.

63. Now let me reconsider: is there any issue with `box` being floats and Pillow version? In Pillow < 8, box not supported. In Pillow >= 8, floats supported. Modern environments fine.

64. Let me now think about the "14-key NvidiaScheduler" — review_shot uses it. Not our concern.

65. Now, let me reconsider one potential real bug in review_shot: line 165 `info` uses `res['key_index']` — but on the *fallback* call, `res` is the second result. If the second call also is CLIENT_ERROR (e.g., fallback model also missing), then `res["status"] != "OK"` → returns error with info from the second call. Fine.

But what if the first call succeeded partially... no.

66. Hmm, actually here's a real bug: line 162 checks `res["status"] == "CLIENT_ERROR" and params.model_missing and sched.model == MODEL`. But `params.model_missing` is set inside `_Params.__call__` only when the *response* has status 400/404 and text contains "not found"/"does not exist". But `sched.call` might retry on 429 and eventually return CLIENT_ERROR with a 429 status, not 404. Then model_missing stays False → no fallback. Fine, that's correct behavior (429 is not model-not-found).

But what if the scheduler returns CLIENT_ERROR for a 404 but the response text is empty? Then model_missing stays False → no fallback → error returned → UNSURE. Acceptable.

67. Now, let me reconsider: is there a scenario where `sched.call` raises an exception (not returning a dict)? E.g., all keys exhausted → the scheduler might raise. Then review() raises → main() raises → traceback, exit 1. Should probably be caught and treated as UNSURE/refused. Hmm. But that's the scheduler's contract. I could flag as medium: uncaught exceptions from the scheduler propagate as a traceback instead of a clean UNSURE/exit 3. Let me check: `review()` line 184 `reply = call_review(parts, sched, params)` — if sched.call raises, it propagates out of review() and main() → uncaught → Python exits with 1 and prints traceback. The spec says "missing answer or empty reply must be UNSURE never PASS" — a scheduler exception isn't a missing answer, but it would be nicer to fail closed as UNSURE. I'll flag as medium.

Actually, let me reconsider: the scheduler is described as having "key rotation, 429 cooldown and retries". If all keys fail, it probably returns a status dict rather than raising. But `load_env_keys` could raise ValueError (caught in main). Network errors (requests.post raising ConnectionError) — the scheduler might or might not catch. If `_http_post = requests.post` raises ConnectionError inside the scheduler's retry loop, and the scheduler doesn't catch it, it propagates. Medium-low. I'll mention as a robustness item but maybe low severity.

68. Let me now focus and enumerate the concrete bugs I'm confident about:

For review_shot.py:
- (a) Line 165 / 171: On the fallback path, if the first call returned CLIENT_ERROR with model_missing, we switch model and retry once. But `info` is computed from the *second* res — fine. However, there's a subtle issue: if the first call's `res` had `key_index`, we ignore it. Not a bug.
- (b) Uncaught exceptions from scheduler/network → traceback instead of UNSURE. Medium.
- (c) `out` dict accesses `job["prompt_sha256"]`, `job["flow_title"]` — KeyError if missing. Low.
- (d) `image_part` doesn't handle EXIF orientation. Low.
- (e) `strip_think` edge cases — probably fine.

Hmm, are there any *concrete logic* bugs? Let me re-examine `parse` once more for a fail-open.

Actually wait. Let me re-read line 91-93 very carefully:

```python
results = [a["result"] for a in answers.values()]
derived = "BLOCK" if "BLOCK" in results else ("UNSURE" if missing or "UNSURE" in results else "PASS")
stated = fields["VERDICT"].split()[0].upper() if fields.get("VERDICT") else None
verdict = derived if stated == derived else ("BLOCK" if derived == "BLOCK" else "UNSURE")
```

Hmm, `results` is a list. `"BLOCK" in results` — checks membership of the string "BLOCK" in the list. Correct.

But wait — `answers.values()` are dicts `{"result": ..., "reason": ...}`. So `a["result"]` is a string. results is list of strings. Good.

Now, is there a case where derived = PASS but there are missing answers? No, because `missing` non-empty → UNSURE. Good.

OK so parse is fail-closed.

Let me look at `choose` again:
```python
passed = [r for r in results if r["verdict"] == "PASS"]
if passed:
    best = min(passed, key=lambda r: sum(a["result"] == "ADVISORY" for a in r["answers"].values()))
    return {"decision": "PASS", "chosen": best["candidate"], "label": best.get("label")}
```
Fine.

Now — here's a thought: what if `results` is empty? In review(), results always has one entry per candidate (labels non-empty since cands non-empty, and main ensures 1-2). So fine.

Let me look at main line 229 again: `return {"PASS": 0, "BLOCK": 1}.get(out["choice"]["decision"], 3)`. If decision is "UNSURE" → 3. Good.

Hmm, what about the case where `out["choice"]["decision"] == "BLOCK"` → exit 1. Docstring: "1 BLOCK (fix)". Good.

Now let me look for something else: the docstring says "Writes <A>__review.json (+ the sheet and the raw report)." Line 198 writes `base.stem + "__review.json"`. If candidate A is "A.png", base.stem = "A", so "A__review.json". Matches "<A>__review.json" if <A> is the candidate label... well, it's base.stem. Fine.

Now, one more: line 181 `report = base.with_name(base.stem + "__review.md")`. Good.

Let me now check bridge_flow_to_h3 more carefully for a concrete bug.

Line 66: `src.resize(size, Image.LANCZOS, box=box).save(dst_path, format="PNG")`.

Hmm — actually here's a real issue: `box` is a tuple of Python floats. Pillow's resize `box` parameter expects a tuple. But there's a subtlety: when `box` is provided, Pillow requires that the box defines a region whose aspect ratio... no, it resamples to `size` regardless. Fine.

But wait — is there a bug where the box is computed in *source* pixel coordinates but the resize's box should be relative to something? No, it's absolute source coordinates. Correct.

Let me reconsider: `plan` returns box with floats like (left, top, right, bottom). For the wide case: box = (left, 0, left+win_w, sh). top = (sh - win_h)/2 = (sh - sh)/2 = 0. So box = (left, 0.0, left+win_w, sh). Good.

Hmm, `top` = (sh - win_h)/2 where win_h = Fraction(sh) → 0. As float 0.0. Good.

Now — a potential real bug: line 54 `crop_px_removed = round(float((sw - win_w) + (sh - win_h)), 3)`. For wide case: sw - win_w (positive) + 0. Good.

Now let me reconsider the exit code semantics in bridge. The docstring doesn't specify. main returns 0 on all-OK/SKIP/DRY, 1 on any REFUSED or no files. Reasonable.

Hmm, one thing: `return 1 if "REFUSED" in statuses else 0` — if statuses is empty? Only if files empty, handled earlier (returns 1). With --src, statuses has one element. Fine.

Now let me reconsider: is there a bug where `_convert` with `--dry-run` still calls `os.makedirs`? No — dry_run returns before makedirs. Good. Line 93-95: if dry_run → print and return "DRY". Good, no write.

Now, let me reconsider the `SKIP` logic: line 83-89: if dst exists and size matches → SKIP. But it opens dst with Image.open — if dst is corrupt, raises OSError → caught → REFUSED. Fine.

Now, a real bug: line 89 `raise ValueError(f"{dst} exists as {existing[0]}x{existing[1]}; not overwriting")` — this is inside the `try` that catches `(ValueError, OSError)`. So it's caught and printed as REFUSED. Good — no silent overwrite.

Hmm OK. Let me now consider whether bridge has a bug where it overwrites: no, explicit check.

Let me now think about whether `bridge()` itself could overwrite: it's only called after the exists-check in `_convert`, and it raises if src==dst. Good.

Now let me reconsider review_shot for a subtle issue with the scheduler and the `_Params` wrapper: line 146 `kwargs["json"] = dict(kwargs["json"], temperature=TEMPERATURE, top_p=TOP_P, seed=SEED, chat_template_kwargs={"enable_thinking": True})`. This mutates the kwargs dict passed by the scheduler. Fine.

But — `seed=108` and `temperature=0.0`. Some APIs reject seed with temperature 0? Unlikely. Fine.

Now, `MAX_TOKENS = 4096`. The reasoning model with enable_thinking=True may use many tokens for reasoning; 4096 total may be too small, leading to truncated output → strip_think returns whatever's after 8, possibly incomplete → parse may find missing answers → UNSURE. That's a tuning issue, not a bug. But it could cause frequent UNSURE. Hmm. Actually the comment in strip_think mentions "reasoning may have used max_tokens". So it's acknowledged. Not a bug.

Let me now think about whether there's a bug in how `call_review` handles the fallback: line 162-164:
```python
if res["status"] == "CLIENT_ERROR" and params.model_missing and sched.model == MODEL:
    sched.model, params.model_missing = FALLBACK_MODEL, False
    res = sched.call(parts, max_tokens=MAX_TOKENS)
```
After this, `res` is the new result. Then line 165 info uses new res. Good. But note: if the fallback call also triggers model_missing (fallback model not found), params.model_missing is set True again, but sched.model != MODEL so no further fallback. Good — no loop.

Now, here's a subtle thing: `sched.model` is set to FALLBACK_MODEL. But does the scheduler's `call` use `self.model`? Presumably. And the scheduler's key rotation is independent of model. Fine.

Now let me reconsider: is there a bug where `reply` in review() might not have "model"? call_review always returns a dict with "model" (in info). Even error path: `return {"error": ..., **info}` where info has "model". Good. So line 194 `reply["model"]` safe. And `reply["key_used"]`, `reply["tries"]` safe.

Wait — line 194: `"model": reply["model"], "key_used": reply["key_used"], "tries": reply["tries"]`. If reply is the error dict from call_review, it has these. Good.

But hold on — line 185 `text = reply.get("text") or ""`. On error path, reply has no "text" → "". Good.

Now, one more: line 196-197:
```python
if reply.get("error"):
    out["error"] = reply["error"]
```
Good.

Now, let me reconsider whether there's a fail-open in `choose` when results contain a mix: e.g., result A = PASS, result B = UNSURE. passed = [A] → decision PASS, chosen A. Is that correct? The spec: "Only a PASS can be kept." So if one candidate PASSes and the other is UNSURE, we keep the PASS one. That seems intended. But hmm — "a missing answer, a missing verdict or a verdict contradicting the