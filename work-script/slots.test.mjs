import test from 'node:test';
import assert from 'node:assert/strict';
import {createSlots, DEFAULT_CAPACITIES} from './slots.mjs';

test('20: NORMAL admits at most one execution', () => {
  const s = createSlots();
  assert.equal(s.capacity('NORMAL'), 1);
  assert.deepEqual(s.acquire('NORMAL', 'e1'), {granted: true});
  assert.deepEqual(s.acquire('NORMAL', 'e2'), {granted: false, reason: 'slot-busy'});
  assert.equal(s.heldCount('NORMAL'), 1);
  assert.deepEqual(s.release('NORMAL', 'e1'), {released: true});
  assert.deepEqual(s.acquire('NORMAL', 'e2'), {granted: true});
});

test('20: TURBO admits two, third waits for a free slot', () => {
  const s = createSlots();
  assert.equal(s.capacity('TURBO'), 2);
  assert.equal(s.acquire('TURBO', 'a').granted, true);
  assert.equal(s.acquire('TURBO', 'b').granted, true);
  assert.deepEqual(s.acquire('TURBO', 'c'), {granted: false, reason: 'slot-busy'});
  assert.deepEqual(s.release('TURBO', 'a'), {released: true});
  assert.equal(s.acquire('TURBO', 'c').granted, true);
  assert.equal(s.heldCount('TURBO'), 2);
});

test('20: unknown mode and missing identity are refused, release is exact', () => {
  const s = createSlots();
  assert.deepEqual(s.acquire('ULTRA', 'x'), {granted: false, reason: 'unknown-mode'});
  assert.deepEqual(s.acquire('NORMAL', ''), {granted: false, reason: 'no-identity'});
  assert.deepEqual(s.release('NORMAL', 'ghost'), {released: false});
  s.acquire('NORMAL', 'e1');
  assert.deepEqual(s.release('TURBO', 'e1'), {released: false}); // wrong mode releases nothing
  assert.equal(s.heldCount('NORMAL'), 1);
});

test('20: duplicate acquire of the same execution counts once', () => {
  const s = createSlots();
  assert.deepEqual(s.acquire('NORMAL', 'e1'), {granted: true});
  assert.deepEqual(s.acquire('NORMAL', 'e1'), {granted: true, duplicate: true});
  assert.equal(s.heldCount('NORMAL'), 1);
});

test('20: modes are independent pools', () => {
  const s = createSlots();
  assert.equal(DEFAULT_CAPACITIES.NORMAL, 1);
  assert.equal(DEFAULT_CAPACITIES.TURBO, 2);
  s.acquire('NORMAL', 'n1');
  assert.equal(s.acquire('TURBO', 't1').granted, true);
  assert.equal(s.acquire('TURBO', 't2').granted, true);
  assert.equal(s.heldCount('NORMAL'), 1);
});

test('RACE-B: concurrent reserve of one slot yields exactly one owner, no sleep', async () => {
  const s = createSlots();
  const outs = await Promise.all(['w1', 'w2', 'w3', 'w4', 'w5'].map(w => Promise.resolve(s.acquire('NORMAL', w))));
  assert.equal(outs.filter(o => o.granted).length, 1);
  assert.equal(s.heldCount('NORMAL'), 1);
});
