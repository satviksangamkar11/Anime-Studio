(function () {
  'use strict';

  var POLL_MS = 5000;
  var ERROR_MS = 8000;
  var MAX_STORY_BYTES = 204800;
  var SLUG_PAT = /^[a-z0-9_]{1,40}$/;
  var NOTE_MIN = 1;
  var NOTE_MAX = 300;

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

  var State = {
    pipeline: null,
    summary: null,
    packInfo: null,
    storyList: null,
    storyText: '',
    storySlug: '',
    packName: '',
    gateNotes: {},
    gateConfirm: {},
    lastJSON: '',
    busy: false,
    focusedInput: null,
    pollTimer: null,
    errorTimer: null,
    visible: !document.hidden,
    storySlugChanged: false,
    storyDirty: false,
    lastStorySlug: '',
    newSlug: '',
    overwrite: false,
    registry: null,
    registryError: '',
    registrySlug: '',
    registryDetail: null
  };

  // Runs & documents: status words and badge classes (style.css)
  var RUN_BADGE = { ok: 'b-ok', failed: 'b-failed', stopped: 'b-review', open: 'b-running', started: 'b-running' };
  var RUN_WORD = { ok: 'OK', failed: 'Failed', stopped: 'Stopped', open: 'Running', started: 'Running', 'no runs': 'No runs' };
  var WRITER_NAME = 'super-vl';   // the default writer for the Analysis step (server default too)

  // ---------- DOM helpers ----------
  function $(id) { return document.getElementById(id); }

  function el(tag, props) {
    var node = document.createElement(tag);
    var p = props || {};
    for (var k in p) {
      if (k === 'textContent') {
        node.textContent = p[k];
      } else if (k === 'children') {
        if (p[k]) {
          p[k].forEach(function (child) {
            if (child === null || child === undefined || child === false) return;
            if (Array.isArray(child)) child.forEach(function (c) { node.appendChild(c); });
            else if (child instanceof Node) node.appendChild(child);
            else node.appendChild(document.createTextNode(String(child)));
          });
        }
      } else if (k === 'class') {
        node.className = p[k];
      } else if (k === 'html') {
        // never
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

  function escapeText(s) {
    return String(s == null ? '' : s);
  }

  function countBytes(str) {
    return new TextEncoder().encode(str).length;
  }

  function stripNewlines(str) {
    return str.replace(/[\r\n]+/g, ' ');
  }

  // ---------- HTTP (returns promises) ----------
  function api(url, opts) {
    opts = opts || {};
    var headers = { 'Content-Type': 'application/json', 'X-UI': '1' };
    if (opts.headers) {
      for (var h in opts.headers) headers[h] = opts.headers[h];
    }
    return fetch(url, {
      method: opts.method || 'GET',
      headers: headers,
      body: opts.body ? JSON.stringify(opts.body) : undefined
    })
    .then(function (r) {
      return r.json().then(function (data) {
        return { ok: r.ok, status: r.status, data: data };
      });
    })
    .then(function (res) {
      if (!res.ok) {
        var e = new Error(res.data && res.data.error || ('HTTP ' + res.status));
        e.status = res.status;
        throw e;
      }
      return res.data;
    });
  }

  function get(url) { return api(url, {}); }
  function post(url, body) { return api(url, { method: 'POST', body: body }); }

  // ---------- Data loading ----------
  function loadPipeline() {
    return get('/api/pipeline')
      .then(function (data) {
        State.pipeline = data;
        var slug = data.project && data.project.story_slug;
        var pack = data.project && data.project.pack;
        if (slug) {
          State.storySlug = slug;
          State.packName = pack || '';
          return loadStory().then(function () {
            loadPackForCurrent();
          });
        } else {
          State.storySlug = '';
          // only forget the old story when it was the one loaded; never wipe typed text on each poll (M2)
          if (State.lastStorySlug !== '') {
            State.lastStorySlug = '';
            State.storyText = '';
            State.storyDirty = false;
            State.packName = '';
          }
          render();
        }
      })
      .catch(function (err) {
        var msg = err.message || String(err);
        if (!State.pipeline) showWizardNotice('Server not reachable, retrying every 5 s. (' + msg + ')');
        showError(msg);
      });
  }

  function loadStory() {
    if (!State.storySlug) {
      render();
      return Promise.resolve();
    }
    return fetch('/api/story/' + encodeURIComponent(State.storySlug), { headers: { 'X-UI': '1' } })
      .then(function (r) {
        if (r.status === 404) return null;
        return r.json();
      })
      .then(function (data) {
        if (State.storySlug !== State.lastStorySlug) {
          // the slug changed: load its text (empty when the story does not exist yet)
          State.lastStorySlug = State.storySlug;
          State.storyText = data ? (data.text || '') : '';
          State.storyDirty = false;
        }
        render();
      })
      .catch(function (err) { showError(err.message || String(err)); });
  }

  function loadSummary() {
    return get('/api/pipeline/summary')
      .then(function (data) {
        State.summary = data;
        if (State.pipeline) render();
      })
      .catch(function (err) { showError(err.message || String(err)); });
  }

  function loadPack(packPath) {
    if (!packPath) return Promise.resolve();
    return get('/api/pack?pack=' + encodeURIComponent(packPath))
      .then(function (data) {
        State.packInfo = data;
        if (State.pipeline) render();
      })
      .catch(function (err) {
        if (err.status === 404) {
          // "no such pack": analysis has not written it yet, which is normal before Gate A (M5)
          State.packInfo = null;
          if (State.pipeline) render();
          return;
        }
        showError(err.message || String(err));
      });
  }

  function loadPackForCurrent() {
    if (State.storySlug && State.packName) {
      var packPath = 'stories/' + State.storySlug + '/' + State.packName;
      return loadPack(packPath);
    }
    return Promise.resolve();
  }

  function loadStoryList() {
    return get('/api/story')
      .then(function (data) {
        State.storyList = data.slugs || [];
        if (State.pipeline) render();
      })
      .catch(function (err) { showError(err.message || String(err)); });
  }

  // Runs & documents: read-only view of GET /api/registry and /api/registry/<slug>
  function loadRegistry() {
    return get('/api/registry')
      .then(function (data) {
        State.registry = data.stories || [];
        State.registryError = '';
        if (State.pipeline) render();
      })
      .catch(function (err) {
        State.registry = null;
        State.registryError = err.message || String(err);
        if (State.pipeline) render();
      });
  }

  function loadRegistryDetail(slug) {
    if (!slug) {
      State.registryDetail = null;
      return Promise.resolve();
    }
    return get('/api/registry/' + encodeURIComponent(slug))
      .then(function (data) {
        State.registryDetail = data;
        if (State.pipeline) render();
      })
      .catch(function (err) {
        State.registryDetail = { slug: slug, error: err.message || String(err) };
        if (State.pipeline) render();
      });
  }

  // ---------- Render ----------
  function render() {
    if (!State.pipeline) return;
    var wizard = $('wizard');
    if (!wizard) return;

    // storyList is part of the key: when /api/story arrives after the first render the picker is redrawn (H2)
    var json = JSON.stringify({ pipeline: State.pipeline, summary: State.summary, packInfo: State.packInfo, storyList: State.storyList,
      registry: State.registry, registryError: State.registryError, registrySlug: State.registrySlug, registryDetail: State.registryDetail });
    if (json === State.lastJSON && State.lastJSON !== '') {
      restoreDrafts();
      return;
    }

    var activeEl = document.activeElement;
    var wizardHasFocus = activeEl && wizard.contains(activeEl);
    var saved = null;
    if (wizardHasFocus) {
      saved = saveFocusedInputs(wizard);
      // remember which control had the caret so the re-render can give it back (M4)
      saved.focusId = activeEl.id || '';
      saved.selStart = activeEl.selectionStart;
      saved.selEnd = activeEl.selectionEnd;
    }

    State.lastJSON = json;
    wizard.textContent = '';
    var stages = State.pipeline.stages || [];
    var current = State.pipeline.current;
    var project = State.pipeline.project || {};

    var pname = $('project-name');
    if (pname) pname.textContent = project.story_slug || '(no story)';

    updateStepper(stages, current);

    stages.forEach(function (stage) {
      var card = mkStageCard(stage, current, project);
      wizard.appendChild(card);
    });
    wizard.appendChild(registryPanel());

    restoreDrafts();
    if (saved) {
      restoreFocusedInputs(saved);
      restoreFocus(saved);
    }
  }

  function restoreFocus(saved) {
    if (!saved || !saved.focusId) return;
    var target = $(saved.focusId);
    if (!target || typeof target.focus !== 'function') return;
    target.focus({ preventScroll: true });
    if (typeof saved.selStart === 'number' && typeof target.setSelectionRange === 'function') {
      try { target.setSelectionRange(saved.selStart, saved.selEnd); } catch (e) { /* this control has no caret */ }
    }
  }

  function showWizardNotice(msg) {
    var wizard = $('wizard');
    if (!wizard) return;
    wizard.textContent = '';
    wizard.appendChild(el('div', { class: 'card notice', role: 'status', textContent: msg }));
  }

  function saveFocusedInputs(wizard) {
    var saved = {};
    var storyTa = $('wiz-story-text');
    if (storyTa && wizard.contains(storyTa)) {
      saved.storyText = storyTa.value;
    }
    var packInput = $('analysis-pack');
    if (packInput && wizard.contains(packInput)) {
      saved.packName = packInput.value;
    }
    var notes = wizard.querySelectorAll('textarea[id^="gate-note-"]');
    notes.forEach(function (ta) {
      var gateId = ta.id.replace('gate-note-', '');
      saved['note' + gateId] = ta.value;
    });
    var startInput = $('gate-confirm-C');
    if (startInput && wizard.contains(startInput)) {
      saved.startConfirm = startInput.value;
    }
    return saved;
  }

  function restoreFocusedInputs(saved) {
    if (!saved) return;
    var storyTa = $('wiz-story-text');
    if (storyTa && saved.storyText !== undefined) {
      storyTa.value = saved.storyText;
    }
    var packInput = $('analysis-pack');
    if (packInput && saved.packName !== undefined) {
      packInput.value = saved.packName;
    }
    var notes = document.querySelectorAll('textarea[id^="gate-note-"]');
    notes.forEach(function (ta) {
      var gateId = ta.id.replace('gate-note-', '');
      var key = 'note' + gateId;
      if (saved[key] !== undefined) {
        ta.value = saved[key];
        State.gateNotes[gateId] = saved[key];
      }
    });
    var startInput = $('gate-confirm-C');
    if (startInput && saved.startConfirm !== undefined) {
      startInput.value = saved.startConfirm;
      State.gateConfirm['C'] = saved.startConfirm;
    }
  }

  function restoreDrafts() {
    var notes = document.querySelectorAll('textarea[id^="gate-note-"]');
    notes.forEach(function (ta) {
      var gateId = ta.id.replace('gate-note-', '');
      if (State.gateNotes[gateId] !== undefined) {
        ta.value = State.gateNotes[gateId];
      }
    });
    var storyTa = $('wiz-story-text');
    if (storyTa && State.storyText !== undefined && !State.storyDirty) {
      storyTa.value = State.storyText;
    }
    var slugInput = $('wiz-story-slug');
    if (slugInput && State.storySlug !== undefined) {
      slugInput.value = State.storySlug;
    }
    var newSlugInput = $('wiz-story-new-slug');
    if (newSlugInput) {
      newSlugInput.value = State.newSlug || '';
    }
    var overwriteBox = $('wiz-story-overwrite');
    if (overwriteBox) {
      overwriteBox.checked = !!State.overwrite;
    }
    var packInput = $('analysis-pack');
    if (packInput && State.packName !== undefined) {
      packInput.value = State.packName;
    }
    var startInput = $('gate-confirm-C');
    if (startInput) {
      startInput.value = State.gateConfirm['C'] || '';
    }
  }

  function updateStepper(stages, current) {
    var stepper = $('stepper');
    if (!stepper) return;
    stages.forEach(function (stage) {
      var item = $('step-' + stage.id);
      if (!item) return;
      item.className = 'status-' + stage.status;
      var line = item.querySelector('.step-status');
      if (line) line.textContent = HUMAN_STATUS[stage.status] || stage.status;
    });
  }

  function mkStageCard(stage, current, project) {
    var card = el('div', { class: 'card stage-' + stage.id + (stage.id === current ? ' current' : '') });

    var header = el('div', { class: 'card-header' });
    header.appendChild(el('h3', { textContent: stage.title }));
    var chip = el('span', { class: 'chip status-' + stage.status, textContent: HUMAN_STATUS[stage.status] || stage.status });
    header.appendChild(chip);
    card.appendChild(header);

    var detail = el('p', { class: 'detail', textContent: stage.detail || '' });
    card.appendChild(detail);

    if (stage.progress && typeof stage.progress.total === 'number' && stage.progress.total > 0) {
      var pct = Math.min(100, Math.max(0, (stage.progress.done / stage.progress.total) * 100));
      var prog = el('div', { class: 'progress' });
      var bar = el('div', { class: 'bar', style: { width: pct + '%' } });
      prog.appendChild(bar);
      card.appendChild(prog);
      // the count sits outside the bar: dark text on white reads at any fill level (M7)
      card.appendChild(el('div', { class: 'progress-text', textContent: stage.progress.done + '/' + stage.progress.total }));
    }

    var actions = el('div', { class: 'actions' });
    var actionEls = stageActions(stage, project);
    if (actionEls) appendKids(actions, actionEls);
    card.appendChild(actions);
    if (stage.status === 'locked') {
      // a locked stage cannot act: disable its buttons instead of letting them answer with an error (L6)
      Array.prototype.forEach.call(actions.querySelectorAll('button'), function (b) { b.disabled = true; });
    }

    var gates = (State.pipeline && State.pipeline.gates) || [];
    gates.forEach(function (gate) {
      if (gate.stage === stage.id) {
        card.appendChild(mkGateCard(gate));
      }
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
      case 'export': return exportActions();
      default: return null;
    }
  }

  function storyActions(project) {
    var frag = document.createDocumentFragment();

    var slugLabel = el('label', { textContent: 'Story slug', for: 'wiz-story-slug' });
    frag.appendChild(slugLabel);

    var slugSelect = el('select', {
      id: 'wiz-story-slug',
      'aria-label': 'Story slug'
    });
    var optNone = el('option', { value: '', textContent: '-- new story --' });
    slugSelect.appendChild(optNone);
    (State.storyList || []).forEach(function (s) {
      var opt = el('option', {
        value: s.slug,
        textContent: s.slug + (s.packs && s.packs.length ? ' (' + s.packs.join(', ') + ')' : '') +
          (s.latest_model ? ' · ' + s.latest_model : '')
      });
      if (s.slug === project.story_slug) opt.selected = true;
      slugSelect.appendChild(opt);
    });
    slugSelect.addEventListener('change', function () {
      var slug = slugSelect.value;
      if (slug) {
        State.storySlugChanged = true;
        State.storyDirty = false;
        fetch('/api/story/' + encodeURIComponent(slug), { headers: { 'X-UI': '1' } })
          .then(function (r) { return r.ok ? r.json() : null; })
          .then(function (data) {
            if (data) {
              State.storySlug = slug;
              State.storyText = data.text || '';
              State.lastStorySlug = slug;
              var ta = $('wiz-story-text');
              if (ta) ta.value = State.storyText;
            }
          })
          .catch(function () {});
      } else {
        State.storySlug = '';
        State.storyText = '';
        State.lastStorySlug = '';
        var ta = $('wiz-story-text');
        if (ta) ta.value = '';
      }
    });
    frag.appendChild(slugSelect);

    var newSlugLabel = el('label', { textContent: 'New slug (if creating)', for: 'wiz-story-new-slug' });
    frag.appendChild(newSlugLabel);
    var newSlugInput = el('input', {
      type: 'text',
      id: 'wiz-story-new-slug',
      placeholder: 'new_slug',
      maxlength: 40,
      'aria-label': 'New slug'
    });
    newSlugInput.value = State.newSlug || '';
    newSlugInput.addEventListener('input', function () {
      State.newSlug = newSlugInput.value;
    });
    frag.appendChild(newSlugInput);

    var textLabel = el('label', { textContent: 'Story text (max ' + MAX_STORY_BYTES + ' bytes UTF-8)', for: 'wiz-story-text' });
    frag.appendChild(textLabel);
    var textarea = el('textarea', {
      id: 'wiz-story-text',
      rows: 10,
      'aria-label': 'Story text'
    });
    textarea.value = State.storyText || '';
    textarea.addEventListener('input', function () {
      State.storyText = textarea.value;
      State.storyDirty = true;
    });
    frag.appendChild(textarea);

    var overwriteBox = el('input', { type: 'checkbox', id: 'wiz-story-overwrite' });
    overwriteBox.checked = !!State.overwrite;
    overwriteBox.addEventListener('change', function () {
      State.overwrite = overwriteBox.checked;
    });
    var overwriteLabel = el('label', { class: 'inline', children: [
      overwriteBox,
      document.createTextNode(' overwrite if SOURCE.md exists')
    ]});
    frag.appendChild(overwriteLabel);

    var saveBtn = el('button', {
      type: 'button',
      textContent: 'Save story',
      onclick: function () {
        var slug = slugSelect.value.trim();
        if (slug === '-- new story --' || slug === '') {
          slug = newSlugInput.value.trim();
        }
        var text = textarea.value;
        var overwrite = $('wiz-story-overwrite') && $('wiz-story-overwrite').checked;
        if (!SLUG_PAT.test(slug)) { showError('Slug must match ' + SLUG_PAT.source); return; }
        if (countBytes(text) > MAX_STORY_BYTES) { showError('Story text too long (max ' + MAX_STORY_BYTES + ' bytes UTF-8)'); return; }
        State.busy = true;
        saveBtn.disabled = true;
        post('/api/story/' + encodeURIComponent(slug), { text: text, overwrite: overwrite })
          .then(function () {
            State.storySlug = slug;
            State.storyText = text;
            State.storyDirty = false;
            State.lastStorySlug = slug;
            State.storySlugChanged = false;
            State.newSlug = '';
            State.overwrite = false;
            showSuccess('Story saved');
            return post('/api/pipeline/project', { story_slug: slug, pack: State.packName || '' });
          })
          .then(function () {
            loadStoryList();
            loadPipeline();
          })
          .catch(function (err) { showError(err.message || String(err)); })
          .finally(function () {
            State.busy = false;
            saveBtn.disabled = false;
          });
      }
    });
    frag.appendChild(saveBtn);

    return [frag];
  }

  // the next free name pack_<writer>_<YYYYMMDD>_v<n> for a story (from the run log; '' when unknown)
  function suggestedPack(slug) {
    var row = (State.registry || []).filter(function (s) { return s.slug === slug; })[0];
    return row && row.next_pack ? row.next_pack : '';
  }

  function analysisActions(project) {
    var frag = document.createDocumentFragment();

    var packLabel = el('label', { textContent: 'Pack name', for: 'analysis-pack' });
    frag.appendChild(packLabel);
    var packInput = el('input', {
      type: 'text',
      id: 'analysis-pack',
      value: State.packName || project.pack || suggestedPack(project.story_slug),
      maxlength: 40,
      'aria-label': 'Pack name'
    });
    packInput.addEventListener('input', function () {
      State.packName = packInput.value.trim();
    });
    frag.appendChild(packInput);

    var runBtn = el('button', {
      type: 'button',
      textContent: 'Run story analysis',
      onclick: function () {
        var slug = project.story_slug;
        var pack = packInput.value.trim();
        var stage = getStage('analysis');
        if (!slug) { showError('Save the story first'); return; }
        if (!pack) { showError('Enter a pack name'); return; }
        if (stage && stage.status !== 'ready' && stage.status !== 'rejected') {
          showError('Analysis is not ready to run');
          return;
        }
        State.busy = true;
        runBtn.disabled = true;
        post('/api/pipeline/project', { story_slug: slug, pack: pack })
          .then(function () {
            loadPackForCurrent();
            return post('/api/preview', { command: 'write_pack', args: { slug: slug, pack: pack, writer: WRITER_NAME } });
          })
          .then(function (data) {
            var argv = data.argv || [];
            var argvText = (data.route ? data.route + '\n' : '') + argv.join(' ');
            confirmDialog('Run story analysis?', argvText, function () {
              var body = { token: data.token };
              post('/api/run', body)
                .then(function () {
                  loadPipeline();
                  loadSummary();
                })
                .catch(function (err) { showError(err.message || String(err)); });
            });
          })
          .catch(function (err) { showError(err.message || String(err)); })
          .finally(function () {
            State.busy = false;
            runBtn.disabled = false;
          });
      }
    });
    frag.appendChild(runBtn);

    if (State.packInfo) {
      var pack = State.packInfo;
      var gateACard = el('div', { class: 'gate-card' });
      var gateATitle = el('h4', { textContent: 'What you must approve' });
      gateACard.appendChild(gateATitle);

      if (pack.shots && pack.shots.length) {
        var tableWrap = el('div', { class: 'tablewrap' });
        var table = el('table');
        var thead = el('thead');
        thead.appendChild(el('tr', { children: [
          el('th', { textContent: 'Shot ID' }),
          el('th', { textContent: 'Episode' }),
          el('th', { textContent: 'Mode' }),
          el('th', { textContent: 'Seconds' }),
          el('th', { textContent: 'Purpose' })
        ]}));
        table.appendChild(thead);
        var tbody = el('tbody');
        pack.shots.forEach(function (s) {
          var purpose = (s.purpose || '').slice(0, 200);
          tbody.appendChild(el('tr', { children: [
            el('td', { textContent: s.id || '' }),
            el('td', { textContent: String(s.episode || '') }),
            el('td', { textContent: s.mode || '' }),
            el('td', { textContent: String(s.seconds || '') }),
            el('td', { textContent: purpose })
          ]}));
        });
        table.appendChild(tbody);
        tableWrap.appendChild(table);
        gateACard.appendChild(tableWrap);
      }

      if (pack.episodes && pack.episodes.length) {
        var epTableWrap = el('div', { class: 'tablewrap' });
        var epTable = el('table');
        var epThead = el('thead');
        epThead.appendChild(el('tr', { children: [
          el('th', { textContent: 'Episode' }),
          el('th', { textContent: 'Shots' }),
          el('th', { textContent: 'Seconds' })
        ]}));
        epTable.appendChild(epThead);
        var epTbody = el('tbody');
        pack.episodes.forEach(function (ep) {
          var epNum = ep.n !== undefined ? ep.n : ep.episode;
          epTbody.appendChild(el('tr', { children: [
            el('td', { textContent: String(epNum) }),
            el('td', { textContent: String(ep.shots) }),
            el('td', { textContent: String(ep.seconds) })
          ]}));
        });
        epTable.appendChild(epTbody);
        epTableWrap.appendChild(epTable);
        gateACard.appendChild(epTableWrap);
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
        var modes = Object.keys(pack.modes).map(function (k) { return k + ':' + pack.modes[k]; }).join(', ');
        namesDiv.appendChild(el('strong', { textContent: 'Modes: ' }));
        namesDiv.appendChild(document.createTextNode(modes));
      }
      gateACard.appendChild(namesDiv);

      if (pack.check) {
        var checkPre = el('pre', { class: 'box', textContent: JSON.stringify(pack.check, null, 2) });
        gateACard.appendChild(checkPre);
      }

      frag.appendChild(gateACard);
    }

    frag.appendChild(el('p', { class: 'hint', textContent: 'What happens next: after you approve Gate A, the image generation stage becomes available.' }));

    return [frag];
  }

  function imagesActions(project) {
    var frag = document.createDocumentFragment();

    var buildBtn = el('button', {
      type: 'button',
      id: 'images-build-jobs',
      textContent: 'Build image jobs',
      onclick: function () { buildImageJobs(project, buildBtn); }
    });
    var packPath = project.story_slug && project.pack ? 'stories/' + project.story_slug + '/' + project.pack : '';
    buildBtn.disabled = !(packPath && gateState('A') === 'approved' && State.packInfo && State.packInfo.pack === packPath);
    frag.appendChild(buildBtn);
    frag.appendChild(el('p', { class: 'hint', textContent: 'Writes the Flow spec and job file from the pack: no model call, no spend' }));

    var packetBtn = el('button', {
      type: 'button',
      textContent: 'Make Flow agent packet',
      onclick: function () {
        var pack = project.pack;
        if (!pack) { showError('Run analysis first'); return; }
        var slug = project.story_slug;
        if (!slug) { showError('Save the story first'); return; }
        State.busy = true;
        packetBtn.disabled = true;
        var jobs = [];
        var packPath = 'stories/' + slug + '/' + pack;
        get('/api/images')
          .then(function (data) {
            jobs = data.jobs || [];
            if (!jobs.length) {
              throw new Error('Image jobs are not built yet (press "Build image jobs" above first)');
            }
            return get('/api/pack?pack=' + encodeURIComponent(packPath));
          })
          .then(function (packData) {
            var shots = (packData.shots || []).map(function (s) { return s.id; });
            var jobsFile = findJobsFile(jobs, shots);
            if (!jobsFile) {
              throw new Error('No jobs file lists every shot of this pack yet');
            }
            return post('/api/packet', { jobs: jobsFile, shots: shots });
          })
          .then(function (data) {
            showPacketMarkdown(data.markdown || '');
          })
          .catch(function (err) { showError(err.message || String(err)); })
          .finally(function () {
            State.busy = false;
            packetBtn.disabled = false;
          });
      }
    });
    frag.appendChild(packetBtn);

    var note = el('p', { class: 'note', textContent: 'Flow agents run on Haiku, effort LOW; Claude starts them from the chat; this page shows their progress' });
    frag.appendChild(note);

    var hint = el('p', { class: 'hint', textContent: 'Full-size check by Claude, then you approve' });
    frag.appendChild(hint);

    if (State.summary && State.summary.images) {
      var imgs = State.summary.images;
      var counts = el('div', { class: 'counts', children: [
        el('span', { textContent: 'Finals: ' + imgs.final + '/' + imgs.expected }),
        el('span', { textContent: 'Pending: ' + imgs.pending }),
        el('span', { textContent: 'Reviewed: ' + imgs.reviewed })
      ]});
      frag.appendChild(counts);
    }

    return [frag];
  }

  // /api/images lists job rows {file, shot_id}. The packet needs one jobs file (path from the studio root)
  // that holds every shot id of the pack.
  function findJobsFile(jobs, shotIds) {
    var byFile = {};
    jobs.forEach(function (j) {
      if (!j || !j.file) return;
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
  var BUILD_ADHYAY = 1;
  var JOB_POLL_MS = 700;
  var JOB_POLL_MAX = 200;

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
    var packPath = 'stories/' + slug + '/' + pack;
    var genDir = 'flow/generated/' + slug + '/';
    var specPath = genDir + slug + '_image_spec.json';
    var seriesPath = genDir + slug + '_flow_series.json';
    var jobsName = slug + '_flow_jobs_adhyay' + ('0' + BUILD_ADHYAY).slice(-2) + '.json';
    State.busy = true;
    btn.disabled = true;
    // overwrite stays false: an existing spec or series (with the owner's accepted flags) is never replaced from the page
    post('/api/preview', { command: 'build_spec', args: { pack: packPath, adhyay: BUILD_ADHYAY, overwrite: false } })
      .then(function (data) {
        confirmDialog('Build the image spec, then the job file, for ' + packPath + '? Files go in ' + genDir + ' only.',
          (data.argv || []).join(' '), function () {
            runImageJobs(data.token);
          });
      })
      .catch(function (err) { showError(err.message || String(err)); })
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
        .catch(function (err) { showError(err.message || String(err)); })
        .finally(function () {
          State.busy = false;
          btn.disabled = false;
          loadPipeline();
          loadSummary();
        });
    }
  }

  function waitForJob(jid, left) {
    var tries = typeof left === 'number' ? left : JOB_POLL_MAX;
    return get('/api/jobs').then(function (list) {
      var job = null;
      (list || []).forEach(function (j) { if (j.id === jid) job = j; });
      if (!job) throw new Error('job ' + jid + ' is not listed');
      if (job.state !== 'running') return job;
      if (tries <= 0) throw new Error('still running after a long wait: see the job list');
      return new Promise(function (resolve) { setTimeout(resolve, JOB_POLL_MS); })
        .then(function () { return waitForJob(jid, tries - 1); });
    });
  }

  // the converter's own refusal ("REFUSED: ...") or the last line of its output goes into the error bar
  function failedJob(job, prefix) {
    return get('/api/jobs/' + encodeURIComponent(job.id) + '/result').then(function (res) {
      var lines = (res && res.lines) || [];
      var refused = lines.filter(function (l) { return l.indexOf('REFUSED') === 0 || l.indexOf('Refusing') === 0; });
      var detail = refused.length ? refused[refused.length - 1] : (lines.length ? lines[lines.length - 1] : 'no output (state ' + job.state + ')');
      throw new Error(prefix + ': ' + detail);
    });
  }

  function showPacketMarkdown(markdown) {
    var modal = $('modal');
    var title = $('modal-title');
    var body = $('modal-body');
    if (!modal || !title || !body) return;
    title.textContent = 'Flow agent packet';
    body.textContent = '';
    var pre = el('pre', { textContent: markdown });
    body.appendChild(pre);
    var copyBtn = el('button', {
      type: 'button',
      textContent: 'Copy',
      onclick: function () {
        if (navigator.clipboard) {
          navigator.clipboard.writeText(markdown).catch(function () {});
        }
      }
    });
    body.appendChild(copyBtn);
    var closeBtn = el('button', {
      type: 'button',
      textContent: 'Close',
      onclick: function () { closeModal(); }
    });
    body.appendChild(closeBtn);
    openModal();
  }

  function readoutActions() {
    var frag = document.createDocumentFragment();
    if (State.summary) {
      var summary = State.summary;

      var tiles = el('div', { class: 'stat-tiles' });
      var clipsPlanned = (summary.video && summary.video.shots && summary.video.takes) ? (summary.video.shots * summary.video.takes) : '-';
      var tileData = [
        { label: 'Reels', value: String(summary.reels) },
        { label: 'Shots', value: String(summary.shots) },
        { label: 'Seconds', value: String(summary.seconds) },
        { label: 'Characters', value: String((summary.characters || []).length) },
        { label: 'Places', value: String((summary.places || []).length) },
        { label: 'Images', value: summary.images ? (String(summary.images.final) + '/' + String(summary.images.expected)) : '-' },
        { label: 'Clips planned', value: String(clipsPlanned) },
        { label: 'Est. G4 units', value: summary.estimate ? String(summary.estimate.g4_units) : '-' },
        { label: 'Est. minutes', value: summary.estimate ? String(summary.estimate.minutes) : '-' }
      ];
      tileData.forEach(function (t) {
        var tile = el('div', { class: 'tile', children: [
          el('div', { class: 'tile-value', textContent: t.value }),
          el('div', { class: 'tile-label', textContent: t.label })
        ]});
        tiles.appendChild(tile);
      });
      frag.appendChild(tiles);

      if (summary.episodes && summary.episodes.length) {
        var epTableWrap = el('div', { class: 'tablewrap' });
        var epTable = el('table');
        var epThead = el('thead');
        epThead.appendChild(el('tr', { children: [
          el('th', { textContent: 'Episode' }),
          el('th', { textContent: 'Shots' }),
          el('th', { textContent: 'Seconds' })
        ]}));
        epTable.appendChild(epThead);
        var epTbody = el('tbody');
        summary.episodes.forEach(function (ep) {
          var epNum = ep.n !== undefined ? ep.n : ep.episode;
          epTbody.appendChild(el('tr', { children: [
            el('td', { textContent: String(epNum) }),
            el('td', { textContent: String(ep.shots) }),
            el('td', { textContent: String(ep.seconds) })
          ]}));
        });
        epTable.appendChild(epTbody);
        epTableWrap.appendChild(epTable);
        frag.appendChild(epTableWrap);
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
        var modes = Object.keys(summary.modes).map(function (k) { return k + ':' + summary.modes[k]; }).join(', ');
        namesDiv.appendChild(el('strong', { textContent: 'Modes: ' }));
        namesDiv.appendChild(document.createTextNode(modes));
      }
      frag.appendChild(namesDiv);

      if (summary.video) {
        var v = summary.video;
        var vDiv = el('div');
        vDiv.appendChild(el('strong', { textContent: 'Takes: ' }));
        vDiv.appendChild(document.createTextNode(String(v.takes || 0)));
        vDiv.appendChild(el('br'));
        vDiv.appendChild(el('strong', { textContent: 'Clips home: ' }));
        vDiv.appendChild(document.createTextNode(String(v.clips_home || 0)));
        frag.appendChild(vDiv);
      }

      if (summary.images) {
        var imgs = summary.images;
        var iDiv = el('div');
        iDiv.appendChild(el('strong', { textContent: 'Finals: ' }));
        iDiv.appendChild(document.createTextNode(String(imgs.final)));
        iDiv.appendChild(el('br'));
        iDiv.appendChild(el('strong', { textContent: 'Pending: ' }));
        iDiv.appendChild(document.createTextNode(String(imgs.pending)));
        iDiv.appendChild(el('br'));
        iDiv.appendChild(el('strong', { textContent: 'Reviewed: ' }));
        iDiv.appendChild(document.createTextNode(String(imgs.reviewed)));
        frag.appendChild(iDiv);
      }

      var checks = el('div', { class: 'checks' });
      (summary.checks || []).forEach(function (c) {
        var mark = c.ok ? 'OK' : 'FAIL';
        var checkEl = el('div', { class: 'check ' + (c.ok ? 'ok' : 'fail'), children: [
          el('span', { class: 'mark', textContent: mark }),
          el('span', { class: 'check-name', textContent: c.name }),
          el('span', { class: 'check-detail', textContent: c.detail })
        ]});
        checks.appendChild(checkEl);
      });
      frag.appendChild(checks);

      var warnings = el('div', { class: 'warnings' });
      (summary.warnings || []).forEach(function (w) {
        warnings.appendChild(el('p', { class: 'warning', textContent: w }));
      });
      frag.appendChild(warnings);
    } else {
      frag.appendChild(el('p', { textContent: 'No summary available' }));
    }
    return [frag];
  }

  function renderActions(project) {
    var frag = document.createDocumentFragment();

    var prepareBtn = el('button', {
      type: 'button',
      textContent: 'Prepare render (no GPU)',
      onclick: function () {
        var slug = project.story_slug;
        var pack = project.pack;
        if (!slug) { showError('Save the story first'); return; }
        if (!pack) { showError('Run analysis first'); return; }
        var stage = getStage('render');
        if (stage && stage.status !== 'ready' && stage.status !== 'rejected') {
          showError('Render is not ready to run');
          return;
        }
        var shotsFile = 'stories/' + slug + '/' + pack + '/shots.json';
        State.busy = true;
        prepareBtn.disabled = true;
        // scope "all" takes no ids; an empty ids string is rejected by the server (H5)
        post('/api/preview', { command: 'h3_prepare', args: { story: shotsFile, scope: 'all' } })
          .then(function (data) {
            var argv = data.argv || [];
            var argvText = argv.join(' ');
            confirmDialog('Prepare render?', argvText, function () {
              var body = { token: data.token };
              post('/api/run', body)
                .then(function () { loadPipeline(); })
                .catch(function (err) { showError(err.message || String(err)); });
            });
          })
          .catch(function (err) { showError(err.message || String(err)); })
          .finally(function () {
            State.busy = false;
            prepareBtn.disabled = false;
          });
      }
    });
    frag.appendChild(prepareBtn);

    if (State.summary && State.summary.video) {
      var v = State.summary.video;
      var clipsPlanned = (v.shots && v.takes) ? (v.shots * v.takes) : '-';
      var info = el('p', { class: 'hint', textContent: 'Clips home: ' + (v.clips_home || 0) + ', planned: ' + clipsPlanned });
      frag.appendChild(info);
    }

    var hint = el('p', { class: 'hint', textContent: 'Colab run: use Advanced tools > Video (spend gate)' });
    frag.appendChild(hint);

    return [frag];
  }

  function exportActions() {
    var frag = document.createDocumentFragment();
    var p = el('p', { textContent: 'Export stage: assembly plan and final reel files. Use the advanced tools for export.' });
    frag.appendChild(p);
    return [frag];
  }

  function getStage(id) {
    if (!State.pipeline || !State.pipeline.stages) return null;
    for (var i = 0; i < State.pipeline.stages.length; i++) {
      if (State.pipeline.stages[i].id === id) return State.pipeline.stages[i];
    }
    return null;
  }

  // ---------- Gates ----------
  function mkGateCard(gate) {
    var card = el('div', { class: 'gate card gate-' + gate.id + ' ' + gate.state });

    var header = el('div', { class: 'gate-header', children: [
      el('h4', { textContent: gate.title }),
      el('span', { class: 'chip status-' + gate.state, textContent: HUMAN_GATE[gate.state] || gate.state })
    ]});
    card.appendChild(header);

    if (gate.state === 'locked') {
      card.appendChild(el('p', { class: 'lock-note', textContent: 'waiting for the previous step' }));
      return card;
    }

    if (gate.state === 'approved' || gate.state === 'rejected') {
      var decideAgain = gate.state === 'rejected';
      var info = el('div', { class: 'gate-info', children: [
        el('p', { children: [el('strong', { textContent: 'By: ' }), document.createTextNode(gate.by || '-')] }),
        el('p', { children: [el('strong', { textContent: 'When: ' }), document.createTextNode(gate.at || '-')] }),
        el('p', { children: [el('strong', { textContent: 'Note: ' }), document.createTextNode(gate.note || '-')] })
      ]});
      card.appendChild(info);
      if (!decideAgain) return card;
    }

    var noteLabel = el('label', { textContent: 'Note (optional for approve, required for reject, max ' + NOTE_MAX + ' chars)', for: 'gate-note-' + gate.id });
    card.appendChild(noteLabel);
    var noteInput = el('textarea', {
      id: 'gate-note-' + gate.id,
      rows: 3,
      maxlength: NOTE_MAX,
      'aria-label': 'Gate note'
    });
    noteInput.value = State.gateNotes[gate.id] || '';
    noteInput.addEventListener('input', function () {
      State.gateNotes[gate.id] = noteInput.value;
    });
    card.appendChild(noteInput);

    var startInput = null;
    if (gate.id === 'C') {
      var startLabel = el('label', { textContent: 'Type START to confirm', for: 'gate-confirm-' + gate.id });
      card.appendChild(startLabel);
      startInput = el('input', {
        type: 'text',
        id: 'gate-confirm-' + gate.id,
        'aria-label': 'START confirmation'
      });
      startInput.value = State.gateConfirm[gate.id] || '';
      card.appendChild(startInput);
      startInput.addEventListener('input', function () {
        State.gateConfirm[gate.id] = startInput.value;
      });
    }

    var btns = el('div', { class: 'gate-btns' });

    var approveBtn = el('button', {
      type: 'button',
      textContent: 'Approve',
      onclick: function () {
        var note = stripNewlines(noteInput.value.trim());
        if (gate.id === 'C') {
          var confirm = startInput ? startInput.value : '';
          if (confirm !== 'START') { showError('Type START exactly'); return; }
          onGateDecision(gate.id, 'approve', note, confirm);
        } else {
          onGateDecision(gate.id, 'approve', note);
        }
      }
    });
    // a property, never an attribute: Gate C stays off until START is typed (H1)
    approveBtn.disabled = (gate.id === 'C') ? (startInput ? startInput.value !== 'START' : true) : false;
    btns.appendChild(approveBtn);

    if (startInput) {
      startInput.addEventListener('input', function () {
        approveBtn.disabled = (startInput.value !== 'START');
      });
    }

    var rejectBtn = el('button', {
      type: 'button',
      textContent: 'Reject',
      onclick: function () {
        var note = stripNewlines(noteInput.value.trim());
        if (note.length < NOTE_MIN || note.length > NOTE_MAX) { showError('Note must be ' + NOTE_MIN + '-' + NOTE_MAX + ' characters'); return; }
        onGateDecision(gate.id, 'reject', note);
      }
    });
    btns.appendChild(rejectBtn);

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

  function onGateDecision(gateId, decision, note, confirm) {
    if (State.busy) { showError('Busy, try again'); return; }
    State.busy = true;
    var body = { gate: gateId, decision: decision, note: note };
    if (confirm) body.confirm = confirm;
    post('/api/pipeline/gate', body)
      .then(function () {
        showSuccess('Gate ' + gateId + ' ' + (decision === 'approve' ? 'approved' : 'rejected'));
        // the note and the START box belong to this decision only: the next one starts empty (L5)
        delete State.gateNotes[gateId];
        delete State.gateConfirm[gateId];
        var noteBox = $('gate-note-' + gateId);
        if (noteBox) noteBox.value = '';
        var startBox = $('gate-confirm-' + gateId);
        if (startBox) startBox.value = '';
        loadPipeline();
      })
      .catch(function (err) { showError(err.message || String(err)); })
      .finally(function () {
        State.busy = false;
      });
  }

  // ---------- Modal (overlay) ----------
  var lastFocused = null;

  function openModal() {
    var modal = $('modal');
    if (!modal) return;
    lastFocused = document.activeElement;
    modal.hidden = false;
    modal.focus();
    var focusable = modal.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
    if (focusable.length) focusable[0].focus();
    if (!modal._escapeListener) {
      modal._escapeListener = function (e) {
        if (e.key === 'Escape') closeModal();
      };
      modal.addEventListener('keydown', modal._escapeListener);
    }
    if (!modal._trapListener) {
      modal._trapListener = function (e) {
        if (e.key === 'Tab') {
          var focusable = modal.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
          var first = focusable[0];
          var last = focusable[focusable.length - 1];
          if (e.shiftKey && document.activeElement === first) {
            e.preventDefault();
            last.focus();
          } else if (!e.shiftKey && document.activeElement === last) {
            e.preventDefault();
            first.focus();
          }
        }
      };
      modal.addEventListener('keydown', modal._trapListener);
    }
  }

  function closeModal() {
    var modal = $('modal');
    if (!modal) return;
    modal.hidden = true;
    if (modal._escapeListener) {
      modal.removeEventListener('keydown', modal._escapeListener);
      modal._escapeListener = null;
    }
    if (modal._trapListener) {
      modal.removeEventListener('keydown', modal._trapListener);
      modal._trapListener = null;
    }
    if (lastFocused && typeof lastFocused.focus === 'function') {
      lastFocused.focus();
    } else {
      var wizard = $('wizard');
      if (wizard) wizard.focus();
    }
  }

  function confirmDialog(message, argvText, onConfirm) {
    var modal = $('modal');
    var title = $('modal-title');
    var body = $('modal-body');
    if (!modal || !title || !body) return;
    title.textContent = 'Confirm command';
    body.textContent = '';
    var msg = el('p', { textContent: message });
    body.appendChild(msg);
    if (argvText) {
      var argvPre = el('pre', { textContent: argvText });
      body.appendChild(argvPre);
    }
    var btns = el('div', { class: 'modal-btns' });
    var okBtn = el('button', {
      type: 'button',
      textContent: 'Run',
      onclick: function () {
        closeModal();
        onConfirm && onConfirm();
      }
    });
    btns.appendChild(okBtn);
    var cancelBtn = el('button', {
      type: 'button',
      textContent: 'Cancel',
      onclick: function () { closeModal(); }
    });
    btns.appendChild(cancelBtn);
    body.appendChild(btns);
    openModal();
  }

  // ---------- Error bar & Success toast ----------
  function showError(msg) {
    var bar = $('error-bar');
    var text = $('error-text');
    if (!bar || !text) return;
    text.textContent = msg;
    bar.hidden = false;
    bar.classList.remove('success');
    if (State.errorTimer) clearTimeout(State.errorTimer);
    State.errorTimer = setTimeout(function () {
      bar.hidden = true;
    }, ERROR_MS);
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
  function dash(v) {
    return v === null || v === undefined || v === '' ? '-' : String(v);
  }

  function listText(v) {
    return v && v.length ? v.join(', ') : '-';
  }

  function shortTime(iso) {
    return iso ? String(iso).replace('T', ' ').slice(0, 16) : '-';
  }

  function runBadge(status) {
    var st = status || 'no runs';
    return el('span', { class: 'badge ' + (RUN_BADGE[st] || 'b-notrun'), textContent: RUN_WORD[st] || st });
  }

  function runsTable(headers, rows) {
    var head = el('tr', { children: headers.map(function (h) { return el('th', { scope: 'col', textContent: h }); }) });
    var table = el('table', { children: [el('thead', { children: [head] }), el('tbody', { children: rows })] });
    return el('div', { class: 'tablewrap', children: [table] });
  }

  function registryPanel() {
    var card = el('div', { class: 'card runs-panel', id: 'runs-panel' });
    card.appendChild(el('h3', { textContent: 'Runs & documents' }));
    card.appendChild(el('p', { class: 'hint', textContent: 'Every writer and analysis run, with its model and each step. Read only: the record is stories/<slug>/RUNS.jsonl, and RUN_REPORT.md is written next to it.' }));
    if (State.registryError) {
      card.appendChild(el('div', { class: 'notice', role: 'status', textContent: 'Run log not available: ' + State.registryError }));
      return card;
    }
    if (!State.registry) {
      card.appendChild(el('p', { class: 'muted', textContent: 'Loading runs...' }));
      return card;
    }
    if (!State.registry.length) {
      card.appendChild(el('p', { class: 'muted', textContent: 'No stories yet.' }));
      return card;
    }
    var rows = State.registry.map(registryRow);
    card.appendChild(runsTable(['Story', 'Source', 'Model', 'Status', 'Last run', 'Packs', 'Runs'], rows));
    if (State.registrySlug) card.appendChild(registryDetail(State.registrySlug));
    return card;
  }

  function registryRow(s) {
    var selected = s.slug === State.registrySlug;
    var pick = function () {
      State.registrySlug = selected ? '' : (s.slug || '');   // a click on the open story closes it
      State.registryDetail = null;
      render();
      loadRegistryDetail(State.registrySlug);
    };
    var status = s.error ? 'failed' : (s.status || 'no runs');
    var story = el('td', { children: [
      el('strong', { textContent: dash(s.slug) }), el('br'),
      el('span', { class: 'muted', textContent: s.error ? s.error : dash(s.title) })
    ] });
    return el('tr', {
      class: 'clickable' + (selected ? ' selected' : ''),
      tabindex: '0',
      onclick: pick,
      onkeydown: function (e) {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          pick();
        }
      },
      children: [
        story,
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
      box.appendChild(el('div', { class: 'notice', role: 'status', textContent: 'Could not read ' + slug + ': ' + d.error }));
      return box;
    }
    box.appendChild(el('h4', { textContent: 'Runs of ' + slug }));
    if (!(d.runs || []).length) box.appendChild(el('p', { class: 'muted', textContent: 'No runs recorded yet.' }));
    else box.appendChild(runsTable(['Run', 'Status', 'Steps', 'Model', 'Pack', 'Started', 'Ended', 'Note'], d.runs.map(runRow)));
    box.appendChild(el('h4', { textContent: 'Steps' }));
    box.appendChild(runsTable(['Run', 'Step', 'Stage', 'Status', 'Via', 'Model', 'Effort', 'Pack', 'Time', 'Note'], (d.steps || []).map(stepRow)));
    box.appendChild(el('h4', { textContent: 'RUN_REPORT.md' }));
    box.appendChild(el('pre', { class: 'box', textContent: d.report || 'No report yet.' }));
    return box;
  }

  // ---------- Polling ----------
  function startPolling() {
    if (State.pollTimer) return;
    State.pollTimer = setInterval(function () {
      loadPipeline();
      loadSummary();
      loadRegistry();
      loadRegistryDetail(State.registrySlug);
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
      loadPipeline();
      loadSummary();
      loadRegistry();
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
      var bar = $('error-bar');
      if (bar) bar.hidden = true;
    });

    // shown until the first /api/pipeline answer; a failed load replaces it with the reason (L7)
    showWizardNotice('Loading the wizard...');

    loadStoryList();
    loadPipeline();
    loadSummary();
    loadRegistry();
    startPolling();
    document.addEventListener('visibilitychange', handleVisibility);
  }

  // ---------- Expose ----------
  window.StudioWizard = {
    refresh: loadPipeline
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
