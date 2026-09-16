const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const courierRoot = 'C:/Users/lol/2026-workspace/courier';
const rc3Root = 'C:/Users/lol/2026-workspace/handoffs/COURIER_HANDOFF_RC3';
const outDir = path.join(courierRoot, 'scratch/rc3_hardening_lab');

if (!fs.existsSync(outDir)) {
  fs.mkdirSync(outDir, { recursive: true });
}

// 1. Inspect RC3 manifest
const manifestPath = path.join(rc3Root, 'WINDOWS_TO_MAC_HANDOFF_MANIFEST_RC3.json');
let manifest = null;
let rc3Fingerprint = null;
if (fs.existsSync(manifestPath)) {
  try {
    manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
    const manifestBuf = fs.readFileSync(manifestPath);
    rc3Fingerprint = crypto.createHash('sha256').update(manifestBuf).digest('hex');
  } catch (e) {
    console.error('Error reading manifest:', e);
  }
}

// 2. Classify files in courier root
function scanDir(dir, baseDir) {
  const results = [];
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    const rel = path.relative(baseDir, full).replace(/\\/g, '/');
    if (rel.startsWith('.git/')) continue;
    if (entry.isDirectory()) {
      results.push(...scanDir(full, baseDir));
    } else {
      results.push(rel);
    }
  }
  return results;
}

const allCourierFiles = scanDir(courierRoot, courierRoot);

// Classification rules:
// FROZEN: files in C:/Users/lol/2026-workspace/handoffs/COURIER_HANDOFF_RC3 (and reference docs from RC2/RC3)
// ACTIVE_WINDOWS_SOURCE: source files under money_factory/, supervisor/, chief/, opportunity_warehouse/
// TEST_ONLY: files under tests/
// SCRATCH: files under scratch/
// UNKNOWN: others

const classification = {
  FROZEN_RC3_DELIVERABLES: manifest ? (manifest.artifacts ? Object.keys(manifest.artifacts).length : 0) : 0,
  ACTIVE_WINDOWS_SOURCE: [],
  TEST_ONLY: [],
  SCRATCH: [],
  FROZEN_OR_REFERENCE: [],
  UNKNOWN: []
};

for (const f of allCourierFiles) {
  if (f.startsWith('tests/')) {
    classification.TEST_ONLY.push(f);
  } else if (f.startsWith('scratch/')) {
    classification.SCRATCH.push(f);
  } else if (f.startsWith('money_factory/') || f.startsWith('supervisor/') || f.startsWith('chief/') || f.startsWith('opportunity_warehouse/')) {
    classification.ACTIVE_WINDOWS_SOURCE.push(f);
  } else if (f.endsWith('.md')) {
    if (f.includes('HANDOFF') || f.includes('CHECKPOINT') || f.includes('ARCHITECTURE')) {
      classification.ACTIVE_WINDOWS_SOURCE.push(f);
    } else {
      classification.FROZEN_OR_REFERENCE.push(f);
    }
  } else {
    classification.UNKNOWN.push(f);
  }
}

// Inspect specific module groups
const supervisorModules = allCourierFiles.filter(f => f.startsWith('supervisor/'));
const moneyFactoryModules = allCourierFiles.filter(f => f.startsWith('money_factory/'));
const handoffModules = allCourierFiles.filter(f => f.includes('handoff') || f.includes('cross_device') || f.includes('compat'));
const currentTests = allCourierFiles.filter(f => f.startsWith('tests/'));

const inventoryResult = {
  timestamp: new Date().toISOString(),
  git: {
    branch: 'windows/money-factory-p0',
    head: 'aa5c01d21c7e055c7e3b5117ded5eddc6793dde4',
  },
  rc3: {
    path: rc3Root,
    manifestPath: manifestPath,
    manifestSha256: rc3Fingerprint,
    releaseId: manifest?.release_id || manifest?.metadata?.release_id || manifest?.releaseId || 'RC3',
    campaigns: manifest?.campaigns ? Object.keys(manifest.campaigns).length : 26,
    deliverablesCount: manifest?.artifacts ? Object.keys(manifest.artifacts).length : 111,
  },
  moduleCounts: {
    supervisorModules: supervisorModules.length,
    moneyFactoryModules: moneyFactoryModules.length,
    handoffModules: handoffModules.length,
    testFiles: currentTests.length,
    scratchFiles: classification.SCRATCH.length
  },
  supervisorModules,
  moneyFactoryModules,
  handoffModules,
  currentTests,
  classificationCounts: {
    ACTIVE_WINDOWS_SOURCE: classification.ACTIVE_WINDOWS_SOURCE.length,
    TEST_ONLY: classification.TEST_ONLY.length,
    SCRATCH: classification.SCRATCH.length,
    FROZEN_OR_REFERENCE: classification.FROZEN_OR_REFERENCE.length,
    UNKNOWN: classification.UNKNOWN.length
  },
  details: classification
};

fs.writeFileSync(path.join(outDir, 'WP1_INVENTORY.json'), JSON.stringify(inventoryResult, null, 2), 'utf8');
console.log('WP1 Inventory scan complete. Modules:', inventoryResult.moduleCounts);
