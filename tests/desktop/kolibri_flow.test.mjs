// Test suite for Kolibri Signal & Flow Translation (Lane L5)
// Enforces truth invariants:
// - Status strings ("VERIFIED", "SUCCESS") alone are never green/verified without authentic event_id.
// - Replay deduplication prevents duplicate active verified pulses.
// - Blocker/Failure takes highest precedence over active states.
// - Unknown stays Unknown.

import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  FLOW_STATES,
  FLOW_COLORS,
  translateSignal,
} from '../../courier_hub/static/kolibri_flow.mjs';

test('translateSignal handles empty or invalid inputs by returning UNKNOWN', () => {
  const empty = translateSignal(null);
  assert.equal(empty.state, FLOW_STATES.UNKNOWN);
  assert.equal(empty.color, FLOW_COLORS[FLOW_STATES.UNKNOWN]);
  assert.equal(empty.event_id, 'evt:unknown:0');
  assert.equal(empty.verified, false);

  const nonObject = translateSignal('string-signal');
  assert.equal(nonObject.state, FLOW_STATES.UNKNOWN);
  assert.equal(nonObject.verified, false);
});

test('translateSignal enforces Fail-Closed: strings alone are NOT verified', () => {
  // item has raw status "VERIFIED" but verified !== true -> MUST NOT BE VERIFIED
  const item1 = { status: 'VERIFIED', event_id: 'evt:123' };
  const res1 = translateSignal(item1);
  assert.notEqual(res1.state, FLOW_STATES.VERIFIED);
  assert.equal(res1.verified, false);

  // item has status "SUCCESS" but verified !== true
  const item2 = { status: 'SUCCESS', event_id: 'evt:456' };
  const res2 = translateSignal(item2);
  assert.notEqual(res2.state, FLOW_STATES.VERIFIED);
  assert.equal(res2.verified, false);
});

test('translateSignal rejects synthetic or unknown event IDs from becoming VERIFIED', () => {
  // synthetic event generator id
  const item1 = { verified: true, event_id: 'evt:gen:1' };
  const res1 = translateSignal(item1);
  assert.notEqual(res1.state, FLOW_STATES.VERIFIED);
  assert.equal(res1.verified, false);

  // unknown event id
  const item2 = { verified: true }; // defaults to evt:unknown:0
  const res2 = translateSignal(item2);
  assert.notEqual(res2.state, FLOW_STATES.VERIFIED);
  assert.equal(res2.verified, false);
});

test('translateSignal prioritizes BLOCKER and FAILED over active states', () => {
  const blocked = {
    status: 'RUNNING',
    blocker: 'MISSING_AUTHORITY_TOKEN',
    event_id: 'evt:auth:99',
  };
  const resB = translateSignal(blocked);
  assert.equal(resB.state, FLOW_STATES.BLOCKED);
  assert.equal(resB.color, FLOW_COLORS[FLOW_STATES.BLOCKED]);
  assert.equal(resB.verified, false);

  const failed = {
    status: 'FAILED',
    event_id: 'evt:run:101',
  };
  const resF = translateSignal(failed);
  assert.equal(resF.state, FLOW_STATES.FAILED);
  assert.equal(resF.color, FLOW_COLORS[FLOW_STATES.FAILED]);
  assert.equal(resF.verified, false);
});

test('translateSignal marks authentic verified item as VERIFIED, and deduplicates replay', () => {
  const authentic = {
    verified: true,
    event_id: 'evt:canonical:mission:999',
  };
  // First time: VERIFIED
  const res1 = translateSignal(authentic);
  assert.equal(res1.state, FLOW_STATES.VERIFIED);
  assert.equal(res1.color, FLOW_COLORS[FLOW_STATES.VERIFIED]);
  assert.equal(res1.verified, true);
  assert.equal(res1.event_id, 'evt:canonical:mission:999');

  // Replay of the exact same event: CLAIMED (no duplicate pulse)
  const res2 = translateSignal(authentic);
  assert.equal(res2.state, FLOW_STATES.CLAIMED);
  assert.equal(res2.verified, false);
});

test('translateSignal maps standard lifecycle states correctly', () => {
  assert.equal(translateSignal({ status: 'RUNNING', event_id: 'evt:r1' }).state, FLOW_STATES.RUNNING);
  assert.equal(translateSignal({ status: 'TRANSFERRED', event_id: 'evt:t1' }).state, FLOW_STATES.TRANSFERRED);
  assert.equal(translateSignal({ status: 'CLAIMED', event_id: 'evt:c1' }).state, FLOW_STATES.CLAIMED);
  assert.equal(translateSignal({ status: 'VERIFYING', event_id: 'evt:v1' }).state, FLOW_STATES.VERIFYING);
  assert.equal(translateSignal({ status: 'WARN', event_id: 'evt:w1' }).state, FLOW_STATES.WARN);
  assert.equal(translateSignal({ status: 'ROUTER', event_id: 'evt:ro1' }).state, FLOW_STATES.ROUTER);
  assert.equal(translateSignal({ status: 'INFRA', event_id: 'evt:i1' }).state, FLOW_STATES.INFRA);
});
