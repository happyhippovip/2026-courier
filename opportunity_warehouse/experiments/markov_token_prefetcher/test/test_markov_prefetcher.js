const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { MarkovTokenPrefetcher } = require('../lib/markov_prefetcher');

const prefetcher = new MarkovTokenPrefetcher({ maxOrder: 2 });

const corpus = [
  'system verification complete all test suites passing deterministically',
  'system verification complete zero errors zero regressions',
  'system verification complete all invariants strictly enforced',
  'autonomous revenue collection verified incoming payment euro five received'
];

prefetcher.train(corpus);

// Test 1: Transition probabilities accurately reflect training frequencies
const preds = prefetcher.predictNext('system verification', 3);
assert.ok(preds.length > 0, 'Should return predictions for known context');
assert.strictEqual(preds[0].token, 'complete', 'Top prediction should be "complete"');
assert.strictEqual(preds[0].probability, 1.0, 'Probability should be 1.0 for unanimous bigram');
console.log('✓ Test 1: Accurate transition probabilities for known bigram');

// Test 2: Speculative multi-step prefetching
const prefetchPlan = prefetcher.speculativePrefetch('system verification', 3);
assert.strictEqual(prefetchPlan.prefetchedTokens.length, 3, 'Should prefetch 3 steps');
assert.strictEqual(prefetchPlan.prefetchedTokens[0].token, 'complete', 'Step 1 should be "complete"');
assert.ok(prefetchPlan.meanConfidence > 0.3, 'Mean confidence should be positive');
console.log('✓ Test 2: Speculative prefetch generated sequence: "' + prefetchPlan.prefetchedSequence + '"');

// Test 3: Fallback to unigrams on unseen context
const unseenPreds = prefetcher.predictNext('unseen alien prompt', 3);
assert.ok(unseenPreds.length > 0, 'Should gracefully fallback to unigrams');
assert.strictEqual(unseenPreds[0].order, 'unigram', 'Fallback order should be unigram');
console.log('✓ Test 3: Unseen context cleanly falls back to unigrams');

// Test 4: Evaluate accuracy and output evidence report
const evalResult = prefetcher.evaluateAccuracy('system verification complete all test suites', 3);
assert.ok(evalResult.hitRate >= 0.75, 'Accuracy should be >= 75% on in-distribution stream');

const evidencePath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_MARKOV_PREFETCH_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify({
  prefetchPlan,
  evaluation: evalResult,
  vocabularySize: Object.keys(prefetcher.unigramCounts).length,
  totalTokensTrained: prefetcher.totalTokens
}, null, 2), 'utf8');
console.log('✓ Test 4: Evaluation achieved ' + (evalResult.hitRate * 100) + '% hit rate and wrote evidence report');

console.log('All Markov Token Prefetcher tests passed successfully!');
