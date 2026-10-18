// Page wiring only. What to show lives in kolibri_core.mjs.
import { POLL_MS, renderKolibri, unavailableSnapshot } from "./kolibri_core.mjs";

const status = document.querySelector("#status");
const view = document.querySelector("#view");

function stamp() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
}

let timer = null;

async function refresh() {
  clearTimeout(timer);
  const observed = stamp();
  try {
    const response = await fetch("/hub/api/kolibri", { cache: "no-store" });
    if (!response.ok) throw new Error(String(response.status));
    const snapshot = await response.json();
    view.innerHTML = renderKolibri(snapshot);
    status.textContent = `Read at ${snapshot.observed_at || observed}`;
    delete status.dataset.tone;
  } catch {
    view.innerHTML = renderKolibri(unavailableSnapshot(observed));
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

refresh();

