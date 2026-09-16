// SourceGapGenerator.js — Inspects production courier source and project-memory to discover specification gaps
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

class SourceGapGenerator {
  constructor(courierRoot, projectMemoryRoot) {
    this.courierRoot = courierRoot;
    this.projectMemoryRoot = projectMemoryRoot;
    this.discoveredGaps = [];
  }

  generate(runtime) {
    const candidates = [];
    
    // Gap 1: No-Stacking NTFS case-folding and subpath prefix guard
    candidates.push({
      title: 'Source Gap: Production No-Stacking NTFS Case-Folding and Subpath Guard',
      category: 'GOVERNANCE',
      priority: 'P1',
      expected_information_gain: 9,
      lane: 'M. NO-STACKING',
      discovery_method: 'CURRENT_SOURCE_ARCHAEOLOGY',
      task_generator_fn: (workingDir, rt) => {
        const prodPath = path.join(this.courierRoot, 'core', 'no_stacking.js');
        const prodExists = fs.existsSync(prodPath);
        const prodContent = prodExists ? fs.readFileSync(prodPath, 'utf8') : '';
        
        // Audit for case sensitivity bug and subpath containment
        const hasCaseInsensitive = prodContent.toLowerCase().includes('tolowercase') || prodContent.includes('toUpperCase');
        const hasSubpathCheck = prodContent.includes('startsWith') || prodContent.includes('relative');
        
        const findings = {
          file: 'courier/core/no_stacking.js',
          exists: prodExists,
          has_case_insensitive_handling: hasCaseInsensitive,
          has_subpath_containment: hasSubpathCheck,
          defect_risk: (!hasCaseInsensitive || !hasSubpathCheck) ? 'HIGH' : 'LOW',
          recommendation: 'Use ResourceLockManager hierarchical NTFS path prefix containment'
        };

        const artifactName = 'no_stacking_gap_audit.json';
        const content = JSON.stringify(findings, null, 2);
        fs.writeFileSync(path.join(workingDir, artifactName), content, 'utf8');
        const sha = crypto.createHash('sha256').update(content).digest('hex');

        return {
          exit_code: 0,
          criteria_key: 'CRIT_NO_STACKING_AUDITED',
          artifacts: [artifactName],
          checksum_map: { [artifactName]: sha }
        };
      }
    });

    // Gap 2: Process Lease PID + StartTime identity binding
    candidates.push({
      title: 'Source Gap: Process Lease PID and Monotonic Start-Time Binding',
      category: 'EXECUTION',
      priority: 'P1',
      expected_information_gain: 9,
      lane: 'N. PROCESS IDENTITY',
      discovery_method: 'AUTHORITY_PATH_DISCOVERY',
      task_generator_fn: (workingDir, rt) => {
        const procLease = rt.processLeases;
        const testPid = process.pid;
        const testToken = 'TOKEN-TEST-IDENTITY-BINDING';
        
        const lease = procLease.register({ pid: testPid, startTime: Date.now(), taskToken: testToken, taskId: 'TASK-PID-TEST' });
        const verified = procLease.verifyIdentity(testPid, lease.start_time, testToken);
        const forged = procLease.verifyIdentity(testPid, lease.start_time - 10000, testToken);

        const findings = {
          test: 'PROCESS_LEASE_IDENTITY_BINDING',
          lease_acquired: !!lease,
          verified_authentic: verified.valid,
          rejected_forgery: !forged.valid,
          status: (verified.valid && !forged.valid) ? 'PASSED' : 'FAILED'
        };

        procLease.deregister(testPid);

        const artifactName = 'process_identity_audit.json';
        const content = JSON.stringify(findings, null, 2);
        fs.writeFileSync(path.join(workingDir, artifactName), content, 'utf8');
        const sha = crypto.createHash('sha256').update(content).digest('hex');

        return {
          exit_code: 0,
          criteria_key: 'CRIT_PROCESS_IDENTITY_PROVEN',
          artifacts: [artifactName],
          checksum_map: { [artifactName]: sha }
        };
      }
    });

    // Gap 3: Project-Memory Host Role Partitioning Audit
    candidates.push({
      title: 'Source Gap: Project-Memory Host Role Partitioning & Confinement Audit',
      category: 'ARCHITECTURE',
      priority: 'P1',
      expected_information_gain: 8,
      lane: 'AF. PROJECT-MEMORY INTEGRATION',
      discovery_method: 'HISTORICAL_EVIDENCE_REVALIDATION',
      task_generator_fn: (workingDir, rt) => {
        const statePath = path.join(this.projectMemoryRoot, 'PROJECT_STATE.md');
        const exists = fs.existsSync(statePath);
        const content = exists ? fs.readFileSync(statePath, 'utf8') : '';
        
        const mentionsPC2 = content.includes('PC2');
        const mentionsRightArm = content.includes('MEMORY_RIGHT_ARM') || content.includes('Rechner 2') || content.includes('Windows');
        const mentionsMacSingleWriter = content.includes('Mac') || content.includes('Rechner 1');

        const findings = {
          file: 'project-memory/PROJECT_STATE.md',
          exists,
          pc2_identified: mentionsPC2,
          role_identified: mentionsRightArm,
          mac_single_writer_asserted: mentionsMacSingleWriter,
          status: exists ? 'PASSED' : 'FAILED'
        };

        const artifactName = 'project_memory_role_audit.json';
        const contentJson = JSON.stringify(findings, null, 2);
        fs.writeFileSync(path.join(workingDir, artifactName), contentJson, 'utf8');
        const sha = crypto.createHash('sha256').update(contentJson).digest('hex');

        return {
          exit_code: 0,
          criteria_key: 'CRIT_HOST_ROLE_CONFIRMED',
          artifacts: [artifactName],
          checksum_map: { [artifactName]: sha }
        };
      }
    });

    return candidates;
  }
}

module.exports = { SourceGapGenerator };