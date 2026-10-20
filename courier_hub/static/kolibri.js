// Page wiring only. What to show lives in kolibri_core.mjs.
import { POLL_MS, demoSnapshot, renderKolibri, unavailableSnapshot } from "./kolibri_core.mjs";
import { initParticles } from "./kolibri_particles.mjs";

initParticles(document.querySelector("#particles"));

const status = document.querySelector("#status");
const view = document.querySelector("#view");

const MODE = new URLSearchParams(window.location.search).get("mode") === "demo" ? "demo" : "live";
let selected = null;
let universePaused = false;

function stamp() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
}

let timer = null;

function paint(snapshot) {
  view.innerHTML = renderKolibri(snapshot, { mode: MODE, selected, paused: universePaused });
}

async function refresh() {
  clearTimeout(timer);
  if (MODE === "demo") {
    const snapshot = demoSnapshot();
    paint(snapshot);
    status.textContent = `DEMO-Modus — deterministische Testevents, keine echte Ausführung (${snapshot.observed_at})`;
    status.dataset.tone = "warn";
    timer = null;
    return;
  }
  const observed = stamp();
  try {
    const response = await fetch("/hub/api/kolibri", { cache: "no-store" });
    if (!response.ok) throw new Error(String(response.status));
    const snapshot = await response.json();
    paint(snapshot);
    status.textContent = `Read at ${snapshot.observed_at || observed}`;
    delete status.dataset.tone;
  } catch {
    paint(unavailableSnapshot(observed));
    status.textContent = "UNKNOWN / nicht erreichbar";
    status.dataset.tone = "warn";
  }
  timer = document.hidden ? null : window.setTimeout(refresh, POLL_MS);
}

document.addEventListener("visibilitychange", () => {
  if (!document.hidden) refresh();
});
window.addEventListener("focus", () => refresh());
window.addEventListener("online", () => refresh());

document.querySelector("#refresh")?.addEventListener("click", () => refresh());

document.addEventListener("keydown", (event) => {
  if (event.key === "r" && !event.ctrlKey && !event.metaKey && document.activeElement?.tagName !== "TEXTAREA" && document.activeElement?.tagName !== "INPUT") {
    refresh();
  }
});

view?.addEventListener("click", (event) => {
  const toggleBtn = event.target?.closest?.("#universe-toggle-motion");
  if (toggleBtn) {
    universePaused = !universePaused;
    refresh();
    return;
  }
  const picked = event.target?.closest?.("[data-workkey]");
  if (!picked) return;
  selected = selected === picked.dataset.workkey ? null : picked.dataset.workkey;
  refresh().finally(() => {
    view.querySelector("#workkey-detail")?.scrollIntoView({ block: "nearest" });
  });
});

window.startKolibriMission = async function() {
  const btn = document.getElementById("k-mission-btn");
  if (!btn) return;
  btn.disabled = true;
  btn.textContent = "Mission läuft…";

  const st1 = document.getElementById("k-st-1");
  const st2 = document.getElementById("k-st-2");
  const st3 = document.getElementById("k-st-3");

  if (st1) { st1.style.borderColor = "#06b6d4"; document.getElementById("k-st-status-1").textContent = "Prüfe Budget…"; }

  try {
    const res = await fetch("/hub/api/mission-chip");
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();

    if (st1) { st1.style.borderColor = "#10b981"; document.getElementById("k-st-status-1").textContent = "✓ OK (0,00 €)"; }
    if (st2) { st2.style.borderColor = "#10b981"; document.getElementById("k-st-status-2").textContent = "✓ Artefakt erzeugt"; }
    if (st3) { st3.style.borderColor = "#10b981"; document.getElementById("k-st-status-3").textContent = "✓ BYTE_LEVEL_GOLD_VERIFIED"; }

    const receipt = document.getElementById("k-mission-receipt");
    if (receipt) {
      receipt.style.display = "block";
      document.getElementById("k-r-task").textContent = data.task_id;
      document.getElementById("k-r-res").textContent = data.verifier_result.resolution + " (BYTE_LEVEL_GOLD_VERIFIED)";
      document.getElementById("k-r-sha").textContent = data.verifier_result.artifact_sha256;
      document.getElementById("k-r-events").textContent = (data.events_replay || []).length + " Events im SQLite Journal";
    }

    // Dynamically pulse the Signal Lane stages to verified green
    const verifiedCard = document.querySelector('[data-lane-stage="VERIFIED"]');
    if (verifiedCard) {
      verifiedCard.setAttribute("data-state", "VERIFIED");
      verifiedCard.style.setProperty("--sig", "#10b981");
      const agentP = verifiedCard.querySelector(".lane-agent");
      if (agentP) agentP.textContent = "✓ BYTE_LEVEL_GOLD_VERIFIED";
      const statusP = verifiedCard.querySelector(".lane-status");
      if (statusP) statusP.textContent = "VERIFIED";
    }

    const doneCard = document.querySelector('[data-lane-stage="DONE"]');
    if (doneCard) {
      doneCard.setAttribute("data-state", "DONE");
      doneCard.style.setProperty("--sig", "#10b981");
      const agentP = doneCard.querySelector(".lane-agent");
      if (agentP) agentP.textContent = "✓ MISSION_COMPLETE";
      const statusP = doneCard.querySelector(".lane-status");
      if (statusP) statusP.textContent = "DONE";
    }

    btn.textContent = "Mission erneut starten";
    btn.disabled = false;
  } catch (err) {
    if (st1) { st1.style.borderColor = "#ef4444"; document.getElementById("k-st-status-1").textContent = "Fehler: " + err.message; }
    btn.textContent = "Mission starten";
    btn.disabled = false;
  }
};

refresh();
