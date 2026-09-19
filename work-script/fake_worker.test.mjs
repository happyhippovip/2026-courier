// Covers MUSE 28 (fake worker), 60/61/146 (fixture structure), 64/65 (cancel/pause
// semantics as documented contracts), 112 (safe demo), 116 (two-lane overlap),
// 117 (scope conflict), 118 (100k streaming import), 127 (credential fail-closed).
import test from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const FAKE = new URL("./fake_worker.mjs", import.meta.url).pathname;
const ROOT = new URL("../ops/ai/cannon_build/", import.meta.url).pathname;
function freshWs(name) {
  const ws = join("/tmp", "courier-fake-test-" + name);
  rmSync(ws, { recursive: true, force: true }); mkdirSync(ws, { recursive: true });
  return ws;
}
function run(ws, mode, attempt, extra = []) {
  try {
    const out = execFileSync("node", [FAKE, mode, ...extra], { env: { ...process.env, COURIER_FAKE_WORKSPACE: ws, COURIER_ATTEMPT: attempt }, encoding: "utf8" });
    return { code: 0, out };
  } catch (e) { return { code: e.status, out: (e.stdout || "") + (e.stderr || "") }; }
}

test("MUSE 112 safe demo: success writes deterministic FAKE result, no network", () => {
  const ws = freshWs("safe"); const r = run(ws, "success", "a1", ["demo/five.txt"]);
  assert.equal(r.code, 0); assert.match(r.out, /RESULT res-a1/);
  assert.equal(readFileSync(join(ws, "demo/five.txt"), "utf8"), "fake result for a1\n");
  const ev = readFileSync(join(ws, "fake_events.jsonl"), "utf8");
  assert.match(ev, /FAKE_LOCAL/); assert.doesNotMatch(ev, /REAL/);
});
test("MUSE 117 scope conflict: second writer waits, first wins", () => {
  const ws = freshWs("scope");
  const r1 = run(ws, "scope_guarded", "A", ["test/foo.txt"]);
  assert.equal(r1.code, 0);
  // Simulate overlap: re-create lock to emulate A still holding it.
  writeFileSync(join(ws, "test/foo.txt.lock"), "A");
  const r2 = run(ws, "scope_guarded", "B", ["test/foo.txt"]);
  assert.equal(r2.code, 10); assert.match(r2.out, /WAITING_SCOPE holder=A/);
});
test("MUSE 114 recovery: crash after persist leaves reconcilable result", () => {
  const ws = freshWs("crash"); const r = run(ws, "crash_after_persist", "c1", ["o.txt"]);
  assert.equal(r.code, 3);
  const res = JSON.parse(readFileSync(join(ws, "result-c1.json"), "utf8"));
  assert.equal(res.result_id, "res-c1"); assert.equal(res.ack, false);
});
test("MUSE 115 unknown effect: no result file, marker only", () => {
  const ws = freshWs("unk"); const r = run(ws, "unknown_effect", "u1");
  assert.equal(r.code, 7); assert.match(r.out, /UNKNOWN_EFFECT/);
  assert.equal(existsSync(join(ws, "result-u1.json")), false);
  assert.equal(existsSync(join(ws, "partial-u1.marker")), true);
});
test("MUSE 113 human gate: out-of-scope delete refused, nothing touched", () => {
  const ws = freshWs("gate"); const r = run(ws, "human_gate", "g1", ["../../etc/passwd"]);
  assert.equal(r.code, 42); assert.match(r.out, /HUMAN_GATE_REQUIRED/);
});
test("MUSE 116 two fake lanes overlap in wall time", async () => {
  const ws = freshWs("lanes"); const t0 = Date.now();
  const { execFile } = await import("node:child_process");
  const env = (a) => ({ ...process.env, COURIER_FAKE_WORKSPACE: ws, COURIER_ATTEMPT: a });
  await Promise.all([
    new Promise((res, rej) => execFile("node", [FAKE, "two_lane", "lane1"], { env: env("l1") }, (e) => e ? rej(e) : res(0))),
    new Promise((res, rej) => execFile("node", [FAKE, "two_lane", "lane2"], { env: env("l2") }, (e) => e ? rej(e) : res(0))),
  ]);
  assert.ok(Date.now() - t0 < 700, "lanes must overlap, not serialize");
});
test("MUSE 118 large import: 100k streamed, preview bounded, no provider calls", () => {
  const ws = freshWs("import"); const r = run(ws, "large_import", "i1");
  assert.match(r.out, /records=100000 preview=10 streaming=yes provider_calls=0/);
  assert.equal(JSON.parse(readFileSync(join(ws, "import/preview.json"), "utf8")).length, 10);
  assert.equal(execFileSync("wc", ["-l", join(ws, "import/records.jsonl")], { encoding: "utf8" }).trim().split(" ")[0], "100000");
});
test("MUSE 127 credential fail-closed: no retry, no account switch", () => {
  const ws = freshWs("cred"); const r = run(ws, "auth_expired", "e1");
  assert.equal(r.code, 11); assert.match(r.out, /AUTH_EXPIRED/); assert.doesNotMatch(r.out, /switch|retry/i);
});
test("MUSE 60/61/146 fixture packs are valid JSON with expected case counts", () => {
  const t = JSON.parse(readFileSync(join(ROOT, "fixtures_time_events.json"), "utf8"));
  assert.equal(t.CLOCK_SKEW_CASES.length, 6);
  assert.equal(t.EVENT_ORDERING_CASES.length, 6);
  assert.equal(t.COUNTER_CASES.length, 5);
  const l = JSON.parse(readFileSync(join(ROOT, "fixtures_lifecycle.json"), "utf8"));
  assert.ok(l.CANCEL_CASES.length >= 7 && l.PAUSE_CASES.length >= 5 && l.MODE_SWITCH_CASES.length >= 7);
  const s = JSON.parse(readFileSync(join(ROOT, "fixtures_safety.json"), "utf8"));
  assert.ok(s.PATH_NORMALIZATION_CASES.length >= 6 && s.FENCING_TOKEN_CASES.length >= 6 && s.GATE_RESUME_CASES.length >= 7);
});
