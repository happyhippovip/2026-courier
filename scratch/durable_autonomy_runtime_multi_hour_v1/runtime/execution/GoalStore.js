// Goal Store with Acceptance Criteria Totality & Evidence Verification
class GoalStore {
  constructor() {
    this.goals = new Map();
    this.evidence = []; // Array of evidence records
  }

  createGoal({ goal_id, goal_version = 1, owner = 'CHIEF', title, acceptance_criteria = [], evidence_requirements = [], dependencies = [], human_gates = [], risk = 'LOW' }) {
    const goal = {
      goal_id,
      goal_version,
      owner,
      title,
      acceptance_criteria,
      evidence_requirements,
      dependencies,
      human_gates,
      risk,
      status: 'ACTIVE',
      created_at: new Date().toISOString()
    };
    this.goals.set(goal_id, goal);
    return goal;
  }

  recordEvidence({ criteria_key, artifact_path, sha256, verified_by = 'EvidenceVerifier' }) {
    const ev = {
      criteria_key,
      artifact_path,
      sha256,
      verified_by,
      recorded_at: new Date().toISOString()
    };
    this.evidence.push(ev);
    return ev;
  }

  evaluateGoalSatisfaction(goal_id) {
    const goal = this.goals.get(goal_id);
    if (!goal) return { satisfied: false, reason: 'GOAL_NOT_FOUND' };
    if (!goal.acceptance_criteria || goal.acceptance_criteria.length === 0) {
      return { satisfied: false, reason: 'NO_ACCEPTANCE_CRITERIA_DEFINED' };
    }

    const verifiedKeys = new Set(this.evidence.map(e => e.criteria_key));
    const missing = goal.acceptance_criteria.filter(req => !verifiedKeys.has(req));

    if (missing.length > 0) {
      return { satisfied: false, missing_criteria: missing, reason: 'PARTIAL_EVIDENCE_PRODUCED' };
    }

    goal.status = 'SATISFIED';
    goal.satisfied_at = new Date().toISOString();
    return { satisfied: true, verified_criteria_count: goal.acceptance_criteria.length };
  }

  getGoal(goal_id) {
    return this.goals.get(goal_id);
  }
}

module.exports = { GoalStore };
