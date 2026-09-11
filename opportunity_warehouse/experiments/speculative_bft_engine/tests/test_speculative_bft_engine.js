const { SpeculativeBFTEngine } = require('../lib/speculative_bft_engine');
const fs = require('fs');
const path = require('path');

console.log('Testing Speculative BFT Consensus Engine...');
const replicas = ['r0', 'r1', 'r2', 'r3'];
const engine = new SpeculativeBFTEngine(replicas, 1);

// Test 1: Fast-Path 1-RTT Unanimous Commit
const res1 = engine.submitRequest('settlement_eur5', 5.00);
console.log('✓ Test 1: Fast-path commit completed with status: ' + res1.commitRecord.path + ' (latency: ' + res1.commitRecord.latencyRTT + ' RTT)');
if (!res1.success || res1.commitRecord.path !== 'FAST_PATH_UNANIMOUS' || res1.commitRecord.latencyRTT !== 1) {
  throw new Error('Fast-path unanimous commit failed');
}

// Test 2: Fallback 2-RTT Commit when 1 replica is faulty/delayed
// We simulate 1 faulty node by overriding its speculative execute method
engine.nodes[3].speculativelyExecute = () => ({
  view: 1,
  seq: 2,
  stateDigest: 'corrupted_state_digest_hash',
  nodeId: 'r3',
  sig: 'corrupted_sig'
});

const res2 = engine.submitRequest('reserve_token', 100);
console.log('✓ Test 2: Fallback path commit completed with status: ' + res2.commitRecord.path + ' (latency: ' + res2.commitRecord.latencyRTT + ' RTT)');
if (!res2.success || res2.commitRecord.path !== 'TWO_PHASE_FALLBACK' || res2.commitRecord.latencyRTT !== 2) {
  throw new Error('Fallback path commit failed');
}

// Test 3: Total committed verification
const committed = engine.getCommittedRequests();
console.log('✓ Test 3: Total committed requests: ' + committed.length);
if (committed.length !== 2) {
  throw new Error('Committed request count mismatch');
}

// Test 4: Write verification report
const report = {
  experiment: 'speculative_bft_engine',
  phase: 483,
  timestamp: new Date().toISOString(),
  replicas: 4,
  fastPathQuorum: 4,
  fallbackQuorum: 3,
  fastPathCommitted: res1.commitRecord,
  fallbackCommitted: res2.commitRecord,
  totalCommitted: committed.length,
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_SPECULATIVE_BFT_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_SPECULATIVE_BFT_REPORT.json');

console.log('All Speculative BFT Consensus tests passed successfully!');
