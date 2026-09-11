const assert = require('assert');
const { detectRuleConflicts } = require('../lib/conflict_detector');

console.log('Running Rule Conflict Detector Tests...');

// Test 1: No conflicts in consistent text
const cleanRules = `
1. Always use TypeScript strict mode.
2. Use functional pure functions where possible.
3. Use 2 spaces for indentation.
`;
const cleanRes = detectRuleConflicts(cleanRules);
assert.strictEqual(cleanRes.conflicts_detected, 0);
console.log('  [PASS] Test 1: Clean rules produce 0 conflicts');

// Test 2: Detect contradiction (strict vs any)
const conflictingRules = `
- Always use strict typing and never use any.
- When prototyping, allow any for rapid iteration.
`;
const conflictRes = detectRuleConflicts(conflictingRules);
assert.strictEqual(conflictRes.conflicts_detected, 1);
assert.strictEqual(conflictRes.conflicts[0].topic, 'TypeScript Typing');
console.log('  [PASS] Test 2: TypeScript typing contradiction detected');

// Test 3: Detect multiple contradictions (functional vs OOP + tabs vs spaces)
const multiConflict = `
- Prefer functional components and avoid classes.
- Use class hierarchy and inheritance for state.
- Always use tabs for indentation.
- Enforce spaces only.
`;
const multiRes = detectRuleConflicts(multiConflict);
assert.strictEqual(multiRes.conflicts_detected, 2);
console.log('  [PASS] Test 3: Multiple contradictory rules detected');

// Test 4: Empty input resilience
const emptyRes = detectRuleConflicts('');
assert.strictEqual(emptyRes.conflicts_detected, 0);
assert.strictEqual(emptyRes.total_lines_analyzed, 0);
console.log('  [PASS] Test 4: Empty input resilience verified');

console.log('ALL 4 RULE CONFLICT DETECTOR TESTS PASSED DETERMINISTICALLY!');
