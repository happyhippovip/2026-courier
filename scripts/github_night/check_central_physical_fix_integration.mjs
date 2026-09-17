import { execFileSync, spawnSync } from "node:child_process";

const target = "origin/release-candidate-integration";
const repair = "origin/central-physical-fix";

function git(args) {
  return execFileSync("git", args, { encoding: "utf8" });
}

function isAncestor(commit, ref) {
  return spawnSync("git", ["merge-base", "--is-ancestor", commit, ref]).status === 0;
}

const psutilCommit = "e99bfdfc";
const identityCommit = "7c0be16b";
const repairedStart = git(["show", `${repair}:scripts/windows_worker/start.bat`]);
const targetStart = git(["show", `${target}:scripts/windows_worker/start.bat`]);
const failures = [];

if (!repairedStart.includes("--with keyring --with psutil")) {
  failures.push("psutil repair is absent from central-physical-fix");
}
if (!repairedStart.includes("COURIER_WORKER_ID")) {
  failures.push("explicit worker identity repair is absent from central-physical-fix");
}
if (!isAncestor(psutilCommit, target)) {
  failures.push("psutil repair is not integrated into PR #39");
}
if (!isAncestor(identityCommit, target)) {
  failures.push("explicit worker identity repair is not integrated into PR #39");
}
if (targetStart.includes("--with psutil") || targetStart.includes("COURIER_WORKER_ID")) {
  failures.push("PR #39 unexpectedly contains an unaccounted worker-start change");
}

for (const failure of failures) console.log(`FAIL: ${failure}`);
console.log(`EXACT_SHA=${git(["rev-parse", target]).trim()}`);
console.log("NEXT_BLOCKER=worker bootstrap repairs are not integrated into the authoritative PR #39 head");
console.log("COMMAND=node scripts/github_night/check_central_physical_fix_integration.mjs");
console.log("EXPECTED=both repair commits are ancestors of PR #39 before physical acceptance evidence is accepted");
console.log(`ACTUAL=${failures.length} invariant failures`);
console.log("FILES=scripts/windows_worker/start.bat; PR #39; origin/central-physical-fix");
console.log("OWNER=Windows/Central");
console.log("MINIMAL_REPAIR=Cherry-pick or merge e99bfdfc and 7c0be16b into the authoritative integration branch, then rerun the same read-only process and registration observation.");
process.exitCode = failures.length === 0 ? 0 : 1;
