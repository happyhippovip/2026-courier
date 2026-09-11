const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { CoherenceValidator } = require('../lib/coherence_validator');

console.log('--- Testing Context Coherence & Pronoun Resolution Validator ---');

const validator = new CoherenceValidator();

// Test 1: Anaphoric reference extraction
const query = 'Can you refactor this function and fix it so that it stops throwing the error?';
const refs = validator.extractReferences(query);
assert.ok(refs.length >= 3, 'Must identify pronouns and demonstratives');
assert.ok(refs.some(r => r.word === 'it'), 'Must detect pronoun it');
console.log('✓ Assertion 1 Passed: Pronouns and anaphoric references extracted');

// Test 2: Antecedent entity detection in retained context (Coherent)
const goodContext = 'In module dataProcessor.js, we defined formatOutput and handlePayload.';
const evalGood = validator.validateCoherence(goodContext, query);
assert.strictEqual(evalGood.isCoherent, true, 'Context with named entities must satisfy coherence check');
assert.strictEqual(evalGood.coherenceScore, 1.0);
console.log('✓ Assertion 2 Passed: Retained entities correctly satisfy pronoun references');

// Test 3: Dangling pronoun detection on over-pruned context
const emptyContext = 'System instructions: respond concisely.';
const evalBad = validator.validateCoherence(emptyContext, query);
assert.strictEqual(evalBad.isCoherent, false, 'Over-pruned context must flag dangling references');
assert.ok(evalBad.danglingReferences.length > 0, 'Dangling references recorded');
assert.strictEqual(evalBad.recommendation, 'RESTORE_REFERRED_ENTITIES');
console.log('✓ Assertion 3 Passed: Dangling references correctly flagged when antecedents are pruned');

// Test 4: Export evidence JSON
const evidencePath = path.resolve(__dirname, '../../../evidence/SAMPLE_COHERENCE_VALIDATION_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(evalGood, null, 2), 'utf8');
assert.ok(fs.existsSync(evidencePath), 'Evidence report must exist');
console.log('✓ Assertion 4 Passed: Evidence exported to SAMPLE_COHERENCE_VALIDATION_REPORT.json');

console.log('All 4 Coherence Validator tests passed successfully!');