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
