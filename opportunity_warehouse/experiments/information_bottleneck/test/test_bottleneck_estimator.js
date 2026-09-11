const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { InformationBottleneckEstimator } = require('../lib/bottleneck_estimator');

console.log('--- Testing Information Bottleneck Estimator ---');

const estimator = new InformationBottleneckEstimator({ tradeoffBeta: 2.0 });

// Test 1: Entropy calculation
const lowEntropy = estimator.calculateEntropy('aaaaaaaaaaaaaaaaaaaa');
const highEntropy = estimator.calculateEntropy('aB3#z9!kL0$qW1@mP8&x');
assert.ok(highEntropy > lowEntropy, 'Complex text must have higher Shannon entropy than repetitive text');
console.log('✓ Assertion 1 Passed: Entropy calculation accurate (Repetitive: ' + lowEntropy + ', Random: ' + highEntropy + ')');

// Test 2: Task relevance scoring
const relevantDoc = 'We must optimize database SQL indexes and query execution latency in PostgreSQL.';
const irrelevantDoc = 'The baking recipe requires three cups of organic flour and two eggs at room temperature.';
const objective = 'Database performance optimization and SQL indexing';

const relScore = estimator.calculateTaskRelevance(relevantDoc, objective);
const irrelScore = estimator.calculateTaskRelevance(irrelevantDoc, objective);
assert.ok(relScore > irrelScore, 'Relevant doc must score significantly higher on task relevance');
console.log('✓ Assertion 2 Passed: Relevance discrimination verified (Relevant: ' + relScore + ', Irrelevant: ' + irrelScore + ')');

// Test 3: Multi-section bottleneck optimization
const sections = [
  { id: 'db_tuning', content: 'Configure PostgreSQL connection pooling and index scans for maximum performance.', tokens: 120 },
  { id: 'cake_recipe', content: 'Mix sugar and eggs until fluffy before adding melted chocolate.', tokens: 400 },
  { id: 'sys_contract', content: 'System rules: respond in concise JSON format with status and metrics.', tokens: 80 }
];

const result = estimator.evaluateBottleneck(sections, objective);
assert.ok(result.tokenReductionPercent > 50, 'Must prune irrelevant bloated sections (>50% token reduction)');
const dbSec = result.evaluatedSections.find(s => s.id === 'db_tuning');
const cakeSec = result.evaluatedSections.find(s => s.id === 'cake_recipe');
assert.strictEqual(dbSec.retainRecommendation, true, 'Relevant section must be retained');
assert.strictEqual(cakeSec.retainRecommendation, false, 'Irrelevant recipe section must be pruned');
console.log('✓ Assertion 3 Passed: Information bottleneck correctly retained task-critical content and pruned irrelevant noise (' + result.tokenReductionPercent + '% tokens pruned)');

// Test 4: Export evidence JSON
const evidencePath = path.resolve(__dirname, '../../../evidence/SAMPLE_INFORMATION_BOTTLENECK_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(result, null, 2), 'utf8');
assert.ok(fs.existsSync(evidencePath), 'Evidence report must exist');
console.log('✓ Assertion 4 Passed: Evidence exported to SAMPLE_INFORMATION_BOTTLENECK_REPORT.json');

console.log('All 4 Information Bottleneck Estimator tests passed successfully!');
