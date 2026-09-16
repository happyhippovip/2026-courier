// Red-Team Simulator Engine
// Mission: WINDOWS_FINAL_INTEGRATION_REDTEAM_PACK_V1

const path = require('path');
const crypto = require('crypto');

class SimulatedDispatcher {
  constructor(config = {}) {
    this.enableFence = config.enableFence !== false;
    this.allowFallbackAroundFence = config.allowFallbackAroundFence === true;
    this.taskStore = new Map();
  }

  setTask(task) {
    this.taskStore.set(task.id, task);
  }

  dispatch(taskId, caller = 'ROUTER', isFallback = false) {
    const task = this.taskStore.get(taskId);
    if (!task) throw new Error(`Task ${taskId} not found`);

    if (this.enableFence) {
      if (this.allowFallbackAroundFence && isFallback) {
        // MUTANT: Fallback bypasses fence!
      } else {
        // Sound invariant check
        if (task.state === 'EXECUTION_UNCERTAIN' || task.execution_uncertain === true || task.side_effect_uncertainty === true) {
          return {
            dispatched: false,
            worker_allocated: false,
            status: 'HOLD_UNCERTAIN',
            reason: `[FENCE_BLOCKED] Task ${taskId} is under execution uncertainty. Caller ${caller} rejected.`
          };
        }

        // Transitive dependency check
        if (Array.isArray(task.dependencies)) {
          for (const depId of task.dependencies) {
            const dep = this.taskStore.get(depId);
            if (dep && (dep.state === 'EXECUTION_UNCERTAIN' || dep.execution_uncertain === true)) {
              return {
                dispatched: false,
                worker_allocated: false,
                status: 'HOLD_UNCERTAIN',
                reason: `[TRANSITIVE_FENCE_BLOCKED] Dependency ${depId} is EXECUTION_UNCERTAIN.`
              };
            }
          }
        }
      }
    }

    // If fence disabled or bypassed
    return {
      dispatched: true,
      worker_allocated: true,
      status: 'DISPATCHED_TO_WORKER',
      caller
    };
  }
}

class SimulatedResourceLockManager {
  constructor(config = {}) {
    this.disableParentChildCheck = config.disableParentChildCheck === true;
    this.disableSemanticLock = config.disableSemanticLock === true;
    this.universalCaseSensitive = config.universalCaseSensitive === true;
    this.activeLocks = new Map();
  }

  canonicalize(uri) {
    const colonIdx = uri.indexOf(':');
    const scheme = colonIdx > -1 ? uri.slice(0, colonIdx).toLowerCase() : 'tree';
    let val = colonIdx > -1 ? uri.slice(colonIdx + 1) : uri;

    if (scheme === 'tree' || scheme === 'file') {
      val = path.normalize(val).replace(/\\/g, '/');
      if (scheme === 'tree' && !val.endsWith('/')) val += '/';
      if (!this.universalCaseSensitive) {
        val = val.toLowerCase();
      }
      return `${scheme}:${val}`;
    }

    if (this.disableSemanticLock) {
      // MUTANT: omits locking on non-filesystem semantic resources!
      return null;
    }

    return `${scheme}:${val.trim().toLowerCase()}`;
  }

  checkConflict(resA, resB) {
    if (!resA || !resB) return false;
    if (resA === resB) return true;

    const [schemeA, pathA] = [resA.slice(0, resA.indexOf(':')), resA.slice(resA.indexOf(':') + 1)];
    const [schemeB, pathB] = [resB.slice(0, resB.indexOf(':')), resB.slice(resB.indexOf(':') + 1)];

    if (schemeA !== schemeB) {
      if (this.disableParentChildCheck) return false; // MUTANT
      if (schemeA === 'file' && schemeB === 'tree') return pathA.startsWith(pathB);
      if (schemeA === 'tree' && schemeB === 'file') return pathB.startsWith(pathA);
      return false;
    }

    if (schemeA === 'tree') {
      if (this.disableParentChildCheck) return pathA === pathB; // MUTANT: exact match only
      return pathA.startsWith(pathB) || pathB.startsWith(pathA);
    }

    if (schemeA === 'file' || schemeA === 'port' || schemeA === 'db' || schemeA === 'gitref') {
      return pathA === pathB;
    }

    return false;
  }

  acquire(taskId, leaseId, resources) {
    const canonical = resources.map(r => this.canonicalize(r)).filter(Boolean);

    if (this.disableSemanticLock && canonical.length === 0) {
      // MUTANT: semantic locks completely omitted, always grants!
      return { acquired: true, granted: [] };
    }

    for (const res of canonical) {
      for (const [activeRes, lock] of this.activeLocks.entries()) {
        if (lock.taskId === taskId) continue;
        if (this.checkConflict(res, activeRes)) {
          return {
            acquired: false,
            conflicting_resource: activeRes,
            conflicting_task_id: lock.taskId,
            reason: `Resource conflict between ${res} and ${activeRes}`
          };
        }
      }
    }

    for (const res of canonical) {
      this.activeLocks.set(res, { taskId, leaseId });
    }

    return { acquired: true, granted: canonical };
  }

  release(leaseId) {
    for (const [res, lock] of this.activeLocks.entries()) {
      if (lock.leaseId === leaseId) {
        this.activeLocks.delete(res);
      }
    }
  }
}

class SimulatedSafetyGate {
  constructor(config = {}) {
    this.allowDeferredZeroEuro = config.allowDeferredZeroEuro === true;
    this.trustNlpAlone = config.trustNlpAlone === true;
    this.allowNonceReuse = config.allowNonceReuse === true;
    this.ignoreTaskVersion = config.ignoreTaskVersion === true;
    this.consumedNonces = new Set();
  }

  evaluate({ prompt = '', operation = '', toolName = '', toolArgs = {}, token = null, expectedTask = null }) {
    const text = `${prompt} ${operation} ${JSON.stringify(toolArgs)}`.toLowerCase();

    // 1. Tool capability check
    const isFinancialTool = ['stripe_charge', 'checkout_api', 'subscribe_tier', 'cloud_billing_enable'].includes(toolName);
    
    // 2. Analysis qualifiers
    const isAnalysis = /\b(analyze|analysis|compare|draft|simulate|paper\s+trade|research|do\s+not\s+(?:charge|buy|subscribe|deploy))\b/i.test(prompt);

    if (this.trustNlpAlone) {
      // MUTANT: If NLP thinks it's analysis, it completely skips tool capability gate!
      if (isAnalysis) {
        return { requires_human_gate: false, executed: true, category: 'HARMLESS_ANALYSIS' };
      }
    } else {
      if (isFinancialTool) {
        // Hard capability barrier: must verify token even if prompt contains analysis words!
        return this._verifyToken(token, expectedTask, 'FINANCIAL_TOOL_CAPABILITY');
      }
    }

    // 3. Deferred liability patterns
    const hasDeferredPattern = /\b(auto[\s-]?renew|free\s+trial|recurring|billing\s+agreement|subscription|monthly\s+charge|annual\s+charge)\b/i.test(text);

    if (hasDeferredPattern) {
      if (this.allowDeferredZeroEuro && toolArgs.amount === 0) {
        // MUTANT: allows €0 deferred commitment!
        return { requires_human_gate: false, executed: true };
      }
      return this._verifyToken(token, expectedTask, 'DEFERRED_FINANCIAL_LIABILITY');
    }

    if (isAnalysis && !isFinancialTool) {
      return { requires_human_gate: false, executed: true, category: 'HARMLESS_ANALYSIS' };
    }

    // 4. Default spend check
    if (toolArgs.amount > 0 || ['payment', 'subscription', 'purchase'].includes(operation)) {
      return this._verifyToken(token, expectedTask, 'EXPLICIT_SPEND');
    }

    return { requires_human_gate: false, executed: true };
  }

  _verifyToken(token, expectedTask, category) {
    if (!token) {
      return { requires_human_gate: true, executed: false, category, reason: 'Human approval required' };
    }

    if (!this.allowNonceReuse && this.consumedNonces.has(token.nonce)) {
      return { requires_human_gate: true, executed: false, category, reason: 'Token nonce already consumed' };
    }

    if (new Date(token.expires_at).getTime() < Date.now()) {
      return { requires_human_gate: true, executed: false, category, reason: 'Token expired' };
    }

    if (!this.ignoreTaskVersion && expectedTask) {
      if (token.task_id !== expectedTask.id || token.task_version !== expectedTask.version) {
        return { requires_human_gate: true, executed: false, category, reason: 'Task version mismatch' };
      }
    }

    this.consumedNonces.add(token.nonce);
    return { requires_human_gate: true, approved_with_token: true, executed: true, category };
  }
}

class SimulatedReconciler {
  constructor(config = {}) {
    this.pidOnlyMatch = config.pidOnlyMatch === true;
    this.unknownToMatch = config.unknownToMatch === true;
    this.unknownToKill = config.unknownToKill === true;
  }

  inspectProcess(lease, currentProcess) {
    if (!lease || !currentProcess) {
      return { status: 'DEFINITE_MISMATCH', can_kill: false, assume_alive: false };
    }

    if (this.pidOnlyMatch) {
      // MUTANT: checks only PID!
      const isAlive = lease.pid === currentProcess.pid;
      return {
        status: isAlive ? 'MATCH_CONFIRMED' : 'DEFINITE_MISMATCH',
        can_kill: isAlive,
        assume_alive: isAlive
      };
    }

    if (currentProcess.inspection_error === 'EPERM' || lease.process_start_time_epoch_ms === undefined) {
      if (this.unknownToMatch) {
        return { status: 'MATCH_CONFIRMED', can_kill: true, assume_alive: true }; // MUTANT
      }
      if (this.unknownToKill) {
        return { status: 'UNKNOWN', can_kill: true, assume_alive: false }; // MUTANT
      }
      return { status: 'UNKNOWN', can_kill: false, assume_alive: false, reason: 'Metadata missing or EPERM' };
    }

    if (lease.pid !== currentProcess.pid) {
      return { status: 'DEFINITE_MISMATCH', can_kill: false, assume_alive: false };
    }

    const delta = Math.abs(lease.process_start_time_epoch_ms - currentProcess.start_time_epoch_ms);
    if (delta > 1000) {
      return { status: 'DEFINITE_MISMATCH', can_kill: false, assume_alive: false, reason: 'PID recycled' };
    }

    if (lease.task_token && currentProcess.env_task_token && lease.task_token !== currentProcess.env_task_token) {
      return { status: 'DEFINITE_MISMATCH', can_kill: false, assume_alive: false, reason: 'Token mismatch' };
    }

    return { status: 'MATCH_CONFIRMED', can_kill: true, assume_alive: true };
  }
}

module.exports = {
  SimulatedDispatcher,
  SimulatedResourceLockManager,
  SimulatedSafetyGate,
  SimulatedReconciler
};
