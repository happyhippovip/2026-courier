const fs = require('fs');
const path = require('path');

function scanDir(dir, depth = 0, maxDepth = 3) {
  if (depth > maxDepth) return [];
  let results = [];
  try {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const ent of entries) {
      if (['node_modules', '.git', 'scratch', 'handoffs', 'dist', 'coverage'].includes(ent.name)) continue;
      const full = path.join(dir, ent.name);
      if (ent.isDirectory()) {
        results.push({ type: 'dir', path: full });
        results = results.concat(scanDir(full, depth + 1, maxDepth));
      } else if (ent.isFile()) {
        results.push({ type: 'file', path: full, size: fs.statSync(full).size });
      }
    }
  } catch(e) {}
  return results;
}

const root = 'C:/Users/lol/2026-workspace/courier';
const tree = scanDir(root);
console.log('Total non-scratch files/dirs found:', tree.length);

const interestingFiles = tree.filter(item => 
  item.type === 'file' && 
  (item.path.endsWith('.js') || item.path.endsWith('.json') || item.path.endsWith('.md'))
);

console.log('\n--- INTERESTING FILES ---');
for (const f of interestingFiles) {
  const rel = path.relative(root, f.path).replace(/\\/g, '/');
  console.log(rel);
}
