// Tests for Kolibri Universe Component (L5 Desktop Hub / Kolibri Visual First)
import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  UNIVERSE_STATUS,
  UNIVERSE_COLORS,
  buildUniverseModel,
  renderKolibriUniverse,
} from '../../courier_hub/static/kolibri_universe.mjs';

test('buildUniverseModel extracts zero fabricated agents/projects from empty snapshot', () => {
  const model = buildUniverseModel({});
  assert.equal(model.center.id, 'courier-core');
  assert.equal(model.agents.length, 0);
  assert.equal(model.projects.length, 0);
  assert.equal(model.connections.length, 0);
  assert.equal(model.teams.length, 0);
});

test('buildUniverseModel handles unavailable snapshot safely without error', () => {
  const model = buildUniverseModel(null);
  assert.ok(model.center);
  assert.equal(model.agents.length, 0);
  assert.equal(model.projects.length, 0);
  assert.equal(model.connections.length, 0);
});

test('buildUniverseModel translates station statuses correctly', () => {
  const snapshot = {
    muse_wall: {
      stations: [
        { id: 'MUSE-01', state: { value: 'RUNNING' }, owner: 'alpha-team', workkey: 'TASK-101' },
        { id: 'MUSE-02', state: { value: 'BLOCKED' }, blocker: 'NO_LEASE', owner: 'beta-team' },
        { id: 'MUSE-03', state: { value: 'DONE' }, verified: true, event_id: 'evt:verifier:99', owner: 'alpha-team' },
        { id: 'MUSE-04', state: { value: 'IDLE' } },
      ],
    },
    ledger_bridge: {
      missions: [
        { id: 'TASK-101', status: 'IN_PROGRESS', workkey: 'TASK-101' },
      ],
    },
  };

  const model = buildUniverseModel(snapshot);
  assert.equal(model.agents.length, 4);

  const agent1 = model.agents.find((a) => a.id === 'MUSE-01');
  const agent2 = model.agents.find((a) => a.id === 'MUSE-02');
  const agent3 = model.agents.find((a) => a.id === 'MUSE-03');
  const agent4 = model.agents.find((a) => a.id === 'MUSE-04');

  assert.equal(agent1.status, UNIVERSE_STATUS.REPORTED);
  assert.equal(agent2.status, UNIVERSE_STATUS.BLOCKED);
  assert.equal(agent2.color, UNIVERSE_COLORS[UNIVERSE_STATUS.BLOCKED]);
  assert.equal(agent3.status, UNIVERSE_STATUS.VERIFIED);
  assert.equal(agent3.color, UNIVERSE_COLORS[UNIVERSE_STATUS.VERIFIED]);
  assert.equal(agent4.status, UNIVERSE_STATUS.UNKNOWN);

  // Teams derived from authentic owners
  assert.ok(model.teams.some((t) => t.name === 'alpha-team'));
  assert.ok(model.teams.some((t) => t.name === 'beta-team'));
});

test('buildUniverseModel establishes real workflow connections only', () => {
  const snapshot = {
    muse_wall: {
      stations: [
        { id: 'MUSE-01', state: { value: 'RUNNING' }, workkey: 'PROJ-ALPHA' },
        { id: 'MUSE-02', state: { value: 'IDLE' }, workkey: null },
      ],
    },
    ledger: {
      items: [
        { id: 'PROJ-ALPHA', title: 'Alpha Project', pile: 'working' },
      ],
    },
  };

  const model = buildUniverseModel(snapshot);
  assert.equal(model.projects.length, 1);
  assert.equal(model.projects[0].id, 'PROJ-ALPHA');

  // Connection from core -> active agent MUSE-01
  const coreToAgent = model.connections.find((c) => c.from === 'courier-core' && c.to === 'MUSE-01');
  assert.ok(coreToAgent, 'Core must connect to active station');

  // Connection from agent MUSE-01 -> project PROJ-ALPHA
  const agentToProj = model.connections.find((c) => c.from === 'MUSE-01' && c.to === 'PROJ-ALPHA');
  assert.ok(agentToProj, 'Agent must connect to linked project');

  // Idle agent MUSE-02 with no workkey must not connect to any project
  const idleConn = model.connections.filter((c) => c.from === 'MUSE-02');
  assert.equal(idleConn.length, 0);
});

test('renderKolibriUniverse generates accessible responsive SVG markup', () => {
  const snapshot = {
    observed_at: '2026-10-20T08:00:00Z',
    muse_wall: {
      stations: [
        { id: 'MUSE-01', state: { value: 'RUNNING' }, workkey: 'K-01' },
      ],
    },
  };

  const html = renderKolibriUniverse(snapshot, { selected: 'MUSE-01' });

  // Viewport & responsive SVG checks
  assert.ok(html.includes('viewBox="0 0 800 600"'));
  assert.ok(html.includes('preserveAspectRatio="xMidYMid meet"'));
  assert.ok(html.includes('role="img"'));

  // Core sphere
  assert.ok(html.includes('COURIER CORE'));
  assert.ok(html.includes('courier-core'));

  // Planet & accessibility
  assert.ok(html.includes('data-workkey="MUSE-01"'));
  assert.ok(html.includes('role="button"'));
  assert.ok(html.includes('tabindex="0"'));
  assert.ok(html.includes('planet-selected'));

  // Legend
  assert.ok(html.includes('VERIFIED'));
  assert.ok(html.includes('REPORTED'));
  assert.ok(html.includes('BLOCKED'));
  assert.ok(html.includes('UNKNOWN'));
});

test('renderKolibriUniverse respects paused animation mode', () => {
  const snapshot = {};
  const htmlRunning = renderKolibriUniverse(snapshot, { paused: false });
  const htmlPaused = renderKolibriUniverse(snapshot, { paused: true });

  assert.ok(!htmlRunning.includes('universe-paused'));
  assert.ok(htmlPaused.includes('universe-paused'));
  assert.ok(htmlPaused.includes('Kosmos bewegen'));
  assert.ok(htmlRunning.includes('Kosmos anhalten'));
});
