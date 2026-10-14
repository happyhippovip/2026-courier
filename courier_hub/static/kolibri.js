// Page wiring only. What to show lives in kolibri_core.mjs.
import { POLL_MS, renderKolibri, unavailableSnapshot } from "./kolibri_core.mjs";

const status = document.querySelector("#status");
const view = document.querySelector("#view");

function stamp() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
}

async function refresh() {
  const observed = stamp();
  try {
    const response = await fetch("/hub/api/kolibri", { cache: "no-store" });
    if (!response.ok) throw new Error(String(response.status));
    const snapshot = await response.json();
    view.innerHTML = renderKolibri(snapshot);
    status.textContent = `Read at ${snapshot.observed_at || observed}`;
  } catch {
    view.innerHTML = renderKolibri(unavailableSnapshot(observed));
    status.textContent = "UNKNOWN / nicht erreichbar";
  }
  window.setTimeout(refresh, POLL_MS);
}

refresh();
