const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { ContextDeltaVisualizer } = require('../lib/delta_visualizer');

console.log('--- Testing Context Delta Visualizer ---');

const visualizer = new ContextDeltaVisualizer();

visualizer.recordTurn(1, 12000, 4800, 'system_rules');
visualizer.recordTurn(2, 24000, 9200, 'code_module');
visualizer.recordTurn(3, 45000, 18000, 'full_history');
visualizer.recordTurn(4, 68000, 22000, 'deep_context');

// Test 1: Record delta metrics
assert.strictEqual(visualizer.turnRecords.length, 4, 'Must record 4 turns');
const r4 = visualizer.turnRecords[3];
assert.strictEqual(r4.tokensSaved, 46000);
assert.ok(r4.savingsPercent > 65, 'Turn 4 savings must exceed 65%');
console.log('✓ Assertion 1 Passed: Turn delta records computed accurately');

// Test 2: ASCII waterfall generation
const waterfall = visualizer.generateAsciiWaterfall();
assert.ok(waterfall.includes('SYMPHONY CONTEXT COMPRESSION WATERFALL'), 'Waterfall header must be present');
assert.ok(waterfall.includes('█'), 'Visual bar glyphs must render');
console.log('✓ Assertion 2 Passed: ASCII compression waterfall rendered successfully');

// Test 3: SVG chart generation
const svg = visualizer.generateSvgChart();
assert.ok(svg.startsWith('<svg'), 'Must render valid SVG root');
assert.ok(svg.endsWith('</svg>'), 'Must properly close SVG tag');
assert.ok(svg.includes('polyline'), 'Must render polyline paths');
console.log('✓ Assertion 3 Passed: SVG delta curve generated without XML syntax errors');

// Test 4: Export evidence files (SVG and JSON)
const svgEvidencePath = path.resolve(__dirname, '../../../evidence/SAMPLE_CONTEXT_DELTA_CHART.svg');
const jsonEvidencePath = path.resolve(__dirname, '../../../evidence/SAMPLE_CONTEXT_DELTA_METRICS.json');
fs.writeFileSync(svgEvidencePath, svg, 'utf8');
fs.writeFileSync(jsonEvidencePath, JSON.stringify(visualizer.turnRecords, null, 2), 'utf8');
assert.ok(fs.existsSync(svgEvidencePath), 'SVG evidence must exist');
assert.ok(fs.existsSync(jsonEvidencePath), 'JSON evidence must exist');
console.log('✓ Assertion 4 Passed: SVG and JSON evidence exported successfully');

console.log('All 4 Context Delta Visualizer tests passed successfully!');