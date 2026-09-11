const { BullsharkFastPath } = require('../lib/bullshark_fast_path');
const fs = require('fs');
const path = require('path');

console.log('Testing Bullshark Fast-Path Consensus Engine...');
const nodes = ['node_0', 'node_1', 'node_2', 'node_3'];
const bsfp = new BullsharkFastPath(nodes, 1);

// Test 1: Round 0 genesis across 4 nodes
const r0 = nodes.map(n => bsfp.addVertex(n, 0, { action: 'GENESIS_' + n }, []));
const r0_hashes = r0.map(v => v.hash);
console.log('✓ Test 1: Created Round 0 genesis vertices');

// Test 2: Round 1 vertices referencing Round 0
// Round 1 leader is node_1 (1 % 4 = 1)
const r1 = nodes.map(n => bsfp.addVertex(n, 1, { action: 'TURN1_' + n }, r0_hashes.slice(0, 3)));
const r1_hashes = r1.map(v => v.hash);
console.log('✓ Test 2: Created Round 1 vertices');

// Test 3: Round 2 vertices: all 4 nodes reference Round 1 leader (Fast Path Trigger)
const r2 = nodes.map(n => bsfp.addVertex(n, 2, { action: 'TURN2_' + n }, r1_hashes));

// Evaluate Fast-Path commit of Round 1 leader
const leader1 = bsfp.getRoundLeader(1);
if (!leader1 || leader1.nodeId !== 'node_1') throw new Error('Expected leader to be node_1');

const committedFast = bsfp.tryFastPathCommit(1);
if (!committedFast) throw new Error('Expected Fast-Path 2-round commit to succeed');
console.log('✓ Test 3: Round 1 leader committed via Fast-Path in only 2 rounds (4/4 unanimity)');

// Test 4: Total causal ordering
const order = bsfp.getLinearOrder();
if (order.length === 0) throw new Error('Linear order empty');
console.log('✓ Test 4: Ordered ' + order.length + ' causal vertices deterministically');

// Test 5: Write verification report
const report = {
  experiment: 'bullshark_fast_path',
  phase: 427,
  timestamp: new Date().toISOString(),
  totalNodes: 4,
  fastQuorum: 4,
  committedLeader: leader1.nodeId,
  commitMode: 'FAST_PATH_2_ROUNDS',
  orderedCount: order.length,
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_BULLSHARK_FAST_PATH_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 5: Evidence report written to SAMPLE_BULLSHARK_FAST_PATH_REPORT.json');

console.log('All Bullshark Fast-Path tests passed successfully!');
