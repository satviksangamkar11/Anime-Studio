FINAL

High, ui/static/pipeline.js:747-748, /api/images returns a list of job dicts (per facts) but code expects `{jobs: [...]}` wrapper; `data.jobs` will be undefined causing "Image jobs are not built yet" error, fix: `jobs = Array.isArray(data) ? data : (data.jobs || [])`

High, ui/static/pipeline.js:800, `findJobsFile` uses `j.shot_id` but facts only guarantee `file` field; if API omits `shot_id`, matching fails with "undefined" keys, fix: `if (j.shot_id) byFile[j.file][String(j.shot_id)] = true;` → `if (j.shot_id != null) byFile[j.file][String(j.shot_id)] = true;` and ensure backend includes `shot_id`

Medium, ui/static/pipeline.js:301-321, `saveFocusedInputs` omits `wiz-story-new-slug` (and `wiz-story-overwrite`); typed text and focus in new-slug field lost on 5s auto-refresh, fix: add `var newSlugInput = $('wiz-story-new-slug'); if (newSlugInput && wizard.contains(newSlugInput)) saved.newSlug = newSlugInput.value;` and restore in `restoreFocusedInputs`

Low, ui/static/pipeline.js:63-64, `el()` helper's array-children branch appends raw values without converting strings to text nodes; would throw if a string ever passed in a children array, fix: `child.forEach(function (c) { if (c instanceof Node) node.appendChild(c); else node.appendChild(document.createTextNode(String(c))); });`