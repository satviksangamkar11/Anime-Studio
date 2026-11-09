# VOICE DESIGN R1 Nemotron Super (NVIDIA), 2 slices

## slice A: what Granth does + what we have
FINAL:
1. HIGH | D3 Job key | Text/settings changed after generation spawns a new clip and spends again; no immutable text lock. | Hash script text into freeze; reject any text/voice/model/settings change after gate; versioned manifest.
2. HIGH | D4 Credit ledger | Crash after API call but before settle leaves credits reserved or retries duplicate. | Write PENDING ledger row with job key before call; mark DONE only after file saved; on resume, skip existing key, never re-call.
3. HIGH | D9 Hindi voices | No Hindi voice in account; shared-library slots may fill and preview may not match paid model. | Pre-audit 6 speakers × 3 languages; provision Hindi voices before gate; record voice_id+model in freeze; no preview acceptance.
4. HIGH | D11 Concurrency | Two processes pass cap check simultaneously and double-spend. | File-lock whole run (flock) plus per-job reservation; single worker only.
5. MEDIUM | D10 Model | Wrong model for Marathi (e.g., turbo unsupported) or API header cost differs from estimate. | Validate model-language support pre-call; settle strictly by API character-cost header; abort if header > estimate + tolerance.
6. MEDIUM | D6 Measure | ffprobe duration exceeds video slot; credits already spent. | Pre-check estimated duration vs slot before spending; shorten text or change voice, never generate overrun.
7. MEDIUM | D7 Freeze | Freeze excludes owner sign-off and pronunciation; manual “not validated” is skippable. | Mandatory owner-listened hash in freeze; CI blocks mix without it.
8. LOW | D2 Voice map | bible.json placeholder IDs are not real ElevenLabs voice_ids. | Resolve placeholders to verified voice_ids before job-key generation.
9. LOW | Missing test | No test for duplicate key reuse or cap refusal. | Unit test: same job key returns cached file, zero API calls. Integration test: cap blocks over-limit spend.
10. HIGH | D1 Voice library | Voice removed from account mid-pipeline makes assigned voice_id invalid. | Pre-flight status check immediately before each call; fail fast if MISSING_FROM_ACCOUNT.
11. MEDIUM | Missing guard | Free preview ≠ paid model; voice may sound different in production. | Accept only actual paid-model output; owner listens to generated clip, never preview.

Could not verify: ElevenLabs character-cost header accuracy; real Hindi/Marathi name pronunciation for the six speakers; ffprobe timing fit for closed-mouth VO against the shared video; shared-library Hindi voice availability at spend time.

## slice B: proposed design, decisions D1-D11, regeneration triggers
FINAL:
1. HIGH D1 Problem: Hindi/Marathi sacred-name quality on turbo untested; wrong model wastes the full run. Fix: Pick (b) only if S3 test passes, else (a). Missed: per-language model selection.
2. HIGH D2 Problem: 18 voice combos exceed the 10 added-voice slot limit; premade vs added unmapped. Fix: Pick (b) 3 voices; audit account slots before S1.
3. MEDIUM D3 Problem: Isolated name tests miss connected-speech errors. Fix: Pick (b); add one full-sentence hard-name line per language. Missed: A/B model comparison.
4. MEDIUM D4 Problem: atempo overrun or post-generation text changes force regeneration. Fix: Pick (a)+(e); freeze text before S5; shorten source pre-generation only.
5. MEDIUM D5 Problem: Model trust or isolated names ignore context; IPA/SSML support unchecked. Fix: Pick (b); test names in sentences; verify zero-cost IPA/SSML (missed).
6. MEDIUM D6 Problem: Setting drift creates a new job key, i.e. a paid duplicate. Fix: Fix settings in the job key; hash settings into the manifest.
7. MEDIUM D7 Problem: Independent lines break intonation; single-request-per-shot missed. Fix: Pick previous/next context; test one request per shot if the API allows.
8. MEDIUM D8 Problem: No content-addressed storage; the same line can be regenerated across runs. Fix: Name files by hash(text+voice+model+settings).
9. MEDIUM D9 Problem: Closed-mouth voice-over may clash with a later lip-sync gate, forcing regeneration. Fix: Confirm the mix/lip-sync pipeline accepts raw VO before S6.
10. HIGH D10 Problem: Estimate vs API header cost mismatch can blow the cap; no hard limit. Fix: Pick cap + header cost; abort if header cost exceeds estimate by >5%.
11. HIGH D11 Problem: No owner sign-off on line count/cost; S5→S6 can duplicate without ledger reset. Fix: Add S0 owner approval; reset the ledger between S5 and S6.
12. HIGH General Problem: Crash after the API call but before the ledger write causes duplicate regeneration. Fix: Write the reservation/ledger atomically before the API call; treat crash-reserved keys as spent.
13. HIGH General Problem: Two processes at once; no ledger lock. Fix: Exclusive fcntl lock on the ledger; fail fast if held.
14. MEDIUM General Problem: Voice deleted mid-project; text changed after generation; API cost differs; free preview does not match paid model. Fix: Re-verify voice pre-call; freeze script hash in the manifest; compare header cost; generate one paid line per voice in S5 to match preview.
15. MEDIUM General Problem: English uncovered; Hindi/Marathi normalization and WPS missing; shared-video drift unguarded. Fix: Add English voice selection, per-language WPS rules, and a cumulative duration check against the shared timeline.
16. LOW Missing tests Problem: Fake HTTP omits 429/500, partial writes, header mismatch, voice deletion, and duplicate-key collision. Fix: Add offline failure-mode tests.
17. LOW Could not verify: API header accuracy, preview-to-paid audio equivalence, provider Hindi/Marathi and sacred-name quality, IPA/SSML support, exact slot allocation, real crash/concurrency behavior, and the atempo artefact threshold.
