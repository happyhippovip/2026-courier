const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { BPEMergeTree } = require('../lib/bpe_tree');

const bpe = new BPEMergeTree();

const trainingCorpus = [
  'autonomous revenue collection verified',
  'autonomous revenue settlement verified',
  'autonomous revenue collection completed',
  'system verification complete zero errors'
];

// Test 1: Learn merge rules from training corpus
const trainStats = bpe.train(trainingCorpus, 25);
assert.ok(trainStats.totalMerges >= 5, 'Should learn at least 5 merge rules from repetitive corpus');
assert.ok(bpe.vocab.size > 26, 'Vocabulary should expand beyond base characters');
console.log('✓ Test 1: BPE learned ' + trainStats.totalMerges + ' merges (vocab size: ' + bpe.vocab.size + ')');

// Test 2: Tokenization replaces frequent pairs with merged tokens
const sample = 'autonomous revenue collection verified';
const encoded = bpe.encode(sample);
assert.ok(encoded.tokenCount < sample.length, 'Encoded token count (' + encoded.tokenCount + ') must be less than raw characters (' + sample.length + ')');
console.log('✓ Test 2: Tokenization compressed ' + sample.length + ' chars into ' + encoded.tokenCount + ' tokens');

// Test 3: Lossless 100% roundtrip detokenization
const decoded = bpe.decode(encoded.tokenIds);
assert.strictEqual(decoded, sample, 'Decoded text must match original text bit-for-bit');
console.log('✓ Test 3: 100% lossless roundtrip decoding confirmed');

// Test 4: Write sample evidence report
const evidencePath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_BPE_TREE_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify({
  trainStats,
  topMerges: bpe.merges.slice(0, 10),
  sampleCompression: {
    rawCharacters: sample.length,
    encodedTokens: encoded.tokenCount,
    compressionRatio: Number((encoded.tokenCount / sample.length).toFixed(4))
  }
}, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_BPE_TREE_REPORT.json');

console.log('All BPE Merge Tree tests passed successfully!');
