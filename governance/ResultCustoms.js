// Result Customs & Independent Disk Evidence Verifier
const fs = require('fs');
const crypto = require('crypto');
const { TaskPassport } = require('./TaskPassport');

class EvidenceVerifier {
  static verifyArtifact(filePath, expectedSha256) {
    if (!fs.existsSync(filePath)) return { verified: false, reason: 'FILE_NOT_FOUND' };
    const buf = fs.readFileSync(filePath);
    const hash = crypto.createHash('sha256').update(buf).digest('hex');
    if (expectedSha256 && hash !== expectedSha256) {
      return { verified: false, reason: 'CHECKSUM_MISMATCH', actual: hash, expected: expectedSha256 };
    }
    return { verified: true, size: buf.length, hash };
  }
}

class ResultCustoms {
  static evaluateResultEnvelope({ task_id, passport, exit_code, artifacts = [], checksum_map = {} }) {
    if (exit_code !== 0) {
      return { accepted: false, reason: 'NON_ZERO_EXIT_CODE', requires_uncertainty_fence: true };
    }
    const pv = TaskPassport.verifyPassport(passport);
    if (!pv.valid) {
      return { accepted: false, reason: 'INVALID_RESULT_PASSPORT' };
    }
    if (!Array.isArray(artifacts) || artifacts.length === 0) {
      return { accepted: false, reason: 'EMPTY_ARTIFACT_MANIFEST' };
    }
    for (const art of artifacts) {
      if (!checksum_map[art]) {
        return { accepted: false, reason: `MISSING_CHECKSUM_FOR_${art}` };
      }
    }
    return { accepted: true, verified_artifacts: artifacts.length };
  }
}

module.exports = { ResultCustoms, EvidenceVerifier };
