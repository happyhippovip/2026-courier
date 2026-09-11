/**
 * test_entropy_measurer.js - Test suite for Context Entropy Measurer
 */
const assert = require('assert');
const { ContextEntropyMeasurer } = require('./lib/entropy_measurer');

console.log('--- Running test_entropy_measurer.js ---');

const measurer = new ContextEntropyMeasurer();

// Test 1: Shannon entropy calculation
const uniformText = 'abcdefghijklmnopqrstuvwxyz';
const repetitiveText = 'aaaaaaaaaaaaaaaaaaaaaaaaaa';
const entropyUniform = measurer.calculateShannonEntropy(uniformText);
const entropyRepetitive = measurer.calculateShannonEntropy(repetitiveText);

assert.ok(entropyUniform > 4.5, 'Uniform text should have high entropy');
assert.strictEqual(entropyRepetitive, 0, 'Single repeating character must have 0 entropy');
console.log('✓ Test 1 Passed: Shannon entropy properly distinguishes high vs zero entropy');

// Test 2: Redundancy detection on repetitive boilerplate
const boilerplate = [
  'const x = 1;',
  'const x = 1;',
  'const x = 1;',
  '----------------------------------------',
  '========================================',
  'const x = 1;'
].join('\n');

const redundancy = measurer.calculateRedundancyRatio(boilerplate);
assert.ok(redundancy > 0.4, 'Redundancy ratio should be > 0.4 for repetitive boilerplate');
console.log('✓ Test 2 Passed: Redundancy ratio accurately detects repetitive lines and chars (' + redundancy + ')');

// Test 3: Information density score
const cleanCode = 'function calculateTotal(items) { return items.reduce((acc, i) => acc + i.price, 0); }';
const dirtyCode = cleanCode + '\n// DEBUG\n// DEBUG\n// DEBUG\n// DEBUG\n' + '                    ';
const densityClean = measurer.calculateInformationDensity(cleanCode);
const densityDirty = measurer.calculateInformationDensity(dirtyCode);

assert.ok(densityClean > densityDirty, 'Clean code must have higher information density than padded/debug code');
assert.ok(densityClean > 50, 'Clean code should score > 50 density');
console.log('✓ Test 3 Passed: Information density correctly rewards clean code vs padded code (' + densityClean + ' vs ' + densityDirty + ')');

// Test 4: Comparison analysis between raw and trimmed prompts
const rawPrompt = 'SYSTEM INSTRUCTIONS:\n' + cleanCode + '\n' + boilerplate;
const trimmedPrompt = 'SYSTEM INSTRUCTIONS:\n' + cleanCode;
const comp = measurer.compare(rawPrompt, trimmedPrompt);

assert.ok(comp.improvements.charsSaved > 0, 'Chars saved must be positive');
assert.ok(comp.improvements.compressionRatioPercent > 30, 'Compression ratio should exceed 30%');
assert.ok(comp.improvements.densityGainPercent > 0, 'Density gain should be positive');
console.log('✓ Test 4 Passed: Comparison report demonstrates density gain (' + comp.improvements.densityGainPercent + '%) and compression (' + comp.improvements.compressionRatioPercent + '%)');

console.log('ALL 4 TESTS PASSED IN test_entropy_measurer.js\n');
