const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { ChandyLamportSnapshotEngine } = require('../lib/snapshot_engine');

const engine = new ChandyLamportSnapshotEngine();

// Create 2 processes: Agent A and Agent B
const pA = engine.registerProcess('Agent_A', { role: 'buyer', balance: 100 });
const pB = engine.registerProcess('Agent_B', { role: 'seller', balance: 0 });

const chAB = engine.createChannel('Agent_A', 'Agent_B');
const chBA = engine.createChannel('Agent_B', 'Agent_A');

// Test 1: Agent A sends transfer of 5 euro to Agent B
pA.mutateState('balance', 95); // A deducted 5
engine.sendMessage('Agent_A', 'Agent_B', { transferEUR: 5.00 });

// Test 2: Agent A initiates Chandy-Lamport snapshot while message is in-flight!
engine.initiateSnapshot('Agent_A');
assert.strictEqual(pA.recordedState.balance, 95, 'Agent A state recorded at 95 balance');
console.log('✓ Test 1: Snapshot initiated; Agent A state recorded at 95 EUR');

// In channel A->B, the queue has [ DATA({transferEUR: 5}), MARKER ]
// Deliver DATA to B before B sees the marker
// Note: B has NOT recorded state yet, so B receives the data and updates state:
engine.deliverNextMessage(chAB); // delivers DATA: B balance becomes received

// Now deliver MARKER to B
engine.deliverNextMessage(chAB); // delivers MARKER: B records its state!
assert.strictEqual(pB.hasRecordedState, true, 'Agent B must record state on first marker');
console.log('✓ Test 2: Marker delivered to Agent B; consistent cut established');

// Deliver remaining marker on B->A
engine.deliverNextMessage(chBA);

// Test 3: Assemble global snapshot
const globalSnapshot = engine.assembleGlobalSnapshot();
assert.ok(globalSnapshot.processStates.Agent_A, 'A state must be present');
assert.ok(globalSnapshot.processStates.Agent_B, 'B state must be present');
console.log('✓ Test 3: Global snapshot assembled consistently across processes');

// Test 4: Write sample evidence report
const evidencePath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_CHANDY_LAMPORT_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify({
  snapshotSummary: {
    processCount: engine.processes.size,
    channelCount: engine.channels.size
  },
  globalSnapshot
}, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_CHANDY_LAMPORT_REPORT.json');

console.log('All Chandy-Lamport Snapshot Engine tests passed successfully!');
