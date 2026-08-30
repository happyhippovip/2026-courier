import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  resolveChiefWaitState,
  resolveCorrelationTruth,
  resolveDecisionTruth,
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

console.log('execution truth tests: PASS (100% SUCCESS)');
