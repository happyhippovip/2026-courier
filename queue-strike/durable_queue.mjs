import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";

const TERMINAL = new Set(["DONE", "FAILED", "HUMAN_REQUIRED", "SKIPPED_NOT_REQUIRED"]);
const digest = (value) => crypto.createHash("sha256").update(JSON.stringify(value)).digest("hex");

export class DurableQueue {
  constructor(file) { this.file = file; this.state = JSON.parse(fs.readFileSync(file, "utf8")); }

  static create(file, tasks) {
    if (tasks.length !== 50 || new Set(tasks.map((task) => task.task_id)).size !== 50) throw new Error("Fixture requires 50 unique tasks");
    const taskIds = new Set(tasks.map((task) => task.task_id));
    for (const task of tasks) for (const dependency of task.dependencies) if (!taskIds.has(dependency)) throw new Error(`Unknown dependency ${dependency}`);
    const state = { schema_version: 1, revision: 0, goal_id: "goal-queue-strike-50", events: [], tasks };
    DurableQueue.atomicWrite(file, state);
    return new DurableQueue(file);
  }

  static atomicWrite(file, value) {
    fs.mkdirSync(path.dirname(file), { recursive: true });
    const temporary = `${file}.${process.pid}.tmp`;
    fs.writeFileSync(temporary, `${JSON.stringify(value, null, 2)}\n`, { mode: 0o600 });
    fs.renameSync(temporary, file);
  }

  persist(event) {
    this.state.revision += 1;
    this.state.events.push({ revision: this.state.revision, ...event });
    DurableQueue.atomicWrite(this.file, this.state);
  }

  task(taskId) {
    const task = this.state.tasks.find((item) => item.task_id === taskId);
    if (!task) throw new Error("Unknown task");
    return task;
  }

  recompute() {
    let changed = false;
    for (const task of this.state.tasks) {
      if (task.status !== "PLANNED") continue;
      if (task.cancelled) { task.status = "SKIPPED_NOT_REQUIRED"; task.verification_state = "NOT_REQUIRED"; changed = true; continue; }
      const dependencies = task.dependencies.map((id) => this.task(id));
      if (dependencies.some((dependency) => ["FAILED", "SKIPPED_NOT_REQUIRED", "HUMAN_REQUIRED"].includes(dependency.status))) {
        task.status = "SKIPPED_NOT_REQUIRED"; task.verification_state = "NOT_REQUIRED"; changed = true; continue;
      }
      if (dependencies.every((dependency) => dependency.status === "DONE")) { task.status = "READY"; changed = true; }
    }
    if (changed) this.persist({ type: "FRONTIER_RECOMPUTED" });
    return changed;
  }

  claim(worker) {
    const task = this.state.tasks.find((item) => item.status === "READY" && item.required_capabilities.every((capability) => worker.capabilities.includes(capability)));
    if (!task) return null;
    task.status = "CLAIMED";
    task.attempt_id = `attempt-${task.task_id}-1`;
    task.owner = worker.worker_id;
    task.lease = { lease_id: `lease-${task.task_id}`, owner: worker.worker_id, acquired_revision: this.state.revision + 1 };
    task.dispatch_count += 1;
    this.persist({ type: "CLAIMED", task_id: task.task_id, attempt_id: task.attempt_id, worker_id: worker.worker_id });
    return structuredClone(task);
  }

  start(taskId, attemptId, workerId) {
    const task = this.task(taskId);
    if (task.status !== "CLAIMED" || task.attempt_id !== attemptId || task.owner !== workerId) throw new Error("Invalid start identity");
    task.status = "RUNNING";
    this.persist({ type: "RUNNING", task_id: taskId, attempt_id: attemptId });
  }

  submitResult(taskId, attemptId, workerId, result) {
    const task = this.task(taskId);
    if (task.status !== "RUNNING" || task.attempt_id !== attemptId || task.owner !== workerId || task.result) throw new Error("Invalid or duplicate result");
    task.result = { result_id: `result-${taskId}`, task_id: taskId, attempt_id: attemptId, worker_id: workerId, success: result.success, output: result.output, digest: digest(result) };
    task.status = "RESULT";
    this.persist({ type: "RESULT", task_id: taskId, result_id: task.result.result_id });
  }

  verify(taskId) {
    const task = this.task(taskId);
    if (task.status !== "RESULT" || !task.result || task.result.task_id !== taskId || task.result.attempt_id !== task.attempt_id) throw new Error("Unverifiable result");
    task.status = "VERIFY";
    task.verification_state = task.result.success ? "PASS" : "FAIL";
    this.persist({ type: "VERIFY", task_id: taskId, verdict: task.verification_state });
    task.status = task.result.success ? "DONE" : "FAILED";
    task.lease = null;
    task.owner = null;
    this.persist({ type: task.status, task_id: taskId });
  }

  holdHumanGate(taskId) {
    const task = this.task(taskId);
    if (task.status !== "READY" || !task.human_gate) throw new Error("Invalid Human Gate");
    task.status = "HUMAN_REQUIRED"; task.verification_state = "HUMAN_DECISION_REQUIRED";
    this.persist({ type: "HUMAN_REQUIRED", task_id: taskId });
  }

  allTerminal() { return this.state.tasks.every((task) => TERMINAL.has(task.status)); }
}

export function fixtureTasks() {
  const specs = [];
  const add = (number, dependencies = [], extras = {}) => specs.push({
    task_id: `task-${String(number).padStart(2, "0")}`, goal_id: "goal-queue-strike-50", package_id: "queue-strike@1.0.0",
    dependencies, required_capabilities: ["deterministic-local"], read_scopes: [`fixture/input/${number}`],
    write_scopes: [`fixture/output/${number}`], status: "PLANNED", attempt_id: null, owner: null, lease: null,
    result: null, verification_state: "PENDING", dispatch_count: 0, ...extras
  });
  for (let number = 1; number <= 10; number += 1) add(number);
  add(11, ["task-01"]); for (let number = 12; number <= 20; number += 1) add(number, [`task-${String(number - 1).padStart(2, "0")}`]);
  add(21, ["task-02"]); for (let number = 22; number <= 26; number += 1) add(number, ["task-21"]); add(27, ["task-22", "task-23", "task-24", "task-25", "task-26"]);
  add(28, ["task-03"]); add(29, ["task-28"]); add(30, ["task-28"]); add(31, ["task-29", "task-30"]); add(32, ["task-31"]); add(33, ["task-31"]); add(34, ["task-32", "task-33"]);
  add(35, [], { controlled_failure: true }); add(36, ["task-35"]);
  add(37, [], { human_gate: "APPROVAL_REQUIRED" });
  add(38, [], { cancelled: true });
  for (let number = 39; number <= 44; number += 1) add(number);
  add(45, ["task-04", "task-05"]); add(46, ["task-06"]); add(47, ["task-07", "task-08"]); add(48, ["task-45", "task-46"]); add(49, ["task-47"]); add(50, ["task-48", "task-49"]);
  return specs;
}
