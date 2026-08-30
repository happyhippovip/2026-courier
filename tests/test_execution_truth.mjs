import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  resolveAcademySummary,
  resolveBodyguardsTruth,
  resolveChiefWaitState,
  resolveCorrelationTruth,
  resolveDecisionTruth,
  resolveDeskMatrix,
  resolveGateDecisionTruth,
  resolveLiveHQMetrics,
  resolveSnitchTruth,
  resolveSpeechBubble,
  resolveExecutionTruth,
  resolveStewardTruth,
  resolveThreadContext,
  validateThreadAssociation,
} from '../studio/execution_truth.js';


// -------------------------------------------------------------
// 1. EXECUTION CLASS RESOLUTION
// -------------------------------------------------------------
// Missing machine evidence must never inherit a class from an agent identity.
assert.equal(resolveExecutionTruth({ id: 'agent-codex-bridge', state: 'RUNNING' }), 'UNKNOWN');

assert.equal(
  resolveExecutionTruth({ execution_class: 'REAL_CODEX_CLI' }),
  'REAL_CODEX_CLI',
);
assert.equal(
  resolveExecutionTruth({ execution_class: 'DETERMINISTIC_ANTIGRAVITY' }),
  'DETERMINISTIC_ANTIGRAVITY',
);
assert.equal(resolveExecutionTruth({ execution_class: 'FALLBACK' }), 'FALLBACK');
assert.equal(resolveExecutionTruth({ execution_class: 'SIMULATED_VISUAL' }), 'SIMULATED_VISUAL');
assert.equal(resolveExecutionTruth({ execution_class: 'untrusted-label' }), 'UNKNOWN');

// -------------------------------------------------------------
// 2. DECISION & CORRELATION RESOLUTION
// -------------------------------------------------------------
// The display layer must not turn no decision into an approval.
assert.equal(resolveDecisionTruth({}), 'NO_DECISION');
assert.equal(resolveDecisionTruth({ last_decision: 'REJECTED' }), 'REJECTED');

// A global decision never attaches to a human gate without matching
// workflow/correlation provenance.
const gateWithoutProvenance = {
  human_gate: true,
  last_decision: 'ACCEPTED',
  active_human_gate: { workflow_id: 'idea-1', correlation_id: null, provenance_complete: false },
  gate_decision: { status: 'ACCEPTED', workflow_id: 'WF-OTHER', correlation_id: 'corr-other' },
};
assert.equal(resolveGateDecisionTruth(gateWithoutProvenance), 'NO_DECISION');
const gateWithMismatchedDecision = {
  human_gate: true,
  active_human_gate: { workflow_id: 'idea-1', correlation_id: 'corr-gate-1', provenance_complete: true },
  gate_decision: { status: 'ACCEPTED', workflow_id: 'WF-OTHER', correlation_id: 'corr-other' },
};
assert.equal(resolveGateDecisionTruth(gateWithMismatchedDecision), 'NO_DECISION');
const gateWithMatchingDecision = {
  human_gate: true,
  active_human_gate: { workflow_id: 'idea-1', correlation_id: 'corr-gate-1', provenance_complete: true },
  gate_decision: { status: 'APPROVE', workflow_id: 'idea-1', correlation_id: 'corr-gate-1' },
};
assert.equal(resolveGateDecisionTruth(gateWithMatchingDecision), 'APPROVE');

assert.match(
  resolveSpeechBubble('agent-snitch', { state: 'EXPECTED_LONG_RUNNING' }, {}),
  /intentionally running continuously/i,
);
assert.match(
  resolveSpeechBubble('agent-snitch', { state: 'STALLED' }, {}),
  /informed Chief/i,
);
assert.match(
  resolveSpeechBubble('agent-chief-commander', {}, {}),
  /No current machine evidence/i,
);

// A missing correlation remains absent; it is never generated in the browser.
assert.equal(resolveCorrelationTruth({}), null);
assert.equal(resolveCorrelationTruth({ correlation_id: 'UNKNOWN' }), null);
assert.equal(resolveCorrelationTruth({ correlation_id: 'corr-from-courier-001' }), 'corr-from-courier-001');

// -------------------------------------------------------------
// 3. UPDATE STEWARD TRUTH RESOLUTION
// -------------------------------------------------------------
// Missing Steward evidence => UNKNOWN and null/empty values, never guessed
const emptySteward = resolveStewardTruth({});
assert.equal(emptySteward.state, 'UNKNOWN');
assert.equal(emptySteward.context_version, null);
assert.equal(emptySteward.snapshot_hash, null);
assert.equal(emptySteward.last_refresh, null);
assert.deepEqual(emptySteward.changed_items, []);

// Real Steward backend snapshot evidence
const sampleState = {
  agents: {
    'agent-update-steward': {
      id: 'agent-update-steward',
      state: 'SNAPSHOT UPDATED',
      task: 'Context v12 (8184d906)',
      progress: 1.0,
      updated_at: '2026-08-30T15:18:25.935944+00:00',
      next_action: 'Context snapshot v12 published to Courier bus',
    },
  },
  context_snapshot: {
    context_version: 12,
    previous_snapshot_version: 11,
    snapshot_hash: '8184d906d79ba4a00dab4ca13a88795f84df87283408e705fd067c998f26a892',
    generated_at: '2026-08-30T15:18:25.935921+00:00',
    changed_since_previous_snapshot: ['workflow_id'],
    repositories: {
      courier_head: 'ee54710dc2dfead91410a9a812bbdfecc3bd8c63',
      memory_head: 'fb330a9bc8c95756df6f74ccb9ac474db88d4a1b',
      godot_head: 'NOT_CONNECTED',
    },
  },
  bus: {
    context_version: 12,
    snapshot_hash: '8184d906d79ba4a00dab4ca13a88795f84df87283408e705fd067c998f26a892',
  },
};

const realSteward = resolveStewardTruth(sampleState);
assert.equal(realSteward.state, 'SNAPSHOT UPDATED');
assert.equal(realSteward.context_version, 12);
assert.equal(realSteward.previous_version, 11);
assert.equal(realSteward.snapshot_hash, '8184d906d79ba4a00dab4ca13a88795f84df87283408e705fd067c998f26a892');
assert.deepEqual(realSteward.changed_items, ['workflow_id']);
assert.equal(realSteward.repositories.courier_head, 'ee54710dc2dfead91410a9a812bbdfecc3bd8c63');
assert.equal(realSteward.repositories.memory_head, 'fb330a9bc8c95756df6f74ccb9ac474db88d4a1b');

// -------------------------------------------------------------
// 4. CHIEF WAIT-STATE RESOLUTION
// -------------------------------------------------------------
// Human Gate active => CHIEF WAITING FOR HUMAN
assert.equal(
  resolveChiefWaitState({ bus: { human_gate: true } }),
  'CHIEF WAITING FOR HUMAN',
);

// Antigravity running => CHIEF WAITING FOR ANTIGRAVITY
assert.equal(
  resolveChiefWaitState({ agents: { 'agent-antigravity-bridge': { state: 'RUNNING' } } }),
  'CHIEF WAITING FOR ANTIGRAVITY',
);

// Codex running => CHIEF WAITING FOR CODEX
assert.equal(
  resolveChiefWaitState({ agents: { 'agent-codex-bridge': { state: 'RUNNING' } } }),
  'CHIEF WAITING FOR CODEX',
);

// Antigravity finished => RESULT RECEIVED FROM ANTIGRAVITY
assert.equal(
  resolveChiefWaitState({ agents: { 'agent-antigravity-bridge': { state: 'AWAITING_CHIEF_REVIEW' } } }),
  'RESULT RECEIVED FROM ANTIGRAVITY',
);

// Codex finished => RESULT RECEIVED FROM CODEX
assert.equal(
  resolveChiefWaitState({ agents: { 'agent-codex-bridge': { state: 'AWAITING_CHIEF_REVIEW' } } }),
  'RESULT RECEIVED FROM CODEX',
);

// Idle state
assert.equal(
  resolveChiefWaitState({ bus: { is_locked: false, active_workflow: 'IDLE_MONITORING' } }),
  'IDLE',
);

// -------------------------------------------------------------
// 5. THREAD CONTEXT & RESULT ASSOCIATION
// -------------------------------------------------------------
const agRunningState = {
  bus: {
    active_workflow: 'WF-CHIEF-001',
    correlation_id: 'corr-test-1234',
    is_locked: true,
  },
  agents: {
    'agent-antigravity-bridge': {
      id: 'agent-antigravity-bridge',
      state: 'RUNNING',
      task: 'WF-CHIEF-001-STEP-1-DISCOVER',
    },
  },
  context_snapshot: {
    context_version: 12,
    snapshot_hash: '8184d906d79b',
  },
};

const tcAg = resolveThreadContext(agRunningState);
assert.equal(tcAg.workflow_id, 'WF-CHIEF-001');
assert.equal(tcAg.correlation_id, 'corr-test-1234');
assert.equal(tcAg.sender_agent_id, 'agent-antigravity-bridge');
assert.equal(tcAg.sender_agent_type, 'antigravity');
assert.equal(tcAg.task_id, 'WF-CHIEF-001-STEP-1-DISCOVER');
assert.equal(tcAg.waiting_for, 'CHIEF WAITING FOR ANTIGRAVITY');
assert.equal(tcAg.context_version, 12);

// Result from Antigravity maps to correct task/workflow/thread
const agResultEnvelope = {
  task_id: 'WF-CHIEF-001-STEP-1-DISCOVER',
  correlation_id: 'corr-test-1234',
  source: 'antigravity',
  payload: {
    workflow_id: 'WF-CHIEF-001',
    context_version_seen: 12,
  },
};
assert.equal(validateThreadAssociation(agResultEnvelope, 'WF-CHIEF-001', 'corr-test-1234'), true);

// Result from Codex maps to correct task/workflow/thread
const cdxResultEnvelope = {
  task_id: 'WF-CHIEF-001-STEP-2-AUDIT',
  correlation_id: 'corr-test-1234',
  source: 'codex',
  payload: {
    workflow_id: 'WF-CHIEF-001',
    context_version_seen: 12,
  },
};
assert.equal(validateThreadAssociation(cdxResultEnvelope, 'WF-CHIEF-001', 'corr-test-1234'), true);

// Cross-thread protection: wrong correlation does not attach to another thread
const wrongCorrResult = {
  task_id: 'WF-OTHER-001-STEP-1',
  correlation_id: 'corr-DIFFERENT-9999',
  payload: { workflow_id: 'WF-OTHER-001' },
};
assert.equal(validateThreadAssociation(wrongCorrResult, 'WF-CHIEF-001', 'corr-test-1234'), false);

// -------------------------------------------------------------
// 6. SOURCE CODE TRUTH INVARIANTS (NO SYNTHETIC GENERATION)
// -------------------------------------------------------------
const studioSource = readFileSync(new URL('../studio/studio.js', import.meta.url), 'utf8');
assert.doesNotMatch(studioSource, /corr-live-|crypto\.randomUUID|Math\.random\(/);
assert.doesNotMatch(studioSource, /last_decision\s*\|\|\s*['\"]ACCEPTED['\"]/);
assert.match(studioSource, /is-flow-active/);

// -------------------------------------------------------------
// 7. AI ACADEMY TRUTH RESOLUTION (TEACHER, DIRECTOR, ECONOMICS)
// -------------------------------------------------------------
import {
  ACADEMY_FLOW_STEPS,
  resolveAcademyEconomics,
  resolveDirectorTruth,
  resolveTeacherTruth,
} from '../studio/execution_truth.js';

// 7.1 Missing Academy Evidence => UNKNOWN / null values
const emptyTeacher = resolveTeacherTruth({});
assert.equal(emptyTeacher.state, 'UNKNOWN');
assert.equal(emptyTeacher.schedule_status, 'UNKNOWN');
assert.equal(emptyTeacher.lessons_today, null);
assert.equal(emptyTeacher.pending_lessons, null);
assert.equal(emptyTeacher.next_school_time, null);

const emptyDirector = resolveDirectorTruth({});
assert.equal(emptyDirector.state, 'UNKNOWN');
assert.equal(emptyDirector.lessons_reviewed, null);
assert.equal(emptyDirector.rule_violations, null);
assert.equal(resolveAcademyEconomics({}).measured_minutes_saved, null);
assert.equal(resolveAcademyEconomics({}).eval_pass_rate, 'UNKNOWN');

// 7.2 Real Teacher Evidence & Schedule vs Research Distinction
const teacherReadyState = {
  agents: {
    'agent-academy-teacher': {
      id: 'agent-academy-teacher',
      name: 'Agentenlehrer',
      state: 'PENDING_REVIEW',
      next_school_time: '06:00 UTC',
      current_topic: 'PROMPT_CACHING_OPTIMIZATION',
      lessons_today: 3,
      opportunities_found: 1,
      affected_agents: ['antigravity', 'codex'],
      pending_lessons: ['lesson-20260830-001'],
      visual_metadata: {
        name: 'AGENTENLEHRER',
        props: ['teacher_hat', 'glasses', 'teacher_pointer'],
      },
    },
  },
};
const teacherTruthReady = resolveTeacherTruth(teacherReadyState);
assert.equal(teacherTruthReady.state, 'PENDING_REVIEW');
assert.equal(teacherTruthReady.schedule_status, 'SCHEDULE READY');
assert.equal(teacherTruthReady.lessons_today, 3);
assert.equal(teacherTruthReady.opportunities_found, 1);
assert.deepEqual(teacherTruthReady.affected_agents, ['antigravity', 'codex']);
assert.deepEqual(teacherTruthReady.visual_metadata.props, ['teacher_hat', 'glasses', 'teacher_pointer']);

// Active Research State distinction
const teacherResearchState = {
  agents: {
    'agent-academy-teacher': {
      state: 'RESEARCHING',
    },
  },
};
const teacherTruthResearch = resolveTeacherTruth(teacherResearchState);
assert.equal(teacherTruthResearch.schedule_status, 'RESEARCH RUNNING');

// 7.3 Real Director Evidence & Governance Metrics
const directorState = {
  agents: {
    'agent-academy-director': {
      id: 'agent-academy-director',
      name: 'Schuldirektor',
      state: 'TEST REQUIRED',
      lessons_reviewed: 4,
      lessons_approved: 3,
      lessons_rejected: 1,
      tests_required: 2,
      evals_passed: 2,
      evals_failed: 0,
      rule_violations: 0,
      measured_savings: { minutes_saved: 14.5, cost_saved_eur: 0.0 },
    },
  },
  academy: {
    total_lessons_adopted: 2,
    measured_minutes_saved: 14.5,
    measured_cost_saved_eur: 0.0,
    revenue_evidence: 'NOT_VERIFIED',
  },
};
const directorTruth = resolveDirectorTruth(directorState);
assert.equal(directorTruth.state, 'TEST REQUIRED');
assert.equal(directorTruth.lessons_reviewed, 4);
assert.equal(directorTruth.lessons_approved, 3);
assert.equal(directorTruth.evals_passed, 2);
assert.equal(directorTruth.rule_violations, 0);

// 7.4 Academy Economics: Truth Invariant (No Fake Revenue)
const econTruth = resolveAcademyEconomics(directorState);
assert.equal(econTruth.measured_minutes_saved, 14.5);
assert.equal(econTruth.measured_cost_saved_eur, 0.0);
assert.equal(econTruth.lessons_adopted, 2);
assert.equal(econTruth.revenue_evidence, 'NOT_VERIFIED');
assert.equal(econTruth.eval_pass_rate, '100%');

// 7.5 The visible Academy map documents a flow, not a fabricated execution.
assert.deepEqual(ACADEMY_FLOW_STEPS, [
  'EXTERNAL FINDING', 'AGENTENLEHRER', 'LESSON', 'SCHULDIREKTOR',
  'TEST / EVAL', 'IDEA SYNC', 'CHIEF', 'UPDATE STEWARD',
  'NEW CONTEXT VERSION', 'AFFECTED AGENT',
]);

// -------------------------------------------------------------
// 8. LIVE AGENT HQ DESK MATRIX, CAPACITIES & METRICS
// -------------------------------------------------------------


// 8.1 Desk Matrix Resolution & Capacities
const mockHQState = {
  bus: {
    is_locked: true,
    active_workflow: 'WF-CHIEF-DEMO-001',
    correlation_id: 'corr-hq-999',
    context_version: 5,
  },
  agents: {
    'agent-chief-commander': { id: 'agent-chief-commander', state: 'COORDINATING', task: 'Directing Task 1' },
    'agent-antigravity-bridge': { id: 'agent-antigravity-bridge', state: 'RUNNING', task: '3D Render', execution_class: 'REAL_ANTIGRAVITY' },
    'agent-codex-bridge': { id: 'agent-codex-bridge', state: 'IDLE', task: 'Standby' },
    'agent-academy-teacher': { id: 'agent-academy-teacher', state: 'PENDING_REVIEW' },
    'agent-academy-director': { id: 'agent-academy-director', state: 'EVALUATING' },
  },
  academy: {
    config: { academy_enabled: true, academy_timezone: 'UTC', academy_daily_time: '06:00' },
    economics: { measured_minutes_saved: 12.0, measured_cost_saved_eur: 0.0, revenue_evidence: 'NOT_VERIFIED' },
    lessons: [
      { lesson_id: 'lesson-001', title: 'Static Caching', topic: 'Performance', status: 'ADOPTED', risk: 'LOW' },
      { lesson_id: 'lesson-002', title: 'Monetization Strategy', topic: 'Distribution', status: 'DISCOVERED', lesson_type: 'OPPORTUNITY_CANDIDATE' },
    ],
    opportunities: [
      { lesson_id: 'lesson-002', title: 'Monetization Strategy', status: 'DISCOVERED', revenue_evidence: 'NOT_VERIFIED' },
    ],
    evaluations: [
      { evaluation_id: 'eval-001', lesson_id: 'lesson-001', verdict: 'PASS', metrics: { runtime_seconds_saved: 15 } },
    ],
  },
};

const desks = resolveDeskMatrix(mockHQState);
assert.equal(desks.length, 36, 'HQ must have 36 visible desks including SNITCH and 8 Bodyguards');

// Verify planned future expansion desks
const futureDesks = desks.filter(d => d.type === 'FUTURE');
assert.equal(futureDesks.length, 3, 'Must have exactly 3 clearly marked future expansion desks');
assert.equal(futureDesks[0].status, 'FUTURE_EXPANSION');
assert.equal(futureDesks[1].status, 'FUTURE_EXPANSION');
assert.equal(futureDesks[2].status, 'FUTURE_EXPANSION');

// Verify active agent vs idle agent desk assignment
const chiefDesk = desks.find(d => d.id === 'DESK-CHIEF-01');
assert.equal(chiefDesk.status, 'ACTIVE');

const agDesk = desks.find(d => d.id === 'DESK-ANTIGRAVITY-05');
assert.equal(agDesk.status, 'ACTIVE');
assert.equal(agDesk.execution_class, 'REAL_ANTIGRAVITY');

const codexDesk = desks.find(d => d.id === 'DESK-CODEX-06');
assert.equal(codexDesk.status, 'IDLE');

// Verify equipped available desk (no active agent attached)
const unassignedEquipped = desks.find(d => d.id === 'DESK-EQUIPPED-18');
assert.equal(unassignedEquipped.status, 'REGISTERED_EQUIPPED');

// 8.2 Master TV Wall Overview Metrics
const hqMetrics = resolveLiveHQMetrics(mockHQState);
assert.equal(hqMetrics.total_desks, 36);
assert.equal(hqMetrics.total_capacity, 40);

assert.equal(hqMetrics.active_agents >= 2, true);
assert.equal(hqMetrics.future_workstations, 3);
assert.equal(hqMetrics.current_workflow, 'WF-CHIEF-DEMO-001');
assert.equal(hqMetrics.correlation_id, 'corr-hq-999');
assert.equal(hqMetrics.context_version, 5);

// No machine state must not turn the TV wall into a healthy/idle claim.
const unknownHQ = resolveLiveHQMetrics({});
assert.equal(unknownHQ.current_workflow, null);
assert.equal(unknownHQ.correlation_id, null);
assert.equal(unknownHQ.context_version, null);
assert.equal(unknownHQ.system_health, 'UNKNOWN');
assert.equal(resolveAcademySummary({}).is_enabled, null);
assert.equal(resolveAcademySummary({}).recent_lessons, null);

// 8.3 Structured Academy Evidence API
const academySummary = resolveAcademySummary(mockHQState);
assert.equal(academySummary.is_enabled, true);
assert.equal(academySummary.daily_time, '06:00');
assert.equal(academySummary.lessons_count, 2);
assert.equal(academySummary.opportunities_count, 1);
assert.equal(academySummary.evaluations_count, 1);
assert.equal(academySummary.recent_opportunities[0].revenue_evidence, 'NOT_VERIFIED');

// 8.4 Real Agent Movement & Task Isolation Invariants
// Task routed to Antigravity does not activate Codex
const agOnlyState = {
  agents: {
    'agent-antigravity-bridge': { id: 'agent-antigravity-bridge', state: 'RUNNING', task: '3D Render' },
    'agent-codex-bridge': { id: 'agent-codex-bridge', state: 'IDLE', task: 'Standby' },
  },
};
const agOnlyDesks = resolveDeskMatrix(agOnlyState);
assert.equal(agOnlyDesks.find(d => d.id === 'DESK-ANTIGRAVITY-05').status, 'ACTIVE');
assert.equal(agOnlyDesks.find(d => d.id === 'DESK-CODEX-06').status, 'IDLE');

// Task routed to Codex does not activate Antigravity
const cdxOnlyState = {
  agents: {
    'agent-antigravity-bridge': { id: 'agent-antigravity-bridge', state: 'IDLE', task: 'Standby' },
    'agent-codex-bridge': { id: 'agent-codex-bridge', state: 'RUNNING', task: 'Code Audit' },
  },
};
const cdxOnlyDesks = resolveDeskMatrix(cdxOnlyState);
assert.equal(cdxOnlyDesks.find(d => d.id === 'DESK-ANTIGRAVITY-05').status, 'IDLE');
assert.equal(cdxOnlyDesks.find(d => d.id === 'DESK-CODEX-06').status, 'ACTIVE');

// -------------------------------------------------------------
// 9. SNITCH 2.0 & EIGHT BODYGUARDS TRUTH INVARIANTS
// -------------------------------------------------------------
// 9.1 SNITCH 2.0 Watchdog Truth Resolution
const defaultSnitch = resolveSnitchTruth({});
assert.equal(defaultSnitch.name, 'SNITCH');
assert.equal(defaultSnitch.state, 'MONITORING');
assert.equal(defaultSnitch.speech, "I'm monitoring running tasks. Everything looks healthy.");
assert.equal(defaultSnitch.auto_kill_policy, 'DISABLED (CHIEF_ESCALATION_ONLY)');
assert.equal(defaultSnitch.five_minute_rule, 'RUNTIME > 5 MIN != ERROR (DISTINGUISHES PERSISTENT SERVICES AND PROGRESSING TASKS)');

const persistentSnitch = resolveSnitchTruth({
  snitch: { state: 'EXPECTED_LONG_RUNNING', speech: 'The Studio server is intentionally persistent. No action needed.' },
});
assert.equal(persistentSnitch.state, 'EXPECTED_LONG_RUNNING');
assert.equal(persistentSnitch.speech, 'The Studio server is intentionally persistent. No action needed.');

const slowSnitch = resolveSnitchTruth({
  snitch: { state: 'SLOW_BUT_PROGRESSING', speech: 'This task has exceeded five minutes, but progress is still detected.' },
});
assert.equal(slowSnitch.state, 'SLOW_BUT_PROGRESSING');
assert.equal(slowSnitch.speech, 'This task has exceeded five minutes, but progress is still detected.');

const stalledSnitch = resolveSnitchTruth({
  snitch: {
    state: 'STALLED',
    speech: 'No meaningful progress detected. I informed Chief.',
    incident: { active: true, classification: 'STALLED', severity: 'HIGH' },
  },
});
assert.equal(stalledSnitch.state, 'STALLED');
assert.equal(stalledSnitch.active_incident, true);
assert.equal(stalledSnitch.incident_details.severity, 'HIGH');

// 9.2 Eight Bodyguards Reserve Pool Truth Resolution
const defaultBodyguards = resolveBodyguardsTruth({});
assert.equal(defaultBodyguards.length, 8);
const expectedBgNames = ['ALPHA', 'BRAVO', 'CHARLIE', 'DELTA', 'ECHO', 'FOXTROT', 'GOLF', 'HOTEL'];
assert.deepEqual(defaultBodyguards.map(b => b.callsign), expectedBgNames);
defaultBodyguards.forEach(bg => {
  assert.equal(bg.state, 'STANDBY');
  assert.equal(bg.is_standby, true);
  assert.equal(bg.model_calls_incurred, 0);
  assert.equal(bg.speech, 'Ready for reserve duty.');
});

// Assigned Bodyguard Alpha
const assignedBgState = {
  bodyguards: [
    {
      id: 'agent-bodyguard-alpha',
      callsign: 'ALPHA',
      state: 'ASSIGNED',
      temporary_role: 'QA_WORKER',
      task: 'TASK-QA-001',
      speech: 'Temporary role QA_WORKER received. Preparing task.',
    },
  ],
};
const resolvedAssignedBgs = resolveBodyguardsTruth(assignedBgState);
const alphaBg = resolvedAssignedBgs.find(b => b.callsign === 'ALPHA');
assert.equal(alphaBg.state, 'ASSIGNED');
assert.equal(alphaBg.temporary_role, 'QA_WORKER');
assert.equal(alphaBg.is_standby, false);
assert.equal(alphaBg.speech, 'Temporary role QA_WORKER received. Preparing task.');

// Bravo remains STANDBY
const bravoBg = resolvedAssignedBgs.find(b => b.callsign === 'BRAVO');
assert.equal(bravoBg.state, 'STANDBY');
assert.equal(bravoBg.is_standby, true);

// 9.3 Live Desk Matrix contains SNITCH, 8 Bodyguards, and 3 Future Expansion Desks
const fullHQDesks = resolveDeskMatrix(assignedBgState);
assert.ok(fullHQDesks.find(d => d.id === 'DESK-SNITCH-10'));
assert.ok(fullHQDesks.find(d => d.id === 'DESK-BG-01'));
assert.ok(fullHQDesks.find(d => d.id === 'DESK-BG-08'));
assert.equal(fullHQDesks.filter(d => d.type === 'BODYGUARD').length, 8);
assert.equal(fullHQDesks.filter(d => d.type === 'FUTURE').length, 3);
assert.equal(fullHQDesks.find(d => d.id === 'DESK-BG-01').status, 'ACTIVE');
assert.equal(fullHQDesks.find(d => d.id === 'DESK-BG-02').status, 'IDLE');

console.log('execution truth tests: PASS (100% SUCCESS)');

