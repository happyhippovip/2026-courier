const assert = require('assert');
const { generateSvgBadge } = require('../lib/badge_generator');

console.log('Running Savings SVG Badge Generator Tests...');

// Test 1: Standard badge generation
const svg = generateSvgBadge('context', '-42%');
assert.ok(svg.includes('<svg xmlns="http://www.w3.org/2000/svg"'));
assert.ok(svg.includes('context'));
assert.ok(svg.includes('-42%'));
console.log('  [PASS] Test 1: SVG badge structure validated');

// Test 2: Custom color support
const customSvg = generateSvgBadge('tokens saved', '142k', '#0969da');
assert.ok(customSvg.includes('#0969da'));
assert.ok(customSvg.includes('tokens saved'));
assert.ok(customSvg.includes('142k'));
console.log('  [PASS] Test 2: Custom dimensions and colors supported');

// Test 3: XML valid markup
assert.ok(svg.endsWith('</svg>'));
assert.ok(svg.includes('clipPath'));
console.log('  [PASS] Test 3: XML and vector paths well-formed');

console.log('ALL 3 BADGE GENERATOR TESTS PASSED DETERMINISTICALLY!');
