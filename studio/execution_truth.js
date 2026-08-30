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
      lessons_today: null,
      latest_lesson: null,
      latest_lesson_status: null,
      pending_lessons: null,
      opportunities_found: null,
      affected_agents: null,
      current_topic: null,
      next_action: null,
      academy_enabled: null,
      school_window_minutes: null,
      eligible_agents: null,
      opportunity_candidates: null,
      progress: null,
      visual_metadata: {
        name: 'AGENTENLEHRER',
        props: ['teacher_hat', 'glasses', 'teacher_pointer'],
        role_label: 'SYSTEM LEARNING + IMPROVEMENT',
      },
    };
  }

  const state = typeof teacher.state === 'string' && teacher.state.trim()
    ? teacher.state
    : 'UNKNOWN';

  const nextSchoolTime = typeof teacher.next_school_time === 'string' && teacher.next_school_time.trim()
    ? teacher.next_school_time
    : null;

  // A schedule is ready only if the backend has supplied a next school time.
  // An absent teacher state never becomes a visual research/schedule claim.
  const scheduleStatus = state === 'RESEARCHING'
    ? 'RESEARCH RUNNING'
    : (nextSchoolTime ? 'SCHEDULE READY' : 'UNKNOWN');

  return {
    state,
    schedule_status: scheduleStatus,
    last_school_time: typeof teacher.last_school_time === 'string' ? teacher.last_school_time : null,
    next_school_time: nextSchoolTime,
    lessons_today: Number.isFinite(teacher.lessons_today) ? teacher.lessons_today : null,
    latest_lesson: typeof teacher.latest_lesson === 'string' ? teacher.latest_lesson : null,
    latest_lesson_status: typeof teacher.latest_lesson_status === 'string' ? teacher.latest_lesson_status : null,
    pending_lessons: Array.isArray(teacher.pending_lessons) ? teacher.pending_lessons : null,
    opportunities_found: Number.isFinite(teacher.opportunities_found) ? teacher.opportunities_found : null,
    affected_agents: Array.isArray(teacher.affected_agents) ? teacher.affected_agents : null,
    current_topic: typeof teacher.current_topic === 'string' ? teacher.current_topic : null,
    next_action: typeof teacher.next_action === 'string'
      ? teacher.next_action
      : (typeof teacher.last_action === 'string' ? teacher.last_action : null),
    academy_enabled: typeof stateData?.academy_config?.academy_enabled === 'boolean'
      ? stateData.academy_config.academy_enabled
      : null,
    school_window_minutes: Number.isFinite(stateData?.academy_config?.academy_window_minutes)
      ? stateData.academy_config.academy_window_minutes
      : null,
    eligible_agents: Array.isArray(teacher.eligible_agents) ? teacher.eligible_agents : null,
    opportunity_candidates: Array.isArray(teacher.opportunity_candidates) ? teacher.opportunity_candidates : null,
    progress: Number.isFinite(teacher.progress) ? teacher.progress : null,
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
      lessons_reviewed: null,
      lessons_approved: null,
      lessons_rejected: null,
      tests_required: null,
      evals_passed: null,
      evals_failed: null,
      rule_violations: null,
      measured_savings: { minutes_saved: null, cost_saved_eur: null },
      next_action: null,
      progress: null,
      visual_metadata: {
        name: 'SCHULDIREKTOR',
        role_label: 'ACADEMY GOVERNANCE + EVALUATION',
      },
    };
  }

  const state = typeof director.state === 'string' && director.state.trim()
    ? director.state
    : 'UNKNOWN';

  return {
    state,
    lessons_reviewed: Number.isFinite(director.lessons_reviewed) ? director.lessons_reviewed : null,
    lessons_approved: Number.isFinite(director.lessons_approved) ? director.lessons_approved : null,
    lessons_rejected: Number.isFinite(director.lessons_rejected) ? director.lessons_rejected : null,
    tests_required: Number.isFinite(director.tests_required) ? director.tests_required : null,
    evals_passed: Number.isFinite(director.evals_passed) ? director.evals_passed : null,
    evals_failed: Number.isFinite(director.evals_failed) ? director.evals_failed : null,
    rule_violations: Number.isFinite(director.rule_violations) ? director.rule_violations : null,
    measured_savings: {
      minutes_saved: Number.isFinite(director.measured_savings?.minutes_saved)
        ? director.measured_savings.minutes_saved
        : null,
      cost_saved_eur: Number.isFinite(director.measured_savings?.cost_saved_eur)
        ? director.measured_savings.cost_saved_eur
        : null,
    },
    next_action: typeof director.next_action === 'string'
      ? director.next_action
      : (typeof director.last_action === 'string' ? director.last_action : null),
    progress: Number.isFinite(director.progress) ? director.progress : null,
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
  const econ = stateData?.academy?.economics || stateData?.academy || {};
  const director = stateData?.agents?.['agent-academy-director'];

  const measuredMinSaved = Number.isFinite(econ.measured_minutes_saved)
    ? econ.measured_minutes_saved
    : (Number.isFinite(director?.measured_savings?.minutes_saved) ? director.measured_savings.minutes_saved : null);

  const measuredCostSaved = Number.isFinite(econ.measured_cost_saved_eur)
    ? econ.measured_cost_saved_eur
    : (Number.isFinite(director?.measured_savings?.cost_saved_eur) ? director.measured_savings.cost_saved_eur : null);

  const totalLessonsAdopted = Number.isFinite(econ.total_lessons_adopted)
    ? econ.total_lessons_adopted
    : null;

  const opportunitiesTested = Number.isFinite(econ.opportunities_tested)
    ? econ.opportunities_tested
    : null;

  const evalsPassed = Number.isFinite(director?.evals_passed) ? director.evals_passed : null;
  const evalsFailed = Number.isFinite(director?.evals_failed) ? director.evals_failed : null;
  const totalEvals = evalsPassed !== null && evalsFailed !== null ? evalsPassed + evalsFailed : null;
  const evalPassRate = totalEvals && totalEvals > 0 ? `${Math.round((evalsPassed / totalEvals) * 100)}%` : 'UNKNOWN';

  const revenueEvidence = typeof econ.revenue_evidence === 'string'
    ? econ.revenue_evidence
    : 'UNKNOWN';

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

/**
 * Resolve bounded Academy structured evidence (config, lessons, opportunities, evaluations).
 */
export function resolveAcademySummary(stateData) {
  const academy = stateData?.academy || {};
  const config = academy.config || {};
  const lessons = Array.isArray(academy.lessons) ? academy.lessons : [];
  const opportunities = Array.isArray(academy.opportunities) ? academy.opportunities : [];
  const evaluations = Array.isArray(academy.evaluations) ? academy.evaluations : [];

  return {
    is_enabled: typeof config.academy_enabled === 'boolean' ? config.academy_enabled : true,
    timezone: config.academy_timezone || 'UTC',
    daily_time: config.academy_daily_time || '06:00',
    window_minutes: typeof config.academy_window_minutes === 'number' ? config.academy_window_minutes : 60,
    lessons_count: lessons.length,
    recent_lessons: lessons,
    opportunities_count: opportunities.length,
    recent_opportunities: opportunities,
    evaluations_count: evaluations.length,
    recent_evaluations: evaluations,
  };
}

/**
 * Resolve Live Agent HQ Desk Matrix (28 workstations: 17 active equipped roles, ~25 equipped, 3 future expansion).
 */
export function resolveDeskMatrix(stateData) {
  const agents = stateData?.agents || {};
  const bus = stateData?.bus || {};

  const deskDefinitions = [
    { id: 'DESK-CHIEF-01', agentId: 'agent-chief-commander', name: 'Chief Commander', zone: 'STRATEGY', icon: '👑', type: 'CORE' },
    { id: 'DESK-CURATOR-02', agentId: 'agent-thought-curator', name: 'Idea Sync / Curator', zone: 'IDEA_LAB', icon: '🧠', type: 'CORE' },
    { id: 'DESK-STEWARD-03', agentId: 'agent-update-steward', name: 'Update Steward', zone: 'CONTEXT', icon: '🔄', type: 'CORE' },
    { id: 'DESK-COURIER-04', agentId: 'agent-courier-relay', name: 'Courier Hub Relay', zone: 'COURIER', icon: '⚡', type: 'CORE' },
    { id: 'DESK-ANTIGRAVITY-05', agentId: 'agent-antigravity-bridge', name: 'Antigravity Studio', zone: 'ANTIGRAVITY', icon: '🎨', type: 'WORKER' },
    { id: 'DESK-CODEX-06', agentId: 'agent-codex-bridge', name: 'Codex Technical Lab', zone: 'CODEX', icon: '💻', type: 'WORKER' },
    { id: 'DESK-TEACHER-07', agentId: 'agent-academy-teacher', name: 'Agentenlehrer', zone: 'ACADEMY', icon: '👨‍🏫', type: 'ACADEMY' },
    { id: 'DESK-DIRECTOR-08', agentId: 'agent-academy-director', name: 'Schuldirektor', zone: 'ACADEMY', icon: '🏛️', type: 'ACADEMY' },
    { id: 'DESK-ROUTER-09', agentId: 'smart-resource-router', name: 'Smart Router', zone: 'STRATEGY', icon: '🧭', type: 'ROUTER' },
    { id: 'DESK-SECURITY-10', agentId: 'agent-security-sentinel', name: 'Security Sentinel', zone: 'SERVER', icon: '🛡️', type: 'SECURITY' },
    { id: 'DESK-ASSET-11', agentId: 'agent-asset-validator', name: 'Asset Validator', zone: 'ANTIGRAVITY', icon: '📐', type: 'WORKER' },
    { id: 'DESK-VIDEO-12', agentId: 'agent-video-synth', name: 'Video Synth', zone: 'ANTIGRAVITY', icon: '🎬', type: 'WORKER' },
    { id: 'DESK-CHANNEL-13', agentId: 'agent-channel-dispatcher', name: 'Channel Dispatcher', zone: 'COURIER', icon: '📡', type: 'COURIER' },
    { id: 'DESK-MEMORY-14', agentId: 'agent-memory-mesh', name: 'Memory Mesh Indexer', zone: 'IDEA_LAB', icon: '🗄️', type: 'INDEXER' },
    { id: 'DESK-GATE-15', agentId: 'agent-human-gate-monitor', name: 'Human Gate Monitor', zone: 'STRATEGY', icon: '🚨', type: 'GATE' },
    { id: 'DESK-TEST-16', agentId: 'agent-test-guardian', name: 'Test Guardian', zone: 'CODEX', icon: '🧪', type: 'QA' },
    { id: 'DESK-LOOP-17', agentId: 'agent-loop-supervisor', name: 'Loop Supervisor', zone: 'STRATEGY', icon: '🔁', type: 'SUPERVISOR' },
    { id: 'DESK-EQUIPPED-18', agentId: null, name: 'Code Review Pod', zone: 'CODEX', icon: '📝', type: 'EQUIPPED' },
    { id: 'DESK-EQUIPPED-19', agentId: null, name: '3D Shader Workbench', zone: 'ANTIGRAVITY', icon: '✨', type: 'EQUIPPED' },
    { id: 'DESK-EQUIPPED-20', agentId: null, name: 'Audio Synth Station', zone: 'ANTIGRAVITY', icon: '🎙️', type: 'EQUIPPED' },
    { id: 'DESK-EQUIPPED-21', agentId: null, name: 'Memory Diff Inspector', zone: 'IDEA_LAB', icon: '📑', type: 'EQUIPPED' },
    { id: 'DESK-EQUIPPED-22', agentId: null, name: 'Academy Eval Pod', zone: 'ACADEMY', icon: '📊', type: 'EQUIPPED' },
    { id: 'DESK-EQUIPPED-23', agentId: null, name: 'Opportunity Scout Desk', zone: 'ACADEMY', icon: '🔭', type: 'EQUIPPED' },
    { id: 'DESK-EQUIPPED-24', agentId: null, name: 'Economics Tracker', zone: 'STRATEGY', icon: '📈', type: 'EQUIPPED' },
    { id: 'DESK-EQUIPPED-25', agentId: null, name: 'Incident Responder Pod', zone: 'SERVER', icon: '🚒', type: 'EQUIPPED' },
    { id: 'DESK-FUTURE-26', agentId: null, name: 'Expansion Station Alpha', zone: 'FUTURE', icon: '🔮', type: 'FUTURE' },
    { id: 'DESK-FUTURE-27', agentId: null, name: 'Expansion Station Beta', zone: 'FUTURE', icon: '🔮', type: 'FUTURE' },
    { id: 'DESK-FUTURE-28', agentId: null, name: 'Expansion Station Gamma', zone: 'FUTURE', icon: '🔮', type: 'FUTURE' },
  ];

  return deskDefinitions.map(def => {
    if (def.type === 'FUTURE') {
      return { ...def, status: 'FUTURE_EXPANSION', state: 'FUTURE', task: 'Reserved for expansion', execution_class: 'UNKNOWN' };
    }

    if (!def.agentId) {
      return { ...def, status: 'AVAILABLE', state: 'READY', task: 'Available Workstation', execution_class: 'UNKNOWN' };
    }

    const agent = agents[def.agentId];
    if (!agent) {
      return { ...def, status: 'IDLE', state: 'IDLE', task: 'Standby', execution_class: 'UNKNOWN' };
    }

    const state = typeof agent.state === 'string' ? agent.state : 'IDLE';
    const isBusy = state === 'RUNNING' || state === 'COMPARING' || state === 'REVIEWING' || state === 'COORDINATING';
    const isBlocked = agent.blocked || bus.human_gate || state.includes('BLOCKED');

    return {
      ...def,
      status: isBlocked ? 'BLOCKED' : (isBusy ? 'ACTIVE' : 'IDLE'),
      state,
      task: agent.task || 'Standby',
      execution_class: resolveExecutionTruth(agent),
      progress: Number.isFinite(agent.progress) ? agent.progress : 0.0,
    };
  });
}

/**
 * Resolve Live HQ Master Overview metrics for the Large Dashboard / TV Wall.
 */
export function resolveLiveHQMetrics(stateData) {
  const desks = resolveDeskMatrix(stateData);
  const bus = stateData?.bus || {};
  const snapshot = stateData?.context_snapshot;

  let activeCount = 0;
  let idleCount = 0;
  let blockedCount = 0;
  let availableCount = 0;
  let futureCount = 0;

  for (const desk of desks) {
    if (desk.status === 'ACTIVE') activeCount++;
    else if (desk.status === 'BLOCKED') blockedCount++;
    else if (desk.status === 'IDLE') idleCount++;
    else if (desk.status === 'AVAILABLE') availableCount++;
    else if (desk.status === 'FUTURE_EXPANSION') futureCount++;
  }

  return {
    total_desks: desks.length,
    active_agents: activeCount,
    idle_agents: idleCount,
    blocked_agents: blockedCount,
    available_workstations: availableCount,
    future_workstations: futureCount,
    total_capacity: 40,
    chief_wait_state: resolveChiefWaitState(stateData),
    current_workflow: typeof bus.active_workflow === 'string' ? bus.active_workflow : 'IDLE_MONITORING',
    correlation_id: resolveCorrelationTruth(bus) || 'NONE',
    context_version: typeof snapshot?.context_version === 'number' ? snapshot.context_version : (bus.context_version || 0),
    system_health: blockedCount > 0 ? 'ATTENTION_REQUIRED' : (bus.is_locked ? 'OPERATIONAL_BUSY' : 'OPERATIONAL_HEALTHY'),
  };
}

// This is a static explanation of the architecture, not execution evidence.
export const ACADEMY_FLOW_STEPS = Object.freeze([
  'EXTERNAL FINDING',
  'AGENTENLEHRER',
  'LESSON',
  'SCHULDIREKTOR',
  'TEST / EVAL',
  'IDEA SYNC',
  'CHIEF',
  'UPDATE STEWARD',
  'NEW CONTEXT VERSION',
  'AFFECTED AGENT',
]);
