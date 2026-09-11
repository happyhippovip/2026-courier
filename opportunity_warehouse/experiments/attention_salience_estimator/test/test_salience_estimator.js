const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { AttentionSalienceEstimator } = require('../lib/salience_estimator');

const estimator = new AttentionSalienceEstimator();

// Sample document with varied sentence salience
const documentText = [
  'SYSTEM MANDATE: All commercial operations must secure attributable EUR 5.00 revenue before convergence.',
  'The weather today is mild and seasonal across central Europe with moderate cloud cover.',
  'General discussion on office supplies was concluded at the previous afternoon sync meeting.',
  'CRITICAL ERROR in module payment_gateway: Webhook HMAC verification failed for TX_99182.',
  'FINAL INSTRUCTION: Release memory mutex lock immediately upon successful receipt processing.'
].join(' ');

// Test 1: Positional weighting curve
const wStart = estimator.computePositionalWeight(0, 5);
const wMid = estimator.computePositionalWeight(2, 5);
const wEnd = estimator.computePositionalWeight(4, 5);
assert.ok(wStart > wMid, 'Start position must have higher weight than middle');
assert.ok(wEnd > wMid, 'End position must have higher weight than middle');
assert.strictEqual(wStart, wEnd, 'Start and end must be symmetric');
console.log('✓ Assertion 1 Passed: Positional U-shaped weighting validated (Edge: ' + wStart + ' vs Center: ' + wMid + ')');

// Test 2: Sentence salience evaluation correctly ranks critical code/money over filler
const rawSentences = documentText.split(/(?<=[.?!])\s+/);
const scored = rawSentences.map((s, i) => estimator.evaluateSentence(s, i, rawSentences.length));
const mandateScore = scored[0].salienceScore;
const weatherScore = scored[1].salienceScore;
const errorScore = scored[3].salienceScore;
assert.ok(mandateScore > weatherScore, 'Mandate must outscore weather filler');
assert.ok(errorScore > weatherScore, 'Error must outscore weather filler');
console.log('✓ Assertion 2 Passed: High-salience sentences outranked generic text (Mandate: ' + mandateScore + ', Error: ' + errorScore + ' vs Filler: ' + weatherScore + ')');

// Test 3: Pruning to token budget preserves critical sentences in chronological order
const pruned = estimator.pruneToTokenBudget(documentText, 85);
assert.ok(pruned.prunedTokens <= 85, 'Pruned text must stay within budget');
assert.ok(pruned.tokensSaved > 0, 'Tokens saved must be positive');
const retainedTexts = pruned.selectedSentences.map(s => s.text);
assert.ok(retainedTexts.some(t => t.includes('EUR 5.00')), 'Must retain EUR 5.00 mandate');
assert.ok(retainedTexts.some(t => t.includes('payment_gateway')), 'Must retain payment gateway error');
assert.ok(!retainedTexts.some(t => t.includes('office supplies')), 'Must drop office supplies filler');
console.log('✓ Assertion 3 Passed: Token budget strictly respected (' + pruned.prunedTokens + '/85 tokens, ' + pruned.savingsPercent + '% saved)');

// Test 4: Export evidence JSON
const evidencePath = path.resolve(__dirname, '../../../evidence/SAMPLE_ATTENTION_SALIENCE_REPORT.json');
const report = {
  timestamp: new Date().toISOString(),
  originalTokens: pruned.originalTokens,
  prunedTokens: pruned.prunedTokens,
  savingsPercent: pruned.savingsPercent,
  retainedSentences: pruned.selectedSentences.map(s => ({ idx: s.index, score: s.salienceScore, snippet: s.text.substring(0, 40) + '...' })),
  salienceOptimizationVerified: true
};
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
assert.ok(fs.existsSync(evidencePath), 'Evidence report must exist');
console.log('✓ Assertion 4 Passed: Evidence exported to SAMPLE_ATTENTION_SALIENCE_REPORT.json');

console.log('All 4 Attention Salience Estimator tests passed successfully!');