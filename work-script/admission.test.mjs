import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {classify, firstWave, identityKey, VERDICTS, why} from './admission.mjs';

const evmap = JSON.parse(readFileSync(new URL('./evidence-map.fixture.json', import.meta.url)));
const evclass = change => evmap.entries.find(e => e.change === change).class;

test('K10: change types map to retest scope, UI/logo never invalidate ledger', () => {
  assert.ok(evmap.entries.length >= 12);
  assert.equal(evclass('ui-text'), 'NO_EFFECT_ON_EVIDENCE');
  assert.equal(evclass('logo-asset'), 'NO_EFFECT_ON_EVIDENCE');
  assert.equal(evclass('result-parser'), 'TARGETED_RETEST');
  assert.ok(evmap.entries.find(e => e.change === 'result-parser').retest.includes('result-tests'));
  assert.equal(evclass('adapter-exec'), 'TARGETED_RETEST');
  assert.equal(evclass('retry-backoff'), 'TARGETED_RETEST');
  assert.equal(evclass('verify-contract'), 'FULL_PATH_RETEST');
  assert.equal(evclass('scheduler-dispatch'), 'NEW_ACCEPTANCE_REQUIRED');
});

const fx = JSON.parse(readFileSync(new URL('./admission100.fixture.json', import.meta.url)));
const mkCtx = () => ({completed: new Set(fx.context.completed), knownDeps: new Set(fx.context.knownDeps),
  results: new Map(Object.entries(fx.context.results)), running: new Map(Object.entries(fx.context.running)),
  scopes: new Set(fx.context.scopes), capabilities: new Set(fx.context.capabilities)});
const byId = id => fx.records.find(r => r.id === id);
const verdict = id => classify(byId(id), mkCtx());

test('K06: 100 mixed records, not all READY, all verdicts reachable', () => {
  assert.equal(fx.records.length, 100);
  const counts = {};
  for (const r of fx.records) { const v = classify(r, mkCtx()).verdict; counts[v] = (counts[v] || 0) + 1; }
  assert.deepEqual(new Set(Object.keys(counts)), new Set(VERDICTS));
  assert.ok(counts.READY_CANDIDATE < 100);
  assert.equal(counts.READY_CANDIDATE, 30);
});

test('K06: spot verdicts per class', () => {
  assert.equal(verdict('ctx-00').verdict, 'STORE_ONLY');
  assert.equal(verdict('valid-00').verdict, 'READY_CANDIDATE');
  assert.deepEqual([verdict('duprun-00').verdict, verdict('duprun-00').reason], ['REUSE_RESULT', 'already-running']);
  assert.deepEqual([verdict('dupres-00').verdict, verdict('dupres-00').reason], ['REUSE_RESULT', 'prior-result']);
  assert.equal(verdict('noappr-00').verdict, 'HUMAN_DECISION');
  assert.equal(verdict('privesc-00').reason, 'self-privilege-or-foreign-command');
  assert.equal(verdict('unkdep-00').verdict, 'NEEDS_CONTEXT');
  assert.equal(verdict('waitdep-00').verdict, 'WAIT_DEPENDENCY');
  assert.equal(verdict('big-00').verdict, 'INVALID');
  assert.equal(verdict('bad-00').verdict, 'INVALID');
  assert.equal(verdict('scope-00').verdict, 'NEEDS_CONTEXT');
  assert.equal(verdict('cap-00').verdict, 'NEEDS_CONTEXT');
});

test('K06: deterministic repeat + same text distinct projects stay distinct', () => {
  const a = fx.records.map(r => classify(r, mkCtx()).verdict).join(',');
  const b = fx.records.map(r => classify(r, mkCtx()).verdict).join(',');
  assert.equal(a, b);
  assert.notEqual(identityKey({project: 'P1', text: 'Same words.'}), identityKey({project: 'P2', text: 'Same words.'}));
});

test('K07: A+B->C, chain, fan-in, blocked branch, suppression, wave cap', () => {
  let g = {tasks: [{id: 'A'}, {id: 'B'}, {id: 'C', depends_on: ['A', 'B']}], completed: []};
  assert.deepEqual(firstWave(g), {wave: ['A', 'B'], deferred: ['C'], suppressed: []});
  g = {tasks: [{id: 'A'}, {id: 'B', depends_on: ['A']}, {id: 'C', depends_on: ['B']}], completed: ['A']};
  assert.deepEqual(firstWave(g), {wave: ['B'], deferred: ['C'], suppressed: ['A']}); // done work is not rescheduled
  g = {tasks: [{id: 'A'}, {id: 'B'}, {id: 'C'}, {id: 'D', depends_on: ['A', 'B', 'C']}], completed: ['A', 'B', 'C']};
  assert.deepEqual(firstWave(g), {wave: ['D'], deferred: [], suppressed: ['A', 'B', 'C']});
  g = {tasks: [{id: 'X', depends_on: ['held']}, {id: 'Y'}], completed: []};
  assert.deepEqual(firstWave(g), {wave: ['Y'], deferred: ['X'], suppressed: []});
  g = {tasks: [{id: 'P', suppressedByResult: 'R-old'}, {id: 'Q'}], completed: ['R-old']};
  assert.deepEqual(firstWave(g), {wave: ['Q'], deferred: [], suppressed: ['P']});
  const many = {tasks: Array.from({length: 50}, (_, i) => ({id: `t${i}`}))};
  const w = firstWave(many, new Set(), 4);
  assert.equal(w.wave.length, 4); // no task explosion: cap holds at 50 queued
  assert.equal(w.deferred.length, 46);
  const five = {tasks: Array.from({length: 5}, (_, i) => ({id: `p${i}`}))};
  assert.deepEqual(firstWave(five, new Set(), 2).wave, ['p0', 'p1']); // analysis: 5 planned -> 2 first
});

test('PREP03: CRLF/BOM/tabs/unicode normalize deterministically, empty stays INVALID', () => {
  const a = {project: 'P', text: 'Line one\r\nLine two.'};
  const b = {project: 'P', text: 'Line one\nLine two.'};
  assert.equal(identityKey(a), identityKey(b));
  assert.equal(identityKey({project: 'P', text: ' hi'}), identityKey({project: 'P', text: 'hi'}));
  assert.equal(identityKey({project: 'P', text: 'a\tb'}), identityKey({project: 'P', text: 'a b'}));
  assert.notEqual(identityKey({project: 'P', text: 'Grüße'}), identityKey({project: 'P', text: 'Grusse'}));
  const ctx = {completed: new Set(), knownDeps: new Set()};
  assert.equal(classify({id: 'e1', kind: 'task', project: 'P', approval: true}, ctx).verdict, 'INVALID');
});

test('WHY: four verifiable lines for ready and blocked records', () => {
  const ctx = {completed: new Set(), knownDeps: new Set()};
  const r1 = why({id: 'v', kind: 'task', project: 'P', text: 'Do.', approval: true}, ctx, {worker: 'w1'});
  assert.equal(r1.WHY_READY, 'admissible');
  assert.equal(r1.WHY_BLOCKED, 'none');
  assert.equal(r1.WHY_WORKER, 'w1');
  assert.equal(r1.WHY_NO_NEW_LANE, 'admit-in-lane');
  const r2 = why({id: 'h', kind: 'task', project: 'P', text: 'Del.', approval: false}, ctx, {unresolved: 2});
  assert.equal(r2.WHY_BLOCKED, 'HUMAN_DECISION/approval-missing');
  assert.equal(r2.WHY_NO_NEW_LANE, 'unresolved:2');
});
