// Normalized activity state
let agentState = {
  MACBOOK: { MUSE: 'OFFLINE', CODEX: 'OFFLINE', GITHUB: 'OFFLINE', ANTIGRAVITY: 'OFFLINE' },
  WINDOWS: { MUSE: 'OFFLINE', CODEX: 'OFFLINE', GITHUB: 'OFFLINE', ANTIGRAVITY: 'OFFLINE' }
};

// F5 state recovery - load from localStorage if present
const storedState = localStorage.getItem('courierOperationsState');
if (storedState) {
  try {
    agentState = JSON.parse(storedState);
  } catch(e) {}
}

const API_BASE = 'http://127.0.0.1:8080';

// Canvas Water Fountain Setup
const canvas = document.getElementById('central-water-fountain');
let ctx = null;
let particles = [];
if (canvas) {
  ctx = canvas.getContext('2d');
}

function initFountain() {
  particles = [];
}

function spawnParticle(intensity) {
  if (!ctx) return;
  // intensity 0 to 4 based on active agents
  if (intensity === 0) return;
  
  const count = intensity * 2;
  for (let i=0; i<count; i++) {
    particles.push({
      x: canvas.width / 2 + (Math.random() * 20 - 10),
      y: canvas.height - 10,
      vx: (Math.random() - 0.5) * (intensity * 1.5),
      vy: -(Math.random() * 3 + intensity * 2),
      life: 1.0,
      decay: 0.01 + Math.random() * 0.02,
      color: `rgba(6, 182, 212, 1)`
    });
  }
}

function updateFountain() {
  if (!ctx) return;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  
  // Calculate total active agents
  let activeCount = 0;
  for (const m in agentState) {
    for (const a in agentState[m]) {
      if (agentState[m][a] === 'ACTIVE') activeCount++;
    }
  }
  
  spawnParticle(activeCount);
  
  for (let i = particles.length - 1; i >= 0; i--) {
    let p = particles[i];
    p.x += p.vx;
    p.y += p.vy;
    p.vy += 0.15; // gravity
    p.life -= p.decay;
    
    if (p.life <= 0) {
      particles.splice(i, 1);
      continue;
    }
    
    ctx.beginPath();
    ctx.arc(p.x, p.y, 3, 0, Math.PI*2);
    ctx.fillStyle = `rgba(6, 182, 212, ${p.life})`;
    ctx.fill();
  }
  
  requestAnimationFrame(updateFountain);
}

if (canvas) {
  requestAnimationFrame(updateFountain);
}

// Map from API states to UI components
async function fetchState() {
  try {
    const res = await fetch(`${API_BASE}/workers`);
    const data = await res.json();
    
    // reset to IDLE if online, OFFLINE if not in workers
    // Actually wait, let's keep it simple: assume if fetch fails, it's offline.
    // If it succeeds, loop through workers.
    let macFound = false;
    let winFound = false;
    
    const now = Date.now() / 1000;
    
    for (const [wid, worker] of Object.entries(data.workers || {})) {
      const isStale = (now - worker.last_seen) > 30; // 30s timeout
      
      let machine = null;
      if (wid.includes('MAC')) { machine = 'MACBOOK'; macFound = true; }
      else if (wid.includes('WINDOWS')) { machine = 'WINDOWS'; winFound = true; }
      
      if (machine) {
        if (isStale) {
          // offline
          Object.keys(agentState[machine]).forEach(a => agentState[machine][a] = 'OFFLINE');
        } else {
          // base state IDLE
          agentState[machine]['ANTIGRAVITY'] = worker.capabilities.includes('antigravity') ? 'IDLE' : 'OFFLINE';
          agentState[machine]['GITHUB'] = 'IDLE';
          agentState[machine]['CODEX'] = 'IDLE';
          agentState[machine]['MUSE'] = 'IDLE';
          
          if (worker.current_task) {
            // Task is running -> ACTIVE
            // Guess which agent based on instruction or target_capability
            const taskStr = JSON.stringify(worker.current_task).toLowerCase();
            if (taskStr.includes('muse')) agentState[machine]['MUSE'] = 'ACTIVE';
            else if (taskStr.includes('github') || taskStr.includes('publish')) agentState[machine]['GITHUB'] = 'ACTIVE';
            else if (taskStr.includes('antigravity')) agentState[machine]['ANTIGRAVITY'] = 'ACTIVE';
            else agentState[machine]['CODEX'] = 'ACTIVE'; // default execution
          }
        }
      }
    }
    
    if (!macFound) Object.keys(agentState['MACBOOK']).forEach(a => agentState['MACBOOK'][a] = 'OFFLINE');
    if (!winFound) Object.keys(agentState['WINDOWS']).forEach(a => agentState['WINDOWS'][a] = 'OFFLINE');
    
  } catch (err) {
    // If API fails, maybe it's just the demo running. Don't override window.demoOverrides if we are injecting from console.
  }
  
  // Stale protection / heartbeat (F5 recovery)
  localStorage.setItem('courierOperationsState', JSON.stringify(agentState));
  renderUI();
}

function renderUI() {
  for (const machine in agentState) {
    for (const agent in agentState[machine]) {
      const state = agentState[machine][agent];
      let prefix = machine === 'MACBOOK' ? 'mac' : 'win';
      let id = `agent-${prefix}-${agent.toLowerCase()}`;
      
      let el = document.getElementById(id);
      if (el) {
        el.className = `agent-status-item ${state.toLowerCase()}`;
        let stateEl = el.querySelector('.agent-state');
        if (stateEl) stateEl.innerText = state;
      }
    }
  }
}

// Fetch every 2 seconds
setInterval(fetchState, 2000);
fetchState();

// For local demo testing via browser console without server
window.demoSetAgentState = function(machine, agent, state) {
  if (agentState[machine] && agentState[machine][agent]) {
    agentState[machine][agent] = state;
    renderUI();
  }
};
