const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { ReservoirSampler } = require('./lib/reservoir_sampler');

console.log('Testing Streaming Reservoir Sampler...');

const sampler = new ReservoirSampler(5);

// Test 1: Fill up to capacity k=5
for (let i = 0; i < 5; i++) {
  sampler.feed('token-' + i);
}
assert.strictEqual(sampler.getSample().length, 5);
assert.strictEqual(sampler.totalSeen, 5);
console.log('✓ Test 1: Reservoir filled to exact capacity k=5');

// Test 2: Process large stream of 1,000 tokens
for (let i = 5; i < 1000; i++) {
  sampler.feed('token-' + i);
}
assert.strictEqual(sampler.getSample().length, 5);
assert.strictEqual(sampler.totalSeen, 1000);
console.log('✓ Test 2: Invariant capacity 5 maintained across 1,000 stream items');

// Test 3: Statistical distribution check across 500 independent passes
const frequency = {};
for (let pass = 0; pass < 500; pass++) {
  const s = new ReservoirSampler(3);
  for (let i = 0; i < 10; i++) {
    s.feed('t' + i);
  }
  for (const item of s.getSample()) {
    frequency[item] = (frequency[item] || 0) + 1;
  }
}
// Each of the 10 items should appear ~ 150 times (3/10 * 500)
for (let i = 0; i < 10; i++) {
  const count = frequency['t' + i] || 0;
  assert.ok(count > 80 && count < 220, 'Item t' + i + ' frequency ' + count + ' within normal bounds');
}
console.log('✓ Test 3: Unbiased uniform probability distribution verified across 500 trials');

// Test 4: Write sample evidence report
const report = {
  timestamp: new Date().toISOString(),
  phase: 321,
  component: 'reservoir_sampler',
  reservoirCapacityK: 5,
  streamSizeProcessed: 1000,
  statisticalUniformityVerified: true,
  verification: '100% PASS'
};

const evidenceDir = path.join(__dirname, '..', '..', 'evidence');
fs.writeFileSync(
  path.join(evidenceDir, 'SAMPLE_RESERVOIR_SAMPLER_REPORT.json'),
  JSON.stringify(report, null, 2),
  'utf8'
);
console.log('✓ Test 4: Evidence report written to SAMPLE_RESERVOIR_SAMPLER_REPORT.json');
console.log('All Reservoir Sampler tests passed successfully!');
