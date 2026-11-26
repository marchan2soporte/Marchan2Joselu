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
  <div class="m-table-grid">${tables.map(t=>{const o=state.orders.find(o=>o.table_id===t.id);const late=o&&o.minutes_open>=90,cook=o&&o.lines.some(l=>l.kitchen==='pending'),ready=o&&o.lines.some(l=>l.kitchen==='ready'&&l.menu_role!=='parent');
    return `<button class="m-table ${o?'busy':''} ${late?'late':''}" data-m="table" data-id="${t.id}"><span class="m-table-name">${esc(t.name)}</span>${o?`<span class="m-table-total">${euro(o.due)}</span><span class="m-table-meta">${o.guests?'👥'+o.guests+' · ':''}${minutesLabel(o.minutes_open)}</span>${cook?'<i class="m-dot cook" title="En cocina">♨</i>':ready?'<i class="m-dot ready" title="Listo">✓</i>':''}`:`<span class="m-table-free">Libre · ${t.seats||4} pl.</span>`}</button>`}).join('')}</div>
  ${direct.length?`<h2 class="m-h2">Ventas directas</h2><div class="m-list">${direct.map(o=>`<button class="m-row" data-m="order" data-id="${o.id}"><span class="m-row-icon">${({llevar:'🛍',domicilio:'🛵',barra:'🍺'})[o.service_type]||'🧾'}</span><span class="m-row-main"><b>${esc(o.table_name||'Cuenta #'+o.id)}</b><small>${o.lines.length} líneas · ${minutesLabel(o.minutes_open)}</small></span><b>${euro(o.due)}</b></button>`).join('')}</div>`:''}</div>
  <nav class="m-bottom"><button class="m-bottom-btn" data-m="direct"><span>＋</span>Venta rápida</button><button class="m-bottom-btn" data-m="takeaway"><span>🛍</span>Para llevar</button><button class="m-bottom-btn" data-m="kitchen"><span>♨</span>Cocina</button></nav>`}

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
    ${newCount&&can('ticket_send')?`<button class="m-cta" data-m="send">♨ Enviar a cocina <b>${newCount}</b></button>`:o.lines.length&&!actionDisabled('payments')?`<button class="m-cta pay" data-m="pay">€ Cobrar</button>`:`<button class="m-cta ghost" data-m="tab" data-tab="${mTab==='carta'?'cuenta':'carta'}">${mTab==='carta'?'Ver cuenta':'Añadir productos'}</button>`}</nav>`;
  const s=$('#m-search');if(s)s.oninput=e=>{mQuery=e.target.value;$('#m-products').innerHTML=mProducts()};
  if(o.table_id&&!o.lines.length&&o.guests==null&&typeof askedGuests!=='undefined'&&!askedGuests.has(o.id)&&!$('#modal').open){askedGuests.add(o.id);guestsDialog(true)}}

/* ---------- Hojas de opciones ---------- */
function mSheet(title,items){openModal(modalTitle(title)+`<div class="m-sheet">${items.map(([id,icon,label,disabled])=>`<button class="m-sheet-btn" data-m="sheet" data-id="${id}" ${disabled?'disabled':''}><span>${icon}</span>${esc(label)}</button>`).join('')}</div>`)}
function mMoreSheet(){const items=[['guests','👥','Comensales'],['customer','👤','Cliente'],['service','🛵','Tipo de servicio'],['move','⇄','Cambiar de mesa'],['merge','⊕','Unir cuentas'],['invite','♡','Invitar'],['ticket_discount','%','Descuento de ticket'],['receipt','▤','Ver / imprimir cuenta'],['payments','€','Cobrar o dividir'],['cancel_ticket','✕','Cancelar ticket']];
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
