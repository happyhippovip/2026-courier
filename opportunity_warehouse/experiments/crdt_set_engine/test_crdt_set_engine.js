const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { PNCounter, ORSet } = require('./lib/crdt_set_engine');

console.log('Testing CRDT PN-Counter & OR-Set Engine...');

// Test 1: Distributed PN-Counter concurrent operations
const c1 = new PNCounter('node-a');
const c2 = new PNCounter('node-b');

c1.increment(10);
c1.decrement(2);
assert.strictEqual(c1.value(), 8);

c2.increment(50);
c2.decrement(10);
assert.strictEqual(c2.value(), 40);

// Merge c1 and c2
c1.merge(c2);
c2.merge(c1);
assert.strictEqual(c1.value(), 48); // (10-2) + (50-10) = 48
assert.strictEqual(c2.value(), 48);
console.log('✓ Test 1: PN-Counter commutative merge verified (both nodes reached value 48)');

// Test 2: Distributed OR-Set add-remove-add causality
const setA = new ORSet();
const setB = new ORSet();

setA.add('symphony');
setA.add('context');

setB.merge(setA);
assert.deepStrictEqual(setB.read().sort(), ['context', 'symphony']);

// Node B removes 'context' while Node A adds 'optimizer'
setB.remove('context');
setA.add('optimizer');

setA.merge(setB);
setB.merge(setA);
assert.deepStrictEqual(setA.read().sort(), ['optimizer', 'symphony']);
assert.deepStrictEqual(setB.read().sort(), ['optimizer', 'symphony']);
console.log('✓ Test 2: OR-Set conflict-free convergence verified without coordination');

// Test 3: Write sample evidence report
const report = {
  timestamp: new Date().toISOString(),
  phase: 359,
  component: 'crdt_set_engine',
  finalCounterValue: c1.value(),
  finalOrSetMembers: setA.read(),
  conflictFreeConvergenceVerified: true,
  verification: '100% PASS'
};

const evidenceDir = path.join(__dirname, '..', '..', 'evidence');
fs.writeFileSync(
  path.join(evidenceDir, 'SAMPLE_CRDT_ENGINE_REPORT.json'),
  JSON.stringify(report, null, 2),
  'utf8'
);
console.log('✓ Test 3: Evidence report written to SAMPLE_CRDT_ENGINE_REPORT.json');
console.log('All CRDT Engine tests passed successfully!');
