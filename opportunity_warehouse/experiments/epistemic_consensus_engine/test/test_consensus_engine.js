const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { EpistemicConsensusEngine } = require('../lib/consensus_engine');

console.log('--- Testing Epistemic Consensus & Dispute Resolution Engine ---');

const engine = new EpistemicConsensusEngine();

// Submit conflicting claims on database caching strategy
engine.submitClaim('agent_eng', 'engineer', 'claim_1', 'cache_strategy', 'We should use local in-memory Map for caching query results without Redis dependency.', 0.85);
engine.submitClaim('agent_sec', 'security_gate', 'claim_2', 'cache_strategy', 'In-memory caching is rejected due to multi-tenant memory leak risks; Redis with TLS must be used.', 0.95);
engine.submitClaim('agent_arch', 'architect', 'claim_3', 'cache_strategy', 'Redis cluster with sentinel failover is preferred for horizontal scaling.', 0.90);

// Test 1: Dispute detection
const disputes = engine.detectDisputes();
assert.strictEqual(disputes.length, 1, 'Must detect 1 topic dispute');
assert.strictEqual(disputes[0].claimCount, 3, 'Must identify 3 conflicting claims on cache_strategy');
console.log('✓ Assertion 1 Passed: Multi-agent topic contradiction accurately detected');

// Test 2: Consensus resolution via role authority weighting
const resolution = engine.resolveConsensus();
assert.strictEqual(resolution.totalDisputesResolved, 1);
const res = resolution.consensusLedger[0];
assert.strictEqual(res.winningRole, 'security_gate', 'Security Gate authority must override engineer and architect');
assert.strictEqual(res.prunedCounterClaimsCount, 2, '2 lower-authority counter-claims pruned');
console.log('✓ Assertion 2 Passed: Authority-weighted resolution selected security gate policy');

// Test 3: Token savings from dispute history compaction
assert.ok(resolution.totalTokensSaved > 0, 'Consensus synthesis must save tokens vs raw chat argument');
console.log('✓ Assertion 3 Passed: Dispute history synthesized into concise consensus statement (' + resolution.totalTokensSaved + ' tokens saved)');

// Test 4: Export evidence JSON
const evidencePath = path.resolve(__dirname, '../../../evidence/SAMPLE_EPISTEMIC_CONSENSUS_LEDGER.json');
fs.writeFileSync(evidencePath, JSON.stringify(resolution, null, 2), 'utf8');
assert.ok(fs.existsSync(evidencePath), 'Evidence ledger must exist');
console.log('✓ Assertion 4 Passed: Evidence exported to SAMPLE_EPISTEMIC_CONSENSUS_LEDGER.json');

console.log('All 4 Epistemic Consensus tests passed successfully!');