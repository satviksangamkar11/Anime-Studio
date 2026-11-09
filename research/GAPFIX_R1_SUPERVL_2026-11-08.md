# GAPFIX R1 (supervl) 11-08 02:57

Brief review: R2/R5 now match the stated spec (inversion corrected), `caption_cues` list-of-cards is consistent with `timeline`'s dict-of-lang→cards handling, and the story_state/write_pack/sheet/pack_to_spec/remove_sparkle/UI packet/step-recording edits are internally consistent. The one concrete defect I can confirm from the diff is `coversAll` omitting the `B` frame job. Several other items are plausible but not verifiable from the diff alone (they depend on unseen function bodies/imports/signatures), so I flag them as `possible` with what to check rather than report them as confirmed bugs.

Concrete finding:

medium | ui/static/pipeline.js:2138 (coversAll) | `coversAll` treats a pack shot as covered only by an exact id or `id + 'A'`, never `id + 'B'`; input: jobs contain only `SHOT-001B` for shot `SHOT-001` → `coversAll(have, ["SHOT-001"])` returns `false` although a frame job exists, so the UI wrongly reports the shot incomplete and can block completion/render. | Fix: `return have[id] === true || have[id + 'A'] === true || have[id + 'B'] === true;`

Possible findings (verify before treating as bugs):

possible | director/write_pack.py:run_staged (~line 378) | the 5e per-episode branch calls `apply_captions(ep_shots, captions["captions"], langs)` and discards the result, then merges unmodified `ep_shots`; if `apply_captions` returns new shot rows (as the single-stage-5 path assumes by assigning its return), captions are silently dropped from `shots.json` for 5e packs. | Fix: assign the result back (`ep_shots = apply_captions(...)`); first check whether `apply_captions` mutates its shot dicts in place.

possible | h3/v4_to_h3.py:~544 (metadata look) | `copy.deepcopy(row["look"])` is used but the diff adds no `import copy`; if the module does not already import `copy`, converting a pack whose shot carries a `look` dict raises `NameError`. | Fix: add `import copy`; verify the module's import block.

possible | flow/scripts/pack_to_spec.py:~560 (OUTPUTS_ROOT_TEMPLATE) | hardcodes `D:/aai work/flow_outputs/anime_{slug}` and claims it equals `ui flow_root(story)`; if `flow_root` resolves elsewhere or the host is not Windows, specs/jobs land in a folder the UI/bridge won't scan. | Fix: derive the root from `flow_root(cfg, slug)`; verify `flow_root`'s return value.

possible | ui/server.py:_convert_pack_to_h3 (~line 764) | calls `v4_to_h3.convert_pack(str(pack_dir), languages=langs)` but the patch does not change `convert_pack`'s signature; if `convert_pack` does not accept `languages`, the uncaught `TypeError` crashes the pack→H3 API call (only `OSError`/`ValueError`/`KeyError` are caught). | Fix: add a `languages` parameter to `convert_pack` (or drop the kwarg); verify its signature.

FINAL: high: 0, medium: 1, low: 0
