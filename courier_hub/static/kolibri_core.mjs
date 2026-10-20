// Kolibri is one read-only view: one flower per source, one bird.
// The bird flies only to a flower whose snapshot says active. Otherwise it rests.

export const UNAVAILABLE = "UNKNOWN / nicht erreichbar";
export const REST_TEXT = "Keine Aktivität";
export const PAUSE = "PAUSE";
export const STALE = "STALE";
export const READY = "READY";
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
  const at = (station) => {
    const value = station && station.state && station.state.at;
    return value && value !== UNAVAILABLE ? value : "";
  };
  const left = at(a);
  const right = at(b);
  if (left !== right) return !left ? 1 : !right ? -1 : left < right ? 1 : -1;
  const lid = (a && a.id) || "";
  const rid = (b && b.id) || "";
  return lid < rid ? -1 : lid > rid ? 1 : 0;
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
    <ellipse class="orbit-ring" cx="24" cy="22" rx="20" ry="7" fill="none" stroke-width="1.2" stroke-dasharray="3 2"/>
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

const STATE_TOKEN = {
  READY: "ready", STALE: "stale", PAUSE: "pause", FEHLER: "fehler",
  LEERLAUF: "leerlauf", BEENDET: "beendet", PAUSIERT: "pausiert",
};

function stateToken(value) {
  const head = String(value || "").split(" · ")[0];
  return STATE_TOKEN[head] || "unknown";
}

function legendHtml() {
  const items = Object.entries(STATE_TOKEN).concat([["UNKNOWN", "unknown"]]);
  return `<ul class="state-legend">${items.map(([label, token]) =>
    `<li class="state-${token}" data-state="${token}">${label}</li>`).join("")}</ul>`;
}

function stationHtml(stations) {
  return stations.map((station) => {
    const token = stateToken(station.state && station.state.value);
    return `<article class="card state-${token}" data-state="${token}" data-station="${escapeHtml(station.id)}">
      <h3>${escapeHtml(text(station.id))}</h3>
      ${field("State", station.state)}
      ${field("Process", station.process)}
      ${field("DONE", station.done)}
    </article>`;
  }).join("");
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
      ${muse.available ? `<p class="note">A slot file in the repo is not a heartbeat. Up to 30 seconds the own reading is shown. Then STALE until 90 seconds, PAUSE until 300 seconds, and unknown after that. An own reading from the last 30 seconds stays attached.</p>` : ""}
      ${muse.available ? legendHtml() : ""}
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
        ${mission.task_id ? field("Workkey", { value: mission.task_id, source: mission.source, at: mission.at }) : ""}
        ${mission.reason ? field("Blocker", { value: mission.reason, source: mission.source, at: mission.at }) : ""}
      </article>`).join("")}</div>
    </section>
    <section id="github-ci" data-available="${ci.available ? "yes" : "no"}">
      <h2>GitHub CI</h2>
      ${field("Reading", ci)}
      <div class="stations">${checks.map((check) => `<article class="card">
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
      <p class="note">Merged pull requests are ordered newest first. Equal timestamps keep number order.</p>
      ${field("Reading", merged)}
      <div class="stations">${mergeRows.map((row) => `<article class="card" data-pr="${escapeHtml(row.pr)}">
        <h3>#${escapeHtml(text(row.pr))}</h3>
        ${field("Subject", { value: row.subject, source: row.source, at: row.at })}
        ${field("Commit", { value: row.sha, source: row.source, at: row.at })}
      </article>`).join("")}</div>
    </section>`;
}

export function renderKolibri(snapshot) {
  const data = snapshot && typeof snapshot === "object" ? snapshot : unavailableSnapshot(UNAVAILABLE);
  const targets = flyingTo(data);
  const resting = targets.length === 0;
  const target = resting ? "" : targets[0];
  const flowers = FLOWERS.map(([id, label]) => {
    const block = blockOf(data, id);
    const active = block.active === true;
    const here = !resting && id === target;
    return `<article class="flower" data-flower="${escapeHtml(id)}" data-planet="${escapeHtml(id)}" data-active="${active ? "yes" : "no"}">
      ${here ? `<div class="bird" data-state="fly" data-target="${escapeHtml(id)}">${birdSvg()}</div>` : ""}
      ${flowerSvg()}
      <h2>${escapeHtml(label)}</h2>
      ${field("Reading", block)}
    </article>`;
  }).join("");
  const perch = resting
    ? `<div class="perch"><div class="bird" data-state="rest">${birdSvg()}</div><p id="kolibri-activity">${REST_TEXT}</p></div>`
    : `<div class="perch"><p id="kolibri-activity" data-target="${escapeHtml(target)}"></p></div>`;
  return `<div class="kolibri" data-bird="${resting ? "rest" : "fly"}" data-truth="REAL">
    <div class="universe-bar" data-truth="REAL" data-simulated="excluded">
      <span class="universe-badge">REAL LEDGER TELEMETRY</span>
      <span class="universe-orbit-hint">SIMULATED: EXCLUDED · ORBITAL NODES: ${FLOWERS.length} · ACTIVE: ${targets.length}</span>
    </div>
    <p class="note">Stations are ordered newest first. Equal timestamps keep id order.</p>
    <div class="garden">
      ${perch}
      <div class="flowers">${flowers}</div>
    </div>
    ${detailHtml(data)}
  </div>`;
}
