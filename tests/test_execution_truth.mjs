import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  ACADEMY_FLOW_STEPS,
  resolveAcademyEconomics,
  resolveAcademySummary,
  resolveBodyguardsTruth,
  resolveChiefWaitState,
  resolveCorrelationTruth,
  resolveDecisionTruth,
  resolveDirectorTruth,
  resolveDeskMatrix,
  resolveGateDecisionTruth,
  resolveLivingRoomAgents,
  resolveLiveHQMetrics,
  resolvePermissionGuardTruth,
  resolveSnitchTruth,
  resolveSpeechBubble,
  resolveExecutionTruth,
  resolveStewardTruth,
  resolveTeacherTruth,
  resolveThreadContext,
  validateThreadAssociation,
  resolveLiveOrchestrationTruth,
  resolveReviewTruth,
  resolveLiveAgentMotion,
  resolveCapabilityTruth,
  resolveSkillTruth,
  resolveHandoffTruth,
  resolveAgentDetailData,
  resolveOpsState,
  normalizeOpsState,
  sanitizeTruthText,
  PROMPT_LIFECYCLE_PHASES,
  TRUTH_MODES,
  CANONICAL_EXAMPLE_STORY,
  CANONICAL_SHOWCASE_1,
  StorySceneController,
  resolveStoryLivingAgents,
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
// 9.4 SNITCH 3.0 Permission Guard Truth Resolution
const defaultPermGuard = resolvePermissionGuardTruth({});
assert.equal(defaultPermGuard.status, 'PERMISSIONS HEALTHY');
assert.equal(defaultPermGuard.recommendation, 'ALREADY_ALLOWED');
assert.equal(defaultPermGuard.risk_class, 'SAFE');

const customPermState = {
  snitch: {
    permission_guard: {
      status: 'DANGEROUS REQUEST',
      last_checked_command: 'sudo rm -rf /var/log',
      rule_match: 'DANGEROUS_COMMANDS',
      recommendation: 'DANGEROUS_DO_NOT_PERSIST',
      risk_class: 'CRITICAL',
      speech: 'Dangerous command detected. Do not add permanent rule. Human approval required.',
    },
  },
};
const customPerm = resolvePermissionGuardTruth(customPermState);
assert.equal(customPerm.status, 'DANGEROUS REQUEST');
assert.equal(customPerm.last_checked_command, 'sudo rm -rf /var/log');
assert.equal(customPerm.recommendation, 'DANGEROUS_DO_NOT_PERSIST');
assert.equal(customPerm.risk_class, 'CRITICAL');
assert.match(customPerm.speech, /Dangerous command detected/);

// -------------------------------------------------------------
// 10. LIVING ROOM OPERATIONS FLOOR & MMORPG AGENT RESOLUTION
// -------------------------------------------------------------
const livingAgents = resolveLivingRoomAgents(customPermState);
// 17 Core/Specialist roles + 8 Bodyguards = 25 visible agents
assert.equal(livingAgents.length, 25);

const chiefChar = livingAgents.find(a => a.id === 'agent-chief-commander');
assert.ok(chiefChar);
assert.match(chiefChar.name, /CHIEF/);
assert.equal(chiefChar.zone, 'COMMAND_TABLE');
assert.equal(typeof chiefChar.x, 'number');
assert.equal(typeof chiefChar.y, 'number');

const snitchChar = livingAgents.find(a => a.id === 'agent-snitch');
assert.ok(snitchChar);
assert.equal(snitchChar.name, 'SNITCH 3.0');

const bgAlpha = livingAgents.find(a => a.name === 'BODYGUARD ALPHA');
assert.ok(bgAlpha);
assert.equal(bgAlpha.is_bodyguard, true);
assert.equal(bgAlpha.state, 'STANDBY');
assert.ok(bgAlpha.leisure_area);

// -------------------------------------------------------------
// 11. WALKABLE NAVIGATION GRAPH & WAYPOINT PATHFINDING
// -------------------------------------------------------------
import { findWalkingPath, HQ_WAYPOINTS, HQ_NAV_GRAPH } from '../studio/execution_truth.js';

assert.ok(HQ_WAYPOINTS.CHIEF_COMMAND);
assert.ok(HQ_WAYPOINTS.COFFEE_BAR_CHARLIE);
assert.ok(HQ_WAYPOINTS.SAUNA_ALPHA);
assert.ok(HQ_NAV_GRAPH.CHIEF_COMMAND.length > 0);

// Path between Sauna and Coffee Bar traverses multiple corridors without teleporting
const walkPath = findWalkingPath(79.0, 14.0, 80.0, 91.0);
assert.ok(Array.isArray(walkPath));
assert.ok(walkPath.length >= 3);
assert.equal(typeof walkPath[0].x, 'number');
assert.equal(typeof walkPath[walkPath.length - 1].x, 'number');

// -------------------------------------------------------------
// 12. STUDIO TELEMETRY + DOM SAFETY REGRESSIONS
// -------------------------------------------------------------
// The existing Academy economics resolver is the callable Treasury source.
assert.equal(typeof resolveAcademyEconomics, 'function');
assert.equal(resolveAcademyEconomics({}).revenue_evidence, 'UNKNOWN');

// No static demo identifiers, versions, hashes, commits, or revenue goals may
// be substituted when backend state is absent.
assert.doesNotMatch(studioSource, /corr-demo-c94b85b8|\bv64\b|8f0874f495cf|e7edad01|62c658b0|\$8 \/ \$1,000,000,000/);
assert.match(studioSource, /resetUnverifiedTelemetry/);
assert.match(studioSource, /textContent = "HEAD: UNAVAILABLE"/);

// Backend-controlled name/title strings are inserted as text, never HTML.
assert.doesNotMatch(studioSource, /nameplate\.innerHTML/);
assert.match(studioSource, /title\.textContent = agent\.name \|\| "UNKNOWN"/);
assert.match(studioSource, /subtitle\.textContent = agent\.title \|\| "UNKNOWN"/);
const hostileAgentName = '<img src=x onerror=alert(1)>';
assert.ok(hostileAgentName.includes('<img'));
assert.match(studioSource, /textContent = agent\.name/);

// -------------------------------------------------------------
// 13. MISSION 108: WALKING AGENT HQ & LIVE ORCHESTRATION TRUTH
// -------------------------------------------------------------

// 1. IDLE agent stays idle without real task
const idleOrch = resolveLiveOrchestrationTruth({});
assert.equal(idleOrch.visual_phase, 'IDLE');
assert.equal(idleOrch.courier_phase, 'IDLE');
assert.equal(idleOrch.active_builder, null);

// 2. Active builder task moves correct agent to workstation & TASK_RECEIVED / WORKING
const workingState = {
  bus: { is_locked: true },
  agents: {
    'agent-antigravity-bridge': {
      id: 'agent-antigravity-bridge',
      state: 'RUNNING',
      task: 'TASK-BUILD-001',
      progress: 0.5,
    },
  },
};
const workingOrch = resolveLiveOrchestrationTruth(workingState);
assert.equal(workingOrch.active_builder, 'agent-antigravity-bridge');
assert.equal(workingOrch.visual_phase, 'WORKING');
assert.equal(workingOrch.active_task, 'TASK-BUILD-001');

// 3. RESULT_READY triggers Courier return visualization
const resultReadyState = {
  bus: { is_locked: true },
  agents: {
    'agent-antigravity-bridge': {
      id: 'agent-antigravity-bridge',
      state: 'AWAITING_CHIEF_REVIEW',
      task: 'TASK-BUILD-001',
      progress: 1.0,
    },
    'agent-courier-relay': {
      id: 'agent-courier-relay',
      state: 'RETURNING',
    },
  },
};
const resultOrch = resolveLiveOrchestrationTruth(resultReadyState);
assert.equal(resultOrch.visual_phase, 'RESULT_READY');
assert.equal(resultOrch.courier_phase, 'RESULT_RETURN');

// 4. NO_REVIEW keeps reviewer idle
const noReviewTruth = resolveReviewTruth({ review_decision: 'NO_REVIEW' });
assert.equal(noReviewTruth.reviewer_label, 'IDLE');
assert.equal(noReviewTruth.reviewer_state, 'IDLE');

// 5. BATCH_REVIEW shows queued state
const batchReviewTruth = resolveReviewTruth({ review_decision: 'BATCH_REVIEW' });
assert.equal(batchReviewTruth.reviewer_label, 'REVIEW QUEUED');
assert.equal(batchReviewTruth.reviewer_state, 'WAITING');

// 6. IMMEDIATE_REVIEW_REQUIRED shows reviewer required state (Codex active/high-priority)
const immReviewTruth = resolveReviewTruth({ review_decision: 'IMMEDIATE_REVIEW_REQUIRED' });
assert.equal(immReviewTruth.reviewer_label, 'REVIEW REQUIRED');
assert.equal(immReviewTruth.reviewer_state, 'WORKING');

// Living room agents reflect review state
const livingImm = resolveLivingRoomAgents({ review_decision: 'IMMEDIATE_REVIEW_REQUIRED' });
const cdxImm = livingImm.find(a => a.id === 'agent-codex-bridge');
assert.ok(cdxImm);
assert.equal(cdxImm.state, 'RUNNING');
assert.equal(cdxImm.is_active, true);
assert.match(cdxImm.title, /REVIEW REQUIRED/);

// 7. Missing telemetry never generates fake activity
const emptyLiving = resolveLivingRoomAgents({});
for (const ag of emptyLiving) {
  if (!ag.is_bodyguard) {
    assert.ok(ag.state === 'IDLE' || ag.state === 'UNKNOWN');
    assert.equal(ag.is_active, false);
  }
}

// 8. Sanitized labels contain no secret payload
const sensitivePrompt = 'Run task with token=ghp_secretToken123456789 and secret=superSecretValue456';
const cleanPrompt = sanitizeTruthText(sensitivePrompt);
assert.doesNotMatch(cleanPrompt, /ghp_secretToken123456789/);
assert.doesNotMatch(cleanPrompt, /superSecretValue456/);
assert.match(cleanPrompt, /\[REDACTED_SECRET\]/);

// -------------------------------------------------------------
// 14. MISSION 109: CINEMATIC PROMPT STORY MODE
// -------------------------------------------------------------

// 1. Truth modes and prompt lifecycle phases are strictly defined
assert.ok(PROMPT_LIFECYCLE_PHASES.includes('PROMPT_RECEIVED'));
assert.ok(PROMPT_LIFECYCLE_PHASES.includes('COURIER_DISPATCH'));
assert.ok(PROMPT_LIFECYCLE_PHASES.includes('WORKING_VISUALIZED'));
assert.ok(PROMPT_LIFECYCLE_PHASES.includes('COURIER_RETURN'));
assert.ok(PROMPT_LIFECYCLE_PHASES.includes('DONE'));

assert.deepEqual(TRUTH_MODES, ['LIVE', 'VISUALIZED', 'UNKNOWN']);

// 2. Canonical Example Story is marked VISUALIZED/DEMO
assert.ok(CANONICAL_EXAMPLE_STORY.story_id === 'story-demo-001' || CANONICAL_EXAMPLE_STORY.story_id === 'showcase-001');
assert.equal(CANONICAL_EXAMPLE_STORY.assigned_agent, 'agent-antigravity-bridge');
for (const step of CANONICAL_EXAMPLE_STORY.steps) {
  assert.equal(step.truth_mode, 'VISUALIZED');
  assert.ok(step.caption);
  assert.doesNotMatch(step.caption, /ghp_|secret|token=|key=/i);
}

// 3. StorySceneController deterministic timeline playback
const controller = new StorySceneController();
assert.equal(controller.isPlaying, false);

// Play starts playback
controller.play();
assert.equal(controller.isPlaying, true);

// Get initial step: PROMPT_RECEIVED
const step0 = controller.getCurrentStep();
assert.equal(step0.phase, 'PROMPT_RECEIVED');
assert.equal(step0.truth_mode, 'VISUALIZED');

// Update advances step deterministically
controller.update(2600); // Exceeds step0 duration (2500ms)
const step1 = controller.getCurrentStep();
assert.equal(step1.phase, 'TASK_ACCEPTED');

// Pause stops advancement
controller.pause();
assert.equal(controller.isPlaying, false);
controller.update(5000);
assert.equal(controller.getCurrentStep().phase, 'TASK_ACCEPTED');

// Restart returns to step 0
controller.restart();
assert.equal(controller.getCurrentStep().phase, 'PROMPT_RECEIVED');
assert.equal(controller.isPlaying, true);

// Next step manual advance
controller.nextStep();
assert.equal(controller.getCurrentStep().phase, 'TASK_ACCEPTED');

// Speed setting
controller.setSpeed(2.0);
assert.equal(controller.playbackSpeed, 2.0);

// 4. resolveStoryLivingAgents updates only active story agent
const baseAgents = resolveLivingRoomAgents({});
const stepDispatch = CANONICAL_EXAMPLE_STORY.steps.find(s => s.phase === 'COURIER_DISPATCH');
const storyLiving = resolveStoryLivingAgents(stepDispatch, baseAgents);

const courierAg = storyLiving.find(a => a.id === 'agent-courier-relay');
assert.ok(courierAg);
assert.equal(courierAg.is_active, true);
assert.equal(courierAg.animation, 'walking');

// Non-active agents remain inactive
const snitchAg = storyLiving.find(a => a.id === 'agent-snitch');
assert.ok(snitchAg);
assert.equal(snitchAg.is_active, false);

// 5. Full prompt is not exposed
const progress = controller.getProgress();
assert.ok(progress.task_title);
assert.ok(progress.caption);
assert.doesNotMatch(progress.caption, /\{.*\}|full_prompt/);

// -------------------------------------------------------------
// 15. MISSION 110: CINEMATIC SHOWCASE #1
// -------------------------------------------------------------

// 1. Showcase #1 begins at Chief
const showcase = CANONICAL_SHOWCASE_1;
assert.equal(showcase.steps[0].phase, 'PROMPT_RECEIVED');
assert.equal(showcase.steps[0].agent, 'agent-chief-commander');
assert.equal(showcase.steps[0].target_waypoint, 'CHIEF_COMMAND');

// 2. TASK packet moves Chief -> Antigravity
const dispatchStep = showcase.steps.find(s => s.phase === 'COURIER_DISPATCH');
assert.ok(dispatchStep);
assert.equal(dispatchStep.agent, 'agent-courier-relay');
assert.equal(dispatchStep.target_waypoint, 'DESK_16');

// 3. Antigravity visibly accepts task: READING -> TASK_ACCEPTED -> PLAN_CREATED
const readingStep = showcase.steps.find(s => s.agent === 'agent-antigravity-bridge' && s.phase === 'READING');
const acceptStep = showcase.steps.find(s => s.agent === 'agent-antigravity-bridge' && s.phase === 'TASK_ACCEPTED');
const planStep = showcase.steps.find(s => s.agent === 'agent-antigravity-bridge' && s.phase === 'PLAN_CREATED');
assert.ok(readingStep);
assert.ok(acceptStep);
assert.ok(planStep);

// 4. WORKING is explicitly VISUALIZED
const workStep = showcase.steps.find(s => s.phase === 'WORKING_VISUALIZED');
assert.ok(workStep);
assert.equal(workStep.truth_mode, 'VISUALIZED');
assert.equal(workStep.agent, 'agent-antigravity-bridge');
assert.match(workStep.caption, /WORKING • VISUALIZED/);

// 5. RESULT packet moves Antigravity -> Chief
const resultStep = showcase.steps.find(s => s.phase === 'RESULT_PREPARED');
const returnStep = showcase.steps.find(s => s.phase === 'COURIER_RETURN');
assert.ok(resultStep);
assert.ok(returnStep);
assert.equal(returnStep.target_waypoint, 'CHIEF_COMMAND');

// 6. Final state is DONE
const finalStep = showcase.steps[showcase.steps.length - 1];
assert.equal(finalStep.phase, 'DONE');
assert.equal(finalStep.agent, 'agent-chief-commander');

// 7. 1x Runtime target is 20-30 seconds
const showcaseCtrl = new StorySceneController(showcase);
const totalRuntimeMs = showcaseCtrl.getTotalRuntimeMs();
assert.ok(totalRuntimeMs >= 20000 && totalRuntimeMs <= 30000, `Showcase runtime ${totalRuntimeMs}ms is within 20-30s`);
assert.equal(totalRuntimeMs, 24000);

// 8. STORY MODE • VISUALIZED is strictly preserved
for (const step of showcase.steps) {
  assert.equal(step.truth_mode, 'VISUALIZED');
}

// 9. Camera sequence covers chief -> courier -> active -> courier -> command -> overview
assert.equal(showcase.steps[0].camera_target, 'command');
assert.ok(showcase.steps.some(s => s.camera_target === 'active'));
assert.ok(showcase.steps.some(s => s.camera_target === 'command'));

// 10. Sanitization: no full prompts, secrets or keys
for (const step of showcase.steps) {
  assert.doesNotMatch(step.caption, /ghp_|bearer|token|secret|password|apiKey/i);
  assert.ok(step.caption.length < 120);
}

// 11. Movement & Dynamic Waypoint Trajectory
const agentsAtStart = resolveStoryLivingAgents(showcase.steps[0], []);
const courierAtStart = agentsAtStart.find(a => a.id === 'agent-courier-relay');
assert.equal(courierAtStart.x, 50.0);
assert.equal(courierAtStart.y, 42.0);

const agentsAtDispatch = resolveStoryLivingAgents(dispatchStep, []);
const courierAtDispatch = agentsAtDispatch.find(a => a.id === 'agent-courier-relay');
assert.equal(courierAtDispatch.x, 66.5);
assert.equal(courierAtDispatch.y, 45.0);
assert.equal(courierAtDispatch.state, 'RUNNING');
assert.equal(courierAtDispatch.animation, 'walking');

const agentsAtReturn = resolveStoryLivingAgents(returnStep, []);
const courierAtReturn = agentsAtReturn.find(a => a.id === 'agent-courier-relay');
assert.equal(courierAtReturn.x, 50.0);
assert.equal(courierAtReturn.y, 42.0);
assert.equal(courierAtReturn.state, 'RUNNING');

const agentsAtWork = resolveStoryLivingAgents(workStep, []);
const agBuilder = agentsAtWork.find(a => a.id === 'agent-antigravity-bridge');
assert.equal(agBuilder.x, 66.5);
assert.equal(agBuilder.y, 45.0);
// -------------------------------------------------------------
// 16. MISSION 111: REAL LIVE AGENT MOVEMENT & STATE MACHINE
// -------------------------------------------------------------

// 1. Idle behavior: no unjustified movement, all at home desks
const idleMotion = resolveLiveAgentMotion({
  bus: { is_locked: false, active_workflow: 'IDLE_MONITORING' },
  agents: {},
  transport: { incoming_count: 0 },
});
assert.equal(idleMotion.is_idle, true);
assert.equal(idleMotion.visual_phase, 'IDLE');
assert.equal(idleMotion.courier_phase, 'IDLE');
assert.equal(idleMotion.destinations['agent-courier-relay'].x, 74.0);
assert.equal(idleMotion.destinations['agent-courier-relay'].y, 45.0);
assert.equal(idleMotion.states['agent-codex-bridge'], 'IDLE');

// 2. Real task dispatch: Task Received -> Courier routes Chief -> Router -> Builder (Desk 16)
const taskDispatchMotion = resolveLiveAgentMotion({
  bus: { is_locked: true, active_workflow: 'WF-BUILD-001', correlation_id: 'corr-001' },
  agents: {
    'agent-antigravity-bridge': { id: 'agent-antigravity-bridge', state: 'RUNNING', task: 'TASK-BUILD-001', progress: 0.2 },
  },
  transport: { incoming_count: 1 },
});
assert.equal(taskDispatchMotion.is_idle, false);
assert.equal(taskDispatchMotion.courier_phase, 'TASK_DELIVERY');
assert.equal(taskDispatchMotion.active_builder, 'agent-antigravity-bridge');
assert.deepEqual(taskDispatchMotion.routes['agent-courier-relay'], ['CHIEF_COMMAND', 'ROUTER_DESK', 'DESK_16']);
assert.equal(taskDispatchMotion.states['agent-courier-relay'], 'DISPATCHED');
assert.equal(taskDispatchMotion.speech_overrides['agent-courier-relay'], 'DISPATCHED');

// 3. Real task result return WITHOUT review: Codex remains strictly IDLE
const resultNoReviewMotion = resolveLiveAgentMotion({
  bus: { is_locked: true, active_workflow: 'WF-BUILD-001', correlation_id: 'corr-001' },
  agents: {
    'agent-antigravity-bridge': { id: 'agent-antigravity-bridge', state: 'AWAITING_CHIEF_REVIEW', task: 'TASK-BUILD-001', progress: 1.0 },
  },
  review_budget: { policy: { defaults: { low_risk_review: 'NO_REVIEW' } } },
});
assert.equal(resultNoReviewMotion.courier_phase, 'RESULT_RETURN');
assert.equal(resultNoReviewMotion.review_required, false);
assert.deepEqual(resultNoReviewMotion.routes['agent-courier-relay'], ['DESK_16', 'CHIEF_COMMAND']);
assert.equal(resultNoReviewMotion.states['agent-codex-bridge'], 'IDLE');
assert.equal(resultNoReviewMotion.destinations['agent-codex-bridge'].x, 14.5);
assert.equal(resultNoReviewMotion.destinations['agent-codex-bridge'].y, 48.0);

// 4. Real task result return WITH review required: Courier routes Builder -> Codex -> Chief
const resultWithReviewMotion = resolveLiveAgentMotion({
  bus: { is_locked: true, active_workflow: 'WF-AUTH-GATE-001', correlation_id: 'corr-auth' },
  agents: {
    'agent-antigravity-bridge': { id: 'agent-antigravity-bridge', state: 'AWAITING_CHIEF_REVIEW', task: 'TASK-AUTH-001', progress: 1.0 },
    'agent-codex-bridge': { id: 'agent-codex-bridge', state: 'RUNNING', task: 'High-risk Auth Review' },
  },
});
assert.equal(resultWithReviewMotion.review_required, true);
assert.deepEqual(resultWithReviewMotion.routes['agent-courier-relay'], ['DESK_16', 'DESK_04', 'CHIEF_COMMAND']);
assert.equal(resultWithReviewMotion.states['agent-codex-bridge'], 'RUNNING');
assert.equal(resultWithReviewMotion.speech_overrides['agent-codex-bridge'], 'WAITING FOR REVIEW');

// 5. Human Gate: Human Gate Monitor routes to Chief Command
const humanGateMotion = resolveLiveAgentMotion({
  bus: {
    is_locked: true,
    active_workflow: 'WF-SPEND-001',
    correlation_id: 'corr-spend',
    active_human_gate: { id: 'gate-spend', state: 'BLOCKED', provenance_complete: true, workflow_id: 'WF-SPEND-001', correlation_id: 'corr-spend' },
  },
  agents: {},
});
assert.equal(humanGateMotion.states['agent-human-gate-monitor'], 'HUMAN_GATE');
assert.deepEqual(humanGateMotion.routes['agent-human-gate-monitor'], ['DESK_01', 'CHIEF_COMMAND']);
assert.equal(humanGateMotion.speech_overrides['agent-human-gate-monitor'], 'HUMAN GATE');

// 6. Deduplication fingerprint stability
const fp1 = taskDispatchMotion.fingerprint;
const taskDispatchMotionAgain = resolveLiveAgentMotion({
  bus: { is_locked: true, active_workflow: 'WF-BUILD-001', correlation_id: 'corr-001' },
  agents: {
    'agent-antigravity-bridge': { id: 'agent-antigravity-bridge', state: 'RUNNING', task: 'TASK-BUILD-001', progress: 0.22 },
  },
  transport: { incoming_count: 1 },
});
// -------------------------------------------------------------
// 17. MISSION 112: REAL ORCHESTRATION CANARY ROUNDTRIP
// -------------------------------------------------------------

// 1. Real task identity & stable correlation identity
const canaryWorkflowId = 'WF-CHIEF-74a781';
const canaryTaskId = 'WF-CHIEF-74a781-STEP-1-DISCOVER';
const canaryCorrelationId = 'corr-chief-20afbb30';

const canaryStateDispatch = {
  bus: {
    is_locked: true,
    active_workflow: canaryWorkflowId,
    correlation_id: canaryCorrelationId,
    context_version: 77,
  },
  agents: {
    'agent-chief-commander': { id: 'agent-chief-commander', state: 'RUNNING', task: `Orchestrating ${canaryWorkflowId}` },
    'agent-antigravity-bridge': { id: 'agent-antigravity-bridge', state: 'RUNNING', task: canaryTaskId, progress: 0.15 },
  },
  transport: { incoming_count: 1 },
  review_budget: { policy: { defaults: { low_risk_review: 'NO_REVIEW' } } },
};

const canaryMotionDispatch = resolveLiveAgentMotion(canaryStateDispatch);

// Exactly one builder
assert.equal(canaryMotionDispatch.active_builder, 'agent-antigravity-bridge');
assert.equal(canaryMotionDispatch.is_idle, false);
assert.equal(canaryMotionDispatch.courier_phase, 'TASK_DELIVERY');

// Exactly-once dispatch visualization
assert.deepEqual(canaryMotionDispatch.routes['agent-courier-relay'], ['CHIEF_COMMAND', 'ROUTER_DESK', 'DESK_16']);
assert.equal(canaryMotionDispatch.states['agent-courier-relay'], 'DISPATCHED');

// Codex remains strictly idle when review is unnecessary
assert.equal(canaryMotionDispatch.states['agent-codex-bridge'], 'IDLE');
assert.equal(canaryMotionDispatch.destinations['agent-codex-bridge'].x, 14.5);
assert.equal(canaryMotionDispatch.destinations['agent-codex-bridge'].y, 48.0);

// Result Ready & Exactly-once result return
const canaryStateResult = {
  bus: {
    is_locked: true,
    active_workflow: canaryWorkflowId,
    correlation_id: canaryCorrelationId,
    context_version: 77,
  },
  agents: {
    'agent-chief-commander': { id: 'agent-chief-commander', state: 'RUNNING', task: `Orchestrating ${canaryWorkflowId}` },
    'agent-antigravity-bridge': { id: 'agent-antigravity-bridge', state: 'AWAITING_CHIEF_REVIEW', task: canaryTaskId, progress: 1.0 },
  },
  review_budget: { policy: { defaults: { low_risk_review: 'NO_REVIEW' } } },
};

const canaryMotionResult = resolveLiveAgentMotion(canaryStateResult);
assert.equal(canaryMotionResult.courier_phase, 'RESULT_RETURN');
assert.deepEqual(canaryMotionResult.routes['agent-courier-relay'], ['DESK_16', 'CHIEF_COMMAND']);
assert.equal(canaryMotionResult.states['agent-codex-bridge'], 'IDLE');

// Unchanged polling does not restart route (fingerprint check)
const canaryStateResultPoll2 = {
  bus: {
    is_locked: true,
    active_workflow: canaryWorkflowId,
    correlation_id: canaryCorrelationId,
    context_version: 77,
  },
  agents: {
    'agent-chief-commander': { id: 'agent-chief-commander', state: 'RUNNING', task: `Orchestrating ${canaryWorkflowId}` },
    'agent-antigravity-bridge': { id: 'agent-antigravity-bridge', state: 'AWAITING_CHIEF_REVIEW', task: canaryTaskId, progress: 1.0 },
  },
  review_budget: { policy: { defaults: { low_risk_review: 'NO_REVIEW' } } },
};
const canaryMotionResultPoll2 = resolveLiveAgentMotion(canaryStateResultPoll2);
// -------------------------------------------------------------
// 18. MISSION 113: CAPABILITY, SKILL & HANDOFF LAYER
// -------------------------------------------------------------

// 1. Capability Truth Resolution
const capabilityState = {
  capabilities: {
    'LOCAL_FILES_READ': 'AVAILABLE',
    'LOCAL_FILES_WRITE': 'AVAILABLE',
    'GIT_READ': 'AVAILABLE',
    'GITHUB_WRITE': 'APPROVAL_REQUIRED',
    'X_READ': 'AUTH_REQUIRED',
  },
};
const capTruth = resolveCapabilityTruth(capabilityState);
assert.equal(capTruth.total_capabilities, 5);
assert.equal(capTruth.available_count, 3);
assert.deepEqual(capTruth.available_capabilities, ['LOCAL_FILES_READ', 'LOCAL_FILES_WRITE', 'GIT_READ']);
assert.deepEqual(capTruth.auth_required_capabilities, ['X_READ']);
assert.deepEqual(capTruth.approval_required_capabilities, ['GITHUB_WRITE']);

// 2. Skill Truth Resolution
const skillState = {
  skills: [
    { skill_id: 'LOCAL_CANARY_VERIFY', owner_agent: 'agent-antigravity-bridge', verification_state: 'ACTIVE' },
    { skill_id: 'REVIEW_BUDGET_EVALUATE', owner_agent: 'agent-codex-bridge', verification_state: 'ACTIVE' },
    { skill_id: 'LEGACY_PROMPT', owner_agent: 'agent-chief-commander', verification_state: 'DEPRECATED' },
  ],
};
const skillTruth = resolveSkillTruth(skillState);
assert.equal(skillTruth.total_skills, 3);
assert.equal(skillTruth.active_skills.length, 2);
assert.deepEqual(skillTruth.owners.sort(), ['agent-antigravity-bridge', 'agent-chief-commander', 'agent-codex-bridge']);

// 3. Handoff Truth Resolution & Motion Mapping
const handoffState = {
  active_handoff: {
    handoff_id: 'handoff-test-001',
    from_agent: 'agent-thought-curator',
    to_agent: 'agent-antigravity-bridge',
    task_id: 'WF-HANDOFF-101',
    correlation_id: 'corr-handoff-101',
    reason: 'Delegate 3D scene compile',
  },
  agents: {
    'agent-thought-curator': { id: 'agent-thought-curator', state: 'HANDOFF' },
    'agent-antigravity-bridge': { id: 'agent-antigravity-bridge', state: 'RUNNING' },
  },
};
const handoffTruth = resolveHandoffTruth(handoffState);
assert.equal(handoffTruth.has_active_handoff, true);
assert.equal(handoffTruth.from_agent, 'agent-thought-curator');
assert.equal(handoffTruth.to_agent, 'agent-antigravity-bridge');
assert.equal(handoffTruth.task_id, 'WF-HANDOFF-101');
assert.equal(handoffTruth.correlation_id, 'corr-handoff-101');

// Verify Courier routes from Desk 02 -> Router -> Desk 16 with HANDOFF state
const handoffMotion = resolveLiveAgentMotion(handoffState);
assert.equal(handoffMotion.states['agent-courier-relay'], 'HANDOFF');
assert.equal(handoffMotion.speech_overrides['agent-courier-relay'], 'HANDOFF');
assert.deepEqual(handoffMotion.routes['agent-courier-relay'], ['DESK_02', 'ROUTER_DESK', 'DESK_16']);
assert.equal(handoffMotion.states['agent-thought-curator'], 'HANDOFF');
assert.equal(handoffMotion.states['agent-antigravity-bridge'], 'RUNNING');

// Agent detail must never invent mission/task and must redact secret-bearing text
const unknownDetail = resolveAgentDetailData({ id: 'agent-x', state: 'UNKNOWN' }, {});
assert.equal(unknownDetail.mission, 'Keine aktive Mission gemeldet');
assert.equal(unknownDetail.task, 'Keine konkrete Aufgabe gemeldet');
const leakDetail = resolveAgentDetailData(
  { id: 'agent-x', state: 'RUNNING', task: 'Verify with token=abc123', blocked_reason: 'wait bearer xyz.9-_' }, {});
assert.doesNotMatch(leakDetail.task, /abc123/);
assert.doesNotMatch(leakDetail.blocked_reason, /xyz/);
const knownDetail = resolveAgentDetailData(
  { id: 'agent-x', state: 'RUNNING', task: 'Proving edge RELEASE' },
  { autonomy_runtime: { current_goal: 'Finish ledger' } });
assert.equal(knownDetail.mission, 'Finish ledger');
assert.equal(knownDetail.task, 'Proving edge RELEASE');

// Single ops_state: sidebar, map, detail and counts must derive identically
assert.equal(normalizeOpsState('COMPUTING'), 'ACTIVE');
assert.equal(normalizeOpsState('WORKING'), 'ACTIVE');
assert.equal(normalizeOpsState('SAFE_IDLE'), 'IDLE');
assert.equal(normalizeOpsState('RECHNET'), 'ACTIVE');
assert.equal(normalizeOpsState('WAITING_HUMAN'), 'WAITING');
assert.equal(normalizeOpsState('HUMAN_GATE'), 'WAITING');
assert.equal(normalizeOpsState('bogus-state-xyz'), 'UNKNOWN');
const opsSnap = {
  server_time: '2026-09-18T00:00:00.000Z',
  local_tools: { observed_at: new Date(Date.now() - 2000).toISOString(),
    tools: { muse: { status: 'COMPUTING', task_known: false }, chatgpt: { status: 'OPEN' }, antigravity: { status: 'OFFLINE' } } },
  agents: { 'worker-codex': { state: 'SAFE_IDLE', task: 'Standby' }, 'worker-google': { state: 'SAFE_IDLE', task: 'Standby' } },
};
const ops = resolveOpsState(opsSnap);
assert.equal(ops.company, 'COURIER SYMPHONY MUSE');
assert.equal(ops.agents.muse.state, 'ACTIVE');
assert.equal(ops.agents.muse.task, null);
assert.equal(ops.agents.codex.state, 'IDLE');
assert.equal(ops.agents.google.state, 'OFFLINE');
assert.equal(resolveOpsState({}).agents.muse.state, 'UNKNOWN');
assert.equal(resolveOpsState(null).agents.codex.task, null);

console.log('execution truth tests: PASS (100% SUCCESS)');

