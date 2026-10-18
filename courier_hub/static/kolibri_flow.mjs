// Kolibri Signal & Flow Translation (Lane L5 - Kolibri Neon Research Facility)
// Translates raw snapshot blocks into formal, traceable flow signals.
// Truth Invariant: Jede Zustandsänderung benötigt eine belegte event_id / source provenance.
// UNKNOWN bleibt UNKNOWN.

export const FLOW_STATES = Object.freeze({
  RUNNING: "RUNNING",         // Violett (#a855f7)
  TRANSFERRED: "TRANSFERRED", // Cyan (#06b6d4)
  CLAIMED: "CLAIMED",         // Türkis (#14b8a6) - Agent übernimmt
  VERIFYING: "VERIFYING",     // Gold (#d8b46a)
  VERIFIED: "VERIFIED",       // Grün (#10b981) - unabhängig VERIFIED
  BLOCKED: "BLOCKED",         // Rot (#ef4444)
  FAILED: "FAILED",           // Rot (#ef4444)
  WARN: "WARN",               // Orange (#f59e0b)
  ROUTER: "ROUTER",           // Magenta (#ec4899)
  INFRA: "INFRA",             // Blau (#3b82f6)
  UNKNOWN: "UNKNOWN",         // Grau (#6b7280)
});

export const FLOW_COLORS = Object.freeze({
  [FLOW_STATES.RUNNING]: "#a855f7",
  [FLOW_STATES.TRANSFERRED]: "#06b6d4",
  [FLOW_STATES.CLAIMED]: "#14b8a6",
  [FLOW_STATES.VERIFYING]: "#d8b46a",
  [FLOW_STATES.VERIFIED]: "#10b981",
  [FLOW_STATES.BLOCKED]: "#ef4444",
  [FLOW_STATES.FAILED]: "#ef4444",
  [FLOW_STATES.WARN]: "#f59e0b",
  [FLOW_STATES.ROUTER]: "#ec4899",
  [FLOW_STATES.INFRA]: "#3b82f6",
  [FLOW_STATES.UNKNOWN]: "#6b7280",
});

// Fail-closed translation contract: a green VERIFIED pulse needs ALL of
//   1. an explicit success claim (verified === true, verifier_verdict "pass"),
//   2. an explicit event identity (event_id / id / task_id / source+at),
//   3. a structured evidence object (state / verifier / verification),
//   4. a success context (VERIFIED / SUCCESS / DONE),
//   5. no replay (this explicit id was not translated before).
// Status strings alone are display labels, never proof. UNKNOWN stays UNKNOWN.
const unknownIdCounter = { value: 0 };
function nextUnknownId() {
  return `evt:unknown:${unknownIdCounter.value++}`;
}
const seenEventIds = new Set();
function hasStructuredEvidence(signal) {
  for (const key of ["state", "verifier", "verification"]) {
    const value = signal?.[key];
    if (typeof value === "object" && value !== null) return true;
  }
  return false;
}

/**
 * Maps a station/task snapshot property to a strictly validated flow state.
 * @param {Object} item
 * @returns {{ state: string, color: string, event_id: string, verified: boolean }}
 */
export function translateSignal(item) {
  if (!item || typeof item !== "object") {
    return {
      state: FLOW_STATES.UNKNOWN,
      color: FLOW_COLORS[FLOW_STATES.UNKNOWN],
      event_id: "evt:unknown:0",
      verified: false,
    };
  }

  const rawState = String(item.state?.value || item.status || item.value || "").toUpperCase();
  const blocker = String(item.blocker?.value || item.blocker || "").toUpperCase();
  // Only caller-supplied ids count as provenance. A synthesized placeholder is
  // unique per call and never re-emittable, so a signal without provenance can
  // neither look real nor replay.
  const explicitId =
    item.event_id ?? item.id ?? item.task_id ??
    (item.source != null && item.at != null ? `${item.source}:${item.at}` : undefined);
  const eventId = String(explicitId ?? nextUnknownId());
  const replay = explicitId !== undefined && seenEventIds.has(String(explicitId));
  if (explicitId !== undefined) seenEventIds.add(String(explicitId));

  const successClaim = item.verified === true || item.verifier_verdict === "pass";
  const successContext = rawState === "VERIFIED" || rawState === "SUCCESS" || rawState === "DONE";
  const isVerified =
    successClaim &&
    explicitId !== undefined &&
    hasStructuredEvidence(item) &&
    successContext &&
    !replay;

  // Priority 1: Blocker or explicit failure
  if (blocker && blocker !== "NONE" && blocker !== "UNKNOWN / NICHT ERREICHBAR") {
    return {
      state: FLOW_STATES.BLOCKED,
      color: FLOW_COLORS[FLOW_STATES.BLOCKED],
      event_id: eventId,
      verified: false,
    };
  }
  if (rawState === "FAILED" || rawState === "ERROR") {
    return {
      state: FLOW_STATES.FAILED,
      color: FLOW_COLORS[FLOW_STATES.FAILED],
      event_id: eventId,
      verified: false,
    };
  }

  // Priority 2: Verifier evidence (Kein grüner Erfolg ohne Verifier-Evidenz)
  if (isVerified) {
    return {
      state: FLOW_STATES.VERIFIED,
      color: FLOW_COLORS[FLOW_STATES.VERIFIED],
      event_id: eventId,
      verified: true,
    };
  }

  // Priority 3: Active execution states
  if (rawState === "RUNNING") {
    return {
      state: FLOW_STATES.RUNNING,
      color: FLOW_COLORS[FLOW_STATES.RUNNING],
      event_id: eventId,
      verified: false,
    };
  }
  if (rawState === "TRANSFERRED") {
    return {
      state: FLOW_STATES.TRANSFERRED,
      color: FLOW_COLORS[FLOW_STATES.TRANSFERRED],
      event_id: eventId,
      verified: false,
    };
  }
  if (rawState === "CLAIMED" || rawState === "IN_PROGRESS") {
    return {
      state: FLOW_STATES.CLAIMED,
      color: FLOW_COLORS[FLOW_STATES.CLAIMED],
      event_id: eventId,
      verified: false,
    };
  }
  if (rawState === "VERIFYING") {
    return {
      state: FLOW_STATES.VERIFYING,
      color: FLOW_COLORS[FLOW_STATES.VERIFYING],
      event_id: eventId,
      verified: false,
    };
  }
  if (rawState === "WARN" || rawState === "NEEDS_YOU") {
    return {
      state: FLOW_STATES.WARN,
      color: FLOW_COLORS[FLOW_STATES.WARN],
      event_id: eventId,
      verified: false,
    };
  }
  if (rawState === "ROUTER" || rawState === "DEMO") {
    return {
      state: FLOW_STATES.ROUTER,
      color: FLOW_COLORS[FLOW_STATES.ROUTER],
      event_id: eventId,
      verified: false,
    };
  }
  if (rawState === "INFRA" || rawState === "READY") {
    return {
      state: FLOW_STATES.INFRA,
      color: FLOW_COLORS[FLOW_STATES.INFRA],
      event_id: eventId,
      verified: false,
    };
  }

  return {
    state: FLOW_STATES.UNKNOWN,
    color: FLOW_COLORS[FLOW_STATES.UNKNOWN],
    event_id: eventId,
    verified: false,
  };
}
