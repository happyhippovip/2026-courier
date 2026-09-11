const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { RepetitionCompressor } = require('../lib/repetition_compressor');

const compressor = new RepetitionCompressor();

const sampleDivider = '=================================================='; // 50 equals
const sampleText = [
  '--- AUDIT REPORT ---',
  sampleDivider,
  'Status: OK',
  sampleDivider
].join('\n');

// Test 1: Compress long character dividers
const comp = compressor.compressRepetitions(sampleText);
assert.ok(comp.compressedText.includes('[REPEAT: "=" x 50]'), 'Must encode 50 equals into repeat tag');
assert.ok(comp.tokensSaved > 0, 'Must save tokens on 50 repeated chars');
console.log('✓ Assertion 1 Passed: Character dividers compressed into repeat tags (' + comp.tokensSaved + ' tokens saved)');

// Test 2: Decompress restores divider losslessly
const decomp = compressor.decompressRepetitions(comp.compressedText);
assert.strictEqual(decomp, sampleText, 'Decompressed text must match original exactly');
console.log('✓ Assertion 2 Passed: Decompression restored original text with 100% byte fidelity');

// Test 3: Repeated pattern compression
const arrayText = 'Values: ' + '0, '.repeat(20);
const compArray = compressor.compressRepetitions(arrayText);
assert.ok(compArray.compressedText.includes('[REPEAT: "0," x 20]'), 'Must compress 20 repeated zeros');
assert.ok(compArray.tokensSaved > 0, 'Tokens saved must be positive');
console.log('✓ Assertion 3 Passed: Repeated array pattern compressed efficiently');

// Test 4: Export evidence JSON
const evidencePath = path.resolve(__dirname, '../../../evidence/SAMPLE_REPETITION_COMPRESSION_REPORT.json');
const report = {
  timestamp: new Date().toISOString(),
  dividerSavings: comp.savingsPct,
  arraySavings: compArray.savingsPct,
  sampleCompressed: comp.compressedText,
  losslessRoundtripVerified: true
};
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
assert.ok(fs.existsSync(evidencePath), 'Evidence report must exist');
console.log('✓ Assertion 4 Passed: Evidence exported to SAMPLE_REPETITION_COMPRESSION_REPORT.json');

console.log('All 4 Repetition Compressor tests passed successfully!');