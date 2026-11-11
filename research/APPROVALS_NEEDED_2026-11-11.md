# Everything that needs the owner's approval (2026-11-11). Reply "approve all" or list the numbers to change.

State: Step 0 (17 module-fix cards) coded: 16 of 17 done by coders (S-05 waits on A1); Nemotron Super reviews running (batch 1 nine cards, batch 2 seven cards). Gap register: research/GAP_REGISTER_2026-11-11.md (46 problems + 18 follow-ups).

## A. Confirm now
A1 Mouth wording (card S-05). One sentence per shot naming each person from the blocking sheet: "A speaks with moving lips; B and C keep their lips completely closed." Replace MOUTH_LOCK_SENTENCE and the "figure's mouth stays closed" rule; delete the "except for non-verbal breaths" clause (reviewers flagged it as contradictory). Render every shot as its own clip (grouped shots were never tested). Lip movement on H3 was never tested: one two-person canary shot before the batch (needs your Colab go later).
A2 Sound words. I understood "keep the system we used" as: keep rule 50(6) and move sound cues out of the action sentences into the soundscape; the model keeps generating sounds, the Ableton mix keeps only script-cue hits. Confirm.
A3 S-12 from_pack: a pack row has no "action" field; I take the first directive's action_pose_expression as the shot action. Confirm.
A4 Test-change policy. Cards that change behaviour force changes to old tests (S-01, S-02, S-06, S-07, S-08, S-09, S-11, S-14, S-16 did this; S-08 deleted the old 13 MB cap test). Policy: allowed only when the reviewer confirms the original intent is kept; otherwise back to the coder.
A5 NEW card X-25 "story -> reels planner" (missing from the Opus plan, needed by your decision 7): input a whole story; Opus (CLI, web on) plans how many reels, each reel's outline/hook/length 60-75 s/10 shots, writes one reel plan file per reel; every reel then goes through the same pipeline; reel 2 is the first run. Approve adding it.
A6 Follow-up fix wave (closes F-01..F-13 of the register): S-07b (copy KFI mid frames, fix stale "22" message), S-01b (bound checks for every lattice length), S-13b (reader/writer scale mismatch), S-12b (clean errors for pack rows, real path test), S-08b (missing-id test, script_path checks), S-14b/S-15b (missing tests), S-16b (real date check), S-17b (missing error tests), S-09b (staged-mode main). Approve running them after the reviews, same coder/reviewer/checklist rules.
A7 Review policy. For every card: Nemotron Super (free NVIDIA) checks each checklist row against the code; I run the tests myself and add a human pass (missing / extra / bad); a failing row goes back to the coder with the row quoted; after 2 failed rounds I stop and ask you. Final audit of the whole register by Nemotron Super + Ultra (free); Codex Luna medium only if you allow it.

## B. The remaining road, one wave at a time (I will ask before each wave)
W1 Blocking and writer: X-01 blocking.json schema + loader, X-02 sheet lint, X-03 adapters, X-06 writer guard (Opus CLI wrapper: limit check, usage log, JSON validation), X-07 write_pack wiring + writer gate, X-08 source_check (your human pass), X-25 story -> reels planner.
W2 Reel 2 content (Opus writes, I never write story text): reel plan, script, shot plan, scene plan, blocking sheets; script gate (S-10/11/12) must PASS; you read and pass it.
W3 Voice and lock: voice_cast (preflight.json, pilot.json, wav_contract, audio_edge, no atempo, hard-name flag), lock writer, build_vo_tracks. The paid ElevenLabs pilot needs your go; you listen to the hard names.
W4 Prompts and keyframes: v4_to_h3 + compile_h3_sing8 + schema_and_linter as one change (blank line, SX-01, mouth sentence, cast from sheet), X-09..X-11 plates, A/B keyframes as edits, keyframe_gate, approval sheet.
W5 Render prep: J8 port of build_h3_batch.py and run_colab_batch.py, soft-end offline trace in the Wan2GP source, runner safety wiring, one-shot canary. Colab needs your go.
W6 Assembly and delivery: lock_rows, render_controller timeline gate, build_final_reel (captions, crop, Ableton mix intake, versioned export, waivers), clip_qa, SFX policy, cue_sheet, stem_builder audition rename, hooks, docs.
W7 End-to-end offline test on reel 2 data, then the final register audit.
Each wave ends with: tests run by me, Super review, register diff, filled checklists shown to you.

## C. Only you can do or authorize
Colab runs (units), paid ElevenLabs runs, listening to hard names, git config core.hooksPath .githooks, rotating the OpenRouter key you pasted, any commit / push, deciding to keep or delete loop_p0, Drive (Drive for Desktop install), approving each wave.

## D. Decisions I made for you (veto any)
D1b REF_SE goes to the Ref2VA workflow (offline Wan2GP check in W5). D4 SFX policy = rule 50(6). D5 -14 LUFS file renamed as audition-only. D6 watermark removal stays manual with a refusal on zero input. D10 disk preflight minimum 5 GB (D: has 21 GB). D11 delivery crop + mix intake in code. D13 accepted flagged clips are recorded in clip_qa.json (code, date, note). D14 lock margin 0 when the input is needed_sec. D16 beat error up to half a frame. D17 shot-length limits from the H3 handle rules (middle 45-258 edit frames). D19 blocking.json schema (approved by me; shown to you when X-01 is coded). D20 no commit/push, chumpy wheel not committed until you say.

## E. Owner answers 2026-11-11 (second round) and what they changed
- A1 mouth wording + individual shots: APPROVED ("lip movement is fine", clip speed can be adjusted). S-05 coder started.
- A4 changing old tests: APPROVED ("we want a foolproof pipeline").
- A5 story -> reels planner: DEFERRED; it exists locally in director/write_pack.py (stage 1, story_plan.json); noted as F-15 in the gap register, no new card now.
- A2/A3/A6/A7 and section D: "rest looks okay" -> treated as approved.
- NEW card X-26: AUTOMATED WATERMARK REMOVAL when any image is finalised (see register F-19). Replaces decision D6 (manual).
- NEW idea F-20: per-language clip retime as the fallback instead of speeding the voice. My suggestion: one picture for all languages (as now); the lock sizes every shot to the LONGEST language, so normally no retime is needed; only if a language still does not fit (voice longer than the lock slot after margin), allow retime of the picture of that language by at most +/-4 % (setpts on the video, matching atempo on the clip's own sound so pitch stays natural), recorded in the lock, never beyond 4 %, never on the voice. Lip movement keeps the same wording (a small speed change does not break it). Needs your yes/no.
- Sound effects: the model still generates the sounds inside each clip (that is how we get SFX). The mix keeps only the hits the script asks for (rule 50(6)), mutes the rest. My suggestion stays: move sound cues out of the action sentences into the soundscape so the model draws no creatures from sound words. Your sentence "packaging scene 12" I could not understand: tell me what you meant.
