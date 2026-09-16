module.exports = class HardenedRouter {
    route(taskState, trigger) {
      if (taskState.executionUncertain === true || taskState.sideEffectPotential === 'POSSIBLE') {
        return { action: 'HOLD_UNCERTAIN', reason: 'EXECUTION_UNCERTAIN_LOCK', trigger };
      }
      return { action: 'REDISPATCH_FALLBACK', worker: 'FALLBACK_W2' };
    }
  };
