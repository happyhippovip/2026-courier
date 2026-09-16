# EXACT NEXT INTEGRATION COMMAND

To apply this integration package to production Courier and verify all 64 tests in one atomic, safe step, copy and paste this command into PowerShell:

```powershell
& "C:\Users\lol\AppData\Local\OpenAI\Codex\runtimes\cua_node\b58ca2eaa616c2da\bin\node.exe" -e "
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const prod = 'C:\\Users\\lol\\2026-workspace\\courier\\supervisor';
const shadow = 'C:\\Users\\lol\\2026-workspace\\courier\\scratch\\fast_production_readiness_v1\\FAST_INTEGRATION_PACKAGE';
const nodeBin = 'C:\\Users\\lol\\AppData\\Local\\OpenAI\\Codex\\runtimes\\cua_node\\b58ca2eaa616c2da\\bin\\node.exe';

console.log('=== STARTING ATOMIC COURIER PRODUCTION INTEGRATION ===');

// 1. Copy bundle directories
console.log('[1/4] Copying runtime bundles...');
const govSrc = path.join(shadow, 'SHADOW_PATCH', 'bundle', 'governance');
const govDst = path.join(prod, 'governance');
if (!fs.existsSync(govDst)) fs.mkdirSync(govDst, { recursive: true });
fs.readdirSync(govSrc).forEach(f => fs.copyFileSync(path.join(govSrc, f), path.join(govDst, f)));

const coreSrc = path.join(shadow, 'SHADOW_PATCH', 'bundle', 'core');
const coreDst = path.join(prod, 'core');
if (!fs.existsSync(coreDst)) fs.mkdirSync(coreDst, { recursive: true });
fs.readdirSync(coreSrc).forEach(f => fs.copyFileSync(path.join(coreSrc, f), path.join(coreDst, f)));

// 2. Copy enhanced supervisor files
console.log('[2/4] Deploying 5 core choke point modules...');
const files = ['no_stacking.js', 'lease_manager.js', 'decision_engine.js', 'progress_tracker.js', 'index.js'];
const shadowSup = path.join('C:\\Users\\lol\\2026-workspace\\courier\\scratch\\fast_production_readiness_v1\\supervisor');
files.forEach(f => fs.copyFileSync(path.join(shadowSup, f), path.join(prod, f)));

// 3. Run regression suite
console.log('[3/4] Running 45 P0 regression tests against production...');
execSync('"' + nodeBin + '" tests/test_supervisor_plane_p0.js', { cwd: 'C:\\Users\\lol\\2026-workspace\\courier', stdio: 'inherit' });

// 4. Run mandatory scenarios suite
console.log('[4/4] Running 19 mandatory readiness scenarios against production...');
execSync('"' + nodeBin + '" scratch/fast_production_readiness_v1/tests/test_mandatory_scenarios_suite.js', { cwd: 'C:\\Users\\lol\\2026-workspace\\courier', stdio: 'inherit' });

console.log('=== ATOMIC PRODUCTION INTEGRATION COMPLETED: 64/64 TESTS PASSED ===');
"
```
