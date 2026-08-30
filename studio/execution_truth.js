/**
 * Execution-truth helpers for the Operations Studio.
 *
 * The studio renders only an explicit execution_class supplied by the Courier
 * state API.  It deliberately does not infer an execution class from an agent
 * id, display name, task name, or UI animation.
 */
export const EXECUTION_CLASSES = Object.freeze([
  'REAL_CODEX_CLI',
  'DETERMINISTIC_CODEX',
  'REAL_ANTIGRAVITY',
  'DETERMINISTIC_ANTIGRAVITY',
  'FALLBACK',
  'SIMULATED_VISUAL',
  'REGISTERED',
  'UNKNOWN',
  'WAITING_FOR_HUMAN',
  'BLOCKED',
]);

const KNOWN_EXECUTION_CLASSES = new Set(EXECUTION_CLASSES);

/**
 * Return only a machine-provided, supported execution class.
 * Missing or malformed evidence is visibly UNKNOWN rather than guessed.
 */
export function resolveExecutionTruth(agentState) {
  const executionClass = agentState?.execution_class;
  return typeof executionClass === 'string' && KNOWN_EXECUTION_CLASSES.has(executionClass)
    ? executionClass
    : 'UNKNOWN';
}

/**
 * A missing decision is not an approval.  This is a display label, not a
 * generated workflow decision.
 */
export function resolveDecisionTruth(busState) {
  const decision = busState?.last_decision;
  return typeof decision === 'string' && decision.trim() ? decision : 'NO_DECISION';
}

/**
 * Return a real correlation id only.  The caller may display a neutral label
 * for null, but must never generate an identifier in the browser.
 */
export function resolveCorrelationTruth(busState) {
  const correlationId = busState?.correlation_id;
  return typeof correlationId === 'string'
    && correlationId.trim()
    && correlationId !== 'UNKNOWN'
    && correlationId !== 'NO_ACTIVE_WORKFLOW'
    ? correlationId
    : null;
}

export function executionBadgeLabel(executionClass) {
  const iconByClass = {
    REAL_CODEX_CLI: '🟢',
    REAL_ANTIGRAVITY: '🟢',
    DETERMINISTIC_CODEX: '🟡',
    DETERMINISTIC_ANTIGRAVITY: '🟡',
    FALLBACK: '🟠',
    SIMULATED_VISUAL: '🟣',
    REGISTERED: '🔵',
    WAITING_FOR_HUMAN: '🟠',
    BLOCKED: '🔴',
    UNKNOWN: '⚪',
  };
  return `${iconByClass[executionClass] || '⚪'} ${executionClass}`;
}

/**
 * Resolve Update Steward truth strictly from backend state evidence.
 * Missing evidence returns neutral UNKNOWN / null values, never fabricated strings.
 */
export function resolveStewardTruth(stateData) {
  const agents = stateData?.agents || {};
  const steward = agents['agent-update-steward'];
  const snapshot = stateData?.context_snapshot;

  const state = typeof steward?.state === 'string' && steward.state.trim()
    ? steward.state
    : (snapshot ? 'CONTEXT CURRENT' : 'UNKNOWN');

  const contextVersion = typeof snapshot?.context_version === 'number'
    ? snapshot.context_version
    : (typeof stateData?.bus?.context_version === 'number' && stateData.bus.context_version > 0
        ? stateData.bus.context_version
        : null);

  const prevVersion = typeof snapshot?.previous_snapshot_version === 'number'
    ? snapshot.previous_snapshot_version
    : null;

  const snapshotHash = typeof snapshot?.snapshot_hash === 'string' && snapshot.snapshot_hash.length >= 8
    ? snapshot.snapshot_hash
    : (typeof stateData?.bus?.snapshot_hash === 'string' && stateData.bus.snapshot_hash !== 'NONE'
        ? stateData.bus.snapshot_hash
        : null);

  const lastRefresh = typeof snapshot?.generated_at === 'string'
    ? snapshot.generated_at
    : (typeof steward?.updated_at === 'string' ? steward.updated_at : null);

  const changedItems = Array.isArray(snapshot?.changed_since_previous_snapshot)
    ? snapshot.changed_since_previous_snapshot
    : [];

  const repositories = typeof snapshot?.repositories === 'object' && snapshot.repositories !== null
    ? snapshot.repositories
    : {};

  const nextAction = typeof steward?.next_action === 'string' && steward.next_action.trim()
    ? steward.next_action
    : (steward?.last_action || null);

  const staleTasks = steward?.blocked || state === 'REFRESH REQUIRED'
    ? 'CONTEXT_REFRESH_REQUIRED'
    : 'NONE';

  return {
    state,
    context_version: contextVersion,
    previous_version: prevVersion,
    snapshot_hash: snapshotHash,
    last_refresh: lastRefresh,
    changed_items: changedItems,
    repositories,
    next_action: nextAction,
    stale_tasks: staleTasks,
    progress: typeof steward?.progress === 'number' ? steward.progress : (snapshot ? 1.0 : 0.0),
    task: steward?.task || (contextVersion ? `Context v${contextVersion}` : 'Standby'),
  };
}

/**
 * Resolve Chief wait-state from explicit machine evidence only.
 */
export function resolveChiefWaitState(stateData) {
  const agents = stateData?.agents || {};
  const bus = stateData?.bus || {};

  const chief = agents['agent-chief-commander'];
  const ag = agents['agent-antigravity-bridge'];
  const cdx = agents['agent-codex-bridge'];
  const curator = agents['agent-thought-curator'];

  // 1. Human Gate required
  if (
    bus.human_gate ||
    chief?.state === 'BLOCKED_HUMAN_GATE' ||
    chief?.state === 'BLOCKED_POLICY_CONFLICT' ||
    ag?.state === 'BLOCKED_HUMAN_GATE' ||
    cdx?.state === 'BLOCKED_HUMAN_GATE' ||
    curator?.state === 'CONFLICT' ||
    curator?.state === 'BLOCKED'
  ) {
    return 'CHIEF WAITING FOR HUMAN';
  }

  // 2. Active worker running
  if (ag?.state === 'RUNNING') {
    return 'CHIEF WAITING FOR ANTIGRAVITY';
  }
  if (cdx?.state === 'RUNNING') {
    return 'CHIEF WAITING FOR CODEX';
  }

  // 3. Worker finished, awaiting review
  if (ag?.state === 'AWAITING_CHIEF_REVIEW') {
    return 'RESULT RECEIVED FROM ANTIGRAVITY';
  }
  if (cdx?.state === 'AWAITING_CHIEF_REVIEW') {
    return 'RESULT RECEIVED FROM CODEX';
  }

  // 4. Chief evaluating or planning
  if (chief?.state === 'REVIEWING' || chief?.state === 'EVALUATING') {
    return 'REVIEWING RESULT';
  }
  if (chief?.state === 'PLANNING' || curator?.state === 'SENT TO CHIEF') {
    return 'PLANNING NEXT TASK';
  }

  // 5. Next task ready
  if (bus.is_locked && bus.last_decision === 'ACCEPTED') {
    return 'NEXT TASK READY';
  }

  // 6. Idle or Unknown
  if (!bus.is_locked && (!bus.active_workflow || bus.active_workflow === 'IDLE_MONITORING')) {
    return 'IDLE';
  }

  return 'UNKNOWN';
}

/**
 * Validate that a returned result strictly matches the expected workflow and correlation.
 * Rejects cross-thread and mismatched correlations.
 */
export function validateThreadAssociation(resultEnvelope, expectedWorkflowId, expectedCorrelationId) {
  if (!resultEnvelope || typeof resultEnvelope !== 'object') return false;

  const resCorr = resultEnvelope.correlation_id;
  const resWf = resultEnvelope.payload?.workflow_id || resultEnvelope.workflow_id;

  if (expectedCorrelationId && resCorr && resCorr !== expectedCorrelationId) {
    return false;
  }

  if (expectedWorkflowId && resWf && resWf !== expectedWorkflowId) {
    return false;
  }

  return true;
}

/**
 * Extract structured bounded thread context metadata from state data.
 */
export function resolveThreadContext(stateData) {
  const bus = stateData?.bus || {};
  const agents = stateData?.agents || {};
  const snapshot = stateData?.context_snapshot;

  const correlationId = resolveCorrelationTruth(bus);
  const workflowId = typeof bus.active_workflow === 'string' && bus.active_workflow !== 'IDLE_MONITORING'
    ? bus.active_workflow
    : null;

  // Identify active worker
  let senderAgentId = null;
  let senderAgentType = null;
  let currentTask = null;

  const ag = agents['agent-antigravity-bridge'];
  const cdx = agents['agent-codex-bridge'];
  const chief = agents['agent-chief-commander'];

  if (ag && (ag.state === 'RUNNING' || ag.state === 'AWAITING_CHIEF_REVIEW')) {
    senderAgentId = ag.id || 'agent-antigravity-bridge';
    senderAgentType = 'antigravity';
    currentTask = ag.task || null;
  } else if (cdx && (cdx.state === 'RUNNING' || cdx.state === 'AWAITING_CHIEF_REVIEW')) {
    senderAgentId = cdx.id || 'agent-codex-bridge';
    senderAgentType = 'codex';
    currentTask = cdx.task || null;
  } else if (chief && chief.task) {
    senderAgentId = chief.id || 'agent-chief-commander';
    senderAgentType = 'chief';
    currentTask = chief.task;
  }

  const waitingFor = resolveChiefWaitState(stateData);

  return {
    workflow_id: workflowId,
    correlation_id: correlationId,
    conversation_thread_id: correlationId,
    task_id: currentTask,
    sender_agent_id: senderAgentId,
    sender_agent_type: senderAgentType,
    recipient_agent_id: 'agent-chief-commander',
    waiting_for: waitingFor,
    context_version: typeof snapshot?.context_version === 'number'
      ? snapshot.context_version
      : (typeof bus.context_version === 'number' && bus.context_version > 0 ? bus.context_version : null),
    context_snapshot_hash: snapshot?.snapshot_hash || (bus.snapshot_hash !== 'NONE' ? bus.snapshot_hash : null),
    is_locked: Boolean(bus.is_locked),
    last_decision: resolveDecisionTruth(bus),
  };
}
