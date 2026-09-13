/**
 * work_stealing.js - Distributed Work Stealing & Lane Concurrency Governor
 * 
 * Invariants:
 * 1. Multi-Worker Non-Contention: Concurrent workers steal unclaimed work atomically without collisions.
 * 2. Strict Lane Concurrency: Max active workers per lane bounded (default 5) to prevent machine thrashing.
 * 3. Resource Lock Respect: Workers skip tasks whose conflict domains / paths are held by other workers.
 * 4. Automatic Abandoned Reclamation: Dead worker leases expire and return to PENDING status without data loss.
 * 5. €0 Autonomous Spend Strictly Maintained.
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { ResourceLockManager } = require('../governance/ResourceLockManager');

class WorkStealingPool {
  constructor(options = {}) {
    this.storageDir = options.storageDir || path.join(__dirname, '..', 'runtime', 'work_stealing');
    if (!fs.existsSync(this.storageDir)) {
      fs.mkdirSync(this.storageDir, { recursive: true });
    }
    this.queueFile = path.join(this.storageDir, 'queue.json');
    this.lockManager = options.lockManager || new ResourceLockManager();
    this.maxConcurrentPerLane = options.maxConcurrentPerLane || 5;
    this.claimTimeoutMs = options.claimTimeoutMs || 60000;

    this.tasks = new Map();
    this.workers = new Map(); // workerId -> { machineId, lane, lastHeartbeat, activeTaskId }
    this._load();
  }

  _load() {
    if (fs.existsSync(this.queueFile)) {
      try {
        const raw = JSON.parse(fs.readFileSync(this.queueFile, 'utf8'));
        if (Array.isArray(raw)) {
          for (const t of raw) {
            this.tasks.set(t.task_id, t);
          }
        }
      } catch (err) {
        console.error('[WORK_STEALING] Warning: failed to parse queue.json:', err.message);
      }
    }
  }

  _persist() {
    const list = Array.from(this.tasks.values());
    const tmp = `${this.queueFile}.tmp.${Date.now()}`;
    fs.writeFileSync(tmp, JSON.stringify(list, null, 2), 'utf8');
    fs.renameSync(tmp, this.queueFile);
  }

  enqueueTask(taskDef = {}) {
    if (!taskDef.task_id) {
      taskDef.task_id = `TASK-WS-${Date.now()}-${crypto.randomBytes(3).toString('hex').toUpperCase()}`;
    }

    const task = {
      task_id: taskDef.task_id,
      goal_id: taskDef.goal_id || 'GOAL-WORK-STEALING',
      title: taskDef.title || taskDef.task_id,
      priority: typeof taskDef.priority === 'number' ? taskDef.priority : 50,
      lane: taskDef.lane || 'WINDOWS_GOOGLE',
      conflict_domain: taskDef.conflict_domain || taskDef.task_id,
      resource_path: taskDef.resource_path || taskDef.scope_paths?.[0] || 'C:/Users/lol/2026-workspace',
      scope_paths: taskDef.scope_paths || ['C:/Users/lol/2026-workspace'],
      executable_command: taskDef.executable_command || taskDef.command || null,
      target_file: taskDef.target_file || null,
      working_dir: taskDef.working_dir || 'C:/Users/lol/2026-workspace',
      timeout_ms: taskDef.timeout_ms || 45000,
      required_capabilities: taskDef.required_capabilities || ['WORKSPACE_WRITE'],
      status: 'PENDING',
      created_at: new Date().toISOString(),
      claimed_by: null,
      claimed_at: null,
      claim_token: null,
      completed_at: null,
      abandoned_count: 0,
      result: null
    };

    this.tasks.set(task.task_id, task);
    this._persist();
    return task;
  }

  registerWorkerHeartbeat(workerId, machineId = 'WINDOWS_LOCAL', lane = 'WINDOWS_GOOGLE') {
    const w = this.workers.get(workerId) || { workerId, machineId, lane, activeTaskId: null };
    w.lastHeartbeat = Date.now();
    w.machineId = machineId;
    w.lane = lane;
    this.workers.set(workerId, w);
    return w;
  }

  releaseAbandonedClaims(timeoutMs = null) {
    const timeout = timeoutMs || this.claimTimeoutMs;
    const now = Date.now();
    let reclaimsCount = 0;

    for (const task of this.tasks.values()) {
      if (task.status === 'CLAIMED' && task.claimed_at) {
        const elapsed = now - new Date(task.claimed_at).getTime();
        if (elapsed > timeout) {
          // Release lock and reclaim
          this.lockManager.release(task.resource_path, task.task_id);
          task.status = 'PENDING';
          task.claimed_by = null;
          task.claimed_at = null;
          task.claim_token = null;
          task.abandoned_count = (task.abandoned_count || 0) + 1;
          reclaimsCount++;
        }
      }
    }

    if (reclaimsCount > 0) {
      this._persist();
    }
    return reclaimsCount;
  }

  getActiveLaneConcurrency(lane) {
    let count = 0;
    for (const task of this.tasks.values()) {
      if (task.status === 'CLAIMED' && task.lane === lane) {
        count++;
      }
    }
    return count;
  }

  stealTask({ workerId, machineId = 'WINDOWS_LOCAL', lane = 'WINDOWS_GOOGLE', capabilities = [] }) {
    if (!workerId) throw new Error('[WORK_STEALING] workerId is required to steal work');

    this.registerWorkerHeartbeat(workerId, machineId, lane);
    this.releaseAbandonedClaims();

    // 1. Check Lane Concurrency Limit
    const activeInLane = this.getActiveLaneConcurrency(lane);
    if (activeInLane >= this.maxConcurrentPerLane) {
      return {
        stolen: false,
        reason: 'LANE_CONCURRENCY_LIMIT_REACHED',
        active_in_lane: activeInLane,
        max_concurrent: this.maxConcurrentPerLane,
        lane
      };
    }

    // 2. Find eligible task sorted by priority DESC, created_at ASC
    const candidates = Array.from(this.tasks.values())
      .filter(t => t.status === 'PENDING')
      .sort((a, b) => (b.priority - a.priority) || (new Date(a.created_at) - new Date(b.created_at)));

    for (const task of candidates) {
      // Capability check
      if (task.required_capabilities && capabilities.length > 0) {
        const satisfied = task.required_capabilities.every(cap => capabilities.includes(cap));
        if (!satisfied) continue;
      }

      // Resource Lock Check (Conflict domain non-stacking)
      const lockCheck = this.lockManager.canAcquire(task.resource_path, task.task_id);
      if (!lockCheck.available) {
        // Resource locked by another worker on this or another machine; skip to next independent task
        continue;
      }

      // Acquire lock atomically
      const lockRes = this.lockManager.acquire(task.resource_path, task.task_id);
      if (!lockRes.acquired) {
        continue;
      }

      // Claim task
      const token = `TOKEN-${task.task_id}-${Date.now()}-${crypto.randomBytes(4).toString('hex').toUpperCase()}`;
      task.status = 'CLAIMED';
      task.claimed_by = workerId;
      task.claimed_at = new Date().toISOString();
      task.claim_token = token;

      const w = this.workers.get(workerId);
      if (w) w.activeTaskId = task.task_id;

      this._persist();

      return {
        stolen: true,
        task: { ...task },
        claim_token: token,
        active_in_lane: activeInLane + 1
      };
    }

    return {
      stolen: false,
      reason: 'NO_ELIGIBLE_WORK_AVAILABLE'
    };
  }

  completeTask({ taskId, claimToken, workerId, resultStatus = 'SUCCESS', artifacts = [], evidenceSha256 = null, error = null }) {
    const task = this.tasks.get(taskId);
    if (!task) {
      return { success: false, error: `Task ${taskId} not found` };
    }

    if (task.status !== 'CLAIMED') {
      return { success: false, error: `Task ${taskId} is not in CLAIMED state (current: ${task.status})` };
    }

    if (task.claimed_by !== workerId) {
      return { success: false, error: `Task claimed by ${task.claimed_by}, not ${workerId}` };
    }

    if (task.claim_token !== claimToken) {
      return { success: false, error: 'INVALID_CLAIM_TOKEN' };
    }

    // Release lock
    this.lockManager.release(task.resource_path, task.task_id);

    task.status = resultStatus === 'SUCCESS' ? 'COMPLETED' : 'FAILED';
    task.completed_at = new Date().toISOString();
    task.result = {
      result_status: resultStatus,
      artifacts,
      evidence_sha256: evidenceSha256,
      error
    };

    const w = this.workers.get(workerId);
    if (w) w.activeTaskId = null;

    this._persist();

    return {
      success: true,
      task_id: taskId,
      status: task.status,
      completed_at: task.completed_at
    };
  }

  getTelemetry() {
    const all = Array.from(this.tasks.values());
    const pending = all.filter(t => t.status === 'PENDING').length;
    const claimed = all.filter(t => t.status === 'CLAIMED').length;
    const completed = all.filter(t => t.status === 'COMPLETED').length;
    const failed = all.filter(t => t.status === 'FAILED').length;

    const laneMap = {};
    for (const t of all) {
      if (t.status === 'CLAIMED') {
        laneMap[t.lane] = (laneMap[t.lane] || 0) + 1;
      }
    }

    return {
      total_tasks: all.length,
      pending,
      claimed,
      completed,
      failed,
      active_lanes: laneMap,
      registered_workers: this.workers.size,
      max_concurrent_per_lane: this.maxConcurrentPerLane
    };
  }
}

module.exports = {
  WorkStealingPool
};
