// Multi-Objective Work Scorer
class WorkScorer {
  static scoreCandidate(candidate, activeGoal) {
    // 1. Goal relevance (0 - 30)
    const goalRel = (candidate.goal_id === activeGoal.goal_id) ? 30 : 10;
    
    // 2. Information gain & uncertainty reduction (0 - 25)
    const infoGain = Math.min(25, (candidate.expected_information_gain || 10) * 2.5);

    // 3. Dependency unlock (0 - 20)
    const depUnlock = (candidate.unlocks_dependents_count || 0) * 5;

    // 4. Priority base score (P0: 30, P1: 20, P2: 10)
    const prioScore = candidate.priority === 'P0' ? 30 : (candidate.priority === 'P1' ? 20 : 10);

    // 5. Machine suitability (PC2 Windows suitability) (0 - 15)
    let machineScore = 15;
    if (candidate.requires_mac) machineScore = -999; // Not runnable on PC2 Windows
    if (candidate.requires_human_gate) machineScore = -999; // Parked

    // 6. Aging boost (1 point per 10 seconds waiting)
    const waitSec = candidate.created_at ? (Date.now() - new Date(candidate.created_at).getTime()) / 1000 : 0;
    const ageBoost = Math.floor(waitSec / 10);

    const totalScore = goalRel + infoGain + depUnlock + prioScore + machineScore + ageBoost;
    return {
      total_score: totalScore,
      breakdown: { goalRel, infoGain, depUnlock, prioScore, machineScore, ageBoost }
    };
  }
}

module.exports = { WorkScorer };
