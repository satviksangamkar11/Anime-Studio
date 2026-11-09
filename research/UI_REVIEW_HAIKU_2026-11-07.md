# UI review: Anime Studio control panel (2026-11-07)

Reviewer: UI-REV (Haiku, extra-high effort). Read-only review. No code was edited. No action button was pressed.
Page: http://127.0.0.1:8765 (the running server; the page itself reports it as "older than its code", pid 37320, started 2026-11-07 03:15).
Viewports: desktop 1280x800 (emulated, shown scaled to 800x500) and phone 375x812 (emulated).
Captures: 51 screenshots (28 desktop, 22 phone full size, 1 phone at 0.6 scale) plus 1 zoom. Total 52 captures.
Not opened: the Advanced "Video" section. Opening it calls Colab (loadVideo calls loadColab), which blot.md RULE 4 forbids. Its content is described from index.html and app.js only.
Checks made by reading the DOM (no clicks on actions): button disabled flags, computed font sizes, horizontal overflow, stepper positions, sticky footer size.

---

## A. Screen map (in the order a user meets it, top to bottom)

Everything is one long page. Advanced tools is folded at the bottom.

1. **Top bar** (story, pack, languages, SPEND OFF, job, 127.0.0.1). Shows what is open and whether paid work is allowed.
2. **Banners**. A red box says the server is out of date and must be restarted before approving. Low-disk warnings appear here too.
3. **Step list** (6 steps: Story, Analysis, Images, Read-out, Render, Export). Shows where the user is. Desktop: left column. Phone: one horizontal strip.
4. **Scope bar** (story, pack, languages, writer chips). Shows which story and draft every panel below belongs to.
5. **Job bar** ("No job running. Each step asks before it starts anything."). Shows whether background work is running.
6. **Step 1 Story card.** Purpose: get the story text in and choose languages. Sub-panels, in order: "Where you stopped" with Continue; story picker; new slug; story text; Save story; Languages (English, Hindi, Marathi, All, Save languages); Voices (English built-in voice checkbox, Save voices); Background music (checkbox, manifest path, Save); Voice map (per character, per language); YouTube link (URL, language, speech-to-text choice, Get transcript).
7. **Step 2 Analysis card.** Purpose: the AI writes the story plan, and the user approves it. Sub-panels: pack name and "Run story analysis"; "What you must approve" (shot table, episode table, names, check JSON); "Pack check (validator)" with "Run validator"; **Gate A** (note, Approve, Reject).
8. **Step 3 Images card.** Purpose: prepare picture work. Buttons: Build image jobs, Make Flow agent packet; counts (Finals, Pending, Reviewed); **Gate B** sits inside this card.
9. **Step 4 Read-out card.** Purpose: a summary of reels, shots, seconds, characters, estimates; checks list; **Gate C** (type START) sits inside this card.
10. **Step 5 Render card.** Purpose: make the video plan. Sub-panels: Prepare render (no GPU); Image jobs and assets; fallback table with human choices; Step 9 render check; H3 field author (dry run, typed phrase, Run author); **Gate D** (per-language rows, approve).
11. **Step 6 Export card.** Purpose: show clips for one reel. Reel number, Show clips.
12. **Ops panel.** Purpose: disk space, server state, Colab paid units used.
13. **Runs & documents.** Purpose: read-only table of past story runs. Clicking a row opens its steps and the run report.
14. **Advanced tools (folded).** Five sub-sections: Story (old manual controls, separate story picker), Images (six tabs: Series, Jobs, Shots, Progress, Queue, Finals), Bridge (key frames), Video (clip batches, H3 engine, Colab with paid run button, live log, clips), Export.
15. **Sticky "Job log tail" footer** (inside Advanced). Shows the last 12 log lines and a Stop job button. It stays on screen while Advanced is open.
16. **Pop-up dialogs.** "Please confirm" (Cancel, Run); "Command" preview with raw command text and Start; "Agent packet" (text, Copy, Close); picture viewer.

---

## B. Component table

Score: 1 = a 60-year-old non-technical woman would not understand it, 5 = clear at once. "EN" = proposed plain English name. "MR" = proposed Marathi name (Devanagari).

### B1. Top bar and banners
| ID | Control now | What it does | Score | EN | MR |
|---|---|---|---|---|---|
| H1 | "ANIME STUDIO" title | Program name | 5 | Anime Studio | ॲनिमे स्टुडिओ |
| H2 | "Story: <name>" chip | Shows the open story | 3 | Story now: | सध्याची कथा: |
| H3 | "Pack: <name>" chip | Shows the open draft (pack) | 1 | Draft now: | सध्याचा आराखडा: |
| H4 | "Languages: none ticked" chip | Shows chosen output languages | 3 | Languages chosen: | निवडलेल्या भाषा: |
| H5 | "SPEND OFF" badge | Shows whether paid work is allowed | 1 | Paid work: OFF (safe) | पैसे लागणारे काम: बंद (सुरक्षित) |
| H6 | "job: none" | Shows whether background work is running | 1 | Work running now: nothing | आत्ता काहीही चालू नाही |
| H7 | "127.0.0.1" | Developer address of this computer | 1 | remove | काढा |
| H8 | Red banner: "The studio server is older than its code. Stop it and start server.py again before you approve anything." | Warns that approvals are unsafe | 2 | This program is out of date. A helper must restart it before you approve anything. | हा प्रोग्राम जुना आहे. मंजुरी देण्यापूर्वी मदतनीसाने तो पुन्हा सुरू करावा. |
| H9 | Error bar text and "Dismiss" | Shows errors or success for 8 s | 3 | Close this message | हा संदेश बंद करा |
| H10 | "Skip to the steps" link | Keyboard skip link | 2 | Go to the steps | टप्प्यांवर जा |
| H11 | (none) | No visible language switch and no theme switch exist. Dark mode follows the operating system only. | n/a | Add a language switch (English / मराठी) | भाषा निवड जोडा |

### B2. Step list
| ID | Control now | What it does | Score | EN | MR |
|---|---|---|---|---|---|
| T1 | "1 Story - Done" | Step 1 status | 5 | 1. Story (finished) | १. कथा (पूर्ण) |
| T2 | "2 Analysis - Waiting for your approval" | Step 2 status | 2 | 2. Plan the story (needs your OK) | २. कथेचा आराखडा (तुमची मंजुरी हवी) |
| T3 | "3 Images - Locked" | Step 3 status | 3 | 3. Pictures (not open yet) | ३. चित्रे (अजून उघडली नाही) |
| T4 | "4 Read-out - Locked" | Step 4 status | 1 | 4. Summary | ४. सारांश |
| T5 | "5 Render - Locked" | Step 5 status | 2 | 5. Make the video | ५. व्हिडिओ बनवा |
| T6 | "6 Export - Locked" | Step 6 status | 2 | 6. Final files | ६. अंतिम फाइली |
| T7 | Step items are plain list items, not buttons | Look like tabs; tapping does nothing | 2 | Make them jump to the step, or show "Step 2 of 6" as a sentence | प्रत्येक टप्प्यावर थेट जा |
| T8 | "Locked" (status word) | Step cannot open yet | 3 | Not open yet | अजून उघडले नाही |
| T9 | "Waiting for your approval" (status word) | Needs the user's OK | 3 | Needs your OK | तुमची मंजुरी हवी |

### B3. Scope bar and job bar
| ID | Control now | What it does | Score | EN | MR |
|---|---|---|---|---|---|
| S0a | "Writer: free writer (super-vl)" chip | Shows the AI that writes the plan | 1 | AI that writes the plan: Super VL (free) | आराखडा लिहिणारा AI: Super VL (मोफत) |
| S0b | "No job running. Each step asks before it starts anything." | Says nothing runs without asking | 4 | Nothing is running. Nothing starts until you say yes. | काहीही चालू नाही. तुम्ही हो म्हटल्याशिवाय काहीही सुरू होत नाही. |

### B4. Step 1: Story card
| ID | Control now | What it does | Score | EN | MR |
|---|---|---|---|---|---|
| S1 | "Where you stopped" | Heading for the next step | 3 | Where we are now | आत्ता आपण कुठे आहोत |
| S2 | "Done" badge | Story step finished | 4 | Finished | पूर्ण |
| S3 | "SOURCE.md saved" | Story file saved | 1 | Your story is saved | तुमची कथा जतन झाली आहे |
| S4 | "Next: Run the pack validator on pack_super-vl_..." | Says what comes next | 2 | Next: check the draft for mistakes | पुढचे काम: आराखडा तपासा |
| S5 | "Continue" | Moves to the next step | 4 | Go to the next step | पुढच्या टप्प्यावर जा |
| S6 | "story.json is missing: run director/backfill_registry.py --apply" | Warns a file is missing | 0 | A file is missing. Ask the helper to fix it. | एक फाइल हरवली आहे. मदतनीसाला दुरुस्त करायला सांगा. |
| S7 | "RUN_REPORT.md is missing: run director/..." | Same warning | 0 | Same as above | वरीलप्रमाणे |
| S8 | "Story" dropdown; options end with "- next: ..." | Picks the story | 2 | Which story? | कोणती कथा? |
| S9 | "-- new story --" option | Starts a new story | 4 | Start a new story | नवीन कथा सुरू करा |
| S10 | "New slug (if creating)" input | Name of a new story | 1 | Short name for a new story (small English letters, numbers, no spaces) | नवीन कथेचे छोटे नाव (इंग्रजी छोटी अक्षरे, आकडे, जागा नाही) |
| S11 | "Story text (max 204800 bytes UTF-8)" box | Where the story is pasted | 2 | Paste your story here (about 200 KB at most) | तुमची कथा इथे पेस्ट करा (सुमारे २०० KB पर्यंत) |
| S12 | "overwrite if SOURCE.md exists" checkbox | Allows replacing the saved story | 1 | Replace the story already saved (be careful) | आधी जतन केलेली कथा बदला (काळजीपूर्वक) |
| S13 | "Save story" | Saves the text | 4 | Save story | कथा जतन करा |
| S14 | "Save to begin. Then tick the languages." | Hint | 3 | Save the story first, then choose languages. | आधी कथा जतन करा, मग भाषा निवडा. |
| S15 | Legend: "Languages to make (tick at least one; the order you tick is the priority)" | Explains language choice | 2 | Which languages should the video be in? Tick one or more. The first one you tick is the main language. | कोणत्या भाषेत व्हिडिओ? एक किंवा अधिक निवडा. आधी निवडलेली भाषा मुख्य. |
| S16 | Pills "English", "Hindi", "Marathi" | Tick languages | 4 | English / Hindi / Marathi | इंग्रजी / हिंदी / मराठी |
| S17 | "All (English, Hindi, Marathi)" | Ticks all three | 3 | Select all three | तिन्ही निवडा |
| S18 | "Saved: none saved yet" | Shows saved languages | 2 | Saved languages: none yet | जतन केलेल्या भाषा: अजून नाही |
| S19 | "Save languages" | Saves the choice | 3 | Save my language choice | माझी भाषा निवड जतन करा |
| S20 | "Voices" heading | Voice settings | 2 | Voice settings | आवाजाची सेटिंग्ज |
| S21 | "English: use the H3 built-in voice" checkbox | Adds an extra English render | 1 | Use the built-in English voice (takes extra time; leave off) | प्रोग्रामचा स्वतःचा इंग्रजी आवाज (जास्त वेळ लागतो; बंद ठेवा) |
| S22 | Warning: "makes an extra English render ... Leave it off to use ElevenLabs (the default)." | Explains cost in time | 1 | Leave this off unless the helper asks. Turning it on makes the video take longer. | मदतनीस सांगेपर्यंत बंद ठेवा. सुरू केल्यास व्हिडिओ बनायला जास्त वेळ लागेल. |
| S23 | "Hindi: ElevenLabs (fixed). Marathi: ElevenLabs (fixed)." | States fixed voices | 1 | Hindi and Marathi voices are set automatically. | हिंदी आणि मराठी आवाज आपोआप निवडले जातात. |
| S24 | "Save voices" | Saves voice choice | 3 | Save voice choice | आवाज निवड जतन करा |
| S25 | "Background music" heading | Music option | 3 | Background music (optional) | पार्श्वसंगीत (ऐच्छिक) |
| S26 | "Add background music (off by default)" checkbox | Turns music on | 3 | Add background music (off for now) | पार्श्वसंगीत जोडा (आत्ता बंद) |
| S27 | "Music manifest (track id, path, license, bpm, lufs)" label | Asks for a music list file | 0 | Music list file (the file that lists your songs) | संगीत यादीची फाइल (गाण्यांची यादी) |
| S28 | "path to the music manifest (JSON)" box | Path to that file | 1 | Where is the music list file? | संगीत यादी फाइल कुठे आहे? |
| S29 | "Save music choice" | Saves music setting | 3 | Save music choice | संगीत निवड जतन करा |
| S30 | "Voice map (one voice per character, per language)" | Which voice for each character | 1 | Which voice speaks for each character | प्रत्येक पात्राला कोणता आवाज |
| S31 | "Tick and save the languages first." | Says a step is missing | 4 | Choose and save languages first. | आधी भाषा निवडा आणि जतन करा. |
| S32 | Voice boxes, placeholder "pending owner choice" | Voice name per character per language | 2 | Voice name for <character> in <language> | <पात्र> चा आवाज (<भाषा>) |
| S33 | "Save voice map" | Saves voice names | 2 | Save these voice names | ही आवाज नावे जतन करा |
| S34 | "No voice is created here. Choosing a voice never calls ElevenLabs." | Reassurance | 2 | Choosing here does not start any paid voice. | इथे निवड केल्याने पैसे लागणारा आवाज सुरू होत नाही. |
| S35 | "YouTube link (captions first; Whisper only if needed)" | Get the story from a YouTube video | 1 | Get the story from a YouTube video (optional) | YouTube व्हिडिओवरून कथा घ्या (ऐच्छिक) |
| S36 | "YouTube link" box, placeholder "paste the YouTube link here" | URL | 4 | Paste the YouTube link here | YouTube ची लिंक इथे पेस्ट करा |
| S37 | "Language of the video" with "Let the server decide" | Video language | 3 | Video language (choose automatically) | व्हिडिओची भाषा (आपोआप) |
| S38 | "Speech-to-text (ASR)" with three options | How words are taken from the video | 1 | How to get the words: use the video's subtitles if there are any / subtitles only / listen to the audio even if subtitles exist | व्हिडिओतले शब्द कसे घ्यायचे |
| S39 | "Replace the existing SOURCE.md" checkbox | Allows replacement | 1 | Replace the story already saved | आधी जतन केलेली कथा बदला |
| S40 | "Get transcript from link" | Fetches the words | 3 | Get the words from this video | या व्हिडिओतले शब्द घ्या |
| S41 | Result text: "Transcript saved", "Not done: ...", "SOURCE.md already exists" | Result of link | 2 | Done: story saved / Not done: reason | झाले: कथा जतन / झाले नाही: कारण |
| S42 | Buttons "Use English / Hindi / Marathi" | Pick video language | 3 | Use this language | ही भाषा वापरा |
| S43 | "Replace SOURCE.md" | Overwrites saved story | 1 | Yes, replace the saved story | होय, जतन केलेली कथा बदला |

### B5. Step 2: Analysis card
| ID | Control now | What it does | Score | EN | MR |
|---|---|---|---|---|---|
| A1 | "Analysis" heading | Step 2 | 2 | 2. Plan the story | २. कथेचा आराखडा |
| A2 | "Waiting for your approval" chip | Status | 3 | Waiting for your OK | तुमच्या मंजुरीची वाट |
| A3 | "Shots ready, awaiting Gate A" | Status line | 1 | The scene list is ready. Waiting for your OK. | दृश्यांची यादी तयार आहे. तुमची मंजुरी हवी. |
| A4 | "Pack name" label and box (pre-filled pack_super-vl_20261106_v1) | Name of this draft | 1 | Name of this draft (leave as shown) | या आराखड्याचे नाव (आहे तसे ठेवा) |
| A5 | "Run story analysis" | Starts the AI that writes the plan (free model) | 2 | Create the story plan (uses a free AI) | कथेचा आराखडा तयार करा (मोफत AI वापरून) |
| A6 | "Writer: free model (super-vl). Fixed for this step." | Says the AI cannot be changed here | 1 | AI used: free "Super VL". You cannot change it here yet. | वापरला जाणारा AI: मोफत Super VL. आत्ता इथे बदलता येत नाही. |
| A7 | "What you must approve" heading | What to check | 3 | What you need to check | तुम्हाला काय तपासायचे आहे |
| A8 | Shot table: Shot ID, Episode, Route, Seconds, Purpose (57 rows) | The scene list | 1 | Scene, Part, Method, Seconds, What happens | दृश्य, भाग, पद्धत, सेकंद, काय घडते |
| A9 | Episode table: Episode, Shots, Seconds | Totals per part | 3 | Part, Scenes, Seconds | भाग, दृश्ये, सेकंद |
| A10 | "Characters: ... Places: ... Props: ... Modes: fl2va:57" | Names and style | 2 | People, Places, Things, Style | माणसे, ठिकाणे, वस्तू, शैली |
| A11 | "Pack check (validator)" heading | Mistake check | 1 | Check for mistakes | चुका तपासा |
| A12 | "The check looks for mistakes in the pack. Gate A cannot be approved while it reports errors." | Explains the check | 2 | This check looks for mistakes. You cannot approve while it finds errors. | ही तपासणी चुका शोधते. चुका असताना मंजुरी देता येणार नाही. |
| A13 | "OK: no errors" chip | Result | 4 | No mistakes found | कोणतीही चूक नाही |
| A14 | "Checked 6 reel(s), 57 shots, 404 s. Format: old (legacy) pack. Warnings: 1." | Result details | 1 | Checked 6 parts, 57 scenes, 404 seconds. Old format. 1 small warning. | ६ भाग, ५७ दृश्ये, ४०४ सेकंद तपासले. जुने स्वरूप. १ छोटी सूचना. |
| A15 | "ROW-02: legacy: V4 column issue, warning only ... route: missing V4 field route" | Warning text | 0 | Small warning: an old-format field is missing. It does not stop you. | छोटी सूचना: जुन्या स्वरूपातील एक माहिती नाही. यामुळे थांबावे लागत नाही. |
| A16 | "Run validator" | Runs the mistake check again | 1 | Check the plan for mistakes again | आराखडा पुन्हा तपासा |
| A17 | "What happens next: after you approve Gate A, the image generation stage becomes available." | Explains next step | 3 | After you approve, the pictures step opens. | तुम्ही मंजूर केल्यावर चित्रांचा टप्पा उघडेल. |
| A18 | "Gate A" heading | Approval 1 | 1 | Approval 1: the scene list | पहिली मंजुरी: दृश्य यादी |
| A19 | "Open" chip | Approval status | 3 | Waiting for you | तुमची वाट |
| A20 | "Story <x> - Pack <y> - Gate A" | Which story and draft | 2 | For story <x>, draft <y> | कथा <x>, आराखडा <y> |
| A21 | "Note (optional for approve, required for reject, max 300 chars)" | Note box label | 2 | Your note (optional for approval; needed to reject) | तुमची नोंद (मंजुरीसाठी ऐच्छिक; नाकारण्यासाठी आवश्यक) |
| A22 | "Approve" | Records approval of Gate A | 4 (label) / safety issue | Approve | मंजूर करा |
| A23 | "Reject" | Records rejection | 4 | Send back (reject) | परत पाठवा (नाकारा) |
| A24 | "What happens next: After approval, image generation (Flow) becomes available." | Next step | 2 | After approval, the pictures step opens. | मंजुरीनंतर चित्रांचा टप्पा उघडेल. |
| A25 | Pop-up: "Please confirm", "Approve Gate A for story ..., pack ...?", buttons Cancel and "Run" | Confirm approval | 2 | Button should read "Yes, approve" and "No, go back" | होय, मंजूर करा / नाही, मागे जा |

### B6. Step 3: Images card
| ID | Control now | What it does | Score | EN | MR |
|---|---|---|---|---|---|
| I1 | "Images" heading | Step 3 | 3 | 3. Pictures | ३. चित्रे |
| I2 | "Locked" / "Waiting for Gate A" | Status | 3 | Not open yet: waiting for approval 1 | अजून उघडले नाही: पहिली मंजुरी हवी |
| I3 | "Build image jobs" | Writes picture work files (no paid call) | 1 | Prepare the picture work list (no payment) | चित्रांची कामाची यादी तयार करा (पैसे लागत नाहीत) |
| I4 | "Approve Gate A first. Then this button writes the image files (no model call, no spend)." | Explains | 2 | Approve the scene list first. This only writes files. Nothing is paid. | आधी दृश्य यादी मंजूर करा. यात फक्त फाइली लिहिल्या जातात. काहीही पैसे लागत नाहीत. |
| I5 | "Make Flow agent packet" | Makes an instruction sheet for the picture helpers | 1 | Make the instruction sheet for the picture helpers | चित्र मदतनीसांसाठी सूचना-पत्र बनवा |
| I6 | "Flow agents run on Haiku, effort LOW; Claude starts them from the chat; this page shows their progress" | Explains helpers | 0 | The picture helpers are started by Claude in the chat. This page shows their progress. | चित्र मदतनीस Claude चॅटमधून सुरू होतात. त्यांची प्रगती इथे दिसेल. |
| I7 | "Full-size check by Claude, then you approve" | Process | 2 | Claude checks each full-size picture; then you approve. | Claude प्रत्येक चित्र पूर्ण आकारात तपासेल; मग तुम्ही मंजूर करा. |
| I8 | "Finals: 0/114", "Pending: 0", "Reviewed: 0" | Picture counts | 2 | Finished pictures: 0 of 114. Waiting: 0. Checked: 0. | पूर्ण चित्रे: ०/११४. प्रलंबित: ०. तपासलेली: ०. |
| I9 | "Gate B" heading, "Locked", "waiting for the previous step" | Approval 2 | 1 | Approval 2: the pictures | दुसरी मंजुरी: चित्रे |

### B7. Step 4: Read-out card
| ID | Control now | What it does | Score | EN | MR |
|---|---|---|---|---|---|
| R1 | "Read-out" heading | Step 4 | 1 | 4. Summary | ४. सारांश |
| R2 | Tile "Reels 6" | Count | 1 | Parts: 6 | भाग: ६ |
| R3 | Tile "Shots 57" | Count | 2 | Scenes: 57 | दृश्ये: ५७ |
| R4 | Tile "Seconds 403.5" | Length | 2 | Total seconds: 403.5 | एकूण सेकंद: ४०३.५ |
| R5 | Tile "Characters 8", "Places 7" | Counts | 2 | People: 8. Places: 7. | माणसे: ८. ठिकाणे: ७. |
| R6 | Tile "Images 0/114" | Pictures finished | 2 | Pictures finished: 0 of 114 | पूर्ण चित्रे: ०/११४ |
| R7 | Tile "Clips planned 171" | Clip count | 1 | Clips planned: 171 | नियोजित क्लिप्स: १७१ |
| R8 | Tile "Est. G4 units 65" | Estimated paid GPU units | 0 | Estimated GPU units (paid) | अंदाजे GPU युनिट (पैसे लागतील) |
| R9 | Tile "Est. minutes 388.2" | Estimated render time | 2 | Estimated minutes to make the video | व्हिडिओ बनवायला अंदाजे मिनिटे |
| R10 | Episode table (Episode, Shots, Seconds) | Per-part totals | 3 | Part, Scenes, Seconds | भाग, दृश्ये, सेकंद |
| R11 | "Characters:", "Places:", "Props:", "Modes:" lines | Lists | 2 | People, Places, Things, Style | माणसे, ठिकाणे, वस्तू, शैली |
| R12 | "Takes:" and "Clips home:" | Tries and clips ready | 0 | Tries per clip. Clips ready on this computer. | प्रत्येक क्लिपचे प्रयत्न. या संगणकावर तयार क्लिप्स. |
| R13 | "Finals:", "Pending:", "Reviewed:" | Picture states | 1 | Finished / Waiting / Checked | पूर्ण / प्रलंबित / तपासलेली |
| R14 | Checks: "shots.json present", "every shot has seconds>0", "no duplicate shot ids" and similar | Automatic checks | 2 | OK: scene file is there / OK: every scene has a length | ठीक: दृश्य फाइल आहे / ठीक: प्रत्येक दृश्याला लांबी आहे |
| R15 | "finals 0 < expected images 114" | Warning | 1 | Pictures are not finished: 0 of 114 | चित्रे अजून पूर्ण झालेली नाहीत: ०/११४ |

### B8. Gate C (inside Read-out) and Step 5: Render card
| ID | Control now | What it does | Score | EN | MR |
|---|---|---|---|---|---|
| GC1 | "Gate C" heading | Approval 3 | 1 | Approval 3: the video plan | तिसरी मंजुरी: व्हिडिओ आराखडा |
| GC2 | "Type START to confirm" box | Typed word to approve | 2 | Type START to approve | मंजुरीसाठी START टाइप करा |
| GC3 | "waiting for the previous step" | Status | 3 | Not open yet | अजून उघडले नाही |
| V1 | "Render" heading | Step 5 | 2 | 5. Make the video | ५. व्हिडिओ बनवा |
| V2 | "Prepare render (no GPU)" | Prepares the plan; no GPU | 1 | Get the video ready (no payment) | व्हिडिओ तयार करा (पैसे लागत नाहीत) |
| V3 | "Prepare is off: the H3 story file is not built for this pack yet. The page shows the exact problems below." | Explains why disabled | 0 | Not ready yet. The video plan is missing. The problems are listed below. | अजून तयार नाही. व्हिडिओ आराखडा नाही. अडचणी खाली दिल्या आहेत. |
| V4 | "Image jobs and assets" heading | Pictures and sound files | 1 | Pictures and sound files | चित्रे आणि आवाज फाइली |
| V5 | "Images: -/114 final Clips: 0 Placeholders: 0 Stale: no" | Counts | 0 | Pictures finished: 0 of 114. Clips: 0. Temporary stand-ins: 0. Out of date: no. | पूर्ण चित्रे ०/११४. क्लिप्स ०. तात्पुरते पर्याय ०. जुने नाही. |
| V6 | "No blocking problems reported." | Status | 3 | No problems stop the video | कोणतीही अडचण थांबवत नाही |
| V7 | Fallback table: Shot, Attempts, Rung, Next action, Your choice | Scenes that need a decision (shown only when present) | 0 | Scenes that need your decision: scene, tries, level, what next, your choice | ज्या दृश्यांना तुमचा निर्णय हवा |
| V8 | Fallback buttons (human choices) and "Note (optional)" | Records choice | 1 | Your choice, with an optional note | तुमची निवड (नोंद ऐच्छिक) |
| V9 | "Step 9 render check" with red "not run" chip | Final video check | 0 | Final video check: not run yet | अंतिम व्हिडिओ तपासणी: अजून झाली नाही |
| V10 | "H3 field author (writes the missing render fields)" | Fills missing details with AI | 0 | Automatic detail writer (fills missing video details, free AI) | व्हिडिओसाठी राहिलेली माहिती भरणारा (मोफत AI) |
| V11 | "Derived by rule: - Missing: 0" | Counts | 0 | Filled by rules: - . Still missing: 0. | नियमांनी भरलेले: -. अजून राहिलेले: ०. |
| V12 | "Cache: -" orange chip | Saved results | 0 | Saved results: none yet | जतन केलेले निकाल: अजून नाही |
| V13 | "Preview author prompts (dry run)" | Shows what would be sent, sends nothing | 0 | See what the AI would be asked (nothing is sent) | AI ला काय विचारले जाईल ते पाहा (काहीही पाठवले जात नाही) |
| V14 | "To run the author (free model), type AUTHOR FIELDS exactly" | Typed phrase to start | 0 | To start the detail writer, type the words AUTHOR FIELDS exactly | तपशील भरणारा सुरू करण्यासाठी AUTHOR FIELDS हे शब्द तसेच टाइप करा |
| V15 | Typed box for AUTHOR FIELDS | Confirmation | 1 | Type the words here | इथे शब्द टाइप करा |
| V16 | "Run author (free model)" (disabled) | Starts the free AI writer | 1 | Start the detail writer (free AI) | तपशील भरणारा सुरू करा (मोफत AI) |
| V17 | "Off: the server must be started with ANIME_STUDIO_ALLOW_FREE_MODEL=1 before this runs." | Says why off | 0 | Off. Ask the helper to switch it on. Nothing is sent. | बंद आहे. मदतनीसाला सुरू करायला सांगा. काहीही पाठवले जात नाही. |
| GD1 | "Gate D" heading | Approval 4 (final check) | 1 | Approval 4: final check | चौथी मंजुरी: अंतिम तपासणी |
| GD2 | Chips "no BGM (2-stem mix)" / "BGM on (3-stem)" | Music mix | 0 | Background music: off / on | पार्श्वसंगीत: बंद / सुरू |
| GD3 | Chip "Safe zone: bottom 896 / top 360 / sides 160 (Instagram Reels + YouTube Shorts)" | Subtitle margins | 0 | Keep subtitles inside the safe edges (for Instagram and YouTube Shorts) | उपशीर्षके सुरक्षित कडांच्या आत ठेवा (Instagram आणि YouTube Shorts साठी) |
| GD4 | Row "English: not ready" | Per-language status | 2 | English: not ready yet | इंग्रजी: अजून तयार नाही |
| GD5 | "Voice-over files: 0/0 (missing)", "Captions (.ass): missing", "Final video (mp4): missing" | Files | 1 | Voice files / Subtitle file / Final video file: missing | आवाज फाइल / उपशीर्षक फाइल / अंतिम व्हिडिओ फाइल: नाही |
| GD6 | "Approve is off: the Step 9 render check has not passed." | Why approval is off | 1 | Approve is off: the final video check has not passed yet. | मंजुरी बंद: अंतिम व्हिडिओ तपासणी अजून पास झाली नाही. |

### B9. Step 6: Export card, Ops and Runs (bottom of the page)
| ID | Control now | What it does | Score | EN | MR |
|---|---|---|---|---|---|
| E1 | "Export" heading | Step 6 | 2 | 6. Final files | ६. अंतिम फाइली |
| E2 | "Reel number" box (value 1) | Part number | 1 | Part number | भाग क्रमांक |
| E3 | "Show clips for this reel" (disabled until Gate D) | Lists clips | 2 | Show the clips for this part | या भागाचे क्लिप्स दाखवा |
| E4 | "Final reel files are not assembled yet. This shows the clips that are ready." | Explains | 2 | The final video is not put together yet. This shows the clips that are ready. | अंतिम व्हिडिओ अजून जोडलेला नाही. तयार क्लिप्स इथे दिसतील. |
| O1 | "Ops: disk, server and Colab spend" | Computer and paid-use check | 0 | Computer and spending check | संगणक आणि खर्च तपासणी |
| O2 | "Disk C: 2.87 GB free" / "Disk D: 8.94 GB free" with "ok" | Disk space | 1 | Space on drive C: 2.87 GB free. OK. | ड्राइव्ह C मध्ये २.८७ GB मोकळे. ठीक. |
| O3 | "Server: pid 37320, started 2026-11-07 03:15, stale: yes" | Program status | 0 | Program started at 03:15. Out of date: yes. | प्रोग्राम ०३:१५ ला सुरू. जुना: होय. |
| O4 | "Colab spend: 0 of 15 units. Sessions listed: -" | Paid GPU use | 0 | Paid GPU time used: 0 of 15 units. Open sessions: none. | वापरलेला पैसे लागणारा GPU वेळ: ०/१५. सुरू असलेली सत्रे: काही नाही. |
| RN1 | "Runs & documents" heading | Past runs | 1 | Past runs and records | मागील कामे आणि नोंदी |
| RN2 | Hint: "Every writer and analysis run, with its model and each step. Read only: the record is stories/<slug>/RUNS.jsonl, and RUN_REPORT.md is written next to it." | Explains | 0 | A list of past story-plan runs. You can only look here. Nothing changes. | आराखडा तयार केलेल्या कामांची यादी. इथे फक्त पाहता येते. काहीही बदलत नाही. |
| RN3 | Table columns Story, Source, Model, Status, Last run, Packs, Runs | Overview | Story 4 / Source 2 / Model 1 / Status 3 / Runs 2 | Story, Where the story came from, AI used, Result, Last time, Drafts, Times run | कथा, कथा कुठून आली, वापरलेला AI, निकाल, शेवटची वेळ, आराखडे, वेळा |
| RN4 | Status badges "OK", "Stopped" | Result of past run | 3 | Finished / Stopped | पूर्ण / थांबवले |
| RN5 | Row click (opens details) | Expands a story | 1 | Tap a story to see its details | तपशील पाहण्यासाठी कथेवर टॅप करा |
| RN6 | Details: "Runs of <slug>", "Steps" table (Run, Step, Stage, Status, Via, Model, Effort, Pack, Time, Note), "Open RUN_REPORT.md as text" | Full run log | 0 | Details: each run, each step, which AI and how much effort. Open the report. | तपशील: प्रत्येक काम, प्रत्येक टप्पा, कोणता AI, किती प्रयत्न. अहवाल उघडा. |

### B10. Advanced tools (folded at the bottom)
| ID | Control now | What it does | Score | EN | MR |
|---|---|---|---|---|---|
| AD1 | "Advanced tools (manual controls)" | Opens expert controls | 2 | Expert controls (for the helper; closed by default) | तज्ञांसाठी नियंत्रणे (मदतनीसासाठी) |
| AD2 | Footer "Job log tail (last 12 lines, redacted)" | Program output | 0 | What the program is doing (last lines) | प्रोग्राम काय करत आहे (शेवटच्या ओळी) |
| AD3 | "Stop job" (footer, disabled) | Stops the local process | 2 | Stop the work now | आता काम थांबवा |
| AD4 | Nav "Story" | Opens advanced story | 4 | Story text | कथा मजकूर |
| AD5 | Nav "Images" | Opens advanced images | 3 | Pictures | चित्रे |
| AD6 | Nav "Bridge" | Opens key-frame step | 0 | Key frames (expert) | मुख्य फ्रेम (तज्ञ) |
| AD7 | Nav "Video" | Opens video controls | 1 | Video clips (expert) | व्हिडिओ क्लिप्स (तज्ञ) |
| AD8 | Nav "Export" | Opens export | 3 | Final files (expert) | अंतिम फाइली (तज्ञ) |
| AD9 | Stray bullet dots after "Story", "Bridge", "Video" (list style not reset) | Visual artefact | n/a | remove | काढा |

#### Advanced: Story (separate story picker)
| ID | Control now | What it does | Score | EN | MR |
|---|---|---|---|---|---|
| AS1 | "Story (slug)" dropdown (shows ashtavakra_gita_katha while top shows upanishad_ganga_ep4_ashtavakra) | Picks a different story than the top bar | 0 | One story only: follow the top bar. If kept: "Story (separate, not the one at the top)" | एकच कथा: वरचीच कथा. वेगळी असेल तर स्पष्ट लिहा. |
| AS2 | "Pack" dropdown "(no packs yet)" | Picks a draft | 1 | Draft | आराखडा |
| AS3 | "Writer: Free writer (set by the server)" | Shows writer | 0 | AI writer: free | AI लेखक: मोफत |
| AS4 | "Writer model" dropdown: "super-vl (free, OpenRouter)" / "ultra (free, OpenRouter)" | Chooses AI for the two buttons below only | 0 | AI for "make new plan" and "continue plan": Super VL (free) / Ultra (free) | नवीन आराखडा आणि अर्धवट आराखडा पुढे नेण्यासाठी AI: Super VL (मोफत) / Ultra (मोफत) |
| AS5 | "Studio OK, flow OK, Colab CLI OK, NVIDIA key files: 15 (count only)." | Connection check | 0 | Connections: program OK, picture tool OK, GPU tool OK, free AI keys found: 15 | जोडण्या: प्रोग्राम ठीक, चित्र साधन ठीक, GPU साधन ठीक, मोफत AI च्या चाव्या: १५ |
| AS6 | "Story text (max 200 KB)", "(73367 bytes on disk)", text box | Story text | 1 | Story text. Size on disk: about 72 KB | कथा मजकूर. फाइलचा आकार: सुमारे ७२ KB |
| AS7 | "Load story" (R) | Reads the saved story | 2 | Load the saved story | जतन केलेली कथा आणा |
| AS8 | "Replace the saved story if it exists" checkbox | Permits overwrite | 2 | Replace the saved story (be careful) | जतन केलेली कथा बदला (काळजीपूर्वक) |
| AS9 | "Save story" (dark button, W) | Writes the file | 2 | Save story (this writes the file) | कथा जतन करा (यामुळे फाइल बदलते) |
| AS10 | "New pack name" box, placeholder "pack_name" | Name for new draft | 0 | New draft name | नवीन आराखड्याचे नाव |
| AS11 | "Run writer: new pack" (N, W) | Calls the free AI and writes files; no typed confirm, but a preview with Start | 0 | Make a new story plan with the free AI | मोफत AI वापरून नवीन कथा-आराखडा बनवा |
| AS12 | "Resume pack" (N, W) | Continues an unfinished plan | 0 | Continue an unfinished plan (free AI) | अर्धवट आराखडा पुढे चालवा (मोफत AI) |
| AS13 | "Check pack" (R) | Read-only check | 1 | Check the plan for mistakes (changes nothing) | आराखडा तपासा (काही बदलत नाही) |
| AS14 | "Stages": eight badges "Stage 1 NOT RUN" ... "Stage 5" | Parts of the plan | 0 | Parts of the plan: 1 story, 2 people and places, 3 scenes (one per part), 5 captions. Not run yet. | आराखड्याचे भाग: १ कथा, २ माणसे-ठिकाणे, ३ दृश्ये (प्रत्येक भागाची), ५ मजकूर. अजून चालले नाही. |
| AS15 | "Gate 1 (story analysis as written)" box | First approval text | 1 | Approval 1 text (the plan as written) | पहिली मंजुरी: लिहिलेला आराखडा |
| AS16 | Episodes table: #, Shots, Seconds, Check | Per part | 2 | Part, Scenes, Seconds, Result | भाग, दृश्ये, सेकंद, निकाल |
| AS17 | "Characters (bible)" and "Places (bible)" lists | People and places | 1 | People in this story / Places in this story | या कथेतील माणसे / ठिकाणे |
| AS18 | Shots table: Shot, Ep, Mode, Sec, Cut in -> cut out, Issues | Per scene | 0 | Scene, Part, Method, Seconds, Start to end, Problems | दृश्य, भाग, पद्धत, सेकंद, सुरुवात ते शेवट, अडचणी |
| AS19 | "Check pack result (JSON)" | Raw check result | 0 | Check result (for the helper) | तपासणीचा निकाल (मदतनीसासाठी) |

#### Advanced: Images (six tabs)
| ID | Control now | What it does | Score | EN | MR |
|---|---|---|---|---|---|
| AI1 | "Adhyay" dropdown 1 to 12 | Chapter | 0 | Chapter (adhyay) number | अध्याय क्रमांक |
| AI2 | "Refresh" (R) | Reloads lists | 2 | Reload the list | यादी पुन्हा आणा |
| AI3 | Tab "Series" | Character and place pictures | 1 | Characters and places pictures | पात्रे आणि ठिकाणांची चित्रे |
| AI4 | Tab "Jobs" | Picture work list | 1 | Work list | कामाची यादी |
| AI5 | Tab "Shots" | Picture choice per scene | 2 | Pictures per scene | प्रत्येक दृश्यासाठी चित्रे |
| AI6 | Tab "Progress" | Progress per picture | 1 | Progress | प्रगती |
| AI7 | Tab "Queue" | Waiting pictures | 1 | Waiting pictures | प्रलंबित चित्रे |
| AI8 | Tab "Finals" | Finished pictures | 3 | Finished pictures | पूर्ण चित्रे |
| AI9 | Series table: Group, Id, Name, Chip, Sheet file, Accepted | Lists | 0 | Group, Code, Name, Tag, Picture file, Approved | गट, कोड, नाव, खूण, चित्र फाइल, मंजूर |
| AI10 | Jobs table: Shot, Scene, Chips, Attempts / cap, Status, Actions | Work list | 1 | Scene, Tags, Tries, Status, Actions | दृश्य, खुणा, प्रयत्न, स्थिती, कृती |
| AI11 | "Packet" button (per job) | Instruction sheet | 1 | Make instruction sheet | सूचना-पत्र बनवा |
| AI12 | "Build*" button (disabled; tooltip "gap G1") | Not available | 0 | Not available yet (remove the asterisk and the code word) | अजून उपलब्ध नाही |
| AI13 | Shots table: Shot, Candidate, Q1 to Q6, Verdict, Actions. Q cells show "[object Object]" | Review answers | 0 | Scene, Picture, Question 1 to 6, Verdict, Actions (answers shown as words) | दृश्य, चित्र, प्रश्न १ ते ६, निकाल, कृती |
| AI14 | Verdict badges: BLOCK, UNSURE, NOT RUN, ERROR | Reviewer result | 1 | Not good enough / Not sure / Not checked / Error | चांगले नाही / खात्री नाही / तपासले नाही / चूक |
| AI15 | "Neighbour sheet" (per shot) | Makes a side-by-side sheet | 0 | Make a side-by-side sheet | शेजारी-शेजारी चित्रांची पत्रक बनवा |
| AI16 | "Run reviewer" (N, W) | Asks the free AI reviewer | 2 | Ask the reviewer to check | परीक्षकाला तपासायला सांगा |
| AI17 | "details" link | Shows reviewer notes | 3 | See the reviewer's notes | परीक्षकाच्या नोंदी पाहा |
| AI18 | "Queue kept" | Adds the picture to the final waiting list | 0 | Keep this picture for the final list | हे चित्र अंतिम यादीसाठी ठेवा |
| AI19 | "Accept (owner)" with check box "I looked at full size" | Owner acceptance | 1 | I approve this picture | मी हे चित्र मंजूर करतो |
| AI20 | Progress table with grey "legacy (no decided_by)" rows | Old records | 0 | Old records (no one recorded who decided) | जुन्या नोंदी (कोणी ठरवले ते नोंद नाही) |
| AI21 | Queue counts: pending, filed, accepted | Counts | 2 | Waiting / moved to final / approved | प्रलंबित / अंतिम मध्ये / मंजूर |
| AI22 | "Collect" (W) | Copies from Downloads into final (refuses existing) | 1 | Copy finished pictures in from the Downloads folder | डाउनलोड फोल्डरमधून पूर्ण चित्रे आत कॉपी करा |
| AI23 | "Tidy plan" (R) | Shows what would move; moves nothing | 0 | Show what would be moved (moves nothing) | कोणत्या फाइली हलतील ते दाखवा (काहीही हलवत नाही) |
| AI24 | "18 final(s). Click a tile for full size." | Count and hint | 2 | 18 finished pictures. Tap one to see it big. | १८ पूर्ण चित्रे. मोठे पाहण्यासाठी एकावर टॅप करा. |
| AI25 | Picture tiles | Opens picture | 4 | (keep) | (तसेच) |
| AI26 | "Close picture" (viewer) | Closes viewer | 4 | Close | बंद करा |

#### Advanced: Bridge, Video, Export
| ID | Control now | What it does | Score | EN | MR |
|---|---|---|---|---|---|
| BR1 | "Bridge (Flow 2K to video keyframes)" | Turns high-res pictures into key frames | 0 | Key frames: from pictures to video (expert) | मुख्य फ्रेम: चित्रांपासून व्हिडिओपर्यंत (तज्ञ) |
| BR2 | "Source: adhyay_01\final (10 LEAP keyframes expected). Output: keyframes_h3\." | Folders | 0 | Takes the chapter 1 final pictures and makes 10 key frames for the leap scenes | अध्याय १ ची अंतिम चित्रे घेऊन लीप दृश्यांसाठी १० मुख्य फ्रेम बनवा |
| BR3 | "Target size" dropdown: "768x1344 (tested in T0)" / "864x1536 (untested ... about 28% more compute)" | Picture size | 0 | Picture size (use the first one) | चित्राचा आकार (पहिला वापरा) |
| BR4 | "Dry run" (R) | Shows what would be made | 2 | See what would be made (nothing changes) | काय बनेल ते पाहा (काहीही बदलत नाही) |
| BR5 | "Write keyframes" (W, dark) | Writes key-frame files | 2 | Make the key frames (writes files) | मुख्य फ्रेम बनवा (फाइली लिहिल्या जातात) |
| BR6 | Table: File, Status, Detail, Removed px | Result | 0 | File, Result, Note, Pixels removed | फाइल, निकाल, नोंद, काढलेले पिक्सेल |
| VD1 | "Video" heading (NOT OPENED, from source) | Clip batches | 1 | Make video clips (expert) | व्हिडिओ क्लिप्स बनवा (तज्ञ) |
| VD2 | "Shot file" dropdown | Which shot list | 0 | Which shot list | कोणती दृश्य यादी |
| VD3 | "Batch" box, value "leap01_05_sing8" | Name of clip group | 0 | Name of this clip group | या क्लिप गटाचे नाव |
| VD4 | "Route: From the shot file (sing8 for LEAP)" | Method (fixed) | 0 | Method: taken from the shot list | पद्धत: दृश्य यादीतून घेतली |
| VD5 | Scope: "Shots / Reel / All" with boxes | Which clips | 1 | Which clips: some shots / one part / all | कोणत्या क्लिप्स: काही दृश्ये / एक भाग / सर्व |
| VD6 | "Keyframes folder" box | Folder of key frames | 0 | Folder of key frames (leave empty) | मुख्य फ्रेमचे फोल्डर (रिकामे ठेवा) |
| VD7 | "Profile 5, target Colab" | Quality setting for Colab | 0 | Quality setting 5, for Google Colab | गुणवत्ता सेटिंग ५, Google Colab साठी |
| VD8 | "Resolution: As in the keyframes folder (set in Bridge)" | Size | 0 | Size: same as the key frames | आकार: मुख्य फ्रेम प्रमाणे |
| VD9 | "1 Prepare batch (no GPU)" (W) | Prepares a clip group | 1 | Get the clip group ready (no payment) | क्लिप गट तयार करा (पैसे लागत नाहीत) |
| VD10 | Batches table: Batch, run.py bytes, Shots, Embed MB | Groups | 0 | Groups ready: name, size, shots, size in MB | तयार गट: नाव, आकार, दृश्ये, MB |
| VD11 | "H3 engine (prepare only)" status box: "NOT BUILT" | Video engine | 0 | Video engine: not installed yet | व्हिडिओ इंजिन: अजून बसवलेले नाही |
| VD12 | "Prepare (H3, no GPU)" button | Prepares engine files | 0 | Prepare the video engine files (no payment) | व्हिडिओ इंजिनच्या फाइली तयार करा (पैसे लागत नाहीत) |
| VD13 | "Colab" heading, "Balance: unknown  Rate: unknown" | Paid GPU service | 0 | Google Colab (paid GPU service). Account balance: not checked yet. | Google Colab (पैसे लागणारी GPU सेवा). खात्यातील शिल्लक: अजून तपासली नाही. |
| VD14 | "Check Colab" (R, network check) | Contacts Colab | 1 | Check the Colab account (contacts Google, costs nothing) | Colab खाते तपासा (Google शी संपर्क, पैसे लागत नाहीत) |
| VD15 | "Run on Colab... (spend gate)" (red, $) | Starts a paid GPU session | 0 | Start a paid GPU session (this costs money) | पैसे लागणारे GPU सत्र सुरू करा (यासाठी पैसे लागतील) |
| VD16 | Colab sessions table with "Stop session <name>" (OPS) | Stops a session | 0 | Open sessions: name, GPU, status, stop | सुरू असलेली सत्रे: नाव, GPU, स्थिती, थांबवा |
| VD17 | "Live" box "No job output yet." | Live output | 2 | What is happening now | आत्ता काय चालले आहे |
| VD18 | "Stop job (local process only)" (OPS) | Stops this computer's process only | 1 | Stop the work on this computer (the cloud part may keep running) | या संगणकावरील काम थांबवा (क्लाउडवरील भाग चालू राहू शकतो) |
| VD19 | "Clips home: 0" | Clips ready | 1 | Clips ready here: 0 | इथे तयार क्लिप्स: ० |
| VD20 | Clips table: Shot / take, File, Seconds, Size, QA, Sheet, Visual QA | Clip list | 1 | Clip, file, seconds, size, checked?, check sheet, picture check | क्लिप, फाइल, सेकंद, आकार, तपासले?, तपासणी पत्रक, चित्र तपासणी |
| VD21 | Visual QA box: "Direction JSON" and "Vision model" (two NVIDIA models) | Picture check settings | 0 | Instructions file / model that looks at pictures | सूचना फाइल / चित्र पाहणारा मॉडेल |
| EX1 | "Export" heading (advanced) | Export | 3 | Final files (expert) | अंतिम फाइली (तज्ञ) |
| EX2 | "Reel" box and "Load" (R) | Part | 2 | Part number and "Show" | भाग क्रमांक आणि "दाखवा" |
| EX3 | "Clips in order" list | Order | 2 | Clips in order | क्लिप्स क्रमाने |
| EX4 | "Assembly plan" box, "NOT BUILT" | How it would be joined | 1 | How the video will be joined (not yet) | व्हिडिओ कसा जोडला जाईल (अजून नाही) |
| EX5 | "Reel files" box, "none yet" | Final files | 1 | Final files for this part | या भागाच्या अंतिम फाइली |
| EX6 | "Open folder" (disabled, X) | Not available | 0 | remove | काढा |

### B11. Pop-up dialogs
| ID | Control now | What it does | Score | EN | MR |
|---|---|---|---|---|---|
| MD1 | "Command" title, "Exact command (argv, one item per line)" with raw text | Shows the raw command | 0 | What will run (plain words first; raw text hidden) | काय चालेल (साध्या शब्दांत) |
| MD2 | "Preview (nothing runs yet)", "Start", "Cancel" | Two steps before any run | 2 | Show what will happen / Yes, start / Go back | काय होईल ते दाखवा / होय, सुरू करा / मागे जा |
| MD3 | "Preview expires in N s." | Time limit | 2 | This preview stops working in N seconds | हे पूर्वावलोकन N सेकंदांनंतर बंद होईल |
| MD4 | "Type EXECUTE <n> to start" | Typed confirmation for paid runs | 1 | Type the exact words shown to start (this may cost money) | सुरू करण्यासाठी दिसणारे शब्द तसेच टाइप करा (पैसे लागू शकतात) |
| MD5 | "Please confirm" with "Cancel" and "Run" | Confirms wizard actions | 2 | Yes, go ahead / No, go back | होय, पुढे जा / नाही, मागे जा |
| MD6 | "Agent packet: <shot>" with "Flow agents run on Haiku, effort LOW", "Saved at: <path>", Copy and Close | Shows the instruction sheet | 1 | Instruction sheet for <scene>. Copy it. Close. | <दृश्य> साठी सूचना-पत्र. कॉपी करा. बंद करा. |
| MD7 | "Command" close button | Closes | 4 | Close | बंद करा |

---

## C. Jargon list (words a 60-year-old would not know)

| Term on screen or in code | Where | Plain English | Marathi |
|---|---|---|---|
| Gate A / B / C / D | Analysis, Images, Read-out, Render | Approval 1 / 2 / 3 / 4 | मंजुरी १ / २ / ३ / ४ |
| Gate note | Gates | Your note | तुमची नोंद |
| Stage 1, 2, 3e1–3e5, 5 | Story advanced | Parts of the plan | आराखड्याचे भाग |
| pack / pack_super-vl_20261106_v1 | everywhere | draft (name of this version) | आराखडा |
| shots / SHOT-001 | Analysis, Images | scenes / scene numbers | दृश्ये / दृश्य क्रमांक |
| validator / Check pack / Pack check | Analysis, Story | mistake check | चूक तपासणी |
| H3 / H3 engine / H3 field author | Voices, Render, Video | video engine / automatic detail writer | व्हिडिओ इंजिन / तपशील भरणारा |
| Step 9 render check | Render | final video check | अंतिम व्हिडिओ तपासणी |
| LUT | not found in the page source | (no text on screen) | — |
| preview token | in code only (sent back to the server) | (not shown; visible text is "Preview expires in N s") | (दिसत नाही) |
| bible (Characters (bible)) | Story, Read-out | people and places in the story | पात्र आणि ठिकाणे |
| reel / Reel number | Analysis, Export, Video | part | भाग |
| Episode | Analysis, Read-out | part (same as reel, the screens use both words) | भाग |
| Adhyay | Images, Bridge | chapter | अध्याय |
| route / fl2va | Analysis, Video | method | पद्धत |
| mode / legacy / old (legacy) pack | Analysis, Images | old format | जुने स्वरूप |
| V4 column / ROW-02 | Analysis warning | (hide; code) | (लपवा) |
| shots.json, bible.json, story.json, PACK.md | checks | story and scene files | कथा आणि दृश्य फाइल |
| SOURCE.md | Story | saved story file | जतन केलेली कथा फाइल |
| RUN_REPORT.md, RUNS.jsonl | Runs | run report, run log | कामाचा अहवाल, कामाची नोंद |
| Flow | Images, Bridge | picture maker (Flow) | चित्र निर्माता (Flow) |
| Flow agent / agent packet | Images, Images tabs | picture helper / instruction sheet | चित्र मदतनीस / सूचना-पत्र |
| Haiku, effort LOW | Images | a small fast helper | छोटा जलद मदतनीस |
| Nano Banana 2.1 x2 | Images queue | picture model | चित्र मॉडेल |
| Q1 to Q6 | Images, Shots | questions 1 to 6 | प्रश्न १ ते ६ |
| PASS / BLOCK / UNSURE | Shots | Good / Not good enough / Not sure | चांगले / चांगले नाही / खात्री नाही |
| review_shot, reviewer (NVIDIA) | Shots | AI reviewer (NVIDIA) | NVIDIA AI परीक्षक |
| neighbour sheet | Shots | side-by-side sheet | शेजारी-शेजारी पत्रक |
| queue / Queue kept / Collect / Tidy plan | Images | waiting list / keep / copy in / preview of moves | प्रलंबित यादी / ठेवा / आत कॉपी करा / हलवण्याचा आराखडा |
| finals | Images | finished pictures | पूर्ण चित्रे |
| accepted / Accept (owner) | Images | approved by you | तुम्ही मंजूर केलेले |
| decided_by / legacy (no decided_by) | Progress | who decided / old record | कोणी ठरवले / जुनी नोंद |
| Build* / gap G1 / gap G12 | Images, Export | not available yet | अजून उपलब्ध नाही |
| Bridge | Advanced | picture-to-video step | चित्र ते व्हिडिओ पायरी |
| keyframes / keyframes_h3 | Bridge, Video | key frames (main picture for each clip) | मुख्य फ्रेम |
| 2K | Bridge | high resolution | उच्च दर्जा |
| 768x1344, 864x1536 | Bridge | picture size | चित्राचा आकार |
| T0 | Bridge | (tested earlier; remove) | (काढा) |
| batch | Video | group of clips | क्लिप गट |
| sing8, LEAP, profile 5 | Video | clip method names (hide) | (लपवा) |
| Kaliya, Mahadev, Dhenukasura | Runs | story names (fine as names) | कथेची नावे |
| Colab, G4, A100 | Video, Ops | paid GPU service and GPU types | पैसे लागणारी GPU सेवा |
| units, est. G4 units, units/h | Ops, Read-out | paid GPU units | पैसे लागणारे GPU युनिट |
| cap | Video | limit | मर्यादा |
| Embed MB | Video | size in MB | MB मध्ये आकार |
| run.py bytes | Video | (hide) | (लपवा) |
| QA / Visual QA / Sheet | Video | quality check / picture check (AI) / check sheet | दर्जा तपासणी / चित्र तपासणी (AI) / तपासणी पत्रक |
| Direction JSON | Visual QA | instructions file | सूचना फाइल |
| Vision model | Visual QA | model that looks at pictures | चित्र पाहणारा मॉडेल |
| Assembly plan / reel files | Export | how the video is joined / final files for this part | व्हिडिओ कसा जोडला जाईल / या भागाच्या अंतिम फाइली |
| Clips home | Read-out, Video | clips ready on this computer | इथे तयार क्लिप्स |
| ASR / Speech-to-text | Story | getting words from speech | बोलण्यातून शब्द घेणे |
| Whisper | Story | automatic speech-to-text tool | स्वयंचलित बोलणे-ते-लिखाण |
| captions / .ass | Story, Gate D | subtitles / subtitle file | उपशीर्षके / उपशीर्षक फाइल |
| ElevenLabs | Voices | voice service (ElevenLabs) | आवाज सेवा (ElevenLabs) |
| BGM, 2-stem mix, 3-stem | Story, Gate D | background music / music mix | पार्श्वसंगीत / संगीत मिश्रण |
| safe zone | Gate D | safe edges | सुरक्षित कडा |
| mp4 | Gate D | video file | व्हिडिओ फाइल |
| fallback / Rung / human choices | Render | backup plan / level / your choice | बॅकअप योजना / पातळी / तुमची निवड |
| Attempts / cap | Images | tries / limit | प्रयत्न / मर्यादा |
| derived by rule | Render | filled in by rules | नियमांनी भरलेले |
| Cache | Render | saved results | जतन केलेले निकाल |
| dry run | many | test run (changes nothing) | चाचणी (काहीही बदलत नाही) |
| stale | banner, Ops | out of date | जुना |
| OPS / R / W / N / $ tags | next to buttons | stops a program / read only / changes files / free AI used / costs money | प्रोग्राम थांबवतो / फक्त पाहणे / फाइली बदलतात / मोफत AI वापरतो / पैसे लागतात |
| SPEND OFF / ON | top bar | paid work off / on | पैसे लागणारे काम बंद / सुरू |
| job | top bar, footer | background work | पार्श्वभूमीतील काम |
| argv | Command dialog | exact command text (hide) | नेमका आदेश (लपवा) |
| redacted | footer | private details hidden | खाजगी तपशील लपवले |
| Stop job (local process only) | footer, Video | stops only this computer's program | फक्त या संगणकावरील प्रोग्राम थांबवतो |
| START / EXECUTE n / AUTHOR FIELDS | typed confirmations | the exact word to type | टाइप करायचा शब्द |
| OpenRouter, NVIDIA, Claude, opus | Story, Runs | free AI services and Claude | मोफत AI सेवा आणि Claude |
| super-vl, ultra, nemotron, dots | Story, Runs | AI model names (show a plain name) | AI मॉडेलची नावे (साधे नाव दाखवा) |
| Studio OK, flow OK, Colab CLI OK | Story | program OK, picture tool OK, GPU tool OK | प्रोग्राम ठीक, चित्र साधन ठीक, GPU साधन ठीक |
| NVIDIA key files | Story | free AI keys found | मोफत AI च्या चाव्या |
| 127.0.0.1 | top bar | (developer address; remove) | (काढा) |
| run director/backfill_registry.py --apply | warnings | ask the helper | मदतनीसाला विचारा |
| ANIME_STUDIO_ALLOW_FREE_MODEL=1 | Render | ask the helper to switch it on | मदतनीसाला सुरू करायला सांगा |
| --allow-spend | (server start) | paid-work switch | पैसे लागणारे काम चालू करण्याचे बटण |
| pid 37320 | Ops | (remove) | (काढा) |
| chip (Chips) | Images | tags | खुणा |
| Gate 1 | Story | first approval text | पहिली मंजुरी: मजकूर |
| Pack check result (JSON) | Story | check result (for the helper) | तपासणीचा निकाल (मदतनीसासाठी) |
| Live | Video | what is happening now | आत्ता काय चालले आहे |
| Scope (Video) | Video | which clips | कोणत्या क्लिप्स |
| Replace SOURCE.md | Story | replace the saved story | जतन केलेली कथा बदला |

---

## D. Model choice (the AI that writes the first step)

**Where the story is pasted.** Step 1 "Story", box "Story text". The same text box exists again in Advanced > Story (app.js), with its own Save story button.

**Where the first AI step runs.** Step 2 "Analysis", button "Run story analysis" (pipeline.js, analysisActions). It sends `write_pack` with `writer: 'super-vl'` and the saved languages (`out_lang`). The server (ui/server.py, b_write_pack) runs `director/write_pack.py <SOURCE.md> <pack> --staged --writer super-vl --out-lang <langs>`.

**What runs today.** `super-vl` = OpenRouter `nvidia/nemotron-3.5-super-vl:free` (write_pack.py WRITERS). Staged mode runs stages 1, 2, 3e1..3e5, 5, each as its own call, with the v2.3 brief by default.

**How it is set today (the default).** Hard-coded in pipeline.js line 16 (`WRITER_NAME = 'super-vl'`). Server default: `DEFAULT_WRITER = "super-vl"` in ui/server.py and director/write_pack.py. app.js uses `WRITER_NAMES[0]`, also super-vl. The label says "Writer: free model (super-vl). Fixed for this step." So the user cannot change it on this step.

**The two competing controls.**
- Step 2 (wizard): no chooser. Fixed label.
- Advanced > Story > "Writer model" dropdown (super-vl or ultra, both free OpenRouter). It feeds only "Run writer: new pack" and "Resume pack" in Advanced. It is not used by the wizard's "Run story analysis".
- So the same job has two controls that disagree, and the Advanced one follows a different story (see G3).

**Backends that exist in the code, and the arguments that select them.**

| Choice the owner wants | Exists in write_pack.py | Reachable from the UI today? | Argument that selects it | Notes |
|---|---|---|---|---|
| Free OpenRouter, Super VL | yes: WRITERS "super-vl" | yes, default | `--writer super-vl` (server sends this) | server enum WRITER_NAME = super-vl, ultra |
| Free OpenRouter, Ultra | yes: WRITERS "ultra" (`nvidia/nemotron-3-ultra-550b-a55b:free`) | yes, but only in Advanced > Story | `--writer ultra` | the server allows it in WRITER_NAME |
| Any other OpenRouter model | yes | no | `--via openrouter --model <id>` | price 0 only; `--allow-paid` is banned in server BANNED_TOKENS |
| Free NVIDIA model | yes: `--via nvidia --model <id>`, default `nvidia/nemotron-3-ultra-550b-a55b`; keys in secrets/nvidia | no (server exposes only a legacy `model` argument, enum with one value; UI never sends it) | `--via nvidia --model <id>` | server writes "legacy NVIDIA path" in the preview text |
| Claude (owner's subscription) | yes: `--writer opus` = `--via claude --model opus --effort medium` | no. server BANNED_PAIRS blocks `--via claude`, and WRITER_NAME excludes opus | `--writer opus` | no run record with the Claude model id was found in the *.jsonl run logs, so this path is untested from this UI |
| Per-stage model choice | yes: `--stage-via`, `--stage-model` | no. `--stage-via` is banned in server | `--stage-via 2=nvidia,3=claude` | not needed for a simple chooser |

**What is missing.**
1. A visible chooser in Step 2 with three plain groups: free NVIDIA model, free OpenRouter model, Claude. Nothing in the UI offers NVIDIA or Claude for the first step.
2. Server support: add `opus` to WRITER_NAME and WRITER_ROUTE; expose a short list for NVIDIA (not only one legacy value); decide whether BANNED_PAIRS keeps blocking `--via claude` for the UI (it can stay blocked if only `--writer opus` is allowed).
3. A saved choice per pack, shown in the scope bar ("AI that writes the plan: ...") and in the Analysis card, so the user always sees which AI wrote the plan.
4. One place only. Remove the Advanced "Writer model" dropdown or make it read the same choice.
5. Owner decision needed: Claude may count as paid use. blot.md says no paid calls without the owner's go, and the write_pack docstring says it uses the owner's subscription. Show the Claude card with "Asks you first. It may use your Claude subscription." until the owner decides.

**Where the chooser should sit.** Step 2, above "Run story analysis" (after the pack name), or as its own block between Languages (Step 1) and Analysis. Three large radio cards:
- "Free AI A: NVIDIA (free)" with a model name below (only if the owner wants a choice of NVIDIA models).
- "Free AI B: Super VL (free)" (default, selected).
- "Free AI C: Ultra (free)".
- "Claude (asks you first)".

The default must stay Super VL so nothing changes unless she picks another card. The Run button label should then read "Create the story plan with [chosen AI]". Languages must be saved first (the server refuses otherwise), so the chooser belongs after the languages step.

---

## E. Layout and beauty problems (with evidence)

1. **Phone: the step list shows only "1 Story Done".** Steps 2 to 6 sit off-screen to the right in a horizontal strip (measured left edges: 377, 730, 1082, 1435, 1788 px on a 375 px screen). The user cannot see her progress without swiping. (Phone screenshot at the top; DOM measurement.)
2. **Phone: the sticky header takes 181 px** of 812 px (four stacked chips, SPEND OFF, "job: none", "127.0.0.1"). Too much of the screen is used before the first instruction.
3. **Phone and desktop: the sticky "Job log tail" footer** (152 px on phone, 121 px on desktop) stays at the bottom whenever Advanced is open and covers content. It shows "No job running" most of the time.
4. **Advanced nav: stray bullet dots** after "Story", "Bridge" and "Video" (list style not reset). On phone the row scrolls sideways and "Export" is cut off (nav scroll width 420 px in a 310 px box).
5. **Desktop Runs table: columns squeezed.** "Source" wraps to "Sour / ce" and "paste" to "past / e"; "Runs" wraps to "Ru / ns"; model ids break mid-word ("nvidia/nemotron-/3-ultra-550b-a55b").
6. **Phone: truncated values.** Story dropdown reads "upanishad_ganga_ep4_ashtavakra (pac"; pack name box reads "pack_super-vl_20261106_"; the music path placeholder is cut.
7. **Phone: 57 shot cards** stacked one per card (about 2 phone screens per shot group) before the Gate A approval buttons. No "show the first 5" option, no grouping by part.
8. **Small text for an older reader.** Measured sizes: body 16 px; hints 14.7 px; chips and status labels 13.6 to 14.1 px; table cells 14.7 px. Recommend body 18 to 20 px, hints 16 to 17 px, chips 15 px, buttons at least 48 px tall.
9. **Clutter of tags.** "R", "W", "N", "$" and "OPS" tags sit next to nearly every button. On phone the tags wrap onto their own lines ("W" appears on a separate line from "Resume pack"). They mean nothing to this user.
10. **Long single page.** Nine panels in one scroll (Story with 7 sub-panels, Analysis, Images, Read-out, Render, Export, Ops, Runs, Advanced). No "you are here" line except the small step list.
11. **Contrast is acceptable** (muted text #555 on white; status colours clear). No contrast fault found in the screens I saw. Dark mode was not tested.
12. **Mixed messages in Step 1 and 2.** Step 1 says "Done" while "Where you stopped" says "Next: run the pack validator" (a step of Analysis). The Analysis step says "Waiting for your approval" while the Languages chip says "none chosen yet" and "Saved: none saved yet", yet a pack already exists. The user cannot tell what is finished.
13. **Two story pickers disagree.** Top scope shows upanishad_ganga_ep4_ashtavakra. Advanced > Story shows ashtavakra_gita_katha (the alphabetically first story, chosen by app.js when nothing is selected). Both screens are visible at once on the page.
14. **Contradictory picture counts.** Step 3 says "Finals: 0/114". Advanced > Images > Finals says "18 final(s)" for the same chapter.
15. **Bug: "[object Object]"** in Advanced > Images > Shots, columns Q1 to Q6 (app.js fillReview converts an object to text). Seen on desktop, confirmed in the DOM (every Q cell).
16. **Lag in captures.** Several screenshots after a tab click still showed the previous tab (desktop tab captures, phone captures). Verified state through the DOM each time; the page itself is fine.
17. **Dead CSS and a stale file.** Several selectors in style.css (around lines 398 to 403) target the removed `#wiz-panels` block (exact count not checked), and `ui/static/_wiz_panels_removed.html` is still in the folder that the server serves.
18. **Disabled "Build*" button** with an asterisk and a tooltip that says "gap G1". Replace with plain "Not available yet" text, or remove.
19. **Stale-server banner** is a short red line at the top. It is the only warning about approvals and it is not linked to the Approve button (see G2).
20. **No language switch and no theme switch exist.** The page is English only; Hindi and Marathi appear only as output-language choices. The owner asked for language toggles: none is present in the code.
21. **Positive:** no horizontal page overflow on phone (page width 375 px equals viewport). Gate A table turns into labelled cards on phone and reads well. The Runs table turns into labelled cards on phone.

---

## F. Safety for a non-technical user

**What could cost money.**
- Colab GPU session: Advanced > Video > "Run on Colab... (spend gate)". Protected today: SPEND OFF; the server was not started with `--allow-spend`; the button is disabled; a preview with an expiry and a typed confirmation are needed. Also "Check Colab" contacts Colab (network check, no spend), and "Stop session" in Colab (OPS).
- Free AI calls (N tag): Run story analysis, Run writer: new pack, Resume pack, Run reviewer, Visual QA, Run author. They cost no money but use free quota and take time. The author is off (env var). The wizard's Run story analysis asks "Run"; the Advanced writer buttons go through preview and Start.
- Gate approvals and rejects record decisions that drive the next steps.

**What could destroy or overwrite work.**
- Save story with "Replace the saved story if it exists" (Story, both places) overwrites SOURCE.md.
- "Replace SOURCE.md" button (YouTube section) overwrites the saved story.
- "Write keyframes" writes files (existing outputs are kept, per the text).
- "Collect" copies files in (refuses existing outputs; the page says it deletes nothing).
- "Accept (owner)" and "Queue kept" change the picture state.
- "Stop job (local process only)": the text warns that a paid job may keep running on Colab.
- Two story pickers: Advanced Save or Run can act on a different story from the one shown at the top.

**Protections that exist today.**
- Paid work is OFF by default (top bar), and paid buttons are disabled with a reason.
- Preview first: the Advanced commands show the exact command and a preview that expires in 60 s.
- Typed confirmations: EXECUTE n for paid runs, START for Gate C, AUTHOR FIELDS for the author.
- Approve Gate A is blocked while the validator reports errors (checked in code).
- Gate D is blocked until the Step 9 check passes (checked in code).
- Server guards: X-UI header on every POST; host check; banned flags (`--allow-paid`, `--push`, `--fetch`, `--stage-via`, `--via claude`, `--via openrouter`).
- Finished packs are never overwritten by a new run (server rule).
- Cancel is the first button in confirmation boxes.

**Gaps.**
- G-a. Approve Gate A stays enabled while the banner says "restart the server before you approve anything" (DOM: approve button disabled = false). The warning and the button disagree.
- G-b. Approval confirmations use a button labelled "Run" for a human approval. Use "Yes, approve".
- G-c. Two story pickers (see E13). Risk of acting on the wrong story.
- G-d. The Analysis confirmation shows the raw command line and the route to a non-technical user. It adds fear, not safety. Show plain words instead; keep the raw text one tap away.
- G-e. Gate approvals have no undo button in the page.
- G-f. "Check Colab" does not say that it contacts Colab. Say so.
- G-g. The Video section (paid run) is one click away once Advanced is open. Put paid items behind an explicit "Paid work" switch.

---

## G. Top 15 fixes, ranked by impact for this user

1. **Add the AI chooser to Step 2** (NVIDIA free, OpenRouter free, Claude with "asks you first"); default Super VL; show the choice in the scope bar; remove the second dropdown in Advanced; server support in section D. This is the owner's direct request.
2. **Stop approvals when the server is out of date.** Disable Approve, Reject, Build and Run buttons while the stale flag is set; show a plain sentence with a "Check again" button. This fixes a real safety gap (G-a).
3. **One story only.** The Advanced Story picker must follow the top story (or be removed). Show "Working on: <story>" in a large line at the top of every step.
4. **Plain words everywhere.** Use the tables in B and C. Remove the R, W, N and $ tags, slugs, file names, argv text, developer address (127.0.0.1), "job: none" and the pid from the main screens. Keep them in an expert area.
5. **Put a three-step guide at the top:** "1. Paste your story" / "2. Choose the AI and make the plan" / "3. Check and approve". One large main button per step. Everything else under "For the helper".
6. **Fix the phone step list.** Show "Step 2 of 6: Plan the story" as one line with Back and Next, or stack the six steps vertically. Make step items buttons only when they are allowed to open.
7. **Shrink the sticky footer and the header.** Show the job footer as one line ("Nothing is running") and only when a job exists. Make the header two lines on phone. Nothing sticky should cover content.
8. **Bigger text and buttons.** Body 18 to 20 px; hints 16 to 17 px; chips 15 px; buttons 48 px tall; line height 1.5. Test at 375 px.
9. **Fix data bugs:** "[object Object]" in Images > Shots (app.js fillReview); the contradictory finals counts (0/114 vs 18); the wrong shot counts shown in two places if they differ.
10. **Plain confirmations.** "Yes, approve" / "Yes, start" / "Go back" in place of "Run". First sentence says what will change, in plain words. Mention money in plain words when it applies ("This may cost money").
11. **Add an English / मराठी language switch** at the top; translate the labels in B. (The owner asked for language toggles; none exists.)
12. **Collapse the 57-shot list** to the first five with "Show all 57", and group shots by part with headings.
13. **Fix the layout bugs:** stray bullets in the Advanced nav; "Export" cut off on phone; Runs table columns (show Story, Status and Last run on desktop; move Source, Model and Runs into the details); allow long names to wrap in dropdowns and boxes.
14. **Move paid items behind a switch.** The Colab block, the H3 engine and the "Run author" button go into a "Paid work (off)" area that says in one plain sentence what it costs and needs the helper to switch it on. Rename "Check Colab" to say that it contacts Colab.
15. **Clean up dead code and files.** Remove the `#wiz-panels` CSS and the served `_wiz_panels_removed.html`; remove the disabled "Build*" button or replace it with plain text; keep the server-state line only in the expert area.

---

## H. What I could not check (honesty list)

- The Advanced **Video** section was not opened, because opening it calls Colab (blot.md RULE 4). Its labels and behaviour are from index.html and app.js only.
- No button was pressed. Error messages, the real outcome of Save, Approve, Run and every paid path are unverified; they are described from source.
- Dark mode, the Hindi/Marathi text in the page (none exists), and print were not tested.
- The Bridge, Export and Video sections were not checked at phone width beyond the navigation row.
- Some panels only appear when data exists (fallback table, Gate D rows, finished pictures grid for the Story pack, Shots candidates for a shot). Those were read from source, not seen.
- Font sizes are computed CSS values. How they read on a real phone for a 60-year-old was not tested with a real user.
- Several screenshots lagged one step behind the last click; the state was then checked through the DOM.
- Eight screenshot items show the same screen twice because of the lag. The count in the header (51 screenshots plus 1 zoom) includes them.
- The sticky footer and the Runs row click: one stray click on phone landed on a Runs card, opened nothing, and changed no state (checked in the DOM).
- The NOW block in PROJECT_LOG.md was not overwritten. The main session should refresh it.
- Marathi names in section B are my proposals. A native Marathi speaker must check them before they go on screen. Hindi names were not proposed (the task asked for Marathi only).
- Contrast was judged from the CSS colour values, not measured with a contrast tool. Section E item 11 is an estimate.
- The "Video" and Colab rows in section B10 (VD1 to VD21) are from source only. Labels shown there were not seen on screen.
- PROJECT_LOG.md received only log lines (rule 1 of CLAUDE.md). One earlier line claimed "LUT, token ... found on screen"; a correction line follows in the log: LUT is not on screen, and "token" appears only in code.
