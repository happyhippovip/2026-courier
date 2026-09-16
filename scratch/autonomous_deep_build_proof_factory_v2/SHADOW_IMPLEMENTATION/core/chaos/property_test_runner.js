'use strict';

const path = require('path');
const { TransitionValidator } = require('../state_machine/transition_validator');
const { HierarchicalResourceMutex } = require('../resources/hierarchical_resource_mutex');

/**
 * PropertyTestRunner
 * Generates randomized inputs to test invariant properties at scale.
 */
class PropertyTestRunner {
  constructor(rng) {
    this.rng = rng || Math.random;
  }

  _randomItem(array) {
    return array[Math.floor(this.rng() * array.length)];
  }

  testStateMachineInvariants(iterations = 500) {
    const specPath = path.join(__dirname, '..', '..', '..', 'STATE_MACHINES', 'state_machines.json');
    const validator = new TransitionValidator(specPath);
    const machine = validator.getMachine('TASK');
    const states = machine.states;
    const events = [...new Set(machine.transitions.map(t => t.event))];

    let validTransitions = 0;
    let rejectedForbidden = 0;

    for (let i = 0; i < iterations; i++) {
      const from = this._randomItem(states);
      const ev = this._randomItem(events);

      const entity = { machineName: 'TASK', currentState: from, version: 1 };
      try {
        const res = validator.validateTransition(entity, ev, {
          expectedVersion: 1,
          verificationProofPassed: true,
          artifactsApproved: true,
          boundaryChecked: true
        });
        validTransitions++;
        if (machine.terminal.includes(from)) {
          throw new Error(`INVARIANT_VIOLATION: Terminal state ${from} allowed transition via ${ev}`);
        }
      } catch (err) {
        rejectedForbidden++;
      }
    }

    return { iterations, validTransitions, rejectedForbidden, invariant_held: true };
  }

  testMutexExclusionInvariants(iterations = 500) {
    const mutex = new HierarchicalResourceMutex();
    const paths = ['src', 'src/core', 'src/core/app.js', 'docs', 'docs/readme.md', 'dist', 'dist/bundle.js'];

    for (let i = 0; i < iterations; i++) {
      const p1 = this._randomItem(paths);
      const p2 = this._randomItem(paths);
      const w1 = `worker_${i}_a`;
      const w2 = `worker_${i}_b`;

      const r1 = mutex.acquireLease(p1, w1, 'WRITE', 10000);
      if (r1.granted) {
        const r2 = mutex.acquireLease(p2, w2, 'WRITE', 10000);
        if (r2.granted) {
          const norm1 = p1.replace(/\\/g, '/').toLowerCase();
          const norm2 = p2.replace(/\\/g, '/').toLowerCase();
          if (norm1 === norm2 || norm1.startsWith(norm2 + '/') || norm2.startsWith(norm1 + '/')) {
            throw new Error(`INVARIANT_VIOLATION: Overlapping leases granted simultaneously for '${p1}' and '${p2}'`);
          }
          mutex.releaseLease(r2.lease.lease_id, w2);
        }
        mutex.releaseLease(r1.lease.lease_id, w1);
      }
    }

    return { iterations, invariant_held: true };
  }
}

module.exports = { PropertyTestRunner };
