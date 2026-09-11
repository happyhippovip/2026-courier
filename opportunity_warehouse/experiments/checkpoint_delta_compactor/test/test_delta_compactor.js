const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { CheckpointDeltaCompactor } = require('../lib/delta_compactor');

const compactor = new CheckpointDeltaCompactor();

const stateTurn1 = {
  agentId: 'agent_executor_01',
  sessionTimestamp: '2026-09-11T12:00:00Z',
  userProfile: {
    id: 'usr_4920',
    tier: 'enterprise_platinum',
    region: 'eu-central-1',
    quota: { maxTokensPerDay: 5000000, maxConcurrentTasks: 50 },
    compliancePolicies: ['SOC2', 'GDPR', 'HIPAA', 'ISO27001', 'FEDRAMP_MODERATE']
  },
  systemPromptConfig: {
    temperature: 0.2,
    topP: 0.95,
    safetyFilters: { hateSpeech: 'block_high', selfHarm: 'block_all' },
    guardrails: ['strict_json_mode', 'no_external_egress_without_hmac']
  },
  currentTask: {
    stepIndex: 1,
    status: 'INITIALIZING',
    completedItems: []
  }
};

const stateTurn2 = {
  agentId: 'agent_executor_01',
  sessionTimestamp: '2026-09-11T12:00:00Z',
  userProfile: {
    id: 'usr_4920',
    tier: 'enterprise_platinum',
    region: 'eu-central-1',
    quota: { maxTokensPerDay: 5000000, maxConcurrentTasks: 50 },
    compliancePolicies: ['SOC2', 'GDPR', 'HIPAA', 'ISO27001', 'FEDRAMP_MODERATE']
  },
  systemPromptConfig: {
    temperature: 0.2,
    topP: 0.95,
    safetyFilters: { hateSpeech: 'block_high', selfHarm: 'block_all' },
    guardrails: ['strict_json_mode', 'no_external_egress_without_hmac']
  },
  currentTask: {
    stepIndex: 2,
    status: 'IN_PROGRESS',
    completedItems: ['step_1_verified']
  }
};

// Test 1: Delta computation replaces identical complex subtrees with $ref
const delta = compactor.computeDelta(stateTurn1, stateTurn2);
assert.deepStrictEqual(delta.userProfile, { $ref: '$.userProfile' }, 'Unchanged userProfile must be referenced');
assert.deepStrictEqual(delta.systemPromptConfig, { $ref: '$.systemPromptConfig' }, 'Unchanged systemPromptConfig must be referenced');
assert.strictEqual(delta.currentTask.stepIndex, 2);
assert.strictEqual(delta.currentTask.status, 'IN_PROGRESS');
console.log('✓ Assertion 1 Passed: Identical subtrees successfully replaced with $ref pointers');

// Test 2: Compression metrics verification
const metrics = compactor.calculateCompressionMetrics(stateTurn1, stateTurn2, delta);
assert.ok(metrics.savingsPct > 50, 'Delta compression should yield >50% token reduction on heavy states');
assert.ok(metrics.tokensSaved > 0, 'Tokens saved must be positive');
console.log('✓ Assertion 2 Passed: Compression metrics verified (>50% savings achieved: ' + metrics.savingsPct + '%)');

// Test 3: Reconstruct state from delta with 100% fidelity
const reconstructed = compactor.reconstructState(stateTurn1, delta);
assert.deepStrictEqual(reconstructed, stateTurn2, 'Reconstructed state must exactly equal stateTurn2');
console.log('✓ Assertion 3 Passed: Reconstructed state has 100% byte/structural fidelity');

// Test 4: Export evidence JSON
const evidencePath = path.resolve(__dirname, '../../../evidence/SAMPLE_CHECKPOINT_DELTA_REPORT.json');
const evidenceReport = {
  timestamp: new Date().toISOString(),
  metrics,
  deltaSample: delta,
  verifiedLossless: true
};
fs.writeFileSync(evidencePath, JSON.stringify(evidenceReport, null, 2), 'utf8');
assert.ok(fs.existsSync(evidencePath), 'Evidence report file must exist');
console.log('✓ Assertion 4 Passed: Evidence exported to SAMPLE_CHECKPOINT_DELTA_REPORT.json');

console.log('All 4 Checkpoint Delta Compactor tests passed successfully!');