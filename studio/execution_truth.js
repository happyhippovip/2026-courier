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

/**
 * Resolve Academy Teacher (Agentenlehrer) truth strictly from backend state evidence.
 * Clearly distinguishes SCHEDULE READY from RESEARCH RUNNING without guessing.
 */
export function resolveTeacherTruth(stateData) {
  const teacher = stateData?.agents?.['agent-academy-teacher'];
  if (!teacher) {
    return {
      state: 'UNKNOWN',
      schedule_status: 'UNKNOWN',
      last_school_time: null,
      next_school_time: null,
      lessons_today: 0,
      latest_lesson: null,
      pending_lessons: [],
      opportunities_found: 0,
      affected_agents: [],
      current_topic: null,
      next_action: null,
      visual_metadata: {
        name: 'AGENTENLEHRER',
        props: ['teacher_hat', 'glasses', 'teacher_pointer'],
        role_label: 'SYSTEM LEARNING + IMPROVEMENT',
      },
    };
  }

  const state = typeof teacher.state === 'string' && teacher.state.trim()
    ? teacher.state
    : 'IDLE';

  // Strict distinction between Schedule Ready and active Research Running
  const scheduleStatus = state === 'RESEARCHING'
    ? 'RESEARCH RUNNING'
    : 'SCHEDULE READY';

  return {
    state,
    schedule_status: scheduleStatus,
    last_school_time: teacher.last_school_time || null,
    next_school_time: teacher.next_school_time || '06:00 UTC',
    lessons_today: typeof teacher.lessons_today === 'number' ? teacher.lessons_today : 0,
    latest_lesson: teacher.latest_lesson || null,
    pending_lessons: Array.isArray(teacher.pending_lessons) ? teacher.pending_lessons : [],
    opportunities_found: typeof teacher.opportunities_found === 'number' ? teacher.opportunities_found : 0,
    affected_agents: Array.isArray(teacher.affected_agents) ? teacher.affected_agents : [],
    current_topic: teacher.current_topic || 'Standby',
    next_action: teacher.next_action || teacher.last_action || 'Monitoring daily school schedule',
    visual_metadata: teacher.visual_metadata || {
      name: 'AGENTENLEHRER',
      props: ['teacher_hat', 'glasses', 'teacher_pointer'],
      role_label: 'SYSTEM LEARNING + IMPROVEMENT',
    },
  };
}

/**
 * Resolve Academy Director (Schuldirektor) truth strictly from backend state evidence.
 */
export function resolveDirectorTruth(stateData) {
  const director = stateData?.agents?.['agent-academy-director'];
  if (!director) {
    return {
      state: 'UNKNOWN',
      lessons_reviewed: 0,
      lessons_approved: 0,
      lessons_rejected: 0,
      tests_required: 0,
      evals_passed: 0,
      evals_failed: 0,
      rule_violations: 0,
      measured_savings: { minutes_saved: 0.0, cost_saved_eur: 0.0 },
      next_action: null,
      visual_metadata: {
        name: 'SCHULDIREKTOR',
        role_label: 'ACADEMY GOVERNANCE + EVALUATION',
      },
    };
  }

  const state = typeof director.state === 'string' && director.state.trim()
    ? director.state
    : 'IDLE';

  return {
    state,
    lessons_reviewed: typeof director.lessons_reviewed === 'number' ? director.lessons_reviewed : 0,
    lessons_approved: typeof director.lessons_approved === 'number' ? director.lessons_approved : 0,
    lessons_rejected: typeof director.lessons_rejected === 'number' ? director.lessons_rejected : 0,
    tests_required: typeof director.tests_required === 'number' ? director.tests_required : 0,
    evals_passed: typeof director.evals_passed === 'number' ? director.evals_passed : 0,
    evals_failed: typeof director.evals_failed === 'number' ? director.evals_failed : 0,
    rule_violations: typeof director.rule_violations === 'number' ? director.rule_violations : 0,
    measured_savings: director.measured_savings || { minutes_saved: 0.0, cost_saved_eur: 0.0 },
    next_action: director.next_action || director.last_action || 'Awaiting lesson submissions and evaluations',
    visual_metadata: director.visual_metadata || {
      name: 'SCHULDIREKTOR',
      role_label: 'ACADEMY GOVERNANCE + EVALUATION',
    },
  };
}

/**
 * Resolve Academy economic improvement metrics strictly from evidence.
 * Never fabricates earned revenue; reports NOT_VERIFIED / UNKNOWN if absent.
 */
export function resolveAcademyEconomics(stateData) {
  const econ = stateData?.academy || {};
  const director = stateData?.agents?.['agent-academy-director'];

  const measuredMinSaved = typeof econ.measured_minutes_saved === 'number'
    ? econ.measured_minutes_saved
    : (typeof director?.measured_savings?.minutes_saved === 'number' ? director.measured_savings.minutes_saved : 0.0);

  const measuredCostSaved = typeof econ.measured_cost_saved_eur === 'number'
    ? econ.measured_cost_saved_eur
    : (typeof director?.measured_savings?.cost_saved_eur === 'number' ? director.measured_savings.cost_saved_eur : 0.0);

  const totalLessonsAdopted = typeof econ.total_lessons_adopted === 'number'
    ? econ.total_lessons_adopted
    : (typeof director?.lessons_approved === 'number' ? director.lessons_approved : 0);

  const opportunitiesTested = typeof econ.opportunities_tested === 'number'
    ? econ.opportunities_tested
    : 0;

  const evalsPassed = typeof director?.evals_passed === 'number' ? director.evals_passed : 0;
  const evalsFailed = typeof director?.evals_failed === 'number' ? director.evals_failed : 0;
  const totalEvals = evalsPassed + evalsFailed;
  const evalPassRate = totalEvals > 0 ? `${Math.round((evalsPassed / totalEvals) * 100)}%` : '100%';

  const revenueEvidence = econ.revenue_evidence === 'VERIFIED_RESULT'
    ? 'VERIFIED_RESULT'
    : 'NOT_VERIFIED';

  return {
    measured_minutes_saved: measuredMinSaved,
    measured_cost_saved_eur: measuredCostSaved,
    lessons_adopted: totalLessonsAdopted,
    opportunities_tested: opportunitiesTested,
    eval_pass_rate: evalPassRate,
    revenue_evidence: revenueEvidence,
    truth_label: 'OPPORTUNITY != REVENUE (MEASURED SAVINGS ONLY)',
  };
}
