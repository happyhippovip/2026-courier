const { PaxosMadeLiveEngine } = require('../lib/paxos_made_live_engine');
const fs = require('fs');
const path = require('path');

console.log('Testing Paxos-Made-Live Consensus Engine...');
const replicas = ['rep_0', 'rep_1', 'rep_2'];
const pml = new PaxosMadeLiveEngine(replicas, 1);

// Test 1: Elect Master and verify lease
const lease = pml.electMaster('rep_0', 10000);
if (!pml.isMasterLeaseValid() || pml.master !== 'rep_0') {
  throw new Error('Master election failed');
}
console.log('✓ Test 1: Master rep_0 elected with term ' + lease.term + ' and valid lease');

// Test 2: Replicate commands and apply to state
const cmd1 = { type: 'COMMERCIAL_SETTLE', amountEur: 5.00, orderId: 'ord_123' };
const entry1 = pml.replicateCommand(cmd1);
if (entry1.index !== 1 || !entry1.checksum) throw new Error('Replication failed');
if (pml.appliedState.balanceEur !== 5.00 || pml.appliedState.processedOrders !== 1) {
  throw new Error('State application mismatch');
}
console.log('✓ Test 2: Replicated log entry 1 with CRC checksum; applied €5.00 revenue to state machine');

// Test 3: Take Snapshot
const snap = pml.takeSnapshot();
if (!snap || snap.lastIndex !== 1 || snap.state.balanceEur !== 5.00) {
  throw new Error('Snapshot creation failed');
}
console.log('✓ Test 3: Created state machine snapshot (hash: ' + snap.snapshotHash.slice(0, 10) + '...)');

// Test 4: Write verification report
const report = {
  experiment: 'paxos_made_live_engine',
  phase: 451,
  timestamp: new Date().toISOString(),
  replicas: 3,
  master: pml.master,
  currentTerm: pml.currentTerm,
  logEntriesCount: pml.log.length,
  snapshot: snap,
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_PAXOS_MADE_LIVE_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_PAXOS_MADE_LIVE_REPORT.json');

console.log('All Paxos-Made-Live tests passed successfully!');
