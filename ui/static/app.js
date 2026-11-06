/*
 * Anime Studio control UI (frontend). Plain JS, ES2018, no framework, no network except same-origin /api/*.
 * Server text only goes in through textContent and createElement; no HTML string is ever parsed.
 *
 * Backend contract: the shapes this page reads, as served by ui/server.py. A missing key shows as "-"; it never throws.
 *   GET  /api/status           {studio_ok, flow_ok, python, colab_cli, nvidia_key_files (count), spend_allowed,
 *                               spend_cap_units, h3_built, job: null | {id, command, state, rc, started, ended, spend, warning}}
 *   GET  /api/jobs             [job summary, newest first]
 *   GET  /api/jobs/{id}/log?tail=N           text, redacted
 *   GET  /api/jobs/{id}/result bridge_*: {records, counts}; queue_collect: {lines}; review_shot: {verdict, exit}; other: {lines}
 *   POST /api/jobs/{id}/stop   {} -> {state, warning}
 *   GET  /api/story            {slugs: [{slug, packs: [name], has_source}]}
 *   GET  /api/story/{slug}     {text, bytes}; 404 = no SOURCE.md yet
 *   POST /api/story/{slug}     {text, overwrite} -> {saved, bytes}; 409 = SOURCE.md exists
 *   GET  /api/pack?pack=stories/<slug>/<name>[&check=1]
 *                              {stages: {"1": bool, ...}, gate1, episodes: [{n, shots, seconds, check}],
 *                               characters: [{id, name}], places: [{id, name}],
 *                               shots: [{id, episode, mode, seconds, cut_in, cut_out, issues: count}], check}
 *   GET  /api/images?adhyay=N  {series: {characters, places, props: [{id, name, chip, sheet, accepted}]},
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
 *   write_pack {slug, pack, writer}          bridge_dry / bridge_write {size, adhyay}
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

  var POLL_MS = 2500;
  var PACK_STAGES = ['1', '2', '3e1', '3e2', '3e3', '3e4', '3e5', '5'];
  var WRITER_NAMES = ['super-vl', 'ultra'];   // write_pack --writer shortcuts: both are free OpenRouter models; super-vl is the default
  var VISION_MODELS = ['nvidia/nemotron-3-nano-omni-30b-a3b-reasoning', 'nvidia/nemotron-3.5-super-vl-120b-a12b'];
  var GPUS = ['G4', 'A100'];
  var SECTIONS = ['story', 'images', 'bridge', 'video', 'export'];
  var IMG_TABS = ['series', 'jobs', 'shots', 'progress', 'queue', 'finals'];
  var MAX_STORY_BYTES = 200 * 1024;
  var JOBS_DIR = 'flow/';
  var FINISHED_TEXT = 'the job had already finished';
  var GUARD_403 = 'Refused by a server guard (403). Spend commands need the server started with --allow-spend. ' +
    'Every request needs header X-UI and Host 127.0.0.1:8765.';
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
  var RISK_TEXT = {
    R: 'R = read-only',
    W: 'W = writes local files (never deletes)',
    N: 'N = free model call (network, rate-limited)',
    '$': '$ = spends Colab units or GPU time (spend gate)',
    OPS: 'OPS = stops a local process (cuts spend, no confirm)',
    X: 'X = not available yet'
  };
  var KIND_TEXT = { ok: 'OK', notrun: 'NOT RUN', review: 'NEEDS REVIEW', failed: 'FAILED', running: 'RUNNING' };

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
    h3Ok: false,
    h3Msg: ''
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
    var t = clear($(id));
    t.appendChild(el('thead', null, el('tr', null, headers.map(function (h) { return el('th', { text: h }); }))));
    var tb = el('tbody');
    if (!rows.length) {
      tb.appendChild(el('tr', null, el('td', { colspan: headers.length, className: 'muted', text: '(none)' })));
    }
    rows.forEach(function (r) {
      var cells = Array.isArray(r) ? r : r.cells;
      var tr = el('tr', { className: Array.isArray(r) ? null : r.className });
      cells.forEach(function (c) { tr.appendChild(el('td', null, c)); });
      tb.appendChild(tr);
    });
    t.appendChild(tb);
    return t;
  }

  function or(v, d) { return (v === undefined || v === null || v === '') ? d : v; }
  function enc(s) { return encodeURIComponent(String(s)); }
  function errText(e) { return (e && e.message) ? e.message : String(e); }
  function yn(v) { return v ? 'OK' : 'missing'; }
  function baseName(p) { return String(or(p, '-')).split(/[\\/]/).pop() || '-'; }

  function risk(codes) {
    return String(codes).split(' ').filter(Boolean).map(function (c) {
      return el('span', { className: 'risk risk-' + (c === '$' ? 'usd' : c), text: c, title: RISK_TEXT[c] || c });
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

  function badge(kind, text) {
    return el('span', { className: 'badge b-' + kind, text: text || KIND_TEXT[kind] });
  }

  function badgeFor(v) {
    return badge(kindOf(v), String(v).toUpperCase());
  }

  function yesNo(v) { return v ? badge('ok', 'yes') : badge('notrun', 'no'); }

  function showError(msg) {
    $('error-text').textContent = String(msg);
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

  function fmtBytes(n) {
    if (typeof n !== 'number') return '-';
    if (n >= 1048576) return (n / 1048576).toFixed(1) + ' MB';
    if (n >= 1024) return Math.round(n / 1024) + ' KB';
    return n + ' B';
  }

  function names(list) {
    return (list || []).map(function (x) {
      var t = typeof x === 'string' ? x : ((x && (x.name || x.id)) || '?');
      return el('li', { text: t });
    });
  }

  function adhyayNow() {
    var n = Number($('img-adhyay').value);
    return (n >= 1 && n <= 12) ? n : 1;
  }

  // ---------- API (the only fetch) ----------
  function fail(status, message) {
    var e = new Error(message);
    e.status = status;
    return e;
  }

  async function api(method, path, body) {
    var opts = { method: method, headers: {}, cache: 'no-store' };
    if (method !== 'GET') {
      opts.headers['X-UI'] = '1';
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body || {});
    }
    var res;
    try {
      res = await fetch(path, opts);
    } catch (e) {
      throw fail(0, 'Cannot reach the studio server on 127.0.0.1:8765. Is server.py running?');
    }
    var text = await res.text();
    var isJson = /json/.test(res.headers.get('Content-Type') || '');
    var data = text;
    if (isJson) {
      try { data = JSON.parse(text); } catch (e) { data = text; }
    }
    if (!res.ok) {
      var msg = (isJson && data && data.error) ? String(data.error) : (text.slice(0, 300) || res.statusText);
      if (res.status === 403) msg = GUARD_403 + ' Server said: ' + msg;
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
    sb.textContent = st.spend_allowed ? 'SPEND ON' : 'SPEND OFF';
    sb.className = 'badge ' + (st.spend_allowed ? 'b-review' : 'b-grey');
    var job = st.job || null;
    S.jobBusy = isRunning(job);
    if (job && job.id) S.lastJobId = job.id;
    var text = (job && job.id) ? 'job: ' + (job.command || 'job') + ' ' + job.id : 'job: none';
    fill($('job-badge'), [text, ' ', S.jobBusy ? badge('running') : null]);
    if (S.status) {
      $('story-status').textContent = 'Studio ' + yn(st.studio_ok) + ', flow ' + yn(st.flow_ok) +
        ', Colab CLI ' + yn(st.colab_cli) + ', NVIDIA key files: ' + or(st.nvidia_key_files, '?') + ' (count only).';
    }
  }

  // Gates: data-gate tokens (spend, colab, h3, job, busy, never) and data-off set a reason; no reason = enabled.
  function applyGates() {
    var st = S.status || {};
    Array.prototype.forEach.call(document.querySelectorAll('[data-gate],[data-off]'), function (n) {
      var g = (n.getAttribute('data-gate') || '').split(' ');
      var why = n.hasAttribute('data-off') ? (n.getAttribute('data-off-why') || 'Not available here') : '';
      if (!why && g.indexOf('never') >= 0) why = n.getAttribute('data-why') || 'Not available yet';
      if (!why && g.indexOf('spend') >= 0 && !st.spend_allowed) why = 'Spend is OFF. The server was not started with --allow-spend.';
      if (!why && g.indexOf('colab') >= 0 && !S.colabOk) why = 'Check Colab first. The balance is unknown.';
      if (!why && g.indexOf('h3') >= 0 && !S.h3Ok) why = S.h3Msg || 'h3 engine not built yet';
      if (!why && g.indexOf('job') >= 0 && S.jobBusy) why = 'A job is already running. One at a time.';
      if (!why && g.indexOf('busy') >= 0 && !S.jobBusy) why = 'No job is running.';
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
        setServerState('server not reachable');
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
    S.trackers.forEach(function (t) {
      var j = jobs.filter(function (x) { return x.id === t.id; })[0];
      if (!j || isRunning(j)) { still.push(t); return; }
      if (!jobOk(j)) {
        showError(t.command + ' ended with rc ' + ((j.rc === null || j.rc === undefined) ? '?' : j.rc) +
          '. Read the log tail at the bottom.');
      }
      Promise.resolve().then(function () { return t.onEnd ? t.onEnd(j) : null; })
        .catch(function (e) { showError(errText(e)); });
    });
    S.trackers = still;
  }

  async function refreshLog() {
    var id = (S.status && S.status.job && S.status.job.id) || S.lastJobId;
    if (!id) return;
    if (!S.jobBusy && S.logDone === id) return;
    var txt = await api('GET', '/api/jobs/' + enc(id) + '/log?tail=12');
    var lines = String(txt || '').split('\n');
    $('log-tail').textContent = lines.slice(-12).join('\n') || '(no output yet)';
    $('log-job').textContent = '(job ' + id + (S.jobBusy ? ', running' : ', finished') + '; last 12 lines, redacted)';
    if (!S.jobBusy) S.logDone = id;
    if (S.section === 'video') {
      var live = await api('GET', '/api/jobs/' + enc(id) + '/log?tail=200');
      $('video-live').textContent = String(live || '') || '(no output yet)';
    }
  }

  function onStarted(cfg, id) {
    if (!id) return showMsg('Started: ' + cfg.command + '.');
    S.lastJobId = id;
    S.logDone = null;
    S.jobBusy = true;
    showMsg('Job ' + id + ' started (' + cfg.command + ').');
    S.trackers.push({ id: id, command: cfg.command, onEnd: cfg.onEnd });
    applyGates();
    tick();
  }

  async function stopJob() {
    var id = (S.status && S.status.job && S.status.job.id) || S.lastJobId;
    if (!id) return showMsg('No job to stop.');
    try {
      var r = await api('POST', '/api/jobs/' + enc(id) + '/stop', {});
      var warn = r && r.warning ? String(r.warning) : '';
      if (warn === FINISHED_TEXT) {
        showMsg('Job ' + id + ' had already finished. Nothing was stopped.');
      } else if (warn) {
        showError('The session may still run. ' + warn);
        loadColab(true);
      } else {
        showMsg('Stop sent to job ' + id + ' (local process only).');
      }
    } catch (e) { showError(errText(e)); }
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
    var previewBtn = btn('Preview (nothing runs yet)', { id: 'modal-preview', className: 'primary' });
    body.appendChild(el('div', { className: 'btnrow' }, previewBtn, btn('Cancel', { id: 'modal-cancel', onclick: closeModal })));

    function doPreview() {
      errBox.hidden = true;
      var values = {};
      var problem = '';
      Object.keys(fieldNodes).forEach(function (k) {
        var f = fieldNodes[k].spec;
        var v = String(fieldNodes[k].input.value || '').trim();
        values[k] = v;
        if (f.required && !v) problem = problem || (f.label + ' is required.');
        else if (v && f.pattern && !f.pattern.test(v)) problem = problem || (f.label + ': ' + (f.hint || 'wrong format') + '.');
      });
      if (!problem && check && !check.checked) problem = 'Tick "' + cfg.check + '" first.';
      if (problem) return showInline(errBox, problem);
      var args = typeof cfg.args === 'function' ? cfg.args(values) : (cfg.args || {});
      previewBtn.disabled = true;
      api('POST', '/api/preview', { command: cfg.command, args: args }).then(function (pv) {
        previewBtn.hidden = true;
        showStage(pv, values);
      }).catch(function (e) {
        showInline(errBox, errText(e));
        previewBtn.disabled = false;
      });
    }

    function showStage(pv, values) {
      clear(stage);
      var argv = Array.isArray(pv.argv) ? pv.argv : [String(or(pv.argv, ''))];
      stage.appendChild(el('h3', { text: 'Exact command (argv, one item per line)' }));
      stage.appendChild(el('pre', { id: 'modal-argv', className: 'argv', text: argv.join('\n') }));
      if (cfg.summary) {
        cfg.summary(values, pv).forEach(function (line) {
          stage.appendChild(el('p', { className: 'summary-line', text: line }));
        });
      }
      if (pv.estimate !== undefined && pv.estimate !== null) {
        stage.appendChild(el('p', { text: 'Estimate: about ' + pv.estimate + ' units (from the server).' }));
      }
      if (pv.balance !== undefined && pv.balance !== null) {
        stage.appendChild(el('p', { text: 'Balance: ' + String(pv.balance) }));
      }
      var expiry = el('p', { id: 'modal-expiry', className: 'muted' });
      stage.appendChild(expiry);
      var needsTyped = !!pv.needs_confirm || cfg.risk.indexOf('$') >= 0;
      var want = needsTyped ? (pv.confirm_text || ('EXECUTE ' + pv.estimate)) : '';
      var typed = null;
      if (needsTyped) {
        typed = el('input', { id: 'modal-confirm-input', type: 'text', autocomplete: 'off', placeholder: want });
        stage.appendChild(el('label', { className: 'field' }, el('span', { text: 'Type ' + want + ' to start:' }), typed));
      }
      var startBtn = btn('Start', { id: 'modal-start', className: needsTyped ? 'danger' : 'primary' });
      stage.appendChild(el('div', { className: 'btnrow' }, startBtn));

      var left = Number(pv.expires_s) || 60;
      function showLeft() {
        if (left > 0) {
          expiry.textContent = 'Preview expires in ' + left + ' s.';
        } else {
          expiry.textContent = 'Preview expired. Close and preview again.';
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
          var t = typed.value.trim();
          if (t !== want) return showInline(errBox, 'Type exactly: ' + want);
          body2.confirm = t;
        }
        startBtn.disabled = true;
        api('POST', '/api/run', body2).then(function (r) {
          closeModal();
          onStarted(cfg, r && r.job_id);
        }).catch(function (e) {
          showInline(errBox, errText(e));
          startBtn.disabled = left <= 0;
        });
      });
    }

    previewBtn.addEventListener('click', doPreview);
    if (!(cfg.fields && cfg.fields.length) && !cfg.check) doPreview();
  }

  function copyText(text, b) {
    function done(ok) { b.textContent = ok ? 'Copied' : 'Copy failed: select the text and copy it'; }
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
  async function loadStory(pack) {
    try {
      var d = await api('GET', '/api/story');
      S.slugs = (d && d.slugs) || [];
      if (!S.slugs.length) {
        fill($('story-slug'), [el('option', { value: '', text: '(no stories)' })]);
        renderPack(null);
        return;
      }
      var keep = S.slugs.some(function (s) { return s.slug === S.story.slug; }) ? S.story.slug : S.slugs[0].slug;
      fill($('story-slug'), S.slugs.map(function (s) { return el('option', { value: s.slug, text: s.slug }); }));
      $('story-slug').value = keep;
      selectSlug(keep, pack);
    } catch (e) { showError(errText(e)); }
  }

  function selectSlug(slug, pack) {
    var changed = slug !== S.story.slug;
    S.story.slug = slug;
    var entry = S.slugs.filter(function (s) { return s.slug === slug; })[0] || { packs: [] };
    var packs = entry.packs || [];
    fill($('story-pack'), packs.length
      ? packs.map(function (p) { return el('option', { value: p, text: p }); })
      : [el('option', { value: '', text: '(no packs yet)' })]);
    if (pack && packs.indexOf(pack) >= 0) $('story-pack').value = pack;
    if (changed) loadStoryText();
    loadPack(false);
  }

  async function loadStoryText() {
    if (!S.story.slug) return;
    try {
      var d = await api('GET', '/api/story/' + enc(S.story.slug));
      $('story-text').value = d.text || '';
      $('story-bytes').textContent = '(' + (d.bytes || 0) + ' bytes on disk)';
    } catch (e) {
      if (e.status === 404) {
        $('story-text').value = '';
        $('story-bytes').textContent = '(no SOURCE.md yet)';
      } else {
        showError(errText(e));
      }
    }
  }

  async function saveStory() {
    if (!S.story.slug) return showError('Pick a story slug first.');
    var text = $('story-text').value;
    var bytes = new TextEncoder().encode(text).length;
    if (bytes > MAX_STORY_BYTES) return showError('Story is ' + bytes + ' bytes. The limit is 200 KB.');
    try {
      var d = await api('POST', '/api/story/' + enc(S.story.slug), { text: text, overwrite: $('story-overwrite').checked });
      $('story-bytes').textContent = '(' + or(d.bytes, bytes) + ' bytes on disk)';
      showMsg('Saved SOURCE.md (' + or(d.bytes, bytes) + ' bytes).');
    } catch (e) {
      if (e.status === 409) showError('SOURCE.md already exists. Tick "overwrite if SOURCE.md exists" to replace it.');
      else showError(errText(e));
    }
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
      showError(errText(e));
      return false;
    }
  }

  async function checkPack() {
    var b = $('story-check');
    b.disabled = true;
    try {
      if (await loadPack(true)) showMsg('Pack checked. The result is in check_pack JSON.');
    } finally {
      b.disabled = false;
    }
  }

  function renderPack(p) {
    p = p || {};
    var st = p.stages || {};
    fill($('story-stages'), PACK_STAGES.map(function (k) {
      var ok = st[k] === true;
      return el('span', { className: 'stagebadge' }, 'Stage ' + k, badge(ok ? 'ok' : 'notrun', ok ? 'OK' : 'NOT RUN'));
    }));
    $('story-gate1').textContent = p.gate1 || '(no Gate 1 text for this pack yet)';
    fillTable('story-episodes', ['#', 'Shots', 'Seconds', 'Check'], (p.episodes || []).map(function (e) {
      return [String(or(e.n, '-')), String(or(e.shots, '-')), String(or(e.seconds, '-')), e.check ? badgeFor(e.check) : '-'];
    }));
    fill($('story-characters'), names(p.characters));
    fill($('story-places'), names(p.places));
    fillTable('story-shots', ['Shot', 'Ep', 'Mode', 'Sec', 'Cut in -> cut out', 'Issues'], (p.shots || []).map(function (s) {
      var n = Array.isArray(s.issues) ? s.issues.length : or(s.issues, 0);
      return [String(or(s.id, '?')), String(or(s.episode, '-')), String(or(s.mode, '-')), String(or(s.seconds, '-')),
        String(or(s.cut_in, '-')) + ' -> ' + String(or(s.cut_out, '-')), String(n)];
    }));
    $('story-check-json').textContent = p.check ? JSON.stringify(p.check, null, 2) : '(no check yet)';
  }

  function writerRun(kind) {
    var slug = S.story.slug;
    if (!slug) return showError('Pick a story slug first.');
    var pack = kind === 'new' ? $('story-newpack').value.trim() : $('story-pack').value;
    if (kind === 'new' && !PAT.name.test(pack)) {
      return showError('New pack name: lowercase letters, digits, _ or -, 1 to 40 characters.');
    }
    if (kind !== 'new' && !pack) return showError('Pick a pack to resume.');
    runCommand({
      title: kind === 'new' ? 'Run writer: new pack' : 'Resume pack',
      command: 'write_pack',
      risk: 'N W',
      note: 'Calls the writer on a free OpenRouter model (streamed). Writes stage files into the pack folder. ' +
        'Saved stages are not sent again.',
      args: { slug: slug, pack: pack, writer: ($('story-model') && $('story-model').value) || WRITER_NAMES[0] },
      onEnd: function () { return loadStory(pack); }
    });
  }

  // ---------- Images ----------
  async function loadImages(quiet) {
    try {
      S.images = await api('GET', '/api/images?adhyay=' + enc(adhyayNow()));
      S.imgAt = Date.now();
      renderImgTab(S.imgTab);
    } catch (e) {
      if (!quiet) showError(errText(e));
    }
  }

  function renderImgTab(tab) {
    S.imgTab = tab;
    IMG_TABS.forEach(function (t) {
      $('img-' + t).hidden = t !== tab;
      var b = $('tab-' + t);
      b.classList.toggle('active', t === tab);
      b.setAttribute('aria-selected', t === tab ? 'true' : 'false');
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

  function renderSeries(d) {
    var rows = [];
    var series = d.series || {};
    ['characters', 'places', 'props'].forEach(function (grp) {
      (Array.isArray(series[grp]) ? series[grp] : []).forEach(function (x) {
        rows.push([grp, String(or(x.id, '?')), String(or(x.name, '-')), String(or(x.chip, '-')), baseName(x.sheet), yesNo(x.accepted)]);
      });
    });
    (d.sheets || []).forEach(function (x) {
      rows.push(['sheet', String(or(x.id, '?')), '-', '-', baseName(x.sheet), yesNo(x.accepted)]);
    });
    fillTable('series-table', ['Group', 'Id', 'Name', 'Chip', 'Sheet file', 'Accepted'], rows);
  }

  function renderJobs(d) {
    fillTable('jobs-table', ['Shot', 'Scene', 'Chips', 'Attempts / cap', 'Status', 'Actions'], (d.jobs || []).map(function (j) {
      var chips = Array.isArray(j.chips) ? j.chips.join(', ') : String(or(j.chips, '-'));
      var packet = btn('Packet', Object.assign({ className: 'act act-packet', onclick: function () { openPacket(j); } },
        offProps(!j.file, 'The server sent no jobs file name for this row.')));
      var build = btn('Build*', {
        className: 'act act-build',
        'data-gate': 'never',
        'data-why': 'Not available yet: the job builder is not in the studio (gap G1; Q5 = no).',
        'data-title': 'Not available yet (gap G1)'
      });
      return [String(or(j.shot_id, '?')), String(or(j.scene, '-')), chips,
        String(or(j.attempts, 0)) + ' / ' + String(or(j.attempt_cap, '?')), badgeFor(or(j.status, 'not run')), [packet, build]];
    }));
  }

  async function openPacket(j) {
    if (!j.file) return showError('The server sent no jobs file name for this row.');
    try {
      var r = await api('POST', '/api/packet', { jobs: JOBS_DIR + j.file, shots: [j.shot_id] });
      showPacket(String(or(j.shot_id, '?')), r || {});
    } catch (e) { showError(errText(e)); }
  }

  function showPacket(shot, r) {
    openModal('Agent packet: ' + shot);
    var body = $('modal-body');
    var pre = el('pre', { id: 'packet-md', className: 'box', text: String(or(r.markdown, '(no markdown returned)')) });
    body.appendChild(el('div', { className: 'banner-info', text: 'Flow agents run on Haiku, effort LOW' }));
    body.appendChild(el('p', { className: 'muted', text: 'One scene per agent, own tab id. Model chip: Nano Banana 2.1 x2. Phase 1: no downloads.' }));
    body.appendChild(el('p', { className: 'muted', text: 'Saved at: ' + String(or(r.path, '(path not returned)')) }));
    body.appendChild(btn('Copy', { id: 'packet-copy', className: 'primary', onclick: function (ev) { copyText(pre.textContent, ev.currentTarget); } }));
    body.appendChild(pre);
    body.appendChild(el('div', { className: 'btnrow' }, btn('Close', { onclick: closeModal })));
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
    tbl.appendChild(el('thead', null, el('tr', null,
      ['Shot', 'Candidate', 'Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'Q6', 'Verdict', 'Actions'].map(function (h) { return el('th', { text: h }); }))));
    (d.shots || []).forEach(function (s) {
      var shotId = String(or(s.id, ''));
      var cands = candList(s);
      var jobs = jobsFor(shotId);
      var why = cands.length ? 'No job entry for this shot in the jobs files.' : 'No candidate pictures for this shot yet.';
      var off = !cands.length || !jobs;
      var tb = el('tbody', { className: 'shotgroup' });
      tb.appendChild(el('tr', { className: 'shotrow' },
        el('th', { text: shotId + ' (' + cands.length + ')', scope: 'rowgroup' }),
        el('td', { colspan: 9 },
          btn('Neighbour sheet', Object.assign({ className: 'act act-neighbours', 'data-gate': 'job',
            onclick: function () { neighbourSheet(shotId, cands, jobs); } }, offProps(off, why))),
          btn('Run reviewer', Object.assign({ className: 'act act-reviewer', 'data-gate': 'job',
            onclick: function () { reviewShot(shotId, cands, jobs); } }, offProps(off, why))))));
      if (!cands.length) {
        tb.appendChild(el('tr', null, el('td', { colspan: 10, className: 'muted', text: 'No candidate files yet.' })));
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
            btn('Queue kept', Object.assign({ className: 'act act-queue-kept', 'data-gate': 'job',
              onclick: function () { queueKept(shotId, c, jobs); } }, offProps(off, why))),
            btn('Accept (owner)', Object.assign({ className: 'act act-accept', 'data-gate': 'job',
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

  function fillReview(p, r, errMsg) {
    var a = (r && r.answers) || {};
    for (var i = 0; i < 6; i += 1) {
      fill(p.q[i], [errMsg ? '-' : String(or(a['Q' + (i + 1)], '-'))]);
    }
    if (errMsg) fill(p.verdict, [badge('failed', 'ERROR')]);
    else if (!r) fill(p.verdict, [badge('notrun', 'NOT RUN')]);
    else {
      fill(p.verdict, [badgeFor(or(r.verdict, 'unknown')), ' ',
        btn('details', { className: 'linkish', onclick: function () { showReview(p.shot, p.cand, r); } })]);
    }
  }

  function showReview(shot, cand, r) {
    var box = $('review-detail');
    fill(box, [
      el('strong', { text: 'Review: ' + shot + ' / ' + cand }),
      el('p', { text: 'Verdict: ' + String(or(r.verdict, '-')) }),
      el('p', { text: 'Fix: ' + String(or(r.fix, '-')) }),
      el('p', { text: 'Regen sentence: ' + String(or(r.regen_sentence, '-')) }),
      el('p', { text: 'Edit instruction: ' + String(or(r.edit_instruction, '-')) })
    ]);
    box.hidden = false;
    if (box.scrollIntoView) box.scrollIntoView({ block: 'nearest' });
  }

  function neighbourSheet(shot, cands, jobs) {
    runCommand({
      title: 'Neighbour sheet: ' + shot,
      command: 'neighbour_sheet',
      risk: 'W',
      note: 'Writes a contact sheet for this shot next to its candidates. Nothing is sent to a model.',
      args: { jobs: jobs, shot: shot, candidates: cands.map(function (c) { return c.path; }), adhyay: adhyayNow() }
    });
  }

  function reviewShot(shot, cands, jobs) {
    runCommand({
      title: 'Run reviewer: ' + shot,
      command: 'review_shot',
      risk: 'N W',
      note: 'Calls the reviewer (NVIDIA, free tier) for Q1 to Q6. Exit 0 PASS, 1 BLOCK, 3 UNSURE.',
      args: { jobs: jobs, shot: shot, candidates: cands.map(function (c) { return c.path; }), adhyay: adhyayNow() },
      onEnd: function () { return loadImages(true); }
    });
  }

  function queueKept(shot, cand, jobs) {
    var m = cand.name.match(/v\d{2}b?/);
    runCommand({
      title: 'Queue kept: ' + shot,
      command: 'queue_add',
      risk: 'W',
      note: 'Adds this kept tile to the download queue (model: Nano Banana 2.1 x2). Downloads nothing. Candidate: ' + cand.name,
      fields: [
        { name: 'version', label: 'Version', value: m ? m[0] : '', pattern: PAT.version, required: true, hint: 'vNN, for example v02' },
        { name: 'edit', label: 'Edit id', pattern: PAT.edit, required: true, placeholder: 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx',
          hint: 'lowercase hex and dashes, 36 characters' },
        { name: 'note', label: 'Note', pattern: PAT.note, required: true, hint: 'one line, up to 200 characters' }
      ],
      args: function (v) { return { shot: shot, version: v.version, edit: v.edit, jobs: jobs, note: v.note, adhyay: adhyayNow() }; },
      onEnd: function () { return loadImages(true); }
    });
  }

  function acceptCand(shot, cand) {
    var m = cand.name.match(/v\d{2}b?/);
    runCommand({
      title: 'Accept (owner): ' + shot,
      command: 'queue_accept',
      risk: 'W',
      note: 'Owner decision, recorded for this shot. Tick only after you looked at the full-size image.',
      check: 'I looked at full size',
      fields: [
        { name: 'version', label: 'Version', value: m ? m[0] : '', pattern: PAT.version, required: true, hint: 'vNN' },
        { name: 'note', label: 'Owner note', pattern: PAT.note, required: true, hint: 'one line, up to 200 characters' }
      ],
      args: function (v) { return { shot: shot, version: v.version, note: v.note, adhyay: adhyayNow() }; },
      onEnd: function () { return loadImages(true); }
    });
  }

  function renderProgress(d) {
    var p = d.progress;
    var lines = Array.isArray(p) ? p : ((p && Array.isArray(p.lines)) ? p.lines : []);
    lines = lines.filter(function (r) { return r && typeof r === 'object'; });
    fillTable('progress-table', ['Shot', 'Status', 'Attempts', 'Decided by', 'Note'], lines.map(function (r) {
      var legacy = !('decided_by' in r);
      return {
        className: legacy ? 'legacy' : null,
        cells: [String(or(r.shot_id, or(r.shot, '?'))), badgeFor(or(r.status, 'not run')), String(or(r.attempts, '-')),
          legacy ? 'legacy (no decided_by)' : String(or(r.decided_by, '-')), String(or(r.note, ''))]
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
    fill($('queue-counts'), [stat('pending', pending), stat('filed', filed), stat('accepted', accepted)]);
  }

  function collect() {
    runCommand({
      title: 'Collect from Downloads',
      command: 'queue_collect',
      risk: 'W',
      note: 'Copies matching files from Downloads into final\\. Refuses existing outputs. Deletes nothing.',
      args: { adhyay: adhyayNow() },
      onEnd: function () { return loadImages(true); }
    });
  }

  function tidy() {
    runCommand({
      title: 'Tidy plan (dry run)',
      command: 'tidy_plan',
      risk: 'R',
      note: 'Dry run only: lists what tidy would move. Moves nothing.',
      args: { adhyay: adhyayNow() },
      onEnd: function (j) { return showTidy(j); }
    });
  }

  async function showTidy(j) {
    try {
      var txt = await api('GET', '/api/jobs/' + enc(j.id) + '/log?tail=200');
      var pre = $('tidy-out');
      pre.textContent = String(txt || '(no output)');
      pre.hidden = false;
    } catch (e) { showError(errText(e)); }
  }

  function renderFinals(d) {
    var list = d.finals || [];
    $('finals-count').textContent = list.length + ' final(s). Click a tile for full size.';
    var grid = clear($('finals-grid'));
    if (!list.length) {
      grid.appendChild(el('p', { className: 'muted', text: 'No finals yet.' }));
      return;
    }
    list.forEach(function (f) {
      var path = typeof f === 'string' ? f : String(or(f.path, ''));
      var name = baseName(path);
      var img = el('img', { src: '/api/file?path=' + enc(path), alt: name, loading: 'lazy' });
      grid.appendChild(el('button', { type: 'button', className: 'tile', title: 'Full size: ' + name,
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
      title: dry ? 'Bridge dry run' : 'Bridge: write keyframes',
      command: cmd,
      risk: dry ? 'R' : 'W',
      note: dry ? 'Shows what would be written at ' + size + '. Writes nothing.'
        : 'Writes keyframes_h3 at ' + size + '. Existing files are not overwritten.',
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
      showMsg(summary ? 'Bridge finished. ' + summary + '.' : 'Bridge job finished with no parsed rows. Read the log tail at the bottom.');
      fillTable('bridge-table', ['File', 'Status', 'Detail', 'Removed px'], rows.map(function (x) {
        return [String(or(x.file, or(x.label, '-'))), badgeFor(or(x.status, 'skip')), String(or(x.detail, or(x.crop, '-'))),
          String(or(x.removed_px, '-'))];
      }));
    } catch (e) { showError(errText(e)); }
  }

  // ---------- Video ----------
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
      showError('Video: ' + errText(e));
    }
    loadH3();
    loadColab(true);
    applyGates();
  }

  function renderBatches(list) {
    fillTable('video-batches', ['Batch', 'run.py bytes', 'Shots', 'Embed MB'], list.map(function (b) {
      return [String(or(b.name, '?')), String(or(b.run_py_bytes, '-')), String(or(b.settings, '-')), String(or(b.embed_mb, '-'))];
    }));
  }

  function renderClips(list) {
    $('clips-home').textContent = String(list.length);
    fillTable('clips-table', ['Shot / take', 'File', 'Seconds', 'Size', 'QA', 'Actions'], list.map(function (c) {
      var path = String(or(c.file, ''));
      var file = el('a', { href: '/api/file?path=' + enc(path), target: '_blank', rel: 'noopener', text: baseName(path) });
      return [String(or(c.shot, '?')) + ' / ' + String(or(c.take, '-')), file, String(or(c.seconds, '-')),
        fmtBytes(c.bytes), yesNo(c.qa),
        [btn('Sheet', { className: 'act act-sheet', 'data-gate': 'job', onclick: function () { clipCmd('clip_qa', 'Clip QA sheet', path); } }),
          btn('Visual QA', { className: 'act act-vqa', 'data-gate': 'job', onclick: function () { clipCmd('visual_qa', 'Visual QA', path); } })]];
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
        note: 'Writes frames and a QA sheet for this clip into ' + out + '.',
        args: { clip: path, out_dir: out },
        onEnd: function () { return loadVideo(); }
      });
    }
    runCommand({
      title: title,
      command: 'visual_qa',
      risk: 'N W',
      note: 'Calls the visual QA model (NVIDIA, free tier, rate-limited) and writes the scores into ' + out + '.',
      fields: [
        { name: 'direction', label: 'Direction JSON', pattern: PAT.json, required: true,
          hint: 'path under the studio folder, ending .json' },
        { name: 'model', label: 'Vision model', options: VISION_MODELS, value: VISION_MODELS[0] }
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

  // Returns {scope, ids | reel} or a string with the reason it is not valid.
  function scopeArgs() {
    var scope = scopeOf();
    if (scope === 'shots') {
      var ids = $('video-ids').value.split(',').map(function (x) { return x.trim(); }).filter(Boolean);
      if (!ids.length) return 'Type at least one shot id, for example SHOT-01.';
      var bad = ids.filter(function (x) { return !PAT.shot.test(x); });
      if (bad.length) return 'Bad shot id: ' + bad[0];
      return { scope: 'shots', ids: ids };
    }
    if (scope === 'reel') {
      var n = $('video-reel').value.trim();
      if (!PAT.count.test(n) || Number(n) < 1) return 'Reel must be a number, 1 or more.';
      return { scope: 'reel', reel: Number(n) };
    }
    return { scope: 'all' };
  }

  function videoPrepare() {
    var batch = $('video-batch').value.trim();
    var sc = scopeArgs();
    if (!PAT.name.test(batch)) return showError('Batch name: lowercase letters, digits, _ or -, up to 40 characters.');
    if (typeof sc === 'string') return showError(sc);
    var shots = $('video-shotfile').value;
    if (!shots) return showError('Pick a shot file.');
    var args = { shots: shots, batch: batch };
    var root = $('video-keyframes').value.trim();
    if (root) args.keyframes = root; // empty = the server default (flow/adhyay_01/keyframes_h3)
    Object.keys(sc).forEach(function (k) { args[k] = sc[k]; });
    runCommand({
      title: '1 Prepare batch (no GPU)',
      command: 'run_kaggle_prepare',
      risk: 'W',
      note: 'Writes colab_batches\\' + batch + '\\ only. No GPU, no Colab, no paid call.',
      args: args,
      onEnd: function () { return loadVideo(); }
    });
  }

  function h3Run() {
    var sc = scopeArgs();
    if (typeof sc === 'string') return showError(sc);
    var args = { story: $('video-shotfile').value };
    Object.keys(sc).forEach(function (k) { args[k] = sc[k]; });
    runCommand({
      title: 'h3 prepare (no GPU)',
      command: 'h3_prepare',
      risk: 'W',
      note: 'h3 prepare-only. Writes the h3 plan files. Execute is not exposed in v1.',
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
      S.h3Msg = String(or(h.message, 'h3 engine not built yet'));
      fill(box, [badge(S.h3Ok ? 'ok' : 'notrun', S.h3Ok ? 'AVAILABLE' : 'NOT BUILT'), ' ',
        S.h3Ok ? 'Prepare-only mode. Execute is not exposed in v1.' : S.h3Msg]);
      cmd.textContent = String(or(h.command_preview, 'command id ' + or(h.command, 'h3_prepare') + ', module ' + or(h.module, '-')));
      cmd.hidden = !S.h3Ok;
    } catch (e) {
      S.h3Ok = false;
      S.h3Msg = 'h3 status unavailable';
      fill(box, [badge('failed', 'ERROR'), ' ', errText(e)]);
      cmd.hidden = true;
    }
    applyGates();
  }

  async function loadColab(quiet) {
    var checkBtn = $('colab-check');
    checkBtn.disabled = true;
    checkBtn.textContent = 'Checking (up to 60 s)...';
    try {
      var c = await api('GET', '/api/colab');
      renderColab(c);
      return c;
    } catch (e) {
      S.colabOk = false;
      $('colab-balance').textContent = 'unknown (check failed)';
      if (!quiet) showError('Colab check failed: ' + errText(e));
      return null;
    } finally {
      checkBtn.disabled = false;
      checkBtn.textContent = 'Check Colab';
      applyGates();
    }
  }

  function renderColab(c) {
    var cc = c || {};
    var sessions = Array.isArray(cc.sessions) ? cc.sessions : null;
    if (sessions === null) {
      fillTable('colab-sessions', ['Session', 'GPU', 'Status', 'Action'],
        [['(could not read the session list from the Colab CLI)', '-', '-', '-']]);
    } else {
      fillTable('colab-sessions', ['Session', 'GPU', 'Status', 'Action'], sessions.map(function (s) {
        var name = String(or(s.name, '?'));
        return [name, String(or(s.gpu, '-')), badgeFor(or(s.status, 'unknown')),
          [btn('Stop session ' + name, { className: 'act act-stop-session', onclick: function () { stopSession(name); } }),
            risk('OPS')]];
      }));
    }
    var usageOk = !(cc.read_ok && cc.read_ok.usage === false);
    var num = typeof cc.balance === 'number' ? cc.balance : NaN;
    S.colabOk = isFinite(num);
    S.colabBalance = S.colabOk ? num : null;
    $('colab-balance').textContent = S.colabOk ? String(num)
      : (usageOk ? 'unknown (no readable balance)' : 'unknown (colab usage not readable)');
    var rates = cc.rate_units_per_hour || {};
    var rateText = Object.keys(rates).map(function (k) { return k + ' ' + rates[k] + ' units/h'; }).join(', ');
    $('colab-rate').textContent = (rateText || 'unknown') + (cc.cap_units ? '; cap ' + cc.cap_units + ' units per run' : '');
    applyGates();
  }

  function colabRun() {
    var batch = $('video-batch').value.trim();
    if (!PAT.name.test(batch)) return showError('Batch name: lowercase letters, digits, _ or -, up to 40 characters.');
    var cap = (S.status && S.status.spend_cap_units) || 15;
    runCommand({
      title: 'CONFIRM SPEND',
      command: 'colab_run',
      risk: '$',
      note: 'Starts a Colab GPU session for batch ' + batch + '. Nothing starts until you type the confirm text.',
      fields: [
        { name: 'gpu', label: 'GPU', options: GPUS, value: 'G4', hint: 'G4 is the default. A100 is also proven.' },
        { name: 'session', label: 'Session name', pattern: PAT.session, required: true, value: 't0-kaliya',
          hint: 'letters, digits, _ or -, up to 40' }
      ],
      args: function (v) { return { batch: batch, gpu: v.gpu, session: v.session }; },
      summary: function (v) {
        return [
          'GPU ' + v.gpu + ', session ' + v.session + ', batch ' + batch,
          'Cap ' + cap + ' units per execute. Balance at the last check: ' + (S.colabBalance === null ? 'unknown' : S.colabBalance) + '.',
          'Stop rule: the runner stops the session only after every clip is home.'
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
    } catch (e) { showError(errText(e)); }
  }

  async function afterStop(name) {
    var c = await loadColab(true);
    if (!c) return showError('Could not re-check Colab after stopping ' + name + '. Check Colab by hand.');
    var still = (Array.isArray(c.sessions) ? c.sessions : []).some(function (s) { return s.name === name; });
    if (still) {
      showError('STOP FAILED: session ' + name + ' is still listed on Colab. The VM may still be running. ' +
        'Stop it by hand on Colab.');
    } else {
      showMsg('Session ' + name + ' is no longer listed on Colab.');
    }
  }

  // ---------- Export ----------
  async function loadExport() {
    var reel = $('export-reel').value.trim();
    if (!PAT.count.test(reel) || Number(reel) < 1) return showError('Reel must be a number, 1 or more.');
    try {
      var d = await api('GET', '/api/export?reel=' + enc(reel));
      var clips = (d.clips_in_order || []).map(function (c) {
        if (typeof c === 'string') return el('li', { text: c });
        return el('li', { text: String(or(c.shot, '?')) + (c.take ? ' (take ' + c.take + ')' : ' (no take picked)') });
      });
      fill($('export-clips'), clips.length ? clips : [el('li', { text: '(no clips for reel ' + reel + ')' })]);
      var a = d.assembly;
      var notBuilt = !a || String(a).toLowerCase() === 'not built';
      fill($('export-assembly'), notBuilt
        ? [badge('notrun', 'NOT BUILT'), ' ' + String(or(d.assembly_note, 'No assembly script yet (gap G12). Nothing is assembled.'))]
        : [typeof a === 'string' ? a : JSON.stringify(a, null, 2)]);
      var files = d.reel_files || [];
      fill($('export-files'), files.length
        ? files.map(function (f) { return el('div', { text: typeof f === 'string' ? f : String(or(f.name, '?')) }); })
        : ['none yet']);
    } catch (e) { showError(errText(e)); }
  }

  // ---------- Init ----------
  function init() {
    document.querySelectorAll('.navbtn').forEach(function (b) {
      b.addEventListener('click', function () { showSection(b.getAttribute('data-section')); });
    });
    document.querySelectorAll('.tabbtn').forEach(function (b) {
      b.addEventListener('click', function () { renderImgTab(b.getAttribute('data-tab')); });
    });
    fill($('story-model'), WRITER_NAMES.map(function (m) { return el('option', { value: m, text: m + ' (free, OpenRouter)' }); }));
    var ay = [];
    for (var i = 1; i <= 12; i += 1) ay.push(el('option', { value: String(i), text: String(i) }));
    fill($('img-adhyay'), ay);
    $('img-adhyay').value = '1';
    $('story-slug').addEventListener('change', function () { selectSlug($('story-slug').value, ''); });
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
    showSection((location.hash || '#story').slice(1));
    tick();
    setInterval(tick, POLL_MS);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
