const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { ScuttlebuttNode } = require('./lib/scuttlebutt_gossip');

console.log('Testing Scuttlebutt Gossip Engine...');

const peer1 = new ScuttlebuttNode('peer-1');
const peer2 = new ScuttlebuttNode('peer-2');

// Peer 1 publishes 2 messages
peer1.publish({ action: 'trim_context', tokensSaved: 100 });
peer1.publish({ action: 'apply_mask', maskId: 'm-42' });

// Peer 2 publishes 1 message
peer2.publish({ action: 'settle_order', amountEur: 5.00 });

// Test 1: Before sync
assert.strictEqual(peer1.feeds.size, 1);
assert.strictEqual(peer2.feeds.size, 1);

// Test 2: Symmetric sync exchange
const res = peer1.syncWith(peer2);
assert.strictEqual(res.itemsToA, 1);
assert.strictEqual(res.itemsToB, 2);
assert.strictEqual(peer1.feeds.size, 2);
assert.strictEqual(peer2.feeds.size, 2);
console.log('✓ Test 1: Symmetric Scuttlebutt gossip sync verified across 2 peers');

// Test 3: Messages replicated exactly in order
const p1FeedFromP2 = peer1.feeds.get('peer-2');
assert.strictEqual(p1FeedFromP2.messages[0].data.amountEur, 5.00);

const p2FeedFromP1 = peer2.feeds.get('peer-1');
assert.strictEqual(p2FeedFromP1.messages[0].data.tokensSaved, 100);
assert.strictEqual(p2FeedFromP1.messages[1].data.maskId, 'm-42');
console.log('✓ Test 2: Messages perfectly replicated in strict sequence order');

// Test 4: Write sample evidence report
const report = {
  timestamp: new Date().toISOString(),
  phase: 367,
  component: 'scuttlebutt_gossip',
  feedsSynchronized: peer1.feeds.size,
  reconciliationSummary: res,
  scuttlebuttEpidemicVerified: true,
  verification: '100% PASS'
};

const evidenceDir = path.join(__dirname, '..', '..', 'evidence');
fs.writeFileSync(
  path.join(evidenceDir, 'SAMPLE_SCUTTLEBUTT_REPORT.json'),
  JSON.stringify(report, null, 2),
  'utf8'
);
console.log('✓ Test 3: Evidence report written to SAMPLE_SCUTTLEBUTT_REPORT.json');
console.log('All Scuttlebutt Gossip tests passed successfully!');
