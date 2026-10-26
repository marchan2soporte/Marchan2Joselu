/* Shared, non-fiscal receipt renderer for TPV and Administration. */
function receiptBody(order,template,company={},catalog={}){
 const taxes={};
 const lineOrder=template?.line_order||'Por defecto';
 const lines=[...order.lines];
 if(lineOrder==='Nombre')lines.sort((a,b)=>a.name.localeCompare(b.name,'es'));
 if(lineOrder==='Categoría'){
  const productCategory=new Map((catalog.products||[]).map(p=>[p.id,p.category_id]));
  const categoryName=new Map((catalog.categories||[]).map(c=>[c.id,c.name]));
  lines.sort((a,b)=>(categoryName.get(productCategory.get(a.product_id))||'').localeCompare(categoryName.get(productCategory.get(b.product_id))||'','es'));
 }
 for(const line of lines){const tax=taxes[line.tax]||(taxes[line.tax]={gross:0});tax.gross+=line.price*line.qty}
 const show=(key,defaultValue=true)=>template?Boolean(template[key]):defaultValue;
 const lineMarkup=lines.map(line=>`<div class="receipt-row"><span>${line.qty} × ${esc(line.name)}</span><b>${euro(line.qty*line.price)}</b></div><div class="receipt-detail">${esc(line.format)}${line.extras.length?' + '+line.extras.map(extra=>esc(extra.name)).join(', '):''}${show('show_unit_price',false)?` · ${euro(line.price)} / ud.`:''}${show('show_item_tax',false)?` · IVA ${line.tax}%`:''}</div>${show('show_notes',false)&&line.note?`<div class="receipt-detail">Nota: ${esc(line.note)}</div>`:''}`).join('');
 const paymentMarkup=order.payments.map(payment=>`<div class="receipt-row"><span>${payment.method==='cash'?'EFECTIVO':'TARJETA'}${show('show_user')&&payment.user_name?' · '+esc(payment.user_name):''}</span><b>${euro(payment.amount)}</b></div>${show('show_tips')&&payment.tip?`<div class="receipt-row"><span>Propina</span><b>${euro(payment.tip)}</b></div>`:''}${payment.method==='cash'?`<div class="receipt-row"><span>Recibido ${euro(payment.tendered)}</span><span>Cambio ${euro(payment.change_due)}</span></div>`:''}`).join('');
 const heading=template?.header||company.trade_name||company.legal_name||'MARCHAN2';
 const date=new Date(order.paid_at||order.created).toLocaleString('es-ES',show('show_time')?undefined:{year:'numeric',month:'numeric',day:'numeric'});
 return `<h2>${esc(heading).replaceAll('\n','<br>')}</h2>${template?.header_image?`<img class="receipt-image" src="${esc(template.header_image)}" alt="Imagen de cabecera">`: ''}${company.tax_id?`<p>CIF: ${esc(company.tax_id)}</p>`:''}${company.address?`<p>${esc(company.address)}</p>`:''}<p>DEMOSTRACIÓN · NO FISCAL</p>${order.series_number?`<p>Referencia interna: ${esc(order.series_name)}-${order.series_number}</p>`:''}<p>${show('show_order_id')?`Cuenta #${String(order.id).padStart(4,'0')}`:''}${show('show_location')?` · ${esc(order.table_name||'VENTA DIRECTA')}`:''}<br>${esc(date)}</p>${show('show_unpaid')&&order.due>0?'<p class="receipt-warning">PENDIENTE DE COBRO</p>':''}<hr>${lineMarkup}<hr><div class="receipt-row"><b>TOTAL PRODUCTOS</b><b>${euro(order.total)}</b></div>${show('show_tax')?Object.entries(taxes).map(([rate,tax])=>`<div class="receipt-row"><span>IVA ${rate}% incluido</span><span>${euro(tax.gross-Math.round(tax.gross/(1+Number(rate)/100)))}</span></div>`).join(''):''}<hr>${paymentMarkup}<div class="receipt-row"><b>PENDIENTE</b><b>${euro(order.due)}</b></div><hr><p>${esc(template?.footer||'Gracias por compartir mesa.\nMarchan2 · JoseluIA').replaceAll('\n','<br>')}</p>${template?.footer_image?`<img class="receipt-image" src="${esc(template.footer_image)}" alt="Imagen del pie">`: ''}`;
}
function receiptDialog(order){
 const template=state?.ticket_template;
 const title=order.status==='paid'?'Cuenta cobrada':'Detalle de la cuenta';
 openModal(modalTitle(title)+`<div class="receipt">${receiptBody(order,template,state?.company||{},state||{})}</div><div class="form-actions"><button class="button secondary" data-close>Volver</button><button class="button primary" id="print-receipt">Imprimir prueba</button></div>`);
 const base=template?.base||'80 mm';
 $('#modal').dataset.paper=base==='A4'?'A4':base.startsWith('56 mm')?'56 mm':'80 mm';
 $('#print-receipt').onclick=async()=>{try{const result=await api('print_document',{kind:'receipt',order_id:order.id});if(!result.configured){window.print();return}toast(result.print_warnings?.length?result.print_warnings.join(' · '):'Ticket enviado a la impresora seleccionada',!!result.print_warnings?.length)}catch(error){toast(error.message,true)}};
}
