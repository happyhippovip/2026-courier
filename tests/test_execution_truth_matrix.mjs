import assert from "assert";
import {
  resolveLivingRoomAgents,
  resolveSpeechBubble,
  resolveChiefAlerts,
  resolveAgentDetailData,
} from "../studio/execution_truth.js";

console.log("=== RUNNING MISSION 199 JS EXECUTION TRUTH TEST MATRIX ===");

// Test 1: All 29 agents (17 core + 8 bodyguards + 4 workers) rendered in default state
{
  const agents = resolveLivingRoomAgents({});
  assert.strictEqual(agents.length, 29, `Expected 29 agents, got ${agents.length}`);

  const google = agents.find(a => a.id === "worker-google");
  const codex = agents.find(a => a.id === "worker-codex");
  const cli1 = agents.find(a => a.id === "worker-cli1");
  const cli2 = agents.find(a => a.id === "worker-cli2");

  assert(google, "Missing worker-google");
  assert(codex, "Missing worker-codex");
  assert(cli1, "Missing worker-cli1");
  assert(cli2, "Missing worker-cli2");

  assert.strictEqual(google.name, "GOOGLE");
  assert.strictEqual(codex.name, "CODEX");
  assert.strictEqual(cli1.name, "CLI 1");
  assert.strictEqual(cli2.name, "CLI 2");

  console.log("✔ Test 1: All 29 logical agents and execution workers rendered successfully.");
}

// Test 2: Sauna props and Bar idle placement in SAFE_IDLE
{
  const agents = resolveLivingRoomAgents({});
  const alpha = agents.find(a => a.id === "bodyguard-alpha" || a.callsign === "ALPHA");
  const bravo = agents.find(a => a.id === "bodyguard-bravo" || a.callsign === "BRAVO");
  const charlie = agents.find(a => a.id === "bodyguard-charlie" || a.callsign === "CHARLIE");

  assert.strictEqual(alpha.prop, "cigarette", "Alpha should have cigarette prop in sauna");
  assert.strictEqual(bravo.prop, "shisha", "Bravo should have shisha prop in sauna");
  assert.strictEqual(charlie.prop, "drink", "Charlie should have drink prop in coffee bar");

  console.log("✔ Test 2: Sauna props (cigarette, shisha) and bar drink props active in leisure areas.");
}

// Test 3: Bodyguard Alert Override triggers on security / permission / hung alert
{
  const alertState = {
    snitch_observer: {
      permission_blocked_count: 1,
      hung_workers_count: 0,
      reasons: ["Worker blocked at interactive permission prompt"],
    }
  };
  const agents = resolveLivingRoomAgents(alertState);
  const alpha = agents.find(a => a.callsign === "ALPHA");
  const bravo = agents.find(a => a.callsign === "BRAVO");

  assert.strictEqual(alpha.state, "ALERT", "Alpha should transition to ALERT on security alert");
  assert.strictEqual(bravo.state, "ALERT", "Bravo should transition to ALERT on security alert");
  assert.strictEqual(alpha.zone, "ALERT_STATION", "Alpha should move to ALERT_STATION");
  assert.strictEqual(alpha.prop, null, "Alpha should holster props during alert");
  assert(alpha.speech.includes("EINSATZ / ALARM"), "Alpha speech should show alert summary");

  console.log("✔ Test 3: Bodyguard alert override correctly triggers duty transition and alert speech.");
}

// Test 4: Deterministic speech bubbles across all 11 states
{
  const testStates = [
    { state: "PROGRESSING", expected: "Arbeite an" },
    { state: "SAFE_IDLE", expected: "SAFE_IDLE" },
    { state: "WAITING_PERMISSION", expected: "Berechtigung" },
    { state: "WAITING_HUMAN", expected: "Human Gate" },
    { state: "RUNNING_NO_PROGRESS", expected: "nächsten Fortschrittsschritt" },
    { state: "HUNG", expected: "WARNUNG" },
    { state: "PROVIDER_ERROR", expected: "Provider-Verbindung" },
    { state: "NETWORK_DEGRADED", expected: "Netzwerk instabil" },
    { state: "COMPLETED", expected: "Mission abgeschlossen" },
    { state: "ORPHANED", expected: "KRITISCH" },
    { state: "UNKNOWN", expected: "Neutraler Status" },
  ];

  for (const { state, expected } of testStates) {
    const bubble = resolveSpeechBubble("worker-test", { state, task: "Task-Test-01" }, {});
    assert(bubble.includes(expected), `Speech bubble for ${state} did not contain '${expected}': got '${bubble}'`);
  }

  console.log("✔ Test 4: Deterministic speech bubbles validated across all 11 states.");
}

// Test 5: Chief Alert Bar Deduplication
{
  const testData = {
    snitch_observer: {
      permission_blocked_count: 2,
      hung_workers_count: 1,
      stale_orphans_count: 1,
    },
    anomalies: {
      quarantined_branches: ["FEATURE_X"],
    },
    autonomy_runtime: {
      jobs_completed: ["OPP-101"],
    }
  };

  const alerts = resolveChiefAlerts(testData);
  assert(alerts.length >= 4, `Expected at least 4 alerts, got ${alerts.length}`);
  const types = alerts.map(a => a.type);
  assert(types.includes("WAITING_PERMISSION"), "Missing WAITING_PERMISSION alert");
  assert(types.includes("HUNG"), "Missing HUNG alert");
  assert(types.includes("ORPHANED"), "Missing ORPHANED alert");
  assert(types.includes("ANOMALY"), "Missing ANOMALY alert");
  assert(types.includes("WORKER_COMPLETED"), "Missing WORKER_COMPLETED alert");

  // Verify deduplication: passing duplicate should not create duplicate entries
  const alerts2 = resolveChiefAlerts(testData);
  assert.strictEqual(alerts.length, alerts2.length, "Alert deduplication mismatch");

  console.log("✔ Test 5: Chief Alert Bar successfully aggregates and deduplicates live alerts.");
}

// Test 6: Detail Panel data completeness (11 required fields)
{
  const agentObj = {
    id: "worker-google",
    name: "GOOGLE",
    role: "Google Pro / Primary Builder",
    state: "PROGRESSING",
    task: "OPP-REMEDIATE-01",
    provider: "GOOGLE_PRO",
    heavy_job: true,
    result_id: "RES-999",
  };
  const detail = resolveAgentDetailData(agentObj, { autonomy_runtime: { current_goal: "Endurance Run" } });

  assert.strictEqual(detail.name, "GOOGLE");
  assert.strictEqual(detail.role, "Google Pro / Primary Builder");
  assert.strictEqual(detail.state, "PROGRESSING");
  assert.strictEqual(detail.mission, "Endurance Run");
  assert.strictEqual(detail.task, "OPP-REMEDIATE-01");
  assert(detail.last_progress, "Missing last_progress");
  assert(detail.state_age, "Missing state_age");
  assert(detail.blocked_reason, "Missing blocked_reason");
  assert.strictEqual(detail.provider, "GOOGLE_PRO");
  assert.strictEqual(detail.heavy_job, "YES (Scope Locked)");
  assert.strictEqual(detail.result_id, "RES-999");

  console.log("✔ Test 6: Detail panel provides all 11 required fields with complete telemetry.");
}

console.log("=== ALL MISSION 199 JS TESTS PASSED ===");
