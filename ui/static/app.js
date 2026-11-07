/*
 * Anime Studio control UI (frontend). Plain JS, ES2018, no framework, no network except same-origin /api*.
 * Server text only goes in through textContent and createElement; no HTML string is ever parsed.
 *
 * Backend contract: the shapes this page reads, as served by ui/server.py. A missing key shows as "-"; it never throws.
 *   GET  /api/status           {studio_ok, flow_ok, python, colab_cli, nvidia_key_files (count), spend_allowed,
 *                               spend_cap_units, h3_built, job: null | {id, command, state, rc, started, ended, spend, warning}}
 *   GET  /api/jobs             [job summary, newest first]
 *   GET  /api/jobs/{id}/log?tail=N           text, redacted
 *   GET  /api/jobs/{id}/result bridge_*: {records, counts}; queue_collect: {lines}; review_shot: {verdict, exit}; other: {lines}
 *   POST /api/jobs/{id}/stop   {} -> {state, warning}
 *   GET  /api/story            {slugs: [{slug, packs: [name], has_source, output_languages}]}
 *   GET  /api/story/{slug}     {text, bytes}; 404 = no SOURCE.md yet
 *   POST /api/story/{slug}     {text, overwrite} -> {saved, bytes}; 409 = SOURCE.md exists
 *   GET  /api/writers          {default, options: [{id, command, args, available, reason, ...}]}
 *   GET  /api/pack?pack=stories/<slug>/<name>[&check=1]
 *                              {stages: {"1": bool, ...}, gate1, episodes: [{n, shots, seconds, check}],
 *                               characters: [{id, name}], places: [{id, name}],
 *                               shots: [{id, episode, mode, seconds, cut_in, cut_out, issues: count}], check}
 *   GET  /api/images?adhyay=N[&story=slug]  {series: {characters, places, props: [{id, name, chip, sheet, accepted}]},
 *                               sheets: [{id, sheet, accepted}], jobs: [{file, shot_id, scene, chips, attempts, attempt_cap, status}],
 *                               shots: [{id, candidates: [{name, path}], reviews}], progress: {lines: [...], total, legacy},
 *                               queue: {pending: [...], counts: {pending, filed, accepted}}, filed: [...], accepted: [...],
 *                               finals: [{name, path, bytes}]}
 *   GET  /api/review?shot=&cand=&adhyay=N   cand = picture FILE NAME; {verdict, fix, regen_sentence, edit_instruction,
 *                                           answers: {Q1..Q6}}; 404 = no review yet
 *   POST /api/packet           {jobs: "flow/<file>.json", shots: [id]} -> {path, markdown}
 *   GET  /api/video            {shot_files: [relative path], batches: [{name, run_py_bytes, settings, embed_mb}],
 *                               clips: [{shot, take, file, bytes, seconds, qa: bool}]}
 *   GET  /api/h3               {built, message, command, module}
 *   GET  /api/colab            {sessions: [{name, gpu, status}] | null, balance: number | null,
 *                               read_ok: {sessions, usage}, rate_units_per_hour: {G4, A100}, cap_units}
 *   GET  /api/export?reel=N    {clips_in_order: [{shot, take, file, ...}], assembly: "not built", assembly_note, reel_files: [name]}
 *   GET  /api/file?path=       bytes (png, jpg, mp4, ...)
 *   POST /api/preview          {command, args} -> {argv, risk, estimate, balance, token, expires_s, needs_confirm,
 *                               confirm_text, spend_allowed}
 *   POST /api/run              {token, confirm?} -> {job_id}
 * Command ids and args (server COMMANDS table; unknown args are refused):
 *   write_pack {slug, pack, out_lang, writer | model}      bridge_dry / bridge_write {size, adhyay}
 *   neighbour_sheet / review_shot {jobs, shot, candidates: [paths], adhyay}
 *   queue_add {shot, version, edit, jobs, note, adhyay}     queue_accept {shot, version, note, adhyay}
 *   queue_collect {adhyay}                   tidy_plan {adhyay}
 *   clip_qa {clip, out_dir}                  visual_qa {clip, direction, out_dir, model}
 *   run_kaggle_prepare {shots, scope, ids | reel, keyframes?, batch}
 *   colab_run {batch, gpu, session}          colab_stop {session}
 *   h3_prepare {story, scope, ids | reel}
 * Relative paths (for example "flow/A_KM_flow_jobs_x.json") are resolved by the server against the studio folder.
 */
(function () {
  'use strict';

  // The string lookup (ui/static/i18n.js). Every visible text goes through the translation helper with a literal key (test_i18n 2b).
  var t = function (k, v) { return window.I18N.t(k, v); };

  var POLL_MS = 2500;
  var PACK_STAGES = ['1', '2', '3e1', '3e2', '3e3', '3e4', '3e5', '5'];
  var WRITER_NAMES = ['super-vl', 'ultra'];   // write_pack --writer shortcuts: both are free OpenRouter models; super-vl is the default
  var DEFAULT_WRITER = 'or-super-vl';         // the chooser default (GET /api/writers says the same)
  var VISION_MODELS = ['nvidia/nemotron-3-nano-omni-30b-a3b-reasoning', 'nvidia/nemotron-3.5-super-vl-120b-a12b'];
  var GPUS = ['G4', 'A100'];
  var SECTIONS = ['story', 'images', 'bridge', 'video', 'export'];
  var IMG_TABS = ['series', 'jobs', 'shots', 'progress', 'queue', 'finals'];
  var MAX_STORY_BYTES = 200 * 1024;
  var JOBS_DIR = 'flow/';
  var FINISHED_TEXT = 'the job had already finished';
  var PAT = {
    slug: /^[a-z0-9_]{1,40}$/,
    name: /^[a-z0-9_-]{1,40}$/,
    shot: /^[A-Z0-9][A-Z0-9_-]{0,39}$/,
    version: /^v\d{2}b?$/,
    edit: /^[0-9a-f-]{36}$/,
    session: /^[A-Za-z0-9_-]{1,40}$/,
    note: /^[^\r\n\u0000-\u001f\u007f]{1,200}$/,
    count: /^\d{1,3}$/,
    json: /^[^\r\n\u0000-\u001f"]{1,260}\.json$/i
  };

  var S = {
    status: null,
    jobBusy: false,
    lastJobId: null,
    logDone: null,
    trackers: [],
    ticking: false,
    section: '',
    slugs: [],
    story: { slug: '' },
    images: null,
    imgTab: 'series',
    imgAt: 0,
    reviewGen: 0,
    colabOk: false,
    colabBalance: null,
    colabData: null,
    h3Ok: false,
    h3Msg: '',
    writerOpts: []
  };
  var modalTimer = null;
  var msgTimer = null;

  // ---------- DOM helpers (textContent and createElement only) ----------
  function $(id) { return document.getElementById(id); }

  function appendKids(node, kids) {
    kids.forEach(function (k) {
      if (k === null || k === undefined || k === false) return;
      if (Array.isArray(k)) appendKids(node, k);
      else if (k instanceof Node) node.appendChild(k);
      else node.appendChild(document.createTextNode(String(k)));
    });
  }

  function el(tag, props) {
    var node = document.createElement(tag);
    var p = props || {};
    Object.keys(p).forEach(function (k) {
      var v = p[k];
      if (v === undefined || v === null || v === false) return;
      if (k === 'text') node.textContent = String(v);
      else if (k === 'className') node.className = String(v);
      else if (k === 'onclick') node.addEventListener('click', v);
      else if (k === 'checked') node.checked = true;
      else if (k === 'value') node.value = String(v);
      else node.setAttribute(k, v === true ? '' : String(v));
    });
    appendKids(node, Array.prototype.slice.call(arguments, 2));
    return node;
  }

  function btn(text, props) {
    var p = props || {};
    p.type = 'button';
    p.text = text;
    return el('button', p);
  }

  // A row-level button that is not available for a data reason. applyGates() keeps it disabled with this reason.
  function offProps(off, why) {
    return off ? { 'data-off': '1', 'data-off-why': why } : {};
  }

  function clear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
    return node;
  }

  function fill(node, kids) {
    clear(node);
    appendKids(node, kids);
    return node;
  }

  function fillTable(id, headers, rows) {
    var tbl = clear($(id));
    tbl.appendChild(el('thead', null, el('tr', null, headers.map(function (h) { return el('th', { text: h }); }))));
    var tb = el('tbody');
    if (!rows.length) {
      tb.appendChild(el('tr', null, el('td', { colspan: headers.length, className: 'muted', text: t('adv.table.none') })));
    }
    rows.forEach(function (r) {
      var cells = Array.isArray(r) ? r : r.cells;
      var tr = el('tr', { className: Array.isArray(r) ? null : r.className });
      cells.forEach(function (c) { tr.appendChild(el('td', null, c)); });
      tb.appendChild(tr);
    });
    tbl.appendChild(tb);
    return tbl;
  }

  function or(v, d) { return (v === undefined || v === null || v === '') ? d : v; }
  function enc(s) { return encodeURIComponent(String(s)); }
  function errText(e) { return (e && e.message) ? e.message : String(e); }
  function yn(v) { return v ? t('adv.head.ok') : t('adv.head.missing'); }
  function baseName(p) { return String(or(p, '-')).split(/[\\/]/).pop() || '-'; }

  function riskText(c) {
    if (c === 'R') return t('risk.r');
    if (c === 'W') return t('risk.w');
    if (c === 'N') return t('risk.n');
    if (c === '$') return t('risk.usd');
    if (c === 'OPS') return t('risk.ops');
    if (c === 'X') return t('risk.x');
    return c;
  }

  function risk(codes) {
    return String(codes).split(' ').filter(Boolean).map(function (c) {
      return el('span', { className: 'risk risk-' + (c === '$' ? 'usd' : c), text: c, title: riskText(c) });
    });
  }

  function kindOf(v) {
    if (v === true) return 'ok';
    if (v === false || v === null || v === undefined) return 'notrun';
    var s = String(v).toLowerCase();
    if (/^(ok|pass|accepted|filed|done|final|yes)$/.test(s)) return 'ok';
    if (/^(block|blocked|fail|failed|error|refused|stopped)$/.test(s)) return 'failed';
    if (/^(unsure|review|warn)$/.test(s) || /^issues\b/.test(s)) return 'review';
    if (/^(running|generating|started)$/.test(s)) return 'running';
    return 'notrun';
  }

  // Badge words for the five kinds (a literal switch, so every key stays visible to the tests).
  function kindText(kind) {
    if (kind === 'ok') return t('adv.kind.ok');
    if (kind === 'review') return t('adv.kind.review');
    if (kind === 'failed') return t('adv.kind.failed');
    if (kind === 'running') return t('adv.kind.running');
    return t('adv.kind.notrun');
  }

  function badge(kind, text) {
    return el('span', { className: 'badge b-' + kind, text: text || kindText(kind) });
  }

  // A value from the server shown as its upper-case word; an empty value shows the NOT RUN badge.
  function badgeFor(v) {
    if (v === undefined || v === null || v === '') return badge('notrun');
    return badge(kindOf(v), String(v).toUpperCase());
  }

  function yesNo(v) { return v ? badge('ok', t('adv.kind.yes')) : badge('notrun', t('adv.kind.no')); }

  // Errors stay until closed. msg: a plain string, or {text, raw} (raw = the server's English words, for the helper).
  function showError(msg) {
    var m = (msg !== null && typeof msg === 'object') ? msg : { text: String(msg), raw: '' };
    $('error-text').textContent = String(m.text);
    var raw = $('error-raw');
    raw.textContent = String(m.raw || '');
    raw.hidden = !m.raw;
    $('error-bar').hidden = false;
  }

  function showMsg(msg) {
    var b = $('msg-bar');
    b.textContent = String(msg);
    b.hidden = false;
    clearTimeout(msgTimer);
    msgTimer = setTimeout(function () { b.hidden = true; }, 9000);
  }

  function showInline(node, msg) {
    node.textContent = String(msg);
    node.hidden = false;
  }

  // The plain sentence for an error. The server's English words are matched by I18N.serverError (the raw part stays English).
  function apiText(e) {
    if (e && e.status === 0) return e.timeout ? t('err.net.timeout') : t('err.net.down');
    return window.I18N.serverError(errText(e)).text;
  }

  function showApiError(e) {
    if (e && e.status === 0) return showError({ text: apiText(e), raw: errText(e) });
    return showError(window.I18N.serverError(errText(e)));
  }

  function fmtBytes(n) {
    if (typeof n !== 'number') return '-';
    if (n >= 1048576) return (n / 1048576).toFixed(1) + ' MB';
    if (n >= 1024) return Math.round(n / 1024) + ' KB';
    return n + ' B';
  }

  function names(list) {
    return (list || []).map(function (x) {
      var s = typeof x === 'string' ? x : ((x && (x.name || x.id)) || '?');
      return el('li', { text: s });
    });
  }

  function adhyayNow() {
    var n = Number($('img-adhyay').value);
    return (n >= 1 && n <= 12) ? n : 1;
  }

  // The story the wizard (step 1 to 6, top of the page) works on. '' when none is chosen yet.
  function projectStory() {
    var pj = (window.StudioWizard && window.StudioWizard.project && window.StudioWizard.project()) || {};
    return pj.story_slug || '';
  }

  // ---------- API (the only fetch) ----------
  function fail(status, message) {
    var e = new Error(message);
    e.status = status;
    return e;
  }

  async function api(method, path, body) {
    var opts = { method: method, headers: {}, cache: 'no-store' };
    opts.headers['X-UI'] = '1';   // every request, as the guard hint promises (server checks POST only today)
    if (method !== 'GET') {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body || {});
    }
    var res;
    var text;
    // a hung server must not hang the modals and the poller forever: give up after 2 minutes (same as pipeline.js).
    // The timer covers the body read too, so a stalled body cannot leave tick() waiting forever.
    var ctl = typeof AbortController === 'function' ? new AbortController() : null;
    var timer = ctl ? setTimeout(function () { ctl.abort(); }, 120000) : null;
    if (ctl) opts.signal = ctl.signal;
    try {
      res = await fetch(path, opts);
      text = await res.text();
    } catch (e) {
      var nf = fail(0, method + ' ' + path + ' (no answer from the server)');
      nf.timeout = !!(e && e.name === 'AbortError');
      throw nf;
    } finally {
      if (timer) clearTimeout(timer);
    }
    var isJson = /json/.test(res.headers.get('Content-Type') || '');
    var data = text;
    if (isJson) {
      try { data = JSON.parse(text); } catch (e) { data = text; }
    }
    if (!res.ok) {
      var msg = (isJson && data && data.error) ? String(data.error) : (text.slice(0, 300) || res.statusText);
      // only host, origin and X-UI refusals get the hint; other 403s (expired preview, etc.) show the server's words
      if (res.status === 403 && /Host|Origin|X-UI/.test(msg)) msg = msg + ' ' + t('adv.guard.hint', { host: location.host });
      throw fail(res.status, msg);
    }
    return data;
  }

  // ---------- Header, job tracking, log bar ----------
  function isRunning(j) { return !!j && String(j.state || '').toLowerCase() === 'running'; }

  function jobOk(j) {
    var rc = (j.rc === null || j.rc === undefined || j.rc === '') ? NaN : Number(j.rc);
    if (j.command === 'review_shot') return rc === 0 || rc === 1 || rc === 3; // 0 PASS, 1 BLOCK, 3 UNSURE
    return rc === 0;
  }

  function setServerState(text) { $('server-state').textContent = text; }

  function renderHeader() {
    var st = S.status || {};
    var sb = $('spend-badge');
    sb.textContent = st.spend_allowed ? t('adv.head.spend_on') : t('app.spend_off');
    sb.className = 'badge ' + (st.spend_allowed ? 'b-review' : 'b-grey');
    var job = st.job || null;
    S.jobBusy = isRunning(job);
    if (job && job.id) S.lastJobId = job.id;
    var text = (job && job.id) ? t('adv.head.job_running', { command: job.command || 'job', id: job.id }) : t('app.job_none');
    fill($('job-badge'), [text, ' ', S.jobBusy ? badge('running') : null]);
    if (S.status) {
      $('story-status').textContent = t('adv.head.conn', {
        studio: yn(st.studio_ok), flow: yn(st.flow_ok), colab: yn(st.colab_cli), keys: or(st.nvidia_key_files, '?')
      });
    }
  }

  // Gates: data-gate tokens (spend, colab, h3, job, busy, never) and data-off set a reason; no reason = enabled.
  function applyGates() {
    var st = S.status || {};
    Array.prototype.forEach.call(document.querySelectorAll('[data-gate],[data-off]'), function (n) {
      var g = (n.getAttribute('data-gate') || '').split(' ');
      var why = n.hasAttribute('data-off') ? (n.getAttribute('data-off-why') || t('adv.gate.not_here')) : '';
      if (!why && g.indexOf('never') >= 0) why = n.getAttribute('data-why') || t('adv.gate.not_yet');
      if (!why && g.indexOf('spend') >= 0 && !st.spend_allowed) why = t('adv.gate.spend_off');
      if (!why && g.indexOf('colab') >= 0 && !S.colabOk) why = t('adv.gate.colab_first');
      if (!why && g.indexOf('h3') >= 0 && !S.h3Ok) why = S.h3Msg || t('err.srv.h3_missing');
      if (!why && g.indexOf('job') >= 0 && S.jobBusy) why = t('adv.gate.job_running');
      if (!why && g.indexOf('busy') >= 0 && !S.jobBusy) why = t('adv.gate.no_job');
      n.disabled = !!why;
      n.title = why || n.getAttribute('data-title') || '';
    });
  }

  async function tick() {
    if (S.ticking) return;
    S.ticking = true;
    try {
      try {
        S.status = await api('GET', '/api/status');
        setServerState('');
      } catch (e) {
        S.status = null;
        setServerState(t('adv.head.server_down'));
      }
      renderHeader();
      try { await pollJobs(); } catch (e) { /* retried on the next tick */ }
      try { await refreshLog(); } catch (e) { /* retried on the next tick */ }
      if (S.section === 'images' && (S.imgTab === 'progress' || S.imgTab === 'queue') && Date.now() - S.imgAt > 10000) {
        loadImages(true);
      }
      applyGates();
    } finally {
      S.ticking = false;
    }
  }

  async function pollJobs() {
    if (!S.trackers.length) return;
    var jobs = await api('GET', '/api/jobs');
    if (!Array.isArray(jobs)) jobs = [];
    var still = [];
    S.trackers.forEach(function (tr) {
      var j = jobs.filter(function (x) { return x.id === tr.id; })[0];
      if (!j || isRunning(j)) { still.push(tr); return; }
      if (!jobOk(j)) {
        showError(t('adv.job.ended_rc', {
          command: tr.command,
          rc: (j.rc === null || j.rc === undefined) ? '?' : j.rc
        }));
      }
      Promise.resolve().then(function () { return tr.onEnd ? tr.onEnd(j) : null; })
        .catch(function (e) { showApiError(e); });
    });
    S.trackers = still;
  }

  async function refreshLog() {
    var id = (S.status && S.status.job && S.status.job.id) || S.lastJobId;
    if (!id) return;
    if (!S.jobBusy && S.logDone === id) return;
    var txt = await api('GET', '/api/jobs/' + enc(id) + '/log?tail=12');
    var lines = String(txt || '').split('\n');
    $('log-tail').textContent = lines.slice(-12).join('\n') || t('adv.log.no_output');
    $('log-job').textContent = t('adv.log.job_line', { id: id, state: S.jobBusy ? t('adv.log.running') : t('adv.log.finished') });
    if (!S.jobBusy) S.logDone = id;
    if (S.section === 'video') {
      var live = await api('GET', '/api/jobs/' + enc(id) + '/log?tail=200');
      $('video-live').textContent = String(live || '') || t('adv.log.no_output');
    }
  }

  function onStarted(cfg, id) {
    if (!id) return showMsg(t('adv.msg.started', { command: cfg.command }));
    S.lastJobId = id;
    S.logDone = null;
    S.jobBusy = true;
    showMsg(t('adv.msg.job_started', { id: id, command: cfg.command }));
    S.trackers.push({ id: id, command: cfg.command, onEnd: cfg.onEnd });
    applyGates();
    tick();
  }

  async function stopJob() {
    var id = (S.status && S.status.job && S.status.job.id) || S.lastJobId;
    if (!id) return showMsg(t('adv.msg.no_job'));
    try {
      var r = await api('POST', '/api/jobs/' + enc(id) + '/stop', {});
      var warn = r && r.warning ? String(r.warning) : '';
      if (warn === FINISHED_TEXT) {
        showMsg(t('adv.msg.already_done', { id: id }));
      } else if (warn) {
        showError(t('adv.msg.may_run', { warn: warn }));
        loadColab(true);
      } else {
        showMsg(t('adv.msg.stop_sent', { id: id }));
      }
    } catch (e) { showApiError(e); }
  }

  // ---------- Modal: command preview, spend gate, packet text ----------
  function openModal(title) {
    clearInterval(modalTimer);
    $('modal-title').textContent = title;
    clear($('modal-body'));
    $('modal').hidden = false;
  }

  function closeModal() {
    clearInterval(modalTimer);
    $('modal').hidden = true;
    clear($('modal-body'));
  }

  // Two steps for every command: Preview (POST /api/preview) shows the exact argv, then Start (POST /api/run).
  // cfg: {title, command, risk, note, fields?, check?, args (object or fn(values)), summary?(values, pv), onEnd?(job)}
  function runCommand(cfg) {
    openModal(cfg.title);
    var body = $('modal-body');
    var errBox = el('div', { className: 'inline-err', hidden: true });
    var fieldNodes = {};
    var form = el('div', { className: 'form' });
    var check = null;
    body.appendChild(el('p', { className: 'risklinehead' }, risk(cfg.risk), el('code', { text: cfg.command })));
    if (cfg.note) body.appendChild(el('p', { className: 'muted', text: cfg.note }));
    (cfg.fields || []).forEach(function (f) {
      var input;
      if (f.options) {
        input = el('select', { id: 'modal-f-' + f.name });
        f.options.forEach(function (o) { input.appendChild(el('option', { value: o, text: o })); });
        input.value = f.value || f.options[0];
      } else {
        input = el('input', { id: 'modal-f-' + f.name, type: 'text', maxlength: 260, autocomplete: 'off',
          placeholder: f.placeholder || '', value: f.value || '' });
      }
      fieldNodes[f.name] = { input: input, spec: f };
      form.appendChild(el('label', { className: 'field' }, el('span', { text: f.label }), input,
        f.hint ? el('small', { className: 'muted', text: f.hint }) : null));
    });
    if (cfg.check) {
      check = el('input', { type: 'checkbox', id: 'modal-check' });
      form.appendChild(el('label', { className: 'inline' }, check, el('span', { text: cfg.check })));
    }
    body.appendChild(form);
    body.appendChild(errBox);
    var stage = el('div', { id: 'modal-stage' });
    body.appendChild(stage);
    var previewBtn = btn(t('adv.modal.preview_btn'), { id: 'modal-preview', className: 'primary' });
    body.appendChild(el('div', { className: 'btnrow' }, previewBtn, btn(t('adv.modal.cancel_btn'), { id: 'modal-cancel', onclick: closeModal })));

    function doPreview() {
      errBox.hidden = true;
      var values = {};
      var problem = '';
      Object.keys(fieldNodes).forEach(function (k) {
        var f = fieldNodes[k].spec;
        var v = String(fieldNodes[k].input.value || '').trim();
        values[k] = v;
        if (f.required && !v) problem = problem || t('adv.form.required', { label: f.label });
        else if (v && f.pattern && !f.pattern.test(v)) {
          problem = problem || t('adv.form.wrong_format', { label: f.label, hint: f.hint || t('adv.form.wrong') });
        }
      });
      if (!problem && check && !check.checked) problem = t('adv.form.tick_first', { check: cfg.check });
      if (problem) return showInline(errBox, problem);
      var args = typeof cfg.args === 'function' ? cfg.args(values) : (cfg.args || {});
      previewBtn.disabled = true;
      api('POST', '/api/preview', { command: cfg.command, args: args }).then(function (pv) {
        previewBtn.hidden = true;
        showStage(pv, values);
      }).catch(function (e) {
        showInline(errBox, apiText(e));
        previewBtn.disabled = false;
      });
    }

    function showStage(pv, values) {
      clear(stage);
      var argv = Array.isArray(pv.argv) ? pv.argv : [String(or(pv.argv, ''))];
      stage.appendChild(el('h3', { text: t('adv.modal.argv_h') }));
      stage.appendChild(el('pre', { id: 'modal-argv', className: 'argv', text: argv.join('\n') }));
      if (cfg.summary) {
        cfg.summary(values, pv).forEach(function (line) {
          stage.appendChild(el('p', { className: 'summary-line', text: line }));
        });
      }
      if (pv.estimate !== undefined && pv.estimate !== null) {
        stage.appendChild(el('p', { text: t('adv.modal.estimate', { n: pv.estimate }) }));
      }
      if (pv.balance !== undefined && pv.balance !== null) {
        stage.appendChild(el('p', { text: t('adv.modal.balance', { n: String(pv.balance) }) }));
      }
      var expiry = el('p', { id: 'modal-expiry', className: 'muted' });
      stage.appendChild(expiry);
      var needsTyped = !!pv.needs_confirm || cfg.risk.indexOf('$') >= 0;
      var want = needsTyped ? (pv.confirm_text || ('EXECUTE ' + pv.estimate)) : '';
      var typed = null;
      if (needsTyped) {
        typed = el('input', { id: 'modal-confirm-input', type: 'text', autocomplete: 'off', placeholder: want });
        stage.appendChild(el('label', { className: 'field' }, el('span', { text: t('adv.modal.type_to_start', { word: want }) }), typed));
      }
      var startBtn = btn(t('adv.modal.start_btn'), { id: 'modal-start', className: needsTyped ? 'danger' : 'primary' });
      stage.appendChild(el('div', { className: 'btnrow' }, startBtn));

      var left = Number(pv.expires_s) || 60;
      function showLeft() {
        if (left > 0) {
          expiry.textContent = t('adv.modal.expires', { s: left });
        } else {
          expiry.textContent = t('adv.modal.expired');
          startBtn.disabled = true;
        }
      }
      showLeft();
      clearInterval(modalTimer);
      modalTimer = setInterval(function () {
        left -= 1;
        showLeft();
        if (left <= 0) clearInterval(modalTimer);
      }, 1000);

      startBtn.addEventListener('click', function () {
        errBox.hidden = true;
        var body2 = { token: pv.token };
        if (typed) {
          var typedVal = typed.value.trim();
          if (typedVal !== want) return showInline(errBox, t('err.srv.type_exactly', { word: want }));
          body2.confirm = typedVal;
        }
        startBtn.disabled = true;
        api('POST', '/api/run', body2).then(function (r) {
          closeModal();
          onStarted(cfg, r && r.job_id);
        }).catch(function (e) {
          showInline(errBox, apiText(e));
          startBtn.disabled = left <= 0;
        });
      });
    }

    previewBtn.addEventListener('click', doPreview);
    if (!(cfg.fields && cfg.fields.length) && !cfg.check) doPreview();
  }

  function copyText(text, b) {
    function done(ok) { b.textContent = ok ? t('adv.copy.done') : t('adv.copy.failed'); }
    function fallback() {
      var ta = el('textarea', { text: text });
      document.body.appendChild(ta);
      ta.select();
      var ok = false;
      try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
      document.body.removeChild(ta);
      done(ok);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () { done(true); }, fallback);
    } else {
      fallback();
    }
  }

  // ---------- Section switching ----------
  function showSection(name) {
    if (SECTIONS.indexOf(name) < 0) name = 'story';
    S.section = name;
    SECTIONS.forEach(function (s) {
      $('sec-' + s).hidden = s !== name;
      var b = $('nav-' + s);
      if (s === name) b.setAttribute('aria-current', 'page');
      else b.removeAttribute('aria-current');
    });
    if (location.hash !== '#' + name) history.replaceState(null, '', '#' + name);
    if (name === 'story') loadStory();
    if (name === 'images') loadImages();
    if (name === 'video') loadVideo();
    if (name === 'export') loadExport();
    applyGates();
  }

  // ---------- Story ----------
  // The story picker and the wizard show one story: the wizard's story wins when it is in the list.
  async function loadStory(pack) {
    try {
      var d = await api('GET', '/api/story');
      S.slugs = Array.isArray(d && d.slugs) ? d.slugs : [];
      if (!S.slugs.length) {
        fill($('story-slug'), [el('option', { value: '', text: t('adv.story.no_stories') })]);
        renderPack(null);
        return;
      }
      var proj = projectStory();
      var keep = inSlugs(proj) ? proj : (inSlugs(S.story.slug) ? S.story.slug : S.slugs[0].slug);
      fill($('story-slug'), S.slugs.map(function (s) { return el('option', { value: s.slug, text: s.slug }); }));
      $('story-slug').value = keep;
      selectSlug(keep, pack);
    } catch (e) { showApiError(e); }
  }

  function inSlugs(slug) {
    return !!slug && S.slugs.some(function (s) { return s.slug === slug; });
  }

  function setStoryHeading(slug) {
    var h = $('sec-story') ? $('sec-story').querySelector('h2') : null;
    if (h) h.textContent = slug ? t('adv.story.following', { slug: slug }) : t('adv.story.title');
  }

  function selectSlug(slug, pack) {
    var changed = slug !== S.story.slug;
    S.story.slug = slug;
    var entry = S.slugs.filter(function (s) { return s.slug === slug; })[0] || { packs: [] };
    var packs = entry.packs || [];
    fill($('story-pack'), packs.length
      ? packs.map(function (p) { return el('option', { value: p, text: p }); })
      : [el('option', { value: '', text: t('adv.story.no_packs') })]);
    if (pack && packs.indexOf(pack) >= 0) $('story-pack').value = pack;
    setStoryHeading(slug);
    if (changed) loadStoryText();
    loadPack(false);
  }

  async function loadStoryText() {
    if (!S.story.slug) return;
    try {
      var d = await api('GET', '/api/story/' + enc(S.story.slug));
      $('story-text').value = d.text || '';
      $('story-bytes').textContent = t('adv.story.bytes', { n: d.bytes || 0 });
    } catch (e) {
      if (e.status === 404) {
        $('story-text').value = '';
        $('story-bytes').textContent = t('adv.story.no_source');
      } else {
        showApiError(e);
      }
    }
  }

  async function saveStory() {
    if (!S.story.slug) return showError(t('adv.story.err_pick_slug'));
    var text = $('story-text').value;
    var bytes = new TextEncoder().encode(text).length;
    if (bytes > MAX_STORY_BYTES) return showError(t('adv.story.too_big', { n: bytes }));
    try {
      var d = await api('POST', '/api/story/' + enc(S.story.slug), { text: text, overwrite: $('story-overwrite').checked });
      $('story-bytes').textContent = t('adv.story.bytes', { n: or(d.bytes, bytes) });
      showMsg(t('adv.story.saved', { n: or(d.bytes, bytes) }));
    } catch (e) { showApiError(e); }
  }

  // check = true asks the server to run check_pack (GET /api/pack?check=1). Returns true when the pack loaded.
  async function loadPack(check) {
    var pack = $('story-pack').value;
    if (!S.story.slug || !pack) { renderPack(null); return false; }
    var url = '/api/pack?pack=' + enc('stories/' + S.story.slug + '/' + pack) + (check ? '&check=1' : '');
    try {
      renderPack(await api('GET', url));
      return true;
    } catch (e) {
      renderPack(null);
      showApiError(e);
      return false;
    }
  }

  async function checkPack() {
    var b = $('story-check');
    b.disabled = true;
    try {
      if (await loadPack(true)) showMsg(t('adv.msg.pack_checked'));
    } finally {
      b.disabled = false;
    }
  }

  function renderPack(p) {
    p = p || {};
    var st = p.stages || {};
    fill($('story-stages'), PACK_STAGES.map(function (k) {
      var ok = st[k] === true;
      return el('span', { className: 'stagebadge' }, t('adv.story.stage', { n: k }), badge(ok ? 'ok' : 'notrun'));
    }));
    $('story-gate1').textContent = p.gate1 || t('adv.story.no_gate1');
    fillTable('story-episodes', [t('adv.th.no'), t('adv.th.scenes'), t('adv.th.seconds'), t('adv.th.check')], (p.episodes || []).map(function (e) {
      return [String(or(e.n, '-')), String(or(e.shots, '-')), String(or(e.seconds, '-')), e.check ? badgeFor(e.check) : '-'];
    }));
    fill($('story-characters'), names(p.characters));
    fill($('story-places'), names(p.places));
    fillTable('story-shots', [t('adv.th.shot'), t('adv.th.part'), t('adv.th.mode'), t('adv.th.sec'), t('adv.th.cut'), t('adv.th.issues')], (p.shots || []).map(function (s) {
      var n = Array.isArray(s.issues) ? s.issues.length : or(s.issues, 0);
      return [String(or(s.id, '?')), String(or(s.episode, '-')), String(or(s.mode, '-')), String(or(s.seconds, '-')),
        String(or(s.cut_in, '-')) + ' -> ' + String(or(s.cut_out, '-')), String(n)];
    }));
    $('story-check-json').textContent = p.check ? JSON.stringify(p.check, null, 2) : t('adv.story.no_check');
  }

  // Writer choices for the Story section: the free options only. When /api/writers fails, the two writer shortcuts.
  function modelLabel(id) {
    if (id === 'nv-ultra') return t('adv.story.model.nv_ultra');
    if (id === 'nv-super-vl') return t('adv.story.model.nv_super_vl');
    if (id === 'or-ultra') return t('adv.story.model.or_ultra');
    return t('adv.story.model.or_super_vl');
  }

  async function loadWriterChoices() {
    var sel = $('story-model');
    var dflt = DEFAULT_WRITER;
    var opts = [];
    try {
      var w = await api('GET', '/api/writers');
      if (w && w.default) dflt = String(w.default);
      opts = (Array.isArray(w && w.options) ? w.options : [])
        .filter(function (o) { return o.command === 'write_pack'; })
        .map(function (o) { return { id: String(o.id), args: o.args || {}, available: o.available !== false }; });
    } catch (e) {
      opts = [];
    }
    if (!opts.length) {
      opts = WRITER_NAMES.map(function (n) { return { id: 'or-' + n, args: { writer: n }, available: true }; });
    }
    S.writerOpts = opts;
    var keep = sel.value;
    fill(sel, opts.map(function (o) {
      return el('option', { value: o.id, text: modelLabel(o.id), disabled: !o.available });
    }));
    var usable = function (id) { return opts.some(function (o) { return o.id === id && o.available; }); };
    sel.value = usable(keep) ? keep : (usable(dflt) ? dflt : opts[0].id);
  }

  function writerChoice() {
    var id = $('story-model') ? $('story-model').value : '';
    var hit = S.writerOpts.filter(function (o) { return o.id === id; })[0];
    return hit || { id: DEFAULT_WRITER, args: { writer: WRITER_NAMES[0] } };
  }

  function storyLangs(slug) {
    var entry = S.slugs.filter(function (s) { return s.slug === slug; })[0] || {};
    return Array.isArray(entry.output_languages) ? entry.output_languages.filter(Boolean) : [];
  }

  // write_pack needs the story's saved output languages (out_lang); without them the page stops here and calls nothing.
  function writerRun(kind) {
    var slug = S.story.slug;
    if (!slug) return showError(t('adv.story.err_pick_slug'));
    var pack = kind === 'new' ? $('story-newpack').value.trim() : $('story-pack').value;
    if (kind === 'new' && !PAT.name.test(pack)) return showError(t('adv.story.new_pack_bad'));
    if (kind !== 'new' && !pack) return showError(t('adv.story.pick_resume'));
    var langs = storyLangs(slug);
    if (!langs.length) return showError(t('adv.story.no_langs'));
    var choice = writerChoice();
    runCommand({
      title: kind === 'new' ? t('adv.story.run_new_btn') : t('adv.story.resume_btn'),
      command: 'write_pack',
      risk: 'N W',
      note: t('adv.story.write_note'),
      args: Object.assign({ slug: slug, pack: pack, out_lang: langs.join(',') }, choice.args),
      onEnd: function () { return loadStory(pack); }
    });
  }

  // ---------- Images ----------
  function setImagesHeading(st) {
    var h = $('sec-images') ? $('sec-images').querySelector('h2') : null;
    if (h) h.textContent = st ? t('adv.images.for_story', { slug: st }) : t('adv.images.title');
  }

  async function loadImages(quiet) {
    try {
      var st = projectStory();
      var url = '/api/images?adhyay=' + enc(adhyayNow()) + (st ? '&story=' + enc(st) : '');
      S.images = await api('GET', url);
      S.imgAt = Date.now();
      setImagesHeading(st);
      renderImgTab(S.imgTab);
    } catch (e) {
      if (!quiet) showApiError(e);
    }
  }

  function renderImgTab(tab) {
    S.imgTab = tab;
    IMG_TABS.forEach(function (x) {
      $('img-' + x).hidden = x !== tab;
      var b = $('tab-' + x);
      b.classList.toggle('active', x === tab);
      b.setAttribute('aria-selected', x === tab ? 'true' : 'false');
    });
    var d = S.images || {};
    if (tab === 'series') renderSeries(d);
    if (tab === 'jobs') renderJobs(d);
    if (tab === 'shots') renderShots(d);
    if (tab === 'progress') renderProgress(d);
    if (tab === 'queue') renderQueue(d);
    if (tab === 'finals') renderFinals(d);
    applyGates();
  }

  function grpText(g) {
    if (g === 'characters') return t('adv.images.grp_characters');
    if (g === 'places') return t('adv.images.grp_places');
    if (g === 'props') return t('adv.images.grp_props');
    if (g === 'sheet') return t('adv.images.grp_sheet');
    return g;
  }

  function renderSeries(d) {
    var rows = [];
    var series = d.series || {};
    ['characters', 'places', 'props'].forEach(function (grp) {
      (Array.isArray(series[grp]) ? series[grp] : []).forEach(function (x) {
        rows.push([grpText(grp), String(or(x.id, '?')), String(or(x.name, '-')), String(or(x.chip, '-')), baseName(x.sheet), yesNo(x.accepted)]);
      });
    });
    (d.sheets || []).forEach(function (x) {
      rows.push([t('adv.images.grp_sheet'), String(or(x.id, '?')), '-', '-', baseName(x.sheet), yesNo(x.accepted)]);
    });
    fillTable('series-table', [t('adv.th.group'), t('adv.th.id'), t('adv.th.name'), t('adv.th.chip'), t('adv.th.sheet_file'), t('adv.th.accepted')], rows);
  }

  function renderJobs(d) {
    fillTable('jobs-table', [t('adv.th.shot'), t('adv.th.scene'), t('adv.th.chips'), t('adv.th.attempts'), t('adv.th.status'), t('adv.th.actions')], (d.jobs || []).map(function (j) {
      var chips = Array.isArray(j.chips) ? j.chips.join(', ') : String(or(j.chips, '-'));
      var packet = btn(t('adv.images.packet_btn'), Object.assign({ className: 'act act-packet', onclick: function () { openPacket(j); } },
        offProps(!j.file, t('adv.images.no_jobs_file'))));
      var build = btn(t('adv.images.build_off'), {
        className: 'act act-build',
        'data-gate': 'never',
        'data-why': t('adv.images.build_why'),
        'data-title': t('adv.images.build_title')
      });
      return [String(or(j.shot_id, '?')), String(or(j.scene, '-')), chips,
        String(or(j.attempts, 0)) + ' / ' + String(or(j.attempt_cap, '?')), badgeFor(j.status), [packet, build]];
    }));
  }

  async function openPacket(j) {
    if (!j.file) return showError(t('adv.images.no_jobs_file'));
    try {
      var r = await api('POST', '/api/packet', { jobs: JOBS_DIR + j.file, shots: [j.shot_id] });
      showPacket(String(or(j.shot_id, '?')), r || {});
    } catch (e) { showApiError(e); }
  }

  function showPacket(shot, r) {
    openModal(t('adv.packet.title', { shot: shot }));
    var body = $('modal-body');
    var pre = el('pre', { id: 'packet-md', className: 'box', text: String(or(r.markdown, t('adv.packet.no_md'))) });
    body.appendChild(el('div', { className: 'banner-info', text: t('adv.packet.rule_haiku') }));
    body.appendChild(el('p', { className: 'muted', text: t('adv.packet.rule_scene') }));
    body.appendChild(el('p', { className: 'muted', text: t('adv.packet.saved_at', { path: String(or(r.path, t('adv.packet.no_path'))) }) }));
    body.appendChild(btn(t('adv.packet.copy_btn'), { id: 'packet-copy', className: 'primary', onclick: function (ev) { copyText(pre.textContent, ev.currentTarget); } }));
    body.appendChild(pre);
    body.appendChild(el('div', { className: 'btnrow' }, btn(t('common.close'), { onclick: closeModal })));
  }

  // Candidates of a shot as {name, path}. name goes to /api/review; path goes to the commands.
  function candList(s) {
    return (s.candidates || []).map(function (c) {
      if (typeof c === 'string') return { name: baseName(c), path: c };
      return { name: String(or(c.name, '')), path: String(or(c.path, '')) };
    }).filter(function (c) { return c.name && c.path; });
  }

  // Jobs file (relative to the studio folder) that holds this shot's job entry, or '' when none is listed.
  function jobsFor(shotId) {
    var hit = ((S.images && S.images.jobs) || []).filter(function (j) { return j && j.shot_id === shotId && j.file; })[0];
    return hit ? JOBS_DIR + hit.file : '';
  }

  function renderShots(d) {
    var tbl = clear($('shots-table'));
    var gen = ++S.reviewGen;
    var pairs = [];
    $('review-detail').hidden = true;
    var heads = [t('adv.th.shot'), t('adv.th.candidate')];
    for (var q = 1; q <= 6; q += 1) heads.push(t('adv.th.q', { n: q }));
    heads.push(t('adv.th.verdict'), t('adv.th.actions'));
    tbl.appendChild(el('thead', null, el('tr', null, heads.map(function (h) { return el('th', { text: h }); }))));
    (d.shots || []).forEach(function (s) {
      var shotId = String(or(s.id, ''));
      var cands = candList(s);
      var jobs = jobsFor(shotId);
      var why = cands.length ? t('adv.shots.no_job') : t('adv.shots.no_cands');
      var off = !cands.length || !jobs;
      var tb = el('tbody', { className: 'shotgroup' });
      tb.appendChild(el('tr', { className: 'shotrow' },
        el('th', { text: t('adv.shots.group', { shot: shotId, n: cands.length }), scope: 'rowgroup' }),
        el('td', { colspan: 9 },
          btn(t('adv.shots.neighbours'), Object.assign({ className: 'act act-neighbours', 'data-gate': 'job',
            onclick: function () { neighbourSheet(shotId, cands, jobs); } }, offProps(off, why))),
          btn(t('adv.shots.reviewer'), Object.assign({ className: 'act act-reviewer', 'data-gate': 'job',
            onclick: function () { reviewShot(shotId, cands, jobs); } }, offProps(off, why))))));
      if (!cands.length) {
        tb.appendChild(el('tr', null, el('td', { colspan: 10, className: 'muted', text: t('adv.shots.no_cand_files') })));
      }
      cands.forEach(function (c) {
        var qCells = [1, 2, 3, 4, 5, 6].map(function () { return el('td', { className: 'q', text: '...' }); });
        var verdict = el('td', null, badge('notrun', '...'));
        pairs.push({ shot: shotId, cand: c.name, q: qCells, verdict: verdict });
        tb.appendChild(el('tr', null,
          el('td', { text: '' }),
          el('td', { text: c.name }),
          qCells,
          verdict,
          el('td', null,
            btn(t('adv.shots.queue_kept'), Object.assign({ className: 'act act-queue-kept', 'data-gate': 'job',
              onclick: function () { queueKept(shotId, c, jobs); } }, offProps(off, why))),
            btn(t('adv.shots.accept'), Object.assign({ className: 'act act-accept', 'data-gate': 'job',
              onclick: function () { acceptCand(shotId, c); } }, offProps(off, why))))));
      });
      tbl.appendChild(tb);
    });
    loadReviews(pairs, gen);
    applyGates();
  }

  function loadReviews(pairs, gen) {
    var next = 0;
    var ay = adhyayNow();
    function worker() {
      if (next >= pairs.length) return Promise.resolve();
      var p = pairs[next];
      next += 1;
      return api('GET', '/api/review?shot=' + enc(p.shot) + '&cand=' + enc(p.cand) + '&adhyay=' + enc(ay)).then(function (r) {
        if (gen === S.reviewGen) fillReview(p, r, null);
      }, function (e) {
        if (gen !== S.reviewGen) return;
        if (e.status === 404) fillReview(p, null, null);
        else fillReview(p, null, errText(e));
      }).then(worker);
    }
    var pool = [];
    for (var i = 0; i < 3; i += 1) pool.push(worker());
    return Promise.all(pool);
  }

  // One review answer as a word: PASS, BLOCK, ADVISORY and UNSURE have words; any other value is shown as the server sent it.
  function qText(res) {
    if (res === undefined || res === null || res === '') return '-';
    var s = String(res);
    if (s === 'PASS') return t('adv.review.q_pass');
    if (s === 'BLOCK') return t('adv.review.q_block');
    if (s === 'ADVISORY') return t('adv.review.q_advisory');
    if (s === 'UNSURE') return t('adv.review.q_unsure');
    return s;
  }

  function fillReview(p, r, errMsg) {
    var a = (r && r.answers) || {};
    for (var i = 0; i < 6; i += 1) {
      var v = a['Q' + (i + 1)];
      var isObj = v !== null && typeof v === 'object';
      fill(p.q[i], [errMsg ? '-' : qText(isObj ? v.result : v)]);
      p.q[i].title = isObj ? String(or(v.reason, '')) : '';
    }
    if (errMsg) fill(p.verdict, [badge('failed', t('adv.kind.error'))]);
    else if (!r) fill(p.verdict, [badge('notrun')]);
    else {
      fill(p.verdict, [badgeFor(or(r.verdict, t('common.unknown'))), ' ',
        btn(t('adv.shots.details'), { className: 'linkish', onclick: function () { showReview(p.shot, p.cand, r); } })]);
    }
  }

  function showReview(shot, cand, r) {
    var box = $('review-detail');
    var answers = r.answers || {};
    var lines = [];
    for (var i = 1; i <= 6; i += 1) {
      var v = answers['Q' + i];
      var isObj = v !== null && typeof v === 'object';
      lines.push(el('li', { text: t('adv.review.q_line', {
        n: i,
        res: qText(isObj ? v.result : v),
        reason: isObj ? String(or(v.reason, '-')) : '-'
      }) }));
    }
    fill(box, [
      el('strong', { text: t('adv.review.title', { shot: shot, cand: cand }) }),
      el('p', { text: t('adv.review.verdict', { v: String(or(r.verdict, '-')) }) }),
      el('p', { text: t('adv.review.fix', { v: String(or(r.fix, '-')) }) }),
      el('p', { text: t('adv.review.regen', { v: String(or(r.regen_sentence, '-')) }) }),
      el('p', { text: t('adv.review.edit', { v: String(or(r.edit_instruction, '-')) }) }),
      el('ol', { className: 'box-list' }, lines)
    ]);
    box.hidden = false;
    if (box.scrollIntoView) box.scrollIntoView({ block: 'nearest' });
  }

  function neighbourSheet(shot, cands, jobs) {
    runCommand({
      title: t('adv.shots.neighbours_title', { shot: shot }),
      command: 'neighbour_sheet',
      risk: 'W',
      note: t('adv.shots.neighbours_note'),
      args: { jobs: jobs, shot: shot, candidates: cands.map(function (c) { return c.path; }), adhyay: adhyayNow() }
    });
  }

  function reviewShot(shot, cands, jobs) {
    runCommand({
      title: t('adv.shots.reviewer_title', { shot: shot }),
      command: 'review_shot',
      risk: 'N W',
      note: t('adv.shots.reviewer_note'),
      args: { jobs: jobs, shot: shot, candidates: cands.map(function (c) { return c.path; }), adhyay: adhyayNow() },
      onEnd: function () { return loadImages(true); }
    });
  }

  function queueKept(shot, cand, jobs) {
    var m = cand.name.match(/v\d{2}b?/);
    runCommand({
      title: t('adv.shots.queue_title', { shot: shot }),
      command: 'queue_add',
      risk: 'W',
      note: t('adv.shots.queue_note', { cand: cand.name }),
      fields: [
        { name: 'version', label: t('adv.queue.version'), value: m ? m[0] : '', pattern: PAT.version, required: true, hint: t('adv.queue.version_hint') },
        { name: 'edit', label: t('adv.queue.edit'), pattern: PAT.edit, required: true, placeholder: '00000000-0000-0000-0000-000000000000',
          hint: t('adv.queue.edit_hint') },
        { name: 'note', label: t('adv.queue.note'), pattern: PAT.note, required: true, hint: t('adv.queue.note_hint') }
      ],
      args: function (v) { return { shot: shot, version: v.version, edit: v.edit, jobs: jobs, note: v.note, adhyay: adhyayNow() }; },
      onEnd: function () { return loadImages(true); }
    });
  }

  function acceptCand(shot, cand) {
    var m = cand.name.match(/v\d{2}b?/);
    runCommand({
      title: t('adv.accept.title', { shot: shot }),
      command: 'queue_accept',
      risk: 'W',
      note: t('adv.accept.note'),
      check: t('adv.accept.check'),
      fields: [
        { name: 'version', label: t('adv.queue.version'), value: m ? m[0] : '', pattern: PAT.version, required: true, hint: t('adv.queue.version_hint') },
        { name: 'note', label: t('adv.accept.owner_note'), pattern: PAT.note, required: true, hint: t('adv.queue.note_hint') }
      ],
      args: function (v) { return { shot: shot, version: v.version, note: v.note, adhyay: adhyayNow() }; },
      onEnd: function () { return loadImages(true); }
    });
  }

  function renderProgress(d) {
    var p = d.progress;
    var lines = Array.isArray(p) ? p : ((p && Array.isArray(p.lines)) ? p.lines : []);
    lines = lines.filter(function (r) { return r && typeof r === 'object'; });
    fillTable('progress-table', [t('adv.th.shot'), t('adv.th.status'), t('adv.th.attempts'), t('adv.th.decided_by'), t('adv.th.note')], lines.map(function (r) {
      var legacy = !('decided_by' in r);
      return {
        className: legacy ? 'legacy' : null,
        cells: [String(or(r.shot_id, or(r.shot, '?'))), badgeFor(r.status), String(or(r.attempts, '-')),
          legacy ? t('adv.images.legacy') : String(or(r.decided_by, '-')), String(or(r.note, ''))]
      };
    }));
  }

  function count(x) {
    if (typeof x === 'number') return x;
    if (Array.isArray(x)) return x.length;
    return 0;
  }

  function stat(label, n) {
    return el('div', { className: 'stat' }, el('div', { className: 'statn', text: String(n) }), el('div', { className: 'muted', text: label }));
  }

  function renderQueue(d) {
    var q = d.queue || {};
    var c = q.counts || {};
    var pending = typeof c.pending === 'number' ? c.pending : count(q.pending);
    var filed = typeof c.filed === 'number' ? c.filed : count(d.filed);
    var accepted = typeof c.accepted === 'number' ? c.accepted : count(d.accepted);
    fill($('queue-counts'), [
      stat(t('adv.images.stat_pending'), pending),
      stat(t('adv.images.stat_filed'), filed),
      stat(t('adv.images.stat_accepted'), accepted)
    ]);
  }

  function collect() {
    runCommand({
      title: t('adv.images.collect_btn'),
      command: 'queue_collect',
      risk: 'W',
      note: t('adv.images.collect_note'),
      args: { adhyay: adhyayNow() },
      onEnd: function () { return loadImages(true); }
    });
  }

  function tidy() {
    runCommand({
      title: t('adv.images.tidy_btn'),
      command: 'tidy_plan',
      risk: 'R',
      note: t('adv.images.tidy_note'),
      args: { adhyay: adhyayNow() },
      onEnd: function (j) { return showTidy(j); }
    });
  }

  async function showTidy(j) {
    try {
      var txt = await api('GET', '/api/jobs/' + enc(j.id) + '/log?tail=200');
      var pre = $('tidy-out');
      pre.textContent = String(txt || t('adv.images.no_output'));
      pre.hidden = false;
    } catch (e) { showApiError(e); }
  }

  function renderFinals(d) {
    var list = d.finals || [];
    $('finals-count').textContent = t('adv.finals.count', { n: list.length });
    var grid = clear($('finals-grid'));
    if (!list.length) {
      grid.appendChild(el('p', { className: 'muted', text: t('adv.finals.none') }));
      return;
    }
    list.forEach(function (f) {
      var path = typeof f === 'string' ? f : String(or(f.path, ''));
      var name = baseName(path);
      var img = el('img', { src: '/api/file?path=' + enc(path), alt: name, loading: 'lazy' });
      grid.appendChild(el('button', { type: 'button', className: 'tile', title: t('adv.finals.tile', { name: name }),
        onclick: function () { openLightbox(path, name); } }, img, el('span', { text: name })));
    });
  }

  function openLightbox(path, name) {
    var im = $('lightbox-img');
    im.setAttribute('src', '/api/file?path=' + enc(path));
    im.setAttribute('alt', name);
    $('lightbox').hidden = false;
  }

  // ---------- Bridge ----------
  function bridgeRun(cmd) {
    var size = $('bridge-size').value;
    var dry = cmd === 'bridge_dry';
    runCommand({
      title: dry ? t('adv.bridge.dry_btn') : t('adv.bridge.write_btn'),
      command: cmd,
      risk: dry ? 'R' : 'W',
      note: dry ? t('adv.bridge.dry_note', { size: size }) : t('adv.bridge.write_note', { size: size }),
      args: { size: size, adhyay: adhyayNow() },
      onEnd: function (j) { return showBridge(j); }
    });
  }

  async function showBridge(j) {
    try {
      var r = await api('GET', '/api/jobs/' + enc(j.id) + '/result');
      var rows = Array.isArray(r) ? r : ((r && Array.isArray(r.records)) ? r.records : []);
      var counts = (r && !Array.isArray(r) && r.counts) || {};
      var summary = Object.keys(counts).map(function (k) { return k + ': ' + counts[k]; }).join(', ');
      showMsg(summary ? t('adv.bridge.finished', { summary: summary }) : t('adv.bridge.no_rows'));
      fillTable('bridge-table', [t('adv.th.file'), t('adv.th.status'), t('adv.th.detail'), t('adv.th.removed')], rows.map(function (x) {
        return [String(or(x.file, or(x.label, '-'))), badgeFor(x.status), String(or(x.detail, or(x.crop, '-'))),
          String(or(x.removed_px, '-'))];
      }));
    } catch (e) { showApiError(e); }
  }

  // ---------- Video ----------
  // Opening this section does not call Colab (the balance is read only by the "Check the Colab account" button).
  async function loadVideo() {
    try {
      var v = await api('GET', '/api/video');
      var files = (v.shot_files || []).map(function (f) { return typeof f === 'string' ? f : String(or(f.path, '')); });
      var sel = $('video-shotfile');
      var keep = sel.value;
      fill(sel, files.map(function (f) { return el('option', { value: f, text: f }); }));
      if (keep && files.indexOf(keep) >= 0) sel.value = keep;
      renderBatches(v.batches || []);
      renderClips(v.clips || []);
    } catch (e) {
      showApiError(e);
    }
    loadH3();
    applyGates();
  }

  function renderBatches(list) {
    fillTable('video-batches', [t('adv.th.batch'), t('adv.th.run_py'), t('adv.th.shots'), t('adv.th.embed')], list.map(function (b) {
      return [String(or(b.name, '?')), String(or(b.run_py_bytes, '-')), String(or(b.settings, '-')), String(or(b.embed_mb, '-'))];
    }));
  }

  function renderClips(list) {
    $('clips-home').textContent = String(list.length);
    fillTable('clips-table', [t('adv.th.shot_take'), t('adv.th.file'), t('adv.th.seconds'), t('adv.th.size'), t('adv.th.qa'), t('adv.th.actions')], list.map(function (c) {
      var path = String(or(c.file, ''));
      var file = el('a', { href: '/api/file?path=' + enc(path), target: '_blank', rel: 'noopener', text: baseName(path) });
      return [String(or(c.shot, '?')) + ' / ' + String(or(c.take, '-')), file, String(or(c.seconds, '-')),
        fmtBytes(c.bytes), yesNo(c.qa),
        [btn(t('adv.clips.sheet'), { className: 'act act-sheet', 'data-gate': 'job', onclick: function () { clipCmd('clip_qa', t('adv.clips.sheet'), path); } }),
          btn(t('adv.clips.vqa'), { className: 'act act-vqa', 'data-gate': 'job', onclick: function () { clipCmd('visual_qa', t('adv.clips.vqa'), path); } })]];
    }));
  }

  // QA output goes to results/qa, the folder the server reads qa json from (clip = results/<shot>/<take>.mp4).
  function qaDirFor(clip) {
    var sep = clip.indexOf('\\') >= 0 ? '\\' : '/';
    var parts = clip.split(/[\\/]/);
    parts.pop();
    parts.pop();
    return parts.join(sep) + sep + 'qa';
  }

  function clipCmd(cmd, title, path) {
    var out = qaDirFor(path);
    if (cmd === 'clip_qa') {
      return runCommand({
        title: title,
        command: 'clip_qa',
        risk: 'W',
        note: t('adv.clips.qa_note', { dir: out }),
        args: { clip: path, out_dir: out },
        onEnd: function () { return loadVideo(); }
      });
    }
    runCommand({
      title: title,
      command: 'visual_qa',
      risk: 'N W',
      note: t('adv.clips.vqa_note', { dir: out }),
      fields: [
        { name: 'direction', label: t('adv.vqa.direction'), pattern: PAT.json, required: true, hint: t('adv.vqa.direction_hint') },
        { name: 'model', label: t('adv.vqa.model'), options: VISION_MODELS, value: VISION_MODELS[0] }
      ],
      args: function (v) { return { clip: path, direction: v.direction, out_dir: out, model: v.model }; },
      onEnd: function () { return loadVideo(); }
    });
  }

  function scopeOf() {
    if ($('video-scope-reel').checked) return 'reel';
    if ($('video-scope-all').checked) return 'all';
    return 'shots';
  }

  // Returns {scope, ids | reel} or a string with the reason it is not valid (already in the page language).
  function scopeArgs() {
    var scope = scopeOf();
    if (scope === 'shots') {
      var ids = $('video-ids').value.split(',').map(function (x) { return x.trim(); }).filter(Boolean);
      if (!ids.length) return t('adv.video.shot_empty');
      var bad = ids.filter(function (x) { return !PAT.shot.test(x); });
      if (bad.length) return t('adv.video.shot_bad', { id: bad[0] });
      return { scope: 'shots', ids: ids };
    }
    if (scope === 'reel') {
      var n = $('video-reel').value.trim();
      if (!PAT.count.test(n) || Number(n) < 1) return t('adv.export.reel_bad');
      return { scope: 'reel', reel: Number(n) };
    }
    return { scope: 'all' };
  }

  function videoPrepare() {
    var batch = $('video-batch').value.trim();
    var sc = scopeArgs();
    if (!PAT.name.test(batch)) return showError(t('adv.video.batch_bad'));
    if (typeof sc === 'string') return showError(sc);
    var shots = $('video-shotfile').value;
    if (!shots) return showError(t('adv.video.err_pick_shot_file'));
    var args = { shots: shots, batch: batch };
    var root = $('video-keyframes').value.trim();
    if (root) args.keyframes = root; // empty = the server default (flow/adhyay_01/keyframes_h3)
    Object.keys(sc).forEach(function (k) { args[k] = sc[k]; });
    runCommand({
      title: t('adv.video.prepare_btn'),
      command: 'run_kaggle_prepare',
      risk: 'W',
      note: t('adv.video.prepare_note', { batch: batch }),
      args: args,
      onEnd: function () { return loadVideo(); }
    });
  }

  function h3Run() {
    var sc = scopeArgs();
    if (typeof sc === 'string') return showError(sc);
    var shots = $('video-shotfile').value;
    if (!shots) return showError(t('adv.video.err_pick_shot_file'));
    var args = { story: shots };
    Object.keys(sc).forEach(function (k) { args[k] = sc[k]; });
    runCommand({
      title: t('adv.video.h3_btn'),
      command: 'h3_prepare',
      risk: 'W',
      note: t('adv.video.h3_note'),
      args: args,
      onEnd: function () { return loadVideo(); }
    });
  }

  async function loadH3() {
    var box = $('h3-status');
    var cmd = $('h3-cmd');
    try {
      var h = await api('GET', '/api/h3');
      S.h3Ok = h.built === true;
      S.h3Msg = S.h3Ok ? '' : (h.message ? window.I18N.serverError(String(h.message)).text : t('err.srv.h3_missing'));
      fill(box, [badge(S.h3Ok ? 'ok' : 'notrun', S.h3Ok ? t('adv.video.h3_available') : t('adv.video.h3_not_built')), ' ',
        S.h3Ok ? t('adv.video.h3_mode') : S.h3Msg]);
      cmd.textContent = String(or(h.command_preview, t('adv.video.h3_cmd', {
        cmd: or(h.command, 'h3_prepare'),
        module: or(h.module, '-')
      })));
      cmd.hidden = !S.h3Ok;
    } catch (e) {
      S.h3Ok = false;
      S.h3Msg = t('adv.video.h3_unavail');
      fill(box, [badge('failed', t('adv.kind.error')), ' ', apiText(e)]);
      cmd.hidden = true;
    }
    applyGates();
  }

  async function loadColab(quiet) {
    var checkBtn = $('colab-check');
    checkBtn.disabled = true;
    checkBtn.textContent = t('adv.video.checking');
    try {
      var c = await api('GET', '/api/colab');
      renderColab(c);
      return c;
    } catch (e) {
      S.colabOk = false;
      $('colab-balance').textContent = t('adv.video.bal_failed');
      if (!quiet) showError(t('adv.video.colab_failed', { err: apiText(e) }));
      return null;
    } finally {
      checkBtn.disabled = false;
      checkBtn.textContent = t('adv.video.colab_check_btn');
      applyGates();
    }
  }

  function renderColab(c) {
    var cc = c || {};
    S.colabData = c || null;
    var sessions = Array.isArray(cc.sessions) ? cc.sessions : null;
    var headers = [t('adv.th.session'), t('adv.th.gpu'), t('adv.th.status'), t('adv.th.action')];
    if (sessions === null) {
      fillTable('colab-sessions', headers, [[t('adv.video.no_sessions'), '-', '-', '-']]);
    } else {
      fillTable('colab-sessions', headers, sessions.map(function (s) {
        var name = String(or(s.name, '?'));
        return [name, String(or(s.gpu, '-')), badgeFor(s.status),
          [btn(t('adv.video.stop_session', { name: name }), { className: 'act act-stop-session', onclick: function () { stopSession(name); } }),
            risk('OPS')]];
      }));
    }
    var usageOk = !(cc.read_ok && cc.read_ok.usage === false);
    var num = typeof cc.balance === 'number' ? cc.balance : NaN;
    S.colabOk = isFinite(num);
    S.colabBalance = S.colabOk ? num : null;
    $('colab-balance').textContent = S.colabOk ? String(num)
      : (usageOk ? t('adv.video.bal_none') : t('adv.video.bal_usage'));
    var rates = cc.rate_units_per_hour || {};
    var rateText = Object.keys(rates).map(function (k) { return t('adv.video.rate_item', { gpu: k, n: rates[k] }); }).join(', ');
    $('colab-rate').textContent = (rateText || t('common.unknown')) + (cc.cap_units ? t('adv.video.cap', { n: cc.cap_units }) : '');
    applyGates();
  }

  function colabRun() {
    var batch = $('video-batch').value.trim();
    if (!PAT.name.test(batch)) return showError(t('adv.video.batch_bad'));
    var cap = (S.status && S.status.spend_cap_units) || 15;
    runCommand({
      title: t('adv.colab.title'),
      command: 'colab_run',
      risk: '$',
      note: t('adv.colab.note', { batch: batch }),
      fields: [
        { name: 'gpu', label: t('adv.colab.gpu'), options: GPUS, value: 'G4', hint: t('adv.colab.gpu_hint') },
        { name: 'session', label: t('adv.colab.session'), pattern: PAT.session, required: true, value: 't0-kaliya',
          hint: t('adv.colab.session_hint') }
      ],
      args: function (v) { return { batch: batch, gpu: v.gpu, session: v.session }; },
      summary: function (v) {
        return [
          t('adv.colab.sum_gpu', { gpu: v.gpu, session: v.session, batch: batch }),
          t('adv.colab.sum_cap', { cap: cap, balance: S.colabBalance === null ? t('common.unknown') : S.colabBalance }),
          t('adv.colab.sum_stop')
        ];
      },
      onEnd: function () { return loadVideo(); }
    });
  }

  // Stop is a direct preview and run (no typed confirm). It is re-checked against the session list when done.
  async function stopSession(name) {
    try {
      var pv = await api('POST', '/api/preview', { command: 'colab_stop', args: { session: name } });
      var r = await api('POST', '/api/run', { token: pv.token });
      onStarted({ command: 'colab_stop', onEnd: function () { return afterStop(name); } }, r.job_id);
    } catch (e) { showApiError(e); }
  }

  async function afterStop(name) {
    var c = await loadColab(true);
    if (!c) return showError(t('adv.colab.recheck_fail', { name: name }));
    var still = (Array.isArray(c.sessions) ? c.sessions : []).some(function (s) { return s.name === name; });
    if (still) {
      showError(t('adv.colab.stop_failed', { name: name }));
    } else {
      showMsg(t('adv.colab.stop_gone', { name: name }));
    }
  }

  // ---------- Export ----------
  async function loadExport() {
    var reel = $('export-reel').value.trim();
    if (!PAT.count.test(reel) || Number(reel) < 1) return showError(t('adv.export.reel_bad'));
    try {
      // export is per pack: the story and pack come from the project pointer (never the Kaliya default)
      var pj = (window.StudioWizard && window.StudioWizard.project && window.StudioWizard.project()) || {};
      if (!pj.story_slug || !pj.pack) return showError(t('adv.export.pick_pack'));
      var d = await api('GET', '/api/export?reel=' + enc(reel) + '&story=' + enc(pj.story_slug) + '&pack=' + enc(pj.pack));
      var clips = (d.clips_in_order || []).map(function (c) {
        if (typeof c === 'string') return el('li', { text: c });
        return el('li', { text: String(or(c.shot, '?')) + ' ' + (c.take ? t('adv.export.take', { take: c.take }) : t('adv.export.no_take')) });
      });
      fill($('export-clips'), clips.length ? clips : [el('li', { text: t('adv.export.no_clips', { reel: reel }) })]);
      var a = d.assembly;
      var notBuilt = !a || String(a).toLowerCase() === 'not built';
      fill($('export-assembly'), notBuilt
        ? [badge('notrun', t('adv.export.not_built')), ' ' + String(or(d.assembly_note, t('adv.export.no_assembly')))]
        : [typeof a === 'string' ? a : JSON.stringify(a, null, 2)]);
      var files = d.reel_files || [];
      fill($('export-files'), files.length
        ? files.map(function (f) { return el('div', { text: typeof f === 'string' ? f : String(or(f.name, '?')) }); })
        : [t('adv.export.none')]);
    } catch (e) { showApiError(e); }
  }

  // ---------- Language change: re-draw what app.js wrote (I18N.apply only moves the static text) ----------
  function onLangChange() {
    renderHeader();
    loadWriterChoices();
    if (S.colabData) renderColab(S.colabData);
    S.logDone = null;
    var cb = $('colab-check');
    if (cb && !cb.disabled) cb.textContent = t('adv.video.colab_check_btn');
    showSection(S.section || 'story');
  }

  // ---------- Init ----------
  function init() {
    document.querySelectorAll('.navbtn').forEach(function (b) {
      b.addEventListener('click', function () { showSection(b.getAttribute('data-section')); });
    });
    document.querySelectorAll('.tabbtn').forEach(function (b) {
      b.addEventListener('click', function () { renderImgTab(b.getAttribute('data-tab')); });
    });
    var ay = [];
    for (var i = 1; i <= 12; i += 1) ay.push(el('option', { value: String(i), text: String(i) }));
    fill($('img-adhyay'), ay);
    $('img-adhyay').value = '1';
    // one story at a time: changing the picker also sets the wizard's story (POST /api/pipeline/project), then the wizard redraws
    $('story-slug').addEventListener('change', function () {
      var slug = $('story-slug').value;
      selectSlug(slug, '');
      api('POST', '/api/pipeline/project', { story_slug: slug, pack: '' }).then(function () {
        if (window.StudioWizard) window.StudioWizard.refresh();
      }).catch(function (e) { showApiError(e); });
    });
    $('story-pack').addEventListener('change', function () { loadPack(false); });
    $('story-load').addEventListener('click', loadStoryText);
    $('story-save').addEventListener('click', saveStory);
    $('story-run-new').addEventListener('click', function () { writerRun('new'); });
    $('story-resume').addEventListener('click', function () { writerRun('resume'); });
    $('story-check').addEventListener('click', checkPack);
    $('img-refresh').addEventListener('click', function () { loadImages(); });
    $('img-adhyay').addEventListener('change', function () { loadImages(); });
    $('btn-collect').addEventListener('click', collect);
    $('btn-tidy').addEventListener('click', tidy);
    $('bridge-dry').addEventListener('click', function () { bridgeRun('bridge_dry'); });
    $('bridge-write').addEventListener('click', function () { bridgeRun('bridge_write'); });
    $('video-prepare').addEventListener('click', videoPrepare);
    $('h3-run').addEventListener('click', h3Run);
    $('colab-check').addEventListener('click', function () { loadColab(false); });
    $('colab-run').addEventListener('click', colabRun);
    $('video-stop').addEventListener('click', stopJob);
    $('log-stop').addEventListener('click', stopJob);
    $('export-load').addEventListener('click', loadExport);
    $('modal-close').addEventListener('click', closeModal);
    $('modal').addEventListener('click', function (ev) { if (ev.target === $('modal')) closeModal(); });
    $('lightbox').addEventListener('click', function () { $('lightbox').hidden = true; });
    $('error-close').addEventListener('click', function () { $('error-bar').hidden = true; });
    document.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape') { closeModal(); $('lightbox').hidden = true; }
    });
    window.addEventListener('hashchange', function () {
      var h = location.hash.slice(1);
      if (h !== S.section) showSection(h);
    });
    window.addEventListener('studio:lang', onLangChange);
    showSection((location.hash || '#story').slice(1));
    loadWriterChoices();
    tick();
    // one poller, and it stays quiet while the tab is hidden
    setInterval(function () { if (!document.hidden) tick(); }, POLL_MS);
  }

  // The strings load first (I18N.ready), then the page starts.
  function boot() {
    var ready = window.I18N ? window.I18N.ready : Promise.resolve();
    ready.then(init, init);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
