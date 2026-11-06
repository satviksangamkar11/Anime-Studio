"""The V4 writer prompts (owner master prompt V4, 2026-11-07; contract research/H3_V4_CONTRACT_2026-11-07.md).

A staged prompt is: the v2.2 brief (write_pack reads it) + OVERRIDE + RULES + the stage text built here + any validation
errors of a repair retry. Every number comes from h3/shot_table_spec.py (imported, never copied). Pure text builders:
no I/O, no model call."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]               # the anime_studio folder: it holds the h3 package
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from h3 import shot_table_spec as spec  # noqa: E402

STAGES = ("1", "2", "3", "5")                            # gate numbers; stage 3 runs once per episode ("3e1", "3e2" ...)

CHECK_TEXT = {   # the six red-line story checks (owner master prompt V4, section 2.2)
    "active_protagonist": "the protagonist actively drives the plot",
    "crisis_from_flaw": "the crisis is made worse by the protagonist's own flaw or inner tension",
    "no_coincidence_resolution": "a coincidence never solves the problem",
    "ending_reuses_emotional_anchor": "the ending reuses an earlier emotional or visual anchor",
    "non_flat_antagonistic_pressure": "the antagonist's pressure is not a flat villain",
    "dialogue_shows_relationship_change": "dialogue or narration shows a change of relationship or state, not the theme",
}

STYLE_LOCK = {   # the 2D anime lock (never the 3D Pixar / C4D / Octane default of the 3d-animation-short-generator)
    "medium": "2D hand-drawn cel-shaded anime",
    "proportions": "Indian classical Puranic facial proportions",
    "line": "organic hand-drawn line weight with a frame-by-frame cel redraw feel",
}
# banned looks live OUTSIDE style_lock: the validator scans every string under a style key for these words
FORBIDDEN_LOOKS = ["3D CG", "Pixar look", "Cinema 4D", "Octane render", "uniform vector lines", "smooth neon plastic skin"]

# the output language of the story (--out-lang): narration, dialogue and captions. The structural parts stay English.
OUT_LANGS = ("en", "hi", "mr")
DEFAULT_OUT_LANG = "hi"
LANG_RULE = {
    "en": {"name": "English", "example": "The lamp was lit at night.",
           "rule": "plain everyday spoken English, the way people talk at home: short sentences, no literary or formal words "
                   "(no 'thus', 'henceforth', 'whereupon'). Captions in the same plain English."},
    "hi": {"name": "Hindi", "example": "रात में दीया जला।",
           "rule": "simple everyday spoken Hindi (बोलचाल की सरल हिंदी), the way a grandmother speaks: no stiff literary verbs, no "
                   "Sanskrit words outside a quoted verse."},
    "mr": {"name": "Marathi", "example": "रात्री दिवा लावला.",
           "rule": "simple everyday spoken Marathi (बोलचालची साधी मराठी): Marathi words and Marathi postpositions (ला, ने, चा, ची, चे, "
                   "मध्ये, साठी, पासून) only, no Hindi words, no stiff literary verbs, no Sanskrit words outside a quoted verse."},
}


CAPTION_EXAMPLE = {"en": "The lamp is lit.", "hi": "दीया जला।", "mr": "दिवा लावला."}


def lang_rule(lang):
    if lang not in LANG_RULE:
        raise ValueError(f"out-lang must be one of {', '.join(OUT_LANGS)}, got {lang!r}")
    return LANG_RULE[lang]


def parse_langs(text):
    """--out-lang: 'en', 'hi', 'mr', a comma list in priority order ('en,hi'), or 'all' (= en,hi,mr). The first is the primary.
    Raises ValueError for an unknown code, a repeated code or an empty list."""
    text = (text or "").strip().lower()
    if text == "all":
        return list(OUT_LANGS)
    codes = [c.strip() for c in text.split(",")]
    if not text or any(not c for c in codes):
        raise ValueError(f"out-lang needs one or more of {', '.join(OUT_LANGS)} (comma list) or 'all', got {text!r}")
    for code in codes:
        if code not in LANG_RULE:
            raise ValueError(f"out-lang must be one of {', '.join(OUT_LANGS)} or 'all', got {code!r}")
    if len(set(codes)) != len(codes):
        raise ValueError(f"out-lang lists a language twice: {text!r}")
    return codes


def lang_list(langs):
    """A list of language codes from one code or a list; validated."""
    langs = [langs] if isinstance(langs, str) else list(langs or [DEFAULT_OUT_LANG])
    for code in langs:
        lang_rule(code)
    if not langs or len(set(langs)) != len(langs):
        raise ValueError(f"output languages must be a non-empty list of distinct codes, got {langs!r}")
    return langs


def multi(langs):
    return len(lang_list(langs)) > 1


def languages_clause(langs):
    """The names and rules of the output languages, in priority order (the first is primary)."""
    langs = lang_list(langs)
    return "; ".join(f"{c} = {LANG_RULE[c]['name']} ({LANG_RULE[c]['rule']})" for c in langs)


OVERRIDE = """## V4 OVERRIDE (owner master prompt V4, 2026-11-07)
The brief above is the v2.2 writer brief. Where it differs from the text below, the text below wins: the rich shot object of
section (c), the staged-output rules of section (d) (including the Gate 1 "no JSON fence" rule) and the video-model limits are
replaced by the V4 rules and the V4 stage outputs. Answer in the stage format given at the end, with nothing else added."""


def rules_block(langs=DEFAULT_OUT_LANG):
    lo, hi = spec.STUDIO_REEL_RANGE
    langs = lang_list(langs)
    if multi(langs):
        language_rule = (f"7. Output languages, primary first: {', '.join(langs)}. Every narration line, dialogue line and caption is "
                         f"written in EACH of them, each in simple everyday language of that language: {languages_clause(langs)}. "
                         f"The same shot carries the same timing in every language. Structural text (ids, stage names, field names) stays English.")
    else:
        language = lang_rule(langs[0])
        language_rule = (f"7. Output language: {language['name']} ({langs[0]}). Every narration line, dialogue line and caption is "
                         f"{language['rule']} Structural text (ids, stage names, field names) stays English.")
    short, long_ = spec.lattice(spec.LATTICE_N_MIN), spec.lattice(spec.LATTICE_N_MAX)
    return f"""## V4 RULES (every stage)
1. Story spine. One active protagonist drives the plot. The crisis grows out of the protagonist's own flaw or inner tension.
   A coincidence never solves the problem. The ending reuses an earlier emotional or visual anchor. The antagonist's pressure
   is never a flat villain. Dialogue and narration show a change of relationship or state; they never explain the theme.
2. Reels. The studio reel preset is {lo:.1f} to {hi:.1f} seconds per episode (one episode = one reel). Duration buckets: {", ".join(spec.DURATION_BUCKETS)}.
3. Frame lattice at {spec.FPS} fps. Every shot has lattice n from {spec.LATTICE_N_MIN} to {spec.LATTICE_N_MAX}: pixel_frames = 5 + 17n and
   latent_slots = 5n + 2. n={short['n']} gives {short['pixel_frames']} frames ({short['seconds']:.2f} s); n={long_['n']} gives {long_['pixel_frames']} frames
   ({long_['seconds']:.2f} s). Editorial duration is at most {spec.MAX_SHOT_SEC:.1f} s and never longer than pixel_frames / {spec.FPS}.
4. Style lock. 2D hand-drawn cel-shaded anime with organic hand-drawn line weight, a frame-by-frame cel redraw feel and Indian
   classical Puranic facial proportions. Never 3D CG, never the Pixar, Cinema 4D or Octane look, no uniform vector lines,
   no smooth plastic skin.
5. No speech in H3. H3 prompts carry no speaker ids such as (S1), no [Language] tags, no <d> tags and no <Audio N> tags. Narration
   and dialogue are text for the ElevenLabs voice, made outside H3. narrator_mouth_closed is true on every shot and every
   second of mouth_state is "closed" or "open_non_verbal_breath". Non-diegetic music is N/A on every shot.
6. No on-screen text. No quoted on-screen text. No storyboard tags ([char:], [scene:], [shot:], [dur:], [hook:]), no Flow chips
   (@CHAR-, SHEET-, ENV-, STYLE-) and no panel labels in any text that becomes an H3 prompt. Ids are JSON keys, never screen text.
{language_rule}
   A caption card has at most {spec.CAPTION['max_words']} words.
8. Characters. At most {spec.MAX_CHARS_PER_SHOT} significant characters in a shot. Use only ids that exist in the Stage 2 bible."""


def _bible_example():
    return {
        "style_lock": dict(STYLE_LOCK, prefix="2D hand-drawn cel-shaded anime, Indian classical Puranic proportions, organic line weight."),
        "forbidden_looks": FORBIDDEN_LOOKS,
        "characters": {"CHAR-RAJ": {"name": "Raj", "role": "protagonist", "description": "...",
                                    "sheet_prompt": "16:9 labeled turnaround, expression and prop sheet on a plain neutral backdrop",
                                    "aspect": "16:9", "backdrop": "plain neutral"}},
        "environments": {"ENV-HALL": {"name": "Teak hall", "description": "...",
                                      "continuity_landmarks": ["carved teak door on the left wall", "brass lamp on the low table",
                                                               "window with blue shutters at the back"],
                                      "lighting_baseline": {"key": "warm lamp light from the right", "fill": "soft cool light from the window",
                                                            "rim": "thin cool edge light", "shot_modifiers": "none"},
                                      "card_prompt": "empty environment plate: architecture, nature and light only; nothing living in frame"}},
        "props": {"PROP-LAMP": {"name": "Brass lamp", "description": "...", "card_prompt": "single brass lamp on a plain neutral backdrop"}},
    }


def stage1_text():
    checks = "\n".join(f"   - {name}: {CHECK_TEXT[name]}" for name in spec.STORY_GATE_CHECKS)
    example = {"story_gate_checks": {name: {"pass": True, "evidence": "one sentence quoting the spine line"}
                                     for name in spec.STORY_GATE_CHECKS},
               "duration_bucket": "60-90", "reel_seconds": 68.0,
               "episodes": [{"episode": 1, "title": "...", "seconds": 68.0}]}
    return f"""Stage 1 only: write the story spine, the six gate checks and the reel plan. Markdown first, then one block.
a) The story spine: the protagonist, the want, the flaw, the crisis, three to five turning points, and the ending anchor (the earlier
   image or feeling that the ending reuses).
b) Gate checks: judge the spine against each of the six checks below. Each check gets pass (true or false) and evidence (one
   sentence that quotes the spine line that proves it). If a check fails, fix the spine before you answer.
{checks}
c) The reel plan: the duration bucket and reel_seconds. The studio preset is {spec.STUDIO_REEL_RANGE[0]:.1f} to {spec.STUDIO_REEL_RANGE[1]:.1f} seconds
   per episode; use it unless the owner asked for another length.
d) The episode split: one line per episode, 'Episode N: title'.
End with exactly one ```json story block holding one JSON object of this shape (all six checks, every episode):
```json story
{json.dumps(example, ensure_ascii=False, indent=1)}
```"""


def _voice_bible_text(langs, en_h3):
    """Stage 2 voice rules: voice_map for every output language (ElevenLabs by default); the speaker map and anchors only
    when English speech is H3 (en = h3, the off-by-default second render)."""
    text = (f"- \"voice_map\": {{character id or NARRATOR: {{language: voice id}}}}. One fixed voice id per character per output language "
            f"({languages_clause(langs)}): an ElevenLabs id or a placeholder name the owner replaces later. NARRATOR is the off-screen "
            "narrator and needs an id in every language too. The same id is used in every shot and reel. The voices are added after "
            "the render; the video carries no speech.\n")
    if en_h3:
        text += ("- \"voice_speaker_map\": {\"S1\": \"CHAR-*\", ...}. English speech only (en = h3). One stable id per speaking character, "
                 "numbered in the order the characters first speak. One character has one id only.\n"
                 "- \"voice_anchor\" inside the card of every speaking character: {\"audio\": null, \"duration_sec\": null, "
                 "\"source\": \"first_approved_h3_clip\", \"clip_shot_id\": null, \"voice_description\": one plain fixed sentence "
                 "(no < > or quote marks, at most 200 characters) reused word for word in every shot where that character speaks}. "
                 "The anchor audio is extracted later from the first approved H3 clip.\n")
    return text


def stage2_text(langs=DEFAULT_OUT_LANG, voice=None):
    langs = lang_list(langs)
    en_h3 = bool(voice) and voice.get("en") == "h3"
    bible = _bible_example()
    bible["voice_map"] = {"CHAR-RAJ": {c: f"placeholder-RAJ-{c}" for c in langs},
                          "NARRATOR": {c: f"placeholder-NARRATOR-{c}" for c in langs}}
    if en_h3:
        bible["voice_speaker_map"] = {"S1": "CHAR-RAJ"}
        bible["characters"]["CHAR-RAJ"]["voice_anchor"] = {"audio": None, "duration_sec": None, "source": "first_approved_h3_clip",
                                                            "clip_shot_id": None, "voice_description": "a low, calm adult male voice"}
    example = json.dumps(bible, ensure_ascii=False, indent=1)
    return f"""Stage 2 only: write the ONE canonical art bible: the style lock, the card prompts and the voice map. Short markdown first, then one block.
Keys (exactly these top-level keys, each card keyed by its id):
- "style_lock": the 2D anime lock (medium, proportions, line, and a one-sentence prefix used at the start of every card prompt).
- "forbidden_looks": a plain list of the looks to ban (3D CG, Pixar, Cinema 4D, Octane and the rest). It is a list of bans, not a style.
- "characters": CHAR-* cards. Each card has a 16:9 labeled sheet prompt (turnaround, expressions, props) on a plain neutral backdrop.
- "environments": ENV-* scene cards. Each card describes the place only (architecture, nature, light): its card_prompt names no
  living thing and no body part. It declares continuity_landmarks (at least three fixed landmarks every shot of this place must keep)
  and a lighting_baseline {{key, fill, rim, shot_modifiers}}.
- "props": PROP-* cards.
{_voice_bible_text(langs, en_h3)}Every id a shot will use must be a key here.
End with exactly one ```json bible block holding this one JSON object (the shape below is an example; write your own content):
```json bible
{example}
```"""


def _col6_text(langs):
    """Column 6 wording for the narration and dialogue of one or several output languages (all share the same time ranges)."""
    if not multi(langs):
        code = langs[0]
        rule = LANG_RULE[code]
        return ("narration {text, language, time_range [start, end]} or null, written in " + rule["name"] + ": " + rule["rule"]
                + ' narration.language is exactly "' + code + '" on every shot that has narration (never another code). '
                "dialogue [{speaker, text, tone, time_range [start, end]}] ([] when none), the dialogue text in " + rule["name"] + ". ")
    primary = langs[0]
    per_lang = "; ".join(f"{c} ({LANG_RULE[c]['name']}): {LANG_RULE[c]['rule']}" for c in langs)
    return ("narration {text, language, time_range [start, end]} or null for the primary language (" + primary + "), plus "
            "narration_by_lang: one object per output language (" + ", ".join(langs) + "), each {text, language, time_range} with its own "
            "language code. dialogue (primary language) plus dialogue_by_lang: one list per output language with the same speakers, tones "
            "and time ranges as the primary dialogue. captions_by_lang: one list per output language of caption cards {text, time_range}, "
            "at most " + str(spec.CAPTION["max_words"]) + " words a card, the same number of cards and the same time_range in every language. "
            "EVERY language uses the SAME time_range as the primary, so one video track serves all languages. Text per language: " + per_lang + ". ")


def stage3_text(episode, seconds=None, first=1, langs=DEFAULT_OUT_LANG):
    """Stage 3 for one episode. first: the number of the episode's first shot (SHOT-NNN, continuing the earlier episodes).
    langs: the story's output languages (primary first); narration and dialogue are written in each of them."""
    langs = lang_list(langs)
    lo, hi = spec.LATTICE_N_MIN, spec.LATTICE_N_MAX
    length = f"about {float(seconds):.1f} seconds" if seconds else "the length planned in stage 1"
    hooks = ", ".join(spec.HOOKS)
    strong = ", ".join(spec.STRONG_HOOKS)
    return f"""Stage 3e{episode} only: write the V4 shot table for Episode {episode} only ({length}). Use only the ids of the Stage 2 bible
(CHAR-*, ENV-*, PROP-*). Shot ids are unique across the whole reel: the first shot of this episode is SHOT-{first:03d}, and the numbers
continue upward from the earlier episodes' shots. Every row fills all six columns:
Col 1 shot_id_and_duration: id, lattice_n ({lo} to {hi}), pixel_frames (5 + 17n), latent_slots (5n + 2) and editorial_duration_sec
   (at most {spec.MAX_SHOT_SEC:.1f} s and no longer than pixel_frames / {spec.FPS}). The rows of this episode add up to the episode length within 1 s.
Col 2 continuity_handoff: incoming (how the pose, camera and momentum arrive from the previous shot), outgoing (what this shot hands
   to the next), loop_seam (null, except on the last shot of a looped reel: the opening state of Shot 1).
Col 3 reference_anchors, with all four sub-fields:
   fixed_landmarks: copied from the ENV card continuity_landmarks;
   character_positions: [{{id, screen, depth}}] for each active character;
   exited_character_status: [{{id, left_after_shot, off_stage_shots, released}}]. A character is released only after two
   consecutive off-stage shots, so released is true only when off_stage_shots is 2 or more;
   lighting_baseline: {{key, fill, rim, shot_modifiers}}, copied from the ENV card (shot_modifiers may change).
Col 4 hook_type: one of {hooks}. The opening shot (is_opening_0_2s_hook true) and the closing shot (is_closing_hook true) use one of
   {strong}. chase, callback and expression-beat never open or close the reel. At least one shot in every three in a row is reveal,
   reversal or callback. An intended flip of eyeline, screen position or lighting carries deliberate_flip_marker (for example
   "HARD CUT — time skip: 2h"); otherwise deliberate_flip_marker is null.
Col 5 per_second_directives: contiguous brackets from 0.0 with no gap and no overlap, up to editorial_duration_sec. One-second
   brackets, plus a sub-second bracket such as 2.0 to 2.5 for a fast burst. Every bracket has t0, t1, action_pose_expression, camera,
   spatial_position, audio_cue (the synchronized birth or impact sound) and handoff_to_next_second.
Col 6 audio_and_dialogue_track: {_col6_text(langs)}performance_notes {{text, narrator_mouth_closed: true, mouth_state: {{"0": "closed", "1": "closed", ...}} with one entry per second}}.
   Output language{'s' if multi(langs) else ''} of this story: {languages_clause(langs)}. sfx_cues [{{time_range "1.2-1.6s", sfx_key, description}}] are in English.
   The speech text is for ElevenLabs. Every H3 field describes picture and sound only: no (S1) ids, no [Language] tags, no <d> tags, no <Audio N>.
Answer with exactly one ```json shots block: a JSON list of this episode's rows, each row in the shape below (the values are an example):
```json shots
{json.dumps([example_row(episode, first, langs)], ensure_ascii=False, indent=1)}
```"""


def example_row(episode=1, first=1, langs=DEFAULT_OUT_LANG):
    """One complete V4 row: the shape the stage 3 answer must follow. Length 7 s, lattice n 10. With several output languages the
    row carries narration_by_lang and dialogue_by_lang with the same time ranges in every language."""
    langs = lang_list(langs)
    lat = spec.lattice(10)
    seconds = int(lat["pixel_frames"] // spec.FPS)                 # 7 whole seconds fit inside 175 frames
    actions = [("Raj lifts his eyes from the scroll", "medium close-up, slow push in", "center-left, mid depth",
                "a page rustles", "eyes meet the door"),
               ("Raj turns toward the door", "medium close-up, hold", "center-left, mid depth",
                "wooden hinge creaks", "head stays turned to the door"),
               ("Raj stands, the lamp flame bends", "medium, pan left", "center, mid depth",
                "cloth sleeve swish", "body rises into frame"),
               ("Raj steps one pace", "medium, track left", "center, mid depth",
                "sandal scuff on stone", "weight shifts to the front foot"),
               ("Raj stops, hand at the door latch", "medium, hold", "center-right, mid depth",
                "latch click", "fingers close on the latch"),
               ("Raj looks back at the lamp", "medium close-up, push in", "center-right, near depth",
                "lamp hiss", "eyes narrow"),
               ("Raj opens the door a crack", "wide, hold", "center-right, far depth",
                "door creak and night insects", "light spills out")]
    directives = [{"t0": float(t), "t1": float(t + 1), "action_pose_expression": a, "camera": c, "spatial_position": s,
                   "audio_cue": au, "handoff_to_next_second": h}
                  for t, (a, c, s, au, h) in enumerate(actions[:seconds])]
    mouth = {str(t): "closed" for t in range(seconds)}
    window = [0.5, 5.0]
    if multi(langs):
        narration_by_lang = {c: {"text": LANG_RULE[c]["example"], "language": c, "time_range": window} for c in langs}
        track = {"narration": dict(narration_by_lang[langs[0]]), "narration_by_lang": narration_by_lang,
                 "dialogue": [], "dialogue_by_lang": {c: [] for c in langs},
                 "captions_by_lang": {c: [{"text": CAPTION_EXAMPLE[c], "time_range": window}] for c in langs}}
    else:
        track = {"narration": {"text": LANG_RULE[langs[0]]["example"], "language": langs[0], "time_range": window}, "dialogue": []}
    track["sfx_cues"] = [{"time_range": "1.2-1.6s", "sfx_key": "brass_lamp_flame_pop", "description": "a small pop as the flame bends"}]
    track["performance_notes"] = {"text": "Narrator voice only, steady and warm.", "narrator_mouth_closed": True, "mouth_state": mouth}
    return {
        "id": f"SHOT-{first:03d}", "episode": episode, "route": "Ref2VA",
        "lattice_n": lat["n"], "pixel_frames": lat["pixel_frames"], "latent_slots": lat["latent_slots"],
        "editorial_duration_sec": float(seconds),
        "continuity_handoff": {"incoming": "Opening shot: the brass lamp is lit on the low table.",
                               "outgoing": "Raj turns from the lamp toward the door, eyes low.", "loop_seam": None},
        "reference_anchors": {
            "fixed_landmarks": ["carved teak door on the left wall", "brass lamp on the low table"],
            "character_positions": [{"id": "CHAR-RAJ", "screen": "center-left", "depth": "mid"}],
            "exited_character_status": [],
            "lighting_baseline": {"key": "warm lamp light from the right", "fill": "soft cool light from the window",
                                  "rim": "thin cool edge light on the hair", "shot_modifiers": "none"}},
        "hook_type": "reveal", "is_opening_0_2s_hook": True, "is_closing_hook": False, "deliberate_flip_marker": None,
        "per_second_directives": directives,
        "audio_and_dialogue_track": track,
    }


def stage5_text(langs=DEFAULT_OUT_LANG):
    langs = lang_list(langs)
    max_words = spec.CAPTION["max_words"]
    if multi(langs):
        shape = ('{"shot_id": "SHOT-001", "captions_by_lang": {' + ", ".join(f'"{c}": [{{"text": "...", "time_range": [0.5, 2.0]}}]' for c in langs) + "}, "
                 '"narration_text_by_lang": {' + ", ".join(f'"{c}": "..."' for c in langs) + '} or null, "dialogue_texts_by_lang": {'
                 + ", ".join(f'"{c}": ["..."]' for c in langs) + "} or {}}")
        lang_work = ("b) Language lock: the output languages are " + languages_clause(langs) + ". Rewrite the narration and dialogue "
                     "lines in EACH language, with the same time ranges in every language. Captions are written in each language too.")
        cap_work = (f"a) Captions: for each shot that speaks, captions_by_lang gives at most {max_words} words per card, in each output "
                    "language, the same number of cards in every language. Captions never cover a face.")
    else:
        shape = '{"shot_id": "SHOT-001", "cards": ["..."], "narration_text": "...", "dialogue_texts": ["..."]}'
        rule = LANG_RULE[langs[0]]
        lang_work = (f"b) Language lock: the output language of this story is {rule['name']} ({langs[0]}). Rewrite the narration and dialogue "
                     f"lines that need it as {rule['rule']} Captions are in the same language.")
        cap_work = (f"a) Captions: for each shot that speaks, at most {max_words} words per card, in the language of the shot's narration "
                    "or dialogue. Captions never cover a face.")
    return f"""Stage 5 only: write the captions, the narration and dialogue language check and the QA. Markdown first, then one block.
{cap_work}
{lang_work}
c) QA: a short checklist: the six story checks, the hook bookends, the lattice counts, the shot-id references, the mouth-closed
   locks and the language lock. Mark each item pass or fail, and name the shot id for every fail.
End with one optional ```json captions block: a JSON list, one object per shot that has captions:
{shape}
(narration text null when the shot has no narration; the dialogue lists in the same order as the dialogue, [] when none)."""


def stage_instruction(name, seconds=None, first=1, langs=DEFAULT_OUT_LANG, voice=None):
    """The THIS STAGE text for stage name ('1', '2', '3e<N>', '5'). langs: the story's output languages (stages 2, 3 and 5).
    voice: the voice_engine dict (stage 2 adds the speaker map and anchors only when en = h3)."""
    if name.startswith("3e"):
        return stage3_text(int(name[2:]), seconds, first, langs)
    if name == "1":
        return stage1_text()
    if name == "2":
        return stage2_text(langs, voice)
    if name == "5":
        return stage5_text(langs)
    raise ValueError(f"unknown stage {name!r}")


def repair_block(errors):
    """Appended to the prompt of the one repair retry: the validator's error list of the last answer."""
    lines = "\n".join(f"- {e}" for e in errors[:60])
    return ("## VALIDATION ERRORS IN YOUR LAST ANSWER\n\nFix every error below, then answer the whole stage again in the same format "
            "(the same blocks, complete, not a patch):\n" + lines)
