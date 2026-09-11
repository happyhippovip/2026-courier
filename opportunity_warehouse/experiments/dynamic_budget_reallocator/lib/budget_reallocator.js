/**
 * budget_reallocator.js - Token Budget Reallocation & Priority Balancing Daemon
 * Dynamically reallocates surplus tokens from low-demand subtasks to high-priority reasoning nodes.
 */
class DynamicBudgetReallocator {
  constructor(options = {}) {
    this.globalCeilingTokens = options.globalCeilingTokens || 16000;
  }

  balanceBudgets(tasks = []) {
    let totalInitialAllocated = 0;
    let totalConsumed = 0;
    let surplusPool = 0;

    const taskStates = tasks.map(t => {
      const initial = t.allocatedBudget || 1000;
      const consumed = t.consumedTokens || 0;
      const priority = t.priority || 1; // 1 = low, 5 = critical
      totalInitialAllocated += initial;
      totalConsumed += consumed;

      let surplus = 0;
      let needsMore = false;
      if (consumed < initial) {
        surplus = initial - consumed;
        surplusPool += surplus;
      } else if (consumed >= initial) {
        needsMore = true;
      }

      return {
        id: t.id,
        priority,
        minBudget: t.minBudget || 500,
        initialBudget: initial,
        consumedTokens: consumed,
        surplus,
        needsMore,
        reallocatedBudget: initial
      };
    });

    // Distribute surplus pool to tasks that need more or have high priority
    const hungryTasks = taskStates.filter(t => t.needsMore || t.priority >= 3);
    const totalPriorityWeight = hungryTasks.reduce((acc, t) => acc + t.priority, 0);

    if (totalPriorityWeight > 0 && surplusPool > 0) {
      hungryTasks.forEach(t => {
        const share = Math.floor(surplusPool * (t.priority / totalPriorityWeight));
        t.reallocatedBudget += share;
      });
    }

    // Trim surplus tasks down to actual consumed + safe margin
    taskStates.forEach(t => {
      if (t.surplus > 0) {
        t.reallocatedBudget = Math.max(t.minBudget, t.consumedTokens + 200);
      }
    });

    // Ensure sum does not exceed global ceiling
    let totalFinalAllocated = taskStates.reduce((acc, t) => acc + t.reallocatedBudget, 0);
    if (totalFinalAllocated > this.globalCeilingTokens) {
      const scale = this.globalCeilingTokens / totalFinalAllocated;
      taskStates.forEach(t => {
        t.reallocatedBudget = Math.floor(t.reallocatedBudget * scale);
      });
      totalFinalAllocated = taskStates.reduce((acc, t) => acc + t.reallocatedBudget, 0);
    }

    return {
      timestamp: new Date().toISOString(),
      globalCeilingTokens: this.globalCeilingTokens,
      summary: {
        totalInitialAllocated,
        totalFinalAllocated,
        totalConsumed,
        surplusHarvested: surplusPool,
        withinCeiling: totalFinalAllocated <= this.globalCeilingTokens
      },
      tasks: taskStates.map(t => ({
        id: t.id,
        priority: t.priority,
        initialBudget: t.initialBudget,
        consumedTokens: t.consumedTokens,
        reallocatedBudget: t.reallocatedBudget,
        deltaTokens: t.reallocatedBudget - t.initialBudget
      }))
    };
  }
}

module.exports = { DynamicBudgetReallocator };
