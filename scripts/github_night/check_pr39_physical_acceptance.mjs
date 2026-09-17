import { execFileSync } from "node:child_process";

const ref = process.argv[2] ?? "origin/release-candidate-integration";

function show(path) {
  return execFileSync("git", ["show", `${ref}:${path}`], { encoding: "utf8" });
}

const acceptance = show("run_acceptance.py");
const releaseNotes = show("docs/RELEASE_CANDIDATE.md");
const failures = [];

if (!releaseNotes.includes("MOTOR_OS_START_PATH=OBSERVED_IN_CODE")) {
  failures.push("release notes leave Motor ownership unobserved");
}
if ((acceptance.match(/subprocess\.Popen/g) ?? []).length < 3) {
  failures.push("acceptance script does not start the expected local child processes");
}
if (!acceptance.includes("w2_proc")) {
  failures.push("acceptance script starts only one worker, not the required two");
}
if (!acceptance.includes("server_proc.terminate()")) {
  failures.push("acceptance script lacks explicit child-process termination");
}
if (!acceptance.includes("verifier_proc.terminate()")) {
  failures.push("acceptance script lacks explicit verifier-process termination");
}
if (!acceptance.includes("w1_proc.terminate()")) {
  failures.push("acceptance script lacks explicit worker-process termination");
}
for (const metric of [
  "USER_CONTINUE_MESSAGES",
  "MANUAL_PROCESS_RESTARTS",
  "DUPLICATE_EXTERNAL_EFFECTS",
  "TEMP_TASK_PROCESSES_AFTER_DONE",
  "CLEAN_IDLE",
]) {
  if (!acceptance.includes(metric)) {
    failures.push(`acceptance script does not measure ${metric}`);
  }
}
if (!acceptance.includes("agent exits") && !acceptance.includes("terminal exit")) {
  failures.push("acceptance script does not test interactive agent or terminal exit");
}

for (const failure of failures) console.log(`FAIL: ${failure}`);
console.log(`REF=${ref}`);
process.exitCode = failures.length === 0 ? 0 : 1;
