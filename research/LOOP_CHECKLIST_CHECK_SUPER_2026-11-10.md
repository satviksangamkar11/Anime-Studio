# Nemotron Super check of the loop checklist

FINDINGS
- Contradiction: coder model. Header/C.2 name Nemotron Super; facts refuse coder_model unless Ultra today. Fix: replace `coder = Nemotron Super (nvidia/nemotron-3.5-super-vl-120b-a12b, the best Nemotron model, also the checklist checker)` with `coder = Ultra today (Nemotron Super refused unless Ultra is coder_model today)`. Replace `2. Coder Super writes module + tests (round 0).` with `2. Coder (Ultra today) writes module + tests (round 0); Nemotron Super only if Ultra is available, thinking OFF; spec input ~10 KB.`
- Contradiction: A3 allow-list. Fix: replace `allow-list of two coder models, Super thinking OFF` with `coder_model = Ultra today; if Ultra is unavailable, no loop coding runs (Nemotron Super is refused unless Ultra). Super thinking OFF if used`.
- Contradiction: A5 no Colab/no paid call vs W7 run_colab_batch. Fix: replace W7 with `W7 run_colab_batch: runner_safety (stop only after verified clips; dead-man; pre-flight); dry-run only, --go forbidden, no paid call, no Colab.`
- Missing exit 1 handling in E. Fix: add to E: `exit 1 (review-open/test-review-open/invalid-spec): return job to coder/spec owner; do not advance.`
- Missing spec path/owner and frozen-test edit rule. Fix: replace C.1 with `1. Spec file per job at _loop/<job>/spec.md with: purpose, public functions + signatures, edge cases, "no network, no GPU", test list from section B; owner = checklist checker.` Replace C.4 with `4. Fix rounds with real pytest output; tests frozen after round 0 — fix rounds may edit only the module, never the test file.`
- Missing claim step for parallel jobs. Fix: add to C as step 0: `0. Claim files in pieces/p1_claims.py; abort on claim conflict (exit 4).`
- J1 scope too big for one whole-file coder reply. Split J1 into J1a `director/timeline_lock_core.py` (build lock, edit_frames, bar/beat candidates, H3 lattice 17n+5, sha256 of inputs) and J1b `director/timeline_lock_io.py` (load/verify; stale hash raises).
- J8 is not a loop job but sits in B; overlaps W6/W7 on build_h3_batch.py/run_colab_batch.py and duplicates J4 compiler fixes. Fix: delete J8 row from B; add pre-B: `J8 (pre-loop, owner/git, not a loop job; supervisor inspects only): port build_h3_batch.py + run_colab_batch.py + tests from v4; apply rule-34 compiler fixes into merge tree (existing compiler file only; do not touch h3/prompt_hygiene.py); keep merge versions of shared files.`
- Vague acceptance criteria. Fixes: J1a `pick fewer spare frames` -> `pick the candidate with fewer spare frames (bar-length vs beat-from-act-start)`; J5 `owner-approved flag set` -> `owner-approved flag set (env SHOT_MODE_S_ALLOW=1)`; J6 `dead-man seconds = estimate*1.5` -> `dead-man seconds = clip_duration_estimate*1.5`; J6 `wheel hash check` -> `wheel hash check for chumpy wheel (repo commit or absolute path D:/aai work/vendor/chumpy_0.71 per owner decision)`; J7 `reuse tools/secret_scan.py` -> `reuse tools/secret_scan.py (create it if missing)`; J3 `same word count check` -> `same word count check between spoken_text and caption_text`; J4 `auto cast line` -> `auto cast line (format CAST: <character>).`
- D names Haiku medium coders (not in facts). Fix: replace `or Haiku medium coders reviewed by Haiku high + Codex` with `or Haiku HIGH coder reviewed by Codex luna.`
- G omits J8. Fix: add to G: `J8 pre-loop port complete and merged.`
- C.7 vague suite timing. Fix: replace C.7 with `7. Copy into anime_studio_merge; run the real suites (director, h3, core, flow, ui) after all J1-J7 pass and after each wiring edit W1-W9; commit on a branch.`
- W5 covers two files vaguely. Fix: replace W5 with `W5a compile_h3_sing8: call prompt_hygiene` and `W5b v4_to_h3: call prompt_hygiene.`
- Missing rate-limit coordination for 14-key ledger. Fix: add to A5: `serialize all loop calls through the shared key ledger; <=10 calls/key/min; 60 s cooldown on 429.`

SPLIT / MERGE / REORDER
- Split J1 into J1a + J1b (scope too big for one whole-file coder reply).
- Split W5 into W5a + W5b (two files).
- Delete J8 from B; move to pre-loop owner/git task (reorder before B, not a loop job).
- No merges needed.

5 MOST LIKELY FAILURES
1. Coder refused: Nemotron Super is not Ultra today, so round 0 never starts.
2. Claim conflict (exit 4): J8/W6/W7 overlap on build_h3_batch.py/run_colab_batch.py or parallel jobs write unclaimed files.
3. J1 too large for one whole-file reply: invalid spec or incomplete module, stuck at exit 1.
4. W7 run_colab_batch breaches A5 (no Colab/paid call), triggering stop condition.
5. Exit 1 (review-open/test-review-open/invalid-spec) is not in supervisor actions, so jobs stall forever.
