// 60-Sekunden-Produktpfad: Start -> Mission -> Ergebnis -> Nachweis -> Pilot.
// Datenquelle: REPLAY (aufgezeichneter echter Lauf von courier_hub.mission_chip) oder
// LIVE (POST /hub/api/mission-chip, nur wenn die Seite vom Hub ausgeliefert wird).
// Grün nur, wenn Verifier-Annahme UND Journal-Eintrag RESULT_ACCEPTED vorliegen.
const $ = (s) => document.querySelector(s);
const state = { mode: "replay", data: null, meta: null, step: 1 };

const EVENT_TEXT = {
  CONTROLLER_STARTED: "Courier ist bereit",
  TASK_CREATED: "Aufgabe angelegt, Budget geprüft (0,00 €)",
  TASK_CLAIMED: "Arbeiter übernimmt die Aufgabe",
  TASK_STARTED: "Ausführung läuft",
  RESULT_READY: "Ergebnis abgegeben, wartet auf Prüfung",
  RESULT_ACCEPTED: "Prüfer hat das Ergebnis angenommen",
  RESULT_REJECTED: "Prüfer hat das Ergebnis abgelehnt",
  TASK_COMPLETE: "Aufgabe erledigt",
};

const esc = (s) => String(s ?? "—").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function acceptedEvent(d) {
  return (d?.events_replay || []).find((e) => e.type === "RESULT_ACCEPTED" && Number.isInteger(e.seq) && e.seq > 0) || null;
}

// The single truth gate for every green element on the page.
function isProven(d) {
  const v = d?.verifier_result;
  return Boolean(v && v.accepted === true && v.resolution === "verified" && d.overall_status === "COMPLETE" && acceptedEvent(d));
}

async function loadReplay() {
  const [d, meta] = await Promise.all([
    fetch("mission_replay.json", { cache: "no-store" }).then((r) => r.json()),
    fetch("replay_meta.json", { cache: "no-store" }).then((r) => r.json()).catch(() => null),
  ]);
  return { d, meta };
}

async function loadLive() {
  const r = await fetch("/hub/api/mission-chip", { method: "POST", cache: "no-store" });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return { d: await r.json(), meta: { recorded_at: new Date().toISOString() } };
}

function setTruth(kind, text) {
  $("#truth").dataset.mode = kind;
  $("#truth").textContent = text;
}

function go(step) {
  state.step = step;
  for (let i = 1; i <= 5; i++) $(`#s${i}`).hidden = i !== step;
  document.querySelectorAll(".steps li").forEach((li) => {
    const n = Number(li.dataset.step);
    li.classList.toggle("done", n < step);
    li.toggleAttribute("aria-current", n === step);
  });
  const h = $(`#s${step} h1, #s${step} h2`);
  if (h) { h.tabIndex = -1; h.focus({ preventScroll: false }); }
}

function fill() {
  const d = state.data;
  const proven = isProven(d);
  const v = d?.verifier_result || {};
  const acc = acceptedEvent(d);
  $("#m-cost").textContent = d ? `${Number(d.cost_eur).toFixed(2).replace(".", ",")} €` : "UNKNOWN";
  $("#r-content").textContent = v.artifact_content ?? "UNKNOWN";
  $("#r-size").textContent = v.artifact_content ? `· ${new TextEncoder().encode(v.artifact_content).length} Bytes` : "";
  $("#r-status").innerHTML = proven ? '<span class="ok">Erledigt und geprüft</span>' : '<span class="unk">Nicht bewiesen</span>';
  $("#r-duration").textContent = d ? `${String(d.duration_ms).replace(".", ",")} ms` : "UNKNOWN";
  $("#p-sha").textContent = v.artifact_sha256 ?? "UNKNOWN";
  $("#p-journal").textContent = acc ? `Nr. ${acc.seq} · RESULT_ACCEPTED` : "keiner – daher nicht bewiesen";
  $("#p-result").textContent = v.accepted_result_id ?? "—";
  $("#checks").innerHTML = (d?.checks || []).map((c) => {
    // Use the boolean, not the server's status string (that one is fixed text in steps 1–2).
    const ok = c.passed === true && proven;
    return `<li class="${ok ? "ok" : "unk"}"><span class="mark" aria-hidden="true">${ok ? "✓" : "?"}</span>
      <span><strong>${esc(c.name)}</strong><br><small>${esc(c.detail)}</small></span>
      <span class="sr">${ok ? "bestanden" : "nicht bewiesen"}</span></li>`;
  }).join("") || '<li class="unk">Keine Prüfdaten</li>';
  const subject = "Pilotanfrage Courier Symphony";
  const body = `Hallo,\n\nich möchte Courier mit folgender Aufgabe testen:\n\n\n(Vorschau-Quittung: ${v.artifact_sha256 ? v.artifact_sha256.slice(0, 16) : "keine"})\n`;
  $("#mail").href = `mailto:founder@couriersymphony.de?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
}

async function playTimeline() {
  const list = $("#timeline");
  list.innerHTML = "";
  $("#run").disabled = true;
  $("#to3").hidden = true;
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const events = state.data?.events_replay || [];
  for (const e of events) {
    const li = document.createElement("li");
    const accepted = e.type === "RESULT_ACCEPTED" && isProven(state.data);
    li.className = accepted ? "ok" : "";
    li.innerHTML = `<span class="seq">${esc(e.seq)}</span> ${esc(EVENT_TEXT[e.type] || e.type)}`;
    list.appendChild(li);
    if (!reduce) await new Promise((r) => setTimeout(r, 380));
  }
  if (!events.length) list.innerHTML = '<li class="unk">Keine Ereignisse – Ergebnis UNKNOWN</li>';
  $("#run").disabled = false;
  $("#run").textContent = "Noch einmal abspielen";
  $("#to3").hidden = false;
  $("#to3").focus();
}

async function sha256Hex(text) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function selfCheck() {
  const v = state.data?.verifier_result || {};
  const out = $("#selfcheck-out");
  if (!v.artifact_content || !v.artifact_sha256) { out.textContent = "Keine Daten zum Nachrechnen."; return; }
  try {
    const mine = await sha256Hex(v.artifact_content);
    out.innerHTML = mine === v.artifact_sha256
      ? `<span class="ok">Stimmt überein.</span> Ihr Browser hat denselben Fingerabdruck berechnet.`
      : `<span class="bad">Abweichung!</span> Browser: ${esc(mine.slice(0, 16))}…`;
  } catch {
    out.textContent = "Ihr Browser erlaubt die Berechnung hier nicht (nur über localhost/https).";
  }
}

function downloadReceipt() {
  const d = state.data;
  const acc = acceptedEvent(d);
  const receipt = {
    source: state.mode === "live" ? "LIVE" : "REPLAY",
    recorded_at: state.meta?.recorded_at ?? null,
    commit: state.meta?.commit ?? null,
    proven: isProven(d),
    task_id: d?.task_id ?? null,
    accepted_result_id: d?.verifier_result?.accepted_result_id ?? null,
    resolution: d?.verifier_result?.resolution ?? null,
    artifact_sha256: d?.verifier_result?.artifact_sha256 ?? null,
    journal_event: acc ? `journal:${acc.seq}:RESULT_ACCEPTED` : null,
    verifier_reason: acc?.payload?.reason ?? null,
    events: (d?.events_replay || []).map((e) => ({ seq: e.seq, type: e.type })),
  };
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([JSON.stringify(receipt, null, 2)], { type: "application/json" }));
  a.download = "courier-quittung.json";
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

async function load() {
  state.data = null;
  try {
    const { d, meta } = state.mode === "live" ? await loadLive() : await loadReplay();
    state.data = d; state.meta = meta;
    if (state.mode === "live") setTruth(isProven(d) ? "live" : "unknown", isProven(d) ? "LIVE · gerade lokal ausgeführt" : "LIVE · nicht bewiesen");
    else setTruth("replay", `REPLAY · echter lokaler Lauf vom ${meta?.recorded_at?.slice(0, 10) ?? "?"} (${meta?.commit ?? "?"}), hier nur abgespielt`);
    $("#source-note").textContent = d.demo_notice || "";
  } catch (err) {
    setTruth("unknown", `${state.mode.toUpperCase()} · UNKNOWN (${err.message || "nicht erreichbar"})`);
    $("#source-note").textContent = state.mode === "live" ? "LIVE geht nur, wenn diese Seite vom laufenden Courier Hub kommt." : "";
  }
  fill();
  $("#timeline").innerHTML = "";
  $("#to3").hidden = true;
  $("#run").textContent = state.mode === "live" ? "Ergebnis anzeigen" : "Mission starten";
}

document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-go]");
  if (b) go(Number(b.dataset.go));
});
$("#run").addEventListener("click", playTimeline);
$("#selfcheck").addEventListener("click", selfCheck);
$("#receipt").addEventListener("click", downloadReceipt);
$("#mode").addEventListener("change", (e) => { state.mode = e.target.value; load(); });
go(1);
load();
