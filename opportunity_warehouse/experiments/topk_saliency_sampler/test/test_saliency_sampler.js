const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { TopKSaliencySampler } = require('../lib/saliency_sampler');

const sampler = new TopKSaliencySampler(3); // retain top 3 items

// Test 1: Insert 5 items with varying saliency
sampler.insert('item_1', 'Low priority background noise', 0.2);
sampler.insert('item_2', 'Medium priority tool result', 0.5);
sampler.insert('pinned_invariant', 'CORE INVARIANT: Spend strictly EUR 0.00', 0.1, true); // pinned!
sampler.insert('item_3', 'High priority customer order spec', 0.9);
sampler.insert('item_4', 'Very high priority settlement trigger', 0.95);

// Total 5 ingested into capacity 3:
// Items: item_1(0.2), item_2(0.5), pinned(Inf), item_3(0.9), item_4(0.95).
// Retained should be: pinned(Inf), item_4(0.95), item_3(0.9)
const retained = sampler.getRetained('SALIENCY');
assert.strictEqual(retained.length, 3, 'Should retain exactly 3 items');
assert.strictEqual(retained[0].id, 'pinned_invariant', 'Pinned item must be top rank');
assert.strictEqual(retained[1].id, 'item_4', 'item_4 should be second');
assert.strictEqual(retained[2].id, 'item_3', 'item_3 should be third');
console.log('✓ Test 1: Top-3 items retained accurately: ' + retained.map(r => r.id).join(', '));

// Test 2: Chronological ordering preserves original sequence
const chrono = sampler.getRetained('CHRONOLOGICAL');
assert.strictEqual(chrono.length, 3);
assert.strictEqual(chrono[0].id, 'pinned_invariant', 'pinned was inserted 3rd (seq 2)');
assert.strictEqual(chrono[1].id, 'item_3', 'item_3 was inserted 4th (seq 3)');
assert.strictEqual(chrono[2].id, 'item_4', 'item_4 was inserted 5th (seq 4)');
console.log('✓ Test 2: Chronological ordering restored sequence: ' + chrono.map(c => c.sequenceIndex).join(' -> '));

// Test 3: Stats verification
const stats = sampler.getStats();
assert.strictEqual(stats.totalIngested, 5);
assert.strictEqual(stats.totalEvicted, 2);
console.log('✓ Test 3: Sampler stats confirmed (5 ingested, 2 evicted)');

// Test 4: Write sample evidence report
const evidencePath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_TOPK_SALIENCY_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify({
  stats,
  retainedItemsSaliency: retained,
  retainedItemsChronological: chrono
}, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_TOPK_SALIENCY_REPORT.json');

console.log('All Top-K Saliency Sampler tests passed successfully!');
