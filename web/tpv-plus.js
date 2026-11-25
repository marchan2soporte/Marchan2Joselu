/* Marchan2 0.24 · Funciones de hostelería en el TPV
   Comensales, clientes, tipo de servicio, invitaciones, descuento de ticket,
   unir cuentas, fichaje, plano de mesas, favoritos y alérgenos. */
const ALLERGEN_CODES={gluten:'GL',crustaceos:'CR',huevo:'HU',pescado:'PE',cacahuete:'CA',soja:'SO',lacteos:'LA',frutos_cascara:'FC',apio:'AP',mostaza:'MO',sesamo:'SE',sulfitos:'SU',altramuces:'AL',moluscos:'MS'};
const SERVICE_ICONS={mesa:'🍽',barra:'🍺',llevar:'🛍',domicilio:'🛵'};
const askedGuests=new Set();
let tablesMode=(()=>{try{return localStorage.getItem('marchan-tables-mode')||'plan'}catch(e){return 'plan'}})();
icons.customers='<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20v-1.5a6.5 6.5 0 0 1 13 0V20"/><circle cx="17.5" cy="9" r="2.5"/><path d="M17 14.2a5 5 0 0 1 4.5 4.8V20"/>';
views.splice(2,0,['customers','Clientes','Tus clientes, por su nombre']);

function allergenChips(list,limit=6){if(!list?.length)return '';const shown=list.slice(0,limit);return `<span class="allergen-chips">${shown.map(a=>`<i title="${esc(state.allergens?.[a]||a)}">${ALLERGEN_CODES[a]||'?'}</i>`).join('')}${list.length>limit?`<i>+${list.length-limit}</i>`:''}</span>`}
function minutesLabel(m){if(m==null)return '';return m<60?`${m} min`:`${Math.floor(m/60)} h ${String(m%60).padStart(2,'0')}`}
function customerById(id){return state.customers?.find(c=>c.id===id)}

/* ---------- Productos: favoritos, más vendidos y alérgenos ---------- */
productCards=function(){
  const q=query.toLocaleLowerCase('es');
  const list=state.products.filter(p=>{const c=state.categories.find(c=>c.id===p.category_id);
    const inFamily=family==='__fav'?p.favorite:family==='__top'?state.best_sellers?.includes(p.id):(!family||c?.parent===family);
    return inFamily&&(!category||p.category_id===category)&&(!q||p.name.toLocaleLowerCase('es').includes(q))});
  if(family==='__top')list.sort((a,b)=>state.best_sellers.indexOf(a.id)-state.best_sellers.indexOf(b.id));
  if(!list.length)return empty(family==='__fav'?'Sin favoritos':'Sin productos',family==='__fav'?'Marca productos como favoritos en Administración → Alérgenos y favoritos.':'Prueba otra categoría o búsqueda.');
  return list.map(p=>{const c=state.categories.find(c=>c.id===p.category_id);const min=Math.min(...p.formats.map(f=>f.price));
    return `<button class="product" data-product="${p.id}" ${!state.permissions?.includes('ticket_add')?'disabled':''} data-parent="${esc(c?.parent)}" style="--tile:${tileColor(p.category_id)}"><span class="product-top"><span class="product-symbol">${esc((p.name||'?').trim().charAt(0))}</span>${p.favorite?'<span class="fav-star" title="Favorito">★</span>':''}</span><strong>${esc(p.name)}</strong>${allergenChips(p.allergens,4)}<span class="price">${p.formats.length>1?'<small>DESDE </small>':''}${euro(min)}${p.weighed?'<small> / KG</small>':''}</span>${p.formats.length>1?`<small class="formats-count">${p.formats.length} formatos</small>`:''}</button>`}).join('')};

/* ---------- Pantalla de venta ---------- */
const plusRenderPos=renderPos;
renderPos=function(){
  plusRenderPos();const o=order();if(!o)return;
  const tabs=$('.family-tabs');
  if(tabs&&!tabs.querySelector('[data-family="__fav"]')){
    const first=tabs.querySelector('[data-family=""]');
    first?.insertAdjacentHTML('afterend',`<button class="pill special ${family==='__fav'?'active':''}" data-family="__fav">★ Favoritos</button>${state.best_sellers?.length?`<button class="pill special ${family==='__top'?'active':''}" data-family="__top">🔥 Más vendidos</button>`:''}`);
    if(family==='__fav'||family==='__top')first?.classList.remove('active');
  }
  const head=$('.ticket-head');
  if(head&&!head.querySelector('.ticket-chips')){
    const cu=customerById(o.customer_id),svc=o.service_type||(o.table_id?'mesa':'');
    head.insertAdjacentHTML('beforeend',`<div class="ticket-chips"><button class="chip" data-plus="guests" title="Comensales">👥 <b>${o.guests||'–'}</b></button><button class="chip ${cu?'filled':''}" data-plus="customer" title="Cliente">${cu?(cu.vip?'⭐ ':'👤 ')+esc(cu.name):'👤 Cliente'}</button><button class="chip" data-plus="service" title="Tipo de servicio">${svc?SERVICE_ICONS[svc]+' '+esc(state.service_types[svc]):'🍽 Servicio'}</button>${o.minutes_open!=null?`<span class="chip ghost">⏱ ${minutesLabel(o.minutes_open)}</span>`:''}</div>`);
    if(cu?.allergens?.length){
      const risky=o.lines.filter(l=>{const p=state.products.find(p=>p.id===l.product_id);return p?.allergens?.some(a=>cu.allergens.includes(a))});
      head.insertAdjacentHTML('beforeend',`<div class="allergy-alert ${risky.length?'danger':''}">⚠ ${esc(cu.name)}: ${cu.allergens.map(a=>esc(state.allergens[a])).join(', ')}${risky.length?` · Revisa: ${risky.map(l=>esc(l.name)).join(', ')}`:''}</div>`);
    }
    if(o.service_type==='domicilio'&&o.delivery_address)head.insertAdjacentHTML('beforeend',`<div class="delivery-line">🛵 ${esc(o.delivery_address)}</div>`);
  }
  document.querySelectorAll('.service-line').forEach(el=>{const l=o.lines.find(l=>l.id===Number(el.dataset.line));if(l?.discount_kind==='invite')el.classList.add('invited')});
  if(o.table_id&&!o.lines.length&&o.guests==null&&!askedGuests.has(o.id)&&!$('#modal').open){askedGuests.add(o.id);guestsDialog(true)}
};

/* ---------- Mesas: plano y lista ---------- */
const plusRenderTables=renderTables;
renderTables=function(){
  plusRenderTables();
  const bar=$('.topbar .pills');
  if(bar&&!$('#tables-mode'))bar.insertAdjacentHTML('afterend',`<div class="segmented" id="tables-mode"><button class="${tablesMode==='plan'?'active':''}" data-tables-mode="plan">Plano</button><button class="${tablesMode==='grid'?'active':''}" data-tables-mode="grid">Lista</button></div>`);
  const grid=$('.table-grid');if(!grid)return;
  const visible=state.tables.filter(t=>t.center_id===center);
  grid.querySelectorAll('[data-table]').forEach(card=>{const t=state.tables.find(t=>t.id===Number(card.dataset.table)),o=state.orders.find(o=>o.table_id===t?.id);
    if(t)card.classList.add('shape-'+(t.shape||'square'));
    if(o){const cu=customerById(o.customer_id);card.insertAdjacentHTML('beforeend',`<div class="table-meta">${o.guests?`<span>👥 ${o.guests}</span>`:''}${o.minutes_open!=null?`<span>⏱ ${minutesLabel(o.minutes_open)}</span>`:''}${cu?`<span class="who">${esc(cu.name)}</span>`:''}</div>`);
      if(o.minutes_open>=90)card.classList.add('long-stay');if(o.lines.some(l=>l.kitchen==='pending'))card.classList.add('cooking')}
    else if(t)card.insertAdjacentHTML('beforeend',`<div class="table-meta"><span>${t.seats||4} plazas</span></div>`)});
  if(tablesMode==='plan'){
    const designed=visible.length&&visible.every(t=>t.pos_x!=null&&t.pos_y!=null);
    grid.classList.add(designed?'floor-plan':'floor-grid');
    if(designed)visible.forEach(t=>{const card=grid.querySelector(`[data-table="${t.id}"]`);if(card){card.style.left=`min(${t.pos_x}%, calc(100% - ${card.classList.contains('shape-long')?210:140}px))`;card.style.top=`min(${t.pos_y}%, calc(100% - 132px))`}});
    else grid.insertAdjacentHTML('afterend','<p class="form-note floor-hint">Diseña la distribución real de la sala en Administración → Plano de mesas.</p>');
  }
  const occupied=state.orders.filter(o=>o.table_id).length,guests=state.orders.reduce((s,o)=>s+(o.guests||0),0),pending=state.orders.reduce((s,o)=>s+o.due,0);
  $('.table-hero .hero-right')?.insertAdjacentHTML('beforeend',`<div class="hero-kpis"><span><b>${guests}</b> comensales</span><span><b>${euro(pending)}</b> pendiente</span><span><b>${state.orders.filter(o=>!o.table_id).length}</b> ventas directas</span></div>`);
  if(!$('#quick-takeaway'))$('#direct-sale')?.insertAdjacentHTML('afterend',`<button class="button secondary" id="quick-takeaway">🛍 Para llevar</button><button class="button secondary" id="quick-delivery">🛵 Domicilio</button>`);
  $('#quick-takeaway')&&($('#quick-takeaway').onclick=()=>directService('llevar'));
  $('#quick-delivery')&&($('#quick-delivery').onclick=()=>directService('domicilio'));
  document.querySelectorAll('.pills [data-order]').forEach(b=>{const o=state.orders.find(o=>o.id===Number(b.dataset.order));if(o?.service_type&&SERVICE_ICONS[o.service_type])b.insertAdjacentHTML('afterbegin',SERVICE_ICONS[o.service_type]+' ')});
};
async function directService(kind){const r=await change('open',{direct:true});if(!r)return;orderId=r.order_id;selectedLine=null;if(kind==='domicilio'){go('pos');serviceDialog('domicilio');return}await change('order_service',{order_id:orderId,service_type:kind});go('pos')}

/* ---------- Clientes (vista del TPV) ---------- */
let customerQuery='';
function customerList(filter,pick){const q=filter.toLocaleLowerCase('es');const list=(state.customers||[]).filter(c=>!q||[c.name,c.phone,c.email,c.tax_id].some(v=>(v||'').toLocaleLowerCase('es').includes(q)));
  return list.length?`<div class="customer-list">${list.map(c=>`<button class="customer-row" data-${pick?'pick-customer':'edit-customer'}="${c.id}"><span class="avatar-circle ${c.vip?'vip':''}">${esc(c.name.slice(0,2))}</span><span class="customer-main"><strong>${esc(c.name)}${c.vip?' <em>VIP</em>':''}</strong><small>${esc([c.phone,c.email].filter(Boolean).join(' · ')||'Sin contacto')}</small>${c.allergens.length?`<small class="warn">⚠ ${c.allergens.map(a=>esc(state.allergens[a])).join(', ')}</small>`:''}</span><span class="customer-stats"><b>${c.visits}</b><small>visitas</small></span><span class="customer-stats"><b>${euro(c.spent)}</b><small>gastado</small></span></button>`).join('')}</div>`:empty('Sin clientes','Crea una ficha con «Nuevo cliente».')}
function renderCustomers(){document.body.classList.remove('selling');$('#main').innerHTML=`<div class="hero compact-hero"><div><span class="welcome-tag">CRM LOCAL</span><h2>Conoce a quien vuelve.</h2><p>Fichas con contacto, alergias, notas y consumo. Asigna el cliente a la cuenta para ver su historial.</p></div><div class="hero-right"><div class="hero-number">${state.customers.length}</div><p>clientes</p></div></div><div class="topbar"><div class="search">${svg('search')}<input id="customer-search" placeholder="Buscar por nombre, teléfono, email o NIF…" value="${esc(customerQuery)}"></div>${can('customer_manage')?'<button class="button primary" id="customer-new">+ Nuevo cliente</button>':''}</div><div id="customer-results">${customerList(customerQuery,false)}</div>`;
  $('#customer-search').oninput=e=>{customerQuery=e.target.value;$('#customer-results').innerHTML=customerList(customerQuery,false)};$('#customer-new')&&($('#customer-new').onclick=()=>customerForm())}
function customerForm(existing,afterSave){const c=existing||{name:'',phone:'',email:'',tax_id:'',address:'',notes:'',allergens:[],vip:false};
  openModal(modalTitle(existing?'Editar cliente':'Nuevo cliente','Datos guardados solo en este equipo.')+`<form id="customer-form" class="form-grid two"><label>NOMBRE<input id="cu-name" required maxlength="120" value="${esc(c.name)}"></label><label>TELÉFONO<input id="cu-phone" inputmode="tel" maxlength="30" value="${esc(c.phone)}"></label><label>EMAIL<input id="cu-email" type="email" maxlength="120" value="${esc(c.email)}"></label><label>NIF / CIF<input id="cu-tax" maxlength="20" value="${esc(c.tax_id)}"></label><label class="span-2">DIRECCIÓN<input id="cu-address" maxlength="200" value="${esc(c.address)}"></label><label class="span-2">NOTAS Y PREFERENCIAS<textarea id="cu-notes" rows="2" maxlength="500">${esc(c.notes)}</textarea></label><fieldset class="span-2 allergen-picker"><legend>ALERGIAS E INTOLERANCIAS</legend>${Object.entries(state.allergens).map(([k,v])=>`<label class="check-chip"><input type="checkbox" value="${k}" ${c.allergens.includes(k)?'checked':''}><span>${ALLERGEN_CODES[k]} · ${esc(v)}</span></label>`).join('')}</fieldset><label class="check-chip span-2"><input type="checkbox" id="cu-vip" ${c.vip?'checked':''}><span>⭐ Cliente VIP</span></label><div class="form-actions span-2"><button type="button" class="button secondary" data-close>Cancelar</button><button class="button primary">Guardar cliente</button></div></form>`);
  $('#customer-form').onsubmit=async e=>{e.preventDefault();const payload={id:existing?.id,name:$('#cu-name').value,phone:$('#cu-phone').value,email:$('#cu-email').value,tax_id:$('#cu-tax').value,address:$('#cu-address').value,notes:$('#cu-notes').value,vip:$('#cu-vip').checked,allergens:[...document.querySelectorAll('.allergen-picker input:checked')].map(i=>i.value)};
    const r=await change('customer_save',payload,'Cliente guardado');if(!r)return;closeModal();if(afterSave)await afterSave(r.customer_id);else if(view==='customers')renderCustomers()}}

/* ---------- Diálogos de la cuenta ---------- */
function guestsDialog(first=false){const o=order();if(!o)return;openModal(modalTitle('Comensales',first?'¿Cuántas personas se sientan en '+(o.table_name||'esta cuenta')+'?':'Número de personas de la cuenta.')+`<div class="guest-grid">${Array.from({length:12},(_,i)=>`<button class="guest-btn ${o.guests===i+1?'active':''}" data-guests="${i+1}">${i+1}</button>`).join('')}</div><label>OTRA CANTIDAD<input id="guests-input" inputmode="numeric" maxlength="3" value="${o.guests||''}"></label>${keypad('guests-input')}<div class="form-actions"><button class="button secondary" data-close>${first?'Omitir':'Cancelar'}</button><button class="button primary" id="guests-save">Guardar</button></div>`);
  const save=async n=>{await change('order_guests',{order_id:o.id,guests:Number(n)||0});closeModal()};
  document.querySelectorAll('[data-guests]').forEach(b=>b.onclick=()=>save(b.dataset.guests));$('#guests-save').onclick=()=>save($('#guests-input').value)}
function customerDialog(){const o=order();if(!o)return;let q='';const draw=()=>{$('#pick-results').innerHTML=customerList(q,true)};
  openModal(modalTitle('Cliente de la cuenta',o.customer_id?'Cliente actual: '+(customerById(o.customer_id)?.name||''):'Busca o crea la ficha del cliente.')+`<div class="topbar"><div class="search">${svg('search')}<input id="pick-search" placeholder="Nombre, teléfono, email o NIF…"></div>${can('customer_manage')?'<button class="button secondary" id="pick-new">+ Nuevo</button>':''}</div><div id="pick-results" class="pick-scroll"></div><div class="form-actions">${o.customer_id?'<button class="button danger" id="pick-clear">Quitar cliente</button>':''}<button class="button secondary" data-close>Cerrar</button></div>`);
  draw();$('#pick-search').oninput=e=>{q=e.target.value;draw()};$('#pick-search').focus();
  $('#pick-clear')&&($('#pick-clear').onclick=async()=>{await change('order_customer',{order_id:o.id,customer_id:null},'Cliente retirado');closeModal()});
  $('#pick-new')&&($('#pick-new').onclick=()=>customerForm(null,async id=>{await change('order_customer',{order_id:o.id,customer_id:id},'Cliente asignado')}))}
function serviceDialog(preset){const o=order();if(!o)return;const cu=customerById(o.customer_id);let chosen=preset||o.service_type||(o.table_id?'mesa':'barra');
  openModal(modalTitle('Tipo de servicio','Cómo se entrega esta cuenta.')+`<div class="service-grid">${Object.entries(state.service_types).map(([k,v])=>`<button class="service-choice ${chosen===k?'active':''}" data-service="${k}"><b>${SERVICE_ICONS[k]}</b><span>${esc(v)}</span></button>`).join('')}</div><label id="address-wrap" ${chosen==='domicilio'?'':'hidden'}>DIRECCIÓN DE ENTREGA<input id="delivery-address" maxlength="200" value="${esc(o.delivery_address||cu?.address||'')}" placeholder="Calle, número, piso…"></label><div class="form-actions"><button class="button secondary" data-close>Cancelar</button><button class="button primary" id="service-save">Guardar</button></div>`);
  document.querySelectorAll('[data-service]').forEach(b=>b.onclick=()=>{chosen=b.dataset.service;document.querySelectorAll('[data-service]').forEach(x=>x.classList.toggle('active',x===b));$('#address-wrap').hidden=chosen!=='domicilio';if(chosen==='domicilio')$('#delivery-address').focus()});
  $('#service-save').onclick=async()=>{const r=await change('order_service',{order_id:o.id,service_type:chosen,address:$('#delivery-address').value});if(r)closeModal()}}
function inviteDialog(){const o=order(),l=line();if(!o)return;let scope=l?'line':'all';const reasons=['Cortesía de la casa','Cliente habitual','Error de cocina o sala','Celebración','Personal'];
  openModal(modalTitle('Invitar','La invitación deja el importe a 0 € y se registra con su motivo.')+`<div class="segmented wide"><button data-scope="line" ${l?'':'disabled'} class="${scope==='line'?'active':''}">Línea seleccionada${l?' · '+esc(l.name):''}</button><button data-scope="all" class="${scope==='all'?'active':''}">Toda la cuenta</button></div><div class="reason-grid">${reasons.map(r=>`<button class="pill" data-reason="${esc(r)}">${esc(r)}</button>`).join('')}</div><label>MOTIVO<input id="invite-reason" maxlength="200" placeholder="Motivo de la invitación"></label><div class="form-actions"><button class="button secondary" data-close>Cancelar</button><button class="button primary" id="invite-save">♡ Invitar</button></div>`);
  document.querySelectorAll('[data-scope]').forEach(b=>b.onclick=()=>{scope=b.dataset.scope;document.querySelectorAll('[data-scope]').forEach(x=>x.classList.toggle('active',x===b))});
  document.querySelectorAll('[data-reason]').forEach(b=>b.onclick=()=>{$('#invite-reason').value=b.dataset.reason;document.querySelectorAll('[data-reason]').forEach(x=>x.classList.toggle('active',x===b))});
  $('#invite-save').onclick=async()=>{const r=await change('invite',{order_id:o.id,reason:$('#invite-reason').value,line_ids:scope==='line'&&l?[l.id]:null},'Invitación registrada');if(r)closeModal()}}
function ticketDiscountDialog(){const o=order();if(!o)return;openModal(modalTitle('Descuento de ticket','Porcentaje sobre todas las líneas de la cuenta (no afecta a invitaciones).')+`<div class="guest-grid">${[5,10,15,20,25,50].map(p=>`<button class="guest-btn" data-percent="${p}">${p}%</button>`).join('')}</div><label>OTRO PORCENTAJE<input id="discount-input" inputmode="decimal" maxlength="6" placeholder="0"></label>${keypad('discount-input',true)}<div class="form-actions"><button class="button danger" id="discount-clear">Quitar descuentos</button><button class="button secondary" data-close>Cancelar</button><button class="button primary" id="discount-save">Aplicar</button></div>`);
  const apply=async v=>{const r=await change('ticket_discount',{order_id:o.id,kind:'percent',value:v},'Descuento aplicado');if(r)closeModal()};
  document.querySelectorAll('[data-percent]').forEach(b=>b.onclick=()=>apply(b.dataset.percent));$('#discount-save').onclick=()=>apply($('#discount-input').value);
  $('#discount-clear').onclick=async()=>{const r=await change('ticket_discount',{order_id:o.id,kind:'clear'},'Descuentos retirados');if(r)closeModal()}}
function mergeDialog(){const o=order();if(!o)return;const others=state.orders.filter(x=>x.id!==o.id&&!x.payments.length);
  openModal(modalTitle('Unir cuentas','Los productos de la cuenta elegida pasan a '+(o.table_name||'esta cuenta')+'.')+(others.length?`<div class="merge-list">${others.map(x=>`<button class="merge-row" data-merge="${x.id}"><strong>${esc(x.table_name||'Venta directa')}</strong><small>Cuenta #${x.id} · ${x.lines.length} líneas${x.guests?' · 👥 '+x.guests:''}</small><b>${euro(x.due)}</b></button>`).join('')}</div>`:empty('No hay otras cuentas','Solo se pueden unir cuentas abiertas sin pagos.'))+'<div class="form-actions"><button class="button secondary" data-close>Cancelar</button></div>');
  document.querySelectorAll('[data-merge]').forEach(b=>b.onclick=async()=>{const r=await change('merge',{order_id:o.id,source_order_id:Number(b.dataset.merge)},'Cuentas unidas');if(r)closeModal()})}
function clockDialog(){const c=state.clock||{};openModal(modalTitle('Control horario',c.working?'Trabajando desde '+new Date(c.since).toLocaleTimeString('es-ES',{hour:'2-digit',minute:'2-digit'}):'Registra tu entrada al empezar el turno.')+`<div class="clock-panel"><div class="clock-big">${new Date().toLocaleTimeString('es-ES',{hour:'2-digit',minute:'2-digit'})}</div><p>${esc(currentUser.name)}</p></div><div class="form-actions"><button class="button secondary" data-close>Cerrar</button><button class="button ${c.working?'danger':'primary'}" id="clock-go">${c.working?'Fichar salida':'Fichar entrada'}</button></div>`);
  $('#clock-go').onclick=async()=>{const r=await change('clock',{kind:c.working?'out':'in'},c.working?'Salida registrada':'Entrada registrada');if(r)closeModal()}}

/* ---------- Acciones configurables ---------- */
const plusActionDisabled=actionDisabled;
actionDisabled=function(id){const o=order(),entry=state.button_layout.catalog.find(a=>a.id===id);
  if(['clock','customers_view'].includes(id))return false;
  if(['guests','customer','service','invite','ticket_discount','merge'].includes(id)){if(entry?.permission&&!can(entry.permission))return true;if(!o)return true;
    if(['invite','ticket_discount'].includes(id))return !o.lines.length||o.payments.length>0;
    if(id==='merge')return o.payments.length>0||!state.orders.some(x=>x.id!==o.id&&!x.payments.length);return false}
  return plusActionDisabled(id)};
const plusExecuteAction=executeAction;
executeAction=async function(id){const map={guests:guestsDialog,customer:customerDialog,service:()=>serviceDialog(),invite:inviteDialog,ticket_discount:ticketDiscountDialog,merge:mergeDialog,clock:clockDialog};
  if(map[id]){if(actionDisabled(id)){toast('Esta acción no está disponible.',true);return}closeModal();await pendingChain;map[id]();return}return plusExecuteAction(id)};

/* ---------- Clics, vistas y cabecera ---------- */
const plusHandleClick=handleClick;
handleClick=async function(b){
  if(b.dataset.plus){return executeAction(b.dataset.plus)}
  if(b.dataset.tablesMode){tablesMode=b.dataset.tablesMode;try{localStorage.setItem('marchan-tables-mode',tablesMode)}catch(e){}renderTables();return}
  if(b.dataset.pickCustomer){const o=order();await change('order_customer',{order_id:o.id,customer_id:Number(b.dataset.pickCustomer)},'Cliente asignado');closeModal();return}
  if(b.dataset.editCustomer){if(!can('customer_manage')){toast('Tu perfil no permite editar clientes.',true);return}customerForm(customerById(Number(b.dataset.editCustomer)));return}
  return plusHandleClick(b)};
const plusRenderView=renderView;
renderView=function(){if(view==='customers'){renderCustomers();return}plusRenderView()};
const plusRender=render;
render=function(){plusRender();if(!state||!currentUser)return;let btn=$('#clock-in');
  if(!btn){$('.header-right .clock')?.insertAdjacentHTML('afterend','<button class="clock-in" id="clock-in"></button>');btn=$('#clock-in');btn.onclick=clockDialog}
  const c=state.clock||{};btn.className='clock-in '+(c.working?'working':'');btn.innerHTML=c.working?`<i></i> En turno · ${minutesLabel(Math.floor((Date.now()-new Date(c.since))/60000))}`:'⏱ Fichar entrada'};
