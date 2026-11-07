// UI language helper (docs/UI_REDESIGN_PLAN_2026-11-07.md section 3.2). Loaded before app.js and pipeline.js.
// Strings live in i18n/en.json and i18n/mr.json. Marathi is a draft until a native speaker checks it.
(function () {
  'use strict';
  var LANGS = ['en', 'mr'];
  var STORE = 'studio.lang';
  var I = { lang: 'en', en: {}, mr: {}, missing: [], loaded: false };

  // status word -> key. A literal map, so every key stays visible to the tests (plan 3.4).
  var STATUS_KEY = {
    locked: 'status.locked', ready: 'status.ready', running: 'status.running',
    waiting_approval: 'status.waiting_approval', approved: 'status.approved', rejected: 'status.rejected',
    done: 'status.done', failed: 'status.failed', open: 'status.open', stopped: 'status.stopped',
    not_run: 'status.not_run'
  };

  // server (or client) error text -> plain key. First match wins (plan 3.5). Optional third item: the placeholder
  // that receives the captured text.
  var ERR_MAP = [
    [/^save the story first/, 'err.srv.save_story_first'],
    [/choose at least one output language/, 'err.srv.no_languages'],
    [/is already finished \(PACK\.md exists\): use (\S+)/, 'err.srv.pack_finished', 'name'],
    [/SOURCE\.md exists: tick overwrite/, 'err.srv.story_exists'],
    [/story is over 200 KB/, 'err.srv.story_too_big'],
    [/another job is running/, 'err.srv.job_running'],
    [/preview expired/, 'err.srv.preview_expired'],
    [/this preview was already used/, 'err.srv.preview_used'],
    [/unknown preview token/, 'err.srv.preview_unknown'],
    [/arguments changed since the preview/, 'err.srv.args_changed'],
    [/spend is OFF/, 'err.srv.spend_off'],
    [/^type exactly: (.+)$/, 'err.srv.type_exactly', 'word'],
    [/claude is off/, 'err.srv.claude_off'],
    [/out of date: restart/, 'err.srv.stale'],
    [/host not allowed|origin not allowed|X-UI/, 'err.srv.guard'],
    [/^no such story/, 'err.srv.no_story'],
    [/^no such pack|pack folder does not exist/, 'err.srv.no_pack'],
    [/no validator report/, 'err.srv.no_validator'],
    [/h3 engine not built yet/, 'err.srv.h3_missing'],
    [/must be an H3 story/, 'err.srv.h3_story_needed'],
    [/slug|pack name: lower-case/, 'err.srv.bad_name'],
    [/balance unknown|below 1\.5 x|above the cap/, 'err.srv.spend_refused'],
    [/unknown job/, 'err.srv.unknown_job'],
    [/Cannot reach the studio server/, 'err.net.down'],
    [/did not answer in 2 minutes/, 'err.net.timeout']
  ];

  function stored() {
    try {
      var v = window.localStorage.getItem(STORE);
      return LANGS.indexOf(v) >= 0 ? v : 'en';
    } catch (e) {
      return 'en';
    }
  }

  function load(lang) {
    return fetch('i18n/' + lang + '.json', { headers: { 'X-UI': '1' } })
      .then(function (r) { return r.ok ? r.json() : {}; })
      .then(function (d) { return d && typeof d === 'object' ? d : {}; })
      .catch(function () { return {}; });
  }

  I.t = function (key, vars) {
    var s = Object.prototype.hasOwnProperty.call(I[I.lang], key) ? I[I.lang][key] : undefined;
    if (s === undefined) {
      s = Object.prototype.hasOwnProperty.call(I.en, key) ? I.en[key] : undefined;
      if (s === undefined) {
        if (I.missing.indexOf(key) < 0) I.missing.push(key);
        return '[' + key + ']';
      }
      if (I.lang !== 'en' && I.missing.indexOf(I.lang + ':' + key) < 0) I.missing.push(I.lang + ':' + key);
    }
    if (!vars) return s;
    return s.replace(/\{(\w+)\}/g, function (m, k) {
      return vars[k] === undefined || vars[k] === null ? m : String(vars[k]);
    });
  };

  I.statusKey = function (status) {
    return Object.prototype.hasOwnProperty.call(STATUS_KEY, status) ? STATUS_KEY[status] : 'status.unknown';
  };

  I.serverError = function (msg) {
    var text = msg === undefined || msg === null ? '' : String(msg);
    for (var i = 0; i < ERR_MAP.length; i += 1) {
      var row = ERR_MAP[i];
      var m = row[0].exec(text);
      if (m) {
        var vars = null;
        if (row[2]) {
          vars = {};
          vars[row[2]] = m[1];
        }
        return { text: I.t(row[1], vars), raw: text };
      }
    }
    return { text: I.t('err.generic'), raw: text };
  };

  // Writes a string into an element. The text it wrote is remembered, so a later language switch
  // leaves alone any text that a script changed since (its owner re-renders that text).
  function setText(node, text) {
    node.textContent = text;
    node._i18nLast = text;
  }

  I.apply = function (root) {
    // no string table (the file did not load): keep the English that the page already shows
    if (!I.loaded || !Object.keys(I.en).length) return;
    var scope = root || document;
    Array.prototype.forEach.call(scope.querySelectorAll('[data-i18n]'), function (n) {
      if ('_i18nLast' in n && n.textContent !== n._i18nLast) return;
      setText(n, I.t(n.getAttribute('data-i18n')));
    });
    Array.prototype.forEach.call(scope.querySelectorAll('[data-i18n-attr]'), function (n) {
      n.getAttribute('data-i18n-attr').split(';').forEach(function (pair) {
        var i = pair.indexOf(':');
        if (i < 1) return;
        var name = pair.slice(0, i).trim();
        var key = pair.slice(i + 1).trim();
        if (name && key) n.setAttribute(name, I.t(key));
      });
    });
    Array.prototype.forEach.call(scope.querySelectorAll('[data-show-lang]'), function (n) {
      n.hidden = n.getAttribute('data-show-lang') !== I.lang;
    });
  };

  function markButtons() {
    LANGS.forEach(function (code) {
      var b = document.getElementById('ui-lang-' + code);
      if (b) b.setAttribute('aria-pressed', code === I.lang ? 'true' : 'false');
    });
  }

  I.setLang = function (lang) {
    if (LANGS.indexOf(lang) < 0) return;
    I.lang = lang;
    try {
      window.localStorage.setItem(STORE, lang);
    } catch (e) {
      // private window or blocked storage: the choice lasts for this page only
    }
    document.documentElement.lang = lang;
    markButtons();
    if (!I.loaded) return;
    I.apply(document);
    window.dispatchEvent(new CustomEvent('studio:lang', { detail: lang }));
  };

  I.ready = Promise.all([load('en'), load('mr')]).then(function (r) {
    I.en = r[0];
    I.mr = r[1];
    I.lang = stored();
    document.documentElement.lang = I.lang;
    I.loaded = true;
    I.apply(document);
    markButtons();
    LANGS.forEach(function (code) {
      var b = document.getElementById('ui-lang-' + code);
      if (b) b.addEventListener('click', function () { I.setLang(code); });
    });
  });

  window.I18N = I;
})();
