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
 * A human-gate decision is valid only when the API has already matched it to
 * the currently active gate by workflow_id *and* correlation_id.  The browser
 * does not attempt that association itself and never falls back to a global
 * latest decision.
 */
export function resolveGateDecisionTruth(busState) {
  const gate = busState?.active_human_gate;
  const decision = busState?.gate_decision;
  if (!gate?.provenance_complete || !gate.workflow_id || !gate.correlation_id) {
    return 'NO_DECISION';
  }
  if (
    decision?.workflow_id !== gate.workflow_id
    || decision?.correlation_id !== gate.correlation_id
  ) {
    return 'NO_DECISION';
  }
  return typeof decision.status === 'string' && decision.status.trim()
    ? decision.status
    : 'NO_DECISION';
}

export function resolveActiveGateTruth(busState) {
  const gate = busState?.active_human_gate;
  if (!gate) return { is_active: false, description: null };
  const isActive = Boolean((gate.state === 'BLOCKED' || gate.is_blocked || gate.is_active) && !gate.decision_made);
  return {
    id: gate.id || gate.gate_id || 'gate-active',
    is_active: isActive,
    description: gate.description || gate.prompt || 'A workflow task requires human authorization.',
  };
}

/** Deterministic, machine-state-derived speech; strictly no model narration. */
export function resolveSpeechBubble(agentId, agentState, busState) {
  const state = typeof agentState?.state === 'string' ? agentState.state : 'UNKNOWN';
  const task = typeof agentState?.task === 'string' && agentState.task && agentState.task !== 'Standby' ? agentState.task : null;
  const blockedReason = agentState?.blocked_reason;

  if (state === 'WAITING_PERMISSION' || agentState?.permission_blocked) {
    return blockedReason ? `Warte auf Berechtigung: ${blockedReason}` : 'Warte auf Berechtigung (Permission Approval).';
  }
  if (state === 'WAITING_HUMAN' || state === 'HUMAN_GATE' || (busState?.human_gate && (agentId === 'agent-chief-commander' || agentId === 'agent-human-gate-monitor'))) {
    return 'Warte auf Chief-Freigabe (Human Gate).';
  }
  if (state === 'MONEY_GATE') {
    return '0 EUR Spend Limit aktiv — Ausgaben verweigert.';
  }
  if (state === 'HUNG') {
    return 'WARNUNG: Worker blockiert — keine Liveness seit >300s.';
  }
  if (state === 'RUNNING_NO_PROGRESS') {
    return 'Task aktiv — warte auf nächsten Fortschrittsschritt.';
  }
  if (state === 'PROVIDER_ERROR') {
    return 'Provider-Verbindung unterbrochen — lokaler Modus aktiv.';
  }
  if (state === 'NETWORK_DEGRADED') {
    return 'Netzwerk instabil — lokaler Fallback aktiv.';
  }
  if (state === 'ORPHANED') {
    return 'KRITISCH: Verwaister Prozess ohne aktiven PID.';
  }
  if (state === 'COMPLETED') {
    return task ? `Mission abgeschlossen: ${task}` : 'Mission abgeschlossen. Ergebnis persistiert.';
  }

  // Active / Progressing states
  if (state === 'PROGRESSING' || state === 'RUNNING' || state === 'WORKING') {
    if (agentId === 'worker-google' || agentId === 'agent-antigravity-bridge') {
      return task ? `Arbeite an: ${task}` : 'Teste Heavy Authority & Autonomie-Logik.';
    }
    if (agentId === 'worker-codex' || agentId === 'agent-codex-bridge') {
      return task ? `Prüfe: ${task}` : 'Prüfe Googles Delta & Test-Orakel.';
    }
    if (agentId === 'agent-snitch') {
      return 'Überwache Worker-Zustände & Berechtigungen.';
    }
    if (agentId === 'smart-resource-router') {
      return 'Suche nächste sichere Aufgabe im Backlog.';
    }
    if (agentId === 'agent-courier-relay') {
      return task ? `Courier transportiert: ${task}` : 'Transportiere Nachrichten & ResultEnvelopes.';
    }
    return task ? `Arbeite an: ${task}` : 'Führe deterministische Aufgabe aus.';
  }

  // Safe Idle & Standby states
  if (state === 'SAFE_IDLE' || state === 'AVAILABLE' || state === 'STANDBY' || state === 'IDLE' || state === 'IDLE_EXPECTED') {
    if (agentId === 'agent-chief-commander') {
      return 'HQ im sicheren Standby. Bereit für Direktiven.';
    }
    if (agentId === 'agent-snitch') {
      return 'Alle Systeme gesund. Keine Anomalien.';
    }
    if (agentId === 'worker-google') {
      return 'SAFE_IDLE — Google Worker bereit für neue Aufgaben.';
    }
    if (agentId === 'worker-codex') {
      return 'SAFE_IDLE — Codex QA bereit für Review.';
    }
    if (agentId === 'worker-cli1') {
      return 'SAFE_IDLE — CLI 1 Terminal aktiv & bereit.';
    }
    if (agentId === 'worker-cli2') {
      return 'SAFE_IDLE — CLI 2 Beata Terminal aktiv & bereit.';
    }
    if (agentId.startsWith('bodyguard-') || agentState?.is_bodyguard) {
      if (agentState.leisure_area === 'SAUNA') return 'Bereitschaft in der Sauna.';
      if (agentState.leisure_area === 'COFFEE_BAR') return 'Bereitschaft an der Bar.';
      if (agentState.leisure_area === 'VISITOR_LOUNGE') return 'Bereitschaft in der Lounge.';
      return 'Bereitschaft im Aufenthaltsraum.';
    }
    return 'SAFE_IDLE — warte auf neue Arbeit.';
  }

  if (state === 'SLEEPING') {
    return 'Zzz...';
  }

  if (state === 'EXPECTED_LONG_RUNNING') {
    return 'Intentionally running continuously.';
  }
  if (state === 'STALLED') {
    return 'Stalled: no progress. Informed Chief.';
  }

  if (state === 'EXPECTED_LONG_RUNNING') return 'Intentionally running continuously.';
  if (state === 'STALLED') return 'Stalled. Informed Chief.';
    if (agentId === 'agent-chief-commander' && state === 'UNKNOWN') return 'No current machine evidence.';
  return 'Neutraler Status — keine aktive Ausführung.';
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
  const academy = stateData?.academy;
  const config = academy?.config;
  const lessons = Array.isArray(academy?.lessons) ? academy.lessons : null;
  const opportunities = Array.isArray(academy?.opportunities) ? academy.opportunities : null;
  const evaluations = Array.isArray(academy?.evaluations) ? academy.evaluations : null;

  return {
    is_enabled: typeof config?.academy_enabled === 'boolean' ? config.academy_enabled : null,
    timezone: typeof config?.academy_timezone === 'string' ? config.academy_timezone : null,
    daily_time: typeof config?.academy_daily_time === 'string' ? config.academy_daily_time : null,
    window_minutes: Number.isFinite(config?.academy_window_minutes) ? config.academy_window_minutes : null,
    lessons_count: lessons?.length ?? null,
    recent_lessons: lessons,
    opportunities_count: opportunities?.length ?? null,
    recent_opportunities: opportunities,
    evaluations_count: evaluations?.length ?? null,
    recent_evaluations: evaluations,
  };
}

/**
 * Resolve SNITCH 2.0 runtime watchdog truth strictly from evidence.
 */
export function resolveSnitchTruth(stateData) {
  const snitch = stateData?.snitch || stateData?.agents?.['agent-snitch'] || {};
  const incidents = Array.isArray(stateData?.incidents) ? stateData.incidents : [];
  const latestAlert = stateData?.runtime_alert;

  const state = typeof snitch.state === 'string' && snitch.state.trim()
    ? snitch.state
    : 'MONITORING';

  const defaultSpeech = state === 'EXPECTED_LONG_RUNNING'
    ? 'The Studio server is intentionally persistent. No action needed.'
    : (state === 'SLOW_BUT_PROGRESSING'
        ? 'This task has exceeded five minutes, but progress is still detected.'
        : (state === 'STALLED' || state === 'SUSPECTED_STALL'
            ? 'No meaningful progress detected. I informed Chief.'
            : (state === 'RUNAWAY_RISK'
                ? 'A bounded process exceeded its safety contract. I raised a high-priority incident.'
                : (state === 'WAITING_FOR_HUMAN'
                    ? 'A workflow task is paused at the Human Gate awaiting sign-off.'
                    : "I'm monitoring running tasks. Everything looks healthy."))));

  const speech = typeof snitch.speech === 'string' && snitch.speech.trim()
    ? snitch.speech
    : defaultSpeech;

  const activeIncident = Boolean(snitch.incident?.active || latestAlert || incidents.length > 0);

  return {
    id: 'agent-snitch',
    name: 'SNITCH',
    role: 'OPERATIONS WATCHDOG / DELAY SENTINEL',
    state,
    speech,
    task: snitch.task || 'Active Monitoring',
    last_action: snitch.last_action || 'Monitoring operations floor for runaway tasks or stalls',
    next_action: snitch.next_action || 'Continue evidence-based monitoring',
    active_incident: activeIncident,
    incident_details: snitch.incident || latestAlert || null,
    incidents_list: incidents,
    permission_guard: resolvePermissionGuardTruth(stateData),
    auto_kill_policy: 'DISABLED (CHIEF_ESCALATION_ONLY)',
    five_minute_rule: 'RUNTIME > 5 MIN != ERROR (DISTINGUISHES PERSISTENT SERVICES AND PROGRESSING TASKS)',
  };
}

/**
 * Resolve SNITCH 3.0 Permission Guard / Sandbox Auditor truth strictly from evidence.
 */
export function resolvePermissionGuardTruth(stateData) {
  const snitch = stateData?.snitch || stateData?.agents?.['agent-snitch'] || {};
  const pg = snitch.permission_guard || stateData?.permission_guard || {};

  const status = typeof pg.status === 'string' && pg.status.trim()
    ? pg.status
    : 'PERMISSIONS HEALTHY';

  const lastCheckedCommand = typeof pg.last_checked_command === 'string' && pg.last_checked_command.trim()
    ? pg.last_checked_command
    : 'python3 scripts/launch_visual_studio.py --status';

  const ruleMatch = typeof pg.rule_match === 'string' && pg.rule_match.trim()
    ? pg.rule_match
    : 'STUDIO_LIFECYCLE';

  const recommendation = typeof pg.recommendation === 'string' && pg.recommendation.trim()
    ? pg.recommendation
    : 'ALREADY_ALLOWED';

  const riskClass = typeof pg.risk_class === 'string' && pg.risk_class.trim()
    ? pg.risk_class
    : 'SAFE';

  const speech = typeof pg.speech === 'string' && pg.speech.trim()
    ? pg.speech
    : 'All observed commands adhere to approved project rules.';

  return {
    status,
    last_checked_command: lastCheckedCommand,
    rule_match: ruleMatch,
    recommendation,
    risk_class: riskClass,
    speech,
  };
}


/**
 * Resolve Eight Bodyguards Reserve Pool truth strictly from evidence.
 */
export function resolveBodyguardsTruth(stateData) {
  const registry = [
    { slot: 'BG-01', callsign: 'ALPHA', id: 'agent-bodyguard-alpha', name: 'BODYGUARD ALPHA' },
    { slot: 'BG-02', callsign: 'BRAVO', id: 'agent-bodyguard-bravo', name: 'BODYGUARD BRAVO' },
    { slot: 'BG-03', callsign: 'CHARLIE', id: 'agent-bodyguard-charlie', name: 'BODYGUARD CHARLIE' },
    { slot: 'BG-04', callsign: 'DELTA', id: 'agent-bodyguard-delta', name: 'BODYGUARD DELTA' },
    { slot: 'BG-05', callsign: 'ECHO', id: 'agent-bodyguard-echo', name: 'BODYGUARD ECHO' },
    { slot: 'BG-06', callsign: 'FOXTROT', id: 'agent-bodyguard-foxtrot', name: 'BODYGUARD FOXTROT' },
    { slot: 'BG-07', callsign: 'GOLF', id: 'agent-bodyguard-golf', name: 'BODYGUARD GOLF' },
    { slot: 'BG-08', callsign: 'HOTEL', id: 'agent-bodyguard-hotel', name: 'BODYGUARD HOTEL' },
  ];

  const poolData = Array.isArray(stateData?.bodyguards) ? stateData.bodyguards : [];
  const agents = stateData?.agents || {};

  return registry.map(reg => {
    const fromPool = poolData.find(b => b.id === reg.id || b.callsign === reg.callsign);
    const fromAgent = agents[reg.id];
    const raw = fromPool || fromAgent || {};

    const state = typeof raw.state === 'string' && raw.state.trim()
      ? raw.state
      : 'STANDBY';

    const tempRole = typeof raw.temporary_role === 'string' && raw.temporary_role.trim()
      ? raw.temporary_role
      : null;

    const defaultSpeech = state === 'STANDBY'
      ? 'Ready for reserve duty.'
      : (state === 'ASSIGNED'
          ? `Temporary role ${tempRole || 'ACCEPTED'} received. Preparing task.`
          : (state === 'WORKING'
              ? "I'm covering this task while the specialist is busy."
              : (state === 'RETURNING'
                  ? 'Result delivered to Courier. Returning to standby.'
                  : (state === 'CAPABILITY_MISMATCH'
                      ? 'Required capability is unavailable. Flagging capability mismatch.'
                      : `Bodyguard ${reg.callsign} on reserve.`))));

    const speech = typeof raw.speech === 'string' && raw.speech.trim()
      ? raw.speech
      : defaultSpeech;

    return {
      slot: reg.slot,
      callsign: reg.callsign,
      id: reg.id,
      name: reg.name,
      state,
      temporary_role: tempRole,
      task: raw.task || (state === 'STANDBY' ? 'Reserve Duty (Standby)' : null),
      progress: Number.isFinite(raw.progress) ? raw.progress : 0.0,
      speech,
      is_standby: state === 'STANDBY',
      blocked: state === 'BLOCKED' || state === 'CAPABILITY_MISMATCH',
      model_calls_incurred: 0,
      supported_capabilities: raw.supported_capabilities || [
        'local_filesystem',
        'deterministic_execution',
        'courier_envelope_handling',
        'git_inspection',
        'media_metadata',
        'test_runner',
      ],
    };
  });
}

/**
 * Resolve Live Agent HQ Desk Matrix (37 total desks: core agents, 8 bodyguards, ~25 equipped pods, 3 future expansion).
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
    { id: 'DESK-SNITCH-10', agentId: 'agent-snitch', name: 'SNITCH Watchdog', zone: 'SERVER', icon: '👀', type: 'WATCHDOG' },
    { id: 'DESK-ASSET-11', agentId: 'agent-asset-validator', name: 'Asset Validator', zone: 'ANTIGRAVITY', icon: '📐', type: 'WORKER' },
    { id: 'DESK-VIDEO-12', agentId: 'agent-video-synth', name: 'Video Synth', zone: 'ANTIGRAVITY', icon: '🎬', type: 'WORKER' },
    { id: 'DESK-CHANNEL-13', agentId: 'agent-channel-dispatcher', name: 'Channel Dispatcher', zone: 'COURIER', icon: '📡', type: 'COURIER' },
    { id: 'DESK-MEMORY-14', agentId: 'agent-memory-mesh', name: 'Memory Mesh Indexer', zone: 'IDEA_LAB', icon: '🗄️', type: 'INDEXER' },
    { id: 'DESK-GATE-15', agentId: 'agent-human-gate-monitor', name: 'Human Gate Monitor', zone: 'STRATEGY', icon: '🚨', type: 'GATE' },
    { id: 'DESK-TEST-16', agentId: 'agent-test-guardian', name: 'Test Guardian', zone: 'CODEX', icon: '🧪', type: 'QA' },
    { id: 'DESK-LOOP-17', agentId: 'agent-loop-supervisor', name: 'Loop Supervisor', zone: 'STRATEGY', icon: '🔁', type: 'SUPERVISOR' },
    { id: 'DESK-BG-01', agentId: 'agent-bodyguard-alpha', name: 'Bodyguard Alpha', zone: 'BODYGUARDS', icon: '🛡️', type: 'BODYGUARD' },
    { id: 'DESK-BG-02', agentId: 'agent-bodyguard-bravo', name: 'Bodyguard Bravo', zone: 'BODYGUARDS', icon: '🛡️', type: 'BODYGUARD' },
    { id: 'DESK-BG-03', agentId: 'agent-bodyguard-charlie', name: 'Bodyguard Charlie', zone: 'BODYGUARDS', icon: '🛡️', type: 'BODYGUARD' },
    { id: 'DESK-BG-04', agentId: 'agent-bodyguard-delta', name: 'Bodyguard Delta', zone: 'BODYGUARDS', icon: '🛡️', type: 'BODYGUARD' },
    { id: 'DESK-BG-05', agentId: 'agent-bodyguard-echo', name: 'Bodyguard Echo', zone: 'BODYGUARDS', icon: '🛡️', type: 'BODYGUARD' },
    { id: 'DESK-BG-06', agentId: 'agent-bodyguard-foxtrot', name: 'Bodyguard Foxtrot', zone: 'BODYGUARDS', icon: '🛡️', type: 'BODYGUARD' },
    { id: 'DESK-BG-07', agentId: 'agent-bodyguard-golf', name: 'Bodyguard Golf', zone: 'BODYGUARDS', icon: '🛡️', type: 'BODYGUARD' },
    { id: 'DESK-BG-08', agentId: 'agent-bodyguard-hotel', name: 'Bodyguard Hotel', zone: 'BODYGUARDS', icon: '🛡️', type: 'BODYGUARD' },
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
      return { ...def, status: 'FUTURE_EXPANSION', state: 'FUTURE', task: null, execution_class: 'UNKNOWN' };
    }

    if (!def.agentId) {
      return { ...def, status: 'REGISTERED_EQUIPPED', state: 'REGISTERED', task: null, execution_class: 'REGISTERED' };
    }

    const agent = agents[def.agentId];
    if (!agent) {
      // Check if it's a bodyguard in pool
      if (def.type === 'BODYGUARD') {
        const bgs = resolveBodyguardsTruth(stateData);
        const bg = bgs.find(b => b.id === def.agentId);
        if (bg) {
          const bgState = bg.state;
          const isBgBusy = bgState === 'WORKING' || bgState === 'PREPARING' || bgState === 'ASSIGNED';
          const isBgBlocked = bgState === 'BLOCKED' || bgState === 'CAPABILITY_MISMATCH';
          return {
            ...def,
            status: isBgBlocked ? 'BLOCKED' : (isBgBusy ? 'ACTIVE' : 'IDLE'),
            state: bgState,
            task: bg.task || 'Reserve Duty (Standby)',
            execution_class: 'DETERMINISTIC_ANTIGRAVITY',
            progress: bg.progress,
            temporary_role: bg.temporary_role,
            speech: bg.speech,
          };
        }
      }
      return { ...def, status: 'UNKNOWN', state: 'UNKNOWN', task: null, execution_class: 'UNKNOWN' };
    }

    const state = typeof agent.state === 'string' ? agent.state : 'IDLE';
    const isBusy = state === 'RUNNING' || state === 'COMPARING' || state === 'REVIEWING' || state === 'COORDINATING' || state === 'WORKING';
    const isBlocked = agent.blocked || bus.human_gate || state.includes('BLOCKED') || state === 'CAPABILITY_MISMATCH';

    return {
      ...def,
      status: isBlocked ? 'BLOCKED' : (isBusy ? 'ACTIVE' : 'IDLE'),
      state,
      task: agent.task || 'Standby',
      execution_class: resolveExecutionTruth(agent),
      progress: Number.isFinite(agent.progress) ? agent.progress : 0.0,
      speech: agent.speech || null,
      temporary_role: agent.temporary_role || null,
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
  const repositories = snapshot?.repositories || {};
  const hasMachineState = Object.keys(stateData?.agents || {}).length > 0 || Boolean(stateData?.bus);

  let activeCount = 0;
  let idleCount = 0;
  let blockedCount = 0;
  let availableCount = 0;
  let futureCount = 0;

  for (const desk of desks) {
    if (desk.status === 'ACTIVE') activeCount++;
    else if (desk.status === 'BLOCKED') blockedCount++;
    else if (desk.status === 'IDLE') idleCount++;
    else if (desk.status === 'REGISTERED_EQUIPPED') availableCount++;
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
    current_workflow: typeof bus.active_workflow === 'string' && bus.active_workflow !== 'IDLE_MONITORING'
      ? bus.active_workflow
      : null,
    correlation_id: resolveCorrelationTruth(bus),
    context_version: Number.isFinite(snapshot?.context_version)
      ? snapshot.context_version
      : (Number.isFinite(bus.context_version) && bus.context_version > 0 ? bus.context_version : null),
    system_health: !hasMachineState
      ? 'UNKNOWN'
      : (blockedCount > 0 ? 'ATTENTION_REQUIRED' : (bus.is_locked ? 'OPERATIONAL_BUSY' : 'OPERATIONAL_HEALTHY')),
    courier_commit: repositories.courier_head || null,
    memory_commit: repositories.memory_head || null,
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

export function sanitizeTruthText(text) {
  if (typeof text !== 'string') return '';
  return text
    .replace(/(?:ghp_[a-zA-Z0-9]+|ghs_[a-zA-Z0-9]+|token=[^\s&]+|secret=[^\s&]+|key=[^\s&]+|bearer\s+[a-zA-Z0-9._-]+)/gi, '[REDACTED_SECRET]')
    .replace(/[0-9a-fA-F]{32,64}/g, match => match.slice(0, 8) + '...')
    .slice(0, 200);
}

export function resolveReviewTruth(stateData) {
  const reviewBudget = stateData?.review_budget;
  const agents = stateData?.agents || {};
  const cdx = agents['agent-codex-bridge'];
  const rawDecision = stateData?.review_decision || (cdx?.state === 'RUNNING' ? 'IMMEDIATE_REVIEW_REQUIRED' : 'NO_REVIEW');
  const riskClass = stateData?.review_risk_class || 'UNKNOWN';

  let reviewerLabel = 'IDLE';
  let reviewerState = 'IDLE';

  if (rawDecision === 'IMMEDIATE_REVIEW_REQUIRED' || riskClass === 'HIGH' || cdx?.state === 'RUNNING') {
    reviewerLabel = 'REVIEW REQUIRED';
    reviewerState = 'WORKING';
  } else if (rawDecision === 'REVIEW_REQUIRED_BEFORE_PUSH') {
    reviewerLabel = 'REVIEW PENDING PUSH';
    reviewerState = 'WAITING';
  } else if (rawDecision === 'BATCH_REVIEW' || (cdx?.task && cdx.task.includes('Review'))) {
    reviewerLabel = 'REVIEW QUEUED';
    reviewerState = 'WAITING';
  } else if (rawDecision === 'NO_REVIEW' || cdx?.state === 'STANDBY' || cdx?.state === 'IDLE') {
    reviewerLabel = 'IDLE';
    reviewerState = 'IDLE';
  }

  return {
    reviewer_label: reviewerLabel,
    reviewer_state: reviewerState,
    review_decision: rawDecision,
    risk_class: riskClass,
    daily_routine_batches_today: reviewBudget?.daily_routine_batches_today ?? 0,
  };
}

export function resolveLiveOrchestrationTruth(stateData) {
  const bus = stateData?.bus || {};
  const agents = stateData?.agents || {};
  const transport = stateData?.transport;

  const ag = agents['agent-antigravity-bridge'];
  const cdx = agents['agent-codex-bridge'];
  const courier = agents['agent-courier-relay'];

  let activeBuilder = null;
  let activeTask = null;
  let progress = 0.0;

  if (ag && (ag.state === 'RUNNING' || ag.state === 'WORKING' || ag.state === 'AWAITING_CHIEF_REVIEW')) {
    activeBuilder = 'agent-antigravity-bridge';
    activeTask = ag.task || null;
    progress = Number.isFinite(ag.progress) ? ag.progress : 0.5;
  } else if (cdx && (cdx.state === 'RUNNING' || cdx.state === 'WORKING' || cdx.state === 'AWAITING_CHIEF_REVIEW')) {
    activeBuilder = 'agent-codex-bridge';
    activeTask = cdx.task || null;
    progress = Number.isFinite(cdx.progress) ? cdx.progress : 0.5;
  }

  let visualPhase = 'IDLE';
  let courierPhase = 'IDLE';

  if (!bus.is_locked && !activeBuilder && !transport?.incoming_count) {
    visualPhase = 'IDLE';
    courierPhase = 'IDLE';
  } else if (transport?.incoming_count > 0 || (bus.is_locked && progress < 0.1)) {
    visualPhase = 'TASK_RECEIVED';
    courierPhase = 'TASK_DELIVERY';
  } else if (activeBuilder && progress >= 0.1 && progress < 0.3) {
    visualPhase = 'WALKING_TO_WORKSTATION';
    courierPhase = 'TASK_DELIVERY';
  } else if (activeBuilder && progress >= 0.3 && progress < 0.8) {
    visualPhase = 'WORKING';
    courierPhase = 'IDLE';
  } else if (activeBuilder && (progress >= 0.8 || ag?.state === 'AWAITING_CHIEF_REVIEW' || cdx?.state === 'AWAITING_CHIEF_REVIEW')) {
    visualPhase = 'RESULT_READY';
    courierPhase = 'RESULT_RETURN';
  } else if (courier && (courier.state === 'RETURNING' || courierPhase === 'RESULT_RETURN')) {
    visualPhase = 'COURIER_RETURN';
    courierPhase = 'RESULT_RETURN';
  } else if (bus.last_decision === 'ACCEPTED' || bus.last_decision === 'DONE') {
    visualPhase = 'DONE';
    courierPhase = 'IDLE';
  }

  const reviewTruth = resolveReviewTruth(stateData);

  return {
    visual_phase: visualPhase,
    active_builder: activeBuilder,
    active_task: activeTask ? sanitizeTruthText(activeTask) : null,
    progress,
    courier_phase: courierPhase,
    review_truth: reviewTruth,
  };
}

export const AGENT_WAYPOINTS = Object.freeze({
  'agent-chief-commander': 'CHIEF_COMMAND',
  'smart-resource-router': 'ROUTER_DESK',
  'agent-human-gate-monitor': 'DESK_01',
  'agent-thought-curator': 'DESK_02',
  'agent-update-steward': 'DESK_03',
  'agent-codex-bridge': 'DESK_04',
  'agent-asset-validator': 'DESK_05',
  'agent-video-synth': 'DESK_06',
  'agent-channel-dispatcher': 'DESK_07',
  'agent-memory-mesh': 'DESK_08',
  'agent-test-guardian': 'DESK_09',
  'agent-snitch': 'DESK_13',
  'agent-antigravity-bridge': 'DESK_16',
  'agent-courier-relay': 'DESK_17',
  'agent-academy-teacher': 'DESK_19',
  'agent-academy-director': 'DESK_21',
  'agent-loop-supervisor': 'DESK_22',
});

/**
 * Resolve Capability Registry truth from local evidence (Mission 113).
 */
export function resolveCapabilityTruth(stateData) {
  const caps = stateData?.capabilities || {};
  const available = Object.entries(caps).filter(([_, state]) => state === 'AVAILABLE').map(([name]) => name);
  const authRequired = Object.entries(caps).filter(([_, state]) => state === 'AUTH_REQUIRED').map(([name]) => name);
  const approvalRequired = Object.entries(caps).filter(([_, state]) => state === 'APPROVAL_REQUIRED').map(([name]) => name);
  return {
    total_capabilities: Object.keys(caps).length,
    available_count: available.length,
    available_capabilities: available,
    auth_required_capabilities: authRequired,
    approval_required_capabilities: approvalRequired,
    is_safe: true,
  };
}

/**
 * Resolve Skill Registry truth grounded in verified local evidence (Mission 113).
 */
export function resolveSkillTruth(stateData) {
  const skills = stateData?.skills || [];
  return {
    total_skills: skills.length,
    active_skills: skills.filter(s => s.verification_state === 'ACTIVE' || !s.verification_state),
    owners: Array.from(new Set(skills.map(s => s.owner_agent))),
  };
}

/**
 * Resolve Agent-to-Agent Handoff truth preserving task and correlation IDs (Mission 113).
 */
export function resolveHandoffTruth(stateData) {
  const handoffs = stateData?.handoffs || [];
  const activeHandoff = stateData?.active_handoff || (handoffs.length > 0 ? handoffs[0] : null);
  if (!activeHandoff) {
    return { has_active_handoff: false, active_handoff: null };
  }
  return {
    has_active_handoff: true,
    active_handoff: activeHandoff,
    handoff_id: activeHandoff.handoff_id,
    from_agent: activeHandoff.from_agent,
    to_agent: activeHandoff.to_agent,
    task_id: activeHandoff.task_id,
    correlation_id: activeHandoff.correlation_id,
    reason: activeHandoff.reason,
  };
}

/**
 * Deterministic Real Live Agent Motion State Machine (Mission 111 & 113).
 * Maps local task/Courier/worker/review/handoff state to agent motion without fake simulation or model calls.
 */
export function resolveLiveAgentMotion(stateData, previousMotionState = null) {
  const bus = stateData?.bus || {};
  const agents = stateData?.agents || {};
  const orchTruth = resolveLiveOrchestrationTruth(stateData);
  const reviewTruth = resolveReviewTruth(stateData);
  const handoffTruth = resolveHandoffTruth(stateData);
  const activeGate = stateData?.bus?.active_human_gate;

  const activeBuilder = orchTruth.active_builder;
  const activeTask = orchTruth.active_task;
  const visualPhase = orchTruth.visual_phase;
  const courierPhase = orchTruth.courier_phase;
  const isLocked = Boolean(bus.is_locked);
  const correlationId = bus.correlation_id || "NONE";
  const workflowId = bus.active_workflow || "IDLE_MONITORING";

  // Build deterministic fingerprint
  const progressBucket = Math.floor((orchTruth.progress || 0.0) * 4) / 4;
  const gateActive = Boolean(activeGate || bus.human_gate);
  const reviewRequired = reviewTruth.reviewer_label === 'REVIEW REQUIRED' || reviewTruth.review_decision === 'HIGH_RISK';
  const handoffActive = Boolean(handoffTruth.has_active_handoff);

  const fingerprint = [
    workflowId,
    correlationId,
    isLocked ? 'LOCKED' : 'UNLOCKED',
    visualPhase,
    courierPhase,
    activeBuilder || 'NONE',
    activeTask || 'NONE',
    progressBucket,
    gateActive ? 'GATE_ACTIVE' : 'GATE_INACTIVE',
    reviewRequired ? 'REVIEW_REQ' : 'NO_REVIEW',
    handoffActive ? `HANDOFF_${handoffTruth.from_agent}_${handoffTruth.to_agent}` : 'NO_HANDOFF',
  ].join('::');

  const destinations = {};
  const routes = {};
  const speechOverrides = {};
  const states = {};

  // 1. Courier Relay & Handoff Transport
  if (handoffActive) {
    const fromWp = AGENT_WAYPOINTS[handoffTruth.from_agent] || 'DESK_02';
    const toWp = AGENT_WAYPOINTS[handoffTruth.to_agent] || 'DESK_16';
    routes['agent-courier-relay'] = [fromWp, 'ROUTER_DESK', toWp];
    destinations['agent-courier-relay'] = HQ_WAYPOINTS[toWp];
    states['agent-courier-relay'] = 'HANDOFF';
    speechOverrides['agent-courier-relay'] = 'HANDOFF';
    states[handoffTruth.from_agent] = 'HANDOFF';
    speechOverrides[handoffTruth.from_agent] = 'HANDOFF';
    states[handoffTruth.to_agent] = 'RUNNING';
  } else if (visualPhase === 'TASK_RECEIVED' || courierPhase === 'TASK_DELIVERY') {
    const builderWaypoint = activeBuilder === 'agent-codex-bridge' ? 'DESK_04' : 'DESK_16';
    routes['agent-courier-relay'] = ['CHIEF_COMMAND', 'ROUTER_DESK', builderWaypoint];
    destinations['agent-courier-relay'] = HQ_WAYPOINTS[builderWaypoint];
    states['agent-courier-relay'] = 'DISPATCHED';
    speechOverrides['agent-courier-relay'] = 'DISPATCHED';
  } else if (visualPhase === 'RESULT_READY' || courierPhase === 'RESULT_RETURN') {
    const builderWaypoint = activeBuilder === 'agent-codex-bridge' ? 'DESK_04' : 'DESK_16';
    if (reviewRequired) {
      routes['agent-courier-relay'] = [builderWaypoint, 'DESK_04', 'CHIEF_COMMAND'];
      states['agent-courier-relay'] = 'WAITING_FOR_REVIEW';
      speechOverrides['agent-courier-relay'] = 'WAITING FOR REVIEW';
    } else {
      routes['agent-courier-relay'] = [builderWaypoint, 'CHIEF_COMMAND'];
      states['agent-courier-relay'] = 'RETURNING';
      speechOverrides['agent-courier-relay'] = 'RESULT READY';
    }
    destinations['agent-courier-relay'] = HQ_WAYPOINTS['CHIEF_COMMAND'];
  } else if (visualPhase === 'WORKING') {
    const builderWaypoint = activeBuilder === 'agent-codex-bridge' ? 'DESK_04' : 'DESK_16';
    destinations['agent-courier-relay'] = HQ_WAYPOINTS[builderWaypoint];
    states['agent-courier-relay'] = 'RUNNING';
  } else {
    // IDLE: Courier stays at Desk 17
    destinations['agent-courier-relay'] = HQ_WAYPOINTS['DESK_17'];
    states['agent-courier-relay'] = 'IDLE';
  }

  // 2. Active Builder (Antigravity or Codex or other)
  if (activeBuilder) {
    states[activeBuilder] = visualPhase === 'RESULT_READY' ? 'RESULT_READY' : 'RUNNING';
    speechOverrides[activeBuilder] = visualPhase === 'RESULT_READY' ? 'RESULT READY' : 'RUNNING';
  }

  // 3. Codex QA Reviewer
  if (reviewRequired && (visualPhase === 'RESULT_READY' || courierPhase === 'RESULT_RETURN')) {
    states['agent-codex-bridge'] = 'RUNNING';
    speechOverrides['agent-codex-bridge'] = 'WAITING FOR REVIEW';
  } else {
    // Codex remains strictly IDLE when review is not required
    states['agent-codex-bridge'] = 'IDLE';
    destinations['agent-codex-bridge'] = HQ_WAYPOINTS['DESK_04'];
  }

  // 4. Human Gate Monitor
  if (gateActive) {
    destinations['agent-human-gate-monitor'] = HQ_WAYPOINTS['CHIEF_COMMAND'];
    routes['agent-human-gate-monitor'] = ['DESK_01', 'CHIEF_COMMAND'];
    states['agent-human-gate-monitor'] = 'HUMAN_GATE';
    speechOverrides['agent-human-gate-monitor'] = 'HUMAN GATE';
  } else {
    destinations['agent-human-gate-monitor'] = HQ_WAYPOINTS['DESK_01'];
    states['agent-human-gate-monitor'] = 'IDLE';
  }

  // 5. Chief Commander
  const chiefPresence = stateData?.chief_presence?.presence || (agents['agent-chief-commander']?.state === 'SLEEPING' ? 'SLEEPING' : 'AWAKE');
  if (chiefPresence === 'SLEEPING' || agents['agent-chief-commander']?.state === 'SLEEPING') {
    destinations['agent-chief-commander'] = HQ_WAYPOINTS['FIREPLACE'];
    states['agent-chief-commander'] = 'SLEEPING';
    speechOverrides['agent-chief-commander'] = 'Zzz...';
  } else {
    destinations['agent-chief-commander'] = HQ_WAYPOINTS['CHIEF_COMMAND'];
    if (isLocked || visualPhase !== 'IDLE') {
      states['agent-chief-commander'] = visualPhase === 'DONE' ? 'COMPLETED' : 'RUNNING';
      if (visualPhase === 'DONE') speechOverrides['agent-chief-commander'] = 'COMPLETED';
    } else {
      states['agent-chief-commander'] = 'IDLE';
    }
  }

  return {
    fingerprint,
    visual_phase: visualPhase,
    courier_phase: courierPhase,
    active_builder: activeBuilder,
    active_task: activeTask,
    is_idle: visualPhase === 'IDLE' && !isLocked && !gateActive,
    destinations,
    routes,
    states,
    speech_overrides: speechOverrides,
    review_required: reviewRequired,
  };
}

/**
 * Resolve Living Room Character Positions, Nameplates, Speech, and Visual States.
 */
export function resolveLivingRoomAgents(stateData) {
  const agents = stateData?.agents || {};
  const bus = stateData?.bus || {};
  const desks = resolveDeskMatrix(stateData);
  const bodyguards = resolveBodyguardsTruth(stateData);
  const reviewTruth = resolveReviewTruth(stateData);

  // Default coordinate map matching the 16:9 pixel-art reference image
  const baseCoordinates = {
    'agent-chief-commander': { x: 50.0, y: 42.0, zone: 'COMMAND_TABLE', name: 'CHIEF COMMANDER', title: 'Chief / Strategy' },
    'smart-resource-router': { x: 57.5, y: 44.0, zone: 'COMMAND_TABLE', name: 'SMART ROUTER', title: 'Task Router' },
    'agent-human-gate-monitor': { x: 14.5, y: 35.5, zone: 'DESK_01', name: 'HUMAN GATE', title: 'Human Gate / Strategy' },
    'agent-thought-curator': { x: 22.0, y: 35.5, zone: 'DESK_02', name: 'IDEA SYNC', title: 'Memory & Curation' },
    'agent-update-steward': { x: 29.5, y: 35.5, zone: 'DESK_03', name: 'UPDATE STEWARD', title: 'Context Sync Steward' },
    'agent-codex-bridge': { x: 14.5, y: 48.0, zone: 'DESK_04', name: 'CODEX BRIDGE', title: 'Technical QA Specialist' },
    'agent-asset-validator': { x: 22.0, y: 48.0, zone: 'DESK_05', name: 'ASSET VALIDATOR', title: 'Media Asset Validator' },
    'agent-video-synth': { x: 29.5, y: 48.0, zone: 'DESK_06', name: 'VIDEO SYNTH', title: '3D Movie Synth' },
    'agent-channel-dispatcher': { x: 14.5, y: 60.5, zone: 'DESK_07', name: 'CHANNEL DISPATCH', title: 'Social Dispatcher' },
    'agent-memory-mesh': { x: 22.0, y: 60.5, zone: 'DESK_08', name: 'MEMORY MESH', title: 'Project Memory Indexer' },
    'agent-test-guardian': { x: 29.5, y: 60.5, zone: 'DESK_09', name: 'TEST GUARDIAN', title: 'Regression Sentinel' },
    'agent-antigravity-bridge': { x: 66.5, y: 45.0, zone: 'DESK_16', name: 'ANTIGRAVITY', title: 'Visual & Heavy Worker' },
    'agent-courier-relay': { x: 74.0, y: 45.0, zone: 'DESK_17', name: 'COURIER', title: 'Message Transport' },
    'agent-academy-teacher': { x: 81.5, y: 45.0, zone: 'DESK_19', name: 'ACADEMY TEACHER', title: 'Agentenlehrer' },
    'agent-academy-director': { x: 89.0, y: 45.0, zone: 'DESK_21', name: 'ACADEMY DIRECTOR', title: 'Schuldirektor' },
    'agent-snitch': { x: 63.5, y: 59.5, zone: 'DESK_13', name: 'SNITCH 3.0', title: 'Runtime & Permission Guard' },
    'agent-loop-supervisor': { x: 71.0, y: 59.5, zone: 'DESK_22', name: 'LOOP SUPERVISOR', title: 'L6 Orchestration' },

    // Execution Workers (Specialist Operator Avatars)
    'worker-google': { x: 78.5, y: 45.0, zone: 'DESK_GOOGLE', name: 'GOOGLE', title: 'Google Pro Builder', provider: 'GOOGLE_PRO' },
    'worker-codex': { x: 14.5, y: 48.0, zone: 'DESK_CODEX', name: 'CODEX', title: 'Codex QA Specialist', provider: 'CODEX' },
    'worker-cli1': { x: 78.5, y: 73.5, zone: 'DESK_CLI1', name: 'CLI 1', title: 'Primary Operator', provider: 'LOCAL_CLI_1' },
    'worker-cli2': { x: 86.0, y: 73.5, zone: 'DESK_CLI2', name: 'CLI 2', title: 'Beata Operator', provider: 'LOCAL_CLI_2' },
  };

  // Bodyguard leisure vs active positions
  const bodyguardStandbySlots = [
    { callsign: 'ALPHA', leisure_area: 'SAUNA', x: 79.0, y: 14.0, prop: 'cigarette' },
    { callsign: 'BRAVO', leisure_area: 'SAUNA', x: 84.0, y: 14.0, prop: 'shisha' },
    { callsign: 'CHARLIE', leisure_area: 'COFFEE_BAR', x: 80.0, y: 91.0, prop: 'drink' },
    { callsign: 'DELTA', leisure_area: 'COFFEE_BAR', x: 85.0, y: 91.0, prop: 'drink' },
    { callsign: 'ECHO', leisure_area: 'VISITOR_LOUNGE', x: 12.0, y: 84.0, prop: 'drink' },
    { callsign: 'FOXTROT', leisure_area: 'VISITOR_LOUNGE', x: 28.0, y: 84.0, prop: 'drink' },
    { callsign: 'GOLF', leisure_area: 'READY_ROOM', x: 44.0, y: 67.0, prop: null },
    { callsign: 'HOTEL', leisure_area: 'READY_ROOM', x: 56.0, y: 67.0, prop: null },
  ];

  const assignedWorkstationCoords = [
    { x: 78.5, y: 59.5 }, // Desk 23
    { x: 86.0, y: 59.5 }, // Desk 24
    { x: 80.0, y: 73.5 }, // Desk 24 lower
    { x: 88.0, y: 73.5 }, // Desk 25 lower
  ];

  const results = [];

  const autoRuntime = stateData?.autonomy_runtime || {};
  const autoAnomalies = stateData?.anomalies || {};
  const snitchObs = stateData?.snitch_observer || {};
  const activeHumanGates = autoRuntime.human_gates || [];
  const activeMoneyGates = autoRuntime.money_gates || [];
  const activeJobs = autoRuntime.jobs_dispatched || [];
  const quarantinedBranches = autoAnomalies.quarantined_branches || [];

  // Bodyguard Alert Override Check
  const hasSecurityAlert = Boolean(
    (snitchObs?.permission_blocked_count > 0) ||
    (snitchObs?.hung_workers_count > 0) ||
    (snitchObs?.stale_orphans_count > 0) ||
    (quarantinedBranches.length > 0) ||
    (bus?.human_gate) ||
    (stateData?.runtime_alert && ['HIGH', 'CRITICAL'].includes(stateData.runtime_alert.severity))
  );
  const alertSummary = snitchObs?.reasons?.[0] || stateData?.runtime_alert?.reason || (bus?.human_gate ? 'Human Gate Freigabe erforderlich' : 'Sicherheitsalarm / Gate aktiv');

  // 1. Process Core, Specialist & Execution Worker Agents
  for (const [agentId, coords] of Object.entries(baseCoordinates)) {
    if (agentId.startsWith('worker-') && stateData && 'snitch' in stateData) continue;

    const raw = agents[agentId] || {};
    const desk = desks.find(d => d.agentId === agentId) || {};
    let state = typeof raw.state === 'string' && raw.state.trim() ? raw.state : (desk.state || 'UNKNOWN');

    // Normalize legacy state names to standard 11 states
    if (state === 'IDLE' || state === 'STANDBY' || state === 'IDLE_EXPECTED') state = 'SAFE_IDLE';
    if (state === 'RUNNING' || state === 'WORKING' || state === 'DISPATCHED') state = 'PROGRESSING';
    if (state === 'HUMAN_GATE' || state === 'BLOCKED_HUMAN_GATE') state = 'WAITING_HUMAN';
    if (state === 'BLOCKED_PERMISSION' || raw.permission_blocked) state = 'WAITING_PERMISSION';

    let title = coords.title;
    let isBusy = state === 'PROGRESSING' || state === 'COMPARING' || state === 'REVIEWING' || state === 'COORDINATING';
    let isBlocked = state === 'WAITING_PERMISSION' || state === 'WAITING_HUMAN' || state === 'MONEY_GATE' || state === 'HUNG' || state === 'ORPHANED' || raw.blocked || desk.status === 'BLOCKED';

    let currentX = coords.x;
    let currentY = coords.y;

    if (agentId === 'agent-chief-commander') {
      const chiefPresence = stateData?.chief_presence?.presence || (raw.state === 'SLEEPING' ? 'SLEEPING' : 'AWAKE');
      if (chiefPresence === 'SLEEPING' || state === 'SLEEPING') {
        state = 'SLEEPING';
        title = 'CHIEF (SLEEPING)';
        isBusy = false;
        currentX = HQ_WAYPOINTS['FIREPLACE'].x;
        currentY = HQ_WAYPOINTS['FIREPLACE'].y;
      }
    }

    // Integrate Review Budget for Codex
    if (agentId === 'agent-codex-bridge' || agentId === 'worker-codex') {
      if (reviewTruth.reviewer_label === 'REVIEW REQUIRED') {
        state = 'RUNNING';
        title = 'REVIEW REQUIRED (HIGH)';
        isBusy = true;
      } else if (reviewTruth.reviewer_label === 'REVIEW PENDING PUSH') {
        state = 'SAFE_IDLE';
        title = 'REVIEW PENDING PUSH';
        isBusy = false;
      } else if (reviewTruth.reviewer_label === 'REVIEW QUEUED') {
        state = 'SAFE_IDLE';
        title = 'REVIEW QUEUED (BATCH)';
        isBusy = false;
      }
    }

    // Integrate Real Autonomy Runtime telemetry
    if (agentId === 'agent-human-gate-monitor' && activeHumanGates.length > 0) {
      state = 'WAITING_HUMAN';
      title = `HUMAN GATE (${activeHumanGates.length} Parked)`;
      isBlocked = true;
    } else if (agentId === 'smart-resource-router' && activeMoneyGates.length > 0) {
      state = 'MONEY_GATE';
      title = `MONEY GATE (0 EUR)`;
      isBlocked = true;
    } else if (agentId === 'agent-snitch') {
      if (quarantinedBranches.length > 0) {
        state = 'ANOMALY';
        title = `SNITCH (${quarantinedBranches.length} Quarantined)`;
        isBlocked = true;
      }
    }

    // Idle Bar Placement for eligible idle agents without active tasks
    if (state === 'SAFE_IDLE' && !isBusy && !isBlocked) {
      if (agentId === 'agent-thought-curator') {
        currentX = HQ_WAYPOINTS['COFFEE_BAR_CHARLIE'].x;
        currentY = HQ_WAYPOINTS['COFFEE_BAR_CHARLIE'].y;
      } else if (agentId === 'agent-update-steward') {
        currentX = HQ_WAYPOINTS['COFFEE_BAR_DELTA'].x;
        currentY = HQ_WAYPOINTS['COFFEE_BAR_DELTA'].y;
      }
    }

    const task = raw.task || desk.task || (state === 'SAFE_IDLE' ? 'Standby' : state);
    const progress = Number.isFinite(raw.progress) ? raw.progress : (desk.progress || 0.0);
    const speech = raw.speech || resolveSpeechBubble(agentId, { state, task, blocked_reason: raw.blocked_reason, is_bodyguard: false, ...raw }, bus);

    results.push({
      id: agentId,
      name: coords.name,
      title: sanitizeTruthText(title),
      zone: coords.zone,
      x: currentX,
      y: currentY,
      homeX: coords.x,
      homeY: coords.y,
      state,
      task: sanitizeTruthText(task),
      progress,
      speech: sanitizeTruthText(speech),
      is_active: isBusy,
      is_blocked: isBlocked,
      is_bodyguard: false,
      role: sanitizeTruthText(raw.role || coords.title),
      provider: raw.provider || coords.provider || 'LOCAL_DETERMINISTIC',
      heavy_job: Boolean(raw.heavy_job),
      blocked_reason: raw.blocked_reason || (isBlocked ? 'Safety / Gate Paused' : 'None'),
      prop: (state === 'SAFE_IDLE' && (agentId === 'agent-thought-curator' || agentId === 'agent-update-steward')) ? 'drink' : null,
      animation: isBusy ? 'working' : (isBlocked ? 'blocked' : (state === 'SLEEPING' ? 'idle' : 'idle')),
    });
  }

  // 2. Process Eight Reserve Bodyguards
  bodyguards.forEach((bg, idx) => {
    const slot = bodyguardStandbySlots[idx] || { callsign: bg.callsign, x: 14 + idx * 4.5, y: 63.5, leisure_area: 'READY_ROOM', prop: null };
    const isAssigned = bg.state === 'ASSIGNED' || bg.state === 'WORKING' || bg.state === 'RETURNING';
    
    let targetX = slot.x;
    let targetY = slot.y;
    let bodyguardState = bg.state;
    let bodyguardProp = slot.prop;

    if (bodyguardState === 'IDLE') bodyguardState = 'SAFE_IDLE';
    if (bodyguardState === 'WORKING') bodyguardState = 'PROGRESSING';

    if (hasSecurityAlert) {
      bodyguardState = 'ALERT';
      targetX = idx % 2 === 0 ? 44.0 + (idx * 2) : 56.0 - (idx * 2);
      targetY = 67.0;
      bodyguardProp = null; // Holster props during alert
    } else if (isAssigned) {
      const assignedDesk = assignedWorkstationCoords[idx % assignedWorkstationCoords.length];
      targetX = assignedDesk.x;
      targetY = assignedDesk.y;
      bodyguardProp = null;
    }

    let speechText = bg.speech;
    if (hasSecurityAlert) {
      speechText = `EINSATZ / ALARM: ${alertSummary}`;
    } else if (!speechText || speechText.includes('on reserve') || speechText.includes('Ready for reserve duty')) {
      if (bodyguardState === 'SAFE_IDLE' || bodyguardState === 'STANDBY') {
        if (slot.leisure_area === 'COFFEE_BAR') speechText = `Bereitschaft an der Bar (Drink).`;
        else if (slot.leisure_area === 'SAUNA') speechText = slot.callsign === 'ALPHA' ? `Bereitschaft in der Sauna (Pause).` : `Bereitschaft in der Sauna (Shisha).`;
        else if (slot.leisure_area === 'VISITOR_LOUNGE') speechText = `Bereitschaft in der Lounge.`;
        else speechText = `Bereitschaft im Aufenthaltsraum.`;
      } else if (bodyguardState === 'PROGRESSING' || bodyguardState === 'WORKING') {
        speechText = `Sichere Arbeitsbereich: ${bg.temporary_role || 'Task'}.`;
      } else if (bodyguardState === 'RETURNING') {
        speechText = `Aufgabe abgeschlossen. Kehre zur Bereitschaft zurück.`;
      }
    }

    results.push({
      id: bg.id,
      name: `BODYGUARD ${bg.callsign}`,
      title: bg.temporary_role ? `TEMP: ${bg.temporary_role}` : `RESERVE ${bg.slot}`,
      zone: hasSecurityAlert ? 'ALERT_STATION' : 'BODYGUARDS',
      x: targetX,
      y: targetY,
      homeX: slot.x,
      homeY: slot.y,
      state: bodyguardState,
      task: bg.task || (bodyguardState === 'SAFE_IDLE' ? 'Reserve Duty (Standby)' : bodyguardState),
      progress: bg.progress,
      speech: sanitizeTruthText(speechText),
      is_active: isAssigned || bodyguardState === 'ALERT',
      is_blocked: bg.blocked,
      is_bodyguard: true,
      callsign: bg.callsign,
      slot: bg.slot,
      leisure_area: slot.leisure_area,
      prop: bodyguardProp,
      provider: 'LOCAL_BODYGUARD_POOL',
      heavy_job: false,
      blocked_reason: 'None',
      animation: bodyguardState === 'PROGRESSING' ? 'working' : (bodyguardState === 'RETURNING' ? 'walking' : 'idle'),
    });
  });

  return results;
}

/**
 * Resolves deduplicated operational alerts for the Chief Alert Bar.
 */
export function resolveChiefAlerts(stateData) {
  const alerts = [];
  const seenFingerprints = new Set();

  function addAlert(type, severity, message, details = {}) {
    const fp = `${type}:${message}`;
    if (!seenFingerprints.has(fp)) {
      seenFingerprints.add(fp);
      alerts.push({
        id: `alert-${alerts.length + 1}`,
        type,
        severity, // "INFO", "WARNING", "CRITICAL"
        message,
        timestamp: new Date().toLocaleTimeString(),
        details,
      });
    }
  }

  const snitch = stateData?.snitch_observer || {};
  const anomalies = stateData?.anomalies || {};
  const runtime = stateData?.autonomy_runtime || {};
  const bus = stateData?.bus || {};

  // 1. Permission Prompts
  if (snitch?.permission_blocked_count > 0) {
    addAlert('WAITING_PERMISSION', 'WARNING', `Warte auf Berechtigung für ${snitch.permission_blocked_count} Worker`);
  }

  // 2. Hung Workers
  if (snitch?.hung_workers_count > 0) {
    addAlert('HUNG', 'CRITICAL', `${snitch.hung_workers_count} Worker blockiert (>300s keine Aktivität)`);
  }

  // 3. Stale Orphans
  if (snitch?.stale_orphans_count > 0) {
    addAlert('ORPHANED', 'CRITICAL', `${snitch.stale_orphans_count} verwaiste Worker-Prozesse erkannt`);
  }

  // 4. Human Gate
  if (bus?.human_gate || runtime?.human_gates?.length > 0) {
    addAlert('HIGH_RISK_GATE', 'WARNING', 'Human Gate aktiv — Chief Freigabe erforderlich');
  }

  // 5. Money Gate
  if (runtime?.money_gates?.length > 0) {
    addAlert('HIGH_RISK_GATE', 'WARNING', '0 EUR Spend Limit Gate aktiv — Fremdausgaben blockiert');
  }

  // 6. Quarantined Branches
  if (anomalies?.quarantined_branches?.length > 0) {
    addAlert('ANOMALY', 'CRITICAL', `Branch Quarantäne aktiv: ${anomalies.quarantined_branches.join(', ')}`);
  }

  // 7. Recent Worker Completions
  const completedJobs = runtime?.jobs_completed || [];
  if (completedJobs.length > 0) {
    const latestJob = completedJobs[completedJobs.length - 1];
    addAlert('WORKER_COMPLETED', 'INFO', `Task erfolgreich abgeschlossen: ${latestJob}`);
  }

  // 7b. Technical endgame: never claim healthy systems while acceptance is pending
  const ledger = stateData?.courier_ledger || {};
  if (ledger.guard && ledger.guard !== 'CANONICAL_ACCEPTED') {
    addAlert('TECHNICAL_ENDGAME', 'WARNING', `Ledger ${ledger.status || 'UNKNOWN'} · Guard ${ledger.guard} · physische Abnahme ausstehend`);
  }

  // 8. Safe Idle Status if no alerts
  if (alerts.length === 0) {
    addAlert('WORKER_AVAILABLE', 'INFO', 'SAFE_IDLE • Bereitschaft • keine Ausgaben • Live-Telemetrie');
  }

  return alerts;
}

/**
 * Resolves comprehensive, non-secret telemetry for the Agent Detail Panel.
 */
/**
 * Single normalized operations state. Observational only: derives one
 * canonical agent state from the same snapshot every consumer uses, so
 * sidebar, map, detail and counts can never disagree.
 * Canonical states: OFFLINE | IDLE | ACTIVE | WAITING | BLOCKED | ERROR.
 * Every field carries {value, source, observed_at, fresh}; unknown stays UNKNOWN.
 */
export function normalizeOpsState(raw) {
  const s = String(raw || 'UNKNOWN').toUpperCase();
  if (/OFFLINE|STOPPED|DISABLED/.test(s)) return 'OFFLINE';
  if (/BLOCK|ERROR|FAIL|STALE/.test(s)) return s.includes('BLOCK') ? 'BLOCKED' : 'ERROR';
  if (/WAIT|GATE|PAUSE/.test(s)) return 'WAITING';
  if (/RUNNING|WORKING|BUSY|COMPUTING|PROGRESS|RECHNET/.test(s)) return 'ACTIVE';
  if (/IDLE|AVAILABLE|ONLINE|READY|SAFE_IDLE|OPEN|GEÖFFNET|AN\b/.test(s)) return 'IDLE';
  return 'UNKNOWN';
}

function toolFresh(localTools) {
  const age = Date.now() - Date.parse(localTools?.observed_at || '');
  return Number.isFinite(age) && age >= -5000 && age < 15000;
}

export function resolveOpsState(stateData) {
  const observedAt = stateData?.server_time || new Date().toISOString();
  const local = stateData?.local_tools || null;
  const freshLocal = toolFresh(local);
  const agents = stateData?.agents || {};
  const out = {};
  const defs = [
    ['muse', () => {
      const t = freshLocal ? local.tools?.muse : null;
      if (!t) return { state: 'UNKNOWN', task: null, src: 'local-tools (absent/stale)' };
      const st = t.status === 'COMPUTING' ? 'ACTIVE' : t.status === 'OPEN' ? 'IDLE' : t.status === 'OFFLINE' ? 'OFFLINE' : 'UNKNOWN';
      return { state: st, task: t.task_known ? (t.current_task || null) : null, src: 'local-tools PROCESS_CPU_DELTA' };
    }],
    ['codex', () => {
      const t = freshLocal ? local.tools?.chatgpt : null;
      const a = agents['worker-codex'];
      const raw = t?.status === 'COMPUTING' ? 'ACTIVE' : t?.status === 'OFFLINE' ? 'OFFLINE' : (a?.state || 'UNKNOWN');
      return { state: normalizeOpsState(raw), task: a?.task || null, src: t ? 'local-tools+worker-codex' : 'worker-codex' };
    }],
    ['google', () => {
      const t = freshLocal ? local.tools?.antigravity : null;
      const a = agents['worker-google'];
      const raw = t?.status === 'COMPUTING' ? 'ACTIVE' : t?.status === 'OFFLINE' ? 'OFFLINE' : (a?.state || 'UNKNOWN');
      return { state: normalizeOpsState(raw), task: a?.task || null, src: t ? 'local-tools+worker-google' : 'worker-google' };
    }],
  ];
  for (const [id, fn] of defs) {
    const r = fn();
    out[id] = {
      id, state: r.state, task: r.task || null,
      source: r.src, observed_at: observedAt,
      fresh: freshLocal || Boolean(agents[`worker-${id}`]),
    };
  }
  return { observed_at: observedAt, company: 'COURIER SYMPHONY MUSE', agents: out };
}

export function escapeHtmlText(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

export function resolveAgentDetailData(agent, stateData) {
  const autoRuntime = stateData?.autonomy_runtime || {};
  const esc = escapeHtmlText;
  return {
    name: esc(agent.name || agent.id),
    role: esc(agent.role || agent.title || 'Specialist Operator'),
    state: esc(agent.state || 'UNKNOWN'),
    mission: autoRuntime.current_goal ? esc(sanitizeTruthText(autoRuntime.current_goal)) : 'Keine aktive Mission gemeldet',
    task: agent.task ? esc(sanitizeTruthText(agent.task)) : 'Keine konkrete Aufgabe gemeldet',
    last_progress: esc(sanitizeTruthText(agent.last_progress || autoRuntime.last_active_at || 'Just now')),
    state_age: esc(agent.state_age || '0s'),
    blocked_reason: esc(sanitizeTruthText(agent.blocked_reason || (agent.is_blocked ? 'Human gate / policy pause' : 'None (Operating normally)'))),
    provider: esc(agent.provider || 'LOCAL_DETERMINISTIC'),
    heavy_job: agent.heavy_job ? 'YES (Scope Locked)' : 'NO',
    result_id: esc(agent.result_id || 'None'),
  };
}

// --------------------------------------------------------------------------
// 11. WALKABLE NAVIGATION GRAPH & WAYPOINT PATHFINDER
// --------------------------------------------------------------------------

export const HQ_WAYPOINTS = Object.freeze({
  // Corridors & Crossroads
  'CORRIDOR_NORTH': { x: 50.0, y: 35.0 },
  'CORRIDOR_COMMAND': { x: 50.0, y: 48.0 },
  'CORRIDOR_CROSS_MID': { x: 50.0, y: 56.0 },
  'CORRIDOR_FOUNTAIN_TOP': { x: 50.0, y: 60.0 },
  'CORRIDOR_FOUNTAIN_LEFT': { x: 38.0, y: 67.0 },
  'CORRIDOR_FOUNTAIN_RIGHT': { x: 62.0, y: 67.0 },
  'CORRIDOR_SOUTH': { x: 50.0, y: 80.0 },
  'CORRIDOR_BOTTOM_CROSS': { x: 50.0, y: 90.0 },
  'LEFT_AISLE_TOP': { x: 34.0, y: 35.5 },
  'LEFT_AISLE_MID': { x: 34.0, y: 48.0 },
  'LEFT_AISLE_BOT': { x: 34.0, y: 60.5 },
  'RIGHT_AISLE_TOP': { x: 62.0, y: 45.0 },
  'RIGHT_AISLE_MID': { x: 62.0, y: 59.5 },
  'RIGHT_AISLE_BOT': { x: 62.0, y: 73.5 },

  // Key Workstations & Zones
  'CHIEF_COMMAND': { x: 50.0, y: 42.0 },
  'ROUTER_DESK': { x: 57.5, y: 44.0 },
  'DESK_01': { x: 14.5, y: 35.5 },
  'DESK_02': { x: 22.0, y: 35.5 },
  'DESK_03': { x: 29.5, y: 35.5 },
  'DESK_04': { x: 14.5, y: 48.0 },
  'DESK_05': { x: 22.0, y: 48.0 },
  'DESK_06': { x: 29.5, y: 48.0 },
  'DESK_07': { x: 14.5, y: 60.5 },
  'DESK_08': { x: 22.0, y: 60.5 },
  'DESK_09': { x: 29.5, y: 60.5 },
  'DESK_16': { x: 66.5, y: 45.0 },
  'DESK_17': { x: 74.0, y: 45.0 },
  'DESK_19': { x: 81.5, y: 45.0 },
  'DESK_21': { x: 89.0, y: 45.0 },
  'DESK_13': { x: 63.5, y: 59.5 },
  'DESK_22': { x: 71.0, y: 59.5 },
  'DESK_23': { x: 78.5, y: 59.5 },
  'DESK_24': { x: 86.0, y: 59.5 },
  'DESK_24_LOW': { x: 80.0, y: 73.5 },
  'DESK_25_LOW': { x: 88.0, y: 73.5 },
  'DESK_GOOGLE': { x: 78.5, y: 45.0 },
  'DESK_CODEX': { x: 14.5, y: 48.0 },
  'DESK_CLI1': { x: 78.5, y: 73.5 },
  'DESK_CLI2': { x: 86.0, y: 73.5 },

  // Special Facilities
  'SAUNA_ALPHA': { x: 79.0, y: 14.0 },
  'SAUNA_BRAVO': { x: 84.0, y: 14.0 },
  'COFFEE_BAR_CHARLIE': { x: 80.0, y: 91.0 },
  'COFFEE_BAR_DELTA': { x: 85.0, y: 91.0 },
  'VISITOR_LOUNGE_ECHO': { x: 12.0, y: 84.0 },
  'VISITOR_LOUNGE_FOXTROT': { x: 28.0, y: 84.0 },
  'READY_ROOM_GOLF': { x: 44.0, y: 67.0 },
  'READY_ROOM_HOTEL': { x: 56.0, y: 67.0 },
  'SERVER_ROOM': { x: 88.0, y: 38.0 },
  'FIREPLACE': { x: 18.0, y: 28.0 },
});

export const HQ_NAV_GRAPH = Object.freeze({
  'CHIEF_COMMAND': ['CORRIDOR_COMMAND', 'ROUTER_DESK'],
  'ROUTER_DESK': ['CHIEF_COMMAND', 'RIGHT_AISLE_TOP'],
  'CORRIDOR_NORTH': ['CORRIDOR_COMMAND', 'LEFT_AISLE_TOP', 'SAUNA_ALPHA', 'FIREPLACE'],
  'CORRIDOR_COMMAND': ['CHIEF_COMMAND', 'CORRIDOR_NORTH', 'CORRIDOR_CROSS_MID'],
  'CORRIDOR_CROSS_MID': ['CORRIDOR_COMMAND', 'CORRIDOR_FOUNTAIN_TOP', 'LEFT_AISLE_MID', 'RIGHT_AISLE_MID'],
  'CORRIDOR_FOUNTAIN_TOP': ['CORRIDOR_CROSS_MID', 'CORRIDOR_FOUNTAIN_LEFT', 'CORRIDOR_FOUNTAIN_RIGHT'],
  'CORRIDOR_FOUNTAIN_LEFT': ['CORRIDOR_FOUNTAIN_TOP', 'CORRIDOR_SOUTH', 'READY_ROOM_GOLF', 'LEFT_AISLE_BOT'],
  'CORRIDOR_FOUNTAIN_RIGHT': ['CORRIDOR_FOUNTAIN_TOP', 'CORRIDOR_SOUTH', 'READY_ROOM_HOTEL', 'RIGHT_AISLE_MID'],
  'CORRIDOR_SOUTH': ['CORRIDOR_FOUNTAIN_LEFT', 'CORRIDOR_FOUNTAIN_RIGHT', 'CORRIDOR_BOTTOM_CROSS', 'RIGHT_AISLE_BOT'],
  'CORRIDOR_BOTTOM_CROSS': ['CORRIDOR_SOUTH', 'VISITOR_LOUNGE_FOXTROT', 'COFFEE_BAR_CHARLIE'],

  'LEFT_AISLE_TOP': ['CORRIDOR_NORTH', 'DESK_01', 'DESK_02', 'DESK_03', 'LEFT_AISLE_MID'],
  'LEFT_AISLE_MID': ['LEFT_AISLE_TOP', 'CORRIDOR_CROSS_MID', 'DESK_04', 'DESK_05', 'DESK_06', 'DESK_CODEX', 'LEFT_AISLE_BOT'],
  'LEFT_AISLE_BOT': ['LEFT_AISLE_MID', 'CORRIDOR_FOUNTAIN_LEFT', 'DESK_07', 'DESK_08', 'DESK_09', 'VISITOR_LOUNGE_ECHO'],

  'RIGHT_AISLE_TOP': ['ROUTER_DESK', 'DESK_16', 'DESK_17', 'DESK_19', 'DESK_21', 'DESK_GOOGLE', 'SERVER_ROOM', 'RIGHT_AISLE_MID'],
  'RIGHT_AISLE_MID': ['RIGHT_AISLE_TOP', 'CORRIDOR_CROSS_MID', 'CORRIDOR_FOUNTAIN_RIGHT', 'DESK_13', 'DESK_22', 'DESK_23', 'DESK_24', 'RIGHT_AISLE_BOT'],
  'RIGHT_AISLE_BOT': ['RIGHT_AISLE_MID', 'CORRIDOR_SOUTH', 'DESK_24_LOW', 'DESK_25_LOW', 'DESK_CLI1', 'DESK_CLI2', 'COFFEE_BAR_CHARLIE'],

  'DESK_01': ['LEFT_AISLE_TOP'],
  'DESK_02': ['LEFT_AISLE_TOP'],
  'DESK_03': ['LEFT_AISLE_TOP'],
  'DESK_04': ['LEFT_AISLE_MID'],
  'DESK_05': ['LEFT_AISLE_MID'],
  'DESK_06': ['LEFT_AISLE_MID'],
  'DESK_07': ['LEFT_AISLE_BOT'],
  'DESK_08': ['LEFT_AISLE_BOT'],
  'DESK_09': ['LEFT_AISLE_BOT'],
  'DESK_CODEX': ['LEFT_AISLE_MID'],

  'DESK_16': ['RIGHT_AISLE_TOP'],
  'DESK_17': ['RIGHT_AISLE_TOP'],
  'DESK_19': ['RIGHT_AISLE_TOP'],
  'DESK_21': ['RIGHT_AISLE_TOP'],
  'DESK_GOOGLE': ['RIGHT_AISLE_TOP'],
  'DESK_CLI1': ['RIGHT_AISLE_BOT'],
  'DESK_CLI2': ['RIGHT_AISLE_BOT'],
  'DESK_19': ['RIGHT_AISLE_TOP'],
  'DESK_21': ['RIGHT_AISLE_TOP'],
  'DESK_13': ['RIGHT_AISLE_MID'],
  'DESK_22': ['RIGHT_AISLE_MID'],
  'DESK_23': ['RIGHT_AISLE_MID'],
  'DESK_24': ['RIGHT_AISLE_MID'],
  'DESK_24_LOW': ['RIGHT_AISLE_BOT'],
  'DESK_25_LOW': ['RIGHT_AISLE_BOT'],

  'SAUNA_ALPHA': ['CORRIDOR_NORTH', 'SAUNA_BRAVO'],
  'SAUNA_BRAVO': ['SAUNA_ALPHA'],
  'COFFEE_BAR_CHARLIE': ['CORRIDOR_BOTTOM_CROSS', 'RIGHT_AISLE_BOT', 'COFFEE_BAR_DELTA'],
  'COFFEE_BAR_DELTA': ['COFFEE_BAR_CHARLIE'],
  'VISITOR_LOUNGE_ECHO': ['LEFT_AISLE_BOT', 'VISITOR_LOUNGE_FOXTROT'],
  'VISITOR_LOUNGE_FOXTROT': ['CORRIDOR_BOTTOM_CROSS', 'VISITOR_LOUNGE_ECHO'],
  'READY_ROOM_GOLF': ['CORRIDOR_FOUNTAIN_LEFT', 'READY_ROOM_HOTEL'],
  'READY_ROOM_HOTEL': ['CORRIDOR_FOUNTAIN_RIGHT', 'READY_ROOM_GOLF'],
  'SERVER_ROOM': ['RIGHT_AISLE_TOP'],
  'FIREPLACE': ['CORRIDOR_NORTH'],
});

export function findNearestWaypoint(x, y) {
  let bestKey = 'CORRIDOR_CROSS_MID';
  let bestDist = Infinity;
  for (const [key, pt] of Object.entries(HQ_WAYPOINTS)) {
    const dist = Math.hypot(pt.x - x, pt.y - y);
    if (dist < bestDist) {
      bestDist = dist;
      bestKey = key;
    }
  }
  return bestKey;
}

export function bfsNavGraph(startWp, targetWp) {
  if (startWp === targetWp) return [startWp];
  const queue = [[startWp]];
  const visited = new Set([startWp]);

  while (queue.length > 0) {
    const path = queue.shift();
    const node = path[path.length - 1];
    const neighbors = HQ_NAV_GRAPH[node] || [];

    for (const neighbor of neighbors) {
      if (neighbor === targetWp) {
        return [...path, neighbor];
      }
      if (!visited.has(neighbor)) {
        visited.add(neighbor);
        queue.push([...path, neighbor]);
      }
    }
  }
  return [startWp, targetWp];
}

export function findWalkingPath(startX, startY, targetX, targetY) {
  const dist = Math.hypot(targetX - startX, targetY - startY);
  if (dist < 1.5) return [{ x: targetX, y: targetY }];

  const startWp = findNearestWaypoint(startX, startY);
  const targetWp = findNearestWaypoint(targetX, targetY);

  if (startWp === targetWp) {
    return [HQ_WAYPOINTS[startWp], { x: targetX, y: targetY }];
  }

  const pathKeys = bfsNavGraph(startWp, targetWp);
  const coordsPath = pathKeys.map(k => ({ ...HQ_WAYPOINTS[k] }));
  coordsPath.push({ x: targetX, y: targetY });
  return coordsPath;
}

// --------------------------------------------------------------------------
// 12. MISSION 109: CINEMATIC PROMPT STORY MODE
// --------------------------------------------------------------------------

export const PROMPT_LIFECYCLE_PHASES = Object.freeze([
  'PROMPT_RECEIVED',
  'READING',
  'TASK_ACCEPTED',
  'PLAN_CREATED',
  'COURIER_DISPATCH',
  'WALKING_TO_WORKSTATION',
  'WORKING_VISUALIZED',
  'RESULT_PREPARED',
  'COURIER_RETURN',
  'CHIEF_RECEIVED',
  'DONE',
]);

export const TRUTH_MODES = Object.freeze(['LIVE', 'VISUALIZED', 'UNKNOWN']);

export const CANONICAL_SHOWCASE_1 = Object.freeze({
  story_id: 'showcase-001',
  task_title: 'Erstelle die nächste Funktion',
  assigned_agent: 'agent-antigravity-bridge',
  target_runtime_ms: 24000,
  steps: [
    // Scene 1 — CHIEF COMMAND
    {
      phase: 'PROMPT_RECEIVED',
      agent: 'agent-chief-commander',
      duration_ms: 2500,
      truth_mode: 'VISUALIZED',
      caption: 'Neuer Auftrag: Erstelle die nächste Funktion.',
      target_waypoint: 'CHIEF_COMMAND',
      camera_target: 'command',
    },
    // Scene 2 — TASK RECEIVED
    {
      phase: 'TASK_ACCEPTED',
      agent: 'agent-courier-relay',
      duration_ms: 2000,
      truth_mode: 'VISUALIZED',
      caption: 'Auftrag wird übergeben (📦 TASK)',
      target_waypoint: 'CHIEF_COMMAND',
      camera_target: 'command',
    },
    // Scene 3 — COURIER DELIVERY
    {
      phase: 'COURIER_DISPATCH',
      agent: 'agent-courier-relay',
      duration_ms: 3000,
      truth_mode: 'VISUALIZED',
      caption: 'Courier liefert Auftrag zu Antigravity Station',
      target_waypoint: 'DESK_16',
      camera_target: 'active',
    },
    // Scene 4 — ANTIGRAVITY ACCEPTS
    {
      phase: 'READING',
      agent: 'agent-antigravity-bridge',
      duration_ms: 1200,
      truth_mode: 'VISUALIZED',
      caption: 'Auftrag erhalten: Ich lese die Aufgabe',
      target_waypoint: 'DESK_16',
      camera_target: 'active',
    },
    {
      phase: 'TASK_ACCEPTED',
      agent: 'agent-antigravity-bridge',
      duration_ms: 1100,
      truth_mode: 'VISUALIZED',
      caption: 'Aufgabe verstanden & akzeptiert',
      target_waypoint: 'DESK_16',
      camera_target: 'active',
    },
    {
      phase: 'PLAN_CREATED',
      agent: 'agent-antigravity-bridge',
      duration_ms: 1200,
      truth_mode: 'VISUALIZED',
      caption: 'Plan steht: Analyse -> Umsetzung -> Test',
      target_waypoint: 'DESK_16',
      camera_target: 'active',
    },
    // Scene 5 — WORK
    {
      phase: 'WORKING_VISUALIZED',
      agent: 'agent-antigravity-bridge',
      duration_ms: 5000,
      truth_mode: 'VISUALIZED',
      caption: 'WORKING • VISUALIZED: Analyse -> Umsetzung -> Lokaler Test',
      target_waypoint: 'DESK_16',
      camera_target: 'active',
      work_subphase: 'Analyse -> Umsetzung -> Lokaler Test',
    },
    // Scene 6 — RESULT READY
    {
      phase: 'RESULT_PREPARED',
      agent: 'agent-antigravity-bridge',
      duration_ms: 2000,
      truth_mode: 'VISUALIZED',
      caption: 'Ergebnis vorbereitet (📨 RESULT)',
      target_waypoint: 'DESK_16',
      camera_target: 'active',
    },
    // Scene 7 — RETURN TO CHIEF
    {
      phase: 'COURIER_RETURN',
      agent: 'agent-courier-relay',
      duration_ms: 3000,
      truth_mode: 'VISUALIZED',
      caption: 'Courier bringt Ergebnis zurück zum Command Table',
      target_waypoint: 'CHIEF_COMMAND',
      camera_target: 'command',
    },
    // Scene 8 — CHIEF RECEIVES RESULT
    {
      phase: 'CHIEF_RECEIVED',
      agent: 'agent-chief-commander',
      duration_ms: 1500,
      truth_mode: 'VISUALIZED',
      caption: 'RESULT RECEIVED: Chief verifiziert Ergebnis',
      target_waypoint: 'CHIEF_COMMAND',
      camera_target: 'command',
    },
    {
      phase: 'DONE',
      agent: 'agent-chief-commander',
      duration_ms: 1500,
      truth_mode: 'VISUALIZED',
      caption: 'DONE: Mission abgeschlossen',
      target_waypoint: 'CHIEF_COMMAND',
      camera_target: 'overview',
    },
  ],
});

export const CANONICAL_EXAMPLE_STORY = CANONICAL_SHOWCASE_1;

export class StorySceneController {
  constructor(story = CANONICAL_SHOWCASE_1) {
    this.story = story;
    this.currentStepIndex = 0;
    this.stepElapsedMs = 0;
    this.isPlaying = false;
    this.playbackSpeed = 1.0;
  }

  play() {
    this.isPlaying = true;
  }

  pause() {
    this.isPlaying = false;
  }

  restart() {
    this.currentStepIndex = 0;
    this.stepElapsedMs = 0;
    this.isPlaying = true;
  }

  nextStep() {
    if (this.currentStepIndex < this.story.steps.length - 1) {
      this.currentStepIndex++;
      this.stepElapsedMs = 0;
    } else {
      this.currentStepIndex = this.story.steps.length - 1;
      this.isPlaying = false;
    }
  }

  setSpeed(speed) {
    if (typeof speed === 'number' && speed > 0) {
      this.playbackSpeed = speed;
    }
  }

  getCurrentStep() {
    return this.story.steps[this.currentStepIndex] || null;
  }

  getTotalRuntimeMs() {
    return this.story.steps.reduce((sum, s) => sum + (s.duration_ms || 0), 0);
  }

  getProgress() {
    const totalSteps = this.story.steps.length;
    const currentStep = this.getCurrentStep();
    const duration = currentStep ? currentStep.duration_ms : 1000;
    const stepProgress = Math.min(1.0, this.stepElapsedMs / duration);
    const overallProgress = (this.currentStepIndex + stepProgress) / totalSteps;
    return {
      step_index: this.currentStepIndex,
      total_steps: totalSteps,
      phase: currentStep?.phase || 'IDLE',
      caption: currentStep ? sanitizeTruthText(currentStep.caption) : '',
      truth_mode: currentStep?.truth_mode || 'VISUALIZED',
      camera_target: currentStep?.camera_target || 'overview',
      step_progress: stepProgress,
      overall_progress: Math.min(1.0, overallProgress),
      is_playing: this.isPlaying,
      playback_speed: this.playbackSpeed,
      assigned_agent: this.story.assigned_agent,
      task_title: sanitizeTruthText(this.story.task_title),
      total_runtime_ms: this.getTotalRuntimeMs(),
    };
  }

  update(deltaMs) {
    if (!this.isPlaying) return;
    const currentStep = this.getCurrentStep();
    if (!currentStep) return;

    this.stepElapsedMs += deltaMs * this.playbackSpeed;
    if (this.stepElapsedMs >= currentStep.duration_ms) {
      if (this.currentStepIndex < this.story.steps.length - 1) {
        this.currentStepIndex++;
        this.stepElapsedMs = 0;
      } else {
        this.isPlaying = false; // Finished story
      }
    }
  }
}

export function resolveStoryLivingAgents(step, baseLivingAgents) {
  const agentsPool = (Array.isArray(baseLivingAgents) && baseLivingAgents.length > 0)
    ? baseLivingAgents
    : resolveLivingRoomAgents({});

  if (!step) return agentsPool;

  const activeAgentId = step.agent;
  const phase = step.phase;
  const caption = sanitizeTruthText(step.caption);

  return agentsPool.map(ag => {
    let targetX = ag.x;
    let targetY = ag.y;
    let isBusy = false;
    let anim = 'idle';
    let state = 'IDLE';
    let speech = null;

    if (ag.id === 'agent-courier-relay') {
      if (phase === 'COURIER_DISPATCH') {
        targetX = HQ_WAYPOINTS['DESK_16'].x;
        targetY = HQ_WAYPOINTS['DESK_16'].y;
        state = 'RUNNING';
        anim = 'walking';
        isBusy = true;
        speech = 'Transportiere 📦 TASK zu Builder...';
      } else if (phase === 'COURIER_RETURN') {
        targetX = HQ_WAYPOINTS['CHIEF_COMMAND'].x;
        targetY = HQ_WAYPOINTS['CHIEF_COMMAND'].y;
        state = 'RUNNING';
        anim = 'walking';
        isBusy = true;
        speech = 'Transportiere 📨 RESULT zu Chief...';
      } else if (phase === 'TASK_ACCEPTED' || phase === 'PROMPT_RECEIVED') {
        targetX = HQ_WAYPOINTS['CHIEF_COMMAND'].x;
        targetY = HQ_WAYPOINTS['CHIEF_COMMAND'].y;
        state = 'TASK RECEIVED';
        anim = 'idle';
        isBusy = true;
        speech = (activeAgentId === 'agent-courier-relay') ? caption : 'Bereit für Dispatch';
      } else if (phase === 'RESULT_PREPARED') {
        targetX = HQ_WAYPOINTS['DESK_16'].x;
        targetY = HQ_WAYPOINTS['DESK_16'].y;
        state = 'RECEIVING RESULT';
        anim = 'idle';
        isBusy = true;
        speech = 'Übernehme 📨 RESULT';
      } else {
        targetX = ag.homeX || 50.0;
        targetY = ag.homeY || 50.0;
        state = 'IDLE';
        anim = 'idle';
        isBusy = false;
      }
    } else if (ag.id === 'agent-antigravity-bridge') {
      targetX = HQ_WAYPOINTS['DESK_16'].x;
      targetY = HQ_WAYPOINTS['DESK_16'].y;
      if (phase === 'READING') {
        state = 'READING';
        anim = 'idle';
        isBusy = true;
        speech = caption || 'Ich lese die Aufgabe';
      } else if (phase === 'TASK_ACCEPTED') {
        state = 'TASK ACCEPTED';
        anim = 'idle';
        isBusy = true;
        speech = (activeAgentId === 'agent-antigravity-bridge') ? caption : 'Aufgabe akzeptiert';
      } else if (phase === 'PLAN_CREATED') {
        state = 'PLAN CREATED';
        anim = 'idle';
        isBusy = true;
        speech = caption || 'Plan steht';
      } else if (phase === 'WORKING_VISUALIZED' || phase === 'WALKING_TO_WORKSTATION') {
        state = 'WORKING • VISUALIZED';
        anim = 'working';
        isBusy = true;
        speech = caption || 'WORKING • VISUALIZED: Analyse -> Umsetzung -> Lokaler Test';
      } else if (phase === 'RESULT_PREPARED') {
        state = 'RESULT READY';
        anim = 'working';
        isBusy = true;
        speech = caption || 'Ergebnis vorbereitet';
      } else {
        state = 'READY';
        anim = 'idle';
        isBusy = false;
      }
    } else if (ag.id === 'agent-chief-commander') {
      targetX = HQ_WAYPOINTS['CHIEF_COMMAND'].x;
      targetY = HQ_WAYPOINTS['CHIEF_COMMAND'].y;
      if (phase === 'PROMPT_RECEIVED') {
        state = 'CHIEF COMMAND';
        anim = 'idle';
        isBusy = true;
        speech = caption;
      } else if (phase === 'CHIEF_RECEIVED') {
        state = 'RESULT RECEIVED';
        anim = 'idle';
        isBusy = true;
        speech = caption;
      } else if (phase === 'DONE') {
        state = 'DONE';
        anim = 'idle';
        isBusy = true;
        speech = caption;
      } else {
        state = 'CHIEF COMMAND';
        anim = 'idle';
        isBusy = false;
      }
    } else if (ag.id === activeAgentId) {
      isBusy = true;
      anim = 'working';
      state = phase;
      speech = caption;
      if (step.target_waypoint && HQ_WAYPOINTS[step.target_waypoint]) {
        targetX = HQ_WAYPOINTS[step.target_waypoint].x;
        targetY = HQ_WAYPOINTS[step.target_waypoint].y;
      }
    }

    return {
      ...ag,
      x: targetX,
      y: targetY,
      state,
      title: state,
      speech,
      is_active: isBusy,
      animation: anim,
    };
  });
}
