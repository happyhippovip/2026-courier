// Kolibri insight (V101 draft, isolated). Pure: snapshot in, facts out.
// Every value carries the source and timestamp it came from. A missing source
// is UNKNOWN, never zero. Nothing here is a measured performance number.
//
// Note: translateSignal() in kolibri_flow.mjs remembers verified event ids to
// suppress replays. Calling it here would consume the first VERIFIED for the
// lane, so this module uses FLOW_COLORS only and its own pure evidence check.

import { FLOW_COLORS, FLOW_STATES } from "./kolibri_flow.mjs";

export const UNKNOWN = "UNKNOWN / nicht erreichbar";
const PILES = ["needs_you", "working", "done"];

function isEvidence(item) {
  const id = item && typeof item.event_id === "string" ? item.event_id : "";
  // Green needs the journal binding the hub derives from RESULT_ACCEPTED.
  // A boolean and a free-form event id are not that binding.
  return Boolean(item && item.verified === true && /^journal:[1-9]\d*:RESULT_ACCEPTED$/.test(id));
}

function minutesSince(at, observedAt) {
  const then = Date.parse(at);
  const now = Date.parse(observedAt);
  if (!Number.isFinite(then) || !Number.isFinite(now) || now < then) return null;
  return Math.floor((now - then) / 60000);
}

function fact(value, source, at) {
  return { value, source: source || UNKNOWN, at: at || UNKNOWN };
}

function stateOf(station) {
  const raw = String((station.state && station.state.value) || "").toUpperCase();
  if (station.blocker) return FLOW_STATES.BLOCKED;
  if (station.resource_pause) return FLOW_STATES.WARN;
  if (!station.heartbeat) return FLOW_STATES.UNKNOWN;
  // The status word alone is not verifier evidence.
  if (raw === "VERIFIED" || raw === "DONE" || raw === "SUCCESS") return FLOW_STATES.UNKNOWN;
  return FLOW_STATES[raw] || FLOW_STATES.UNKNOWN;
}

/** Facts for the HUD and the graph for the beams. */
export function deriveInsights(snapshot, observedAt) {
  const snap = snapshot && typeof snapshot === "object" ? snapshot : {};
  const mode = snap.mode === "demo" ? "demo" : "live";
  const ledger = snap.ledger && snap.ledger.available ? snap.ledger : null;
  const wall = snap.muse_wall && snap.muse_wall.available ? snap.muse_wall : null;
  const bridge = snap.ledger_bridge && snap.ledger_bridge.available ? snap.ledger_bridge : null;

  const queue = {};
  for (const pile of PILES) {
    const value = ledger && ledger.counts ? ledger.counts[pile] : undefined;
    queue[pile] = Number.isInteger(value) ? fact(value, ledger.source, ledger.at) : fact(UNKNOWN);
  }

  const blockers = [];
  const waiting = [];
  const missingEvidence = [];
  const verifiedIds = [];
  const nodes = [{ id: "courier", kind: "courier", state: ledger ? FLOW_STATES.INFRA : FLOW_STATES.UNKNOWN }];
  const edges = [];

  for (const station of (wall && Array.isArray(wall.stations) ? wall.stations : []).slice(0, 15)) {
    if (!station || typeof station.id !== "string") continue;
    const state = stateOf(station);
    nodes.push({ id: station.id, kind: "station", state });
    edges.push({ id: `${station.id}>courier`, from: station.id, to: "courier", state, verified: false });
    for (const key of ["blocker", "resource_pause"]) {
      if (station[key]) blockers.push({ target: station.id, kind: key, ...fact(station[key].value, station[key].source, station[key].at) });
    }
  }

  for (const item of ledger && Array.isArray(ledger.items) ? ledger.items : []) {
    if (!item || typeof item.id !== "string") continue;
    if (item.pile !== "done" && typeof item.at === "string") {
      const minutes = minutesSince(item.at, observedAt);
      if (minutes !== null) waiting.push({ target: item.id, pile: item.pile, minutes, source: item.source, at: item.at });
    }
    if (item.pile === "done") {
      if (isEvidence(item)) {
        verifiedIds.push(item.event_id);
        edges.push({ id: `courier>verified:${item.id}`, from: "courier", to: "verifier", state: FLOW_STATES.VERIFIED,
          verified: true, event_id: item.event_id });
      } else {
        missingEvidence.push({ target: item.id, reason: "kein Verifier-Nachweis", source: item.source, at: item.at });
      }
    }
  }

  for (const mission of bridge && Array.isArray(bridge.missions) ? bridge.missions : []) {
    if (!mission || typeof mission.id !== "string") continue;
    if (mission.reason === "evidence_missing" || mission.reason === "human_confirmed") {
      missingEvidence.push({ target: mission.id, reason: mission.reason, source: mission.source, at: mission.at });
    }
    if (mission.blocker) blockers.push({ target: mission.id, kind: "blocker", ...fact(mission.blocker, mission.source, mission.at) });
  }

  const verifier = verifiedIds.length
    ? { state: FLOW_STATES.VERIFIED, event_ids: verifiedIds, source: ledger.source, at: ledger.at }
    : { state: ledger ? "NONE" : FLOW_STATES.UNKNOWN, event_ids: [], source: ledger ? ledger.source : UNKNOWN, at: ledger ? ledger.at : UNKNOWN };
  nodes.push({ id: "verifier", kind: "verifier", state: verifiedIds.length ? FLOW_STATES.VERIFIED : FLOW_STATES.VERIFYING });

  if (mode === "demo") {
    // DEMO never shows green and never claims a verifier result.
    for (const edge of edges) { edge.verified = false; if (edge.state === FLOW_STATES.VERIFIED) edge.state = FLOW_STATES.ROUTER; }
    verifier.state = "DEMO";
    verifier.event_ids = [];
    for (const node of nodes) if (node.state === FLOW_STATES.VERIFIED) node.state = FLOW_STATES.ROUTER;
  }
  for (const node of nodes) node.color = FLOW_COLORS[node.state] || FLOW_COLORS[FLOW_STATES.UNKNOWN];
  for (const edge of edges) edge.color = mode === "demo" ? FLOW_COLORS[FLOW_STATES.ROUTER] : (FLOW_COLORS[edge.state] || FLOW_COLORS[FLOW_STATES.UNKNOWN]);

  return { mode, queue, blockers, waiting, missingEvidence, verifier, graph: { nodes, edges } };
}
