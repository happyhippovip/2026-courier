'use strict';
let token='', timer=null;
const $=id=>document.getElementById(id);
const labels={NOT_STARTED:'Noch nicht gestartet',RUNNING:'DAUERLAUF AKTIV',COOLDOWN:'DAUERLAUF AKTIV · Abstand vor nächster Aufgabe',IDLE:'Queue im Leerlauf',PAUSED:'Pausiert',RECONCILE_REQUIRED:'BRAUCHT PRÜFUNG · unklarer Ausgang',BLOCKED:'Blockiert · Prüfung erforderlich',BLOCKED_UNAVAILABLE:'Runtime nicht verfügbar · Queue gespeichert',CANNON_PAUSED_RESOURCE:'Ressourcenpause · Queue gespeichert',WAITING:'BEREIT — wartet auf Arbeit',COMPLETED:'Abgeschlossen',ERROR:'Fehler'};
async function refresh(){
 clearTimeout(timer);
 try{
  const res=await fetch('/api/cannon/status');if(!res.ok)throw Error('Status nicht verfügbar');
  const data=await res.json(); token=data.token;
  const s=data.state,m=s.metrics||{},c=s.counts||{};
  $('status').textContent=labels[s.status]||(data.helper_active?'DAUERLAUF AKTIV':s.status);
  $('notice').textContent=data.helper_exit && !data.helper_active?`Test gestoppt: ${data.error?.error||'Kein vollständiger Abschluss. Siehe Prüfdaten.'}`:'';
  const currentBuild=data.loaded_build===data.source_build;
  if(!currentBuild)$('notice').textContent='Neue Version vorhanden – Cannon neu öffnen.';
  $('counts').replaceChildren();
  const lanes=Object.values(s.lanes||{}), active=lanes.find(l=>l.phase==='RUNNING');
  $('current-task').textContent=`Aktuelle Aufgabe: ${active?.task?.task_id||'keine'}`;
  const counts={'Queue':c.QUEUED||0,'Läuft':s.active_lanes||0,'Wartet':c.RESULT_RECEIVED||0,'Blockiert':lanes.filter(l=>['UNKNOWN','ERROR'].includes(l.phase)).length,'Erledigt':m.DONE||0};
  for(const [key,value]of Object.entries(counts)){const cell=document.createElement('span');cell.textContent=`${key}: ${value}`;$('counts').append(cell);}
  $('result').textContent=s.last_result?JSON.stringify(s.last_result,null,2):'Noch kein bestätigtes Ergebnis.';
  $('evidence').textContent=JSON.stringify({...data,token:undefined},null,2);
  const bs = s.status || 'IDLE';
  const canStart = currentBuild && !data.helper_active && (bs === 'IDLE' || bs === 'COMPLETED' || bs === 'NOT_STARTED');
  const canPauseStop = data.helper_active;
  const canResume = currentBuild && !data.helper_active && ['PAUSED','COOLDOWN','WAITING','BLOCKED_UNAVAILABLE','CANNON_PAUSED_RESOURCE'].includes(bs);
  $('start').disabled=!canStart;
  $('resume').disabled=!canResume;
  $('pause').disabled=!canPauseStop; $('stop').disabled=!canPauseStop;
  const runLabel=data.helper_active||bs==='PAUSED'?'Aktueller Lauf':'Letzter Lauf';
  $('run-info').textContent=(data.helper_active||data.session.mode==='UNENDLICH')?`${runLabel}: ∞ UNBEGRENZT · eine Aufgabe nach der anderen · 5s nach sauberem Abschluss.`:'Noch kein Lauf gestartet.';
  if(data.helper_active)timer=setTimeout(refresh,1000);
 }catch(e){$('notice').textContent=e.message;}
}
async function act(action){try{const r=await fetch('/api/cannon/action',{method:'POST',headers:{'Content-Type':'application/json','X-Symphony-Token':token},body:JSON.stringify({action})});const d=await r.json();if(!r.ok)throw Error(d.error);await refresh();}catch(e){$('notice').textContent=e.message;}}
for(const [id,action]of Object.entries({start:'START',pause:'PAUSE',resume:'RESUME',stop:'STOP_AFTER_CURRENT'}))$(id).addEventListener('click',()=>act(action));
$('refresh').addEventListener('click',refresh);refresh();
