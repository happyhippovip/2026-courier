const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { ContextSlotAllocator } = require('../lib/slot_allocator');

const allocator = new ContextSlotAllocator();

// Define competing context requests
const requests = [
  { id: 'system_prompt', priority: 10, minTokens: 1000, requestedTokens: 1000 },
  { id: 'response_buffer', priority: 10, minTokens: 2048, requestedTokens: 2048 },
  { id: 'tool_schemas', priority: 8, minTokens: 500, requestedTokens: 1200 },
  { id: 'rag_documents', priority: 5, minTokens: 1000, requestedTokens: 4000 },
  { id: 'history_turns', priority: 4, minTokens: 500, requestedTokens: 3000 }
];

// Total budget: 8192 tokens
const result = allocator.allocateSlots(8192, requests);

// Test 1: Priority invariants receive 100% of requested tokens
assert.strictEqual(result.allocations['system_prompt'], 1000, 'System prompt must receive full 1000 tokens');
assert.strictEqual(result.allocations['response_buffer'], 2048, 'Response buffer must receive full 2048 tokens');
console.log('✓ Assertion 1 Passed: Priority invariants fully funded');

// Test 2: Total allocation strictly respects budget without overflow
assert.ok(result.totalAllocated <= 8192, 'Total allocated must not exceed 8192');
assert.strictEqual(result.totalAllocated, 8192, 'Budget must be fully utilized by elastic demands');
assert.strictEqual(result.remainingBudget, 0, 'Remaining headroom must be 0');
console.log('✓ Assertion 2 Passed: Context budget strictly respected with 100% utilization');

// Test 3: Tool schemas and higher priority elastic components satisfy higher percentage
const toolComponent = result.componentBreakdown.find(c => c.id === 'tool_schemas');
const ragComponent = result.componentBreakdown.find(c => c.id === 'rag_documents');
assert.strictEqual(toolComponent.allocatedTokens, 1200, 'Tool schemas must be 100% funded');
assert.ok(ragComponent.allocatedTokens >= ragComponent.minTokens, 'RAG must receive at least minimum tokens');
console.log('✓ Assertion 3 Passed: Priority-weighted distribution validated (Tools: ' + toolComponent.satisfiedPercent + '%, RAG: ' + ragComponent.satisfiedPercent + '%)');

// Test 4: Export evidence JSON
const evidencePath = path.resolve(__dirname, '../../../evidence/SAMPLE_SLOT_ALLOCATION_REPORT.json');
const report = {
  timestamp: new Date().toISOString(),
  totalBudget: result.totalBudget,
  totalAllocated: result.totalAllocated,
  allocations: result.allocations,
  componentBreakdown: result.componentBreakdown,
  overflowSafeVerified: true
};
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
assert.ok(fs.existsSync(evidencePath), 'Evidence report must exist');
console.log('✓ Assertion 4 Passed: Evidence exported to SAMPLE_SLOT_ALLOCATION_REPORT.json');

console.log('All 4 Context Slot Allocator tests passed successfully!');