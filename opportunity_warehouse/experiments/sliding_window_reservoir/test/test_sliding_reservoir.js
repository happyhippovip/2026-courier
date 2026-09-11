const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { SlidingWindowReservoir } = require('../lib/sliding_reservoir');

console.log('--- Testing Sliding Window Reservoir ---');

const reservoir = new SlidingWindowReservoir(1000); // 1,000 token budget

// Add initial core anchor event
reservoir.addEvent('anchor_sys_prompt', 'critical', 300, 'System Directives', true);

// Test 1: Anchor event registered
assert.strictEqual(reservoir.events.length, 1);
assert.strictEqual(reservoir.events[0].isAnchor, true);
console.log('✓ Assertion 1 Passed: Core anchor event successfully registered');

// Test 2: Add medium and low priority events within budget
reservoir.addEvent('event_log_1', 'low', 200, 'User connected');
reservoir.addEvent('event_log_2', 'medium', 250, 'Ran unit test suite');
assert.strictEqual(reservoir.getCurrentTokenTotal(), 750, 'Total should be 750 tokens');
console.log('✓ Assertion 2 Passed: Events within capacity retained');

// Test 3: Saturate reservoir with high priority event, forcing low priority eviction
reservoir.addEvent('event_security_alert', 'critical', 400, 'Security gate blocked unauthorized call');

// Budget was 1000. Total added = 300 (anchor) + 200 (low) + 250 (med) + 400 (crit) = 1150 > 1000.
// Low event (event_log_1, 200) should have been evicted first -> Remaining = 300 + 250 + 400 = 950 <= 1000.
assert.ok(reservoir.getCurrentTokenTotal() <= 1000, 'Budget must not be exceeded');
const hasAnchor = reservoir.events.some(e => e.id === 'anchor_sys_prompt');
const hasLow = reservoir.events.some(e => e.id === 'event_log_1');
const hasCrit = reservoir.events.some(e => e.id === 'event_security_alert');

assert.strictEqual(hasAnchor, true, 'Anchor event must never be evicted');
assert.strictEqual(hasLow, false, 'Low priority event must be evicted under saturation');
assert.strictEqual(hasCrit, true, 'Critical event must be retained');
console.log('✓ Assertion 3 Passed: Priority decay evicted low-signal events while preserving anchor');

// Test 4: Export evidence JSON
const report = reservoir.generateReservoirReport();
const evidencePath = path.resolve(__dirname, '../../../evidence/SAMPLE_SLIDING_RESERVOIR_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
assert.ok(fs.existsSync(evidencePath), 'Evidence report must exist');
console.log('✓ Assertion 4 Passed: Evidence exported to SAMPLE_SLIDING_RESERVOIR_REPORT.json');

console.log('All 4 Sliding Window Reservoir tests passed successfully!');