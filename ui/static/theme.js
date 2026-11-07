// Colour theme switch for the control panel (docs/UI_COLOUR_SYSTEM_GUIDE_2026-11-07_v2.md section 6).
// Choice in localStorage under studio.theme: system (default, follows the device), light, dark or reading (optional).
// tokens.css does the colouring; this file only sets data-theme on <html> and keeps the selector in step.
// The head script in index.html already applied the saved choice before first paint, so this runs after it.
(function () {
  'use strict';
  var THEMES = ['system', 'light', 'dark', 'reading'];
  var STORE = 'studio.theme';
  var root = document.documentElement;
  var select = document.getElementById('theme-select');
  var dark = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;

  function stored() {
    try {
      var v = window.localStorage.getItem(STORE);
      return THEMES.indexOf(v) >= 0 ? v : 'system';
    } catch (e) {
      return 'system';   // storage blocked: the device setting applies
    }
  }

  function save(theme) {
    try {
      window.localStorage.setItem(STORE, theme);
    } catch (e) {
      // blocked storage: the choice lasts for this page only
    }
  }

  // Keeps the browser's own colour (address bar, tabs) in step with the page background.
  function syncMeta() {
    if (!window.getComputedStyle) return;
    var bg = window.getComputedStyle(root).getPropertyValue('--app-bg').trim();
    var meta = document.querySelector('meta[name="theme-color"]');
    if (!meta && bg) {
      meta = document.createElement('meta');
      meta.setAttribute('name', 'theme-color');
      document.head.appendChild(meta);
    }
    if (meta && bg) meta.setAttribute('content', bg);
  }

  function apply(theme) {
    if (theme === 'system') root.removeAttribute('data-theme');   // no attribute: tokens.css follows prefers-color-scheme
    else root.setAttribute('data-theme', theme);
    if (select) select.value = theme;
    syncMeta();
  }

  apply(stored());

  if (select) {
    select.addEventListener('change', function () {
      var theme = THEMES.indexOf(select.value) >= 0 ? select.value : 'system';
      save(theme);
      apply(theme);
    });
  }

  // With the system choice the CSS switches by itself; this only refreshes the browser colour.
  if (dark) {
    var onDeviceChange = function () { syncMeta(); };
    if (dark.addEventListener) dark.addEventListener('change', onDeviceChange);
    else if (dark.addListener) dark.addListener(onDeviceChange);
  }
})();
