# Voice system for the anime pipeline (design for review), 2026-11-09

Owner orders: copy the GranthStudio ElevenLabs "fix the character voice" system; NO regeneration (every line is generated once); every step reconfirmed with the reviewers with all possibilities listed; do not waste ElevenLabs credits. Nothing below has been generated or spent yet.

## 1. What GranthStudio does (read from its code, read-only)
Files: `scripts/pipeline/voice_library.py`, `scripts/source/a1_eleven.py`, `canon/series/voices.json`, `canon/audio/A1_eleven_voices.json`, `canon/audio/A1_eleven_measured.json`, `canon/adhyay_01/audio_freeze.json`.
1. **Voice library** (`voices.json`): the account's voices fetched once from the API and normalised: voice_id, name, gender, age, accent, descriptive, use_case, hindi_verified, marathi_verified (from `verified_languages`), status ASSIGNED / AVAILABLE / MISSING_FROM_ACCOUNT, assigned_to, owner_note.
2. **Voice map** (`A1_eleven_voices.json`): `{"mr": {"narrator": voice_id, ...}, "hi": {...}}`. ONE fixed voice id per character per language, never changed.
3. **Job key** = sha256(language | voice id | model | settings | text). The clip file is named after the key. A re-run with the same key reuses the accepted clip; a changed text, voice, model or setting makes a NEW clip and never overwrites an accepted one. So a re-run buys nothing twice.
4. **Credit ledger**: append-only, file-locked; reserves the estimate BEFORE each call, settles with the API's own `character-cost` header; refuses past the cap (default 8,000 credits) or while any reservation is open.
5. **Gate to spend**: `jobs` (dry list with credit estimate) is free; `run` needs `--allow-paid` and a cap.
6. **Measure**: every accepted clip is probed with ffprobe (real duration); a file that cannot be decoded or has an implausible duration stops the run. The measured file feeds the timing plan: every line's window must be at least its measured seconds.
7. **Freeze file**: sha256 of the plan, the measured file, the script text, and the manifest; "voices NOT VALIDATED until the owner has listened".
8. **Export**: accepted clips decoded to mono 16-bit wav named `<line>.<lang>.wav` for the mix.

## 2. What we already have in this project
- `bible.json` has `voice_map` = {NARRATOR, CHAR-KALI, CHAR-MARKANDEYA, CHAR-HIMALAYAN-MUNIS, CHAR-BRAHMA, CHAR-SAVITRI, CHAR-DAKSHA, CHAR-MANASA-PUTRAS, ... } each with en, hi, mr = placeholder ids (`placeholder-NARRATOR-hi`). `h3/voice_engine.py` and `h3/voice_manifest.py` define the rules (VM-*: one fixed voice id per character per language) and a manifest of wavs; nothing calls ElevenLabs. Gate D (`h3/gate_d_audio.py`) mixes the wavs, `vo_fit` checks length against the slot.
- Reel 1 script: 18 lines per language (10 narration + 8 dialogue), speakers NARRATOR, HIMALAYAN-MUNIS, MARKANDEYA, KAMADEVA, BRAHMA, SHIVA. 2,496 characters in all (en 850, hi 803, mr 843). Account: Starter, 35,704 credits left.
- ElevenLabs account voices: English premade (George, Brian, Adam, Bill, Daniel, ...), Marathi professional (Bipin narrator, Sharad deep powerful narrator, Kalyani, Radha K, Shrey, Tukaram x2, Ativir, Swapnil J, Vinayak, others). NO Hindi voice in the account. Shared library (free to add on Starter, 10 slots): Hindi narrators such as Ayush M (deep mythology narrator), Ritu Rathore (soulful female), Natraj, Ajay, Ibad, Azad.
- Models (from the API, cost multiplier per character): eleven_v4 x1.0, eleven_v3 x1.0, eleven_v4_turbo x0.5, eleven_v3_conversational x0.5; all support hi and mr; eleven_multilingual_v2, flash_v2_5, turbo_v2_5 support hi but NOT mr.

## 3. Proposed design for us (copy of the Granth system, adapted)
New files (no change to existing ones except filling the voice_map):
- `director/voice_library.py`: fetch + normalise + write `<story>/voices_library.json` (read-only API calls, free) including each voice's free `preview_url`.
- `<story pack>/voices_cast.json`: the voice map, filled by the owner's choice after listening to free previews; MUST resolve every speaker x language of the script.
- `director/voice_cast.py`: `jobs` (free dry list), `run` (paid, `--allow-paid --cap N`), `measured`, `export`, with the job key, the ledger, reuse, ffprobe checks and the manifest, exactly as in Granth, reading `narration_by_lang` and `dialogue_by_lang` of the pack's shots.json.
- Pre-flight checks before any spend: every speaker has a cast voice in each language; the voice is `hindi_verified`/`marathi_verified` for that language or the owner accepted it; text passes the easy-language and the words-per-second check; a hard-name list is tested first; total credits vs the cap.
- Tests offline with a fake HTTP (no API calls).

## 4. Decisions with ALL possibilities (reviewers: argue each)
D1 **Model**: (a) eleven_v4 x1.0 (newest, best claim for hi/mr); (b) eleven_v4_turbo x0.5 (half the cost, quality unknown); (c) eleven_v3 x1.0; (d) eleven_v3_conversational x0.5; (e) multilingual_v2 for Hindi only (cheaper, not Marathi). Risk: quality for Marathi/Hindi and sacred names is untested on this account.
D2 **Voices per language**: (a) 1 voice for everyone; (b) narrator + 1 male + 1 female (3); (c) one voice per character (6 speakers x 3 languages = 18 voices; account slot limit 10 for added library voices, premade/Marathi pro voices already in account do not use slots). Consistency rule VM-*: same speaker keeps the same voice in every shot and reel.
D3 **Test before the full run**: (a) none (no); (b) 3 short lines per language incl. hard names (about 360 credits, 1%); (c) full run directly. Free previews first (voice `preview_url` samples cost 0 credits) so voices are chosen by ear before any paid call.
D4 **Timing fit without regeneration**: (a) generate once then fit with ffmpeg `atempo` (free, up to about 8% without artefacts); (b) regenerate with speed setting (costs credits); (c) shorten text (changes meaning, parity across languages); (d) widen the slot using spare clip frames (30 to 43 per shot); (e) shorten text BEFORE generation only for lines that the words-per-second rule already marks too fast (8 Hindi lines).
D5 **Pronunciation**: (a) trust the model; (b) test the hard names with 2 candidate spellings first (मन्मथ, कंदर्प, दक्ष, ब्रह्मा, मार्कंडेय; Marathi forms); (c) use a pronunciation dictionary/IPA if the API offers it (cost 0); decide after the test.
D6 **Voice settings**: default vs fixed (stability/similarity/style/speed) saved IN the job key so they can never drift; changing them = a new key = paid. Choose once, before the run.
D7 **Continuity inside a shot**: send previous_text/next_text for lines of the same shot so intonation joins (no extra cost) vs independent lines.
D8 **Where the clip files live**: local D: only (small mp3s, 2,496 characters is about 3 to 4 minutes of audio).
D9 **Mouths are closed in every clip**: dialogue is voice-over; keep, or add lip-sync later (out of scope).
D10 **Spend control**: cap per run (proposal 3,000 credits for the full reel, 400 for the test); the run refuses to start if the estimate exceeds the cap or any reservation is open; every clip's real cost is read from the API header.
D11 **Order of work (each step reviewed)**: S1 library + free previews (no spend) -> owner picks voices -> S2 cast file + lint (no spend) -> S3 code + tests -> S4 `jobs` dry run -> S5 test run 360 credits (owner listens) -> S6 full run once -> S7 measure + fit + wavs -> S8 freeze file.

## 5. What would make us regenerate (to prevent)
Wrong text (fix the 8 Hindi lines and wording BEFORE), wrong voice (choose by free preview), wrong model (test first), a name said wrongly (test first), a line too long for its slot (fit locally), a changed setting (frozen in the key), a crash mid-run (ledger + reuse by key), a duplicate call (reservation lock).
