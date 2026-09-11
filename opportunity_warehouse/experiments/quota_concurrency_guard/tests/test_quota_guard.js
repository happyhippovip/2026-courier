const assert = require('assert');
const { QuotaConcurrencyGuard } = require('../lib/quota_guard');

console.log('Testing QuotaConcurrencyGuard...');

// Test 1: Solo tier allows 1 slot
const soloGuard = new QuotaConcurrencyGuard({ tier: 'SOLO' });
const s1 = soloGuard.acquireSlot('worker_1');
assert.strictEqual(s1.acquired, true);

// Test 2: Solo tier rejects second slot
const s2 = soloGuard.acquireSlot('worker_2');
assert.strictEqual(s2.acquired, false);
assert.strictEqual(s2.reason, 'CONCURRENCY_QUOTA_EXCEEDED');

// Test 3: Release slot frees capacity
const rel = soloGuard.releaseSlot('worker_1');
assert.strictEqual(rel.released, true);
assert.strictEqual(rel.remainingActive, 0);
const s3 = soloGuard.acquireSlot('worker_2');
assert.strictEqual(s3.acquired, true);

// Test 4: Team tier supports multiple slots
const teamGuard = new QuotaConcurrencyGuard({ tier: 'TEAM' });
for (let i = 1; i <= 5; i++) {
  const res = teamGuard.acquireSlot('team_worker_' + i);
  assert.strictEqual(res.acquired, true);
}
const teamReject = teamGuard.acquireSlot('team_worker_6');
assert.strictEqual(teamReject.acquired, false);

console.log('All QuotaConcurrencyGuard tests passed (4/4)!');
