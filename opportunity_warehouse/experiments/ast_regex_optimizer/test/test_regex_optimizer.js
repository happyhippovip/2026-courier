const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { RegexOptimizer } = require('../lib/regex_optimizer');

console.log('--- Testing AST Regular Expression Optimizer ---');

const optimizer = new RegexOptimizer();

const rawPattern = '^[a-zA-Z0-9_]+-[0-9]{4}-[abcabc]+$';

// Test 1: Redundancy detection
const red = optimizer.detectRedundancies(rawPattern);
assert.ok(red.length >= 2, 'Must detect at least 2 redundancies');
assert.ok(red.some(r => r.type === 'UNOPTIMIZED_WORD_CLASS'));
assert.ok(red.some(r => r.type === 'DUPLICATE_CLASS_CHARS'));
console.log('✓ Assertion 1 Passed: Redundant classes and duplicate characters detected');

// Test 2: Pattern optimization
const opt = optimizer.optimizePattern(rawPattern);
assert.ok(opt.optimizedPattern.includes('\\w+'), 'Word class must be simplified to \\w');
assert.ok(opt.optimizedPattern.includes('\\d{4}'), 'Digit class must be simplified to \\d');
assert.ok(opt.optimizedPattern.includes('[abc]+'), 'Duplicate characters in set must be removed');
assert.ok(opt.reductionPercent > 20, 'Pattern length reduction must exceed 20%');
console.log('✓ Assertion 2 Passed: Pattern compacted (' + opt.reductionPercent + '% length reduction)');

// Test 3: Semantic equivalence verification
const testInputs = ['user_1-2026-abc', 'admin-1234-a', 'invalid-str', 'user-9999-cbab'];
const sem = optimizer.verifySemantics(rawPattern, opt.optimizedPattern, testInputs);
assert.strictEqual(sem.allEquivalent, true, 'Optimized regex must match identically to original');
console.log('✓ Assertion 3 Passed: 100% semantic matching equivalence confirmed across test inputs');

// Test 4: Export evidence JSON
const evidencePath = path.resolve(__dirname, '../../../evidence/SAMPLE_REGEX_OPTIMIZATION_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify({ optimization: opt, semantics: sem }, null, 2), 'utf8');
assert.ok(fs.existsSync(evidencePath), 'Evidence report must exist');
console.log('✓ Assertion 4 Passed: Evidence exported to SAMPLE_REGEX_OPTIMIZATION_REPORT.json');

console.log('All 4 Regex Optimizer tests passed successfully!');