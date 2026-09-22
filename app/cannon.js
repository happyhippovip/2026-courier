'use strict';
let token='', timer=null;
const $=id=>document.getElementById(id);
const RUN_TARGET=1000000000;
let runBaseDone=null;
let lastDone=0;

function currentRunDone(total){
  total=Math.max(0,Math.floor(Number(total)||0));
  if(runBaseDone===null) runBaseDone=total;
  lastDone=total;
  return Math.max(0,total-runBaseDone);
}

function fmtCount(n){
  n=Math.max(0,Math.floor(Number(n)||0));
  return n.toLocaleString("de-DE");
}
const labels={NOT_STARTED:'Noch nicht gestartet',RUNNING:'DAUERLAUF AKTIV',COOLDOWN:'DAUERLAUF AKTIV · Abstand vor nächster Aufgabe',IDLE:'Queue im Leerlauf',PAUSED:'Pausiert',RECONCILE_REQUIRED:'BRAUCHT PRÜFUNG · unklarer Ausgang',BLOCKED:'Blockiert · Prüfung erforderlich',BLOCKED_UNAVAILABLE:'Runtime nicht verfügbar · Queue gespeichert',CANNON_PAUSED_RESOURCE:'Ressourcenpause · Queue gespeichert',WAITING:'Wartet · Queue gespeichert',COMPLETED:'Abgeschlossen',ERROR:'Fehler'};
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
  $('erledigt').textContent=
  'ERLEDIGT: '+fmtCount(currentRunDone(m.DONE||0))+
  ' / '+fmtCount(RUN_TARGET);
  $('uebrig').textContent='ÜBRIG: '+fmtCount(data.session.remaining ?? 1000000000);
  const counts={'Queue':c.QUEUED||0,'Läuft':s.active_lanes||0,'Wartet':c.RESULT_RECEIVED||0,'Blockiert':lanes.filter(l=>['UNKNOWN','ERROR'].includes(l.phase)).length,'Erledigt':currentRunDone(m.DONE||0)};
  for(const [key,value]of Object.entries(counts)){const cell=document.createElement('span');cell.textContent=`${key}: ${value}`;$('counts').append(cell);}
  const rt=data.live?data.live.text:s.last_result?JSON.stringify(s.last_result,null,2):'Noch kein bestätigtes Ergebnis.';if($('result').textContent!==rt)$('result').textContent=rt;
  $('evidence').textContent=JSON.stringify({...data,token:undefined},null,2);
  const bs = s.status || 'IDLE';
  const canStart = currentBuild && !data.helper_active && (bs === 'IDLE' || bs === 'COMPLETED' || bs === 'NOT_STARTED');
  const canPauseStop = data.helper_active;
  const canResume = currentBuild && !data.helper_active && ['PAUSED','COOLDOWN','WAITING','BLOCKED_UNAVAILABLE','CANNON_PAUSED_RESOURCE'].includes(bs);
  $('start').disabled=!canStart; $('mode').disabled=!canStart; $('count').disabled=!canStart;
  $('resume').disabled=!canResume;
  $('pause').disabled=!canPauseStop; $('stop').disabled=!canPauseStop;
  const runLabel=data.helper_active||bs==='PAUSED'?'Aktueller Lauf':'Letzter Lauf';
  $('run-info').textContent='Laufziel: 1.000.000.000 Aufgaben.';
  if(data.helper_active)timer=setTimeout(refresh,1000);
 }catch(e){$('notice').textContent=e.message;}
}
async function act(action){
if(action==='START'){
  runBaseDone=lastDone;
  const el=$('erledigt');
  if(el) el.textContent='ERLEDIGT: 0 / '+fmtCount(RUN_TARGET);
}
try{const r=await fetch('/api/cannon/action',{method:'POST',headers:{'Content-Type':'application/json','X-Symphony-Token':token},body:JSON.stringify({action,mode:$('mode').value,count:Number($('count').value)})});const d=await r.json();if(!r.ok)throw Error(d.error);await refresh();}catch(e){$('notice').textContent=e.message;}}
for(const [id,action]of Object.entries({start:'START',pause:'PAUSE',resume:'RESUME',stop:'STOP_AFTER_CURRENT'}))$(id).addEventListener('click',()=>act(action));
$('refresh').addEventListener('click',refresh);refresh();
