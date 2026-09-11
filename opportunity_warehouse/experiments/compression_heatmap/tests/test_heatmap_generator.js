const assert = require('assert');
const { HeatmapGenerator } = require('../lib/heatmap_generator');

console.log('Testing HeatmapGenerator...');

const generator = new HeatmapGenerator();

// Test 1: Color logic
assert.strictEqual(generator.getHeatColor(15), '#10B981');
assert.strictEqual(generator.getHeatColor(45), '#F59E0B');
assert.strictEqual(generator.getHeatColor(85), '#EF4444');

// Test 2: Generate SVG
const svg = generator.generateHeatmapSvg([10, 50, 90]);
assert.ok(svg.startsWith('<svg'));
assert.ok(svg.endsWith('</svg>'));
assert.ok(svg.includes('Chunk 1'));
assert.ok(svg.includes('Chunk 2'));
assert.ok(svg.includes('Chunk 3'));

// Test 3: Dimensions
assert.ok(svg.includes('viewBox="0 0 600 220"'));

console.log('All HeatmapGenerator tests passed (3/3)!');
