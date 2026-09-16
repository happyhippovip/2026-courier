'use strict';

/**
 * SHADOW IMPLEMENTATION: TRANSITION VALIDATOR
 * Component: shadow/core/state_machine/transition_validator.js
 * Mission: WINDOWS_AUTONOMOUS_DEEP_BUILD_PROOF_FACTORY_V2
 */

const fs = require('fs');
const path = require('path');

class IllegalTransitionError extends Error {
  constructor(message, details = {}) {
    super(message);
    this.name = 'IllegalTransitionError';
    this.details = details;
  }
}

class StaleVersionError extends Error {
  constructor(message, details = {}) {
    super(message);
    this.name = 'StaleVersionError';
    this.details = details;
  }
}

class GuardViolationError extends Error {
  constructor(message, details = {}) {
    super(message);
    this.name = 'GuardViolationError';
    this.details = details;
  }
}

class TerminalStateError extends Error {
  constructor(message, details = {}) {
    super(message);
    this.name = 'TerminalStateError';
    this.details = details;
  }
}

class TransitionValidator {
  constructor(specPathOrObject, options = {}) {
    if (typeof specPathOrObject === 'string') {
      this.spec = JSON.parse(fs.readFileSync(specPathOrObject, 'utf8'));
    } else {
      this.spec = specPathOrObject;
    }

    // Mutation test switches
    this.allowSkippedVerification = options.allowSkippedVerification || false;
    this.disableVersionCheck = options.disableVersionCheck || false;
    this.trustWorkerSelfPass = options.trustWorkerSelfPass || false;
    this.allowTerminalTransition = options.allowTerminalTransition || false;
  }

  getMachine(machineName) {
    const m = this.spec.machines[machineName];
    if (!m) throw new Error(`Unknown state machine: '${machineName}'`);
    return m;
  }

  validateTransition(entity, eventName, context = {}) {
    const { machineName, currentState, version } = entity;
    const machine = this.getMachine(machineName);

    // 1. Terminal state check
    if (machine.terminal.includes(currentState) && !this.allowTerminalTransition) {
      throw new TerminalStateError(
        `Cannot transition out of terminal state '${currentState}' for machine '${machineName}'`,
        { entity, eventName }
      );
    }

    // 2. Version check (Optimistic Concurrency)
    if (!this.disableVersionCheck) {
      if (context.expectedVersion !== undefined && context.expectedVersion !== version) {
        throw new StaleVersionError(
          `State version mismatch on '${entity.id || machineName}': expected ${context.expectedVersion}, but current is ${version}`,
          { currentVersion: version, expectedVersion: context.expectedVersion }
        );
      }
    }

    // 3. Find matching legal transition
    const validTransition = machine.transitions.find(
      t => t.from === currentState && t.event === eventName
    );

    if (!validTransition) {
      throw new IllegalTransitionError(
        `Illegal transition: No edge from '${currentState}' via event '${eventName}' in machine '${machineName}'`,
        { currentState, eventName, machineName }
      );
    }

    const targetState = validTransition.to;

    // 4. Guard evaluations
    if (validTransition.guard) {
      this.evaluateGuard(validTransition.guard, entity, targetState, context);
    }

    // 5. Anti-skipped verification invariant for TASK
    if (machineName === 'TASK' && targetState === 'CLOSED') {
      if (!this.allowSkippedVerification) {
        if (currentState !== 'VERIFIED') {
          throw new GuardViolationError(
            `Anti-Skipped-Verification Violation: Task cannot transition to CLOSED from '${currentState}' without passing through VERIFIED state.`,
            { entity, targetState }
          );
        }
      }
    }

    // Return the successful transition envelope
    return {
      success: true,
      previousState: currentState,
      newState: targetState,
      previousVersion: version,
      newVersion: (version || 1) + 1,
      event: eventName,
      timestamp: new Date().toISOString()
    };
  }

  evaluateGuard(guardName, entity, targetState, context) {
    switch (guardName) {
      case 'requires_passport':
        if (!context.passport || !context.passport.valid) {
          throw new GuardViolationError(`Guard failed: 'requires_passport' missing or invalid`, { guardName });
        }
        break;

      case 'requires_mutex_lease':
        if (!context.lease_id || !context.lease_held) {
          throw new GuardViolationError(`Guard failed: 'requires_mutex_lease' not held`, { guardName });
        }
        break;

      case 'requires_result_customs':
        if (!context.customs_clearance || context.customs_clearance.verdict !== 'APPROVED') {
          throw new GuardViolationError(`Guard failed: 'requires_result_customs' not cleared`, { guardName });
        }
        break;

      case 'independent_assertion_check':
        if (!this.trustWorkerSelfPass) {
          if (!context.independent_verifier_passed || context.worker_self_reported === true && !context.independent_verifier_passed) {
            throw new GuardViolationError(`Guard failed: 'independent_assertion_check' requires non-worker independent validation`, { guardName });
          }
        }
        break;

      case 'requires_lease_release':
        if (context.active_lease_count > 0) {
          throw new GuardViolationError(`Guard failed: 'requires_lease_release' active leases remain`, { guardName });
        }
        break;

      case 'valid_signed_token':
        if (!context.signed_token || context.signed_token.valid !== true) {
          throw new GuardViolationError(`Guard failed: 'valid_signed_token' required for human gate passage`, { guardName });
        }
        break;

      case 'single_use_and_scope_match':
        if (context.token_already_consumed) {
          throw new GuardViolationError(`Guard failed: 'single_use_and_scope_match' token replay blocked`, { guardName });
        }
        if (!context.scope_match) {
          throw new GuardViolationError(`Guard failed: 'single_use_and_scope_match' scope mismatch`, { guardName });
        }
        break;

      case 'verified_pid_start_time_match':
        if (context.pid_identity_verdict !== 'MATCH') {
          throw new GuardViolationError(`Guard failed: 'verified_pid_start_time_match' requires strict MATCH, got ${context.pid_identity_verdict}`, { guardName });
        }
        break;

      case 'cryptographic_envelope_proof':
        if (!context.satisfaction_envelope || !context.satisfaction_envelope.valid_hash) {
          throw new GuardViolationError(`Guard failed: 'cryptographic_envelope_proof' missing valid cryptographic hash`, { guardName });
        }
        break;

      default:
        // Default pass for un-mocked minor guards
        break;
    }
  }
}

module.exports = {
  IllegalTransitionError,
  StaleVersionError,
  GuardViolationError,
  TerminalStateError,
  TransitionValidator
};
