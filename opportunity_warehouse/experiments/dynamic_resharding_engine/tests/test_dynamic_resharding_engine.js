const { DynamicReshardingEngine } = require('../lib/dynamic_resharding_engine');
const fs = require('fs');
const path = require('path');

console.log('Testing Dynamic Resharding Consensus Engine...');
const nodes = ['node_0', 'node_1', 'node_2', 'node_3'];
const engine = new DynamicReshardingEngine('shard_genesis', nodes, 8, 1);

// Test 1: Write 7 transactions (below threshold 8)
for (let i = 0; i < 7; i++) {
  engine.write(100 + i, 'val_' + i);
}
console.log('✓ Test 1: 7 transactions written to shard_genesis; routing table unchanged');
if (engine.routingTable.length !== 1) {
  throw new Error('Routing table split prematurely');
}

// Test 2: 8th transaction triggers dynamic BFT split
const resSplit = engine.write(107, 'val_split_trigger');
console.log('✓ Test 2: 8th transaction triggered BFT split: ' + JSON.stringify(resSplit.reconfigRecord.event));

if (!resSplit.reconfigRecord || resSplit.reconfigRecord.event !== 'DYNAMIC_BFT_SPLIT') {
  throw new Error('Dynamic BFT split was not triggered');
}

// Test 3: Verify new routing table contains 2 child shards
const routes = engine.getRoutingTable();
console.log('✓ Test 3: New routing table: ' + JSON.stringify(routes));
if (routes.length !== 2 || routes[0].shardId !== 'shard_genesis_left' || routes[1].shardId !== 'shard_genesis_right') {
  throw new Error('Routing table structure mismatch post-split');
}

// Test 4: Verify state preservation and retrieval across split shards
for (let i = 0; i <= 7; i++) {
  const val = engine.get(100 + i);
  const expected = i === 7 ? 'val_split_trigger' : 'val_' + i;
  if (val !== expected) {
    throw new Error('State lost after resharding for key ' + (100 + i) + ': got ' + val);
  }
}
console.log('✓ Test 4: All historical state verified intact across newly split shards');

// Test 5: Write verification report
const report = {
  experiment: 'dynamic_resharding_engine',
  phase: 491,
  timestamp: new Date().toISOString(),
  initialShard: 'shard_genesis',
  splitThreshold: 8,
  reconfigRecord: resSplit.reconfigRecord,
  finalRoutingTable: routes,
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_DYNAMIC_RESHARDING_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 5: Evidence report written to SAMPLE_DYNAMIC_RESHARDING_REPORT.json');

console.log('All Dynamic Resharding tests passed successfully!');
