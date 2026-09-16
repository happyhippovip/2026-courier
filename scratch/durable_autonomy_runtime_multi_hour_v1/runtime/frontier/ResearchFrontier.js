// Research Frontier & Dynamic Work Scheduler
const { WorkScorer } = require('./WorkScorer');

class ResearchFrontier {
  constructor(lowWaterMark = 5) {
    this.candidates = [];
    this.inFlight = new Map();
    this.completed = [];
    this.lowWaterMark = lowWaterMark;
  }

  addCandidate(candidate) {
    if (!candidate.candidate_id) candidate.candidate_id = `CAND-${Date.now()}-${Math.floor(Math.random()*10000)}`;
    if (!candidate.created_at) candidate.created_at = new Date().toISOString();
    candidate.status = 'READY';
    this.candidates.push(candidate);
    return candidate;
  }

  getReadyCount() {
    return this.candidates.filter(c => c.status === 'READY').length;
  }

  needsReplenishment() {
    return this.getReadyCount() < this.lowWaterMark;
  }

  selectNextBest(activeGoal, lockManager) {
    const ready = this.candidates.filter(c => c.status === 'READY');
    if (ready.length === 0) return null;

    // Score all candidates
    ready.forEach(c => {
      const s = WorkScorer.scoreCandidate(c, activeGoal);
      c.effective_score = s.total_score;
      c.score_breakdown = s.breakdown;
    });

    // Sort descending
    ready.sort((a, b) => b.effective_score - a.effective_score);

    // Pick highest that is not resource-locked
    for (const cand of ready) {
      if (cand.working_dir) {
        const lockCheck = lockManager.canAcquire(cand.working_dir, cand.candidate_id);
        if (!lockCheck.available) continue; // Locked, skip to next
      }
      return cand;
    }
    return null;
  }

  markInFlight(candidateId) {
    const idx = this.candidates.findIndex(c => c.candidate_id === candidateId);
    if (idx !== -1) {
      const cand = this.candidates.splice(idx, 1)[0];
      cand.status = 'IN_FLIGHT';
      cand.dispatched_at = new Date().toISOString();
      this.inFlight.set(candidateId, cand);
      return cand;
    }
    return null;
  }

  markCompleted(candidateId, evidenceRecord) {
    const cand = this.inFlight.get(candidateId);
    if (cand) {
      this.inFlight.delete(candidateId);
      cand.status = 'COMPLETED';
      cand.completed_at = new Date().toISOString();
      cand.evidence = evidenceRecord;
      this.completed.push(cand);
      return cand;
    }
    return null;
  }
}

module.exports = { ResearchFrontier };
