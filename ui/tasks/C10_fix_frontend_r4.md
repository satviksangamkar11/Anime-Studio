You are the coder fixing the wizard front end after the round-3 review (context: ui/_review_frontend_haiku_round3.md is binding; ui/CHECKLIST_REDESIGN.md is the API contract). Change as little as possible; keep every existing behaviour and id the tests rely on (ui/test_static.py). Return ALL allowed files complete.

Fix exactly these findings (line numbers are from the review):
- H1 pipeline.js ~1000: `disabled: false` goes through el() and calls setAttribute('disabled', false), which DISABLES the button. Never pass `disabled` as a prop. Create the button, then set `btn.disabled = <bool>` as a property. Check el() for any other boolean prop passed as false (checked, hidden, readonly) and fix the same way (el() must skip props whose value is false/null/undefined).
- H2 pipeline.js ~203-221: after loadStoryList finishes set State.lastJSON = '' (or the render key) before render() so the story picker is redrawn.
- H3 pipeline.js ~673-679: /api/images `jobs` is a LIST OF DICTS with a `file` field (not strings). Build the unique job file list as 'flow/' + j.file; choose the file whose shot ids belong to the current pack; no `.indexOf` on dicts.
- H5 pipeline.js ~891: do not send `ids: ''` in the prepare-render args (the server rejects empty ids); omit the key when empty.
- M2 pipeline.js ~143-160: when no saved story exists do not assign State.storyText = '' on each poll while the user has typed text (storyDirty true); keep the typed text.
- M3 pipeline.js ~433-462 and the draft save/restore (~251-323): keep the new-slug and overwrite inputs in State and restore them after a re-render.
- M4 pipeline.js ~232, 273-297: after a re-render restore focus (save the active element id and selectionStart/selectionEnd, call focus() and setSelectionRange).
- M5 pipeline.js ~185-201: loadPack must ignore a 404 "no such pack" (no error bar every 5 s before the analysis has run).
- M7 style.css: text contrast: use dark text (#1f2937) on the orange and amber chips; make the blue at least #1d4ed8 behind white text; put the progress count outside or use a colour with 4.5:1 contrast.
- L1 "Gate A (Gate A)" title: show the title once. L2 typo "rejectd" -> "rejected". L3 when State.busy is true show a short message instead of silently dropping the click. L5 clear the gate note field after a decision is recorded. L6 buttons of a locked stage are disabled (property, not attribute). L7 when /api/pipeline fails show the error text inside the wizard area, not a blank page. L4 clear the success/error class of the message bar when a new message is shown and add a .bar-ok rule (green background, dark text) in style.css.
Rules: plain JS, textContent only (no innerHTML with data), every POST sends header X-UI: 1 (already so), no new dependencies.
Allowed files: ui/static/pipeline.js, ui/static/style.css, ui/static/index.html. Test gate: C:/Python314/python.exe -m pytest -q -p no:cacheprovider ui/test_static.py passes.
