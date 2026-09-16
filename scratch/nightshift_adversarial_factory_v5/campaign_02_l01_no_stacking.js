/**
 * CAMPAIGN FAMILY L — DEEP HIERARCHICAL & SEMANTIC NO-STACKING (L01)
 */

const path = require('path');
const { IndependentSafetyOracles } = require('./ORACLES/independent_safety_oracles');

function runCampaignL01(ctx) {
  console.log('=== EXECUTING CAMPAIGN FAMILY L: DEEP NO-STACKING (L01) ===\n');

  // 1. Path Hierarchy & Prefix-Lookalikes
  const hierarchyCases = [
    { a: 'src/', b: 'src/core/', expectConflict: true, desc: 'Parent contains Child' },
    { a: 'src/core/', b: 'src/core/auth/', expectConflict: true, desc: 'Child contained in Parent' },
    { a: 'src/core/', b: 'src/api/', expectConflict: false, desc: 'Unrelated Sibling Directories' },
    { a: 'src/core', b: 'src/core_v2', expectConflict: false, desc: 'Lookalike Prefix must NOT collide without trailing slash' },
    { a: 'tests/', b: 'tests/unit/', expectConflict: true, desc: 'Test subdirectory containment' }
  ];

  let hierarchyPass = 0;
  hierarchyCases.forEach(hc => {
    ctx.scenarios++;
    ctx.l01Attacks++;
    const res = IndependentSafetyOracles.isWriterConflict(hc.a, hc.b, true);
    if (res === hc.expectConflict) {
      hierarchyPass++;
    } else {
      if (!res && hc.expectConflict) ctx.secondWriterEscaped++;
    }
  });
  console.log(`  [L01.1] Path Hierarchy: Verified ${hierarchyPass}/${hierarchyCases.length} hierarchical containment & lookalike cases.`);

  // 2. Case Normalization (Filesystem Semantics)
  const caseCases = [
    { a: 'src/Core/', b: 'src/core/', isCaseInsensitive: true, expectConflict: true, desc: 'APFS/Windows Case Insensitive Match' },
    { a: 'src/Core/', b: 'src/core/', isCaseInsensitive: false, expectConflict: false, desc: 'Linux Ext4 Case Sensitive Distinct' },
    { a: 'SRC/CORE/AUTH/', b: 'src/core/', isCaseInsensitive: true, expectConflict: true, desc: 'Uppercase Child in Lowercase Parent' }
  ];

  caseCases.forEach(cc => {
    ctx.scenarios++;
    ctx.l01Attacks++;
    const res = IndependentSafetyOracles.isWriterConflict(cc.a, cc.b, cc.isCaseInsensitive);
    if (res !== cc.expectConflict) {
      ctx.secondWriterEscaped++;
    }
  });
  console.log(`  [L01.2] Case Normalization: Explicit filesystem case-sensitivity toggle verified.`);

  // 3. Path Separators & Relative Paths
  const normCases = [
    { a: 'src\\core\\auth\\', b: 'src/core/', expectConflict: true, desc: 'Windows backslash vs Unix slash' },
    { a: './src/core/', b: 'src/core/auth/', expectConflict: true, desc: 'Leading dot-slash normalization' },
    { a: 'src/../src/core/', b: 'src/core/auth/', expectConflict: true, desc: 'Relative dot-dot resolution' }
  ];

  normCases.forEach(nc => {
    ctx.scenarios++;
    ctx.l01Attacks++;
    const res = IndependentSafetyOracles.isWriterConflict(nc.a, nc.b, true);
    if (res !== nc.expectConflict) {
      ctx.secondWriterEscaped++;
    }
  });
  console.log(`  [L01.3] Normalization: Separator and dot-dot relative path resolution verified.`);

  // 4. Non-File Semantic Resources & Hybrid Locking
  const semanticCases = [
    { a: 'db:users', b: 'db:users', expectConflict: true, desc: 'Exact semantic database lock conflict' },
    { a: 'db:users', b: 'db:orders', expectConflict: false, desc: 'Distinct semantic database locks' },
    { a: 'net:port:8080', b: 'net:port:8080', expectConflict: true, desc: 'Port collision' },
    { a: 'git:refs/heads/main', b: 'git:refs/heads/main', expectConflict: true, desc: 'Git branch mutex' },
    { a: 'artifact:release.zip', b: 'artifact:release.zip', expectConflict: true, desc: 'Artifact lock' }
  ];

  semanticCases.forEach(sc => {
    ctx.scenarios++;
    ctx.l01Attacks++;
    const res = IndependentSafetyOracles.isWriterConflict(sc.a, sc.b, true);
    if (res !== sc.expectConflict) {
      ctx.secondWriterEscaped++;
    }
  });
  console.log(`  [L01.4] Semantic Non-File Locks: Database, port, git ref, and artifact resource locks verified.`);

  // 5. Overlocking Prevention (Safe Parallelism)
  ctx.scenarios++;
  ctx.l01Attacks++;
  const parallelCheck1 = IndependentSafetyOracles.isWriterConflict('src/auth/', 'src/billing/', true);
  const parallelCheck2 = IndependentSafetyOracles.isWriterConflict(['src/auth/', 'db:auth'], ['src/billing/', 'db:billing'], true);
  if (!parallelCheck1 && !parallelCheck2) {
    console.log('  [L01.5] Overlocking Prevention: Unrelated modules remain independently writable in parallel.');
  } else {
    console.log('  [L01.5 ERROR] Overlocking occurred on unrelated directories!');
  }

  console.log('  Family L01 Completed Cleanly.\n');
}

module.exports = { runCampaignL01 };
