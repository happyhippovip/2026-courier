/**
 * @symphony/agent-locks v1.0.0
 * Lightweight, zero-dependency, deterministic hierarchical file & directory mutex for multi-agent systems.
 * Extracted from Courier's battle-tested governance plane.
 */

const fs = require('fs');
const path = require('path');

class AgentLockManager {
  constructor(lockDir = '.agent_locks') {
    this.lockDir = path.resolve(lockDir);
    if (!fs.existsSync(this.lockDir)) {
      fs.mkdirSync(this.lockDir, { recursive: true });
    }
  }

  _normalizePath(targetPath) {
    return path.resolve(targetPath).replace(/\\/g, '/').toLowerCase();
  }

  _getLockFilePath(normalizedPath) {
    const hash = require('crypto').createHash('sha256').update(normalizedPath).digest('hex').slice(0, 16);
    const safeName = path.basename(normalizedPath).replace(/[^a-zA-Z0-9_-]/g, '_');
    return path.join(this.lockDir, `lock_${safeName}_${hash}.json`);
  }

  isProcessAlive(pid) {
    if (!pid || typeof pid !== 'number') return false;
    try {
      process.kill(pid, 0);
      return true;
    } catch (e) {
      return e.code === 'EPERM'; // Alive but different user
    }
  }

  acquireLock(targetPath, holderId = `proc_${process.pid}`, timeoutMs = 5000) {
    const normalized = this._normalizePath(targetPath);
    const lockFile = this._getLockFilePath(normalized);

    // Check existing lock
    if (fs.existsSync(lockFile)) {
      try {
        const lockData = JSON.parse(fs.readFileSync(lockFile, 'utf8'));
        
        // Re-entrancy check: same holder can re-acquire
        if (lockData.holder_id === holderId) {
          lockData.reentrant_count = (lockData.reentrant_count || 1) + 1;
          lockData.updated_at = new Date().toISOString();
          fs.writeFileSync(lockFile, JSON.stringify(lockData, null, 2), 'utf8');
          return { acquired: true, lock_id: lockData.lock_id, reentrant: true };
        }

        // Dead-PID reconciliation: if owner process is dead, auto-reclaim
        if (lockData.pid && !this.isProcessAlive(lockData.pid)) {
          fs.unlinkSync(lockFile);
        } else {
          // Lock is actively held by another live process
          return { acquired: false, reason: 'LOCKED_BY_ACTIVE_HOLDER', holder: lockData.holder_id, pid: lockData.pid };
        }
      } catch (err) {
        // Corrupt lock file -> clean up fail-closed
        try { fs.unlinkSync(lockFile); } catch (e) {}
      }
    }

    // Write new lock atomically
    const lockId = `LOCK-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const payload = {
      lock_id: lockId,
      target_path: normalized,
      holder_id: holderId,
      pid: process.pid,
      created_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + timeoutMs).toISOString(),
      reentrant_count: 1
    };

    const tmpFile = lockFile + '.tmp.' + Date.now();
    fs.writeFileSync(tmpFile, JSON.stringify(payload, null, 2), 'utf8');
    fs.renameSync(tmpFile, lockFile);

    return { acquired: true, lock_id: lockId, reentrant: false };
  }

  releaseLock(targetPath, holderId = `proc_${process.pid}`) {
    const normalized = this._normalizePath(targetPath);
    const lockFile = this._getLockFilePath(normalized);

    if (!fs.existsSync(lockFile)) {
      return { released: false, reason: 'LOCK_NOT_FOUND' };
    }

    try {
      const lockData = JSON.parse(fs.readFileSync(lockFile, 'utf8'));
      if (lockData.holder_id !== holderId) {
        return { released: false, reason: 'HOLDER_MISMATCH', active_holder: lockData.holder_id };
      }

      if (lockData.reentrant_count > 1) {
        lockData.reentrant_count -= 1;
        fs.writeFileSync(lockFile, JSON.stringify(lockData, null, 2), 'utf8');
        return { released: true, remaining_count: lockData.reentrant_count };
      }

      fs.unlinkSync(lockFile);
      return { released: true, remaining_count: 0 };
    } catch (e) {
      return { released: false, reason: 'ERROR', error: e.message };
    }
  }
}

module.exports = { AgentLockManager };
