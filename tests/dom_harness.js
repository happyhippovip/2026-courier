// node dom_harness.js <cannon.js> <status.json> [polls]  ->  JSON-Log aller DOM-Schreibzugriffe (ohne echtes DOM, ohne Netz)
const fs = require('fs'), vm = require('vm');
const [js, st, polls = '3'] = process.argv.slice(2);
const status = JSON.parse(fs.readFileSync(st, 'utf8')), log = [], els = {}, every = [], once = [];
const chain = (id, path) => new Proxy(function () {}, {
  get: (_, k) => typeof k === 'symbol' ? (k === Symbol.toPrimitive ? () => '' : undefined) : chain(id, path + '.' + k),
  apply: (_, __, a) => { log.push([id, 'call:' + path, a.map(String).join('|')]); return chain(id, path + '()'); },
  set: (_, k, v) => { log.push([id, path + '.' + String(k), String(v)]); return true; } });
const el = id => els[id] || (els[id] = new Proxy({ textContent: '', value: id === 'mode' ? 'UNENDLICH' : id === 'count' ? '1000000' : '', append() {}, replaceChildren() {} }, {
  get: (t, k) => { if (typeof k === 'symbol') return k === Symbol.toPrimitive ? () => '' : undefined; if (k === 'addEventListener') return () => {}; return k in t ? t[k] : chain(id, String(k)); },
  set: (t, k, v) => { log.push([id, String(k), String(v)]); t[k] = v; return true; } }));
const doc = { getElementById: el, querySelector: s => el(s), querySelectorAll: () => [], body: el('body'), documentElement: el('html'),
  readyState: 'complete', cookie: '', addEventListener: (e, f) => { if (e === 'DOMContentLoaded') f(); },
  createElement: (...a) => { log.push(['document', 'createElement', a.join()]); return el('__new'); } };
const store = { getItem: () => null, setItem() {}, removeItem() {} };
const ctx = { document: doc, location: { search: '', hash: '', href: 'http://localhost/', origin: 'http://localhost', pathname: '/', hostname: 'localhost' },
  localStorage: store, sessionStorage: store, URLSearchParams, console, navigator: { clipboard: { writeText: async () => {} } },
  fetch: async u => ({ ok: true, status: 200, json: async () => /status/.test(u) ? status : {}, text: async () => '' }),
  setInterval: f => { every.push(f); return 1; }, setTimeout: f => { once.push(f); return 1; }, clearInterval() {}, clearTimeout() {} };
ctx.window = ctx; vm.createContext(ctx);
process.on('unhandledRejection', e => log.push(['!', 'unhandledRejection', String(e)]));
const tick = () => new Promise(r => setImmediate(r));
(async () => {
  try { vm.runInContext(fs.readFileSync(js, 'utf8'), ctx); } catch (e) { log.push(['!', 'error', String(e)]); }
  for (let i = 0; i < +polls; i++) {
    await tick(); await tick();
    for (const f of [...every, ...once.splice(0)]) { try { await f(); } catch (e) { log.push(['!', 'error', String(e)]); } }
  }
  await tick(); await tick(); console.log(JSON.stringify(log));
})();
