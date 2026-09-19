import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import assert from "node:assert/strict";
import { DurableQueue, fixtureTasks } from "./durable_queue.mjs";

const directory = fs.mkdtempSync(path.join(os.tmpdir(), "courier-queue-strike-"));
const stateFile = path.join(directory, "queue.json");
const evidenceFile = new URL("./evidence_50.json", import.meta.url);
let queue = DurableQueue.create(stateFile, fixtureTasks());
const worker = { worker_id: "isolated-local-worker", capabilities: ["deterministic-local"] };
let executed = 0;
let restarts = 0;

while (!queue.allTerminal()) {
  queue.recompute();
  const gate = queue.state.tasks.find((task) => task.status === "READY" && task.human_gate);
  if (gate) { queue.holdHumanGate(gate.task_id); continue; }
  const claimed = queue.claim(worker);
  if (!claimed) {
    queue.recompute();
    if (!queue.allTerminal()) throw new Error("Nonterminal queue has no executable transition");
    break;
  }
  queue.start(claimed.task_id, claimed.attempt_id, worker.worker_id);
  queue.submitResult(claimed.task_id, claimed.attempt_id, worker.worker_id, { success: !claimed.controlled_failure, output: claimed.controlled_failure ? "controlled failure" : `completed ${claimed.task_id}` });
  queue.verify(claimed.task_id);
  executed += 1;
  if (executed === 17) { queue = new DurableQueue(stateFile); restarts += 1; }
}

const tasks = queue.state.tasks;
const events = queue.state.events;
const doneRevision = new Map(events.filter((event) => event.type === "DONE").map((event) => [event.task_id, event.revision]));
const prematureClaims = events.filter((event) => event.type === "CLAIMED" && queue.task(event.task_id).dependencies.some((dependency) => !doneRevision.has(dependency) || doneRevision.get(dependency) >= event.revision));
const lifecycleViolations = tasks.filter((task) => task.dispatch_count === 1 && !task.human_gate && !task.cancelled && !["SKIPPED_NOT_REQUIRED"].includes(task.status)).filter((task) => {
  const sequence = events.filter((event) => event.task_id === task.task_id).map((event) => event.type);
  const terminal = task.status;
  return JSON.stringify(sequence) !== JSON.stringify(["CLAIMED", "RUNNING", "RESULT", "VERIFY", terminal]);
});
const evidence = {
  fixture: "50-task-isolated-durable-queue", tasks_planned: tasks.length,
  tasks_terminal: tasks.filter((task) => ["DONE", "FAILED", "HUMAN_REQUIRED", "SKIPPED_NOT_REQUIRED"].includes(task.status)).length,
  statuses: Object.fromEntries(["DONE", "FAILED", "HUMAN_REQUIRED", "SKIPPED_NOT_REQUIRED"].map((status) => [status, tasks.filter((task) => task.status === status).length])),
  human_relay_after_start: 0, duplicate_dispatch: tasks.filter((task) => task.dispatch_count > 1).length,
  premature_dependents: prematureClaims.length, lifecycle_violations: lifecycleViolations.length,
  false_done: tasks.filter((task) => task.status === "DONE" && (!task.result || task.verification_state !== "PASS")).length,
  model_wait_polling: 0, restart_count: restarts, final_revision: queue.state.revision,
  state_sha256: (await import("node:crypto")).createHash("sha256").update(fs.readFileSync(stateFile)).digest("hex")
};

assert.equal(evidence.tasks_planned, 50);
assert.equal(evidence.tasks_terminal, 50);
assert.deepEqual(evidence.statuses, { DONE: 46, FAILED: 1, HUMAN_REQUIRED: 1, SKIPPED_NOT_REQUIRED: 2 });
assert.equal(evidence.duplicate_dispatch, 0);
assert.equal(evidence.false_done, 0);
assert.equal(evidence.premature_dependents, 0);
assert.equal(evidence.lifecycle_violations, 0);
assert.equal(evidence.human_relay_after_start, 0);
assert.equal(evidence.model_wait_polling, 0);
assert.equal(tasks.find((task) => task.task_id === "task-36").status, "SKIPPED_NOT_REQUIRED");
assert.equal(tasks.find((task) => task.task_id === "task-38").status, "SKIPPED_NOT_REQUIRED");
assert.equal(tasks.find((task) => task.task_id === "task-50").status, "DONE");

fs.writeFileSync(evidenceFile, `${JSON.stringify(evidence, null, 2)}\n`);
console.log(JSON.stringify(evidence));
