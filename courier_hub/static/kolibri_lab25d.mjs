/* Kolibri 2.5D Lab core: event-driven state machine + particle budget.
 * DOM-free logic (createLab) plus a thin DOM renderer (mountLab).
 * Rule: no animation without an evidenced transition. LIVE = real events,
 * DEMO = visible banner, REPLAY = silent state reconstruction, no pulses.
 * No permanent render loop: the renderer runs only while particles live.
 * Reduced motion and RESOURCE_PAUSE stop all spawning.
 */

export const MODES = ["live", "demo", "replay"];

export const RANK = {
  UNKNOWN: -1,
  QUEUED: 0,
  READY: 1,
  RUNNING: 2,
  TRANSFERRED: 3,
  VERIFYING: 4,
  VERIFIED: 5,
  DONE: 6,
  BLOCKED: 7,
  FAILED: 8,
};

const TERMINAL = new Set(["DONE", "BLOCKED", "FAILED"]);

/* Station placement per status: spatial A/B lanes plus verifier C. */
export function stationFor(status) {
  if (status === "QUEUED" || status === "READY") return "A";
  if (status === "RUNNING" || status === "TRANSFERRED") return "B";
  if (status === "VERIFYING" || status === "VERIFIED" || status === "DONE") return "C";
  return null; // BLOCKED / FAILED / UNKNOWN keep their last station
}

/* Typed glow color per transition kind (renderer maps these to CSS classes). */
export function pulseFor(from, to) {
  if (to === "BLOCKED" || to === "FAILED") return "red";
  if (to === "VERIFIED" || to === "DONE") return "green";
  if (to === "VERIFYING") return "gold";
  if (to === "TRANSFERRED") return "turquoise";
  if (to === "RUNNING" || to === "READY") return "cyan";
  if (from === "UNKNOWN" || to === "QUEUED") return "violet";
  return "gray";
}

function isRecord(value) {
  return typeof value === "object" && value !== null;
}

export function validEvent(ev) {
  return (
    isRecord(ev) &&
    typeof ev.event_id === "string" &&
    ev.event_id.length > 0 &&
    typeof ev.workkey === "string" &&
    ev.workkey.length > 0 &&
    typeof ev.status === "string" &&
    Object.prototype.hasOwnProperty.call(RANK, ev.status) &&
    (ev.source === undefined || typeof ev.source === "string") &&
    (ev.target === undefined || typeof ev.target === "string") &&
    (ev.timestamp === undefined || typeof ev.timestamp === "string")
  );
}

function forwardAllowed(from, to) {
  if (!(to in RANK) || !(from in RANK)) return false;
  if (from === to) return true; // same-status progress refreshes evidence
  // First sighting: accept anything but a claimed completion. VERIFIED and
  // DONE need a tracked earlier step in the same chain.
  // Fail edges stay fail-closed: BLOCKED/FAILED from anywhere, even UNKNOWN.
  if (from === "UNKNOWN") return to !== "DONE" && to !== "VERIFIED";
  if (TERMINAL.has(from)) return false; // terminal states never advance
  if (to === "BLOCKED" || to === "FAILED") return true; // fail edges from anywhere live
  if (to === "UNKNOWN") return false;
  return RANK[to] === RANK[from] + 1;
}

export function createLab(options = {}) {
  const mode = MODES.includes(options.mode) ? options.mode : "live";
  const maxParticles =
    Number.isInteger(options.maxParticles) && options.maxParticles > 0
      ? Math.min(options.maxParticles, 300)
      : 300;
  const state = {
    mode,
    reducedMotion: options.reducedMotion === true,
    paused: options.paused === true,
    workkeys: new Map(),
    seen: new Set(),
    particles: [],
    counters: { applied: 0, duplicate: 0, rejected: 0, pulses: 0 },
  };

  function recordFor(workkey) {
    let rec = state.workkeys.get(workkey);
    if (!rec) {
      rec = { status: "UNKNOWN", station: null, evidence: [], demo: mode === "demo" };
      state.workkeys.set(workkey, rec);
    }
    return rec;
  }

  function spawn(kind, workkey) {
    if (state.reducedMotion || state.paused) return null;
    if (state.particles.length >= maxParticles) return null;
    const particle = { kind, workkey, ageMs: 0, ttlMs: kind === "green" ? 1400 : 900 };
    state.particles.push(particle);
    state.counters.pulses += 1;
    return particle;
  }

  function applyEvent(ev) {
    if (!validEvent(ev)) return { applied: false, reason: "bad-shape" };
    if (state.seen.has(ev.event_id)) {
      state.counters.duplicate += 1;
      return { applied: false, reason: "duplicate" };
    }
    const rec = recordFor(ev.workkey);
    if (!forwardAllowed(rec.status, ev.status)) {
      state.counters.rejected += 1;
      return { applied: false, reason: "out-of-order" };
    }
    state.seen.add(ev.event_id);
    const from = rec.status;
    rec.status = ev.status;
    const station = stationFor(ev.status);
    if (station) rec.station = station;
    rec.evidence.push(ev.event_id);
    if (mode === "demo") rec.demo = true;
    state.counters.applied += 1;
    // REPLAY reconstructs state only: no pulses, no particles, no renewed
    // success signals — the static SVG already shows the rebuilt state.
    const pulse = mode === "replay" ? null : spawn(pulseFor(from, ev.status), ev.workkey);
    return { applied: true, from, to: ev.status, pulse: pulse ? pulse.kind : null, replay: mode === "replay" };
  }

  function step(dtMs) {
    const dt = Math.max(0, Number(dtMs) || 0);
    state.particles = state.particles.filter((p) => (p.ageMs += dt) < p.ttlMs);
    return state.particles.length;
  }

  function snapshot() {
    const workkeys = {};
    for (const [key, rec] of state.workkeys) {
      workkeys[key] = { status: rec.status, station: rec.station, evidence: [...rec.evidence], demo: rec.demo };
    }
    return {
      mode: state.mode,
      reducedMotion: state.reducedMotion,
      paused: state.paused,
      workkeys,
      particles: state.particles.map((p) => ({ ...p })),
      counters: { ...state.counters },
    };
  }

  function setPaused(paused) {
    state.paused = paused === true;
    return state.paused;
  }

  return { applyEvent, step, snapshot, setPaused, maxParticles };
}

/* Thin DOM renderer. Static SVG is the 2D fallback: with reduced motion,
 * without canvas, or while paused, state still renders, only motion stops.
 * The loop runs on demand and halts after 1s idle — never permanently.
 */
const STATION_POS = {
  A: { x: 120, y: 200, label: "Station A" },
  B: { x: 360, y: 200, label: "Station B" },
  C: { x: 600, y: 200, label: "Verifier C" },
};

function el(tag, attrs = {}, parent = null) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  if (parent) parent.appendChild(node);
  return node;
}

export function mountLab(container, lab, options = {}) {
  if (!container || typeof document === "undefined") return null;
  const snap0 = lab.snapshot();
  const reduce =
    options.reducedMotion === true ||
    snap0.reducedMotion ||
    (typeof window !== "undefined" &&
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  container.classList.add("lab25d");
  if (snap0.mode === "demo") container.classList.add("lab25d-demo");
  if (reduce) container.classList.add("lab25d-reduced");

  const banner = document.createElement("p");
  banner.className = "lab25d-banner";
  banner.textContent = snap0.mode === "demo" ? "DEMO — Testevents, keine echte Ausführung" : "";
  container.appendChild(banner);

  const svg = el("svg", { viewBox: "0 0 720 400", role: "img", "aria-label": "Kolibri 2.5D Lab" });
  container.appendChild(svg);
  // Laser links A->B and B->C; classes reflect live link state.
  const linkAB = el("line", { x1: 150, y1: 200, x2: 330, y2: 200, class: "lab25d-link" }, svg);
  const linkBC = el("line", { x1: 390, y1: 200, x2: 570, y2: 200, class: "lab25d-link" }, svg);
  const nodes = {};
  for (const [id, pos] of Object.entries(STATION_POS)) {
    const group = el("g", { class: "lab25d-node", transform: `translate(${pos.x},${pos.y})` }, svg);
    el("circle", { r: 26, class: "lab25d-node-ring" }, group);
    const label = el("text", { y: 44, class: "lab25d-label" }, group);
    label.textContent = `${pos.label} · idle`;
    nodes[id] = { group, label };
  }
  const canvas = document.createElement("canvas");
  canvas.className = "lab25d-particles";
  canvas.width = 720;
  canvas.height = 400;
  const particles2d = !reduce && typeof canvas.getContext === "function" ? canvas.getContext("2d") : null;
  if (particles2d) container.appendChild(canvas);

  const COLORS = {
    cyan: "#22d3ee",
    violet: "#a78bfa",
    turquoise: "#2dd4bf",
    gold: "#fbbf24",
    green: "#34d399",
    red: "#f87171",
    gray: "#6b7280",
  };

  let raf = 0;
  let last = 0;
  let idleSince = 0;

  function draw(now) {
    raf = 0;
    const dt = Math.min(100, now - (last || now));
    last = now;
    const active = lab.step(dt);
    // Node labels always reflect state, even without motion.
    const snap = lab.snapshot();
    let anyLive = false;
    for (const [id, node] of Object.entries(nodes)) {
      const here = Object.entries(snap.workkeys)
        .filter(([, rec]) => rec.station === id)
        .map(([key, rec]) => `${key}:${rec.status}`);
      node.label.textContent = here.length ? `${STATION_POS[id].label} · ${here.join(", ")}` : `${STATION_POS[id].label} · idle`;
      node.group.dataset.live = here.length ? "yes" : "no";
      if (here.length) anyLive = true;
    }
    linkAB.dataset.live = snap.workkeys && Object.values(snap.workkeys).some((r) => r.station === "B") ? "yes" : "no";
    linkBC.dataset.live = Object.values(snap.workkeys).some((r) => r.station === "C") ? "yes" : "no";
    if (particles2d) {
      const ctx = particles2d;
      ctx.clearRect(0, 0, 720, 400);
      for (const p of snap.particles) {
        const rec = snap.workkeys[p.workkey];
        const pos = rec && rec.station ? STATION_POS[rec.station] : STATION_POS.A;
        const t = p.ageMs / p.ttlMs;
        ctx.globalAlpha = Math.max(0, 1 - t);
        ctx.fillStyle = COLORS[p.kind] || COLORS.gray;
        ctx.beginPath();
        ctx.arc(pos.x + Math.sin(p.ageMs / 90) * 18 * t, pos.y - 34 * t, 3, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalAlpha = 1;
    }
    if ((active > 0 || anyLive) && !snap.paused && !snap.reducedMotion) {
      idleSince = 0;
      raf = requestAnimationFrame(draw);
    } else if (!idleSince) {
      idleSince = now;
      raf = requestAnimationFrame(draw);
    } else if (now - idleSince < 1000) {
      raf = requestAnimationFrame(draw);
    } else {
      idleSince = 0; // halted: static SVG keeps showing state
    }
  }

  function kick() {
    if (!raf && !reduce) {
      last = 0;
      idleSince = 0;
      raf = requestAnimationFrame(draw);
    } else if (reduce) {
      draw(performance.now());
      if (raf) {
        cancelAnimationFrame(raf);
        raf = 0;
      }
    }
  }

  // Initial static paint so state is visible before any event.
  kick();
  return {
    kick,
    stop() {
      if (raf) cancelAnimationFrame(raf);
      raf = 0;
    },
    hasCanvas: particles2d !== null,
  };
}
