import test from 'node:test';
import assert from 'node:assert/strict';
import {createExecAdapter, FORBIDDEN_FLAGS, errorClassOf} from './exec-adapter.mjs';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

const STUB = fileURLToPath(new URL('./stub-proc.mjs', import.meta.url));
const CWD = path.dirname(STUB);
const base = extra => createExecAdapter({command: process.execPath,
  baseArgs: [STUB], allowedCwds: [CWD],
  approval: {granted: true, by: 'test-owner'}, timeoutMs: 3000,
  maxBytes: 65536, ...extra});
const run = (a, o) => a.run({cwd: CWD, expectMarker: 'COURIER_DONE',
  idempotencyKey: `k-${Math.random()}`, ...o});

test('13: stub success binds task/attempt/cwd and proves completion by marker', async () => {
  const a = base();
  const r = await run(a, {argvExtra: ['--mode=ok', '--marker=COURIER_DONE'],
    taskId: 't1', attemptId: 'a1', idempotencyKey: 'k-ok'});
  assert.equal(r.status, 'COMPLETE');
  assert.equal(r.exitCode, 0);
  assert.equal(r.markerFound, true);
  assert.equal(r.taskId, 't1');
  assert.equal(r.attemptId, 'a1');
  assert.ok(r.stdout.includes('COURIER_DONE'));
});

test('13: exit 0 without marker is INCOMPLETE, not success', async () => {
  const a = base();
  const r = await run(a, {argvExtra: ['--mode=partial'], idempotencyKey: 'k-partial'});
  assert.equal(r.status, 'INCOMPLETE');
  assert.equal(r.reason, 'no-completion-marker');
  assert.equal(r.exitCode, 0); // exit 0 alone proves nothing
  assert.ok(r.stdout.includes('half-output-no-marker')); // partial output preserved
});

test('13: failing exit reports exit code, big output is truncated and bounded', async () => {
  const a = base();
  const r = await run(a, {argvExtra: ['--mode=fail'], idempotencyKey: 'k-fail'});
  assert.equal(r.status, 'INCOMPLETE');
  assert.equal(r.reason, 'exit-3');
  const big = await run(a, {argvExtra: ['--mode=ok', '--bytes=70000'], idempotencyKey: 'k-big'});
  assert.equal(big.truncated, true);
  assert.ok(big.stdout.length <= 65536);
});

test('13: no shell interpolation — user text stays a single argv element', async () => {
  const a = base();
  const evil = '$(touch pwned);`id`';
  const r = await run(a, {argvExtra: [`--mode=ok`, `--marker=${evil}`],
    idempotencyKey: 'k-evil'});
  // marker with shell metachars is passed literally, never expanded: no match, no exec
  assert.equal(r.markerFound, false);
  assert.equal(r.status, 'INCOMPLETE');
});

test('14: abort of own run reads ABORTED with identity, unknown owner untouched', async () => {
  const a = base();
  const h = a.start({cwd: CWD, expectMarker: 'COURIER_DONE',
    argvExtra: ['--mode=slow', '--extra=5000'],
    taskId: 't9', attemptId: 'a9', idempotencyKey: 'k-abort', timeout: 8000});
  await new Promise(r => setTimeout(r, 200));
  const c = await h.cancel();
  assert.equal(c.cancelled, true);
  assert.equal(c.taskId, 't9');
  assert.equal(c.attemptId, 'a9');
  const r = await h.done();
  assert.equal(r.status, 'ABORTED');
  assert.equal(a.activeCount, 0);
  const unknown = await a.cancel('exec-9999');
  assert.deepEqual(unknown, {cancelled: false, reason: 'unknown-owner'});
});

test('14: timeout kills only the own child and stays bounded', async () => {
  const a = base();
  const t0 = Date.now();
  const r = await run(a, {argvExtra: ['--mode=slow', '--extra=30000'],
    idempotencyKey: 'k-timeout', timeout: 400});
  assert.equal(r.status, 'TIMEOUT');
  assert.ok(Date.now() - t0 < 5000);
  assert.equal(a.activeCount, 0);
});

test('15: yolo flags are refused, missing approval blocks without spawn', async () => {
  const a = base();
  for (const flag of FORBIDDEN_FLAGS) {
    const r = await run(a, {argvExtra: [flag], idempotencyKey: `k-${flag}`});
    assert.equal(r.status, 'BLOCKED');
    assert.equal(r.reason, 'forbidden-flag');
  }
  const noAppr = base({approval: null});
  const r = await run(noAppr, {argvExtra: ['--mode=ok'], idempotencyKey: 'k-noappr'});
  assert.equal(r.status, 'BLOCKED');
  assert.equal(r.reason, 'approval');
  const wrongCwd = await run(a, {cwd: '/tmp', argvExtra: ['--mode=ok'], idempotencyKey: 'k-cwd'});
  assert.equal(wrongCwd.status, 'BLOCKED');
  assert.equal(wrongCwd.reason, 'cwd');
});

test('5D: timeout after possible effect keeps partial output marked TIMEOUT, no auto-retry', async () => {
  const a = base();
  const r = await run(a, {argvExtra: ['--mode=slow', '--extra=30000'],
    idempotencyKey: 'k-5d', timeout: 1500});
  assert.equal(r.status, 'TIMEOUT');
  assert.ok(r.stdout.includes('partial-before-timeout')); // partial preserved...
  assert.equal(r.markerFound, false); // ...but marked incomplete, never success
  assert.equal(r.truncated, false);
  const again = a.redeliver('k-5d'); // lost ack redelivers same result...
  assert.equal(again.status, 'TIMEOUT');
  assert.equal(a.activeCount, 0); // ...without re-executing the effect
});

test('16: lost ack redelivers stored result instead of re-executing', async () => {
  const a = base();
  const first = await run(a, {argvExtra: ['--mode=ok'], idempotencyKey: 'k-redeliver'});
  assert.equal(first.status, 'COMPLETE');
  // simulate a second start with the same key: no new child, stored result returned
  const h = a.start({cwd: CWD, expectMarker: 'COURIER_DONE',
    argvExtra: ['--mode=ok'], idempotencyKey: 'k-redeliver'});
  const second = await h.done();
  assert.equal(second.redelivered, true);
  assert.equal(second.status, 'COMPLETE');
  assert.equal(a.activeCount, 0);
  const direct = a.redeliver('k-redeliver');
  assert.equal(direct.status, 'COMPLETE');
  assert.equal(a.redeliver('k-missing'), null);
});

test('K11: fake-adapter outcome matrix maps to provider-neutral error classes', async () => {
  const a = base();
  const cases = [
    [['--mode=ok'], 'k-e11a', 'success'],
    [['--mode=auth'], 'k-e11b', 'auth-required'],
    [['--mode=payment'], 'k-e11c', 'payment-required'],
    [['--mode=partial'], 'k-e11d', 'malformed-result'],
    [['--mode=fail'], 'k-e11e', 'error-exit'],
  ];
  for (const [extra, key, cls] of cases) {
    const r = await run(a, {argvExtra: extra, idempotencyKey: key});
    assert.equal(r.errorClass, cls, extra.join(' '));
  }
  const to = await run(a, {argvExtra: ['--mode=slow', '--extra=30000'], idempotencyKey: 'k-e11f', timeout: 400});
  assert.equal(to.errorClass, 'temporary-unavailable');
  const h = a.start({cwd: CWD, expectMarker: 'COURIER_DONE', argvExtra: ['--mode=slow', '--extra=5000'],
    idempotencyKey: 'k-e11g', timeout: 8000});
  await new Promise(r => setTimeout(r, 200));
  await h.cancel();
  assert.equal((await h.done()).errorClass, 'cancelled');
  const bad = createExecAdapter({command: '/nonexistent-proc-xyz', allowedCwds: [CWD],
    approval: {granted: true, by: 't'}});
  const sf = await bad.run({cwd: CWD, idempotencyKey: 'k-e11h'});
  assert.equal(sf.errorClass, 'unknown-outcome');
});

test('K11: same task over two adapter instances keeps Courier semantics', async () => {
  const a1 = base(), a2 = base();
  const args = {argvExtra: ['--mode=ok'], taskId: 'same', attemptId: 'same-1'};
  const r1 = await run(a1, {...args, idempotencyKey: 'k-x1'});
  const r2 = await run(a2, {...args, idempotencyKey: 'k-x2'});
  assert.equal(r1.status, r2.status);
  assert.equal(r1.status, 'COMPLETE');
});

test('K13: large stderr is bounded, stdout unaffected', async () => {
  const a = base();
  const r = await run(a, {argvExtra: ['--mode=ok', '--errbytes=70000'], idempotencyKey: 'k-errbig'});
  assert.ok(r.stderr.length <= 65536);
  assert.equal(r.truncated, true);
  assert.equal(r.status, 'COMPLETE'); // marker intact on stdout
});

test('RACE-A: concurrent same-key starts share one child, no double execution', async () => {
  const a = base();
  const opts = {cwd: CWD, expectMarker: 'COURIER_DONE', argvExtra: ['--mode=slow', '--extra=1500'],
    taskId: 't-race', attemptId: 'a-race', idempotencyKey: 'k-race', timeout: 8000};
  const [h1, h2] = [a.start(opts), a.start(opts)];
  const [r1, r2] = await Promise.all([h1.done(), h2.done()]);
  assert.equal(r1.status, 'COMPLETE');
  assert.equal(r2.status, 'COMPLETE');
  assert.equal(r2.redelivered, true); // second starter joined, never spawned
  assert.equal(a.activeCount, 0);
});
