const assert = require('assert');
const { TerminalAnimator } = require('../lib/terminal_animator');

console.log('--- TEST 1: SVG Terminal Card Generation ---');
const sampleLines = [
  '$ npx agent-context-trimmer --audit',
  '=== CONTEXT TOKEN BLOAT AUDIT ===',
  'Target File: .cursorrules (14,280 tokens)',
  'Redundant Boilerplate: 5,998 tokens (42.0% BLOAT)',
  'Estimated Waste: $26.80 / month',
  'Amortization: 5.6 days at €5.00 purchase',
  '✔ AUDIT COMPLETE: Potential 42% context compaction verified.'
];

const svg = TerminalAnimator.generateCardSVG({
  title: 'agent-context-trimmer Demo Card',
  lines: sampleLines
});

assert(svg.startsWith('<svg xmlns="http://www.w3.org/2000/svg"'));
assert(svg.includes('agent-context-trimmer Demo Card'));
assert(svg.includes('Redundant Boilerplate: 5,998 tokens'));
assert(svg.includes('fill="#2ea043"'), 'Accented lines must use green fill');
console.log('PASS [Test 1]: SVG card accurately compiles terminal text into vector graphics.');

console.log('--- TEST 2: XML Character Escaping ---');
const unescapedLines = [
  'Checking <special> & "quoted" characters in code'
];
const escapedSvg = TerminalAnimator.generateCardSVG({ lines: unescapedLines });
assert(escapedSvg.includes('&lt;special&gt; &amp; &quot;quoted&quot;'));
assert(!escapedSvg.includes('<special>'));
console.log('PASS [Test 2]: XML special characters safely escaped against injection.');

console.log('--- TEST 3: Dynamic Height Calculation ---');
const shortCard = TerminalAnimator.generateCardSVG({ lines: ['Line 1'] });
const tallCard = TerminalAnimator.generateCardSVG({ lines: ['Line 1', 'Line 2', 'Line 3', 'Line 4', 'Line 5'] });
const getHeight = (str) => parseInt(str.match(/height="(\d+)"/)[1], 10);
assert(getHeight(tallCard) > getHeight(shortCard));
console.log('PASS [Test 3]: SVG viewBox height dynamically scales with line count.');

console.log('\n>>> ALL 3 TERMINAL ANIMATOR TESTS PASS (100% DETERMINISTIC) <<<');
