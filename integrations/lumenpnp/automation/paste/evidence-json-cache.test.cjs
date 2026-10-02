'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
const {createReader} = require('./evidence-json-cache.cjs');
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');

test('invocation reader rehashes each access and reuses only frozen parsed JSON for exact path+digest', t => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'evidence-json-cache-'));
  t.after(() => fs.rmSync(dir, {recursive:true, force:true}));
  const file = path.join(dir, 'record.json');
  fs.writeFileSync(file, '{"nested":{"value":7}}\n');
  let reads = 0;
  const countedFs = Object.assign({}, fs, {readFileSync: function () { reads++; return fs.readFileSync.apply(fs, arguments); }});
  const read = createReader(countedFs, crypto);
  const evidence = {path:file, sha256:sha(fs.readFileSync(file))};
  const first = read(evidence, true), second = read(evidence, true);
  assert.equal(reads, 2, 'each use re-reads the file before returning cached JSON');
  assert.strictEqual(first, second, 'same canonical path and digest reuse identity for continuation memoization');
  assert.equal(Object.isFrozen(first.nested), true);
  assert.throws(() => { first.nested.value = 8; }, TypeError);
  assert.equal(read(evidence, false), '{"nested":{"value":7}}\n');
  assert.equal(reads, 3, 'text reads also re-read and hash');
  fs.writeFileSync(file, '{"nested":{"value":8}}\n');
  assert.throws(() => read(evidence, true), /SHA-256 mismatch/);
  assert.equal(reads, 4, 'mutated bytes cannot be served from a prior cache entry');
  const updated = {path:file, sha256:sha(fs.readFileSync(file))};
  assert.notStrictEqual(read(updated, true), first, 'new digest gets a distinct parsed object');
});

test('reader does not cache parse failures', t => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'evidence-json-invalid-'));
  t.after(() => fs.rmSync(dir, {recursive:true, force:true}));
  const file=path.join(dir,'broken.json');fs.writeFileSync(file,'{');
  const read=createReader(fs,crypto), evidence={path:file,sha256:sha(fs.readFileSync(file))};
  assert.throws(()=>read(evidence,true),SyntaxError);
  assert.throws(()=>read(evidence,true),SyntaxError);
});
