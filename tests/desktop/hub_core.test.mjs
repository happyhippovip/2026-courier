// Desktop Hub view logic (lane L5): rendering, connection, decisions.
// The fixture comes from the real Python projection model (tests/hub/fixture_source.py).
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

import {
  MARKS, createDecisionClient, decisionsAllowed, escapeHtml, findChoice, initialConnection,
  interpretResponse, nextConnection, renderCard, renderHome, renderProjectBase, renderReceipt, retryDelayMs, statusLine, viewSignature,
} from '../../courier_hub/static/hub_core.mjs';

const view = JSON.parse(readFileSync(new URL('./fixtures/home_view.json', import.meta.url), 'utf8'));
const NOW = Date.parse('2026-10-02T08:05:00Z');
const live = { state: 'live', failures: 0, lastGoodAt: '2026-10-02T08:05:00Z' };
const doneCard = (id) => view.done.find((c) => c.id === id);

test('home renders the three piles in fixed order, never a chat', () => {
  const html = renderHome(view, { now: NOW });
  const order = ['pile-needs_you', 'pile-working', 'pile-done'].map((k) => html.indexOf(k));
  assert.deepEqual([...order].sort((a, b) => a - b), order);
  assert.ok(!/chat|message courier/i.test(html));
});

test('only the verified outcome carries the check mark', () => {
  const verified = renderCard(doneCard('t-verified'), { now: NOW });
  const human = renderCard(doneCard('t-human'), { now: NOW });
  assert.ok(verified.includes(MARKS.check.glyph) && verified.includes('Checked by Courier'));
  assert.ok(!human.includes(MARKS.check.glyph));
  assert.ok(human.includes('Confirmed by ana') && human.includes('did not verify'));
});

test('a stop after an uncertain effect says the action may have happened', () => {
  const html = renderCard(doneCard('t-uncertain'), { now: NOW });
  assert.ok(html.includes('Outcome uncertain'));
  assert.ok(html.includes('The earlier action may already have happened.'));
  assert.ok(!/safely stopped/i.test(html));
});

test('every done outcome looks different', () => {
  const classes = view.done.map((c) => renderCard(c, { now: NOW }).match(/outcome-[a-z_]+/)[0]);
  assert.equal(new Set(classes).size, view.done.length);
});

test('needs-you card offers the three decisions as real buttons tied to the blocked attempt', () => {
  const html = renderCard(view.needs_you[0], { now: NOW });
  for (const label of ['It happened', 'Try once more', 'Stop here']) assert.ok(html.includes(`>${label}</button>`));
  assert.equal((html.match(/data-attempt="1"/g) || []).length, 3);
  assert.ok(html.includes('role="group"'));
});

test('decisions are disabled while offline, in safe mode, or while one is pending', () => {
  const card = view.needs_you[0];
  assert.ok(renderCard(card, { now: NOW, decisionsAllowed: false }).includes('disabled'));
  assert.ok(renderCard(card, { now: NOW, pendingDecision: card.id }).includes('Sending your decision'));
  assert.equal(decisionsAllowed(view, { state: 'offline' }), false);
  assert.equal(decisionsAllowed({ ...view, status: { controller: 'safe_mode' } }, live), false);
  assert.equal(decisionsAllowed(view, live), true);
});

test('try once more carries a concrete consequence before anything is sent', () => {
  const choice = findChoice(view, 't-blocked', 'retry_authorized');
  assert.match(choice.confirm, /could repeat it/);
  assert.match(choice.confirm, /written a second time/);
  assert.equal(findChoice(view, 't-blocked', 'effect_confirmed').confirm, undefined);
});

test('working card shows observable state, authority and a stop control', () => {
  const html = renderCard(view.working[0], { now: NOW });
  assert.ok(html.includes('In progress') && html.includes('Courier may:') && html.includes('Must ask before:'));
  assert.ok(html.includes('data-action="stop"'));
});

test('empty piles say so plainly', () => {
  const html = renderHome({ needs_you: [], working: [], done: [] }, { now: NOW });
  assert.ok(html.includes('Nothing needs you right now.'));
  assert.ok(!html.includes('class="count"'));
});

test('status line: running, unreachable, safe mode, offline, not set up', () => {
  assert.match(statusLine(view, live, NOW).text, /^1 needs you · 1 working · 4 done$/);
  assert.match(statusLine({ ...view, status: { controller: 'unreachable' } }, live, NOW).text, /isn't running/);
  assert.match(statusLine({ ...view, status: { controller: 'safe_mode' } }, live, NOW).text, /safe mode/);
  assert.match(statusLine(view, { state: 'offline', lastGoodAt: '2026-10-02T08:00:00Z' }, NOW).text,
    /last known state\. Last updated 5 minutes ago/);
  assert.match(statusLine({ truth: 'not_set_up' }, live, NOW).text, /hasn't been set up/);
});

test('connection: reconnecting, then offline, then live again with backoff', () => {
  let c = nextConnection(initialConnection(), { type: 'ok', at: 'x' });
  assert.equal(c.state, 'live');
  c = nextConnection(c, { type: 'fail' });
  assert.equal(c.state, 'reconnecting');
  c = nextConnection(nextConnection(c, { type: 'fail' }), { type: 'fail' });
  assert.equal(c.state, 'offline');
  assert.equal(c.lastGoodAt, 'x');
  assert.ok(retryDelayMs(c) > retryDelayMs({ state: 'live', failures: 0 }));
  assert.ok(retryDelayMs({ state: 'offline', failures: 99 }) <= 30000);
  assert.equal(nextConnection(c, { type: 'ok', at: 'y' }).state, 'live');
});

test('a double click sends exactly one decision', async () => {
  const calls = [];
  let release;
  const fetchFn = (url, init) => {
    calls.push({ url, init });
    return new Promise((resolve) => { release = () => resolve({ status: 200, json: async () => ({ result: 'recorded', item: {} }) }); });
  };
  const client = createDecisionClient(fetchFn);
  const a = client.decide('t-blocked', 'effect_confirmed', 1);
  const b = client.decide('t-blocked', 'effect_confirmed', 1);
  assert.equal(a, b);
  assert.equal(client.busy('t-blocked'), true);
  release();
  assert.equal((await a).kind, 'success');
  assert.equal(calls.length, 1);
  assert.equal(calls[0].init.headers['X-Courier-Hub'], '1');
  assert.deepEqual(JSON.parse(calls[0].init.body), { decision: 'effect_confirmed', attempt: 1 });
  assert.equal(client.busy('t-blocked'), false);
});

test('responses: recorded, already recorded, stale, offline, error', () => {
  assert.equal(interpretResponse(200, { result: 'recorded' }).kind, 'success');
  assert.equal(interpretResponse(200, { result: 'already_recorded' }).kind, 'already');
  const stale = interpretResponse(409, { result: 'stale', message: 'This changed since you opened it.' });
  assert.equal(stale.kind, 'stale');
  assert.equal(stale.message, 'This changed since you opened it.');
  assert.equal(interpretResponse(-1, null).kind, 'unknown');
  assert.equal(interpretResponse(504, { result: 'unknown', message: 'm', item: null }).kind, 'unknown');
  assert.equal(interpretResponse(503, { result: 'offline', message: 'x' }).kind, 'offline');
  assert.equal(interpretResponse(400, { result: 'invalid', message: 'Unknown decision.' }).kind, 'error');
});

test('an answer the hub does not vouch for is unknown, never "nothing was changed"', () => {
  for (const [status, payload] of [[500, null], [502, null], [200, null], [200, { result: 'surprise' }],
    [500, { result: 'unknown', message: 'The hub hit an internal error. Courier may have recorded this.' }]]) {
    const result = interpretResponse(status, payload);
    assert.equal(result.kind, 'unknown', `${status} ${JSON.stringify(payload)}`);
    assert.doesNotMatch(result.message, /nothing (was )?changed/i);
  }
});

test('a network failure after sending is reported as unknown, never as success or as "nothing changed"', async () => {
  const client = createDecisionClient(async () => { throw new TypeError('fetch failed'); });
  const result = await client.decide('t-blocked', 'cancel', 1);
  assert.equal(result.kind, 'unknown');
  assert.doesNotMatch(result.message, /nothing (was )?changed/i);
  assert.match(result.message, /Couldn't confirm/);
});

test('an unchanged view has the same signature, so the page does not re-render while idle', () => {
  const a = viewSignature(view, live, null);
  assert.equal(a, viewSignature(JSON.parse(JSON.stringify(view)), live, null));
  assert.notEqual(a, viewSignature({ ...view, head_seq: view.head_seq + 1 }, live, null));
  assert.notEqual(a, viewSignature(view, { ...live, state: 'offline' }, null));
  assert.notEqual(a, viewSignature(view, live, 't-blocked'));
});

test('a disabled stop says so to assistive technology; an unrecognised item offers no actions', () => {
  assert.ok(renderCard(view.working[0], { now: NOW, decisionsAllowed: false }).includes('aria-disabled="true"'));
  const odd = { ...view.working[0], phase: 'unrecognised', label: 'State not recognised by this hub', stop: null };
  assert.ok(!renderCard(odd, { now: NOW }).includes('data-action="stop"'));
});

test('receipt answers the seven questions and keeps ids in the support view', () => {
  const item = {
    card: view.done[0],
    receipt: {
      understood: 'Courier was asked to write the test file (Synthetic test task).',
      authorized: { may: ['Write the test file once'], must_ask: ['Anything after an unclear outcome'], note: 'n' },
      tried: [{ what: 'Courier started the work', at: '2026-10-02T08:00:00Z' }], resumed: true,
      happened: 'Confirmed by ana', how_known: 'Confirmed by ana. Courier did not verify it.',
      decisions: [{ who: 'ana', decided: 'A person confirmed it happened', reason: 'saw it', at: '2026-10-02T08:01:00Z' }],
      changed_later: [], evidence: [],
    },
    support: { task: { dispatch_id: 'dsp-1' }, events: [] },
  };
  const html = renderReceipt(item, { now: NOW });
  for (const q of ['What Courier understood', 'What Courier was allowed to do', 'What Courier did', 'What happened',
    'How Courier knows', 'Who decided', 'What changed later']) assert.ok(html.includes(q), q);
  assert.ok(html.includes('Courier may, without asking again') && html.includes('Courier must ask before'));
  assert.ok(html.includes('resumed after an interruption'));
  const beforeSupport = html.slice(0, html.indexOf('<details'));
  assert.ok(!beforeSupport.includes('dsp-1'));
  assert.ok(html.includes('<summary>For support</summary>'));
  const exportLink = html.slice(html.indexOf('<details'));
  assert.ok(exportLink.includes(`href="/hub/api/items/${view.done[0].id}/support" download`));
});

test('everything shown is escaped', () => {
  const evil = { ...view.working[0], title: '<img src=x onerror=alert(1)>' };
  const html = renderCard(evil, { now: NOW });
  assert.ok(!html.includes('<img'));
  assert.equal(escapeHtml(`"'<>&`), '&quot;&#39;&lt;&gt;&amp;');
});

test('keyboard: every action is a focusable button with a visible label', () => {
  const html = renderHome(view, { now: NOW });
  const actions = html.match(/data-action="[a-z]+"/g) || [];
  const buttons = html.match(/<button type="button"[^>]*data-action=/g) || [];
  assert.ok(actions.length > 0);
  assert.equal(buttons.length, actions.length);
  assert.ok(!html.includes('tabindex="-1"'));
});

test('renderProjectBase renders unified founder base sections with escaping', () => {
  assert.equal(renderProjectBase(null), '');
  const pb = {
    counts: { active_workkeys: 1 },
    next_safe_action: {
      type: 'DECISION_REQUIRED',
      urgency: 'HIGH',
      title: 'Review payment decision',
      description: 'Courier needs your confirmation.',
    },
    current_workkeys: [
      { workkey: 'L5-BASE', status: 'RUNNING', worker_id: 'mac-worker', adapter: 'mac' },
    ],
    last_verified_result: {
      title: 'Checked invoice',
      verified_at: '2026-10-02T08:00:00Z',
      evidence: [{ name: 'invoice.pdf' }],
      seq: 42,
      hash: 'abcdef1234567890',
    },
    away_summary: {
      since_seq: 10,
      events_count: 5,
      completed_count: 2,
      blocked_count: 1,
      failed_count: 0,
      milestones: [{ summary: 'Task t1 verified', at: '2026-10-02T08:02:00Z' }],
    },
    durable_context: {
      repository: 'happyhippovip/2026-courier',
      trunk_branch: 'integration/v1',
      head_seq: 45,
      total_tasks: 8,
      total_events: 45,
    },
  };

  const html = renderProjectBase(pb, { now: NOW });
  assert.ok(html.includes('Review payment decision'));
  assert.ok(html.includes('base-action-high'));
  assert.ok(html.includes('L5-BASE'));
  assert.ok(html.includes('Checked invoice'));
  assert.ok(html.includes('Seq #42'));
  assert.ok(html.includes('5 event(s) recorded'));
  assert.ok(html.includes('integration/v1'));
  assert.ok(html.includes('#45'));
});

