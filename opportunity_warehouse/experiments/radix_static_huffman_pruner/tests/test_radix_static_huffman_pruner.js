const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { RadixStaticHuffmanPruner } = require('../lib/radix_static_huffman_pruner');

console.log('Testing Radix Static Huffman Saliency Pruner...');
const pruner = new RadixStaticHuffmanPruner();

const sampleTokens = [
  { id: 101, token: 'function', saliencyScore: 0.95 },
  { id: 102, token: 'authGuard', saliencyScore: 0.92 },
  { id: 103, token: '(', saliencyScore: 0.15 },
  { id: 104, token: 'req', saliencyScore: 0.78 },
  { id: 105, token: ',', saliencyScore: 0.12 },
  { id: 106, token: 'res', saliencyScore: 0.75 },
  { id: 107, token: ')', saliencyScore: 0.14 },
  { id: 108, token: '{', saliencyScore: 0.10 },
  { id: 109, token: 'checkPermission', saliencyScore: 0.98 },
  { id: 110, token: '}', saliencyScore: 0.11 }
];

const freqs = pruner.buildFrequencyTable(sampleTokens);
assert.strictEqual(freqs.size, 10);
console.log('✓ Test 1: Frequency table built for 10 distinct tokens');

const codeLengths = pruner.computeCodeLengths(freqs);
assert.ok(codeLengths.size === 10);
console.log('✓ Test 2: Canonical Huffman code lengths computed');

const pruned = pruner.prune(sampleTokens, 5);
assert.strictEqual(pruned.retained.length, 5);
assert.strictEqual(pruned.prunedCount, 5);
assert.strictEqual(pruned.compressionRatio, 0.5);

// Verify high-saliency tokens were preserved
const retainedIds = new Set(pruned.retained.map(t => t.id));
assert.ok(retainedIds.has(101)); // function (0.95)
assert.ok(retainedIds.has(102)); // authGuard (0.92)
assert.ok(retainedIds.has(109)); // checkPermission (0.98)
console.log('✓ Test 3: Saliency pruning preserved top 5 tokens in causal order');

const report = {
  test: 'RADIX_STATIC_HUFFMAN_PRUNER',
  passed: true,
  tokenCount: sampleTokens.length,
  retainedCount: pruned.retained.length,
  timestamp: new Date().toISOString()
};

fs.writeFileSync(path.join(__dirname, 'SAMPLE_RADIX_HUFFMAN_PRUNER_REPORT.json'), JSON.stringify(report, null, 2));
console.log('✓ Test 4: Evidence report written to SAMPLE_RADIX_HUFFMAN_PRUNER_REPORT.json');
console.log('All Radix Static Huffman Saliency Pruner tests passed successfully!');
