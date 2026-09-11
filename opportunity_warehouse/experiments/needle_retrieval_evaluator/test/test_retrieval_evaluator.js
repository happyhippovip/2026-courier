const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { NeedleRetrievalEvaluator } = require('../lib/retrieval_evaluator');

console.log('--- Testing Needle Retrieval & Attention Drift Evaluator ---');

const evaluator = new NeedleRetrievalEvaluator();

// Test 1: Attention U-curve verification
const headScore = evaluator.calculateAttentionScore(5);   // near prompt start
const midScore = evaluator.calculateAttentionScore(50);   // deep middle
const tailScore = evaluator.calculateAttentionScore(95);  // near prompt end

assert.ok(headScore > midScore, 'Head attention must exceed middle attention');
assert.ok(tailScore > midScore, 'Tail attention must exceed middle attention');
assert.ok(midScore < 0.5, 'Middle attention score must exhibit lost-in-the-middle degradation');
console.log('✓ Assertion 1 Passed: Attention U-curve validated (Head: ' + headScore + ', Mid: ' + midScore + ', Tail: ' + tailScore + ')');

// Test 2: Needle evaluation and risk scoring
const criticalMidNeedle = evaluator.evaluateNeedleRisk({
  id: 'security_policy',
  priority: 'critical',
  positionTokens: 50000,
  totalTokens: 100000
});
assert.strictEqual(criticalMidNeedle.needsHoisting, true, 'Critical needle in the middle must require hoisting');
assert.strictEqual(criticalMidNeedle.recommendedAction, 'HOIST_TO_HEAD_OR_TAIL');
console.log('✓ Assertion 2 Passed: High-risk middle needle accurately flagged for hoisting');

// Test 3: Multi-section context audit
const sections = [
  { id: 'sys_prompt', label: 'System Instructions', tokens: 2000, priority: 'critical' },
  { id: 'user_rules', label: 'Safety Guidelines', tokens: 1500, priority: 'high' },
  { id: 'retrieved_docs_1', label: 'Unchecked PDF Excerpts', tokens: 25000, priority: 'medium' },
  { id: 'critical_constraint', label: 'Zero-Spend Invariant', tokens: 500, priority: 'critical' },
  { id: 'retrieved_docs_2', label: 'Legacy SQL Tables', tokens: 30000, priority: 'low' },
  { id: 'current_turn', label: 'Current User Query', tokens: 1000, priority: 'high' }
];

const audit = evaluator.auditContextSections(sections);
assert.strictEqual(audit.totalSections, 6, 'Must audit all 6 sections');
assert.ok(audit.atRiskCount >= 1, 'Must detect at least 1 at-risk critical section in the middle');
console.log('✓ Assertion 3 Passed: Context audit identified at-risk constraints in deep context');

// Test 4: Export evidence JSON
const evidencePath = path.resolve(__dirname, '../../../evidence/SAMPLE_NEEDLE_RETRIEVAL_AUDIT.json');
fs.writeFileSync(evidencePath, JSON.stringify(audit, null, 2), 'utf8');
assert.ok(fs.existsSync(evidencePath), 'Evidence audit file must exist');
console.log('✓ Assertion 4 Passed: Evidence exported to SAMPLE_NEEDLE_RETRIEVAL_AUDIT.json');

console.log('All 4 Needle Retrieval Evaluator tests passed successfully!');
