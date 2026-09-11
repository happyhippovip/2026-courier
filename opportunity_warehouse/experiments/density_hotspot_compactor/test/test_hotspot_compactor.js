const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { DensityHotspotCompactor } = require('../lib/hotspot_compactor');

const compactor = new DensityHotspotCompactor();

const sampleLog = [
  'MUTEX LOCK ACQUIRED: resource=0x4910 nonce=994821',
  'heartbeat tick 1 ok',
  'heartbeat tick 2 ok',
  'heartbeat tick 3 ok',
  'heartbeat tick 4 ok',
  'ORDER SETTLED: receipt=EUR 5.00 tx=TX_99182 status=SETTLED',
  'idle ping received',
  'idle ping received',
  'MUTEX LOCK RELEASED: resource=0x4910' // Hotspot
].join('\n');

// Test 1: Density calculation cleanly separates hot vs cold lines
const hotDensity = compactor.calculateLineDensity('ORDER SETTLED: receipt=EUR 5.00 tx=TX_99182 status=SETTLED');
const coldDensity = compactor.calculateLineDensity('heartbeat tick 1 ok');
assert.ok(hotDensity >= 1.0, 'Hot lines must have density >= 1.0');
assert.ok(coldDensity < 0.5, 'Cold lines must have density < 0.5');
console.log('✓ Assertion 1 Passed: Density calculations validated (Hot: ' + hotDensity + ' vs Cold: ' + coldDensity + ')');

// Test 2: Compaction collapses cold zones and preserves hotspots 100%
const result = compactor.compactContext(sampleLog, 0.5);
assert.ok(result.compactedText.includes('MUTEX LOCK ACQUIRED: resource=0x4910 nonce=994821'), 'Must preserve lock acquisition');
assert.ok(result.compactedText.includes('ORDER SETTLED: receipt=EUR 5.00 tx=TX_99182 status=SETTLED'), 'Must preserve settlement hotspot');
assert.ok(result.compactedText.includes('MUTEX LOCK RELEASED: resource=0x4910'), 'Must preserve lock release');
assert.ok(result.compactedText.includes('[... 4 routine status log lines collapsed ...]'), 'Must collapse 4 heartbeat ticks');
assert.ok(result.compactedText.includes('[... 2 routine status log lines collapsed ...]'), 'Must collapse 2 idle pings');
console.log('✓ Assertion 2 Passed: Hotspots preserved 100% and 6 cold lines collapsed');

// Test 3: Token savings verification
assert.ok(result.tokensSaved > 0, 'Tokens saved must be positive');
assert.strictEqual(result.collapsedLinesCount, 6, 'Must collapse exactly 6 cold lines');
console.log('✓ Assertion 3 Passed: Token savings verified (' + result.tokensSaved + ' tokens saved, ' + result.savingsPercent + '%)');

// Test 4: Export evidence JSON
const evidencePath = path.resolve(__dirname, '../../../evidence/SAMPLE_HOTSPOT_COMPACTOR_REPORT.json');
const report = {
  timestamp: new Date().toISOString(),
  originalLines: result.originalLines,
  compactedLines: result.compactedLines,
  collapsedLinesCount: result.collapsedLinesCount,
  tokensSaved: result.tokensSaved,
  savingsPercent: result.savingsPercent,
  compactedSample: result.compactedText,
  hotspotsPreservedVerified: true
};
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
assert.ok(fs.existsSync(evidencePath), 'Evidence report must exist');
console.log('✓ Assertion 4 Passed: Evidence exported to SAMPLE_HOTSPOT_COMPACTOR_REPORT.json');

console.log('All 4 Density Hotspot Compactor tests passed successfully!');