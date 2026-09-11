const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { AgentLockManager } = require('../lib/agent_locks');

const testLockDir = path.join(__dirname, 'temp_locks');
if (fs.existsSync(testLockDir)) fs.rmSync(testLockDir, { recursive: true, force: true });

const mgr = new AgentLockManager(testLockDir);

console.log('[TEST 1] Exclusive Lock Acquisition...');
const res1 = mgr.acquireLock('src/app.js', 'agent_alpha');
assert.strictEqual(res1.acquired, true, 'Alpha should acquire lock');
assert.strictEqual(res1.reentrant, false);

console.log('[TEST 2] Collision Denial (Anti-Stacking)...');
const res2 = mgr.acquireLock('src/app.js', 'agent_beta');
assert.strictEqual(res2.acquired, false, 'Beta should be denied lock');
assert.strictEqual(res2.reason, 'LOCKED_BY_ACTIVE_HOLDER');

console.log('[TEST 3] Re-entrant Lock by Same Holder...');
const res3 = mgr.acquireLock('src/app.js', 'agent_alpha');
assert.strictEqual(res3.acquired, true, 'Alpha should re-enter lock');
assert.strictEqual(res3.reentrant, true);

console.log('[TEST 4] Re-entrant Release...');
const rel1 = mgr.releaseLock('src/app.js', 'agent_alpha');
assert.strictEqual(rel1.released, true);
assert.strictEqual(rel1.remaining_count, 1);

console.log('[TEST 5] Full Lock Release...');
const rel2 = mgr.releaseLock('src/app.js', 'agent_alpha');
assert.strictEqual(rel2.released, true);
assert.strictEqual(rel2.remaining_count, 0);

console.log('[TEST 6] Beta Acquires After Alpha Releases...');
const res4 = mgr.acquireLock('src/app.js', 'agent_beta');
assert.strictEqual(res4.acquired, true, 'Beta should now acquire lock');

console.log('[TEST 7] Case-Insensitive Path Normalization...');
const res5 = mgr.acquireLock('SRC/APP.JS', 'agent_gamma');
assert.strictEqual(res5.acquired, false, 'Uppercase path should collide with lowercase lock');

// Cleanup
mgr.releaseLock('src/app.js', 'agent_beta');
fs.rmSync(testLockDir, { recursive: true, force: true });

console.log('\n>>> ALL 7 AGENT-LOCKS TESTS PASS (100% DETERMINISTIC) <<<');
