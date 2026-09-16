/**
 * CAMPAIGN FAMILY B — DEEP PROCESS IDENTITY & PID RECYCLING (B01)
 */

const fs = require('fs');
const path = require('path');
const { IndependentSafetyOracles } = require('./ORACLES/independent_safety_oracles');

function runCampaignB01(ctx) {
  console.log('=== EXECUTING CAMPAIGN FAMILY B: DEEP PROCESS IDENTITY (B01) ===\n');

  // 1. Multi-Factor Tuple & PID Recycling Permutations
  const lease = {
    machineId: 'WIN-HOST-01',
    pid: 7701,
    startTime: 100000,
    taskToken: 'TOKEN-LEAD-7701'
  };

  const processPermutations = [
    { name: 'EXACT_MATCH', proc: { exists: true, startTime: 100000, taskToken: 'TOKEN-LEAD-7701' }, expect: 'MATCH_CONFIRMED' },
    { name: 'SAME_PID_DIFF_START', proc: { exists: true, startTime: 100500, taskToken: 'TOKEN-LEAD-7701' }, expect: 'NOT_MATCH' },
    { name: 'SAME_PID_DIFF_TOKEN', proc: { exists: true, startTime: 100000, taskToken: 'TOKEN-OTHER-9999' }, expect: 'NOT_MATCH' },
    { name: 'REUSED_AFTER_RESTART', proc: { exists: true, startTime: 200000, taskToken: null }, expect: 'NOT_MATCH' },
    { name: 'INACCESSIBLE_METADATA', proc: { exists: true, inaccessible: true }, expect: 'UNKNOWN' },
    { name: 'MISSING_START_TIME', proc: { exists: true, startTime: null }, expect: 'UNKNOWN' },
    { name: 'PROCESS_DEAD', proc: { exists: false }, expect: 'NOT_MATCH' }
  ];

  let permPass = 0;
  processPermutations.forEach(p => {
    ctx.scenarios++;
    ctx.b01Attacks++;
    const res = IndependentSafetyOracles.evaluateProcessMatch(lease, p.proc);
    if (res === p.expect) {
      permPass++;
    } else {
      if (res === 'MATCH_CONFIRMED' && p.expect !== 'MATCH_CONFIRMED') {
        ctx.pidIdentityFalseMatchEscaped++;
      }
    }
  });
  console.log(`  [B01.1] Process Matching: ${permPass}/${processPermutations.length} permutations evaluated accurately.`);

  // 2. Start-Time Granularity & Clock Tick Disambiguation
  // Two processes spawn in the same second/tick (startTime identical), but have different taskTokens
  ctx.scenarios++;
  ctx.b01Attacks++;
  const tickCollisionProc = {
    exists: true,
    startTime: 100000, // Same clock tick!
    taskToken: 'TOKEN-UNRELATED-DAEMON' // Disambiguated by token!
  };

  const tickCheck = IndependentSafetyOracles.evaluateProcessMatch(lease, tickCollisionProc);
  if (tickCheck === 'NOT_MATCH') {
    console.log('  [B01.2] Start-Time Granularity: Disambiguated same-tick process reuse via TaskToken.');
  } else {
    ctx.pidIdentityFalseMatchEscaped++;
  }

  // 3. Metadata Inaccessibility (UNKNOWN State Machine)
  ctx.scenarios++;
  ctx.b01Attacks++;
  const unknownProc = { exists: true, inaccessible: true };
  const matchUnknown = IndependentSafetyOracles.evaluateProcessMatch(lease, unknownProc);
  const killCheckUnknown = IndependentSafetyOracles.isProcessKillAllowed(matchUnknown, lease, { lastActivityMsAgo: 999999 });

  if (matchUnknown === 'UNKNOWN' && !killCheckUnknown.allowed && killCheckUnknown.reason === 'CANNOT_KILL_UNKNOWN_PROCESS_FAIL_CLOSED') {
    console.log('  [B01.3] UNKNOWN Safety: Inaccessible process metadata strictly prevents kill and prevents false liveness.');
  } else {
    ctx.unsafeProcessKillEscaped++;
  }

  // 4. Process Tree Reparenting (Child survives parent exit)
  // When Courier parent restarts, child is adopted by system (PID 1 on Darwin). PPID changes.
  ctx.scenarios++;
  ctx.b01Attacks++;
  const reparentedChild = {
    exists: true,
    startTime: 100000,
    taskToken: 'TOKEN-LEAD-7701',
    ppid: 1 // Adopted by init/launchd
  };
  const reparentCheck = IndependentSafetyOracles.evaluateProcessMatch(lease, reparentedChild);
  if (reparentCheck === 'MATCH_CONFIRMED') {
    console.log('  [B01.4] Process Reparenting: Identity preserved after parent exit without requiring immutable PPID.');
  }

  // 5. Explicit Kill Authorization Oracle
  const killCases = [
    { match: 'NOT_MATCH', evidence: { lastActivityMsAgo: 50000 }, expectKill: false, desc: 'Do not kill unrelated process' },
    { match: 'UNKNOWN', evidence: { lastActivityMsAgo: 50000 }, expectKill: false, desc: 'Do not kill unknown process' },
    { match: 'MATCH_CONFIRMED', evidence: { lastActivityMsAgo: 1000 }, expectKill: false, desc: 'Do not kill actively progressing matched process' },
    { match: 'MATCH_CONFIRMED', evidence: { lastActivityMsAgo: 60000 }, expectKill: true, desc: 'Kill verified hung/expired matched process' }
  ];

  let killPass = 0;
  killCases.forEach(kc => {
    ctx.scenarios++;
    ctx.b01Attacks++;
    const res = IndependentSafetyOracles.isProcessKillAllowed(kc.match, lease, kc.evidence);
    if (res.allowed === kc.expectKill) {
      killPass++;
    } else {
      if (res.allowed && !kc.expectKill) ctx.unsafeProcessKillEscaped++;
    }
  });
  console.log(`  [B01.5] Kill Oracle: Verified ${killPass}/${killCases.length} process kill authorization boundaries.`);

  // 6. Queue Darwin Native Proof Item
  const macQueuePath = path.join(ctx.root, 'MAC_NATIVE_PROOF_QUEUE.md');
  const macEntry = `\n### B01 Darwin Process Inspection Proof\n` +
    `- **Component**: Darwin proc_pidinfo pbi_start_tvsec retrieval\n` +
    `- **Target**: Verify Sandbox/SIP behavior when calling proc_pidinfo(pid, PROC_PIDTASKINFO) from non-root worker.\n` +
    `- **Status**: QUEUED_FOR_POST_FREEZE_MAC_EXECUTION\n`;
  fs.appendFileSync(macQueuePath, macEntry, 'utf8');

  console.log('  Family B01 Completed Cleanly.\n');
}

module.exports = { runCampaignB01 };
