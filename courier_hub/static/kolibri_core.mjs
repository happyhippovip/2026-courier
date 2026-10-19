// Kolibri is one read-only view: one flower per source, one bird.
// The bird flies only to a flower whose snapshot says active. Otherwise it rests.
// Signal Lab (V17 slice): a five-stage signal lane (A → B → C → VERIFIED → DONE)
// derived from the same snapshot, plus an explicit LIVE/DEMO ticker. The lane
// never invents evidence: VERIFIED lights only on verifier evidence with a
// real event_id (see kolibri_flow.mjs); DEMO fixtures stay ROUTER-magenta.

import { translateSignal } from "./kolibri_flow.mjs";

export const UNAVAILABLE = "UNKNOWN / nicht erreichbar";
export const REST_TEXT = "Keine Aktivität";
export const PAUSE = "Pause";
export const POLL_MS = 15000;

export const FLOWERS = [
  ["muse_wall", "Muse wall"],
  ["ledger", "Ledger"],
  ["ledger_bridge", "Ledger bridge"],
  ["postfach_alt_an_neu", "Postfach alt an neu"],
  ["postfach_neu_an_alt", "Postfach neu an alt"],
  ["github_ci", "GitHub CI"],
  ["draft_prs", "Draft pull requests"],
  ["merged_prs", "Merged into integration/v1"],
];

export function stationKey(slotId) {
  const match = /^MUSE-(\d+)$/.exec(slotId || "");
  if (match) return { group: 0, n: Number(match[1]), id: slotId };
  return { group: 1, n: Number.MAX_SAFE_INTEGER, id: slotId || "" };
}

export function compareStations(a, b) {
  const left = stationKey(a.id);
  const right = stationKey(b.id);
  if (left.group !== right.group) return left.group - right.group;
  if (left.n !== right.n) return left.n - right.n;
  if (left.id < right.id) return -1;
  if (left.id > right.id) return 1;
  return 0;
}

export function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[ch]));
}

function text(value) {
  if (value === undefined || value === null || value === "") return UNAVAILABLE;
  return String(value);
}

function field(label, record) {
  const body = record && typeof record === "object" ? record : {};
  return `<div class="field">
    <p><span class="quiet">${escapeHtml(label)}</span> <strong>${escapeHtml(text(body.value))}</strong></p>
    <p class="meta">source ${escapeHtml(text(body.source))}</p>
    <p class="meta">timestamp ${escapeHtml(text(body.at))}</p>
  </div>`;
}

function flowerSvg() {
  return `<svg class="flower-mark" viewBox="0 0 48 64" width="48" height="64" aria-hidden="true">
    <line x1="24" y1="28" x2="24" y2="60" stroke="currentColor" stroke-width="2"/>
    <circle cx="24" cy="18" r="8" fill="none" stroke="currentColor" stroke-width="2"/>
    <circle cx="14" cy="24" r="6" fill="none" stroke="currentColor" stroke-width="2"/>
    <circle cx="34" cy="24" r="6" fill="none" stroke="currentColor" stroke-width="2"/>
  </svg>`;
}

function birdSvg() {
  return `<svg class="bird-mark" viewBox="0 0 64 40" width="64" height="40" aria-hidden="true">
    <ellipse cx="34" cy="22" rx="14" ry="8" fill="none" stroke="currentColor" stroke-width="2"/>
    <polygon points="48,22 62,18 48,26" fill="currentColor"/>
    <path d="M28 18 C18 8 10 14 16 22" fill="none" stroke="currentColor" stroke-width="2"/>
    <circle cx="40" cy="20" r="1.5" fill="currentColor"/>
  </svg>`;
}

function blockOf(snapshot, id) {
  const block = snapshot[id];
  return block && typeof block === "object" ? block : {
    available: false,
    active: false,
    source: id,
    at: UNAVAILABLE,
    value: UNAVAILABLE,
  };
}

export function flyingTo(snapshot) {
  return FLOWERS.map(([id]) => id).filter((id) => blockOf(snapshot, id).active === true);
}

export function unavailableSnapshot(observedAt) {
  const block = (source) => ({
    available: false,
    active: false,
    source,
    at: UNAVAILABLE,
    observed_at: observedAt,
    value: UNAVAILABLE,
  });
  return {
    observed_at: observedAt,
    bird: { state: "rest", target: null },
    activity: REST_TEXT,
    muse_wall: { ...block("scripts/windows_muse_wall/runtime/slots"), stations: [] },
    ledger: { ...block("courier journal (courier.db)"), items: [], counts: {} },
    ledger_bridge: { ...block("ledger_bridge_state.json"), missions: [] },
    postfach_alt_an_neu: { ...block("POSTFACH_ALT_AN_NEU"), entries: null },
    postfach_neu_an_alt: { ...block("POSTFACH_NEU_AN_ALT"), entries: null },
    github_ci: { ...block("github statuses integration/v1"), checks: [] },
    draft_prs: { ...block("github pulls integration/v1"), rows: [] },
    merged_prs: { ...block("git log integration/v1"), rows: [] },
  };
}

function stationHtml(stations) {
  const optional = [
    ["Workkey", "workkey"],
    ["Owner", "owner"],
    ["Lease", "lease"],
    ["Blocker", "blocker"],
    ["Resource pause", "resource_pause"],
  ];
  return stations.map((station) => `<article class="card" data-station="${escapeHtml(station.id)}">
      <h3>${escapeHtml(text(station.id))}</h3>
      ${field("State", station.state)}
      ${field("Process", station.process)}
      ${field("DONE", station.done)}
      ${optional.filter(([, key]) => station[key]).map(([label, key]) => field(label, station[key])).join("")}
    </article>`).join("");
}

function detailHtml(snapshot) {
  const muse = blockOf(snapshot, "muse_wall");
  const ledger = blockOf(snapshot, "ledger");
  const bridge = blockOf(snapshot, "ledger_bridge");
  const merged = blockOf(snapshot, "merged_prs");
  const ci = blockOf(snapshot, "github_ci");
  const drafts = blockOf(snapshot, "draft_prs");
  const stations = Array.isArray(muse.stations) ? [...muse.stations].sort(compareStations) : [];
  const items = Array.isArray(ledger.items) ? ledger.items : [];
  const counts = ledger.counts && typeof ledger.counts === "object" ? ledger.counts : {};
  const missions = Array.isArray(bridge.missions) ? bridge.missions : [];
  const checks = Array.isArray(ci.checks) ? ci.checks : [];
  const draftRows = Array.isArray(drafts.rows) ? drafts.rows : [];
  const mergeRows = Array.isArray(merged.rows) ? merged.rows : [];
  const countHtml = ["needs_you", "working", "done"].map((key) => field(key, {
    value: counts[key], source: ledger.source, at: ledger.at,
  })).join("") + field("done_shown", { value: ledger.done_shown, source: ledger.source, at: ledger.at });
  return `
    <section id="muse-wall" data-available="${muse.available ? "yes" : "no"}">
      <h2>Muse wall</h2>
      ${muse.available ? `<p class="note">A slot file in the repo is not a live heartbeat. Without a fresh process heartbeat the state is ${PAUSE}.</p>` : ""}
      ${field("Reading", muse)}
      <div class="stations">${stationHtml(stations)}</div>
    </section>
    <section id="ledger" data-available="${ledger.available ? "yes" : "no"}">
      <h2>Ledger</h2>
      ${field("Reading", ledger)}
      <div class="counts">${countHtml}</div>
      <div class="stations">${items.map((item) => `<article class="card" data-ledger="${escapeHtml(item.id)}">
        <h3>${escapeHtml(text(item.title))}</h3>
        ${field("Pile", { value: item.pile, source: item.source, at: item.at })}
        ${field("Id", { value: item.id, source: item.source, at: item.at })}
      </article>`).join("")}</div>
    </section>
    <section id="ledger-bridge" data-available="${bridge.available ? "yes" : "no"}">
      <h2>Ledger bridge</h2>
      ${field("Reading", bridge)}
      <div class="stations">${missions.map((mission) => `<article class="card" data-mission="${escapeHtml(mission.id)}">
        <h3>${escapeHtml(text(mission.id))}</h3>
        ${field("Status", { value: mission.status, source: mission.source, at: mission.at })}
        ${["workkey", "task_id", "owner", "lease", "blocker", "resource_pause", "reason"]
          .filter((k) => mission[k])
          .map((k) => field(k, { value: mission[k], source: mission.source, at: mission.at }))
          .join("")}
      </article>`).join("")}</div>
    </section>
    <section id="github-ci" data-available="${ci.available ? "yes" : "no"}">
      <h2>GitHub CI</h2>
      ${field("Reading", ci)}
      <div class="stations">${checks.map((check) => `<article class="card" data-check="${escapeHtml(check.context)}">
        ${field(text(check.context), { value: check.state, source: check.source, at: check.at })}
      </article>`).join("")}</div>
    </section>
    <section id="draft-prs" data-available="${drafts.available ? "yes" : "no"}">
      <h2>Draft pull requests</h2>
      ${field("Reading", drafts)}
      <div class="stations">${draftRows.map((row) => `<article class="card" data-draft="${escapeHtml(row.pr)}">
        <h3>#${escapeHtml(text(row.pr))}</h3>
        ${field("Title", { value: row.title, source: row.source, at: row.at })}
      </article>`).join("")}</div>
    </section>
    <section id="merged" data-available="${merged.available ? "yes" : "no"}">
      <h2>Merged into integration/v1</h2>
      <p class="note">Merged pull requests are ordered by commit time, oldest first, then by number.</p>
      ${field("Reading", merged)}
      <div class="stations">${mergeRows.map((row) => `<article class="card" data-pr="${escapeHtml(row.pr)}">
        <h3>#${escapeHtml(text(row.pr))}</h3>
        ${field("Subject", { value: row.subject, source: row.source, at: row.at })}
        ${field("Commit", { value: row.sha, source: row.source, at: row.at })}
      </article>`).join("")}</div>
    </section>`;
}

/* Session latch: a VERIFIED pulse fires once per event_id (flow module
   deduplicates replays). The lane keeps the VERIFIED stage lit while the
   evidenced item is still present in the snapshot; when it leaves, so does
   the light. No latch without verifier evidence, ever. */
const _verifiedLatch = new Set();

function laneItemFor(station) {
  if (!station) return null;
  const sig = translateSignal(station);
  if (sig.verified) _verifiedLatch.add(sig.event_id);
  const latched = sig.verified || _verifiedLatch.has(sig.event_id);
  return { station, sig, latched };
}

function stageCard(slot, item, proofDefault) {
  const sigState = item ? item.sig.state : "UNKNOWN";
  const color = item ? item.sig.color : "#6b7280";
  const st = item ? item.station : null;
  const val = (f) => (st && st[f] && st[f].value !== undefined ? st[f] : { value: "—", source: proofDefault, at: UNAVAILABLE });
  const stampOf = (f) => (st && st[f] && st[f].at ? st[f].at : UNAVAILABLE);
  const proof = item ? item.sig.event_id : "evt:unknown:0";
  const lit = sigState === "VERIFIED" && item && item.latched;
  const shown = lit ? "VERIFIED" : sigState;
  return `<article class="lane-stage" data-lane-stage="${escapeHtml(slot)}" data-state="${escapeHtml(shown)}" style="--sig:${escapeHtml(color)}"${st ? ` data-workkey="${escapeHtml(st.id)}"` : ""}>
    <h3>${escapeHtml(slot)}</h3>
    <p class="lane-agent">${escapeHtml(st ? String(st.id) : "— keine Station —")}</p>
    <p class="lane-status">${escapeHtml(shown)}</p>
    <div class="lane-fields">
      ${field("Workkey", val("workkey"))}
      ${field("Owner", val("owner"))}
      ${field("Lease", val("lease"))}
      ${field("Status", { value: shown, source: st ? (st.state || {}).source : proofDefault, at: st ? stampOf("state") : UNAVAILABLE })}
      ${field("Zeitstempel", { value: st ? stampOf("state") : UNAVAILABLE, source: proofDefault, at: st ? stampOf("state") : UNAVAILABLE })}
      ${field("Prüfnachweis", { value: proof, source: proofDefault, at: st ? stampOf("state") : UNAVAILABLE })}
    </div>
  </article>`;
}

function laneVerifiedCard(items, proofDefault) {
  const hit = items.find((item) => item && item.latched && item.sig.verified)
    || items.find((item) => item && item.latched);
  if (!hit) {
    return `<article class="lane-stage" data-lane-stage="VERIFIED" data-state="UNKNOWN" style="--sig:#6b7280">
      <h3>VERIFIED</h3>
      <p class="lane-agent">— wartet auf Verifier-Evidenz —</p>
      <p class="lane-status">UNKNOWN</p>
      <div class="lane-fields">${field("Prüfnachweis", { value: "keine verifizierte Resolution im Snapshot", source: proofDefault, at: UNAVAILABLE })}</div>
    </article>`;
  }
  return stageCard("VERIFIED", hit, proofDefault);
}

function laneDoneCard(stations, merged, proofDefault) {
  const done = stations.filter((s) => s && s.done && s.done.value === "DONE");
  if (done.length === 0) {
    return `<article class="lane-stage" data-lane-stage="DONE" data-state="UNKNOWN" style="--sig:#6b7280">
      <h3>DONE</h3>
      <p class="lane-agent">— nichts abgeschlossen —</p>
      <p class="lane-status">UNKNOWN</p>
      <div class="lane-fields">${field("Prüfnachweis", { value: `git log integration/v1: ${(merged.rows || []).length} Einträge`, source: proofDefault, at: merged.at || UNAVAILABLE })}</div>
    </article>`;
  }
  const latest = done[done.length - 1];
  const rows = merged.rows || [];
  const hit = rows.find((r) => latest.done && latest.done.pr !== undefined && r.pr === latest.done.pr) || rows[rows.length - 1] || {};
  const proof = hit.sha ? `${hit.sha}${hit.pr ? ` (#${hit.pr})` : ""}` : (hit.pr ? `#${hit.pr}` : "evt:unknown:0");
  return stageCard("DONE", { station: latest, sig: { state: "DONE", color: "#10b981", event_id: proof, verified: false }, latched: false }, proofDefault);
}

export function renderSignalLane(snapshot) {
  const data = snapshot && typeof snapshot === "object" ? snapshot : {};
  const muse = blockOf(data, "muse_wall");
  const merged = blockOf(data, "merged_prs");
  const stations = Array.isArray(muse.stations) ? [...muse.stations].sort(compareStations) : [];
  const proofDefault = muse.source || "muse wall";
  const picked = [stations[0] || null, stations[1] || null, stations[2] || null];
  const items = picked.map(laneItemFor);
  const cards = [
    stageCard("A", items[0], proofDefault),
    stageCard("B", items[1], proofDefault),
    stageCard("C", items[2], proofDefault),
    laneVerifiedCard(items.filter(Boolean), proofDefault),
    laneDoneCard(stations, merged, proofDefault),
  ];
  return `<section id="signal-lane" aria-label="Signalfluss A zu B zu C zu VERIFIED zu DONE">
    <h2>Signalfluss · A → B → C → VERIFIED → DONE</h2>
    <div class="lane">${cards.join('<div class="lane-link" aria-hidden="true"></div>')}</div>
  </section>`;
}

export function renderTicker(mode, observedAt) {
  const demo = mode === "demo";
  return `<div class="hud-ticker" data-mode="${demo ? "demo" : "live"}">
    ${demo
      ? '<span class="badge-demo">DEMO · deterministische Testevents — keine echte Courier-Ausführung</span>'
      : '<span class="badge-live">LIVE · echte Courier-Events</span>'}
    <span class="ticker-stamp">gelesen ${escapeHtml(observedAt || UNAVAILABLE)}</span>
  </div>`;
}

export function renderScroller(snapshot) {
  const data = snapshot && typeof snapshot === "object" ? snapshot : {};
  const merged = blockOf(data, "merged_prs");
  const drafts = blockOf(data, "draft_prs");
  const rows = [
    ...(Array.isArray(merged.rows) ? merged.rows.slice(-5).map((r) => ({ kind: "merge", label: `#${r.pr} ${r.subject || ""}`, at: r.at })) : []),
    ...(Array.isArray(drafts.rows) ? drafts.rows.slice(0, 3).map((r) => ({ kind: "draft", label: `#${r.pr} ${r.title || ""}`, at: r.at })) : []),
  ];
  if (rows.length === 0) {
    return `<section id="event-scroller" aria-label="Ereignisse"><h2>Ereignisse</h2><p class="note">Keine Ereignisse im Snapshot.</p></section>`;
  }
  const items = rows.map((r) => `<li data-kind="${escapeHtml(r.kind)}"><span>${escapeHtml(r.label.slice(0, 80))}</span> <span class="meta">${escapeHtml(r.at || UNAVAILABLE)}</span></li>`).join("");
  return `<section id="event-scroller" aria-label="Ereignisse"><h2>Ereignisse</h2><div class="scroller"><ul>${items}</ul></div></section>`;
}

export function renderDetail(snapshot, selectedId) {
  if (!selectedId) return `<section id="workkey-detail" aria-label="Detailansicht"><h2>Detail</h2><p class="note">Station oder Lane-Stufe wählen — Detail erscheint hier mit Agent, Workkey, Owner, Lease, Status, Zeitstempel, Prüfnachweis.</p></section>`;
  const data = snapshot && typeof snapshot === "object" ? snapshot : {};
  const muse = blockOf(data, "muse_wall");
  const stations = Array.isArray(muse.stations) ? muse.stations : [];
  const st = stations.find((s) => s && s.id === selectedId);
  if (!st) return `<section id="workkey-detail" aria-label="Detailansicht"><h2>Detail</h2><p class="note">Unbekannte Workkey: ${escapeHtml(selectedId)}</p></section>`;
  const item = laneItemFor(st);
  return `<section id="workkey-detail" aria-label="Detailansicht" data-detail="${escapeHtml(st.id)}">
    <h2>Detail · ${escapeHtml(st.id)}</h2>
    <div class="detail-grid">
      ${field("Agent", { value: st.id, source: st.state.source, at: st.state.at })}
      ${field("Workkey", st.workkey || { value: "—", source: st.state.source, at: st.state.at })}
      ${field("Owner", st.owner || { value: "—", source: st.state.source, at: st.state.at })}
      ${field("Lease", st.lease || { value: "—", source: st.state.source, at: st.state.at })}
      ${field("Status", { value: item.latched && item.sig.verified ? "VERIFIED" : item.sig.state, source: st.state.source, at: st.state.at })}
      ${field("Zeitstempel", { value: st.state.at, source: st.state.source, at: st.state.at })}
      ${field("Prüfnachweis", { value: item.sig.event_id, source: st.state.source, at: st.state.at })}
      ${st.blocker ? field("Blocker", st.blocker) : ""}
    </div>
  </section>`;
}

/* Deterministische DEMO-Fixture: feste Ids, feste Zeitstempel, Status DEMO.
   translateSignal mappt DEMO → ROUTER (magenta). Niemals grün, niemals echt. */
export const DEMO_OBSERVED_AT = "2026-10-18T00:00:00Z";
export function demoSnapshot() {
  const at = "2026-10-18T00:00:00Z";
  const station = (id, workkey) => ({
    id,
    heartbeat: false,
    state: { value: "DEMO", source: "demo-fixture", at },
    process: { value: "demo", source: "demo-fixture", at },
    done: { value: "not done", source: "demo-fixture", at },
    workkey: { value: workkey, source: "demo-fixture", at },
    owner: { value: "demo-agent", source: "demo-fixture", at },
    lease: { value: "DEMO-LEASE", source: "demo-fixture", at },
  });
  return {
    observed_at: DEMO_OBSERVED_AT,
    bird: { state: "rest", target: null },
    activity: "DEMO",
    muse_wall: { available: true, active: false, source: "demo-fixture", at, observed_at: at, value: "Pause", stations: [station("DEMO-A", "DEMO-001"), station("DEMO-B", "DEMO-002"), station("DEMO-C", "DEMO-003")] },
    ledger: { available: false, active: false, source: "demo-fixture", at: UNAVAILABLE, observed_at: at, value: UNAVAILABLE, items: [], counts: {} },
    ledger_bridge: { available: false, active: false, source: "demo-fixture", at: UNAVAILABLE, observed_at: at, value: UNAVAILABLE, missions: [] },
    postfach_alt_an_neu: { available: false, active: false, source: "demo-fixture", at: UNAVAILABLE, observed_at: at, value: UNAVAILABLE, entries: null },
    postfach_neu_an_alt: { available: false, active: false, source: "demo-fixture", at: UNAVAILABLE, observed_at: at, value: UNAVAILABLE, entries: null },
    github_ci: { available: false, active: false, source: "demo-fixture", at: UNAVAILABLE, observed_at: at, value: UNAVAILABLE, checks: [] },
    draft_prs: { available: false, active: false, source: "demo-fixture", at: UNAVAILABLE, observed_at: at, value: UNAVAILABLE, rows: [{ pr: 1, title: "Demo-Entwurf", source: "demo-fixture", at }] },
    merged_prs: { available: true, active: false, source: "demo-fixture", at, observed_at: at, value: "0", rows: [] },
    arbitrage_research: {
      available: true,
      source: "demo-fixture",
      at,
      pairs_monitored: [
        { pair: "BTC/EUR", venues: ["Kraken", "Bitstamp"], spread_bps: 12.4, status: "active" },
        { pair: "ETH/EUR", venues: ["Kraken", "Coinbase"], spread_bps: 7.8, status: "active" },
      ],
      simulation: {
        gross_opportunity_eur: 128.40,
        estimated_fees_eur: 38.50,
        estimated_slippage_eur: 14.20,
        net_simulated_profit_eur: 75.70,
        simulation_runs: 1420,
        success_rate_pct: 89.4,
        status: "SIMULATED (NO REAL TRADES)",
      },
      verified_actual_revenue: {
        amount_eur: 0.00,
        status: "NO_LIVE_REVENUE_RECORDED",
        evidence_id: null,
      },
    },
  };
}

export function renderArbitrageResearch(snapshot) {
  const data = snapshot && typeof snapshot === "object" ? snapshot : {};
  const arbi = data.arbitrage_research || { available: false, simulation: {}, pairs_monitored: [], verified_actual_revenue: {} };
  const sim = arbi.simulation || {};
  const actual = arbi.verified_actual_revenue || {};
  const pairs = Array.isArray(arbi.pairs_monitored) ? arbi.pairs_monitored : [];

  const actualRevText = actual.amount_eur !== undefined
    ? `${Number(actual.amount_eur).toFixed(2)} EUR`
    : UNAVAILABLE;
  const actualStatus = actual.status || "UNKNOWN";

  const netProfitText = sim.net_simulated_profit_eur !== undefined
    ? `+${Number(sim.net_simulated_profit_eur).toFixed(2)} EUR`
    : UNAVAILABLE;

  const pairsHtml = pairs.length > 0
    ? pairs.map((p) => `<div class="arbi-pair-chip"><strong>${escapeHtml(p.pair)}</strong> <span class="spread">+${p.spread_bps || 0} bps</span> <span class="venues">${escapeHtml((p.venues || []).join(" ↔ "))}</span></div>`).join("")
    : `<p class="note">${UNAVAILABLE}</p>`;

  const simLossText = sim.simulated_loss_eur !== undefined
    ? `-${Number(sim.simulated_loss_eur).toFixed(2)} EUR`
    : UNAVAILABLE;
  const netRoiText = sim.net_roi_pct !== undefined
    ? `+${Number(sim.net_roi_pct).toFixed(2)}%`
    : UNAVAILABLE;
  const oppsDetected = sim.opportunities_detected !== undefined
    ? String(sim.opportunities_detected)
    : UNAVAILABLE;
  const oppsExecutable = sim.opportunities_executable !== undefined
    ? String(sim.opportunities_executable)
    : UNAVAILABLE;
  const bestStrat = sim.best_simulated_strategy || UNAVAILABLE;
  const arbiBlocker = sim.blocker || "NONE";
  const arbiTitle = arbi.title || "👑 COURIER AI ARBITRAGE · BINANCE ↔ KRAKEN";

  return `<section id="arbitrage-research" aria-label="${escapeHtml(arbiTitle)}">
    <div class="arbi-header">
      <h2>${escapeHtml(arbiTitle)}</h2>
      <span class="arbi-badge-sim">SIMULATION · KEIN ECHTGELD · REAL_TRADES=0</span>
    </div>
    <div class="arbi-grid">
      <div class="arbi-card" data-metric="sim-profit">
        <span class="arbi-label">Simulierter Nettogewinn</span>
        <span class="arbi-value highlight-cyan">${escapeHtml(netProfitText)}</span>
        <span class="arbi-sub">Nach Gebühren (${sim.estimated_fees_eur !== undefined ? Number(sim.estimated_fees_eur).toFixed(2) + " €" : "—"}) &amp; Slippage</span>
      </div>
      <div class="arbi-card" data-metric="sim-loss">
        <span class="arbi-label">Simulierte Verlustsumme</span>
        <span class="arbi-value highlight-gold">${escapeHtml(simLossText)}</span>
        <span class="arbi-sub">Ausführungsrisiko &amp; 2nd Leg Rejects</span>
      </div>
      <div class="arbi-card" data-metric="net-roi">
        <span class="arbi-label">Netto-Rendite (ROI)</span>
        <span class="arbi-value highlight-green">${escapeHtml(netRoiText)}</span>
        <span class="arbi-sub">Kapitalgewichteter Ertrag</span>
      </div>
      <div class="arbi-card" data-metric="opportunities-detected">
        <span class="arbi-label">Erkannte Arbitrage-Chancen</span>
        <span class="arbi-value">${escapeHtml(oppsDetected)}</span>
        <span class="arbi-sub">Brutto-Spread &gt; 0</span>
      </div>
      <div class="arbi-card" data-metric="opportunities-executable">
        <span class="arbi-label">Ausführbare Chancen</span>
        <span class="arbi-value highlight-cyan">${escapeHtml(oppsExecutable)}</span>
        <span class="arbi-sub">Positiver Nettoertrag nach Kosten</span>
      </div>
      <div class="arbi-card" data-metric="success-rate">
        <span class="arbi-label">Erfolgsquote &amp; Simulationen</span>
        <span class="arbi-value highlight-gold">${sim.success_rate_pct !== undefined ? sim.success_rate_pct + "%" : UNAVAILABLE}</span>
        <span class="arbi-sub">${sim.simulation_runs !== undefined ? sim.simulation_runs + " Testläufe" : "0"} · Replay-Prüfung</span>
      </div>
      <div class="arbi-card" data-metric="best-strategy">
        <span class="arbi-label">Beste simulierte Strategie</span>
        <span class="arbi-value" style="font-size:14px;">${escapeHtml(bestStrat)}</span>
        <span class="arbi-sub">Höchste risikoadjustierte Marge</span>
      </div>
      <div class="arbi-card" data-metric="actual-revenue">
        <span class="arbi-label">Tatsächlich nachgewiesene Einnahmen</span>
        <span class="arbi-value highlight-green">${escapeHtml(actualRevText)}</span>
        <span class="arbi-sub">Status: ${escapeHtml(actualStatus)} (getrennt von Simulation)</span>
      </div>
      <div class="arbi-card" data-metric="data-freshness">
        <span class="arbi-label">Datenaktualität &amp; Blocker</span>
        <span class="arbi-value" style="font-size:14px;">${escapeHtml(arbiBlocker)}</span>
        <span class="arbi-sub">Zeitstempel: ${escapeHtml(arbi.at || UNAVAILABLE)}</span>
      </div>
      <div class="arbi-card span-2" data-metric="monitored-venues">
        <span class="arbi-label">Beobachtete Börsen &amp; Handelspaare</span>
        <div class="arbi-pairs-list">${pairsHtml}</div>
      </div>
    </div>
  </section>`;
}

export function renderKolibri(snapshot, options) {
  const opts = options && typeof options === "object" ? options : {};
  const mode = opts.mode === "demo" ? "demo" : "live";
  const data = snapshot && typeof snapshot === "object" ? snapshot : unavailableSnapshot(UNAVAILABLE);
  const targets = flyingTo(data);
  const resting = targets.length === 0;
  const target = resting ? "" : targets[0];
  const flowers = FLOWERS.map(([id, label]) => {
    const block = blockOf(data, id);
    const active = block.active === true;
    const here = !resting && id === target;
    return `<article class="flower" data-flower="${escapeHtml(id)}" data-active="${active ? "yes" : "no"}">
      ${here ? `<div class="bird" data-state="fly" data-target="${escapeHtml(id)}">${birdSvg()}</div>` : ""}
      ${flowerSvg()}
      <h2>${escapeHtml(label)}</h2>
      ${field("Reading", block)}
    </article>`;
  }).join("");
  const perchText = mode === "demo" ? "DEMO · keine echte Ausführung" : REST_TEXT;
  const perch = resting
    ? `<div class="perch"><div class="bird" data-state="rest">${birdSvg()}</div><p id="kolibri-activity">${perchText}</p></div>`
    : `<div class="perch"><p id="kolibri-activity" data-target="${escapeHtml(target)}"></p></div>`;
  return `<div class="kolibri" data-bird="${resting ? "rest" : "fly"}" data-mode="${mode}">
    ${renderTicker(mode, data.observed_at)}
    ${renderArbitrageResearch(data)}
    ${renderSignalLane(data)}
    ${renderScroller(data)}
    ${renderDetail(data, opts.selected || null)}
    <section id="system-resources" aria-label="System & Ressourcen">
      <h2>System &amp; Ressourcen</h2>
      <p class="note">Stations are ordered by slot number, lowest first, so MUSE-2 stays before MUSE-10.</p>
      <div class="garden">
        ${perch}
        <div class="flowers">${flowers}</div>
      </div>
      ${detailHtml(data)}
    </section>
  </div>`;
}
