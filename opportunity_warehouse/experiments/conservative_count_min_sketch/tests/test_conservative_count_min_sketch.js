const { ConservativeCountMinSketch } = require('../lib/conservative_count_min_sketch');
const fs = require('fs');
const path = require('path');

console.log('Testing Conservative Count-Min Sketch Evaluator...');
const ccms = new ConservativeCountMinSketch(128, 5);

// Add items:
// 'token_core': 300
// 'token_aux': 100
// 500 noise items
ccms.add('token_core', 300);
ccms.add('token_aux', 100);

for (let i = 0; i < 500; i++) {
  ccms.add('noise_' + i, 1);
}

// Test 1: High frequency item estimate
const estCore = ccms.estimate('token_core');
console.log('✓ Test 1: Conservative estimate for token_core: ' + estCore + ' (actual: 300)');
if (estCore < 300 || estCore > 310) {
  throw new Error('Conservative update overestimation exceeded bounds: ' + estCore);
}

// Test 2: Medium frequency item estimate
const estAux = ccms.estimate('token_aux');
console.log('✓ Test 2: Conservative estimate for token_aux: ' + estAux + ' (actual: 100)');
if (estAux < 100 || estAux > 115) {
  throw new Error('Conservative update aux overestimation exceeded bounds: ' + estAux);
}

// Test 3: Unseen token should estimate to 0 or very small (< 3) despite 500 noise additions
const estUnseen = ccms.estimate('token_completely_unseen');
console.log('✓ Test 3: Unseen token estimate: ' + estUnseen);
if (estUnseen > 3) throw new Error('Unseen token estimate too high: ' + estUnseen);

// Test 4: Write verification report
const report = {
  experiment: 'conservative_count_min_sketch',
  phase: 449,
  timestamp: new Date().toISOString(),
  width: ccms.width,
  depth: ccms.depth,
  totalEvents: ccms.totalEvents,
  testedEstimates: {
    core: { actual: 300, estimated: estCore },
    aux: { actual: 100, estimated: estAux },
    unseen: { actual: 0, estimated: estUnseen }
  },
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_CONSERVATIVE_CMS_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_CONSERVATIVE_CMS_REPORT.json');

console.log('All Conservative Count-Min Sketch tests passed successfully!');
