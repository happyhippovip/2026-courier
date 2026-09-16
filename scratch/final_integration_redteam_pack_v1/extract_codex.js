const fs = require('fs');
const readline = require('readline');

async function run() {
  const stream = fs.createReadStream('C:/Users/lol/.gemini/antigravity/brain/ec711710-4565-4f5b-9ad4-8d95cd8540b9/.system_generated/logs/transcript_full.jsonl');
  const rl = readline.createInterface({ input: stream, crlfDelay: Infinity });
  let found = [];
  for await (const line of rl) {
    if (!line.trim()) continue;
    try {
      const obj = JSON.parse(line);
      if (obj.step_index >= 3463 && obj.step_index <= 3500 && obj.source === 'MODEL' && obj.content) {
        if (obj.content.includes('DEFECT-A01') || obj.content.includes('DEFECT-L01') || obj.content.includes('DEFECT-G01') || obj.content.includes('DEFECT-B01') || obj.content.includes('CODEX')) {
          found.push({ step: obj.step_index, content: obj.content });
        }
      }
    } catch(e){}
  }
  console.log('Found steps:', found.map(f => f.step));
  if (found.length > 0) {
    fs.writeFileSync('C:/Users/lol/2026-workspace/courier/scratch/final_integration_redteam_pack_v1/codex_extracted.txt', found[found.length - 1].content, 'utf8');
    console.log('Wrote last found step length:', found[found.length - 1].content.length);
  }
}
run();
