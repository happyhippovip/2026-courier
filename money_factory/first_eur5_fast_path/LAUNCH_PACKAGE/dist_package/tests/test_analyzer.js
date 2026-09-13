// tests/test_analyzer.js
// Deterministic unit tests for agent-context-trimmer

const assert = require('assert');
const path = require('path');
const fs = require('fs');
const { ContextAnalyzer } = require('../lib/analyzer');
const { AuditReporter } = require('../lib/reporter');

console.log('=== RUNNING AGENT CONTEXT TRIMMER TEST SUITE ===');

const analyzer = new ContextAnalyzer({ sessionTurns: 40, sessionsPerMonth: 20 });
const exampleDir = path.join(__dirname, '..', 'example');

// Test 1: Token Estimation Heuristic
{
  const shortText = "Hello world";
  const tokens = ContextAnalyzer.estimateTokens(shortText);
  assert(tokens >= 2 && tokens <= 4, `Expected 2-4 tokens, got ${tokens}`);
  console.log('[PASS] Test 1: Token estimation heuristic');
}

// Test 2: File Discovery in Workspace
{
  const files = analyzer.scanDirectory(exampleDir);
  assert.strictEqual(files.length, 2, `Expected 2 agent rule files, got ${files.length}`);
  console.log(`[PASS] Test 2: Directory scan discovered ${files.length} rule files`);
}

// Test 3: Duplicate Rule Detection
{
  const cursorFile = path.join(exampleDir, '.cursorrules');
  const rep = analyzer.analyzeFile(cursorFile);
  
  const duplicates = rep.issues.filter(i => i.type === 'DUPLICATE_RULE');
  assert(duplicates.length >= 2, `Expected at least 2 duplicate rules, found ${duplicates.length}`);
  
  const boilerplate = rep.issues.filter(i => i.type === 'VERBOSE_BOILERPLATE');
  assert(boilerplate.length >= 1, `Expected verbose boilerplate detected, found ${boilerplate.length}`);
  
  const giantBlock = rep.issues.filter(i => i.type === 'GIANT_EMBEDDED_CODE_BLOCK');
  assert(giantBlock.length >= 1, `Expected giant embedded code block detected, found ${giantBlock.length}`);

  console.log(`[PASS] Test 3: Issue detection (Duplicates: ${duplicates.length}, Boilerplate: ${boilerplate.length}, Giant Blocks: ${giantBlock.length})`);
}

// Test 4: Workspace Audit & Cost Projection
{
  const audit = analyzer.auditWorkspace(exampleDir);
  assert(audit.total_context_tokens_per_turn > 0, 'Context tokens must be > 0');
  assert(audit.total_wasted_tokens_per_turn > 0, 'Wasted tokens must be > 0');
  assert(audit.cost_breakdown['claude-3-5-sonnet'].monthly_wasted_burn_usd > 0, 'Monthly wasted burn must be > 0');
  assert(audit.optimization_potential_percent > 0, 'Optimization potential must be > 0');
  console.log(`[PASS] Test 4: Workspace cost projection (Tokens/turn: ${audit.total_context_tokens_per_turn}, Wasted/turn: ${audit.total_wasted_tokens_per_turn})`);
}

// Test 5: Terminal & HTML Report Rendering
{
  const audit = analyzer.auditWorkspace(exampleDir);
  const terminalOut = AuditReporter.formatTerminal(audit);
  assert(terminalOut.includes('AGENT CONTEXT & TOKEN COST AUDIT REPORT'), 'Terminal output must contain header');
  
  const tmpHtml = path.join(__dirname, 'test_output.html');
  AuditReporter.generateHtmlReport(audit, tmpHtml);
  assert(fs.existsSync(tmpHtml), 'HTML report must be generated on disk');
  const htmlContent = fs.readFileSync(tmpHtml, 'utf8');
  assert(htmlContent.includes('<!DOCTYPE html>'), 'HTML content must be valid HTML');
  assert(htmlContent.includes(audit.total_context_tokens_per_turn.toString()), 'HTML content must reflect token counts');
  
  fs.unlinkSync(tmpHtml); // Clean up
  console.log('[PASS] Test 5: Terminal formatting and HTML report generation');
}

// Test 6: Empty Directory Handling (Graceful Zeroes)
{
  const emptyDir = path.join(__dirname, 'empty_temp');
  if (!fs.existsSync(emptyDir)) fs.mkdirSync(emptyDir);
  const emptyAudit = analyzer.auditWorkspace(emptyDir);
  assert.strictEqual(emptyAudit.files_discovered_count, 0);
  assert.strictEqual(emptyAudit.total_context_tokens_per_turn, 0);
  assert.strictEqual(emptyAudit.total_wasted_tokens_per_turn, 0);
  fs.rmdirSync(emptyDir);
  console.log('[PASS] Test 6: Graceful zero handling on empty workspace');
}

console.log('\nALL 6 AGENT CONTEXT TRIMMER UNIT TESTS PASSED CLEANLY.\n');
