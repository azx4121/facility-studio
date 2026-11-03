/* Tutorial DOM-event contract. This is not browser layout or native GUI proof. */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const page = fs.readFileSync(path.join(__dirname, '../docs/tutorial/START_HERE.html'), 'utf8');
const content = page.match(/<script type="application\/json" id="tutorial-data">([\s\S]*?)<\/script>/)[1];
const script = [...page.matchAll(/<script>([\s\S]*?)<\/script>/g)].at(-1)[1];
let checks = 0;
function check(value, message) { checks++; assert.ok(value, message); }
function load(search = '', hash = '', saved = '{}') {
  const elements = new Map();
  const store = new Map([['facility-tutorial-v556-r1', saved]]);
  function element() {
    return {children: [], hidden: false, disabled: false, checked: false, value: '', textContent: '',
      classList: {toggle() {}}, setAttribute() {}, scrollIntoView() {},
      replaceChildren() { this.children = []; }, append(child) { this.children.push(child); },
      set id(value) { this._id = value; elements.set(value, this); }, get id() { return this._id; }};
  }
  for (const id of ['tutorial-data', 'title', 'subtitle', 'offline', 'language', 'all', 'print',
    'files-label', 'reset', 'previous', 'next', 'mark', 'done', 'progress-label', 'progress', 'nav', 'sheet', 'main']) {
    const node = element(); node.id = id;
  }
  elements.get('tutorial-data').textContent = content;
  const document = {documentElement: {}, body: element(), events: {},
    getElementById: id => elements.get(id), createElement: element,
    addEventListener(name, callback) { this.events[name] = callback; }};
  const location = {search, hash};
  const window = {print() { window.printed = true; }};
  const context = vm.createContext({document, window, location, URLSearchParams, Set,
    localStorage: {getItem: key => store.get(key), setItem: (key, value) => store.set(key, value)},
    history: {replaceState(a, b, hash) { location.hash = hash; }}});
  vm.runInContext(script, context);
  return {el: id => elements.get(id), document, location, window, store,
    visible: () => elements.get('sheet').children.filter(node => !node.hidden),
    clickAnchor(id) { let prevented = false; document.events.click({
      target: {closest: () => ({getAttribute: () => '#' + id})},
      preventDefault() { prevented = true; }}); return prevented; }};
}
for (const language of ['zh-Hant', 'en']) {
  const app = load('?language=' + language, '#capacity');
  check(app.document.documentElement.lang === language, 'URL language');
  check(app.visible().length === 1 && app.visible()[0].id === 'capacity', 'Deep link');
  check(app.el('nav').children.length === 24, 'All chapter navigation entries');
  check(app.el('next').disabled, 'Final step cannot advance');
  app.el('previous').onclick();
  check(app.visible()[0].id === 'pump_suction', 'Previous');
  app.el('next').onclick();
  check(app.visible()[0].id === 'capacity', 'Next');
  check(app.clickAnchor('start'), 'Intercept valid chapter link');
  check(app.visible()[0].id === 'start' && app.el('previous').disabled, 'First step');
  app.el('done').checked = true; app.el('done').onchange();
  check(app.el('progress').value === 1, 'Core progress');
  app.clickAnchor('lighting');
  app.el('done').checked = true; app.el('done').onchange();
  check(app.el('progress').value === 1, 'Optional reading does not advance core progress');
  app.el('language').value = language === 'en' ? 'zh-Hant' : 'en'; app.el('language').onchange();
  check(app.visible()[0].id === 'lighting', 'Language switch retains chapter');
  const persisted = load('', '#lighting', app.store.get('facility-tutorial-v556-r1'));
  check(persisted.el('progress').value === 1 && persisted.el('done').checked, 'Persisted reading state');
  app.el('all').onclick();
  check(app.visible().length === 24 && app.el('done').disabled, 'Read-all mode');
  app.el('done').checked = false; app.el('done').onchange();
  app.el('all').onclick();
  check(app.visible().length === 1 && app.el('done').checked, 'Read-all cannot mark wrong step');
  app.location.hash = '#air'; app.window.onhashchange();
  check(app.visible()[0].id === 'air', 'Hash navigation');
  app.el('print').onclick(); check(app.window.printed, 'Print action');
  app.el('reset').onclick(); check(app.el('progress').value === 0, 'Reset');
}
for (const saved of ['broken JSON', 'null', '{}']) {
  const app = load('?language=missing', '#missing', saved);
  check(app.document.documentElement.lang === 'zh-Hant' && app.visible()[0].id === 'start', 'Safe fallback');
}
console.log(JSON.stringify({passed: true, checks, scope: 'JavaScript DOM-event mock, not browser rendering or native GUI acceptance'}));
