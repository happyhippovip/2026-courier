import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync, writeFileSync, readFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {buildContext} from './context-packager.mjs';

const task = {id: 't1', goal: 'G', text: 'Do it.', inputRevision: 'r7'};
const files = [{path: 'a.txt'}, {path: 'b.txt'}];
const readFile = p => ({'a.txt': 'hello', 'b.txt': 'world'}[p] ?? null);

test('K08: exact context is clean and complete', () => {
  const r = buildContext({task, acceptance: 'ok', readScope: ['fs'], writeScope: ['out'],
    files, results: [{id: 'res-1', summary: 'prior', relevant: true}],
    constraints: ['c1'], doNotRepeat: ['d1'], expectedOutput: 'done', readFile});
  assert.deepEqual(r.flags, {stale: [], missing: [], oversized: [], droppedIrrelevant: 0});
  assert.equal(r.package.TASK_ID, 't1');
  assert.equal(r.package.RELEVANT_FILES.length, 2);
  assert.equal(r.package.RELEVANT_RESULTS.length, 1);
  assert.ok(r.package.RELEVANT_FILES[0].sha256);
});

test('K08: thin context flags missing and stale, drops nothing silently', () => {
  const r = buildContext({task, files: [{path: 'gone.txt'}, {path: 'a.txt', recordedHash: '0'.repeat(64)}],
    results: [], readFile});
  assert.deepEqual(r.flags.missing, ['gone.txt']);
  assert.deepEqual(r.flags.stale, ['a.txt']);
});

test('K08: bloated context references huge file and drops irrelevant results', () => {
  const dir = mkdtempSync(join(tmpdir(), 'ctx-'));
  const big = join(dir, 'big.bin');
  writeFileSync(big, Buffer.alloc(200000, 7));
  const r = buildContext({task, files: [{path: big}], fileCap: 65536,
    results: [{id: 'r1', summary: 'useful', relevant: true},
      ...[2, 3, 4, 5, 6].map(i => ({id: `old-${i}`, summary: 'stale', relevant: false}))],
    readFile: p => { try { return readFileSync(p); } catch { return null; } }});
  assert.deepEqual(r.flags.oversized, [big]);
  assert.equal(r.flags.droppedIrrelevant, 5);
  assert.equal(r.package.RELEVANT_RESULTS.length, 1);
  assert.equal(r.package.RELEVANT_FILES[0].status, 'oversized');
  assert.equal(r.package.RELEVANT_FILES[0].sha256, null); // referenced, never hashed
});
