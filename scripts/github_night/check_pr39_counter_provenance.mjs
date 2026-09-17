import { execFileSync } from "node:child_process";

const ref = process.argv[2] ?? "origin/release-candidate-integration";

function show(path) {
  return execFileSync("git", ["show", `${ref}:${path}`], { encoding: "utf8" });
}

const proof = show("proof_canonical_central_multiworker.py");
const failures = [];

if (proof.includes('API_KEY = "')) {
  failures.push("proof embeds a worker credential instead of using OS-managed runtime authority");
}
if (proof.includes('VERIFIER_KEY = "')) {
  failures.push("proof embeds a verifier credential instead of using OS-managed runtime authority");
}
if (proof.includes('s["goals"] = {}') || proof.includes('s["tasks"] = {}')) {
  failures.push("proof directly mutates canonical central state before observation");
}
if (proof.includes("subprocess.Popen(") && proof.includes("worker_cli_proc")) {
  failures.push("second worker is manually launched by the proof");
}
if (proof.includes("verifier_proc = subprocess.Popen(")) {
  failures.push("verifier is manually launched by the proof");
}
if (proof.includes("p.kill()") && !proof.includes("p.wait(")) {
  failures.push("proof kills child processes without waiting for exact cleanup");
}
for (const metric of [
  "USER_CONTINUE_MESSAGES",
  "MANUAL_PROCESS_RESTARTS",
  "MANUAL_ACCOUNT_CONTEXT_RECONSTRUCTION",
  "DUPLICATE_EXTERNAL_EFFECTS",
  "TEMP_TASK_PROCESSES_AFTER_DONE",
  "CLEAN_IDLE",
]) {
  if (!proof.includes(metric)) failures.push(`proof does not derive ${metric}`);
}

for (const failure of failures) console.log(`FAIL: ${failure}`);
console.log(`EXACT_SHA=${execFileSync("git", ["rev-parse", ref], { encoding: "utf8" }).trim()}`);
console.log("NEXT_BLOCKER=acceptance counters are not derived from independent OS-owned runtime evidence");
console.log(`COMMAND=node scripts/github_night/check_pr39_counter_provenance.mjs ${ref}`);
console.log("EXPECTED=proof uses existing OS-owned processes and derives every Issue #37 counter");
console.log(`ACTUAL=${failures.length} invariant failures`);
console.log("FILES=proof_canonical_central_multiworker.py; scripts/windows_worker/install_service.ps1; scripts/install_verifier_service.ps1");
console.log("OWNER=Windows/Central");
console.log("MINIMAL_REPAIR=Central should emit an immutable runtime evidence record from existing OS-owned service and worker identities; the proof should only observe it.");
process.exitCode = failures.length === 0 ? 0 : 1;
