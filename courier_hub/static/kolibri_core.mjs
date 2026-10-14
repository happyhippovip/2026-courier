// Kolibri is one read-only view. Rendering never invents a value: a missing
// field stays UNKNOWN / nicht erreichbar, with the source beside it.

export const UNAVAILABLE = "UNKNOWN / nicht erreichbar";
export const POLL_MS = 15000;

export function stationKey(slotId) {
  const match = /^MUSE-(\d+)$/.exec(slotId || "");
  if (match) return { group: 0, n: Number(match[1]), id: slotId };
  return { group: 1, n: Number.MAX_SAFE_INTEGER, id: slotId || "" };
}

/** Slot number, lowest first. The same ids always compare the same way. */
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
  const value = text(body.value);
  const source = text(body.source);
  const at = text(body.at);
  return `<div class="field">
    <p><span class="quiet">${escapeHtml(label)}</span> <strong>${escapeHtml(value)}</strong></p>
    <p class="meta">source ${escapeHtml(source)}</p>
    <p class="meta">timestamp ${escapeHtml(at)}</p>
  </div>`;
}

function sectionOpen(id, title, block) {
  const available = Boolean(block && block.available);
  return `<section id="${id}" data-available="${available ? "yes" : "no"}">
    <h2>${escapeHtml(title)}</h2>
    ${field("Reading", block)}`;
}

export function unavailableSnapshot(observedAt) {
  const block = (source) => ({
    available: false,
    source,
    at: UNAVAILABLE,
    observed_at: observedAt,
    value: UNAVAILABLE,
  });
  return {
    observed_at: observedAt,
    muse_wall: { ...block("scripts/windows_muse_wall/runtime/slots"), stations: [] },
    ledger: { ...block("courier journal (courier.db)"), items: [], counts: {} },
    merged_prs: { ...block("git log integration/v1"), rows: [] },
  };
}

export function renderKolibri(snapshot) {
  const data = snapshot && typeof snapshot === "object" ? snapshot : unavailableSnapshot(UNAVAILABLE);
  const muse = data.muse_wall || {};
  const ledger = data.ledger || {};
  const merged = data.merged_prs || {};
  const stations = Array.isArray(muse.stations) ? [...muse.stations].sort(compareStations) : [];
  const stationHtml = stations.map((station) => `<article class="card" data-station="${escapeHtml(station.id)}">
      <h3>${escapeHtml(text(station.id))}</h3>
      ${field("State", station.state)}
      ${field("Process", station.process)}
      ${field("DONE", station.done)}
    </article>`).join("");
  const items = Array.isArray(ledger.items) ? ledger.items : [];
  const itemHtml = items.map((item) => `<article class="card" data-ledger="${escapeHtml(item.id)}">
      <h3>${escapeHtml(text(item.title))}</h3>
      ${field("Pile", { value: item.pile, source: item.source, at: item.at })}
      ${field("Id", { value: item.id, source: item.source, at: item.at })}
    </article>`).join("");
  const counts = ledger.counts && typeof ledger.counts === "object" ? ledger.counts : {};
  const countHtml = ["needs_you", "working", "done"].map((key) => field(key, {
    value: counts[key],
    source: ledger.source,
    at: ledger.at,
  })).join("") + field("done_shown", {
    value: ledger.done_shown,
    source: ledger.source,
    at: ledger.at,
  });
  const rows = Array.isArray(merged.rows) ? merged.rows : [];
  const rowHtml = rows.map((row) => `<article class="card" data-pr="${escapeHtml(row.pr)}">
      <h3>#${escapeHtml(text(row.pr))}</h3>
      ${field("Subject", { value: row.subject, source: row.source, at: row.at })}
      ${field("Commit", { value: row.sha, source: row.source, at: row.at })}
    </article>`).join("");
  return `<div class="kolibri">
    <p class="note">Stations are ordered by slot number, lowest first, so MUSE-2 stays before MUSE-10 and the order does not change between reads.</p>
    <p class="note">Merged pull requests are ordered by commit time, oldest first, then by number. DONE on a station is that list: the station is DONE only when a merged subject on integration/v1 names its slot.</p>
    ${sectionOpen("muse-wall", "Muse wall", muse)}
      <div class="stations">${stationHtml}</div>
    </section>
    ${sectionOpen("ledger", "Ledger", ledger)}
      <div class="counts">${countHtml}</div>
      <div class="stations">${itemHtml}</div>
    </section>
    ${sectionOpen("merged", "Merged into integration/v1", merged)}
      <div class="stations">${rowHtml}</div>
    </section>
  </div>`;
}
