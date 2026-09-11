const { SuffixWaveletRLECompressor } = require('../lib/suffix_wavelet_rle_compressor');
const assert = require('assert');
const path = require('path');

console.log('Testing Suffix Wavelet RLE Compressor...');

const compressor = new SuffixWaveletRLECompressor();

// Test 1: Empty stream
const emptyResult = compressor.compress([]);
assert.strictEqual(emptyResult.runCount, 0);
assert.deepStrictEqual(compressor.decompress(), []);
console.log('✓ Test 1: Empty stream handling verified');

// Test 2: Highly repetitive token stream (ideal for BWT + RLE)
const repetitive = [10, 10, 10, 20, 20, 10, 10, 10, 20, 20, 30, 30, 30];
const compRep = compressor.compress(repetitive);
assert(compRep.runCount < repetitive.length, 'RLE must achieve run count reduction');
const decompRep = compressor.decompress();
assert.deepStrictEqual(decompRep, repetitive, 'Lossless roundtrip must restore exact tokens');
console.log('✓ Test 2: Lossless roundtrip verified on repetitive stream');

// Test 3: Frequency queries
const freq10 = compressor.querySymbolFrequency(10);
assert.strictEqual(freq10, 6, 'Frequency of token 10 must be exactly 6');
const freq30 = compressor.querySymbolFrequency(30);
assert.strictEqual(freq30, 3, 'Frequency of token 30 must be exactly 3');
console.log('✓ Test 3: Symbol frequency query accurately verified');

// Test 4: Arbitrary integer sequence
const sequence = [5, 2, 8, 1, 9, 3, 5, 2, 8];
compressor.compress(sequence);
const decompSeq = compressor.decompress();
assert.deepStrictEqual(decompSeq, sequence, 'Arbitrary sequence must restore identically');
console.log('✓ Test 4: Arbitrary sequence lossless restoration confirmed');

// Test 5: Export evidence report
const reportPath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_SUFFIX_WAVELET_RLE_REPORT.json');
const report = compressor.exportEvidenceReport(reportPath);
assert(report.subsystem === 'suffix_wavelet_rle_compressor');
console.log('✓ Test 5: Evidence report written to SAMPLE_SUFFIX_WAVELET_RLE_REPORT.json');

console.log('All Suffix Wavelet RLE Compressor tests passed successfully!');
