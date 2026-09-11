const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { BFTShardAdaptivePacemakerEngine } = require('../lib/bft_shard_adaptive_pacemaker_engine');

console.log('Testing BFT Shard Adaptive Pacemaker Consensus Engine...');
const pacemaker = new BFTShardAdaptivePacemakerEngine({
  minTimeoutMs: 400,
  maxTimeoutMs: 8000,
  initialTimeoutMs: 1000,
  alpha: 0.25
});

// Record normal fast commit
const res1 = pacemaker.recordRoundCommit(1, 200);
assert.strictEqual(res1.event, 'ROUND_COMMIT');
assert.ok(res1.nextTimeoutMs <= 1000);

// Record consecutive timeouts triggering backoff
const res2 = pacemaker.recordRoundTimeout(2);
assert.strictEqual(res2.consecutiveTimeouts, 1);
const res3 = pacemaker.recordRoundTimeout(3);
assert.strictEqual(res3.consecutiveTimeouts, 2);
assert.ok(res3.nextTimeoutMs > res2.nextTimeoutMs);

// Recovery commit resets consecutive timeouts
const res4 = pacemaker.recordRoundCommit(4, 150);
assert.strictEqual(pacemaker.consecutiveTimeouts, 0);

const status = pacemaker.getPacemakerStatus();
assert.strictEqual(status.currentRound, 4);

const report = {
  experiment: 'bft_shard_adaptive_pacemaker_engine',
  status: 'VERIFIED',
  testSuite: 'test_bft_shard_adaptive_pacemaker_engine',
  pacemakerStatus: status,
  eventHistory: pacemaker.history,
  timestamp: new Date().toISOString()
};

fs.writeFileSync(
  path.join(__dirname, 'SAMPLE_BFT_ADAPTIVE_PACEMAKER_REPORT.json'),
  JSON.stringify(report, null, 2),
  'utf8'
);

console.log('✓ BFT Shard Adaptive Pacemaker Consensus Engine verified successfully.');
