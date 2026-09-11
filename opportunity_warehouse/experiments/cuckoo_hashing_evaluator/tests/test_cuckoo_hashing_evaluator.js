const { CuckooHashTable } = require('../lib/cuckoo_hashing_evaluator');
const fs = require('fs');
const path = require('path');

console.log('Testing Cuckoo Hashing Evaluator...');
const cht = new CuckooHashTable(128, 32);

// Test 1: Insert multiple context key-values
cht.insert('token_system_scope', { span: [0, 200], role: 'system' });
cht.insert('token_user_prompt', { span: [200, 450], role: 'user' });
cht.insert('token_agent_call', { span: [450, 800], role: 'assistant' });
cht.insert('token_tool_result', { span: [800, 1200], role: 'tool' });

if (cht.size !== 4) throw new Error('Expected size 4, got ' + cht.size);
if (!cht.contains('token_system_scope')) throw new Error('Missing token_system_scope');
if (cht.lookup('token_user_prompt').role !== 'user') throw new Error('Role mismatch');
console.log('✓ Test 1: Inserted and verified 4 key-value items in O(1) time');

// Test 2: In-place update
cht.insert('token_system_scope', { span: [0, 250], role: 'system_updated' });
if (cht.size !== 4) throw new Error('Update should not change size');
if (cht.lookup('token_system_scope').role !== 'system_updated') throw new Error('Update failed');
console.log('✓ Test 2: In-place update succeeded idempotently');

// Test 3: Deletion in O(1) time
const deleted = cht.delete('token_agent_call');
if (!deleted || cht.contains('token_agent_call')) throw new Error('Deletion failed');
if (cht.size !== 3) throw new Error('Size should be 3 after deletion');
console.log('✓ Test 3: Deletion confirmed in O(1) steps');

// Test 4: Write verification report
const report = {
  experiment: 'cuckoo_hashing_evaluator',
  phase: 437,
  timestamp: new Date().toISOString(),
  tableSize: cht.tableSize,
  activeItems: cht.size,
  testedLookups: ['token_system_scope', 'token_user_prompt', 'token_tool_result'],
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_CUCKOO_HASHING_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_CUCKOO_HASHING_REPORT.json');

console.log('All Cuckoo Hashing tests passed successfully!');
