(function () {
  'use strict';
  var t = function (k, v) { return window.I18N.t(k, v); };

  var POLL_MS = 5000;
  var DETAIL_EVERY = 6;            // side panels reload every 6th poll (about 30 s)
  var SUCCESS_MS = 8000;           // success lines hide by themselves; errors stay until closed (plan B10)
  var MAX_STORY_BYTES = 204800;
  var SLUG_PAT = /^[a-z0-9_]{1,40}$/;
  var NOTE_MIN = 1;
  var NOTE_MAX = 300;
  var LANGS = ['en', 'hi', 'mr'];
  var AUTHOR_PHRASE = 'AUTHOR FIELDS';
  var DISK_LOW_GB = 2;
  var BUILD_ADHYAY = 1;
  var API_TIMEOUT_MS = 120000;
  var JOB_POLL_MS = 700;
  var JOB_POLL_MAX = 900;          // about 10 minutes, then the job bar keeps showing the job
  var WRITER_STORE = 'studio.writer';
  var SVG_NS = 'http' + '://www.w3.org/2000/svg';   // XML namespace name, not a link
  var STAGE_IDS = ['story', 'analysis', 'images', 'readout', 'render', 'export'];
  var CLAUDE_COMMAND = 'write_pack_claude';   // the one command that uses Claude: it needs the typed word CLAUDE

  // which wizard stage each story_state next_step key opens (director/story_state.py keys)
  var NEXT_STAGE = {
    save_story: 'story', run_writer: 'analysis', run_writer_resume: 'analysis', fix_failed_stage: 'analysis',
    run_validator: 'analysis', gate_rejected: 'analysis', await_gate_A: 'analysis', build_image_jobs: 'images',
    link_images: 'images', run_image_review: 'images', await_gate_B: 'images', await_gate_C: 'readout',
    prepare_render: 'render', await_gate_D: 'render', run_final_qc_export: 'export'
  };

  // Runs & documents: badge classes (style.css); the words come from runWord()
  var RUN_BADGE = { ok: 'b-ok', failed: 'b-failed', stopped: 'b-review', open: 'b-running', started: 'b-running' };

  // one fixed id per writer card (the parity test looks for these literal ids)
  var WRITER_CARD_ID = {
    'nv-ultra': 'writer-opt-nv-ultra',
    'nv-super-vl': 'writer-opt-nv-super-vl',
    'or-super-vl': 'writer-opt-or-super-vl',
    'or-ultra': 'writer-opt-or-ultra',
    'claude-opus': 'writer-opt-claude-opus'
  };

  var ICONS = {
    check: [['path', { d: 'M5 13l4 4L19 7' }]],
    x: [['path', { d: 'M6 6l12 12M18 6L6 18' }]],
    lock: [['rect', { x: 5, y: 11, width: 14, height: 10, rx: 2 }], ['path', { d: 'M8 11V7a4 4 0 0 1 8 0v4' }]],
    clock: [['circle', { cx: 12, cy: 12, r: 9 }], ['path', { d: 'M12 7v5l3 3' }]],
    alert: [['circle', { cx: 12, cy: 12, r: 9 }], ['path', { d: 'M12 7v6M12 17h.01' }]],
    arrow: [['path', { d: 'M5 12h14M13 6l6 6-6 6' }]],
    info: [['circle', { cx: 12, cy: 12, r: 9 }], ['path', { d: 'M12 11v6M12 7h.01' }]],
    globe: [['circle', { cx: 12, cy: 12, r: 9 }], ['path', { d: 'M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18' }]]
  };

  var State = {
    pipeline: null,
    summary: null,
    packInfo: null,
    storyList: null,
    storyText: '',
    storySlug: '',
    storyDirty: false,
    lastStorySlug: '',
    newSlug: '',
    overwrite: false,
    scopeKey: '',
    prefsFor: '',
    langPick: [],
    drafts: {},                    // typed-but-not-saved values, by element id (survive a re-render)
    busy: false,
    lastJSON: '',
    errorTimer: null,
    pollTimer: null,
    pollCount: 0,
    lastFocused: null,
    job: null,
    storyState: null,
    stateError: '',
    validator: null,
    validatorError: '',
    render: null,
    renderError: '',
    author: null,
    authorError: '',
    authorPreview: '',
    voices: null,
    voicesError: '',
    exportData: null,
    ops: null,
    opsError: '',
    version: null,
    link: null,
    jumpTo: '',
    registry: null,
    registryError: '',
    registrySlug: '',
    registryDetail: null,
    writers: null,                 // GET /api/writers
    writersError: '',
    writerChoice: '',              // the picked writer card id (never claude-opus from storage)
    claudeAck: false,              // the Claude warning box is ticked (per page load only)
    openStep: '',                  // '' = the server's current step
    openDetails: {},               // open state of every details box, by its id (survives re-renders)
    showAllShots: false,
    imageJobs: null,               // image jobs listed for this plan (null = not counted)
    detailBusy: null,
    detailAgain: false,
    confirmPending: false
  };

  // ---------- DOM helpers ----------
  function $(id) { return document.getElementById(id); }

  function el(tag, props) {
    var node = document.createElement(tag);
    var p = props || {};
    for (var k in p) {
      if (k === 'textContent') {
        node.textContent = p[k];
      } else if (k === 'children') {
        appendKids(node, p[k] || []);
      } else if (k === 'class') {
        node.className = p[k];
      } else if (k.indexOf('on') === 0 && typeof p[k] === 'function') {
        node.addEventListener(k.slice(2), p[k]);
      } else if (k === 'style') {
        for (var s in p[k]) node.style[s] = p[k][s];
      } else if (p[k] === null || p[k] === undefined || p[k] === false) {
        // skipped: setAttribute('disabled', false) would still disable the control
      } else if (p[k] === true) {
        node[k] = true;
      } else {
        node.setAttribute(k, p[k]);
      }
    }
    return node;
  }

  function appendKids(node, kids) {
    kids.forEach(function (k) {
      if (k === null || k === undefined || k === false) return;
      if (Array.isArray(k)) appendKids(node, k);
      else if (k instanceof Node) node.appendChild(k);
      else node.appendChild(document.createTextNode(String(k)));
    });
  }

  function setAttrs(node, attrs) {
    Object.keys(attrs).forEach(function (k) { node.setAttribute(k, String(attrs[k])); });
  }

  // inline SVG icon (plan 4.3): built node by node with createElementNS, no markup strings
  function icon(name) {
    var svg = document.createElementNS(SVG_NS, 'svg');
    setAttrs(svg, { viewBox: '0 0 24 24', width: 24, height: 24, 'aria-hidden': 'true', focusable: 'false',
      fill: 'none', stroke: 'currentColor', 'stroke-width': 2, 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'class': 'icon' });
    (ICONS[name] || []).forEach(function (part) {
      var node = document.createElementNS(SVG_NS, part[0]);
      setAttrs(node, part[1]);
      svg.appendChild(node);
    });
    return svg;
  }

  function statusIcon(s) {
    switch (s) {
      case 'approved': case 'done': return 'check';
      case 'failed': case 'rejected': return 'x';
      case 'locked': return 'lock';
      case 'waiting_approval': case 'running': return 'clock';
      case 'stopped': return 'alert';
      default: return 'arrow';
    }
  }

  function countBytes(str) {
    return new TextEncoder().encode(str).length;
  }

  function stripNewlines(str) {
    return str.replace(/[\r\n]+/g, ' ');
  }

  function enc(s) { return encodeURIComponent(String(s == null ? '' : s)); }

  function safeId(s) { return String(s).replace(/[^A-Za-z0-9_-]/g, '_'); }

  function errText(err) {
    return err && err.message ? err.message : String(err);
  }

  function dash(v) {
    return v === null || v === undefined || v === '' ? '-' : String(v);
  }

  function listText(v) {
    return v && v.length ? v.join(', ') : '-';
  }

  function shortTime(iso) {
    return iso ? String(iso).replace('T', ' ').slice(0, 16) : '-';
  }

  function chip(text, cls) {
    return el('span', { class: 'chip ' + (cls || ''), textContent: text });
  }

  function notice(text) {
    return el('div', { class: 'notice', role: 'status', textContent: text });
  }

  function sameList(a, b) {
    return a.slice().sort().join(',') === b.slice().sort().join(',');
  }

  // a table whose cells carry data-label, so the phone view can stack them (no horizontal scroll)
  function dataTable(headers, rows) {
    var head = el('tr', { children: headers.map(function (h) { return el('th', { scope: 'col', textContent: h }); }) });
    var tbody = el('tbody');
    rows.forEach(function (cells) {
      var tr = el('tr');
      cells.forEach(function (cell, i) {
        tr.appendChild(el('td', { 'data-label': headers[i] || '', children: [cell] }));
      });
      tbody.appendChild(tr);
    });
    return el('div', { class: 'tablewrap', children: [el('table', { children: [el('thead', { children: [head] }), tbody] })] });
  }

  // a closed box for raw text and codes (plan 4.2 "Details for the helper")
  function foldDetails(id, summaryText, kids) {
    var key = 'details-' + id;
    var d = el('details', { class: 'expert', id: key, open: !!State.openDetails[key] });
    d.appendChild(el('summary', { textContent: summaryText }));
    appendKids(d, kids);
    d.addEventListener('toggle', function () { State.openDetails[key] = d.open; });
    return d;
  }

  function helperDetails(id, kids) {
    return foldDetails(id, t('common.details_helper'), kids);
  }

  // ---------- HTTP (promises; every error becomes an Error with a plain message) ----------
  function api(url, opts) {
    opts = opts || {};
    var method = opts.method || 'GET';
    var headers = { 'Content-Type': 'application/json', 'X-UI': '1' };
    // a request that hangs must not leave every button disabled: give up after 2 minutes
    var ctl = typeof AbortController === 'function' ? new AbortController() : null;
    var timer = ctl ? setTimeout(function () { ctl.abort(); }, API_TIMEOUT_MS) : null;
    return fetch(url, {
      method: method,
      headers: headers,
      signal: ctl ? ctl.signal : undefined,
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined
    }).then(function (r) {
      if (timer) clearTimeout(timer);
      return r.text().then(function (text) {
        var data = text;
        try { data = JSON.parse(text); } catch (e) { data = text; }
        if (!r.ok) {
          var msg = (data && typeof data === 'object' && data.error) ? String(data.error)
            : (String(text).slice(0, 300) || ('HTTP ' + r.status));
          var err = new Error(msg);
          err.status = r.status;
          throw err;
        }
        return data;
      });
    }, function (e) {
      if (timer) clearTimeout(timer);
      if (e && e.name === 'AbortError') throw new Error(t('err.net.timeout'));
      throw new Error(t('err.net.down'));
    });
  }

  function get(url) { return api(url, {}); }
  function post(url, body) { return api(url, { method: 'POST', body: body }); }

  function packPath(slug, pack) { return 'stories/' + slug + '/' + pack; }
  function projectOf() { return (State.pipeline && State.pipeline.project) || {}; }

  function draftOr(id, fallback) {
    var d = State.drafts[id];
    if (!d) return fallback;
    return ('checked' in d) ? d.checked : d.value;
  }

  function clearDrafts(prefix) {
    Object.keys(State.drafts).forEach(function (k) {
      if (k.indexOf(prefix) === 0) delete State.drafts[k];
    });
  }

  // ---------- Words: literal maps, so every key stays visible to the tests ----------
  // The server sends stage details in English (pipeline.py); show them in the chosen language. Unknown text is shown as it is.
  function stageDetail(raw) {
    var d = String(raw), m;
    switch (d) {
      case 'SOURCE.md saved': return t('step.det_story_saved');
      case 'Story not saved': return t('step.det_story_not_saved');
      case 'Waiting for story': return t('step.det_wait_story');
      case 'Shots ready, awaiting Gate A': return t('step.det_shots_ready_a');
      case 'Ready for analysis': return t('step.det_ready_analysis');
      case 'No finals yet': return t('step.det_no_finals');
      case 'All finals ready, awaiting Gate B': return t('step.det_all_finals_b');
      case 'Ready for images': return t('step.det_ready_images');
      case 'Awaiting Gate C (START)': return t('step.det_awaiting_c');
      case 'No clips yet': return t('step.det_no_clips');
      case 'All clips home, awaiting Gate D': return t('step.det_all_clips_d');
      case 'Ready for render': return t('step.det_ready_render');
      case 'Ready for export': return t('step.det_ready_export');
      default: break;
    }
    m = /^Gate ([A-D]) approved$/.exec(d);
    if (m) return t('step.det_gate_approved', { g: m[1] });
    m = /^Gate ([A-D]) rejected, rerun the stage or decide again$/.exec(d);
    if (m) return t('step.det_gate_rejected', { g: m[1] });
    m = /^Waiting for Gate ([A-D])$/.exec(d);
    if (m) return t('step.det_wait_gate', { g: m[1] });
    m = /^(\d+) stages saved, run again to resume$/.exec(d);
    if (m) return t('step.det_stages_saved', { n: m[1] });
    m = /^Finals: (\d+)\/(\d+), pending: (\d+)$/.exec(d);
    if (m) return t('step.det_finals', { a: m[1], b: m[2], c: m[3] });
    m = /^Clips: (\d+)\/(\d+)$/.exec(d);
    if (m) return t('step.det_clips', { a: m[1], b: m[2] });
    return d;
  }
  function statusWord(s) {
    switch (s) {
      case 'locked': return t('status.locked');
      case 'ready': return t('status.ready');
      case 'running': return t('status.running');
      case 'waiting_approval': return t('status.waiting_approval');
      case 'approved': return t('status.approved');
      case 'rejected': return t('status.rejected');
      case 'done': return t('status.done');
      case 'failed': return t('status.failed');
      case 'open': return t('status.open');
      case 'stopped': return t('status.stopped');
      case 'not_run': return t('status.not_run');
      default: return t('status.unknown');
    }
  }

  function stepName(id) {
    switch (id) {
      case 'story': return t('step.story.name');
      case 'analysis': return t('step.analysis.name');
      case 'images': return t('step.images.name');
      case 'readout': return t('step.readout.name');
      case 'render': return t('step.render.name');
      case 'export': return t('step.export.name');
      default: return String(id);
    }
  }

  function stepShort(id) {
    switch (id) {
      case 'story': return t('step.story.short');
      case 'analysis': return t('step.analysis.short');
      case 'images': return t('step.images.short');
      case 'readout': return t('step.readout.short');
      case 'render': return t('step.render.short');
      case 'export': return t('step.export.short');
      default: return String(id);
    }
  }

  function stepIntro(id) {
    switch (id) {
      case 'story': return t('step.story.intro');
      case 'analysis': return t('step.analysis.intro');
      case 'images': return t('step.images.intro');
      case 'readout': return t('step.readout.intro');
      case 'render': return t('step.render.intro');
      case 'export': return t('step.export.intro');
      default: return '';
    }
  }

  function langName(code) {
    switch (code) {
      case 'en': return t('story.lang_en');
      case 'hi': return t('story.lang_hi');
      case 'mr': return t('story.lang_mr');
      default: return String(code || '');
    }
  }

  function writerName(id) {
    switch (id) {
      case 'nv-ultra': return t('writer.nv_ultra.name');
      case 'nv-super-vl': return t('writer.nv_super_vl.name');
      case 'or-super-vl': return t('writer.or_super_vl.name');
      case 'or-ultra': return t('writer.or_ultra.name');
      case 'claude-opus': return t('writer.claude_opus.name');
      default: return '';
    }
  }

  function writerShort(id) {
    switch (id) {
      case 'nv-ultra': return t('writer.nv_ultra.short');
      case 'nv-super-vl': return t('writer.nv_super_vl.short');
      case 'or-super-vl': return t('writer.or_super_vl.short');
      case 'or-ultra': return t('writer.or_ultra.short');
      case 'claude-opus': return t('writer.claude_opus.short');
      default: return '';
    }
  }

  function writerDesc(id) {
    switch (id) {
      case 'nv-ultra': return t('writer.nv_ultra.desc');
      case 'nv-super-vl': return t('writer.nv_super_vl.desc');
      case 'or-super-vl': return t('writer.or_super_vl.desc');
      case 'or-ultra': return t('writer.or_ultra.desc');
      case 'claude-opus': return t('writer.claude_opus.desc');
      default: return '';
    }
  }

  function writerGroup(g) {
    switch (g) {
      case 'nvidia': return t('writer.group.nvidia');
      case 'openrouter': return t('writer.group.openrouter');
      case 'claude': return t('writer.group.claude');
      default: return String(g);
    }
  }

  function writerReason(code) {
    switch (code) {
      case 'no_nvidia_key': return t('writer.reason.no_nvidia_key');
      case 'no_openrouter_key': return t('writer.reason.no_openrouter_key');
      case 'claude_off': return t('writer.reason.claude_off');
      case 'claude_missing': return t('writer.reason.claude_missing');
      default: return t('writer.reason.unknown');
    }
  }

  function costWord(c) {
    return c === 'subscription' ? t('writer.cost.subscription') : t('writer.cost.free');
  }

  function speedWord(s) {
    switch (s) {
      case 'fast': return t('writer.speed.fast');
      case 'slow': return t('writer.speed.slow');
      default: return t('writer.speed.medium');
    }
  }

  function qualityWord(q) {
    switch (q) {
      case 'good': return t('writer.quality.good');
      case 'high': return t('writer.quality.high');
      default: return t('writer.quality.highest');
    }
  }

  function gateTitle(id) {
    switch (id) {
      case 'A': return t('gate.title_a');
      case 'B': return t('gate.title_b');
      case 'C': return t('gate.title_c');
      default: return t('gate.title_d');
    }
  }

  function gateApprove(id) {
    switch (id) {
      case 'A': return t('gate.approve_a');
      case 'B': return t('gate.approve_b');
      case 'C': return t('gate.approve_c');
      default: return t('gate.approve_d');
    }
  }

  function gateConfirm(id, project) {
    switch (id) {
      case 'A': return t('gate.confirm_a', { story: project.story_slug, pack: project.pack });
      case 'B': return t('gate.confirm_b', { story: project.story_slug, pack: project.pack });
      case 'C': return t('gate.confirm_c', { story: project.story_slug, pack: project.pack });
      default: return t('gate.confirm_d', { story: project.story_slug, pack: project.pack });
    }
  }

  function gateNext(id) {
    switch (id) {
      case 'A': return t('gate.next_a');
      case 'B': return t('gate.next_b');
      case 'C': return t('gate.next_c');
      default: return t('gate.next_d');
    }
  }

  // the server's next step key -> plain sentence; unknown keys keep the server text
  function nextText(key, fallback) {
    switch (key) {
      case 'save_story': return t('next.save_story');
      case 'gate_rejected': return t('next.gate_rejected');
      case 'fix_failed_stage': return t('next.fix_failed_stage');
      case 'run_writer_resume': return t('next.run_writer_resume');
      case 'run_writer': return t('next.run_writer');
      case 'run_validator': return t('next.run_validator');
      case 'await_gate_A': return t('next.await_gate_a');
      case 'build_image_jobs': return t('next.build_image_jobs');
      case 'link_images': return t('next.link_images');
      case 'run_image_review': return t('next.run_image_review');
      case 'await_gate_B': return t('next.await_gate_b');
      case 'await_gate_C': return t('next.await_gate_c');
      case 'prepare_render': return t('next.prepare_render');
      case 'await_gate_D': return t('next.await_gate_d');
      case 'run_final_qc_export': return t('next.run_final_qc_export');
      default: return String(fallback || '');
    }
  }

  // story_state warning keys look like "empty_pack:name"; the part before ":" picks the sentence
  function warnText(key) {
    switch (String(key || '').split(':')[0]) {
      case 'no_story_json': return t('warn.no_story_json');
      case 'source_changed_since_save': return t('warn.source_changed_since_save');
      case 'source_changed': return t('warn.source_changed');
      case 'empty_pack': return t('warn.empty_pack');
      case 'stage_failed': return t('warn.stage_failed');
      case 'finish_length': return t('warn.finish_length');
      case 'tiny_stage_file': return t('warn.tiny_stage_file');
      case 'link_missing': return t('warn.link_missing');
      default: return t('warn.other');
    }
  }

  function checkLabel(name) {
    switch (name) {
      case 'shots.json present': return t('sum.check.shots_file');
      case 'bible.json present': return t('sum.check.bible_file');
      case 'every shot has seconds>0': return t('sum.check.seconds');
      case 'every shot has an episode': return t('sum.check.episode');
      case 'at least one episode': return t('sum.check.episodes');
      case 'no duplicate shot ids': return t('sum.check.dup_ids');
      default: return String(name || '');
    }
  }

  function choiceLabel(code) {
    switch (code) {
      case 'switch_models': return t('video.choice.switch_models');
      case 'relax_requirements': return t('video.choice.relax_requirements');
      case 'skip_with_placeholder_missing_clip': return t('video.choice.skip_with_placeholder_missing_clip');
      case 'supply_reference_video': return t('video.choice.supply_reference_video');
      default: return String(code);
    }
  }

  function runWord(st) {
    switch (st) {
      case 'ok': return t('runs.badge_ok');
      case 'failed': return t('runs.badge_failed');
      case 'stopped': return t('runs.badge_stopped');
      case 'open': case 'started': return t('runs.badge_running');
      case 'no runs': return t('runs.badge_none');
      default: return String(st);
    }
  }

  // ---------- Data loading ----------
  function loadPipeline() {
    return get('/api/pipeline').then(function (data) {
      State.pipeline = data;
      var project = data.project || {};
      var slug = project.story_slug || '';
      var key = slug + '|' + (project.pack || '');
      var changed = key !== State.scopeKey;
      if (changed) {
        // another story or pack is now the project: forget what belonged to the old one
        State.scopeKey = key;
        State.packInfo = null;
        State.storyState = null;
        State.stateError = '';
        State.validator = null;
        State.validatorError = '';
        State.render = null;
        State.renderError = '';
        State.author = null;
        State.authorError = '';
        State.authorPreview = '';
        State.voices = null;
        State.voicesError = '';
        State.exportData = null;
        State.link = null;
        State.prefsFor = '';
        State.langPick = [];
        State.drafts = {};
        State.imageJobs = null;
        State.showAllShots = false;
      }
      State.storySlug = slug;
      if (slug) {
        return loadStory().then(function () { render(changed); return changed; });
      }
      if (State.lastStorySlug !== '') {
        State.lastStorySlug = '';
        State.storyText = '';
        State.storyDirty = false;
      }
      render(changed);
      return changed;
    }).catch(function (err) {
      if (!State.pipeline) showWizardNotice(t('step.server_down', { error: errText(err) }));
      showApiError(err);
      return false;
    });
  }

  function loadStory() {
    if (!State.storySlug) return Promise.resolve();
    return get('/api/story/' + enc(State.storySlug))
      .catch(function (err) { if (err.status === 404) return null; throw err; })
      .then(function (data) {
        if (State.storySlug !== State.lastStorySlug) {
          // the slug changed: load its text (empty when the story does not exist yet)
          State.lastStorySlug = State.storySlug;
          State.storyText = data && data.text ? data.text : '';
          State.storyDirty = false;
        }
      })
      .catch(function (err) { showApiError(err); });
  }

  // adopt the saved languages once per story; after that the page keeps what the owner ticked
  function adoptPrefs(slug, st) {
    if (State.prefsFor === slug) return;
    State.prefsFor = slug;
    State.langPick = (st && st.output_languages || []).filter(function (c) { return LANGS.indexOf(c) >= 0; });
  }

  // one detail load at a time: a poll that arrives mid-load is folded into one rerun,
  // so an older response can never land on top of a newer one
  function loadDetail() {
    if (State.detailBusy) { State.detailAgain = true; return State.detailBusy; }
    State.detailBusy = loadDetailNow().then(finish, finish);
    function finish() {
      State.detailBusy = null;
      if (State.detailAgain) { State.detailAgain = false; return loadDetail(); }
    }
    return State.detailBusy;
  }

  // one request per panel; each panel shows its own error, none breaks the rest
  function loadDetailNow() {
    var project = projectOf();
    var slug = project.story_slug || '';
    var pack = project.pack || '';
    var jobs = [];
    if (slug) {
      jobs.push(get('/api/story/' + enc(slug) + '/state').then(function (d) {
        State.storyState = d;
        State.stateError = '';
        adoptPrefs(slug, d);
      }, function (e) {
        State.storyState = null;
        State.stateError = errText(e);
      }));
    }
    if (slug && pack) {
      var pp = packPath(slug, pack);
      jobs.push(get('/api/pack?pack=' + enc(pp)).then(function (d) {
        State.packInfo = d;
      }, function (e) {
        // 404 = the analysis has not written the pack yet, which is normal before Gate A
        State.packInfo = null;
        if (e.status !== 404) showApiError(e);
      }));
      jobs.push(get('/api/pack/validate?pack=' + enc(pp)).then(function (d) {
        State.validator = d;
        State.validatorError = '';
      }, function (e) {
        State.validator = null;
        State.validatorError = e.status === 404 ? '' : errText(e);
      }));
      jobs.push(get('/api/render/status?story=' + enc(slug) + '&pack=' + enc(pack)).then(function (d) {
        State.render = d;
        State.renderError = '';
      }, function (e) {
        State.render = null;
        State.renderError = errText(e);
      }));
      jobs.push(get('/api/author/status?story=' + enc(slug) + '&pack=' + enc(pp)).then(function (d) {
        State.author = d;
        State.authorError = '';
      }, function (e) {
        State.author = null;
        State.authorError = errText(e);
      }));
      jobs.push(get('/api/pack/voices?pack=' + enc(pp)).then(function (d) {
        State.voices = d;
        State.voicesError = '';
      }, function (e) {
        State.voices = null;
        State.voicesError = e.status === 404 ? '' : errText(e);
      }));
      jobs.push(get('/api/images?story=' + enc(slug) + '&pack=' + enc(pack)).then(function (d) {
        State.imageJobs = d && d.jobs ? d.jobs.length : 0;
      }, function () {
        State.imageJobs = null;
      }));
    }
    return Promise.all(jobs).then(function () { render(true); });
  }

  function loadSummary() {
    return get('/api/pipeline/summary')
      .then(function (data) {
        State.summary = data;
        render();
      })
      .catch(function (err) { showApiError(err); });
  }

  function loadStoryList() {
    return get('/api/story')
      .then(function (data) {
        State.storyList = data.slugs || [];
        render();
      })
      .catch(function (err) { showApiError(err); });
  }

  function loadStatus() {
    return get('/api/status')
      .then(function (data) {
        State.job = data.job || null;
        render();
      })
      .catch(function () {
        State.job = null;
      });
  }

  // withSessions = true only from the "Check Colab sessions" button (B9: never on the poll)
  function loadOps(withSessions) {
    var url = withSessions ? '/api/ops?colab=1' : '/api/ops';
    return Promise.all([
      get(url).then(function (d) { State.ops = d; State.opsError = ''; }, function (e) { State.ops = null; State.opsError = errText(e); }),
      get('/api/version').then(function (d) { State.version = d; }, function () { State.version = null; })
    ]).then(function () { render(true); });
  }

  // step 2 choices: GET /api/writers (read only, no key text)
  function loadWriters() {
    return get('/api/writers').then(function (d) {
      State.writers = d;
      State.writersError = '';
      settleWriter();
      render(true);
    }, function (e) {
      State.writersError = errText(e);
      render(true);
    });
  }

  // Runs & documents: read-only view of GET /api/registry and /api/registry/<slug>
  function loadRegistry() {
    return get('/api/registry')
      .then(function (data) {
        State.registry = data.stories || [];
        State.registryError = '';
        render();
      })
      .catch(function (err) {
        State.registry = null;
        State.registryError = errText(err);
        render();
      });
  }

  function loadRegistryDetail(slug) {
    if (!slug) {
      State.registryDetail = null;
      return Promise.resolve();
    }
    return get('/api/registry/' + enc(slug))
      .then(function (data) {
        State.registryDetail = data;
        render();
      })
      .catch(function (err) {
        State.registryDetail = { slug: slug, error: errText(err) };
        render();
      });
  }

  // one wizard refresh: the pointer first, the side panels when the project changed or on the slow tick
  function refreshWizard(withDetail) {
    return loadPipeline().then(function (changed) {
      if (changed || withDetail) return loadDetail();
    });
  }

  // ---------- Writer choice (step 2) ----------
  function optById(id) {
    var list = (State.writers && State.writers.options) || [];
    for (var i = 0; i < list.length; i++) {
      if (list[i].id === id) return list[i];
    }
    return null;
  }

  function selectedOpt() {
    if (!State.writers) return null;
    return optById(State.writerChoice || State.writers.default);
  }

  // Claude is never restored from storage: only free choices are saved
  function readStoredWriter() {
    try {
      var v = window.localStorage.getItem(WRITER_STORE);
      return v && v !== 'claude-opus' ? v : '';
    } catch (e) {
      return '';
    }
  }

  function writeStoredWriter(id) {
    try {
      window.localStorage.setItem(WRITER_STORE, id);
    } catch (e) {
      // private window or blocked storage: the choice lasts for this page only
    }
  }

  function settleWriter() {
    if (!State.writers) return;
    var cur = State.writerChoice || readStoredWriter();
    var opt = optById(cur);
    State.writerChoice = opt && opt.available ? cur : State.writers.default;
  }

  function chooseWriter(id) {
    State.writerChoice = id;
    if (id !== 'claude-opus') {
      writeStoredWriter(id);
      State.claudeAck = false;
    }
    render(true);
  }

  // ---------- Render ----------
  function render(force) {
    if (!State.pipeline) return;
    var wizard = $('wizard');
    if (!wizard) return;

    var json = JSON.stringify([State.pipeline, State.summary, State.packInfo, State.storyList, State.storyState, State.stateError,
      State.validator, State.validatorError, State.render, State.renderError, State.author, State.authorError, State.authorPreview,
      State.voices, State.voicesError, State.exportData, State.ops, State.opsError, State.version, State.job, State.link,
      State.langPick, State.registry, State.registryError, State.registrySlug, State.registryDetail, State.storySlug,
      State.writers, State.writersError, State.writerChoice, State.claudeAck, State.openStep, State.showAllShots, State.imageJobs]);
    if (!force && json === State.lastJSON) return;
    State.lastJSON = json;

    var activeEl = document.activeElement;
    var focusId = (activeEl && wizard.contains(activeEl) && activeEl.id) ? activeEl.id : '';
    var caret = null;
    if (focusId && typeof activeEl.selectionStart === 'number') {
      caret = { s: activeEl.selectionStart, e: activeEl.selectionEnd };
    }

    wizard.textContent = '';
    var stages = State.pipeline.stages || [];
    var current = State.pipeline.current;
    var project = projectOf();

    var pname = $('project-name');
    if (pname) pname.textContent = project.story_slug || t('app.no_story');
    var cpack = $('chip-pack');
    if (cpack) cpack.textContent = t('scope.plan', { pack: project.pack || t('scope.none') });
    var clang = $('chip-languages');
    if (clang) {
      var picked = (State.storyState && State.storyState.output_languages) || [];
      clang.textContent = t('scope.languages', { langs: picked.length ? picked.map(function (c) { return c.toUpperCase(); }).join(', ') : t('scope.none_ticked') });
    }

    updateStepper(stages, current);

    var working = $('working-on');
    if (working) {
      working.textContent = '';
      working.appendChild(scopeBar(project));
      working.appendChild(jobBar());
    }

    wizard.appendChild(progressLine(stages, current));
    stages.forEach(function (stage) {
      wizard.appendChild(mkStageCard(stage, current, project));
    });

    var ops = $('expert-ops');
    if (ops) {
      ops.textContent = '';
      ops.appendChild(opsPanel());
    }
    var runs = $('runs-slot');
    if (runs) {
      runs.textContent = '';
      runs.appendChild(registryPanel());
    }

    applyDrafts(wizard);
    renderBanner();
    if (focusId) restoreFocus(focusId, caret);
    if (State.jumpTo) {
      var target = wizard.querySelector('.stage-' + State.jumpTo);
      State.jumpTo = '';
      if (target && target.scrollIntoView) target.scrollIntoView({ block: 'start' });
    }
  }

  function applyDrafts(wizard) {
    Object.keys(State.drafts).forEach(function (id) {
      var node = $(id);
      if (!node || !wizard.contains(node)) return;
      var d = State.drafts[id];
      if ('checked' in d) node.checked = d.checked;
      else node.value = d.value;
    });
  }

  function restoreFocus(id, caret) {
    var target = $(id);
    if (!target || typeof target.focus !== 'function') return;
    target.focus({ preventScroll: true });
    if (caret && typeof target.setSelectionRange === 'function') {
      try { target.setSelectionRange(caret.s, caret.e); } catch (e) { /* this control has no caret */ }
    }
  }

  function captureDraft(e) {
    var tg = e.target;
    if (!tg || !tg.id) return;
    if (tg.id === 'wiz-story-slug' || tg.id.indexOf('lang-') === 0) return;   // these follow the server or State
    if (tg.id.indexOf('writer-') === 0) return;                             // writer choice lives in State
    if (tg.type === 'checkbox') State.drafts[tg.id] = { checked: tg.checked };
    else State.drafts[tg.id] = { value: tg.value };
  }

  function showWizardNotice(msg) {
    var wizard = $('wizard');
    if (!wizard) return;
    wizard.textContent = '';
    wizard.appendChild(notice(msg));
  }

  function updateStepper(stages, current) {
    var stepper = $('stepper');
    if (!stepper) return;
    stages.forEach(function (stage) {
      var item = $('step-' + stage.id);
      if (!item) return;
      item.className = 'status-' + stage.status + (stage.id === current ? ' current' : '');
      if (stage.id === current) item.setAttribute('aria-current', 'step');
      else item.removeAttribute('aria-current');
      var line = item.querySelector('.step-status');
      if (line) line.textContent = statusWord(stage.status);
    });
  }

  // the one sentence above the cards: "Step 2 of 6: Plan the story - needs your OK"
  function progressLine(stages, current) {
    var idx = -1;
    var cur = null;
    stages.forEach(function (s, i) { if (s.id === current) { idx = i; cur = s; } });
    if (!cur) return el('p', { class: 'progress-line', id: 'progress-line', textContent: '' });
    return el('p', { class: 'progress-line', id: 'progress-line',
      textContent: t('step.progress', { n: idx + 1, name: stepName(cur.id), status: statusWord(cur.status) }) });
  }

  // working-on line: every panel below belongs to this story and plan
  function scopeBar(project) {
    var langs = State.langPick.length ? State.langPick.map(langName).join(', ') : t('scope.none_ticked');
    var opt = selectedOpt();
    return el('div', { class: 'card scope-bar', id: 'wizard-scope', role: 'status', children: [
      el('span', { class: 'chip', textContent: t('scope.working_on', { story: project.story_slug || t('scope.none') }) }),
      el('span', { class: 'chip', textContent: t('scope.plan', { pack: project.pack || t('scope.none') }) }),
      el('span', { class: 'chip', textContent: t('scope.languages', { langs: langs }) }),
      el('span', { class: 'chip', textContent: t('scope.writer', { name: opt ? writerShort(opt.id) : '-' }) })
    ]});
  }

  function jobBar() {
    var job = State.job;
    var text = job ? t('scope.job_running', { job: dash(job.command || job.kind || 'job'), state: dash(job.state || 'running') })
      : t('scope.job_idle');
    return el('div', { class: 'card jobbar ' + (job ? 'running' : ''), id: 'wizard-jobbar', role: 'status', textContent: text });
  }

  // the one banner: out-of-date server, low disk. It sits under the header and has "Check again".
  function renderBanner() {
    var banner = $('pipe-banner');
    if (!banner) return;
    var lines = [];
    if (State.version && State.version.stale) lines.push(t('banner.stale'));
    var disk = State.ops && State.ops.disk ? State.ops.disk : {};
    ['C', 'D'].forEach(function (d) {
      var row = disk[d];
      if (row && typeof row.free_gb === 'number' && row.free_gb < DISK_LOW_GB) {
        lines.push(t('banner.disk_low', { drive: d, free: row.free_gb, min: DISK_LOW_GB }));
      }
    });
    banner.textContent = '';
    if (!lines.length) { banner.hidden = true; return; }
    banner.hidden = false;
    lines.forEach(function (m) { banner.appendChild(el('p', { textContent: m })); });
    banner.appendChild(el('button', { type: 'button', id: 'banner-recheck', class: 'btn-quiet', textContent: t('banner.recheck_btn'),
      onclick: function () { loadOps(false); } }));
  }

  // only the open card shows its body (plan 4.4): the server's current step unless the owner opened another
  function stageIsOpen(id, current) {
    return id === (State.openStep || current || 'story');
  }

  function openStep(id) {
    State.openStep = id;
    State.jumpTo = id;
    render(true);
  }

  function mkStageCard(stage, current, project) {
    var open = stageIsOpen(stage.id, current);
    var card = el('div', { class: 'card step stage-' + stage.id + (stage.id === current ? ' is-current' : '') + (open ? ' is-open' : '') });

    var num = STAGE_IDS.indexOf(stage.id) + 1;
    card.appendChild(el('div', { class: 'card-header', children: [
      el('span', { class: 'step-circle', textContent: String(num) }),
      el('h3', { textContent: stepName(stage.id) }),
      el('span', { class: 'chip status-' + stage.status, children: [icon(statusIcon(stage.status)), statusWord(stage.status)] })
    ]}));
    card.appendChild(el('p', { class: 'detail', textContent: stepIntro(stage.id) }));

    if (!open) {
      card.appendChild(el('button', { type: 'button', class: 'btn-quiet', id: 'open-step-' + stage.id, textContent: t('step.open_btn'),
        onclick: function () { openStep(stage.id); } }));
      return card;
    }

    if (stage.progress && typeof stage.progress.total === 'number' && stage.progress.total > 0) {
      var pct = Math.min(100, Math.max(0, (stage.progress.done / stage.progress.total) * 100));
      card.appendChild(el('div', { class: 'progress', children: [el('div', { class: 'bar', style: { width: pct + '%' } })] }));
      card.appendChild(el('div', { class: 'progress-text', textContent: stage.progress.done + '/' + stage.progress.total }));
    }

    var actions = el('div', { class: 'actions' });
    var actionEls = stageActions(stage, project);
    if (actionEls) appendKids(actions, actionEls);
    card.appendChild(actions);
    if (stage.status === 'locked') {
      // a locked stage cannot act: disable its buttons instead of letting them answer with an error
      card.appendChild(el('p', { class: 'muted', textContent: t('step.locked_note') }));
      Array.prototype.forEach.call(actions.querySelectorAll('button'), function (b) { b.disabled = true; });
    }

    var gates = (State.pipeline && State.pipeline.gates) || [];
    gates.forEach(function (gate) {
      if (gate.stage === stage.id) card.appendChild(mkGateCard(gate, project));
    });

    if (stage.detail) {
      card.appendChild(helperDetails('stage-' + stage.id, [el('p', { class: 'muted', textContent: stageDetail(stage.detail) })]));
    }
    return card;
  }

  function stageActions(stage, project) {
    switch (stage.id) {
      case 'story': return storyActions(project);
      case 'analysis': return analysisActions(project);
      case 'images': return imagesActions(project);
      case 'readout': return readoutActions(project);
      case 'render': return renderActions(project);
      case 'export': return exportActions(project);
      default: return null;
    }
  }

  // ---------- Story card (step 1) ----------
  function savedLangs() {
    return (State.storyState && State.storyState.output_languages) || [];
  }

  // which one button is the main one in step 1: save the story, save the languages, or go on
  function storyMainAction(project) {
    if (!project.story_slug || State.storyDirty) return 'save';
    if (!savedLangs().length || !sameList(State.langPick, savedLangs())) return 'langs';
    return 'next';
  }

  function storyActions(project) {
    var frag = document.createDocumentFragment();
    var ns = State.storyState;
    var main = storyMainAction(project);

    // where it stopped, with Continue
    var nextBox = el('div', { class: 'gate-card', id: 'next-step' });
    nextBox.appendChild(el('h4', { textContent: t('next.title') }));
    if (State.stateError) {
      nextBox.appendChild(notice(t('next.err', { error: State.stateError })));
    } else if (!project.story_slug) {
      nextBox.appendChild(el('p', { class: 'muted', textContent: t('next.none_story') }));
    } else if (!ns) {
      nextBox.appendChild(el('p', { class: 'muted', textContent: t('next.loading') }));
    } else {
      var nx = ns.next_step || {};
      var nxStage = nx.stage || NEXT_STAGE[nx.key] || '';
      var nxText = nextText(nx.key, nx.label || nx.text || '');
      nextBox.appendChild(el('p', { textContent: nxText ? t('next.label', { text: nxText }) : t('next.nothing') }));
      if (nx.text) nextBox.appendChild(helperDetails('next', [el('p', { class: 'muted', textContent: String(nx.text) })]));
      if (nxStage) {
        var target = { stage: nxStage, pack: nx.pack || ns.latest_pack || '' };
        nextBox.appendChild(el('button', { type: 'button', id: 'btn-continue', class: 'btn-quiet', textContent: t('next.continue'),
          onclick: function () { continueStory(target, project); } }));
      }
      (ns.warnings || []).forEach(function (w, i) {
        var key = w && typeof w === 'object' ? String(w.key || '') : '';
        var raw = w && typeof w === 'object' ? (w.text || w.key || '') : String(w);
        nextBox.appendChild(el('p', { class: 'warning', textContent: warnText(key) }));
        nextBox.appendChild(helperDetails('warn-' + i, [el('p', { class: 'muted', textContent: String(raw) })]));
      });
    }
    frag.appendChild(nextBox);

    // story picker: the server is the only source of the selection
    frag.appendChild(el('label', { textContent: t('story.picker_label'), 'for': 'wiz-story-slug' }));
    var slugSelect = el('select', { id: 'wiz-story-slug', 'aria-label': t('story.picker_label') });
    slugSelect.appendChild(el('option', { value: '', textContent: t('story.new_option') }));
    (State.storyList || []).forEach(function (s) {
      var opt = el('option', {
        value: s.slug,
        textContent: s.slug + (s.packs && s.packs.length ? ' (' + s.packs.join(', ') + ')' : '')
      });
      if (s.slug === project.story_slug) opt.selected = true;
      slugSelect.appendChild(opt);
    });
    slugSelect.addEventListener('change', function () {
      var slug = slugSelect.value;
      if (!slug) {
        showError(t('story.err_new_hint'));
        render(true);
        return;
      }
      if (State.storyDirty) {
        showError(t('story.err_unsaved_switch'));
        render(true);
        return;
      }
      var row = (State.storyList || []).filter(function (s) { return s.slug === slug; })[0];
      State.busy = true;
      post('/api/pipeline/project', { story_slug: slug, pack: row && row.latest_pack ? row.latest_pack : '' })
        .then(function () { return refreshWizard(true); })
        .catch(function (err) { showApiError(err); render(true); })
        .finally(function () { State.busy = false; });
    });
    frag.appendChild(slugSelect);

    frag.appendChild(el('label', { textContent: t('story.new_slug_label'), 'for': 'wiz-story-new-slug' }));
    var newSlugInput = el('input', { type: 'text', id: 'wiz-story-new-slug', placeholder: t('story.new_slug_ph'), maxlength: 40, 'aria-label': t('story.new_slug_label'), value: State.newSlug || '' });
    newSlugInput.addEventListener('input', function () { State.newSlug = newSlugInput.value; });
    frag.appendChild(newSlugInput);

    frag.appendChild(el('label', { textContent: t('story.text_label'), 'for': 'wiz-story-text' }));
    var textarea = el('textarea', { id: 'wiz-story-text', rows: 10, 'aria-label': t('story.text_label') });
    textarea.value = State.storyText || '';
    textarea.addEventListener('input', function () {
      State.storyText = textarea.value;
      State.storyDirty = true;
    });
    frag.appendChild(textarea);

    var overwriteBox = el('input', { type: 'checkbox', id: 'wiz-story-overwrite', checked: !!State.overwrite });
    overwriteBox.addEventListener('change', function () { State.overwrite = overwriteBox.checked; });
    frag.appendChild(el('label', { class: 'inline', 'for': 'wiz-story-overwrite', children: [overwriteBox, ' ' + t('story.overwrite_label')] }));

    var saveBtn = el('button', {
      type: 'button',
      id: 'btn-save-story',
      class: main === 'save' ? 'btn-main' : 'btn-quiet',
      textContent: t('story.save_btn'),
      onclick: function () {
        var slug = slugSelect.value.trim() || newSlugInput.value.trim();
        var text = textarea.value;
        if (!SLUG_PAT.test(slug)) { showError(t('story.err_bad_name')); return; }
        if (countBytes(text) > MAX_STORY_BYTES) { showError(t('story.err_too_long')); return; }
        State.busy = true;
        post('/api/story/' + enc(slug), { text: text, overwrite: overwriteBox.checked })
          .then(function () {
            State.storySlug = slug;
            State.storyText = text;
            State.storyDirty = false;
            State.lastStorySlug = slug;
            State.newSlug = '';
            State.overwrite = false;
            showSuccess(t('ok.story_saved'));
            // a plan belongs to one story: keep the old plan only when the same story is still the project
            var keepPack = slug === projectOf().story_slug ? (projectOf().pack || '') : '';
            return post('/api/pipeline/project', { story_slug: slug, pack: keepPack });
          })
          .then(function () { return loadStoryList().then(function () { return refreshWizard(true); }); })
          .catch(function (err) { showApiError(err); })
          .finally(function () { State.busy = false; });
      }
    });
    frag.appendChild(saveBtn);
    if (!project.story_slug) frag.appendChild(el('p', { class: 'hint', textContent: t('story.saved_hint') }));

    frag.appendChild(languagesBox(project, main));
    if (project.story_slug) {
      frag.appendChild(foldDetails('story-more', t('story.more_choices'), [voiceEngineBox(project), bgmBox(project), voiceMapBox(project)]));
      frag.appendChild(foldDetails('story-youtube', t('story.youtube_title'), [linkBox(project)]));
      frag.appendChild(el('button', { type: 'button', id: 'btn-story-next', class: main === 'next' ? 'btn-main' : 'btn-quiet',
        textContent: t('story.next_btn'), onclick: function () { openStep('analysis'); } }));
    } else {
      frag.appendChild(foldDetails('story-youtube', t('story.youtube_title'), [linkBox(project)]));
    }

    return [frag];
  }

  function continueStory(target, project) {
    if (State.busy) { showError(t('story.err_busy')); return; }
    State.busy = true;
    post('/api/pipeline/project', { story_slug: project.story_slug, pack: target.pack || project.pack || '' })
      .then(function () {
        State.openStep = target.stage || '';
        State.jumpTo = target.stage || '';
        return refreshWizard(true);
      })
      .catch(function (err) { showApiError(err); })
      .finally(function () { State.busy = false; });
  }

  function toggleLang(code, on) {
    var i = State.langPick.indexOf(code);
    if (on && i < 0) State.langPick.push(code);
    if (!on && i >= 0) State.langPick.splice(i, 1);
    render(true);
  }

  function languagesBox(project, main) {
    var box = el('fieldset', { class: 'langs' });
    box.appendChild(el('legend', { textContent: t('story.langs_label') }));
    var pills = el('div', { class: 'pills' });
    LANGS.forEach(function (code) {
      var cb = el('input', { type: 'checkbox', id: 'lang-' + code, checked: State.langPick.indexOf(code) >= 0 });
      cb.addEventListener('change', function () { toggleLang(code, cb.checked); });
      pills.appendChild(el('label', { 'class': 'pill', 'for': 'lang-' + code, children: [cb, ' ' + langName(code)] }));
    });
    var allBtn = el('button', { type: 'button', id: 'lang-all', class: 'btn-quiet', textContent: t('story.lang_all'), onclick: function () {
      State.langPick = LANGS.slice();
      render(true);
    }});
    pills.appendChild(allBtn);
    box.appendChild(pills);
    var saved = savedLangs().length ? savedLangs().join(', ') : t('story.langs_none_saved');
    box.appendChild(el('p', { class: 'hint', textContent: t('story.langs_saved', { langs: saved }) }));
    var saveLang = el('button', { type: 'button', id: 'lang-save', class: main === 'langs' ? 'btn-main' : 'btn-quiet', textContent: t('story.lang_save_btn'),
      disabled: !State.langPick.length || !project.story_slug, onclick: function () {
      if (!State.langPick.length) { showError(t('story.err_pick_lang')); return; }
      State.busy = true;
      post('/api/story/' + enc(project.story_slug) + '/languages', { languages: State.langPick.slice() })
        .then(function (d) {
          showSuccess(t('ok.languages_saved', { langs: ((d && d.output_languages) || State.langPick).join(', ') }));
          State.prefsFor = '';
          return refreshWizard(true);
        })
        .catch(function (err) { showApiError(err); })
        .finally(function () { State.busy = false; });
    }});
    box.appendChild(saveLang);
    if (!project.story_slug) box.appendChild(el('p', { class: 'hint', textContent: t('story.lang_hint_pick') }));
    return box;
  }

  function voiceEngineBox(project) {
    var ve = (State.storyState && State.storyState.voice_engine) || {};
    var box = el('div', { class: 'gate-card', id: 'voice-engine' });
    box.appendChild(el('h4', { textContent: t('story.voices_title') }));
    var h3 = el('input', { type: 'checkbox', id: 'voice-en-h3', checked: draftOr('voice-en-h3', ve.en === 'h3') });
    box.appendChild(el('label', { class: 'inline', 'for': 'voice-en-h3', children: [h3, ' ' + t('story.voice_h3_label')] }));
    box.appendChild(el('p', { class: 'warning', textContent: t('story.voice_warn') }));
    box.appendChild(el('p', { class: 'hint', textContent: t('story.voice_fixed') }));
    box.appendChild(el('button', { type: 'button', id: 'voice-save', class: 'btn-quiet', textContent: t('story.voice_save_btn'), disabled: !project.story_slug, onclick: function () {
      var h3On = $('voice-en-h3') && $('voice-en-h3').checked;
      post('/api/story/' + enc(project.story_slug) + '/voices', { voice_engine: { en: h3On ? 'h3' : 'elevenlabs', hi: 'elevenlabs', mr: 'elevenlabs' } })
        .then(function () {
          delete State.drafts['voice-en-h3'];
          showSuccess(t('ok.voice_saved'));
          return refreshWizard(true);
        })
        .catch(function (err) { showApiError(err); });
    }}));
    return box;
  }

  function bgmBox(project) {
    var bg = (State.storyState && State.storyState.bgm) || {};
    var box = el('div', { class: 'gate-card', id: 'bgm-box' });
    box.appendChild(el('h4', { textContent: t('story.bgm_title') }));
    var on = el('input', { type: 'checkbox', id: 'bgm-on', checked: draftOr('bgm-on', !!bg.enabled) });
    var manifest = el('input', { type: 'text', id: 'bgm-manifest', 'aria-label': t('story.bgm_file_label'), placeholder: t('story.bgm_file_ph'), value: draftOr('bgm-manifest', bg.manifest || ''), disabled: !on.checked });
    on.addEventListener('change', function () { manifest.disabled = !on.checked; });
    box.appendChild(el('label', { class: 'inline', 'for': 'bgm-on', children: [on, ' ' + t('story.bgm_label')] }));
    box.appendChild(el('label', { 'for': 'bgm-manifest', textContent: t('story.bgm_file_label') }));
    box.appendChild(manifest);
    box.appendChild(el('button', { type: 'button', id: 'bgm-save', class: 'btn-quiet', textContent: t('story.bgm_save_btn'), disabled: !project.story_slug, onclick: function () {
      var enabled = $('bgm-on').checked;
      var path = $('bgm-manifest').value.trim();
      if (enabled && !path) { showError(t('story.bgm_need_path')); return; }
      post('/api/story/' + enc(project.story_slug) + '/bgm', { enabled: enabled, manifest: path })
        .then(function () {
          delete State.drafts['bgm-on'];
          delete State.drafts['bgm-manifest'];
          showSuccess(enabled ? t('ok.bgm_on') : t('ok.bgm_off'));
          return refreshWizard(true);
        })
        .catch(function (err) { showApiError(err); });
    }}));
    return box;
  }

  function voiceMapBox(project) {
    var box = el('div', { class: 'gate-card', id: 'voice-map' });
    box.appendChild(el('h4', { textContent: t('story.voicemap_title') }));
    if (!project.pack) { box.appendChild(el('p', { class: 'muted', textContent: t('story.voicemap_need_plan') })); return box; }
    if (!State.langPick.length) { box.appendChild(el('p', { class: 'muted', textContent: t('story.voicemap_need_langs') })); return box; }
    if (State.voicesError) { box.appendChild(notice(t('story.voicemap_unavailable', { error: State.voicesError }))); return box; }
    var vm = State.voices;
    if (!vm) { box.appendChild(el('p', { class: 'muted', textContent: t('story.voicemap_none') })); return box; }
    var voices = vm.voices || {};
    var ids = vm.characters ? vm.characters.map(function (c) { return c.id; }) : Object.keys(voices);
    if (!ids.length) { box.appendChild(el('p', { class: 'muted', textContent: t('story.voicemap_no_chars') })); return box; }
    var pp = packPath(project.story_slug, project.pack);
    var rowsBox = el('div');
    ids.forEach(function (cid) {
      var name = (vm.characters || []).filter(function (c) { return c.id === cid; })[0];
      var label = name && name.name ? name.name : cid;
      var fs = el('fieldset', { class: 'vm-row' });
      fs.appendChild(el('legend', { textContent: label }));
      State.langPick.forEach(function (lang) {
        var cur = voices[cid] && voices[cid][lang] ? voices[cid][lang] : '';
        var fid = 'voice-' + safeId(cid) + '-' + lang;
        fs.appendChild(el('label', { 'for': fid, textContent: langName(lang) }));
        fs.appendChild(el('input', { type: 'text', id: fid, value: draftOr(fid, cur), placeholder: t('story.voice_ph'), 'aria-label': t('story.voice_aria', { name: label, lang: langName(lang) }) }));
      });
      rowsBox.appendChild(fs);
    });
    box.appendChild(rowsBox);
    box.appendChild(el('button', { type: 'button', id: 'voice-map-save', class: 'btn-quiet', textContent: t('story.voicemap_save_btn'), onclick: function () {
      var out = {};
      ids.forEach(function (cid) {
        out[cid] = {};
        State.langPick.forEach(function (lang) {
          var node = $('voice-' + safeId(cid) + '-' + lang);
          out[cid][lang] = node ? node.value.trim() : '';
        });
      });
      post('/api/pack/voices?pack=' + enc(pp), { voices: out })
        .then(function () {
          Object.keys(State.drafts).forEach(function (k) { if (k.indexOf('voice-') === 0 && k !== 'voice-en-h3') delete State.drafts[k]; });
          showSuccess(t('ok.voice_map_saved'));
          return loadDetail();
        })
        .catch(function (err) { showApiError(err); });
    }}));
    box.appendChild(el('p', { class: 'hint', textContent: t('story.voicemap_hint') }));
    return box;
  }

  // YouTube link: preview, then the same run path as every other command (no spend)
  function linkBox(project) {
    var box = el('div', { class: 'gate-card', id: 'link-box' });
    box.appendChild(el('label', { 'for': 'link-url', textContent: t('story.link_label') }));
    box.appendChild(el('input', { type: 'text', id: 'link-url', placeholder: t('story.link_ph'), value: draftOr('link-url', '') }));
    box.appendChild(el('label', { 'for': 'link-lang', textContent: t('story.link_lang_label') }));
    var lang = el('select', { id: 'link-lang' });
    [['auto', t('story.link_lang_auto')], ['en', langName('en')], ['hi', langName('hi')], ['mr', langName('mr')]].forEach(function (o) {
      lang.appendChild(el('option', { value: o[0], textContent: o[1], selected: draftOr('link-lang', 'auto') === o[0] }));
    });
    box.appendChild(lang);
    box.appendChild(el('label', { 'for': 'link-asr', textContent: t('story.link_asr_label') }));
    var asr = el('select', { id: 'link-asr' });
    [['auto', t('story.asr_auto')], ['off', t('story.asr_off')], ['force', t('story.asr_force')]].forEach(function (o) {
      asr.appendChild(el('option', { value: o[0], textContent: o[1], selected: draftOr('link-asr', 'auto') === o[0] }));
    });
    box.appendChild(asr);
    box.appendChild(el('label', { class: 'inline', 'for': 'link-overwrite', children: [
      el('input', { type: 'checkbox', id: 'link-overwrite', checked: draftOr('link-overwrite', false) }), ' ' + t('story.link_overwrite')
    ]}));
    box.appendChild(el('button', { type: 'button', id: 'link-run', class: 'btn-quiet', textContent: t('story.link_run_btn'), disabled: !project.story_slug || State.busy, onclick: function () {
      runLink(null, null);
    }}));
    box.appendChild(linkResultBox());
    return box;
  }

  function engineText(engine) {
    return engine === 'whisper' ? t('story.engine_whisper') : t('story.engine_captions');
  }

  function linkResultBox() {
    var box = el('div', { id: 'link-result', role: 'status' });
    var r = State.link;
    if (!r) return box;
    if (r.status === 'ok') {
      var done = r.file ? t('story.link_ok_file', { file: r.file }) : t('story.link_ok');
      var extra = engineText(r.engine) + (r.chars ? ' ' + t('story.chars', { n: r.chars }) : '');
      box.appendChild(el('p', { textContent: done + ' ' + extra }));
    } else if (r.status === 'needs_choice') {
      box.appendChild(el('p', { textContent: t('story.link_pick') }));
      r.candidates.forEach(function (c) {
        box.appendChild(el('button', { type: 'button', id: 'link-cand-' + safeId(c), class: 'btn-quiet', textContent: t('story.link_use', { lang: langName(c) }), onclick: function () { runLink(c, null); } }));
      });
    } else if (r.status === 'refused' && /exist/i.test(r.reason || '')) {
      box.appendChild(notice(t('story.link_exists')));
      box.appendChild(el('button', { type: 'button', id: 'link-replace', class: 'btn-quiet', textContent: t('story.link_replace_btn'), onclick: function () { runLink(null, true); } }));
    } else {
      box.appendChild(el('p', { class: 'warning', textContent: t('story.link_not_done', { reason: r.reason || r.status || t('story.link_no_reason') }) }));
    }
    return box;
  }

  function runLink(langOverride, overwriteOverride) {
    var project = projectOf();
    if (!project.story_slug) { showError(t('story.err_pick_story')); return; }
    var url = $('link-url') ? $('link-url').value.trim() : '';
    if (!url) { showError(t('story.err_link_empty')); return; }
    if (State.busy) { showError(t('story.err_busy')); return; }
    var body = {
      url: url,
      lang: langOverride || ($('link-lang') ? $('link-lang').value : 'auto'),
      asr: $('link-asr') ? $('link-asr').value : 'auto',
      overwrite: overwriteOverride !== null ? overwriteOverride : !!($('link-overwrite') && $('link-overwrite').checked)
    };
    State.busy = true;
    State.link = { status: 'running', candidates: [] };
    render(true);
    post('/api/story/' + enc(project.story_slug) + '/link', body)
      .then(function (prev) {
        confirmDialog(t('story.confirm_link'), (prev.argv || []).join(' '), function () {
          State.busy = true;
          post('/api/run', { token: prev.token })
            .then(function (r) { return waitForJob(r.job_id); })
            .then(function (job) {
              return get('/api/jobs/' + enc(job.id) + '/result').then(function (res) {
                State.link = normalizeLink(res, job);
              });
            })
            .catch(function (err) { State.link = { status: 'failed', reason: errText(err), candidates: [] }; showApiError(err); })
            .finally(function () { State.busy = false; render(true); });
        }, function () { State.link = null; render(true); }, { yes: t('story.link_yes') });
      })
      .catch(function (err) {
        State.link = { status: 'refused', reason: errText(err), candidates: [] };
        showApiError(err);
        render(true);
      })
      .finally(function () { if (!State.confirmPending) State.busy = false; });
  }

  function normalizeLink(res, job) {
    var r = res && typeof res === 'object' ? res : {};
    var status = r.status || (job && job.state === 'done' ? 'ok' : 'failed');
    return {
      status: status,
      candidates: Array.isArray(r.candidates) ? r.candidates.map(String) : [],
      engine: r.engine || '',
      chars: r.chars || 0,
      file: r.file || '',
      reason: r.reason || r.message || ''
    };
  }

  // ---------- Plan card (step 2) ----------
  function suggestedPack(slug) {
    var row = (State.registry || []).filter(function (s) { return s.slug === slug; })[0];
    return row && row.next_pack ? row.next_pack : '';
  }

  function writerChooser(project) {
    var box = el('div', { id: 'writer-choice', class: 'writer-choice', role: 'radiogroup', 'aria-labelledby': 'writer-choice-title' });
    box.appendChild(el('h4', { id: 'writer-choice-title', textContent: t('writer.title') }));
    if (!State.writers) {
      box.appendChild(State.writersError ? notice(t('writer.load_fail', { error: State.writersError })) : el('p', { class: 'muted', textContent: t('writer.loading') }));
      return box;
    }
    var picked = State.writerChoice || State.writers.default;
    ['nvidia', 'openrouter', 'claude'].forEach(function (g) {
      var group = el('fieldset', { class: 'writer-group' });
      group.appendChild(el('legend', { textContent: writerGroup(g) }));
      (State.writers.options || []).forEach(function (opt) {
        if (opt.group === g) group.appendChild(writerCard(opt, picked));
      });
      box.appendChild(group);
    });
    var sel = selectedOpt();
    if (sel && sel.id === 'claude-opus') box.appendChild(claudeWarnBox());
    return box;
  }

  function writerCard(opt, picked) {
    var id = WRITER_CARD_ID[opt.id] || ('writer-opt-' + safeId(opt.id));
    var input = el('input', { type: 'radio', name: 'writer-opt', id: id, value: opt.id, checked: opt.id === picked, disabled: !opt.available });
    input.addEventListener('change', function () { chooseWriter(opt.id); });
    var tags = [chip(costWord(opt.cost), 'status-ready'), chip(speedWord(opt.speed), 'status-ready'), chip(qualityWord(opt.quality), 'status-ready')];
    if (!opt.tested) tags.push(chip(t('writer.tag_new'), 'status-open'));
    var body = el('span', { class: 'writer-main', children: [
      el('strong', { textContent: writerName(opt.id) }),
      el('span', { class: 'writer-desc', textContent: writerDesc(opt.id) }),
      el('span', { class: 'writer-tags', children: tags })
    ]});
    if (!opt.available) body.appendChild(el('span', { class: 'writer-reason', textContent: writerReason(opt.reason) }));
    return el('label', { class: 'writer-card' + (opt.id === picked ? ' is-picked' : '') + (opt.available ? '' : ' is-off'),
      'for': id, children: [input, body] });
  }

  // Claude: a warning and a tick box; the run then asks for the typed word (plan 2.4)
  function claudeWarnBox() {
    var box = el('div', { id: 'writer-claude-warn', class: 'notice warn-box' });
    box.appendChild(el('p', { textContent: t('writer.claude_warn') }));
    var ack = el('input', { type: 'checkbox', id: 'writer-claude-ack', checked: State.claudeAck });
    ack.addEventListener('change', function () { State.claudeAck = ack.checked; render(true); });
    box.appendChild(el('label', { class: 'inline', 'for': 'writer-claude-ack', children: [ack, ' ' + t('writer.claude_ack')] }));
    return box;
  }

  function analysisActions(project) {
    var frag = document.createDocumentFragment();
    var stage = getStage('analysis');
    var opt = selectedOpt();
    var needAck = !!(opt && opt.id === 'claude-opus' && !State.claudeAck);
    var canRun = !!(opt && opt.available) && !needAck && !State.busy;
    var readyToRun = !stage || stage.status === 'ready' || stage.status === 'rejected';

    frag.appendChild(writerChooser(project));

    frag.appendChild(el('label', { textContent: t('plan.name_label'), 'for': 'analysis-pack' }));
    var packInput = el('input', {
      type: 'text',
      id: 'analysis-pack',
      value: draftOr('analysis-pack', project.pack || suggestedPack(project.story_slug)),
      maxlength: 40,
      'aria-label': t('plan.name_label')
    });
    frag.appendChild(packInput);

    var runBtn = el('button', {
      type: 'button',
      id: 'analysis-run',
      class: readyToRun ? 'btn-main' : 'btn-quiet',
      textContent: t('plan.run_btn', { name: opt ? writerShort(opt.id) : '' }),
      disabled: !canRun,
      onclick: function () { runAnalysis(project, packInput.value.trim(), opt); }
    });
    frag.appendChild(runBtn);
    if (needAck) frag.appendChild(el('p', { class: 'btn-reason', textContent: t('plan.need_ack') }));
    else if (opt && !opt.available) frag.appendChild(el('p', { class: 'btn-reason', textContent: writerReason(opt.reason) }));

    if (State.packInfo) {
      frag.appendChild(packDetails(State.packInfo));
    } else if (project.pack) {
      frag.appendChild(el('p', { class: 'muted', textContent: t('plan.not_written') }));
    }

    frag.appendChild(validatorPanel(project));
    return [frag];
  }

  function runAnalysis(project, pack, opt) {
    var slug = project.story_slug;
    var stage = getStage('analysis');
    if (!slug) { showError(t('plan.err_no_story')); return; }
    if (!pack) { showError(t('plan.err_no_pack')); return; }
    var langs = savedLangs();
    if (!langs.length) { showError(t('plan.err_no_langs')); return; }
    if (!opt || !opt.available) { showError(t('plan.err_unavailable')); return; }
    if (stage && stage.status !== 'ready' && stage.status !== 'rejected') {
      showError(t('plan.err_not_ready'));
      return;
    }
    State.busy = true;
    var isClaude = opt.command === CLAUDE_COMMAND || opt.id === 'claude-opus';
    var args = Object.assign({ slug: slug, pack: pack, out_lang: langs.join(',') }, opt.args || {});
    post('/api/pipeline/project', { story_slug: slug, pack: pack })
      .then(function () {
        return post('/api/preview', { command: opt.command, args: args });
      })
      .then(function (data) {
        var argvText = (data.route ? data.route + '\n' : '') + (data.argv || []).join(' ');
        var message = isClaude ? t('plan.confirm_claude', { story: slug }) : t('plan.confirm_free', { story: slug, name: writerShort(opt.id) });
        confirmDialog(message, argvText, function (typed) {
          State.busy = true;
          post('/api/run', { token: data.token, confirm: typed || undefined })
            .then(function () { return refreshWizard(true); })
            .catch(function (err) { showApiError(err); })
            .finally(function () { State.busy = false; });
        }, null, isClaude
          ? { yes: t('dialog.yes_claude'), typed: data.confirm_text || 'CLAUDE' }
          : { yes: t('dialog.yes_start') });
      })
      .catch(function (err) { showApiError(err); })
      .finally(function () { if (!State.confirmPending) State.busy = false; });
  }

  // the scene list the owner checks at Gate A
  function packDetails(pack) {
    var box = el('div', { class: 'gate-card', id: 'plan-check' });
    box.appendChild(el('h4', { textContent: t('plan.what_title') }));
    var shots = pack.shots || [];
    var eps = pack.episodes || [];
    var secs = 0;
    shots.forEach(function (s) { secs += Number(s.editorial_duration_sec || s.seconds || 0) || 0; });
    box.appendChild(el('p', { textContent: t('plan.what_check', { scenes: shots.length, parts: eps.length, secs: Math.round(secs) }) }));

    if (eps.length) {
      var headsPart = [t('plan.h_part'), t('plan.h_scenes'), t('plan.h_seconds')];
      box.appendChild(dataTable(headsPart, eps.map(function (ep) {
        return [String(ep.n !== undefined ? ep.n : ep.episode), String(ep.shots), String(ep.seconds)];
      })));
    }
    if (shots.length) {
      var shown = State.showAllShots ? shots : shots.slice(0, 5);
      var headsScene = [t('plan.h_scene'), t('plan.h_part'), t('plan.h_route'), t('plan.h_seconds'), t('plan.h_what')];
      box.appendChild(dataTable(headsScene, shown.map(function (s) {
        return [
          s.id || '',
          String(s.episode || ''),
          s.route || s.mode || '',
          String(s.editorial_duration_sec || s.seconds || ''),
          (s.purpose || '').slice(0, 200)
        ];
      })));
      if (shots.length > 5) {
        box.appendChild(el('button', { type: 'button', id: 'plan-show-all', class: 'btn-quiet',
          textContent: State.showAllShots ? t('plan.show_fewer') : t('plan.show_all', { n: shots.length }),
          onclick: function () { State.showAllShots = !State.showAllShots; render(true); } }));
      }
    }

    var names = el('div');
    nameLine(names, t('plan.people'), pack.character_names);
    nameLine(names, t('plan.places'), pack.place_names);
    nameLine(names, t('plan.things'), pack.prop_names);
    if (pack.modes) {
      names.appendChild(el('strong', { textContent: t('plan.modes') + ': ' }));
      names.appendChild(document.createTextNode(Object.keys(pack.modes).map(function (k) { return k + ':' + pack.modes[k]; }).join(', ')));
    }
    box.appendChild(names);

    var kids = [];
    if (pack.check) kids.push(el('pre', { class: 'box', textContent: JSON.stringify(pack.check, null, 2) }));
    if (pack.route) kids.push(el('p', { class: 'muted', textContent: String(pack.route) }));
    if (kids.length) box.appendChild(helperDetails('plan-check-json', kids));
    return box;
  }

  function nameLine(node, label, list) {
    if (!list || !list.length) return;
    node.appendChild(el('strong', { textContent: label + ': ' }));
    node.appendChild(document.createTextNode(list.join(', ')));
    node.appendChild(el('br'));
  }

  function validatorPanel(project) {
    var box = el('div', { class: 'gate-card', id: 'validator-panel' });
    box.appendChild(el('h4', { textContent: t('plan.check_title') }));
    box.appendChild(el('p', { class: 'hint', textContent: t('plan.check_intro') }));
    if (!project.pack) {
      box.appendChild(el('p', { class: 'muted', textContent: t('plan.check_empty') }));
      return box;
    }
    if (State.validatorError) {
      box.appendChild(notice(t('plan.check_unavailable', { error: State.validatorError })));
    } else if (!State.validator) {
      box.appendChild(el('p', { class: 'muted', textContent: t('plan.check_not_run') }));
    } else {
      var v = State.validator;
      var errors = v.errors || [];
      var warnings = v.warnings || [];
      var clean = !validatorBlocks();
      box.appendChild(el('p', { children: [chip(clean ? t('plan.check_ok') : t('plan.check_errors', { n: errors.length }), clean ? 'status-approved' : 'status-failed')] }));
      var eps = v.stats && v.stats.episodes ? Object.keys(v.stats.episodes).map(function (k) { return v.stats.episodes[k]; }) : [];
      var nShots = 0, nSec = 0;
      eps.forEach(function (e) { nShots += e.shots || 0; nSec += e.seconds || 0; });
      box.appendChild(el('p', { textContent: t('plan.check_summary', { reels: eps.length, shots: nShots, secs: Math.round(nSec),
        mode: v.mode === 'legacy' ? t('plan.mode_legacy') : dash(v.mode), warnings: warnings.length }) }));
      var raw = [];
      warnings.forEach(function (w) { raw.push(el('p', { class: 'muted', textContent: (w.code ? w.code + ': ' : '') + (w.message || String(w)) })); });
      errors.forEach(function (e) { raw.push(el('p', { class: 'muted', textContent: [e.code || '', e.where || '', e.message || ''].join(' | ') })); });
      if (raw.length) box.appendChild(helperDetails('validator', raw));
    }
    var clean2 = !validatorBlocks();
    box.appendChild(el('button', { type: 'button', id: 'validator-run', class: (State.validator && clean2) ? 'btn-quiet' : 'btn-main',
      textContent: (State.validator && clean2) ? t('plan.check_again') : t('plan.check_btn'), disabled: State.busy, onclick: function () {
      State.busy = true;
      post('/api/pack/validate', { pack: packPath(project.story_slug, project.pack) })
        .then(function (rep) { State.validator = rep; State.validatorError = ''; render(true); })
        .catch(function (err) { showApiError(err); })
        .finally(function () { State.busy = false; });
    }}));
    return box;
  }

  function validatorBlocks() {
    var v = State.validator;
    return !v || v.ok === false || (v.errors || []).length > 0;
  }

  // ---------- Pictures card (step 3) ----------
  function imagesActions(project) {
    var frag = document.createDocumentFragment();
    var ok = !!(project.story_slug && project.pack && gateState('A') === 'approved');
    var jobsDone = State.imageJobs > 0;

    var buildBtn = el('button', {
      type: 'button',
      id: 'images-build-jobs',
      class: jobsDone ? 'btn-quiet' : 'btn-main',
      textContent: t('pics.build_btn'),
      disabled: !ok,
      onclick: function () { buildImageJobs(project, buildBtn); }
    });
    frag.appendChild(buildBtn);
    frag.appendChild(el('p', { class: 'hint', textContent: ok ? t('pics.build_hint_ok') : t('pics.build_hint_off') }));

    var packetBtn = el('button', {
      type: 'button',
      id: 'images-packet',
      class: jobsDone ? 'btn-main' : 'btn-quiet',
      textContent: t('pics.packet_btn'),
      onclick: function () {
        var pack = project.pack;
        var slug = project.story_slug;
        if (!slug) { showError(t('plan.err_no_story')); return; }
        if (!pack) { showError(t('plan.err_run_first')); return; }
        State.busy = true;
        var pp = packPath(slug, pack);
        get('/api/images?story=' + enc(slug) + '&pack=' + enc(pack))
          .then(function (data) {
            var jobs = data.jobs || [];
            if (!jobs.length) {
              showError(t('pics.err_no_jobs'));
              return null;
            }
            return get('/api/pack?pack=' + enc(pp)).then(function (packData) {
              var shots = (packData.shots || []).map(function (s) { return s.id; });
              var jobsFile = findJobsFile(jobs, shots, slug);
              if (!jobsFile) {
                showError(t('pics.err_no_jobs_file'));
                return null;
              }
              return post('/api/packet', { jobs: jobsFile, shots: shots, story: slug, pack: pack });
            });
          })
          .then(function (data) { if (data) showPacketMarkdown(data.markdown || ''); })
          .catch(function (err) { showApiError(err); })
          .finally(function () { State.busy = false; });
      }
    });
    frag.appendChild(packetBtn);

    frag.appendChild(el('p', { class: 'note', textContent: t('pics.rule_haiku') }));
    frag.appendChild(helperDetails('pics-rule', [el('p', { class: 'muted', textContent: t('pics.rule_raw') })]));
    frag.appendChild(el('p', { class: 'hint', textContent: t('pics.rule_full') }));

    if (State.summary && State.summary.images) {
      var imgs = State.summary.images;
      frag.appendChild(el('div', { class: 'counts', children: [
        el('span', { textContent: t('pics.finished', { final: imgs.final, expected: imgs.expected }) }),
        el('span', { textContent: t('pics.waiting', { n: imgs.pending }) }),
        el('span', { textContent: t('pics.checked', { n: imgs.reviewed }) })
      ]}));
    }
    return [frag];
  }

  // /api/images lists job rows {file, shot_id}. The packet needs one jobs file that holds every shot id of the pack.
  function findJobsFile(jobs, shotIds, slug) {
    var byFile = {};
    jobs.forEach(function (j) {
      if (!j || !j.file) return;
      if (slug && String(j.file).indexOf('generated/' + slug + '/') < 0) return;   // this story's folder only
      if (!byFile[j.file]) byFile[j.file] = {};
      if (j.shot_id) byFile[j.file][String(j.shot_id)] = true;
    });
    var names = Object.keys(byFile);
    for (var i = 0; i < names.length; i++) {
      if (coversAll(byFile[names[i]], shotIds)) return 'flow/' + names[i];
    }
    return null;
  }

  function coversAll(have, ids) {
    return ids.length > 0 && ids.every(function (id) { return have[String(id)] === true; });
  }

  // ---------- Image jobs: build_spec, then build_jobs_cmd (files only: no model call, no spend) ----------
  function gateState(id) {
    var gates = (State.pipeline && State.pipeline.gates) || [];
    for (var i = 0; i < gates.length; i++) {
      if (gates[i].id === id) return gates[i].state;
    }
    return null;
  }

  function buildImageJobs(project, btn) {
    var slug = project.story_slug;
    var pack = project.pack;
    if (!slug) { showError(t('plan.err_no_story')); return; }
    if (!pack) { showError(t('plan.err_run_first')); return; }
    if (gateState('A') !== 'approved') { showError(t('pics.err_gate_a')); return; }
    if (State.busy) { showError(t('story.err_busy')); return; }
    var packP = packPath(slug, pack);
    var genDir = 'flow/generated/' + slug + '/';
    var specPath = genDir + slug + '_image_spec.json';
    var seriesPath = genDir + slug + '_flow_series.json';
    var jobsName = slug + '_flow_jobs_adhyay' + ('0' + BUILD_ADHYAY).slice(-2) + '.json';
    State.busy = true;
    btn.disabled = true;
    // overwrite stays false: an existing spec or series (with the owner's accepted flags) is never replaced from the page
    post('/api/preview', { command: 'build_spec', args: { pack: packP, adhyay: BUILD_ADHYAY, overwrite: false } })
      .then(function (data) {
        confirmDialog(t('pics.confirm_build', { pack: packP, folder: genDir }), (data.argv || []).join(' '), function () {
          runImageJobs(data.token);
        }, null, { yes: t('dialog.yes_start') });
      })
      .catch(function (err) { showApiError(err); })
      .finally(function () {
        if (!State.confirmPending) State.busy = false;
        btn.disabled = false;
      });

    function runImageJobs(token) {
      State.busy = true;
      btn.disabled = true;
      post('/api/run', { token: token })
        .then(function (r) { return waitForJob(r.job_id); })
        .then(function (job) {
          if (job.state !== 'done') return failedJob(job, t('pics.err_spec'));
          return post('/api/preview', { command: 'build_jobs_cmd', args: { spec: specPath, series: seriesPath, adhyay: BUILD_ADHYAY, out: jobsName } })
            .then(function (p) { return post('/api/run', { token: p.token }); })
            .then(function (r) { return waitForJob(r.job_id); })
            .then(function (job2) {
              if (job2.state !== 'done') return failedJob(job2, t('pics.err_jobs'));
              showSuccess(t('ok.images_built', { path: genDir + jobsName }));
            });
        })
        .catch(function (err) { showApiError(err); })
        .finally(function () {
          State.busy = false;
          btn.disabled = false;
          refreshWizard(true);
        });
    }
  }

  // keeps polling while the job runs; the job bar at the top shows its state
  function waitForJob(jid, left) {
    var tries = typeof left === 'number' ? left : JOB_POLL_MAX;
    return get('/api/jobs').then(function (list) {
      var job = null;
      (list || []).forEach(function (j) { if (j.id === jid) job = j; });
      if (!job) throw new Error(t('ops.job_missing', { id: jid }));
      if (job.state !== 'running') return job;
      if (tries <= 0) throw new Error(t('ops.still_running'));
      return new Promise(function (resolve) { setTimeout(resolve, JOB_POLL_MS); })
        .then(function () { return waitForJob(jid, tries - 1); });
    });
  }

  // the converter's own refusal ("REFUSED: ...") or the last line of its output goes into the error bar
  function failedJob(job, prefix) {
    return get('/api/jobs/' + enc(job.id) + '/result').then(function (res) {
      var lines = (res && res.lines) || [];
      var refused = lines.filter(function (l) { return l.indexOf('REFUSED') === 0 || l.indexOf('Refusing') === 0; });
      var detail = refused.length ? refused[refused.length - 1] : (lines.length ? lines[lines.length - 1] : t('pics.no_output', { state: job.state }));
      throw new Error(prefix + ': ' + detail);
    });
  }

  function showPacketMarkdown(markdown) {
    var body = $('modal-body');
    var title = $('modal-title');
    if (!$('modal') || !title || !body) return;
    title.textContent = t('dialog.packet_title');
    body.textContent = '';
    body.appendChild(el('pre', { textContent: markdown }));
    body.appendChild(el('button', {
      type: 'button',
      class: 'btn-main',
      textContent: t('dialog.copy'),
      onclick: function () {
        if (navigator.clipboard) navigator.clipboard.writeText(markdown).catch(function () {});
      }
    }));
    body.appendChild(el('button', { type: 'button', class: 'btn-quiet', textContent: t('common.close'), onclick: function () { closeModal(); } }));
    openModal();
  }

  // ---------- Summary card (step 4) ----------
  function readoutActions(project) {
    var frag = document.createDocumentFragment();
    if (!State.summary) {
      frag.appendChild(el('p', { class: 'muted', textContent: t('sum.none') }));
      return [frag];
    }
    var summary = State.summary;
    var tiles = el('div', { class: 'stat-tiles' });
    var clipsPlanned = (summary.video && summary.video.shots && summary.video.takes) ? (summary.video.shots * summary.video.takes) : '-';
    [
      { label: t('sum.tile_parts'), value: dash(summary.reels) },
      { label: t('sum.tile_scenes'), value: dash(summary.shots) },
      { label: t('sum.tile_seconds'), value: dash(summary.seconds) },
      { label: t('sum.tile_people'), value: String((summary.characters || []).length) },
      { label: t('sum.tile_places'), value: String((summary.places || []).length) },
      { label: t('sum.tile_pics'), value: summary.images ? (String(summary.images.final) + '/' + String(summary.images.expected)) : '-' },
      { label: t('sum.tile_clips'), value: String(clipsPlanned) },
      { label: t('sum.tile_minutes'), value: summary.estimate ? String(summary.estimate.minutes) : '-' }
    ].forEach(function (tile) {
      tiles.appendChild(el('div', { class: 'tile', children: [
        el('div', { class: 'tile-value', textContent: tile.value }),
        el('div', { class: 'tile-label', textContent: tile.label })
      ]}));
    });
    frag.appendChild(tiles);

    var more = [];
    if (summary.episodes && summary.episodes.length) {
      var headsSum = [t('sum.h_part'), t('sum.h_scenes'), t('sum.h_seconds')];
      more.push(dataTable(headsSum, summary.episodes.map(function (ep) {
        return [String(ep.n !== undefined ? ep.n : ep.episode), String(ep.shots), String(ep.seconds)];
      })));
    }
    var namesDiv = el('div');
    nameLine(namesDiv, t('plan.people'), summary.characters);
    nameLine(namesDiv, t('plan.places'), summary.places);
    nameLine(namesDiv, t('plan.things'), summary.props);
    if (summary.modes) {
      namesDiv.appendChild(el('strong', { textContent: t('plan.modes') + ': ' }));
      namesDiv.appendChild(document.createTextNode(Object.keys(summary.modes).map(function (k) { return k + ':' + summary.modes[k]; }).join(', ')));
    }
    more.push(namesDiv);
    if (summary.video) {
      more.push(el('div', { children: [
        el('strong', { textContent: t('sum.takes') + ': ' }), document.createTextNode(String(summary.video.takes || 0)), el('br'),
        el('strong', { textContent: t('sum.clips_home') + ': ' }), document.createTextNode(String(summary.video.clips_home || 0))
      ]}));
    }
    if (summary.images) {
      more.push(el('div', { children: [
        el('strong', { textContent: t('sum.pics_done') + ': ' }), document.createTextNode(String(summary.images.final)), el('br'),
        el('strong', { textContent: t('sum.pics_pending') + ': ' }), document.createTextNode(String(summary.images.pending)), el('br'),
        el('strong', { textContent: t('sum.pics_checked') + ': ' }), document.createTextNode(String(summary.images.reviewed))
      ]}));
    }
    if (summary.estimate) more.push(helperDetails('sum-gpu', [el('p', { class: 'muted', textContent: t('sum.gpu', { units: String(summary.estimate.g4_units) }) })]));
    frag.appendChild(foldDetails('sum-more', t('sum.more_title'), more));

    frag.appendChild(el('h4', { textContent: t('sum.checks_title') }));
    var rawChecks = [];
    (summary.checks || []).forEach(function (c) {
      frag.appendChild(el('div', { class: 'check ' + (c.ok ? 'ok' : 'fail'), children: [
        el('span', { class: 'mark', textContent: c.ok ? t('sum.check_ok') : t('sum.check_fail') }),
        el('span', { class: 'check-name', textContent: checkLabel(c.name) })
      ]}));
      rawChecks.push(el('p', { class: 'muted', textContent: dash(c.name) + ': ' + dash(c.detail) }));
    });
    if (rawChecks.length) frag.appendChild(helperDetails('sum-checks', rawChecks));

    if ((summary.warnings || []).length) {
      frag.appendChild(el('h4', { textContent: t('sum.warn_title') }));
      frag.appendChild(el('div', { class: 'warnings', children: (summary.warnings || []).map(function (w) {
        return el('p', { class: 'warning', textContent: String(w) });
      })}));
    }
    return [frag];
  }

  // ---------- Video card (step 5) ----------
  function renderActions(project) {
    var frag = document.createDocumentFragment();
    var rs = State.render;
    var canPrepare = !!(rs && rs.prepare_ready === true);

    var prepareBtn = el('button', {
      type: 'button',
      id: 'render-prepare',
      class: canPrepare ? 'btn-quiet' : 'btn-main',
      textContent: t('video.prepare_btn'),
      disabled: !canPrepare || State.busy,
      onclick: function () {
        var slug = project.story_slug;
        var pack = project.pack;
        if (!slug || !pack) { showError(t('video.err_pick')); return; }
        State.busy = true;
        post('/api/preview', { command: 'h3_prepare', args: { story: packPath(slug, pack) + '/shots.json', scope: 'all' } })
          .then(function (data) {
            confirmDialog(t('video.confirm_prepare'), (data.argv || []).join(' '), function () {
              State.busy = true;
              post('/api/run', { token: data.token })
                .then(function () { return refreshWizard(true); })
                .catch(function (err) { showApiError(err); })
                .finally(function () { State.busy = false; });
            }, null, { yes: t('dialog.yes_start') });
          })
          .catch(function (err) { showApiError(err); })
          .finally(function () { if (!State.confirmPending) State.busy = false; });
      }
    });
    frag.appendChild(prepareBtn);
    frag.appendChild(el('p', { class: 'hint', textContent: canPrepare ? t('video.prepare_hint_ok') : t('video.prepare_hint_off') }));

    if (!project.pack) {
      frag.appendChild(el('p', { class: 'muted', textContent: t('video.need_plan') }));
      return [frag];
    }
    if (State.renderError) { frag.appendChild(notice(t('video.status_unavailable', { error: State.renderError }))); return [frag]; }
    if (!rs) { frag.appendChild(el('p', { class: 'muted', textContent: t('video.loading') })); return [frag]; }

    // images and asset manifest
    var assets = rs.asset_manifest || {};
    var blocking = assets.blocking_problems || [];
    var assetBox = el('div', { class: 'gate-card', id: 'asset-panel' });
    assetBox.appendChild(el('h4', { textContent: t('video.assets_title') }));
    assetBox.appendChild(el('p', { textContent: t('video.assets_line', {
      final: rs.images ? dash(rs.images.final) : '-', expected: rs.images ? dash(rs.images.expected) : '-',
      clips: dash(assets.clips), stand: dash(assets.placeholders), stale: assets.stale ? t('video.yes') : t('video.no') }) }));
    if (blocking.length) {
      assetBox.appendChild(el('p', { class: 'warning', textContent: t('video.blocking', { n: blocking.length }) }));
      assetBox.appendChild(el('ul', { children: blocking.map(function (b) { return el('li', { textContent: String(b) }); }) }));
    } else {
      assetBox.appendChild(el('p', { class: 'muted', textContent: t('video.no_blocking') }));
    }
    frag.appendChild(assetBox);

    // per-shot fallback with the human choices
    var fb = rs.fallback || [];
    if (fb.length) {
      var rows = fb.map(function (f) {
        var sid = String(f.shot_id || '');
        var choices = (f.human_choices || []).map(function (c) {
          return el('button', { type: 'button', id: 'choice-' + safeId(sid) + '-' + safeId(c), class: 'btn-quiet', textContent: choiceLabel(String(c)), onclick: function () {
            var note = $('choice-note-' + safeId(sid));
            post('/api/render/choice', { story: projectOf().story_slug, pack: projectOf().pack, shot: sid, choice: c, note: note ? note.value.trim() : '' })
              .then(function () { showSuccess(t('ok.choice_recorded', { shot: sid, choice: choiceLabel(String(c)) })); return loadDetail(); })
              .catch(function (err) { showApiError(err); });
          }});
        });
        var cell = el('div', { children: [
          el('label', { 'for': 'choice-note-' + safeId(sid), textContent: t('video.note_label') }),
          el('input', { type: 'text', id: 'choice-note-' + safeId(sid), maxlength: NOTE_MAX, value: draftOr('choice-note-' + safeId(sid), '') }),
          el('div', { class: 'btnrow', children: choices.length ? choices : [el('span', { class: 'muted', textContent: t('video.no_choice') })] })
        ]});
        return [sid, String(f.attempts === undefined ? '-' : f.attempts), dash(f.rung), dash(f.action), cell];
      });
      frag.appendChild(el('h4', { textContent: t('video.choice_title') }));
      var headsShot = [t('video.h_shot'), t('video.h_tries'), t('video.h_level'), t('video.h_next'), t('video.h_choice')];
      frag.appendChild(dataTable(headsShot, rows));
    }

    // Step 9 QC
    var s9 = rs.step9 || null;
    var s9Box = el('div', { class: 'gate-card', id: 'step9-panel' });
    s9Box.appendChild(el('h4', { textContent: t('video.final_title') }));
    if (!s9 || !s9.status) {
      s9Box.appendChild(el('p', { class: 'muted', textContent: t('video.final_none') }));
    } else {
      s9Box.appendChild(el('p', { children: [chip(s9.status === 'pass' ? t('video.final_pass') : t('video.final_fail'), s9.status === 'pass' ? 'status-approved' : 'status-failed')] }));
      var s9raw = [];
      (s9.checks || []).forEach(function (c) {
        s9raw.push(el('p', { class: 'muted', textContent: (c.ok ? 'OK: ' : 'FAIL: ') + dash(c.name) + (c.detail ? ' - ' + c.detail : '') }));
      });
      if (s9raw.length) s9Box.appendChild(helperDetails('step9', s9raw));
    }
    frag.appendChild(s9Box);

    frag.appendChild(authorPanel(project));
    return [frag];
  }

  // the detail writer: shows what it would fill; the run stays off unless the server allows it
  function authorPanel(project) {
    var box = el('div', { class: 'gate-card', id: 'author-panel' });
    box.appendChild(el('h4', { textContent: t('video.author_title') }));
    var a = State.author;
    if (State.authorError) {
      box.appendChild(notice(t('video.author_unavailable', { error: State.authorError })));
    } else if (!a) {
      box.appendChild(el('p', { class: 'muted', textContent: t('video.author_loading') }));
    } else {
      var derived = a.derived || {};
      var missing = a.missing || [];
      box.appendChild(el('p', { textContent: t('video.author_counts', { derived: dash(derived.count), missing: missing.length }) }));
      box.appendChild(el('p', { children: [chip(t('video.author_cache', { state: dash(a.cache) }), a.cache === 'fresh' ? 'status-approved' : 'status-ready')] }));
      if (missing.length) {
        var headsAuthor = [t('video.h_author_shot'), t('video.h_author_fields')];
        box.appendChild(dataTable(headsAuthor, missing.map(function (m) {
          return [String(m.shot_id || m.shot || ''), (m.fields || []).join(', ')];
        })));
      }
    }
    box.appendChild(el('button', { type: 'button', id: 'author-preview', class: 'btn-quiet', textContent: t('video.author_preview_btn'), disabled: !project.pack || State.busy, onclick: function () {
      State.busy = true;
      post('/api/author/preview', { pack: packPath(project.story_slug, project.pack) })
        .then(function (d) {
          State.authorPreview = typeof d === 'string' ? d : JSON.stringify(d, null, 2);
          render(true);
        })
        .catch(function (err) { showApiError(err); })
        .finally(function () { State.busy = false; });
    }}));
    if (State.authorPreview) box.appendChild(el('pre', { class: 'box', id: 'author-preview-out', textContent: State.authorPreview }));

    var allowed = !!(a && a.run_allowed);
    box.appendChild(el('label', { 'for': 'author-phrase', textContent: t('video.author_type', { phrase: AUTHOR_PHRASE }) }));
    box.appendChild(el('input', { type: 'text', id: 'author-phrase', autocomplete: 'off', value: draftOr('author-phrase', ''), 'aria-label': t('video.author_type', { phrase: AUTHOR_PHRASE }) }));
    box.appendChild(el('button', { type: 'button', id: 'author-run', class: 'btn-quiet', textContent: t('video.author_run_btn'), disabled: !allowed || !project.pack, onclick: function () {
      var typed = $('author-phrase') ? $('author-phrase').value.trim() : '';
      if (typed !== AUTHOR_PHRASE) { showError(t('video.author_err_phrase', { phrase: AUTHOR_PHRASE })); return; }
      State.busy = true;
      post('/api/preview', { command: 'h3_author', args: { pack: packPath(project.story_slug, project.pack) } })
        .then(function (data) {
          confirmDialog(t('video.confirm_author'), (data.argv || []).join(' '), function () {
            State.busy = true;
            post('/api/run', { token: data.token })
              .then(function () { delete State.drafts['author-phrase']; return refreshWizard(true); })
              .catch(function (err) { showApiError(err); })
              .finally(function () { State.busy = false; });
          }, null, { yes: t('dialog.yes_start') });
        })
        .catch(function (err) { showApiError(err); })
        .finally(function () { if (!State.confirmPending) State.busy = false; });
    }}));
    if (!allowed) box.appendChild(el('p', { class: 'hint', textContent: t('video.author_off') }));
    return box;
  }

  // ---------- Files card (step 6) ----------
  function exportActions(project) {
    var frag = document.createDocumentFragment();
    if (!project.story_slug || !project.pack) {
      frag.appendChild(el('p', { class: 'muted', textContent: t('files.need_plan') }));
      return [frag];
    }
    frag.appendChild(el('label', { 'for': 'export-reel-wiz', textContent: t('files.part_label') }));
    frag.appendChild(el('input', { type: 'number', id: 'export-reel-wiz', min: '1', value: draftOr('export-reel-wiz', '1') }));
    frag.appendChild(el('button', { type: 'button', id: 'export-show', class: 'btn-main', textContent: t('files.show_btn'), onclick: function () {
      var reel = $('export-reel-wiz') ? $('export-reel-wiz').value.trim() : '';
      if (!/^[0-9]+$/.test(reel) || Number(reel) < 1) { showError(t('files.err_part')); return; }
      get('/api/export?reel=' + enc(reel) + '&story=' + enc(project.story_slug) + '&pack=' + enc(project.pack))
        .then(function (d) { State.exportData = { reel: reel, data: d }; render(true); })
        .catch(function (err) { showApiError(err); });
    }}));
    var ex = State.exportData;
    if (ex && ex.data) {
      var d = ex.data;
      var clips = d.clips_in_order || [];
      frag.appendChild(el('p', { textContent: t('files.part_line', { reel: ex.reel, n: clips.length }) }));
      clips.forEach(function (c) {
        var label = typeof c === 'string' ? c : String(c.shot || '?') + (c.take ? ' ' + t('files.take', { n: c.take }) : ' ' + t('files.no_take'));
        frag.appendChild(el('p', { textContent: label }));
      });
      var a = d.assembly;
      var notBuilt = !a || String(a).toLowerCase() === 'not built';
      frag.appendChild(el('p', { children: [chip(notBuilt ? t('files.not_built') : t('files.built'), notBuilt ? 'status-failed' : 'status-approved'),
        document.createTextNode(' ' + (notBuilt ? dash(d.assembly_note) : String(a)))] }));
    }
    frag.appendChild(el('p', { class: 'hint', textContent: t('files.note') }));
    return [frag];
  }

  function getStage(id) {
    if (!State.pipeline || !State.pipeline.stages) return null;
    for (var i = 0; i < State.pipeline.stages.length; i++) {
      if (State.pipeline.stages[i].id === id) return State.pipeline.stages[i];
    }
    return null;
  }

  // ---------- Gates (scoped: every card shows its story and plan; every decision sends them) ----------
  function gateBlockReason(gate) {
    if (State.version && State.version.stale) return t('gate.off_stale');
    if (gate.id === 'A' && validatorBlocks()) return State.validator ? t('gate.off_errors') : t('gate.off_no_check');
    if (gate.id === 'D') return gateDBlockReason();
    return '';
  }

  function mkGateCard(gate, project) {
    var card = el('div', { class: 'gate card gate-' + gate.id + ' ' + gate.state });

    card.appendChild(el('div', { class: 'gate-header', children: [
      el('h4', { textContent: gateTitle(gate.id) }),
      el('span', { class: 'chip status-' + gate.state, textContent: statusWord(gate.state) })
    ]}));
    card.appendChild(el('p', { class: 'scope-line', textContent: t('gate.scope', { story: dash(project.story_slug), pack: dash(project.pack) }) }));

    if (gate.state === 'locked') {
      card.appendChild(el('p', { class: 'lock-note', textContent: t('gate.locked') }));
      return card;
    }

    if (gate.state === 'approved' || gate.state === 'rejected') {
      card.appendChild(el('div', { class: 'gate-info', children: [
        el('p', { children: [el('strong', { textContent: t('gate.by') + ': ' }), document.createTextNode(gate.by || '-')] }),
        el('p', { children: [el('strong', { textContent: t('gate.when') + ': ' }), document.createTextNode(gate.at || '-')] }),
        el('p', { children: [el('strong', { textContent: t('gate.note') + ': ' }), document.createTextNode(gate.note || '-')] })
      ]}));
      if (gate.state === 'approved') return card;
    }

    if (gate.id === 'D') card.appendChild(gateDRows(project));

    card.appendChild(el('label', { textContent: t('gate.note_label'), 'for': 'gate-note-' + gate.id }));
    var noteInput = el('textarea', { id: 'gate-note-' + gate.id, rows: 3, maxlength: NOTE_MAX, 'aria-label': t('gate.note_label') });
    noteInput.value = draftOr('gate-note-' + gate.id, '');
    card.appendChild(noteInput);

    var startInput = null;
    if (gate.id === 'C') {
      card.appendChild(el('label', { textContent: t('gate.start_label'), 'for': 'gate-confirm-C' }));
      startInput = el('input', { type: 'text', id: 'gate-confirm-C', autocomplete: 'off', 'aria-label': t('gate.start_label'), value: draftOr('gate-confirm-C', '') });
      card.appendChild(startInput);
    }

    var blockReason = gateBlockReason(gate);
    var stale = !!(State.version && State.version.stale);
    var needsStart = gate.id === 'C';
    var approveOff = !!blockReason || (needsStart && !(startInput && startInput.value === 'START'));
    var approveBtn = el('button', { type: 'button', id: 'gate-approve-' + gate.id, class: approveOff ? 'btn-quiet' : 'btn-main', textContent: gateApprove(gate.id), disabled: approveOff });
    approveBtn.addEventListener('click', function () {
      var note = stripNewlines(noteInput.value.trim());
      if (gate.id === 'C') {
        var typed = startInput ? startInput.value : '';
        if (typed !== 'START') { showError(t('gate.err_start')); return; }
        onGateDecision(gate.id, project, 'approve', note, typed);
        return;
      }
      confirmDialog(gateConfirm(gate.id, project), '', function () {
        onGateDecision(gate.id, project, 'approve', note, '');
      }, null, { yes: t('dialog.yes_approve') });
    });

    if (startInput) {
      startInput.addEventListener('input', function () {
        approveBtn.disabled = !!blockReason || startInput.value !== 'START';
      });
    }

    var btns = el('div', { class: 'gate-btns', children: [approveBtn, el('button', { type: 'button', id: 'gate-reject-' + gate.id, class: 'btn-quiet', textContent: t('gate.send_back'), disabled: stale, onclick: function () {
      var note = stripNewlines(noteInput.value.trim());
      if (note.length < NOTE_MIN || note.length > NOTE_MAX) { showError(t('gate.err_note')); return; }
      onGateDecision(gate.id, project, 'reject', note, '');
    }})]});
    card.appendChild(btns);
    if (blockReason) card.appendChild(el('p', { class: 'btn-reason', textContent: blockReason }));

    card.appendChild(el('p', { class: 'hint', textContent: gateNext(gate.id) }));
    return card;
  }

  // Gate D: one row per language, the BGM status and the subtitle safe edges
  function gateDRows(project) {
    var box = el('div', { class: 'gate-langs', id: 'gate-d-langs' });
    var rs = State.render || {};
    var langs = (rs.gate_d && rs.gate_d.languages) || [];
    var bgmOn = !!(State.storyState && State.storyState.bgm && State.storyState.bgm.enabled);
    box.appendChild(el('p', { children: [
      chip(bgmOn ? t('gate.d_bgm_on') : t('gate.d_bgm_off'), 'status-ready'), document.createTextNode(' '),
      chip(t('gate.d_safe'), 'status-ready')
    ]}));
    if (!langs.length) {
      box.appendChild(el('p', { class: 'muted', textContent: t('gate.d_no_rows') }));
    }
    langs.forEach(function (r) {
      var vo = r.vo || {};
      var checks = r.checks || [];
      var rowOk = (Number(vo.present) >= Number(vo.expected)) && !!r.captions_ass && !!r.final_mp4 && checks.every(function (c) { return c.ok; });
      var name = langName(r.lang);
      var row = el('div', { class: 'gate-lang-row ' + (rowOk ? 'ok' : 'fail') });
      row.appendChild(el('h5', { textContent: rowOk ? t('gate.d_lang_ready', { lang: name }) : t('gate.d_lang_not', { lang: name }) }));
      row.appendChild(el('p', { textContent: t('gate.d_voice', { present: dash(vo.present), expected: dash(vo.expected) }) + (Number(vo.present) < Number(vo.expected) ? t('gate.d_missing') : '') }));
      row.appendChild(el('p', { textContent: r.captions_ass ? t('gate.d_captions_yes') : t('gate.d_captions_no') }));
      row.appendChild(el('p', { textContent: r.final_mp4 ? t('gate.d_video_yes') : t('gate.d_video_no') }));
      var raw = [];
      checks.forEach(function (c) {
        row.appendChild(el('p', { textContent: c.ok ? t('gate.d_check_ok', { name: dash(c.name) }) : t('gate.d_check_fail', { name: dash(c.name) }) }));
        raw.push(el('p', { class: 'muted', textContent: dash(c.name) + (c.detail ? ' - ' + c.detail : '') }));
      });
      if (raw.length) row.appendChild(helperDetails('gate-d-' + safeId(String(r.lang || 'x')), raw));
      box.appendChild(row);
    });
    return box;
  }

  function gateDBlockReason() {
    var rs = State.render;
    var s9 = rs && rs.step9;
    if (!s9 || s9.status !== 'pass') return t('gate.off_s9');
    var langs = (rs.gate_d && rs.gate_d.languages) || [];
    if (!langs.length) return t('gate.off_no_rows');
    var bad = langs.filter(function (r) {
      var vo = r.vo || {};
      return !(Number(vo.present) >= Number(vo.expected) && r.captions_ass && r.final_mp4 && (r.checks || []).every(function (c) { return c.ok; }));
    });
    return bad.length ? t('gate.off_bad_row') : '';
  }

  function onGateDecision(gateId, project, decision, note, confirm) {
    if (State.busy) { showError(t('story.err_busy')); return; }
    if (!project.story_slug || !project.pack) { showError(t('gate.err_pick')); return; }
    State.busy = true;
    var body = { story: project.story_slug, pack: project.pack, gate: gateId, decision: decision, note: note };
    if (confirm) body.confirm = confirm;
    post('/api/pipeline/gate', body)
      .then(function () {
        var info = { title: gateTitle(gateId), story: project.story_slug, pack: project.pack };
        showSuccess(decision === 'approve' ? t('ok.gate_approved', info) : t('ok.gate_sent_back', info));
        clearDrafts('gate-note-' + gateId);
        clearDrafts('gate-confirm-' + gateId);
        return refreshWizard(true);
      })
      .catch(function (err) { showApiError(err); })
      .finally(function () { State.busy = false; });
  }

  // ---------- Computer check (Experts area, #expert-ops) ----------
  function opsPanel() {
    var box = el('div', { class: 'card ops-panel', id: 'ops-panel' });
    box.appendChild(el('h3', { textContent: t('ops.title') }));
    if (State.opsError) { box.appendChild(notice(t('ops.err', { error: State.opsError }))); return box; }
    var o = State.ops;
    if (!o) { box.appendChild(el('p', { class: 'muted', textContent: t('ops.loading') })); return box; }
    var disk = o.disk || {};
    ['C', 'D'].forEach(function (d) {
      var row = disk[d] || {};
      var low = typeof row.free_gb === 'number' && row.free_gb < DISK_LOW_GB;
      var text = typeof row.free_gb === 'number' ? t('ops.disk', { drive: d, free: row.free_gb }) : t('ops.disk_unknown', { drive: d });
      box.appendChild(el('p', { children: [
        chip(text, low ? 'status-failed' : 'status-approved'),
        document.createTextNode(' ' + (low ? t('ops.low') : t('ops.ok')))
      ]}));
    });
    var srv = o.server || {};
    box.appendChild(el('p', { textContent: t('ops.server', { pid: dash(srv.pid), started: shortTime(srv.started), stale: srv.stale ? t('ops.yes') : t('ops.no') }) }));
    var colab = o.colab || {};
    box.appendChild(el('p', { textContent: t('ops.colab_units', { used: dash(colab.ledger_total_units), cap: dash(colab.cap_units) }) }));
    box.appendChild(el('p', { textContent: colab.sessions_checked ? t('ops.sessions_listed', { names: listText(colab.sessions_listed) }) : t('ops.sessions_not_checked') }));
    box.appendChild(el('button', { type: 'button', id: 'ops-colab-check', class: 'btn-quiet', textContent: t('ops.colab_check_btn'), onclick: function () { loadOps(true); } }));
    return box;
  }

  // ---------- Modal (one implementation for the wizard) ----------
  function focusables(modal) {
    return modal.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
  }

  function openModal() {
    var modal = $('modal');
    if (!modal) return;
    State.lastFocused = document.activeElement;
    modal.hidden = false;
    var items = focusables(modal);
    if (items.length) items[0].focus();
    if (!modal._escapeListener) {
      modal._escapeListener = function (e) {
        if (e.key === 'Escape') closeModal();
        if (e.key === 'Tab') {
          var list = focusables(modal);
          if (!list.length) return;
          var first = list[0];
          var last = list[list.length - 1];
          if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
          else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
        }
      };
      modal.addEventListener('keydown', modal._escapeListener);
    }
  }

  function closeModal() {
    // a confirm that is closed (Run, Cancel, X, Escape, backdrop) ends the command it was holding
    if (State.confirmPending) { State.confirmPending = false; State.busy = false; }
    var modal = $('modal');
    if (!modal) return;
    modal.hidden = true;
    if (State.lastFocused && typeof State.lastFocused.focus === 'function') {
      State.lastFocused.focus();
    } else {
      var wizard = $('wizard');
      if (wizard) wizard.focus();
    }
  }

  // Cancel gets the focus first: Enter alone never runs a command.
  // opts.yes = the text of the yes button (already translated); opts.typed = the word the owner must type first.
  // onConfirm receives the typed word (or nothing).
  function confirmDialog(message, argvText, onConfirm, onCancel, opts) {
    var o = opts || {};
    var modal = $('modal');
    var title = $('modal-title');
    var body = $('modal-body');
    if (!modal || !title || !body) return;
    title.textContent = t('dialog.title');
    body.textContent = '';
    body.appendChild(el('p', { textContent: message }));
    var typedInput = null;
    if (o.typed) {
      body.appendChild(el('label', { 'for': 'confirm-typed', textContent: t('dialog.type_word', { word: o.typed }) }));
      typedInput = el('input', { type: 'text', id: 'confirm-typed', autocomplete: 'off', maxlength: 20, 'aria-label': t('dialog.type_word', { word: o.typed }) });
      body.appendChild(typedInput);
    }
    if (argvText) body.appendChild(helperDetails('confirm', [el('pre', { class: 'box', textContent: argvText })]));
    var cancelBtn = el('button', { type: 'button', id: 'confirm-cancel', class: 'btn-quiet', textContent: t('dialog.no_back'), onclick: function () {
      closeModal();
      if (onCancel) onCancel();
    }});
    var okBtn = el('button', { type: 'button', id: 'confirm-run', class: 'btn-main', textContent: o.yes || t('dialog.yes_start'), disabled: !!o.typed, onclick: function () {
      if (o.typed && (!typedInput || typedInput.value.trim().toUpperCase() !== o.typed)) return;
      closeModal();
      if (onConfirm) onConfirm(o.typed || '');
    }});
    if (typedInput) {
      typedInput.addEventListener('input', function () {
        okBtn.disabled = typedInput.value.trim().toUpperCase() !== o.typed;
      });
    }
    body.appendChild(el('div', { class: 'modal-btns', children: [cancelBtn, okBtn] }));
    State.confirmPending = true;   // State.busy stays set while the user decides (see closeModal)
    openModal();
    cancelBtn.focus();
  }

  // ---------- Error bar & success line ----------
  // errors stay until the owner closes them (B10); raw is the technical text, shown in "Details for the helper"
  function showError(msg, raw) {
    var bar = $('error-bar');
    var text = $('error-text');
    if (!bar || !text) return;
    text.textContent = msg;
    bar.classList.remove('success');
    if (State.errorTimer) { clearTimeout(State.errorTimer); State.errorTimer = null; }
    var rawText = raw === undefined || raw === null ? '' : String(raw);
    var rawNode = $('error-raw');
    var details = $('error-details');
    if (rawNode) { rawNode.textContent = rawText; rawNode.hidden = !rawText; }
    if (details) details.hidden = !rawText;
    bar.hidden = false;
    if (bar.scrollIntoView) bar.scrollIntoView({ block: 'nearest' });
  }

  function showApiError(err) {
    var s = window.I18N.serverError(errText(err));
    showError(s.text, s.raw);
  }

  function showSuccess(msg) {
    showError(msg, '');
    var bar = $('error-bar');
    if (!bar) return;
    bar.classList.add('success');
    State.errorTimer = setTimeout(function () {
      bar.hidden = true;
      bar.classList.remove('success');
    }, SUCCESS_MS);
  }

  // ---------- Runs & documents (run registry: read only) ----------
  function runBadge(status) {
    var st = status || 'no runs';
    return el('span', { class: 'badge ' + (RUN_BADGE[st] || 'b-notrun'), textContent: runWord(st) });
  }

  function runsTable(headers, rows) {
    var head = el('tr', { children: headers.map(function (h) { return el('th', { scope: 'col', textContent: h }); }) });
    var table = el('table', { children: [el('thead', { children: [head] }), el('tbody', { children: rows })] });
    // stacked labels on a phone: each cell names its column
    Array.prototype.forEach.call(table.querySelectorAll('tbody tr'), function (tr) {
      Array.prototype.forEach.call(tr.children, function (td, i) { td.setAttribute('data-label', headers[i] || ''); });
    });
    return el('div', { class: 'tablewrap', children: [table] });
  }

  function registryPanel() {
    var card = el('div', { class: 'card runs-panel', id: 'runs-panel' });
    card.appendChild(el('h3', { textContent: t('runs.title') }));
    card.appendChild(el('p', { class: 'hint', textContent: t('runs.hint') }));
    if (State.registryError) {
      card.appendChild(notice(t('runs.err', { error: State.registryError })));
      return card;
    }
    if (!State.registry) {
      card.appendChild(el('p', { class: 'muted', textContent: t('runs.loading') }));
      return card;
    }
    if (!State.registry.length) {
      card.appendChild(el('p', { class: 'muted', textContent: t('runs.none_stories') }));
      return card;
    }
    var headsRegistry = [t('runs.h_story'), t('runs.h_source'), t('runs.h_model'), t('runs.h_status'), t('runs.h_last'), t('runs.h_packs'), t('runs.h_runs')];
    card.appendChild(runsTable(headsRegistry, State.registry.map(registryRow)));
    if (State.registrySlug) card.appendChild(registryDetail(State.registrySlug));
    return card;
  }

  function registryRow(s) {
    var selected = s.slug === State.registrySlug;
    var pick = function () {
      State.registrySlug = selected ? '' : (s.slug || '');   // a click on the open story closes it
      State.registryDetail = null;
      render(true);
      loadRegistryDetail(State.registrySlug);
    };
    var status = s.error ? 'failed' : (s.status || 'no runs');
    return el('tr', {
      class: 'clickable' + (selected ? ' selected' : ''),
      tabindex: '0',
      onclick: pick,
      onkeydown: function (e) {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pick(); }
      },
      children: [
        el('td', { children: [el('strong', { textContent: dash(s.slug) }), el('br'), el('span', { class: 'muted', textContent: s.error ? s.error : dash(s.title) })] }),
        el('td', { textContent: s.source && s.source.type ? s.source.type : '-' }),
        el('td', { textContent: s.pack_models && s.latest_pack ? dash(s.pack_models[s.latest_pack] || s.last_model) : dash(s.last_model) }),
        el('td', { children: [runBadge(status)] }),
        el('td', { textContent: shortTime(s.last_run_at) }),
        el('td', { textContent: listText(s.packs) }),
        el('td', { textContent: String(s.run_count || 0) })
      ]
    });
  }

  function runRow(r) {
    return el('tr', { children: [
      el('td', { textContent: dash(r.run_id) }),
      el('td', { children: [runBadge(r.status)] }),
      el('td', { textContent: String(r.steps || 0) }),
      el('td', { textContent: listText(r.models) }),
      el('td', { textContent: listText(r.packs) }),
      el('td', { textContent: shortTime(r.started_at) }),
      el('td', { textContent: shortTime(r.ended_at) }),
      el('td', { textContent: dash(r.note) })
    ] });
  }

  function stepRow(r) {
    return el('tr', { children: [
      el('td', { textContent: dash(r.run_id) }),
      el('td', { textContent: dash(r.kind) }),
      el('td', { textContent: dash(r.stage) }),
      el('td', { children: [runBadge(r.status)] }),
      el('td', { textContent: dash(r.via) }),
      el('td', { textContent: dash(r.model) }),
      el('td', { textContent: dash(r.effort) }),
      el('td', { textContent: dash(r.pack) }),
      el('td', { textContent: shortTime(r.ended_at || r.at) }),
      el('td', { textContent: dash(r.note) })
    ] });
  }

  function registryDetail(slug) {
    var box = el('div', { class: 'runs-detail', id: 'runs-detail' });
    var d = State.registryDetail;
    if (!d || d.slug !== slug) {
      box.appendChild(el('p', { class: 'muted', textContent: t('runs.detail_loading', { slug: slug }) }));
      return box;
    }
    if (d.error) {
      box.appendChild(notice(t('runs.detail_err', { slug: slug, error: d.error })));
      return box;
    }
    box.appendChild(el('h4', { textContent: t('runs.detail_title', { slug: slug }) }));
    if (!(d.runs || []).length) box.appendChild(el('p', { class: 'muted', textContent: t('runs.none_runs') }));
    else {
      var headsRuns = [t('runs.h_run'), t('runs.h_result'), t('runs.h_steps'), t('runs.h_model'), t('runs.h_packs'), t('runs.h_started'), t('runs.h_ended'), t('runs.h_note')];
      box.appendChild(runsTable(headsRuns, d.runs.map(runRow)));
    }
    box.appendChild(el('h4', { textContent: t('runs.steps_title') }));
    var headsSteps = [t('runs.h_run'), t('runs.h_step'), t('runs.h_stage'), t('runs.h_result'), t('runs.h_via'), t('runs.h_model'), t('runs.h_effort'), t('runs.h_pack'), t('runs.h_time'), t('runs.h_note')];
    box.appendChild(runsTable(headsSteps, (d.steps || []).map(stepRow)));
    box.appendChild(el('h4', { textContent: t('runs.report_title') }));
    box.appendChild(el('p', { children: [el('a', {
      href: '/api/file?path=' + enc('stories/' + slug + '/RUN_REPORT.md'),
      target: '_blank',
      rel: 'noopener',
      textContent: t('runs.report_link')
    })] }));
    box.appendChild(el('pre', { class: 'box', textContent: d.report || t('runs.report_none') }));
    return box;
  }

  // ---------- Polling (one loop, paused while the tab is hidden) ----------
  function tick() {
    State.pollCount += 1;
    var slow = State.pollCount % DETAIL_EVERY === 1;
    loadStatus();
    loadSummary();
    loadRegistry();
    if (State.registrySlug) loadRegistryDetail(State.registrySlug);
    if (slow) {
      loadStoryList();
      loadOps(false);
      loadWriters();
    }
    refreshWizard(slow);
  }

  function startPolling() {
    if (State.pollTimer) return;
    State.pollTimer = setInterval(function () {
      if (!document.hidden) tick();
    }, POLL_MS);
  }

  function stopPolling() {
    if (State.pollTimer) {
      clearInterval(State.pollTimer);
      State.pollTimer = null;
    }
  }

  function handleVisibility() {
    if (document.hidden) {
      stopPolling();
    } else {
      startPolling();
      tick();
    }
  }

  // ---------- Init ----------
  function init() {
    var bar = $('error-bar');
    if (bar) bar.setAttribute('aria-live', 'polite');

    var modal = $('modal');
    if (modal) {
      modal.addEventListener('click', function (e) {
        if (e.target === modal) closeModal();
      });
    }

    var modalClose = $('modal-close');
    if (modalClose) modalClose.addEventListener('click', closeModal);

    var errorClose = $('error-close');
    if (errorClose) errorClose.addEventListener('click', function () {
      var b = $('error-bar');
      if (b) b.hidden = true;
    });

    var wizard = $('wizard');
    if (wizard) {
      // typed values are kept by id, so a re-render does not lose them
      wizard.addEventListener('input', captureDraft);
      wizard.addEventListener('change', captureDraft);
    }
    var working = $('working-on');
    if (working && !$('pipe-banner')) {
      var banner = el('div', { class: 'notice pipe-banner', id: 'pipe-banner', role: 'alert' });
      banner.hidden = true;
      working.parentNode.insertBefore(banner, working);
    }

    STAGE_IDS.forEach(function (id) {
      var b = $('step-btn-' + id);
      if (b) b.addEventListener('click', function () { openStep(id); });
    });

    window.addEventListener('studio:lang', function () { render(true); renderBanner(); });

    showWizardNotice(t('step.loading'));

    loadStoryList();
    loadPipeline().then(function () { return loadDetail(); });
    loadSummary();
    loadRegistry();
    loadStatus();
    loadOps(false);
    loadWriters();
    startPolling();
    document.addEventListener('visibilitychange', handleVisibility);
  }

  // ---------- Expose ----------
  window.StudioWizard = {
    refresh: function () { return refreshWizard(true); },
    project: function () { return projectOf(); }
  };

  function boot() {
    // the string table loads first, so the first render already has the right language
    if (window.I18N && window.I18N.ready) window.I18N.ready.then(init, init);
    else init();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
