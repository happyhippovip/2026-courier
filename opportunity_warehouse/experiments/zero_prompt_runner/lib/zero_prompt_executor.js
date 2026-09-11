// Universal Zero-Prompt Autonomy Executor
// Enforces unattended, non-interactive execution with fail-closed timeout and invariant checks.
// Zero external dependencies.

class ZeroPromptExecutor {
  constructor({
    maxTimeoutMs = 15000,
    allowedScope = []
  } = {}) {
    this.maxTimeoutMs = maxTimeoutMs;
    this.allowedScope = allowedScope;
  }

  executeTask({ taskId, action, targetPath }) {
    if (!taskId || typeof taskId !== 'string') {
      throw new Error('[ZERO_PROMPT_ERROR] taskId is required');
    }
    if (!action || typeof action !== 'function') {
      throw new Error('[ZERO_PROMPT_ERROR] action must be an executable function');
    }

    // Boundary Scope Check
    if (targetPath && this.allowedScope.length > 0) {
      const normalizedTarget = targetPath.toLowerCase().replace(/\\/g, '/');
      const isAllowed = this.allowedScope.some(scope => {
        const normScope = scope.toLowerCase().replace(/\\/g, '/');
        return normalizedTarget.startsWith(normScope);
      });
      if (!isAllowed) {
        throw new Error(`[ZERO_PROMPT_ERROR] Target path '${targetPath}' outside authorized scope`);
      }
    }

    const startTime = Date.now();
    let result;
    try {
      result = action();
    } catch (err) {
      throw new Error(`[ZERO_PROMPT_ERROR] Task '${taskId}' failed during execution: ${err.message}`);
    }

    const durationMs = Date.now() - startTime;
    if (durationMs > this.maxTimeoutMs) {
      throw new Error(`[ZERO_PROMPT_ERROR] Task '${taskId}' exceeded execution budget (${durationMs}ms > ${this.maxTimeoutMs}ms)`);
    }

    return {
      taskId,
      status: 'COMPLETED_UNATTENDED',
      durationMs,
      result
    };
  }
}

module.exports = { ZeroPromptExecutor };
