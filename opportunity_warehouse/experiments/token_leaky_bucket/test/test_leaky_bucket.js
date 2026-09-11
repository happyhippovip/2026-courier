const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { TokenLeakyBucket } = require('../lib/leaky_bucket');

let simTime = 1000000; // simulated start time in ms
const bucket = new TokenLeakyBucket({ capacity: 500, leakRate: 100, startTime: simTime });

// Test 1: Immediate consumption within capacity
const res1 = bucket.tryConsume(300, simTime);
assert.strictEqual(res1.allowed, true, 'First 300 tokens must be allowed');
assert.strictEqual(res1.currentWater, 300);
assert.strictEqual(res1.waitMs, 0);
console.log('✓ Test 1: Allowed 300 tokens within burst capacity (water: 300/500)');

// Test 2: Consumption exceeding capacity returns allowed: false with waitMs
const res2 = bucket.tryConsume(300, simTime); // 300 + 300 = 600 > 500 (excess: 100)
assert.strictEqual(res2.allowed, false, 'Should reject when burst capacity exceeded');
assert.strictEqual(res2.waitMs, 1000, 'Wait time should be 1000ms (100 tokens / 100 tokens/sec)');
console.log('✓ Test 2: Excess request cleanly rejected with ' + res2.waitMs + 'ms backpressure delay');

// Test 3: Advancing virtual time leaks water and allows subsequent request
simTime += 2000; // 2 seconds elapsed -> leaks 200 tokens (water: 300 - 200 = 100)
const res3 = bucket.tryConsume(300, simTime); // 100 + 300 = 400 <= 500
assert.strictEqual(res3.allowed, true, 'Request should be allowed after leaking water');
assert.strictEqual(res3.currentWater, 400);
console.log('✓ Test 3: Water leaked over 2000ms; new request succeeded (water: 400/500)');

// Test 4: Write sample evidence report
const evidencePath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_LEAKY_BUCKET_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify({
  capacity: bucket.capacity,
  leakRate: bucket.leakRate,
  totalConsumed: bucket.totalConsumed,
  totalRejected: bucket.totalRejected,
  finalFillPercentage: bucket.getFillPercentage(simTime),
  sampleExecutions: [res1, res2, res3]
}, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_LEAKY_BUCKET_REPORT.json');

console.log('All Token Leaky Bucket tests passed successfully!');
