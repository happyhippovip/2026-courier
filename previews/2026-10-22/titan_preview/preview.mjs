// Local TITAN preview: wires the existing Kolibri modules together, nothing new is rendered
// by hand except the detail card and filter. Data: REPLAY (a real local controller run with
// the synthetic adapter), DEMO (kolibri_core.demoSnapshot) or LIVE (/hub/api/kolibri).
import { demoSnapshot, unavailableSnapshot, escapeHtml, UNAVAILABLE } from "/courier_hub/static/kolibri_core.mjs";
import { UNIVERSE_STATUS, buildUniverseModel, renderKolibriUniverse, toBeamGraph } from "/courier_hub/static/kolibri_universe.mjs";
import { createBeams } from "/courier_hub/static/kolibri_beams.mjs";
import { paintBiosphere, BIOSPHERE_CSS } from "/courier_hub/static/kolibri_biosphere.mjs";
import { renderEvidenceBadge } from "/courier_hub/static/evidence_badge.mjs";

const $ = (s) => document.querySelector(s);
const reducedQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
const state = { mode: "replay", snapshot: null, model: null, selected: null, paused: reducedQuery.matches,
  hidden: new Set() };
let beams = null;

function textOf(v) { return v && typeof v === "object" ? (v.value ?? UNAVAILABLE) : (v ?? UNAVAILABLE); }

async function load(mode) {
  if (mode === "demo") return { snap: demoSnapshot(), banner: "DEMO · Testdaten · nichts davon ist echt, nie grün", tone: "demo" };
  const url = mode === "replay" ? "/titan/replay_snapshot.json" : "/hub/api/kolibri";
  try {
    const r = await fetch(url, { cache: "no-store" });
    if (!r.ok) throw new Error(String(r.status));
    const snap = await r.json();
    const banner = mode === "replay" ? `REPLAY · ${snap.mode_note || "aufgezeichneter Snapshot"} · ${snap.observed_at}`
      : `LIVE · gelesen ${snap.observed_at || UNAVAILABLE}`;
    return { snap, banner, tone: mode };
  } catch {
    return { snap: unavailableSnapshot(new Date().toISOString()), banner: `${mode.toUpperCase()} · UNKNOWN / nicht erreichbar`, tone: "unknown" };
  }
}

function renderFilter() {
  const box = $("#filter");
  box.querySelectorAll("label").forEach((l) => l.remove());
  for (const st of Object.values(UNIVERSE_STATUS)) {
    const id = `f-${st}`;
    const label = document.createElement("label");
    label.innerHTML = `<input type="checkbox" id="${id}" ${state.hidden.has(st) ? "" : "checked"}> ${st}`;
    label.querySelector("input").addEventListener("change", (e) => {
      if (e.target.checked) state.hidden.delete(st); else state.hidden.add(st);
      applyFilter();
    });
    box.appendChild(label);
  }
}

function nodeFor(id) {
  const m = state.model;
  return m.agents.find((a) => a.id === id) || m.projects.find((p) => p.id === id) || null;
}

function applyFilter() {
  document.querySelectorAll("#universe [data-workkey]").forEach((g) => {
    const node = nodeFor(g.getAttribute("data-workkey"));
    g.classList.toggle("titan-hidden", Boolean(node && state.hidden.has(node.status)));
  });
}

function detailHtml(node) {
  if (!node) return '<p class="hint">Planet anklicken (oder Tab + Enter) für Details.</p>';
  const snap = state.snapshot || {};
  let blocker = "—", owner = node.owner || "—", lease = node.lease || "—", badge = "";
  if (node.kind === "agent") {
    const st = (snap.muse_wall?.stations || []).find((s) => s.id === node.id) || {};
    blocker = st.blocker ? textOf(st.blocker) : (st.resource_pause ? textOf(st.resource_pause) : "—");
  } else {
    const item = (snap.ledger?.items || []).find((i) => String(i.id) === node.id);
    if (item) badge = renderEvidenceBadge(item);
    const mission = (snap.ledger_bridge?.missions || []).find((m) => String(m.id) === node.id);
    if (mission?.blocker) blocker = mission.blocker;
  }
  return `<h2>${escapeHtml(node.kind === "agent" ? "Agent" : "Projekt")} · ${escapeHtml(node.label)}</h2>
    <dl>
      <dt>Status</dt><dd>${escapeHtml(node.status)}</dd>
      <dt>Owner</dt><dd>${escapeHtml(owner)}</dd>
      <dt>Workkey</dt><dd>${escapeHtml(node.workkey || "—")}</dd>
      <dt>Lease</dt><dd>${escapeHtml(lease)}</dd>
      <dt>Blocker</dt><dd>${escapeHtml(blocker)}</dd>
      <dt>Evidenz</dt><dd>${escapeHtml(node.event_id || "keine Journal-Evidenz")}</dd>
    </dl>
    ${badge ? `<p>Evidence-Badge: ${badge}</p>` : ""}`;
}

function paint() {
  const opts = { mode: state.mode === "demo" ? "demo" : "live", selected: state.selected, paused: state.paused };
  state.model = buildUniverseModel(state.snapshot, opts);
  $("#universe").innerHTML = renderKolibriUniverse(state.snapshot, opts);
  applyFilter();
  $("#detail").innerHTML = detailHtml(state.selected ? nodeFor(state.selected) : null);
  if (beams) beams.setGraph(toBeamGraph(state.model), opts.mode);
}

function select(id) {
  state.selected = state.selected === id ? null : id;
  paint();
  if (state.selected) $("#detail").focus();
}

async function refresh() {
  const { snap, banner, tone } = await load(state.mode);
  state.snapshot = snap;
  $("#mode-banner").textContent = banner;
  $("#mode-banner").dataset.mode = tone;
  paint();
}

function setPaused(paused) {
  state.paused = paused;
  $("#motion").setAttribute("aria-pressed", String(paused));
  $("#motion").textContent = paused ? "Bewegung fortsetzen" : "Bewegung anhalten";
  // Paused or reduced motion still draws the static wiring; only the event pulses stop.
  if (beams) beams.destroy();
  beams = createBeams($("#beams"), { reducedMotion: () => state.paused || reducedQuery.matches });
  paint();
}

function init() {
  const style = document.createElement("style");
  style.textContent = BIOSPHERE_CSS;
  document.head.appendChild(style);
  const bio = $("#biosphere");
  paintBiosphere(bio, { width: window.innerWidth, height: window.innerHeight, dpr: Math.min(1.5, window.devicePixelRatio || 1) });

  $("#universe").addEventListener("click", (e) => {
    if (e.target.closest("#universe-toggle-motion")) { setPaused(!state.paused); return; }
    const g = e.target.closest("[data-workkey]");
    if (g) select(g.getAttribute("data-workkey"));
  });
  $("#universe").addEventListener("keydown", (e) => {
    const g = e.target.closest?.("[data-workkey]");
    if (g && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); select(g.getAttribute("data-workkey")); }
  });
  $("#mode").addEventListener("change", (e) => { state.mode = e.target.value; state.selected = null; refresh(); });
  $("#motion").addEventListener("click", () => setPaused(!state.paused));
  reducedQuery.addEventListener?.("change", () => setPaused(reducedQuery.matches || state.paused));
  renderFilter();
  setPaused(state.paused);
  refresh();
}

init();
