/* Marchan2 0.26 · Comandero móvil
   Interfaz propia para pantallas de teléfono (≤ 760 px): mesas, carta y cuenta
   con botones grandes para el pulgar, barra inferior fija, hojas deslizantes,
   avisos de «plato listo» con vibración y notas rápidas de preparación. */
const mobileQuery=matchMedia('(max-width: 760px)');
const isMobile=()=>mobileQuery.matches;
let mTab='carta',mQuery='',mFamily='',mCategory=0,mCenter=0,mLastKitchen=null,mAlertTimer=null;
const vibrate=p=>{try{navigator.vibrate?.(p)}catch(e){}};

/* ---------- Notas rápidas (escritorio y móvil) ---------- */
noteDialog=function(){const l=line();if(!l)return;const notes=state.prep_notes||[];
  openModal(modalTitle('Nota de preparación',l.name)+`<div class="quick-notes">${notes.map(n=>`<button type="button" class="quick-note" data-quick-note="${esc(n)}">${esc(n)}</button>`).join('')}</div><label>NOTA<textarea id="line-note-text" rows="3" maxlength="300" placeholder="Escribe o toca las notas rápidas">${esc(l.note)}</textarea></label><div class="form-actions"><button class="button secondary" id="clear-note">Borrar</button><button class="button primary" id="save-note">Guardar nota</button></div>`);
  const area=$('#line-note-text');
  document.querySelectorAll('[data-quick-note]').forEach(b=>{const n=b.dataset.quickNote;b.classList.toggle('active',area.value.toUpperCase().split(' · ').includes(n));b.onclick=()=>{const parts=area.value.split(' · ').map(x=>x.trim()).filter(Boolean);const i=parts.map(x=>x.toUpperCase()).indexOf(n);if(i>=0)parts.splice(i,1);else parts.push(n);area.value=parts.join(' · ');b.classList.toggle('active',i<0);vibrate(10)}});
  $('#clear-note').onclick=()=>{area.value='';document.querySelectorAll('[data-quick-note]').forEach(b=>b.classList.remove('active'))};
  $('#save-note').onclick=async()=>{if(await change('note',{order_id:orderId,line_ids:[l.id],note:area.value},'Nota guardada'))closeModal()}};

/* ---------- Avisos de plato listo ---------- */
function checkReady(){if(!state?.orders||!currentUser)return;const now={};const ready=[];
  for(const o of state.orders)for(const l of o.lines){now[l.id]=l.kitchen;if(mLastKitchen&&mLastKitchen[l.id]==='pending'&&l.kitchen==='ready'&&(o.created_by===currentUser.id||currentUser.role==='admin'))ready.push({o,l})}
  mLastKitchen=now;if(!ready.length)return;
  const byOrder={};ready.forEach(({o,l})=>{(byOrder[o.id]=byOrder[o.id]||{o,items:[]}).items.push(`${l.qty}× ${l.name}`)});
  const text=Object.values(byOrder).map(x=>`<b>${esc(x.o.table_name||'Venta directa')}</b> · ${x.items.map(esc).join(', ')}`).join('<br>');
  let el=$('#ready-alert');if(!el){document.body.insertAdjacentHTML('beforeend','<div id="ready-alert" role="alert"></div>');el=$('#ready-alert')}
  el.innerHTML=`<span class="ready-icon">🔔</span><div><small>LISTO PARA SERVIR</small><p>${text}</p></div><button data-m="dismiss-alert" aria-label="Cerrar aviso">✕</button>`;el.className='show';
  vibrate([220,90,220]);if(typeof beep==='function')beep();clearTimeout(mAlertTimer);mAlertTimer=setTimeout(()=>el.className='',12000)}

/* ---------- Render ---------- */
const mobilePrevRender=render;
render=function(){if(state&&currentUser)checkReady();
  if(isMobile()&&state&&currentUser&&view==='pos'&&!order())view='tables';
  if(!isMobile()||!state||!currentUser||!['tables','pos'].includes(view)||(view==='pos'&&!order())){document.body.classList.remove('m-app');if(isMobile()&&state&&currentUser)document.body.classList.add('m-lite');else document.body.classList.remove('m-lite');return mobilePrevRender()}
  document.body.classList.remove('m-lite','selling','login-mode');document.body.classList.add('m-app','tpv-mode');$('#user-switch').hidden=false;
  if(view==='pos')mOrder();else mTables()};
mobileQuery.addEventListener('change',()=>{if(state&&currentUser)render()});

function mInitials(name){return esc((name||'?').trim().slice(0,2))}
function mTop(left,title,sub,right){return `<header class="m-top">${left}<div class="m-title"><h1>${title}</h1>${sub?`<small>${sub}</small>`:''}</div>${right}</header>`}

function mTables(){if(!mCenter||!state.centers.some(c=>c.id===mCenter))mCenter=state.centers[0]?.id;
  const tables=state.tables.filter(t=>t.center_id===mCenter),occupied=state.orders.filter(o=>o.table_id).length,pending=state.orders.reduce((s,o)=>s+o.due,0);
  const direct=state.orders.filter(o=>!o.table_id);
  $('#main').innerHTML=mTop(`<button class="m-avatar" data-m="menu" aria-label="Menú">${mInitials(currentUser.name)}</button>`,'Mesas',`${occupied} ocupadas · ${euro(pending)} pendiente`,`<button class="m-icon ${state.clock?.working?'on':''}" data-m="clock" aria-label="Fichar">⏱</button>`)+
  `<div class="m-body"><div class="m-chips">${state.centers.map(c=>{const n=state.orders.filter(o=>state.tables.find(t=>t.id===o.table_id)?.center_id===c.id).length;return `<button class="m-chip ${c.id===mCenter?'active':''}" data-m="center" data-id="${c.id}">${esc(c.name)}${n?` <b>${n}</b>`:''}</button>`}).join('')}</div>
  <div class="m-table-grid">${tables.map(t=>{const o=state.orders.find(o=>o.table_id===t.id);const late=o&&o.minutes_open>=90,billing=o&&o.bill_requested_at,cook=o&&o.lines.some(l=>l.kitchen==='pending'),ready=o&&o.lines.some(l=>l.kitchen==='ready'&&l.menu_role!=='parent');
    return `<button class="m-table ${o?'busy':''} ${late?'late':''} ${billing?'billing':''}" data-m="table" data-id="${t.id}"><span class="m-table-name">${esc(t.name)}</span>${o?`<span class="m-table-total">${euro(o.due)}</span><span class="m-table-meta">${o.guests?'👥'+o.guests+' · ':''}${minutesLabel(o.minutes_open)}</span>${o.bill_requested_at?'<i class="m-dot bill" title="Pide la cuenta">🧾</i>':cook?'<i class="m-dot cook" title="En cocina">♨</i>':ready?'<i class="m-dot ready" title="Listo">✓</i>':''}`:`<span class="m-table-free">Libre · ${t.seats||4} pl.</span>`}</button>`}).join('')}</div>
  ${direct.length?`<h2 class="m-h2">Ventas directas</h2><div class="m-list">${direct.map(o=>`<button class="m-row" data-m="order" data-id="${o.id}"><span class="m-row-icon">${({llevar:'🛍',domicilio:'🛵',barra:'🍺'})[o.service_type]||'🧾'}</span><span class="m-row-main"><b>${esc(o.table_name||'Cuenta #'+o.id)}</b><small>${o.lines.length} líneas · ${minutesLabel(o.minutes_open)}</small></span><b>${euro(o.due)}</b></button>`).join('')}</div>`:''}</div>
  <nav class="m-bottom"><button class="m-bottom-btn" data-m="direct"><span>＋</span>Venta rápida</button><button class="m-bottom-btn" data-m="takeaway"><span>🛍</span>Para llevar</button><button class="m-bottom-btn" data-m="soldout"><span>🚫</span>Agotados</button></nav>`}

function mProducts(){const q=mQuery.toLocaleLowerCase('es');
  const list=state.products.filter(p=>{const c=state.categories.find(c=>c.id===p.category_id);const fam=mFamily==='__fav'?p.favorite:mFamily==='__top'?state.best_sellers?.includes(p.id):(!mFamily||c?.parent===mFamily);return fam&&(!mCategory||p.category_id===mCategory)&&(!q||p.name.toLocaleLowerCase('es').includes(q))});
  if(!list.length)return empty('Sin productos','Prueba otra búsqueda o categoría.');
  return `<div class="m-products">${list.map(p=>{const min=Math.min(...p.formats.map(f=>f.price));return `<button class="m-product" data-m="product" data-id="${p.id}" style="--tile:${tileColor(p.category_id)}" ${!state.permissions?.includes('ticket_add')?'disabled':''}><span class="m-product-name">${esc(p.name)}</span>${p.menu_sections?.length?'<span class="menu-badge">MENÚ</span>':''}${typeof allergenChips==='function'?allergenChips(p.allergens,4):''}<span class="m-product-price">${p.formats.length>1?'<small>desde </small>':''}${euro(min)}</span><span class="m-plus">＋</span></button>`}).join('')}</div>`}

function mLines(o){if(!o.lines.length)return empty('Cuenta vacía','Añade productos desde la pestaña Carta.');
  return `<div class="m-lines">${o.lines.map(l=>{const editable=l.kitchen==='new'&&!o.paid&&!l.menu_role;const status=l.menu_role==='parent'?'MENÚ':l.kitchen==='new'?'Sin enviar':l.kitchen==='pending'?'En cocina':'Listo';
    return `<article class="m-line ${l.menu_role==='item'?'sub':''} ${selectedLine===l.id?'selected':''} k-${l.kitchen}"><div class="m-line-main" data-m="select-line" data-id="${l.id}"><b class="m-line-name">${esc(l.name)}</b><small>${esc(l.format)}${l.extras?.length?' · '+l.extras.map(e=>esc(e.name)).join(', '):''}${l.discount_label?' · '+esc(l.discount_label):''}${l.tariff?' · '+esc(l.tariff):''}</small>${l.note?`<em>📝 ${esc(l.note)}</em>`:''}<span class="m-status">${status}</span></div>
      <div class="m-line-side"><b>${euro(l.qty*l.price)}</b>${l.menu_role==='item'?`<span class="m-qty-static">${l.qty}</span>`:`<div class="m-stepper">${editable&&!l.is_weighed?`<button data-m="minus" data-id="${l.id}" aria-label="Quitar uno">−</button>`:'<span></span>'}<span>${l.qty}</span>${editable&&!l.is_weighed?`<button data-m="plus" data-id="${l.id}" aria-label="Añadir uno">+</button>`:'<span></span>'}</div>`}
      <div class="m-line-tools">${can('ticket_note')?`<button data-m="note" data-id="${l.id}" aria-label="Nota">📝</button>`:''}${l.kitchen==='new'&&!l.menu_role&&can('ticket_march')?`<button data-m="march" data-id="${l.id}" aria-label="Marchar">↗</button>`:''}${l.menu_role!=='item'&&!o.paid&&can('ticket_cancel')?`<button data-m="remove" data-id="${l.id}" aria-label="Quitar">🗑</button>`:''}</div></div></article>`}).join('')}</div>`}

function mOrder(){const o=order();if(!o){go('tables');return}
  const cu=typeof customerById==='function'?customerById(o.customer_id):null,newCount=o.lines.filter(l=>l.kitchen==='new'&&l.menu_role!=='parent').length,units=o.lines.filter(l=>l.menu_role!=='item').reduce((s,l)=>s+l.qty,0);
  const sub=[o.guests?'👥 '+o.guests:'',minutesLabel(o.minutes_open),cu?esc(cu.name):''].filter(Boolean).join(' · ');
  const families=[...new Set(state.categories.map(c=>c.parent))];
  $('#main').innerHTML=mTop('<button class="m-icon" data-m="back" aria-label="Volver a mesas">‹</button>',esc(o.table_name||'Venta directa'),sub||'Cuenta #'+o.id,'<button class="m-icon" data-m="more" aria-label="Más opciones">⋯</button>')+
  `${cu?.allergens?.length?`<div class="m-allergy">⚠ Alergias: ${cu.allergens.map(a=>esc(state.allergens[a])).join(', ')}</div>`:''}${state.active_tariff?`<div class="m-tariff">🕒 ${esc(state.active_tariff.name)} activa</div>`:''}
  <div class="m-tabs"><button class="${mTab==='carta'?'active':''}" data-m="tab" data-tab="carta">Carta</button><button class="${mTab==='cuenta'?'active':''}" data-m="tab" data-tab="cuenta">Cuenta${units?` <b>${units}</b>`:''}</button></div>
  <div class="m-body">${mTab==='carta'?`<div class="m-search">${svg('search')}<input id="m-search" type="search" placeholder="Buscar en la carta…" value="${esc(mQuery)}" enterkeyhint="search"></div>
    <div class="m-chips"><button class="m-chip ${!mFamily?'active':''}" data-m="family" data-id="">Todo</button><button class="m-chip gold ${mFamily==='__fav'?'active':''}" data-m="family" data-id="__fav">★ Favoritos</button>${state.best_sellers?.length?`<button class="m-chip gold ${mFamily==='__top'?'active':''}" data-m="family" data-id="__top">🔥 Top</button>`:''}${families.map(f=>`<button class="m-chip ${mFamily===f?'active':''}" data-m="family" data-id="${esc(f)}">${esc(f)}</button>`).join('')}</div>
    ${!mFamily.startsWith('__')?`<div class="m-chips small">${state.categories.filter(c=>!mFamily||c.parent===mFamily).map(c=>`<button class="m-chip ${mCategory===c.id?'active':''}" data-m="category" data-id="${c.id}" style="--tile:${tileColor(c.id)}"><i class="dot"></i>${esc(c.name)}</button>`).join('')}</div>`:''}
    <div id="m-products">${mProducts()}</div>`:mLines(o)}</div>
  <nav class="m-bottom m-order-bar"><div class="m-total"><small>${o.paid?'Pendiente':'Total'}</small><b>${euro(o.due)}</b></div>
    ${(()=>{const canPay=o.lines.length&&!actionDisabled('payments'),canSend=newCount&&can('ticket_send');
      if(canSend&&canPay)return `<button class="m-cta" data-m="send">♨ Enviar <b>${newCount}</b></button><button class="m-cta pay compact" data-m="pay" aria-label="Cobrar">€</button>`;
      if(canSend)return `<button class="m-cta" data-m="send">♨ Enviar a cocina <b>${newCount}</b></button>`;
      if(canPay)return `<button class="m-cta pay" data-m="pay">€ Cobrar</button>`;
      return `<button class="m-cta ghost" data-m="tab" data-tab="${mTab==='carta'?'cuenta':'carta'}">${mTab==='carta'?'Ver cuenta':'Añadir productos'}</button>`})()}</nav>`;
  const s=$('#m-search');if(s)s.oninput=e=>{mQuery=e.target.value;$('#m-products').innerHTML=mProducts()};
  if(o.table_id&&!o.lines.length&&o.guests==null&&typeof askedGuests!=='undefined'&&!askedGuests.has(o.id)&&!$('#modal').open){askedGuests.add(o.id);guestsDialog(true)}}

/* ---------- Hojas de opciones ---------- */
function mSheet(title,items){openModal(modalTitle(title)+`<div class="m-sheet">${items.map(([id,icon,label,disabled])=>`<button class="m-sheet-btn" data-m="sheet" data-id="${id}" ${disabled?'disabled':''}><span>${icon}</span>${esc(label)}</button>`).join('')}</div>`)}
function mMoreSheet(){const items=[['repeat_round','↻','Repetir ronda'],['bill_request','🧾',order()?.bill_requested_at?'Quitar «pide la cuenta»':'Pide la cuenta'],['guests','👥','Comensales'],['customer','👤','Cliente'],['service','🛵','Tipo de servicio'],['move','⇄','Cambiar de mesa'],['merge','⊕','Unir cuentas'],['invite','♡','Invitar'],['ticket_discount','%','Descuento de ticket'],['receipt','▤','Ver / imprimir cuenta'],['payments','€','Cobrar o dividir'],['cancel_ticket','✕','Cancelar ticket']];
  mSheet('Opciones de la cuenta',items.map(([id,i,l])=>[id,i,l,actionDisabled(id)]))}
function mMenuSheet(){mSheet(currentUser.name,[['nav:kitchen','♨','Cocina y barra'],['nav:customers','👥','Clientes'],['clock','⏱',state.clock?.working?'Fichar salida':'Fichar entrada'],['theme','🌓','Tema claro / oscuro'],['switch_user','↪','Cambiar de usuario']])}

/* ---------- Acciones ---------- */
async function mAction(b){const id=Number(b.dataset.id),act=b.dataset.m;
  switch(act){
    case 'dismiss-alert':$('#ready-alert').className='';return;
    case 'center':mCenter=id;vibrate(8);return mTables();
    case 'table':{vibrate(12);const r=await change('open',{table_id:id});if(r){orderId=r.order_id;selectedLine=null;mTab=state.orders.find(o=>o.id===r.order_id)?.lines.length?'cuenta':'carta';go('pos')}return}
    case 'order':orderId=id;selectedLine=null;mTab='cuenta';return go('pos');
    case 'direct':{const r=await change('open',{direct:true});if(r){orderId=r.order_id;selectedLine=null;mTab='carta';go('pos')}return}
    case 'takeaway':return directService('llevar');
    case 'kitchen':return go('kitchen');
    case 'menu':return mMenuSheet();
    case 'clock':return clockDialog();
    case 'back':selectedLine=null;mQuery='';return go('tables');
    case 'more':return mMoreSheet();
    case 'tab':mTab=b.dataset.tab;return mOrder();
    case 'family':mFamily=b.dataset.id;mCategory=0;return mOrder();
    case 'category':mCategory=mCategory===id?0:id;return mOrder();
    case 'product':{vibrate(15);b.classList.add('pop');setTimeout(()=>b.classList.remove('pop'),250);return chooseProduct(id)}
    case 'select-line':selectedLine=selectedLine===id?null:id;return mOrder();
    case 'plus':case 'minus':vibrate(8);return change('quantity',{line_id:id,delta:act==='plus'?1:-1});
    case 'note':selectedLine=id;return noteDialog();
    case 'march':selectedLine=id;return executeAction('march');
    case 'remove':selectedLine=id;return executeAction('cancel_line');
    case 'send':{vibrate([20,40,20]);await pendingChain;const r=await change('send',{order_id:orderId},'Enviado a cocina');if(r)mTab='cuenta';return}
    case 'pay':return executeAction('payments');
    case 'sheet':{const target=b.dataset.id;closeModal();
      if(target==='theme')return setTheme(document.documentElement.dataset.theme==='dark'?'light':'dark');
      if(target.startsWith('nav:'))return go(target.slice(4));
      return executeAction(target)}
  }}
const mobilePrevClick=handleClick;
handleClick=async function(b){if(b.dataset.m){try{await mAction(b)}catch(e){toast(e.message,true)}return}return mobilePrevClick(b)};

/* Actualiza mesas y cuentas cada 10 s en el móvil (otros camareros, cocina lista). */
setInterval(()=>{if(!isMobile()||!state||!currentUser||$('#modal').open||document.activeElement?.tagName==='INPUT'||document.hidden)return;if(['tables','pos','kitchen'].includes(view)&&view!=='kitchen')refresh().catch(()=>{})},10000);
/* Algunos flujos del TPV llaman directamente a renderPos/renderTables: en el móvil, usar la interfaz propia. */
const mobilePrevPos=renderPos,mobilePrevTables=renderTables;
function mEnter(){document.body.classList.remove('m-lite','selling','login-mode');document.body.classList.add('m-app','tpv-mode')}
renderPos=function(){if(isMobile()&&state&&currentUser&&order()){mEnter();return mOrder()}return mobilePrevPos()};
renderTables=function(){if(isMobile()&&state&&currentUser){mEnter();return mTables()}return mobilePrevTables()};

/* Cobro desde el móvil: solo si el administrador lo permite (Otros → Comandero móvil). */
const payPrevDisabled=actionDisabled;
actionDisabled=function(id){if(['payments','split_pay'].includes(id)&&state?.lan&&!state.lan_allow_pay)return true;return payPrevDisabled(id)};

/* ---------- Repetir ronda y «pide la cuenta» (TPV y móvil) ---------- */
function lastRound(o){const sent=o.lines.filter(l=>l.sent_at&&l.menu_role!=='item'&&l.menu_role!=='parent'&&!l.is_weighed);
  if(!sent.length)return o.lines.filter(l=>!l.menu_role&&!l.is_weighed);const last=sent.map(l=>l.sent_at).sort().pop();return sent.filter(l=>l.sent_at===last)}
async function repeatRound(){const o=order();if(!o)return;const items=lastRound(o);if(!items.length){toast('No hay ronda que repetir.',true);return}
  openModal(modalTitle('Repetir ronda','Se vuelven a añadir estos productos, sin enviar todavía.')+`<div class="m-list">${items.map(l=>`<div class="m-row"><span class="m-row-icon">${l.qty}×</span><span class="m-row-main"><b>${esc(l.name)}</b><small>${esc(l.format)}${l.extras.length?' + '+l.extras.map(e=>esc(e.name)).join(', '):''}</small></span><b>${euro(l.qty*(l.base_price??l.price))}</b></div>`).join('')}</div><div class="form-actions"><button class="button secondary" data-close>Cancelar</button><button class="button primary" id="repeat-go">↻ Repetir ronda</button></div>`);
  $('#repeat-go').onclick=async()=>{$('#repeat-go').disabled=true;for(const l of items){await change('add',{order_id:o.id,format_id:l.format_id,qty:l.qty,extras:l.extras.map(e=>e.id).filter(Boolean),note:l.note||''})}closeModal();toast('Ronda repetida: '+items.reduce((s,l)=>s+l.qty,0)+' productos');vibrate(20)}}
async function billRequest(){const o=order();if(!o)return;const on=!o.bill_requested_at;
  const r=await change('bill_request',{order_id:o.id,requested:on},on?'Mesa marcada: pide la cuenta':'Aviso de cuenta retirado');
  if(r&&on&&can('ticket_print')){try{const p=await api('print_document',{kind:'receipt',order_id:o.id});if(p.configured)toast(p.print_warnings?.length?p.print_warnings.join(' · '):'Cuenta impresa',!!p.print_warnings?.length)}catch(e){}}}
const roundPrevDisabled=actionDisabled;
actionDisabled=function(id){const o=order();if(id==='repeat_round')return !o||!can('ticket_add')||!!o.paid||!lastRound(o).length;if(id==='bill_request')return !o||!o.lines.length||!can('ticket_open');return roundPrevDisabled(id)};
const roundPrevExecute=executeAction;
executeAction=async function(id){if(id==='repeat_round'){closeModal();return repeatRound()}if(id==='bill_request'){closeModal();return billRequest()}return roundPrevExecute(id)};

/* =====================================================================
   0.28 · Cobro con pregunta de impresión, cierre con cuentas abiertas,
   productos agotados, plano de mesas en el móvil y cocina fuera del TPV.
   ===================================================================== */

/* La cocina tiene su propia app (/cocina): fuera de la parte de venta. */
views=views.filter(v=>v[0]!=='kitchen');
const k028PrevView=renderView;
renderView=function(){if(view==='kitchen'){view='tables'}return k028PrevView()};

/* ---------- Al cobrar: ¿imprimir ticket? y salir de la mesa ---------- */
function paidDialog(r){const receipt=r.receipt;closeModal();
  const cash=(receipt.payments||[]).filter(p=>p.method==='cash').pop();
  const changeDue=r.change||0;
  openModal(modalTitle('Cuenta cobrada',`${esc(receipt.table_name||'Venta directa')} · ${euro(receipt.total)}`)+`<div class="paid-box">${cash?`<span>Cambio</span><b>${euro(changeDue)}</b>`:'<span>Cobro registrado</span><b>✓</b>'}</div>${r.auto_printed?'<p class="form-note" style="text-align:center">🖨 El ticket se ha impreso automáticamente.</p>':'<p class="paid-question">¿Imprimir el ticket?</p>'}<div class="form-actions paid-actions">${r.auto_printed?'<button class="button primary" data-close>Continuar</button>':`<button class="button secondary" id="paid-no">No imprimir</button><button class="button primary" id="paid-print">🖨 Imprimir ticket</button>`}</div>`);
  const done=()=>{closeModal();orderId=null;selectedLine=null;go('tables')};
  $('#paid-no')&&($('#paid-no').onclick=done);
  $('#paid-print')&&($('#paid-print').onclick=async()=>{const b=$('#paid-print');b.disabled=true;b.textContent='Imprimiendo…';
    try{const p=await api('print_document',{kind:'receipt',order_id:receipt.id});if(!p.configured){closeModal();receiptDialog(receipt);return}toast(p.print_warnings?.length?p.print_warnings.join(' · '):'Ticket impreso',!!p.print_warnings?.length)}catch(e){toast(e.message,true)}done()})}

/* ---------- Cerrar jornada con cuentas abiertas ---------- */
let keepOpenOnClose=false;
const k028PrevApi=api;
api=async function(action,data){if(action==='cash_close'&&keepOpenOnClose&&data)data={...data,keep_open:true};return k028PrevApi(action,data)};
const k028PrevCount=cashCountDialog;
cashCountDialog=async function(wantsClose=false){
  if(!wantsClose){keepOpenOnClose=false;return k028PrevCount(false)}
  await refresh().catch(()=>{});
  const open=state.orders.filter(o=>o.lines.length||o.payments.length);
  if(!open.length){keepOpenOnClose=false;return k028PrevCount(true)}
  const due=open.reduce((s,o)=>s+o.due,0);
  openModal(modalTitle('Hay cuentas abiertas',`${open.length} ${open.length===1?'cuenta pendiente':'cuentas pendientes'} · ${euro(due)}`)+`<p class="form-note">Puedes cobrarlas ahora o cerrar la jornada y dejarlas abiertas para el siguiente turno. Las que queden abiertas aparecerán en el informe Z.</p><div class="close-choice"><button class="service-choice" id="close-pay"><b>€</b><span>Cobrarlas ahora</span><small>Solo verás las cuentas pendientes</small></button><button class="service-choice" id="close-keep"><b>⏭</b><span>Dejarlas abiertas</span><small>Se cobran en la próxima jornada</small></button></div><div class="form-actions"><button class="button secondary" data-close>Cancelar</button></div>`);
  $('#close-keep').onclick=()=>{keepOpenOnClose=true;closeModal();k028PrevCount(true)};
  $('#close-pay').onclick=()=>pendingTicketsDialog()};
function pendingTicketsDialog(){const open=state.orders.filter(o=>o.lines.length||o.payments.length);
  if(!open.length){closeModal();toast('No quedan cuentas pendientes.');keepOpenOnClose=false;return k028PrevCount(true)}
  openModal(modalTitle('Cuentas pendientes de cobro','Toca una cuenta para cobrarla. Cuando no quede ninguna podrás cerrar la jornada.')+`<div class="merge-list">${open.map(o=>`<button class="merge-row" data-pending-pay="${o.id}"><strong>${esc(o.table_name||'Venta directa')}</strong><small>#${o.id} · ${o.lines.length} líneas${o.minutes_open!=null?' · '+minutesLabel(o.minutes_open):''}</small><b>${euro(o.due)}</b></button>`).join('')}</div><div class="form-actions"><button class="button secondary" data-close>Volver</button><button class="button primary" id="pending-close">Cerrar jornada</button></div>`);
  document.querySelectorAll('[data-pending-pay]').forEach(b=>b.onclick=async()=>{orderId=Number(b.dataset.pendingPay);selectedLine=null;closingFlow=true;closeModal();go('pos');await pendingChain;paymentsDialog()});
  $('#pending-close').onclick=()=>{closeModal();cashCountDialog(true)}}
let closingFlow=false;
const k028PrevPaid=paidDialog;
paidDialog=function(r){if(closingFlow){closingFlow=false;closeModal();orderId=null;go('tables');toast('Cuenta cobrada');setTimeout(pendingTicketsDialog,300);return}return k028PrevPaid(r)};

/* ---------- Productos agotados ---------- */
const soldOut=()=>new Set(state.products.filter(p=>p.sold_out).map(p=>p.id));
const k028PrevCards=productCards;
productCards=function(){let html=k028PrevCards();for(const id of soldOut())html=html.replace(`data-product="${id}"`,`data-product="${id}" data-soldout="1" disabled`);return html};
const k028PrevMProducts=mProducts;
mProducts=function(){let html=k028PrevMProducts();for(const id of soldOut())html=html.replace(`data-m="product" data-id="${id}"`,`data-m="product" data-id="${id}" data-soldout="1" disabled`);return html};
function soldOutDialog(){let q='';const draw=()=>{const list=state.products.filter(p=>!q||p.name.toLocaleLowerCase('es').includes(q.toLocaleLowerCase('es')));
  $('#soldout-list').innerHTML=list.map(p=>`<label class="soldout-row ${p.sold_out?'off':''}"><span><b>${esc(p.name)}</b><small>${p.sold_out?'AGOTADO':'Disponible'}</small></span><input type="checkbox" data-soldout-toggle="${p.id}" ${p.sold_out?'checked':''}></label>`).join('');
  document.querySelectorAll('[data-soldout-toggle]').forEach(i=>i.onchange=async()=>{await change('sold_out',{product_id:Number(i.dataset.soldoutToggle),sold_out:i.checked},i.checked?'Marcado como agotado':'Disponible de nuevo');draw()})};
  openModal(modalTitle('Productos agotados','Marca lo que se ha terminado: no se podrá vender hasta que lo desmarques.')+`<div class="search" style="margin-bottom:10px">${svg('search')}<input id="soldout-q" placeholder="Buscar producto…"></div><div id="soldout-list" class="soldout-list"></div><div class="form-actions"><button class="button primary" data-close>Hecho</button></div>`);
  $('#soldout-q').oninput=e=>{q=e.target.value;draw()};draw()}
const k028PrevDisabled=actionDisabled;
actionDisabled=function(id){if(id==='sold_out_manage')return !can('ticket_add');return k028PrevDisabled(id)};
const k028PrevExec=executeAction;
executeAction=async function(id){if(id==='sold_out_manage'){closeModal();return soldOutDialog()}return k028PrevExec(id)};

/* ---------- Móvil: plano de mesas y menú ---------- */
let mTablesMode=(()=>{try{return localStorage.getItem('marchan-m-tables')||'grid'}catch(e){return 'grid'}})();
const k028PrevMTables=mTables;
mTables=function(){k028PrevMTables();
  const chips=document.querySelector('.m-body .m-chips');
  chips?.insertAdjacentHTML('afterend',`<div class="m-seg"><button class="${mTablesMode==='grid'?'active':''}" data-m="tables-mode" data-mode="grid">▦ Lista</button><button class="${mTablesMode==='plan'?'active':''}" data-m="tables-mode" data-mode="plan">⌗ Plano</button></div>`);
  const grid=document.querySelector('.m-table-grid');if(!grid||mTablesMode!=='plan')return;
  const tables=state.tables.filter(t=>t.center_id===mCenter);
  if(!tables.length||!tables.every(t=>t.pos_x!=null&&t.pos_y!=null)){grid.insertAdjacentHTML('beforebegin','<p class="m-hint">Este salón aún no tiene plano. Dibújalo en Administración → Plano de mesas.</p>');return}
  grid.classList.add('m-plan');
  grid.querySelectorAll('[data-m="table"]').forEach(b=>{const t=tables.find(t=>t.id===Number(b.dataset.id));if(!t)return;b.style.left=`min(${t.pos_x}%, calc(100% - 23%))`;b.style.top=`min(${t.pos_y}%, calc(100% - 17%))`;b.classList.add('shape-'+(t.shape||'square'))})};
const k028PrevMAction=mAction;
mAction=async function(b){if(b.dataset.m==='tables-mode'){mTablesMode=b.dataset.mode;try{localStorage.setItem('marchan-m-tables',mTablesMode)}catch(e){}return mTables()}
  if(b.dataset.m==='kitchen'||b.dataset.m==='soldout')return soldOutDialog();
  return k028PrevMAction(b)};
mMenuSheet=function(){mSheet(currentUser.name,[['sold_out_manage','🚫','Productos agotados'],['nav:customers','👥','Clientes'],['clock','⏱',state.clock?.working?'Fichar salida':'Fichar entrada'],['theme','🌓','Tema claro / oscuro'],['switch_user','↪','Cambiar de usuario']])};
