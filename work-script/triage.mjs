// Deterministic morning triage: group results, no model summary required.
// Priority for needs-human: AUTH, PAYMENT, HUMAN_DECISION, UNKNOWN_EFFECT,
// SECURITY, repeated failure, ordinary failure. One root-cause group yields
// one alert, never 20 identical messages. Causes are observed keys only.
const NEEDS_RANK = {AUTH_REQUIRED: 1, PAYMENT_REQUIRED: 2, SECURITY: 3,
  UNKNOWN_EFFECT: 4, HUMAN_DECISION: 5};

export function triage(results = []) {
  const groups = {DONE: [], FAILED: [], BLOCKED: [], HUMAN_GATE: [],
    UNKNOWN_OUTCOME: [], REUSED: [], NEEDS_REVIEW: []};
  const causeGroups = new Map();
  for (const r of results) {
    const g = groups[r.outcome] ? r.outcome : 'NEEDS_REVIEW';
    groups[g].push(r.id);
    if (r.outcome !== 'DONE' && r.outcome !== 'REUSED') {
      const key = `${r.cause || 'unknown-cause'}`;
      if (!causeGroups.has(key)) causeGroups.set(key, []);
      causeGroups.get(key).push(r.id);
    }
  }
  const needsHuman = [];
  for (const [cause, ids] of causeGroups) {
    const first = results.find(r => r.id === ids[0]);
    const rank = NEEDS_RANK[first.need] || (first.repeat ? 6 : 7);
    needsHuman.push({cause, count: ids.length, rank, sample: ids[0]});
  }
  needsHuman.sort((a, b) => a.rank - b.rank || b.count - a.count);
  return {groups, rootCauseGroups: [...causeGroups.keys()],
    duplicateAlertsSuppressed: [...causeGroups.values()].reduce((n, ids) => n + Math.max(0, ids.length - 1), 0),
    needsHuman};
}

export function nextReady(admitted = []) {
  return admitted.filter(a => a.verdict === 'READY_CANDIDATE').map(a => a.id);
}
