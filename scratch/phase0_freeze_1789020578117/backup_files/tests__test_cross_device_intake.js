const assert = require('assert');
const { MessageClass, TaskStatus, ActionDomain, CrossDeviceIntakeEngine } = require('../cross_device_intake');

const engine = new CrossDeviceIntakeEngine();

console.log('Running Courier Cross-Device Intake Node.js Test Suite...');

// CASE 1
const c1 = engine.classifyAndRoute("Windows sagt GitHub login nötig.");
assert.strictEqual(c1.messageClass, MessageClass.HUMAN_GATE);
assert.strictEqual(c1.status, TaskStatus.BLOCKED);
assert.strictEqual(c1.erledigt, false);
assert.strictEqual(c1.actionDomain, ActionDomain.HUMAN_ONLY);
assert.ok(engine.formatTerminalOutput(c1).includes('ERLEDIGT: NEIN'));
console.log('PASS: CASE 1 (Human Gate)');

// CASE 2
const c2 = engine.classifyAndRoute("Windows sagt: ChatGPT soll das über den verbundenen GitHub machen.", { hasConnectedTool: true });
assert.strictEqual(c2.messageClass, MessageClass.DELEGATION_TO_CHIEF);
assert.strictEqual(c2.actionDomain, ActionDomain.CONNECTED_REMOTE);
assert.strictEqual(c2.requiresWorkerLaunch, true);
assert.strictEqual(c2.erledigt, false);
console.log('PASS: CASE 2 (Delegation to Chief)');

// CASE 3
const c3 = engine.classifyAndRoute("Tests 25/25 PASS, Datei remote verifiziert.");
assert.strictEqual(c3.messageClass, MessageClass.COMPLETED_RESULT);
assert.strictEqual(c3.status, TaskStatus.DONE);
assert.strictEqual(c3.erledigt, true);
assert.strictEqual(c3.blocker, 'NONE');
assert.ok(engine.formatTerminalOutput(c3).includes('ERLEDIGT: JA'));
console.log('PASS: CASE 3 (Verified Completion)');

// CASE 4
const c4 = engine.classifyAndRoute("Worker says success with no proof.");
assert.strictEqual(c4.erledigt, false);
assert.notStrictEqual(c4.status, TaskStatus.DONE);
assert.ok(engine.formatTerminalOutput(c4).includes('ERLEDIGT: NEIN'));
console.log('PASS: CASE 4 (Worker claim without evidence)');

// CASE 5
const c5 = engine.classifyAndRoute("Task still running.");
assert.strictEqual(c5.status, TaskStatus.RUNNING);
assert.strictEqual(c5.erledigt, false);
assert.strictEqual(c5.requiresWorkerLaunch, false);
assert.ok(engine.formatTerminalOutput(c5).includes('ERLEDIGT: NEIN'));
console.log('PASS: CASE 5 (Task running, no duplicate worker)');

// CASE 6
const c6 = engine.classifyAndRoute("Blocked by OAuth.");
assert.strictEqual(c6.messageClass, MessageClass.HUMAN_GATE);
assert.strictEqual(c6.status, TaskStatus.BLOCKED);
assert.strictEqual(c6.erledigt, false);
assert.ok(engine.formatTerminalOutput(c6).includes('ERLEDIGT: NEIN'));
console.log('PASS: CASE 6 (Blocked by OAuth)');

// CASE 7
const c7 = engine.classifyAndRoute("weiter");
assert.strictEqual(c7.messageClass, MessageClass.TASK_REQUEST);
assert.strictEqual(c7.requiresWorkerLaunch, true);
assert.strictEqual(c7.actionDomain, ActionDomain.LOCAL_MACHINE);
assert.strictEqual(c7.erledigt, false);
assert.ok(c7.nextStep.includes('ONE next safe local action'));
console.log('PASS: CASE 7 (Continuation directive weiter)');

// CASE 8
const c8 = engine.classifyAndRoute("Partial success: 3 of 5 steps completed.");
assert.strictEqual(c8.status, TaskStatus.PARTIAL);
assert.strictEqual(c8.erledigt, false);
assert.ok(engine.formatTerminalOutput(c8).includes('ERLEDIGT: NEIN'));
console.log('PASS: CASE 8 (Partial success)');

console.log('ALL 8 CROSS-DEVICE INTAKE TESTS PASSED SUCCESSFULLY (8/8)!');
