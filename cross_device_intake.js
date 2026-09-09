const MessageClass = {
  STATUS_ONLY: 'STATUS_ONLY',
  TASK_REQUEST: 'TASK_REQUEST',
  HUMAN_GATE: 'HUMAN_GATE',
  BLOCKER_REPORT: 'BLOCKER_REPORT',
  DELEGATION_TO_CHIEF: 'DELEGATION_TO_CHIEF',
  COMPLETED_RESULT: 'COMPLETED_RESULT'
};

const TaskStatus = {
  RUNNING: 'RUNNING',
  BLOCKED: 'BLOCKED',
  FAILED: 'FAILED',
  DONE: 'DONE',
  PARTIAL: 'PARTIAL'
};

const ActionDomain = {
  CONNECTED_REMOTE: 'CONNECTED_REMOTE',
  LOCAL_MACHINE: 'LOCAL_MACHINE',
  HUMAN_ONLY: 'HUMAN_ONLY'
};

class CrossDeviceIntakeEngine {
  constructor() {
    this.humanGatePatterns = [
      /oauth/i, /login n[öo]tig/i, /auth login/i, /2fa/i, /password/i,
      /passwort/i, /credential/i, /keychain/i, /human_gate/i, /blocked by oauth/i
    ];
    this.delegationPatterns = [
      /chatgpt soll/i, /chief soll/i, /über den verbundenen github/i,
      /delegat/i, /mach du das/i, /übernimm das/i, /kurier das/i
    ];
    this.verifiedEvidencePatterns = [
      /pass/i, /erfolgreich/i, /verifiziert/i, /100%/, /bit-for-bit/i,
      /commit [0-9a-f]{7}/i, /sha-256/i
    ];
  }

  classifyAndRoute(text, context = {}) {
    const t = (text || '').trim();
    const tLower = t.toLowerCase();

    // 1. Human Gate
    const isHumanGate = this.humanGatePatterns.some(p => p.test(tLower));
    if (isHumanGate && !context.authenticated) {
      return {
        messageClass: MessageClass.HUMAN_GATE,
        taskDescription: `Human authorization gate required (${t})`,
        status: TaskStatus.BLOCKED,
        erledigt: false,
        evidence: 'Authentication barrier encountered; local human agency required',
        blocker: t,
        nextStep: 'Human must perform one-time authentication action',
        actionDomain: ActionDomain.HUMAN_ONLY,
        requiresWorkerLaunch: false
      };
    }

    // 2. Delegation to Chief
    const isDelegation = this.delegationPatterns.some(p => p.test(tLower));
    if (isDelegation) {
      const hasConnectedTool = context.hasConnectedTool !== false;
      if (hasConnectedTool) {
        return {
          messageClass: MessageClass.DELEGATION_TO_CHIEF,
          taskDescription: `Execute connected action on Chief (${t})`,
          status: TaskStatus.RUNNING,
          erledigt: false,
          evidence: 'Connected tool capability available in Chief environment',
          blocker: 'NONE',
          nextStep: 'Chief executes task via connected tool',
          actionDomain: ActionDomain.CONNECTED_REMOTE,
          requiresWorkerLaunch: true
        };
      } else {
        return {
          messageClass: MessageClass.BLOCKER_REPORT,
          taskDescription: `Connected capability unavailable for: ${t}`,
          status: TaskStatus.BLOCKED,
          erledigt: false,
          evidence: 'Chief lacks remote connector for this action',
          blocker: 'Missing connected tool',
          nextStep: 'Route to machine-local agent',
          actionDomain: ActionDomain.LOCAL_MACHINE,
          requiresWorkerLaunch: false
        };
      }
    }

    // 3. Partial
    if (tLower.includes('partial') || tLower.includes('teilweise') || tLower.includes('unvollständig')) {
      return {
        messageClass: MessageClass.BLOCKER_REPORT,
        taskDescription: `Partial progress reported (${t})`,
        status: TaskStatus.PARTIAL,
        erledigt: false,
        evidence: t,
        blocker: 'Required sub-steps remain incomplete',
        nextStep: 'Complete remaining steps before marking done',
        actionDomain: ActionDomain.LOCAL_MACHINE,
        requiresWorkerLaunch: true
      };
    }

    // 4. Running
    if (tLower.includes('running') || tLower.includes('läuft') || tLower.includes('still running')) {
      return {
        messageClass: MessageClass.STATUS_ONLY,
        taskDescription: `Background task in progress (${t})`,
        status: TaskStatus.RUNNING,
        erledigt: false,
        evidence: t,
        blocker: 'NONE',
        nextStep: 'Wait for running worker to finish; do not spawn duplicate',
        actionDomain: ActionDomain.LOCAL_MACHINE,
        requiresWorkerLaunch: false
      };
    }

    // 5. Continuation Directive
    if (tLower === 'weiter' || tLower === 'continue') {
      return {
        messageClass: MessageClass.TASK_REQUEST,
        taskDescription: 'Execute single next safe local task',
        status: TaskStatus.RUNNING,
        erledigt: false,
        evidence: 'Explicit user continuation directive received',
        blocker: 'NONE',
        nextStep: 'Execute exactly ONE next safe local action',
        actionDomain: ActionDomain.LOCAL_MACHINE,
        requiresWorkerLaunch: true
      };
    }

    // 6. Worker claims without evidence
    const hasEvidence = this.verifiedEvidencePatterns.some(p => p.test(tLower));
    const workerClaimOnly = (tLower.includes('worker says') || tLower.includes('erfolgreich behauptet') || tLower.includes('claims success')) && !hasEvidence;

    if (workerClaimOnly) {
      return {
        messageClass: MessageClass.STATUS_ONLY,
        taskDescription: `Unverified worker claim: ${t}`,
        status: TaskStatus.BLOCKED,
        erledigt: false,
        evidence: 'Worker claim lacks independent verification or effect proof',
        blocker: 'Unverified claim; effect not proven',
        nextStep: 'Execute deterministic verification test to confirm claim',
        actionDomain: ActionDomain.LOCAL_MACHINE,
        requiresWorkerLaunch: false
      };
    }

    // 7. Verified Completion
    if (hasEvidence && !tLower.includes('error') && !tLower.includes('fail') && !tLower.includes('blocked')) {
      return {
        messageClass: MessageClass.COMPLETED_RESULT,
        taskDescription: `Verified result: ${t}`,
        status: TaskStatus.DONE,
        erledigt: true,
        evidence: t,
        blocker: 'NONE',
        nextStep: 'NONE',
        actionDomain: ActionDomain.LOCAL_MACHINE,
        requiresWorkerLaunch: false
      };
    }

    // 8. Default fallback
    return {
      messageClass: MessageClass.STATUS_ONLY,
      taskDescription: t,
      status: TaskStatus.PARTIAL,
      erledigt: false,
      evidence: t,
      blocker: 'NONE',
      nextStep: 'Inspect status and define next action',
      actionDomain: ActionDomain.LOCAL_MACHINE,
      requiresWorkerLaunch: false
    };
  }

  formatTerminalOutput(res) {
    return [
      `AUFGABE: ${res.taskDescription}`,
      `STATUS: ${res.status}`,
      `ERLEDIGT: ${res.erledigt ? 'JA' : 'NEIN'}`,
      `BEWEIS: ${res.evidence}`,
      `BLOCKER: ${res.blocker}`,
      `NÄCHSTER_SCHRITT: ${res.nextStep}`
    ].join('\n');
  }
}

module.exports = {
  MessageClass,
  TaskStatus,
  ActionDomain,
  CrossDeviceIntakeEngine
};
