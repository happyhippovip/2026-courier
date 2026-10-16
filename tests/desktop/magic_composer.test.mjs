import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  COPY,
  FILE_MAX,
  addFiles,
  normalizeGoal,
  buildReview,
  canReview,
  createTaskId,
  executionHint,
  fileSummary,
  formatBytes,
  goalBlockReason,
  pathMarks,
  permissionHint,
} from '../../product/magic-composer/model.mjs';

test('a goal is the trimmed sentence, ready only when it has text', () => {
  assert.equal(goalBlockReason('  '), COPY.emptyGoal);
  assert.equal(canReview('   '), false);
  assert.equal(canReview('Erstelle mir einen Bericht aus diesen Dateien.'), true);
  assert.equal(normalizeGoal('  Ein Satz.\nNoch einer.  '), 'Ein Satz.\nNoch einer.');
});

test('an oversized goal is refused with the limit', () => {
  const huge = 'a'.repeat(4001);
  assert.equal(canReview(huge), false);
  assert.match(goalBlockReason(huge), /4000/);
});

test('task ids match the courier task- plus 32 hex form', () => {
  const id = createTaskId(new Uint8Array(16).fill(0xab));
  assert.equal(id, `task-${'ab'.repeat(16)}`);
  assert.match(createTaskId(crypto.getRandomValues(new Uint8Array(16))), /^task-[0-9a-f]{32}$/);
  assert.throws(() => createTaskId(new Uint8Array(8)), /16 bytes/);
});

test('files keep name and size only, and stop at twelve', () => {
  const incoming = Array.from({ length: 14 }, (_, i) => ({
    name: `datei-${i}.txt`,
    size: 2048,
    type: 'text/plain',
    content: 'nicht übernehmen',
  }));
  const result = addFiles([], incoming);
  assert.equal(result.overflow, true);
  assert.equal(result.files.length, FILE_MAX);
  assert.deepEqual(result.files[0], { name: 'datei-0.txt', size: 2048, type: 'text/plain' });
  assert.equal(formatBytes(2048), '2 KB');
  assert.equal(fileSummary([]), COPY.noFiles);
});

test('review tells the truth about files, voice, and the wait for permission', () => {
  const review = buildReview({
    text: '  Erstelle mir einen Bericht aus diesen Dateien. ',
    files: [{ name: 'bericht.pdf', size: 2400, type: 'application/pdf' }],
    voiceUsed: true,
  });
  assert.equal(review.goal, 'Erstelle mir einen Bericht aus diesen Dateien.');
  assert.match(review.files, /bericht\.pdf/);
  assert.equal(review.voice, COPY.voiceUsed);
  assert.match(review.execution, /Task-ID/);
  assert.match(review.execution, /Freigabe/);
  assert.match(review.permission, /Kein Upload/);
  assert.match(review.permission, /Mikrofon war nur für die Eingabe an/);
});

test('execution hints never claim the work is already running', () => {
  for (const phase of ['compose', 'review', 'receipt']) {
    const hint = executionHint(phase);
    assert.match(hint, /Freigabe/);
    assert.doesNotMatch(hint, /läuft|gestartet|erledigt|ausgeführt/i);
  }
});

test('permission hints stay specific to the choice the person just made', () => {
  assert.match(permissionHint(), /Datei/);
  assert.match(permissionHint(), /Mikrofon/);
  assert.match(permissionHint({ files: [{ name: 'a.txt' }], voice: 'idle' }), /Kein Upload/);
  assert.match(permissionHint({ voice: 'ask' }), /nur für diese Eingabe/i);
  assert.match(permissionHint({ voice: 'listening' }), /Mikrofon ist an/);
  assert.match(permissionHint({ voice: 'denied' }), /nicht erlaubt/);
  assert.match(permissionHint({ voice: 'unsupported' }), /nicht verfügbar/);
});

test('the path marks typing, optional file and voice, then review, send, and task id', () => {
  const empty = pathMarks({ phase: 'compose', text: '', files: [], voiceUsed: false });
  assert.equal(empty.find((step) => step.current).id, 'type');
  assert.equal(empty.find((step) => step.id === 'file').optional, true);
  assert.equal(empty.find((step) => step.id === 'voice').optional, true);

  const ready = pathMarks({
    phase: 'compose',
    text: 'Bericht',
    files: [{ name: 'a.txt', size: 1, type: '' }],
    voiceUsed: true,
  });
  assert.equal(ready.find((step) => step.id === 'file').done, true);
  assert.equal(ready.find((step) => step.id === 'voice').done, true);
  assert.equal(ready.find((step) => step.id === 'review').next, true);

  const review = pathMarks({ phase: 'review', text: 'Bericht', files: [], voiceUsed: false });
  assert.equal(review.find((step) => step.current).id, 'review');
  assert.equal(review.find((step) => step.id === 'send').next, true);

  const receipt = pathMarks({ phase: 'receipt', text: 'Bericht', files: [], voiceUsed: false });
  assert.equal(receipt.find((step) => step.current).id, 'task');
  assert.equal(receipt.find((step) => step.id === 'send').done, true);
});
