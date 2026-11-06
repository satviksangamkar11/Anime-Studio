

# BATCH u1_server (dots) 11-07 03:05



## Findings

**1. Medium — server.py:1792‑1799 (Host/Origin guard gap)**  
The `_guard` method only checks the `Origin` header when it is present. A POST request that omits `Origin` (e.g., from a non‑browser client or a malicious local app) bypasses the origin check entirely. The only remaining protection is the `X‑UI: 1` header, which is a static, easily guessed value.  
**Failing input:** `curl -X POST -H "X-UI: 1" http://127.0.0.1:8765/api/run -d '{"token":"abc123"}'` (no `Origin` header) → 200 OK.  
**Fix:** Require a valid `Origin` header for all POST requests and reject the request if it is missing or not in the allowed set.

**2. Medium — server.py:1660‑1670 (Race condition in gate approval)**  
`pipeline_gate` calls `pl.apply_gate` without holding the server‑wide `api.lock`. Two concurrent POST requests to `/api/pipeline/gate` can read the same pipeline state, both write to `approvals.jsonl`, and return inconsistent results. The file append itself is atomic, but the read‑modify‑write cycle is not serialised.  
**Failing input:** Two browser tabs submit a gate decision at the same time; the second response may not reflect the first decision.  
**Fix:** Acquire `api.lock` (or a dedicated gate lock) for the whole `apply_gate` call.

**3. Low — server.py:1695‑1696 (Contract mismatch: `/api/author/status` ignores `story`)**  
The UI contract addendum specifies `GET /api/author/status?story=&pack=`, but the dispatch only passes `q.get("pack","")` to `api.author_status`. The `story` parameter is silently dropped.  
**Failing input:** `GET /api/author/status?story=my-story&pack=mypack` → server tries to find a pack named `mypack` (without the story folder) and returns 404.  
**Fix:** Accept and validate the `story` query parameter, or update the contract to remove it.

**4. Low — server.py:1438‑1450 (Author status does not cross‑check story/pack)**  
Even when the full pack path is supplied, `author_status` does not verify that the pack actually belongs to the given story. A UI that sends `story=foo` and `pack=stories/bar/baz` (where `bar ≠ foo`) will get a valid response for the wrong story.  
**Failing input:** `GET /api/author/status?story=foo&pack=stories/bar/baz` → returns the author status for `stories/bar/baz` even though the story is `foo`.  
**Fix:** In `author_status`, validate that the slug extracted from the pack path matches the `story` parameter (if supplied).

**5. Low — server.py:1521‑1531 (Hard‑coded paths in `results_roots` ignore root overrides)**  
For the legacy Kaliya story, `results_roots` appends `director/t0_pack/results` and `colab_batches` sub‑folders using `cfg.studio`. If the owner starts the server with `--root-override studio=...`, these paths are still resolved under the new studio root, which may not exist or may point to wrong data.  
**Failing input:** `--root-override studio=/tmp/fake` → `/api/export?reel=1&story=kaliya_mardan&pack=...` looks for clips in `/tmp/fake/director/t0_pack/results` instead of the real studio.  
**Fix:** Resolve these legacy paths relative to the original studio root (or the `--root-override` value if explicitly intended), and document the behaviour.

---

FINAL:
1. Medium – server.py:1792‑1799 – Origin header check is optional; POST without Origin bypasses CSRF protection.
2. Medium – server.py:1660‑1670 – `pipeline_gate` has no locking, allowing race conditions in gate approval.
3. Low – server.py:1695‑1696 – `GET /api/author/status` ignores the `story` query parameter, contradicting the contract.
4. Low – server.py:1438‑1450 – `author_status` does not verify that the pack belongs to the given story.
5. Low – server.py:1521‑1531 – `results_roots` hard‑codes legacy paths that ignore `--root-override studio`.
