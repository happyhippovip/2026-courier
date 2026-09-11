const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { DictionaryTokenEncoder } = require('../lib/dictionary_encoder');

const encoder = new DictionaryTokenEncoder();

// Sample multi-turn tool transcripts with recurring verbose keys
const sampleBatch = [
  {
    transaction_reference_id: 'TX_99182',
    cryptographic_signature: 'sig_7f83b165',
    verification_status: 'SETTLED_EUR5',
    timestamp_epoch_millis: 1789128000,
    customer_account_metadata: { tier: 'enterprise', country_code: 'DE' }
  },
  {
    transaction_reference_id: 'TX_99183',
    cryptographic_signature: 'sig_4910a221',
    verification_status: 'SETTLED_EUR5',
    timestamp_epoch_millis: 1789128060,
    customer_account_metadata: { tier: 'enterprise', country_code: 'FR' }
  },
  {
    transaction_reference_id: 'TX_99184',
    cryptographic_signature: 'sig_882910df',
    verification_status: 'PENDING',
    timestamp_epoch_millis: 1789128120,
    customer_account_metadata: { tier: 'pro', country_code: 'NL' }
  }
];

// Test 1: Build dictionary
const dict = encoder.buildDictionary(sampleBatch);
assert.ok(dict.totalKeys >= 5, 'Should index at least 5 recurring keys');
assert.ok(dict.encodeDict['transaction_reference_id'] !== undefined, 'Must map transaction_reference_id');
console.log('✓ Assertion 1 Passed: Dictionary built indexing ' + dict.totalKeys + ' keys');

// Test 2: Encode payload
const encoded = encoder.encodePayload(sampleBatch, dict.encodeDict);
assert.ok(encoded[0]['$0'] !== undefined || encoded[0]['$1'] !== undefined, 'Keys must be replaced with $ shorthand');
assert.strictEqual(encoded[0].transaction_reference_id, undefined, 'Original verbose key must be stripped');
console.log('✓ Assertion 2 Passed: Payload successfully encoded with shorthand identifiers');

// Test 3: Lossless decode verification
const decoded = encoder.decodePayload(encoded, dict.decodeDict);
assert.deepStrictEqual(decoded, sampleBatch, 'Decoded payload must exactly equal original object');
console.log('✓ Assertion 3 Passed: 100% lossless round-trip decoded with deep equality');

// Test 4: Export evidence JSON
const efficiency = encoder.evaluateEfficiency(sampleBatch, encoded, dict);
const evidencePath = path.resolve(__dirname, '../../../evidence/SAMPLE_DICTIONARY_ENCODER_REPORT.json');
const report = {
  timestamp: new Date().toISOString(),
  totalKeysIndexed: dict.totalKeys,
  keyMappings: dict.encodeDict,
  efficiency,
  losslessEqualityVerified: true
};
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
assert.ok(fs.existsSync(evidencePath), 'Evidence report must exist');
console.log('✓ Assertion 4 Passed: Evidence exported to SAMPLE_DICTIONARY_ENCODER_REPORT.json');

console.log('All 4 Dictionary Token Encoder tests passed successfully!');