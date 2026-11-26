/* Marchan2 0.26 · Administración: notas rápidas de preparación. */
managementRoutes['Notas de preparación']='prep_notes';
CARTA_VIEWS.prep_notes='Notas de preparación';
let prepDraft=null;
function adminPrepNotes(){if(!prepDraft)prepDraft=[...(state.prep_notes||[])];
  $('#main').innerHTML=cartaBack('Notas de preparación','Botones rápidos que aparecen al poner una nota a un producto en el TPV y en el comandero móvil. Toca una nota para quitarla, escribe una nueva y pulsa Añadir. Se muestran en el orden de la lista.')+`<section class="panel prep-panel"><div class="quick-notes">${prepDraft.map((n,i)=>`<button class="quick-note active" data-prep-remove="${i}" title="Quitar">${esc(n)} ✕</button>`).join('')||'<p class="muted">Sin notas rápidas.</p>'}</div><form id="prep-form" class="topbar"><input id="prep-new" maxlength="40" placeholder="Nueva nota, p. ej. SIN PICANTE" style="flex:1"><button class="button secondary">Añadir</button></form><div class="form-actions"><button class="button secondary" id="prep-reset">Restaurar cambios</button><button class="button primary" id="prep-save">Guardar notas</button></div></section>`;
  document.querySelectorAll('[data-prep-remove]').forEach(b=>b.onclick=()=>{prepDraft.splice(Number(b.dataset.prepRemove),1);adminPrepNotes()});
  $('#prep-form').onsubmit=e=>{e.preventDefault();const v=$('#prep-new').value.trim().toUpperCase();if(v&&!prepDraft.includes(v))prepDraft.push(v);adminPrepNotes();$('#prep-new').focus()};
  $('#prep-reset').onclick=()=>{prepDraft=null;adminPrepNotes()};
  $('#prep-save').onclick=async()=>{const r=await change('prep_notes_save',{notes:prepDraft},'Notas guardadas');if(r)prepDraft=null}}
const prepRenderView=renderView;
renderView=function(){if(view==='prep_notes'){$('#heading').innerHTML='Notas de preparación<span>.</span>';return adminPrepNotes()}prepRenderView()};
