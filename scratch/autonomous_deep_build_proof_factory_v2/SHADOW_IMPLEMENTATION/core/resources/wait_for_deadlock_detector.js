'use strict';

/**
 * SHADOW IMPLEMENTATION: WAIT-FOR GRAPH DEADLOCK DETECTOR
 * Component: shadow/core/resources/wait_for_deadlock_detector.js
 * Mission: WINDOWS_AUTONOMOUS_DEEP_BUILD_PROOF_FACTORY_V2
 */

class DeadlockCycleDetectedError extends Error {
  constructor(message, details = {}) {
    super(message);
    this.name = 'DeadlockCycleDetectedError';
    this.details = details;
  }
}

class WaitForDeadlockDetector {
  constructor(options = {}) {
    this.preemptHighestPriority = options.preemptHighestPriority || false; // Mutant!
    this.disableUpgradeDeadlock = options.disableUpgradeDeadlock || false; // Mutant!
  }

  // waitGraph: Map of taskId -> { waitingForTaskIds: Set, priority: number, heldLocks: [] }
  detectCycles(waitGraph) {
    const visited = new Set();
    const stack = new Set();
    const cycles = [];

    const dfs = (node, path = []) => {
      visited.add(node);
      stack.add(node);
      path.push(node);

      const record = waitGraph.get(node);
      if (record && record.waitingForTaskIds) {
        for (const neighbor of record.waitingForTaskIds) {
          if (!visited.has(neighbor)) {
            dfs(neighbor, [...path]);
          } else if (stack.has(neighbor)) {
            // Found cycle
            const startIdx = path.indexOf(neighbor);
            const cyclePath = path.slice(startIdx);
            cyclePath.push(neighbor);
            cycles.push(cyclePath);
          }
        }
      }

      stack.delete(node);
    };

    for (const node of waitGraph.keys()) {
      if (!visited.has(node)) {
        dfs(node);
      }
    }

    return cycles;
  }

  detectUpgradeDeadlock(activeLocks, upgradeRequests) {
    if (this.disableUpgradeDeadlock) {
      return null; // Mutant!
    }

    // If resource R is held in SHARED mode by both A and B, and BOTH A and B submit an EXCLUSIVE upgrade request:
    // Neither can proceed until the other releases -> classic upgrade deadlock!
    for (const reqA of upgradeRequests) {
      for (const reqB of upgradeRequests) {
        if (reqA.taskId !== reqB.taskId && reqA.resourceKey === reqB.resourceKey) {
          return {
            isDeadlock: true,
            resourceKey: reqA.resourceKey,
            conflictingTasks: [
              { taskId: reqA.taskId, priority: reqA.priority },
              { taskId: reqB.taskId, priority: reqB.priority }
            ]
          };
        }
      }
    }

    return null;
  }

  resolveDeadlock(waitGraph, mutex) {
    const cycles = this.detectCycles(waitGraph);
    if (cycles.length === 0) {
      return { resolved: true, preemptedTaskIds: [] };
    }

    const preemptedTaskIds = [];

    for (const cycle of cycles) {
      const distinctTaskIds = Array.from(new Set(cycle));
      const candidates = distinctTaskIds.map(id => ({
        id,
        priority: waitGraph.get(id) ? waitGraph.get(id).priority : 0
      }));

      // Sort by priority (lowest first by default)
      candidates.sort((a, b) => {
        return this.preemptHighestPriority ? b.priority - a.priority : a.priority - b.priority;
      });

      const victim = candidates[0];
      if (!preemptedTaskIds.includes(victim.id)) {
        preemptedTaskIds.push(victim.id);
        // Break the cycle by releasing victim's locks in mutex
        if (mutex) {
          mutex.releaseAllLocksForTask(victim.id);
        }
        waitGraph.delete(victim.id);
      }
    }

    return {
      resolved: true,
      preemptedTaskIds,
      cyclesCount: cycles.length
    };
  }
}

module.exports = {
  WaitForDeadlockDetector,
  DeadlockCycleDetectedError
};
