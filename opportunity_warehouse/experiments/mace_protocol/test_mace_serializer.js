/**
 * test_mace_serializer.js - Test suite for MACE Serializer
 */
const assert = require('assert');
const { MaceSerializer } = require('./lib/mace_serializer');

console.log('--- Running test_mace_serializer.js ---');

const serializer = new MaceSerializer();

// Test 1: Serialize clean context
const mockContext = {
  messages: [
    { role: 'user', content: 'Please review the user service implementation.' },
    { role: 'assistant', content: 'I will analyze the user service.' }
  ],
  toolOutputs: [
    { name: 'read_file', callId: 'call_1', output: 'class UserService { getUser() { return 1; } }' }
  ],
  workspaceFlags: { branch: 'main' }
};

const payload = serializer.serializeHandoff('ArchitectAgent', 'CoderAgent', mockContext);
assert.strictEqual(payload.protocol, 'MACE', 'Protocol must be MACE');
assert.strictEqual(payload.header.senderAgent, 'ArchitectAgent');
assert.ok(payload.checksum.length === 64, 'Checksum must be 64-char sha256');
console.log('✓ Test 1 Passed: Basic serialization produces valid MACE envelope');

// Test 2: Tool output deduplication
const dupContext = {
  messages: mockContext.messages,
  toolOutputs: [
    { name: 'read_file', callId: 'call_1', output: 'REPEATED_LARGE_FILE_CONTENT_XYZ'.repeat(20) },
    { name: 'read_file', callId: 'call_2', output: 'REPEATED_LARGE_FILE_CONTENT_XYZ'.repeat(20) } // duplicate
  ]
};

const dupPayload = serializer.serializeHandoff('PlannerAgent', 'ExecutorAgent', dupContext);
assert.ok(dupPayload.header.duplicateTokensSaved > 0, 'Must record tokens saved from deduplication');
assert.ok(dupPayload.state.toolOutputs[1].output.startsWith('[MACE_REF:'), 'Second output should be reference');
console.log('✓ Test 2 Passed: Redundant tool output replaced with MACE reference');

// Test 3: Deserialization and reference expansion
const restored = serializer.deserializeHandoff(dupPayload);
assert.strictEqual(restored.verified, true, 'Restoration must verify checksum');
assert.strictEqual(restored.toolOutputs[0].output, restored.toolOutputs[1].output, 'Restored content must match original');
assert.strictEqual(restored.toolOutputs[1].restoredFromRef, true, 'Second output flagged as restored');
console.log('✓ Test 3 Passed: Deserialization faithfully reconstructs referenced outputs');

// Test 4: Tamper detection / checksum validation
const tamperedPayload = JSON.parse(JSON.stringify(payload));
tamperedPayload.state.messages[0].content = 'Tampered content injection!';
assert.throws(() => {
  serializer.deserializeHandoff(tamperedPayload);
}, /MACE checksum mismatch/, 'Must reject tampered state');
console.log('✓ Test 4 Passed: Cryptographic checksum prevents state tampering');

console.log('ALL 4 TESTS PASSED IN test_mace_serializer.js\n');
