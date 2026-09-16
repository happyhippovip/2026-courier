const fs = require('fs');
const path = require('path');

const transcriptPath = 'C:/Users/lol/.gemini/antigravity/brain/ec711710-4565-4f5b-9ad4-8d95cd8540b9/.system_generated/logs/transcript_full.jsonl';
const outDir = 'C:/Users/lol/2026-workspace/courier/scratch/rc3_hardening_lab';
if (!fs.existsSync(outDir)) {
  fs.mkdirSync(outDir, { recursive: true });
}

const content = fs.readFileSync(transcriptPath, 'utf8');
const lines = content.split('\n');
let found = null;
for (let i = lines.length - 1; i >= 0; i--) {
  const line = lines[i].trim();
  if (!line) continue;
  try {
    const obj = JSON.parse(line);
    if (obj.type === 'USER_INPUT' && obj.content && obj.content.includes('HARDENING LAB')) {
      found = obj.content;
      break;
    }
  } catch (e) {}
}

if (found) {
  fs.writeFileSync(path.join(outDir, 'MISSION_PROMPT.txt'), found, 'utf8');
  console.log('SUCCESS: Extracted prompt length:', found.length);
} else {
  console.log('NOT FOUND');
}
