import { test } from "node:test";
import assert from "node:assert/strict";
import { deriveInsights, UNKNOWN } from "../../courier_hub/static/kolibri_insight.mjs";
import { createBeams, LIMITS, layout, curve, pointOn } from "../../courier_hub/static/kolibri_beams.mjs";
import { paintBiosphere, BIOSPHERE_LIMITS, BIOSPHERE_COLORS, prng } from "../../courier_hub/static/kolibri_biosphere.mjs";

const AT = "2026-10-19T10:00:00Z";
const GREEN = "#10b981";

function fakeCtx(log) {
  const grad = { addColorStop() {} };
  const handler = {
    get(target, prop) {
      if (prop in target) return target[prop];
      if (["createRadialGradient", "createLinearGradient"].includes(prop)) return () => grad;
      return (...args) => log.push([prop, ...args]);
    },
    set(target, prop, value) { log.push(["set", prop, value]); target[prop] = value; return true; },
  };
  return new Proxy({}, handler);
}
function fakeCanvas(log, w = 800, h = 450) {
  const c = { width: w, height: h, getContext: () => fakeCtx(log) };
  return c;
}
function env(over = {}) {
  const frames = [];
  let t = 0;
  const doc = { visibilityState: "visible", addEventListener() {}, removeEventListener() {} };
  return {
    frames, doc,
    advance(ms) { t += ms; const pending = frames.splice(0); pending.forEach((cb) => cb(t)); },
    opts: {
      document: doc, dpr: 1, now: () => t, reducedMotion: () => false,
      requestAnimationFrame: (cb) => { frames.push(cb); return frames.length; },
      cancelAnimationFrame: () => { frames.length = 0; },
      makeCanvas: (w, h) => fakeCanvas([], w, h),
      ...over,
    },
  };
}
const snap = (over = {}) => ({
  observed_at: AT,
  ledger: { available: true, source: "courier journal (courier.db)", at: AT,
    counts: { needs_you: 1, working: 2, done: 2 },
    items: [
      { id: "t1", pile: "working", source: "j", at: "2026-10-19T09:48:00Z" },
      { id: "t2", pile: "done", source: "j", at: AT, verified: true, event_id: "journal:7:RESULT_ACCEPTED" },
      { id: "t3", pile: "done", source: "j", at: AT },
    ] },
  muse_wall: { available: true, stations: [
    { id: "MUSE-1", heartbeat: true, state: { value: "RUNNING", source: "w", at: AT } },
    { id: "MUSE-2", heartbeat: false, state: { value: "Pause", source: "w", at: AT }, blocker: { value: "BLOCKED", source: "w", at: AT } },
  ] },
  ledger_bridge: { available: true, missions: [{ id: "A", status: "POSTED", reason: "evidence_missing", source: "b", at: AT }] },
  ...over,
});

test("insight: real queue counts with source; missing counts are UNKNOWN, never 0", () => {
  const i = deriveInsights(snap(), AT);
  assert.equal(i.queue.working.value, 2);
  assert.equal(i.queue.working.source, "courier journal (courier.db)");
  const none = deriveInsights({}, AT);
  for (const pile of ["needs_you", "working", "done"]) assert.equal(none.queue[pile].value, UNKNOWN);
  assert.equal(none.verifier.state, "UNKNOWN");
});

test("insight: waiting only with a recorded timestamp; blockers and missing evidence surface", () => {
  const i = deriveInsights(snap(), AT);
  assert.deepEqual(i.waiting.map((w) => [w.target, w.minutes]), [["t1", 12]]);
  assert.ok(i.blockers.some((b) => b.target === "MUSE-2"));
  assert.deepEqual(i.missingEvidence.map((m) => m.target).sort(), ["A", "t3"]);
  const noAt = snap(); delete noAt.ledger.items[0].at;
  assert.equal(deriveInsights(noAt, AT).waiting.length, 0);
});

test("insight: green only for verifier evidence with a real event id", () => {
  const i = deriveInsights(snap(), AT);
  const green = i.graph.edges.filter((e) => e.color === GREEN);
  assert.deepEqual(green.map((e) => e.event_id), ["journal:7:RESULT_ACCEPTED"]);
  const fake = snap(); fake.ledger.items[1].event_id = "evt:unknown:0";
  assert.equal(deriveInsights(fake, AT).graph.edges.filter((e) => e.color === GREEN).length, 0);
  const statusOnly = snap(); delete statusOnly.ledger.items[1].verified; statusOnly.ledger.items[1].status = "VERIFIED";
  assert.equal(deriveInsights(statusOnly, AT).graph.edges.filter((e) => e.color === GREEN).length, 0);
  const looseId = snap(); looseId.ledger.items[1].event_id = "evt:canonical:mission:999";
  assert.equal(deriveInsights(looseId, AT).graph.edges.filter((e) => e.color === GREEN).length, 0);
  const worded = snap();
  worded.muse_wall.stations.push({ id: "MUSE-3", heartbeat: true, state: { value: "VERIFIED", source: "w", at: AT } });
  const station = deriveInsights(worded, AT).graph.nodes.find((n) => n.id === "MUSE-3");
  assert.equal(station.state, "UNKNOWN");
  assert.notEqual(station.color, GREEN);
});

test("insight: DEMO has no green edge, no green node and no verifier claim", () => {
  const i = deriveInsights({ ...snap(), mode: "demo" }, AT);
  assert.equal(i.mode, "demo");
  assert.ok(i.graph.edges.every((e) => e.color === "#ec4899" && e.verified === false));
  assert.ok(i.graph.nodes.every((n) => n.color !== GREEN));
  assert.equal(i.verifier.state, "DEMO");
});

test("beams: deterministic layout and curves; budget caps", () => {
  const nodes = [{ id: "courier", kind: "courier" }, { id: "verifier", kind: "verifier" },
    ...Array.from({ length: 30 }, (_, k) => ({ id: `S${k}`, kind: "station" }))];
  const a = layout(nodes, 800, 450);
  const b = layout(nodes, 800, 450);
  assert.deepEqual([...a.entries()], [...b.entries()]);
  const c = curve(a.get("courier"), a.get("verifier"), "e1");
  assert.deepEqual(pointOn(c, 0), { x: c.x0, y: c.y0 });
  assert.deepEqual(curve(a.get("courier"), a.get("verifier"), "e1"), c);
  const e = env();
  const beams = createBeams(fakeCanvas([]), e.opts);
  const edges = Array.from({ length: 60 }, (_, k) => ({ id: `e${k}`, from: `S${k % 30}`, to: "courier", color: "#a855f7", event_id: `ev${k}` }));
  beams.setGraph({ nodes, edges }, "live");
  assert.ok(beams.stats().pulses <= LIMITS.pulses);
  beams.destroy();
});

test("beams: one pulse per event id, no frames when idle, none while hidden", () => {
  const e = env();
  const beams = createBeams(fakeCanvas([]), e.opts);
  const graph = deriveInsights(snap(), AT).graph;
  beams.setGraph(graph, "live");
  assert.equal(beams.stats().pulses, 1);
  beams.setGraph(graph, "live"); // replay of the same snapshot
  assert.equal(beams.stats().pulses, 1);
  for (let k = 0; k < 120; k += 1) e.advance(16);
  assert.equal(e.frames.length, 0, "no frame scheduled after the pulse ends");
  assert.equal(beams.stats().running, false);
  const h = env(); h.doc.visibilityState = "hidden";
  const hb = createBeams(fakeCanvas([]), h.opts);
  hb.setGraph(graph, "live");
  assert.equal(h.frames.length, 0, "hidden tab schedules no frame");
  hb.destroy(); beams.destroy();
});

test("beams: reduced motion draws once, no pulses; LIVE without evidence never strokes green", () => {
  const log = [];
  const e = env({ reducedMotion: () => true });
  const beams = createBeams(fakeCanvas(log), e.opts);
  beams.setGraph(deriveInsights(snap(), AT).graph, "live");
  assert.equal(beams.stats().pulses, 0);
  assert.equal(e.frames.length, 0);
  const log2 = [];
  const e2 = env();
  const b2 = createBeams(fakeCanvas(log2), e2.opts);
  const noProof = snap(); delete noProof.ledger.items[1].verified;
  b2.setGraph(deriveInsights(noProof, AT).graph, "live");
  for (let k = 0; k < 120; k += 1) e2.advance(16);
  assert.ok(!log2.some((x) => x[0] === "set" && (x[1] === "strokeStyle" || x[1] === "fillStyle") && x[2] === GREEN));
  b2.destroy(); beams.destroy();
});

test("beams: destroy frees sprites and pending frames (no leak)", () => {
  const e = env();
  const beams = createBeams(fakeCanvas([]), e.opts);
  beams.setGraph(deriveInsights(snap(), AT).graph, "live");
  assert.ok(beams.stats().sprites > 0);
  beams.destroy();
  assert.equal(beams.stats().sprites, 0);
  assert.equal(beams.stats().running, false);
});

test("biosphere: deterministic, within budget, never the verified green", () => {
  const log1 = []; const log2 = [];
  const r1 = paintBiosphere(fakeCanvas(log1), { width: 800, height: 450, dpr: 3 });
  const r2 = paintBiosphere(fakeCanvas(log2), { width: 800, height: 450, dpr: 3 });
  assert.deepEqual(r1, r2);
  assert.equal(r1.glyphs.length, BIOSPHERE_LIMITS.glyphs);
  assert.ok(r1.clusters.length <= BIOSPHERE_LIMITS.clusters);
  assert.ok(!Object.values(BIOSPHERE_COLORS).includes(GREEN));
  assert.ok(!JSON.stringify(log1).includes(GREEN));
  assert.equal(prng(1)(), prng(1)());
});

test("beams: DEMO strokes only magenta even for edges added outside insight; green needs verified", () => {
  const log = [];
  const e = env();
  const beams = createBeams(fakeCanvas(log), e.opts);
  const graph = { nodes: [{ id: "courier", kind: "courier", color: "#3b82f6" }, { id: "verifier", kind: "verifier", color: "#d8b46a" }],
    edges: [{ id: "x", from: "courier", to: "verifier", color: "#06b6d4", event_id: "fx:1" },
            { id: "g", from: "courier", to: "verifier", color: GREEN, verified: false, event_id: "fx:2" }] };
  beams.setGraph(graph, "demo");
  for (let k = 0; k < 120; k += 1) e.advance(16);
  const colors = log.filter((x) => x[0] === "set" && (x[1] === "strokeStyle" || x[1] === "fillStyle")).map((x) => x[2]);
  assert.ok(colors.length > 0 && colors.every((c) => c === "#ec4899"), JSON.stringify([...new Set(colors)]));
  const log2 = []; const e2 = env();
  const b2 = createBeams(fakeCanvas(log2), e2.opts);
  b2.setGraph(graph, "live");
  for (let k = 0; k < 120; k += 1) e2.advance(16);
  assert.ok(!log2.some((x) => x[0] === "set" && x[2] === GREEN), "unverified green edge is not drawn green");
  beams.destroy(); b2.destroy();
});
