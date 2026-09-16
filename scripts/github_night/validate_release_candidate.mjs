import { execFileSync } from "node:child_process";

const ref = "origin/release-candidate";

function gitShow(path) {
  return execFileSync("git", ["show", `${ref}:${path}`], { encoding: "utf8" });
}

function trackedPaths() {
  return new Set(
    execFileSync("git", ["ls-tree", "-r", "--name-only", ref], {
      encoding: "utf8",
    }).trim().split("\n"),
  );
}

const failures = [];
const workflow = gitShow(".github/workflows/courier_motor.yml");
const app = gitShow("server/app.py");
const paths = trackedPaths();

if (workflow.includes('COURIER_API_KEY: "cron_motor_key"')) {
  failures.push("hard-coded insecure COURIER_API_KEY in Courier Motor");
}
if (workflow.includes('COURIER_VERIFIER_API_KEY: "cron_motor_key"')) {
  failures.push("hard-coded shared COURIER_VERIFIER_API_KEY in Courier Motor");
}
if (!workflow.includes("\nconcurrency:")) {
  failures.push("Courier Motor has no workflow concurrency guard");
}
if (app.includes("STATE_LOCK = threading.RLock()") && !app.includes("fcntl.flock")) {
  failures.push("central state mutation lock is process-local only");
}
if (
  app.includes('if "task_id" not in step:') &&
  !app.includes("duplicate task_id") &&
  !app.includes("Duplicate task_id")
) {
  failures.push("submitted workflow plans have no duplicate task_id rejection");
}
if (
  app.includes('set_task_status(task, "DISPATCHED")') &&
  app.includes('if candidate["status"] == "QUEUED":')
) {
  failures.push("provider resume leaves a released task DISPATCHED and unclaimable");
}

const runtimeDebris = [
  "central_state.json",
  "reconciliation.json",
  "logs/courier_daemon.log",
  "scripts/mac_worker/logs/worker.log",
  "scripts/mac_worker/state/run_canary-mac-native.sh",
  "scripts/windows_worker/courier_canary_test-win-001.txt",
];
for (const path of runtimeDebris) {
  if (paths.has(path)) failures.push(`tracked runtime or proof debris: ${path}`);
}

for (const failure of failures) console.log(`FAIL: ${failure}`);
console.log(`REF=${ref}`);
process.exitCode = failures.length === 0 ? 0 : 1;
