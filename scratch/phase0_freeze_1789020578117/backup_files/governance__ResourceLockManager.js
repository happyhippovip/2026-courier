// Hierarchical NTFS Resource Mutex with Case Folding & Prefix Containment
const path = require('path');

class ResourceLockManager {
  constructor() {
    this.locks = new Map(); // normalizedPath -> { taskId, mode, acquiredAt }
  }

  static norm(p) {
    return path.resolve(p).toLowerCase().replace(/\\/g, '/');
  }

  canAcquire(resourcePath, taskId) {
    const target = ResourceLockManager.norm(resourcePath);
    for (const [held, lock] of this.locks.entries()) {
      if (lock.taskId === taskId) continue; // Reentrant for same task
      const overlap = target === held || target.startsWith(held + '/') || held.startsWith(target + '/');
      if (overlap) {
        return { available: false, conflicting_task_id: lock.taskId, conflicting_path: held };
      }
    }
    return { available: true };
  }

  acquire(resourcePath, taskId, mode = 'EXCL') {
    const check = this.canAcquire(resourcePath, taskId);
    if (!check.available) {
      return { acquired: false, conflicting_task_id: check.conflicting_task_id, conflicting_path: check.conflicting_path };
    }
    const target = ResourceLockManager.norm(resourcePath);
    this.locks.set(target, { taskId, mode, acquiredAt: new Date().toISOString() });
    return { acquired: true, resource: target };
  }

  release(resourcePath, taskId) {
    const target = ResourceLockManager.norm(resourcePath);
    const lock = this.locks.get(target);
    if (lock && lock.taskId === taskId) {
      this.locks.delete(target);
      return true;
    }
    return false;
  }

  releaseAllForTask(taskId) {
    let count = 0;
    for (const [k, lock] of this.locks.entries()) {
      if (lock.taskId === taskId) {
        this.locks.delete(k);
        count++;
      }
    }
    return count;
  }

  activeLocks() {
    return Array.from(this.locks.entries()).map(([k, v]) => ({ resource: k, ...v }));
  }
}

module.exports = { ResourceLockManager };
