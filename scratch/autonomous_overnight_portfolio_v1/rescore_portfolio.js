// Portfolio Dynamic Rescoring Engine
// Mission: COURIER_AUTONOMOUS_OVERNIGHT_PORTFOLIO_V1

const fs = require('fs');
const path = require('path');

const root = 'C:/Users/lol/2026-workspace/courier/scratch/autonomous_overnight_portfolio_v1';
const wsPath = path.join(root, 'WORKSTREAM_LEDGER.jsonl');

function rescoreAll(justCompletedWsId = null) {
  const lines = fs.readFileSync(wsPath, 'utf8').trim().split('\n').filter(Boolean);
  const streams = lines.map(l => JSON.parse(l));

  for (const s of streams) {
    if (justCompletedWsId && s.id === justCompletedWsId) {
      s.sat = 10; // Fully saturated
      s.status = 'SATURATED';
    }
    // Priority formula:
    // (info_gain + goal_progress + safety_impact + dep_val + user_val) - (dup + sat + cost)
    s.priority_score = (s.info_gain + s.goal_progress + s.safety_impact + s.dep_val + s.user_val) - (s.dup + s.sat + s.cost);
    s.updated_at = new Date().toISOString();
  }

  // Sort active/queued streams first by score, saturated last
  streams.sort((a, b) => {
    if (a.status === 'SATURATED' && b.status !== 'SATURATED') return 1;
    if (b.status === 'SATURATED' && a.status !== 'SATURATED') return -1;
    return b.priority_score - a.priority_score;
  });

  fs.writeFileSync(wsPath, streams.map(s => JSON.stringify(s)).join('\n') + '\n', 'utf8');

  const nextActive = streams.find(s => s.status !== 'SATURATED');
  console.log(`Rescoring complete. Saturated: ${streams.filter(s => s.status === 'SATURATED').length}/${streams.length}`);
  if (nextActive) {
    console.log(`NEXT TOP WORKSTREAM: [${nextActive.id}] ${nextActive.name} (Score: ${nextActive.priority_score})`);
    return nextActive;
  } else {
    console.log('ALL INITIAL WORKSTREAMS SATURATED. TRIGGERING PORTFOLIO EXPANSION REVIEW.');
    return null;
  }
}

const next = rescoreAll(process.argv[2] || null);
if (next) {
  const missionStatePath = path.join(root, 'MISSION_STATE.json');
  const ms = JSON.parse(fs.readFileSync(missionStatePath, 'utf8'));
  ms.active_workstream = next.id;
  ms.exact_next_safe_action = `Dispatch next top-ranked workstream: ${next.id} (${next.name})`;
  ms.last_updated_at = new Date().toISOString();
  fs.writeFileSync(missionStatePath, JSON.stringify(ms, null, 2), 'utf8');
}
