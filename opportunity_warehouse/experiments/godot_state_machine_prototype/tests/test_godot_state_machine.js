const assert = require('assert');
const { GodotStateMachineGenerator } = require('../lib/state_machine_generator');

console.log('--- TEST 1: Default Player HFSM Generation ---');
const gdscript = GodotStateMachineGenerator.generateHFSM();
assert(gdscript.includes('class_name PlayerStateMachine'));
assert(gdscript.includes('enum State {'));
assert(gdscript.includes('IDLE = "Idle"'));
assert(gdscript.includes('change_state(new_state: State)'));
assert(gdscript.includes('state_changed.emit'));
console.log('PASS [Test 1]: Default Godot 4 HFSM code generated cleanly.');

console.log('--- TEST 2: Custom States and Transition Validation ---');
const customHFSM = GodotStateMachineGenerator.generateHFSM({
  className: 'BossStateMachine',
  initialState: 'Patrol',
  states: ['Patrol', 'Chase', 'Stunned', 'Enraged'],
  transitions: [
    { from: 'Patrol', to: 'Chase', trigger: 'player_in_sight()' },
    { from: 'Chase', to: 'Enraged', trigger: 'health < 30.0' },
    { from: 'Enraged', to: 'Stunned', trigger: 'parry_landed()' }
  ]
});
assert(customHFSM.includes('class_name BossStateMachine'));
assert(customHFSM.includes('PATROL = "Patrol"'));
assert(customHFSM.includes('ENRAGED = "Enraged"'));
assert(customHFSM.includes('health < 30.0'));
console.log('PASS [Test 2]: Custom states and conditional transitions integrated.');

console.log('--- TEST 3: Invalid Initial State Fail-Closed ---');
assert.throws(() => {
  GodotStateMachineGenerator.generateHFSM({
    initialState: 'NonExistentState',
    states: ['Idle', 'Walk']
  });
}, /GODOT_ERROR/, 'Initial state outside states list must throw');
console.log('PASS [Test 3]: Invalid initial state fails closed.');

console.log('\n>>> ALL 3 GODOT STATE MACHINE TESTS PASS (100% DETERMINISTIC) <<<');
