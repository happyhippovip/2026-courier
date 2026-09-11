const assert = require('assert');
const { RadarChartGenerator } = require('../lib/radar_generator');

console.log('Testing RadarChartGenerator...');

const generator = new RadarChartGenerator();

// Test 1: Generates valid SVG container
const svg = generator.generateSvg();
assert.ok(svg.startsWith('<svg'));
assert.ok(svg.endsWith('</svg>'));
assert.ok(svg.includes('polygon points='));

// Test 2: Custom metrics injection
const customSvg = generator.generateSvg({
  tokenSavings: 90,
  latencySpeedup: 99,
  memoryEfficiency: 88,
  rulePreservation: 100,
  costEfficiency: 95
});
assert.ok(customSvg.includes('Rule Preservation (100%)'));
assert.ok(customSvg.includes('Token Reduction (90%)'));

// Test 3: Verified view dimensions
assert.ok(svg.includes('viewBox="0 0 500 500"'));

console.log('All RadarChartGenerator tests passed (3/3)!');
