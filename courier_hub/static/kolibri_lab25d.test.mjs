/* Focused unit tests for the Kolibri 2.5D Lab core (DOM-free logic).
 * Run: node --test courier_hub/static/kolibri_lab25d.test.mjs
 */
import test from "node:test";
import assert from "node:assert/strict";
import { RANK, createLab, pulseFor, stationFor, validEvent } from "./kolibri_lab25d.mjs";

// NOTE: forwardAllowed is module-private; tests pin behavior via applyEvent.

const ev = (over = {}) => ({
  event_id: "e1",
  workkey: "WK-A",
  source: "A",
  target: "B",
  status: "QUEUED",
  timestamp: "2026-10-18T04:00:00Z",
  ...over,
});

test("forward chain A->B->C applies step by step", () => {
  const lab = createLab({ mode: "live" });
  const chain = ["QUEUED", "READY", "RUNNING", "TRANSFERRED", "VERIFYING", "VERIFIED", "DONE"];
  let n = 0;
  for (const status of chain) {
    n += 1;
    const res = lab.applyEvent(ev({ event_id: `e${n}`, status }));
    assert.equal(res.applied, true, `${status}: ${res.reason || "ok"}`);
  }
  const snap = lab.snapshot();
  assert.equal(snap.workkeys["WK-A"].status, "DONE");
  assert.equal(snap.workkeys["WK-A"].station, "C");
});

test("first-seen live status is accepted with evidence (mid-flight join)", () => {
  const lab = createLab();
  const res = lab.applyEvent(ev({ event_id: "e1", status: "RUNNING" }));
  assert.equal(res.applied, true);
  assert.equal(res.from, "UNKNOWN");
  const snap = lab.snapshot();
  assert.equal(snap.workkeys["WK-A"].status, "RUNNING");
  assert.equal(snap.workkeys["WK-A"].station, "B");
  assert.deepEqual(snap.workkeys["WK-A"].evidence, ["e1"]);
});

test("claimed completion without a tracked chain is rejected", () => {
  const lab = createLab();
  const res = lab.applyEvent(ev({ event_id: "e1", status: "DONE" }));
  assert.equal(res.applied, false);
  assert.equal(res.reason, "out-of-order");
  assert.equal(lab.snapshot().workkeys["WK-A"].status, "UNKNOWN");
});

test("backward transition is rejected as out-of-order", () => {
  const lab = createLab();
  lab.applyEvent(ev({ event_id: "e1", status: "QUEUED" }));
  lab.applyEvent(ev({ event_id: "e2", status: "READY" }));
  const res = lab.applyEvent(ev({ event_id: "e3", status: "QUEUED" }));
  assert.equal(res.applied, false);
  assert.equal(res.reason, "out-of-order");
  assert.equal(lab.snapshot().workkeys["WK-A"].status, "READY");
});

test("duplicate event_id never double-applies", () => {
  const lab = createLab();
  assert.equal(lab.applyEvent(ev({ event_id: "dup", status: "QUEUED" })).applied, true);
  const again = lab.applyEvent(ev({ event_id: "dup", status: "READY" }));
  assert.equal(again.applied, false);
  assert.equal(again.reason, "duplicate");
  assert.equal(lab.snapshot().workkeys["WK-A"].status, "QUEUED");
});

test("first sighting cannot claim VERIFIED or DONE", () => {
  const lab = createLab();
  const verified = lab.applyEvent(ev({ event_id: "v-cold", status: "VERIFIED" }));
  assert.equal(verified.applied, false);
  assert.equal(verified.reason, "out-of-order");
  assert.equal(verified.pulse, undefined);
  const done = lab.applyEvent(ev({ event_id: "d-cold", status: "DONE" }));
  assert.equal(done.applied, false);
  assert.equal(done.reason, "out-of-order");
  assert.equal(lab.snapshot().counters.pulses, 0);
  assert.equal(lab.snapshot().workkeys["WK-A"].status, "UNKNOWN");
});

test("unknown workkey registers as UNKNOWN, fail edges always allowed", () => {
  const lab = createLab();
  const blocked = lab.applyEvent(ev({ event_id: "b1", status: "BLOCKED" }));
  assert.equal(blocked.applied, true);
  assert.equal(blocked.from, "UNKNOWN");
  assert.equal(lab.snapshot().workkeys["WK-A"].station, null);
});

test("terminal states never advance", () => {
  const lab = createLab();
  lab.applyEvent(ev({ event_id: "e1", status: "QUEUED" }));
  lab.applyEvent(ev({ event_id: "e2", status: "BLOCKED" }));
  const res = lab.applyEvent(ev({ event_id: "e3", status: "READY" }));
  assert.equal(res.applied, false);
  assert.equal(res.reason, "out-of-order");
});

test("bad shapes are rejected without state change", () => {
  const lab = createLab();
  assert.equal(lab.applyEvent({}).applied, false);
  assert.equal(lab.applyEvent(ev({ status: "NOPE" })).applied, false);
  assert.equal(lab.applyEvent(ev({ event_id: "" })).applied, false);
  assert.deepEqual(lab.snapshot().workkeys, {});
});

test("replay mode applies state but emits no success pulse", () => {
  const lab = createLab({ mode: "replay" });
  const chain = ["QUEUED", "READY", "RUNNING", "TRANSFERRED", "VERIFYING", "VERIFIED", "DONE"];
  let n = 0;
  for (const status of chain) {
    n += 1;
    const res = lab.applyEvent(ev({ event_id: `r${n}`, status }));
    assert.equal(res.applied, true);
    if (status === "VERIFIED" || status === "DONE") assert.equal(res.pulse, null);
  }
  assert.equal(lab.snapshot().counters.pulses, 0);
});

test("demo mode flags records, live mode does not", () => {
  const demo = createLab({ mode: "demo" });
  demo.applyEvent(ev({ event_id: "d1", status: "QUEUED" }));
  assert.equal(demo.snapshot().workkeys["WK-A"].demo, true);
  const live = createLab({ mode: "live" });
  live.applyEvent(ev({ event_id: "l1", status: "QUEUED" }));
  assert.equal(live.snapshot().workkeys["WK-A"].demo, false);
});

test("particle budget caps at 300 and pause/reduced-motion spawn nothing", () => {
  const lab = createLab({ maxParticles: 5 });
  for (let i = 0; i < 20; i += 1) {
    lab.applyEvent(ev({ event_id: `c${i}`, workkey: `WK-${i}`, status: "QUEUED" }));
  }
  assert.ok(lab.snapshot().particles.length <= 5);
  const paused = createLab({ paused: true });
  paused.applyEvent(ev({ event_id: "p1", status: "QUEUED" }));
  assert.equal(paused.snapshot().particles.length, 0);
  assert.equal(paused.snapshot().counters.applied, 1); // state still applies
  const reduced = createLab({ reducedMotion: true });
  reduced.applyEvent(ev({ event_id: "m1", status: "QUEUED" }));
  assert.equal(reduced.snapshot().particles.length, 0);
});

test("station and pulse mapping cover the required flow", () => {
  assert.equal(stationFor("QUEUED"), "A");
  assert.equal(stationFor("READY"), "A");
  assert.equal(stationFor("RUNNING"), "B");
  assert.equal(stationFor("TRANSFERRED"), "B");
  assert.equal(stationFor("VERIFYING"), "C");
  assert.equal(stationFor("BLOCKED"), null);
  assert.equal(pulseFor("RUNNING", "TRANSFERRED"), "turquoise");
  assert.equal(pulseFor("TRANSFERRED", "VERIFYING"), "gold");
  assert.equal(pulseFor("VERIFYING", "VERIFIED"), "green");
  assert.equal(pulseFor("RUNNING", "BLOCKED"), "red");
  assert.equal(pulseFor("UNKNOWN", "QUEUED"), "violet");
  assert.ok("QUEUED" in RANK && "DONE" in RANK && "UNKNOWN" in RANK);
});

test("validEvent accepts the documented event contract", () => {
  assert.equal(validEvent(ev()), true);
  assert.equal(validEvent(ev({ source: undefined, target: undefined, timestamp: undefined })), true);
});
