// Cryptographically Signed Task Passport
const crypto = require('crypto');
const path = require('path');

class TaskPassport {
  static createPassport({ task_id, task_version = 1, goal_id, scope_paths = [], max_capability = 'WORKSPACE_WRITE', secret_salt = 'COURIER_V2' }) {
    const normPaths = scope_paths.map(p => path.resolve(p).toLowerCase().replace(/\\/g, '/')).sort();
    const payload = `${task_id}:${task_version}:${goal_id}:${normPaths.join(';')}:${max_capability}:${secret_salt}`;
    const signature = crypto.createHash('sha256').update(payload).digest('hex');
    return {
      task_id,
      task_version,
      goal_id,
      scope_paths: normPaths,
      max_capability,
      signature,
      issued_at: new Date().toISOString()
    };
  }

  static verifyPassport(passport, secret_salt = 'COURIER_V2') {
    if (!passport || !passport.signature) return { valid: false, reason: 'MISSING_SIGNATURE' };
    const normPaths = (passport.scope_paths || []).slice().sort();
    const payload = `${passport.task_id}:${passport.task_version}:${passport.goal_id}:${normPaths.join(';')}:${passport.max_capability}:${secret_salt}`;
    const expected = crypto.createHash('sha256').update(payload).digest('hex');
    if (passport.signature !== expected) {
      return { valid: false, reason: 'TAMPERED_PASSPORT_SIGNATURE' };
    }
    return { valid: true, passport };
  }
}

module.exports = { TaskPassport };
