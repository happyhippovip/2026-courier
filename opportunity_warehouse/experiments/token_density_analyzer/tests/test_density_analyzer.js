const assert = require('assert');
const { TokenDensityAnalyzer, MODEL_SPECS } = require('../lib/density_analyzer');

console.log('Testing TokenDensityAnalyzer...');

const analyzer = new TokenDensityAnalyzer();

// Test 1: Model spec retrieval
const gptSpec = analyzer.getModelSpec('gpt-4o');
assert.strictEqual(gptSpec.maxContext, 128000);
const unknownSpec = analyzer.getModelSpec('custom-llm');
assert.strictEqual(unknownSpec.maxContext, 128000);

// Test 2: Token estimation
const text = 'Hello world, this is a prompt for an agent with instructions.';
const tokens = analyzer.estimateTokens(text, 'gpt-4o');
assert.ok(tokens.estimatedTokens > 0);
assert.strictEqual(tokens.modelId, 'gpt-4o');

// Test 3: Prompt efficiency analysis
const originalPrompt = 'System instructions: '.repeat(200);
const trimmedPrompt = 'System instructions: '.repeat(100);
const efficiency = analyzer.analyzePromptEfficiency(originalPrompt, trimmedPrompt, 'claude-3-5-sonnet');
assert.ok(efficiency.savings.savingsPercent > 49 && efficiency.savings.savingsPercent < 51);
assert.ok(efficiency.savings.tokensSaved > 0);
assert.ok(efficiency.savings.costSavingsEurUsd > 0);

// Test 4: Benchmark across all frontier models
const benchmark = analyzer.benchmarkAcrossFrontierModels(originalPrompt, trimmedPrompt);
assert.ok(benchmark['gpt-4o']);
assert.ok(benchmark['claude-3-5-sonnet']);
assert.ok(benchmark['gemini-1-5-pro']);
assert.ok(benchmark['deepseek-v3']);

console.log('All TokenDensityAnalyzer tests passed (4/4)!');
