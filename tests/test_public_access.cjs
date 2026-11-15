const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {spawnSync} = require('node:child_process');
const root = path.resolve(__dirname, '..');
for (const name of ['dh20', 'golden']) {
  const result = spawnSync(process.execPath, [path.join(__dirname, `test_${name}.mjs`)], {encoding: 'utf8'});
  assert.equal(result.status, 0, result.stderr || result.stdout);
}
async function checkLoader(name, fail) {
  let removed = false, mounted = false;
  const nodes = [];
  const target = {hidden: true, busy: false,
    setAttribute(k) {if (k === 'aria-busy') this.busy = true;},
    removeAttribute(k) {if (k === 'aria-busy') this.busy = false;},
    replaceChildren() {nodes.length = 0;}, append(...els) {nodes.push(...els);}};
  const contentId = name === 'dh20' ? 'd2Content' : 'goldenContent';
  const study = JSON.parse(fs.readFileSync(path.join(root, `${name}-study.json`)));
  let reloaded = false;
  const context = vm.createContext({
    document: {getElementById(id) {return id === contentId ? target : {remove() {removed = true;}};},
      createElement() {return {setAttribute() {}};}},
    location: {reload() {reloaded = true;}},
    fetch: async url => {assert.equal(url, `${name}-study.json?v=20261115-public1`); return {ok: !fail, json: async () => study};},
    loadModule: async () => ({mount: async (el, data) => {assert.equal(el, target); assert.equal(data, study); mounted = true;}})
  });
  // VM import substitution avoids requiring an experimental module loader for this browser entry point.
  const source = fs.readFileSync(path.join(root, `${name}-gate.js`), 'utf8').replace(/\bimport\(/g, 'loadModule(');
  await vm.runInContext(source, context);
  assert(removed); assert.equal(target.hidden, false); assert.equal(target.busy, false);
  assert.equal(mounted, !fail);
  if (fail) {assert.match(nodes[1].textContent, /temporarily unavailable/); nodes[2].onclick(); assert(reloaded);}
  const html = fs.readFileSync(path.join(root, `${name}.html`), 'utf8');
  assert(!/type="password"|Unlock|PRIVATE ACCESS|ENCRYPTED ACCESS/.test(html));
  assert(!new RegExp(`id="${contentId}"[^>]*hidden`).test(html));
}
(async () => {
  for (const name of ['dh20', 'golden']) {await checkLoader(name, false); await checkLoader(name, true);}
  console.log('Public access checks passed: automatic entry, unavailable study, retry and unchanged system rules.');
})().catch(error => {console.error(error); process.exitCode = 1;});
