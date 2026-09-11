const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { JsonSchemaPruner } = require('../lib/schema_pruner');

console.log('--- Testing JSON Schema Pruner & Type Flattener ---');

const pruner = new JsonSchemaPruner();

const sampleToolSchema = {
  '$schema': 'https://json-schema.org/draft/2020-12/schema',
  'title': 'ExecuteDatabaseQuery',
  'type': 'object',
  'additionalProperties': false,
  'allOf': [
    {
      'type': 'object',
      'properties': {
        'query': {
          'type': 'string',
          'description': 'The exact SQL query string to run on the database.',
          'examples': ['SELECT * FROM users WHERE active = true']
        },
        'timeoutMs': {
          'type': 'number',
          'description': 'Query execution timeout in milliseconds.',
          'default': 5000
        }
      },
      'required': ['query']
    }
  ]
};

// Test 1: Pruning metadata fields and flattening allOf
const result = pruner.pruneSchema(sampleToolSchema);
assert.strictEqual(result.prunedSchema.$schema, undefined, '$schema must be stripped');
assert.strictEqual(result.prunedSchema.title, undefined, 'title must be stripped');
assert.strictEqual(result.prunedSchema.allOf, undefined, 'allOf wrapper must be flattened');
assert.ok(result.prunedSchema.properties.query, 'query property must be preserved');
assert.strictEqual(result.prunedSchema.properties.query.examples, undefined, 'examples must be stripped');
console.log('✓ Assertion 1 Passed: Schema metadata stripped and allOf flattened');

// Test 2: Token savings verification
assert.ok(result.tokensSaved > 0, 'Must save tokens');
assert.ok(result.savingsPercent > 40, 'Savings must exceed 40%');
console.log('✓ Assertion 2 Passed: Schema minification saved ' + result.savingsPercent + '% tokens');

// Test 3: Validation compatibility against original schema expectations
const validPayload = { query: 'SELECT 1', timeoutMs: 3000 };
const invalidPayload = { timeoutMs: 3000 }; // missing required query
assert.strictEqual(pruner.validatePayload(result.prunedSchema, validPayload), true, 'Valid payload must pass');
assert.strictEqual(pruner.validatePayload(result.prunedSchema, invalidPayload), false, 'Invalid payload must fail');
console.log('✓ Assertion 3 Passed: Pruned schema maintains strict validation contract');

// Test 4: Export evidence JSON
const evidencePath = path.resolve(__dirname, '../../../evidence/SAMPLE_JSON_SCHEMA_PRUNING_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(result, null, 2), 'utf8');
assert.ok(fs.existsSync(evidencePath), 'Evidence report must exist');
console.log('✓ Assertion 4 Passed: Evidence exported to SAMPLE_JSON_SCHEMA_PRUNING_REPORT.json');

console.log('All 4 JSON Schema Pruner tests passed successfully!');