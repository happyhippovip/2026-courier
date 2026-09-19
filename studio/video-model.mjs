export const scenes = [
  {title:'Aus Gedanken wird Richtung.', label:'Gedanken ordnen', detail:'Szene 01 · Muse sammelt die Idee am Thought-Punkt.', text:'Eine Idee wird zum Ausgangspunkt. Muse bringt Gedanken in eine klare Reihenfolge.'},
  {title:'Arbeit findet ihren Weg.', label:'Arbeit verbinden', detail:'Szene 02 · Muse verbindet die Arbeitsstationen.', text:'Vom Ziel zum nächsten Schritt. Ein sichtbarer Weg verbindet Gedanken, Arbeit und Ergebnisse.'},
  {title:'Vertrauen braucht Belege.', label:'Ergebnisse prüfen', detail:'Szene 03 · Muse erreicht die symbolische Prüfstation.', text:'Ein Ergebnis ist eine Einladung zur Prüfung. Die Animation ist kein Nachweis einer realen Ausführung.'},
  {title:'Bereit für den nächsten Gedanken.', label:'Klar weitergehen', detail:'Szene 04 · Muse führt den Ablauf zurück zum Ergebnis.', text:'Ergebnisse sichtbar machen. Den nächsten sinnvollen Schritt verstehen. Gemeinsam weiterdenken.'},
];
const points = [[14.5,78.5],[23.5,53],[35.5,51],[43.2,49.4],[65.7,49.4],[79.4,68.6],[65.2,82.6],[53,79.6],[35.2,82.4],[14.5,78.5]];
export function filmFrame(elapsed, duration) {
  const progress = ((elapsed % duration) + duration) % duration / duration;
  const routePosition = progress * (points.length - 1);
  const index = Math.floor(routePosition);
  const blend = (1 - Math.cos(Math.PI * (routePosition - index))) / 2;
  return {progress, scene:Math.min(3, Math.floor(progress*4)),
    x:points[index][0]+(points[index+1][0]-points[index][0])*blend,
    y:points[index][1]+(points[index+1][1]-points[index][1])*blend};
}
export function formatTime(seconds) {
  const value = Math.max(0, Math.floor(seconds));
  return `${String(Math.floor(value/60)).padStart(2,'0')}:${String(value%60).padStart(2,'0')}`;
}
export function cannonView(snapshot, now=Date.now()) {
  const age=now-Date.parse(snapshot?.observed_at || '');
  if(snapshot?.available!==true || !snapshot.cannon?.state || !Number.isFinite(age) || age< -5000 || age>=15000)
    return {live:false,label:'DEMO / KEINE LIVE-DATEN',moving:true,task:'Keine aktuellen Cannon-Daten.'};
  const c=snapshot.cannon,s=c.state;
  const labels={RUNNING:'ARBEITET',PAUSED:'PAUSIERT',IDLE:'WARTET',WAITING:'WARTET',COMPLETED:'FERTIG',ERROR:'BRAUCHT DICH',UNKNOWN:'BRAUCHT DICH',RECONCILE_REQUIRED:'BRAUCHT DICH'};
  const number=value=>Number.isSafeInteger(value)&&value>=0?String(value):'—';
  return {live:true,label:labels[s.status]||'BRAUCHT DICH',moving:s.status==='RUNNING',
    task:Array.isArray(s.tasks)&&s.tasks.length?s.tasks.filter(t=>typeof t==='string').join(' · '):'Keine aktuelle Aufgabe gemeldet.',
    done:number(s.metrics?.DONE),ready:number(s.counts?.READY ?? s.counts?.QUEUED),
    remaining:c.session?.mode==='UNENDLICH'?'∞':number(c.session?.count),
    mode:typeof c.session?.mode==='string'?c.session.mode:'—',
    result:typeof s.last_result?.result_id==='string'?s.last_result.result_id:'Kein Ergebnis gemeldet',
    provenance:c.live_muse==='UNPROVEN'?'Lokaler Cannon-Test · Live-Muse UNPROVEN':'Cannon-Status · keine unabhängige Ausführungsabnahme'};
}
export function museTelemetry(snapshot, now=Date.now()) {
  const age = now - Date.parse(snapshot?.observed_at || '');
  const tool = snapshot?.tools?.muse;
  if (!tool || !Number.isFinite(age) || age < -5000 || age >= 15000) {
    return {fresh:false, status:'Nicht aktuell belegt', task:'Keine aktuelle Muse-Aufgabe gemeldet.'};
  }
  const labels={COMPUTING:'Rechenaktivität gemeldet',OPEN:'Muse geöffnet',OFFLINE:'Muse als offline gemeldet'};
  if (!(tool.status in labels)) return {fresh:false,status:'Status unbekannt',task:'Keine bestätigte Aktivitätsmeldung.'};
  return {fresh:true,status:labels[tool.status],task:tool.task_known === true && typeof tool.current_task === 'string' && tool.current_task.trim()
    ? tool.current_task.slice(0,400) : 'Prozessstatus vorhanden; konkrete Aufgabe nicht gemeldet.'};
}
