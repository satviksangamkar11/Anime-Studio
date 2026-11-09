# BRIEF: shorter spoken lines (Haiku medium). Strict. Read ALL of it before writing.
Goal: every spoken line of an anime reel (18 lines x English, Hindi, Marathi) must fit its time slot when read by a slow dramatic voice. I measured the voices: they need about 0.065-0.09 seconds per character. For each line below I give MAX CHARS per language (spaces and punctuation count). Write the SHORTEST natural version that keeps the meaning. Where the line already fits, copy it UNCHANGED.

## HARD RULES (a line that breaks one is rejected)
1. Length: each language's text MUST be <= its MAX CHARS. Count characters yourself with Python len() (run python, do not guess); put the count in the output.
2. Meaning: keep who does what to whom, the question or statement type, and the story facts. Do NOT add facts, names, objects or feelings. Do NOT remove these approved details: SHOT-005-N the second man born from his mind, yellow as gold; SHOT-005-D1 work, home and wife (all three); SHOT-006-D1 flower arrows win every heart and even Shiva; SHOT-007-N Brahma's court, everyone's mind slipped; SHOT-008-D1 she is your own daughter (Brahma); SHOT-009-D1 Mahadeva's eye-fire will burn you; SHOT-010-D1 you told me to aim at everyone, blame.
3. Names: keep Brahma, Kamadeva, Mahadeva, Shiva, Vishnu, Sati, Markandeya in the SAME spelling as the current text of that language. Never write a bare "Kama" for Kamadeva.
4. Language: EASY spoken words a child can follow. Hindi and Marathi in Devanagari script as now; no hard Sanskrit words; no English words inside Hindi/Marathi. English plain and short. Marathi must be real Marathi (not Hindi spelled in Marathi).
5. Format: plain text, normal sentence punctuation (. ? !), no quotes marks, no brackets, no emotion tags, no stage directions, no emoji. Keep questions as questions.
6. The three languages say the same thing (parity) even if the wording differs.
7. Do NOT edit any file except the one output file named below. Do not run any other command than python for counting and reading. No internet. No paid tools.

## CHECKLIST (tick every box per line in the output; a line without all ticks is rejected)
[ ] en <= max chars (count shown)  [ ] hi <= max chars  [ ] mr <= max chars
[ ] same meaning in 3 languages   [ ] approved details of rule 2 kept   [ ] names spelled as current
[ ] easy words   [ ] no added facts   [ ] unchanged copy used where the line already fits
Finally: [ ] all 18 lines present, ids in the same order  [ ] python count printed for all 54 texts

## OUTPUT
Write ONE data file: D:/aai work/anime_studio_merge/research/SHORT_TEXT_DRAFT_2026-11-09.json = a JSON list of 18 objects: {"id": "SHOT-003-N", "en": "...", "hi": "...", "mr": "...", "chars": {"en": n, "hi": n, "mr": n}, "max": {"en": n, "hi": n, "mr": n}, "changed": true, "note": "what was cut, one short sentence"}. Write it with Python json.dump(ensure_ascii=False), utf-8. Then a second file D:/aai work/anime_studio_merge/research/SHORT_TEXT_DRAFT_2026-11-09.md with a table of the same data (id, language, text, chars/max). Then append one log line with the Bash tool: echo "$(date +%m-%d' '%H:%M) | haiku-short | AGENT-DONE | research/SHORT_TEXT_DRAFT_2026-11-09.json | <n lines changed; all within max: yes or no>" >> "D:/aai work/anime_studio/PROJECT_LOG.md". Report once: how many lines changed, and any line you could NOT fit (say which and why; never exceed max silently).

## LINES (current text, slot seconds, max chars)
### SHOT-001-N  speaker NARRATOR  slot 5.0 s
- en: CURRENT (46 chars) Before the world began, she was already there.  | MAX CHARS 68 (measured pace) | already fits: copy unchanged
- hi: CURRENT (36 chars) दुनिया बनने से पहले भी, वो वहाँ थीं।  | MAX CHARS 62 (measured pace) | already fits: copy unchanged
- mr: CURRENT (38 chars) जग बनण्याच्या आधीसुद्धा, ती तिथे होती.  | MAX CHARS 49 (estimated pace, 10% safety) | already fits: copy unchanged

### SHOT-002-N  speaker NARRATOR  slot 4.4 s
- en: CURRENT (54 chars) Her sword cuts our chains. Her open hand sets us free.  | MAX CHARS 59 (measured pace) | already fits: copy unchanged
- hi: CURRENT (65 chars) उनकी तलवार हमारे बंधन काटती है। उनका खुला हाथ हमें आज़ाद करता है।  | MAX CHARS 54 (measured pace) | OVER by 11
- mr: CURRENT (66 chars) तिची तलवार आपल्या बेड्या तोडते. तिचा उघडा हात आपल्याला मोकळं करतो.  | MAX CHARS 42 (estimated pace, 10% safety) | OVER by 24

### SHOT-003-N  speaker NARRATOR  slot 1.8 s
- en: CURRENT (27 chars) At dawn, sages came asking.  | MAX CHARS 22 (measured pace) | OVER by 5
- hi: CURRENT (23 chars) सुबह मुनि सवाल लेकर आए।  | MAX CHARS 20 (measured pace) | OVER by 3
- mr: CURRENT (26 chars) पहाटे ऋषी प्रश्न घेऊन आले.  | MAX CHARS 16 (estimated pace, 10% safety) | OVER by 10

### SHOT-003-D1  speaker HIMALAYAN-MUNIS  slot 2.1 s
- en: CURRENT (44 chars) Sati's birth? Shiva's marriage? Please tell.  | MAX CHARS 26 (measured pace) | OVER by 18
- hi: CURRENT (32 chars) सती कैसे जन्मीं? शिव-ब्याह कैसे?  | MAX CHARS 19 (estimated pace, 10% safety) | OVER by 13
- mr: CURRENT (33 chars) सती कशी जन्मली? शिवांचं लग्न कसं?  | MAX CHARS 19 (estimated pace, 10% safety) | OVER by 14

### SHOT-003-D2  speaker MARKANDEYA  slot 2.2 s
- en: CURRENT (37 chars) Listen. Brahma told this story first.  | MAX CHARS 25 (measured pace) | OVER by 12
- hi: CURRENT (37 chars) सुनो। ब्रह्मा ने पहले ये कहानी सुनाई।  | MAX CHARS 29 (measured pace) | OVER by 8
- mr: CURRENT (39 chars) ऐका. ही कथा आधी ब्रह्मदेवांनी सांगितली.  | MAX CHARS 20 (estimated pace, 10% safety) | OVER by 19

### SHOT-004-N  speaker NARRATOR  slot 7.2 s
- en: CURRENT (93 chars) Brahma made the gods, the sages and Daksha. Then, from his deep thought, a daughter was born.  | MAX CHARS 100 (measured pace) | already fits: copy unchanged
- hi: CURRENT (71 chars) ब्रह्मा जी ने देवता, ऋषि और दक्ष बनाए। फिर उनके ध्यान से एक बेटी जन्मी।  | MAX CHARS 91 (measured pace) | already fits: copy unchanged
- mr: CURRENT (78 chars) ब्रह्मदेवांनी देव, ऋषी आणि दक्ष घडवले. मग त्यांच्या ध्यानातून एक मुलगी जन्मली.  | MAX CHARS 71 (estimated pace, 10% safety) | OVER by 7

### SHOT-005-N  speaker NARRATOR  slot 3.3 s
- en: CURRENT (48 chars) Then another came from his mind, yellow as gold.  | MAX CHARS 44 (measured pace) | OVER by 4
- hi: CURRENT (41 chars) फिर उनके मन से एक और जन्मा, सोने-सा पीला।  | MAX CHARS 40 (measured pace) | OVER by 1
- mr: CURRENT (54 chars) मग त्यांच्या मनातून आणखी एक जन्मला, सोन्यासारखा पिवळा.  | MAX CHARS 31 (estimated pace, 10% safety) | OVER by 23

### SHOT-005-D1  speaker KAMADEVA  slot 3.4 s
- en: CURRENT (46 chars) Lord, what's my work? Give me a home and wife.  | MAX CHARS 47 (measured pace) | already fits: copy unchanged
- hi: CURRENT (46 chars) प्रभु, मेरा काम क्या? मुझे घर दीजिए, पत्नी भी।  | MAX CHARS 32 (estimated pace, 10% safety) | OVER by 14
- mr: CURRENT (46 chars) प्रभू, माझं काम काय? मला घर द्या, आणि बायकोही.  | MAX CHARS 32 (estimated pace, 10% safety) | OVER by 14

### SHOT-006-N  speaker NARRATOR  slot 2.9 s
- en: CURRENT (47 chars) The sages named him Manmatha, Madana, Kandarpa.  | MAX CHARS 38 (measured pace) | OVER by 9
- hi: CURRENT (43 chars) मुनियों ने उसे नाम दिए, मन्मथ, मदन, कंदर्प।  | MAX CHARS 35 (measured pace) | OVER by 8
- mr: CURRENT (44 chars) ऋषींनी त्याला नावं दिली, मन्मथ, मदन, कंदर्प.  | MAX CHARS 27 (estimated pace, 10% safety) | OVER by 17

### SHOT-006-D1  speaker BRAHMA  slot 3.3 s
- en: CURRENT (65 chars) Your flower arrows win every heart. Mine, Vishnu's, even Shiva's.  | MAX CHARS 37 (measured pace) | OVER by 28
- hi: CURRENT (56 chars) तुम्हारे फूल-बाण हर मन जीतेंगे। मेरा, विष्णु, शिव का भी।  | MAX CHARS 24 (measured pace) | OVER by 32
- mr: CURRENT (69 chars) तुझे फुलांचे बाण प्रत्येक मन जिंकतील. माझं, विष्णूंचं, शिवांचंसुद्धा.  | MAX CHARS 31 (estimated pace, 10% safety) | OVER by 38

### SHOT-007-N  speaker NARRATOR  slot 3.6 s
- en: CURRENT (51 chars) He aimed at Brahma's own court. Every mind slipped.  | MAX CHARS 48 (measured pace) | OVER by 3
- hi: CURRENT (50 chars) उसने ब्रह्मा जी की सभा पर बाण चलाया। सबका मन डोला।  | MAX CHARS 44 (measured pace) | OVER by 6
- mr: CURRENT (61 chars) त्याने ब्रह्मदेवांच्या सभेवरच बाण सोडला. सगळ्यांचं मन डळमळलं.  | MAX CHARS 34 (estimated pace, 10% safety) | OVER by 27

### SHOT-007-D1  speaker KAMADEVA  slot 1.6 s
- en: CURRENT (23 chars) Let's see if it's true.  | MAX CHARS 20 (measured pace) | OVER by 3
- hi: CURRENT (21 chars) देखूँ, सच है या नहीं।  | MAX CHARS 14 (estimated pace, 10% safety) | OVER by 7
- mr: CURRENT (15 chars) बघू, हे खरं का?  | MAX CHARS 14 (estimated pace, 10% safety) | OVER by 1

### SHOT-008-N  speaker NARRATOR  slot 2.9 s
- en: CURRENT (47 chars) Brahma and the sages hung their heads in shame.  | MAX CHARS 38 (measured pace) | OVER by 9
- hi: CURRENT (34 chars) ब्रह्मा जी और मुनि शर्म से झुक गए।  | MAX CHARS 35 (measured pace) | already fits: copy unchanged
- mr: CURRENT (43 chars) ब्रह्मदेव आणि ऋषींनी लाजेने मान खाली घातली.  | MAX CHARS 27 (estimated pace, 10% safety) | OVER by 16

### SHOT-008-D1  speaker SHIVA  slot 3.2 s
- en: CURRENT (58 chars) Brahma, she's your own daughter. How could your mind slip?  | MAX CHARS 41 (measured pace) | OVER by 17
- hi: CURRENT (42 chars) ब्रह्मा जी, वो आपकी बेटी है। मन कैसे डोला?  | MAX CHARS 35 (measured pace) | OVER by 7
- mr: CURRENT (52 chars) ब्रह्मदेव, ती तुमचीच मुलगी आहे. तुमचं मन कसं डळमळलं?  | MAX CHARS 30 (estimated pace, 10% safety) | OVER by 22

### SHOT-009-N  speaker NARRATOR  slot 2.2 s
- en: CURRENT (32 chars) Kamadeva's hands began to shake.  | MAX CHARS 28 (measured pace) | OVER by 4
- hi: CURRENT (25 chars) कामदेव के हाथ काँपने लगे।  | MAX CHARS 25 (measured pace) | already fits: copy unchanged
- mr: CURRENT (26 chars) कामदेवाचे हात थरथरू लागले.  | MAX CHARS 20 (estimated pace, 10% safety) | OVER by 6

### SHOT-009-D1  speaker BRAHMA  slot 4.0 s
- en: CURRENT (52 chars) You shot me? Fire from Mahadeva's eye will burn you.  | MAX CHARS 46 (measured pace) | OVER by 6
- hi: CURRENT (49 chars) मुझ पर बाण? महादेव की आँख की आग तुम्हें जला देगी।  | MAX CHARS 30 (measured pace) | OVER by 19
- mr: CURRENT (52 chars) माझ्यावर बाण? महादेवांच्या डोळ्यांतली आग तुला जाळेल.  | MAX CHARS 38 (estimated pace, 10% safety) | OVER by 14

### SHOT-010-N  speaker NARRATOR  slot 2.0 s
- en: CURRENT (31 chars) Would Brahma ever take it back?  | MAX CHARS 25 (measured pace) | OVER by 6
- hi: CURRENT (33 chars) क्या ब्रह्मा जी श्राप वापस लेंगे?  | MAX CHARS 23 (measured pace) | OVER by 10
- mr: CURRENT (27 chars) ब्रह्मदेव शाप परत घेतील का?  | MAX CHARS 18 (estimated pace, 10% safety) | OVER by 9

### SHOT-010-D1  speaker KAMADEVA  slot 2.8 s
- en: CURRENT (39 chars) You said aim at everyone. Why blame me?  | MAX CHARS 38 (measured pace) | OVER by 1
- hi: CURRENT (37 chars) आपने कहा, सब पर चलाओ। मेरी गलती क्या?  | MAX CHARS 26 (estimated pace, 10% safety) | OVER by 11
- mr: CURRENT (51 chars) तुम्हीच सांगितलं होतं, सगळ्यांवर सोड. माझी काय चूक?  | MAX CHARS 26 (estimated pace, 10% safety) | OVER by 25
