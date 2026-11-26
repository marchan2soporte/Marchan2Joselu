/* Marchan2 0.25 · TPV: menús, tarifas y monitor de cocina con tiempos. */

/* ---------- Menús ---------- */
const cartaChooseProduct=chooseProduct;
chooseProduct=function(id){const p=state.products.find(p=>p.id===id);if(p?.menu_sections?.length&&order())return menuDialog(p);return cartaChooseProduct(id)};
function menuDialog(p,formatId){const f=p.formats.find(f=>f.id===formatId)||(p.formats.length===1?p.formats[0]:null);
  if(!f){openModal(modalTitle(p.name,'Elige el formato del menú.')+`<div class="format-options fast-formats">${p.formats.map(f=>`<button class="format-option" data-menu-format="${f.id}"><strong>${esc(f.name)}</strong><span>${euro(f.price)}</span></button>`).join('')}</div>`);
    document.querySelectorAll('[data-menu-format]').forEach(b=>b.onclick=()=>menuDialog(p,Number(b.dataset.menuFormat)));return}
  const picks=p.menu_sections.map(s=>s.options.length===1?s.options[0]:null);
  const draw=()=>{$('#menu-sections').innerHTML=p.menu_sections.map((s,i)=>`<section class="menu-section"><h3><span class="step-dot ${picks[i]?'done':''}">${picks[i]?'✓':i+1}</span>${esc(s.name)}</h3><div class="menu-options">${s.options.map(id=>{const o=state.products.find(x=>x.id===id);return o?`<button class="menu-option ${picks[i]===id?'active':''}" data-menu-pick="${i}:${id}" style="--tile:${tileColor(o.category_id)}"><strong>${esc(o.name)}</strong>${typeof allergenChips==='function'?allergenChips(o.allergens,5):''}</button>`:''}).join('')}</div></section>`).join('');
    $('#menu-add').disabled=picks.some(x=>!x);
    document.querySelectorAll('[data-menu-pick]').forEach(b=>b.onclick=()=>{const [i,id]=b.dataset.menuPick.split(':').map(Number);picks[i]=id;draw()})};
  openModal(modalTitle(p.name+' · '+f.name,`${euro(f.price)} · Elige un plato de cada apartado.`)+`<div id="menu-sections" class="menu-scroll"></div><div class="form-actions"><button class="button secondary" data-close>Cancelar</button><button class="button primary" id="menu-add">Añadir menú</button></div>`);
  draw();$('#menu-add').onclick=async()=>{const r=await change('add_menu',{order_id:orderId,format_id:f.id,choices:picks},'Menú añadido');if(r){selectedLine=r.line_id;closeModal()}}}

/* ---------- Venta: tarifa activa y líneas de menú ---------- */
const cartaRenderPos=renderPos;
renderPos=function(){cartaRenderPos();const o=order();if(!o)return;
  const status=$('.sale-status');if(status&&state.active_tariff&&!status.querySelector('.tariff-live'))status.insertAdjacentHTML('afterbegin',`<span class="tariff-live">🕒 ${esc(state.active_tariff.name)} · ${state.active_tariff.percent>0?'+':''}${(state.active_tariff.percent/100).toLocaleString('es-ES')} %</span>`);
  document.querySelectorAll('.service-line').forEach(el=>{const l=o.lines.find(l=>l.id===Number(el.dataset.line));if(!l)return;
    if(l.menu_role==='item')el.classList.add('menu-item');if(l.menu_role==='parent')el.classList.add('menu-parent');
    if(l.tariff&&!el.querySelector('.tariff-tag'))el.querySelector('.line-info strong')?.insertAdjacentHTML('afterend',`<small class="tariff-tag">${esc(l.tariff)}</small>`)});
  document.querySelectorAll('.product[data-product]').forEach(el=>{const p=state.products.find(p=>p.id===Number(el.dataset.product));if(p?.menu_sections?.length&&!el.querySelector('.menu-badge'))el.querySelector('strong')?.insertAdjacentHTML('beforebegin','<span class="menu-badge">MENÚ</span>')})};

/* ---------- Monitor de cocina ---------- */
let kitchenSeen=null,kitchenTimer=null,kitchenSound=(()=>{try{return localStorage.getItem('marchan-kitchen-sound')!=='off'}catch(e){return true}})();
function beep(){try{const ctx=new (window.AudioContext||window.webkitAudioContext)();[0,0.18].forEach(t=>{const o=ctx.createOscillator(),g=ctx.createGain();o.frequency.value=880;o.connect(g);g.connect(ctx.destination);g.gain.setValueAtTime(.2,ctx.currentTime+t);g.gain.exponentialRampToValueAtTime(.001,ctx.currentTime+t+.15);o.start(ctx.currentTime+t);o.stop(ctx.currentTime+t+.16)})}catch(e){}}
function elapsed(stamp){if(!stamp)return 0;return Math.max(0,Math.floor((Date.now()-new Date(stamp).getTime())/1000))}
function clockText(s){return `${Math.floor(s/60)}:${String(s%60).padStart(2,'0')}`}
renderKitchen=async function(){const requested=prepFilter;
  try{const all=await api('preparation');if(view!=='kitchen'||requested!==prepFilter)return;
    const orders=all.map(o=>({...o,pending:o.lines.filter(l=>l.kitchen==='pending'&&l.prep===prepFilter)})).filter(o=>o.pending.length).map(o=>({...o,since:o.pending.map(l=>l.sent_at).filter(Boolean).sort()[0]})).sort((a,b)=>(a.since||'').localeCompare(b.since||''));
    const ids=new Set(orders.map(o=>o.id));if(kitchenSeen&&kitchenSound&&[...ids].some(id=>!kitchenSeen.has(id)))beep();kitchenSeen=ids;
    const avg=orders.length?Math.round(orders.reduce((s,o)=>s+elapsed(o.since),0)/orders.length):0;
    $('#main').innerHTML=`<div class="topbar"><div class="pills" style="flex:1;margin:0">${['COCINA','BARRA'].map(p=>`<button class="pill ${p===prepFilter?'active':''}" data-prep="${p}">${p}</button>`).join('')}</div><div class="kds-stats"><span><b>${orders.length}</b> comandas</span><span><b>${orders.reduce((s,o)=>s+o.pending.reduce((n,l)=>n+l.qty,0),0)}</b> platos</span><span>espera media <b>${clockText(avg)}</b></span></div><button class="button secondary" id="kds-sound">${kitchenSound?'🔔 Sonido':'🔕 Silencio'}</button><button class="button secondary" id="refresh-kitchen">Actualizar</button></div>
    <div class="kitchen-grid kds">${orders.length?orders.map(o=>{const s=elapsed(o.since);return `<section class="panel kitchen-card ${s>=1200?'late':s>=600?'warn':''}"><div class="kitchen-top"><b>${esc(o.table_name||'VENTA DIRECTA')} · #${o.id}</b><span class="kds-timer" data-since="${esc(o.since||'')}">${clockText(s)}</span></div><div class="kds-meta">${o.guests?`👥 ${o.guests} · `:''}${esc(o.user_name||'')}${o.service_type&&o.service_type!=='mesa'?' · '+esc((state.service_types||{})[o.service_type]||''):''}</div><div class="kitchen-body">${o.pending.sort((a,b)=>courses.indexOf(a.course)-courses.indexOf(b.course)).map(l=>`<article class="${l.menu_role==='item'?'from-menu':''}"><span class="badge">${esc(l.course)}</span><strong>${l.qty} × ${esc(l.name)}</strong>${esc(l.format)}${l.weight_label?' · '+esc(l.weight_label):''}${l.extras.length?'<br>+ '+l.extras.map(e=>esc(e.name)).join(', '):''}${l.note?'<br><b class="kds-note">'+esc(l.note)+'</b>':''}</article>`).join('')}</div><button class="button primary" data-ready="${o.id}">✓ Listo para servir</button></section>`}).join(''):empty('Todo al día','Las comandas nuevas aparecen aquí con su tiempo de espera.')}</div>`;
    $('#refresh-kitchen').onclick=renderKitchen;$('#kds-sound').onclick=()=>{kitchenSound=!kitchenSound;try{localStorage.setItem('marchan-kitchen-sound',kitchenSound?'on':'off')}catch(e){}if(kitchenSound)beep();renderKitchen()};
    clearInterval(kitchenTimer);kitchenTimer=setInterval(()=>{if(view!=='kitchen'){clearInterval(kitchenTimer);return}document.querySelectorAll('.kds-timer').forEach(t=>{const s=elapsed(t.dataset.since);t.textContent=clockText(s);const card=t.closest('.kitchen-card');card.classList.toggle('warn',s>=600&&s<1200);card.classList.toggle('late',s>=1200)})},1000);
    clearTimeout(renderKitchen.poll);renderKitchen.poll=setTimeout(()=>{if(view==='kitchen'&&!$('#modal').open)renderKitchen()},15000);
  }catch(e){toast(e.message,true)}};
