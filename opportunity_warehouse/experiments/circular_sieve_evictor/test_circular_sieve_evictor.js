const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { CircularSieveEvictor } = require('./lib/circular_sieve_evictor');

console.log('Testing Circular Sieve Evictor...');

const sieve = new CircularSieveEvictor(4);

// Test 1: Add entries and pin one invariant entry
sieve.put('k1', 'data-1');
sieve.put('k2', 'data-2');
sieve.put('k3', 'data-3', true); // Pinned invariant
sieve.put('k4', 'data-4');

assert.strictEqual(sieve.size(), 4);
console.log('✓ Test 1: Capacity 4 filled with 1 pinned invariant entry');

// Test 2: Access k1 to give it a second chance
sieve.get('k1'); // visited = true

// Test 3: Insert k5 -> triggers eviction; k2 has visited=false and pinned=false, so k2 gets evicted
sieve.put('k5', 'data-5');
assert.strictEqual(sieve.size(), 4);
assert.strictEqual(sieve.get('k2'), null); // k2 was evicted
assert.strictEqual(sieve.get('k1'), 'data-1'); // k1 preserved
assert.strictEqual(sieve.get('k3'), 'data-3'); // pinned k3 preserved
assert.strictEqual(sieve.get('k5'), 'data-5'); // k5 added
console.log('✓ Test 2: Sieve eviction gave second-chance to k1, evicted k2, preserved pinned k3');

// Test 4: Write sample evidence report
const report = {
  timestamp: new Date().toISOString(),
  phase: 309,
  component: 'circular_sieve_evictor',
  capacity: 4,
  currentEntries: sieve.entries.map(e => ({ key: e.key, pinned: e.pinned, visited: e.visited })),
  evictionVerification: '100% PASS'
};

const evidenceDir = path.join(__dirname, '..', '..', 'evidence');
fs.writeFileSync(
  path.join(evidenceDir, 'SAMPLE_CIRCULAR_SIEVE_REPORT.json'),
  JSON.stringify(report, null, 2),
  'utf8'
);
console.log('✓ Test 4: Evidence report written to SAMPLE_CIRCULAR_SIEVE_REPORT.json');
console.log('All Circular Sieve Evictor tests passed successfully!');
