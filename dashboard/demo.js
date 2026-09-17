async function runDemo() {
  console.log("CASE 1: all agents idle");
  window.demoSetAgentState('MACBOOK', 'MUSE', 'IDLE');
  window.demoSetAgentState('MACBOOK', 'CODEX', 'IDLE');
  await new Promise(r => setTimeout(r, 2000));
  
  console.log("CASE 2: one agent active");
  window.demoSetAgentState('MACBOOK', 'ANTIGRAVITY', 'ACTIVE');
  await new Promise(r => setTimeout(r, 2000));
  
  console.log("CASE 3: Muse active");
  window.demoSetAgentState('MACBOOK', 'ANTIGRAVITY', 'IDLE');
  window.demoSetAgentState('WINDOWS', 'MUSE', 'ACTIVE');
  await new Promise(r => setTimeout(r, 2000));
  
  console.log("CASE 4: Codex active");
  window.demoSetAgentState('WINDOWS', 'MUSE', 'IDLE');
  window.demoSetAgentState('MACBOOK', 'CODEX', 'ACTIVE');
  await new Promise(r => setTimeout(r, 2000));
  
  console.log("CASE 5: two agents simultaneously active");
  window.demoSetAgentState('WINDOWS', 'MUSE', 'ACTIVE');
  await new Promise(r => setTimeout(r, 2000));
  
  console.log("CASE 6: GitHub offline/paused");
  window.demoSetAgentState('MACBOOK', 'GITHUB', 'OFFLINE');
  window.demoSetAgentState('WINDOWS', 'GITHUB', 'OFFLINE');
  await new Promise(r => setTimeout(r, 2000));
  
  console.log("CASE 7: refresh while an agent is active (simulated by localStorage)");
  console.log(localStorage.getItem('courierOperationsState'));
  
  console.log("CASE 8: agent finishes and animation stops");
  window.demoSetAgentState('MACBOOK', 'CODEX', 'IDLE');
  window.demoSetAgentState('WINDOWS', 'MUSE', 'IDLE');
}
window.runDemo = runDemo;
