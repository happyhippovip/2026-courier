// Completion Governor: Enforces the Inviolable Rule that Workers cannot declare Global Saturation
class CompletionGovernor {
  constructor() {
    this.globalCompletionDisabled = true; // Hard-locked for this Windows autonomous expedition
  }

  evaluateWorkerReport(workerReport) {
    if (!workerReport || typeof workerReport !== 'object') {
      return { admitted: false, reason: 'INVALID_WORKER_REPORT' };
    }

    // Workers may only report WORK_UNIT_COMPLETE or NO_MORE_WORK_KNOWN_TO_THIS_WORKER
    const validWorkerStatuses = ['WORK_UNIT_COMPLETE', 'NO_MORE_WORK_KNOWN_TO_THIS_WORKER', 'TASK_BLOCKED', 'TASK_FAILED'];
    if (!validWorkerStatuses.includes(workerReport.status)) {
      return {
        admitted: false,
        reason: `ILLEGAL_WORKER_STATUS: Worker reported '${workerReport.status}'. Workers are forbidden from claiming global mission status.`
      };
    }

    return { admitted: true, status: workerReport.status };
  }

  evaluateMissionStatus(openWorkCount, capacityAvailable = true) {
    if (!capacityAvailable) {
      return { mission_status: 'PAUSED_CAPACITY', terminal: true, reason: 'Session / context capacity limit reached with safe work remaining.' };
    }
    if (this.globalCompletionDisabled) {
      return {
        mission_status: 'ACTIVE_CONTINUUM',
        terminal: false,
        reason: 'Global saturation is disabled on Windows host; runtime continues autonomous progression.'
      };
    }
    return { mission_status: 'ACTIVE_CONTINUUM', terminal: false };
  }
}

module.exports = { CompletionGovernor };
