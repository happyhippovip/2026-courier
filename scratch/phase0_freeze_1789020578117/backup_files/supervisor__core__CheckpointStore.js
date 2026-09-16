// Checkpoint Store: Manages atomic durable JSON & MD checkpoints
const fs = require('fs');
const path = require('path');

class CheckpointStore {
  constructor(missionRoot) {
    this.missionRoot = missionRoot;
    this.jsonPath = path.join(missionRoot, 'CURRENT_CHECKPOINT.json');
    this.mdPath = path.join(missionRoot, 'CURRENT_CHECKPOINT.md');
  }

  saveCheckpoint(checkpointData) {
    const enriched = {
      ...checkpointData,
      saved_at_utc: new Date().toISOString()
    };
    
    // Atomic JSON write
    const tmpJson = this.jsonPath + '.tmp';
    fs.writeFileSync(tmpJson, JSON.stringify(enriched, null, 2), 'utf8');
    fs.renameSync(tmpJson, this.jsonPath);

    // Markdown summary write
    let md = `# CURRENT CHECKPOINT — ${enriched.mission_id}\n\n`;
    md += `- **Status**: \`${enriched.status}\`\n`;
    md += `- **Saved At**: ${enriched.saved_at_utc}\n`;
    md += `- **Active Work Units**: ${enriched.open_work_units || 0}\n`;
    md += `- **Completed Work Units**: ${enriched.completed_work_units || 0}\n`;
    md += `- **Active Writer Leases**: ${enriched.active_leases_count || 0}\n`;
    md += `- **Fenced Tasks**: ${enriched.fenced_tasks_count || 0}\n`;
    md += `- **Real Elapsed Seconds**: ${enriched.real_elapsed_seconds || 0}s\n`;
    md += `- **Last Action**: ${enriched.last_action || 'NONE'}\n`;
    fs.writeFileSync(this.mdPath, md, 'utf8');

    return enriched;
  }

  loadCheckpoint() {
    if (!fs.existsSync(this.jsonPath)) return null;
    return JSON.parse(fs.readFileSync(this.jsonPath, 'utf8'));
  }
}

module.exports = { CheckpointStore };
