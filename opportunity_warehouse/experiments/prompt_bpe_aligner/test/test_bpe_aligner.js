const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { BpePromptAligner } = require('../lib/bpe_aligner');

console.log('--- Testing BPE Alignment & Model Tokenizer Engine ---');

const aligner = new BpePromptAligner();

const sampleText = [
  '# System Directives',
  'You are an autonomous engineering agent operating under Symphony standards.',
  '',
  '## Section 1: Security Controls',
  'Always enforce zero spend constraints and isolate memory boundaries.',
  'Never leak proprietary context outside permitted processes.',
  '',
  '```javascript',
  'function verifyAccess(token) {',
  '  return token.isValid && !token.isExpired;',
  '}',
  '```',
  '',
  '## Section 2: Historical Dialogue',
  'User asked for benchmark analysis on token compaction.',
  'Agent performed multi-stage pruning with zero data loss.'
].join('\n');

// Test 1: Multi-model token estimation
const densities = aligner.compareModelDensities(sampleText);
assert.ok(densities['gpt-4o'].estimatedTokens > 0, 'GPT-4o tokens estimated');
assert.ok(densities['claude-3-5'].estimatedTokens > 0, 'Claude tokens estimated');
assert.ok(densities['gemini-1-5'].estimatedTokens > 0, 'Gemini tokens estimated');
console.log('✓ Assertion 1 Passed: Multi-model token density profiles verified');

// Test 2: Safe boundary detection avoiding mid-code cut
const boundaries = aligner.findSafeBoundaries(sampleText);
assert.ok(boundaries.length > 0, 'Safe boundaries detected');
const codeFence = '```';
const codeStartOffset = sampleText.indexOf(codeFence + 'javascript');
const codeEndOffset = sampleText.indexOf(codeFence, codeStartOffset + 10) + 3;
const inCodeBoundary = boundaries.find(b => b.charOffset > codeStartOffset && b.charOffset < codeEndOffset);
assert.strictEqual(inCodeBoundary, undefined, 'Code block interior must not contain safe cut boundaries');
console.log('✓ Assertion 2 Passed: Safe structural boundaries identified without code block rupture');

// Test 3: Pruning alignment on structural heading boundary
const alignment = aligner.alignPruneSelection(sampleText, 0.35);
assert.ok(alignment.selectedBoundary !== null, 'High-safety boundary selected');
assert.strictEqual(alignment.selectedBoundary.safetyLevel, 'HIGH', 'Must prioritize HIGH safety boundary');
console.log('✓ Assertion 3 Passed: Pruning cut aligned cleanly to ' + alignment.selectedBoundary.reason);

// Test 4: Export evidence JSON
const evidencePath = path.resolve(__dirname, '../../../evidence/SAMPLE_BPE_ALIGNMENT_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(alignment, null, 2), 'utf8');
assert.ok(fs.existsSync(evidencePath), 'Evidence alignment report must exist');
console.log('✓ Assertion 4 Passed: Evidence exported to SAMPLE_BPE_ALIGNMENT_REPORT.json');

console.log('All 4 BPE Alignment Engine tests passed successfully!');