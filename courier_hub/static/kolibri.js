// Page wiring only. What to show lives in kolibri_core.mjs.
import { POLL_MS, renderKolibri, unavailableSnapshot } from "./kolibri_core.mjs";

const status = document.querySelector("#status");
const view = document.querySelector("#view");

function stamp() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
}

let lastEtag = null;
let pollTimer = null;

function scheduleNext(delay) {
  if (pollTimer) window.clearTimeout(pollTimer);
  pollTimer = window.setTimeout(refresh, delay);
}

async function refresh() {
  const observed = stamp();
  try {
    const headers = {};
    if (lastEtag) {
      headers["If-None-Match"] = lastEtag;
    }
    const response = await fetch("/hub/api/kolibri", {
      cache: "no-store",
      headers,
    });
    if (response.status === 304) {
      status.textContent = `Read at ${observed} (unchanged)`;
    } else if (!response.ok) {
      throw new Error(String(response.status));
    } else {
      const etag = response.headers.get("ETag");
      if (etag) lastEtag = etag;
      const snapshot = await response.json();
      view.innerHTML = renderKolibri(snapshot);
      status.textContent = `Read at ${snapshot.observed_at || observed}`;
    }
  } catch {
    view.innerHTML = renderKolibri(unavailableSnapshot(observed));
    status.textContent = "UNKNOWN / nicht erreichbar";
  }
  const nextDelay = document.hidden ? 60000 : POLL_MS;
  scheduleNext(nextDelay);
}

document.addEventListener("visibilitychange", () => {
  if (!document.hidden) {
    refresh();
  }
});

refresh();
