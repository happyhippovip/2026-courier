// TITAN truth-first: the universe never shows more certainty than the snapshot proves.
// Green needs the journaled RESULT_ACCEPTED proof; the core is never green; teams
// follow their members; beams pulse only for a journal-proven edge.
import { test } from "node:test";
import assert from "node:assert/strict";
import { UNIVERSE_STATUS, buildUniverseModel, renderKolibriUniverse, toBeamGraph } from "../../courier_hub/static/kolibri_universe.mjs";
import { createBeams } from "../../courier_hub/static/kolibri_beams.mjs";

const AT = "2026-10-21T10:00:00Z";
const PROOF_ID = "journal:7:RESULT_ACCEPTED";
const GREEN = "#10b981";

const ledger = (items) => ({ ledger: { available: true, items } });

test("truth 1: a done ledger item without the journal proof is never VERIFIED", () => {
  for (const item of [
    { id: "t1", pile: "done" },
    { id: "t1", pile: "done", verified: true },
    { id: "t1", pile: "done", verified: true, event_id: "task:t1:verified" },
    { id: "t1", pile: "done", verified: true, event_id: "journal:0:RESULT_ACCEPTED" },
    { id: "t1", pile: "done", verified: "true", event_id: PROOF_ID },
    { id: "t1", pile: "done", event_id: PROOF_ID },
  ]) {
    const p = buildUniverseModel(ledger([item])).projects[0];
    assert.notEqual(p.status, UNIVERSE_STATUS.VERIFIED, JSON.stringify(item));
    assert.notEqual(p.color, GREEN, JSON.stringify(item));
    assert.equal(p.event_id, null);
  }
});

test("truth 1: mission status strings VERIFIED/DONE/FINAL_DONE are claims, not proof", () => {
  for (const status of ["VERIFIED", "DONE", "FINAL_DONE"]) {
    const m = buildUniverseModel({ ledger_bridge: { available: true, missions: [{ id: "M1", status }] } });
    assert.equal(m.projects[0].status, UNIVERSE_STATUS.REPORTED, status);
  }
  const unknown = buildUniverseModel({ ledger_bridge: { available: true, missions: [{ id: "M1", status: "UNKNOWN / nicht erreichbar" }] } });
  assert.equal(unknown.projects[0].status, UNIVERSE_STATUS.UNKNOWN);
});

test("truth 1 control: a journal-proven ledger item is VERIFIED and carries its proof id", () => {
  const p = buildUniverseModel(ledger([{ id: "t2", pile: "done", verified: true, event_id: PROOF_ID }])).projects[0];
  assert.equal(p.status, UNIVERSE_STATUS.VERIFIED);
  assert.equal(p.color, GREEN);
  assert.equal(p.event_id, PROOF_ID);
  const viaMission = buildUniverseModel({
    ...ledger([{ id: "task-9", pile: "done", verified: true, event_id: PROOF_ID }]),
    ledger_bridge: { available: true, missions: [{ id: "M9", status: "FINAL_DONE", task_id: "task-9" }] },
  });
  assert.equal(viaMission.projects.find((x) => x.id === "M9").status, UNIVERSE_STATUS.VERIFIED);
});

test("truth 2: the core is never VERIFIED; unknown without any live source", () => {
  for (const snap of [null, {}, { muse_wall: { available: false }, ledger: { available: false } }]) {
    assert.equal(buildUniverseModel(snap).center.status, UNIVERSE_STATUS.UNKNOWN);
  }
  const live = buildUniverseModel({ observed_at: AT, ...ledger([{ id: "t2", pile: "done", verified: true, event_id: PROOF_ID }]) });
  assert.equal(live.center.status, UNIVERSE_STATUS.REPORTED);
});

test("truth 3: team status follows its members, unknown when nothing is known", () => {
  const team = (stations) => buildUniverseModel({ muse_wall: { available: true, stations } }).teams[0].status;
  assert.equal(team([{ id: "S1", state: { value: "BLOCKED" }, blocker: "NO_LEASE", owner: "a" }]), UNIVERSE_STATUS.BLOCKED);
  assert.equal(team([
    { id: "S1", state: { value: "RUNNING" }, owner: "a" },
    { id: "S2", state: { value: "IDLE" }, owner: "a" },
  ]), UNIVERSE_STATUS.REPORTED);
  assert.equal(team([{ id: "S1", state: { value: "IDLE" }, owner: "a" }]), UNIVERSE_STATUS.UNKNOWN);
  assert.equal(team([
    { id: "S1", state: { value: "BLOCKED" }, blocker: "X", owner: "a" },
    { id: "S2", verified: true, event_id: "evt:verifier:1", owner: "a" },
  ]), UNIVERSE_STATUS.BLOCKED);
});

test("truth 3 control: a team is VERIFIED only when every member is verified", () => {
  const m = buildUniverseModel({ muse_wall: { available: true, stations: [
    { id: "S1", verified: true, event_id: "evt:verifier:1", owner: "a" },
    { id: "S2", verified: true, event_id: "evt:verifier:2", owner: "a" },
  ] } });
  assert.equal(m.teams[0].status, UNIVERSE_STATUS.VERIFIED);
  assert.ok(m.teams[0].halo, "decorative halo is separate from the state colour");
});

test("demo: nothing is green, even with a journal proof", () => {
  const m = buildUniverseModel(ledger([{ id: "t2", pile: "done", verified: true, event_id: PROOF_ID }]), { mode: "demo" });
  assert.notEqual(m.projects[0].color, GREEN);
  const html = renderKolibriUniverse(ledger([{ id: "t2", pile: "done", verified: true, event_id: PROOF_ID }]), { mode: "demo" });
  assert.ok(!html.includes(`fill="${GREEN}"`) && !html.includes(`stroke="${GREEN}"`));
});

test("beams: only a journal-proven edge carries an event id and pulses once", () => {
  const snap = {
    muse_wall: { available: true, stations: [
      { id: "S1", state: { value: "RUNNING" }, workkey: "t2" },
      { id: "S2", state: { value: "RUNNING" }, workkey: "t3" },
    ] },
    ...ledger([
      { id: "t2", pile: "done", verified: true, event_id: PROOF_ID },
      { id: "t3", pile: "done" },
    ]),
  };
  const graph = toBeamGraph(buildUniverseModel(snap));
  const withId = graph.edges.filter((e) => e.event_id);
  assert.deepEqual(withId.map((e) => e.id), ["S1->verifier"]);
  assert.ok(withId.every((e) => e.verified === true && e.event_id === PROOF_ID));
  assert.ok(graph.edges.filter((e) => e.from === "courier").every((e) => e.verified === false && e.event_id === null));
  assert.ok(!graph.edges.some((e) => e.from === "S2" && e.to === "verifier"), "an unproven project gets no verifier beam");

  const frames = [];
  const ctx = new Proxy({}, { get: (t, p) => (p in t ? t[p] : (["createRadialGradient", "createLinearGradient"].includes(p) ? () => ({ addColorStop() {} }) : () => {})), set: (t, p, v) => { t[p] = v; return true; } });
  const canvas = { width: 800, height: 450, getContext: () => ctx };
  const doc = { visibilityState: "visible", addEventListener() {}, removeEventListener() {} };
  const beams = createBeams(canvas, { document: doc, dpr: 1, now: () => 0, reducedMotion: () => false,
    requestAnimationFrame: (cb) => { frames.push(cb); return frames.length; }, cancelAnimationFrame() {},
    makeCanvas: (w, h) => ({ width: w, height: h, getContext: () => ctx }) });
  beams.setGraph(graph, "live");
  assert.equal(beams.stats().pulses, 1);
  beams.setGraph(graph, "live");
  assert.equal(beams.stats().pulses, 1, "the same proof never pulses twice");
  beams.destroy();
});
