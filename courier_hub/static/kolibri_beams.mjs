// Kolibri Black Orb beams (V101 draft, isolated). Canvas 2D only.
// Black glossy orbs, a large Courier master orb, quadratic Bezier beams with
// three translucent glow layers, and event pulses. Truth rules:
// - a pulse runs only for an edge that carries an event_id, once per id;
// - green only for an edge with verified === true in LIVE mode;
// - DEMO is magenta and dashed, never green.
// Frames run only while a pulse travels. Idle, hidden tab or reduced motion
// means no frames (no permanent loop).

export const LIMITS = Object.freeze({ orbs: 16, beams: 24, pulses: 32, dpr: 1.5 });
const GREEN = "#10b981";
const MAGENTA = "#ec4899";
const PULSE_MS = 1400;

function hash(text) {
  let h = 2166136261;
  for (let i = 0; i < text.length; i += 1) { h ^= text.charCodeAt(i); h = Math.imul(h, 16777619); }
  return h >>> 0;
}

/** Deterministic layout: master left of centre, verifier right, stations on an arc. */
export function layout(nodes, width, height) {
  const out = new Map();
  const stations = nodes.filter((n) => n.kind === "station");
  out.set("courier", { x: width * 0.36, y: height * 0.5, r: Math.min(width, height) * 0.16 });
  out.set("verifier", { x: width * 0.86, y: height * 0.5, r: Math.min(width, height) * 0.045 });
  stations.forEach((node, i) => {
    const t = stations.length === 1 ? 0.5 : i / (stations.length - 1);
    const angle = Math.PI * (0.62 + 0.76 * t);
    const ring = Math.min(width, height) * 0.36;
    const size = 0.035 + (hash(node.id) % 3) * 0.008; // depth by size, stable per id
    out.set(node.id, { x: width * 0.36 + Math.cos(angle) * ring, y: height * 0.5 + Math.sin(angle) * ring,
      r: Math.min(width, height) * size });
  });
  return out;
}

/** Quadratic Bezier control point, offset perpendicular to the chord. */
export function curve(a, b, id) {
  const mx = (a.x + b.x) / 2;
  const my = (a.y + b.y) / 2;
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const len = Math.hypot(dx, dy) || 1;
  const sign = hash(id) % 2 ? 1 : -1;
  const k = (0.18 + (hash(id) % 10) / 100) * sign;
  return { x0: a.x, y0: a.y, cx: mx - (dy / len) * len * k, cy: my + (dx / len) * len * k, x1: b.x, y1: b.y };
}

export function pointOn(c, t) {
  const u = 1 - t;
  return { x: u * u * c.x0 + 2 * u * t * c.cx + t * t * c.x1, y: u * u * c.y0 + 2 * u * t * c.cy + t * t * c.y1 };
}

function orbSprite(make, radius, rim) {
  const size = Math.ceil(radius * 2 + 8);
  const sprite = make(size, size);
  const g = sprite.getContext("2d");
  const c = size / 2;
  const body = g.createRadialGradient(c - radius * 0.35, c - radius * 0.4, radius * 0.05, c, c, radius);
  body.addColorStop(0, "#2a2a33");
  body.addColorStop(0.35, "#0b0b10");
  body.addColorStop(1, "#000000");
  g.fillStyle = body;
  g.beginPath(); g.arc(c, c, radius, 0, Math.PI * 2); g.fill();
  g.globalAlpha = 0.9; g.lineWidth = Math.max(1, radius * 0.06); g.strokeStyle = rim;
  g.beginPath(); g.arc(c, c, radius * 0.97, 0, Math.PI * 2); g.stroke();
  g.globalAlpha = 0.22; g.fillStyle = "#ffffff";
  g.beginPath(); g.ellipse(c - radius * 0.32, c - radius * 0.42, radius * 0.32, radius * 0.16, -0.5, 0, Math.PI * 2); g.fill();
  return sprite;
}

export function createBeams(canvas, env = {}) {
  const win = env.window ?? globalThis.window;
  const doc = env.document ?? globalThis.document;
  const raf = env.requestAnimationFrame ?? ((cb) => win.requestAnimationFrame(cb));
  const caf = env.cancelAnimationFrame ?? ((id) => win.cancelAnimationFrame(id));
  const now = env.now ?? (() => performance.now());
  const make = env.makeCanvas ?? ((w, h) => { const c = doc.createElement("canvas"); c.width = w; c.height = h; return c; });
  const reduced = env.reducedMotion ?? (() => !!(win && win.matchMedia && win.matchMedia("(prefers-reduced-motion: reduce)").matches));
  const dpr = Math.min(env.dpr ?? (win && win.devicePixelRatio) ?? 1, LIMITS.dpr);
  const ctx = canvas.getContext("2d");
  const seen = new Set();
  const sprites = new Map();
  let pulses = [];
  let scene = { nodes: [], edges: [], mode: "live", pos: new Map(), curves: new Map() };
  let frame = 0;
  let alive = true;
  const stats = { frames: 0, totalMs: 0, maxMs: 0 };

  const width = () => canvas.width / dpr;
  const height = () => canvas.height / dpr;
  const hidden = () => !!(doc && doc.visibilityState === "hidden");

  function sprite(radius, rim) {
    const key = `${Math.round(radius)}|${rim}`;
    if (!sprites.has(key)) sprites.set(key, orbSprite(make, radius, rim));
    return sprites.get(key);
  }

  function strokeBeam(c, color, dashed) {
    ctx.setLineDash(dashed ? [6, 6] : []);
    ctx.beginPath(); ctx.moveTo(c.x0, c.y0); ctx.quadraticCurveTo(c.cx, c.cy, c.x1, c.y1);
    ctx.strokeStyle = color;
    ctx.globalAlpha = 0.06; ctx.lineWidth = 14; ctx.stroke(); // light cone
    ctx.globalAlpha = 0.18; ctx.lineWidth = 5; ctx.stroke(); // halo
    ctx.globalAlpha = 0.85; ctx.lineWidth = 1.2; ctx.stroke(); // core
  }

  function draw(t) {
    const start = now();
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width(), height());
    ctx.globalCompositeOperation = "lighter";
    for (const edge of scene.edges) {
      // DEMO is enforced here too, whatever colour the caller passed.
      const color = scene.mode === "demo" ? MAGENTA : (edge.color === GREEN && edge.verified !== true ? "#14b8a6" : edge.color);
      strokeBeam(scene.curves.get(edge.id), color, scene.mode === "demo" || edge.state === "UNKNOWN");
    }
    ctx.setLineDash([]);
    for (const p of pulses) {
      const k = Math.min(1, (t - p.start) / PULSE_MS);
      const c = scene.curves.get(p.edge);
      if (!c) continue;
      for (let tail = 0; tail < 4; tail += 1) {
        const pt = pointOn(c, Math.max(0, k - tail * 0.03));
        ctx.globalAlpha = 0.9 - tail * 0.22;
        ctx.fillStyle = p.color;
        ctx.beginPath(); ctx.arc(pt.x, pt.y, 3.2 - tail * 0.6, 0, Math.PI * 2); ctx.fill();
      }
    }
    ctx.globalCompositeOperation = "source-over";
    ctx.globalAlpha = 1;
    for (const node of scene.nodes) {
      const p = scene.pos.get(node.id);
      if (!p) continue;
      const s = sprite(p.r, scene.mode === "demo" ? MAGENTA : node.color);
      ctx.drawImage(s, p.x - s.width / 2, p.y - s.height / 2);
    }
    const spent = now() - start;
    stats.frames += 1; stats.totalMs += spent; stats.maxMs = Math.max(stats.maxMs, spent);
  }

  function loop(t) {
    frame = 0;
    if (!alive || hidden()) return; // a hidden tab gets no frames at all
    pulses = pulses.filter((p) => t - p.start < PULSE_MS);
    draw(t);
    if (pulses.length) frame = raf(loop);
  }

  function kick() {
    if (!alive || hidden()) return;
    if (!frame) frame = raf(loop);
  }

  function onVisibility() {
    if (hidden()) { if (frame) caf(frame); frame = 0; } else { draw(now()); if (pulses.length) kick(); }
  }
  if (doc && doc.addEventListener) doc.addEventListener("visibilitychange", onVisibility);

  return {
    setGraph(graph, mode = "live") {
      const nodes = (graph && graph.nodes ? graph.nodes : []).slice(0, LIMITS.orbs);
      const ids = new Set(nodes.map((n) => n.id));
      const edges = (graph && graph.edges ? graph.edges : []).filter((e) => ids.has(e.from) && ids.has(e.to)).slice(0, LIMITS.beams);
      const pos = layout(nodes, width(), height());
      const curves = new Map(edges.map((e) => [e.id, curve(pos.get(e.from), pos.get(e.to), e.id)]));
      scene = { nodes, edges, mode: mode === "demo" ? "demo" : "live", pos, curves };
      const t = now();
      if (!reduced()) {
        for (const edge of edges) {
          if (typeof edge.event_id !== "string" || !edge.event_id || seen.has(edge.event_id)) continue;
          seen.add(edge.event_id);
          const green = edge.verified === true && scene.mode === "live";
          pulses.push({ edge: edge.id, start: t, color: green ? GREEN : (scene.mode === "demo" ? MAGENTA : edge.color === GREEN ? "#14b8a6" : edge.color) });
        }
        if (pulses.length > LIMITS.pulses) pulses = pulses.slice(-LIMITS.pulses);
      }
      if (!hidden()) draw(t);
      if (pulses.length) kick();
    },
    stats: () => ({ ...stats, avgMs: stats.frames ? stats.totalMs / stats.frames : 0, pulses: pulses.length, sprites: sprites.size, running: frame !== 0 }),
    destroy() {
      alive = false;
      if (frame) caf(frame);
      frame = 0;
      pulses = [];
      sprites.clear();
      if (doc && doc.removeEventListener) doc.removeEventListener("visibilitychange", onVisibility);
    },
  };
}
