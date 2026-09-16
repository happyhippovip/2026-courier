// Border Guard Admissibility Choke Point
const path = require('path');
const { TaskPassport } = require('./TaskPassport');
const { CapabilityEngine, CAPABILITY_LATTICE } = require('./CapabilityEngine');

class BorderGuard {
  static inspect(task, passport, lockManager, currentSpendEur = 0) {
    // 1. Passport validity check
    const pv = TaskPassport.verifyPassport(passport);
    if (!pv.valid) {
      return { outcome: 'BLOCK', stage: 'PASSPORT_SIGNATURE', reason: pv.reason };
    }

    // 2. Version binding check
    const tVer = task.version || task.task_version; const pVer = passport.task_version || passport.version; if (task.task_id !== passport.task_id || tVer !== pVer) {
      return { outcome: 'HOLD', stage: 'VERSION_BINDING', reason: 'TASK_PASSPORT_VERSION_MISMATCH' };
    }

    // 3. Scope confinement check
    const taskPath = path.resolve(task.working_dir).toLowerCase().replace(/\\/g, '/');
    const withinScope = passport.scope_paths.some(sp => taskPath === sp || taskPath.startsWith(sp + '/'));
    if (!withinScope) {
      return { outcome: 'BLOCK', stage: 'SCOPE_CONFINEMENT', reason: 'OUT_OF_SCOPE_DIRECTORY' };
    }

    // 4. Capability check
    const capAuth = CapabilityEngine.authorize(task.required_capability || 'WORKSPACE_WRITE', CAPABILITY_LATTICE.WORKSPACE_WRITE);
    if (!capAuth.allowed) {
      if (capAuth.requires_human_gate) {
        return { outcome: 'ESCALATE', stage: 'HUMAN_GATE', reason: capAuth.reason };
      }
      return { outcome: 'BLOCK', stage: 'CAPABILITY_CEILING', reason: capAuth.reason };
    }

    // 5. Spend ceiling check (€0)
    if (task.cost_eur && task.cost_eur > 0) {
      return { outcome: 'ESCALATE', stage: 'SPEND_CEILING', reason: 'NON_ZERO_COST_REQUIRES_HUMAN_GATE' };
    }

    // 6. Resource Lock check
    const lockCheck = lockManager.canAcquire(task.working_dir, task.task_id);
    if (!lockCheck.available) {
      return { outcome: 'HOLD', stage: 'RESOURCE_LOCK_CONTENTION', reason: 'RESOURCE_LOCKED_BY_' + lockCheck.conflicting_task_id };
    }

    return { outcome: 'GREEN_CARD', stage: 'ALL_CHECKS_PASSED' };
  }
}

module.exports = { BorderGuard };
