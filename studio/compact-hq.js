// Presentation only: every activity indicator is derived from the existing state bus.
export function workerIndicator(worker) {
  if (!worker) return {kind:'unknown', label:'?'};
  const status = String(worker.status || worker.state || 'UNKNOWN').toUpperCase();
  const age = worker.heartbeat_age_seconds;
  const stamp = Date.parse(worker.updated_at || worker.last_heartbeat || '');
  const fresh = (Number.isFinite(age) && age <= 90) || (Number.isFinite(stamp) && Math.abs(Date.now()-stamp) < 90000);
  if (/OFFLINE|STOPPED|DISABLED/.test(status)) return {kind:'off', label:'AUS'};
  if (/STALE|UNKNOWN/.test(status) || !fresh) return {kind:'unknown', label:'?'};
  if (/BLOCK|ERROR|WAITING/.test(status)) return {kind:'waiting', label:'WARTET'};
  if (/RUNNING|WORKING|BUSY|PROGRESSING/.test(status)) return {kind:'working', label:'AKTIV'};
  if (/IDLE|AVAILABLE|ONLINE|READY/.test(status)) return {kind:'on', label:'AN'};
  return {kind:'unknown', label:'?'};
}
function badge(el, worker) {
  const value = worker?.displayIndicator || workerIndicator(worker);
  el.dataset.state = value.kind;
  el.querySelector('em').textContent = value.label;
  el.title = worker ? `${worker.worker_id || worker.id || ''}: ${worker.status || worker.state || 'UNKNOWN'} · ${worker.current_task || worker.task || 'Keine Aufgabe'}` : 'Kein aktueller Statusnachweis';
  const detail = el.querySelector('small');
  if (detail) detail.textContent = worker?.detail || '';
}
export function updateCompactHQ(state) {
  if (!document.getElementById('machine-rail')) mount();
  const workers = Object.values(state.platform_runtime?.workers || {});
  for (let n=1;n<=8;n++) {
    const exact = workers.find(w => new RegExp(`(?:^|[-_])CLI[-_]?${n}(?:$|[-_])`, 'i').test(w.worker_id || ''));
    badge(document.getElementById(`cli-slot-${n}`), exact);
  }
  const mac = workers.find(w => /mac/i.test(w.platform || w.worker_id));
  const win = workers.find(w => /win/i.test(w.platform || w.worker_id));
  badge(document.getElementById('host-mac'), mac);
  badge(document.getElementById('host-win'), win);
  const local = state.local_tools;
  const age = Date.now() - Date.parse(local?.observed_at || '');
  const fresh = Number.isFinite(age) && age >= -5000 && age < 15000;
  if (fresh) badge(document.getElementById('host-mac'), {status:'ONLINE', heartbeat_age_seconds:0});
  const windows = fresh ? local.hosts?.windows : null;
  if (windows) {
    const detail = windows.runtime_sha
      ? `Courier gesund · ${windows.runtime_sha.slice(0,8)}`
      : (windows.courier_health === 'HEALTHY' ? 'Courier gesund' : 'Nicht erreichbar');
    badge(document.getElementById('host-win'), {
      status: windows.status,
      heartbeat_age_seconds: 0,
      task: 'Konkrete Aufgabe nicht gemeldet',
      detail,
    });
  }
  for (const [key, id] of [['muse','muse-main'],['chatgpt','rail-chatgpt'],['antigravity','rail-antigravity']]) {
    const tool = fresh ? local.tools?.[key] : null;
    const kind = tool?.status === 'COMPUTING' ? 'working' : tool?.status === 'OPEN' ? 'on' : tool?.status === 'OFFLINE' ? 'off' : 'unknown';
    const label = {working:'RECHNET',on:'GEÖFFNET',off:'AUS',unknown:'?'}[kind];
    badge(document.getElementById(id), {status:label, task: tool?.cpu_percent == null ? 'Arbeitsinhalt nicht gemeldet' : `${tool.cpu_percent}% CPU · Arbeitsinhalt nicht gemeldet`, displayIndicator:{kind,label}});
  }

}
function mount() {
  const rail = document.createElement('aside'); rail.id='machine-rail'; rail.setAttribute('aria-label','Computer und CLI Status');
  rail.innerHTML = `<div class="rail-caption">COMPUTER</div><div class="rail-host" id="host-mac"><b>⌘ MACBOOK</b><em>?</em><small></small></div><div class="rail-host" id="host-win"><b>⊞ WINDOWS</b><em>?</em><small></small></div><div class="rail-caption">CLI · LIVE</div><div class="cli-slots">${Array.from({length:8},(_,i)=>`<div class="cli-slot" id="cli-slot-${i+1}"><i></i><span>CLI${i+1}</span><em>?</em></div>`).join('')}</div><div class="rail-note">AN = frisch<br>? = unbestätigt</div>`;
  document.body.append(rail);
  const team=document.createElement('aside'); team.id='team-rail'; team.setAttribute('aria-label','Haupt-Worker und Agenten');
  team.innerHTML=`<div class="rail-caption">MAIN WORKER</div><div id="muse-main" class="muse-card"><img src="assets/muse-meta.svg" alt="Meta-Symbol"/><b>MUSE</b><small>HAUPTANTRIEB</small><em>?</em></div><div class="rail-caption">TEAM</div>${[['chatgpt','ChatGPT / Codex'],['antigravity','Google Antigravity']].map(([n,label])=>`<div class="rail-agent" id="rail-${n}"><b>${label}</b><em>?</em></div>`).join('')}<div class="rail-note">Laufwege ≈ CPU<br>Aufgabe unbekannt</div>`;
  document.body.append(team);
  const water=document.createElement('div'); water.className='fountain-motion'; water.setAttribute('aria-hidden','true'); water.innerHTML='<i></i><i></i><i></i><span></span>'; document.getElementById('living-hq-stage').append(water);
}


// Local app actors are display-only; they never change Courier workflow truth.
export function localToolActors(snapshot) {
  const age = Date.now() - Date.parse(snapshot?.observed_at || '');
  const fresh = Number.isFinite(age) && age >= -5000 && age < 15000;
  return [
    ['chatgpt','ChatGPT / Codex',14.5,48,11,84,'💬'],
    ['muse','MUSE',75,59,50,88,'∞'],
    ['antigravity','Google Antigravity',67,46,80,87,'✦'],
  ].map(([key,name,x,y,restX,restY,icon]) => {
    const tool = fresh ? snapshot.tools?.[key] : null;
    const active = tool?.status === 'COMPUTING';
    const label = active ? 'RECHNET' : tool?.status === 'OPEN' ? 'GEÖFFNET' : tool?.status === 'OFFLINE' ? 'AUS' : 'UNBESTÄTIGT';
    return {id:`local-tool-${key}`,name,title:label,display_state:label,icon,
      x:restX,y:restY,homeX:restX,homeY:restY,targetX:active?x:restX,targetY:active?y:restY,
      state:active?'WORKING':tool?.status==='OPEN'?'SAFE_IDLE':'UNKNOWN',
      task:'Lokale Prozessaktivität; konkrete Aufgabe nicht gemeldet',
      speech:active?'Rechenaktivität · Weg symbolisch':'', role:'Lokales Arbeitstool',
      provider:key,is_active:active,is_bodyguard:false,is_blocked:false,progress:0,
      activity_source:'PROCESS_CPU_DELTA',animation:active?'working':'idle'};
  });
}
