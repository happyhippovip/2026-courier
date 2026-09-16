// MutationGapGenerator.js — Generates mutation tests against critical decision boundaries
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

class MutationGapGenerator {
  generate(runtime) {
    const candidates = [];

    // Mutation 1: Border Guard Stamp Bypass Rejection
    candidates.push({
      title: 'Mutation Gap: Border Guard Unstamped Task Rejection',
      category: 'GOVERNANCE',
      priority: 'P1',
      expected_information_gain: 9,
      lane: 'G. BORDER GUARD',
      discovery_method: 'MUTATION_SURVIVOR_ANALYSIS',
      task_generator_fn: (workingDir, rt) => {
        const { BorderGuard } = require(path.join(rt.missionRoot, 'runtime', 'governance', 'BorderGuard.js'));
        const { TaskPassport } = require(path.join(rt.missionRoot, 'runtime', 'governance', 'TaskPassport.js'));
        
        // Unstamped task inspection
        const unstampedTask = { task_id: 'TASK-MUTANT-UNSTAMPED', state: 'PROPOSED', scope_paths: [workingDir] };
        const outcomeUnstamped = BorderGuard.inspect(unstampedTask, null, rt.lockManager);
        
        // Invalid capability task
        const illegalPassport = TaskPassport.createPassport({
          task_id: 'TASK-MUTANT-ILLEGAL-CAP',
          task_version: 1,
          goal_id: 'GOAL-TEST',
          scope_paths: [workingDir],
          max_capability: 'ROOT_SHELL'
        });
        const illegalTask = { task_id: 'TASK-MUTANT-ILLEGAL-CAP', state: 'STAMPED', required_capability: 'ROOT_SHELL', scope_paths: [workingDir] };
        const outcomeIllegal = BorderGuard.inspect(illegalTask, illegalPassport, rt.lockManager);

        const findings = {
          test: 'MUTATION_BORDER_GUARD_BYPASS',
          unstamped_rejected: outcomeUnstamped.outcome !== 'GREEN_CARD',
          illegal_capability_rejected: outcomeIllegal.outcome !== 'GREEN_CARD',
          status: (outcomeUnstamped.outcome !== 'GREEN_CARD' && outcomeIllegal.outcome !== 'GREEN_CARD') ? 'PASSED' : 'FAILED'
        };

        const artifactName = 'border_guard_mutant_audit.json';
        const content = JSON.stringify(findings, null, 2);
        fs.writeFileSync(path.join(workingDir, artifactName), content, 'utf8');
        const sha = crypto.createHash('sha256').update(content).digest('hex');

        return {
          exit_code: 0,
          criteria_key: 'CRIT_MUTATION_BORDER_GUARD_KILLED',
          artifacts: [artifactName],
          checksum_map: { [artifactName]: sha }
        };
      }
    });

    // Mutation 2: Worker Report Global Saturation Forgery Rejection
    candidates.push({
      title: 'Mutation Gap: Worker Global Saturation Forgery Rejection',
      category: 'GOVERNANCE',
      priority: 'P1',
      expected_information_gain: 9,
      lane: 'Z. COMPLETION GOVERNOR',
      discovery_method: 'ASSUMPTION_INVERSION',
      task_generator_fn: (workingDir, rt) => {
        const { CompletionGovernor } = require(path.join(rt.missionRoot, 'runtime', 'governance', 'CompletionGovernor.js'));
        const gov = new CompletionGovernor();
        
        // Worker attempting to close mission
        const rogueReport = { status: 'MISSION_SATURATED', worker_id: 'ROGUE_WORKER_01' };
        const evalResult = gov.evaluateWorkerReport(rogueReport);

        const findings = {
          test: 'MUTATION_WORKER_SATURATION_FORGERY',
          admitted: evalResult.admitted,
          violation_flagged: !evalResult.admitted,
          reason: evalResult.reason,
          status: (!evalResult.admitted) ? 'PASSED' : 'FAILED'
        };

        const artifactName = 'completion_governor_mutant_audit.json';
        const content = JSON.stringify(findings, null, 2);
        fs.writeFileSync(path.join(workingDir, artifactName), content, 'utf8');
        const sha = crypto.createHash('sha256').update(content).digest('hex');

        return {
          exit_code: 0,
          criteria_key: 'CRIT_MUTATION_WORKER_SATURATION_KILLED',
          artifacts: [artifactName],
          checksum_map: { [artifactName]: sha }
        };
      }
    });

    // Mutation 3: Result Customs Envelope Checksum Tamper Rejection
    candidates.push({
      title: 'Mutation Gap: Result Customs Envelope Checksum Tamper Rejection',
      category: 'GOVERNANCE',
      priority: 'P1',
      expected_information_gain: 9,
      lane: 'H. RESULT CUSTOMS',
      discovery_method: 'STRONGEST_CLAIM_FALSIFICATION',
      task_generator_fn: (workingDir, rt) => {
        const { ResultCustoms, EvidenceVerifier } = require(path.join(rt.missionRoot, 'runtime', 'governance', 'ResultCustoms.js'));
        const { TaskPassport } = require(path.join(rt.missionRoot, 'runtime', 'governance', 'TaskPassport.js'));
        
        const testFile = 'tampered_data.txt';
        const fullPath = path.join(workingDir, testFile);
        fs.writeFileSync(fullPath, 'ORIGINAL_AUTHENTIC_PAYLOAD', 'utf8');
        const authenticSha = crypto.createHash('sha256').update('ORIGINAL_AUTHENTIC_PAYLOAD').digest('hex');

        const passport = TaskPassport.createPassport({
          task_id: 'TASK-MUTANT-CUSTOMS',
          task_version: 1,
          goal_id: 'GOAL-TEST',
          scope_paths: [workingDir],
          max_capability: 'WORKSPACE_WRITE'
        });

        // Tamper with checksum map
        const forgedSha = 'deadbeef0123456789abcdef0123456789abcdef0123456789abcdef01234567';
        const customsRes = ResultCustoms.evaluateResultEnvelope({
          task_id: 'TASK-MUTANT-CUSTOMS',
          passport,
          exit_code: 0,
          artifacts: [testFile],
          checksum_map: { [testFile]: authenticSha }
        });

        const verifierTampered = EvidenceVerifier.verifyArtifact(fullPath, forgedSha);

        const findings = {
          test: 'MUTATION_CUSTOMS_CHECKSUM_TAMPER',
          customs_envelope_accepted: customsRes.accepted,
          tampered_checksum_rejected: !verifierTampered.verified,
          status: (customsRes.accepted && !verifierTampered.verified) ? 'PASSED' : 'FAILED'
        };

        const artifactName = 'customs_mutant_audit.json';
        const content = JSON.stringify(findings, null, 2);
        fs.writeFileSync(path.join(workingDir, artifactName), content, 'utf8');
        const sha = crypto.createHash('sha256').update(content).digest('hex');

        return {
          exit_code: 0,
          criteria_key: 'CRIT_MUTATION_CUSTOMS_TAMPER_KILLED',
          artifacts: [artifactName],
          checksum_map: { [artifactName]: sha }
        };
      }
    });

    return candidates;
  }
}

module.exports = { MutationGapGenerator };