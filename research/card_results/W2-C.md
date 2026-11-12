# W2-C (G5, G6, G21) voice_cast.py
- SETTINGS now explicit API defaults (stability .5, similarity .75, style 0, speaker boost); speed lines = defaults + speed.
- language_code = lang for eleven_v3/v4 only; seed = int(sha256(line id)[:8],16); both in job + body + key.
- pronunciation_dictionary_locators(story_dir, lang) reads pronunciation_<lang>.json {"locators":[...]}, >3 -> SystemExit; main loads from voices file dir.
- output_format from cast "_output_format" (default mp3_44100_128; non-default joins key, file ext wav/pcm).
- Optional key parts join the hash only when set (mp3 default adds nothing). Old keys DO change (new settings/lang/seed) = intended per B-09: existing clips re-buy.
- Edited 2 asserts in test_voice_cast.py (settings now include defaults). New tests: director/test_voice_cast_g5.py.
