// Kolibri Universe Component (L5 Desktop Hub / Kolibri Visual First)
// Pure declarative SVG & HTML representation of Courier Symphony as an interactive cosmos.
// Truth Invariant: Planeten, Teams, Agenten und Workflows stammen AUSSCHLIESSLICH aus dem echten Snapshot.
// Keine erfundenen Live-Daten, keine fingierten Einnahmen, keine simulierten Agentenstatus.

import { escapeHtml, UNAVAILABLE } from "./kolibri_core.mjs";
import { translateSignal } from "./kolibri_flow.mjs";

export const UNIVERSE_STATUS = Object.freeze({
  VERIFIED: "VERIFIED", // Hellgrün (#10b981)
  REPORTED: "REPORTED", // Türkis / Cyan (#14b8a6 / #06b6d4)
  UNKNOWN: "UNKNOWN",   // Grau (#6b7280)
  BLOCKED: "BLOCKED",   // Rot (#ef4444)
});

export const UNIVERSE_COLORS = Object.freeze({
  CORE_SPHERE: "#a855f7",    // Violett (Courier Core)
  CORE_INNER: "#3b82f6",     // Blau
  CORE_RING: "#c084fc",      // Lila
  [UNIVERSE_STATUS.VERIFIED]: "#10b981", // Hellgrün
  [UNIVERSE_STATUS.REPORTED]: "#06b6d4", // Cyan/Türkis
  [UNIVERSE_STATUS.UNKNOWN]: "#6b7280",  // Grau
  [UNIVERSE_STATUS.BLOCKED]: "#ef4444",  // Rot
  AMBER_ACCENT: "#d8b46a",   // Courier Gold
});

// A ledger item is verified only when read_ledger saw the journaled RESULT_ACCEPTED
// proof (it then sets verified === true and event_id "journal:<seq>:RESULT_ACCEPTED").
const JOURNAL_PROOF_ID = /^journal:[1-9][0-9]*:RESULT_ACCEPTED$/;

function ledgerVerified(item) {
  return item.verified === true && typeof item.event_id === "string" && JOURNAL_PROOF_ID.test(item.event_id);
}

function sourceAvailable(block) {
  return Boolean(block && typeof block === "object" && block.available === true);
}

// Team state from its members: any blocked member blocks the team, any member still
// working keeps it reported, green only when every member is verified; else unknown.
function teamStatus(members) {
  const states = members.map((a) => a.status);
  if (states.includes(UNIVERSE_STATUS.BLOCKED)) return UNIVERSE_STATUS.BLOCKED;
  if (states.includes(UNIVERSE_STATUS.REPORTED)) return UNIVERSE_STATUS.REPORTED;
  if (states.length > 0 && states.every((st) => st === UNIVERSE_STATUS.VERIFIED)) return UNIVERSE_STATUS.VERIFIED;
  return UNIVERSE_STATUS.UNKNOWN;
}

/**
 * Extracts normalized planet and workflow graph from snapshot.
 * Guarantees zero synthetic or invented items.
 */
export function buildUniverseModel(snapshot, options) {
  const opts = options && typeof options === "object" ? options : {};
  const isDemo = opts.mode === "demo";
  const verifiedGreen = isDemo ? "#ec4899" : UNIVERSE_COLORS[UNIVERSE_STATUS.VERIFIED];

  const data = snapshot && typeof snapshot === "object" ? snapshot : {};
  const muse = data.muse_wall && typeof data.muse_wall === "object" ? data.muse_wall : {};
  const ledger = data.ledger && typeof data.ledger === "object" ? data.ledger : {};
  const bridge = data.ledger_bridge && typeof data.ledger_bridge === "object" ? data.ledger_bridge : {};

  // Center node: Courier Symphony Core. Its status is the health of the snapshot,
  // never VERIFIED: reported while at least one real source answered, else unknown.
  const coreLive = [muse, ledger, bridge].some(sourceAvailable);
  const center = {
    id: "courier-core",
    label: "Courier Symphony Core",
    kind: "core",
    status: coreLive ? UNIVERSE_STATUS.REPORTED : UNIVERSE_STATUS.UNKNOWN,
    color: UNIVERSE_COLORS.CORE_SPHERE,
    observed_at: data.observed_at || UNAVAILABLE,
  };

  const rawStations = Array.isArray(muse.stations) ? muse.stations : [];
  const rawMissions = Array.isArray(bridge.missions) ? bridge.missions : [];
  const rawLedgerItems = Array.isArray(ledger.items) ? ledger.items : [];

  // 1. Agent / Station Planets
  const agents = rawStations.map((station, index) => {
    const sig = translateSignal(station, { peek: true });
    let status = UNIVERSE_STATUS.UNKNOWN;
    let color = UNIVERSE_COLORS[UNIVERSE_STATUS.UNKNOWN];

    if (sig.state === "BLOCKED" || sig.state === "FAILED") {
      status = UNIVERSE_STATUS.BLOCKED;
      color = UNIVERSE_COLORS[UNIVERSE_STATUS.BLOCKED];
    } else if (sig.state === "VERIFIED" || sig.verified === true) {
      status = UNIVERSE_STATUS.VERIFIED;
      color = verifiedGreen;
    } else if (["RUNNING", "TRANSFERRED", "CLAIMED", "VERIFYING", "WARN", "ROUTER"].includes(sig.state)) {
      status = UNIVERSE_STATUS.REPORTED;
      color = sig.state === "RUNNING" ? "#a855f7" : (sig.state === "CLAIMED" ? "#14b8a6" : UNIVERSE_COLORS[UNIVERSE_STATUS.REPORTED]);
    }

    const workkey = station.workkey?.value || station.workkey || null;
    const owner = station.owner?.value || station.owner || null;
    const lease = station.lease?.value || station.lease || null;

    return {
      id: station.id,
      label: station.id,
      kind: "agent",
      team: owner ? String(owner) : "Unassigned",
      workkey: workkey ? String(workkey) : null,
      owner: owner ? String(owner) : null,
      lease: lease ? String(lease) : null,
      status,
      color,
      event_id: sig.event_id,
      raw_state: sig.state,
      index,
    };
  });

  // Group teams derived from real station owners
  const teamSet = new Set();
  agents.forEach((a) => {
    if (a.owner && a.owner !== "—") teamSet.add(a.owner);
  });
  const teams = Array.from(teamSet).map((name, i) => {
    const status = teamStatus(agents.filter((a) => a.owner === name));
    return {
      id: `team-${i + 1}`,
      name,
      kind: "team",
      status,
      color: status === UNIVERSE_STATUS.VERIFIED ? verifiedGreen : UNIVERSE_COLORS[status],
      halo: UNIVERSE_COLORS.CORE_RING, // decorative Lila halo, carries no state
    };
  });

  // 2. Project / Mission Planets
  const projects = [];
  const seenProjKeys = new Set();
  // Only the journal proves a project done; mission status strings are claims.
  const provenLedger = new Map(rawLedgerItems.filter((item) => item && ledgerVerified(item))
    .map((item) => [String(item.id), item]));

  rawMissions.forEach((m, idx) => {
    const pid = String(m.id || m.task_id || `mission-${idx + 1}`);
    seenProjKeys.add(pid);
    const mStatusRaw = String(m.status || "").toUpperCase();
    const proof = provenLedger.get(String(m.task_id || "")) || provenLedger.get(pid);
    let status = UNIVERSE_STATUS.UNKNOWN;
    if (mStatusRaw === "BLOCKED" || m.blocker) status = UNIVERSE_STATUS.BLOCKED;
    else if (proof) status = UNIVERSE_STATUS.VERIFIED;
    else if (mStatusRaw.length > 0 && !mStatusRaw.startsWith("UNKNOWN")) status = UNIVERSE_STATUS.REPORTED;

    projects.push({
      id: pid,
      label: pid,
      kind: "project",
      workkey: m.workkey || null,
      status,
      color: status === UNIVERSE_STATUS.VERIFIED ? verifiedGreen : UNIVERSE_COLORS[status],
      event_id: status === UNIVERSE_STATUS.VERIFIED ? proof.event_id : null,
    });
  });

  rawLedgerItems.forEach((item, idx) => {
    const pid = String(item.id || `ledger-${idx + 1}`);
    if (!seenProjKeys.has(pid)) {
      seenProjKeys.add(pid);
      // "done" alone is not proof: it also holds human-confirmed, stopped and failed tasks.
      const proven = ledgerVerified(item);
      const status = proven ? UNIVERSE_STATUS.VERIFIED
        : (item.pile === "working" ? UNIVERSE_STATUS.REPORTED : UNIVERSE_STATUS.UNKNOWN);
      projects.push({
        id: pid,
        label: String(item.title || pid).slice(0, 32),
        kind: "project",
        workkey: pid,
        status,
        color: proven ? verifiedGreen : UNIVERSE_COLORS[status],
        event_id: proven ? item.event_id : null,
      });
    }
  });

  // 3. Real Workflow Connections
  // Core -> Agent (if active or verified)
  // Agent -> Project (if matching workkey)
  const connections = [];

  agents.forEach((agent) => {
    if (agent.status === UNIVERSE_STATUS.VERIFIED || agent.status === UNIVERSE_STATUS.REPORTED || agent.status === UNIVERSE_STATUS.BLOCKED) {
      connections.push({
        from: center.id,
        to: agent.id,
        status: agent.status,
        color: agent.color,
        workkey: agent.workkey,
        verified: false, // a station report is no journal proof
        event_id: null,
      });
    }

    if (agent.workkey) {
      const match = projects.find((p) => p.workkey === agent.workkey || p.id === agent.workkey);
      if (match) {
        // Only an edge into a journal-proven project is verified and may carry the
        // proof event id, so a beam pulses once per real RESULT_ACCEPTED, never otherwise.
        const proven = match.status === UNIVERSE_STATUS.VERIFIED && typeof match.event_id === "string";
        connections.push({
          from: agent.id,
          to: match.id,
          status: agent.status,
          color: agent.color,
          workkey: agent.workkey,
          verified: proven,
          event_id: proven ? match.event_id : null,
        });
      }
    }
  });

  return { center, teams, agents, projects, connections };
}

/**
 * Graph for kolibri_beams.createBeams().setGraph(), in its own topology: the Courier
 * master ("courier"), the verifier ("verifier") and agents as stations. Courier -> agent
 * beams show live wiring and never pulse. An agent -> verifier beam exists only for a
 * journal-proven project and carries that RESULT_ACCEPTED id, so it pulses once per proof.
 */
export function toBeamGraph(model) {
  const m = model && typeof model === "object" ? model : {};
  const agents = Array.isArray(m.agents) ? m.agents : [];
  const known = new Set(agents.map((a) => a.id));
  const nodes = [
    { id: "courier", color: m.center ? m.center.color : UNIVERSE_COLORS.CORE_SPHERE },
    { id: "verifier", color: UNIVERSE_COLORS[UNIVERSE_STATUS.UNKNOWN] },
    ...agents.map((a) => ({ id: a.id, kind: "station", color: a.color })),
  ];
  const edges = [];
  for (const c of Array.isArray(m.connections) ? m.connections : []) {
    if (m.center && c.from === m.center.id && known.has(c.to)) {
      edges.push({ id: `courier->${c.to}`, from: "courier", to: c.to, color: c.color, state: c.status,
        verified: false, event_id: null });
    } else if (known.has(c.from) && c.verified === true && typeof c.event_id === "string") {
      edges.push({ id: `${c.from}->verifier`, from: c.from, to: "verifier", color: c.color, state: c.status,
        verified: true, event_id: c.event_id });
    }
  }
  return { nodes, edges };
}

/**
 * Calculates (x, y) coordinates on an elliptical celestial orbit.
 */
function orbitPoint(cx, cy, rx, ry, angleDeg) {
  const rad = (angleDeg * Math.PI) / 180;
  return {
    x: Math.round(cx + rx * Math.cos(rad)),
    y: Math.round(cy + ry * Math.sin(rad)),
  };
}

/**
 * Renders the Kolibri Universe interactive view.
 */
export function renderKolibriUniverse(snapshot, options) {
  const opts = options && typeof options === "object" ? options : {};
  const selectedKey = opts.selected || null;
  const isPaused = opts.paused === true;
  const model = buildUniverseModel(snapshot, opts);

  const cx = 400;
  const cy = 300;
  const orbit1Rx = 180;
  const orbit1Ry = 110;
  const orbit2Rx = 310;
  const orbit2Ry = 190;

  // Position agents along inner orbit
  const agentCount = Math.max(model.agents.length, 1);
  const positionedAgents = model.agents.map((agent, i) => {
    const angle = (360 / agentCount) * i - 90;
    const pt = orbitPoint(cx, cy, orbit1Rx, orbit1Ry, angle);
    return { ...agent, x: pt.x, y: pt.y };
  });

  // Position projects along outer orbit
  const projCount = Math.max(model.projects.length, 1);
  const positionedProjects = model.projects.map((proj, i) => {
    const angle = (360 / projCount) * i - 45;
    const pt = orbitPoint(cx, cy, orbit2Rx, orbit2Ry, angle);
    return { ...proj, x: pt.x, y: pt.y };
  });

  // Lookup map for coords
  const coordsMap = new Map();
  coordsMap.set(model.center.id, { x: cx, y: cy });
  positionedAgents.forEach((a) => coordsMap.set(a.id, { x: a.x, y: a.y }));
  positionedProjects.forEach((p) => coordsMap.set(p.id, { x: p.x, y: p.y }));

  // Draw workflow connection lines
  const connectionSvg = model.connections.map((c, idx) => {
    const p1 = coordsMap.get(c.from);
    const p2 = coordsMap.get(c.to);
    if (!p1 || !p2) return "";
    const strokeDash = c.status === UNIVERSE_STATUS.REPORTED ? 'stroke-dasharray="4 4"' : "";
    return `<line class="universe-workflow-line" data-status="${escapeHtml(c.status)}" x1="${p1.x}" y1="${p1.y}" x2="${p2.x}" y2="${p2.y}" stroke="${escapeHtml(c.color)}" stroke-width="1.8" ${strokeDash} opacity="0.65" />`;
  }).join("\n");

  // Draw Agent planet nodes
  const agentSvg = positionedAgents.map((a) => {
    const isSelected = selectedKey === a.id || (a.workkey && selectedKey === a.workkey);
    const selClass = isSelected ? " planet-selected" : "";
    const r = isSelected ? 12 : 9;
    return `<g class="universe-planet universe-agent${selClass}" data-workkey="${escapeHtml(a.id)}" tabindex="0" role="button" aria-label="Agent ${escapeHtml(a.id)}: Status ${escapeHtml(a.status)}" transform="translate(${a.x}, ${a.y})">
      <circle r="${r + 4}" fill="${escapeHtml(a.color)}" opacity="0.2" class="planet-pulse" />
      <circle r="${r}" fill="#0a0d14" stroke="${escapeHtml(a.color)}" stroke-width="2.2" />
      <text y="${r + 14}" text-anchor="middle" fill="#e5e7eb" font-size="10" font-family="ui-monospace, monospace" font-weight="600">${escapeHtml(a.id)}</text>
      <text y="${r + 25}" text-anchor="middle" fill="${escapeHtml(a.color)}" font-size="8.5" font-family="sans-serif">${escapeHtml(a.status)}</text>
    </g>`;
  }).join("\n");

  // Draw Project planet nodes
  const projectSvg = positionedProjects.map((p) => {
    const isSelected = selectedKey === p.id || (p.workkey && selectedKey === p.workkey);
    const selClass = isSelected ? " planet-selected" : "";
    const r = isSelected ? 11 : 8;
    return `<g class="universe-planet universe-project${selClass}" data-workkey="${escapeHtml(p.id)}" tabindex="0" role="button" aria-label="Projekt ${escapeHtml(p.id)}: Status ${escapeHtml(p.status)}" transform="translate(${p.x}, ${p.y})">
      <circle r="${r + 3}" fill="${escapeHtml(p.color)}" opacity="0.15" />
      <polygon points="0,-${r} ${r},${r} -${r},${r}" fill="#0f172a" stroke="${escapeHtml(p.color)}" stroke-width="2" />
      <text y="${r + 15}" text-anchor="middle" fill="#94a3b8" font-size="9.5" font-family="sans-serif">${escapeHtml(p.label)}</text>
    </g>`;
  }).join("\n");

  const pauseClass = isPaused ? " universe-paused" : "";

  return `<section id="kolibri-universe" class="kolibri-universe-section${pauseClass}" aria-label="Kolibri Universum · Interaktive Sphären">
    <div class="universe-header">
      <div class="universe-title-wrap">
        <h2>👑 COURIER SYMPHONY · CELESTIAL UNIVERSE</h2>
        <span class="universe-badge">KOSMISCHE ORCHESTRIERUNG · ZERO FABRICATION</span>
      </div>
      <div class="universe-controls">
        <button type="button" id="universe-toggle-motion" class="universe-ctrl-btn" title="Animation umschalten (Ressourcenschonend)">
          ${isPaused ? "▶ Kosmos bewegen" : "⏸ Kosmos anhalten"}
        </button>
      </div>
    </div>

    <div class="universe-viewport">
      <svg class="universe-canvas" viewBox="0 0 800 600" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Interaktives Universum mit Teams, Agenten, Projekten und Workflows">
        <defs>
          <radialGradient id="core-glow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stop-color="#a855f7" stop-opacity="0.8"/>
            <stop offset="60%" stop-color="#3b82f6" stop-opacity="0.3"/>
            <stop offset="100%" stop-color="#0a0d14" stop-opacity="0"/>
          </radialGradient>
          <filter id="neon-glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>

        <!-- Orbital Rings -->
        <ellipse class="universe-orbit orbit-inner" cx="${cx}" cy="${cy}" rx="${orbit1Rx}" ry="${orbit1Ry}" fill="none" stroke="rgba(192, 132, 252, 0.18)" stroke-width="1.2" stroke-dasharray="6 6" />
        <ellipse class="universe-orbit orbit-outer" cx="${cx}" cy="${cy}" rx="${orbit2Rx}" ry="${orbit2Ry}" fill="none" stroke="rgba(6, 182, 212, 0.15)" stroke-width="1.2" stroke-dasharray="4 8" />

        <!-- Real Workflow Connections -->
        <g class="universe-workflows">
          ${connectionSvg}
        </g>

        <!-- Central Sphere: Courier Symphony Core -->
        <g id="${escapeHtml(model.center.id)}" class="universe-core" data-core="${escapeHtml(model.center.id)}" transform="translate(${cx}, ${cy})" filter="url(#neon-glow)">
          <circle r="46" fill="url(#core-glow)" />
          <circle r="28" fill="#131722" stroke="${UNIVERSE_COLORS.CORE_RING}" stroke-width="2.5" />
          <circle r="16" fill="none" stroke="${UNIVERSE_COLORS.AMBER_ACCENT}" stroke-width="2" />
          <!-- Courier Symphony Logo Glyph -->
          <circle cx="0" cy="0" r="5" fill="${UNIVERSE_COLORS.AMBER_ACCENT}" />
          <text y="42" text-anchor="middle" fill="#c084fc" font-size="11" font-weight="700" letter-spacing="0.08em">COURIER CORE</text>
        </g>

        <!-- Agent Planets -->
        <g class="universe-agents-layer">
          ${agentSvg}
        </g>

        <!-- Project Planets -->
        <g class="universe-projects-layer">
          ${projectSvg}
        </g>
      </svg>
    </div>

    <!-- Status Legend & Metrics Bar -->
    <div class="universe-footer-bar">
      <div class="universe-legend">
        <span class="legend-item"><span class="dot dot-verified"></span> VERIFIED</span>
        <span class="legend-item"><span class="dot dot-reported"></span> REPORTED</span>
        <span class="legend-item"><span class="dot dot-blocked"></span> BLOCKED</span>
        <span class="legend-item"><span class="dot dot-unknown"></span> UNKNOWN</span>
      </div>
      <div class="universe-summary">
        <span>Planeten: <strong>${positionedAgents.length + positionedProjects.length}</strong></span>
        <span>Echte Workflows: <strong>${model.connections.length}</strong></span>
        <span>Teams: <strong>${model.teams.length}</strong></span>
      </div>
    </div>
  </section>`;
}
