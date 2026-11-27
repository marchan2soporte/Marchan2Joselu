/* Marchan2 · Monitor de cocina (KDS) independiente.
   Se abre en http://IP:PUERTO/cocina. Empareja la pantalla una vez, elige el
   monitor configurado en Administración y muestra las comandas de sus tipos
   de preparación con cronómetro, aviso sonoro y tres disposiciones. */
const $=s=>document.querySelector(s);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const TOKEN=$('meta[name="marchan-token"]').content,LAN=$('meta[name="marchan-lan"]').content==='1';
const store={get:k=>{try{return localStorage.getItem(k)}catch(e){return null}},set:(k,v)=>{try{localStorage.setItem(k,v)}catch(e){}}};
let monitorId=Number(store.get('marchan-kds-monitor'))||0,data=null,seen=null,audioCtx=null,pollTimer=null,clockTimer=null;
const LAYOUTS={left:'Desde la izquierda',right:'Desde la derecha',stack:'Apiladas (papel pinchado)'};
const SOUNDS={beep:'Pitido',bell:'Campana',double:'Doble pitido',off:'Sin sonido'};

function toast(text,error){const t=$('#kds-toast');t.textContent=text;t.className='kds-toast show'+(error?' error':'');clearTimeout(t.timer);t.timer=setTimeout(()=>t.className='kds-toast',3500)}
async function api(path,body){const headers={'X-Marchan2-Device':store.get('marchan-device')||''};if(body!==undefined){headers['Content-Type']='application/json';headers['X-Marchan2-Token']=TOKEN}
  const res=await fetch('/api/'+path,{headers,...(body===undefined?{}:{method:'POST',body:JSON.stringify(body)})});const r=await res.json().catch(()=>({}));
  if(!res.ok){const e=Error(r.error||'Sin conexión con el servidor.');e.pair=!!r.pair_required;throw e}return r}

/* ---------- Sonido ---------- */
function ensureAudio(){if(!audioCtx){try{audioCtx=new (window.AudioContext||window.webkitAudioContext)()}catch(e){}}if(audioCtx?.state==='suspended')audioCtx.resume();return audioCtx}
function play(kind,volume){const ctx=ensureAudio();if(!ctx||kind==='off'||!volume)return;const v=Math.max(.01,volume/100)*.6;
  const tone=(f,t,d)=>{const o=ctx.createOscillator(),g=ctx.createGain();o.type=kind==='bell'?'triangle':'square';o.frequency.value=f;o.connect(g);g.connect(ctx.destination);g.gain.setValueAtTime(v,ctx.currentTime+t);g.gain.exponentialRampToValueAtTime(.0001,ctx.currentTime+t+d);o.start(ctx.currentTime+t);o.stop(ctx.currentTime+t+d+.02)};
  if(kind==='bell'){tone(1320,0,.9);tone(990,.25,.9)}else if(kind==='double'){tone(880,0,.15);tone(880,.22,.15);tone(1175,.44,.25)}else{tone(950,0,.25)}}
if(audioCtx===null)$('#kds-unlock').hidden=false;
$('#kds-unlock').onclick=()=>{ensureAudio();$('#kds-unlock').hidden=true};

/* ---------- Emparejar y elegir monitor ---------- */
function pairScreen(){clearTimeout(pollTimer);$('#kds-board').innerHTML=`<form class="kds-panel" id="pair"><h1>Emparejar pantalla</h1><p>Introduce el código de 6 cifras que aparece en Marchan2 Servidor.</p><label>Nombre de la pantalla<input id="pair-name" value="Pantalla cocina" maxlength="40"></label><label>Código<input id="pair-code" inputmode="numeric" maxlength="6" required></label><p class="err" id="pair-err"></p><button>Emparejar</button></form>`;
  $('#pair').onsubmit=async e=>{e.preventDefault();try{const res=await fetch('/api/pair',{method:'POST',headers:{'Content-Type':'application/json','X-Marchan2-Token':TOKEN},body:JSON.stringify({code:$('#pair-code').value,name:$('#pair-name').value})});const r=await res.json();if(!res.ok)throw Error(r.error);store.set('marchan-device',r.device_token);navigator.storage?.persist?.();start()}catch(err){$('#pair-err').textContent=err.message}}}
async function chooseMonitor(){clearTimeout(pollTimer);let list;try{list=(await api('kds/monitors')).monitors}catch(e){if(e.pair)return pairScreen();return toast(e.message,true)}
  $('#kds-board').innerHTML=`<div class="kds-panel"><h1>Elige el monitor</h1><p>Los monitores se crean en Administración → Monitores de cocina.</p><div class="kds-choices">${list.filter(m=>m.active).map(m=>`<button data-monitor="${m.id}"><b>${esc(m.name)}</b><small>${esc(m.prep_types.join(' · '))}</small></button>`).join('')||'<p>No hay monitores.</p>'}</div></div>`;
  document.querySelectorAll('[data-monitor]').forEach(b=>b.onclick=()=>{monitorId=Number(b.dataset.monitor);store.set('marchan-kds-monitor',monitorId);seen=null;load()})}

/* ---------- Tablero ---------- */
const secs=stamp=>stamp?Math.max(0,Math.floor((Date.now()-new Date(stamp).getTime())/1000)):0;
const clock=s=>`${Math.floor(s/60)}:${String(s%60).padStart(2,'0')}`;
const SERVICE={llevar:'🛍 PARA LLEVAR',domicilio:'🛵 DOMICILIO',barra:'🍺 BARRA'};
function card(o,m){const s=secs(o.since),state=s>=m.late_minutes*60?'late':s>=m.warn_minutes*60?'warn':'';const courses=[...new Set(o.lines.map(l=>l.course))];
  return `<article class="ticket ${state}" data-order="${o.id}"><header><div><b class="t-table">${esc(o.table_name)}</b><small>#${o.id}${o.guests?' · 👥 '+o.guests:''}${o.user_name?' · '+esc(o.user_name):''}</small>${SERVICE[o.service_type]?`<em>${SERVICE[o.service_type]}</em>`:''}</div><span class="t-timer" data-since="${esc(o.since||'')}">${clock(s)}</span></header>
  <div class="t-body">${courses.map(c=>`<div class="t-course">${esc(c)}</div>${o.lines.filter(l=>l.course===c).map(l=>`<button class="t-line" data-line="${l.id}" style="--prep:${data.colors[l.prep]||'#888'}"><span class="t-qty">${l.qty}</span><span class="t-name"><b>${esc(l.name)}</b>${l.format&&!l.format.startsWith('MENÚ')?`<small>${esc(l.format)}</small>`:l.format?`<small>${esc(l.format)}</small>`:''}${l.extras.map(e=>`<small>+ ${esc(e.name)}</small>`).join('')}${l.note?`<i>⚠ ${esc(l.note)}</i>`:''}</span>${m.prep_types.length>1?`<span class="t-prep">${esc(l.prep)}</span>`:''}</button>`).join('')}`).join('')}</div>
  <footer><button class="t-ready" data-ready="${o.id}">✓ LISTO</button></footer></article>`}
function render(){const m=data.monitor;document.title='Cocina · '+m.name;$('#kds-name').textContent='🍳 '+m.name;$('#kds-types').textContent=m.prep_types.join(' · ');
  const items=data.orders.reduce((n,o)=>n+o.lines.reduce((k,l)=>k+l.qty,0),0),avg=data.orders.length?Math.round(data.orders.reduce((n,o)=>n+secs(o.since),0)/data.orders.length):0;
  $('#kds-orders').textContent=data.orders.length;$('#kds-items').textContent=items;$('#kds-avg').textContent=clock(avg);
  const board=$('#kds-board');board.className='kds-board layout-'+m.layout;
  const orders=m.layout==='stack'?[...data.orders].reverse():data.orders;
  board.innerHTML=orders.length?orders.map(o=>card(o,m)).join(''):`<div class="kds-empty"><b>Todo al día</b><span>Las comandas nuevas aparecerán aquí.</span></div>`;
  board.querySelectorAll('[data-ready]').forEach(b=>b.onclick=()=>act('ready',{order_id:Number(b.dataset.ready)},b.closest('.ticket')));
  board.querySelectorAll('[data-line]').forEach(b=>b.onclick=()=>{b.classList.add('done');act('line_ready',{line_id:Number(b.dataset.line)})})}
async function act(action,body,el){if(el)el.classList.add('leaving');try{await api('kds/'+action,{monitor_id:monitorId,...body});setTimeout(load,el?250:0)}catch(e){el?.classList.remove('leaving');toast(e.message,true)}}
async function load(){clearTimeout(pollTimer);if(!monitorId)return chooseMonitor();
  try{data=await api('kds/board?monitor='+monitorId)}catch(e){if(e.pair)return pairScreen();if(/monitor/i.test(e.message)){monitorId=0;return chooseMonitor()}toast(e.message,true);pollTimer=setTimeout(load,5000);return}
  const ids=new Set(data.orders.map(o=>o.id));if(seen&&[...ids].some(id=>!seen.has(id)))play(data.monitor.sound,data.monitor.volume);seen=ids;
  render();pollTimer=setTimeout(load,4000)}
clockTimer=setInterval(()=>{$('#kds-clock').textContent=new Date().toLocaleTimeString('es-ES',{hour:'2-digit',minute:'2-digit'});if(!data)return;const m=data.monitor;
  document.querySelectorAll('.t-timer').forEach(t=>{const s=secs(t.dataset.since);t.textContent=clock(s);const card=t.closest('.ticket');card.classList.toggle('warn',s>=m.warn_minutes*60&&s<m.late_minutes*60);card.classList.toggle('late',s>=m.late_minutes*60)})},1000);

/* ---------- Recuperar y configuración ---------- */
function sheet(html){const s=$('#kds-sheet');s.innerHTML=`<div class="sheet-card">${html}</div>`;s.hidden=false;s.onclick=e=>{if(e.target===s)s.hidden=true}}
$('#kds-recall').onclick=()=>{if(!data)return;sheet(`<h2>Recuperar comanda</h2><p>Comandas marcadas como listas en los últimos 15 minutos.</p><div class="kds-choices">${data.recent.map(r=>`<button data-recall="${r.order_id}"><b>${esc(r.table_name)} · #${r.order_id}</b><small>${r.n} platos · ${esc((r.ready_at||'').slice(11,16))}</small></button>`).join('')||'<p>No hay comandas recientes.</p>'}</div><button class="close">Cerrar</button>`);
  document.querySelectorAll('[data-recall]').forEach(b=>b.onclick=async()=>{await act('recall',{order_id:Number(b.dataset.recall)});$('#kds-sheet').hidden=true;toast('Comanda recuperada')});$('#kds-sheet .close').onclick=()=>$('#kds-sheet').hidden=true};
$('#kds-settings').onclick=()=>{if(!data)return chooseMonitor();const m=data.monitor;
  sheet(`<h2>Configuración · ${esc(m.name)}</h2>
  <h3>Cómo se colocan las comandas</h3><div class="layout-pick">${Object.entries(LAYOUTS).map(([k,v])=>`<button data-layout="${k}" class="${m.layout===k?'active':''}"><span class="lp lp-${k}"><i></i><i></i><i></i></span>${v}</button>`).join('')}</div>
  <h3>Aviso de comanda nueva</h3><div class="sound-row"><select id="s-sound">${Object.entries(SOUNDS).map(([k,v])=>`<option value="${k}" ${m.sound===k?'selected':''}>${v}</option>`).join('')}</select><label class="vol">🔈<input id="s-volume" type="range" min="0" max="100" step="5" value="${m.volume}"><b id="s-vol-label">${m.volume}%</b></label><button id="s-test">▶ Probar</button></div>
  <div class="sheet-actions"><button id="s-monitor">Cambiar de monitor</button><button id="s-save" class="primary">Guardar</button></div>`);
  let layout=m.layout;document.querySelectorAll('[data-layout]').forEach(b=>b.onclick=()=>{layout=b.dataset.layout;document.querySelectorAll('[data-layout]').forEach(x=>x.classList.toggle('active',x===b))});
  $('#s-volume').oninput=e=>$('#s-vol-label').textContent=e.target.value+'%';$('#s-test').onclick=()=>play($('#s-sound').value,Number($('#s-volume').value));
  $('#s-monitor').onclick=()=>{$('#kds-sheet').hidden=true;monitorId=0;store.set('marchan-kds-monitor','');chooseMonitor()};
  $('#s-save').onclick=async()=>{try{await api('kds/settings',{monitor_id:monitorId,layout,sound:$('#s-sound').value,volume:Number($('#s-volume').value)});$('#kds-sheet').hidden=true;toast('Configuración guardada');load()}catch(e){toast(e.message,true)}}};
$('#kds-full').onclick=()=>document.fullscreenElement?document.exitFullscreen():document.documentElement.requestFullscreen?.().catch(()=>{});
function start(){load()}
start();
