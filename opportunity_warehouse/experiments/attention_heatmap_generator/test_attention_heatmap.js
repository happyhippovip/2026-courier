/**
 * test_attention_heatmap.js - Test suite for Attention Heatmap Generator
 */
const assert = require('assert');
const { AttentionHeatmapGenerator } = require('./lib/attention_heatmap');

console.log('--- Running test_attention_heatmap.js ---');

const gen = new AttentionHeatmapGenerator();

// Test 1: Profile calculation across 10 buckets
const res = gen.calculateRetentionProfile('claude-3-5-sonnet', 10);
assert.strictEqual(res.buckets.length, 11, 'Should produce 11 buckets from 0% to 100%');
assert.strictEqual(res.buckets[0].depthPercentage, 0);
assert.strictEqual(res.buckets[10].depthPercentage, 100);
assert.strictEqual(res.buckets[0].estimatedAttentionRetention, 1.0, 'Edges must have 100% retention');
assert.strictEqual(res.buckets[10].estimatedAttentionRetention, 1.0, 'End edge must have 100% retention');
console.log('✓ Test 1 Passed: Retention profile generates accurate 11-point curve');

// Test 2: Center attention degradation ("Lost in the middle")
const centerBucket = res.buckets[5]; // 50% depth
assert.strictEqual(centerBucket.depthPercentage, 50);
assert.ok(centerBucket.estimatedAttentionRetention < 0.85, 'Center bucket must experience attention decay');
assert.strictEqual(centerBucket.zone, 'CRITICAL_ATTENTION_DEGRADATION');
console.log('✓ Test 2 Passed: 50% depth correctly flagged as critical degradation (' + centerBucket.estimatedAttentionRetention + ')');

// Test 3: SVG generation and structure
const svgOut = gen.generateSvg('gpt-4o');
assert.ok(svgOut.svg.startsWith('<svg'));
assert.ok(svgOut.svg.endsWith('</svg>'));
assert.ok(svgOut.svg.includes('Attention Retention Curve: GPT-4o'));
console.log('✓ Test 3 Passed: Clean SVG diagram generated with model metadata');

// Test 4: Model comparison support
const sonnet = gen.calculateRetentionProfile('claude-3-5-sonnet');
const gemini = gen.calculateRetentionProfile('gemini-1-5-pro');
assert.ok(gemini.buckets[5].estimatedAttentionRetention > sonnet.buckets[5].estimatedAttentionRetention, 'Gemini 1.5 Pro should retain higher center attention');
console.log('✓ Test 4 Passed: Model comparative differentials accurately modeled');

console.log('ALL 4 TESTS PASSED IN test_attention_heatmap.js\n');
