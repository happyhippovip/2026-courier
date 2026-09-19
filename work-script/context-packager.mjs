// Minimal reproducible task context: references and freshness flags only.
// Never full chat, repo, or result history. Missing/stale/oversized inputs
// are flagged, not silently fixed. Oversized files are referenced, not hashed.
import {createHash} from 'node:crypto';

export const FILE_HARD_CAP = 1024 * 1024; // never hash beyond this

export function buildContext({task, acceptance = null, readScope = [], writeScope = [],
  files = [], results = [], constraints = [], doNotRepeat = [], expectedOutput = null,
  readFile = null, fileCap = 65536} = {}) {
  if (!task || !task.id) throw new Error('task.id required');
  const flags = {stale: [], missing: [], oversized: [], droppedIrrelevant: 0};
  const relevantFiles = files.map(f => {
    const entry = {path: f.path, bytes: null, sha256: null, status: 'ok'};
    let data = null;
    try { data = readFile ? readFile(f.path) : null; } catch { data = null; }
    if (data === null || data === undefined) { entry.status = 'missing'; flags.missing.push(f.path); return entry; }
    const bytes = Buffer.isBuffer(data) ? data : Buffer.from(String(data));
    entry.bytes = bytes.length;
    if (bytes.length > fileCap) { entry.status = 'oversized'; flags.oversized.push(f.path); return entry; }
    if (bytes.length <= FILE_HARD_CAP)
      entry.sha256 = createHash('sha256').update(bytes).digest('hex');
    if (f.recordedHash && entry.sha256 && f.recordedHash !== entry.sha256) {
      entry.status = 'stale'; flags.stale.push(f.path);
    }
    return entry;
  });
  const relevantResults = [];
  for (const r of results) {
    if (r.relevant) relevantResults.push({id: r.id, summary: r.summary || ''});
    else flags.droppedIrrelevant++;
  }
  return {package: {TASK_ID: task.id, GOAL: task.goal || null, EXACT_TASK: task.text || null,
      INPUT_REVISION: task.inputRevision || null, ACCEPTANCE: acceptance,
      READ_SCOPE: readScope, WRITE_SCOPE: writeScope, RELEVANT_FILES: relevantFiles,
      RELEVANT_RESULTS: relevantResults, KNOWN_CONSTRAINTS: constraints,
      DO_NOT_REPEAT: doNotRepeat, EXPECTED_OUTPUT: expectedOutput}, flags};
}
