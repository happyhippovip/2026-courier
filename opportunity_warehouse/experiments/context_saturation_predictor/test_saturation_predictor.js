/**
 * test_saturation_predictor.js - Test suite for Context Saturation Predictor
 */
const assert = require('assert');
const { ContextSaturationPredictor } = require('./lib/saturation_predictor');

console.log('--- Running test_saturation_predictor.js ---');

const predictor = new ContextSaturationPredictor();

// Test 1: Low-risk prompt within safe limits
const shortPrompt = 'You are a TypeScript expert. Refactor this 5-line function.';
const res1 = predictor.predictSaturation(shortPrompt, 'claude-3-5-sonnet');
assert.strictEqual(res1.degradationRisk, 'LOW', 'Short prompt must have LOW degradation risk');
assert.ok(res1.saturationPercentage < 5, 'Saturation percentage should be tiny');
assert.strictEqual(res1.lostInMiddleWarnings.length, 0, 'Zero lost-in-middle warnings');
console.log('✓ Test 1 Passed: Low-risk prompt identified accurately');

// Test 2: High saturation alert
// Generate simulated ~100k token string
const chunk = 'This is repetitive context line for saturation testing.\n';
const largeText = chunk.repeat(7000); // ~400k chars => ~100k tokens
const res2 = predictor.predictSaturation(largeText, 'gpt-4o');
assert.ok(res2.degradationRisk === 'HIGH' || res2.degradationRisk === 'CRITICAL', 'Must flag high saturation risk on 100k tokens for GPT-4o (128k cap)');
assert.ok(res2.recommendations.some(r => r.includes('AST token trimming')), 'Must suggest AST trimming');
console.log('✓ Test 2 Passed: High saturation risk detected with actionable trimming recommendations');

// Test 3: Lost-in-the-middle hazard detection
const longDoc = 'Header information\n' + 'A'.repeat(5000) + '\nCRITICAL_RULE_DO_NOT_HALLUCINATE\n' + 'B'.repeat(5000) + '\nFooter instructions.';
const rulePos = longDoc.indexOf('CRITICAL_RULE_DO_NOT_HALLUCINATE');
const res3 = predictor.predictSaturation(longDoc, 'claude-3-5-sonnet', [rulePos]);
assert.strictEqual(res3.lostInMiddleWarnings.length, 1, 'Must catch instruction in middle attention zone');
assert.ok(res3.lostInMiddleWarnings[0].relativeDepthPercentage > 40 && res3.lostInMiddleWarnings[0].relativeDepthPercentage < 60);
console.log('✓ Test 3 Passed: Lost-in-the-middle attention hazard flagged with relocation warning');

// Test 4: Model registry lookup support
const models = ['claude-3-5-sonnet', 'gpt-4o', 'gemini-1-5-pro', 'llama-3-1-70b'];
models.forEach(m => {
  const check = predictor.predictSaturation('Test prompt', m);
  assert.strictEqual(check.targetModel, m);
  assert.ok(check.promptMetrics.modelCapacityTokens > 0);
});
console.log('✓ Test 4 Passed: All 4 frontier model profiles supported seamlessly');

console.log('ALL 4 TESTS PASSED IN test_saturation_predictor.js\n');
