# English H3 voice consistency (2026-11-07)

Scope: how the English voice is kept the same across shots and reels. Hindi and Marathi never use H3 speech.
Sources were read on 2026-11-07 through WebFetch of `raw.githubusercontent.com/MiniMax-AI/MiniMax-H3/main/...` (the raw files, summarised by a small model; section numbers are the ones the fetch quoted). Re-check the raw text before a real render.

## 0. Decision in force (owner, 2026-11-07, Option A: render once)
- ONE shared pure-Foley H3 render serves every selected language. The video is rendered once; voices are added after render and Step 9 QC.
- Defaults: `en = elevenlabs`, `hi = elevenlabs`, `mr = elevenlabs`. ElevenLabs is never called by code; the owner supplies voices later.
- `en = h3` is an OFF-BY-DEFAULT switch for English only. It means a SECOND English H3 render with speech in its prompt. It breaks the render-once rule and adds H3 cost. hi and mr can never be `h3`.
- Consistency for ElevenLabs voices comes from the bible `voice_map` (one fixed voice id, or placeholder name, per character per language; NARRATOR is a character too). A missing or changing entry fails the validator. No owner clips are needed.
- Consistency for en=h3 comes from a voice anchor: the audio of the FIRST APPROVED H3 clip of each speaking character, extracted (no ElevenLabs call), plus a fixed voice description sentence. Later Ref2VA shots reuse it as `<Audio N>`. `<Audio N>` is allowed in Ref2VA only in en-h3 mode.
- Gate D picks the video per language: the shared render for elevenlabs languages; the English render only when en = h3.
- Checks: identical shot durations and time ranges across languages (TIME-01); VO fit per language (wav <= editorial - 0.10 s).

## 1. What the repo already holds
- `h3/schema_and_linter.py`: SL-01 `(S\d+)` ids, SL-02 `[Language]` tags, SL-03 `<d>` wrappers, SL-04 utterances refused at source, AU-01 `<Audio N>`, MO-01 mouth lock (lines 94-115, 158-200). Written for the pure-Foley owner rule; the en-h3 mode relaxes speech refusals only for English.
- `h3/SPEC.md` (line 35): a dialogue block `says in an off-screen voiceover: <d>{language}...` (old V3 format; stale, to refresh).
- `research/workflow_review/V1_unlimited_anime_pipeline.md` (lines 93-128, 149): a per-character voice registry idea. Its own note says the clip "most likely conditions the timbre" (inference, unverified). Pre-V4.
- `research/workflow_review/W4_transcript_tips.md` (lines 47, 63, 120, 155): tips that a reference can change the speaker when an extension adds a new speaker (used only as a warning).
- `research/workflow_review/W3` (line 89) and `research/PLAN_v3_2026-11-05.md` (line 37): ElevenLabs line kept as H3 soundtrack via Wan2GP `audio_prompt_type` (a different tool path, not the MiniMax official route).
- `research/OPUS` (line 65), `research/four_videos` guide (lines 37, 172) and `research/UNIFIED` (line 25): earlier notes on voice; they do not change the rules above.

## 2. Official MiniMax H3 (VERIFIED from the repo files)
Base mode (`references/base-en.txt`, covers T2VA, I2VA, FL2VA, L2VA; no Ref2VA in this file):
- §4.4: "Subjects who speak, sing, or produce an off-screen human voice use stable IDs such as `(S1)` and `(S2)`." Compound `(S1,S2)` for several speakers.
- §4.4: "A speaker keeps the same ID across shots; characters who never vocalize receive no speaker ID."
- §4.4: "When a speaker first appears, provide enough information from the visual and audio context to establish a stable identity."
- §4.4: inside `<d>` only the language tag and the spoken words; the speaker phrase and ID stay outside. Words are kept verbatim.
- §4.4: voiceover uses the exact phrase "says in an off-screen voiceover"; "Immediately after every voiceover `<d>` block, state that the corresponding on-screen character's lips remain closed."
- §4.4: `<scenetrans>` when a line crosses a cut, `<cutoff>` when speech is truncated by the end of the video.
- The base file says nothing about `<Audio N>` (VERIFIED: a direct question found no audio text).

Full-reference mode (`references/ref-en.txt`, the Ref2VA guide):
- §5.1: "Give vocal sources stable `(S1)`, `(S2)`, and subsequent IDs." §5.1 format: `<d>[Language] ...</d>`.
- §5.4: "Assign `(Sx)` once according to the order of actual vocal events in the target video." "Reuse the corresponding ID at every actual vocal event." "Do not write `(Sx)` in `retention_analysis`."
- §5.4: `[unclear]` for unintelligible spans.
- §2.4: `<Audio N>` uses include "Referencing a speaker's voice timbre and delivery"; "When an `<Audio N>` explicitly corresponds to a target speaker, reuse that speaker's global ID in the definition."
- §5.4: "When only timbre, rhythm, emotion, or delivery is referenced, do not carry the original dialogue from the reference audio into the target video."
- §2.5: "An ordinary reference video does not create `<Audio N>` merely because the file contains sound."
- The consistent-voice mechanism named by the file is the stable `(Sx)` ID (§5.4) plus an `<Audio N>` timbre reference bound to that speaker (§2.4).

Limits (README `raw.githubusercontent.com/.../README.md`, summary of the raw text):
- Ref2VA references: images <= 9; videos <= 3 clips of 2-15 s, total <= 15 s; audio <= 3 clips of 2-15 s, total <= 15 s; all inputs <= 12 files.
- Stable spoken languages: Arabic, Chinese, English, French, German, Italian, Japanese, Korean, Portuguese, Russian, Spanish. "Additional languages are also supported to varying degrees." Hindi and Marathi are not in the stable list (hence elevenlabs for hi/mr).

## 3. Conflicts with the owner's V4 text (to tell the owner)
- The owner's master prompt says "Prohibit <Audio N> in Ref2VA (ref-en.txt section 2.4)". The official section 2.4 does NOT prohibit it. It lists speaker voice timbre as a use. The ban is therefore the owner's policy choice, not an official rule. The pure-Foley ban stays for the H3 Foley mode; the en-h3 mode uses `<Audio N>` as the owner asked.
- A render-once story with `en = h3` needs a second English H3 render. That second render is not the shared video, so the cost and the render-once rule are the owner's call (warning VE-04 is raised in code).

## 4. Built on this basis (the code follows section 2 only)
- English speech (en = h3 only) = `<d>[English] ...</d>` lines with stable `(S1)`, `(S2)` ids from one story-wide map (`voice_speaker_map`).
- Off-screen narration keeps "says in an off-screen voiceover" and the lips-closed sentence (official).
- On-screen speakers: no lips-closed sentence (no official rule found); their mouth_state reads "speaking" inside their time range (INFERRED).
- Speaking shots that carry a voice anchor are routed Ref2VA (the only mode where `<Audio N>` is documented), max 3 audio refs, each 2-15 s, total <= 15 s (official limits).
- Voice anchor per speaking character: one audio clip path, its duration, and one fixed voice description sentence. The validator requires the same sentence text in every shot where the character speaks. Pending form: `audio: null`, `source: first_approved_h3_clip`, `clip_shot_id` names the first approved clip the audio is extracted from.
- ElevenLabs languages: bible `voice_map` per character per language (VM-01/02/03).

## 5. VERIFIED vs INFERRED vs UNVERIFIED
| Item | Status | Source |
|---|---|---|
| Stable `(Sx)` id per speaker across shots | VERIFIED | base §4.4, ref §5.1, §5.4 |
| `(S1,S2)` compound id | VERIFIED | base §4.4 |
| `<d>[Language] text</d>` format; only language and words inside | VERIFIED | base §4.4, ref §5.1 |
| Voice description at first appearance | VERIFIED (what to write) | base §4.4 |
| `<Audio N>` as voice timbre bound to a speaker, Ref2VA | VERIFIED as a documented use | ref §2.4 |
| Ref2VA limits 3 audio clips, 2-15 s each, total <= 15 s | VERIFIED via README summary (re-check raw) | README |
| Lips-closed sentence after an off-screen voiceover | VERIFIED | base §4.4 |
| Ref2VA prohibits `<Audio N>` | REFUTED (owner text is wrong about the source) | ref §2.4 |
| Same audio clip gives the same timbre across separate renders and reels | UNVERIFIED (no official rule) | none |
| Repeating the same voice sentence verbatim in each shot keeps the voice | INFERRED (our rule, not official) | base §4.4 "stable identity" |
| On-screen speaker mouth "speaking" state | INFERRED | none |
| A fixed seed keeps the voice | UNVERIFIED, not used | none |
| `<Audio N>` in base modes (T2VA, I2VA, FL2VA, L2VA) | UNVERIFIED, not used | base has no audio text |
| Speech in FL2VA or L2VA | UNVERIFIED (examples carry no dialogue) | base examples |
| Anchor from the first approved H3 clip gives the same timbre in later shots | UNVERIFIED (the cross-render timbre question; needs a real render, owner go) | none |

## 6. Open owner questions
1. English narration on h3 (VE-05): there is no H3 voice path for narration yet; narration stays on ElevenLabs or is a dialogue line.
2. Cross-render timbre stability of the first-approved-clip anchor is UNVERIFIED. Confirm before relying on en = h3 for a real reel.
3. Does `clip_shot_id` get filled by a later step? Currently optional for pending anchors.
4. Confirm the owner's "no `<Audio N>` in Ref2VA" is a policy, not an official rule; the en-h3 mode allows it.
5. ElevenLabs is never called by code; any ElevenLabs use still needs the owner's go.
