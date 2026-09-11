const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { TokenAmortizationEngine } = require('../lib/amortization_engine');

console.log('--- Testing Context Token Amortization Engine ---');

const engine = new TokenAmortizationEngine({
  baseInputPerMillion: 3.00,
  cachedInputPerMillion: 0.30,
  cacheWritePerMillion: 3.75,
  outputPerMillion: 15.00,
  currency: 'EUR'
});

// Test 1: Turn cost calculation
const turn1 = engine.calculateTurnCost({
  cachedTokens: 50000,
  freshInputTokens: 2000,
  outputTokens: 500,
  isFirstTurnWrite: true
});
assert.ok(turn1.optimizedCost > 0, 'Turn 1 optimized cost must be calculated');
assert.strictEqual(typeof turn1.savings, 'number', 'Savings must be a number');
console.log('✓ Assertion 1 Passed: Individual turn cost computation verified');

// Test 2: Turn 2 (Cache Read) substantial discount verification
const turn2 = engine.calculateTurnCost({
  cachedTokens: 50000,
  freshInputTokens: 2000,
  outputTokens: 500,
  isFirstTurnWrite: false
});
assert.ok(turn2.optimizedCost < turn2.unoptimizedCost, 'Turn 2 must yield net savings');
assert.ok(turn2.savingsPercent > 50, 'Turn 2 savings percent should exceed 50%');
console.log('✓ Assertion 2 Passed: Cache read turn yields significant savings (' + turn2.savingsPercent + '%)');

// Test 3: Break-even turn calculation
const breakEven = engine.findBreakEvenTurn(50000);
assert.strictEqual(breakEven, 2, 'Break even turn should be turn 2 under standard pricing');
console.log('✓ Assertion 3 Passed: Break-even turn accurately determined as Turn ' + breakEven);

// Test 4: 10-turn schedule generation and export to evidence
const schedule = engine.generateAmortizationSchedule({
  totalTurns: 10,
  cachedTokens: 60000,
  freshInputPerTurn: 1000,
  outputPerTurn: 500
});

assert.ok(schedule.netSavingsPercent > 60, '10-turn session net savings must exceed 60%');
assert.strictEqual(schedule.schedule.length, 10, 'Schedule must contain 10 turns');

const evidencePath = path.resolve(__dirname, '../../../evidence/SAMPLE_TOKEN_AMORTIZATION_SCHEDULE.json');
fs.writeFileSync(evidencePath, JSON.stringify(schedule, null, 2), 'utf8');
assert.ok(fs.existsSync(evidencePath), 'Evidence schedule must exist');
console.log('✓ Assertion 4 Passed: Amortization schedule exported to SAMPLE_TOKEN_AMORTIZATION_SCHEDULE.json');

console.log('All 4 Token Amortization Engine tests passed successfully!');
