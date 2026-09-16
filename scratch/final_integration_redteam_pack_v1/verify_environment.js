const fs = require('fs');
const { execSync } = require('child_process');
const crypto = require('crypto');

console.log('=== VERIFY ENVIRONMENT ===');

// 1. Verify V5 state
try {
  const v5State = JSON.parse(fs.readFileSync('C:/Users/lol/2026-workspace/courier/scratch/nightshift_adversarial_factory_v5/MISSION_STATE.json', 'utf8'));
  console.log('V5 Status:', v5State.status);
  console.log('V5 exact_next_action:', v5State.exact_next_action);
  if (v5State.status !== 'COMPLETE') {
    console.error('ERROR: V5 is not COMPLETE');
    process.exit(1);
  }
} catch (e) {
  console.error('ERROR reading V5 state:', e.message);
  process.exit(1);
}

// 2. Check git status
try {
  const branch = execSync('git rev-parse --abbrev-ref HEAD', { cwd: 'C:/Users/lol/2026-workspace/courier' }).toString().trim();
  const head = execSync('git rev-parse HEAD', { cwd: 'C:/Users/lol/2026-workspace/courier' }).toString().trim();
  console.log('Git Branch:', branch);
  console.log('Git Head:', head);
} catch (e) {
  console.error('Git check error:', e.message);
}

// 3. Check RC3 hash
try {
  const rc3Manifest = 'C:/Users/lol/2026-workspace/handoffs/COURIER_HANDOFF_RC3/WINDOWS_TO_MAC_HANDOFF_MANIFEST_RC3.json';
  const buf = fs.readFileSync(rc3Manifest);
  const hash = crypto.createHash('sha256').update(buf).digest('hex');
  console.log('RC3 Manifest SHA256:', hash);
  if (hash.toLowerCase() !== '739fe3d87af99a65b43ffb6ef53c47ebefcb6602448ace95fc7dd13dd3435cd4') {
    console.error('ERROR: RC3 manifest hash mismatch!');
    process.exit(1);
  }
} catch (e) {
  console.error('RC3 check error:', e.message);
  process.exit(1);
}

// 4. Check active processes
try {
  const tasklist = execSync('tasklist').toString();
  const lines = tasklist.split('\n');
  const nodeProcesses = lines.filter(l => l.toLowerCase().startsWith('node.exe'));
  console.log('Node processes count (including current):', nodeProcesses.length);
} catch (e) {
  console.error('Tasklist error:', e.message);
}

console.log('ENVIRONMENT VERIFICATION PASSED');
