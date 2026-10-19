// Page wiring only. What to show lives in kolibri_core.mjs.
import { POLL_MS, demoSnapshot, renderKolibri, unavailableSnapshot } from "./kolibri_core.mjs";
import { initParticles } from "./kolibri_particles.mjs";

initParticles(document.querySelector("#particles"));

const status = document.querySelector("#status");
const view = document.querySelector("#view");

const MODE = new URLSearchParams(window.location.search).get("mode") === "demo" ? "demo" : "live";
let selected = null;

function stamp() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
}

let timer = null;

function paint(snapshot) {
  view.innerHTML = renderKolibri(snapshot, { mode: MODE, selected });
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
  const picked = event.target?.closest?.("[data-workkey]");
  if (!picked) return;
  selected = selected === picked.dataset.workkey ? null : picked.dataset.workkey;
  refresh().finally(() => {
    view.querySelector("#workkey-detail")?.scrollIntoView({ block: "nearest" });
  });
});

refresh();
