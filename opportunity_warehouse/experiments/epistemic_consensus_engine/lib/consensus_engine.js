/**
 * Context Window Multi-Agent Epistemic Consensus & Dispute Resolution Engine
 * Ingests claims from multiple agents, detects conflicting assertions,
 * resolves disputes via role authority weighting, and compacts history into an authoritative consensus statement.
 */

class EpistemicConsensusEngine {
  constructor() {
    this.claims = new Map(); // claimId -> { agentId, claimId, topic, assertion, confidence, authorityWeight }
    this.authorityWeights = {
      'security_gate': 10.0,
      'supervisor': 8.0,
      'architect': 6.0,
      'engineer': 4.0,
      'researcher': 2.0
    };
  }

  submitClaim(agentId, role, claimId, topic, assertion, confidence = 0.9) {
    const authority = this.authorityWeights[role] || 3.0;
    const claim = {
      agentId,
      role,
      claimId,
      topic,
      assertion,
      confidence,
      authorityWeight: authority,
      effectiveScore: Number((authority * confidence).toFixed(2))
    };
    this.claims.set(claimId, claim);
    return claim;
  }

  detectDisputes() {
    const topics = new Map();
    for (const claim of this.claims.values()) {
      if (!topics.has(claim.topic)) {
        topics.set(claim.topic, []);
      }
      topics.get(claim.topic).push(claim);
    }

    const disputes = [];
    for (const [topic, claimList] of topics.entries()) {
      if (claimList.length > 1) {
        // Multiple claims on same topic represent a dispute candidate
        disputes.push({
          topic,
          claimCount: claimList.length,
          claims: claimList
        });
      }
    }

    return disputes;
  }

  resolveConsensus() {
    const disputes = this.detectDisputes();
    const consensusResults = [];
    let tokensSaved = 0;

    for (const dispute of disputes) {
      // Sort claims descending by effectiveScore
      dispute.claims.sort((a, b) => b.effectiveScore - a.effectiveScore);
      const winner = dispute.claims[0];
      const rejected = dispute.claims.slice(1);

      // Raw unpruned tokens across all dispute claims
      const totalRawTokens = dispute.claims.reduce((acc, c) => acc + Math.round((c.assertion || '').length / 4), 0);
      const consensusStatement = '[CONSENSUS_RESOLVED: ' + dispute.topic + ']: ' + winner.assertion + ' (Affirmed by ' + winner.role + ')';
      const consensusTokens = Math.max(1, Math.round(consensusStatement.length / 4));

      const saved = Math.max(0, totalRawTokens - consensusTokens);
      tokensSaved += saved;

      consensusResults.push({
        topic: dispute.topic,
        winningAgent: winner.agentId,
        winningRole: winner.role,
        consensusAssertion: consensusStatement,
        prunedCounterClaimsCount: rejected.length,
        tokensSaved: saved
      });
    }

    return {
      totalDisputesResolved: disputes.length,
      totalTokensSaved: tokensSaved,
      consensusLedger: consensusResults
    };
  }
}

module.exports = { EpistemicConsensusEngine };
