// Deterministic admission gate: IMPORTED -> CLASSIFIED -> {STORE_ONLY, NEEDS_CONTEXT,
// HUMAN_DECISION, REUSE_RESULT, WAIT_DEPENDENCY, READY_CANDIDATE, INVALID}.
// No model calls. No mass classification. Same text is not the same task:
// identity is (project, normalized text) unless an explicit id is given.
// Privilege-escalating text never grants rights: it routes to HUMAN_DECISION.
export const VERDICTS = ['STORE_ONLY', 'NEEDS_CONTEXT', 'HUMAN_DECISION',
  'REUSE_RESULT', 'WAIT_DEPENDENCY', 'READY_CANDIDATE', 'INVALID'];

// Compact routing explanation: only verifiable rules/facts, no chain-of-thought.
export function why(rec, ctx = {}, lane = {}) {
  const c = classify(rec, ctx);
  const ready = c.verdict === 'READY_CANDIDATE';
  const unresolved = Number.isInteger(lane.unresolved) ? lane.unresolved : 0;
  return {
    WHY_READY: ready ? c.reason : `no:${c.verdict}/${c.reason}`,
    WHY_BLOCKED: ready ? 'none' : `${c.verdict}/${c.reason}`,
    WHY_WORKER: lane.worker || 'unassigned',
    WHY_NO_NEW_LANE: unresolved > 0 ? `unresolved:${unresolved}`
      : (ready ? 'admit-in-lane' : 'no-admissible-work'),
  };
}

export const DEFAULT_LIMITS = {maxBytes: 65536, maxInitialWave: 4};

const CONTROL_PATTERNS = [
  /grant\s+(yourself|me)\s+admin/i,
  /ignore\s+(permissions|permission|approval)/i,
  /\brm\s+-rf\s+\//,
  /disable\s+(sandbox|permission)/i,
  /--yolo\b/,
  /exfiltrat|send\s+.*secret/i,
];

export function identityKey(rec) {
  const project = rec.project || '';
  const text = typeof rec.text === 'string' ? rec.text.trim().replace(/\s+/g, ' ') : '';
  return `${project}\n${text}`;
}

// ctx: {completed:Set(taskIds), results:Map(identityKey->resultRef),
//       running:Map(identityKey->taskId), knownDeps:Set(taskIds),
//       capabilities:Set, scopes:Set, limits}
export function classify(rec, ctx = {}) {
  const limits = {...DEFAULT_LIMITS, ...(ctx.limits || {})};
  const out = (verdict, reason) => ({id: rec.id || null, verdict, reason});
  if (!rec || typeof rec !== 'object' || typeof rec.id !== 'string' || !rec.id)
    return out('INVALID', 'missing-id');
  if (rec.kind === 'context' || (!rec.kind && !rec.text))
    return {id: rec.id, verdict: 'STORE_ONLY', reason: 'no-executable-order'};
  if (typeof rec.text !== 'string' || !rec.text.trim())
    return out('INVALID', 'missing-text');
  if (typeof rec.bytes === 'number' && rec.bytes > limits.maxBytes)
    return out('INVALID', 'too-large');
  if (rec.raw !== undefined && typeof rec.raw === 'string') {
    try { JSON.parse(rec.raw); } catch { return out('INVALID', 'broken-envelope'); }
  }
  if (CONTROL_PATTERNS.some(re => re.test(rec.text)))
    return out('HUMAN_DECISION', 'self-privilege-or-foreign-command');
  const key = identityKey(rec);
  if (ctx.results && ctx.results.has(key))
    return {id: rec.id, verdict: 'REUSE_RESULT', reason: 'prior-result', ref: ctx.results.get(key)};
  if (ctx.running && ctx.running.has(key))
    return {id: rec.id, verdict: 'REUSE_RESULT', reason: 'already-running', ref: ctx.running.get(key)};
  if (rec.approval !== true)
    return out('HUMAN_DECISION', 'approval-missing');
  const deps = rec.depends_on === undefined ? [] : Array.isArray(rec.depends_on) ? rec.depends_on : [rec.depends_on];
  const completed = ctx.completed || new Set();
  const known = ctx.knownDeps || new Set();
  for (const d of deps) {
    if (!completed.has(d)) {
      if (!known.has(d)) return {id: rec.id, verdict: 'NEEDS_CONTEXT', reason: `unknown-dependency:${d}`};
      return {id: rec.id, verdict: 'WAIT_DEPENDENCY', reason: `waiting:${d}`};
    }
  }
  if (rec.scope && ctx.scopes && !ctx.scopes.has(rec.scope))
    return out('NEEDS_CONTEXT', 'scope-unknown');
  if (rec.capability && ctx.capabilities && !ctx.capabilities.has(rec.capability))
    return out('NEEDS_CONTEXT', 'capability-unknown');
  return {id: rec.id, verdict: 'READY_CANDIDATE', reason: 'admissible', identity: key};
}

// K07: first wave only. New tasks arise only from admitted need, capped.
// graph: {tasks:[{id, depends_on?, suppressedByResult?}], completed:[ids]}
// Returns {wave, deferred, suppressed}. Never materializes the whole graph.
export function firstWave(graph, completed = new Set(), maxInitialWave = DEFAULT_LIMITS.maxInitialWave) {
  const done = new Set([...(graph.completed || []), ...completed]);
  const wave = [], deferred = [], suppressed = [];
  for (const t of graph.tasks || []) {
    if (t.suppressedByResult && done.has(t.suppressedByResult)) { suppressed.push(t.id); continue; }
    const deps = t.depends_on || [];
    if (!deps.every(d => done.has(d))) { deferred.push(t.id); continue; }
    if (done.has(t.id)) { suppressed.push(t.id); continue; }
    if (wave.length < maxInitialWave) wave.push(t.id);
    else deferred.push(t.id);
  }
  return {wave, deferred, suppressed};
}
