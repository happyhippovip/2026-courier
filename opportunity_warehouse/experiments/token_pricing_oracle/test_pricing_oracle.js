/**
 * test_pricing_oracle.js - Test suite for Token Pricing Oracle
 */
const assert = require('assert');
const { TokenPricingOracle } = require('./lib/pricing_oracle');

console.log('--- Running test_pricing_oracle.js ---');

const oracle = new TokenPricingOracle();

// Test 1: Accurate cost lookup and calculation
const cost = oracle.calculateCost('claude-3-5-sonnet', 1000000, 100000);
assert.strictEqual(cost.inputCostUsd, 3.00, 'Input cost for 1M tokens should be $3.00');
assert.strictEqual(cost.outputCostUsd, 1.50, 'Output cost for 100k tokens should be $1.50');
assert.strictEqual(cost.totalCostUsd, 4.50, 'Total cost should be $4.50');
console.log('✓ Test 1 Passed: 1M token calculation matches standard pricing sheet');

// Test 2: Savings calculation between raw and trimmed tokens
const savings = oracle.calculateSavings('gpt-4o', 10000, 6000);
assert.strictEqual(savings.savedTokens, 4000, 'Saved tokens must be 4,000');
assert.strictEqual(savings.savingsPercent, 40.00, 'Savings percent must be 40.00%');
assert.ok(savings.savedCostUsd > 0, 'Saved dollar amount must be > 0');
console.log('✓ Test 2 Passed: 40% pruning calculates exact savings on GPT-4o');

// Test 3: Custom model registration
const customOracle = new TokenPricingOracle({
  'internal-llama3': { provider: 'PrivateCloud', inputPerM: 0.50, outputPerM: 1.00 }
});
const customCost = customOracle.calculateCost('internal-llama3', 2000000, 0);
assert.strictEqual(customCost.totalCostUsd, 1.00, '2M tokens at $0.50/M must equal $1.00');
console.log('✓ Test 3 Passed: Custom internal model rates supported cleanly');

// Test 4: Multi-model comparison matrix
const matrix = oracle.compareAllModels(100000, 65000);
assert.ok(matrix.length >= 7, 'Must compare across all 7 default models');
const claudeEntry = matrix.find(m => m.modelId === 'claude-3-5-sonnet');
assert.ok(claudeEntry.savedCostUsd > 0.10, 'Claude savings correctly calculated in matrix');
console.log('✓ Test 4 Passed: Multi-model comparison matrix generated across 7 providers');

console.log('ALL 4 TESTS PASSED IN test_pricing_oracle.js\n');
