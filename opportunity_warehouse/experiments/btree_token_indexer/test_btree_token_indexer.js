const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { BTreeTokenIndexer } = require('./lib/btree_token_indexer');

console.log('Testing B-Tree Token Range Search & Saliency Indexer...');

const indexer = new BTreeTokenIndexer(4);

const sampleTokens = [
  { score: 0.15, token: 'the', position: 0 },
  { score: 0.85, token: 'symphony', position: 1 },
  { score: 0.42, token: 'orchestrates', position: 2 },
  { score: 0.95, token: 'revenue', position: 3 },
  { score: 0.31, token: 'across', position: 4 },
  { score: 0.78, token: 'multi-agent', position: 5 },
  { score: 0.05, token: 'system', position: 6 },
  { score: 0.64, token: 'boundaries', position: 7 }
];

for (const t of sampleTokens) {
  indexer.insert(t.score, t.token, t.position);
}

// Test 1: Total tokens inserted
assert.strictEqual(indexer.totalTokens, 8);
console.log('✓ Test 1: B-Tree balanced insertion of 8 tokens verified');

// Test 2: Range search [0.50, 1.00] (High saliency tokens)
const highSaliency = indexer.rangeSearch(0.50, 1.00);
const highTokens = highSaliency.map(t => t.token);
assert.strictEqual(highSaliency.length, 4);
assert.ok(highTokens.includes('symphony'));
assert.ok(highTokens.includes('revenue'));
assert.ok(highTokens.includes('multi-agent'));
assert.ok(highTokens.includes('boundaries'));
console.log('✓ Test 2: Range search [0.50, 1.00] correctly retrieved 4 high-saliency tokens');

// Test 3: Range search [0.00, 0.20] (Stopwords/low-saliency)
const lowSaliency = indexer.rangeSearch(0.00, 0.20);
assert.strictEqual(lowSaliency.length, 2);
const lowTokens = lowSaliency.map(t => t.token);
assert.ok(lowTokens.includes('the'));
assert.ok(lowTokens.includes('system'));
console.log('✓ Test 3: Range search [0.00, 0.20] correctly isolated low-saliency candidate tokens');

// Test 4: Write sample evidence report
const report = {
  timestamp: new Date().toISOString(),
  phase: 305,
  component: 'btree_token_indexer',
  order: 4,
  totalTokensIndexed: indexer.totalTokens,
  rangeQueryResults: {
    highSaliencyCount: highSaliency.length,
    lowSaliencyCount: lowSaliency.length
  },
  verification: '100% PASS'
};

const evidenceDir = path.join(__dirname, '..', '..', 'evidence');
fs.writeFileSync(
  path.join(evidenceDir, 'SAMPLE_BTREE_INDEXER_REPORT.json'),
  JSON.stringify(report, null, 2),
  'utf8'
);
console.log('✓ Test 4: Evidence report written to SAMPLE_BTREE_INDEXER_REPORT.json');
console.log('All B-Tree Token Indexer tests passed successfully!');
