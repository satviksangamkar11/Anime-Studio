# Director v2.2 spec (2026-11-04): shared contracts for every module

Goal: a complete system that turns any story into ALL raw material for images, video and sound, directed as
**Indian epic culture and expressive acting x modern Japanese anime choreography, cinematography, 2.5D depth and compositing**,
using any model through three paths (Claude CLI, NVIDIA build API, OpenRouter free models). Shot count and reel count come from the story.
Source: the owner's audit of commit db2fbb1 (missing: Indian visual language, anime animation direction, visual acceptance).

## Files (one owner each; nobody edits another's files)
| File | Owner | Purpose |
|---|---|---|
| shot_schema.py | A | the rich shot contract below: `validate_shot(shot) -> list[str]` problems, `validate_shots(shots)` adds cross-shot checks |
| layout_validator.py | A | `check_layout(shots) -> list[str]`: screen direction (180-degree rule), eyelines, character/prop positions, cut types, state hand-off (shot N end_state == shot N+1 start_state) |
| h3_director.py | A | `settings_for(shot)` accepts BOTH the old flat shot and the rich shot; a rich shot is COMPILED into the H3 prompt (beats with time codes, poses, secondary motion, camera, light) and the full rich spec is kept next to the settings as `<id>.direction.json` |
| check_pack.py | A | adds: every shot has acting beats, poses, camera, layers, continuity; reports missing fields per shot |
| style_bible.py | B | structured, reusable Indian-anime visual language (below); `load(project)`, `prompt_block(entity_id)` returns the locked text used in Flow and H3 prompts |
| acting_library.py | B | bhava -> acting progression library (below); `progression(bhava, character)` returns ordered beats (eyes -> face -> head -> hands -> torso -> full body -> cloth follow-through) |
| MASTER_PROMPT_v2.2.md | B | the brief: v2.1 + Indian design rules + anime direction rules + the rich shot contract; output split by gate (see writer) |
| write_pack.py | C | staged mode: one call per gate (gate 1, 2, 3+4 per episode, 5), each saved before the next, any path/model per gate; the old single-call mode stays |
| visual_qa.py | C | frame review: QA sheet + rubric (below) scored by a vision model through any path, or by hand; writes `<clip>_visual_qa.json` |
| tests | each owner | `test_<module>.py` next to the module; no network, no model call in tests |

## Rich shot contract (JSON, one object per shot)
```json
{"id": "SHOT-07", "episode": 2, "scene": "kadamba_leap", "mode": "fl2va", "seconds": 5.2, "aspect": "9:16",
 "purpose": "why this shot exists (story or emotion), one line",
 "cast": [{"id": "CHAR-KRISHNA", "screen": "center", "facing": "right", "start_pose": "POSE-crouch-branch", "end_pose": "POSE-dive"}],
 "props": [{"id": "PROP-KALI-KAMLI", "where": "tied at waist"}],
 "set": "ENV-KADAMBA-BANK",
 "beats": [{"t": [0.0, 0.8], "acting": "bare foot grips the branch, hand tightens on bark, gaze settles on the river", "bhava": "resolve"},
           {"t": [0.8, 1.6], "acting": "lowers centre of gravity, knees bend, shoulders tilt forward", "secondary": "sash still settling"}],
 "camera": {"move": "track down with the fall", "lens_mm": 24, "height": "branch level", "start_framing": "full body", "end_framing": "water surface"},
 "layers": {"fg": "kadamba leaves, out of focus", "mid": "Krishna (cel)", "bg": "painted river and far bank", "fx": "splash sheet, composited"},
 "light": {"key": "low morning sun from screen left", "rim": "warm gold on Krishna", "mood": "earthy Braj daylight"},
 "compositing": {"generated": "character motion + splash", "held": "background plate", "post": "on-2s holds, impact frame at 4.1s"},
 "start_state": "Krishna crouched on the high branch, facing river (screen right)",
 "end_state": "white water sheet rising where Krishna entered",
 "cut_in": "match on action from SHOT-06", "cut_out": "splash wipe into SHOT-08",
 "keyframes": {"start": "keyframes/SHOT-07-FRAME-A.png", "end": "keyframes/SHOT-07-FRAME-B.png"},
 "refs": [], "subjects": [],
 "sound": "branch creak, wind, splash (no dialogue words)",
 "dialogue": [{"who": "SHRIDAMA", "t": [0.2, 1.4], "line_hi": "नहीं-नहीं लाला!", "line_en": "No, no, Lala!"}]}
```
Rules: beats cover 0..seconds without gaps or overlap; at most ONE primary action per shot (other beats are anticipation, follow-through, reaction or hold); every cast id, prop id and set id exists in the style bible; facing/screen follow the layout rules; `refs`/`subjects` required for mode ref2va; a hold beat must say its emotional purpose.

## Style bible content (style_bible.py data, JSON-serialisable)
Per project: `palette` (Braj daylight earth tones, cloth and ornament colours, scene-motivated divine light; hex), `line` (weights, colour), `shading` (tones), `rim_light` rules (when allowed, never constant neon), and entities:
- CHARACTERS: proportions in heads (child 5-6, adult 7-7.5, elderly), silhouette markers, skin treatment (Krishna: deep cloud-blue, NOT a generic anime protagonist painted blue), eyes (shape, iris layers), hair, costume pieces + physics (dhoti, pitambara, uttariya, veils, hair ornaments, jewellery: how each reacts to running, wind, water, turning), recurring attributes, forbidden drift.
- ENVIRONMENTS: Braj geography (cowherd settlement, forest, kadamba, Yamuna, banks, vegetation), day/night keys, pictorial composition borrowed from Indian painting (high horizon, flat colour fields, layered depth) translated into 2.5D layers.
- ICONOGRAPHY: identity rules, symbol use, restrictions on invented supernatural effects.
- REFERENCES: each entry lists its sources (museum or text URL + what it shows); mark UNVERIFIED when not checked.
Ship one project file: `style/kaliya_mardan.json`.

## Acting library content (acting_library.py)
Bhavas at least: affection, mischief, maternal anxiety, anger, courage, surrender, compassion, devotion, fear, wonder, grief, relief, playful defeat.
Each: ordered progression (eyes, brows, mouth, head, breath, hands, torso, full body, cloth/hair follow-through) with typical timing in seconds; everyday gestures vs classical mudras (a mudra only with narrative purpose); character overrides (child Krishna, Yashoda, Balarama, Kaliya).

## Visual QA rubric (visual_qa.py), each 0-2 with a one-line reason
indian_identity (costume, ornaments, setting read as Braj), character_consistency (matches the sheet), proportions, line_art_intact, acting_reads (the beat's bhava is visible), motion_has_weight (anticipation, follow-through), staging_readable (silhouette, screen direction), light_motivated (no glow hiding the performance), continuity (start/end state). Accept = no 0 and total >= 14 of 18.

## Writer stages (write_pack.py staged mode)
Gate 1 (story autopsy + scene list + episode split chosen from the story) -> Gate 2 (style bible JSON + Flow sheet prompts + acting notes) -> Gates 3+4 per episode (rich shots JSON + Flow Frame_A prompt + Frame_B edit per shot) -> Gate 5 (sound/caption/QA). Each stage gets the earlier stages' saved output as input, saves `stage_<n>_raw.json` before parsing, and can use its own `--via/--model` per stage.
