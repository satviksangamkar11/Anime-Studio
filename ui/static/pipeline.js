(function () {
  'use strict';

  var POLL_MS = 5000;
  var DETAIL_EVERY = 6;            // side panels reload every 6th poll (about 30 s)
  var ERROR_MS = 8000;
  var MAX_STORY_BYTES = 204800;
  var SLUG_PAT = /^[a-z0-9_]{1,40}$/;
  var NOTE_MIN = 1;
  var NOTE_MAX = 300;
  var LANGS = ['en', 'hi', 'mr'];
  var LANG_LABEL = { en: 'English', hi: 'Hindi', mr: 'Marathi' };
  var SAFE_ZONE = 'bottom 896 / top 360 / sides 160 (Instagram Reels + YouTube Shorts)';
  var AUTHOR_PHRASE = 'AUTHOR FIELDS';
  var DISK_LOW_GB = 2;
  var WRITER_NAME = 'super-vl';     // the default writer for the Analysis step (server default too)
  var BUILD_ADHYAY = 1;
  var API_TIMEOUT_MS = 120000;
  var JOB_POLL_MS = 700;
  var JOB_POLL_MAX = 900;           // about 10 minutes, then the job bar keeps showing the job

  var HUMAN_STATUS = {
    locked: 'Locked',
    ready: 'Ready',
    running: 'Running',
    waiting_approval: 'Waiting for your approval',
    approved: 'Approved',
    rejected: 'Rejected',
    done: 'Done',
    failed: 'Failed'
  };
  var HUMAN_GATE = {
    locked: 'Locked',
    open: 'Open',
    approved: 'Approved',
    rejected: 'Rejected'
  };

  // Runs & documents: status words and badge classes (style.css)
  var RUN_BADGE = { ok: 'b-ok', failed: 'b-failed', stopped: 'b-review', open: 'b-running', started: 'b-running' };
  var RUN_WORD = { ok: 'OK', failed: 'Failed', stopped: 'Stopped', open: 'Running', started: 'Running', 'no runs': 'No runs' };

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
    registryDetail: null
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
      if (e && e.name === 'AbortError') throw new Error('The server did not answer in 2 minutes. Try again.');
      throw new Error('Cannot reach the studio server. Is server.py running?');
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
      if (!State.pipeline) showWizardNotice('Server not reachable, retrying every 5 s. (' + errText(err) + ')');
      showError(errText(err));
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
      .catch(function (err) { showError(errText(err)); });
  }

  // adopt the saved languages once per story; after that the page keeps what the owner ticked
  function adoptPrefs(slug, st) {
    if (State.prefsFor === slug) return;
    State.prefsFor = slug;
    State.langPick = (st && st.output_languages || []).filter(function (c) { return LANGS.indexOf(c) >= 0; });
  }

  // one request per panel; each panel shows its own error, none breaks the rest
  function loadDetail() {
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
        if (e.status !== 404) showError(errText(e));
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
    }
    return Promise.all(jobs).then(function () { render(true); });
  }

  function loadSummary() {
    return get('/api/pipeline/summary')
      .then(function (data) {
        State.summary = data;
        render();
      })
      .catch(function (err) { showError(errText(err)); });
  }

  function loadStoryList() {
    return get('/api/story')
      .then(function (data) {
        State.storyList = data.slugs || [];
        render();
      })
      .catch(function (err) { showError(errText(err)); });
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

  function loadOps() {
    return Promise.all([
      get('/api/ops').then(function (d) { State.ops = d; State.opsError = ''; }, function (e) { State.ops = null; State.opsError = errText(e); }),
      get('/api/version').then(function (d) { State.version = d; }, function () { State.version = null; })
    ]).then(function () { render(true); });
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

  // ---------- Render ----------
  function render(force) {
    if (!State.pipeline) return;
    var wizard = $('wizard');
    if (!wizard) return;

    var json = JSON.stringify([State.pipeline, State.summary, State.packInfo, State.storyList, State.storyState, State.stateError,
      State.validator, State.validatorError, State.render, State.renderError, State.author, State.authorError, State.authorPreview,
      State.voices, State.voicesError, State.exportData, State.ops, State.opsError, State.version, State.job, State.link,
      State.langPick, State.registry, State.registryError, State.registrySlug, State.registryDetail, State.storySlug]);
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
    if (pname) pname.textContent = project.story_slug || '(no story)';
    var cpack = $('chip-pack');
    if (cpack) cpack.textContent = 'Pack: ' + (project.pack || 'none');
    var clang = $('chip-languages');
    if (clang) {
      var picked = (State.storyState && State.storyState.output_languages) || [];
      clang.textContent = 'Languages: ' + (picked.length ? picked.map(function (c) { return c.toUpperCase(); }).join(', ') : 'none ticked');
    }

    updateStepper(stages, current);

    wizard.appendChild(scopeBar(project));
    wizard.appendChild(jobBar());

    stages.forEach(function (stage) {
      wizard.appendChild(mkStageCard(stage, current, project));
    });
    wizard.appendChild(opsPanel());
    wizard.appendChild(registryPanel());

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
    var t = e.target;
    if (!t || !t.id) return;
    if (t.id === 'wiz-story-slug' || t.id.indexOf('lang-') === 0) return;   // these follow the server or State
    if (t.type === 'checkbox') State.drafts[t.id] = { checked: t.checked };
    else State.drafts[t.id] = { value: t.value };
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
      var line = item.querySelector('.step-status');
      if (line) line.textContent = HUMAN_STATUS[stage.status] || stage.status;
    });
  }

  // scope header: every panel below belongs to this story and pack
  function scopeBar(project) {
    var langs = State.langPick.length ? State.langPick.map(function (c) { return LANG_LABEL[c] || c; }).join(', ') : 'none chosen yet';
    var writer = State.pipeline && State.pipeline.write_pack_route ? State.pipeline.write_pack_route : 'free writer (' + WRITER_NAME + ')';
    return el('div', { class: 'card scope-bar', id: 'wizard-scope', role: 'status', children: [
      el('span', { class: 'chip', textContent: 'Story: ' + (project.story_slug || 'none') }),
      el('span', { class: 'chip', textContent: 'Pack: ' + (project.pack || 'none') }),
      el('span', { class: 'chip', textContent: 'Languages: ' + langs }),
      el('span', { class: 'chip', textContent: 'Writer: ' + writer })
    ]});
  }

  function jobBar() {
    var job = State.job;
    var text = job ? ('Running: ' + dash(job.command || job.kind || 'job') + ' (' + dash(job.state || 'running') + '). Wait for it to finish; the page updates on its own.')
      : 'No job running. Each step asks before it starts anything.';
    return el('div', { class: 'card jobbar ' + (job ? 'running' : ''), id: 'wizard-jobbar', role: 'status', textContent: text });
  }

  // top banner: stale server, low disk. Placed above the wizard.
  function renderBanner() {
    var banner = $('pipe-banner');
    if (!banner) return;
    var msgs = [];
    if (State.version && State.version.stale) {
      msgs.push('The studio server is older than its code. Stop it and start server.py again before you approve anything.');
    }
    var disk = State.ops && State.ops.disk ? State.ops.disk : {};
    ['C', 'D'].forEach(function (d) {
      var row = disk[d];
      if (row && typeof row.free_gb === 'number' && row.free_gb < DISK_LOW_GB) {
        msgs.push('Low disk space on ' + d + ': ' + row.free_gb + ' GB free (keep at least ' + DISK_LOW_GB + ' GB).');
      }
    });
    banner.textContent = '';
    if (!msgs.length) { banner.hidden = true; return; }
    banner.hidden = false;
    msgs.forEach(function (m) { banner.appendChild(el('p', { textContent: m })); });
  }

  function mkStageCard(stage, current, project) {
    var card = el('div', { class: 'card stage-' + stage.id + (stage.id === current ? ' current' : '') });

    var header = el('div', { class: 'card-header' });
    header.appendChild(el('h3', { textContent: stage.title }));
    header.appendChild(el('span', { class: 'chip status-' + stage.status, textContent: HUMAN_STATUS[stage.status] || stage.status }));
    card.appendChild(header);

    card.appendChild(el('p', { class: 'detail', textContent: stage.detail || '' }));

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
      Array.prototype.forEach.call(actions.querySelectorAll('button'), function (b) { b.disabled = true; });
    }

    var gates = (State.pipeline && State.pipeline.gates) || [];
    gates.forEach(function (gate) {
      if (gate.stage === stage.id) card.appendChild(mkGateCard(gate, project));
    });

    return card;
  }

  function stageActions(stage, project) {
    switch (stage.id) {
      case 'story': return storyActions(project);
      case 'analysis': return analysisActions(project);
      case 'images': return imagesActions(project);
      case 'readout': return readoutActions();
      case 'render': return renderActions(project);
      case 'export': return exportActions(project);
      default: return null;
    }
  }

  // which wizard stage each story_state next_step key opens (director/story_state.py keys)
  var NEXT_STAGE = {
    save_story: 'story', run_writer: 'analysis', run_writer_resume: 'analysis', fix_failed_stage: 'analysis',
    run_validator: 'analysis', gate_rejected: 'analysis', build_image_jobs: 'images', link_images: 'images',
    run_image_review: 'images', prepare_render: 'render', run_final_qc_export: 'export'
  };

  // ---------- Story card ----------
  function storyActions(project) {
    var frag = document.createDocumentFragment();
    var ns = State.storyState;

    // where it stopped, with Continue
    var nextBox = el('div', { class: 'gate-card', id: 'next-step' });
    nextBox.appendChild(el('h4', { textContent: 'Where you stopped' }));
    if (State.stateError) {
      nextBox.appendChild(notice('Could not read the story state: ' + State.stateError));
    } else if (!project.story_slug) {
      nextBox.appendChild(el('p', { class: 'muted', textContent: 'No story yet. Pick one below, or type a new slug and press Save story.' }));
    } else if (!ns) {
      nextBox.appendChild(el('p', { class: 'muted', textContent: 'Loading the next step...' }));
    } else {
      var nx = ns.next_step || {};
      // the server sends {key, text}; the key says which stage to open
      var nxStage = nx.stage || NEXT_STAGE[nx.key] || '';
      var nxText = nx.label || nx.text || '';
      nextBox.appendChild(el('p', { textContent: nxText ? 'Next: ' + nxText : 'Nothing to do right now.' }));
      if (nxStage) {
        nx = { stage: nxStage, pack: nx.pack || ns.latest_pack || '' };
        nextBox.appendChild(el('button', { type: 'button', id: 'btn-continue', textContent: 'Continue', onclick: function () { continueStory(nx, project); } }));
      }
      (ns.warnings || []).forEach(function (w) {
        var msg = w && typeof w === 'object' ? (w.text || w.key || '') : String(w);
        nextBox.appendChild(el('p', { class: 'warning', textContent: msg }));
      });
    }
    frag.appendChild(nextBox);

    // story picker: the server is the only source of the selection
    frag.appendChild(el('label', { textContent: 'Story', for: 'wiz-story-slug' }));
    var slugSelect = el('select', { id: 'wiz-story-slug', 'aria-label': 'Story' });
    slugSelect.appendChild(el('option', { value: '', textContent: '-- new story --' }));
    (State.storyList || []).forEach(function (s) {
      var nxl = s.state && s.state.next_step && (s.state.next_step.label || s.state.next_step.text) ? ' - next: ' + (s.state.next_step.label || s.state.next_step.text) : '';
      var opt = el('option', {
        value: s.slug,
        textContent: s.slug + (s.packs && s.packs.length ? ' (' + s.packs.join(', ') + ')' : '') + nxl
      });
      if (s.slug === project.story_slug) opt.selected = true;
      slugSelect.appendChild(opt);
    });
    slugSelect.addEventListener('change', function () {
      var slug = slugSelect.value;
      if (!slug) {
        showError('Type a new slug below and press Save story.');
        render(true);
        return;
      }
      if (State.storyDirty) {
        showError('The story text has changes that are not saved. Save the story first, then switch.');
        render(true);
        return;
      }
      var row = (State.storyList || []).filter(function (s) { return s.slug === slug; })[0];
      State.busy = true;
      post('/api/pipeline/project', { story_slug: slug, pack: row && row.latest_pack ? row.latest_pack : '' })
        .then(function () { return refreshWizard(true); })
        .catch(function (err) { showError(errText(err)); render(true); })
        .finally(function () { State.busy = false; });
    });
    frag.appendChild(slugSelect);

    frag.appendChild(el('label', { textContent: 'New slug (if creating)', for: 'wiz-story-new-slug' }));
    var newSlugInput = el('input', { type: 'text', id: 'wiz-story-new-slug', placeholder: 'new_slug', maxlength: 40, 'aria-label': 'New slug', value: State.newSlug || '' });
    newSlugInput.addEventListener('input', function () { State.newSlug = newSlugInput.value; });
    frag.appendChild(newSlugInput);

    frag.appendChild(el('label', { textContent: 'Story text (max ' + MAX_STORY_BYTES + ' bytes UTF-8)', for: 'wiz-story-text' }));
    var textarea = el('textarea', { id: 'wiz-story-text', rows: 10, 'aria-label': 'Story text' });
    textarea.value = State.storyText || '';
    textarea.addEventListener('input', function () {
      State.storyText = textarea.value;
      State.storyDirty = true;
    });
    frag.appendChild(textarea);

    var overwriteBox = el('input', { type: 'checkbox', id: 'wiz-story-overwrite', checked: !!State.overwrite });
    overwriteBox.addEventListener('change', function () { State.overwrite = overwriteBox.checked; });
    frag.appendChild(el('label', { class: 'inline', children: [overwriteBox, ' overwrite if SOURCE.md exists'] }));

    var saveBtn = el('button', {
      type: 'button',
      id: 'btn-save-story',
      textContent: 'Save story',
      onclick: function () {
        var slug = slugSelect.value.trim() || newSlugInput.value.trim();
        var text = textarea.value;
        if (!SLUG_PAT.test(slug)) { showError('Slug must be lower case letters, digits or _ (1-40 characters)'); return; }
        if (countBytes(text) > MAX_STORY_BYTES) { showError('Story text too long (max ' + MAX_STORY_BYTES + ' bytes UTF-8)'); return; }
        State.busy = true;
        post('/api/story/' + enc(slug), { text: text, overwrite: overwriteBox.checked })
          .then(function () {
            State.storySlug = slug;
            State.storyText = text;
            State.storyDirty = false;
            State.lastStorySlug = slug;
            State.newSlug = '';
            State.overwrite = false;
            showSuccess('Story saved. Next: pick the languages below.');
            return post('/api/pipeline/project', { story_slug: slug, pack: projectOf().pack || '' });
          })
          .then(function () { return loadStoryList().then(function () { return refreshWizard(true); }); })
          .catch(function (err) { showError(errText(err)); })
          .finally(function () { State.busy = false; });
      }
    });
    frag.appendChild(saveBtn);
    if (!project.story_slug) frag.appendChild(el('p', { class: 'hint', textContent: 'Save the story to begin. Then tick the languages.' }));

    frag.appendChild(languagesBox(project));
    frag.appendChild(voiceEngineBox(project));
    frag.appendChild(bgmBox(project));
    frag.appendChild(voiceMapBox(project));
    frag.appendChild(linkBox(project));

    return [frag];
  }

  function continueStory(nx, project) {
    if (State.busy) { showError('Busy, try again'); return; }
    State.busy = true;
    post('/api/pipeline/project', { story_slug: project.story_slug, pack: nx.pack || project.pack || '' })
      .then(function () {
        State.jumpTo = nx.stage || '';
        return refreshWizard(true);
      })
      .catch(function (err) { showError(errText(err)); })
      .finally(function () { State.busy = false; });
  }

  function toggleLang(code, on) {
    var i = State.langPick.indexOf(code);
    if (on && i < 0) State.langPick.push(code);
    if (!on && i >= 0) State.langPick.splice(i, 1);
    render(true);
  }

  function languagesBox(project) {
    var box = el('fieldset', { class: 'langs' });
    box.appendChild(el('legend', { textContent: 'Languages to make (tick at least one; the order you tick is the priority)' }));
    var pills = el('div', { class: 'pills' });
    LANGS.forEach(function (code) {
      var cb = el('input', { type: 'checkbox', id: 'lang-' + code, checked: State.langPick.indexOf(code) >= 0 });
      cb.addEventListener('change', function () { toggleLang(code, cb.checked); });
      pills.appendChild(el('label', { class: 'pill', 'for': 'lang-' + code, children: [cb, ' ' + LANG_LABEL[code]] }));
    });
    var allBtn = el('button', { type: 'button', id: 'lang-all', textContent: 'All (English, Hindi, Marathi)', onclick: function () {
      State.langPick = LANGS.slice();
      render(true);
    }});
    pills.appendChild(allBtn);
    box.appendChild(pills);
    var saved = State.storyState && State.storyState.output_languages && State.storyState.output_languages.length
      ? State.storyState.output_languages.join(', ') : 'none saved yet';
    box.appendChild(el('p', { class: 'hint', textContent: 'Saved: ' + saved }));
    var saveLang = el('button', { type: 'button', id: 'lang-save', textContent: 'Save languages', disabled: !State.langPick.length || !project.story_slug, onclick: function () {
      if (!State.langPick.length) { showError('Tick at least one language first.'); return; }
      State.busy = true;
      post('/api/story/' + enc(project.story_slug) + '/languages', { languages: State.langPick.slice() })
        .then(function (d) {
          showSuccess('Languages saved: ' + ((d && d.output_languages) || State.langPick).join(', '));
          State.prefsFor = '';
          return refreshWizard(true);
        })
        .catch(function (err) { showError(errText(err)); })
        .finally(function () { State.busy = false; });
    }});
    box.appendChild(saveLang);
    if (!project.story_slug) box.appendChild(el('p', { class: 'hint', textContent: 'Pick or save a story first.' }));
    return box;
  }

  function voiceEngineBox(project) {
    var ve = (State.storyState && State.storyState.voice_engine) || {};
    var box = el('div', { class: 'gate-card', id: 'voice-engine' });
    box.appendChild(el('h4', { textContent: 'Voices' }));
    var h3 = el('input', { type: 'checkbox', id: 'voice-en-h3', checked: draftOr('voice-en-h3', ve.en === 'h3') });
    box.appendChild(el('label', { class: 'inline', 'for': 'voice-en-h3', children: [h3, ' English: use the H3 built-in voice']}));
    box.appendChild(el('p', { class: 'warning', textContent: 'Warning: this makes an extra English render, so it costs extra H3 time. Leave it off to use ElevenLabs (the default).' }));
    box.appendChild(el('p', { class: 'hint', textContent: 'Hindi: ElevenLabs (fixed). Marathi: ElevenLabs (fixed).' }));
    var save = el('button', { type: 'button', id: 'voice-save', textContent: 'Save voices', disabled: !project.story_slug, onclick: function () {
      var h3On = $('voice-en-h3') && $('voice-en-h3').checked;
      post('/api/story/' + enc(project.story_slug) + '/voices', { voice_engine: { en: h3On ? 'h3' : 'elevenlabs', hi: 'elevenlabs', mr: 'elevenlabs' } })
        .then(function () {
          delete State.drafts['voice-en-h3'];
          showSuccess('Voice choice saved');
          return refreshWizard(true);
        })
        .catch(function (err) { showError(errText(err)); });
    }});
    box.appendChild(save);
    return box;
  }

  function bgmBox(project) {
    var bg = (State.storyState && State.storyState.bgm) || {};
    var box = el('div', { class: 'gate-card', id: 'bgm-box' });
    box.appendChild(el('h4', { textContent: 'Background music' }));
    var on = el('input', { type: 'checkbox', id: 'bgm-on', checked: draftOr('bgm-on', !!bg.enabled) });
    var manifest = el('input', { type: 'text', id: 'bgm-manifest', 'aria-label': 'Music manifest path', placeholder: 'path to the music manifest (JSON)', value: draftOr('bgm-manifest', bg.manifest || ''), disabled: !on.checked });
    on.addEventListener('change', function () { manifest.disabled = !on.checked; });
    box.appendChild(el('label', { class: 'inline', 'for': 'bgm-on', children: [on, ' Add background music (off by default)'] }));
    box.appendChild(el('label', { 'for': 'bgm-manifest', textContent: 'Music manifest (track id, path, license, bpm, lufs)' }));
    box.appendChild(manifest);
    box.appendChild(el('button', { type: 'button', id: 'bgm-save', textContent: 'Save music choice', disabled: !project.story_slug, onclick: function () {
      var enabled = $('bgm-on').checked;
      var path = $('bgm-manifest').value.trim();
      if (enabled && !path) { showError('Type the path to the music manifest, or turn background music off.'); return; }
      post('/api/story/' + enc(project.story_slug) + '/bgm', { enabled: enabled, manifest: path })
        .then(function () {
          delete State.drafts['bgm-on'];
          delete State.drafts['bgm-manifest'];
          showSuccess(enabled ? 'Background music on' : 'Background music off (2-stem mix)');
          return refreshWizard(true);
        })
        .catch(function (err) { showError(errText(err)); });
    }}));
    return box;
  }

  function voiceMapBox(project) {
    var box = el('div', { class: 'gate-card', id: 'voice-map' });
    box.appendChild(el('h4', { textContent: 'Voice map (one voice per character, per language)' }));
    if (!project.pack) { box.appendChild(el('p', { class: 'muted', textContent: 'Run the story analysis first. The voice map belongs to a pack.' })); return box; }
    if (!State.langPick.length) { box.appendChild(el('p', { class: 'muted', textContent: 'Tick and save the languages first.' })); return box; }
    if (State.voicesError) { box.appendChild(notice('Voice map not available: ' + State.voicesError)); return box; }
    var vm = State.voices;
    if (!vm) { box.appendChild(el('p', { class: 'muted', textContent: 'No voice map yet. It appears after the pack is written.' })); return box; }
    var voices = vm.voices || {};
    var ids = vm.characters ? vm.characters.map(function (c) { return c.id; }) : Object.keys(voices);
    if (!ids.length) { box.appendChild(el('p', { class: 'muted', textContent: 'The pack has no characters yet.' })); return box; }
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
        fs.appendChild(el('label', { 'for': fid, textContent: LANG_LABEL[lang] || lang }));
        fs.appendChild(el('input', { type: 'text', id: fid, value: draftOr(fid, cur), placeholder: 'pending owner choice', 'aria-label': label + ' voice in ' + (LANG_LABEL[lang] || lang) }));
      });
      rowsBox.appendChild(fs);
    });
    box.appendChild(rowsBox);
    box.appendChild(el('button', { type: 'button', id: 'voice-map-save', textContent: 'Save voice map', onclick: function () {
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
          showSuccess('Voice map saved. Empty boxes stay pending until you choose.');
          return loadDetail();
        })
        .catch(function (err) { showError(errText(err)); });
    }}));
    box.appendChild(el('p', { class: 'hint', textContent: 'No voice is created here. Choosing a voice never calls ElevenLabs.' }));
    return box;
  }

  // YouTube link: preview, then the same run path as every other command (no spend)
  function linkBox(project) {
    var box = el('div', { class: 'gate-card', id: 'link-box' });
    box.appendChild(el('h4', { textContent: 'YouTube link (captions first; Whisper only if needed)' }));
    box.appendChild(el('label', { 'for': 'link-url', textContent: 'YouTube link' }));
    box.appendChild(el('input', { type: 'text', id: 'link-url', placeholder: 'paste the YouTube link here', value: draftOr('link-url', '') }));
    box.appendChild(el('label', { 'for': 'link-lang', textContent: 'Language of the video' }));
    var lang = el('select', { id: 'link-lang' });
    [['auto', 'Let the server decide'], ['en', 'English'], ['hi', 'Hindi'], ['mr', 'Marathi']].forEach(function (o) {
      lang.appendChild(el('option', { value: o[0], textContent: o[1], selected: draftOr('link-lang', 'auto') === o[0] }));
    });
    box.appendChild(lang);
    box.appendChild(el('label', { 'for': 'link-asr', textContent: 'Speech-to-text (ASR)' }));
    var asr = el('select', { id: 'link-asr' });
    [['auto', 'Auto: captions if present, else Whisper'], ['off', 'Off: captions only'], ['force', 'Force: Whisper even if captions exist']].forEach(function (o) {
      asr.appendChild(el('option', { value: o[0], textContent: o[1], selected: draftOr('link-asr', 'auto') === o[0] }));
    });
    box.appendChild(asr);
    box.appendChild(el('label', { class: 'inline', 'for': 'link-overwrite', children: [
      el('input', { type: 'checkbox', id: 'link-overwrite', checked: draftOr('link-overwrite', false) }), ' Replace the existing SOURCE.md'
    ]}));
    box.appendChild(el('button', { type: 'button', id: 'link-run', textContent: 'Get transcript from link', disabled: !project.story_slug || State.busy, onclick: function () {
      runLink(null, null);
    }}));
    box.appendChild(linkResultBox());
    return box;
  }

  function linkResultBox() {
    var box = el('div', { id: 'link-result', role: 'status' });
    var r = State.link;
    if (!r) return box;
    if (r.status === 'ok') {
      box.appendChild(el('p', { textContent: 'Transcript saved' + (r.file ? ' to ' + r.file : '') + '. ' + (r.engine === 'whisper' ? 'Whisper used.' : 'Captions used.') + (r.chars ? ' ' + r.chars + ' characters.' : '') }));
    } else if (r.status === 'needs_choice') {
      box.appendChild(el('p', { textContent: 'The video language is not clear. Pick one:' }));
      r.candidates.forEach(function (c) {
        box.appendChild(el('button', { type: 'button', id: 'link-cand-' + safeId(c), textContent: 'Use ' + (LANG_LABEL[c] || c), onclick: function () { runLink(c, null); } }));
      });
    } else if (r.status === 'refused' && /exist/i.test(r.reason || '')) {
      box.appendChild(notice('SOURCE.md already exists. Replace it only if you mean to.'));
      box.appendChild(el('button', { type: 'button', id: 'link-replace', textContent: 'Replace SOURCE.md', onclick: function () { runLink(null, true); } }));
    } else {
      box.appendChild(el('p', { class: 'warning', textContent: 'Not done: ' + (r.reason || r.status || 'unknown reason') }));
    }
    return box;
  }

  function runLink(langOverride, overwriteOverride) {
    var project = projectOf();
    if (!project.story_slug) { showError('Pick a story first'); return; }
    var url = $('link-url') ? $('link-url').value.trim() : '';
    if (!url) { showError('Paste a YouTube link first'); return; }
    if (State.busy) { showError('Busy, try again'); return; }
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
        confirmDialog('Get the transcript from this link? This makes no model call and costs nothing.', (prev.argv || []).join(' '), function () {
          State.busy = true;
          post('/api/run', { token: prev.token })
            .then(function (r) { return waitForJob(r.job_id); })
            .then(function (job) {
              return get('/api/jobs/' + enc(job.id) + '/result').then(function (res) {
                State.link = normalizeLink(res, job);
              });
            })
            .catch(function (err) { State.link = { status: 'failed', reason: errText(err), candidates: [] }; showError(errText(err)); })
            .finally(function () { State.busy = false; render(true); });
        }, function () { State.link = null; render(true); });
      })
      .catch(function (err) {
        State.link = { status: 'refused', reason: errText(err), candidates: [] };
        showError(errText(err));
        render(true);
      })
      .finally(function () { State.busy = false; });
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

  // ---------- Analysis card ----------
  function suggestedPack(slug) {
    var row = (State.registry || []).filter(function (s) { return s.slug === slug; })[0];
    return row && row.next_pack ? row.next_pack : '';
  }

  function analysisActions(project) {
    var frag = document.createDocumentFragment();

    frag.appendChild(el('label', { textContent: 'Pack name', for: 'analysis-pack' }));
    var packInput = el('input', {
      type: 'text',
      id: 'analysis-pack',
      value: draftOr('analysis-pack', project.pack || suggestedPack(project.story_slug)),
      maxlength: 40,
      'aria-label': 'Pack name'
    });
    frag.appendChild(packInput);

    var runBtn = el('button', {
      type: 'button',
      id: 'analysis-run',
      textContent: 'Run story analysis',
      onclick: function () {
        var slug = project.story_slug;
        var pack = packInput.value.trim();
        var stage = getStage('analysis');
        if (!slug) { showError('Save the story first'); return; }
        if (!pack) { showError('Enter a pack name'); return; }
        var savedLangs = (State.storyState && State.storyState.output_languages) || [];
        if (!savedLangs.length) { showError('Tick the languages and press Save languages first. The writer has no default language.'); return; }
        if (stage && stage.status !== 'ready' && stage.status !== 'rejected') {
          showError('Analysis is not ready to run');
          return;
        }
        State.busy = true;
        post('/api/pipeline/project', { story_slug: slug, pack: pack })
          .then(function () {
            return post('/api/preview', { command: 'write_pack', args: { slug: slug, pack: pack, writer: WRITER_NAME, out_lang: savedLangs.join(',') } });
          })
          .then(function (data) {
            var argv = data.argv || [];
            var argvText = (data.route ? data.route + '\n' : '') + argv.join(' ');
            confirmDialog('Run story analysis for pack ' + pack + ' of story ' + slug + '?', argvText, function () {
              post('/api/run', { token: data.token })
                .then(function () { return refreshWizard(true); })
                .catch(function (err) { showError(errText(err)); });
            });
          })
          .catch(function (err) { showError(errText(err)); })
          .finally(function () { State.busy = false; });
      }
    });
    frag.appendChild(runBtn);
    frag.appendChild(el('p', { class: 'hint', textContent: 'Writer: free model (' + WRITER_NAME + '). Fixed for this step.' }));

    if (State.packInfo) {
      var pack = State.packInfo;
      var gateACard = el('div', { class: 'gate-card' });
      gateACard.appendChild(el('h4', { textContent: 'What you must approve' }));

      if (pack.shots && pack.shots.length) {
        gateACard.appendChild(dataTable(['Shot ID', 'Episode', 'Route', 'Seconds', 'Purpose'], pack.shots.map(function (s) {
          return [
            s.id || '',
            String(s.episode || ''),
            s.route || s.mode || '',
            String(s.editorial_duration_sec || s.seconds || ''),
            (s.purpose || '').slice(0, 200)
          ];
        })));
      }

      if (pack.episodes && pack.episodes.length) {
        gateACard.appendChild(dataTable(['Episode', 'Shots', 'Seconds'], pack.episodes.map(function (ep) {
          return [String(ep.n !== undefined ? ep.n : ep.episode), String(ep.shots), String(ep.seconds)];
        })));
      }

      var namesDiv = el('div');
      if (pack.character_names && pack.character_names.length) {
        namesDiv.appendChild(el('strong', { textContent: 'Characters: ' }));
        namesDiv.appendChild(document.createTextNode(pack.character_names.join(', ')));
        namesDiv.appendChild(el('br'));
      }
      if (pack.place_names && pack.place_names.length) {
        namesDiv.appendChild(el('strong', { textContent: 'Places: ' }));
        namesDiv.appendChild(document.createTextNode(pack.place_names.join(', ')));
        namesDiv.appendChild(el('br'));
      }
      if (pack.prop_names && pack.prop_names.length) {
        namesDiv.appendChild(el('strong', { textContent: 'Props: ' }));
        namesDiv.appendChild(document.createTextNode(pack.prop_names.join(', ')));
        namesDiv.appendChild(el('br'));
      }
      if (pack.modes) {
        namesDiv.appendChild(el('strong', { textContent: 'Modes: ' }));
        namesDiv.appendChild(document.createTextNode(Object.keys(pack.modes).map(function (k) { return k + ':' + pack.modes[k]; }).join(', ')));
      }
      gateACard.appendChild(namesDiv);

      if (pack.check) {
        gateACard.appendChild(el('pre', { class: 'box', textContent: JSON.stringify(pack.check, null, 2) }));
      }
      frag.appendChild(gateACard);
    } else if (project.pack) {
      frag.appendChild(el('p', { class: 'muted', textContent: 'The pack is not written yet. Run the story analysis above.' }));
    }

    frag.appendChild(validatorPanel(project));
    frag.appendChild(el('p', { class: 'hint', textContent: 'What happens next: after you approve Gate A, the image generation stage becomes available.' }));
    return [frag];
  }

  function validatorPanel(project) {
    var box = el('div', { class: 'gate-card', id: 'validator-panel' });
    box.appendChild(el('h4', { textContent: 'Pack check (validator)' }));
    box.appendChild(el('p', { class: 'hint', textContent: 'The check looks for mistakes in the pack. Gate A cannot be approved while it reports errors.' }));
    if (!project.pack) {
      box.appendChild(el('p', { class: 'muted', textContent: 'Run the story analysis first.' }));
      return box;
    }
    if (State.validatorError) {
      box.appendChild(notice('Validator not available: ' + State.validatorError));
    } else if (!State.validator) {
      box.appendChild(el('p', { class: 'muted', textContent: 'Not run yet. Press "Run validator" to check this pack.' }));
    } else {
      var v = State.validator;
      var errors = v.errors || [];
      var warnings = v.warnings || [];
      var clean = v.ok !== false && errors.length === 0;
      box.appendChild(el('p', { children: [chip(clean ? 'OK: no errors' : errors.length + ' error(s): fix them, then run again', clean ? 'status-approved' : 'status-failed')] }));
      var eps = v.stats && v.stats.episodes ? Object.keys(v.stats.episodes).map(function (k) { return v.stats.episodes[k]; }) : [];
      var nShots = 0, nSec = 0;
      eps.forEach(function (e) { nShots += e.shots || 0; nSec += e.seconds || 0; });
      box.appendChild(el('p', { textContent: 'Checked ' + eps.length + ' reel(s), ' + nShots + ' shots, ' + Math.round(nSec) + ' s. Format: ' +
        (v.mode === 'legacy' ? 'old (legacy) pack' : dash(v.mode)) + '. Warnings: ' + warnings.length + '.' }));
      warnings.slice(0, 3).forEach(function (w) {
        box.appendChild(el('p', { class: 'muted', textContent: (w.code ? w.code + ': ' : '') + (w.message || String(w)) }));
      });
      if (errors.length) {
        box.appendChild(dataTable(['Code', 'Where', 'Message'], errors.map(function (e) {
          return [e.code || '', e.where || '', e.message || ''];
        })));
      }
    }
    box.appendChild(el('button', { type: 'button', id: 'validator-run', textContent: 'Run validator', disabled: State.busy, onclick: function () {
      State.busy = true;
      post('/api/pack/validate', { pack: packPath(project.story_slug, project.pack) })
        .then(function (rep) { State.validator = rep; State.validatorError = ''; render(true); })
        .catch(function (err) { showError(errText(err)); })
        .finally(function () { State.busy = false; });
    }}));
    return box;
  }

  function validatorBlocks() {
    var v = State.validator;
    return !v || v.ok === false || (v.errors || []).length > 0;
  }

  // ---------- Images card ----------
  function imagesActions(project) {
    var frag = document.createDocumentFragment();

    var buildBtn = el('button', {
      type: 'button',
      id: 'images-build-jobs',
      textContent: 'Build image jobs',
      onclick: function () { buildImageJobs(project, buildBtn); }
    });
    var ok = !!(project.story_slug && project.pack && gateState('A') === 'approved');
    buildBtn.disabled = !ok;
    frag.appendChild(buildBtn);
    frag.appendChild(el('p', { class: 'hint', textContent: ok ? 'Writes the Flow spec and job file from the pack: no model call, no spend' : 'Approve Gate A first. Then this button writes the image files (no model call, no spend).' }));

    var packetBtn = el('button', {
      type: 'button',
      id: 'images-packet',
      textContent: 'Make Flow agent packet',
      onclick: function () {
        var pack = project.pack;
        var slug = project.story_slug;
        if (!slug) { showError('Save the story first'); return; }
        if (!pack) { showError('Run analysis first'); return; }
        State.busy = true;
        var pp = packPath(slug, pack);
        get('/api/images?story=' + enc(slug) + '&pack=' + enc(pack))
          .then(function (data) {
            var jobs = data.jobs || [];
            if (!jobs.length) {
              throw new Error('Image jobs are not built yet (press "Build image jobs" above first)');
            }
            return get('/api/pack?pack=' + enc(pp)).then(function (packData) {
              var shots = (packData.shots || []).map(function (s) { return s.id; });
              var jobsFile = findJobsFile(jobs, shots, slug);
              if (!jobsFile) throw new Error('No jobs file lists every shot of this pack yet');
              return post('/api/packet', { jobs: jobsFile, shots: shots, story: slug, pack: pack });
            });
          })
          .then(function (data) { showPacketMarkdown(data.markdown || ''); })
          .catch(function (err) { showError(errText(err)); })
          .finally(function () { State.busy = false; });
      }
    });
    frag.appendChild(packetBtn);

    frag.appendChild(el('p', { class: 'note', textContent: 'Flow agents run on Haiku, effort LOW; Claude starts them from the chat; this page shows their progress' }));
    frag.appendChild(el('p', { class: 'hint', textContent: 'Full-size check by Claude, then you approve' }));

    if (State.summary && State.summary.images) {
      var imgs = State.summary.images;
      frag.appendChild(el('div', { class: 'counts', children: [
        el('span', { textContent: 'Finals: ' + imgs.final + '/' + imgs.expected }),
        el('span', { textContent: 'Pending: ' + imgs.pending }),
        el('span', { textContent: 'Reviewed: ' + imgs.reviewed })
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
    if (!slug) { showError('Save the story first'); return; }
    if (!pack) { showError('Run analysis first'); return; }
    if (gateState('A') !== 'approved') { showError('Approve Gate A first'); return; }
    if (State.busy) { showError('Busy, try again'); return; }
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
        confirmDialog('Build the image spec, then the job file, for ' + packP + '? Files go in ' + genDir + ' only.',
          (data.argv || []).join(' '), function () {
            runImageJobs(data.token);
          });
      })
      .catch(function (err) { showError(errText(err)); })
      .finally(function () {
        State.busy = false;
        btn.disabled = false;
      });

    function runImageJobs(token) {
      State.busy = true;
      btn.disabled = true;
      post('/api/run', { token: token })
        .then(function (r) { return waitForJob(r.job_id); })
        .then(function (job) {
          if (job.state !== 'done') return failedJob(job, 'Building the image spec failed');
          return post('/api/preview', { command: 'build_jobs_cmd', args: { spec: specPath, series: seriesPath, adhyay: BUILD_ADHYAY, out: jobsName } })
            .then(function (p) { return post('/api/run', { token: p.token }); })
            .then(function (r) { return waitForJob(r.job_id); })
            .then(function (job2) {
              if (job2.state !== 'done') return failedJob(job2, 'Building the image jobs failed');
              showSuccess('Image jobs built: ' + genDir + jobsName);
            });
        })
        .catch(function (err) { showError(errText(err)); })
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
      if (!job) throw new Error('job ' + jid + ' is not listed');
      if (job.state !== 'running') return job;
      if (tries <= 0) throw new Error('Still running after about 10 minutes. Check the job bar at the top of the page.');
      return new Promise(function (resolve) { setTimeout(resolve, JOB_POLL_MS); })
        .then(function () { return waitForJob(jid, tries - 1); });
    });
  }

  // the converter's own refusal ("REFUSED: ...") or the last line of its output goes into the error bar
  function failedJob(job, prefix) {
    return get('/api/jobs/' + enc(job.id) + '/result').then(function (res) {
      var lines = (res && res.lines) || [];
      var refused = lines.filter(function (l) { return l.indexOf('REFUSED') === 0 || l.indexOf('Refusing') === 0; });
      var detail = refused.length ? refused[refused.length - 1] : (lines.length ? lines[lines.length - 1] : 'no output (state ' + job.state + ')');
      throw new Error(prefix + ': ' + detail);
    });
  }

  function showPacketMarkdown(markdown) {
    var body = $('modal-body');
    var title = $('modal-title');
    if (!$('modal') || !title || !body) return;
    title.textContent = 'Flow agent packet';
    body.textContent = '';
    body.appendChild(el('pre', { textContent: markdown }));
    body.appendChild(el('button', {
      type: 'button',
      textContent: 'Copy',
      onclick: function () {
        if (navigator.clipboard) navigator.clipboard.writeText(markdown).catch(function () {});
      }
    }));
    body.appendChild(el('button', { type: 'button', textContent: 'Close', onclick: function () { closeModal(); } }));
    openModal();
  }

  // ---------- Read-out card ----------
  function readoutActions() {
    var frag = document.createDocumentFragment();
    if (!State.summary) {
      frag.appendChild(el('p', { class: 'muted', textContent: 'No summary yet. It appears once a story and pack exist.' }));
      return [frag];
    }
    var summary = State.summary;
    var tiles = el('div', { class: 'stat-tiles' });
    var clipsPlanned = (summary.video && summary.video.shots && summary.video.takes) ? (summary.video.shots * summary.video.takes) : '-';
    [
      { label: 'Reels', value: dash(summary.reels) },
      { label: 'Shots', value: dash(summary.shots) },
      { label: 'Seconds', value: dash(summary.seconds) },
      { label: 'Characters', value: String((summary.characters || []).length) },
      { label: 'Places', value: String((summary.places || []).length) },
      { label: 'Images', value: summary.images ? (String(summary.images.final) + '/' + String(summary.images.expected)) : '-' },
      { label: 'Clips planned', value: String(clipsPlanned) },
      { label: 'Est. G4 units', value: summary.estimate ? String(summary.estimate.g4_units) : '-' },
      { label: 'Est. minutes', value: summary.estimate ? String(summary.estimate.minutes) : '-' }
    ].forEach(function (t) {
      tiles.appendChild(el('div', { class: 'tile', children: [
        el('div', { class: 'tile-value', textContent: t.value }),
        el('div', { class: 'tile-label', textContent: t.label })
      ]}));
    });
    frag.appendChild(tiles);

    if (summary.episodes && summary.episodes.length) {
      frag.appendChild(dataTable(['Episode', 'Shots', 'Seconds'], summary.episodes.map(function (ep) {
        return [String(ep.n !== undefined ? ep.n : ep.episode), String(ep.shots), String(ep.seconds)];
      })));
    }

    var namesDiv = el('div');
    if (summary.characters && summary.characters.length) {
      namesDiv.appendChild(el('strong', { textContent: 'Characters: ' }));
      namesDiv.appendChild(document.createTextNode(summary.characters.join(', ')));
      namesDiv.appendChild(el('br'));
    }
    if (summary.places && summary.places.length) {
      namesDiv.appendChild(el('strong', { textContent: 'Places: ' }));
      namesDiv.appendChild(document.createTextNode(summary.places.join(', ')));
      namesDiv.appendChild(el('br'));
    }
    if (summary.props && summary.props.length) {
      namesDiv.appendChild(el('strong', { textContent: 'Props: ' }));
      namesDiv.appendChild(document.createTextNode(summary.props.join(', ')));
      namesDiv.appendChild(el('br'));
    }
    if (summary.modes) {
      namesDiv.appendChild(el('strong', { textContent: 'Modes: ' }));
      namesDiv.appendChild(document.createTextNode(Object.keys(summary.modes).map(function (k) { return k + ':' + summary.modes[k]; }).join(', ')));
    }
    frag.appendChild(namesDiv);

    if (summary.video) {
      frag.appendChild(el('div', { children: [
        el('strong', { textContent: 'Takes: ' }), document.createTextNode(String(summary.video.takes || 0)), el('br'),
        el('strong', { textContent: 'Clips home: ' }), document.createTextNode(String(summary.video.clips_home || 0))
      ]}));
    }
    if (summary.images) {
      frag.appendChild(el('div', { children: [
        el('strong', { textContent: 'Finals: ' }), document.createTextNode(String(summary.images.final)), el('br'),
        el('strong', { textContent: 'Pending: ' }), document.createTextNode(String(summary.images.pending)), el('br'),
        el('strong', { textContent: 'Reviewed: ' }), document.createTextNode(String(summary.images.reviewed))
      ]}));
    }

    frag.appendChild(el('div', { class: 'checks', children: (summary.checks || []).map(function (c) {
      return el('div', { class: 'check ' + (c.ok ? 'ok' : 'fail'), children: [
        el('span', { class: 'mark', textContent: c.ok ? 'OK' : 'FAIL' }),
        el('span', { class: 'check-name', textContent: c.name }),
        el('span', { class: 'check-detail', textContent: c.detail })
      ]});
    })}));
    frag.appendChild(el('div', { class: 'warnings', children: (summary.warnings || []).map(function (w) {
      return el('p', { class: 'warning', textContent: String(w) });
    })}));
    return [frag];
  }

  // ---------- Render card: image jobs, assets, fallback, Step 9, author panel ----------
  function renderActions(project) {
    var frag = document.createDocumentFragment();
    var rs = State.render;
    var canPrepare = !!(rs && rs.prepare_ready === true);

    var prepareBtn = el('button', {
      type: 'button',
      id: 'render-prepare',
      textContent: 'Prepare render (no GPU)',
      disabled: !canPrepare || State.busy,
      onclick: function () {
        var slug = project.story_slug;
        var pack = project.pack;
        if (!slug || !pack) { showError('Pick a story and a pack first'); return; }
        State.busy = true;
        post('/api/preview', { command: 'h3_prepare', args: { story: packPath(slug, pack) + '/shots.json', scope: 'all' } })
          .then(function (data) {
            confirmDialog('Prepare render?', (data.argv || []).join(' '), function () {
              post('/api/run', { token: data.token })
                .then(function () { return refreshWizard(true); })
                .catch(function (err) { showError(errText(err)); });
            });
          })
          .catch(function (err) { showError(errText(err)); })
          .finally(function () { State.busy = false; });
      }
    });
    frag.appendChild(prepareBtn);
    frag.appendChild(el('p', { class: 'hint', textContent: canPrepare ? 'The render plan is ready. Preparing makes no GPU call.'
      : 'Prepare is off: the H3 story file is not built for this pack yet. The page shows the exact problems below.' }));

    if (!project.pack) {
      frag.appendChild(el('p', { class: 'muted', textContent: 'Run the analysis and approve the gates first. Then this panel fills in.' }));
      return [frag];
    }
    if (State.renderError) { frag.appendChild(notice('Render status not available: ' + State.renderError)); return [frag]; }
    if (!rs) { frag.appendChild(el('p', { class: 'muted', textContent: 'Loading the render status...' })); return [frag]; }

    // images and asset manifest
    var assets = rs.asset_manifest || {};
    var blocking = assets.blocking_problems || [];
    var assetBox = el('div', { class: 'gate-card', id: 'asset-panel' });
    assetBox.appendChild(el('h4', { textContent: 'Image jobs and assets' }));
    assetBox.appendChild(el('p', { textContent: 'Images: ' + (rs.images ? (dash(rs.images.final) + '/' + dash(rs.images.expected) + ' final') : 'not counted yet') +
      '   Clips: ' + dash(assets.clips) + '   Placeholders: ' + dash(assets.placeholders) + '   Stale: ' + (assets.stale ? 'yes' : 'no') }));
    if (blocking.length) {
      assetBox.appendChild(el('p', { class: 'warning', textContent: blocking.length + ' problem(s) block the render:' }));
      assetBox.appendChild(el('ul', { children: blocking.map(function (b) { return el('li', { textContent: String(b) }); }) }));
    } else {
      assetBox.appendChild(el('p', { class: 'muted', textContent: 'No blocking problems reported.' }));
    }
    frag.appendChild(assetBox);

    // per-shot fallback with the human choices
    var fb = rs.fallback || [];
    if (fb.length) {
      var rows = fb.map(function (f) {
        var sid = String(f.shot_id || '');
        var choices = (f.human_choices || []).map(function (c) {
          return el('button', { type: 'button', id: 'choice-' + safeId(sid) + '-' + safeId(c), textContent: String(c), onclick: function () {
            var note = $('choice-note-' + safeId(sid));
            post('/api/render/choice', { story: projectOf().story_slug, pack: projectOf().pack, shot: sid, choice: c, note: note ? note.value.trim() : '' })
              .then(function () { showSuccess('Choice recorded for ' + sid + ': ' + c); return loadDetail(); })
              .catch(function (err) { showError(errText(err)); });
          }});
        });
        var cell = el('div', { children: [
          el('label', { 'for': 'choice-note-' + safeId(sid), textContent: 'Note (optional)' }),
          el('input', { type: 'text', id: 'choice-note-' + safeId(sid), maxlength: NOTE_MAX, value: draftOr('choice-note-' + safeId(sid), '') }),
          el('div', { class: 'btnrow', children: choices.length ? choices : [el('span', { class: 'muted', textContent: 'no choice needed' })] })
        ]});
        return [sid, String(f.attempts === undefined ? '-' : f.attempts), dash(f.rung), dash(f.action), cell];
      });
      frag.appendChild(el('h4', { textContent: 'Shots that need a fallback' }));
      frag.appendChild(dataTable(['Shot', 'Attempts', 'Rung', 'Next action', 'Your choice'], rows));
    }

    // Step 9 QC
    var s9 = rs.step9 || null;
    var s9Box = el('div', { class: 'gate-card', id: 'step9-panel' });
    s9Box.appendChild(el('h4', { textContent: 'Step 9 render check' }));
    if (!s9 || !s9.status) {
      s9Box.appendChild(el('p', { class: 'muted', textContent: 'Not run. Gate D stays closed until the render check passes.' }));
    } else {
      s9Box.appendChild(el('p', { children: [chip(String(s9.status), s9.status === 'pass' ? 'status-approved' : 'status-failed')] }));
      (s9.checks || []).forEach(function (c) {
        s9Box.appendChild(el('p', { textContent: (c.ok ? 'OK: ' : 'FAIL: ') + dash(c.name) + (c.detail ? ' - ' + c.detail : '') }));
      });
    }
    frag.appendChild(s9Box);

    frag.appendChild(authorPanel(project));
    return [frag];
  }

  // H3 field author: derived fields, missing ones, cache, a dry-run preview. The run button stays off unless the server allows it.
  function authorPanel(project) {
    var box = el('div', { class: 'gate-card', id: 'author-panel' });
    box.appendChild(el('h4', { textContent: 'H3 field author (writes the missing render fields)' }));
    var a = State.author;
    if (State.authorError) {
      box.appendChild(notice('Author status not available: ' + State.authorError));
    } else if (!a) {
      box.appendChild(el('p', { class: 'muted', textContent: 'Loading the author status...' }));
    } else {
      var derived = a.derived || {};
      var missing = a.missing || [];
      box.appendChild(el('p', { textContent: 'Derived by rule: ' + dash(derived.count) + '   Missing: ' + missing.length }));
      box.appendChild(el('p', { children: [chip('Cache: ' + dash(a.cache), a.cache === 'fresh' ? 'status-approved' : 'status-ready')] }));
      if (missing.length) {
        box.appendChild(dataTable(['Shot', 'Fields missing'], missing.map(function (m) {
          return [String(m.shot_id || m.shot || ''), (m.fields || []).join(', ')];
        })));
      }
    }
    box.appendChild(el('button', { type: 'button', id: 'author-preview', textContent: 'Preview author prompts (dry run)', disabled: !project.pack || State.busy, onclick: function () {
      State.busy = true;
      post('/api/author/preview', { pack: packPath(project.story_slug, project.pack) })
        .then(function (d) {
          State.authorPreview = typeof d === 'string' ? d : JSON.stringify(d, null, 2);
          render(true);
        })
        .catch(function (err) { showError(errText(err)); })
        .finally(function () { State.busy = false; });
    }}));
    if (State.authorPreview) box.appendChild(el('pre', { class: 'box', id: 'author-preview-out', textContent: State.authorPreview }));

    var allowed = !!(a && a.run_allowed);
    box.appendChild(el('label', { 'for': 'author-phrase', textContent: 'To run the author (free model), type ' + AUTHOR_PHRASE + ' exactly' }));
    box.appendChild(el('input', { type: 'text', id: 'author-phrase', autocomplete: 'off', value: draftOr('author-phrase', ''), 'aria-label': 'Confirm phrase for the author run' }));
    box.appendChild(el('button', { type: 'button', id: 'author-run', textContent: 'Run author (free model)', disabled: !allowed || !project.pack, onclick: function () {
      var typed = $('author-phrase') ? $('author-phrase').value.trim() : '';
      if (typed !== AUTHOR_PHRASE) { showError('Type ' + AUTHOR_PHRASE + ' exactly first'); return; }
      State.busy = true;
      post('/api/preview', { command: 'h3_author', args: { pack: packPath(project.story_slug, project.pack) } })
        .then(function (data) {
          confirmDialog('Run the H3 field author with a free model for this pack? It writes the cache only.', (data.argv || []).join(' '), function () {
            post('/api/run', { token: data.token })
              .then(function () { delete State.drafts['author-phrase']; return refreshWizard(true); })
              .catch(function (err) { showError(errText(err)); });
          });
        })
        .catch(function (err) { showError(errText(err)); })
        .finally(function () { State.busy = false; });
    }}));
    if (!allowed) box.appendChild(el('p', { class: 'hint', textContent: 'Off: the server must be started with ANIME_STUDIO_ALLOW_FREE_MODEL=1 before this runs.' }));
    return box;
  }

  // ---------- Export card: scoped (story and pack) ----------
  function exportActions(project) {
    var frag = document.createDocumentFragment();
    if (!project.story_slug || !project.pack) {
      frag.appendChild(el('p', { class: 'muted', textContent: 'Pick a story and run the analysis first. Then the clips of that pack show here.' }));
      return [frag];
    }
    frag.appendChild(el('label', { 'for': 'export-reel-wiz', textContent: 'Reel number' }));
    frag.appendChild(el('input', { type: 'number', id: 'export-reel-wiz', min: '1', value: draftOr('export-reel-wiz', '1') }));
    frag.appendChild(el('button', { type: 'button', id: 'export-show', textContent: 'Show clips for this reel', onclick: function () {
      var reel = $('export-reel-wiz') ? $('export-reel-wiz').value.trim() : '';
      if (!/^[0-9]+$/.test(reel) || Number(reel) < 1) { showError('Reel must be a number, 1 or more.'); return; }
      get('/api/export?reel=' + enc(reel) + '&story=' + enc(project.story_slug) + '&pack=' + enc(project.pack))
        .then(function (d) { State.exportData = { reel: reel, data: d }; render(true); })
        .catch(function (err) { showError(errText(err)); });
    }}));
    var ex = State.exportData;
    if (ex && ex.data) {
      var d = ex.data;
      var clips = d.clips_in_order || [];
      frag.appendChild(el('p', { textContent: 'Reel ' + ex.reel + ': ' + clips.length + ' clip(s) from this pack.' }));
      clips.forEach(function (c) {
        var label = typeof c === 'string' ? c : String(c.shot || '?') + (c.take ? ' (take ' + c.take + ')' : ' (no take picked)');
        frag.appendChild(el('p', { textContent: label }));
      });
      var a = d.assembly;
      var notBuilt = !a || String(a).toLowerCase() === 'not built';
      frag.appendChild(el('p', { children: [chip(notBuilt ? 'NOT BUILT' : 'Built', notBuilt ? 'status-failed' : 'status-approved'),
        document.createTextNode(' ' + (notBuilt ? dash(d.assembly_note) : String(a)))] }));
    }
    frag.appendChild(el('p', { class: 'hint', textContent: 'Final reel files are not assembled yet. This shows the clips that are ready.' }));
    return [frag];
  }

  function getStage(id) {
    if (!State.pipeline || !State.pipeline.stages) return null;
    for (var i = 0; i < State.pipeline.stages.length; i++) {
      if (State.pipeline.stages[i].id === id) return State.pipeline.stages[i];
    }
    return null;
  }

  // ---------- Gates (scoped: every card shows its story and pack, every decision sends them) ----------
  function mkGateCard(gate, project) {
    var card = el('div', { class: 'gate card gate-' + gate.id + ' ' + gate.state });

    card.appendChild(el('div', { class: 'gate-header', children: [
      el('h4', { textContent: gate.title }),
      el('span', { class: 'chip status-' + gate.state, textContent: HUMAN_GATE[gate.state] || gate.state })
    ]}));
    card.appendChild(el('p', { class: 'scope-line', textContent: 'Story ' + dash(project.story_slug) + ' - Pack ' + dash(project.pack) + ' - Gate ' + gate.id }));

    if (gate.state === 'locked') {
      card.appendChild(el('p', { class: 'lock-note', textContent: 'waiting for the previous step' }));
      return card;
    }

    if (gate.state === 'approved' || gate.state === 'rejected') {
      card.appendChild(el('div', { class: 'gate-info', children: [
        el('p', { children: [el('strong', { textContent: 'By: ' }), document.createTextNode(gate.by || '-')] }),
        el('p', { children: [el('strong', { textContent: 'When: ' }), document.createTextNode(gate.at || '-')] }),
        el('p', { children: [el('strong', { textContent: 'Note: ' }), document.createTextNode(gate.note || '-')] })
      ]}));
      if (gate.state === 'approved') return card;
    }

    if (gate.id === 'D') card.appendChild(gateDRows(project));

    card.appendChild(el('label', { textContent: 'Note (optional for approve, required for reject, max ' + NOTE_MAX + ' chars)', 'for': 'gate-note-' + gate.id }));
    var noteInput = el('textarea', { id: 'gate-note-' + gate.id, rows: 3, maxlength: NOTE_MAX, 'aria-label': 'Gate note' });
    noteInput.value = draftOr('gate-note-' + gate.id, '');
    card.appendChild(noteInput);

    var startInput = null;
    if (gate.id === 'C') {
      card.appendChild(el('label', { textContent: 'Type START to confirm', 'for': 'gate-confirm-C' }));
      startInput = el('input', { type: 'text', id: 'gate-confirm-C', 'aria-label': 'START confirmation', value: draftOr('gate-confirm-C', '') });
      card.appendChild(startInput);
    }

    var btns = el('div', { class: 'gate-btns' });
    var approveBtn = el('button', { type: 'button', id: 'gate-approve-' + gate.id, textContent: 'Approve' });
    var blockReason = '';
    if (gate.id === 'A' && validatorBlocks()) {
      blockReason = State.validator ? 'Approve is off: the pack check reports errors. Fix them and run the validator again.' : 'Approve is off until you run the pack check (validator).';
    }
    if (gate.id === 'D') blockReason = gateDBlockReason();
    var needsStart = gate.id === 'C';
    approveBtn.disabled = !!blockReason || (needsStart && !(startInput && startInput.value === 'START'));
    approveBtn.addEventListener('click', function () {
      var note = stripNewlines(noteInput.value.trim());
      if (gate.id === 'C') {
        var typed = startInput ? startInput.value : '';
        if (typed !== 'START') { showError('Type START exactly'); return; }
        onGateDecision(gate.id, project, 'approve', note, typed);
        return;
      }
      confirmDialog('Approve Gate ' + gate.id + ' for story ' + project.story_slug + ', pack ' + project.pack + '?', '', function () {
        onGateDecision(gate.id, project, 'approve', note, '');
      });
    });
    btns.appendChild(approveBtn);
    if (blockReason) card.appendChild(el('p', { class: 'warning', textContent: blockReason }));

    if (startInput) {
      startInput.addEventListener('input', function () {
        approveBtn.disabled = (startInput.value !== 'START');
      });
    }

    btns.appendChild(el('button', { type: 'button', id: 'gate-reject-' + gate.id, textContent: 'Reject', onclick: function () {
      var note = stripNewlines(noteInput.value.trim());
      if (note.length < NOTE_MIN || note.length > NOTE_MAX) { showError('Note must be ' + NOTE_MIN + '-' + NOTE_MAX + ' characters'); return; }
      onGateDecision(gate.id, project, 'reject', note, '');
    }}));
    card.appendChild(btns);

    var nextHint = '';
    switch (gate.id) {
      case 'A': nextHint = 'After approval, image generation (Flow) becomes available.'; break;
      case 'B': nextHint = 'After approval, the read-out stage becomes available.'; break;
      case 'C': nextHint = 'After approval, the render stage becomes available.'; break;
      case 'D': nextHint = 'After approval, the export stage becomes available.'; break;
    }
    if (nextHint) card.appendChild(el('p', { class: 'hint', textContent: 'What happens next: ' + nextHint }));
    return card;
  }

  // Gate D: one row per language, the BGM status and the caption safe zone
  function gateDRows(project) {
    var box = el('div', { class: 'gate-langs', id: 'gate-d-langs' });
    var rs = State.render || {};
    var langs = (rs.gate_d && rs.gate_d.languages) || [];
    var bgmOn = !!(State.storyState && State.storyState.bgm && State.storyState.bgm.enabled);
    box.appendChild(el('p', { children: [
      chip(bgmOn ? 'BGM on (3-stem)' : 'no BGM (2-stem mix)', 'status-ready'), document.createTextNode(' '),
      chip('Safe zone: ' + SAFE_ZONE, 'status-ready')
    ]}));
    if (!langs.length) {
      box.appendChild(el('p', { class: 'muted', textContent: 'No language rows yet. They appear after the render plan exists.' }));
    }
    langs.forEach(function (r) {
      var vo = r.vo || {};
      var checks = r.checks || [];
      var rowOk = (Number(vo.present) >= Number(vo.expected)) && !!r.captions_ass && !!r.final_mp4 && checks.every(function (c) { return c.ok; });
      var row = el('div', { class: 'gate-lang-row ' + (rowOk ? 'ok' : 'fail') });
      row.appendChild(el('h5', { textContent: (LANG_LABEL[r.lang] || dash(r.lang)) + ': ' + (rowOk ? 'ready' : 'not ready') }));
      row.appendChild(el('p', { textContent: 'Voice-over files: ' + dash(vo.present) + '/' + dash(vo.expected) + (Number(vo.present) < Number(vo.expected) ? ' (missing)' : '') }));
      row.appendChild(el('p', { textContent: 'Captions (.ass): ' + (r.captions_ass ? 'present' : 'missing') }));
      row.appendChild(el('p', { textContent: 'Final video (mp4): ' + (r.final_mp4 ? 'present' : 'missing') }));
      checks.forEach(function (c) {
        row.appendChild(el('p', { textContent: (c.ok ? 'OK: ' : 'FAIL: ') + dash(c.name) + (c.detail ? ' - ' + c.detail : '') }));
      });
      box.appendChild(row);
    });
    return box;
  }

  function gateDBlockReason() {
    var rs = State.render;
    var s9 = rs && rs.step9;
    if (!s9 || s9.status !== 'pass') return 'Approve is off: the Step 9 render check has not passed.';
    var langs = (rs.gate_d && rs.gate_d.languages) || [];
    if (!langs.length) return 'Approve is off: no language rows to check yet.';
    var bad = langs.filter(function (r) {
      var vo = r.vo || {};
      return !(Number(vo.present) >= Number(vo.expected) && r.captions_ass && r.final_mp4 && (r.checks || []).every(function (c) { return c.ok; }));
    });
    return bad.length ? 'Approve is off: a language row is not ready.' : '';
  }

  function onGateDecision(gateId, project, decision, note, confirm) {
    if (State.busy) { showError('Busy, try again'); return; }
    if (!project.story_slug || !project.pack) { showError('Pick a story and a pack first'); return; }
    State.busy = true;
    var body = { story: project.story_slug, pack: project.pack, gate: gateId, decision: decision, note: note };
    if (confirm) body.confirm = confirm;
    post('/api/pipeline/gate', body)
      .then(function () {
        showSuccess('Gate ' + gateId + ' ' + (decision === 'approve' ? 'approved' : 'rejected') + ' for ' + project.story_slug + ' / ' + project.pack);
        clearDrafts('gate-note-' + gateId);
        clearDrafts('gate-confirm-' + gateId);
        return refreshWizard(true);
      })
      .catch(function (err) { showError(errText(err)); })
      .finally(function () { State.busy = false; });
  }

  // ---------- Ops panel ----------
  function opsPanel() {
    var box = el('div', { class: 'card ops-panel', id: 'ops-panel' });
    box.appendChild(el('h3', { textContent: 'Ops: disk, server and Colab spend' }));
    if (State.opsError) { box.appendChild(notice('Ops not available: ' + State.opsError)); return box; }
    var o = State.ops;
    if (!o) { box.appendChild(el('p', { class: 'muted', textContent: 'Loading ops...' })); return box; }
    var disk = o.disk || {};
    ['C', 'D'].forEach(function (d) {
      var row = disk[d] || {};
      var low = typeof row.free_gb === 'number' && row.free_gb < DISK_LOW_GB;
      box.appendChild(el('p', { children: [
        chip('Disk ' + d + ': ' + (typeof row.free_gb === 'number' ? row.free_gb + ' GB free' : 'unknown'), low ? 'status-failed' : 'status-approved'),
        document.createTextNode(low ? ' low' : ' ok')
      ]}));
    });
    var srv = o.server || {};
    box.appendChild(el('p', { textContent: 'Server: pid ' + dash(srv.pid) + ', started ' + shortTime(srv.started) + ', stale: ' + (srv.stale ? 'yes' : 'no') }));
    var colab = o.colab || {};
    box.appendChild(el('p', { textContent: 'Colab spend: ' + dash(colab.ledger_total_units) + ' of ' + dash(colab.cap_units) + ' units. Sessions listed: ' + dash(colab.sessions_listed) }));
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

  // Cancel gets the focus first: Enter alone never runs a command
  function confirmDialog(message, argvText, onConfirm, onCancel) {
    var modal = $('modal');
    var title = $('modal-title');
    var body = $('modal-body');
    if (!modal || !title || !body) return;
    title.textContent = 'Please confirm';
    body.textContent = '';
    body.appendChild(el('p', { textContent: message }));
    if (argvText) body.appendChild(el('pre', { textContent: argvText }));
    var cancelBtn = el('button', { type: 'button', id: 'confirm-cancel', textContent: 'Cancel', onclick: function () {
      closeModal();
      if (onCancel) onCancel();
    }});
    var okBtn = el('button', { type: 'button', id: 'confirm-run', textContent: 'Run', onclick: function () {
      closeModal();
      if (onConfirm) onConfirm();
    }});
    body.appendChild(el('div', { class: 'modal-btns', children: [cancelBtn, okBtn] }));
    openModal();
    cancelBtn.focus();
  }

  // ---------- Error bar & success line ----------
  function showError(msg) {
    var bar = $('error-bar');
    var text = $('error-text');
    if (!bar || !text) return;
    text.textContent = msg;
    bar.hidden = false;
    bar.classList.remove('success');
    if (State.errorTimer) clearTimeout(State.errorTimer);
    State.errorTimer = setTimeout(function () { bar.hidden = true; }, ERROR_MS);
  }

  function showSuccess(msg) {
    var bar = $('error-bar');
    var text = $('error-text');
    if (!bar || !text) return;
    text.textContent = msg;
    bar.hidden = false;
    bar.classList.add('success');
    if (State.errorTimer) clearTimeout(State.errorTimer);
    State.errorTimer = setTimeout(function () {
      bar.hidden = true;
      bar.classList.remove('success');
    }, ERROR_MS);
  }

  // ---------- Runs & documents (run registry: read only) ----------
  function runBadge(status) {
    var st = status || 'no runs';
    return el('span', { class: 'badge ' + (RUN_BADGE[st] || 'b-notrun'), textContent: RUN_WORD[st] || st });
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
    card.appendChild(el('h3', { textContent: 'Runs & documents' }));
    card.appendChild(el('p', { class: 'hint', textContent: 'Every writer and analysis run, with its model and each step. Read only: the record is stories/<slug>/RUNS.jsonl, and RUN_REPORT.md is written next to it.' }));
    if (State.registryError) {
      card.appendChild(notice('Run log not available: ' + State.registryError));
      return card;
    }
    if (!State.registry) {
      card.appendChild(el('p', { class: 'muted', textContent: 'Loading runs...' }));
      return card;
    }
    if (!State.registry.length) {
      card.appendChild(el('p', { class: 'muted', textContent: 'No stories yet. Save a story to start a run log.' }));
      return card;
    }
    card.appendChild(runsTable(['Story', 'Source', 'Model', 'Status', 'Last run', 'Packs', 'Runs'], State.registry.map(registryRow)));
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
      box.appendChild(el('p', { class: 'muted', textContent: 'Loading the run log of ' + slug + '...' }));
      return box;
    }
    if (d.error) {
      box.appendChild(notice('Could not read ' + slug + ': ' + d.error));
      return box;
    }
    box.appendChild(el('h4', { textContent: 'Runs of ' + slug }));
    if (!(d.runs || []).length) box.appendChild(el('p', { class: 'muted', textContent: 'No runs recorded yet.' }));
    else box.appendChild(runsTable(['Run', 'Status', 'Steps', 'Model', 'Pack', 'Started', 'Ended', 'Note'], d.runs.map(runRow)));
    box.appendChild(el('h4', { textContent: 'Steps' }));
    box.appendChild(runsTable(['Run', 'Step', 'Stage', 'Status', 'Via', 'Model', 'Effort', 'Pack', 'Time', 'Note'], (d.steps || []).map(stepRow)));
    box.appendChild(el('h4', { textContent: 'RUN_REPORT.md' }));
    box.appendChild(el('p', { children: [el('a', {
      href: '/api/file?path=' + enc('stories/' + slug + '/RUN_REPORT.md'),
      target: '_blank',
      rel: 'noopener',
      textContent: 'Open RUN_REPORT.md as text'
    })] }));
    box.appendChild(el('pre', { class: 'box', textContent: d.report || 'No report yet. It is written after the first run.' }));
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
      loadOps();
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
      if (!$('pipe-banner')) {
        var banner = el('div', { class: 'notice pipe-banner', id: 'pipe-banner', role: 'alert' });
        banner.hidden = true;
        wizard.parentNode.insertBefore(banner, wizard);
      }
    }

    showWizardNotice('Loading the wizard...');

    loadStoryList();
    loadPipeline().then(function () { return loadDetail(); });
    loadSummary();
    loadRegistry();
    loadStatus();
    loadOps();
    startPolling();
    document.addEventListener('visibilitychange', handleVisibility);
  }

  // ---------- Expose ----------
  window.StudioWizard = {
    refresh: function () { return refreshWizard(true); },
    project: function () { return projectOf(); }
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
