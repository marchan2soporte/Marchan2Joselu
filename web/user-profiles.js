/* Administration editor for permissions supported by Marchan2. */
if(appMode==='admin'){
 const renderEarlier=renderView;
 renderView=function(){if(view==='profiles')renderUserProfiles();else renderEarlier()};
 const openEarlier=openManagementModule;
 openManagementModule=function(name){if(name==='Perfiles de usuario'){go('profiles');return}openEarlier(name)};
 const dialogEarlier=userDialog;
 userDialog=function(id){
  dialogEarlier(id);
  const select=$('#user-profile'),role=$('#user-role');
  const chosen=select.value;
  role.onchange=()=>{
   const profiles=state.user_profiles||[];
   const eligible=profiles.filter(p=>role.value==='admin'?p.name==='Administrador':p.name!=='Administrador');
   select.innerHTML=eligible.map(p=>`<option value="${p.id}">${esc(p.name)}</option>`).join('');
   if(eligible.some(p=>String(p.id)===chosen))select.value=chosen;
  };
 };
}

async function renderUserProfiles(){
 const requestView=view;
 $('#main').innerHTML='<div class="loading-panel">Cargando perfiles…</div>';
 try{
  const data=await api('user_profiles');
  if(view!==requestView)return;
  state.user_profiles=data.profiles;
  $('#main').innerHTML=`<div class="section-title"><div><span class="eyebrow">ADMINISTRACIÓN / EQUIPO</span><h2>Perfiles y permisos</h2><p>La autorización se aplica en el TPV al ejecutar cada operación.</p></div><button class="button primary" id="profile-new">+ Nuevo perfil</button></div><div class="pos-profile-grid">${data.profiles.map(p=>`<article class="panel pos-profile-card"><span class="eyebrow">${p.users} USUARIOS</span><h3>${esc(p.name)}</h3><p>${p.permissions.length} permisos de ${Object.keys(data.catalog).length} disponibles</p><div class="pos-profile-actions"><button class="button secondary" data-profile-edit="${p.id}">${p.name==='Administrador'?'Ver':'Editar'}</button><button class="button secondary" data-profile-copy="${p.id}">Copiar</button>${p.protected?'':`<button class="button danger" data-profile-delete="${p.id}">Eliminar</button>`}</div></article>`).join('')}</div><p class="form-note">Solo aparecen operaciones disponibles en Marchan2. Los permisos de módulos pendientes del archivo de referencia todavía no tienen efecto.</p>`;
  $('#profile-new').onclick=()=>editUserProfile(null,data);
  document.querySelectorAll('[data-profile-edit]').forEach(b=>b.onclick=()=>editUserProfile(data.profiles.find(p=>p.id===Number(b.dataset.profileEdit)),data));
  document.querySelectorAll('[data-profile-copy]').forEach(b=>b.onclick=()=>{const p=data.profiles.find(p=>p.id===Number(b.dataset.profileCopy));editUserProfile({...p,id:null,name:p.name+' copia',protected:0},data)});
  document.querySelectorAll('[data-profile-delete]').forEach(b=>b.onclick=async()=>{try{await api('user_profile_delete',{id:Number(b.dataset.profileDelete)});toast('Perfil eliminado');renderUserProfiles()}catch(e){toast(e.message,true)}});
 }catch(e){if(view===requestView)$('#main').innerHTML=empty('No se pudieron cargar los perfiles',e.message)}
}

function editUserProfile(profile,data){
 const p=profile||{name:'',permissions:[],protected:0};
 const locked=p.name==='Administrador';
 openModal(modalTitle(p.id?'Editar perfil':'Nuevo perfil','Elige las acciones que podrá realizar este perfil en el TPV.')+`<form id="profile-form"><label>NOMBRE<input id="profile-name" required maxlength="80" value="${esc(p.name)}" ${locked?'disabled':''}></label><label class="full">FILTRAR PERMISOS<input id="profile-search" placeholder="Buscar acción…"></label><div class="permission-list">${Object.entries(data.catalog).map(([key,label])=>`<label class="permission-item" data-permission-label="${esc(label.toLocaleLowerCase())}"><input type="checkbox" value="${key}" ${p.permissions.includes(key)?'checked':''} ${locked?'disabled':''}><span>${esc(label)}</span></label>`).join('')}</div><div class="form-actions"><button type="button" class="button secondary" data-close>Volver</button>${locked?'':`<button class="button primary">Guardar perfil</button>`}</div></form>`);
 $('#profile-search').oninput=e=>document.querySelectorAll('.permission-item').forEach(row=>row.hidden=!row.dataset.permissionLabel.includes(e.target.value.toLocaleLowerCase()));
 if(!locked)$('#profile-form').onsubmit=async e=>{e.preventDefault();try{await api('user_profile_save',{id:p.id||undefined,name:$('#profile-name').value,permissions:[...document.querySelectorAll('.permission-item input:checked')].map(x=>x.value)});closeModal();toast('Perfil guardado y aplicado al TPV');renderUserProfiles()}catch(error){toast(error.message,true)}};
}

if(appMode==='tpv'){
 const permitted=key=>state?.permissions?.includes(key);
 const earlierRender=render;
 render=function(){
  earlierRender();
  if(!permitted('kitchen_view'))document.querySelector('[data-view="kitchen"]')?.remove();
  if(view==='pos'){
   const controls={
    'ticket_add':['.product'], 'ticket_quantity':['[data-delta]'],
    'ticket_note':['#line-note'], 'ticket_course':['#course'],
    'ticket_cancel':['#cancel-line'], 'ticket_send':['#prepare'],
    'ticket_march':['#march'], 'ticket_move':['#move'],
    'ticket_print':['#receipt'], 'ticket_pay':['#payments']
   };
   for(const [key,selectors] of Object.entries(controls))if(!permitted(key))
    selectors.forEach(selector=>document.querySelectorAll(selector).forEach(button=>{button.disabled=true;button.title='Tu perfil no permite esta acción'}));
   const selected=order()?.lines.find(item=>item.id===selectedLine);
   if(selected?.kitchen!=='new'&&!permitted('ticket_cancel_prepared')){
    const button=$('#cancel-line');if(button){button.disabled=true;button.title='Tu perfil no permite cancelar líneas preparadas'}
   }
  }
  if(view==='tables'&&!permitted('ticket_open')){
   document.querySelectorAll('#direct-sale,[data-table],[data-order]').forEach(button=>{button.disabled=true;button.title='Tu perfil no permite abrir cuentas'});
  }
 };
 const earlierKitchen=renderKitchen;
 renderKitchen=async function(){await earlierKitchen();if(!permitted('kitchen_ready'))document.querySelectorAll('[data-ready]').forEach(button=>{button.disabled=true;button.title='Tu perfil no permite marcar pedidos como preparados'})};
}
