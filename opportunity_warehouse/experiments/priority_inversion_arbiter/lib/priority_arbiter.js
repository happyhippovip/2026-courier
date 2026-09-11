/**
 * Multi-Tenant Context Window Priority Inversion & Fair Bounded-Wait Arbiter
 * Implements the Priority Inheritance Protocol (PIP) for multi-agent shared context buffers,
 * dynamically boosting low-priority resource holders to prevent unbounded priority inversion.
 */

class AgentTask {
  constructor(agentId, basePriority = 1) {
    this.agentId = agentId;
    this.basePriority = basePriority;
    this.effectivePriority = basePriority;
    this.acquiredLocks = new Set();
    this.waitingForLock = null;
  }
}

class ResourceLock {
  constructor(lockId) {
    this.lockId = lockId;
    this.holder = null;
    this.waitQueue = []; // array of AgentTask sorted by effectivePriority descending
  }
}

class PriorityInversionArbiter {
  constructor() {
    this.agents = new Map();
    this.locks = new Map();
    this.elevationEvents = [];
  }

  registerAgent(agentId, basePriority = 1) {
    const agent = new AgentTask(agentId, basePriority);
    this.agents.set(agentId, agent);
    return agent;
  }

  getOrCreateLock(lockId) {
    if (!this.locks.has(lockId)) {
      this.locks.set(lockId, new ResourceLock(lockId));
    }
    return this.locks.get(lockId);
  }

  acquireLock(agentId, lockId) {
    const agent = this.agents.get(agentId);
    if (!agent) throw new Error('Unregistered agent: ' + agentId);
    const lock = this.getOrCreateLock(lockId);

    if (lock.holder === null) {
      // Immediate uncontended acquisition
      lock.holder = agent;
      agent.acquiredLocks.add(lock);
      return { acquired: true, elevated: false };
    }

    if (lock.holder === agent) {
      return { acquired: true, elevated: false }; // reentrant
    }

    // Contention: agent must wait
    agent.waitingForLock = lock;
    lock.waitQueue.push(agent);
    lock.waitQueue.sort((a, b) => b.effectivePriority - a.effectivePriority);

    // Check priority inheritance
    const holder = lock.holder;
    if (agent.effectivePriority > holder.effectivePriority) {
      const prevPriority = holder.effectivePriority;
      holder.effectivePriority = agent.effectivePriority;
      const event = {
        holderId: holder.agentId,
        elevatedFrom: prevPriority,
        elevatedTo: holder.effectivePriority,
        blockedAgentId: agent.agentId,
        lockId
      };
      this.elevationEvents.push(event);
      return { acquired: false, elevated: true, elevationEvent: event };
    }

    return { acquired: false, elevated: false };
  }

  releaseLock(agentId, lockId) {
    const agent = this.agents.get(agentId);
    if (!agent) throw new Error('Unregistered agent: ' + agentId);
    const lock = this.locks.get(lockId);
    if (!lock || lock.holder !== agent) {
      throw new Error('Lock not held by agent ' + agentId);
    }

    lock.holder = null;
    agent.acquiredLocks.delete(lock);

    // Demote agent back to base priority (or highest among remaining locks)
    agent.effectivePriority = agent.basePriority;

    if (lock.waitQueue.length > 0) {
      // Dispatch to highest priority waiter
      const nextAgent = lock.waitQueue.shift();
      nextAgent.waitingForLock = null;
      lock.holder = nextAgent;
      nextAgent.acquiredLocks.add(lock);
      return { released: true, nextHolderId: nextAgent.agentId };
    }

    return { released: true, nextHolderId: null };
  }
}

module.exports = { PriorityInversionArbiter };
