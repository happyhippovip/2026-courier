// FAKE worker for demos and fixtures. Deterministic, local only, no network,
// no provider calls. Operates strictly inside COURIER_FAKE_WORKSPACE.
// Every output is labeled provenance=FAKE_LOCAL. Never emits REAL.
import { appendFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";

const ws = resolve(process.env.COURIER_FAKE_WORKSPACE || "/tmp/courier-fake-ws");
mkdirSync(ws, { recursive: true });
const mode = process.argv[2] || "success";
const attemptId = process.env.COURIER_ATTEMPT || "attempt-demo-1";
const eventsLog = join(ws, "fake_events.jsonl");

function emit(obj) {
  appendFileSync(eventsLog, JSON.stringify({ provenance: "FAKE_LOCAL", attempt_id: attemptId, ...obj }) + "\n");
}
function scopedPath(rel) {
  const p = resolve(ws, rel);
  if (!p.startsWith(ws + "/")) { console.log("HUMAN_GATE_REQUIRED scope_escape=" + rel); process.exit(42); }
  mkdirSync(join(p, ".."), { recursive: true });
  return p;
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const target = process.argv[3] || "out/result.txt";

async function main() {
  switch (mode) {
    case "success": {
      const p = scopedPath(target); emit({ event: "STARTED", mode });
      writeFileSync(p, "fake result for " + attemptId + "\n");
      emit({ event: "RESULT", result_id: "res-" + attemptId, path: target });
      console.log("RESULT res-" + attemptId); break;
    }
    case "scope_guarded": {
      // Advisory lock demo for MUSE 117: second writer on same scope must wait.
      const lock = scopedPath(target + ".lock");
      if (existsSync(lock)) { console.log("WAITING_SCOPE holder=" + readFileSync(lock, "utf8").trim()); process.exit(10); }
      writeFileSync(lock, attemptId); emit({ event: "STARTED", mode });
      await sleep(300); writeFileSync(scopedPath(target), "written by " + attemptId + "\n");
      await sleep(100); break;
    }
    case "crash_after_persist": {
      const p = scopedPath(target); emit({ event: "STARTED", mode });
      writeFileSync(p, "effect complete\n"); writeFileSync(join(ws, "result-" + attemptId + ".json"), JSON.stringify({ result_id: "res-" + attemptId, ack: false }));
      emit({ event: "CRASH", note: "ACK lost after persist" }); process.exit(3);
    }
    case "unknown_effect": {
      emit({ event: "STARTED", mode }); await sleep(100);
      writeFileSync(join(ws, "partial-" + attemptId + ".marker"), "begun, no confirmation");
      console.log("UNKNOWN_EFFECT connection died before result confirmation"); process.exit(7);
    }
    case "human_gate": {
      console.log("HUMAN_GATE_REQUIRED action=delete_outside_testscope target=" + target); process.exit(42);
    }
    case "two_lane": {
      const lane = process.argv[3] || "lane1"; emit({ event: "STARTED", mode, lane, ts: Date.now() });
      await sleep(400); emit({ event: "RESULT", lane, ts: Date.now() }); console.log("RESULT lane=" + lane); break;
    }
    case "large_import": {
      const n = 100000, out = scopedPath("import/records.jsonl");
      mkdirSync(join(ws, "import"), { recursive: true });
      const t0 = Date.now();
      let fh = ""; const preview = [];
      for (let i = 0; i < n; i++) { const line = JSON.stringify({ i, topic: "t" + (i % 5) }); if (i < 10) preview.push(line); fh += line + "\n"; if (i % 20000 === 19999) { appendFileSync(out, fh); fh = ""; } }
      appendFileSync(out, fh);
      writeFileSync(join(ws, "import/preview.json"), JSON.stringify(preview));
      console.log("IMPORT records=" + n + " preview=10 streaming=yes provider_calls=0 ms=" + (Date.now() - t0)); break;
    }
    case "auth_expired": console.log("AUTH_EXPIRED worker=fake reason=expired_key"); process.exit(11);
    case "permanent_fail": console.log("PERMANENT_FAIL reason=provider_rejected_input"); process.exit(12);
    case "provider_429": console.log("PROVIDER_429 retry_after_s=60 circuit=HALF_OPEN_probe_scheduled"); process.exit(13);
    default: console.log("UNKNOWN_MODE " + mode); process.exit(2);
  }
}
main();
