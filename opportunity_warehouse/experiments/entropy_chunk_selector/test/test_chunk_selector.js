const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { EntropyChunkSelector } = require('../lib/chunk_selector');

const selector = new EntropyChunkSelector();

// Sample chunks with differing informational densities
const sampleChunks = [
  { id: 'c0_log', text: 'INFO [2026-09-11 12:00:00]: Heartbeat ok. Heartbeat ok. Heartbeat ok. Heartbeat ok.' },
  { id: 'c1_security', text: 'CRITICAL SECURITY: Mutex acquired on resource:0x4910. HMAC sha256:7f83b165 signed with ephemeral nonce.' },
  { id: 'c2_filler', text: 'System status normal. System status normal. System status normal. System status normal.' },
  { id: 'c3_payment', text: 'ORDER EVENT: Received purchase receipt EUR 5.00 from buyer:anon_948. Transaction ID: TX_9948172.' },
  { id: 'c4_debug', text: 'DEBUG: tick. DEBUG: tick. DEBUG: tick. DEBUG: tick. DEBUG: tick.' }
];

// Test 1: Shannon entropy distinguishes boilerplate from high-entropy events
const entBoilerplate = selector.computeShannonEntropy(sampleChunks[0].text);
const entSecurity = selector.computeShannonEntropy(sampleChunks[1].text);
assert.ok(entSecurity > entBoilerplate, 'Security chunk must have higher entropy than repetitive heartbeat');
console.log('✓ Assertion 1 Passed: Entropy cleanly separates informational signal (' + entSecurity + ') from noise (' + entBoilerplate + ')');

// Test 2: Chunk density scoring correctly evaluates candidates
const evaluated = sampleChunks.map((c, i) => selector.evaluateChunk(c, i));
const securityItem = evaluated.find(e => e.id === 'c1_security');
const logItem = evaluated.find(e => e.id === 'c0_log');
assert.ok(securityItem.densityScore > logItem.densityScore, 'Security score must exceed log score');
console.log('✓ Assertion 2 Passed: Density scoring favors diverse lexical items (Security: ' + securityItem.densityScore + ' vs Log: ' + logItem.densityScore + ')');

// Test 3: Budget packing strictly respects limit and maintains chronological sequence
const packed = selector.packBudget(sampleChunks, 60);
assert.ok(packed.usedTokens <= 60, 'Packed tokens must not exceed budget');
assert.ok(packed.selectedCount >= 2, 'Should pick at least 2 top chunks');
// Verify selected chunks contain high-entropy items
const selectedIds = packed.selectedChunks.map(c => c.id);
assert.ok(selectedIds.includes('c1_security'), 'Must retain security chunk');
assert.ok(selectedIds.includes('c3_payment'), 'Must retain payment chunk');
// Verify chronological ordering preserved
for (let i = 1; i < packed.selectedChunks.length; i++) {
  assert.ok(packed.selectedChunks[i].originalIndex > packed.selectedChunks[i - 1].originalIndex, 'Chronological ordering must be preserved');
}
console.log('✓ Assertion 3 Passed: Packed within budget (' + packed.usedTokens + '/60 tokens) preserving chronological ordering');

// Test 4: Export evidence JSON
const evidencePath = path.resolve(__dirname, '../../../evidence/SAMPLE_ENTROPY_CHUNK_REPORT.json');
const report = {
  timestamp: new Date().toISOString(),
  tokenBudget: packed.tokenBudget,
  usedTokens: packed.usedTokens,
  selectedIds,
  verifiedMonotonicOrder: true
};
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
assert.ok(fs.existsSync(evidencePath), 'Evidence report must exist');
console.log('✓ Assertion 4 Passed: Evidence exported to SAMPLE_ENTROPY_CHUNK_REPORT.json');

console.log('All 4 Entropy-Weighted Chunk Selector tests passed successfully!');