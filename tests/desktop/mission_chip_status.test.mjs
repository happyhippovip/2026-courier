import assert from 'node:assert/strict';
import { test } from 'node:test';

import { chipStageView } from '../../courier_hub/static/mission_chip_status.mjs';

test('a failed chip is not painted as passed', () => {
  const view = chipStageView({
    overall_status: 'FAILED',
    verifier_result: { accepted: false, resolution: 'rejected' },
    checks: [
      { step: 1, passed: false, status: 'FAIL' },
      { step: 2, passed: false, status: 'FAIL' },
      { step: 3, passed: false, status: 'FAIL' },
    ],
  });
  assert.equal(view.complete, false);
  assert.equal(view.pill, 'FAILED');
  assert.deepEqual(view.stages.map((stage) => stage.className), [
    'stage-box failed',
    'stage-box failed',
    'stage-box failed',
  ]);
});

test('only a verified complete chip paints every stage passed', () => {
  const view = chipStageView({
    overall_status: 'COMPLETE',
    verifier_result: { accepted: true, resolution: 'verified' },
    checks: [
      { step: 1, passed: true, status: 'PASS' },
      { step: 2, passed: true, status: 'PASS' },
      { step: 3, passed: true, status: 'PASS' },
    ],
  });
  assert.equal(view.complete, true);
  assert.equal(view.pill, 'COMPLETE');
  assert.ok(view.stages.every((stage) => stage.className === 'stage-box passed'));
});

test('http success without an accepted verifier is not complete', () => {
  const view = chipStageView({ overall_status: 'COMPLETE', checks: [] });
  assert.equal(view.complete, false);
  assert.equal(view.pill, 'FAILED');
});
