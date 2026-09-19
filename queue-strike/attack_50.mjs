import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import assert from "node:assert/strict";
import { DurableQueue, fixtureTasks } from "./durable_queue.mjs";

const file = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "courier-queue-attack-")), "queue.json");
let primary = DurableQueue.create(file, fixtureTasks());
const worker = { worker_id: "worker-a", capabilities: ["deterministic-local"] };
primary.recompute();

const first = primary.claim(worker);
assert.equal(first.task_id, "task-01");
assert.equal(primary.task("task-11").status, "PLANNED", "dependent must not become READY before task-01 DONE");

const afterRestart = new DurableQueue(file);
assert.equal(afterRestart.task("task-01").status, "CLAIMED");
assert.equal(afterRestart.task("task-01").lease.owner, worker.worker_id);
const second = afterRestart.claim(worker);
assert.notEqual(second.task_id, first.task_id, "restart must not double-claim active task");

assert.throws(() => primary.start(first.task_id, "wrong-attempt", worker.worker_id), /Invalid start identity/);
primary = new DurableQueue(file);
primary.start(first.task_id, first.attempt_id, worker.worker_id);
primary.submitResult(first.task_id, first.attempt_id, worker.worker_id, { success: true, output: "ok" });
assert.throws(() => primary.submitResult(first.task_id, first.attempt_id, worker.worker_id, { success: true, output: "duplicate" }), /Invalid or duplicate result/);
primary.verify(first.task_id);
primary.recompute();
assert.equal(primary.task("task-11").status, "READY");
assert.throws(() => primary.verify(second.task_id), /Unverifiable result/);
assert.equal(primary.task(second.task_id).status, "CLAIMED");

console.log(JSON.stringify({
  active_lease_survives_restart: true,
  double_claim_rejected: true,
  wrong_attempt_rejected: true,
  duplicate_result_rejected: true,
  premature_dependent_rejected: true,
  false_done_rejected: true
}));
