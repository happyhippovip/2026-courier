/**
 * test_roi_calculator.js - Test suite for Enterprise ROI Calculator
 */
const assert = require('assert');
const { EnterpriseRoiCalculator } = require('./lib/roi_calculator');

console.log('--- Running test_roi_calculator.js ---');

const calc = new EnterpriseRoiCalculator();

// Test 1: Standard 10-dev team calculation on Claude 3.5 Sonnet
const res1 = calc.calculate({ teamSize: 10, promptsPerDevPerDay: 40, model: 'claude-3-5-sonnet' });
assert.ok(res1.monthlyMetrics.grossSavingsUsd > 100, 'Monthly savings should exceed $100 for 10 devs');
assert.ok(res1.annualMetrics.grossSavingsUsd > 1000, 'Annual savings should exceed $1,000 for 10 devs');
assert.ok(res1.annualMetrics.paybackDays < 50.0, 'Payback period should be under 50 working days');
assert.ok(res1.annualMetrics.roiPercentage > 500, 'ROI percentage should be > 500%');
console.log('✓ Test 1 Passed: 10-dev team achieves $' + res1.monthlyMetrics.grossSavingsUsd + '/mo savings and ' + res1.annualMetrics.paybackDays + '-day payback');

// Test 2: Single developer €5 payback calculation
const res2 = calc.calculate({ teamSize: 1, promptsPerDevPerDay: 25, licenseCostEur: 5.00 });
assert.ok(res2.monthlyMetrics.grossSavingsUsd > 5, 'Single dev should save > $5/mo');
assert.ok(res2.annualMetrics.paybackDays < 15.0, '€5 license should pay back in under 15 days');
console.log('✓ Test 2 Passed: Single dev €5 tier pays back in ' + res2.annualMetrics.paybackDays + ' days');

// Test 3: Model comparison: GPT-4o vs Claude 3.5
const resGpt = calc.calculate({ teamSize: 10, model: 'gpt-4o' });
const resClaude = calc.calculate({ teamSize: 10, model: 'claude-3-5-sonnet' });
assert.ok(resClaude.monthlyMetrics.grossSavingsUsd > resGpt.monthlyMetrics.grossSavingsUsd, 'Claude rate ($3) saves more dollars than GPT-4o rate ($2.50)');
console.log('✓ Test 3 Passed: Multi-model pricing differences properly reflected');

// Test 4: Markdown summary table generation
const md = calc.generateMarkdownTable(res1);
assert.ok(md.includes('Enterprise ROI Financial Summary'), 'Markdown must contain summary header');
assert.ok(md.includes('Payback Period'), 'Markdown must include payback period');
console.log('✓ Test 4 Passed: Formatted markdown financial report generated successfully');

console.log('ALL 4 TESTS PASSED IN test_roi_calculator.js\n');
