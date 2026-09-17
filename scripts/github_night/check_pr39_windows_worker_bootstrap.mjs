import { execFileSync } from "node:child_process";

const ref = process.argv[2] ?? "origin/release-candidate-integration";

function show(path) {
  return execFileSync("git", ["show", `${ref}:${path}`], { encoding: "utf8" });
}

const config = JSON.parse(show("scripts/windows_worker/config.json"));
const daemon = show("scripts/windows_worker/daemon.py");
const start = show("scripts/windows_worker/start.bat");
const failures = [];

if (config.WORKER_ID === "WINDOWS-TEST-WORKER") {
  failures.push("committed worker identity is WINDOWS-TEST-WORKER");
}
if (
  daemon.includes("f\"courier_worker_{worker_id}.lock\"") &&
  daemon.includes("Another instance is already running. Exiting to prevent duplicates.")
) {
  failures.push("that identity exits on an existing instance lock");
}
if (daemon.includes("import psutil") && !start.includes("--with psutil")) {
  failures.push("committed start.bat omits daemon's psutil dependency");
}

for (const failure of failures) console.log(`FAIL: ${failure}`);
console.log(`EXACT_SHA=${execFileSync("git", ["rev-parse", ref], { encoding: "utf8" }).trim()}`);
console.log("NEXT_BLOCKER=worker bootstrap cannot reproducibly start a uniquely identified daemon");
console.log(`COMMAND=node scripts/github_night/check_pr39_windows_worker_bootstrap.mjs ${ref}`);
console.log("EXPECTED=installer supplies all daemon dependencies and a non-test persistent worker identity");
console.log(`ACTUAL=${failures.length} invariant failures`);
console.log("FILES=scripts/windows_worker/config.json; scripts/windows_worker/daemon.py; scripts/windows_worker/start.bat");
console.log("OWNER=Windows/Central");
console.log("MINIMAL_REPAIR=Windows/Central must persist a unique non-test worker ID before WMI launch and make the committed start path install psutil; retain the exact single-instance lock.");
process.exitCode = failures.length === 0 ? 0 : 1;
