const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { LevenshteinAutomaton } = require('./lib/levenshtein_automaton');

console.log('Testing Levenshtein Automaton & Approximate Keyword Search...');

// Test 1: Exact match with distance 0
const auto1 = new LevenshteinAutomaton('symphony', 2);
const res1 = auto1.match('symphony');
assert.strictEqual(res1.matches, true);
assert.strictEqual(res1.distance, 0);
assert.strictEqual(res1.similarity, 1.0);
console.log('✓ Test 1: Exact match distance 0 verified');

// Test 2: Single edit distance
const res2a = auto1.match('sympony'); // deletion of 'h'
assert.strictEqual(res2a.matches, true);
assert.strictEqual(res2a.distance, 1);

const res2b = auto1.match('symphonx'); // substitution of 'y' -> 'x'
assert.strictEqual(res2b.matches, true);
assert.strictEqual(res2b.distance, 1);
console.log('✓ Test 2: Single edit (deletion & substitution) verified');

// Test 3: Fuzzy search across vocabulary
const vocab = [
  'symphony', 'sympony', 'symphonx', 'sympathy', 'symphonies',
  'synchrony', 'synthesis', 'orchestra', 'cadence'
];
const matches = auto1.search(vocab);
const matchTokens = matches.map(m => m.token);
assert.ok(matchTokens.includes('symphony'));
assert.ok(matchTokens.includes('sympony'));
assert.ok(matchTokens.includes('symphonx'));
assert.ok(!matchTokens.includes('orchestra'));
assert.ok(!matchTokens.includes('cadence'));
console.log('✓ Test 3: Fuzzy vocabulary search correctly identified candidate matches (' + matches.length + ' matches found)');

// Test 4: Generate evidence report
const report = {
  timestamp: new Date().toISOString(),
  phase: 293,
  component: 'levenshtein_automaton',
  queryPattern: 'symphony',
  maxDistance: 2,
  vocabularySize: vocab.length,
  matchedCount: matches.length,
  matches,
  verification: '100% PASS'
};

const evidenceDir = path.join(__dirname, '..', '..', 'evidence');
fs.writeFileSync(
  path.join(evidenceDir, 'SAMPLE_LEVENSHTEIN_REPORT.json'),
  JSON.stringify(report, null, 2),
  'utf8'
);
console.log('✓ Test 4: Evidence report written to SAMPLE_LEVENSHTEIN_REPORT.json');
console.log('All Levenshtein Automaton tests passed successfully!');
