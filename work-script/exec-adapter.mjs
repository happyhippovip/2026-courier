// Bounded local exec adapter (stub-tested only; not a live Muse binding).
// - argv array only, never a shell: no interpolation of user text.
// - cwd must be allow-listed; approval must be explicit (never derived).
// - stdout/stderr drained with byte caps; timeout kills ONLY the own child.
// - exit 0 or much text alone is not success: a completion marker is required.
// - same idempotencyKey redelivers the stored result instead of re-executing.
import {spawn} from 'node:child_process';

export const FORBIDDEN_FLAGS = ['--yolo', '--disable-sandbox', '-- dangerously-disable-permissions'];
export const ERROR_CLASSES = ['success', 'temporary-unavailable', 'auth-required',
  'payment-required', 'timeout-exit', 'malformed-result', 'cancelled',
  'unknown-outcome', 'blocked-local', 'error-exit'];

export function errorClassOf({status, exitCode, reason}) {
  if (status === 'COMPLETE') return 'success';
  if (status === 'TIMEOUT') return 'temporary-unavailable';
  if (status === 'ABORTED') return 'cancelled';
  if (status === 'BLOCKED') return 'blocked-local';
  if (exitCode === 4) return 'auth-required';
  if (exitCode === 5) return 'payment-required';
  if (exitCode === null || exitCode === undefined) return 'unknown-outcome';
  if (exitCode !== 0) return reason === 'timeout' ? 'temporary-unavailable' : 'error-exit';
  return 'malformed-result'; // exit 0 without a valid completion marker
}
const KILL_GRACE_MS = 500;

export function createExecAdapter({command, baseArgs = [], allowedCwds = [],
  approval = null, timeoutMs = 10_000, maxBytes = 65536,
  spawnImpl = spawn, now = Date.now, killGraceMs = KILL_GRACE_MS} = {}) {
  if (!command) throw new Error('command required');
  const running = new Map(); // execId -> {child, taskId, attemptId}
  const results = new Map(); // idempotencyKey -> result
  const pending = new Map(); // idempotencyKey -> done promise (concurrent same-key starts share one child)
  let serial = 0;

  function blocked(reason, extra = {}) {
    return {status: 'BLOCKED', reason, errorClass: 'blocked-local', exitCode: null, timedOut: false,
      aborted: false, truncated: false, markerFound: false,
      stdout: '', stderr: '', durationMs: 0, redelivered: false, ...extra};
  }

  function start({argvExtra = [], cwd, stdinText = null, idempotencyKey,
    expectMarker, taskId = null, attemptId = null, timeout = timeoutMs,
    externalSignal = null} = {}) {
    if (!approval || approval.granted !== true) return {execId: null, ...blockedResult(blocked('approval')), done: async () => blocked('approval'), cancel: async () => ({cancelled: false, reason: 'not-started'})};
    if (!allowedCwds.includes(cwd)) return deadHandle(blocked('cwd'));
    const argv = [...baseArgs, ...argvExtra];
    const bad = argv.find(a => FORBIDDEN_FLAGS.includes(a));
    if (bad) return deadHandle(blocked('forbidden-flag', {flag: bad}));
    if (typeof idempotencyKey === 'string' && results.has(idempotencyKey)) {
      return deadHandle({...results.get(idempotencyKey), redelivered: true});
    }
    if (typeof idempotencyKey === 'string' && pending.has(idempotencyKey)) {
      const shared = pending.get(idempotencyKey);
      return {execId: null, done: async () => ({...(await shared), redelivered: true}),
        cancel: async () => ({cancelled: false, reason: 'shared-execution'})};
    }
    const execId = `exec-${++serial}`;
    let child;
    try {
      child = spawnImpl(command, argv, {cwd, stdio: ['pipe', 'pipe', 'pipe']});
    } catch (err) {
      return deadHandle({...blocked('spawn-failed', {error: String(err && err.message || err)}), execId});
    }
    const abortedFlag = {value: false};
    const rec = {child, taskId, attemptId, pid: child.pid ?? null, aborted: abortedFlag};
    running.set(execId, rec);
    if (stdinText !== null) { try { child.stdin.write(stdinText); } catch {} try { child.stdin.end(); } catch {} }
    else { try { child.stdin.end(); } catch {} }
    if (externalSignal) externalSignal.addEventListener?.('abort', () => cancel(execId), {once: true});

    const donePromise = (async () => {
      const t0 = now();
      let out = '', err = '', truncated = false, timedOut = false, aborted = false;
      const onData = (buf, isErr) => {
        let s = buf.toString('utf8');
        const room = maxBytes - (isErr ? err.length : out.length);
        if (room <= 0) { truncated = true; return; }
        if (s.length > room) { s = s.slice(0, room); truncated = true; }
        if (isErr) err += s; else out += s;
      };
      child.stdout.on('data', b => onData(b, false));
      child.stderr.on('data', b => onData(b, true));
      const exitCode = await new Promise(resolve => {
        let settled = false;
        const to = setTimeout(() => {
          if (settled) return; timedOut = true;
          try { child.kill('SIGTERM'); } catch {}
          setTimeout(() => { try { if (child.exitCode === null) child.kill('SIGKILL'); } catch {} }, killGraceMs);
        }, timeout);
        if (to.unref) to.unref();
        child.on('error', () => { if (!settled) { settled = true; clearTimeout(to); resolve(null); } });
        child.on('close', code => { if (!settled) { settled = true; clearTimeout(to); resolve(code); } });
      });
      try { child.stdout.destroy(); } catch {}
      try { child.stderr.destroy(); } catch {}
      running.delete(execId);
      pending.delete(idempotencyKey);
      const markerFound = typeof expectMarker === 'string' && expectMarker !== '' && out.includes(expectMarker);
      const wasAborted = rec.aborted.value;
      const complete = exitCode === 0 && markerFound && !timedOut && !wasAborted;
      const status = complete ? 'COMPLETE' : (wasAborted ? 'ABORTED' : timedOut ? 'TIMEOUT' : 'INCOMPLETE');
      const reason = complete ? null : (wasAborted ? 'cancelled' : timedOut ? 'timeout' : exitCode !== 0 ? `exit-${exitCode}` : 'no-completion-marker');
      const result = {status, reason,
        errorClass: errorClassOf({status, exitCode, reason}),
        exitCode, timedOut, aborted: wasAborted, truncated, markerFound,
        stdout: out, stderr: err, durationMs: now() - t0, redelivered: false, execId, taskId, attemptId};
      if (typeof idempotencyKey === 'string') results.set(idempotencyKey, {...result});
      return result;
    })();
    if (typeof idempotencyKey === 'string') pending.set(idempotencyKey, donePromise);
    // cancel() marks abort before signalling so the outcome reads ABORTED, never DONE.
    const handle = {execId, done: () => donePromise, cancel: () => cancel(execId)};
    rec.handle = handle;
    return handle;
  }

  function blockedResult(r) { return r; }
  function deadHandle(r) {
    return {execId: r.execId ?? null, done: async () => r, cancel: async () => ({cancelled: false, reason: 'not-started'})};
  }

  async function cancel(execId) {
    const rec = running.get(execId);
    if (!rec) return {cancelled: false, reason: 'unknown-owner'};
    if (rec.child.pid === undefined || rec.child.pid === null) return {cancelled: false, reason: 'no-pid'};
    rec.aborted.value = true; // outcome reads ABORTED even if the child exits 0 afterwards
    try { rec.child.kill('SIGTERM'); } catch (err) { return {cancelled: false, reason: String(err && err.message || err)}; }
    return {cancelled: true, pid: rec.child.pid, taskId: rec.taskId, attemptId: rec.attemptId};
  }

  async function run(opts) {
    const h = start(opts);
    return h.done();
  }

  return {start, run, cancel,
    get activeCount() { return running.size; },
    // 16: redeliver the stored result for a lost ack instead of re-executing.
    redeliver(idempotencyKey) {
      const r = results.get(idempotencyKey);
      return r ? {...r, redelivered: true} : null;
    }};
}
