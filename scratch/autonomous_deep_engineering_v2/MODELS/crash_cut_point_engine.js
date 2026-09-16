/**
 * CRASH CUT-POINT EXPLORER ENGINE (V2 LAB)
 * 
 * Simulates 22 distinct micro-boundaries in the Courier task execution pipeline.
 * Evaluates post-crash durable state reconstruction and safe next action.
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const CUT_POINTS = [
  'before_task_stamp',
  'after_stamp_persistence',
  'before_worker_lease',
  'after_worker_lease',
  'before_dispatch_intent',
  'after_dispatch_intent',
  'before_worker_ack',
  'after_worker_ack',
  'during_worker_execution',
  'after_output_creation',
  'before_result_envelope',
  'after_result_envelope',
  'before_result_persistence',
  'after_result_persistence',
  'before_verification',
  'during_verification',
  'after_verification',
  'before_terminal_transition',
  'after_terminal_transition',
  'before_cleanup',
  'during_cleanup',
  'after_cleanup'
];

class CrashCutPointEngine {
  constructor(storageDir) {
    this.storageDir = storageDir;
    if (!fs.existsSync(storageDir)) fs.mkdirSync(storageDir, { recursive: true });
    this.stateFile = path.join(storageDir, 'durable_state.json');
    this.auditFile = path.join(storageDir, 'audit_ledger.jsonl');
    this.outputFile = path.join(storageDir, 'task_output.txt');
  }

  _persistState(state) {
    fs.writeFileSync(this.stateFile, JSON.stringify(state, null, 2), 'utf8');
  }

  _logEvent(event, data) {
    fs.appendFileSync(this.auditFile, JSON.stringify({ timestamp: new Date().toISOString(), event, data }) + '\n', 'utf8');
  }

  /**
   * Executes the full pipeline up to cutPoint. If cutPoint matches, throws/halts to simulate crash.
   */
  runPipelineWithCutPoint(taskId, cutPoint) {
    if (!CUT_POINTS.includes(cutPoint)) {
      throw new Error(`[CUTPOINT_ERROR] Unknown cut-point: ${cutPoint}`);
    }

    const state = {
      task_id: taskId,
      phase: 'INIT',
      stamped: false,
      lease_acquired: false,
      dispatched: false,
      worker_acked: false,
      output_created: false,
      result_persisted: false,
      verified: false,
      terminal: false,
      cleaned_up: false
    };
    this._persistState(state);

    if (cutPoint === 'before_task_stamp') throw new Error('SIMULATED_CRASH:before_task_stamp');
    state.phase = 'STAMPED';
    state.stamped = true;
    this._persistState(state);
    this._logEvent('TASK_STAMPED', { taskId });

    if (cutPoint === 'after_stamp_persistence') throw new Error('SIMULATED_CRASH:after_stamp_persistence');

    if (cutPoint === 'before_worker_lease') throw new Error('SIMULATED_CRASH:before_worker_lease');
    state.lease_acquired = true;
    state.phase = 'LEASE_ACQUIRED';
    this._persistState(state);
    this._logEvent('LEASE_ACQUIRED', { taskId });

    if (cutPoint === 'after_worker_lease') throw new Error('SIMULATED_CRASH:after_worker_lease');

    if (cutPoint === 'before_dispatch_intent') throw new Error('SIMULATED_CRASH:before_dispatch_intent');
    state.dispatched = true;
    state.phase = 'DISPATCHED';
    this._persistState(state);
    this._logEvent('DISPATCH_INTENT', { taskId });

    if (cutPoint === 'after_dispatch_intent') throw new Error('SIMULATED_CRASH:after_dispatch_intent');

    if (cutPoint === 'before_worker_ack') throw new Error('SIMULATED_CRASH:before_worker_ack');
    state.worker_acked = true;
    state.phase = 'ACKED';
    this._persistState(state);
    this._logEvent('WORKER_ACKNOWLEDGED', { taskId });

    if (cutPoint === 'after_worker_ack') throw new Error('SIMULATED_CRASH:after_worker_ack');

    if (cutPoint === 'during_worker_execution') throw new Error('SIMULATED_CRASH:during_worker_execution');

    // Simulate worker output creation on disk
    fs.writeFileSync(this.outputFile, `Output content for ${taskId}`, 'utf8');
    state.output_created = true;
    state.phase = 'OUTPUT_CREATED';
    this._persistState(state);
    this._logEvent('OUTPUT_WRITTEN', { taskId });

    if (cutPoint === 'after_output_creation') throw new Error('SIMULATED_CRASH:after_output_creation');

    if (cutPoint === 'before_result_envelope') throw new Error('SIMULATED_CRASH:before_result_envelope');
    const resultEnvelope = {
      task_id: taskId,
      status: 'SUCCESS',
      output_hash: crypto.createHash('sha256').update(fs.readFileSync(this.outputFile)).digest('hex')
    };
    state.phase = 'ENVELOPE_BUILT';

    if (cutPoint === 'after_result_envelope') throw new Error('SIMULATED_CRASH:after_result_envelope');

    if (cutPoint === 'before_result_persistence') throw new Error('SIMULATED_CRASH:before_result_persistence');
    state.result_persisted = true;
    state.result_envelope = resultEnvelope;
    state.phase = 'RESULT_PERSISTED';
    this._persistState(state);
    this._logEvent('RESULT_PERSISTED', { taskId, hash: resultEnvelope.output_hash });

    if (cutPoint === 'after_result_persistence') throw new Error('SIMULATED_CRASH:after_result_persistence');

    if (cutPoint === 'before_verification') throw new Error('SIMULATED_CRASH:before_verification');
    if (cutPoint === 'during_verification') throw new Error('SIMULATED_CRASH:during_verification');
    state.verified = true;
    state.phase = 'VERIFIED';
    this._persistState(state);
    this._logEvent('VERIFICATION_COMPLETE', { taskId });

    if (cutPoint === 'after_verification') throw new Error('SIMULATED_CRASH:after_verification');

    if (cutPoint === 'before_terminal_transition') throw new Error('SIMULATED_CRASH:before_terminal_transition');
    state.terminal = true;
    state.phase = 'CLOSED';
    this._persistState(state);
    this._logEvent('TASK_CLOSED', { taskId });

    if (cutPoint === 'after_terminal_transition') throw new Error('SIMULATED_CRASH:after_terminal_transition');

    if (cutPoint === 'before_cleanup') throw new Error('SIMULATED_CRASH:before_cleanup');
    if (cutPoint === 'during_cleanup') throw new Error('SIMULATED_CRASH:during_cleanup');
    state.cleaned_up = true;
    state.phase = 'CLEANED_UP';
    this._persistState(state);
    this._logEvent('CLEANUP_COMPLETE', { taskId });

    if (cutPoint === 'after_cleanup') throw new Error('SIMULATED_CRASH:after_cleanup');

    return state;
  }

  /**
   * Reconstructs durable state after crash and determines the safe next action.
   */
  reconstructAndAnalyze(taskId) {
    if (!fs.existsSync(this.stateFile)) {
      return {
        state_classification: 'NOT_STARTED',
        safe_action: 'SAFE_TO_START',
        reason: 'Zero durable state found on disk'
      };
    }

    const state = JSON.parse(fs.readFileSync(this.stateFile, 'utf8'));
    const outputExists = fs.existsSync(this.outputFile);

    // Terminal or cleanup phases
    if (state.cleaned_up || state.terminal) {
      return {
        state_classification: 'VERIFIED',
        safe_action: 'NO_ACTION_REQUIRED_TASK_TERMINAL',
        reason: 'Task reached verified terminal state prior to interruption'
      };
    }

    // Verified but not terminal
    if (state.verified) {
      return {
        state_classification: 'VERIFIED',
        safe_action: 'COMPLETE_TERMINAL_TRANSITION',
        reason: 'Task verification passed; proceed directly to close without re-executing'
      };
    }

    // Result persisted but not verified
    if (state.result_persisted) {
      return {
        state_classification: 'RESULT_PERSISTED',
        safe_action: 'PROCEED_TO_INDEPENDENT_VERIFICATION',
        reason: 'Worker result persisted; do NOT re-execute; perform independent verification'
      };
    }

    // Worker was dispatched or output exists without valid result envelope -> UNCERTAIN
    if (state.dispatched || state.worker_acked || outputExists) {
      return {
        state_classification: 'EXECUTION_UNCERTAIN',
        safe_action: 'BLOCK_REDISPATCH_REQUIRE_COORDINATOR_RECONCILIATION',
        reason: 'Execution was in-flight or side-effects may exist without durable result confirmation. Blind retry forbidden.'
      };
    }

    // Stamped or lease acquired prior to dispatch intent
    if (state.stamped || state.lease_acquired) {
      return {
        state_classification: 'STARTED_NO_EXTERNAL_EFFECT',
        safe_action: 'PROCEED_DISPATCH_OR_RELEASE_LEASE',
        reason: 'No dispatch intent was committed and no external effect exists'
      };
    }

    return {
      state_classification: 'NOT_STARTED',
      safe_action: 'SAFE_TO_START',
      reason: 'Task was in initial uncommitted state'
    };
  }
}

module.exports = {
  CUT_POINTS,
  CrashCutPointEngine
};
