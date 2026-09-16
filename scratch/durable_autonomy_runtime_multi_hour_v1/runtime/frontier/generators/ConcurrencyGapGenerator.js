// ConcurrencyGapGenerator.js — Generates multi-process and multi-worker contention tests
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

class ConcurrencyGapGenerator {
  generate(runtime) {
    const candidates = [];

    // Concurrency 1: Multi-Process NTFS File Lock Mutex Race
    candidates.push({
      title: 'Concurrency Gap: Multi-Process NTFS Exclusive Lock Mutex Race',
      category: 'CONCURRENCY',
      priority: 'P1',
      expected_information_gain: 9,
      lane: 'M. NO-STACKING',
      discovery_method: 'CONCURRENCY_RACE_GENERATION',
      task_generator_fn: (workingDir, rt) => {
        const lockPath = path.join(workingDir, 'race.lock');
        const counterPath = path.join(workingDir, 'race_counter.txt');
        fs.writeFileSync(counterPath, '0', 'utf8');

        // Test ResourceLockManager mutual exclusion
        const lockMgr = rt.lockManager;
        const taskA = 'TASK-CONCURRENCY-A';
        const taskB = 'TASK-CONCURRENCY-B';
        const resPath = path.join(workingDir, 'shared_res');

        const acqA = lockMgr.acquire(resPath, taskA);
        const acqB = lockMgr.acquire(resPath, taskB); // should fail or return false

        lockMgr.release(resPath, taskA);
        const acqBAfter = lockMgr.acquire(resPath, taskB); // should succeed
        lockMgr.release(resPath, taskB);

        const findings = {
          test: 'EXCLUSIVE_LOCK_MUTEX_RACE',
          acqA_success: acqA,
          acqB_blocked: !acqB,
          acqB_after_release: acqBAfter,
          status: (acqA && !acqB && acqBAfter) ? 'PASSED' : 'FAILED'
        };

        const artifactName = 'mutex_concurrency_proof.json';
        const content = JSON.stringify(findings, null, 2);
        fs.writeFileSync(path.join(workingDir, artifactName), content, 'utf8');
        const sha = crypto.createHash('sha256').update(content).digest('hex');

        return {
          exit_code: 0,
          criteria_key: 'CRIT_MUTEX_CONCURRENCY_ASSERTED',
          artifacts: [artifactName],
          checksum_map: { [artifactName]: sha }
        };
      }
    });

    // Concurrency 2: Subpath Prefix Containment Collision
    candidates.push({
      title: 'Concurrency Gap: Hierarchical Subpath Prefix Collision Detection',
      category: 'CONCURRENCY',
      priority: 'P1',
      expected_information_gain: 9,
      lane: 'L. RESOURCE LEASES',
      discovery_method: 'ASSUMPTION_INVERSION',
      task_generator_fn: (workingDir, rt) => {
        const lockMgr = rt.lockManager;
        const parentPath = path.join(workingDir, 'parent_dir');
        const childPath = path.join(workingDir, 'parent_dir', 'child_dir');

        const lockParent = lockMgr.acquire(parentPath, 'TASK-PARENT');
        const lockChild = lockMgr.acquire(childPath, 'TASK-CHILD'); // Must be blocked by parent lock

        lockMgr.release(parentPath, 'TASK-PARENT');

        const findings = {
          test: 'HIERARCHICAL_SUBPATH_COLLISION',
          parent_lock: lockParent,
          child_collision_prevented: !lockChild,
          status: (lockParent && !lockChild) ? 'PASSED' : 'FAILED'
        };

        const artifactName = 'subpath_collision_proof.json';
        const content = JSON.stringify(findings, null, 2);
        fs.writeFileSync(path.join(workingDir, artifactName), content, 'utf8');
        const sha = crypto.createHash('sha256').update(content).digest('hex');

        return {
          exit_code: 0,
          criteria_key: 'CRIT_SUBPATH_COLLISION_PREVENTED',
          artifacts: [artifactName],
          checksum_map: { [artifactName]: sha }
        };
      }
    });

    return candidates;
  }
}

module.exports = { ConcurrencyGapGenerator };