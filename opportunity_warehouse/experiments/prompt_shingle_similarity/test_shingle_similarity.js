/**
 * test_shingle_similarity.js - Test suite for Shingle Similarity
 */
const assert = require('assert');
const { PromptShingleSimilarity } = require('./lib/shingle_similarity');

console.log('--- Running test_shingle_similarity.js ---');

const measurer = new PromptShingleSimilarity({ k: 3, similarityThreshold: 0.70 });

// Test 1: Identical strings have 1.0 Jaccard similarity
const textA = 'you must always preserve existing comments and fail closed';
const textB = 'you must always preserve existing comments and fail closed';
const setA = measurer.generateShingles(textA);
const setB = measurer.generateShingles(textB);
const sim1 = measurer.calculateJaccard(setA, setB);
assert.strictEqual(sim1, 1.0, 'Identical text must have similarity 1.0');
console.log('✓ Test 1 Passed: Exact duplicates yield 1.0 Jaccard similarity');

// Test 2: Near-duplicate detection
const para1 = 'Rule 1: Always check for active leases and prevent double allocation of worker threads.';
const para2 = 'Rule 1: Always check for active leases and prevent double allocation of worker processes.'; // 1 word changed
const res2 = measurer.analyzeParagraphs(para1 + '\n\n' + para2);
assert.strictEqual(res2.redundancyCount, 1);
assert.ok(res2.redundancyPairs[0].jaccardSimilarity >= 0.70);
console.log('✓ Test 2 Passed: Near-duplicate paragraph detected with high Jaccard index (' + res2.redundancyPairs[0].jaccardSimilarity + ')');

// Test 3: Disjoint paragraphs yield low similarity
const pDisjoint1 = 'Database configuration: host localhost port 5432 user postgres database courier';
const pDisjoint2 = 'Frontend react application layout: sidebar header navbar footer container';
const res3 = measurer.analyzeParagraphs(pDisjoint1 + '\n\n' + pDisjoint2);
assert.strictEqual(res3.redundancyCount, 0, 'Disjoint paragraphs must not trigger redundancy alert');
console.log('✓ Test 3 Passed: Distinct paragraphs pass with 0 false positives');

// Test 4: Recommendation generation
assert.strictEqual(res2.recommendedDeduplications.length, 1);
assert.ok(res2.recommendedDeduplications[0].action.includes('Deduplicate paragraph'));
console.log('✓ Test 4 Passed: Actionable deduplication recommendations generated');

console.log('ALL 4 TESTS PASSED IN test_shingle_similarity.js\n');
