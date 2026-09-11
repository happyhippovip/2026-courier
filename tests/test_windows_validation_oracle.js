const assert = require('assert');
const fs = require('fs');
const path = require('path');
const {
  ShellClass,
  CommandType,
  ProcessState,
  AccessIntegrityStatus,
  WindowsValidationOracle
} = require('../windows_validation_oracle');

console.log('Running Windows Validation Oracle Test Suite...');

const oracle = new WindowsValidationOracle();

// --- TEST 1: Path Assumptions & Reserved Device Names ---
console.log('\n[TEST 1] Validating Windows Path Assumptions & Reserved Device Names...');
const p1 = oracle.normalizePath('C:/Users/lol/2026-workspace/courier/file.txt', 'windows');
assert.strictEqual(p1.valid, true);
assert.strictEqual(p1.normalized, 'C:\\Users\\lol\\2026-workspace\\courier\\file.txt');
assert.strictEqual(p1.isLongPath, false);

const p2 = oracle.normalizePath('C:\\Users\\lol\\nul.txt', 'windows');
assert.strictEqual(p2.valid, false);
assert.ok(p2.error.includes('RESERVED_WINDOWS_DEVICE_NAME: NUL'));

const p3 = oracle.normalizePath('C:/Users/lol/' + 'a'.repeat(270) + '/file.txt', 'windows');
assert.strictEqual(p3.valid, true);
assert.strictEqual(p3.isLongPath, true);
assert.strictEqual(p3.requiresLongPathPrefix, true);
console.log('✓ PASS [Test 1]: Path normalization, 260-char bound, and reserved device names verified.');

// --- TEST 2: Mac-Only Assumption Detection ---
console.log('\n[TEST 2] Detecting Mac-Only Assumptions...');
const macSnippet1 = 'flock -n /tmp/courier.lock -c "node runner.js"';
const findings1 = oracle.detectMacOnlyAssumptions(macSnippet1);
assert.ok(findings1.length >= 2, 'Should catch flock and /tmp');
assert.ok(findings1.some(f => f.issue.includes('flock')));
assert.ok(findings1.some(f => f.issue.includes('/tmp')));

const macSnippet2 = 'kill -9 -1234 && pbcopy < result.txt';
const findings2 = oracle.detectMacOnlyAssumptions(macSnippet2);
assert.ok(findings2.length >= 2, 'Should catch kill -9 and pbcopy');
console.log('✓ PASS [Test 2]: Mac-only assumptions successfully flagged.');

// --- TEST 3: Shell Provenance Classification ---
console.log('\n[TEST 3] Classifying Shell Provenance (CMD vs POWERSHELL vs BASH)...');
const pwshCmd = '$env:HOME = "C:\\Users\\lol"; Get-Process | Measure-Object';
assert.strictEqual(oracle.classifyShell(pwshCmd), ShellClass.POWERSHELL);

const cmdCmd = 'set FOO=BAR && dir /b && type nul > test.txt';
assert.strictEqual(oracle.classifyShell(cmdCmd), ShellClass.CMD);

const bashCmd = 'export FOO=BAR && source ./env.sh';
assert.strictEqual(oracle.classifyShell(bashCmd), ShellClass.BASH);
console.log('✓ PASS [Test 3]: Shell provenance strictly distinguished without cross-confusion.');

// --- TEST 4: Command Type Classification & Unresolved Placeholders ---
console.log('\n[TEST 4] Classifying Command Types & Enforcing Fail-Closed Template Guards...');
const templateCmd = 'powershell -File script.ps1 -TargetDir <TARGET_PATH> -Port {{PORT}}';
const cType1 = oracle.classifyCommandType(templateCmd);
assert.strictEqual(cType1.commandType, CommandType.TEMPLATE);
assert.strictEqual(cType1.canExecute, false);
assert.ok(cType1.reason.includes('UNRESOLVED_PLACEHOLDER'));

const exampleCmd = '# example: run this to check memory\nGet-Process';
const cType2 = oracle.classifyCommandType(exampleCmd);
assert.strictEqual(cType2.commandType, CommandType.EXAMPLE);
assert.strictEqual(cType2.canExecute, false);

const executableCmd = 'powershell -NoProfile -ExecutionPolicy Bypass -File .\\Test-CourierAgyConfiguration.ps1';
const cType3 = oracle.classifyCommandType(executableCmd);
assert.strictEqual(cType3.commandType, CommandType.EXECUTABLE);
assert.strictEqual(cType3.canExecute, true);
console.log('✓ PASS [Test 4]: Template placeholders and example scripts fail closed deterministically.');

// --- TEST 5: Content Integrity != Access Integrity Decoupling ---
console.log('\n[TEST 5] Verifying Content Integrity vs Access Integrity Decoupling...');
const payload = 'CONFIDENTIAL_STATE_RECORD_V1';
const contentRes = oracle.verifyContentIntegrity(payload);
assert.strictEqual(typeof contentRes.sha256, 'string');
assert.strictEqual(contentRes.sha256.length, 64);

// Simulate broad Everyone:(F) ACL
const badAcl = 'C:\\workspace\\secret.json Everyone:(F) NT AUTHORITY\\SYSTEM:(F)';
const badAccess = oracle.evaluateAccessIntegrity(badAcl);
assert.strictEqual(badAccess.accessIntegrity, AccessIntegrityStatus.INSECURE_EVERYONE_FULLCONTROL);
assert.strictEqual(badAccess.isBroadFullControl, true);

// Prove decoupling: Content passes, but access fails closed!
const decouplingEval = oracle.assertIntegrityDecoupling(true, badAccess.accessIntegrity);
assert.strictEqual(decouplingEval.contentIntegrity, 'PASS');
assert.strictEqual(decouplingEval.totalAcceptance, 'FAIL_CLOSED');
console.log('✓ PASS [Test 5]: Invariant verified: Matching hash does NOT prove ACL access integrity.');

// --- TEST 6: Process State Machine & UNKNOWN != STOPPED Invariant ---
console.log('\n[TEST 6] Verifying Process State Machine & UNKNOWN != STOPPED Invariant...');
// Case 6A: Active process
const pState1 = oracle.evaluateProcessState({ pid: 12345, hasActivePid: true });
assert.strictEqual(pState1.state, ProcessState.RUNNING);
assert.strictEqual(pState1.isStopped, false);

// Case 6B: Stopping process
const pState2 = oracle.evaluateProcessState({ pid: 12345, hasActivePid: true, timeoutGraceExpired: true });
assert.strictEqual(pState2.state, ProcessState.STOPPING);
assert.strictEqual(pState2.isStopped, false);

// Case 6C: Positive evidence of termination
const pState3 = oracle.evaluateProcessState({ pid: 12345, hasActivePid: false, exitCode: 0 });
assert.strictEqual(pState3.state, ProcessState.STOPPED);
assert.strictEqual(pState3.isStopped, true);

// Case 6D: Missing PID without exit code evidence -> MUST BE UNKNOWN, NEVER STOPPED!
const pState4 = oracle.evaluateProcessState({ pid: 12345, hasActivePid: false, exitCode: null });
assert.strictEqual(pState4.state, ProcessState.UNKNOWN);
assert.strictEqual(pState4.isStopped, false);
assert.ok(pState4.reason.includes('UNKNOWN != STOPPED'));

// Case 6E: Query error / timeout -> strictly UNKNOWN
const pState5 = oracle.evaluateProcessState({ pid: 12345, queryError: 'RPC_TIMEOUT' });
assert.strictEqual(pState5.state, ProcessState.UNKNOWN);
assert.strictEqual(pState5.isStopped, false);
console.log('✓ PASS [Test 6]: Exact process state machine verified; UNKNOWN != STOPPED enforced.');

// --- TEST 7: Durable State Format & Safe Atomic Write ---
console.log('\n[TEST 7] Verifying Durable State Format & Safe Atomic Write...');
assert.strictEqual(oracle.validateIso8601UtcTimestamp('2026-09-11T13:45:00.000Z'), true);
assert.strictEqual(oracle.validateIso8601UtcTimestamp('2026-09-11 13:45:00'), false);
assert.strictEqual(oracle.validateIso8601UtcTimestamp('invalid-date'), false);

const testTarget = path.join(__dirname, 'scratch_test_atomic_write.json');
const testContent = JSON.stringify({ test: 'durable', timestamp: new Date().toISOString() });
const writeRes = oracle.safeAtomicWrite(testTarget, testContent);
assert.strictEqual(writeRes.success, true);
assert.strictEqual(fs.existsSync(testTarget), true);
assert.strictEqual(fs.readFileSync(testTarget, 'utf8'), testContent);
fs.unlinkSync(testTarget); // clean up
console.log('✓ PASS [Test 7]: ISO 8601 format validated and atomic write verified.');

console.log('\n======================================================================');
console.log(' ALL 7 WINDOWS VALIDATION ORACLE TEST SUITES PASSED (100% GREEN)');
console.log('======================================================================');
