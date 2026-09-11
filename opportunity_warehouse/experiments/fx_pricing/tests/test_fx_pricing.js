const assert = require('assert');
const { convertPrice, generateFullMatrix, roundCharmPrice } = require('../lib/fx_pricing_matrix');

console.log('Running FX Pricing Matrix Tests...');

// Test 1: Base EUR identity
const eur = convertPrice(5.00, 'EUR');
assert.strictEqual(eur.currency, 'EUR');
assert.strictEqual(eur.charm_price, 4.99);
console.log('  [PASS] Test 1: Base EUR conversion validated');

// Test 2: USD conversion & charm rounding
const usd = convertPrice(5.00, 'USD');
assert.strictEqual(usd.currency, 'USD');
assert.ok(usd.charm_price === 5.49 || usd.charm_price === 5.99, 'USD charm price should end in .49 or .99');
console.log('  [PASS] Test 2: USD conversion and charm pricing validated');

// Test 3: JPY integer rounding
const jpy = convertPrice(5.00, 'JPY');
assert.strictEqual(jpy.currency, 'JPY');
assert.strictEqual(Number.isInteger(jpy.charm_price), true, 'JPY price must be integer');
console.log('  [PASS] Test 3: JPY integer pricing validated');

// Test 4: Full matrix generation
const fullMatrix = generateFullMatrix(5.00);
assert.strictEqual(fullMatrix.base_price, 5.00);
assert.ok(Object.keys(fullMatrix.matrix).length >= 6, 'Matrix must contain all key currencies');
console.log('  [PASS] Test 4: Full multi-currency matrix generated successfully');

console.log('ALL 4 FX PRICING TESTS PASSED DETERMINISTICALLY!');
